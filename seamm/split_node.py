# -*- coding: utf-8 -*-

"""A node to split the flow into parallel segements in a flowchart"""

import seamm
import seamm_util.printing as printing
from seamm_util.printing import FormattedText as __
import logging

logger = logging.getLogger(__name__)
job = printing.getPrinter()
printer = printing.getPrinter("split")


class Split(seamm.Node):
    def __init__(self, flowchart=None, extension=None):
        """Initialize a node for splitting the flow apart

        Keyword arguments:
        """
        logger.debug("Constructing split node {}".format(self))
        super().__init__(flowchart=flowchart, title="Split", extension=extension)

    @property
    def version(self):
        """The semantic version of this module."""
        return seamm.__version__

    @property
    def git_revision(self):
        """The git version of this module."""
        return seamm.__git_revision__

    def description_text(self, P=None):
        """Return a short description of this step.

        Return a nicely formatted string describing what this step will
            do.

        Keyword arguments:
            P: a dictionary of parameter values, which may be variables
                or final values. If None, then the parameters values will
                be used as is.
        """

        # if not P:
        #     P = self.parameters.values_to_dict()

        text = ""
        text += "Split into several threads of execution"

        return self.header + "\n" + __(text, indent=4 * " ").__str__()
