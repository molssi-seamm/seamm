# -*- coding: utf-8 -*-

"""Flowchart specs: short YAML descriptions of flowcharts for people and AI to write.

A spec lists the steps and only the parameters that differ from the defaults::

    title: Water optimization
    steps:
    - Model Chemistry: {model chemistry: "ORCA:DFT@B3LYP/bse:def2-SVPD"}
    - from SMILES: {smiles string: O}
    - ORCA:
        steps:
        - Optimization
        - Energy: {extra keywords: TightSCF}
    - Loop:
        type: Foreach
        variable: SMILES
        values: C CC CCC
        body:
        - from SMILES: {smiles string: $SMILES}

Each step is a name -- its extension name, as in the editor's step menu, the name in its
description, or its default title -- alone or with a mapping of its parameters.
``steps`` holds the sub-steps of a step like ORCA, and ``body`` the steps of a loop.
Parameters with units take ``[value, units]`` or "value units", e.g. ``temperature: 300
K``.

A spec is never run as it is: ``build()`` checks every value and makes a complete
flowchart, with the installed plug-ins' defaults for everything the spec leaves out,
which is what is written, run and archived. ``reduce()`` goes the other way, giving
the spec for any flowchart, which is a compact way to read one.
"""

import logging

from .builder import FlowchartBuilder, FlowchartBuildError
from .catalog import Catalog
from .format3 import dump_yaml, load_yaml, subflowchart, tree

logger = logging.getLogger(__name__)

# Keys in a step's mapping that are not parameters
_STRUCTURE_KEYS = ("steps", "body")


class SpecError(ValueError):
    """A spec that cannot be understood."""


def load(text):
    """Read a spec from YAML text. 'yes' and 'no' stay strings."""
    data = load_yaml(text)
    if isinstance(data, list):
        data = {"steps": data}
    if not isinstance(data, dict):
        raise SpecError("A spec is a mapping with 'steps', or a list of steps.")
    return data


def dump(spec):
    """Write a spec as YAML text."""
    return dump_yaml(spec)


def _entry(step, where):
    """The name, parameters, sub-steps and body of one step of a spec."""
    if isinstance(step, str):
        return step, {}, None, None
    if isinstance(step, dict) and len(step) == 1:
        ((name, data),) = step.items()
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise SpecError(
                f"The parameters of '{name}' ({where}) should be a mapping, not "
                f"{data!r}"
            )
        data = dict(data)
        substeps = data.pop("steps", None)
        body = data.pop("body", None)
        return name, data, substeps, body
    raise SpecError(
        f"Each step ({where}) is a name, or a name with a mapping of parameters, "
        f"not {step!r}"
    )


def _add_steps(sequence, steps, where):
    if steps is None:
        return
    if not isinstance(steps, list):
        raise SpecError(f"The steps ({where}) should be a list.")
    for n, step in enumerate(steps, start=1):
        here = f"{where}{n}"
        name, parameters, substeps, body = _entry(step, here)
        try:
            if body is not None:
                with sequence.loop(parameters) as loop_body:
                    _add_steps(loop_body, body, f"{here}.")
                continue
            added = sequence.add(name, parameters)
        except (FlowchartBuildError, KeyError) as e:
            raise SpecError(f"Step {here} ('{name}'): {e}") from None
        if substeps is not None:
            _add_steps(added, substeps, f"{here}.")


def build(spec, catalog=None, flowchart=None):
    """Build a complete flowchart from a spec.

    Parameters
    ----------
    spec : dict or str
        The spec, or its YAML text.
    catalog : seamm.catalog.Catalog, optional
        The catalog of steps, to reuse one already loaded.
    flowchart : seamm.Flowchart, optional
        An empty flowchart to build in.

    Returns
    -------
    seamm.builder.FlowchartBuilder
        The builder holding the flowchart; use its write() or to_text().

    Raises
    ------
    SpecError
        If the spec cannot be understood, or a step or value is not valid. The
        message says which step.
    """
    if isinstance(spec, str):
        spec = load(spec)
    fb = FlowchartBuilder(
        title=spec.get("title", ""),
        description=spec.get("description", ""),
        keywords=spec.get("keywords"),
        catalog=catalog,
        flowchart=flowchart,
    )
    for key in ("creators", "grants"):
        if key in spec:
            fb.metadata[key] = spec[key]
    _add_steps(fb, spec.get("steps"), "")
    return fb


# -----------------------------------------------------------------------------
# Reducing a flowchart to a spec
# -----------------------------------------------------------------------------


def _same(a, b):
    """Whether two parameter values are the same, allowing '10' == 10."""
    if a == b:
        return True
    if isinstance(a, (dict, list)) or isinstance(b, (dict, list)):
        return False
    return str(a) == str(b)


def changed_parameters(node, default_node):
    """The parameters of a node that differ from a new node's, as spec values."""
    result = {}
    if node.parameters is None:
        return result
    for key, parameter in node.parameters.items():
        data = parameter.to_dict()
        value, units = data["value"], data["units"]
        if default_node is not None and key in default_node.parameters:
            default = default_node.parameters[key].to_dict()
            same_units = units in (None, "", default["units"]) or units == (
                parameter.default_units
            )
            if _same(value, default["value"]) and same_units:
                continue
        if units not in (None, "") and units != parameter.default_units:
            result[key] = [value, units]
        else:
            result[key] = value
    return result


def _reduce_items(items, catalog):
    result = []
    for item in items:
        node = item.node
        extension = node.extension
        try:
            default_node = catalog.node(extension)
        except Exception:
            default_node = None
        data = changed_parameters(node, default_node)
        if item.body is not None:
            data["body"] = _reduce_items(item.body, catalog)
        sub = subflowchart(node)
        if sub is not None:
            steps, _ = tree(sub)
            if steps:
                data["steps"] = _reduce_items(steps, catalog.subcatalog(extension))
        # The extension name: unique, as in the editor's step menu and 3.0 files
        result.append({extension: data} if data else extension)
    return result


def reduce(flowchart, catalog=None):
    """The spec of a flowchart: its steps and the parameters that are not defaults.

    Steps not connected to the flowchart are left out, since they do not run.

    Parameters
    ----------
    flowchart : seamm.Flowchart
    catalog : seamm.catalog.Catalog, optional
        The catalog of the flowchart's steps; by default one for the flowchart.

    Returns
    -------
    dict
    """
    if catalog is None:
        catalog = Catalog(flowchart)
    metadata = flowchart.metadata
    spec = {}
    for key in ("title", "description", "keywords"):
        if metadata.get(key):
            spec[key] = metadata[key]
    steps, _ = tree(flowchart)
    spec["steps"] = _reduce_items(steps, catalog)
    return spec
