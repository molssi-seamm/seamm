# -*- coding: utf-8 -*-

"""An MCP server for building, reading and editing SEAMM flowcharts.

It offers the same operations as the ``seamm-flowchart`` command as tools for AI
clients (Claude Desktop, Claude Code and others), keeping the plug-ins loaded between
calls, so each call takes well under a second rather than the 6-25 s of loading
them. It runs locally, next to a SEAMM installation, over stdio::

    seamm-flowchart mcp

and needs the optional ``mcp`` package (``pip install seamm[mcp]``). Every value is
checked by the same code, and rules, as the builder and the editor.

The flowchart files are the single source of truth: each tool reads the file it is
given and writes the result back (or to ``output``), in format 3.0.

The job tools run flowcharts through the dashboards in the installation's
``dashboards.ini``, with the credentials in ``~/.seamm.d/seammrc``; both files are only
read, and the credentials are never returned. ``submit_job`` checks the flowchart first,
fills in the defaults of its command-line parameters, and needs a queue when the
dashboard has queues.
"""

import logging
import os
from pathlib import Path
import stat
import threading

logger = logging.getLogger(__name__)

INSTRUCTIONS = """\
Tools for SEAMM flowcharts (.flow files): graphs of steps, each a plug-in with
parameters. Never write or edit a .flow file by hand; use these tools, which check
every step name, parameter, choice, number and unit.

To make a flowchart:
1. Look up the steps with list_steps (and list_steps with a step name for the
   sub-steps of ORCA, MOPAC, LAMMPS, ...), and their parameters, choices, defaults and
   units with describe_step (e.g. "ORCA/Energy"). Don't guess names or values.
2. Write a spec in YAML, giving only what differs from the defaults:
       title: Water optimization
       steps:
       - Model Chemistry: {model chemistry: "ORCA:DFT@B3LYP/bse:def2-SVP"}
       - FromSMILESStep: {smiles string: O}
       - ORCA:
           steps:
           - Optimization
   'steps:' holds a code step's sub-steps; 'body:' holds a Loop's steps (the Join is
   added). Units as "300 K"; variables as "$name"; an "=" expression is Python with
   bare variable names.
3. build_flowchart the spec; an error names the step and the closest choices. Fix the
   spec and build again.
4. validate_flowchart, then show the user show_flowchart's summary.

To change a flowchart, use flowchart_tree for the steps' addresses ("3", "3.2",
"ORCA/Energy"), then set_parameters, insert_step, remove_step or move_step, and
validate_flowchart. Settings that have no effect with the others are refused, with the
reason: set the controlling parameters in the same call.

To run a flowchart: list_dashboards, then dashboard_info for the dashboard's projects
and queues. Confirm the dashboard, project and queue with the user before
submit_job, which starts a real calculation. Then follow it with job_status, and read
its output with read_job_file ("job.out", a table's .csv, ...); list_job_files lists
what it has written. Loops carry on past errors, so a finished job can still have
failed iterations: look for "Caught exception in loop iteration" in job.out.
"""

# SEAMM's objects are not thread safe, and the tools run in worker threads.
_lock = threading.RLock()
_catalog = None


def catalog():
    """The catalog of steps, loading the plug-ins the first time."""
    global _catalog
    with _lock:
        if _catalog is None:
            from .catalog import Catalog

            _catalog = Catalog()
        return _catalog


def _path(path, must_exist=True):
    """An absolute path, with ~ expanded, relative to the server's directory."""
    if path is None or str(path).strip() == "":
        raise ValueError("A path to a flowchart is needed.")
    result = Path(os.path.expanduser(str(path))).resolve()
    if must_exist and not result.exists():
        raise ValueError(f"There is no file {result}")
    return result


def _write(flowchart, path, format="3.0"):
    """Write a flowchart, made executable, as the editor and command do."""
    text = flowchart.to_text(format=format)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    mode = stat.S_IMODE(os.lstat(path).st_mode)
    os.chmod(path, mode | stat.S_IXUSR | stat.S_IXGRP)


def _read(path):
    from . import edit

    catalog()  # the plug-ins, loaded once
    try:
        return edit.read(path)
    except Exception as e:
        raise ValueError(f"Could not read {path}: {e}")


