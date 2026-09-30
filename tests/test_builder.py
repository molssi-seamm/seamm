#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for building flowcharts programmatically: the catalog, builder and layout.

These use small stand-in steps rather than real plug-ins, so they run without any
plug-in installed.
"""

import json
import os

import pytest

import seamm
from seamm.builder import FlowchartBuilder, FlowchartBuildError, set_parameters
from seamm.catalog import Catalog, StepNotFoundError
from seamm import flowchart_cli

# -----------------------------------------------------------------------------
# Stand-in steps and plug-in manager
# -----------------------------------------------------------------------------


class _Parameters(seamm.Parameters):
    parameters = {}

    def __init__(self, defaults={}, data=None):
        super().__init__(defaults={**self.parameters, **defaults}, data=data)


class CalcParameters(_Parameters):
    parameters = {
        "method": {
            "default": "HF",
            "kind": "enum",
            "default_units": "",
            "enumeration": ("HF", "MP2", "DFT"),
            "format_string": "",
            "description": "Method:",
            "help_text": "The method.",
        },
        "use model chemistry": {
            "default": "no",
            "kind": "boolean",
            "default_units": "",
            "enumeration": ("yes", "no"),
            "format_string": "",
            "description": "Use the model chemistry:",
            "help_text": "Use the model chemistry from a Model Chemistry step.",
        },
        "bond orders": {
            "default": "yes",
            "kind": "enum",
            "default_units": "",
            "enumeration": ("no", "yes"),
            "format_string": "",
            "description": "Bond orders:",
            "help_text": "Whether to calculate bond orders.",
        },
        "max iterations": {
            "default": 100,
            "kind": "integer",
            "default_units": "",
            "enumeration": ("default",),
            "format_string": "",
            "description": "Maximum iterations:",
            "help_text": "The maximum number of iterations.",
        },
        "temperature": {
            "default": 298.15,
            "kind": "float",
            "default_units": "K",
            "enumeration": tuple(),
            "format_string": ".2f",
            "description": "Temperature:",
            "help_text": "The temperature.",
        },
        "extra keywords": {
            "default": "",
            "kind": "string",
            "default_units": "",
            "enumeration": ("TightSCF", "VeryTightSCF"),
            "format_string": "",
            "description": "Extra keywords:",
            "help_text": "Extra keywords, typed or chosen.",
        },
        "row": {
            "default": "current",
            "kind": "string",
            "default_units": "",
            "enumeration": "current",  # a plug-in bug: a string, not a tuple
            "format_string": "",
            "description": "Row:",
            "help_text": "The row.",
        },
        "results": {
            "default": {},
            "kind": "dictionary",
            "default_units": "",
            "enumeration": tuple(),
            "format_string": "",
            "description": "results",
            "help_text": "The results to save.",
        },
    }


class LoopParameters(_Parameters):
    parameters = {
        "type": {
            "default": "For",
            "kind": "enumeration",
            "default_units": "",
            "enumeration": ("For", "Foreach"),
            "format_string": "",
            "description": "Type:",
            "help_text": "The type of loop.",
        },
        "variable": {
            "default": "i",
            "kind": "string",
            "default_units": "",
            "enumeration": tuple(),
            "format_string": "",
            "description": "Variable:",
            "help_text": "The loop variable.",
        },
        "end": {
            "default": "10",
            "kind": "float",
            "default_units": "",
            "enumeration": tuple(),
            "format_string": "",
            "description": "End:",
            "help_text": "The last value.",
        },
    }


class _Node(seamm.Node):
    @property
    def version(self):
        return seamm.__version__


class Calc(_Node):
    def __init__(self, flowchart=None, title="Calculation", extension=None, **kwargs):
        super().__init__(flowchart=flowchart, title=title, extension=extension)
        self.parameters = CalcParameters()


class ModelChemistry(_Node):
    def __init__(self, flowchart=None, title="Model Chemistry", extension=None):
        super().__init__(flowchart=flowchart, title=title, extension=extension)


class Loop(_Node):
    def __init__(self, flowchart=None, title="Loop", extension=None):
        super().__init__(flowchart=flowchart, title=title, extension=extension)
        self.parameters = LoopParameters()


class Code(_Node):
    """A step with sub-steps, like ORCA."""

    def __init__(self, flowchart=None, title="Code", extension=None):
        super().__init__(flowchart=flowchart, title=title, extension=extension)
        self.subflowchart = seamm.Flowchart(
            parent=self, name="Code", namespace="org.molssi.seamm.code"
        )
        self.subflowchart.plugin_manager = FakePluginManager(
            "org.molssi.seamm.code",
            {"Energy": ("Energy", "Calculation", Calc, "Energy")},
        )


# seamm.Node reads the bibliography of the installed package that defines the class;
# these stand-ins have none, so they claim to be part of seamm.
for _cls in (Calc, ModelChemistry, Loop, Code):
    _cls.__module__ = "seamm.test_standins"


class FakeStep:
    def __init__(self, name, group, cls, title):
        self.name, self.group, self.cls, self.title = name, group, cls, title

    def description(self):
        return {"name": self.name, "group": self.group, "description": self.title}

    def create_node(self, flowchart=None, **kwargs):
        return self.cls(flowchart=flowchart, title=self.title, **kwargs)


class FakePluginManager:
    """Stands in for seamm.PluginManager, with a fixed set of steps."""

    def __init__(self, namespace, steps):
        self.namespace = namespace
        self._steps = {
            extension: data if not isinstance(data, tuple) else FakeStep(*data)
            for extension, data in steps.items()
        }
        self.manager = self

    def names(self):
        return list(self._steps)

    def get(self, name):
        return self._steps[name]


MAIN_STEPS = {
    "Join": seamm.JoinStep(),
    "Loop": ("Loop", "Control", Loop, "Loop"),
    "CalcStep": ("Calculation", "Simulation", Calc, "Single-Point Calculation"),
    "Model Chemistry": ("Model Chemistry", "Simulation", ModelChemistry, "Model Chem"),
    "Code": ("Code", "Simulation", Code, "Code"),
}


def fake_flowchart():
    flowchart = seamm.Flowchart()
    flowchart.plugin_manager = FakePluginManager("org.molssi.seamm", MAIN_STEPS)
    return flowchart


@pytest.fixture
def builder():
    return FlowchartBuilder(title="test", flowchart=fake_flowchart())


@pytest.fixture
def catalog():
    return Catalog(fake_flowchart())


def out_edges(flowchart, node):
    return {
        (e.edge_type, e.edge_subtype): e.node2
        for e in flowchart.edges(node, direction="out")
    }


# -----------------------------------------------------------------------------
# Catalog
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "CalcStep",
        "Calculation",
        "calculation",
        "Single-Point Calculation",
        "single_point_calculation",
    ],
)
def test_resolve_any_name(catalog, name):
    assert catalog.resolve(name) == "CalcStep"


def test_resolve_suggests(catalog):
    with pytest.raises(StepNotFoundError, match="Did you mean: 'Calculation'"):
        catalog.resolve("Calculaton")


def test_steps_listing(catalog):
    steps = catalog.steps()
    assert [s["extension"] for s in steps][:2] == ["Join", "Loop"]
    assert {"extension", "name", "group", "description"} <= set(steps[0])


def test_describe(catalog):
    data = catalog.describe("Calculation")
    assert data["extension"] == "CalcStep"
    assert data["title"] == "Single-Point Calculation"
    method = data["parameters"]["method"]
    assert method["kind"] == "enum"
    assert method["enumeration"] == ["HF", "MP2", "DFT"]
    assert data["parameters"]["temperature"]["units"] == "K"
    # A string enumeration is a single choice, not a list of letters
    assert data["parameters"]["row"]["enumeration"] == ["current"]
    assert "substeps" not in data


def test_describe_substep(catalog):
    data = catalog.describe("Code")
    assert data["substeps"] == ["Energy"]
    assert data["substep namespace"] == "org.molssi.seamm.code"
    data = catalog.describe("Code/Energy")
    assert data["namespace"] == "org.molssi.seamm.code"
    assert "method" in data["parameters"]


def test_describe_missing_substep(catalog):
    with pytest.raises(ValueError, match="no sub-steps"):
        catalog.describe("Calculation/Energy")


# -----------------------------------------------------------------------------
# Parameter values
# -----------------------------------------------------------------------------


def calc_node():
    return Calc(flowchart=fake_flowchart())


def test_keyword_names():
    node = calc_node()
    set_parameters(node, extra_keywords="TightSCF", max_iterations=50)
    assert node.parameters["extra keywords"].value == "TightSCF"
    assert node.parameters["max iterations"].value == 50


def test_dict_names():
    node = calc_node()
    set_parameters(node, {"bond orders": "no"})
    assert node.parameters["bond orders"].value == "no"


def test_unknown_parameter():
    with pytest.raises(FlowchartBuildError, match="Did you mean: 'max iterations'"):
        set_parameters(calc_node(), max_iteration=5)


def test_enum_checked():
    with pytest.raises(FlowchartBuildError, match="Choose one of: 'HF', 'MP2', 'DFT'"):
        set_parameters(calc_node(), method="CCSD")


def test_enum_case_is_corrected():
    node = calc_node()
    set_parameters(node, method="dft")
    assert node.parameters["method"].value == "DFT"


def test_string_enumeration_is_only_suggestions():
    node = calc_node()
    set_parameters(node, extra_keywords="NormalSCF Grid5")
    assert node.parameters["extra keywords"].value == "NormalSCF Grid5"


@pytest.mark.parametrize("value, expected", [(True, "yes"), (False, "no")])
def test_bool_for_yes_no(value, expected):
    node = calc_node()
    set_parameters(node, bond_orders=value, use_model_chemistry=value)
    assert node.parameters["bond orders"].value == expected
    assert node.parameters["use model chemistry"].value == expected


def test_boolean_rejects_nonsense():
    with pytest.raises(FlowchartBuildError, match="not valid"):
        set_parameters(calc_node(), use_model_chemistry="maybe")


@pytest.mark.parametrize("value", [10.5, "10.5", "ten", True])
def test_integer_checked(value):
    with pytest.raises(FlowchartBuildError, match="needs an integer"):
        set_parameters(calc_node(), max_iterations=value)


def test_integer_choice_allowed():
    node = calc_node()
    set_parameters(node, max_iterations="default")
    assert node.parameters["max iterations"].value == "default"


def test_expression_syntax_checked():
    with pytest.raises(FlowchartBuildError, match="bare names"):
        set_parameters(calc_node(), method="=('HF', 'MP2')[$i]")
    with pytest.raises(FlowchartBuildError, match="not valid Python"):
        set_parameters(calc_node(), method="=('HF', 'MP2'")


@pytest.mark.parametrize("value", ["$n", "=2*n", "=('HF', 'MP2')[int(i) - 1]"])
def test_expressions_pass(value):
    node = calc_node()
    set_parameters(node, method=value, max_iterations=value)
    assert node.parameters["method"].value == value


@pytest.mark.parametrize("value", [(300, "degC"), "300 degC"])
def test_units(value):
    node = calc_node()
    set_parameters(node, temperature=value)
    assert str(node.parameters["temperature"].value) == "300"
    assert node.parameters["temperature"].units == "degC"


def test_incompatible_units():
    with pytest.raises(FlowchartBuildError, match="cannot be converted"):
        set_parameters(calc_node(), temperature=(3, "Pa"))


def test_unknown_units():
    with pytest.raises(FlowchartBuildError, match="not units that SEAMM knows"):
        set_parameters(calc_node(), temperature=(3, "flibbertigibbet"))


@pytest.mark.parametrize("units", ["kcal/mol", "kJ/mol", "eV", "cm^-1"])
def test_context_conversions_allowed(units):
    """SEAMM's units convert energy to temperature, wavenumbers and frequency."""
    node = calc_node()
    set_parameters(node, temperature=(0.6, units))
    assert node.parameters["temperature"].units == units
    assert node.parameters["temperature"].value == 0.6


