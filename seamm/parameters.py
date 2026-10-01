# -*- coding: utf-8 -*-

"""Control parameters for a step in a MolSSI flowchart"""

import collections.abc
import importlib
import json
import logging
from seamm_util import Q_
from seamm_util import ureg
import pprint

logger = logging.getLogger(__name__)


def strtobool(value):
    """Convert a string representation of truth to 1 or 0.

    True values are 'y', 'yes', 't', 'true', 'on' and '1'; false values are
    'n', 'no', 'f', 'false', 'off' and '0'. Raises ValueError otherwise.
    (Replaces ``distutils.util.strtobool``; distutils was removed in Python 3.12.)
    """
    text = str(value).strip().lower()
    if text in ("y", "yes", "t", "true", "on", "1"):
        return 1
    if text in ("n", "no", "f", "false", "off", "0"):
        return 0
    raise ValueError(f"invalid truth value {value!r}")


# All for a default root context for evaluating expressions
# and variables

root_context = None


def set_context(context):
    """Set the default root context for evaluating variables
    and expressions in parameters."""

    global root_context
    root_context = context


class Parameter(collections.abc.MutableMapping):
    """A single parameter, with defaults, units, description, etc.
    This is object is a dict-like mutable mapping with properties
    to make it appear to be a simple object with attributes.
    """

    def __init__(self, *args, **kwargs):
        """Initialize this parameter"""

        logger.debug("\nParameter.__init__")

        self._data = {}
        self.dimensionality = None
        self._widget = None

        self.reset()

        # Handle positional or keyword arguments
        for data in args:
            if isinstance(data, dict):
                self.update(data)
            else:
                raise RuntimeError("Positional arguments must be dicts")

        self.update(kwargs)

        logger.debug("Finished constructing Parameter\n")

    def __getitem__(self, key):
        """Allow [] access to the dictionary!"""
        return self._data[key]

    def __setitem__(self, key, value):
        """Allow x[key] access to the data"""
        self._data[key] = value

    def __delitem__(self, key):
        """Allow deletion of keys"""
        del self._data[key]

    def __iter__(self):
        """Allow iteration over the object"""
        return iter(self._data)

    def __len__(self):
        """The len() command"""
        return len(self._data)

    def __repr__(self):
        """The official string representation of this object"""
        if self.units is None or self.units == "":
            return str(self.value)
        else:
            return ("{} {}").format(self.value, self.units)

    def __str__(self):
        if self.units is None or self.units == "":
            if self.kind == "integer":
                try:
                    value = int(self.value)
                    return ("{:" + self.format_string + "}").format(value)
                except Exception:
                    return ("{}").format(self.value)
            if self.kind == "float":
                try:
                    value = float(self.value)
                    return ("{:" + self.format_string + "}").format(value)
                except ValueError:
                    return ("{}").format(self.value)
            if self.format_string == "":
                return str(self.value)
            else:
                return ("{:" + self.format_string + "}").format(self.value)
        else:
            if self.kind == "integer":
                try:
                    value = int(self.value)
                    return ("{:" + self.format_string + "} {}").format(
                        value, self.units
                    )
                except ValueError:
                    return ("{} {}").format(self.value, self.units)
            if self.kind == "float":
                try:
                    value = float(self.value)
                    return ("{:" + self.format_string + "} {}").format(
                        value, self.units
                    )
                except Exception:
                    return ("{} {}").format(self.value, self.units)
            if self.format_string == "":
                return "{} {}".format(self.value, self.units)
            else:
                return ("{:" + self.format_string + "} {}").format(
                    self.value, self.units
                )

    def __contains__(self, item):
        """Return a boolean indicating if a key exists."""
        if item in self._data:
            return True
        return False

    def __eq__(self, other):
        """Return a boolean if this object is equal to another"""
        return self._data == other._data

    def copy(self):
        """Return a shallow copy of the dictionary"""
        return self._data.copy()

    @property
    def value(self):
        """The current value of the parameter. May be a value, a
        Python expression containing variables prefix with $,
        standard operators or parentheses."""

        if "value" not in self._data:
            self._data["value"] = self._data["default"]

        result = self._data["value"]
        if result is None:
            result = self._data["default"]

        return result

    @value.setter
    def value(self, value):
        self._data["value"] = value

    @property
    def default(self):
        """The current default of the parameter. May be a value, a
        Python expression containing variables prefix with $,
        standard operators or parenthesise, or a pint units
        quantity."""

        return self._data["default"]

    @default.setter
    def default(self, value):
        self._data["default"] = value

    @property
    def kind(self):
        """The type of the parameter: integer, float, string,
        enum or special.
        This can be used to convert the value to the correct
        type in e.g. get_value."""

        return self._data["kind"]

    @kind.setter
    def kind(self, value):
        if value not in ("integer", "float", "string"):
            raise RuntimeError(
                "The 'kind' must be 'integer', 'float', or "
                "'string', not '{}'".format(value)
            )
        self._data["kind"] = value

    @property
    def units(self):
        """The units, as a string. These need to be compatible with
        pint"""
        if "units" not in self._data:
            self._data["units"] = self._data["default_units"]

        if self._data["units"] is None:
            return self["default_units"]

        return self._data["units"]

    @units.setter
    def units(self, value):
        logger.debug("units: value = '{}'".format(value))

        if value == "":
            value = None
        if value is None:
            self.dimensionality = None
        else:
            tmp = ureg(value)
            logger.debug("   tmp = '{}'".format(tmp))
            if self.dimensionality is None:
                self.dimensionality = tmp.dimensionality

            logger.debug("   dimensionality = '{}'".format(self.dimensionality))

            if tmp.dimensionality != self.dimensionality:
                try:
                    # The current units; self._data["units"] may not be set yet.
                    Q_(1.0, self.units).to(value)
                except Exception:
                    raise RuntimeError(
                        (
                            "Units '{}' have a different dimensionality than "
                            "the parameters: '{}' != '{}'"
                        ).format(value, tmp.dimensionality, self.dimensionality)
                    )
        self._data["units"] = value

    @property
    def default_units(self):
        """The default units, as a string. These need to be compatible with
        pint"""
        return self._data["default_units"]

    @default_units.setter
    def default_units(self, value):
        if value == "":
            value = None
        if value is None:
            self.dimensionality = None
        else:
            tmp = ureg(value)
            if self.dimensionality is None:
                self.dimensionality = tmp.dimensionality

            if tmp.dimensionality != self.dimensionality:
                raise RuntimeError(
                    (
                        "The default units '{}' have a different "
                        "dimensionality than the parameters: "
                        "'{}' != '{}'"
                    ).format(value, tmp.dimensionality, self.dimensionality)
                )
        self._data["default_units"] = value

    @property
    def enumeration(self):
        """The possible values for an enumerated type."""
        return self._data["enumeration"]

    @property
    def format_string(self):
        """The format string for the value"""
        return self._data["format_string"]

    @format_string.setter
    def format_string(self, value):
        self._data["format_string"] = value

    @property
    def description(self):
        """Short description of this parameter, preferable just a
        few words"""
        return self._data["description"]

    @description.setter
    def description(self, value):
        self._data["description"] = value

    @property
    def help_text(self):
        """A longer description of this parameter that is suitable
        for e.g. help text."""
        return self._data["help_text"]

    @help_text.setter
    def help_text(self, value):
        self._data["help_text"] = value

    @property
    def has_units(self):
        """Does this parameter have units associated?"""
        if self.dimensionality is None:
            return False
        if self.dimensionality == "":
            return False
        return True

    @property
    def is_expr(self):
        """Is the current value a variable reference or
        expression?"""
        if isinstance(self.value, str) and len(self.value) > 0:
            return self.value[0] in ("$", "=") and self.value != "=="
        else:
            return False

    def get(self, context=None, formatted=False, units=True):
        """Return the value evaluated in the given context"""
        if self.is_expr:
            if context is None:
                if root_context is None:
                    raise RuntimeError("No context available")
                result = eval(self.value[1:], root_context)
            else:
                result = eval(self.value[1:], context)
        else:
            result = self.value

        # If it is an enum, just return that.
        if self.enumeration is not None and result in self.enumeration:
            if self.kind == "boolean":
                return bool(strtobool(result))
        # convert to proper type
        elif self.kind == "integer":
            result = int(result)
        elif self.kind == "float":
            result = float(result)
        elif self.kind == "boolean":
            if isinstance(result, str):
                result = bool(strtobool(result))
            elif not isinstance(result, bool):
                result = bool(result)
        elif self.kind == "list" or self.kind == "periodic table":
            if not isinstance(result, list):
                if (
                    isinstance(result, str)
                    and len(result) > 0
                    and result[0] not in ("$", "=")
                ):
                    result = json.loads(result)
            return result
        elif self.kind == "dictionary":
            if not isinstance(result, dict):
                result = json.loads(result)
            return result

        # format if requested
        if formatted:
            fstring = self.format_string
            if fstring is not None and fstring != "":
                try:
                    result = f"{result:{fstring}}"
                except Exception:
                    pass
            if self.units is not None and self.units != "":
                result += " " + self.units
            return result

        # and run into pint quantity if requested
        if units and self.units is not None and self.units != "":
            # Might be a string...
            if isinstance(result, str):
                pass
            else:
                result = Q_(result, self.units)

        return result

    def set(self, value):
        """Set the fields based on the type of value given"""
        if self.kind == "special" or self.kind == "periodic table":
            self.value = value
        elif self.kind == "list":
            self.value = value
        elif isinstance(value, tuple) or isinstance(value, list):
            if len(value) == 1:
                self.value = value[0]
            elif len(value) == 2:
                self.value = value[0]
                self.units = value[1]
            else:
                raise RuntimeError(
                    "Parameter.set expected a sequence of length "
                    "1 or 2, not '{}'".format(len(value))
                )
        else:
            self.value = value

    def reset(self):
        """Reset to an empty state"""
        self._data = {
            "default": None,
            "kind": None,
            "widget": None,
            "default_units": None,
            "enumeration": None,
            "format_string": None,
            "group": "",
            "description": None,
            "help_text": None,
            "applies_when": None,
        }
        self.dimensionality = None

    def widget(self, frame, **kwargs):
        """Return a widget for handling the parameter"""
        # Will this keep the graphics isolated?
        import seamm_widgets as sw

        logger.debug("Creating widget for {}".format(type(self)))

        if self._widget is not None:
            logger.debug("   Destroying existing widget.")
            try:
                self._widget.destroy()
            except Exception:
                pass

        labeltext = kwargs.pop("labeltext", self.description)

        if self.kind == "special":
            module_name, class_name = self["widget"].split(".")
            mdl = importlib.import_module(module_name)
            cls = getattr(mdl, class_name)
            w = cls(frame, labeltext=labeltext, **kwargs)
            w.set(self.value)
        elif self.kind == "periodic table":
            w = sw.PeriodicTable(frame, **kwargs)
            w.set(self.value)
        elif self.enumeration is not None:
            if "width" not in kwargs:
                if len(self.enumeration) > 0:
                    width = max(len(x) for x in self.enumeration)
                    if width < 10:
                        width = 10
                else:
                    width = 10
                kwargs["width"] = width

            if self.dimensionality is None:
                logger.debug("    making LabeledCombobox")
                w = sw.LabeledCombobox(
                    frame,
                    labeltext=labeltext,
                    values=self.enumeration,
                    **kwargs,
                )
                w.set(self.value)
            else:
                logger.debug("   making UnitCombobox")
                w = sw.UnitCombobox(
                    frame,
                    labeltext=labeltext,
                    values=self.enumeration,
                    **kwargs,
                )
                w.set(self.value, self.units)
        else:
            if self.dimensionality is None:
                logger.debug("   making LabeledEntry")
                w = sw.LabeledEntry(frame, labeltext=labeltext, **kwargs)
                w.set(self.value)
            else:
                logger.debug("   making UnitEntry")
                w = sw.UnitEntry(frame, labeltext=labeltext, **kwargs)
                w.set(self.value, self.units)

        self._widget = w

        logger.debug("   returning {}".format(w))
        return w

    def set_from_widget(self):
        """Set the value from the widget, ignoring if there is no widget."""
        if self._widget is not None:
            self.set(self._widget.get())

    def reset_widget(self):
        """Reset the values in the widget, if it has been created."""
        if self._widget is not None:
            if self.dimensionality is None:
                self._widget.set(self.value)
            else:
                self._widget.set(self.value, self.units)

    def to_dict(self):
        """Convert into a string suitable for editing"""
        result = dict()
        # if self['kind'] == 'list':
        #     result['value'] = json.dumps(self.value)
        # elif self['kind'] == 'dict':
        #     result['value'] = json.dumps(self.value)
        # else:
        #     result['value'] = self.value
        result["value"] = self.value
        result["units"] = self.units
        return result

    def update(self, data):
        """Update values from a dict

        This assumes that the static data such as 'kind' and
        'default' has been created already.
        """

        logger.debug("Parameter.update....")
        for key, value in data.items():
            logger.debug("{:>10s} {}".format(key, value))
            if key in ("value", "default"):
                # if self['kind'] in ('list', 'dictionary'):
                #     self._data[key] = json.loads(value)
                # else:
                self._data[key] = value
            elif key == "units":
                self._data[key] = value
            elif key not in self:
                raise RuntimeError(
                    "update: dictionary not compatible with Parameters,"
                    " which do not have an attribute '{}'".format(key)
                )
            else:
                self._data[key] = value

        # Update the dimensionality if needed
        if "units" in self._data:
            self.units = self._data["units"]
        if "default_units" in self._data:
            self.default_units = self._data["default_units"]

    def debug_print(self):
        logger.debug("\nParameter instance:\n{}".format(pprint.pformat(self._data)))


