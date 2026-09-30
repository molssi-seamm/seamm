# -*- coding: utf-8 -*-

"""Build flowcharts programmatically, without the graphical editor.

A flowchart is built from the top down, one step after another, as it will run::

    from seamm.builder import FlowchartBuilder

    fb = FlowchartBuilder(title="Water optimization")
    fb.add("Model Chemistry", model_chemistry="ORCA:DFT@B3LYP/bse:def2-SVPD")
    fb.add("from SMILES", smiles_string="O")
    orca = fb.add("ORCA")
    orca.add("Optimization")
    orca.add("Energy", extra_keywords="TightSCF")
    with fb.loop(type="For", variable="i", start=1, end=10) as body:
        body.add("Custom Python", ...)
    fb.write("water.flow")

Steps are named by their extension name, as in the editor's step menu, by the name in
their description, or by their default title. Parameters are given as keyword arguments,
with underscores for the spaces in their names, or as a dict. Every value is checked
when it is set: the parameter must exist, a choice must be one of the allowed ones, a
number must be a number, and units must match -- unless the value is a variable or
expression such as ``$SMILES``.

The builder makes the Join node that a loop needs, sets the types of the edges, and
lays out the steps as the editor's "clean layout" does, so the editor opens the result
as if it had been drawn by hand.
"""

import contextlib
import logging

import re

from seamm_util import Q_, ureg

import seamm
from .catalog import Catalog, choices_are_strict, enumeration_of, normalize, suggestions
from .layout import layout

logger = logging.getLogger(__name__)


class FlowchartBuildError(ValueError):
    """A step or parameter value that cannot go in the flowchart."""


# A number followed by units, e.g. "300 K" or "-1.5e-3 kcal/mol"
_number_and_units = re.compile(
    r"^\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)"
    r"\s*(?![eE][-+]?\d)([A-Za-z\u00b5\u03bc\u00c5\u00b0%].*?)\s*$"
)


def _choices_text(choices, value, n=40):
    """The allowed choices for an error message, shortened if there are many."""
    choices = [str(c) for c in choices]
    close = suggestions(value, choices)
    if len(choices) <= n:
        text = "Choose one of: " + ", ".join(repr(c) for c in choices)
    else:
        text = f"There are {len(choices)} choices"
    if close:
        text += ". Closest: " + ", ".join(repr(c) for c in close)
    return text


def is_expression(value):
    """Whether a value is a variable or expression, such as '$SMILES' or '=2*$n'."""
    return (
        isinstance(value, str)
        and len(value) > 0
        and value[0] in ("$", "=")
        and value != "=="
    )


def _is_number(value, integer=False):
    """Whether a value is a number, or text that is one; optionally an integer."""
    if isinstance(value, bool):
        return False
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            return False
    if not isinstance(value, (int, float)):
        return False
    return not integer or float(value).is_integer()


