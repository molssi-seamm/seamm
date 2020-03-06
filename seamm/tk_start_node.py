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

    def __init__(self, canvas=None, x=150, y=50, w=200, h=50):
        """Initialize the start node.

        Keyword arguments:
        """
        super().__init__(canvas=canvas, x=x, y=y, w=w, h=h, title='Start')

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

    def add_to_popup(self, popup_menu):
        """At the moment, since we shouldn't delete the start node
        there is nothing to do here.
        """

        popup_menu.destroy()
        return None

    def draw(self):
        """Draw the node on the given canvas, making it visible"""

        # Remove the items form the canvas if they exist.
        self.undraw()

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
