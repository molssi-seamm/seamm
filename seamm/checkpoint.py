# -*- coding: utf-8 -*-

"""What happens between the steps of a running flowchart: the checkpoint.

The flowchart evaluator and the Loop step (which runs its body itself) both call
:func:`step_completed` after each step. With a :class:`Checkpointer` installed (by
the evaluator, for a job database in the job's directory), that commits the
step's database writes -- the job database defers molsystem's own commits while
a step runs, so a step is one transaction -- and in the same transaction records
where the flowchart has got to, so that a rerun with ``--resume`` can continue
from there. Without one it just commits, as before.

The checkpoint is one JSON document in a one-row ``_checkpoint`` table of the
job database, mirrored to ``checkpoint.json`` in the job directory for people.
Decisions are only ever taken from the database copy. See the phase 5 notes in
seamm_exec's developer guide (campaigns/2026-10-02/NOTES_phase5.rst).
"""

import datetime
import importlib.metadata
import json
import logging
import os
from pathlib import Path, PurePath
import sqlite3

import seamm

logger = logging.getLogger(__name__)

FORMAT = 1
TABLE = "_checkpoint"

# Variables the evaluator makes itself, never saved or restored.
EVALUATOR_VARIABLES = (
    "printer",
    "_system_db",
    "__builtins__",
    "_start_time",
    "_job_id",
)

_checkpointer = None


class CheckpointError(RuntimeError):
    """A checkpoint cannot be written, read or used."""


def get_checkpointer():
    """The checkpointer of the running flowchart, or None."""
    return _checkpointer


def set_checkpointer(checkpointer):
    """Install (or, with None, remove) the checkpointer of the running flowchart."""
    global _checkpointer
    _checkpointer = checkpointer


def step_completed(node=None, next_node=None):
    """Record that a step has finished: commit, and checkpoint if enabled.

    Parameters
    ----------
    node : seamm.Node
        The step that finished.
    next_node : seamm.Node or None
        The step that runs next: None at the end of the flowchart; the Loop
        itself at the end of an iteration of its body.
    """
    if _checkpointer is not None:
        _checkpointer.step_completed(node, next_node)
        return
    variables = seamm.flowchart_variables
    if variables is not None and variables.exists("_system_db"):
        variables.get_variable("_system_db").db.commit()


# --------------------------------------------------------------------------
# Variables
# --------------------------------------------------------------------------


class _NotEncodable(Exception):
    pass


class Unrestorable:
    """Stands in for a variable that could not be restored on resume.

    Using it in almost any way raises a CheckpointError that says what it was,
    so a step that needs it fails clearly; a flowchart whose later steps never
    touch it resumes normally.
    """

    def __init__(self, name, type_name, origin=None):
        self._name = name
        self._type = type_name
        self._origin = origin

    @property
    def message(self):
        where = "" if self._origin is None else f" set by step {self._origin}"
        return (
            f"The variable '{self._name}' (a {self._type}{where}) could not be "
            "saved in the checkpoint, so it is not available after the job "
            "resumed. Rerun the job without --resume to run it from the top."
        )

    def _fail(self, *args, **kwargs):
        raise CheckpointError(self.message)

    def __getattr__(self, attribute):
        if attribute.startswith("__") and attribute.endswith("__"):
            raise AttributeError(attribute)
        raise CheckpointError(self.message)

    def __repr__(self):
        return f"<variable '{self._name}' not restored from the checkpoint>"

    __str__ = __repr__

    __call__ = __iter__ = __len__ = __bool__ = __getitem__ = __setitem__ = _fail
    __contains__ = __add__ = __radd__ = __sub__ = __rsub__ = __mul__ = _fail
    __rmul__ = __truediv__ = __rtruediv__ = __floordiv__ = __mod__ = _fail
    __pow__ = __neg__ = __abs__ = __float__ = __int__ = __index__ = _fail
    __lt__ = __le__ = __gt__ = __ge__ = __format__ = __fspath__ = _fail

    def __eq__(self, other):
        self._fail()

    __hash__ = object.__hash__


