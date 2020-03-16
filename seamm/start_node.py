# -*- coding: utf-8 -*-

"""The start node in a flowchart"""

import logging
import seamm
import seamm_util.printing as printing
from seamm_util.printing import FormattedText as __  # noqa: F401

logger = logging.getLogger(__name__)
job = printing.getPrinter()
printer = printing.getPrinter('start')


class StartNode(seamm.Node):

    def __init__(self, title='Start'):
        """The special node that anchors the flowchart.

        There can be only one start node in a flowchart. Therefore the user
        cannot delete or create start nodes. The flowchart code ensures that
        there is always one start node.

        Keyword arguments:

        """
        logger.debug('Constructing start node {}'.format(self))
        super().__init__(title=title)

        # The start node has the special uuid of 1
        self._uuid = 1

    @property
    def version(self):
        """The semantic version of this module.
        """
        return seamm.__version__

    @property
    def git_revision(self):
        """The git version of this module.
        """
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
        return self.header + '\n'

    def run(self):
        """'Run' the start node, i.e. do nothing but print
        """

        super().run(printer)
        printer.important(self.header)
        return self.next()

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
