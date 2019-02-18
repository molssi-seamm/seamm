# -*- coding: utf-8 -*-

"""A node to join together parallel flows in a workflow"""

import molssi_workflow
import logging

logger = logging.getLogger(__name__)


class Join(molssi_workflow.Node):
    def __init__(self,
                 workflow=None,
                 extension=None):
        '''Initialize a node for joining the flow together again

        Keyword arguments:
        '''
        logger.debug('Constructing join node {}'.format(self))
        super().__init__(workflow=workflow, title='Join')
