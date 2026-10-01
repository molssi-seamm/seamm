# -*- coding: utf-8 -*-

"""Flowchart format 3.0: YAML that a person can read, complete enough to reproduce.

A 3.0 file holds the flowchart's metadata, the versions of the plug-ins it was made
with, a digest, the steps with every parameter value, and optionally where the editor
draws each step::

    #!/usr/bin/env run_flowchart
    format: MolSSI flowchart 3.0
    metadata: {title: ..., description: ..., keywords: [], creators: [], grants: []}
    requires: {seamm: 2026.9.29, loop-step: 2026.9.18, ...}
    digest: {sha256: ..., sha256_strict: ...}
    steps:
    - step: Table
      parameters: {method: Create, table name: table1, ...}
    - step: Loop
      parameters: {type: Foreach, variable: SMILES, ...}
      body:
      - step: FromSMILESStep
        parameters: {...}
    - step: MOPAC
      steps:
      - step: Energy
        parameters: {...}
    unconnected: []   # steps not connected to the flowchart, kept for the editor
    layout: {"0": [150, 35], "1": [150, 105], ...}

Steps are named by their extension name. A parameter with units is written as
``[value, units]``; any other parameter as its value. The Join node in front of each
loop is implied by the loop. Execution order is the order of the list; nothing else in
the file refers to a step, so there are no ids or edges.

Only a node's parameters are saved: the phase 0 survey (see the 2026-09-30 campaign)
found that every other attribute written by format 2.0 was a constant, run-time state
or a cache derivable from the parameters. The caches -- the tables a step creates --
are rebuilt when a flowchart is read.
"""

import functools
import hashlib
import importlib.metadata
import json
import logging
import re

import yaml

import seamm

logger = logging.getLogger(__name__)

FORMAT = "MolSSI flowchart 3.0"
SHEBANG = "#!/usr/bin/env run_flowchart"


# -----------------------------------------------------------------------------
# YAML
# -----------------------------------------------------------------------------


class Loader(yaml.SafeLoader):
    """A safe YAML loader where only true/false are booleans, as in YAML 1.2.

    YAML 1.1 also reads yes/no/on/off as booleans, but SEAMM uses 'yes' and 'no' as
    the values of many parameters, so they must stay strings.
    """


Loader.yaml_implicit_resolvers = {
    key: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:bool"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
Loader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    list("tTfF"),
)


class Dumper(yaml.SafeDumper):
    """Writes block-style YAML, keeping the order of keys."""


def _represent_str(dumper, data):
    # Multi-line text, e.g. help or a script, as a block
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


Dumper.add_representer(str, _represent_str)


def _represent_list(dumper, data):
    # Short lists of plain values on one line, e.g. [298.15, K] or [150, 35]
    flow = (
        len(data) <= 12
        and all(
            x is None
            or isinstance(x, (bool, int, float))
            or (isinstance(x, str) and "\n" not in x)
            for x in data
        )
        and sum(len(str(x)) + 2 for x in data) < 60
    )
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=flow)


Dumper.add_representer(list, _represent_list)


def load_yaml(text):
    """Read YAML text with the SEAMM loader (yes/no stay strings)."""
    return yaml.load(text, Loader=Loader)


def dump_yaml(data):
    """Write data as YAML, keeping key order and quoting what must be quoted."""
    return yaml.dump(
        data,
        Dumper=Dumper,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=88,
    )


def is_format3(text):
    """Whether text is a format 3.0 flowchart."""
    for line in text.splitlines()[:5]:
        if line.startswith("#!"):
            continue
        if line.strip() == "":
            continue
        return line.strip() == f"format: {FORMAT}" or line.strip().startswith(
            "format: MolSSI flowchart 3."
        )
    return False


# -----------------------------------------------------------------------------
# The flowchart as a tree of steps
# -----------------------------------------------------------------------------


class Item(object):
    """A step in the tree: a node, the body of a loop, and the Join in front of it."""

    def __init__(self, node, body=None, join=None):
        self.node = node
        self.body = body
        self.join = join

    def __repr__(self):
        return f"Item({self.node.extension!r}, body={self.body!r})"


def _after(flowchart, node, subtype):
    """The node after a node along an edge of the given subtype, or None."""
    if node is None:
        return None
    for edge in flowchart.edges(node, direction="out"):
        if edge.edge_subtype == subtype:
            return edge.node2
    return None


def is_loop(flowchart, node):
    """Whether a node is a loop: it has an outgoing 'loop' edge, or is a Loop step."""
    return node.extension == "Loop" or _after(flowchart, node, "loop") is not None


