#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for editing flowcharts, with stand-in steps (no plug-ins needed)."""

import pytest

from seamm import edit, format3
from seamm.flowchart_cli import _assignments

from .test_format3 import build


@pytest.fixture
def flowchart():
    """1 Model Chemistry, 2 CalcStep, 3 Loop [3.1 CalcStep], 4 Code [4.1 Energy]"""
    return build().flowchart


def steps(flowchart):
    return format3.to_data(flowchart, layout=False)["steps"]


def test_tree(flowchart):
    lines = [line.split() for line in edit.tree(flowchart)]
    assert [line[0] for line in lines] == ["1", "2", "3", "3.1", "4", "4.1"]


@pytest.mark.parametrize("address", ["2", "Calculation", "calcstep"])
def test_set_by_position_or_name(flowchart, address):
    edit.set_parameters(flowchart, address, {"method": "DFT"})
    assert steps(flowchart)[1]["parameters"]["method"] == "DFT"


def test_set_nested(flowchart):
    edit.set_parameters(flowchart, "Code/Energy", {"method": "MP2"})
    edit.set_parameters(flowchart, "3.1", {"max_iterations": 7})
    data = steps(flowchart)
    assert data[3]["steps"][0]["parameters"]["method"] == "MP2"
    assert data[2]["body"][0]["parameters"]["max iterations"] == 7


def test_a_name_finds_a_nested_step_when_unique(flowchart):
    edit.set_parameters(flowchart, "Energy", {"method": "MP2"})
    assert steps(flowchart)[3]["steps"][0]["parameters"]["method"] == "MP2"


def test_ambiguous_names_are_an_error(flowchart):
    edit.insert(flowchart, "Calculation", after="2")
    with pytest.raises(edit.EditError, match="Several steps match 'Calculation'"):
        edit.remove(flowchart, "Calculation")
    # and the one inside the loop was not touched
    assert len(steps(flowchart)[3]["body"]) == 1


def test_set_checks_values(flowchart):
    with pytest.raises(edit.EditError, match=r"Step 4.1 \(Energy\): 'CCSD' is not"):
        edit.set_parameters(flowchart, "4.1", {"method": "CCSD"})


def test_bad_addresses(flowchart):
    with pytest.raises(edit.EditError, match="There is no step 9"):
        edit.remove(flowchart, "9")
    with pytest.raises(edit.EditError, match="No step 'Nope'"):
        edit.remove(flowchart, "Nope")
    with pytest.raises(edit.EditError, match="has no steps inside it"):
        edit.remove(flowchart, "2.1")


def test_insert_after_before_into(flowchart):
    assert edit.insert(flowchart, "Calculation", {"method": "MP2"}, after="1") == "2"
    assert edit.insert(flowchart, "Model Chemistry", before="1") == "1"
    assert edit.insert(flowchart, "Calculation", into="Loop") == "5.2"
    assert edit.insert(flowchart, "Energy", into="Code") == "6.2"
    assert edit.insert(flowchart, "Calculation") == "7"
    data = steps(flowchart)
    assert [s["step"] for s in data] == [
        "Model Chemistry",
        "Model Chemistry",
        "CalcStep",
        "CalcStep",
        "Loop",
        "Code",
        "CalcStep",
    ]
    assert data[2]["parameters"]["method"] == "MP2"
    assert len(data[4]["body"]) == 2 and len(data[5]["steps"]) == 2


def test_insert_checks(flowchart):
    with pytest.raises(edit.EditError, match="no step 'Energy'"):
        edit.insert(flowchart, "Energy")  # a sub-step, not a main step
    with pytest.raises(edit.EditError, match="cannot hold other steps"):
        edit.insert(flowchart, "Calculation", into="2")
    with pytest.raises(edit.EditError, match="'CCSD' is not valid"):
        edit.insert(flowchart, "Calculation", {"method": "CCSD"})


def test_new_loop_and_code_step_are_empty_until_filled(flowchart):
    edit.insert(flowchart, "Loop")
    edit.insert(flowchart, "Code")
    problems = edit.validate(flowchart)
    assert any("Step 5 (Loop): the loop has no steps" in p for p in problems)
    assert any("Step 6 (Code): has no sub-steps" in p for p in problems)
    edit.insert(flowchart, "Calculation", into="5")
    edit.insert(flowchart, "Energy", into="6")
    assert edit.validate(flowchart) == []


def test_remove(flowchart):
    edit.remove(flowchart, "Loop")
    assert [s["step"] for s in steps(flowchart)] == [
        "Model Chemistry",
        "CalcStep",
        "Code",
    ]
    edit.remove(flowchart, "3.1")
    assert steps(flowchart)[2]["steps"] == []


def test_move(flowchart):
    assert edit.move(flowchart, "2", after="Loop") == "3"
    assert [s["step"] for s in steps(flowchart)][:3] == [
        "Model Chemistry",
        "Loop",
        "CalcStep",
    ]
    assert edit.move(flowchart, "3", into="Loop") == "2.2"
    assert edit.move(flowchart, "2.2", before="2.1") == "2.1"
    assert len(steps(flowchart)[1]["body"]) == 2


def test_move_checks(flowchart):
    with pytest.raises(edit.EditError, match="inside itself"):
        edit.move(flowchart, "3", into="3")
    with pytest.raises(edit.EditError, match="cannot go there"):
        edit.move(flowchart, "4.1", after="1")  # a Code sub-step to the main line


def test_validate_finds_stale_values(flowchart):
    flowchart.get_nodes()[2].parameters["method"].value = "gDIIS"
    problems = edit.validate(flowchart)
    assert (
        len(problems) == 1 and "Step 2 (CalcStep): 'gDIIS' is not valid" in problems[0]
    )


def test_edits_keep_unconnected_steps_and_update_the_digest(flowchart):
    stray = flowchart.create_node("CalcStep")
    flowchart.add_node(stray)
    before = format3.digest(flowchart)
    edit.set_parameters(flowchart, "2", {"method": "DFT"})
    assert format3.digest(flowchart) != before
    assert format3.to_data(flowchart, layout=False)["unconnected"]


def test_assignments():
    params = _assignments(
        [
            "method=MP2",
            "max_iterations=10",
            "use model chemistry=yes",
            "t=300 K",
            "results={energy: {table: t1}}",
            "empty=",
        ]
    )
    assert params == {
        "method": "MP2",
        "max_iterations": 10,
        "use model chemistry": "yes",
        "t": "300 K",
        "results": {"energy": {"table": "t1"}},
        "empty": "",
    }
    with pytest.raises(ValueError, match="not name=value"):
        _assignments(["method"])
