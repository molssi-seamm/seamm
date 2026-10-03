# -*- coding: utf-8 -*-

"""Old parameter values in flowcharts (seamm#221) and Path names (seamm#220)."""

from pathlib import Path

import pytest

import seamm
from seamm.standard_parameters import (
    safe_format,
    structure_handling_description,
    structure_handling_parameters,
)


@pytest.mark.parametrize(
    "old, new",
    [
        ("be put in a new configuration", "Create a new configuration"),
        ("overwrite the current configuration", "Overwrite the current configuration"),
        ("be put in a new system", "Create a new system and configuration"),
    ],
)
def test_old_structure_handling_is_translated(old, new):
    parameters = seamm.Parameters(
        defaults=structure_handling_parameters,
        data={"structure handling": {"value": old}},
    )
    assert parameters["structure handling"].value == new


def test_plugins_with_the_old_choices_keep_them():
    """A plug-in whose choices are still the old spellings is left alone."""
    defaults = {
        "structure handling": {
            "default": "be put in a new configuration",
            "kind": "enum",
            "default_units": "",
            "enumeration": (
                "overwrite the current configuration",
                "be put in a new configuration",
            ),
            "format_string": "s",
            "description": "Strained structure will",
            "help_text": "",
        }
    }
    parameters = seamm.Parameters(
        defaults=defaults,
        data={"structure handling": {"value": "be put in a new configuration"}},
    )
    assert parameters["structure handling"].value == "be put in a new configuration"


def test_safe_format_path():
    assert safe_format(Path("/a/b.mol")) == "/a/b.mol"
    assert safe_format("{x} and {y}", x=1) == "1 and {y}"


def test_structure_handling_description_with_path_name():
    P = {
        "structure handling": "Create a new system and configuration",
        "system name": Path("/data/water.mol"),
        "configuration name": "initial",
    }
    text = structure_handling_description(P)
    assert "'/data/water.mol'" in text
