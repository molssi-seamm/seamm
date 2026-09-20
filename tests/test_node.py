# -*- coding: utf-8 -*-

"""Tests for seamm.Node helpers that don't need a full flowchart."""

import logging
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


# ---------------------------------------------------------------------
# model setter -- collapsing '/' in the method onto '-', keeping the
# method/basis separator as the last '/'.
# ---------------------------------------------------------------------
class _FakeModelNode:
    """Exposes the real model property on a bare object."""

    model = seamm.Node.model

    def __init__(self):
        self._model = None


def test_model_setter_no_slash_unchanged():
    node = _FakeModelNode()
    node.model = "PM7"
    assert node.model == "PM7"


def test_model_setter_single_slash_unchanged():
    node = _FakeModelNode()
    node.model = "mp2/6-31g"
    assert node.model == "mp2/6-31g"


def test_model_setter_collapses_slash_in_method():
    node = _FakeModelNode()
    node.model = "REVDSD-PBEP86-D4/2021/def2-QZVPP"
    assert node.model == "REVDSD-PBEP86-D4-2021/def2-QZVPP"


def test_model_setter_none_unchanged():
    node = _FakeModelNode()
    node.model = None
    assert node.model is None


class _FakeParameter:
    """Stand-in for a seamm.Parameter, which just holds the results dict."""

    def __init__(self, value):
        self.value = value


class _FakeProperties:
    """Minimal stand-in for molsystem's properties, with settable units."""

    def __init__(self, units):
        self._units = units
        self.values = {}

    def exists(self, name):
        return name in self._units

    def units(self, name):
        return self._units[name]

    def put(self, name, value):
        self.values[name] = value


class _FakeConfiguration:
    def __init__(self, properties):
        self.properties = properties


class _FakeResultsNode:
    """Just enough of a Node to call store_results() on."""

    metadata = {
        "results": {
            "T,inefficiency": {
                "description": "statistical inefficiency of the temperature",
                "dimensionality": "scalar",
                "property": "temperature, inefficiency#LAMMPS#{model}",
                "type": "float",
                "units": "",
            },
            "stress,inefficiency": {
                "description": "statistical inefficiency of the stress",
                "dimensionality": "[6]",
                "property": "stress, inefficiency#LAMMPS#{model}",
                "type": "json",
                "units": "",
            },
            "T": {
                "description": "temperature",
                "dimensionality": "scalar",
                "property": "temperature#LAMMPS#{model}",
                "type": "float",
                "units": "K",
            },
        }
    }

    def __init__(self, results):
        self.parameters = {"results": _FakeParameter(results)}
        self.model = "oplsaa+"
        self.logger = logging.getLogger("test")


def test_store_results_dimensionless_units_stored_as_null():
    """Properties read from e.g. an SDF may have NULL units.

    Those must compare equal to the "" in the step's metadata rather than being
    handed to Pint, which raises. See the temperature/stress "inefficiency"
    properties of the LAMMPS step.
    """
    results = {
        "T,inefficiency": {"property": "temperature, inefficiency#LAMMPS#{model}"},
        "stress,inefficiency": {"property": "stress, inefficiency#LAMMPS#{model}"},
    }
    properties = _FakeProperties(
        {
            "temperature, inefficiency#LAMMPS#oplsaa+": None,
            "stress, inefficiency#LAMMPS#oplsaa+": None,
        }
    )
    node = _FakeResultsNode(results)
    data = {
        "T,inefficiency": 3.5,
        "stress,inefficiency": [1.0, 2.0, 3.0, 0.0, 0.0, 0.0],
    }

    seamm.Node.store_results(
        node, configuration=_FakeConfiguration(properties), data=data
    )

    assert properties.values == {
        "temperature, inefficiency#LAMMPS#oplsaa+": 3.5,
        "stress, inefficiency#LAMMPS#oplsaa+": [1.0, 2.0, 3.0, 0.0, 0.0, 0.0],
    }


def test_store_results_still_converts_units():
    """The normalization must not break a real unit conversion."""
    results = {"T": {"property": "temperature#LAMMPS#{model}"}}
    properties = _FakeProperties({"temperature#LAMMPS#oplsaa+": "degC"})
    node = _FakeResultsNode(results)

    seamm.Node.store_results(
        node, configuration=_FakeConfiguration(properties), data={"T": 298.15}
    )

    assert properties.values["temperature#LAMMPS#oplsaa+"] == pytest.approx(25.0)
