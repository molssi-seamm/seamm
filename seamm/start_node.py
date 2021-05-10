# -*- coding: utf-8 -*-

"""The start node in a flowchart"""

import logging
import seamm
import seamm_util.printing as printing
from seamm_util.printing import FormattedText as __  # noqa: F401

logger = logging.getLogger(__name__)
job = printing.getPrinter()
printer = printing.getPrinter("start")


class StartNode(seamm.Node):
    def __init__(self, flowchart=None):
        """Initialize a specialized start node, which is the
        anchor for the graph.

        Keyword arguments:
        """
        logger.debug("Constructing start node {}".format(self))
        super().__init__(flowchart=flowchart, title="Start", uid=1)

    @property
    def version(self):
        """The semantic version of this module."""
        return seamm.__version__

    @property
    def git_revision(self):
        """The git version of this module."""
        return seamm.__git_revision__

    def set_uuid(self):
        pass

    def description_text(self, P=None):
        """Return a short description of this step.

        Return a nicely formatted string describing what this step will
        do.

        Keyword arguments:
            P: a dictionary of parameter values, which may be variables
                or final values. If None, then the parameters values will
                be used as is.
        """
        return self.header + "\n"

    def describe(self):
        """Write out information about what this node will do"""

        self.visited = True

        # The description
        job.job(self.indent + self.description_text())

        next_node = self.next()

        if next_node is None or next_node.visited:
            return None
        else:
            return next_node

    def run(self):
        """'Run' the start node, i.e. do nothing but print"""

        next_node = super().run(printer)
        printer.important(self.header + "\n")
        return next_node

    def setup_printing(self, aprinter):
        """Establish the handlers for printing as controlled by
        options. The start step never writes to disk, so don't
        create that handler.
        """

        # First remove an existing handlers
        self.close_printing(printer)

        # A handler for stdout
        console_handler = logging.StreamHandler()
        console_handler.setLevel(printing.JOB)
        console_handler.setFormatter(self.formatter)
        printer.addHandler(console_handler)