def check_value(parameter, value, name="parameter", units=None):
    """Check and normalize a value for a parameter.

    Parameters
    ----------
    parameter : seamm.Parameter
        The parameter.
    value : any
        The value: a string, number, bool, list or dict as the parameter needs; a
        (value, units) pair or Pint quantity for a parameter with units; or a variable
        or expression such as ``$SMILES``.
    name : str
        The parameter's name, for error messages.
    units : str, optional
        Units given separately.

    Returns
    -------
    (value, units)
        The value as the editor would store it, and the units (None to keep the
        parameter's current units).

    Raises
    ------
    FlowchartBuildError
        If the value is not valid for the parameter.
    """
    kind = parameter.kind
    enumeration = enumeration_of(parameter)
    has_units = parameter.default_units not in (None, "")

    # Split off units
    if isinstance(value, Q_):
        value, units = value.magnitude, str(value.units)
    elif isinstance(value, (tuple, list)) and len(value) == 2 and has_units:
        value, units = value
    elif (
        isinstance(value, tuple)
        and len(value) == 2
        and isinstance(value[1], str)
        and kind not in ("list", "periodic table", "dictionary")
    ):
        value, units = value
    elif (
        has_units
        and isinstance(value, str)
        and not is_expression(value)
        and not (enumeration and value in enumeration)
    ):
        match = _number_and_units.match(value)
        if match is not None:
            value, units = match.group(1), match.group(2)

    if units is not None:
        if not has_units:
            raise FlowchartBuildError(
                f"'{name}' does not take units, but got '{units}'"
            )
        # Any conversion SEAMM's unit registry allows, including those through its
        # contexts, e.g. kcal/mol to K or to wavenumbers, as the editor allows.
        try:
            ureg.Unit(units)
        except Exception:
            raise FlowchartBuildError(f"'{units}' are not units that SEAMM knows")
        try:
            Q_(1.0, units).to(parameter.default_units)
        except Exception:
            raise FlowchartBuildError(
                f"The units '{units}' for '{name}' cannot be converted to its "
                f"default units '{parameter.default_units}'"
            )

    if is_expression(value):
        if value[0] == "=":
            # A Python expression, evaluated with the variables as bare names. Check
            # the syntax now rather than when the job runs.
            try:
                compile(value[1:], "<expression>", "eval")
            except SyntaxError as e:
                text = (
                    f"The expression {value!r} for '{name}' is not valid Python: "
                    f"{e.msg}"
                )
                if "$" in value:
                    text += (
                        ". In an '=' expression, use variables by their bare names, "
                        "e.g. '=2 * n' rather than '=2 * $n'"
                    )
                raise FlowchartBuildError(text)
        return value, units

    # A Python bool for a yes/no choice, whatever its kind
    if isinstance(value, bool) and enumeration:
        wanted = "yes" if value else "no"
        for choice in enumeration:
            if normalize(choice) == wanted:
                return choice, units

    if kind == "boolean":
        if isinstance(value, bool):
            value = "yes" if value else "no"
        if enumeration and choices_are_strict(parameter):
            for choice in enumeration:
                if normalize(choice) == normalize(value):
                    return choice, units
            if normalize(value) in ("true", "on", "1"):
                return enumeration[0], units
            if normalize(value) in ("false", "off", "0"):
                return enumeration[-1], units
            raise FlowchartBuildError(
                f"'{value}' is not valid for '{name}'. "
                + _choices_text(enumeration, value)
            )
        return value, units

    if kind in ("enum", "enumeration"):
        if enumeration and choices_are_strict(parameter):
            if value in enumeration:
                return value, units
            for choice in enumeration:
                if normalize(choice) == normalize(value):
                    return choice, units
            raise FlowchartBuildError(
                f"'{value}' is not valid for '{name}'. "
                + _choices_text(enumeration, value)
            )
        return value, units

    if kind in ("integer", "int", "float"):
        if enumeration and value in enumeration:
            return value, units
        integer = kind != "float"
        if not _is_number(value, integer):
            text = f"'{name}' needs {'an integer' if integer else 'a number'}"
            text += f", not {value!r}"
            if enumeration:
                text += ", or one of " + ", ".join(repr(c) for c in enumeration)
            raise FlowchartBuildError(text)
        if integer and isinstance(value, float):
            value = int(value)
        # Kept as given: the editor stores text, defaults are often numbers, and
        # Parameter.get() converts either.
        return value, units

    if kind in ("list", "periodic table"):
        if not isinstance(value, (list, str)):
            raise FlowchartBuildError(f"'{name}' needs a list, not {value!r}")
        return value, units

    if kind == "dictionary":
        if not isinstance(value, (dict, str)):
            raise FlowchartBuildError(f"'{name}' needs a dict, not {value!r}")
        return value, units

    # string, str, special and anything else: stored as given
    return value, units


def set_parameters(node, params=None, **kwargs):
    """Set the parameters of a node, checking each value.

    Parameters
    ----------
    node : seamm.Node
        The node.
    params : dict, optional
        Parameter values by their exact names, e.g. {"smiles string": "O"}.
    kwargs
        Parameter values by name with underscores for spaces, e.g. smiles_string="O".
        Names are matched ignoring case, spaces, underscores and hyphens.
    """
    values = {}
    if params is not None:
        values.update(params)
    values.update(kwargs)
    if len(values) == 0:
        return
    if node.parameters is None:
        raise FlowchartBuildError(f"The step '{node.title}' has no parameters.")

    P = node.parameters
    by_normal = {normalize(key): key for key in P}
    for name, value in values.items():
        key = name if name in P else by_normal.get(normalize(name))
        if key is None:
            close = suggestions(name, P.keys())
            text = f"The step '{node.title}' has no parameter '{name}'"
            if close:
                text += ". Did you mean: " + ", ".join(repr(c) for c in close) + "?"
            raise FlowchartBuildError(text)
        parameter = P[key]
        value, units = check_value(parameter, value, name=key)
        parameter.value = value
        if units is not None:
            parameter.units = units


