# -*- coding: utf-8 -*-

"""The start node in a flowchart"""

import seamm


class TkStartNode(seamm.TkNode):
    """The Tk-based graphical representation of a Start node"""

    anchor_points = {
        's': (0, 0.5),
        'e': (0.5, 0.0),
        'w': (-0.5, 0.0),
    }

    def __init__(
        self,
        tk_flowchart=None,
        node=None,
        canvas=None,
        x=150,
        y=50,
        w=200,
        h=50
    ):
        '''Initialize a node

        Keyword arguments:
        '''
        super().__init__(
            tk_flowchart=tk_flowchart,
            node=node,
            canvas=canvas,
            x=x,
            y=y,
            w=w,
            h=h
        )

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
        y0 = self.y - self.h / 2
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
        self.title_label = self.canvas.create_text(
            self.x, self.y, text=self.title, tags=[self.tag, 'type=title']
        )
