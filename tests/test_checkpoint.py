#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests of the flowchart checkpoint (seamm/checkpoint.py)."""

import datetime
import json
import math
from pathlib import Path

import numpy as np
import pandas
import pytest

from molsystem import SystemDB
import seamm
from seamm.checkpoint import (
    Checkpointer,
    CheckpointError,
    Unrestorable,
    decode_value,
    flowchart_fingerprint,
    encode_value,
    read_checkpoint,
    resumable,
)
from seamm_util import Q_


class Step(seamm.Node):
    """A step that adds a system named after itself and sets a variable."""

    version = "2026.10.4"

    def __init__(self, flowchart=None, title="Step", fail=False):
        super().__init__(flowchart=flowchart, title=title)
        self.fail = fail

    def run(self):
        db = self.get_variable("_system_db")
        system = db.create_system(name=self.title)
        system.create_configuration(name=self.title)
        self.set_variable(f"ran_{self.title}", True)
        if self.fail:
            raise RuntimeError(f"{self.title} failed")
        return self.next()


class Thing:
    """An object that is not plain data."""

    def __init__(self, filename):
        self.filename = filename


class MakesThing(Step):
    """A step whose variable needs its help to be checkpointed."""

    def run(self):
        self.set_variable("thing", Thing("ff.frc"))
        return self.next()

    def checkpoint_variable(self, name, value):
        return {"filename": value.filename}

    def restore_variable(self, name, data):
        return Thing(data["filename"])


def make_flowchart(*steps):
    flowchart = seamm.Flowchart()
    previous = flowchart.get_node("1")
    nodes = []
    for step in steps:
        flowchart.add_node(step)
        flowchart.add_edge(previous, step, edge_type="execution")
        previous = step
        nodes.append(step)
    flowchart.set_ids()
    return flowchart, nodes


@pytest.fixture()
def job(tmp_path):
    """A job directory with a deferring job database and fresh variables."""
    db = SystemDB(filename=f"file:{tmp_path / 'seamm.db'}", deferred_commit=True)
    seamm.flowchart_variables = seamm.Variables()
    seamm.flowchart_variables.set_variable("_system_db", db)
    yield tmp_path, db
    seamm.checkpoint.set_checkpointer(None)
    seamm.flowchart_variables = None


def evaluate(flowchart, db, root, resume=None, command_line=()):
    """A minimal evaluator: what exec_flowchart does around each node."""
    checkpointer = Checkpointer(db, root, flowchart, command_line, resume=resume)
    seamm.checkpoint.set_checkpointer(checkpointer)
    checkpointer.restore_variables(seamm.flowchart_variables)
    node = checkpointer.start(flowchart.get_node("1"))
    try:
        while node is not None:
            current = node
            node = node.run()
            seamm.step_completed(current, node)
    except Exception:
        checkpointer.finish("error")
        raise
    checkpointer.finish("finished")
    return checkpointer


# --------------------------------------------------------------------------
# The codec
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        3,
        2.5,
        "text",
        [1, "a", None],
        (1, (2, 3)),
        {"a": 1, "b": [1, 2]},
        {1: "one", (2, 3): "pair"},
        {"__seamm__": "not a tag"},
        {1, 2, 3},
        Path("/tmp/x.sdf"),
        datetime.datetime(2026, 10, 4, 12, 0, tzinfo=datetime.timezone.utc),
        datetime.date(2026, 10, 4),
        np.float64(1.5),
        np.int32(7),
        np.arange(6, dtype=float).reshape(2, 3),
        np.array([["a", "b"]]),
    ],
)
def test_round_trip(value):
    text = json.dumps(encode_value(value))
    result = decode_value(json.loads(text))
    if isinstance(value, np.ndarray):
        assert result.dtype == value.dtype
        assert result.shape == value.shape
        assert (result == value).all()
    else:
        assert result == value
        assert type(result) is type(value)


def test_round_trip_nan():
    result = decode_value(json.loads(json.dumps(encode_value([math.nan, -math.inf]))))
    assert math.isnan(result[0]) and result[1] == -math.inf


def test_round_trip_quantity():
    value = Q_(np.array([1.0, 2.0]), "kJ/mol")
    result = decode_value(json.loads(json.dumps(encode_value(value))))
    assert str(result.units) == str(value.units)
    assert (result.magnitude == value.magnitude).all()


def test_round_trip_dataframe():
    value = pandas.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    result = decode_value(json.loads(json.dumps(encode_value(value))))
    assert result.equals(value)


def test_round_trip_table(job):
    root, db = job
    db.user_tables.create("energies", columns=[("E", "float")])
    value = seamm.Table(db, "energies")
    result = decode_value(json.loads(json.dumps(encode_value(value))), db)
    assert isinstance(result, seamm.Table) and result.name == "energies"