def _chain(flowchart, node, stop, visited):
    """The items from a node along the flowchart, until the end or a stop node."""
    items = []
    while node is not None and node not in stop and node not in visited:
        visited.add(node)
        following = (
            _after(flowchart, node, "next") if node.extension == "Join" else None
        )
        if (
            following is not None
            and following not in visited
            and is_loop(flowchart, following)
        ):
            # A Join in front of a loop, which the loop implies
            loop = following
            visited.add(loop)
            body = _chain(
                flowchart,
                _after(flowchart, loop, "loop"),
                stop | {node, loop},
                visited,
            )
            items.append(Item(loop, body=body, join=node))
            node = _after(flowchart, loop, "exit")
        elif is_loop(flowchart, node):
            body = _chain(
                flowchart, _after(flowchart, node, "loop"), stop | {node}, visited
            )
            items.append(Item(node, body=body))
            node = _after(flowchart, node, "exit")
        else:
            items.append(Item(node))
            node = _after(flowchart, node, "next")
    return items


def tree(flowchart):
    """The steps of a flowchart as a tree.

    Parameters
    ----------
    flowchart : seamm.Flowchart

    Returns
    -------
    ([Item], [[Item]])
        The steps after the start node, and the chains of steps that are not connected
        to the flowchart.
    """
    visited = set()
    start = flowchart.get_node("1")
    visited.add(start)
    steps = _chain(flowchart, _after(flowchart, start, "next"), set(), visited)

    # Steps not connected to the flowchart, in chains. Start each chain at a node
    # with nothing unvisited leading into it.
    unconnected = []
    remaining = [node for node in flowchart if node not in visited]
    while remaining:
        heads = [
            node
            for node in remaining
            if not any(
                e.node1 in remaining for e in flowchart.edges(node, direction="in")
            )
        ]
        head = heads[0] if heads else remaining[0]
        unconnected.append(_chain(flowchart, head, set(), visited))
        remaining = [node for node in flowchart if node not in visited]
    return steps, unconnected


def subflowchart(node):
    """A node's subflowchart, or None."""
    sub = getattr(node, "subflowchart", None)
    return sub if isinstance(sub, seamm.Flowchart) else None


# -----------------------------------------------------------------------------
# Writing
# -----------------------------------------------------------------------------


def parameters_data(node):
    """A node's parameters as 3.0 data: {name: value or [value, units]}."""
    if node.parameters is None:
        return None
    result = {}
    for key, parameter in node.parameters.items():
        data = parameter.to_dict()
        if parameter.default_units not in (None, "") or data["units"] not in (None, ""):
            result[key] = [data["value"], data["units"]]
        else:
            result[key] = data["value"]
    return result


def _steps_data(items, layout, prefix, positions):
    result = []
    for n, item in enumerate(items, start=1):
        path = f"{prefix}{n}"
        node = item.node
        data = {"step": node.extension}
        parameters = parameters_data(node)
        if parameters is not None:
            data["parameters"] = parameters
        if positions:
            layout[path] = _position(node)
            if item.join is not None:
                layout[path + ".join"] = _position(item.join)
        if item.body is not None:
            data["body"] = _steps_data(item.body, layout, path + ".", positions)
        sub = subflowchart(node)
        if sub is not None:
            steps, unconnected = tree(sub)
            if positions:
                layout[path + ".0"] = _position(sub.get_node("1"))
            data["steps"] = _steps_data(steps, layout, path + ".", positions)
            if unconnected:
                data["unconnected"] = [
                    _steps_data(chain, layout, f"{path}.u{i}.", positions)
                    for i, chain in enumerate(unconnected, start=1)
                ]
        result.append(data)
    return result


def _position(node):
    return [node.x, node.y] if node.x is not None and node.y is not None else None


def _has_positions(flowchart):
    for node in flowchart:
        if node.x is None or node.y is None:
            return False
        sub = subflowchart(node)
        if sub is not None and not _has_positions(sub):
            return False
    return True


def steps_data(flowchart, layout=None):
    """The steps and unconnected steps of a flowchart as 3.0 data.

    Parameters
    ----------
    flowchart : seamm.Flowchart
    layout : dict, optional
        If given, filled with the positions of the steps by path.

    Returns
    -------
    ([dict], [[dict]])
    """
    positions = layout is not None
    if positions:
        layout["0"] = _position(flowchart.get_node("1"))
    else:
        layout = {}
    steps, unconnected = tree(flowchart)
    return (
        _steps_data(steps, layout, "", positions),
        [
            _steps_data(chain, layout, f"u{i}.", positions)
            for i, chain in enumerate(unconnected, start=1)
        ],
    )


def _nodes(flowchart):
    """Every node, including those in subflowcharts."""
    for node in flowchart:
        yield node
        sub = subflowchart(node)
        if sub is not None:
            yield from _nodes(sub)


