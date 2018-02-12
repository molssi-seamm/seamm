# -*- coding: utf-8 -*-
"""The start node in a workflow"""

import molssi_workflow


class TkStartNode(molssi_workflow.TkNode):
    """The Tk-based graphical representation of a Start node"""

    anchor_points = {
        's': (0, 1),
        'e': (0.5, 0.5),
        'w': (-0.5, 0.5),
    }

    def __init__(self, tk_workflow=None, node=None,
                 canvas=None, x=120, y=20, w=200, h=70):
        '''Initialize a node

        Keyword arguments:
        '''
        super().__init__(tk_workflow=tk_workflow, node=node,
                         canvas=canvas, x=x, y=y, w=w, h=h)

    def right_click(self, event):
        """At the moment, since we shouldn't delete the start node
        there is nothing to do here.
        """

        pass

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
            fill='white',
        )

        # the label in the middle
        x0 = self.x
        y0 = self.y + self.h / 2
        self.title_label = self.canvas.create_text(
            x0, y0, text=self.title, tags=[self.tag, 'type=title'])