def test_unrestorable_fails_when_used():
    value = Unrestorable("_forcefield", "Forcefield", "2")
    assert "could not be restored" in repr(value) or "not restored" in repr(value)
    with pytest.raises(CheckpointError, match="_forcefield"):
        value.atom_types
    with pytest.raises(CheckpointError):
        len(value)
    with pytest.raises(CheckpointError):
        bool(value)
    variables = seamm.Variables()
    variables.set_variable("x", value)
    with pytest.raises(CheckpointError):
        variables.get_variable("x")


# --------------------------------------------------------------------------
# Writing, reading and resuming
# --------------------------------------------------------------------------


def systems(path):
    """The names of the systems committed in the job database."""
    import sqlite3

    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return [row[0] for row in db.execute("SELECT name FROM system ORDER BY id")]
    finally:
        db.close()


def test_no_checkpointer_just_commits(job):
    root, db = job
    db.deferred_commit = False
    db.create_system(name="x")
    seamm.step_completed(None)
    assert systems(root / "seamm.db") == ["x"]
    assert read_checkpoint(root / "seamm.db") is None


def test_finished_run(job):
    root, db = job
    flowchart, nodes = make_flowchart(Step(title="A"), Step(title="B"))
    evaluate(flowchart, db, root)
    checkpoint = read_checkpoint(root / "seamm.db")
    assert checkpoint["state"] == "finished"
    assert systems(root / "seamm.db") == ["A", "B"]
    mirror = json.loads((root / "checkpoint.json").read_text())
    assert mirror["state"] == "finished"
    ok, why = resumable(checkpoint, flowchart_fingerprint(flowchart), [])
    assert not ok and "finished" in why


def test_error_rolls_back_the_failing_step(job):
    root, db = job
    flowchart, nodes = make_flowchart(
        Step(title="A"), Step(title="B", fail=True), Step(title="C")
    )
    with pytest.raises(RuntimeError):
        evaluate(flowchart, db, root)
    checkpoint = read_checkpoint(root / "seamm.db")
    assert checkpoint["state"] == "error"
    assert checkpoint["position"] == [{"node": list(nodes[1]._id)}]
    # B's system was rolled back, and so was its variable in the checkpoint.
    assert systems(root / "seamm.db") == ["A"]
    assert "ran_A" in checkpoint["variables"]
    assert "ran_B" not in checkpoint["variables"]
    ok, why = resumable(checkpoint, flowchart_fingerprint(flowchart), [])
    assert ok, why


def test_resume_reruns_only_the_failed_step(job):
    root, db = job
    b = Step(title="B", fail=True)
    flowchart, nodes = make_flowchart(Step(title="A"), b, Step(title="C"))
    with pytest.raises(RuntimeError):
        evaluate(flowchart, db, root)

    # Fix the problem and resume.
    b.fail = False
    checkpoint = read_checkpoint(root / "seamm.db")
    seamm.flowchart_variables = seamm.Variables()
    seamm.flowchart_variables.set_variable("_system_db", db)
    evaluate(flowchart, db, root, resume=checkpoint)
    assert systems(root / "seamm.db") == ["A", "B", "C"]
    assert seamm.flowchart_variables.get_variable("ran_A") is True
    assert read_checkpoint(root / "seamm.db")["state"] == "finished"


def test_killed_process(tmp_path):
    """A process killed mid-step: earlier steps kept, the running one lost."""
    import subprocess
    import sys
    import textwrap

    script = textwrap.dedent(f"""
        import os, sys
        sys.path.insert(0, {str(Path(__file__).parent)!r})
        import seamm
        from molsystem import SystemDB
        from test_checkpoint import Step, make_flowchart, evaluate

        class Dies(Step):
            def run(self):
                db = self.get_variable("_system_db")
                db.create_system(name="half done")
                os._exit(9)

        db = SystemDB(filename="file:{tmp_path / 'seamm.db'}", deferred_commit=True)
        seamm.flowchart_variables = seamm.Variables()
        seamm.flowchart_variables.set_variable("_system_db", db)
        flowchart, nodes = make_flowchart(Step(title="A"), Dies(title="D"))
        evaluate(flowchart, db, {str(tmp_path)!r})
        """)
    result = subprocess.run([sys.executable, "-c", script])
    assert result.returncode == 9
    assert systems(tmp_path / "seamm.db") == ["A"]
    checkpoint = read_checkpoint(tmp_path / "seamm.db")
    assert checkpoint["state"] == "running"
    assert checkpoint["position"][0]["node"] == ["2"]


