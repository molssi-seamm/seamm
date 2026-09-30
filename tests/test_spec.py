#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for flowchart specs, with stand-in steps (no plug-ins needed)."""

import pytest

from seamm import format3, spec
from seamm.catalog import Catalog

from .test_builder import fake_flowchart, out_edges

SPEC = """\
title: Spec test
description: A flowchart from a spec
steps:
- Model Chemistry
- Calculation:
    method: MP2
    temperature: 300 degC
    use model chemistry: yes
    max iterations: 50
- Loop:
    type: Foreach
    variable: x
    body:
    - Calculation: {extra keywords: TightSCF}
- Code:
    steps:
    - Energy: {method: DFT}
"""


def build(text=SPEC):
    return spec.build(text, flowchart=fake_flowchart())


def test_build():
    fb = build()
    fc = fb.flowchart
    assert fb.metadata["title"] == "Spec test"
    nodes = fc.get_nodes()
    assert [n.extension for n in nodes] == [
        None,
        "Model Chemistry",
        "CalcStep",
        "Join",
        "Loop",
    ]
    calc = nodes[2].parameters
    assert calc["method"].value == "MP2"
    assert (str(calc["temperature"].value), calc["temperature"].units) == (
        "300",
        "degC",
    )
    assert calc["use model chemistry"].value == "yes"  # 'yes' stays a string
    assert calc["max iterations"].value == 50
    body = out_edges(fc, nodes[4])[("execution", "loop")]
    assert body.parameters["extra keywords"].value == "TightSCF"
    code = out_edges(fc, nodes[4])[("execution", "exit")]
    assert code.subflowchart.get_node("1").next().parameters["method"].value == "DFT"
    assert fb.validate() == []


def test_list_of_steps():
    fb = build("- Calculation\n- Calculation: {method: DFT}\n")
    assert len(fb.flowchart.get_nodes()) == 3


def test_true_for_yes():
    fb = build("- Calculation: {bond orders: false}\n")
    assert fb.flowchart.get_nodes()[1].parameters["bond orders"].value == "no"


@pytest.mark.parametrize(
    "text, message",
    [
        ("- Calculation: {method: CCSD}", r"Step 1 \('Calculation'\): 'CCSD' is not"),
        ("- Nope", "Step 1 \\('Nope'\\): There is no step 'Nope'"),
        ("- Code:\n    steps:\n    - Energy: {mehtod: DFT}", "Step 1.1 \\('Energy'\\)"),
        ("- Calculation: DFT", "should be a mapping"),
        ("- {Calculation: {}, Code: {}}", "Each step"),
        ("- Loop:\n    body: []", "at least one step"),
    ],
)
def test_errors_say_where(text, message):
    with pytest.raises(spec.SpecError, match=message):
        build(text)


def test_reduce_gives_only_changes():
    fb = build()
    reduced = spec.reduce(fb.flowchart, catalog=Catalog(fake_flowchart()))
    assert reduced["title"] == "Spec test"
    steps = reduced["steps"]
    assert steps[0] == "Model Chemistry"
    assert steps[1] == {
        "CalcStep": {
            "method": "MP2",
            "use model chemistry": "yes",
            "max iterations": 50,
            "temperature": ["300", "degC"],  # as written in the spec, "300 degC"
        }
    }
    assert steps[2]["Loop"]["type"] == "Foreach"
    assert steps[2]["Loop"]["body"] == [{"CalcStep": {"extra keywords": "TightSCF"}}]
    assert steps[3] == {"Code": {"steps": [{"Energy": {"method": "DFT"}}]}}


def test_reduce_then_build_is_the_same_flowchart():
    fb = build()
    text = spec.dump(spec.reduce(fb.flowchart, catalog=Catalog(fake_flowchart())))
    again = build(text)
    assert format3.digest(again.flowchart) == format3.digest(fb.flowchart)


def test_reduce_leaves_out_unconnected_steps():
    fb = build()
    stray = fb.flowchart.create_node("CalcStep")
    fb.flowchart.add_node(stray)
    reduced = spec.reduce(fb.flowchart, catalog=Catalog(fake_flowchart()))
    assert len(reduced["steps"]) == 4
