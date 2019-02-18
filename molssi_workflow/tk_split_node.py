# -*- coding: utf-8 -*-
"""A node to split the flow in a workflow"""

import logging
import molssi_workflow

logger = logging.getLogger(__name__)


class TkSplit(molssi_workflow.TkNode):
    """The Tk-based graphical representation of a splitting node"""

    anchor_points = {
        'n': (0, 0),
        's': (0, 1),
        'e': (0.5, 0.5),
        'w': (-0.5, 0.5),
    }

    def __init__(self, tk_workflow=None, node=None,
                 canvas=None, x=120, y=20, w=10, h=10):
        '''Initialize a node

        Keyword arguments:
        '''
        logger.debug('Creating TkSplit, {} {} {} {} {}'
                     .format(node, x, y, w, h))
        super().__init__(tk_workflow=tk_workflow, node=node,
                         canvas=canvas, x=x, y=y, w=w, h=h)

    def draw(self):
        """Draw the node on the given canvas, making it visible"""

        # the outline
        x0 = self.x - self.w / 2
        x1 = x0 + self.w
        y0 = self.y
        y1 = y0 + self.h
        self._border = self.canvas.create_oval(
            x0,
            y0,
            x1,
            y1,
            tags=[self.tag, 'type=outline'],
            fill='black',
        )
