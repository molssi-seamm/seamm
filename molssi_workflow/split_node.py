# -*- coding: utf-8 -*-

"""A node to split the flow into parallel segements in a workflow"""

import molssi_workflow
import logging

logger = logging.getLogger(__name__)


class Split(molssi_workflow.Node):
    def __init__(self,
                 workflow=None,
                 extension=None):
        '''Initialize a node for splitting the flow apart

        Keyword arguments:
        '''
        logger.debug('Constructing split node {}'.format(self))
        super().__init__(workflow=workflow, title='Split')
