# -*- coding: utf-8 -*-
"""Standard sets of parameters widely used in SEAMM.

Attributes
----------
structure_handling_parameters : dict(str, dict(str, str))
    Parameters for providing options for how to handle newly created structures.
    The options are:

        * Overwrite the current configuration in the current system.
        * Add a new configuration to the current system.
        * Create new system and a configuration in it to hold the structure.

    In addition, options are provided for naming the system and configuration whether
    or not new ones are created, i.e. the system and configuration can be renamed if
    they are reused.
"""


structure_handling_parameters = {
    "structure handling": {
        "default": "Overwrite the current configuration",
        "kind": "enum",
        "default_units": "",
        "enumeration": (
            "Overwrite the current configuration",
            "Create a new configuration",
            "Create a new system and configuration",
        ),
        "format_string": "s",
        "description": "First structure:",
        "help_text": (
            "Whether to overwrite the current configuration, or create a new "
            "configuration or system and configuration for the new structure"
        ),
    },
    "subsequent structure handling": {
        "default": "Create a new system and configuration",
        "kind": "enum",
        "default_units": "",
        "enumeration": (
            "Create a new configuration",
            "Create a new system and configuration",
        ),
        "format_string": "s",
        "description": "Subsequent structures:",
        "help_text": (
            "Whether to create a new configuration or system and configuration for "
            "new structures after the first structure, if any."
        ),
    },
    "system name": {
        "default": "from file",
        "kind": "string",
        "default_units": "",
        "enumeration": (
            "from file",
            "keep current name",
            "use SMILES string",
            "use Canonical SMILES string",
        ),
        "format_string": "s",
        "description": "System name:",
        "help_text": "The name for the new system",
    },
    "configuration name": {
        "default": "use Canonical SMILES string",
        "kind": "string",
        "default_units": "",
        "enumeration": (
            "keep current name",
            "use SMILES string",
            "use Canonical SMILES string",
        ),
        "format_string": "s",
        "description": "Configuration name:",
        "help_text": "The name for the new configuration",
    },
}


def structure_handling_description(P):
    """Return a standard description for how the structure will be handled.

    Parameters
    ----------
    P : dict(str, any)
        The dictionary of parameter values, which must contain the standard structure
        handling parameters.

    Returns
    -------
    str
        The text for printing.
    """

    text = ""

    handling = P["structure handling"]
    if handling == "Overwrite the current configuration":
        text += "The structure will overwrite the current configuration."
    elif handling == "Create a new configuration":
        text += "The structure will be put in a new configuration."
    elif handling == "Create a new system and configuration":
        text += "The structure will be put in a new system."
    else:
        raise ValueError(f"Do not understand how to handle the structure: '{handling}'")

    sysname = P["system name"]
    if sysname == "use SMILES string":
        text += " The name of the system will be the SMILES string given."
    elif sysname == "use Canonical SMILES string":
        text += " The name of the system will be the canonical SMILES of the structure."
    else:
        text += f" The name of the system will be {sysname}."

    confname = P["configuration name"]
    if confname == "use SMILES string":
        text += " The name of the configuration will be the SMILES string given."
    elif confname == "use Canonical SMILES string":
        text += (
            " The name of the configuration will be the canonical SMILES of the "
            "structure."
        )
    else:
        text += f" The name of the configuration will be {confname}."

    return text


def multiple_structure_handling_description(P):
    """Return a standard description for how the new structures will be handled.

    Parameters
    ----------
    P : dict(str, any)
        The dictionary of parameter values, which must contain the standard structure
        handling parameters.

    Returns
    -------
    str
        The text for printing.
    """

    text = "The first structure will "

    handling = P["structure handling"]
    if handling == "Overwrite the current configuration":
        text += "overwrite the current configuration."
    elif handling == "Create a new configuration":
        text += "created as a new configuration of the current system."
    elif handling == "Create a new system and configuration":
        text += "created in a new system and configuration."
    else:
        raise ValueError(f"Do not understand how to handle the structure: '{handling}'")

    handling = P["subsequent structure handling"]
    text += " Any subsequent structures will be "
    if handling == "Create a new configuration":
        text += "created as a new configuration of the current system."
    elif handling == "Create a new system and configuration":
        text += "created in a new system and configuration."
    else:
        raise ValueError(f"Do not understand how to handle the structure: '{handling}'")

    sysname = P["system name"]
    if sysname == "use SMILES string":
        text += " The name of the system will be the SMILES string given."
    elif sysname == "use Canonical SMILES string":
        text += " The name of the system will be the canonical SMILES of the structure."
    else:
        text += f" The name of the system will be {sysname}."

    confname = P["configuration name"]
    if confname == "use SMILES string":
        text += " The name of the configuration will be the SMILES string given."
    elif confname == "use Canonical SMILES string":
        text += (
            " The name of the configuration will be the canonical SMILES of the "
            "structure."
        )
    else:
        text += f" The name of the configuration will be {confname}."

    return text
