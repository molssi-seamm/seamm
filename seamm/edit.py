# -*- coding: utf-8 -*-

"""Edit flowcharts: set parameters, insert, remove and move steps, and validate.

Steps are addressed by a path through the flowchart: positions (``3``, or ``3.2`` for
the second step inside step 3 -- the body of a loop or the sub-steps of a step like
ORCA), names (``ORCA/Energy``), or a mix (``3/Energy``). A name matches a step's
extension name, the name in its description, or its title, ignoring case, spaces,
underscores and hyphens; if several steps match, the error lists their positions.

Every change goes through the same checks as building a flowchart: parameter names,
choices, numbers and units. The result is a complete flowchart, re-read so that its
digest and layout are up to date::

    from seamm import edit

    flowchart = edit.read("my.flow")
    edit.set_parameters(flowchart, "ORCA/Energy", {"basis": "def2-TZVP"})
    edit.insert(flowchart, "Energy", after="ORCA/Optimization")
    problems = edit.validate(flowchart)
    flowchart.write("my.flow")
"""

import copy
import logging
import re

import seamm
from . import format3
from .builder import (
    FlowchartBuildError,
    check_value,
    set_parameters as _set_node_parameters,
    validate as _validate_flowchart,
)
from .catalog import Catalog, choices_are_strict, normalize

logger = logging.getLogger(__name__)


class EditError(ValueError):
    """An edit that cannot be made."""


class _NoSuchStep(EditError):
    """No step at this level has the name (it may be deeper)."""


# -----------------------------------------------------------------------------
# Reading and writing
# -----------------------------------------------------------------------------


def read(path):
    """Read a flowchart in any format."""
    flowchart = seamm.Flowchart()
    flowchart.read(str(path))
    return flowchart


def _data(flowchart):
    return format3.to_data(flowchart, layout=False)


def _replace(flowchart, data):
    """Replace a flowchart's contents with 3.0 data, laying it out afresh."""
    data = {k: v for k, v in data.items() if k != "layout"}
    format3.from_data(flowchart, data)
    return flowchart


# -----------------------------------------------------------------------------
# Addresses
# -----------------------------------------------------------------------------


class _Level(object):
    """A list of steps and the catalog of steps that may go in it."""

    def __init__(self, steps, catalog, path):
        self.steps = steps
        self.catalog = catalog
        self.path = path  # e.g. "3." for the steps inside step 3

    def label(self, index):
        return f"{self.path}{index + 1}"


def _segments(address):
    """Split an address into segments: positions (int) and names (str)."""
    if address is None or str(address).strip() == "":
        raise EditError("No step given.")
    parts = []
    for part in str(address).split("/"):
        part = part.strip()
        if part == "":
            continue
        if re.fullmatch(r"\d+(\.\d+)*", part):
            parts.extend(int(p) for p in part.split("."))
        else:
            parts.append(part)
    return parts


def _names(step, catalog, titles=False):
    """The names a step may be called by: its extension name and the name in its
    description, and with ``titles`` its default title too (which is slower, since
    finding titles makes a node of every kind of step)."""
    extension = step["step"]
    names = {normalize(extension)}
    try:
        names.add(normalize(catalog.descriptions()[extension]["name"]))
        if titles:
            names.add(normalize(catalog.titles()[extension]))
    except KeyError:
        pass
    return names


def _children(level, index):
    """The level inside a step (loop body or sub-steps), or None."""
    step = level.steps[index]
    path = f"{level.label(index)}."
    if "body" in step:
        return _Level(step["body"], level.catalog, path)
    if "steps" in step:
        return _Level(step["steps"], level.catalog.subcatalog(step["step"]), path)
    return None


def _find(level, segment, whole):
    """The index of the step a segment names in a level."""
    if isinstance(segment, int):
        if not 1 <= segment <= len(level.steps):
            where = f"inside {level.path[:-1]}" if level.path else "in the flowchart"
            raise EditError(
                f"There is no step {level.path}{segment}: there are "
                f"{len(level.steps)} steps {where}."
            )
        return segment - 1
    key = normalize(segment)
    matches = [
        i for i, step in enumerate(level.steps) if key in _names(step, level.catalog)
    ]
    if len(matches) == 0:
        matches = [
            i
            for i, step in enumerate(level.steps)
            if key in _names(step, level.catalog, titles=True)
        ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) == 0:
        available = ", ".join(
            f"{level.label(i)} {s['step']}" for i, s in enumerate(level.steps)
        )
        raise _NoSuchStep(
            f"No step '{segment}' in '{whole}'. The steps are: {available}"
        )
    raise EditError(
        f"Several steps match '{segment}' in '{whole}': "
        + ", ".join(level.label(i) for i in matches)
        + ". Give the position instead."
    )