def test_resumable_reasons(job):
    root, db = job
    flowchart, nodes = make_flowchart(Step(title="A"), Step(title="B", fail=True))
    with pytest.raises(RuntimeError):
        evaluate(flowchart, db, root, command_line=["--n", "3"])
    checkpoint = read_checkpoint(root / "seamm.db")
    digest = flowchart_fingerprint(flowchart)
    assert resumable(checkpoint, digest, ["--n", "3"])[0]
    ok, why = resumable(checkpoint, digest, ["--n", "4"])
    assert not ok and "command line" in why
    ok, why = resumable(checkpoint, "another digest", ["--n", "3"])
    assert not ok and "flowchart has changed" in why
    ok, why = resumable(None, digest, [])
    assert not ok


def test_variables_that_need_their_step(job):
    root, db = job
    flowchart, nodes = make_flowchart(MakesThing(title="M"), Step(title="B", fail=True))
    seamm.flowchart_variables.set_variable("array", np.ones(3))
    with pytest.raises(RuntimeError):
        evaluate(flowchart, db, root)
    checkpoint = read_checkpoint(root / "seamm.db")
    assert "thing" in checkpoint["restorable"]

    # A resume reads the flowchart again: same steps, new uuids.
    flowchart, nodes = make_flowchart(MakesThing(title="M"), Step(title="B", fail=True))
    seamm.flowchart_variables = seamm.Variables()
    seamm.flowchart_variables.set_variable("_system_db", db)
    checkpointer = Checkpointer(db, root, flowchart, (), resume=checkpoint)
    checkpointer.restore_variables(seamm.flowchart_variables)
    assert seamm.flowchart_variables._origins["thing"] == str(nodes[0].uuid)
    thing = seamm.flowchart_variables.get_variable("thing")
    assert isinstance(thing, Thing) and thing.filename == "ff.frc"
    assert (seamm.flowchart_variables.get_variable("array") == np.ones(3)).all()


def test_unrestorable_variable(job):
    root, db = job
    flowchart, nodes = make_flowchart(Step(title="A"), Step(title="B", fail=True))
    # Set by a step that cannot save it, like a Custom step's function.
    seamm.flowchart_variables.set_variable("helper", lambda x: x, origin=nodes[0].uuid)
    with pytest.raises(RuntimeError):
        evaluate(flowchart, db, root)
    checkpoint = read_checkpoint(root / "seamm.db")
    assert checkpoint["unrestorable"]["helper"]["type"] == "function"

    seamm.flowchart_variables = seamm.Variables()
    seamm.flowchart_variables.set_variable("_system_db", db)
    checkpointer = Checkpointer(db, root, flowchart, (), resume=checkpoint)
    checkpointer.restore_variables(seamm.flowchart_variables)
    with pytest.raises(CheckpointError, match="helper"):
        seamm.flowchart_variables.get_variable("helper")
    # ... and it stays unrestorable in the next checkpoint
    assert "helper" in checkpointer.document()["unrestorable"]


def test_step_outside_the_position_is_not_resumable(job):
    """A step completing that the checkpointer was not told about."""
    root, db = job
    flowchart, nodes = make_flowchart(Step(title="A"), Step(title="B"))
    checkpointer = Checkpointer(db, root, flowchart)
    seamm.checkpoint.set_checkpointer(checkpointer)
    checkpointer.start(flowchart.get_node("1"))
    seamm.step_completed(nodes[1], None)  # not the node the position expects
    checkpoint = read_checkpoint(root / "seamm.db")
    assert checkpoint["resumable"] is False
    ok, why = resumable(checkpoint, flowchart_fingerprint(flowchart), [])
    assert not ok and "too old" in why


def test_current_system_restored(job):
    root, db = job
    flowchart, nodes = make_flowchart(
        Step(title="A"), Step(title="B"), Step(title="C", fail=True)
    )
    with pytest.raises(RuntimeError):
        evaluate(flowchart, db, root)
    db.system = db.get_system("A")  # as if the in-memory choice were lost
    checkpoint = read_checkpoint(root / "seamm.db")
    checkpointer = Checkpointer(db, root, flowchart, (), resume=checkpoint)
    checkpointer.restore_variables(seamm.Variables())
    assert db.system.name == "B"


def test_fingerprint_covers_loop_bodies_not_versions():
    """Unlike Flowchart.digest, which stops at a Loop and includes versions."""
    flowchart, nodes = make_flowchart(Step(title="A"), Step(title="B"))
    before = flowchart_fingerprint(flowchart)
    Step.version = "2099.1.1"
    try:
        assert flowchart_fingerprint(flowchart) == before
    finally:
        Step.version = "2026.10.4"
    extra = Step(flowchart, title="C")
    flowchart.add_node(extra)
    flowchart.add_edge(nodes[1], extra, edge_type="execution")
    assert flowchart_fingerprint(flowchart) != before
