#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The MCP server's tools, called through a real MCP client connected in-process.
Skipped without the optional 'mcp' package or the plug-ins the flowcharts use."""

import asyncio
import json
import os

import pytest

pytest.importorskip("mcp")
for _plugin in ("from_smiles_step", "mopac_step", "loop_step"):
    pytest.importorskip(_plugin)

from mcp import Client  # noqa: E402

from seamm import mcp_server  # noqa: E402

SPEC = """\
title: Ethanol PM7
description: A PM7 energy of ethanol
steps:
- FromSMILESStep: {smiles string: CCO}
- MOPAC:
    steps:
    - Energy: {hamiltonian: PM7}
"""


_server = None


def server():
    global _server
    if _server is None:
        _server = mcp_server.create_server()
    return _server


def call(name, arguments=None):
    """Call a tool through an MCP client; returns (is_error, value or message)."""

    async def run():
        async with Client(server()) as client:
            return await client.call_tool(name, arguments or {})

    result = asyncio.run(run())
    text = result.content[0].text if result.content else ""
    if result.is_error:
        return True, text
    if result.structured_content is not None:
        return False, result.structured_content.get("result", result.structured_content)
    try:
        return False, json.loads(text)
    except ValueError:
        return False, text


def ok(name, arguments=None):
    is_error, value = call(name, arguments)
    assert not is_error, value
    return value


def error(name, arguments=None):
    is_error, value = call(name, arguments)
    assert is_error, value
    return value


@pytest.fixture
def flow(tmp_path):
    path = tmp_path / "ethanol.flow"
    ok("build_flowchart", {"spec": SPEC, "path": str(path)})
    return path


def test_tools_listed():
    async def run():
        async with Client(server()) as client:
            return await client.list_tools()

    tools = {t.name: t for t in asyncio.run(run()).tools}
    assert set(tools) == {
        "list_steps",
        "describe_step",
        "show_flowchart",
        "flowchart_tree",
        "validate_flowchart",
        "build_flowchart",
        "set_parameters",
        "insert_step",
        "remove_step",
        "move_step",
        "convert_flowchart",
    }
    assert tools["describe_step"].annotations.read_only_hint
    assert not tools["set_parameters"].annotations.read_only_hint
    assert tools["remove_step"].annotations.destructive_hint
    assert "spec" in tools["build_flowchart"].input_schema["properties"]


def test_list_and_describe():
    names = [s["extension"] for s in ok("list_steps")]
    assert "MOPAC" in names and "Loop" in names
    assert "Energy" in [s["extension"] for s in ok("list_steps", {"step": "MOPAC"})]
    info = ok("describe_step", {"step": "MOPAC/Energy"})
    assert "PM7" in info["parameters"]["hamiltonian"]["enumeration"]
    assert "Did you mean: 'MOPAC'" in error("describe_step", {"step": "MOPAK"})


def test_build(flow):
    text = flow.read_text()
    assert "format: MolSSI flowchart 3.0" in text
    assert os.access(flow, os.X_OK)
    assert "hamiltonian: PM7" in ok("show_flowchart", {"path": str(flow)})
    assert ok("validate_flowchart", {"path": str(flow)}) == {
        "valid": True,
        "problems": [],
    }
    tree = ok("flowchart_tree", {"path": str(flow)})
    assert any("MOPAC" in line for line in tree)


def test_build_refuses_to_replace(flow):
    message = error("build_flowchart", {"spec": SPEC, "path": str(flow)})
    assert "overwrite" in message
    ok("build_flowchart", {"spec": SPEC, "path": str(flow), "overwrite": True})


def test_build_errors_name_the_step(tmp_path):
    bad = SPEC.replace("PM7", "PM8")
    message = error("build_flowchart", {"spec": bad, "path": str(tmp_path / "x.flow")})
    assert "'PM8' is not valid for 'hamiltonian'" in message
    assert "PM7" in message
    assert not (tmp_path / "x.flow").exists()


def test_set_parameters(flow, tmp_path):
    result = ok(
        "set_parameters",
        {
            "path": str(flow),
            "step": "MOPAC/Energy",
            "parameters": {"hamiltonian": "AM1"},
        },
    )
    assert result["problems"] == []
    assert "hamiltonian: AM1" in ok("show_flowchart", {"path": str(flow)})

    # A setting with no effect is refused, saying why, and the file is unchanged
    before = flow.read_text()
    message = error(
        "set_parameters",
        {
            "path": str(flow),
            "step": "MOPAC/Energy",
            "parameters": {"calculation": "CIS: CI with singles", "uhf": "yes"},
        },
    )
    assert "'uhf' has no effect" in message
    assert flow.read_text() == before

    # Written elsewhere when asked
    other = tmp_path / "other.flow"
    ok(
        "set_parameters",
        {
            "path": str(flow),
            "step": "2.1",
            "parameters": {"hamiltonian": "PM6"},
            "output": str(other),
        },
    )
    assert "hamiltonian: PM6" in ok("show_flowchart", {"path": str(other)})
    assert "hamiltonian: AM1" in ok("show_flowchart", {"path": str(flow)})


def test_insert_move_remove(flow):
    result = ok(
        "insert_step",
        {
            "path": str(flow),
            "step": "Optimization",
            "parameters": {"hamiltonian": "PM7"},
            "before": "MOPAC/Energy",
        },
    )
    assert result["message"] == "Inserted Optimization as step 2.1"
    assert result["problems"] == []

    result = ok("move_step", {"path": str(flow), "step": "2.2", "before": "2.1"})
    assert result["message"] == "Moved it to step 2.1"
    tree = "\n".join(result["steps"])
    assert tree.index("Energy") < tree.index("Optimization")

    result = ok("remove_step", {"path": str(flow), "step": "2.2"})
    assert "Optimization" not in "\n".join(result["steps"])
    assert "There is no step 7" in error(
        "remove_step", {"path": str(flow), "step": "7"}
    )


def test_convert(flow, tmp_path):
    target = tmp_path / "copy.flow"
    assert ok("convert_flowchart", {"path": str(flow), "output": str(target)}) == {
        "path": str(target),
        "format": "3.0",
    }
    assert ok("validate_flowchart", {"path": str(target)})["valid"]


def test_missing_file(tmp_path):
    missing = str(tmp_path / "nothing.flow")
    assert "There is no file" in error("show_flowchart", {"path": missing})
    result = ok("validate_flowchart", {"path": missing})
    assert not result["valid"]
