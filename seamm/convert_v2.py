# -*- coding: utf-8 -*-

"""Convert flowcharts in format 1.0 or 2.0 to format 3.0. This module is frozen.

It works on the file's data alone and imports nothing from SEAMM or its plug-ins, so
it gives the same result whatever is installed, now or later, and can be kept as it is
for as long as old flowcharts exist -- for example the older versions of flowcharts on
Zenodo, which cannot be changed. Do not edit it to follow changes elsewhere in SEAMM.

A 2.0 file already holds everything 3.0 needs: each step's extension name and version,
every parameter value and its units, the edges, the subflowcharts and the positions.
The conversion

* turns the edges into the order of the steps, the body of each loop, and the chains
  of steps that are not connected to the flowchart, leaving out the Join in front of
  each loop;
* copies the parameters, writing a parameter with units as [value, units];
* collects the versions of the steps into ``requires``, per package;
* copies the positions into ``layout`` if every step has one;
* drops everything else -- run-time state and caches saved by accident in 2.0 -- and
  reports every non-empty attribute it drops; and
* maps the settings that one old plug-in kept outside its parameters: lammps_step's
  Minimization before 2025.3.16 kept the convergence level as an attribute.

Usage::

    from seamm.convert_v2 import convert
    text3, report = convert(text2)
"""

import hashlib
import json
import re

import yaml

FORMAT = "MolSSI flowchart 3.0"
SHEBANG = "#!/usr/bin/env run_flowchart"

# Node attributes that are not settings but are expected in 2.0 files
_STANDARD = {
    "_uuid",
    "_title",
    "extension",
    "parameters",
    "x",
    "y",
    "w",
    "h",
    "_tables",
    "citation_level",
    "_method",
}


class ConversionError(ValueError):
    """A file that cannot be converted."""


# -----------------------------------------------------------------------------
# YAML, as format 3.0 writes it
# -----------------------------------------------------------------------------


class _Dumper(yaml.SafeDumper):
    pass