class Parameters(collections.abc.MutableMapping):
    """A dict-like container for parameters"""

    def __init__(self, defaults={}, data=None):
        """Create an instance, optionally from a dict"""

        logger.debug("\nParameters.__init__")
        logger.debug(pprint.pformat(defaults))

        self.defaults = defaults
        logger.debug("\ndefaults:\n{}".format(pprint.pformat(defaults)))

        self._data = {}

        self.initialize()

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("\nafter defaults:")
            for key, value in self.items():
                logger.debug("  {}: {}".format(key, pprint.pformat(value._data)))

        if data:
            if isinstance(data, dict):
                self.update(data)

                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("\nafter data:")
                    for key, value in self.items():
                        logger.debug(
                            "  {}: {}".format(key, pprint.pformat(value._data))
                        )
            else:
                raise RuntimeError(
                    "A Parameters object can be initialized with a dict object"
                )

    def __getitem__(self, key):
        """Allow [] access to the dictionary!"""
        return self._data[key]

    def __setitem__(self, key, value):
        """Allow x[key] access to the data"""
        self._data[key] = value

    def __delitem__(self, key):
        """Allow deletion of keys"""
        del self._data[key]

    def __iter__(self):
        """Allow iteration over the object"""
        return iter(self._data)

    def __len__(self):
        """The len() command"""
        return len(self._data)

    def __repr__(self):
        """The string representation of this object"""
        return repr(self._data)

    def __str__(self):
        """The pretty string representation of this object"""
        return pprint.pformat(self.to_dict())

    def __contains__(self, item):
        """Return a boolean indicating if a key exists."""
        if item in self._data:
            return True
        return False

    def __eq__(self, other):
        """Return a boolean if this object is equal to another"""
        return self._data == other._data

    def copy(self):
        """Return a shallow copy of the dictionary"""
        return self._data.copy()

    def to_dict(self):
        """Return a new dictionary with the pertinent data

        The Parameter class only saves the value and units,
        as everything else comes form the constructor below
        """
        data = {}
        for key in self:
            try:
                data[key] = self[key].to_dict()
            except:  # noqa: E722
                logger.critical(
                    ("An error occurred in Parameters.to_dict " "with key '{}'").format(
                        key
                    )
                )
                logger.critical(("The type of the key is '{}'").format(type(self[key])))
                raise
        return data

    def from_dict(self, data):
        """Recreate the object from a dictionary"""
        self._data = dict()
        # Put back in all the constant data
        self.initialize()
        # and update with the new data
        self.update(data)

    def initialize(self):
        for key, value in self.defaults.items():
            self[key] = Parameter(value)

    def update(self, data):
        for key in data:
            self[key].update(data[key])

    def values_to_dict(self):
        """Return a dict of the raw values of the parameters
        formatted for printing"""

        data = {}
        for key in self:
            try:
                data[key] = str(self[key])
            except Exception as e:
                logger.warning("Cannot format '{}': {}".format(key, str(e)))
                data[key] = "#err#"

        return data

    def current_values_to_dict(self, context=None, formatted=False, units=True):
        """Return the current values of the parameters, resolving
        any expressions, etc. in the given context or the root
        context is none is given."""

        data = {}
        for key in self:
            data[key] = self[key].get(context=context, formatted=formatted, units=units)

        return data

    def set_from_widgets(self):
        """Convenience function to set the parameters from their widgets."""
        for key in self:
            self[key].set_from_widget()

    def reset_widgets(self):
        """Convenience function to reset the widgets to the current value."""
        for key in self:
            try:
                self[key].reset_widget()
            except ValueError as e:
                logger.warning("Error resetting widget for {}: {}".format(key, str(e)))
                raise
            except Exception:
                raise

    # -------------------------------------------------------------------------
    # Rules shared by the dialog and by building flowcharts without it
    #
    # Which parameters apply, which choices are valid and which values follow
    # from others depend on the other parameters. A step's dialog uses these to
    # hide, narrow and set its controls; the flowchart builder uses them to refuse
    # settings that would have no effect or are not valid. A plug-in declares
    # simple conditions with "applies_when" in a parameter's definition and
    # overrides these methods for anything more.
    #
    # Each method takes the values to judge -- {name: value}, e.g. the dialog's
    # current widget values -- or, by default, the parameters' own values. A value
    # that is a variable or expression ("$x", "=...") is not known until the
    # flowchart runs, so a condition on it counts as met.
    # -------------------------------------------------------------------------

    def current_values(self):
        """The parameters' values, {name: value}."""
        return {key: parameter.value for key, parameter in self.items()}

    @staticmethod
    def _is_expr(value):
        return (
            isinstance(value, str)
            and len(value) > 0
            and value[0] in ("$", "=")
            and value != "=="
        )

    def applies(self, key, values=None, _seen=None):
        """Whether a parameter applies, i.e. has any effect, given the others.

        The default follows the parameter's "applies_when" definition: a mapping
        from other parameters to the value, list of values, or {"not": value(s)}
        they must have. The parameters it names must themselves apply.

        Parameters
        ----------
        key : str
            The parameter.
        values : dict, optional
            The values to judge; by default the parameters' own.

        Returns
        -------
        bool
        """
        if values is None:
            values = self.current_values()
        if key not in self:
            return False
        conditions = self[key]._data.get("applies_when")
        if not conditions:
            return True
        seen = set() if _seen is None else _seen
        if key in seen:
            return True  # a circular definition; do not loop
        seen = seen | {key}
        for other, wanted in conditions.items():
            if other not in self:
                continue
            if not self.applies(other, values, seen):
                return False
            value = values.get(other, self[other].value)
            if self._is_expr(value):
                continue
            negate = isinstance(wanted, dict) and "not" in wanted
            if negate:
                wanted = wanted["not"]
            if not isinstance(wanted, (list, tuple, set)):
                wanted = [wanted]
            if (value in wanted) == negate:
                return False
        return True

    def applicable(self, values=None):
        """Which parameters apply, {name: bool}."""
        if values is None:
            values = self.current_values()
        return {key: self.applies(key, values) for key in self}

    def choices(self, key, values=None):
        """The valid choices for a parameter given the others, or None if the
        parameter's own list (or any value) is valid. Override to narrow."""
        return None

    def implied(self, values=None):
        """Values that other parameters imply, {name: value}. Override when a
        choice requires a value elsewhere (e.g. a basis set for a method)."""
        return {}

    def problems(self, values=None):
        """Combinations of values that cannot work, as messages.

        The default checks that each parameter that applies and has narrowed
        choices has one of them. Override to add checks.
        """
        if values is None:
            values = self.current_values()
        result = []
        for key in self:
            if not self.applies(key, values):
                continue
            allowed = self.choices(key, values)
            if allowed is None:
                continue
            value = values.get(key)
            # A value may be a mapping with a name, e.g. a basis set
            name = value.get("name") if isinstance(value, dict) else value
            if self._is_expr(name):
                continue
            if name not in allowed:
                shown = ", ".join(repr(c) for c in list(allowed)[:20])
                if len(allowed) > 20:
                    shown += f", ... ({len(allowed)} in all)"
                result.append(
                    f"{value!r} is not valid for '{key}' with these settings; "
                    f"choose one of: {shown}"
                )
        return result

    def not_applicable_reason(self, key, values=None):
        """Why a parameter does not apply, as text ('' if it does, or no reason is
        known). The default names the declared condition that is not met;
        override to explain other rules."""
        if values is None:
            values = self.current_values()
        if Parameters.applies(self, key, values):
            return ""
        # A parameter it depends on may not apply itself: explain that first.
        for other in self[key]._data.get("applies_when") or {}:
            if other in self and not self.applies(other, values):
                why = self.not_applicable_reason(other, values)
                return f"it needs '{other}', which does not apply" + (
                    f" ({why})" if why else ""
                )
        condition = self.describe_condition(key)
        return f"it applies when {condition}" if condition else ""

    def describe_condition(self, key):
        """The declared condition for a parameter to apply, as text, or ''."""
        conditions = self[key]._data.get("applies_when") if key in self else None
        if not conditions:
            return ""
        parts = []
        for other, wanted in conditions.items():
            negate = isinstance(wanted, dict) and "not" in wanted
            if negate:
                wanted = wanted["not"]
            if not isinstance(wanted, (list, tuple, set)):
                wanted = [wanted]
            wanted = [repr(w) for w in wanted]
            if not negate:
                text = "is " + " or ".join(wanted)
            elif len(wanted) == 1:
                text = f"is not {wanted[0]}"
            else:
                text = "is neither " + ", ".join(wanted[:-1]) + f" nor {wanted[-1]}"
            parts.append(f"'{other}' {text}")
        return " and ".join(parts)
