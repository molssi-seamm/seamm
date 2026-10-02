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
        "list_dashboards",
        "dashboard_info",
        "submit_job",
        "job_status",
        "list_jobs",
        "list_job_files",
        "read_job_file",
    }
    assert tools["submit_job"].annotations.open_world_hint
    assert not tools["submit_job"].annotations.read_only_hint
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


# -----------------------------------------------------------------------------
# Job tools, with a stand-in for the dashboard client (no network)
# -----------------------------------------------------------------------------

PARAMETERS_SPEC = """\
title: PM7 energy of a SMILES
steps:
- Parameters:
    variables:
      SMILES:
        optional: 'Yes'
        type: str
        nargs: a single value
        overwrite: 'No'
        default: O
        choices: []
        help: The molecule
      verbose:
        optional: 'Yes'
        type: bool
        nargs: a single value
        overwrite: 'No'
        default: 'no'
        choices: []
        help: More output
- FromSMILESStep: {smiles string: $SMILES}
- MOPAC:
    steps:
    - Energy: {hamiltonian: PM7}
"""


class FakeDashboard:
    def __init__(self, queues=()):
        self.name = "fake"
        self.queues = list(queues)
        self.submitted = None

    def status(self):
        return "running"

    def list_projects(self):
        return ["default", "test"]

    def list_queues(self):
        return [{"name": q} for q in self.queues]

    def submit(self, flowchart, values, project, title, description, queue, **kw):
        self.submitted = {"values": values, "project": project, "queue": queue}
        return 42

    def job(self, job_id):
        return {"id": job_id, "status": "submitted", "parameters": {"queue": "q"}}


@pytest.fixture
def fake(monkeypatch):
    def install(queues=()):
        client = FakeDashboard(queues)
        monkeypatch.setattr(mcp_server, "_dashboard", lambda name: client)
        return client

    return install


@pytest.fixture
def parameters_flow(tmp_path):
    path = tmp_path / "params.flow"
    mcp_server.build_flowchart(PARAMETERS_SPEC, str(path))
    return path


def test_submit_fills_defaults_and_converts(fake, parameters_flow):
    client = fake()
    result = mcp_server.submit_job(
        str(parameters_flow), "fake", project="test", values={"SMILES": "CCO"}
    )
    assert result["id"] == 42
    assert client.submitted["values"] == {"SMILES": "CCO", "verbose": False}
    assert client.submitted["queue"] is None


def test_submit_needs_a_queue_when_there_are_queues(fake, parameters_flow):
    client = fake(queues=("local", "cluster"))
    with pytest.raises(ValueError, match="Choose a queue on 'fake': local, cluster"):
        mcp_server.submit_job(str(parameters_flow), "fake")
    with pytest.raises(ValueError, match="There is no queue 'gpu'"):
        mcp_server.submit_job(str(parameters_flow), "fake", queue="gpu")
    mcp_server.submit_job(str(parameters_flow), "fake", queue="cluster")
    assert client.submitted["queue"] == "cluster"


def test_submit_refuses(fake, parameters_flow, tmp_path):
    client = fake()
    with pytest.raises(ValueError, match="no parameter 'SMILE'"):
        mcp_server.submit_job(str(parameters_flow), "fake", values={"SMILE": "C"})
    with pytest.raises(ValueError, match="no project 'other'"):
        mcp_server.submit_job(str(parameters_flow), "fake", project="other")
    # A flowchart with problems is not submitted
    bad = tmp_path / "bad.flow"
    bad.write_text(
        parameters_flow.read_text().replace("hamiltonian: PM7", "hamiltonian: PM9")
    )
    with pytest.raises(ValueError, match="has problems, so it was not submitted"):
        mcp_server.submit_job(str(bad), "fake")
    assert client.submitted is None


def test_submit_through_the_client_reports_errors(fake, parameters_flow):
    fake()
    is_error, message = call(
        "submit_job",
        {"path": str(parameters_flow), "dashboard": "fake", "project": "nope"},
    )
    assert is_error and "no project 'nope'" in message


def test_file_lists():
    web_ui = [{"path": "job.out", "size": 10}, {"path": "1/step.out", "size": 5}]
    assert mcp_server._file_list(web_ui) == web_ui
    old = [
        {"id": "/jobs/Job_1", "parent": "#", "text": "Job_1"},
        {"id": "/jobs/Job_1/1", "parent": "/jobs/Job_1", "text": "1"},
        {"id": "x", "parent": "/jobs/Job_1", "text": "job.out", "a_attr": {}},
        {"id": "y", "parent": "/jobs/Job_1/1", "text": "step.out", "a_attr": {}},
    ]
    assert [f["path"] for f in mcp_server._file_list(old)] == ["job.out", "1/step.out"]


def test_dashboards_and_credentials(tmp_path, monkeypatch):
    """The dashboards come from dashboards.ini and the credentials from seammrc,
    which are only read; a dashboard without credentials is used without a login."""
    import seamm_util

    ini = tmp_path / "dashboards.ini"
    ini.write_text("[GENERAL]\n\n[one]\nurl = http://x:1\n\n[two]\nurl = http://y:2\n")
    monkeypatch.setattr(seamm_util, "installation_path", lambda *parts: ini)
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".seamm.d").mkdir()
    rc = tmp_path / ".seamm.d" / "seammrc"
    rc.write_text("[VERSION]\nfile = 1.0\n\n[Dashboard: one]\nuser = u\npassword = p\n")
    before = rc.read_text()
    assert mcp_server.list_dashboards() == [
        {"name": "one", "url": "http://x:1", "credentials": True},
        {"name": "two", "url": "http://y:2", "credentials": False},
    ]
    # No credentials: connect without logging in (a web UI running without logins)
    two = mcp_server._dashboard("two")
    assert two.url == "http://y:2" and two.username is None and two.password is None
    with pytest.raises(ValueError, match="no dashboard 'three'"):
        mcp_server._dashboard("three")
    assert mcp_server._dashboard("one").url == "http://x:1"
    assert rc.read_text() == before


def test_parameters_found_after_a_loop(fake, tmp_path):
    """A Parameters step after a loop was missed (get_nodes() stops at a loop)."""
    spec = """\
title: Parameters after a loop
steps:
- Loop:
    type: Foreach
    variable: X
    values: C CC
    body:
    - FromSMILESStep: {smiles string: $X}
- Parameters:
    variables:
      SMILES:
        optional: 'Yes'
        type: str
        nargs: a single value
        overwrite: 'No'
        default: O
        choices: []
        help: The molecule
- FromSMILESStep: {smiles string: $SMILES}
"""
    path = tmp_path / "after_loop.flow"
    mcp_server.build_flowchart(spec, str(path))
    client = fake()
    mcp_server.submit_job(str(path), "fake", values={"SMILES": "CCO"})
    assert client.submitted["values"] == {"SMILES": "CCO"}
