# -*- coding: utf-8 -*-

"""Problems found when checking a flowchart, and the fixes for them.

A problem is the text describing it -- a ``str``, so code that only reports
problems needs nothing more -- with its severity and, where the check knows it,
how to fix it: changes to the parameters of steps. Errors stop a job from being
submitted or run; warnings are reported but do not.

A fix is data, not code: the editor offers a button for it, ``seamm-flowchart
validate --fix`` applies it, and the MCP tools return it as the step's address,
the parameter and its value, which ``set_parameters`` applies.
"""

#: The severities of a problem
ERROR = "error"
WARNING = "warning"


class Edit(object):
    """Setting one parameter of one step."""

    def __init__(self, node, parameter, value, units=None):
        self.node = node
        self.parameter = parameter
        self.value = value
        self.units = units

    def apply(self):
        """Set the parameter of the step."""
        parameter = self.node.parameters[self.parameter]
        parameter.value = self.value
        if self.units is not None:
            parameter.units = self.units

    def __repr__(self):
        units = "" if self.units is None else f" {self.units}"
        return f"Edit({self.node.title!r}: {self.parameter} = {self.value}{units})"


class Fix(object):
    """One way of fixing a problem: a label for it and the edits it makes."""

    def __init__(self, label, edits):
        self.label = label
        self.edits = list(edits)

    def apply(self):
        """Make the edits."""
        for edit in self.edits:
            edit.apply()

    def __repr__(self):
        return f"Fix({self.label!r}, {self.edits!r})"


class Problem(str):
    """A problem with a flowchart: its description, severity and fixes."""

    def __new__(cls, text, severity=ERROR, fixes=()):
        problem = super().__new__(cls, text)
        problem.severity = severity
        problem.fixes = list(fixes)
        return problem

    def prefixed(self, prefix):
        """The same problem, its description after ``prefix``."""
        return Problem(prefix + str(self), severity=self.severity, fixes=self.fixes)


def severity(problem):
    """The severity of a problem; a plain string is an error."""
    return getattr(problem, "severity", ERROR)


def is_error(problem):
    return severity(problem) == ERROR


def fixes(problem):
    """The fixes of a problem; a plain string has none."""
    return list(getattr(problem, "fixes", []))
