# -*- coding: utf-8 -*-

"""The start node in a workflow"""

import molssi_workflow
import logging

logger = logging.getLogger(__name__)


class StartNode(molssi_workflow.Node):
    def __init__(self, workflow=None):

        '''Initialize a specialized start node, which is the
        anchor for the graph.

        Keyword arguments:
        '''
        logger.debug('Constructing start node {}'.format(self))
        super().__init__(workflow=workflow, title='Start')

        self._uuid = 1

    def set_uuid(self):
        pass

    def describe(self, indent='', json_dict=None):
        """Write out information about what this node will do
        If json_dict is passed in, add information to that dictionary
        so that it can be written out by the controller as appropriate.
        """

        next_node = super().describe(indent, json_dict)

        self.job_output('')

        return next_node
