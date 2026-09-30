#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for flowchart format 3.0, with stand-in steps (no plug-ins needed)."""

import pytest

import seamm
from seamm import format3
from seamm.builder import FlowchartBuilder

from .test_builder import fake_flowchart, out_edges


def build():
    """A flowchart with a loop, sub-steps and units."""
    fb = FlowchartBuilder(title="Format 3 test", flowchart=fake_flowchart())
    fb.add("Model Chemistry")
    fb.add("Calculation", method="MP2", temperature=(300, "degC"), max_iterations=50)
    with fb.loop(type="Foreach", variable="x") as body:
        body.add(
            "Calculation",
            results={"energy": {"table": "table1", "column": "E"}},
        )
    code = fb.add("Code")
    code.add("Energy", method="DFT")
    fb.layout()
    return fb


def read(text):
    flowchart = fake_flowchart()
    flowchart.from_text(text)
    return flowchart


def test_round_trip_is_exact():
    fb = build()
    text = fb.flowchart.to_text(format="3.0")
    assert text.startswith(
        "#!/usr/bin/env run_flowchart\nformat: MolSSI flowchart 3.0\n"
    )
    again = read(text)
    assert again.to_text(format="3.0") == text


def test_structure_and_values():
    data = format3.to_data(build().flowchart)
    steps = data["steps"]
    assert [s["step"] for s in steps] == ["Model Chemistry", "CalcStep", "Loop", "Code"]
    calc = steps[1]["parameters"]
    assert calc["method"] == "MP2"
    assert calc["temperature"] == [300, "degC"]  # a parameter with units
    assert calc["max iterations"] == 50
    assert "parameters" not in steps[0]  # Model Chemistry has none here
    assert steps[2]["parameters"]["type"] == "Foreach"
    assert [s["step"] for s in steps[2]["body"]] == ["CalcStep"]
    assert steps[3]["steps"][0]["parameters"]["method"] == "DFT"
    # No Join: the loop implies it
    assert "Join" not in str(steps)


def test_compact_lists_in_text():
    text = build().flowchart.to_text(format="3.0")
    assert "temperature: [300, degC]" in text
    assert "'0': [150, 35]" in text


def test_reading_rebuilds_the_graph():
    flowchart = read(build().flowchart.to_text(format="3.0"))
    nodes = flowchart.get_nodes()
    assert [n.extension for n in nodes] == [
        None,
        "Model Chemistry",
        "CalcStep",
        "Join",
        "Loop",
    ]
    join, loop = nodes[3], nodes[4]
    body = out_edges(flowchart, loop)[("execution", "loop")]
    code = out_edges(flowchart, loop)[("execution", "exit")]
    assert out_edges(flowchart, body) == {("execution", "next"): join}
    assert code.extension == "Code"
    energy = code.subflowchart.get_node("1").next()
    assert energy.parameters["method"].value == "DFT"
    calc = nodes[2]
    assert calc.parameters["temperature"].value == 300
    assert calc.parameters["temperature"].units == "degC"


def test_tables_are_restored():
    flowchart = read(build().flowchart.to_text(format="3.0"))
    loop = flowchart.get_nodes()[4]
    body = out_edges(flowchart, loop)[("execution", "loop")]
    assert body.tables == ["table1"]
    assert flowchart.get_nodes()[2].tables == []


def test_layout_kept_and_used():
    fb = build()
    node = fb.flowchart.get_nodes()[1]
    node.x, node.y = 1000, 2000  # moved by hand in the editor
    text = fb.flowchart.to_text(format="3.0")
    flowchart = read(text)
    assert (flowchart.get_nodes()[1].x, flowchart.get_nodes()[1].y) == (1000, 2000)
    # and the edges are routed from the positions
    edge = flowchart.edges(flowchart.get_nodes()[1], direction="in")[0]
    assert edge["coords"][-2:] == [1000, 1975]


