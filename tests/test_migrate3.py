#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for migrating an installation to format 3.0, with stand-in steps."""

import json
import os
import sqlite3

import pytest

from seamm import convert_v2, format3, migrate3

from .test_builder import out_edges
from .test_format3 import build

SCHEMA = """
create table flowcharts (
    id integer primary key, sha256 text, sha256_strict text unique,
    flowchart_version float, doi text, conceptdoi text, title text, description text,
    creators json, keywords json, json json not null, flowchart_metadata json,
    other_permissions text, owner_id integer, owner_permissions text,
    group_id integer, group_permissions text
);
create table jobs (id integer primary key, flowchart_id text, path text);
create table flowchart_project (flowchart text, project text);
"""


def two_point_oh(body_method="HF"):
    """The 2.0 text of a flowchart; body_method changes a value in the loop body."""
    flowchart = build().flowchart
    loop = flowchart.get_nodes()[4]
    body = out_edges(flowchart, loop)[("execution", "loop")]
    body.parameters["method"].value = body_method
    return flowchart.to_text(format="2.0")


def section(text):
    return text.split("#flowchart\n", 1)[1].split("\n#end")[0]


@pytest.fixture
def installation(tmp_path):
    """A root with a datastore: row 1 is shared by two jobs whose flowcharts differ
    only inside a loop body (the 2.0 digest cannot tell them apart), row 2 belongs to
    a job whose directory is gone, and row 3 has no jobs but a DOI."""
    root = tmp_path / "SEAMM"
    jobs = root / "Jobs" / "projects" / "default"
    (root / "Jobs").mkdir(parents=True)
    db = sqlite3.connect(root / "Jobs" / "seamm.db")
    db.executescript(SCHEMA)

    texts = {
        "a": two_point_oh("HF"),
        "b": two_point_oh("MP2"),
        "c": two_point_oh("DFT"),
    }
    for n, (name, text) in enumerate([("a", texts["a"]), ("b", texts["b"])], start=1):
        path = jobs / f"Job_00000{n}"
        path.mkdir(parents=True)
        (path / "flowchart.flow").write_text(text)
        os.chmod(path / "flowchart.flow", 0o750)
        db.execute("insert into jobs values (?, ?, ?)", (n, "1", str(path)))
    db.execute("insert into jobs values (3, '2', ?)", (str(jobs / "Job_000003"),))

    def row(rid, text, doi=None):
        db.execute(
            "insert into flowcharts (id, sha256, sha256_strict, flowchart_version, "
            "doi, "
            "title, description, creators, keywords, json, flowchart_metadata, "
            "owner_id, owner_permissions) values (?, ?, ?, 2.0, ?, 'T', '', '[]', "
            "'[]', ?, '{}', 7, 'read')",
            (rid, f"old{rid}", f"old{rid}", doi, json.dumps(section(text))),
        )
        db.execute("insert into flowchart_project values (?, '1')", (str(rid),))

    row(1, texts["a"])
    row(2, texts["c"])
    row(3, texts["c"].replace('"MP2"', '"HF"'), doi="10.5281/zenodo.1")
    db.commit()
    db.close()
    return root, texts


def test_plan_changes_nothing(installation):
    root, texts = installation
    before = (root / "Jobs" / "seamm.db").read_bytes()
    the_plan = migrate3.plan(root)
    assert the_plan["summary"]["job flowcharts to convert"] == 2
    assert the_plan["summary"]["rows created (splits)"] == 1
    assert the_plan["summary"]["jobs without a flowchart file"] == 1
    assert (root / "Jobs" / "seamm.db").read_bytes() == before
    assert not list(root.rglob("flowchart.v2.flow"))


def test_apply(installation):
    root, texts = installation
    result = migrate3.apply(migrate3.plan(root))
    assert os.path.exists(result["backup"])

    db = sqlite3.connect(root / "Jobs" / "seamm.db")
    rows = {
        r[0]: r
        for r in db.execute(
            "select id, sha256_strict, flowchart_version, "
            "doi, owner_id from flowcharts"
        )
    }
    jobs = dict(db.execute("select id, flowchart_id from jobs"))
    # Both jobs had row 1; now each has a row with its own flowchart
    assert jobs[1] != jobs[2]
    for job, name in ((1, "a"), (2, "b")):
        digest = convert_v2.convert_data(texts[name])[0]["digest"]["sha256_strict"]
        assert rows[int(jobs[job])][1] == digest
    # The new row has the permissions and projects of the one it was split from
    new = max(rows)
    assert rows[new][4] == 7
    assert (
        db.execute(
            "select count(*) from flowchart_project where flowchart=?", (str(new),)
        ).fetchone()[0]
        == 1
    )
    # Row 2 (its job's directory is gone) and row 3 (no jobs) are converted in place
    assert jobs[3] == "2"
    assert rows[2][2] == 3.0 and rows[3][2] == 3.0
    assert rows[3][3] == "10.5281/zenodo.1"
    assert all(r[2] == 3.0 for r in rows.values())

    # The files: 3.0 in flowchart.flow, the original kept, the mode kept
    for n, name in ((1, "a"), (2, "b")):
        path = root / "Jobs" / "projects" / "default" / f"Job_00000{n}"
        assert format3.is_format3((path / "flowchart.flow").read_text())
        assert (path / "flowchart.v2.flow").read_text() == texts[name]
        assert oct(os.stat(path / "flowchart.flow").st_mode & 0o777) == "0o750"

    # Undo puts the files back
    assert migrate3.undo_files(result["manifest"]) == 2
    path = root / "Jobs" / "projects" / "default" / "Job_000001"
    assert (path / "flowchart.flow").read_text() == texts["a"]
    assert not (path / "flowchart.v2.flow").exists()


def test_apply_twice_changes_nothing_more(installation):
    root, _ = installation
    migrate3.apply(migrate3.plan(root))
    again = migrate3.plan(root)
    assert again["summary"].get("job flowcharts to convert", 0) == 0
    assert again["summary"]["job flowcharts already 3.0"] == 2
    assert again["summary"]["rows updated in place"] == 0
    assert again["summary"]["rows created (splits)"] == 0
    assert again["summary"]["jobs pointed at another row"] == 0


def test_no_datastore(tmp_path):
    with pytest.raises(migrate3.MigrationError, match="no datastore"):
        migrate3.plan(tmp_path)
