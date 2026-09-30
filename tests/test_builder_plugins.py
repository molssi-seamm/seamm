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

    # The same flowchart, parameter for parameter. (Not Flowchart.digest(), which
    # stops at the first loop.)
    def parameters(fc):
        result = {}
        for node in fc:
            if node.parameters is not None:
                result[node.uuid] = node.parameters.to_dict()
            if hasattr(node, "subflowchart"):
                result.update(parameters(node.subflowchart))
        return result

    assert parameters(flowchart) == parameters(fb.flowchart)
    assert len(parameters(flowchart)) == 6


def test_real_choices_checked(catalog):
    fb = FlowchartBuilder(catalog=catalog)
    mopac = fb.add("MOPAC")
    with pytest.raises(FlowchartBuildError, match="Closest: 'PM7'"):
        mopac.add("Energy", hamiltonian="PM8")


def test_describe_real_substep(catalog):
    data = catalog.describe("MOPAC/Energy")
    assert data["parameters"]["hamiltonian"]["kind"] == "enumeration"
    assert "PM7" in data["parameters"]["hamiltonian"]["enumeration"]
