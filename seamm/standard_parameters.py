# -*- coding: utf-8 -*-
"""Standard sets of parameters widely used in SEAMM.

Parameters
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
        "default": "keep current name",
        "kind": "string",
        "default_units": "",
        "enumeration": (
            "keep current name",
            "use SMILES string",
            "use Canonical SMILES string",
            "use IUPAC name",
            "use InChI",
            "use InChIKey",
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
            "use IUPAC name",
            "use InChI",
            "use InChIKey",
        ),
        "format_string": "s",
        "description": "Configuration name:",
        "help_text": "The name for the new configuration",
    },
}


def structure_handling_description(P, **kwargs):
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
    if sysname == "keep current name":
        text += " The name of the system will not be changed."
    elif sysname == "use SMILES string":
        text += " The name of the system will be its SMILES."
    elif sysname == "use Canonical SMILES string":
        text += " The name of the system will be its canonical SMILES."
    elif sysname == "use IUPAC name":
        text += " The name of the system will be its IUPAC name."
    elif sysname == "use InChI":
        text += " The name of the system will be its InChI."
    elif sysname == "use InChIKey":
        text += " The name of the system will be its InChIKey."
    else:
        tmp = safe_format(sysname, **kwargs)
        text += f" The name of the system will be '{tmp}'."

    confname = P["configuration name"]
    if confname == "keep current name":
        text += " The name of the configuration will not be changed."
    elif confname == "use SMILES string":
        text += " The name of the configuration will be its SMILES."
    elif confname == "use Canonical SMILES string":
        text += " The name of the configuration will be its canonical SMILES."
    elif confname == "use IUPAC name":
        text += " The name of the configuration will be its IUPAC name."
    elif confname == "use InChI":
        text += " The name of the configuration will be its InChI."
    elif confname == "use InChIKey":
        text += " The name of the configuration will be its InChIKey."
    else:
        tmp = safe_format(confname, **kwargs)
        text += f" The name of the configuration will be '{tmp}'."

    return text


def multiple_structure_handling_description(P, **kwargs):
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
        text += "be added as a new configuration of the current system."
    elif handling == "Create a new system and configuration":
        text += "be added as a new system and configuration."
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
    if sysname == "keep current name":
        text += " The name of the system will not be changed."
    elif sysname == "use SMILES string":
        text += " The name of the system will be its SMILES."
    elif sysname == "use Canonical SMILES string":
        text += " The name of the system will be its canonical SMILES."
    elif sysname == "use IUPAC name":
        text += " The name of the system will be its IUPAC name."
    elif sysname == "use InChI":
        text += " The name of the system will be its InChI."
    elif sysname == "use InChIKey":
        text += " The name of the system will be its InChIKey."
    else:
        tmp = safe_format(sysname, **kwargs)
        text += f" The name of the system will be '{tmp}'."

    confname = P["configuration name"]
    if confname == "keep current name":
        text += " The name of the configuration will not be changed."
    elif confname == "use SMILES string":
        text += " The name of the configuration will be its SMILES."
    elif confname == "use Canonical SMILES string":
        text += " The name of the configuration will be its canonical SMILES."
    elif confname == "use IUPAC name":
        text += " The name of the configuration will be its IUPAC name."
    elif confname == "use InChI":
        text += " The name of the configuration will be its InChI."
    elif confname == "use InChIKey":
        text += " The name of the configuration will be its InChIKey."
    else:
        tmp = safe_format(confname, **kwargs)
        text += f" The name of the configuration will be '{tmp}'."

    return text


def set_names(system, configuration, P, _first=True, **kwargs):
    """Set the names of the system and configuration.

    Parameters
    ----------
    system : _System
        The system being named

    configuration : _Configuration
        The configuration being named

    P : dict(str, any)
        The dictionary of parameter values, which must contain the standard structure
        handling parameters.

    _first : bool
        Whether this is the first or a subseqnet structure.

    kwargs : {str: str}
        keyword arguments providing values that may be substituted in the names.

    Returns
    -------
    str
        The text for printing.
    """
    sysname = P["system name"]
    if sysname == "keep current name":
        pass
    elif sysname == "use SMILES string":
        system.name = configuration.smiles
    elif sysname == "use Canonical SMILES string":
        system.name = configuration.canonical_smiles
    elif sysname == "use IUPAC name":
        system.name = configuration.PC_iupac_name(fallback=configuration.formula[0])
    elif sysname == "use InChI":
        system.name = configuration.inchi
    elif sysname == "use InChIKey":
        system.name = configuration.inchikey
    else:
        system.name = safe_format(sysname, **kwargs)

    confname = P["configuration name"]
    if confname == "keep current name":
        pass
    elif confname == "use SMILES string":
        configuration.name = configuration.smiles
    elif confname == "use Canonical SMILES string":
        configuration.name = configuration.canonical_smiles
    elif confname == "use IUPAC name":
        configuration.name = configuration.PC_iupac_name(
            fallback=configuration.formula[0]
        )
    elif confname == "use InChI":
        configuration.name = configuration.inchi
    elif confname == "use InChIKey":
        configuration.name = configuration.inchikey
    else:
        configuration.name = safe_format(confname, **kwargs)

    if _first:
        text = "The first structure "

        handling = P["structure handling"]
        if handling == "Overwrite the current configuration":
            text += "overwrote the current configuration, and was"
        elif handling == "Create a new configuration":
            text += "was added as a new configuration of the current system"
        elif handling == "Create a new system and configuration":
            text += "was added as a new system and configuration "
        else:
            raise ValueError(
                f"Do not understand how to handle the structure: '{handling}'"
            )
    else:
        handling = P["subsequent structure handling"]
        text = "This subsequent structure was "
        if handling == "Create a new configuration":
            text += "created as a new configuration of the current system"
        elif handling == "Create a new system and configuration":
            text += "created in a new system and configuration"
        else:
            raise ValueError(
                f"Do not understand how to handle the structure: '{handling}'"
            )

    text += f" named '{system.name}' / '{configuration.name}'."
    return text


def safe_format(s, *args, **kwargs):
    while True:
        try:
            return s.format(*args, **kwargs)
        except KeyError as e:
            e = e.args[0]
            kwargs[e] = "{%s}" % e