def requirements(flowchart):
    """The package and version of every step, from the nodes themselves.

    Returns
    -------
    {str: str}
        Package (the name that is imported, e.g. 'table_step') -> version, sorted by
        name. The frozen 2.0 converter can find the same names in a 2.0 file.
    """
    result = {}
    for node in _nodes(flowchart):
        name = type(node).__module__.split(".")[0]
        try:
            version = node.version
        except Exception:
            version = None
        if version is not None:
            result[name] = str(version)
    return dict(sorted(result.items()))


def _canonical(data):
    """Numbers as text, so 10 and '10', which SEAMM treats alike, digest alike."""
    if isinstance(data, dict):
        return {str(k): _canonical(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_canonical(v) for v in data]
    if isinstance(data, bool) or data is None:
        return data
    if isinstance(data, (int, float)):
        return str(data)
    return data


def _connected(steps):
    """The steps without any unconnected steps, which never run, at any level."""
    result = []
    for step in steps:
        step = {k: v for k, v in step.items() if k != "unconnected"}
        for key in ("body", "steps"):
            if key in step:
                step[key] = _connected(step[key])
        result.append(step)
    return result


def digest(flowchart, strict=False):
    """A digest of what the flowchart does: its steps and every parameter value.

    Unlike format 2.0's ``Flowchart.digest()``, this covers the whole flowchart,
    including the bodies of loops and the steps after them. Metadata, layout and steps
    not connected to the flowchart are not included.

    Parameters
    ----------
    flowchart : seamm.Flowchart
    strict : bool
        Also include the versions of the plug-ins.

    Returns
    -------
    str
        The SHA-256 hex digest.
    """
    steps, _ = steps_data(flowchart)
    data = {"steps": _canonical(_connected(steps))}
    if strict:
        data["requires"] = requirements(flowchart)
    text = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def to_data(flowchart, layout=True):
    """The flowchart as 3.0 data (a dict)."""
    positions = {} if layout and _has_positions(flowchart) else None
    steps, unconnected = steps_data(flowchart, positions)
    metadata = {
        k: v
        for k, v in flowchart.metadata.items()
        if k not in ("sha256", "sha256_strict")
    }
    data = {
        "format": FORMAT,
        "metadata": metadata,
        "requires": requirements(flowchart),
        "digest": {
            "sha256": digest(flowchart),
            "sha256_strict": digest(flowchart, strict=True),
        },
        "steps": steps,
    }
    if unconnected:
        data["unconnected"] = unconnected
    if positions:
        data["layout"] = positions
    return data


def to_text(flowchart, layout=True):
    """The flowchart as the text of a 3.0 .flow file."""
    return SHEBANG + "\n" + dump_yaml(to_data(flowchart, layout=layout))


# -----------------------------------------------------------------------------
# Reading
# -----------------------------------------------------------------------------


class FlowchartFormatError(ValueError):
    """A 3.0 flowchart that cannot be read."""


def apply_parameters(node, parameters):
    """Set a node's parameters from 3.0 data, as format 2.0 would restore them.

    As in 2.0, a new object of the node's parameters class is made from the data, so
    the fixes plug-ins make in ``__init__`` for renamed or replaced parameters apply
    (e.g. lammps_step's NPT turns 'keep orthorhombic' into 'allow shear'), and a
    parameter the plug-in does not have is an error.
    """
    if parameters is None:
        return
    if node.parameters is None:
        raise FlowchartFormatError(
            f"The step '{node.extension}' has no parameters, but the file gives some."
        )
    data = {}
    for key, value in parameters.items():
        units = None
        if key in node.parameters:
            has_units = node.parameters[key].default_units not in (None, "")
            kind = node.parameters[key].kind
        else:
            has_units, kind = True, None
        if (
            has_units
            and kind not in ("list", "periodic table")
            and isinstance(value, list)
            and len(value) == 2
            and (value[1] is None or isinstance(value[1], str))
        ):
            value, units = value
        data[key] = {"value": value, "units": units}
    node.parameters = type(node.parameters)(data=data)


def _create(flowchart, extension):
    try:
        node = flowchart.create_node(extension)
    except KeyError:
        raise FlowchartFormatError(
            f"The flowchart uses the step '{extension}', which is not installed "
            f"(plug-in namespace {flowchart.plugin_manager.namespace})."
        )
    flowchart.add_node(node)
    return node


def _connect(flowchart, node1, node2, subtype):
    if node1 is not None:
        flowchart.add_edge(node1, node2, edge_type="execution", edge_subtype=subtype)


def _build(flowchart, steps, after, subtype, layout, prefix):
    """Create the nodes for a list of 3.0 steps after a node. Returns the last node
    and the subtype of the edge that should leave it."""
    last = after
    for n, step in enumerate(steps, start=1):
        path = f"{prefix}{n}"
        if not isinstance(step, dict) or "step" not in step:
            raise FlowchartFormatError(f"Step {path} does not say which step it is.")
        extension = step["step"]
        if "body" in step:
            join = _create(flowchart, "Join")
            _connect(flowchart, last, join, subtype)
            layout.setdefault("nodes", {})[path + ".join"] = join
            node = _create(flowchart, extension)
            apply_parameters(node, step.get("parameters"))
            _connect(flowchart, join, node, "next")
            end, end_subtype = _build(
                flowchart, step["body"] or [], node, "loop", layout, path + "."
            )
            if end is not node:
                _connect(flowchart, end, join, end_subtype)
            last, subtype = node, "exit"
        else:
            node = _create(flowchart, extension)
            apply_parameters(node, step.get("parameters"))
            _connect(flowchart, last, node, subtype)
            last, subtype = node, "next"
        layout.setdefault("nodes", {})[path] = node
        sub = subflowchart(node)
        if sub is not None:
            layout["nodes"][path + ".0"] = sub.get_node("1")
            _build(
                sub,
                step.get("steps") or [],
                sub.get_node("1"),
                "next",
                layout,
                path + ".",
            )
            for i, chain in enumerate(step.get("unconnected") or [], start=1):
                _build(sub, chain, None, "next", layout, f"{path}.u{i}.")
        elif step.get("steps"):
            raise FlowchartFormatError(
                f"The step '{extension}' ({path}) does not take sub-steps."
            )
    return last, subtype


def restore_tables(flowchart):
    """Rebuild the tables each step creates, which the editor uses in its dropdowns.

    A step's tables are those its 'results' parameter puts results in; a Table step
    that creates or reads a table also has that table.
    """
    for node in _nodes(flowchart):
        P = node.parameters
        if P is None:
            continue
        tables = set()
        if "results" in P and isinstance(P["results"].value, dict):
            for data in P["results"].value.values():
                if isinstance(data, dict) and "table" in data:
                    tables.add(data["table"])
        if node.extension == "Table" and "method" in P and "table name" in P:
            if P["method"].value in ("Create", "Read"):
                tables.add(P["table name"].value)
        node.tables = sorted(str(t) for t in tables)


@functools.lru_cache(maxsize=1)
def _packages_distributions():
    """Which distribution provides each top-level package. Finding out reads every
    installed package's files (about 0.5 s), so it is done once per process."""
    return importlib.metadata.packages_distributions()


def from_data(flowchart, data):
    """Recreate a flowchart from 3.0 data (a dict), replacing what it holds."""
    if not isinstance(data, dict) or not str(data.get("format", "")).startswith(
        "MolSSI flowchart 3."
    ):
        raise FlowchartFormatError("The data is not a format 3.0 flowchart.")

    flowchart.clear()
    metadata = dict(data.get("metadata") or {})
    flowchart.metadata = metadata

    nodes = {}
    layout = {"nodes": nodes}
    start = flowchart.get_node("1")
    nodes["0"] = start
    _build(flowchart, data.get("steps") or [], start, "next", layout, "")
    for i, chain in enumerate(data.get("unconnected") or [], start=1):
        _build(flowchart, chain, None, "next", layout, f"u{i}.")

    restore_tables(flowchart)

    # The positions for the editor, if every step has one; otherwise a clean layout.
    positions = data.get("layout") or {}
    if all(positions.get(path) for path in nodes):
        from .layout import route_edges, WIDTH, HEIGHT

        for path, node in nodes.items():
            node.x, node.y = positions[path]
            node.w, node.h = WIDTH, HEIGHT
        route_edges(flowchart)
    else:
        from .layout import layout as clean_layout

        clean_layout(flowchart)

    # Warn about plug-ins that are missing or at another version
    distributions = _packages_distributions()
    for name, version in (data.get("requires") or {}).items():
        try:
            installed = importlib.metadata.version(distributions.get(name, [name])[0])
        except importlib.metadata.PackageNotFoundError:
            logger.warning(
                f"The flowchart was made with {name} {version}, "
                "which is not installed."
            )
            continue
        if installed != version:
            logger.info(
                f"The flowchart was made with {name} {version}; "
                f"{installed} is installed."
            )
    return flowchart


def from_text(flowchart, text):
    """Recreate a flowchart from the text of a 3.0 .flow file."""
    try:
        data = load_yaml(text)
    except yaml.YAMLError as e:
        raise FlowchartFormatError(f"The flowchart is not valid YAML: {e}")
    return from_data(flowchart, data)