def test_without_layout_a_clean_layout_is_made():
    text = format3.dump_yaml(
        {k: v for k, v in format3.to_data(build().flowchart).items() if k != "layout"}
    )
    flowchart = read(text)
    loop = flowchart.get_nodes()[4]
    assert (loop.x, loop.y) == (150, 315)
    body = out_edges(flowchart, loop)[("execution", "loop")]
    assert (body.x, body.y) == (450, 315)


def test_unconnected_steps_are_kept_but_not_digested():
    fb = build()
    digest = format3.digest(fb.flowchart)
    stray = fb.flowchart.create_node("CalcStep")
    fb.flowchart.add_node(stray)
    stray.parameters["method"].value = "DFT"
    data = format3.to_data(fb.flowchart, layout=False)
    assert data["unconnected"][0][0]["parameters"]["method"] == "DFT"
    assert format3.digest(fb.flowchart) == digest
    flowchart = read(format3.dump_yaml(data))
    assert len(list(flowchart)) == len(list(fb.flowchart))
    assert (
        format3.to_data(flowchart, layout=False)["unconnected"] == data["unconnected"]
    )


def test_digest_covers_loop_bodies():
    """Format 2.0's digest stops at the first loop; 3.0's does not."""
    a, b = build(), build()
    body = out_edges(b.flowchart, b.flowchart.get_nodes()[4])[("execution", "loop")]
    body.parameters["method"].value = "DFT"
    assert a.flowchart.digest() == b.flowchart.digest()  # the 2.0 bug
    assert format3.digest(a.flowchart) != format3.digest(b.flowchart)


def test_digest_ignores_layout_metadata_and_number_types():
    a, b = build(), build()
    b.flowchart.metadata["title"] = "Another title"
    b.flowchart.get_nodes()[1].x = 999
    b.flowchart.get_nodes()[2].parameters["max iterations"].value = "50"
    assert format3.digest(a.flowchart) == format3.digest(b.flowchart)
    assert format3.digest(a.flowchart, strict=True) != format3.digest(a.flowchart)


def test_requires():
    data = format3.to_data(build().flowchart)
    assert data["requires"] == {"seamm": seamm.__version__}


def test_yes_and_no_stay_strings():
    data = format3.load_yaml("a: yes\nb: no\nc: on\nd: true\ne: False\n")
    assert data == {"a": "yes", "b": "no", "c": "on", "d": True, "e": False}


def test_unknown_step():
    text = format3.SHEBANG + "\nformat: MolSSI flowchart 3.0\nsteps:\n- step: Nope\n"
    with pytest.raises(format3.FlowchartFormatError, match="'Nope', which is not"):
        read(text)


def test_unknown_parameter_is_an_error():
    text = (
        "format: MolSSI flowchart 3.0\nsteps:\n"
        "- step: CalcStep\n  parameters: {no such thing: 1}\n"
    )
    with pytest.raises(KeyError):
        read(text)


def test_missing_parameters_get_defaults():
    text = (
        "format: MolSSI flowchart 3.0\nsteps:\n"
        "- step: CalcStep\n  parameters: {method: DFT}\n"
    )
    calc = read(text).get_nodes()[1]
    assert calc.parameters["method"].value == "DFT"
    assert calc.parameters["max iterations"].value == 100


def test_format_detection():
    assert format3.is_format3(
        "#!/usr/bin/env run_flowchart\nformat: MolSSI flowchart 3.0"
    )
    assert not format3.is_format3("#!/usr/bin/env run_flowchart\n!MolSSI flowchart 2.0")


def test_3_0_is_the_default():
    fb = build()
    assert fb.flowchart.to_text().splitlines()[1] == "format: MolSSI flowchart 3.0"
    assert fb.to_text().splitlines()[1] == "format: MolSSI flowchart 3.0"
    # 2.0 can still be written when asked for
    assert fb.flowchart.to_text(format="2.0").splitlines()[1] == "!MolSSI flowchart 2.0"
