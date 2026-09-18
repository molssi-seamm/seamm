# -*- coding: utf-8 -*-

"""Tests for the standard structure-selection parameters and select_configurations."""

import pytest
from molsystem.system_db import SystemDB

from seamm.standard_parameters import (
    select_configurations,
    structure_selection_description,
    structure_selection_parameters,
)


def _P(**overrides):
    P = {k: v["default"] for k, v in structure_selection_parameters.items()}
    P.update(overrides)
    return P


@pytest.fixture()
def db():
    """Three systems: water (3 configurations), methane (2), ethanol (1)."""
    db = SystemDB(filename="file:selection_test?mode=memory&cache=shared")
    for name, confs in (
        ("water", ["frame1", "frame2", "frame3"]),
        ("methane", ["opt", "frame1"]),
        ("ethanol", ["opt"]),
    ):
        system = db.create_system(name=name)
        for cname in confs:
            system.create_configuration(name=cname)
    # leave 'water' as the current system with 'frame2' current
    db.system = db.get_system("water")
    db.system.configuration = db.system.configurations[1].id
    yield db
    db.close()


def _names(configurations):
    return [(c.system.name, c.name) for c in configurations]


def test_defaults_are_the_current_configuration(db):
    assert _names(select_configurations(db, _P())) == [("water", "frame2")]


def test_current_system_all_configurations(db):
    got = select_configurations(db, _P(**{"source configurations": "all"}))
    assert _names(got) == [
        ("water", "frame1"),
        ("water", "frame2"),
        ("water", "frame3"),
    ]


def test_last_and_first(db):
    assert _names(
        select_configurations(db, _P(**{"source configurations": "last"}))
    ) == [("water", "frame3")]
    assert _names(
        select_configurations(
            db, _P(**{"source systems": "all", "source configurations": "first"})
        )
    ) == [("water", "frame1"), ("methane", "opt"), ("ethanol", "opt")]


def test_all_systems_current_configurations(db):
    got = select_configurations(db, _P(**{"source systems": "all"}))
    # each system's current configuration: water's is frame2; the others default to
    # their last-created one
    assert _names(got)[0] == ("water", "frame2")
    assert len(got) == 3


def test_system_name_filters(db):
    P = _P(**{"source systems": "name is", "source system name": "methane"})
    P["source configurations"] = "all"
    assert _names(select_configurations(db, P)) == [
        ("methane", "opt"),
        ("methane", "frame1"),
    ]
    P = _P(**{"source systems": "name matches", "source system name": "*ethan*"})
    P["source configurations"] = "first"
    assert _names(select_configurations(db, P)) == [
        ("methane", "opt"),
        ("ethanol", "opt"),
    ]
    P = _P(
        **{"source systems": "name regexp", "source system name": "^(water|ethanol)$"}
    )
    P["source configurations"] = "last"
    assert _names(select_configurations(db, P)) == [
        ("water", "frame3"),
        ("ethanol", "opt"),
    ]


def test_configuration_name_filters(db):
    P = _P(**{"source systems": "all", "source configurations": "name is"})
    P["source configuration name"] = "opt"
    assert _names(select_configurations(db, P)) == [
        ("methane", "opt"),
        ("ethanol", "opt"),
    ]
    P["source configurations"] = "name matches"
    P["source configuration name"] = "frame*"
    assert _names(select_configurations(db, P)) == [
        ("water", "frame1"),
        ("water", "frame2"),
        ("water", "frame3"),
        ("methane", "frame1"),
    ]
    P["source configurations"] = "name regexp"
    P["source configuration name"] = r"frame[13]"
    assert _names(select_configurations(db, P)) == [
        ("water", "frame1"),
        ("water", "frame3"),
        ("methane", "frame1"),
    ]


def test_variable_holding_configurations_or_systems(db):
    water = db.get_system("water")
    confs = [water.configurations[0], water.configurations[2]]
    assert select_configurations(db, _P(**{"source systems": confs})) == confs
    systems = [db.get_system("methane"), db.get_system("ethanol")]
    P = _P(**{"source systems": systems, "source configurations": "all"})
    assert _names(select_configurations(db, P)) == [
        ("methane", "opt"),
        ("methane", "frame1"),
        ("ethanol", "opt"),
    ]


def test_empty_selection(db):
    P = _P(**{"source systems": "name is", "source system name": "nothing"})
    with pytest.raises(ValueError, match="No structures matched"):
        select_configurations(db, P)
    assert select_configurations(db, P, errors=False) == []
    with pytest.raises(ValueError):
        select_configurations(db, _P(**{"source systems": []}))


def test_bad_choices(db):
    with pytest.raises(ValueError):
        select_configurations(db, _P(**{"source systems": "some"}))
    with pytest.raises(ValueError):
        select_configurations(db, _P(**{"source configurations": "some"}))
    P = _P(**{"source systems": "name regexp", "source system name": "("})
    with pytest.raises(ValueError, match="Invalid regular expression"):
        select_configurations(db, P)


def test_description():
    assert structure_selection_description(_P()) == (
        "The current configuration of the current system will be used."
    )
    P = _P(**{"source systems": "all", "source configurations": "all"})
    assert structure_selection_description(P) == (
        "All configurations of every system will be used."
    )
    P = _P(**{"source systems": "name matches", "source system name": "H2O*"})
    P["source configurations"] = "last"
    assert "the systems matching 'H2O*'" in structure_selection_description(P)
    assert "last configuration" in structure_selection_description(P)
    assert "variable $frames" in structure_selection_description(
        _P(**{"source systems": "$frames"})
    )
