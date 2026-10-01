#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Finding a package's data files, also in an editable (development) install,
whose list of files holds only its link to the source."""

import pytest

from seamm.node import _bibliography_path, _templates_path


def test_seamm_templates():
    path = _templates_path("seamm")
    assert path is not None
    assert (path / "line.graph_template").is_file()


def test_no_templates():
    assert _templates_path("seamm_util.printing") is None


def test_plugin_bibliography():
    """lammps_step (skipped if not installed) keeps it in data/."""
    pytest.importorskip("lammps_step")
    path = _bibliography_path("lammps_step")
    assert path is not None and path.name == "references.bib"


def test_bibliography_parsed_once(tmp_path):
    """Every new step reads its plug-in's references.bib, so it is parsed once."""
    from seamm.node import _read_bibliography

    path = tmp_path / "references.bib"
    path.write_text("@misc{one, title = {One}}\n")
    first = _read_bibliography(path)
    assert list(first) == ["one"]
    assert _read_bibliography(path) is first
    # A changed file is read again
    import os

    path.write_text("@misc{two, title = {Two}}\n")
    stamp = path.stat().st_mtime_ns + 1_000_000
    os.utime(path, ns=(stamp, stamp))
    assert list(_read_bibliography(path)) == ["two"]
