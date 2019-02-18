# -*- coding: utf-8 -*-

import collections.abc
import logging
import molssi_workflow  # nopep8
import pprint

"""A dictionary-like object for holding variables accessible to the
executing workflow.
"""

logger = logging.getLogger(__name__)
# Module level variable to be used in other modules
workflow_variables = None


class Variables(collections.abc.MutableMapping):
    def __init__(self, **kwargs):
        self._data = dict(**kwargs)

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
        return pprint.pformat(self._data)

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

    def value(self, string):
        """Return the value of the variable if it is a variable
        i.e. starts with a $ and optionally has braces around the
        variable name.

        If it is not a variable, return the original string unchanged
        """

        if string[0] == '$':
            if string[1] == '{':
                if string[-1] != '}':
                    raise RuntimeError("'" + string +
                                       "'is not a valid variable name")
                else:
                    name = string[2:-2]
            else:
                name = string[1:]
            if name in self._data:
                return self._data[name]
            else:
                raise RuntimeError("Variable '" + string + "' does not exist")
        else:
            return string