def locate(flowchart, data, address):
    """Find a step.

    Returns
    -------
    (_Level, int)
        The level holding the step and its index there.
    """
    level = _Level(data["steps"], Catalog(flowchart), "")
    segments = _segments(address)
    for n, segment in enumerate(segments):
        try:
            index = _find(level, segment, address)
        except _NoSuchStep:
            # A name may be of a step nested deeper, e.g. MOPAC inside a loop -- but
            # only when no step at this level has it.
            if isinstance(segment, int):
                raise
            found = _search(level, segment)
            if len(found) != 1:
                if len(found) > 1:
                    raise EditError(
                        f"Several steps match '{segment}' in '{address}': "
                        + ", ".join(lv.label(i) for lv, i in found)
                        + ". Give the position instead."
                    ) from None
                raise
            level, index = found[0]
        if n == len(segments) - 1:
            return level, index
        inner = _children(level, index)
        if inner is None:
            raise EditError(
                f"Step {level.label(index)} ({level.steps[index]['step']}) has no "
                "steps inside it."
            )
        level = inner


def _search(level, segment, titles=None):
    """Every step, at any depth below a level, that a name segment matches: by
    extension and description names, or failing that also by titles."""
    if titles is None:
        return _search(level, segment, False) or _search(level, segment, True)
    key = normalize(segment)
    found = []
    for i in range(len(level.steps)):
        inner = _children(level, i)
        if inner is not None:
            for j, other in enumerate(inner.steps):
                if key in _names(other, inner.catalog, titles=titles):
                    found.append((inner, j))
            found.extend(_search(inner, segment, titles))
    return found


def _inside(flowchart, data, address):
    """The level inside a step (for inserting into its body or sub-steps)."""
    if address in (None, "", "/"):
        return _Level(data["steps"], Catalog(flowchart), "")
    level, index = locate(flowchart, data, address)
    inner = _children(level, index)
    if inner is None:
        raise EditError(
            f"Step {level.label(index)} ({level.steps[index]['step']}) cannot hold "
            "other steps."
        )
    return inner


# -----------------------------------------------------------------------------
# Steps as data
# -----------------------------------------------------------------------------


def _fresh(catalog, extension, parameters=None):
    """A new node for a step, with parameters from 3.0 data."""
    node = catalog.flowchart.create_node(extension)
    if parameters:
        format3.apply_parameters(node, copy.deepcopy(parameters))
    return node


def _step_data(catalog, name, params):
    """3.0 data for a new step, with every value checked."""
    extension = catalog.resolve(name)
    node = _fresh(catalog, extension)
    _set_node_parameters(node, params)
    data = {"step": extension}
    parameters = format3.parameters_data(node)
    if parameters is not None:
        data["parameters"] = parameters
    if extension == "Loop":
        data["body"] = []
    elif format3.subflowchart(node) is not None:
        data["steps"] = []
    return data


# -----------------------------------------------------------------------------
# Edits
# -----------------------------------------------------------------------------


def set_parameters(flowchart, address, params):
    """Set parameters of a step, checking each value.

    Parameters
    ----------
    flowchart : seamm.Flowchart
    address : str
        The step, e.g. "3.2" or "ORCA/Energy".
    params : dict
        Parameter values by name (loose matching, as in the builder).
    """
    data = _data(flowchart)
    level, index = locate(flowchart, data, address)
    step = level.steps[index]
    node = _fresh(level.catalog, step["step"], step.get("parameters"))
    try:
        _set_node_parameters(node, params)
    except FlowchartBuildError as e:
        raise EditError(f"Step {level.label(index)} ({step['step']}): {e}") from None
    step["parameters"] = format3.parameters_data(node)
    return _replace(flowchart, data)