def _edited(path, output, action):
    """Read a flowchart, change it, write it, and say what it now holds."""
    from . import edit

    with _lock:
        source = _path(path)
        flowchart = _read(source)
        message = action(edit, flowchart)
        target = _path(output, must_exist=False) if output else source
        _write(flowchart, target)
        return {
            "path": str(target),
            "message": message or "",
            "steps": edit.tree(flowchart),
            "problems": edit.validate(flowchart),
        }


# -----------------------------------------------------------------------------
# The tools, as plain functions (tested directly) registered with the server below
# -----------------------------------------------------------------------------


def list_steps(step: str | None = None) -> list[dict]:
    """The steps that can go in a flowchart, or the sub-steps of a step.

    Args:
        step: A step with sub-steps, e.g. "ORCA", "MOPAC" or "LAMMPS", to list its
            sub-steps; or "ORCA/..." paths. Omit for the main steps.

    Returns each step's extension name (use it in specs), name, group and description.
    """
    with _lock:
        steps_catalog = catalog()
        if step:
            parent, extension = steps_catalog.find(step)
            steps_catalog = parent.subcatalog(extension)
        return steps_catalog.steps()


def describe_step(step: str) -> dict:
    """A step's parameters: kind, default, units, choices (strict) or suggestions,
    when each applies, and help; plus its sub-steps if it has them.

    Args:
        step: The step, e.g. "Loop", "FromSMILESStep", or a path to a sub-step such
            as "ORCA/Energy" or "LAMMPS/NPT".
    """
    with _lock:
        return catalog().describe(step)


def build_flowchart(spec: str, path: str, overwrite: bool = False) -> dict:
    """Build a complete flowchart from a spec (YAML text, see the server
    instructions) and write it in format 3.0.

    Args:
        spec: The spec as YAML (or JSON) text.
        path: Where to write the flowchart (.flow).
        overwrite: Replace an existing file. By default an existing file is not
            replaced.

    Returns the path, the steps with their addresses, and the flowchart read back as
    a spec (only the settings that are not defaults).
    """
    from . import edit, spec as spec_module

    with _lock:
        target = _path(path, must_exist=False)
        if target.exists() and not overwrite:
            raise ValueError(
                f"{target} exists. Use overwrite=true to replace it, or choose another "
                "path."
            )
        fb = spec_module.build(spec, catalog=catalog())
        text = fb.to_text(format="3.0")  # validates first
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        mode = stat.S_IMODE(os.lstat(target).st_mode)
        os.chmod(target, mode | stat.S_IXUSR | stat.S_IXGRP)
        return {
            "path": str(target),
            "steps": edit.tree(fb.flowchart),
            "spec": spec_module.dump(spec_module.reduce(fb.flowchart)),
        }


def show_flowchart(path: str) -> str:
    """What a flowchart does, as a spec in YAML: its steps and only the parameters
    that differ from the defaults. Much easier to read than the file.

    Args:
        path: The flowchart (.flow), format 3.0 or 2.0.
    """
    from . import spec as spec_module

    with _lock:
        flowchart = _read(_path(path))
        return spec_module.dump(spec_module.reduce(flowchart))


def flowchart_tree(path: str) -> list[str]:
    """The steps of a flowchart with their addresses ("3", "3.2", ...), which the
    editing tools take.

    Args:
        path: The flowchart (.flow).
    """
    from . import edit

    with _lock:
        return edit.tree(_read(_path(path)))


def validate_flowchart(path: str) -> dict:
    """Check a flowchart: its structure and every stored value, including old values
    the plug-ins no longer accept and settings that cannot work together.

    Args:
        path: The flowchart (.flow).

    Returns whether it is valid, and a description of each problem.
    """
    from . import edit

    with _lock:
        try:
            flowchart = _read(_path(path))
        except ValueError as e:
            return {"valid": False, "problems": [str(e)]}
        problems = edit.validate(flowchart)
        return {"valid": not problems, "problems": problems}


def set_parameters(
    path: str, step: str, parameters: dict, output: str | None = None
) -> dict:
    """Set parameters of a step in a flowchart.

    Args:
        path: The flowchart (.flow).
        step: The step's address: a position ("3", "3.2"), a name ("ORCA/Energy"),
            or both ("3/Energy").
        parameters: Parameter names (as describe_step gives them) and values, e.g.
            {"basis": "def2-TZVP", "temperature": "300 K"}. Set controlling
            parameters in the same call as those that depend on them.
        output: Write the result here instead of back to path.
    """
    return _edited(
        path,
        output,
        lambda edit, fc: edit.set_parameters(fc, step, parameters) and None,
    )


