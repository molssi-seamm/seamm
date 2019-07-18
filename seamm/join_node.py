# -*- coding: utf-8 -*-

"""A node to join together parallel flows in a flowchart"""

import seamm
import logging

logger = logging.getLogger(__name__)


class Join(seamm.Node):

    def __init__(self, flowchart=None, extension='Join'):
        '''Initialize a node for joining the flow together again

        Keyword arguments:
        '''
        logger.debug('Constructing join node {}'.format(self))
        super().__init__(
            flowchart=flowchart, title='Join', extension=extension
        )
