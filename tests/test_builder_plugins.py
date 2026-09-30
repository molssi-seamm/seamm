#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Build flowcharts with the real plug-ins and read them back with SEAMM's reader.

Skipped unless loop_step, table_step, from_smiles_step and mopac_step are installed.
"""

import pytest

for _package in ("loop_step", "table_step", "from_smiles_step", "mopac_step"):
    pytest.importorskip(_package)

import seamm  # noqa: E402
from seamm.builder import FlowchartBuilder, FlowchartBuildError  # noqa: E402
from seamm.catalog import Catalog  # noqa: E402


@pytest.fixture(scope="module")
def catalog():
    """One catalog for the module, since loading every plug-in takes a while."""
    return Catalog()


def build(catalog):
    fb = FlowchartBuilder(title="MOPAC energies in a loop", catalog=catalog)
    fb.add(
        "Table",
        method="Create",
        table_name="table1",
        columns=[
            {"name": "SMILES", "type": "string", "default": ""},
            {"name": "energy", "type": "float", "default": ""},
        ],
    )
    with fb.loop(type="Foreach", variable="SMILES", values="C CC CCC") as body:
        body.add(
            "Table",
            method="Append a row to",
            table_name="table1",
            columns=[{"name": "SMILES", "value": "$SMILES"}],
        )
        body.add("from SMILES", smiles_string="$SMILES")
        mopac = body.add("MOPAC")
        mopac.add(
            "Energy",
            hamiltonian="PM7",
            results={"energy": {"table": "table1", "column": "energy"}},
        )
    fb.add("Table", method="Save as", table_name="table1", filename="energies.csv")
    return fb


def test_round_trip(catalog):
    fb = build(catalog)
    text = fb.to_text()

    flowchart = seamm.Flowchart()
    flowchart.from_text(text)
    titles = [node.title for node in flowchart.get_nodes()]
    # get_nodes follows 'next' edges, so it stops at the loop
    assert titles == ["Start", "Table", "Join", "Loop"]

    loop = flowchart.get_nodes()[3]
    assert loop.exit_node().parameters["method"].value == "Save as"
    assert loop.parameters["type"].value == "Foreach"
    assert loop.parameters["values"].value == "C CC CCC"
    body = loop.loop_node()
    assert body.parameters["method"].value == "Append a row to"

    mopac = body.next().next()
    energy = mopac.subflowchart.get_node("1").next()
    assert energy.parameters["hamiltonian"].value == "PM7"
    assert energy.parameters["results"].value == {
        "energy": {"table": "table1", "column": "energy"}
    }

    # The same flowchart, step for step and parameter for parameter. (Not
    # Flowchart.digest(), which stops at the first loop, and not node uuids, which
    # are not kept.)
    from seamm import format3

    assert format3.steps_data(flowchart) == format3.steps_data(fb.flowchart)
    assert format3.digest(flowchart) == format3.digest(fb.flowchart)


def test_real_choices_checked(catalog):
    fb = FlowchartBuilder(catalog=catalog)
    mopac = fb.add("MOPAC")
    with pytest.raises(FlowchartBuildError, match="Closest: 'PM7'"):
        mopac.add("Energy", hamiltonian="PM8")


def test_describe_real_substep(catalog):
    data = catalog.describe("MOPAC/Energy")
    assert data["parameters"]["hamiltonian"]["kind"] == "enumeration"
    assert "PM7" in data["parameters"]["hamiltonian"]["enumeration"]


SPEC = """\
title: Spec with real plug-ins
steps:
- Table:
    method: Create
    columns:
    - {name: SMILES, type: string, default: ''}
    - {name: energy, type: float, default: ''}
- Loop:
    type: Foreach
    variable: SMILES
    values: C CC CCC
    body:
    - Table:
        method: Append a row to
        columns:
        - {name: SMILES, value: $SMILES}
    - from SMILES: {smiles string: $SMILES}
    - MOPAC:
        steps:
        - Energy:
            hamiltonian: PM7
            results:
              energy: {table: table1, column: energy}
- Table: {method: Save as, filename: energies.csv}
"""


def test_cli_build_show_convert(tmp_path, capsys):
    from seamm import flowchart_cli, format3, spec

    spec_file = tmp_path / "spec.yaml"
    spec_file.write_text(SPEC)
    flow3 = tmp_path / "energies.flow"
    assert (
        flowchart_cli.main(
            ["build", str(spec_file), "-o", str(flow3), "--format", "3.0"]
        )
        == 0
    )
    text = flow3.read_text()
    assert text.splitlines()[1] == "format: MolSSI flowchart 3.0"

    # 'show' gives back what the spec said, and nothing more
    capsys.readouterr()
    assert flowchart_cli.main(["show", str(flow3)]) == 0
    shown = spec.load(capsys.readouterr().out)
    assert shown["title"] == "Spec with real plug-ins"
    assert shown["steps"][1]["Loop"]["values"] == "C CC CCC"
    mopac = shown["steps"][1]["Loop"]["body"][2]["MOPAC"]
    assert mopac["steps"][0]["Energy"]["hamiltonian"] == "PM7"

    # 3.0 -> 2.0 -> 3.0 keeps every value
    flow2 = tmp_path / "energies2.flow"
    flow3b = tmp_path / "energies3.flow"
    assert (
        flowchart_cli.main(["convert", str(flow3), "-o", str(flow2), "--format", "2.0"])
        == 0
    )
    assert flowchart_cli.main(["convert", str(flow2), "-o", str(flow3b)]) == 0
    a, b = format3.load_yaml(text), format3.load_yaml(flow3b.read_text())
    assert a["digest"] == b["digest"]
    assert a["steps"] == b["steps"]