def _represent_str(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


def _represent_list(dumper, data):
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


_Dumper.add_representer(str, _represent_str)
_Dumper.add_representer(list, _represent_list)


def _dump(data):
    return yaml.dump(
        data,
        Dumper=_Dumper,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=88,
    )


# -----------------------------------------------------------------------------
# Reading 1.0 and 2.0
# -----------------------------------------------------------------------------


def parse(text):
    """The metadata and flowchart data of a 1.0 or 2.0 file.

    Returns
    -------
    (str, dict, dict)
        The format version, the metadata and the flowchart.
    """
    lines = text.splitlines()
    i = 0
    if lines and lines[0].startswith("#!"):
        i = 1
    if i >= len(lines) or not lines[i].startswith("!MolSSI"):
        raise ConversionError("This is not a MolSSI file.")
    words = lines[i].split()
    if len(words) < 3 or words[1] != "flowchart":
        raise ConversionError(f"This is not a flowchart: {lines[i]}")
    version = words[2]
    rest = lines[i + 1 :]
    if version.startswith("1."):
        return version, {}, json.loads("\n".join(rest))
    if not version.startswith("2."):
        raise ConversionError(f"Cannot convert flowchart format {version}.")

    sections = {}
    current = None
    for line in rest:
        if line.strip() == "":
            continue
        if line.startswith("#"):
            name = line.strip()[1:]
            current = None if name == "end" else sections.setdefault(name, [])
            continue
        if current is not None:
            current.append(line)
    if "flowchart" not in sections:
        raise ConversionError("The file has no #flowchart section.")
    metadata = json.loads("\n".join(sections.get("metadata", ["{}"])))
    return version, metadata, json.loads("\n".join(sections["flowchart"]))


# -----------------------------------------------------------------------------
# Structure
# -----------------------------------------------------------------------------


class _Graph(object):
    """The nodes and edges of one flowchart in a 2.0 file."""

    def __init__(self, data):
        self.nodes = {}
        self.order = []
        for node in data.get("nodes", []):
            uuid = node["attributes"]["_uuid"]
            self.nodes[uuid] = node
            self.order.append(uuid)
        self.out = {uuid: [] for uuid in self.nodes}
        self.into = {uuid: [] for uuid in self.nodes}
        for edge in data.get("edges", []):
            if edge["node1"] in self.nodes and edge["node2"] in self.nodes:
                self.out[edge["node1"]].append(edge)
                self.into[edge["node2"]].append(edge)
        starts = [u for u in self.order if self.nodes[u].get("class") == "StartNode"]
        self.start = starts[0] if starts else (1 if 1 in self.nodes else None)

    def after(self, uuid, subtype):
        if uuid is None:
            return None
        for edge in self.out[uuid]:
            if edge.get("edge_subtype") == subtype:
                return edge["node2"]
        return None

    def extension(self, uuid):
        return self.nodes[uuid].get("extension")

    def is_loop(self, uuid):
        return self.extension(uuid) == "Loop" or self.after(uuid, "loop") is not None


class _Item(object):
    def __init__(self, uuid, body=None, join=None):
        self.uuid = uuid
        self.body = body
        self.join = join


def _chain(graph, uuid, stop, visited):
    items = []
    while uuid is not None and uuid not in stop and uuid not in visited:
        visited.add(uuid)
        following = (
            graph.after(uuid, "next") if graph.extension(uuid) == "Join" else None
        )
        if (
            following is not None
            and following not in visited
            and graph.is_loop(following)
        ):
            loop = following
            visited.add(loop)
            body = _chain(
                graph, graph.after(loop, "loop"), stop | {uuid, loop}, visited
            )
            items.append(_Item(loop, body=body, join=uuid))
            uuid = graph.after(loop, "exit")
        elif graph.is_loop(uuid):
            body = _chain(graph, graph.after(uuid, "loop"), stop | {uuid}, visited)
            items.append(_Item(uuid, body=body))
            uuid = graph.after(uuid, "exit")
        else:
            items.append(_Item(uuid))
            uuid = graph.after(uuid, "next")
    return items


def _tree(graph):
    visited = set()
    steps = []
    if graph.start is not None:
        visited.add(graph.start)
        steps = _chain(graph, graph.after(graph.start, "next"), set(), visited)
    unconnected = []
    remaining = [u for u in graph.order if u not in visited]
    while remaining:
        heads = [
            u
            for u in remaining
            if not any(e["node1"] in remaining for e in graph.into[u])
        ]
        unconnected.append(
            _chain(graph, heads[0] if heads else remaining[0], set(), visited)
        )
        remaining = [u for u in graph.order if u not in visited]
    return steps, unconnected


# -----------------------------------------------------------------------------
# Steps
# -----------------------------------------------------------------------------


def _pint_to_list(value):
    """A Pint quantity as saved by seamm_util's encoder -> [magnitude, units]."""
    magnitude, units = value["data"]
    text = "*".join(f"{name}**{power}" if power != 1 else name for name, power in units)
    return [magnitude, text]


def _parameters(node):
    attributes = node["attributes"]
    parameters = attributes.get("parameters")
    if parameters is None:
        return None
    result = {}
    for key, data in parameters.items():
        if key.startswith("__"):
            continue
        if isinstance(data, dict) and "value" in data:
            value, units = data["value"], data.get("units")
        else:
            value, units = data, None
        if isinstance(value, dict) and value.get("__type__") == "pint_units":
            value, units = _pint_to_list(value)
        result[key] = [value, units] if units not in (None, "") else value
    return result


def _legacy(node, parameters, where, report):
    """Settings that old plug-ins kept as attributes, mapped to parameters."""
    attributes = node["attributes"]
    module = node.get("module", "")
    if (
        module.startswith("lammps_step.")
        and node.get("class") == "Minimization"
        and "convergence" in attributes
        and (parameters is None or "convergence" not in parameters)
    ):
        convergence = attributes["convergence"]
        if convergence in ("crude", "loose", "normal", "tight"):
            parameters = dict(parameters or {})
            parameters["convergence"] = convergence
            report.append(
                f"{where}: lammps_step Minimization: convergence '{convergence}' "
                "moved from an attribute to the parameters"
            )
        else:
            report.append(
                f"{where}: lammps_step Minimization: convergence '{convergence}' "
                "(with explicit tolerances) cannot be converted; the default applies"
            )
        return parameters, {
            "convergence",
            "etol_method",
            "etol",
            "etol_variable",
            "ftol_method",
            "ftol",
            "ftol_variable",
            "maxiters_method",
            "maxiters",
            "maxiters_variable",
            "maxevals_method",
            "maxevals",
            "maxevals_variable",
        }
    return parameters, set()


def _empty(value):
    return value is None or value == 0 or value == "" or value == [] or value == {}


def _step(graph, item, where, layout, positions, versions, report):
    node = graph.nodes[item.uuid]
    data = {"step": node.get("extension")}
    parameters = _parameters(node)
    parameters, mapped = _legacy(node, parameters, where, report)
    if parameters is not None:
        data["parameters"] = parameters

    dropped = [
        key
        for key, value in node["attributes"].items()
        if key not in _STANDARD
        and key not in mapped
        and not (key == "citation_level" or _empty(value))
    ]
    if dropped:
        report.append(
            f"{where} ({data['step']}): dropped attributes "
            + ", ".join(sorted(dropped))
        )
    if node["attributes"].get("parameters") is None and any(
        not _empty(node["attributes"].get(k)) for k in dropped
    ):
        report.append(
            f"{where} ({data['step']}): has no parameters but has settings as "
            "attributes (a legacy file); the step's defaults will apply"
        )

    _version(node, versions)
    if positions is not None:
        positions[where] = _position(node)
        if item.join is not None:
            positions[where + ".join"] = _position(graph.nodes[item.join])
            _version(graph.nodes[item.join], versions)

    if item.body is not None:
        data["body"] = [
            _step(graph, it, f"{where}.{n}", layout, positions, versions, report)
            for n, it in enumerate(item.body, start=1)
        ]
    for key, value in node.items():
        if "flowchart" in key and isinstance(value, dict):
            sub = _Graph(value)
            steps, unconnected = _tree(sub)
            if positions is not None and sub.start is not None:
                positions[where + ".0"] = _position(sub.nodes[sub.start])
            if sub.start is not None:
                _version(sub.nodes[sub.start], versions)
            data["steps"] = [
                _step(sub, it, f"{where}.{n}", layout, positions, versions, report)
                for n, it in enumerate(steps, start=1)
            ]
            if unconnected:
                data["unconnected"] = [
                    [
                        _step(
                            sub,
                            it,
                            f"{where}.u{i}.{n}",
                            layout,
                            positions,
                            versions,
                            report,
                        )
                        for n, it in enumerate(chain, start=1)
                    ]
                    for i, chain in enumerate(unconnected, start=1)
                ]
    return data


def _position(node):
    attributes = node["attributes"]
    x, y = attributes.get("x"), attributes.get("y")
    return [x, y] if x is not None and y is not None else None


def _version(node, versions):
    version = node.get("version")
    module = node.get("module") or ""
    if version is None or module == "":
        return
    package = module.split(".")[0]
    versions.setdefault(package, set()).add(str(version))


def _version_key(version):
    """Sort CalVer and similar versions: numbers compare as numbers."""
    return [int(p) if p.isdigit() else -1 for p in re.split(r"[.+-]", version)]


def _requires(versions, report):
    result = {}
    for package in sorted(versions):
        found = sorted(versions[package], key=_version_key)
        result[package] = found[-1]
        if len(found) > 1:
            report.append(
                f"requires: steps from {package} have versions {', '.join(found)}; "
                f"recorded {found[-1]}"
            )
    return result


# -----------------------------------------------------------------------------
# The digest, as format 3.0 defines it
# -----------------------------------------------------------------------------


def _canonical(data):
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
    result = []
    for step in steps:
        step = {k: v for k, v in step.items() if k != "unconnected"}
        for key in ("body", "steps"):
            if key in step:
                step[key] = _connected(step[key])
        result.append(step)
    return result


def _digest(steps, requires=None):
    data = {"steps": _canonical(_connected(steps))}
    if requires is not None:
        data["requires"] = requires
    text = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# -----------------------------------------------------------------------------
# Converting
# -----------------------------------------------------------------------------


def convert_data(text):
    """Convert a 1.0 or 2.0 flowchart to 3.0 data.

    Returns
    -------
    (dict, [str])
        The 3.0 data, and a report of what was dropped or mapped.
    """
    version, metadata, flowchart = parse(text)
    report = []
    graph = _Graph(flowchart)
    steps, unconnected = _tree(graph)
    versions = {}
    positions = {}
    if graph.start is not None:
        positions["0"] = _position(graph.nodes[graph.start])
        _version(graph.nodes[graph.start], versions)

    data_steps = [
        _step(graph, it, str(n), None, positions, versions, report)
        for n, it in enumerate(steps, start=1)
    ]
    data_unconnected = [
        [
            _step(graph, it, f"u{i}.{n}", None, positions, versions, report)
            for n, it in enumerate(chain, start=1)
        ]
        for i, chain in enumerate(unconnected, start=1)
    ]
    requires = _requires(versions, report)

    data = {
        "format": FORMAT,
        "metadata": {
            k: v for k, v in metadata.items() if k not in ("sha256", "sha256_strict")
        },
        "requires": requires,
        "digest": {
            "sha256": _digest(data_steps),
            "sha256_strict": _digest(data_steps, requires),
        },
        "steps": data_steps,
    }
    if data_unconnected:
        data["unconnected"] = data_unconnected
    if positions and all(p is not None for p in positions.values()):
        data["layout"] = positions
    return data, report


def convert(text):
    """Convert the text of a 1.0 or 2.0 flowchart to the text of a 3.0 flowchart.

    Returns
    -------
    (str, [str])
        The 3.0 text, and a report of what was dropped or mapped.
    """
    data, report = convert_data(text)
    return SHEBANG + "\n" + _dump(data), report