def insert(flowchart, name, params=None, after=None, before=None, into=None):
    """Insert a new step.

    Exactly one of ``after``, ``before`` or ``into`` gives where; with none, the step
    goes at the end of the flowchart. ``into`` puts it at the end of a loop's body or
    of a step's sub-steps.

    Returns
    -------
    str
        The address of the new step.
    """
    if sum(x is not None for x in (after, before, into)) > 1:
        raise EditError("Give only one of after, before or into.")
    data = _data(flowchart)
    if after is not None or before is not None:
        level, index = locate(flowchart, data, after if after is not None else before)
        index = index + 1 if after is not None else index
    else:
        level = _inside(flowchart, data, into)
        index = len(level.steps)
    try:
        step = _step_data(level.catalog, name, params or {})
    except (FlowchartBuildError, KeyError) as e:
        raise EditError(str(e).strip('"')) from None
    level.steps.insert(index, step)
    _replace(flowchart, data)
    return level.label(index)


def remove(flowchart, address):
    """Remove a step (and, for a loop or a step like ORCA, the steps inside it)."""
    data = _data(flowchart)
    level, index = locate(flowchart, data, address)
    del level.steps[index]
    return _replace(flowchart, data)


def move(flowchart, address, after=None, before=None, into=None):
    """Move a step, with the steps inside it.

    Returns
    -------
    str
        The new address of the step.
    """
    if sum(x is not None for x in (after, before, into)) != 1:
        raise EditError("Give one of after, before or into.")
    data = _data(flowchart)
    level, index = locate(flowchart, data, address)
    step = level.steps[index]
    target = after if after is not None else before if before is not None else into
    # Moving a step inside itself would lose it
    moved = str(level.label(index))
    if str(target) == moved or str(target).startswith(moved + "."):
        raise EditError(f"Cannot move step {moved} to a place inside itself.")
    # Find the destination first, so that positions refer to the flowchart as it is
    if into is not None:
        destination = _inside(flowchart, data, into)
        position = len(destination.steps)
    else:
        destination, position = locate(flowchart, data, target)
        if after is not None:
            position += 1
    if destination.catalog.namespace != level.catalog.namespace:
        raise EditError(
            f"Step {moved} ({step['step']}) cannot go there: it belongs in "
            f"{level.catalog.namespace}, not {destination.catalog.namespace}."
        )
    marker = {"step": "__moving__"}
    destination.steps.insert(position, marker)
    for k, other in enumerate(level.steps):
        if other is step:
            del level.steps[k]
            break
    new_position = next(k for k, s in enumerate(destination.steps) if s is marker)
    destination.steps[new_position] = step
    _replace(flowchart, data)
    return destination.label(new_position)


# -----------------------------------------------------------------------------
# Looking at a flowchart
# -----------------------------------------------------------------------------


def tree(flowchart):
    """The steps of a flowchart with their addresses, as lines of text."""
    data = _data(flowchart)
    catalog = Catalog(flowchart)
    lines = []

    def walk(level, depth):
        for i, step in enumerate(level.steps):
            try:
                title = level.catalog.titles().get(step["step"], step["step"])
            except Exception:
                title = step["step"]
            label = level.label(i)
            name = (
                step["step"] if title == step["step"] else f"{title} [{step['step']}]"
            )
            lines.append(f"{'    ' * depth}{label:8s} {name}")
            inner = _children(level, i)
            if inner is not None:
                walk(inner, depth + 1)

    walk(_Level(data["steps"], catalog, ""), 0)
    if data.get("unconnected"):
        lines.append(f"(and {len(data['unconnected'])} chains of unconnected steps)")
    return lines


def validate(flowchart):
    """Check a flowchart: its structure and every stored value.

    Returns
    -------
    [str]
        A description of each problem; empty if none.
    """
    problems = list(_validate_flowchart(flowchart))
    data = _data(flowchart)

    def walk(level):
        for i, step in enumerate(level.steps):
            label = f"Step {level.label(i)} ({step['step']})"
            if "body" in step and not step["body"]:
                problems.append(f"{label}: the loop has no steps in its body.")
            if "steps" in step and not step["steps"]:
                problems.append(f"{label}: has no sub-steps, so it does nothing.")
            try:
                node = _fresh(level.catalog, step["step"], step.get("parameters"))
            except Exception as e:
                problems.append(f"{label}: {e}")
                continue
            if node.parameters is not None:
                for key, parameter in node.parameters.items():
                    value = parameter.value
                    if not choices_are_strict(parameter):
                        # Only choices are worth checking again: numbers and units
                        # were checked when set, and may be expressions.
                        continue
                    try:
                        check_value(parameter, value, name=key)
                    except FlowchartBuildError as e:
                        problems.append(f"{label}: {e}")
            inner = _children(level, i)
            if inner is not None:
                walk(inner)

    walk(_Level(data["steps"], Catalog(flowchart), ""))
    return problems
