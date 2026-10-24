"""'{current name}' in the names an optimizer gives a structure, and copies that keep
their source's name, so that titles read from a file survive (SEAMM 5380,
2026-10-23: every configuration became 'optimized')."""

import pytest

import seamm
from seamm.standard_parameters import set_names, structure_handling_parameters
from molsystem import SystemDB


@pytest.fixture
def db(tmp_path):
    db = SystemDB(filename=f"file:{tmp_path / 'seamm.db'}")
    previous = seamm.flowchart_variables
    seamm.flowchart_variables = seamm.Variables()
    seamm.flowchart_variables.set_variable("_system_db", db)
    yield db
    seamm.flowchart_variables = previous
    db.close()


def values(**changes):
    P = {k: v["default"] for k, v in structure_handling_parameters.items()}
    P.update(changes)
    return P


def named(db, name="DMC_cc"):
    system = db.create_system(name="EC-DMC")
    configuration = system.create_configuration(name=name)
    configuration.atoms.append(x=[0.0], y=[0.0], z=[0.0], symbol=["He"])
    return system, configuration


def test_current_name_in_the_template(db):
    system, configuration = named(db)
    P = values(**{"configuration name": "{current name}/optimized"})
    set_names(system, configuration, P)
    assert configuration.name == "DMC_cc/optimized"
    P = values(
        **{
            "configuration name": "DZP {current name}",
            "system name": "{current name} r2SCAN",
        }
    )
    set_names(system, configuration, P)
    assert configuration.name == "DZP DMC_cc/optimized"
    assert system.name == "EC-DMC r2SCAN"
    # other fields as before; unknown ones are left as they are
    P = values(**{"configuration name": "{current name} with {model} {unknown}"})
    set_names(system, configuration, P, model="PM7")
    assert configuration.name == "DZP DMC_cc/optimized with PM7 {unknown}"


def test_a_new_configuration_keeps_the_name(db):
    system, configuration = named(db)
    node = seamm.Node(flowchart=seamm.Flowchart())
    P = values(**{"structure handling": "Create a new configuration"})
    system2, copy = node.get_system_configuration(P)
    assert system2 is system or system2.id == system.id
    assert copy.id != configuration.id
    assert copy.name == "DMC_cc"
    P["configuration name"] = "keep current name"
    set_names(system2, copy, P)
    assert copy.name == "DMC_cc"
    P["configuration name"] = "{current name}/optimized"
    set_names(system2, copy, P)
    assert copy.name == "DMC_cc/optimized"
    assert configuration.name == "DMC_cc"


def test_a_new_system_keeps_the_names(db):
    system, configuration = named(db)
    node = seamm.Node(flowchart=seamm.Flowchart())
    P = values(**{"structure handling": "Create a new system and configuration"})
    system2, copy = node.get_system_configuration(P)
    assert system2.id != system.id
    assert system2.name == "EC-DMC"
    assert copy.name == "DMC_cc"


def test_descriptions_show_the_placeholder():
    """Before the run the name is not known: '<current name>', which the printer
    (FormattedText, which formats with the parameters) can take."""
    from seamm.standard_parameters import structure_handling_description
    from seamm_util.printing import FormattedText as __

    P = values(**{"configuration name": "{current name} optimized with {model}"})
    text = structure_handling_description(P, model="PM7")
    assert "'<current name> optimized with PM7'" in text
    assert "<current name>" in str(__(text, **P, indent=""))