def insert_step(
    path: str,
    step: str,
    parameters: dict | None = None,
    after: str | None = None,
    before: str | None = None,
    into: str | None = None,
    output: str | None = None,
) -> dict:
    """Insert a step into a flowchart, after or before another step, or into a code
    step (as a sub-step) or loop (into its body).

    Args:
        path: The flowchart (.flow).
        step: The step to insert, by extension name (see list_steps).
        parameters: Its parameters that differ from the defaults.
        after: The address of the step to insert after.
        before: The address of the step to insert before.
        into: The address of a step with sub-steps, or a loop, to insert at the end of.
        output: Write the result here instead of back to path.
    """

    def action(edit, flowchart):
        address = edit.insert(
            flowchart, step, parameters or {}, after=after, before=before, into=into
        )
        return f"Inserted {step} as step {address}"

    return _edited(path, output, action)


def remove_step(path: str, step: str, output: str | None = None) -> dict:
    """Remove a step, and any steps inside it, from a flowchart.

    Args:
        path: The flowchart (.flow).
        step: The step's address (see flowchart_tree).
        output: Write the result here instead of back to path.
    """
    return _edited(path, output, lambda edit, fc: edit.remove(fc, step) and None)


def move_step(
    path: str,
    step: str,
    after: str | None = None,
    before: str | None = None,
    into: str | None = None,
    output: str | None = None,
) -> dict:
    """Move a step, and any steps inside it, within a flowchart.

    Args:
        path: The flowchart (.flow).
        step: The address of the step to move (see flowchart_tree).
        after: The address of the step to move it after.
        before: The address of the step to move it before.
        into: The address of a step with sub-steps, or a loop, to move it into.
        output: Write the result here instead of back to path.
    """

    def action(edit, flowchart):
        address = edit.move(flowchart, step, after=after, before=before, into=into)
        return f"Moved it to step {address}"

    return _edited(path, output, action)


def convert_flowchart(path: str, output: str, format: str = "3.0") -> dict:
    """Write a flowchart in another format, e.g. an old format 2.0 file as 3.0.

    Args:
        path: The flowchart (.flow).
        output: Where to write the converted flowchart.
        format: The format to write, "3.0" (the default) or "2.0".
    """
    with _lock:
        flowchart = _read(_path(path))
        target = _path(output, must_exist=False)
        _write(flowchart, target, format=format)
        return {"path": str(target), "format": format}


# -----------------------------------------------------------------------------
# Jobs: running flowcharts through a dashboard (the web UI or the old Dashboard).
# The dashboards are those in the installation's dashboards.ini, and the credentials
# those in ~/.seamm.d/seammrc. Both files are only read, never written, and the
# credentials are never returned.
# -----------------------------------------------------------------------------


def _dashboards_config():
    import configparser

    import seamm_util

    path = seamm_util.installation_path("dashboards.ini")
    config = configparser.ConfigParser()
    if path.exists():
        config.read(path)
    names = sorted(s for s in config.sections() if s != "GENERAL")
    return path, config, names


def _credentials(name):
    """The user and password for a dashboard from ~/.seamm.d/seammrc, read only."""
    import configparser

    config = configparser.ConfigParser()
    config.read(Path("~/.seamm.d/seammrc").expanduser())
    section = f"Dashboard: {name}"
    return (
        config.get(section, "user", fallback=None),
        config.get(section, "password", fallback=None),
    )


def _dashboard(name):
    """A client for the named dashboard."""
    import seamm_dashboard_client

    from .dashboard_handler import _parse_verify

    path, config, names = _dashboards_config()
    if name not in names:
        raise ValueError(
            f"There is no dashboard '{name}' in {path}. The dashboards are: "
            + ", ".join(names)
        )
    # Without a user and password the client connects without logging in, which is
    # what a web UI running without logins (e.g. one on 127.0.0.1) expects; one that
    # needs a login then refuses the requests, and says so.
    user, password = _credentials(name)
    try:
        from . import __version__ as version
    except Exception:
        version = ""
    return seamm_dashboard_client.Dashboard(
        name,
        config[name]["url"],
        username=user,
        password=password,
        user_agent=f"SEAMM-MCP/{version}",
        verify=_parse_verify(config[name].get("verify", "")),
    )


