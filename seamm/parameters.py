# -*- coding: utf-8 -*-

"""Control parameters for a step in a MolSSI flowchart"""

import collections.abc
from distutils.util import strtobool
import importlib
import json
import logging
from seamm_util import Q_
from seamm_util import ureg
import pprint

logger = logging.getLogger(__name__)

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
            return self.value
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
            return self.value and self.value[0] == "$"
        else:
            return False

    def get(self, context=None, formatted=False, units=True):
        """Return the value evaluated in the given context"""
        if self.is_expr:
            if context is None:
                global root_context
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
            else:
                return result

        # convert to proper type
        if self.kind == "integer":
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
                if isinstance(result, str) and len(result) > 0 and result[0] != "$":
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
                result = f"{result:{fstring}}"
            if self.units is not None and self.units != "":
                result += " " + self.units

        # and run into pint quantity if requested
        if units and self.units is not None and self.units != "":
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
            if len(self.enumeration) > 0:
                width = max(len(x) for x in self.enumeration)
                if width < 10:
                    width = 10
            else:
                width = 10
            if self.dimensionality is None:
                logger.debug("    making LabeledCombobox")
                w = sw.LabeledCombobox(
                    frame,
                    labeltext=labeltext,
                    values=self.enumeration,
                    width=width,
                    **kwargs,
                )
                w.set(self.value)
            else:
                logger.debug("   making UnitCombobox")
                w = sw.UnitCombobox(
                    frame,
                    labeltext=labeltext,
                    values=self.enumeration,
                    width=width,
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
