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

    def __init__(self, flowchart=None):
        '''Initialize a specialized start node, which is the
        anchor for the graph.

        Keyword arguments:
        '''
        logger.debug('Constructing start node {}'.format(self))
        super().__init__(flowchart=flowchart, title='Start')

        self._uuid = 1

    def set_uuid(self):
        pass

    def describe(self, indent='', json_dict=None):
        """Write out information about what this node will do
        If json_dict is passed in, add information to that dictionary
        so that it can be written out by the controller as appropriate.
        """

        next_node = super().describe(indent, json_dict)

        return next_node

    def run(self):
        """'Run' the start node, i.e. do nothing but print
        """

        next_node = super().run(printer)
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