def _job_summary(job):
    """The useful fields of a job, as plain data."""
    data = dict(job)
    parameters = data.get("parameters") or {}
    projects = data.get("projects") or []
    return {
        "id": data.get("id"),
        "title": data.get("title"),
        "description": data.get("description"),
        "status": data.get("status"),
        "projects": [p.get("name", p) if isinstance(p, dict) else p for p in projects],
        "queue": parameters.get("queue"),
        "submitted": data.get("submitted"),
        "started": data.get("started"),
        "finished": data.get("finished"),
        "path": data.get("path"),
    }


def _job(dashboard, job_id):
    job = dashboard.job(int(job_id))
    if not job:
        raise ValueError(
            f"There is no job {job_id} on the dashboard '{dashboard.name}'."
        )
    return job


def list_dashboards(check: bool = False) -> list[dict]:
    """The dashboards that jobs can be submitted to, from the installation's
    dashboards.ini, and whether there are credentials for each (a web UI running
    without logins needs none).

    Args:
        check: Also contact each dashboard for its status ("running", "down" or
            "error"); slower, up to several seconds for one that is down.
    """
    _, config, names = _dashboards_config()
    result = []
    for name in names:
        user, password = _credentials(name)
        entry = {
            "name": name,
            "url": config[name].get("url", ""),
            # Not needed for a web UI that runs without logins
            "credentials": user is not None and password is not None,
        }
        if check:
            try:
                entry["status"] = _dashboard(name).status()
            except Exception as e:
                entry["status"] = f"error: {e}"
        result.append(entry)
    return result


def dashboard_info(dashboard: str) -> dict:
    """What a dashboard offers for submitting a job: its status, projects and
    queues (with the SLURM settings each queue lets a job override, and their
    limits).

    Args:
        dashboard: The dashboard's name (see list_dashboards).
    """
    client = _dashboard(dashboard)
    status = client.status()
    if status != "running":
        return {"dashboard": dashboard, "status": status}
    return {
        "dashboard": dashboard,
        "status": status,
        "projects": client.list_projects(),
        "queues": client.list_queues(),
    }


def _all_steps(flowchart):
    """Every step connected to the start, following every edge (get_nodes() follows
    only "next" edges, so it stops at a loop)."""
    result, seen, queue = [], set(), [flowchart.get_node("1")]
    while queue:
        node = queue.pop(0)
        if node.uuid not in seen:
            seen.add(node.uuid)
            result.append(node)
            queue.extend(edge.node2 for edge in flowchart.edges(node, direction="out"))
    return result


def _control_values(flowchart, values):
    """The values for the flowchart's Parameters steps (its command-line
    arguments): those given, else the defaults. Files must exist here; they are
    uploaded with the job."""
    import shlex

    variables = {}
    for node in _all_steps(flowchart):
        if node.step_type == "control-parameters-step":
            variables.update(node.parameters["variables"].value)
    values = dict(values or {})
    unknown = sorted(set(values) - set(variables))
    if unknown:
        raise ValueError(
            "The flowchart has no parameter "
            + ", ".join(repr(u) for u in unknown)
            + ". Its parameters are: "
            + (", ".join(variables) or "none")
        )
    result = {}
    for name, data in variables.items():
        value = values.get(name, data.get("default", ""))
        if data.get("type") == "bool":
            if isinstance(value, str):
                value = value.strip().lower() in ("yes", "true", "1", "on")
            result[name] = bool(value)
            continue
        if isinstance(value, (list, tuple)):
            value = shlex.join(str(v) for v in value)
        value = "" if value is None else str(value)
        if data.get("optional") != "Yes" and value == "":
            raise ValueError(f"The flowchart's parameter '{name}' needs a value.")
        if data.get("type") == "file" and value != "":
            paths = (
                [value] if data.get("nargs") == "a single value" else shlex.split(value)
            )
            for path in paths:
                if not Path(path).expanduser().exists():
                    raise ValueError(f"The file '{path}' for '{name}' does not exist.")
        result[name] = value
    return result


