#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Problems with severities and fixes, from the steps' checks of a flowchart."""

import json

import seamm
from seamm import edit
from seamm.builder import validate
from seamm.problems import ERROR, WARNING, Edit, Fix, Problem, is_error


class Checked(seamm.Node):
    """A step whose check warns about its mode and offers to change it."""

    def __init__(self, flowchart=None):
        super().__init__(flowchart=flowchart, title="Checked", extension="Checked")
        self.parameters = seamm.Parameters(
            defaults={
                "mode": {
                    "default": "a",
                    "kind": "string",
                    "default_units": "",
                    "enumeration": ("a", "b"),
                    "format_string": "s",
                    "description": "Mode:",
                    "help_text": "The mode.",
                }
            }
        )

    def check_flowchart(self, preceding):
        if self.parameters["mode"].value == "a":
            fix = Fix("Use mode b", [Edit(self, "mode", "b")])
            return [Problem("Mode a is risky.", severity=WARNING, fixes=[fix])]
        return []


def _flowchart():
    flowchart = seamm.Flowchart()
    previous = flowchart.get_node("1")
    nodes = []
    for _ in range(2):
        node = Checked(flowchart)
        flowchart.add_node(node)
        flowchart.add_edge(previous, node, edge_type="execution", edge_subtype="next")
        previous = node
        nodes.append(node)
    return flowchart, nodes


def test_a_problem_is_its_text():
    fix = Fix("Use mode b", [])
    problem = Problem("Mode a is risky.", severity=WARNING, fixes=[fix])
    assert problem == "Mode a is risky." and isinstance(problem, str)
    assert json.dumps([problem]) == '["Mode a is risky."]'
    assert not is_error(problem) and is_error("plain text")
    prefixed = problem.prefixed("Step 2: ")
    assert prefixed == "Step 2: Mode a is risky."
    assert prefixed.severity == WARNING and prefixed.fixes == [fix]
    assert Problem("x").severity == ERROR


def test_warnings_only_when_asked():
    flowchart, nodes = _flowchart()
    assert validate(flowchart) == []
    problems = validate(flowchart, warnings=True)
    assert problems == ["Mode a is risky."] * 2
    # edit.validate also checks each step against the installed plug-ins, which
    # do not include this test's step: only the warnings are of interest here.
    assert "Mode a is risky." not in edit.validate(flowchart)
    assert edit.validate(flowchart, warnings=True).count("Mode a is risky.") == 2


def test_fixes_as_data_and_applied():
    flowchart, nodes = _flowchart()
    problems = validate(flowchart, warnings=True)
    described = edit.describe_problems(flowchart, problems)
    assert described[1] == {
        "problem": "Mode a is risky.",
        "severity": "warning",
        "fixes": [
            {
                "label": "Use mode b",
                "set": [{"step": "2", "parameter": "mode", "value": "b"}],
            }
        ],
    }
    applied, remaining = edit.fix(flowchart)
    assert applied == ["Use mode b"] * 2
    # (edit.validate also reports this test's steps as unknown plug-ins)
    assert not any("Mode a" in p for p in remaining)
    assert [n.parameters["mode"].value for n in nodes] == ["b", "b"]
    assert validate(flowchart, warnings=True) == []


class MD(seamm.Node):
    def __init__(self, flowchart=None):
        super().__init__(flowchart=flowchart, title="MD", extension="MD")
        self.parameters = seamm.Parameters(
            defaults={
                "rate": {
                    "default": "2000",
                    "kind": "integer",
                    "default_units": "",
                    "enumeration": tuple(),
                    "format_string": "d",
                    "description": "Rate:",
                    "help_text": "How often to sample.",
                }
            }
        )


class Needs(seamm.Node):
    """An analysis needing the MD sampled at least every ``most``."""

    def __init__(self, flowchart, md, most):
        super().__init__(flowchart=flowchart, title=f"Needs {most}", extension="Needs")
        self.md = md
        self.most = most

    def check_flowchart(self, preceding):
        if int(self.md.parameters["rate"].value) <= self.most:
            return []
        fix = Fix(f"Sample every {self.most}", [Edit(self.md, "rate", self.most)])
        return [Problem(f"Sample at least every {self.most}.", fixes=[fix])]


def test_overlapping_fixes_are_applied_one_at_a_time():
    """The looser need's fix first must not leave the tighter one unmet."""
    flowchart = seamm.Flowchart()
    md = MD(flowchart)
    loose = Needs(flowchart, md, 1000)
    tight = Needs(flowchart, md, 500)
    previous = flowchart.get_node("1")
    for node in (md, loose, tight):
        flowchart.add_node(node)
        flowchart.add_edge(previous, node, edge_type="execution", edge_subtype="next")
        previous = node
    applied, remaining = edit.fix(flowchart)
    assert applied == ["Sample every 1000", "Sample every 500"]
    assert md.parameters["rate"].value == 500
    assert validate(flowchart, warnings=True) == []
