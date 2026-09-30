# -*- coding: utf-8 -*-

"""A catalog of the steps available for building flowcharts.

The catalog answers the questions a programmer -- or an AI system -- needs answered to
build a flowchart without the graphical editor: which steps exist, what they are
called, which sub-steps a step with a subflowchart accepts, and what parameters each
step has, with their kinds, defaults, units, choices and help text.

It is built at run time from the installed plug-ins, so it always matches what the
flowchart will run with.
"""

import difflib
import logging
import re

import seamm

logger = logging.getLogger(__name__)


class StepNotFoundError(KeyError):
    """No step with the given name is available."""

    def __str__(self):
        # KeyError quotes its argument; show the message as written.
        return str(self.args[0])


def normalize(name):
    """Normalize a name for loose matching: case, spaces, underscores, hyphens.

    Parameters
    ----------
    name : str
        The name, e.g. "smiles_string" or "From SMILES".

    Returns
    -------
    str
        The normalized name, e.g. "smiles string" or "from smiles".
    """
    return re.sub(r"[\s_\-]+", " ", str(name)).strip().casefold()


def suggestions(name, choices, n=5):
    """Close matches for a name among choices, for error messages.

    Parameters
    ----------
    name : str
        The name that did not match.
    choices : iterable of str
        The valid names.
    n : int
        The maximum number of suggestions.

    Returns
    -------
    [str]
        The closest valid names, best first.
    """
    choices = list(choices)
    by_normal = {normalize(c): c for c in choices}
    hits = difflib.get_close_matches(normalize(name), list(by_normal), n=n, cutoff=0.5)
    result = [by_normal[h] for h in hits]
    # Also offer names containing the given text, e.g. "Energy" -> "Single-Point ..."
    key = normalize(name)
    for normal, choice in by_normal.items():
        if len(result) >= n:
            break
        if key and key in normal and choice not in result:
            result.append(choice)
    return result


def enumeration_of(parameter):
    """The choices of a parameter as a tuple, or None if it has none.

    A plug-in that writes ``("current")`` rather than ``("current",)`` gives a string;
    treat that as the single choice rather than a sequence of letters.
    """
    enumeration = parameter.enumeration
    if enumeration is None:
        return None
    if isinstance(enumeration, str):
        return (enumeration,)
    enumeration = tuple(enumeration)
    return enumeration if len(enumeration) > 0 else None


def parameter_info(parameter):
    """The description of a single parameter, as plain data.

    Parameters
    ----------
    parameter : seamm.Parameter
        The parameter.

    Returns
    -------
    dict
        kind, default, units, enumeration, description and help.
    """
    enumeration = enumeration_of(parameter)
    if enumeration is not None:
        enumeration = list(enumeration)
    units = parameter.default_units
    return {
        "kind": parameter.kind,
        "default": parameter.default,
        "units": units if units else None,
        "enumeration": enumeration if enumeration else None,
        "description": parameter.description,
        "help": parameter.help_text,
    }


