# -*- coding: utf-8 -*-

"""Migrate an installation's jobs and datastore to flowchart format 3.0.

For an installation (a SEAMM root such as ~/SEAMM_DEV) this

* converts each job's ``flowchart.flow`` from format 2.0 (or 1.0) to 3.0 with the
  frozen converter, renaming the original to ``flowchart.v2.flow`` -- its content is
  never changed -- and writing the 3.0 file as ``flowchart.flow``;
* points each job in the datastore at the flowchart row for its own file's digest:
  rows that now have the same digest are merged, rows that the old digest wrongly
  merged (it stopped at the first loop) are split, and rows left without jobs are
  deleted. Rows keep their id where possible; permissions, projects and DOIs are
  carried over;
* converts rows that have no jobs from their own stored content.

By default nothing is changed: the plan is worked out and reported (a dry run).
With ``apply=True`` the datastore is first backed up, then changed in one
transaction, then the files are converted; a manifest of the file changes is written
so that they can be undone with ``undo()``.
"""

import datetime
import glob
import hashlib
import json
import logging
import os
from pathlib import Path
import sqlite3
import stat

from . import convert_v2
from .format3 import FORMAT, SHEBANG, dump_yaml, is_format3, load_yaml

logger = logging.getLogger(__name__)


class MigrationError(RuntimeError):
    """The migration cannot go ahead."""


def _flowchart_text(path):
    try:
        return Path(path).read_text()
    except (FileNotFoundError, NotADirectoryError):
        return None


class _Converter(object):
    """Converts flowchart texts, each distinct text once."""

    def __init__(self):
        self.cache = {}
        self.reports = {}

    def __call__(self, text):
        """(3.0 text or None, 3.0 data or None, report lines, error or None)"""
        key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if key not in self.cache:
            try:
                if is_format3(text):
                    self.cache[key] = (None, load_yaml(text), [], None)
                else:
                    data, report = convert_v2.convert_data(text)
                    text3 = SHEBANG + "\n" + dump_yaml(data)
                    self.cache[key] = (text3, data, report, None)
            except Exception as e:
                self.cache[key] = (None, None, [], f"{type(e).__name__}: {e}")
        return self.cache[key]


def _row_text(row):
    """A 2.0 flowchart's text rebuilt from its datastore row."""
    metadata = dict(json.loads(row["flowchart_metadata"] or "{}"))
    for key in ("title", "description"):
        if row[key] is not None:
            metadata[key] = row[key]
    for key in ("keywords", "creators"):
        if row[key] is not None:
            metadata[key] = json.loads(row[key])
    body = json.loads(row["json"])
    if not isinstance(body, str):
        body = json.dumps(body)
    version = row["flowchart_version"] or 2.0
    return (
        f"#!/usr/bin/env run_flowchart\n!MolSSI flowchart {version}\n#metadata\n"
        + json.dumps(metadata)
        + "\n#flowchart\n"
        + body
        + "\n#end\n"
    )


def _row_values(data):
    """The datastore columns for a 3.0 flowchart, as seamm_datastore stores them."""
    metadata = dict(data.get("metadata") or {})
    columns = {
        "title": metadata.pop("title", None),
        "description": metadata.pop("description", None),
        "keywords": json.dumps(metadata.pop("keywords", None)),
        "creators": json.dumps(metadata.pop("creators", None)),
        "sha256": data["digest"]["sha256"],
        "sha256_strict": data["digest"]["sha256_strict"],
        "flowchart_version": float(data["format"].split()[-1]),
        "json": json.dumps(data),
    }
    for key in ("doi", "conceptdoi"):
        if key in metadata:
            columns[key] = metadata.pop(key)
    columns["flowchart_metadata"] = json.dumps(metadata)
    return columns


def _out(target):
    """A row id, or ["new", n] for the n'th new row -- as JSON can hold it."""
    return list(target) if isinstance(target, tuple) else target