def test_units_not_taken():
    with pytest.raises(FlowchartBuildError, match="does not take units"):
        set_parameters(calc_node(), max_iterations=(3, "K"))


def test_dictionary_checked():
    with pytest.raises(FlowchartBuildError, match="needs a dict"):
        set_parameters(calc_node(), results=[1, 2])


# -----------------------------------------------------------------------------
# Building
# -----------------------------------------------------------------------------


def test_linear_chain(builder):
    a = builder.add("Calculation", method="MP2")
    b = builder.add("Calculation")
    fc = builder.flowchart
    start = fc.get_node("1")
    assert out_edges(fc, start) == {("execution", "next"): a.node}
    assert out_edges(fc, a.node) == {("execution", "next"): b.node}
    assert [n.title for n in fc.get_nodes()] == [
        "Start",
        "Single-Point Calculation",
        "Single-Point Calculation",
    ]


def test_bad_step_is_not_added(builder):
    with pytest.raises(FlowchartBuildError):
        builder.add("Calculation", method="nonsense")
    assert len(list(builder.flowchart)) == 1


def test_loop_structure(builder):
    builder.add("Calculation")
    with builder.loop(type="Foreach", variable="x") as body:
        b1 = body.add("Calculation")
        b2 = body.add("Calculation")
    after = builder.add("Calculation")

    fc = builder.flowchart
    loop = body.loop_step.node
    assert loop.parameters["type"].value == "Foreach"
    join = loop.previous()
    assert isinstance(join, seamm.Join)
    assert out_edges(fc, join) == {("execution", "next"): loop}
    assert out_edges(fc, loop) == {
        ("execution", "loop"): b1.node,
        ("execution", "exit"): after.node,
    }
    assert out_edges(fc, b1.node) == {("execution", "next"): b2.node}
    # The end of the body returns to the Join
    assert out_edges(fc, b2.node) == {("execution", "next"): join}


