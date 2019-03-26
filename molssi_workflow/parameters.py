# -*- coding: utf-8 -*-
"""Control parameters for a step in a MolSSI flowchart"""

import collections.abc
from distutils.util import strtobool
import logging
from molssi_workflow import Q_
from molssi_workflow import ureg
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

        logger.debug('Parameter.__init__')

        self._data = {}
        self.dimensionality = None
        self._widget = None

        self.reset()
        
        # Handle positional or keyword arguments
        for data in args:
            if isinstance(data, dict):
                self.update(data)
            else:
                raise RuntimeError('Positional arguments must be dicts')

        self.update(kwargs)

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
        if self.units or self.units == '':
            return self.value
        else:
            return ('{} {}').format(self.value, self.units)

    def __str__(self):
        if not self.units or self.units == '':
            if self.kind == 'integer':
                try:
                    value = int(self.value)
                    return ('{:' + self.format_string + '}').format(value)
                except:
                    return ('{}').format(self.value)
            if self.kind == 'float':
                try:
                    value = float(self.value)
                    return ('{:' + self.format_string + '}').format(value)
                except:
                    return ('{}').format(self.value)
            return ('{:' + self.format_string + '}').format(self.value)
        else:
            if self.kind == 'integer':
                try:
                    value = int(self.value)
                    return ('{:' + self.format_string + '} {}').format(
                        value, self.units)
                except:
                    return ('{} {}').format(self.value, self.units)
            if self.kind == 'float':
                try:
                    value = float(self.value)
                    return ('{:' + self.format_string + '} {}').format(
                        value, self.units)
                except:
                    return ('{} {}').format(self.value, self.units)
            return ('{:' + self.format_string + '} {}').format(
                self.value, self.units)

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

        if 'value' not in self._data:
            self._data['value'] = self._data['default']

        result = self._data['value']
        if result is None:
            result = self._data['default']

        return result

    @value.setter
    def value(self, value):
        self._data['value'] = value

    @property
    def default(self):
        """The current default of the parameter. May be a value, a
        Python expression containing variables prefix with $,
        standard operators or parenthesise, or a pint units
        quantity."""

        return self._data['default']

    @default.setter
    def default(self, value):
        self._data['default'] = value

    @property
    def kind(self):
        """The type of the parameter: integer, float, string
        or enum.
        This can be used to convert the value to the correct
        type in e.g. get_value."""

        return self._data['kind']

    @kind.setter
    def kind(self, value):
        if value not in ('integer', 'float', 'string'):
            raise RuntimeError(
                "The 'kind' must be 'integer', 'float', or "
                "'string', not '{}'".format(value)
            )
        self._data['kind'] = value
    
    @property
    def units(self):
        """The units, as a string. These need to be compatible with
        pint"""
        if 'units' not in self._data:
            self._data['units'] = self._data['default_units']

        if self._data['units'] is None:
            return self['default_units']

        return self._data['units']

    @units.setter
    def units(self, value):

        logger.debug("units: value = '{}'".format(value))

        if value == '':
            value = None
        if value is not None:
            tmp = ureg(value)
            logger.debug("   tmp = '{}'".format(tmp))
            if self.dimensionality is None:
                self.dimensionality = tmp.dimensionality

            logger.debug("   dimensionality = '{}'".format(
                self.dimensionality)
            )

            if tmp.dimensionality != self.dimensionality:
                raise RuntimeError(
                    ("Units '{}' have a different dimensionality than "
                     "the parameters: '{}' != '{}'").format(
                         value, tmp.dimensionality, self.dimensionality)
                )
        self._data['units'] = value
    
    @property
    def default_units(self):
        """The default units, as a string. These need to be compatible with
        pint"""
        return self._data['default_units']

    @default_units.setter
    def default_units(self, value):
        if value == '':
            value = None
        if value is not None:
            tmp = ureg(value)
            if self.dimensionality is None:
                self.dimensionality = tmp.dimensionality

                if tmp.dimensionality != self.dimensionality:
                    raise RuntimeError(
                        ("The default units '{}' have a different "
                         "dimensionality than the parameters: "
                         "'{}' != '{}'").format(
                             value, tmp.dimensionality, self.dimensionality)
                    )
        self._data['default_units'] = value

    @property
    def enumeration(self):
        """The possible values for an enumerated type."""
        return self._data['enumeration']

    @property
    def format_string(self):
        """The format string for the value"""
        return self._data['format_string']

    @format_string.setter
    def format_string(self, value):
        self._data['format_string'] = value

    @property
    def description(self):
        """Short description of this parameter, preferable just a
        few words"""
        return self._data['description']

    @description.setter
    def description(self, value):
        self._data['description'] = value

    @property
    def help_text(self):
        """A longer description of this parameter that is suitable
        for e.g. help text."""
        return self._data['help_text']

    @help_text.setter
    def help_text(self, value):
        self._data['help_text'] = value

    @property
    def has_units(self):
        """Does this parameter have associated associated?"""
        if self.dimensionality:
            return False
        if self.dimensionality == '':
            return False
        return True

    @property
    def is_expr(self):
        """Is the current value a variable reference or
        expression?"""
        if isinstance(self.value, str):
            return self.value[0] == '$'
        else:
            return False

    def get(self, context=None, formatted=False, units=True):
        """Return the value evaluated in the given context"""
        if self.is_expr:
            if context is None:
                global root_context
                if root_context is None:
                    raise RuntimeError('No context available')
                result = eval(self.value[1:], root_context)
            else:
                result = eval(self.value[1:], context)
        else:
            result = self.value

        # If it is an enum, just return that.
        if result in self.enumeration:
            if self.kind == 'boolean':
                return bool(strtobool(result))
            else:
                return result
        
        # convert to proper type
        if self.kind == 'integer':
            result = int(result)
        elif self.kind == 'float':
            result = float(result)
        elif self.kind == 'boolean':
            if isinstance(result, str):
                result = bool(strtobool(result))
            elif not isinstance(result, bool):
                result = bool(result)

        # format if requested
        if formatted:
            result = self.format_string.format(result)
            if self.units:
                result += ' ' + self.units

        # and run into pint quantity if requested
        if units and self.units:
            result = Q_(result, self.units)

        return result

    def set(self, value):
        """Set the fields based on the type of value given"""
        if isinstance(value, tuple) or isinstance(value, list):
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
            'default':       None,
            'kind':          None,
            'default_units': None,
            'enumeration':   tuple(),
            'format_string': None,
            'description':   None,
            'help_text':     None,
        }
        self.dimensionality = None
        
    def widget(self, frame,  **kwargs):
        """Return a widget for handling the parameter"""
        # Will this keep the graphics isolated?
        import molssi_util.molssi_widgets as mw

        logger.debug('Creating widget for {}'.format(self))

        if self._widget is not None:
            if self._widget.winfo_exists():
                raise RuntimeError(
                    'Widget for Parameter {} already exists!'
                    .format(self)
                )

        logger.debug('   finished checking if the widget already exists.')

        labeltext = kwargs.pop('labeltext', self.description)

        if self.enumeration:
            if self.dimensionality:
                logger.debug('   making UnitComboBox')
                w = mw.UnitComboBox(
                    frame,
                    labeltext=labeltext,
                    values=self.enumeration,
                    **kwargs
                )
                w.set(self.value, self.units)
            else:
                logger.debug('    making LabeledComboBox')
                w = mw.LabeledComboBox(
                    frame,
                    labeltext=labeltext,
                    values=self.enumeration,
                    **kwargs
                )
                w.set(self.value)
        else:
            if self.dimensionality:
                logger.debug('   making UnitEntry')
                w = mw.UnitEntry(
                    frame,
                    labeltext=labeltext,
                    **kwargs
                )
                w.set(self.value, self.units)
            else:
                logger.debug('   making LabeledEntry')
                w = mw.LabeledEntry(
                    frame,
                    labeltext=labeltext,
                    **kwargs
                )
                w.set(self.value)

        self._widget = w

        logger.debug('   returning {}'.format(w))
        return w

    def set_from_widget(self):
        """Set the value from the widget"""
        self.set(self._widget.get())

    def to_dict(self):
        """Convert into a string suitable for editing"""
        return dict(self._data)

    def from_dict(self, data):
        """Convert from a dict back to an object"""
        for key in data:
            if key not in self._data and key not in ('value', 'units'):
                raise RuntimeError(
                    'from_dict: dictionary not compatible with Parameters,'
                    " which do not have an attribute '{}'".format(key)
                )
        self.reset()
        self._data.update(data)

        # Update the dimensionality if needed
        self.units = self._data['units']
        self.default_units = self._data['default_units']

    def update(self, data):
        """Update values from a dict"""
        for key in data:
            if key not in self._data and key not in ('value', 'units'):
                raise RuntimeError(
                    'update: dictionary not compatible with Parameters,'
                    " which do not have an attribute '{}'".format(key)
                )
        self._data.update(data)

        # Update the dimensionality if needed
        if 'units' in self._data:
            self.units = self._data['units']
        if 'default_units' in self._data:
            self.default_units = self._data['default_units']


class Parameters(collections.abc.MutableMapping):
    """A dict-like container for parameters"""
    def __init__(self, data=None):
        """Create an instance, optionally from a dict"""

        logger.debug('Parameters.__init__')

        if data:
            if isinstance(data, dict):
                self.from_dict(data)
            else:
                raise RuntimeError(
                    'A Parameters object can be initialized with a dict object'
                )
        else:
            self._data = {}

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
        data = {}
        for key in self:
            data[key] = self[key].to_dict()
        return data

    def from_dict(self, data):
        self._data = dict()
        self.update(data)

    def update(self, data):
        for key in data:
            self[key] = Parameter(data[key])

    def values_to_dict(self):
        """Return a dict of the raw values of the parameters
        formatted for printing"""

        data = {}
        for key in self:
            data[key] = str(self[key])

        return data

    def current_values_to_dict(self, context=None, formatted=False,
                               units=True):
        """Return the current values of the parameters, resolving
        any expressions, etc. in the given context or the root
        context is none is given."""

        data = {}
        for key in self:
            data[key] = self[key].get(context)

        return data
