#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for the rules shared by step dialogs and the flowchart builder:
which parameters apply, narrowed choices, implied values and problems."""

import pytest

import seamm
from seamm import edit, spec
from seamm.builder import FlowchartBuilder, FlowchartBuildError, set_parameters
from seamm.catalog import Catalog

from .test_builder import (
    FakePluginManager,
    MAIN_STEPS,
    _Node,
    _Parameters,
)

F12_BASES = ("cc-pVDZ-F12", "cc-pVTZ-F12")


def _enum(default, choices, applies_when=None, kind="enum"):
    return {
        "default": default,
        "kind": kind,
        "default_units": "",
        "enumeration": choices,
        "format_string": "",
        "description": "",
        "help_text": "",
        "applies_when": applies_when,
    }


class RulesParameters(_Parameters):
    parameters = {
        "use model chemistry": _enum("yes", ("yes", "no"), kind="boolean"),
        "method": _enum(
            "HF", ("HF", "DFT", "CCSD(T)-F12"), {"use model chemistry": "no"}
        ),
        "functional": _enum("B3LYP", ("B3LYP", "PBE0"), {"method": "DFT"}),
        "basis": _enum(
            "def2-TZVP",
            ("def2-SVP", "def2-TZVP") + F12_BASES,
            {"use model chemistry": "no"},
            kind="string",
        ),
        "extrapolation": _enum("none", ("none", "cc"), {"use model chemistry": "no"}),
        "family": _enum("cc", ("cc", "def2"), {"extrapolation": {"not": "none"}}),
    }

    def choices(self, key, values=None):
        values = self.current_values() if values is None else values
        if key == "basis" and "F12" in str(values.get("method", "")):
            return F12_BASES
        return super().choices(key, values)

    def implied(self, values=None):
        values = self.current_values() if values is None else values
        if "F12" in str(values.get("method", "")):
            if values.get("basis") not in F12_BASES:
                return {"basis": "cc-pVTZ-F12"}
        return {}


class RulesStep(_Node):
    def __init__(self, flowchart=None, title="Rules", extension=None):
        super().__init__(flowchart=flowchart, title=title, extension=extension)
        self.parameters = RulesParameters()


RulesStep.__module__ = "seamm.test_standins"


def rules_flowchart():
    flowchart = seamm.Flowchart()
    steps = dict(MAIN_STEPS)
    steps["RulesStep"] = ("Rules", "Simulation", RulesStep, "Rules")
    flowchart.plugin_manager = FakePluginManager("org.molssi.seamm", steps)
    return flowchart


def node():
    return RulesStep(flowchart=rules_flowchart())


# -----------------------------------------------------------------------------
# The rules themselves
# -----------------------------------------------------------------------------


def test_applies_follows_the_conditions_and_chains():
    P = RulesParameters()
    assert not P.applies("method")  # the model chemistry is used
    assert not P.applies("functional")  # method does not apply, so neither does this
    values = {**P.current_values(), "use model chemistry": "no", "method": "DFT"}
    assert P.applies("method", values) and P.applies("functional", values)
    assert not P.applies("family", values)
    values["extrapolation"] = "cc"
    assert P.applies("family", values)


def test_expressions_count_as_met():
    P = RulesParameters()
    values = {**P.current_values(), "use model chemistry": "$use", "method": "$m"}
    assert P.applies("functional", values)


def test_describe_condition():
    P = RulesParameters()
    P["family"]._data["applies_when"] = {"extrapolation": {"not": ["none", "cc"]}}
    assert (
        P.describe_condition("family") == "'extrapolation' is neither 'none' nor 'cc'"
    )
    P = RulesParameters()
    assert P.describe_condition("functional") == "'method' is 'DFT'"
    assert P.describe_condition("family") == "'extrapolation' is not 'none'"
    assert P.describe_condition("use model chemistry") == ""


def test_problems_from_narrowed_choices():
    P = RulesParameters()
    values = {
        **P.current_values(),
        "use model chemistry": "no",
        "method": "CCSD(T)-F12",
        "basis": "def2-TZVP",
    }
    (problem,) = P.problems(values)
    assert "'def2-TZVP' is not valid for 'basis'" in problem


# -----------------------------------------------------------------------------
# The builder follows the rules
# -----------------------------------------------------------------------------


def test_setting_what_does_not_apply_is_refused():
    # The model chemistry is used, so neither method nor functional applies
    with pytest.raises(
        FlowchartBuildError,
        match=r"it needs 'method', which does not apply \(it applies when 'use model "
        r"chemistry' is 'no'\)",
    ):
        set_parameters(node(), functional="PBE0")
    # The method applies but is not DFT
    with pytest.raises(FlowchartBuildError, match="it applies when 'method' is 'DFT'"):
        set_parameters(node(), use_model_chemistry="no", functional="PBE0")


def test_order_does_not_matter():
    n = node()
    set_parameters(n, functional="PBE0", method="DFT", use_model_chemistry=False)
    assert n.parameters["functional"].value == "PBE0"


def test_implied_values_are_filled_in():
    n = node()
    set_parameters(n, use_model_chemistry="no", method="CCSD(T)-F12")
    assert n.parameters["basis"].value == "cc-pVTZ-F12"


def test_contradicting_an_implied_value_is_refused():
    with pytest.raises(FlowchartBuildError, match="'basis' cannot be 'def2-SVP'"):
        set_parameters(
            node(), use_model_chemistry="no", method="CCSD(T)-F12", basis="def2-SVP"
        )


def test_a_refused_change_leaves_the_step_unchanged():
    n = node()
    set_parameters(n, use_model_chemistry="no", method="DFT")
    with pytest.raises(FlowchartBuildError):
        set_parameters(n, method="HF", functional="PBE0")
    assert n.parameters["method"].value == "DFT"


def test_builder_and_spec_and_describe():
    fb = FlowchartBuilder(flowchart=rules_flowchart())
    fb.add("Rules", use_model_chemistry="no", method="DFT", functional="PBE0")
    step = fb.flowchart.get_nodes()[1]
    # A value left from before that no longer applies is not part of the spec
    step.parameters["method"].value = "HF"
    reduced = spec.reduce(fb.flowchart, catalog=Catalog(rules_flowchart()))
    # (method 'HF' is the default; the functional no longer applies)
    assert reduced["steps"][0] == {"RulesStep": {"use model chemistry": "no"}}
    data = Catalog(rules_flowchart()).describe("Rules")
    assert data["parameters"]["functional"]["applies when"] == "'method' is 'DFT'"
    assert "applies when" not in data["parameters"]["use model chemistry"]


def test_validate_reports_problems():
    fb = FlowchartBuilder(flowchart=rules_flowchart())
    fb.add("Rules", use_model_chemistry="no", method="CCSD(T)-F12")
    fb.flowchart.get_nodes()[1].parameters["basis"].value = "def2-SVP"
    problems = edit.validate(fb.flowchart)
    assert any("'def2-SVP' is not valid for 'basis'" in p for p in problems)