def test_nested_loops(builder):
    with builder.loop() as outer:
        outer.add("Calculation")
        with outer.loop() as inner:
            inner.add("Calculation")
    fc = builder.flowchart
    inner_loop = inner.loop_step.node
    outer_join = outer.loop_step.node.previous()
    # The inner loop's exit is the end of the outer body
    assert out_edges(fc, inner_loop)[("execution", "exit")] is outer_join


def test_empty_loop(builder):
    with pytest.raises(FlowchartBuildError, match="at least one step"):
        with builder.loop():
            pass


def test_substeps(builder):
    code = builder.add("Code")
    energy = code.add("Energy", method="DFT")
    sub = code.node.subflowchart
    assert out_edges(sub, sub.get_node("1")) == {("execution", "next"): energy.node}
    assert energy.parameters["method"].value == "DFT"
    with pytest.raises(StepNotFoundError):
        code.add("Calculation")  # a main-flowchart step, not a sub-step


def test_no_substeps(builder):
    calc = builder.add("Calculation")
    with pytest.raises(FlowchartBuildError, match="no sub-steps"):
        calc.add("Energy")


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------


def test_model_chemistry_missing(builder):
    builder.add("Calculation", use_model_chemistry=True)
    problems = builder.validate()
    assert len(problems) == 1 and "no Model Chemistry step" in problems[0]
    with pytest.raises(FlowchartBuildError, match="has problems"):
        builder.to_text()
    builder.to_text(check=False)