def submit_job(
    path: str,
    dashboard: str,
    project: str = "default",
    title: str = "",
    description: str = "",
    queue: str | None = None,
    values: dict | None = None,
    slurm: dict | None = None,
) -> dict:
    """Submit a flowchart to run as a job. The flowchart is checked first and not
    submitted if it has problems. This starts a calculation on real computers, so
    confirm the dashboard, project and queue with the user first.

    Args:
        path: The flowchart (.flow).
        dashboard: The dashboard to submit to (see list_dashboards).
        project: An existing project on that dashboard (see dashboard_info).
        title: The job's title.
        description: The job's description.
        queue: Where the job runs, one of the dashboard's queues (see
            dashboard_info). Needed when the dashboard has queues.
        values: Values for the flowchart's command-line parameters (its Parameters
            step), by name; the defaults are used for those not given. Files are
            local paths, uploaded with the job.
        slurm: SLURM settings to override for this job, e.g. {"ntasks": "4",
            "time": "1:00:00"}, within the queue's limits.

    Returns the job's id and status.
    """
    from . import edit

    client = _dashboard(dashboard)
    with _lock:
        flowchart = _read(_path(path))
        problems = edit.validate(flowchart)
        if problems:
            raise ValueError(
                "The flowchart has problems, so it was not submitted:\n"
                + "\n".join(problems)
            )
        control = _control_values(flowchart, values)

    status = client.status()
    if status != "running":
        raise ValueError(f"The dashboard '{dashboard}' is not running ({status}).")
    projects = client.list_projects()
    if project not in projects:
        raise ValueError(
            f"There is no project '{project}' on '{dashboard}'. The projects are: "
            + ", ".join(projects)
        )
    queues = [q["name"] if isinstance(q, dict) else q for q in client.list_queues()]
    if queues and queue is None:
        raise ValueError(f"Choose a queue on '{dashboard}': " + ", ".join(queues))
    if queues and queue not in queues:
        raise ValueError(
            f"There is no queue '{queue}' on '{dashboard}'. The queues are: "
            + ", ".join(queues)
        )

    with _lock:
        job_id = client.submit(
            flowchart,
            values=control,
            project=project,
            title=title or flowchart.metadata.get("title", ""),
            description=description or flowchart.metadata.get("description", ""),
            queue=queue,
            slurm_overrides=slurm,
        )
    return _job_summary(_job(client, job_id))


def job_status(dashboard: str, job_id: int) -> dict:
    """A job's status ("submitted", "running", "finished", "error", ...), its
    times, project, queue and directory.

    Args:
        dashboard: The dashboard (see list_dashboards).
        job_id: The job's id.
    """
    return _job_summary(_job(_dashboard(dashboard), job_id))


def list_jobs(dashboard: str, limit: int = 10) -> list[dict]:
    """The most recent jobs on a dashboard, newest first.

    Args:
        dashboard: The dashboard (see list_dashboards).
        limit: How many jobs, at most.
    """
    client = _dashboard(dashboard)
    response = client._url_get(
        "/api/jobs",
        params={"limit": int(limit), "sortby": "id", "sort_by": "id", "order": "desc"},
    )
    if response.status_code != 200:
        raise ValueError(
            f"Could not list the jobs on '{dashboard}' (code {response.status_code})."
        )
    jobs = sorted(response.json(), key=lambda j: j.get("id", 0), reverse=True)
    return [_job_summary(job) for job in jobs[: int(limit)]]


def _file_list(data):
    """The files of a job, from either dashboard's file listing."""
    from pathlib import PurePath

    if all("path" in entry for entry in data):  # the web UI
        return [{"path": e["path"], "size": e.get("size")} for e in data]
    # The old Dashboard: a tree, whose files have an "a_attr"
    root = None
    for entry in data:
        if entry.get("parent") == "#":
            root = PurePath(entry["id"])
            break
    result = []
    for entry in data:
        if "a_attr" in entry:
            path = PurePath(entry["parent"]) / entry["text"]
            if root is not None:
                path = path.relative_to(root)
            result.append({"path": str(path), "size": None})
    return result


def list_job_files(dashboard: str, job_id: int) -> list[dict]:
    """The files a job has written so far: job.out, each step's step.out, tables
    (.csv), structures, graphs and so on, by path within the job.

    Args:
        dashboard: The dashboard (see list_dashboards).
        job_id: The job's id.
    """
    client = _dashboard(dashboard)
    response = client._url_get(f"/api/jobs/{int(job_id)}/files")
    if response.status_code != 200:
        raise ValueError(
            f"Could not list the files of job {job_id} on '{dashboard}' (code "
            f"{response.status_code})."
        )
    return _file_list(response.json())


