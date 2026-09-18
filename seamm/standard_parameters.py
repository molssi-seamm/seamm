# -*- coding: utf-8 -*-
"""Standard sets of parameters widely used in SEAMM.

Parameters
----------
structure_selection_parameters : dict(str, dict(str, str))
    Parameters for selecting which existing structures a step operates on: which
    systems (current, all, or by name) and which configurations of each (current,
    all, last, first, or by name). See :func:`select_configurations`.

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

import fnmatch
import re

structure_selection_parameters = {
    "source systems": {
        "default": "current",
        "kind": "string",
        "default_units": "",
        "enumeration": ("current", "all", "name is", "name matches", "name regexp"),
        "format_string": "s",
        "description": "Systems:",
        "help_text": (
            "Which systems to take the structures from: the current system, all "
            "systems, or those whose name is / matches (shell wildcards) / matches "
            "the regular expression given. A variable ($name) holding a list of "
            "configurations or of systems may also be given."
        ),
    },
    "source system name": {
        "default": "",
        "kind": "string",
        "default_units": "",
        "enumeration": tuple(),
        "format_string": "s",
        "description": "",
        "help_text": "The system name, wildcard pattern or regular expression.",
    },
    "source configurations": {
        "default": "current",
        "kind": "string",
        "default_units": "",
        "enumeration": (
            "current",
            "all",
            "last",
            "first",
            "name is",
            "name matches",
            "name regexp",
        ),
        "format_string": "s",
        "description": "Configurations:",
        "help_text": (
            "Which configurations of each selected system to use: its current "
            "configuration, all of them, the last or first, or those whose name is "
            "/ matches (shell wildcards) / matches the regular expression given."
        ),
    },
    "source configuration name": {
        "default": "",
        "kind": "string",
        "default_units": "",
        "enumeration": tuple(),
        "format_string": "s",
        "description": "",
        "help_text": "The configuration name, wildcard pattern or regular expression.",
    },
}

structure_handling_parameters = {
    "structure handling": {
        "default": "Overwrite the current configuration",
        "kind": "enum",
        "default_units": "",
        "enumeration": (
            "Overwrite the current configuration",
            "Create a new configuration",
            "Create a new system and configuration",
            "Discard the structure",
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
            "Discard the structure",
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
            "use isomeric SMILES string",
            "use IUPAC name",
            "use InChI",
            "use InChIKey",
            "use chemical formula",
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
            "use isomeric SMILES string",
            "use IUPAC name",
            "use InChI",
            "use InChIKey",
            "sequential",
            "use chemical formula",
        ),
        "format_string": "s",
        "description": "Configuration name:",
        "help_text": "The name for the new configuration",
    },
}


def structure_handling_description(__P, **kwargs):
    """Return a standard description for how the structure will be handled.

    Parameters
    ----------
    __P : dict(str, any)
        The dictionary of parameter values, which must contain the standard structure
        handling parameters.

    Returns
    -------
    str
        The text for printing.
    """

    text = ""

    handling = __P["structure handling"]
    if handling == "Overwrite the current configuration":
        text += "The structure will overwrite the current configuration."
    elif handling == "Create a new configuration":
        text += "The structure will be put in a new configuration."
    elif handling == "Create a new system and configuration":
        text += "The structure will be put in a new system."
    elif handling == "Discard the structure":
        text += "The structure will be discarded."
    elif handling.startswith("$") or handling.startswith("="):
        text += f"The handling of the structure will be determined by '{handling}'."
    else:
        raise ValueError(f"Do not understand how to handle the structure: '{handling}'")

    if handling != "Discard the structure":
        sysname = __P["system name"]
        if sysname == "keep current name":
            text += " The name of the system will not be changed."
        elif sysname == "use SMILES string":
            text += " The name of the system will be its SMILES."
        elif sysname == "use Canonical SMILES string":
            text += " The name of the system will be its canonical SMILES."
        elif sysname == "use isomeric SMILES string":
            text += " The name of the system will be its isomeric SMILES."
        elif sysname == "use IUPAC name":
            text += " The name of the system will be its IUPAC name."
        elif sysname == "use InChI":
            text += " The name of the system will be its InChI."
        elif sysname == "use InChIKey":
            text += " The name of the system will be its InChIKey."
        elif sysname == "use chemical formula":
            text += " The name of the system will be its chemical formula."
        else:
            tmp = safe_format(sysname, **kwargs)
            text += f" The name of the system will be '{tmp}'."

        confname = __P["configuration name"]
        if confname == "keep current name":
            text += " The name of the configuration will not be changed."
        elif confname == "use SMILES string":
            text += " The name of the configuration will be its SMILES."
        elif confname == "use Canonical SMILES string":
            text += " The name of the configuration will be its canonical SMILES."
        elif confname == "use isomeric SMILES string":
            text += " The name of the configuration will be its isomeric SMILES."
        elif confname == "use IUPAC name":
            text += " The name of the configuration will be its IUPAC name."
        elif confname == "use InChI":
            text += " The name of the configuration will be its InChI."
        elif confname == "use InChIKey":
            text += " The name of the configuration will be its InChIKey."
        elif confname == "use chemical formula":
            text += " The name of the configuration will be its chemical formula."
        else:
            tmp = safe_format(confname, **kwargs)
            text += f" The name of the configuration will be '{tmp}'."

    return text


def multiple_structure_handling_description(__P, **kwargs):
    """Return a standard description for how the new structures will be handled.

    Parameters
    ----------
    __P : dict(str, any)
        The dictionary of parameter values, which must contain the standard structure
        handling parameters.

    Returns
    -------
    str
        The text for printing.
    """

    text = "The first structure will "

    handling = __P["structure handling"]
    if handling == "Overwrite the current configuration":
        text += "overwrite the current configuration."
    elif handling == "Create a new configuration":
        text += "be added as a new configuration of the current system."
    elif handling == "Create a new system and configuration":
        text += "be added as a new system and configuration."
    elif handling.startswith("$") or handling.startswith("="):
        text += f"be handled as determined by '{handling}'."
    else:
        raise ValueError(f"Do not understand how to handle the structure: '{handling}'")

    handling = __P["subsequent structure handling"]
    text += " Any subsequent structures will be "
    if handling == "Create a new configuration":
        text += "created as a new configuration of the current system."
    elif handling == "Create a new system and configuration":
        text += "created in a new system and configuration."
    elif handling.startswith("$") or handling.startswith("="):
        text += f"handled as determined by '{handling}'."
    else:
        raise ValueError(f"Do not understand how to handle the structure: '{handling}'")

    sysname = __P["system name"]
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

    confname = __P["configuration name"]
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


def set_names(__system, __configuration, __P, _first=True, **kwargs):
    """Set the names of the system and configuration.

    Parameters
    ----------
    __system : _System
        The system being named

    __configuration : _Configuration
        The configuration being named

    __P : dict(str, any)
        The dictionary of parameter values, which must contain the standard structure
        handling parameters.

    _first : bool
        Whether this is the first or a subsequent structure.

    kwargs : {str: str}
        keyword arguments providing values that may be substituted in the names.

    Returns
    -------
    str
        The text for printing.
    """
    if __P["structure handling"] == "Discard the structure":
        return "The structure was discarded."

    sysname = __P["system name"]
    if sysname == "keep current name":
        pass
    elif sysname == "use SMILES string":
        __system.name = __configuration.smiles
    elif sysname == "use Canonical SMILES string":
        __system.name = __configuration.canonical_smiles
    elif sysname == "use isomeric SMILES string":
        __system.name = __configuration.isomeric_smiles
    elif sysname == "use IUPAC name":
        __system.name = __configuration.PC_iupac_name(
            fallback=__configuration.formula[0]
        )
    elif sysname == "use InChI":
        __system.name = __configuration.inchi
    elif sysname == "use InChIKey":
        __system.name = __configuration.inchikey
    elif sysname == "use chemical formula":
        __system.name = __configuration.formula[0]
    else:
        __system.name = safe_format(sysname, **kwargs)

    confname = __P["configuration name"]
    if confname == "keep current name":
        pass
    elif confname == "use SMILES string":
        __configuration.name = __configuration.smiles
    elif confname == "use Canonical SMILES string":
        __configuration.name = __configuration.canonical_smiles
    elif confname == "use isomeric SMILES string":
        __configuration.name = __configuration.isomeric_smiles
    elif confname == "use IUPAC name":
        __configuration.name = __configuration.PC_iupac_name(
            fallback=__configuration.formula[0]
        )
    elif confname == "use InChI":
        __configuration.name = __configuration.inchi
    elif confname == "use InChIKey":
        __configuration.name = __configuration.inchikey
    elif confname == "use chemical formula":
        __configuration.name = __configuration.formula[0]
    else:
        __configuration.name = safe_format(confname, **kwargs)

    if _first:
        text = "The structure "

        handling = __P["structure handling"]
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
        handling = __P["subsequent structure handling"]
        text = "This subsequent structure was "
        if handling == "Create a new configuration":
            text += "created as a new configuration of the current system"
        elif handling == "Create a new system and configuration":
            text += "created in a new system and configuration"
        else:
            raise ValueError(
                f"Do not understand how to handle the structure: '{handling}'"
            )

    text += f" named '{__system.name}' / '{__configuration.name}'."
    return text


def safe_format(__s, *args, **kwargs):
    while True:
        try:
            return __s.format(*args, **kwargs)
        except KeyError as e:
            e = e.args[0]
            kwargs[e] = "{%s}" % e


def _name_filter(items, how, name, what):
    """Filter systems or configurations by name: 'is', 'matches' or 'regexp'."""
    if how == "name is":
        return [x for x in items if x.name == name]
    if how == "name matches":
        return [x for x in items if fnmatch.fnmatch(x.name, name)]
    if how == "name regexp":
        try:
            pattern = re.compile(name)
        except re.error as e:
            raise ValueError(f"Invalid regular expression for the {what} name: {e}")
        return [x for x in items if pattern.search(x.name) is not None]
    raise ValueError(f"Do not understand how to select {what}s: '{how}'")


def select_configurations(system_db, P, errors=True):
    """Select configurations according to the structure-selection parameters.

    Parameters
    ----------
    system_db : molsystem.SystemDB
        The system database.
    P : dict
        The (dereferenced) parameter values, containing the keys of
        :data:`structure_selection_parameters`. ``P["source systems"]`` may also be
        a list -- from a ``$variable`` -- of configurations (used as is) or of
        systems (then filtered by the configuration choice).
    errors : bool = True
        Whether an empty selection raises an error.

    Returns
    -------
    [molsystem._Configuration]
        The selected configurations, in system order then configuration order.
    """
    systems_spec = P.get("source systems", "current")
    conf_how = P.get("source configurations", "current")
    conf_name = str(P.get("source configuration name", ""))

    # A variable holding a list: of configurations, or of systems.
    if not isinstance(systems_spec, str):
        items = list(systems_spec)
        if len(items) == 0:
            if errors:
                raise ValueError("The variable given for the systems is empty.")
            return []
        if hasattr(items[0], "system_db") and hasattr(items[0], "atoms"):
            return items  # configurations
        systems = items
    else:
        how = systems_spec.strip()
        if how == "current":
            systems = [] if system_db.system is None else [system_db.system]
        elif how == "all":
            systems = system_db.systems
        elif how.startswith("name "):
            systems = _name_filter(
                system_db.systems, how, str(P.get("source system name", "")), "system"
            )
        else:
            raise ValueError(f"Do not understand how to select systems: '{how}'")

    configurations = []
    for system in systems:
        if system.n_configurations == 0:
            continue
        if conf_how == "current":
            c = system.configuration
            if c is not None:
                configurations.append(c)
        elif conf_how == "all":
            configurations.extend(system.configurations)
        elif conf_how == "last":
            configurations.append(system.configurations[-1])
        elif conf_how == "first":
            configurations.append(system.configurations[0])
        elif conf_how.startswith("name "):
            configurations.extend(
                _name_filter(
                    system.configurations, conf_how, conf_name, "configuration"
                )
            )
        else:
            raise ValueError(
                f"Do not understand how to select configurations: '{conf_how}'"
            )

    if errors and len(configurations) == 0:
        raise ValueError(
            "No structures matched the selection: systems '"
            f"{systems_spec if isinstance(systems_spec, str) else 'from variable'}'"
            + (
                f" (name {P.get('source system name', '')!r})"
                if isinstance(systems_spec, str) and systems_spec.startswith("name ")
                else ""
            )
            + f", configurations '{conf_how}'"
            + (f" (name {conf_name!r})" if conf_how.startswith("name ") else "")
        )
    return configurations


def structure_selection_description(P):
    """A sentence describing which structures will be used, for description_text."""
    systems_spec = P.get("source systems", "current")
    conf_how = P.get("source configurations", "current")
    conf_name = P.get("source configuration name", "")

    if not isinstance(systems_spec, str):
        return "The structures in the given variable will be used."
    how = systems_spec.strip()
    if how.startswith("$"):
        return f"The structures in the variable {how} will be used."

    if conf_how == "current":
        confs = "the current configuration"
    elif conf_how == "all":
        confs = "all configurations"
    elif conf_how in ("last", "first"):
        confs = f"the {conf_how} configuration"
    elif conf_how == "name is":
        confs = f"the configuration named '{conf_name}'"
    elif conf_how == "name matches":
        confs = f"the configurations matching '{conf_name}'"
    else:
        confs = f"the configurations matching the regular expression '{conf_name}'"

    sys_name = P.get("source system name", "")
    if how == "current":
        if conf_how == "current":
            return "The current configuration of the current system will be used."
        return f"{confs[0].upper()}{confs[1:]} of the current system will be used."
    if how == "all":
        return f"{confs[0].upper()}{confs[1:]} of every system will be used."
    if how == "name is":
        return f"{confs[0].upper()}{confs[1:]} of the system '{sys_name}' will be used."
    if how == "name matches":
        return (
            f"{confs[0].upper()}{confs[1:]} of the systems matching '{sys_name}' "
            "will be used."
        )
    return (
        f"{confs[0].upper()}{confs[1:]} of the systems matching the regular "
        f"expression '{sys_name}' will be used."
    )