class Catalog(object):
    """The steps that can go in one flowchart (or subflowchart).

    Parameters
    ----------
    flowchart : seamm.Flowchart, optional
        The flowchart whose plug-ins to describe. Its plug-in namespace decides which
        steps are available: the main flowchart's, or a subflowchart's, such as
        ORCA's sub-steps. Nodes are created in this flowchart only temporarily, to
        read their parameters, and are never added to it. By default a new main
        flowchart is created, which loads every installed plug-in.
    """

    def __init__(self, flowchart=None):
        if flowchart is None:
            flowchart = seamm.Flowchart()
        self.flowchart = flowchart
        self._descriptions = None
        self._titles = None
        self._nodes = {}
        self._subcatalogs = {}

    @property
    def namespace(self):
        """The plug-in namespace, e.g. 'org.molssi.seamm' or 'org.molssi.seamm.orca'."""
        return self.flowchart.plugin_manager.namespace

    @property
    def plugin_manager(self):
        """The plug-in manager of the flowchart."""
        return self.flowchart.plugin_manager

    # -------------------------------------------------------------------------
    # Listing
    # -------------------------------------------------------------------------

    def extensions(self):
        """The extension names of all the steps, which uniquely identify them.

        Returns
        -------
        [str]
        """
        return sorted(self.plugin_manager.manager.names())

    def descriptions(self):
        """The name, group and description of each step, by extension name.

        Returns
        -------
        {str: dict}
        """
        if self._descriptions is None:
            self._descriptions = {}
            for extension in self.extensions():
                data = self.plugin_manager.get(extension).description()
                self._descriptions[extension] = {
                    "name": data.get("name", extension),
                    "group": data.get("group", ""),
                    "description": data.get("description", ""),
                }
        return self._descriptions

    def steps(self):
        """A summary of every step, sorted by group and name.

        Returns
        -------
        [dict]
            extension, name, group and description of each step.
        """
        result = [
            {"extension": extension, **data}
            for extension, data in self.descriptions().items()
        ]
        return sorted(result, key=lambda x: (x["group"], x["name"]))

    # -------------------------------------------------------------------------
    # Finding steps
    # -------------------------------------------------------------------------

    def resolve(self, name):
        """The extension name of a step given any of its names.

        A step may be named by its extension name ("FromSMILESStep"), its name in the
        editor's menu ("from SMILES") or its default title. Matching ignores case,
        spaces, underscores and hyphens.

        Parameters
        ----------
        name : str
            The name of the step.

        Returns
        -------
        str
            The extension name.

        Raises
        ------
        StepNotFoundError
            If no step has that name. The message suggests close matches.
        """
        extensions = self.extensions()
        if name in extensions:
            return name

        key = normalize(name)
        for extension in extensions:
            if normalize(extension) == key:
                return extension
        for extension, data in self.descriptions().items():
            if normalize(data["name"]) == key:
                return extension
        for extension, title in self.titles().items():
            if normalize(title) == key:
                return extension

        names = set(extensions)
        names.update(d["name"] for d in self.descriptions().values())
        close = suggestions(name, names)
        text = f"There is no step '{name}'"
        if self.namespace != "org.molssi.seamm":
            text += f" in {self.namespace}"
        if close:
            text += ". Did you mean: " + ", ".join(repr(c) for c in close) + "?"
        else:
            text += ". Available steps: " + ", ".join(extensions)
        raise StepNotFoundError(text)

    def titles(self):
        """The default title of each step, by extension name.

        Returns
        -------
        {str: str}
        """
        if self._titles is None:
            self._titles = {}
            for extension in self.extensions():
                try:
                    self._titles[extension] = self.node(extension).title
                except Exception as e:
                    logger.warning(f"Could not create a '{extension}' node: {e}")
        return self._titles

    # -------------------------------------------------------------------------
    # Describing steps
    # -------------------------------------------------------------------------

    def node(self, name):
        """A scratch node for a step, used to read its parameters and title.

        The node is created in the catalog's flowchart but not added to it.

        Parameters
        ----------
        name : str
            Any name of the step.

        Returns
        -------
        seamm.Node
        """
        extension = self.resolve(name) if name not in self._nodes else name
        if extension not in self._nodes:
            self._nodes[extension] = self.flowchart.create_node(extension)
        return self._nodes[extension]

    def has_subflowchart(self, name):
        """Whether a step holds sub-steps in a subflowchart, like ORCA or MOPAC."""
        return isinstance(
            getattr(self.node(name), "subflowchart", None), seamm.Flowchart
        )

    def subcatalog(self, name):
        """The catalog of sub-steps for a step with a subflowchart.

        Parameters
        ----------
        name : str
            Any name of the step, e.g. "ORCA".

        Returns
        -------
        Catalog
            The catalog of its sub-steps.

        Raises
        ------
        ValueError
            If the step has no subflowchart.
        """
        extension = self.resolve(name)
        if extension not in self._subcatalogs:
            node = self.node(extension)
            subflowchart = getattr(node, "subflowchart", None)
            if not isinstance(subflowchart, seamm.Flowchart):
                raise ValueError(f"The step '{extension}' has no sub-steps.")
            self._subcatalogs[extension] = Catalog(subflowchart)
        return self._subcatalogs[extension]

    def find(self, path):
        """The catalog and extension name for a step given by a path.

        Parameters
        ----------
        path : str
            A step name, or a path through subflowcharts such as "ORCA/Energy".

        Returns
        -------
        (Catalog, str)
            The catalog holding the step, and its extension name.
        """
        parts = [p.strip() for p in path.split("/") if p.strip() != ""]
        if len(parts) == 0:
            raise StepNotFoundError("No step given")
        catalog = self
        for part in parts[:-1]:
            catalog = catalog.subcatalog(part)
        return catalog, catalog.resolve(parts[-1])

    def describe(self, path):
        """Everything needed to use a step, as plain data.

        Parameters
        ----------
        path : str
            A step name, or a path such as "ORCA/Energy".

        Returns
        -------
        dict
            extension, name, group, description, title, namespace, the parameters by
            name, and the sub-steps (extension names) if the step has a subflowchart.
        """
        catalog, extension = self.find(path)
        node = catalog.node(extension)
        result = {
            "extension": extension,
            **catalog.descriptions()[extension],
            "title": node.title,
            "namespace": catalog.namespace,
            "parameters": {},
        }
        if node.parameters is not None:
            for key, parameter in node.parameters.items():
                result["parameters"][key] = parameter_info(parameter)
        if catalog.has_subflowchart(extension):
            sub = catalog.subcatalog(extension)
            result["substep namespace"] = sub.namespace
            result["substeps"] = sub.extensions()
        return result