def read_job_file(
    dashboard: str,
    job_id: int,
    filename: str,
    tail_lines: int | None = None,
    max_characters: int = 50000,
) -> str:
    """The text of a file of a job, e.g. "job.out" (the job's output; look for
    "Caught exception in loop iteration", since loops carry on past errors), a
    step's "2/step.out", or a table such as "energies.csv".

    Args:
        dashboard: The dashboard (see list_dashboards).
        job_id: The job's id.
        filename: The file's path within the job (see list_job_files).
        tail_lines: Only the last this many lines.
        max_characters: At most this many characters (the end of the file when
            tail_lines is given, else the start).
    """
    job = _job(_dashboard(dashboard), job_id)
    text = job.get_file(filename)
    if text is None:
        raise ValueError(
            f"Could not read '{filename}' of job {job_id} on '{dashboard}'."
        )
    if tail_lines is not None:
        text = "\n".join(text.splitlines()[-int(tail_lines) :])
        if len(text) > max_characters:
            text = text[-max_characters:]
    elif len(text) > max_characters:
        text = text[:max_characters] + f"\n... ({len(text)} characters in all)"
    return text


_READ_ONLY = (
    list_steps,
    describe_step,
    show_flowchart,
    flowchart_tree,
    validate_flowchart,
)
_WRITING = (
    build_flowchart,
    set_parameters,
    insert_step,
    remove_step,
    move_step,
    convert_flowchart,
)
# Talk to dashboards: reading, and submitting (which starts real calculations)
_JOBS_READ = (
    list_dashboards,
    dashboard_info,
    job_status,
    list_jobs,
    list_job_files,
    read_job_file,
)


def _dashboard_errors():
    """The dashboard client's errors (connection, login, timeouts, ...)."""
    import seamm_dashboard_client.dashboard as client

    return tuple(
        getattr(client, name)
        for name in (
            "DashboardConnectionError",
            "DashboardLoginError",
            "DashboardNotRunningError",
            "DashboardSubmitError",
            "DashboardTimeoutError",
            "DashboardUnknownError",
        )
        if hasattr(client, name)
    )


def _guarded(function):
    """Report the errors users can fix to the client as tool errors, with their
    message, rather than as an unexplained failure."""
    import functools

    from mcp.server.mcpserver.exceptions import ToolError

    from .builder import FlowchartBuildError
    from .catalog import StepNotFoundError
    from .edit import EditError
    from .spec import SpecError

    expected = (
        FlowchartBuildError,
        StepNotFoundError,
        EditError,
        SpecError,
        ValueError,
        KeyError,
        *_dashboard_errors(),
    )

    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except expected as e:
            text = e.args[0] if isinstance(e, KeyError) and e.args else str(e)
            raise ToolError(str(text).strip('"'))

    return wrapper


def create_server():
    """The MCP server with the flowchart tools."""
    from contextlib import asynccontextmanager

    from mcp.server.mcpserver import MCPServer
    from mcp.types import ToolAnnotations

    @asynccontextmanager
    async def lifespan(server):
        # Load the plug-ins in the background once serving has started (when stray
        # output from them cannot reach the protocol stream), so the first call is
        # quick and the client is not kept waiting to connect.
        threading.Thread(target=_warm_up, daemon=True).start()
        yield {}

    try:
        from . import __version__ as version
    except Exception:
        version = ""

    server = MCPServer(
        name="seamm-flowchart",
        title="SEAMM flowcharts",
        description="Build, read, edit and check SEAMM flowcharts.",
        instructions=INSTRUCTIONS,
        version=str(version),
        lifespan=lifespan,
        log_level="WARNING",
    )
    for function in _READ_ONLY:
        server.add_tool(
            _guarded(function),
            annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False),
        )
    for function in _WRITING:
        server.add_tool(
            _guarded(function),
            annotations=ToolAnnotations(
                readOnlyHint=False,
                destructiveHint=function is remove_step,
                openWorldHint=False,
            ),
        )
    for function in _JOBS_READ:
        server.add_tool(
            _guarded(function),
            annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
        )
    server.add_tool(
        _guarded(submit_job),
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
    )
    return server


def _warm_up():
    try:
        # One step of each kind, which also parses the plug-ins' bibliographies. Under
        # the lock, like the tools: SEAMM's objects are not thread safe.
        with _lock:
            catalog().titles()
    except Exception as e:  # pragma: no cover
        logger.warning(f"Could not load the plug-ins: {e}")


def main():
    """Run the server over stdio."""
    create_server().run("stdio")