def encode_value(value):
    """Encode a value as JSON-compatible data, or raise _NotEncodable."""
    # Exact types: numpy's float64 is a float, and must keep its type.
    if value is None or type(value) in (bool, int, str, float):
        return value  # json writes NaN/Infinity for floats, and reads them back
    if isinstance(value, list):
        return [encode_value(v) for v in value]
    if isinstance(value, tuple):
        return {"__seamm__": "tuple", "items": [encode_value(v) for v in value]}
    if isinstance(value, (set, frozenset)):
        return {"__seamm__": "set", "items": [encode_value(v) for v in value]}
    if isinstance(value, dict):
        if all(isinstance(k, str) for k in value) and "__seamm__" not in value:
            return {k: encode_value(v) for k, v in value.items()}
        return {
            "__seamm__": "dict",
            "items": [[encode_value(k), encode_value(v)] for k, v in value.items()],
        }
    if isinstance(value, PurePath):
        return {"__seamm__": "path", "value": str(value)}
    if isinstance(value, datetime.datetime):
        return {"__seamm__": "datetime", "value": value.isoformat()}
    if isinstance(value, datetime.date):
        return {"__seamm__": "date", "value": value.isoformat()}
    if isinstance(value, seamm.Table):
        return {"__seamm__": "table", "name": value.name}

    module = type(value).__module__.split(".")[0]
    if module == "numpy":
        import numpy as np

        if isinstance(value, np.ndarray):
            if value.dtype == object:
                return {
                    "__seamm__": "ndarray",
                    "dtype": "object",
                    "shape": list(value.shape),
                    "data": [encode_value(v) for v in value.ravel().tolist()],
                }
            return {
                "__seamm__": "ndarray",
                "dtype": value.dtype.str,
                "shape": list(value.shape),
                "data": value.ravel().tolist(),
            }
        if isinstance(value, np.generic):
            return {
                "__seamm__": "npscalar",
                "dtype": value.dtype.str,
                "value": value.item(),
            }
    if module == "pint" or hasattr(value, "magnitude") and hasattr(value, "units"):
        return {
            "__seamm__": "quantity",
            "magnitude": encode_value(value.magnitude),
            "units": str(value.units),
        }
    if module == "pandas":
        import pandas

        if isinstance(value, pandas.DataFrame):
            return {"__seamm__": "dataframe", "value": value.to_json(orient="split")}
        if isinstance(value, pandas.Series):
            return {"__seamm__": "series", "value": value.to_json(orient="split")}
    if isinstance(value, (bool, int, float, str)):
        # Other subclasses (enums, ...) as the plain value.
        for kind in (bool, int, float, str):
            if isinstance(value, kind):
                return kind(value)
    raise _NotEncodable(type(value).__name__)


def decode_value(data, system_db=None):
    """The inverse of encode_value."""
    if isinstance(data, list):
        return [decode_value(v, system_db) for v in data]
    if not isinstance(data, dict):
        return data
    kind = data.get("__seamm__")
    if kind is None:
        return {k: decode_value(v, system_db) for k, v in data.items()}
    if kind == "tuple":
        return tuple(decode_value(v, system_db) for v in data["items"])
    if kind == "set":
        return set(decode_value(v, system_db) for v in data["items"])
    if kind == "dict":
        return {
            _hashable(decode_value(k, system_db)): decode_value(v, system_db)
            for k, v in data["items"]
        }
    if kind == "path":
        return Path(data["value"])
    if kind == "datetime":
        return datetime.datetime.fromisoformat(data["value"])
    if kind == "date":
        return datetime.date.fromisoformat(data["value"])
    if kind == "table":
        return seamm.Table(system_db, data["name"])
    if kind == "ndarray":
        import numpy as np

        if data["dtype"] == "object":
            values = [decode_value(v, system_db) for v in data["data"]]
            result = np.empty(len(values), dtype=object)
            result[:] = values
            return result.reshape(data["shape"])
        return np.array(data["data"], dtype=np.dtype(data["dtype"])).reshape(
            data["shape"]
        )
    if kind == "npscalar":
        import numpy as np

        return np.dtype(data["dtype"]).type(data["value"])
    if kind == "quantity":
        from seamm_util import Q_

        return Q_(decode_value(data["magnitude"], system_db), data["units"])
    if kind == "dataframe":
        import io
        import pandas

        return pandas.read_json(io.StringIO(data["value"]), orient="split")
    if kind == "series":
        import io
        import pandas

        return pandas.read_json(
            io.StringIO(data["value"]), orient="split", typ="series"
        )
    raise CheckpointError(f"Unknown kind of value '{kind}' in the checkpoint.")


def _hashable(value):
    if isinstance(value, list):
        return tuple(_hashable(v) for v in value)
    if isinstance(value, set):
        return frozenset(value)
    return value


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------


