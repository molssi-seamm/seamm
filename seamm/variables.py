# -*- coding: utf-8 -*-

"""
A dictionary-like object for holding variables accessible to the
executing flowchart.
"""

import collections.abc
import logging
import seamm
import pprint

logger = logging.getLogger(__name__)
# Module level variable to be used in other modules
flowchart_variables = None


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
        """Return the value of the variable or expression if it is an
        expression, i.e. starts with a $ and optionally has braces around the
        variable name.

        If it is not a variable, return the original string unchanged
        """

        if isinstance(string, str) and string[0] == "$":
            expression = self.filter_expression(string)

            result = eval(expression, seamm.flowchart_variables._data)
            return result
        else:
            return string

    def set_variable(self, variable, value):
        """Set the value of the variable. The variable may be a simple string
        or start with a $ and optionally have braces around it, i.e.

            <name>
            $<name>

        or

            ${<name>}

        """

        name = self.variable(variable)
        self._data[name] = value

    def get_variable(self, variable):
        """Get the value of the variable. The variable may be a simple string
        or start with a $ and optionally have braces around it, i.e.

            <name>
            $<name>

        or

            ${<name>}

        """

        name = self.variable(variable)
        if name not in self._data:
            raise RuntimeError("Workspace variable '{}' does not exist.".format(name))
        return self._data[name]

    def exists(self, variable):
        """Return whether a variable exists. The variable may be specified
        as a simple string or start with a $ and optionally have braces
        around it, i.e.

            <name>
            $<name>

        or

            ${<name>}

        """

        return self.variable(variable) in self._data

    def delete(self, variable):
        """Return whether a variable exists. The variable may be specified
        as a simple string or start with a $ and optionally have braces
        around it, i.e.

            <name>
            $<name>

        or

            ${<name>}

        """

        name = self.variable(variable)
        if name in self._data:
            del self._data[name]

    def variable(self, string):
        """Return the name of a variable. The variable may be specified
        as a simple string or start with a $ and optionally have braces
        around it, i.e.

            <string>
            $<string>

        or

            ${<string>}

        """

        if string[0] == "$":
            if string[1] == "{":
                if string[-1] != "}":
                    raise RuntimeError("'" + string + "'is not a valid string name")
                else:
                    return string[2:-1]
            else:
                return string[1:]
        else:
            return string

    def filter_expression(self, string):
        """A variable or expression coming from the GUI uses '$'
        to indicate a variable, optionally bracketing the variable
        with braces, i.e. ${name}.

        This method filters out the variable markers, respecting
        quoted string, returning a string that can be eval'ed in
        the Python interpreter.
        """

        result = ""
        state = ""
        for char in string:
            if state == "in single quotes":
                result += char
                if char == "'":
                    state = ""
            elif state == "in double quotes":
                result += char
                if char == '"':
                    state = ""
            elif state == "protected":
                result += char
                state = ""
            elif state == "in variable name":
                if char == "}":
                    state = ""
                elif char == "{":
                    pass
                else:
                    result += char
            else:
                if char == "$":
                    state = "in variable name"
                elif char == "'":
                    result += char
                    state = "in single quotes"
                elif char == '"':
                    result += char
                    state = "in double quotes"
                elif char == "\\":
                    state = "protected"
                else:
                    result += char

        return result
