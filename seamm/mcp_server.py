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