def read_checkpoint(path):
    """The checkpoint stored in a job database, or None.

    Opens the database read-only, so it can be used on a database another
    process has open.

    Parameters
    ----------
    path : str or pathlib.Path
        The job database, normally ``<job>/seamm.db``.

    Returns
    -------
    dict or None
        The checkpoint document, or None if the database has none (including a
        database from before checkpoints existed, or no database at all).
    """
    path = Path(path)
    if not path.exists():
        return None
    try:
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10.0)
    except sqlite3.Error:
        return None
    try:
        row = db.execute(f"SELECT document FROM {TABLE} WHERE id = 1").fetchone()
    except sqlite3.Error:
        return None
    finally:
        db.close()
    if row is None:
        return None
    return json.loads(row[0])


def changed_versions(checkpoint, flowchart):
    """The packages whose versions differ from those the checkpoint recorded.

    Returns
    -------
    [(str, str, str)]
        (package, version in the checkpoint, version now), sorted.
    """
    then = checkpoint.get("versions", {})
    now = package_versions(flowchart)
    return [
        (package, then.get(package, "-"), now.get(package, "-"))
        for package in sorted(set(then) | set(now))
        if then.get(package) != now.get(package)
    ]


def describe_position(checkpoint):
    """A short description of where a checkpoint is, for people."""
    text = []
    for frame in checkpoint.get("position", []):
        node = frame.get("node")
        loop = frame.get("loop")
        if loop is not None:
            text.append(
                f"step {'.'.join(frame['node'])}, iteration {loop.get('count')} of "
                f"{loop.get('length')}"
            )
        elif node is not None:
            text.append(f"step {'.'.join(node)}")
    if len(text) == 0:
        return "the end of the flowchart"
    return ", ".join(text)


def resumable(checkpoint, digest, command_line):
    """Whether a checkpoint can be resumed by this flowchart and command line.

    Returns
    -------
    (bool, str)
        Whether, and if not, why not.
    """
    if checkpoint is None:
        return False, "there is no checkpoint"
    if checkpoint.get("format") != FORMAT:
        return False, f"the checkpoint has format {checkpoint.get('format')}"
    if checkpoint.get("state") == "finished":
        return False, "the previous run finished"
    if not checkpoint.get("resumable", True):
        return False, checkpoint.get(
            "why not resumable", "the checkpoint is marked not resumable"
        )
    if checkpoint.get("flowchart_digest_strict") != digest:
        return False, "the flowchart has changed since the checkpoint was written"
    if list(checkpoint.get("command_line", [])) != list(command_line):
        return False, "the command line differs from the one checkpointed"
    if len(checkpoint.get("position", [])) == 0:
        return False, "the checkpoint does not say where to continue"
    return True, ""


# --------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------


def _id(node):
    return None if node is None else [str(x) for x in node._id]


def find_node(flowchart, node_id):
    """The node of the flowchart with the given id (a list of strings), or None.

    Searches the whole graph rather than following the steps, which cannot get
    past a Loop. Ids are unique once the flowchart's ids are set, and a Loop sets
    the ids of its body for each iteration.
    """
    target = [str(x) for x in node_id]
    for node in flowchart:
        if node._id is not None and _id(node) == target:
            return node
    return None


def package_versions(flowchart):
    """The versions of seamm and of the packages of the flowchart's steps."""
    packages = {"seamm", "molsystem", "seamm_exec", "seamm_util"}
    for node in flowchart:
        packages.add(type(node).__module__.split(".")[0])
    versions = {}
    for package in sorted(packages):
        for name in (package, package.replace("_", "-")):
            try:
                versions[package] = importlib.metadata.version(name)
                break
            except importlib.metadata.PackageNotFoundError:
                continue
    return versions