def test_model_chemistry_in_substep(builder):
    code = builder.add("Code")
    code.add("Energy", use_model_chemistry="yes")
    assert "Code/Energy" in builder.validate()[0]


def test_model_chemistry_present(builder):
    builder.add("Model Chemistry")
    code = builder.add("Code")
    code.add("Energy", use_model_chemistry="yes")
    with builder.loop() as body:
        body.add("Calculation", use_model_chemistry="yes")
    assert builder.validate() == []


# -----------------------------------------------------------------------------
# Layout and output
# -----------------------------------------------------------------------------


def test_layout_matches_editor_grid(builder):
    a = builder.add("Calculation")
    with builder.loop() as body:
        b1 = body.add("Calculation")
        b2 = body.add("Calculation")
    after = builder.add("Calculation")
    builder.layout()

    fc = builder.flowchart
    loop = body.loop_step.node
    join = loop.previous()
    start = fc.get_node("1")
    assert (start.x, start.y, start.w, start.h) == (150, 35, 200, 50)
    assert (a.node.x, a.node.y) == (150, 105)
    assert (join.x, join.y) == (150, 175)
    assert (loop.x, loop.y) == (150, 245)
    # The body is one column right, starting level with the loop
    assert (b1.node.x, b1.node.y) == (450, 245)
    assert (b2.node.x, b2.node.y) == (450, 315)
    # and the step after the loop is below the body
    assert (after.node.x, after.node.y) == (150, 385)

    edges = {(e.node1, e.node2): e for e in fc.edges()}
    loop_edge = edges[(loop, b1.node)]
    assert (loop_edge["anchor1"], loop_edge["anchor2"]) == ("e", "w")
    back = edges[(b2.node, join)]
    assert (back["anchor1"], back["anchor2"]) == ("s", "e")
    # Down, right past the body, up, and into the Join from the right
    assert back["coords"] == [450, 340, 450, 350, 590, 350, 590, 175, 250, 175]
    down = edges[(a.node, join)]
    assert (down["anchor1"], down["anchor2"]) == ("s", "n")
    assert down["coords"] == [150, 130, 150, 150]


