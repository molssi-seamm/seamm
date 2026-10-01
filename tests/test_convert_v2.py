#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for the frozen 2.0 -> 3.0 converter, with stand-in steps."""

import json

import pytest

from seamm import convert_v2, format3

from .test_builder import fake_flowchart
from .test_format3 import build


def two_point_oh(flowchart):
    """A flowchart's 2.0 text and its parsed flowchart section."""
    text = flowchart.to_text(format="2.0")
    return text, json.loads(text.split("#flowchart\n", 1)[1].split("#end")[0])


def rebuild(data):
    """2.0 text from a (modified) flowchart section."""
    return (
        "#!/usr/bin/env run_flowchart\n!MolSSI flowchart 2.0\n#metadata\n{}\n"
        "#flowchart\n" + json.dumps(data) + "\n#end\n"
    )


def test_same_as_the_live_writer():
    """Converting a 2.0 file gives what the live 3.0 writer gives."""
    flowchart = build().flowchart
    text, _ = two_point_oh(flowchart)
    converted, report = convert_v2.convert_data(text)
    live = format3.to_data(flowchart)
    assert report == []
    for key in ("steps", "requires", "digest", "layout", "metadata"):
        assert converted[key] == live[key], key


def test_converted_text_reads_back():
    flowchart = build().flowchart
    text3, _ = convert_v2.convert(two_point_oh(flowchart)[0])
    again = fake_flowchart()
    again.from_text(text3)
    assert format3.digest(again) == format3.digest(flowchart)


def test_junk_attributes_dropped_and_reported():
    _, data = two_point_oh(build().flowchart)
    data["nodes"][2]["attributes"]["calls"] = 3
    data["nodes"][2]["attributes"]["table"] = None  # empty: not worth reporting
    converted, report = convert_v2.convert_data(rebuild(data))
    assert "calls" not in json.dumps(converted["steps"])
    assert len(report) == 1 and "dropped attributes calls" in report[0]


def test_legacy_lammps_minimization():
    node = {
        "item": "object",
        "module": "lammps_step.minimization",
        "class": "Minimization",
        "version": "2023.6.17",
        "extension": "Minimization",
        "attributes": {
            "_uuid": 7,
            "_title": "Minimization",
            "extension": "Minimization",
            "parameters": {
                "__class__": "MinimizationParameters",
                "__module__": "lammps_step.minimization_parameters",
                "create tables": {"value": "yes", "units": None},
            },
            "convergence": "crude",
            "ftol": {
                "__type__": "pint_units",
                "data": [0.1, [["kilocalorie", 1], ["mole", -1], ["angstrom", -1]]],
            },
            "maxiters": 10000,
            "x": 150,
            "y": 105,
        },
    }
    start = {
        "module": "seamm.start_node",
        "class": "StartNode",
        "version": "2023.6.1",
        "extension": None,
        "attributes": {"_uuid": 1, "x": 150, "y": 35, "parameters": None},
    }
    data = {
        "nodes": [start, node],
        "edges": [
            {"node1": 1, "node2": 7, "edge_type": "execution", "edge_subtype": "next"}
        ],
    }
    converted, report = convert_v2.convert_data(rebuild(data))
    parameters = converted["steps"][0]["parameters"]
    assert parameters == {"create tables": "yes", "convergence": "crude"}
    assert any("convergence 'crude' moved" in line for line in report)
    assert not any("dropped" in line for line in report)
    assert converted["requires"] == {"lammps_step": "2023.6.17", "seamm": "2023.6.1"}


def test_malformed_edges():
    """Scripts made edges with edge_type None or 'next'; the subtype decides."""
    _, data = two_point_oh(build().flowchart)
    for edge in data["edges"]:
        if edge["edge_subtype"] == "next":
            edge["edge_type"] = None
    converted, _ = convert_v2.convert_data(rebuild(data))
    live = format3.to_data(build().flowchart)
    assert converted["steps"] == live["steps"]


def test_unconnected_and_missing_positions():
    fb = build()
    stray = fb.flowchart.create_node("CalcStep")
    fb.flowchart.add_node(stray)
    _, data = two_point_oh(fb.flowchart)
    converted, _ = convert_v2.convert_data(rebuild(data))
    assert converted["unconnected"][0][0]["step"] == "CalcStep"
    assert "layout" not in converted  # the stray step has no position
    assert converted["digest"] == format3.to_data(build().flowchart)["digest"]


def test_version_conflict_reported():
    """Steps of one package at different versions are reported, and the newest is
    required. Every version is set here: the installed one depends on how seamm was
    installed (a shallow checkout without tags gives '0+unknown')."""
    _, data = two_point_oh(build().flowchart)

    def set_versions(item):
        if isinstance(item, dict):
            if "version" in item and "module" in item:
                item["version"] = "2021.2.2"
            for value in item.values():
                set_versions(value)
        elif isinstance(item, list):
            for value in item:
                set_versions(value)

    set_versions(data)  # sub-flowcharts' start steps carry versions too
    data["nodes"][1]["version"] = "2020.1.1"
    converted, report = convert_v2.convert_data(rebuild(data))
    assert any("have versions 2020.1.1, 2021.2.2" in line for line in report)
    assert converted["requires"]["seamm"] == "2021.2.2"


def test_format_1_0():
    _, data = two_point_oh(build().flowchart)
    text = "!MolSSI flowchart 1.0\n" + json.dumps(data)
    converted, _ = convert_v2.convert_data(text)
    assert converted["steps"] == format3.to_data(build().flowchart)["steps"]
    assert converted["metadata"] == {}


@pytest.mark.parametrize(
    "text, message",
    [
        ("hello", "not a MolSSI file"),
        ("!MolSSI job_data 1.0\n{}", "not a flowchart"),
        ("!MolSSI flowchart 3.0\n", "Cannot convert flowchart format 3.0"),
    ],
)
def test_not_convertible(text, message):
    with pytest.raises(convert_v2.ConversionError, match=message):
        convert_v2.convert(text)


def test_converter_imports_nothing_from_seamm():
    """The converter is frozen: it must not depend on SEAMM or plug-ins."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(convert_v2))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add((node.module or ".").split(".")[0] if node.level == 0 else ".")
    assert modules <= {"hashlib", "json", "re", "yaml"}