def plan(root, datastore=None):
    """Work out what migrating an installation would do, changing nothing.

    Parameters
    ----------
    root : str or Path
        The SEAMM root, e.g. ~/SEAMM_DEV.
    datastore : str or Path, optional
        The datastore; by default <root>/Jobs/seamm.db.

    Returns
    -------
    dict
        The plan: files to convert, datastore changes, and a summary.
    """
    root = Path(root).expanduser()
    datastore = (
        Path(datastore).expanduser() if datastore else root / "Jobs" / "seamm.db"
    )
    if not datastore.exists():
        raise MigrationError(f"There is no datastore at {datastore}")

    db = sqlite3.connect(f"file:{datastore}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    rows = {r["id"]: dict(r) for r in db.execute("select * from flowcharts")}
    jobs = [dict(r) for r in db.execute("select id, flowchart_id, path from jobs")]
    projects = {}
    for r in db.execute("select flowchart, project from flowchart_project"):
        projects.setdefault(int(r["flowchart"]), set()).add(int(r["project"]))
    db.close()

    convert = _Converter()
    summary = {}

    def count(key, n=1):
        summary[key] = summary.get(key, 0) + n

    # 1. The jobs' own flowcharts
    files = {}  # path of flowchart.flow -> {"text3", "report"}
    job_digest = {}  # job id -> sha256_strict of its own flowchart
    job_data = {}  # sha256_strict -> 3.0 data
    problems = []
    for job in jobs:
        path = Path(job["path"]) / "flowchart.flow" if job["path"] else None
        text = _flowchart_text(path) if path else None
        if text is None:
            count("jobs without a flowchart file")
            continue
        text3, data, report, error = convert(text)
        if error:
            count("jobs whose flowchart cannot be converted")
            problems.append(f"Job {job['id']}: {path}: {error}")
            continue
        if text3 is not None:
            files[str(path)] = {"text3": text3, "report": report}
            count("job flowcharts to convert")
        else:
            count("job flowcharts already 3.0")
        digest = data["digest"]["sha256_strict"]
        job_digest[job["id"]] = digest
        job_data[digest] = data

    # Job directories on disk that the datastore does not know
    known = {str(Path(j["path"]) / "flowchart.flow") for j in jobs if j["path"]}
    for path in sorted(
        glob.glob(str(root / "Jobs" / "projects" / "*" / "*" / "flowchart.flow"))
    ):
        if path in known:
            continue
        text3, data, report, error = convert(_flowchart_text(path))
        if error:
            problems.append(f"{path} (not in the datastore): {error}")
        elif text3 is not None:
            files[path] = {"text3": text3, "report": report}
            count("flowcharts in job directories not in the datastore, to convert")

    # 2. Which row each job's flowchart goes in
    old_row = {j["id"]: int(j["flowchart_id"]) for j in jobs if j["flowchart_id"]}
    groups = {}
    for job_id, digest in job_digest.items():
        groups.setdefault(digest, []).append(job_id)

    by_digest = {
        r["sha256_strict"]: rid
        for rid, r in rows.items()
        if r["flowchart_version"] and r["flowchart_version"] >= 3
    }
    claimed = {}  # row id -> digest
    targets = {}  # digest -> row id, or ("new", n)
    creations = []
    for digest, members in sorted(groups.items(), key=lambda g: (-len(g[1]), g[0])):
        if digest in by_digest and by_digest[digest] not in claimed:
            target = by_digest[digest]
        else:
            tally = {}
            for job_id in members:
                if job_id in old_row:
                    tally[old_row[job_id]] = tally.get(old_row[job_id], 0) + 1
            candidates = sorted(
                (rid for rid in tally if rid not in claimed and rid in rows),
                key=lambda rid: (-tally[rid], rid),
            )
            if candidates:
                target = candidates[0]
            else:
                source = (
                    max(tally, key=lambda rid: (tally[rid], -rid)) if tally else None
                )
                target = ("new", len(creations))
                creations.append({"digest": digest, "copy from": source})
        claimed[target] = digest
        targets[digest] = target

    updates = {}  # row id -> digest to write into it
    for digest, target in targets.items():
        if not isinstance(target, tuple):
            current = rows[target]
            if not (
                current["sha256_strict"] == digest
                and current["flowchart_version"]
                and current["flowchart_version"] >= 3
            ):
                updates[target] = digest

    repoint = {}
    for job_id, digest in job_digest.items():
        target = targets[digest]
        if old_row.get(job_id) != target:
            repoint[job_id] = target

    def final_counts():
        result = {}
        for job in jobs:
            rid = repoint.get(job["id"], old_row.get(job["id"]))
            result[rid] = result.get(rid, 0) + 1
        return result

    # Rows not chosen for any job's own flowchart: converted from their own content.
    # Those that still have jobs (whose files are missing or cannot be converted) keep
    # them, unless the content matches another row, into which they are merged.
    deletions = []
    own = {}  # row id -> digest after converting its own content
    counts = final_counts()
    for rid, row in sorted(rows.items()):
        if rid in claimed:
            continue
        if counts.get(rid, 0) == 0 and rid in set(old_row.values()):
            deletions.append(rid)  # all its jobs went elsewhere
            continue
        if row["flowchart_version"] and row["flowchart_version"] >= 3:
            continue
        text3, data, report, error = convert(_row_text(row))
        if error:
            problems.append(f"Row {rid}: its own content cannot be converted: {error}")
            continue
        digest = data["digest"]["sha256_strict"]
        other = targets.get(digest)
        if other is None:
            other = next((r for r, d in own.items() if d == digest), None)
        if other is not None:
            for job in jobs:
                if repoint.get(job["id"], old_row.get(job["id"])) == rid:
                    repoint[job["id"]] = other
            deletions.append(rid)
            count("rows whose own content duplicates another row, merged into it")
        else:
            own[rid] = digest
            job_data[digest] = data
            if counts.get(rid, 0):
                count("rows converted from their own content (their jobs lack files)")
            else:
                count("rows without jobs, converted from their own content")

    # DOIs and projects of deleted rows go to the row(s) their jobs went to
    carry = []
    for rid in deletions:
        moved_to = sorted(
            {repoint[j] for j in repoint if old_row.get(j) == rid}, key=str
        )
        for target in moved_to:
            carry.append({"to": _out(target), "from": rid})

    summary.update(
        {
            "rows updated in place": len(updates),
            "rows created (splits)": len(creations),
            "rows deleted (merged, or unused)": len(deletions),
            "jobs pointed at another row": len(repoint),
        }
    )
    report_lines = {}
    for data in files.values():
        for line in data["report"]:
            key = line.split(": ", 1)[-1]
            report_lines[key] = report_lines.get(key, 0) + 1

    return {
        "root": str(root),
        "datastore": str(datastore),
        "summary": summary,
        "problems": problems,
        "converter report": report_lines,
        "files": files,
        "updates": updates,
        "creations": creations,
        "repoint": {str(k): _out(v) for k, v in repoint.items()},
        "deletions": sorted(deletions),
        "own": {str(k): v for k, v in own.items()},
        "carry": carry,
        "data": job_data,
        "rows before": len(rows),
        "dois": {str(r): rows[r]["doi"] for r in rows if rows[r]["doi"]},
        "projects": {k: sorted(v) for k, v in projects.items()},
    }


def apply(the_plan, backup=True, files=True):
    """Carry out a plan made by plan(). The services must be stopped first.

    Parameters
    ----------
    the_plan : dict
        From plan().
    backup : bool
        Back up the datastore first.
    files : bool
        Also convert the job directories' files (False: only the datastore, e.g. to
        rehearse on a copy of it).

    Returns
    -------
    dict
        The paths of the datastore backup and of the manifest of file changes.
    """
    datastore = Path(the_plan["datastore"])
    root = Path(the_plan["root"])
    stamp = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")
    result = {}

    if backup:
        target = datastore.with_name(f"{datastore.name}.bak-{stamp}-before-format3")
        src = sqlite3.connect(str(datastore))
        dst = sqlite3.connect(str(target))
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
        result["backup"] = str(target)

    data = the_plan["data"]
    db = sqlite3.connect(str(datastore))
    db.row_factory = sqlite3.Row
    try:
        with db:
            rows = {r["id"]: dict(r) for r in db.execute("select * from flowcharts")}
            touched = list(the_plan["updates"]) + list(the_plan["own"])
            touched = [int(r) for r in touched]
            # Clear the digests being replaced first: sha256_strict is unique
            for rid in touched:
                db.execute(
                    "update flowcharts set sha256_strict=NULL where id=?", (rid,)
                )

            def write(rid, digest):
                values = _row_values(data[digest])
                old = rows[rid]
                for key in ("doi", "conceptdoi"):
                    if not values.get(key):
                        values[key] = old.get(key)
                sets = ", ".join(f"{k}=?" for k in values)
                db.execute(
                    f"update flowcharts set {sets} where id=?", (*values.values(), rid)
                )

            for rid, digest in the_plan["updates"].items():
                write(int(rid), digest)
            for rid, digest in the_plan["own"].items():
                write(int(rid), digest)

            new_ids = {}
            for n, creation in enumerate(the_plan["creations"]):
                values = _row_values(data[creation["digest"]])
                source = (
                    rows.get(creation["copy from"]) if creation["copy from"] else None
                )
                for key in (
                    "doi",
                    "conceptdoi",
                    "owner_id",
                    "owner_permissions",
                    "group_id",
                    "group_permissions",
                    "other_permissions",
                ):
                    if source is not None and not values.get(key):
                        values[key] = source.get(key)
                names = ", ".join(values)
                marks = ", ".join("?" for _ in values)
                cursor = db.execute(
                    f"insert into flowcharts ({names}) values ({marks})",
                    tuple(values.values()),
                )
                new_ids[n] = cursor.lastrowid
                if source is not None:
                    for (project,) in db.execute(
                        "select project from flowchart_project where flowchart=?",
                        (str(source["id"]),),
                    ).fetchall():
                        db.execute(
                            "insert into flowchart_project (flowchart, project) "
                            "values (?, ?)",
                            (str(cursor.lastrowid), project),
                        )

            def row_id(target):
                if isinstance(target, (list, tuple)):
                    return new_ids[int(target[1])]
                return int(target)

            for job_id, target in the_plan["repoint"].items():
                db.execute(
                    "update jobs set flowchart_id=? where id=?",
                    (str(row_id(target)), int(job_id)),
                )

            # Carry DOIs and projects from deleted rows, then delete them
            for item in the_plan["carry"]:
                tid = row_id(item["to"])
                for rid in [item["from"]]:
                    old = rows[rid]
                    for key in ("doi", "conceptdoi"):
                        if old.get(key):
                            db.execute(
                                f"update flowcharts set {key}=coalesce({key}, ?) "
                                "where id=?",
                                (old[key], tid),
                            )
                    for (project,) in db.execute(
                        "select project from flowchart_project where flowchart=?",
                        (str(rid),),
                    ).fetchall():
                        exists = db.execute(
                            "select 1 from flowchart_project where flowchart=? and "
                            "project=?",
                            (str(tid), project),
                        ).fetchone()
                        if not exists:
                            db.execute(
                                "insert into flowchart_project (flowchart, project) "
                                "values (?, ?)",
                                (str(tid), project),
                            )
            for rid in the_plan["deletions"]:
                remaining = db.execute(
                    "select count(*) from jobs where flowchart_id=?", (str(rid),)
                ).fetchone()[0]
                if remaining:
                    raise MigrationError(f"Row {rid} still has {remaining} jobs")
                db.execute(
                    "delete from flowchart_project where flowchart=?", (str(rid),)
                )
                db.execute("delete from flowcharts where id=?", (rid,))
    finally:
        db.close()

    if not files:
        return result

    # The files: rename the original, write the 3.0 flowchart
    manifest = {
        "root": str(root),
        "datastore backup": result.get("backup"),
        "files": [],
    }
    for path, info in the_plan["files"].items():
        path = Path(path)
        original = path.with_name("flowchart.v2.flow")
        if original.exists():
            logger.warning(f"{original} exists; not converting {path}")
            continue
        mode = stat.S_IMODE(os.lstat(path).st_mode)
        os.rename(path, original)
        path.write_text(info["text3"])
        os.chmod(path, mode)
        manifest["files"].append(str(path))
    manifest_path = root / "Jobs" / f"format3-migration-{stamp}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    result["manifest"] = str(manifest_path)
    return result


def undo_files(manifest_path):
    """Put back the original flowchart.flow files recorded in a manifest.

    The datastore is restored separately, from the backup named in the manifest.
    """
    manifest = json.loads(Path(manifest_path).read_text())
    restored = 0
    for path in manifest["files"]:
        path = Path(path)
        original = path.with_name("flowchart.v2.flow")
        if original.exists():
            os.replace(original, path)
            restored += 1
    return restored


def text_report(the_plan, examples=5):
    """A readable summary of a plan."""
    lines = [
        f"Migration of {the_plan['root']} to flowchart format 3.0",
        f"Datastore: {the_plan['datastore']} "
        f"({the_plan['rows before']} flowchart rows)",
        "",
    ]
    for key, value in the_plan["summary"].items():
        lines.append(f"  {key:66s} {value:6d}")
    if the_plan["converter report"]:
        lines += ["", "What the converter reported, by kind:"]
        for key, n in sorted(the_plan["converter report"].items(), key=lambda x: -x[1]):
            lines.append(f"  {n:5d}  {key}")
    if the_plan["problems"]:
        lines += ["", f"Problems ({len(the_plan['problems'])}):"]
        lines += [f"  {p}" for p in the_plan["problems"][: examples * 4]]
    if the_plan["creations"]:
        lines += ["", "New rows (a row whose jobs have different flowcharts is split):"]
        for c in the_plan["creations"][:examples]:
            lines.append(f"  from row {c['copy from']}: {c['digest'][:12]}...")
    if the_plan["deletions"]:
        lines += ["", f"Rows to delete: {the_plan['deletions'][:examples * 4]}"]
    dois = [c for c in the_plan["carry"] if the_plan["dois"].get(str(c["from"]))]
    if dois:
        lines += ["", "DOIs carried from deleted rows:"]
        for c in dois:
            lines.append(
                f"  row {c['from']} ({the_plan['dois'][str(c['from'])]}) -> {c['to']}"
            )
    return "\n".join(lines) + "\n"


__all__ = ["plan", "apply", "undo_files", "text_report", "MigrationError", "FORMAT"]