class Checkpointer:
    """Writes the checkpoint of a running flowchart, and guides a resume.

    The position is a stack of frames, outermost first. Each frame names the
    node to run next at its level (None after the last one); a frame whose node
    is a Loop that is part way through also holds the Loop's own state under
    ``loop`` and is followed by the frame of the loop's body.

    Parameters
    ----------
    system_db : molsystem.SystemDB
        The job database, opened with ``deferred_commit=True``.
    root : str or pathlib.Path
        The job directory, for the ``checkpoint.json`` mirror.
    flowchart : seamm.Flowchart
        The flowchart being run.
    command_line : [str]
        The command-line arguments of the run.
    resume : dict
        The checkpoint being resumed from, or None for a run from the top.
    """

    def __init__(self, system_db, root, flowchart, command_line=(), resume=None):
        self.system_db = system_db
        self.root = Path(root)
        self.flowchart = flowchart
        self.command_line = list(command_line)
        self.digest = flowchart.digest(strict=True)
        self.versions = package_versions(flowchart)
        self.frames = [{"node": None}]
        self.resumable = True
        self.why_not = ""
        self.resumed_from = resume  # the whole document, kept
        self.resume = resume  # the position still to be resumed into
        self._resume_depth = 0
        self._last_document = None
        if resume is not None:
            self.frames = [dict(frame) for frame in resume["position"]]

    # Where to start -------------------------------------------------------

    def start(self, first_node):
        """The node the evaluator starts at: the first, or where to resume."""
        if self.resume is None:
            self.frames = [{"node": _id(first_node)}]
            return first_node
        target = self.resume["position"][0]["node"]
        node = find_node(self.flowchart, target)
        if node is None:
            raise CheckpointError(
                f"Cannot find step {'.'.join(target)} to resume at in the flowchart."
            )
        self.frames = [{"node": _id(node)}]
        if "loop" not in self.resume["position"][0]:
            self.resume = None
        return node

    def restore_variables(self, variables):
        """Put the checkpointed variables into the flowchart's variables."""
        document = self.resumed_from
        if document is None:
            return
        for name, data in document.get("variables", {}).items():
            try:
                variables._data[name] = decode_value(data, self.system_db)
            except Exception as e:
                logger.warning(f"Could not restore variable '{name}': {e}")
                variables._data[name] = Unrestorable(name, "value", None)
        for name, saved in document.get("restorable", {}).items():
            node = self.flowchart.get_node(saved["origin"])
            value = None
            if node is not None:
                try:
                    value = node.restore_variable(name, saved["data"])
                except Exception as e:
                    logger.warning(f"Could not restore variable '{name}': {e}")
                    value = None
            if value is None:
                value = Unrestorable(name, saved.get("type", "?"), saved.get("step"))
            variables._data[name] = value
        for name, info in document.get("unrestorable", {}).items():
            variables._data[name] = Unrestorable(name, info["type"], info.get("step"))
        origins = document.get("origins", {})
        variables._origins.update({k: v for k, v in origins.items()})
        system_id = document.get("system_id")
        if system_id is not None and system_id in self.system_db.system_ids:
            self.system_db.system = system_id

    # Loops ----------------------------------------------------------------

    def _level(self, node):
        """The level of the frame whose next node is ``node``, or None."""
        target = _id(node)
        for level in range(len(self.frames) - 1, -1, -1):
            if self.frames[level].get("node") == target:
                return level
        return None

    def loop_resume(self, loop):
        """If resuming into this Loop, its saved state and where its body resumes.

        Returns
        -------
        (dict, [str] or None) or None
            The Loop's state, and the id of the body node to start at (None if the
            saved iteration had finished), or None if not resuming into this Loop.
        """
        if self.resume is None:
            return None
        position = self.resume["position"]
        level = self._resume_depth
        if level >= len(position) or position[level].get("node") != _id(loop):
            return None
        frame = position[level]
        if "loop" not in frame:
            return None
        self._resume_depth += 1
        inner = position[level + 1]["node"] if level + 1 < len(position) else None
        if level + 1 >= len(position) or "loop" not in position[level + 1]:
            # Nothing deeper to resume into.
            self.resume = None
        failed = frame.get("failed", [])
        here = self._level(loop)
        if here is not None:
            self.frames[here]["failed"] = list(failed)
        return frame["loop"], inner

    def enter_iteration(self, loop, state, first_node):
        """A Loop starts (or resumes) an iteration of its body.

        Parameters
        ----------
        loop : seamm.Node
            The Loop.
        state : dict
            The Loop's state, JSON-compatible, enough to set up this iteration
            again; it should include ``count`` and ``length`` for messages.
        first_node : seamm.Node
            The body node that runs first in this iteration.
        """
        level = self._level(loop)
        if level is None:
            self._not_resumable(
                f"the Loop {'.'.join(_id(loop))} is not in the position"
            )
            return
        self.frames[level]["loop"] = state
        del self.frames[level + 1 :]
        self.frames.append({"node": _id(first_node)})
        # Written now, so the iteration's set-up (its directory name, current
        # row, ...) is on record before its body runs.
        self.write()

    def iteration_failed(self, loop, node):
        """A Loop caught an error in its body and continues: keep the writes."""
        level = self._level(loop)
        if level is not None:
            state = self.frames[level].get("loop", {})
            failed = self.frames[level].setdefault("failed", [])
            failed.append(state.get("count"))
            del self.frames[level + 1 :]
            self.frames[level]["loop"] = dict(state, done=True)
        self.write()

    def leave_loop(self, loop):
        """A Loop has finished all its iterations (or broken out)."""
        level = self._level(loop)
        if level is not None:
            self.frames[level].pop("loop", None)
            self.frames[level].pop("failed", None)
            del self.frames[level + 1 :]

    # Steps ----------------------------------------------------------------

    def step_completed(self, node, next_node):
        """A step finished: move the position on, then commit and checkpoint."""
        level = self._level(node) if node is not None else None
        if level is None or level != len(self.frames) - 1:
            # A step this checkpointer was not told about, e.g. the body of a
            # Loop from a loop_step that predates checkpoints.
            self._not_resumable(
                f"step {'.'.join(_id(node)) if node is not None else '?'} ran "
                "outside the checkpointed position (a plug-in too old to "
                "checkpoint?)"
            )
        elif (
            level > 0
            and next_node is not None
            and (_id(next_node) == self.frames[level - 1].get("node"))
        ):
            # The end of an iteration of a Loop's body.
            del self.frames[level:]
            state = self.frames[level - 1].get("loop")
            if state is not None:
                self.frames[level - 1]["loop"] = dict(state, done=True)
        else:
            self.frames[level]["node"] = _id(next_node)
        self.write()

    def _not_resumable(self, why):
        if self.resumable:
            logger.warning(f"This job will not be resumable: {why}.")
        self.resumable = False
        self.why_not = why

    # The document ----------------------------------------------------------

    def document(self, state="running"):
        """The checkpoint as a JSON-compatible dictionary."""
        variables = seamm.flowchart_variables
        encoded = {}
        restorable = {}
        unrestorable = {}
        origins = {}
        if variables is not None:
            origins = dict(getattr(variables, "_origins", {}))
            for name, value in variables._data.items():
                if name in EVALUATOR_VARIABLES or isinstance(value, Unrestorable):
                    if isinstance(value, Unrestorable):
                        unrestorable[name] = {
                            "type": value._type,
                            "step": value._origin,
                        }
                    continue
                try:
                    encoded[name] = encode_value(value)
                    continue
                except _NotEncodable:
                    pass
                type_name = type(value).__name__
                origin = origins.get(name)
                step = None
                saved = None
                if origin is not None:
                    node = self.flowchart.get_node(origin)
                    if node is not None:
                        step = ".".join(_id(node) or [])
                        try:
                            saved = node.checkpoint_variable(name, value)
                        except Exception as e:
                            logger.warning(f"Could not checkpoint '{name}': {e}")
                if saved is not None:
                    restorable[name] = {
                        "origin": origin,
                        "data": saved,
                        "type": type_name,
                        "step": step,
                    }
                else:
                    # Including the modules and functions a Custom step leaves.
                    unrestorable[name] = {"type": type_name, "step": step}

        system_id = getattr(self.system_db, "_current_system_id", None)
        document = {
            "format": FORMAT,
            "state": state,
            "resumable": self.resumable,
            "flowchart_digest_strict": self.digest,
            "command_line": self.command_line,
            "versions": self.versions,
            "written": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "position": self.frames,
            "system_id": system_id,
            "variables": encoded,
            "restorable": restorable,
            "unrestorable": unrestorable,
            "origins": origins,
        }
        if not self.resumable:
            document["why not resumable"] = self.why_not
        return document

    def write(self, state="running", document=None):
        """Write the checkpoint and commit, then mirror it to checkpoint.json."""
        if document is None:
            document = self.document(state)
        self._last_document = document
        text = json.dumps(document, indent=1)
        db = self.system_db.db
        db.execute(
            f"CREATE TABLE IF NOT EXISTS {TABLE} "
            "(id INTEGER PRIMARY KEY CHECK (id = 1), document TEXT NOT NULL)"
        )
        db.execute(
            f"INSERT OR REPLACE INTO {TABLE} (id, document) VALUES (1, ?)", (text,)
        )
        self.system_db.commit_transaction()
        try:
            mirror = self.root / "checkpoint.json"
            tmp = self.root / "checkpoint.json.tmp"
            tmp.write_text(text + "\n")
            os.replace(tmp, mirror)
        except OSError as e:
            logger.warning(f"Could not write checkpoint.json: {e}")

    def finish(self, state):
        """The end of the run: 'finished', or 'error' after rolling back.

        For an error, the step that raised is abandoned (its writes are rolled
        back), so the database matches the checkpoint and a resume re-runs it.
        """
        if state == "finished":
            self.frames = []
            self.write(state)
            return
        self.system_db.rollback_transaction()
        if self._last_document is None:
            self.write(state)
        else:
            # The database is back at the last checkpoint, so is everything else:
            # not the variables as the failing step left them.
            document = dict(self._last_document, state=state)
            document["written"] = datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat()
            self.write(state, document=document)
