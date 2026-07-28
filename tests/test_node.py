# -*- coding: utf-8 -*-

"""Tests for seamm.Node helpers that don't need a full flowchart."""

from pathlib import Path

import pytest

import seamm


class _Chain:
    """Minimal stand-in exposing previous(), to exercise previous_nodes()."""

    def __init__(self, prev):
        self._prev = prev

    def previous(self):
        return self._prev


class _A(_Chain):
    pass


class _B(_Chain):
    pass


def test_previous_nodes_order():
    a = _A(None)
    b = _B(a)
    c = _A(b)
    # previous_nodes only uses previous(); call it with our stand-in as self.
    assert seamm.Node.previous_nodes(c) == [b, a]
    assert seamm.Node.previous_nodes(a) == []


def test_previous_nodes_type_filter():
    a = _A(None)
    b = _B(a)
    c = _A(b)
    assert seamm.Node.previous_nodes(c, _A) == [a]
    assert seamm.Node.previous_nodes(c, _B) == [b]
    assert seamm.Node.previous_nodes(c, (_A, _B)) == [b, a]


class _FakeNode:
    """Minimal stand-in exposing what file_path needs, including the real
    _parse_job_reference/_other_job_path (file_path calls them via
    'self.', so a fake needs them bound too)."""

    _parse_job_reference = staticmethod(seamm.Node._parse_job_reference)
    _other_job_path = seamm.Node._other_job_path

    def __init__(self, wd, job_path):
        self.wd = wd
        self.job_path = job_path


# ---------------------------------------------------------------------
# _parse_job_reference (staticmethod -- no fake node needed)
# ---------------------------------------------------------------------
def test_parse_job_reference_none_for_plain_string():
    assert seamm.Node._parse_job_reference("plain/path") is None


def test_parse_job_reference_shorthand():
    assert seamm.Node._parse_job_reference("job:xyz") == (None, "xyz")


def test_parse_job_reference_this_job_full_form():
    assert seamm.Node._parse_job_reference("job:///xyz") == (None, "xyz")


def test_parse_job_reference_other_job():
    assert seamm.Node._parse_job_reference("job://53/xyz") == (53, "xyz")


def test_parse_job_reference_malformed_single_slash():
    with pytest.raises(ValueError, match="Malformed"):
        seamm.Node._parse_job_reference("job:/xyz")


def test_parse_job_reference_malformed_no_tail():
    with pytest.raises(ValueError, match="Malformed"):
        seamm.Node._parse_job_reference("job://53")


def test_parse_job_reference_malformed_job_number():
    with pytest.raises(ValueError, match="not a job number"):
        seamm.Node._parse_job_reference("job://abc/xyz")


# ---------------------------------------------------------------------
# file_path
# ---------------------------------------------------------------------
def test_file_path_relative(tmp_path):
    node = _FakeNode(wd=tmp_path / "3", job_path=tmp_path)
    assert seamm.Node.file_path(node, "foo.txt") == tmp_path / "3" / "foo.txt"


def test_file_path_relative_to_override(tmp_path):
    node = _FakeNode(wd=tmp_path / "3", job_path=tmp_path)
    other = tmp_path / "other"
    result = seamm.Node.file_path(node, "foo.txt", relative_to=other)
    assert result == other / "foo.txt"


def test_file_path_absolute_used_as_is(tmp_path):
    """No sandboxing -- an absolute path is honored as-is, e.g. to gather
    results into a folder in the user's home directory."""
    node = _FakeNode(wd=tmp_path / "3", job_path=tmp_path)
    somewhere = tmp_path.parent / "elsewhere" / "foo.txt"
    assert seamm.Node.file_path(node, str(somewhere)) == somewhere


def test_file_path_tilde_expanded(tmp_path):
    node = _FakeNode(wd=tmp_path / "3", job_path=tmp_path)
    result = seamm.Node.file_path(node, "~/foo.txt")
    assert result == Path("~/foo.txt").expanduser()


def test_file_path_job_shorthand_and_full_form(tmp_path):
    node = _FakeNode(wd=tmp_path / "3", job_path=tmp_path)
    assert seamm.Node.file_path(node, "job:foo.txt") == tmp_path / "foo.txt"
    assert seamm.Node.file_path(node, "job:///foo.txt") == tmp_path / "foo.txt"


def test_file_path_other_job_requires_read_only(tmp_path):
    jobs_root = tmp_path / "Jobs"
    other_job = jobs_root / "projects" / "default" / "Job_000053"
    other_job.mkdir(parents=True)
    this_job = jobs_root / "projects" / "default" / "Job_000001"
    this_job.mkdir(parents=True)
    node = _FakeNode(wd=this_job / "3", job_path=this_job)

    with pytest.raises(ValueError, match="read_only"):
        seamm.Node.file_path(node, "job://53/foo.txt")

    result = seamm.Node.file_path(node, "job://53/foo.txt", read_only=True)
    assert result == other_job / "foo.txt"


# ---------------------------------------------------------------------
# _other_job_path
# ---------------------------------------------------------------------
def test_other_job_path_not_found(tmp_path):
    jobs_root = tmp_path / "Jobs"
    this_job = jobs_root / "projects" / "default" / "Job_000001"
    this_job.mkdir(parents=True)
    node = _FakeNode(wd=this_job / "3", job_path=this_job)
    with pytest.raises(ValueError, match="Could not find job"):
        seamm.Node._other_job_path(node, 999)


def test_other_job_path_requires_jobs_root(tmp_path):
    this_job = tmp_path / "somewhere" / "else" / "Job_000001"
    this_job.mkdir(parents=True)
    node = _FakeNode(wd=this_job / "3", job_path=this_job)
    with pytest.raises(ValueError, match="Jobs"):
        seamm.Node._other_job_path(node, 5)