class Step(object):
    """A step that has been added to a flowchart.

    Parameters
    ----------
    node : seamm.Node
        The node for the step.
    catalog : Catalog
        The catalog the step came from.
    """

    def __init__(self, node, catalog):
        self.node = node
        self._catalog = catalog
        self._sequence = None

    def __repr__(self):
        return f"Step({self.node.title!r})"

    @property
    def title(self):
        """The title of the step."""
        return self.node.title

    @property
    def extension(self):
        """The extension name of the step."""
        return self.node.extension

    @property
    def parameters(self):
        """The step's control parameters (a seamm.Parameters), or None."""
        return self.node.parameters

    def set(self, params=None, **kwargs):
        """Set parameters of the step, checking each value. See set_parameters()."""
        set_parameters(self.node, params, **kwargs)
        return self

    @property
    def has_substeps(self):
        """Whether this step holds sub-steps, like ORCA or MOPAC."""
        return isinstance(getattr(self.node, "subflowchart", None), seamm.Flowchart)

    @property
    def sequence(self):
        """The sequence of sub-steps of a step with a subflowchart."""
        if self._sequence is None:
            if not self.has_substeps:
                raise FlowchartBuildError(f"The step '{self.title}' has no sub-steps.")
            catalog = self._catalog.subcatalog(self.node.extension)
            flowchart = self.node.subflowchart
            self._sequence = Sequence(catalog, flowchart, flowchart.get_node("1"))
        return self._sequence

    def add(self, step, params=None, **kwargs):
        """Add a sub-step, e.g. an Energy step to ORCA. See Sequence.add()."""
        return self.sequence.add(step, params, **kwargs)

    def loop(self, params=None, **kwargs):
        """Add a loop of sub-steps. See Sequence.loop()."""
        return self.sequence.loop(params, **kwargs)


class Sequence(object):
    """A sequence of steps that run one after another.

    The main flowchart, the sub-steps of a step like ORCA, and the body of a loop are
    each a sequence. New steps go after the last one.

    Parameters
    ----------
    catalog : Catalog
        The catalog of steps that may be added.
    flowchart : seamm.Flowchart
        The flowchart the steps go in.
    after : seamm.Node
        The node the first step follows.
    edge_subtype : str
        The kind of the edge to the first step: "next", or "loop" for a loop body.
    """

    def __init__(self, catalog, flowchart, after, edge_subtype="next"):
        self.catalog = catalog
        self.flowchart = flowchart
        self._last = after
        self._edge_subtype = edge_subtype
        self.steps = []

    def add(self, step, params=None, **kwargs):
        """Add a step after the last one.

        Parameters
        ----------
        step : str
            Any name of the step: its extension name (as in the editor's step menu),
            the name in its description, or its default title.
        params : dict, optional
            Parameter values by exact name.
        kwargs
            Parameter values by name with underscores for spaces.

        Returns
        -------
        Step
            The new step. For a step with sub-steps, use its add() to add them.
        """
        extension = self.catalog.resolve(step)
        node = self.flowchart.create_node(extension)
        set_parameters(node, params, **kwargs)
        self._append(node)
        result = Step(node, self.catalog)
        self.steps.append(result)
        return result

    def _append(self, node):
        """Add a node to the flowchart and connect it after the last one."""
        self.flowchart.add_node(node)
        self.flowchart.add_edge(
            self._last, node, edge_type="execution", edge_subtype=self._edge_subtype
        )
        self._last = node
        self._edge_subtype = "next"

    @contextlib.contextmanager
    def loop(self, params=None, **kwargs):
        """Add a loop, whose body is built inside a with block.

        ::

            with fb.loop(type="For", variable="i", start=1, end=10) as body:
                body.add(...)

        Parameters
        ----------
        params : dict, optional
            The Loop step's parameter values by exact name.
        kwargs
            Its parameter values by name with underscores for spaces.

        Yields
        ------
        Sequence
            The body of the loop.
        """
        join = self.flowchart.create_node(self.catalog.resolve("Join"))
        self._append(join)
        loop = self.add("Loop", params, **kwargs)
        body = Sequence(self.catalog, self.flowchart, loop.node, edge_subtype="loop")
        body.loop_step = loop
        yield body
        if len(body.steps) == 0:
            raise FlowchartBuildError("The body of a loop needs at least one step.")
        # The end of the body goes back to the Join in front of the loop
        self.flowchart.add_edge(
            body._last, join, edge_type="execution", edge_subtype=body._edge_subtype
        )
        # and the flowchart carries on from the loop's exit.
        self._last = loop.node
        self._edge_subtype = "exit"