def test_substeps_laid_out(builder):
    code = builder.add("Code")
    energy = code.add("Energy")
    builder.layout()
    assert (energy.node.x, energy.node.y) == (150, 105)


def test_write(builder, tmp_path):
    builder.add("Calculation", method="MP2", temperature=(300, "K"))
    path = tmp_path / "test.flow"
    builder.write(path)
    assert os.access(path, os.X_OK)
    text = path.read_text()
    assert text.startswith("#!/usr/bin/env run_flowchart\n!MolSSI flowchart 2.0\n")
    data = json.loads(text.split("#flowchart\n", 1)[1].split("#end")[0])
    calc = data["nodes"][1]
    assert calc["extension"] == "CalcStep"
    assert calc["attributes"]["parameters"]["method"] == {"value": "MP2", "units": None}
    assert calc["attributes"]["parameters"]["temperature"] == {
        "value": 300,
        "units": "K",
    }
    (edge,) = data["edges"]
    assert (edge["edge_type"], edge["edge_subtype"]) == ("execution", "next")
    assert edge["attributes"]["anchor1"] == "s"


def test_metadata():
    fb = FlowchartBuilder(
        title="T", description="D", keywords=["a"], flowchart=fake_flowchart()
    )
    assert fb.metadata["title"] == "T"
    assert fb.metadata["description"] == "D"
    assert fb.metadata["keywords"] == ["a"]


# -----------------------------------------------------------------------------
# Command line
# -----------------------------------------------------------------------------


@pytest.fixture
def fake_cli(monkeypatch):
    monkeypatch.setattr(flowchart_cli, "_catalog", lambda: Catalog(fake_flowchart()))


def test_cli_steps_json(fake_cli, capsys):
    assert flowchart_cli.main(["steps", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert "CalcStep" in [s["extension"] for s in data]


def test_cli_substeps(fake_cli, capsys):
    assert flowchart_cli.main(["steps", "Code", "--json"]) == 0
    assert [s["extension"] for s in json.loads(capsys.readouterr().out)] == ["Energy"]


def test_cli_describe(fake_cli, capsys):
    assert flowchart_cli.main(["describe", "Code/Energy"]) == 0
    out = capsys.readouterr().out
    assert "'method'  (enum, default 'HF')" in out
    assert "choices: HF, MP2, DFT" in out


def test_cli_describe_json(fake_cli, capsys):
    assert flowchart_cli.main(["describe", "Calculation", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["parameters"]["temperature"]["units"] == "K"


def test_cli_unknown_step(fake_cli, capsys):
    assert flowchart_cli.main(["describe", "Calculaton"]) == 1
    assert "Did you mean" in capsys.readouterr().err
