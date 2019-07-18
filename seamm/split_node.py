# -*- coding: utf-8 -*-

"""A node to split the flow into parallel segements in a flowchart"""

import seamm
import logging

logger = logging.getLogger(__name__)


class Split(seamm.Node):

    def __init__(self, flowchart=None, extension=None):
        '''Initialize a node for splitting the flow apart

        Keyword arguments:
        '''
        logger.debug('Constructing split node {}'.format(self))
        super().__init__(flowchart=flowchart, title='Split')