class FlowchartBuilder(Sequence):
    """Build a flowchart step by step.

    Parameters
    ----------
    title : str
        The title of the flowchart.
    description : str
        A description of the flowchart.
    keywords : [str], optional
        Keywords for the flowchart's metadata.
    catalog : Catalog, optional
        The catalog of steps. By default one is created for the flowchart.
    flowchart : seamm.Flowchart, optional
        An empty flowchart to build in. By default a new one is created, which loads
        all the installed plug-ins.
    """

    def __init__(
        self, title="", description="", keywords=None, catalog=None, flowchart=None
    ):
        if flowchart is None:
            flowchart = seamm.Flowchart(name=title, description=description)
        else:
            if len(list(flowchart)) != 1:
                raise ValueError("The flowchart to build in must be empty")
            flowchart.metadata["title"] = title
            flowchart.metadata["description"] = description
        if keywords is not None:
            flowchart.metadata["keywords"] = list(keywords)
        if catalog is None:
            catalog = Catalog(flowchart)
        elif catalog.namespace != flowchart.plugin_manager.namespace:
            raise ValueError("The catalog must be for the main flowchart")
        super().__init__(catalog, flowchart, flowchart.get_node("1"))

    @property
    def metadata(self):
        """The flowchart's metadata: title, description, keywords, creators, ..."""
        return self.flowchart.metadata

    def validate(self):
        """Check the flowchart as a whole.

        Returns
        -------
        [str]
            A description of each problem found; empty if none.
        """
        return validate(self.flowchart)

    def layout(self):
        """Lay out the steps as the editor's clean layout does."""
        layout(self.flowchart)

    def _finish(self, check):
        """Validate if asked, raising FlowchartBuildError on problems, and lay out."""
        if check:
            problems = self.validate()
            if problems:
                raise FlowchartBuildError(
                    "The flowchart has problems:\n  " + "\n  ".join(problems)
                )
        from .format3 import restore_tables

        restore_tables(self.flowchart)
        self.layout()

    def to_text(self, check=True, format="3.0"):
        """The flowchart as the text of a .flow file.

        Parameters
        ----------
        check : bool
            Validate first and raise FlowchartBuildError if there are problems.
        format : str
            The flowchart format, "3.0" (the default) or "2.0".
        """
        self._finish(check)
        return self.flowchart.to_text(format=format)

    def write(self, path, check=True, format="3.0"):
        """Write the flowchart to a .flow file, which is made executable.

        Parameters
        ----------
        path : str or pathlib.Path
            The file to write.
        check : bool
            Validate first and raise FlowchartBuildError if there are problems.
        format : str
            The flowchart format, "3.0" (the default) or "2.0".
        """
        self._finish(check)
        self.flowchart.write(str(path), format=format)


def _main_line(flowchart):
    """The nodes of a flowchart in execution order, including loop bodies."""
    nodes = []
    seen = set()

    def walk(node):
        while node is not None and node not in seen:
            seen.add(node)
            nodes.append(node)
            following = None
            for edge in flowchart.edges(node, direction="out"):
                if edge.edge_type != "execution":
                    continue
                if edge.edge_subtype == "loop":
                    walk(edge.node2)
                elif edge.edge_subtype in ("next", "exit"):
                    following = edge.node2
            node = following

    walk(flowchart.get_node("1"))
    return nodes


def validate(flowchart):
    """Check a flowchart as a whole, beyond the individual parameter values.

    Checks that a step using the model chemistry (its "use model chemistry"
    parameter is "yes") comes after a Model Chemistry step; for a sub-step, that the
    Model Chemistry step comes before the step holding it.

    Parameters
    ----------
    flowchart : seamm.Flowchart
        The main flowchart.

    Returns
    -------
    [str]
        A description of each problem found; empty if none.
    """
    problems = []

    def uses_model_chemistry(node):
        P = node.parameters
        if P is None or "use model chemistry" not in P:
            return False
        value = P["use model chemistry"].value
        return not is_expression(value) and normalize(value) in ("yes", "true")

    def check(flowchart, have_model_chemistry, where):
        for node in _main_line(flowchart):
            if node.extension == "Model Chemistry":
                have_model_chemistry = True
            elif uses_model_chemistry(node) and not have_model_chemistry:
                problems.append(
                    f"'{where}{node.title}' uses the model chemistry, but no Model "
                    "Chemistry step comes before it. Add one, or set 'use model "
                    "chemistry' to 'no' and choose the method explicitly."
                )
            subflowchart = getattr(node, "subflowchart", None)
            if isinstance(subflowchart, seamm.Flowchart):
                check(subflowchart, have_model_chemistry, f"{where}{node.title}/")
        return have_model_chemistry

    check(flowchart, False, "")
    return problems
