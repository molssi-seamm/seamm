# -*- coding: utf-8 -*-

"""The Tk graphical representation of an edge in the graph, i.e. an
arrow connecting nodes.

The information is stored in the graph object as attributes of the
edge so that the graphical representation can be restored as needed.
"""

import logging
import math
import seamm
from tkinter import font
import tkinter as tk
import weakref

logger = logging.getLogger(__name__)


class TkEdge(seamm.Edge):
    str_to_object = weakref.WeakValueDictionary()

    def __init__(
        self,
        graph,
        node1,
        node2,
        edge_type="execution",
        edge_subtype="next",
        canvas=None,
        anchor1="s",
        anchor2="n",
        coords=None,
        **kwargs
    ):
        """Initialize the edge, ensuring that it is
        in the graph.

        Keyword arguments:
        """
        self._data = []
        logger.debug("Creating TkEdge {}".format(self))
        logger.debug("\tnode1 = {}".format(node1))
        logger.debug("\tnode2 = {}".format(node2))

        # Initialize the parent class
        super().__init__(graph, node1, node2, edge_type, edge_subtype, **kwargs)

        self._data["canvas"] = canvas
        self.anchor1 = anchor1
        self.anchor2 = anchor2
        if coords is None:
            x0, y0 = self.node1.anchor_point(self.anchor1)
            x1, y1 = self.node2.anchor_point(self.anchor2)
            self.coords = [x0, y0, x1, y1]
        else:
            self.coords = coords

        # Remember the object so can get from tags on the canvas
        TkEdge.str_to_object[str(id(self))] = self

        # Arrange that the graphics are deleted when we are
        self._finalizer = weakref.finalize(self, self.canvas.delete, self.tag())
        self._finalizer.atexit = False

    def __eq__(self, other):
        """Return a boolean if this object is equal to another"""
        return super().__eq__(other)

    @property
    def canvas(self):
        return self._data["canvas"]

    @property
    def anchor1(self):
        return self._data["anchor1"]

    @anchor1.setter
    def anchor1(self, value):
        self._data["anchor1"] = value

    @property
    def anchor2(self):
        return self._data["anchor2"]

    @anchor2.setter
    def anchor2(self, value):
        self._data["anchor2"] = value

    @property
    def coords(self):
        return self._data["coords"]

    @coords.setter
    def coords(self, value):
        self._data["coords"] = value

    @property
    def has_label(self):
        return "label_id" in self._data

    @property
    def label_id(self):
        return self._data["label_id"]

    @property
    def label_bg_id(self):
        return self._data["label_bg_id"]

    def tag(self):
        """Return a string tag for self"""
        return "edge=" + str(id(self))

    def draw(self):
        """Draw the arrow for this edge"""
        self.move()

    def move(self):
        """Redraw the arrow when the nodes have moved"""

        x0, y0 = self.node1.anchor_point(self.anchor1)
        x1, y1 = self.node2.anchor_point(self.anchor2)
        self.coords[0] = x0
        self.coords[1] = y0
        self.coords[-2] = x1
        self.coords[-1] = y1

        # the arrow
        self.canvas.delete(self.tag() + "&& type=arrow")
        arrow_id = self.canvas.create_line(
            self.coords, arrow=tk.LAST, tags=[self.tag(), "type=arrow"]
        )
        self._data["arrow_id"] = arrow_id

        # and the label
        if self.edge_subtype != "next":
            self.canvas.delete(self.tag() + "&& type=label")
            text = self.canvas.create_text(
                self.label_position(x0, y0, x1, y1),
                text=self.edge_subtype,
                font=font.Font(family="Helvetica", size=8),
                tags=[self.tag(), "type=label"],
            )
            self._data["label_id"] = text
            self.canvas.delete(self.tag() + "&& type=label_bg")
            bg = self.canvas.create_rectangle(
                self.canvas.bbox(text),
                outline="white",
                fill="white",
                tags=[self.tag(), "type=label_bg"],
            )
            self._data["label_bg_id"] = bg
            self.canvas.tag_lower(bg, text)

    def label_position(self, x0, y0, x1, y1, offset=15):
        """Work out the position for the label on an edge"""
        dx = x1 - x0
        dy = y1 - y0
        length = math.sqrt(dx * dx + dy * dy)
        if length < 2 * offset:
            offset = int(length / 2)
        xy = [
            x0 if dx == 0.0 else x0 + dx / length * offset,
            y0 if dy == 0.0 else y0 + dy / length * offset,
        ]
        return xy

    def undraw(self):
        """Remove any graphics"""
        self.canvas.delete(self.tag())
        if "arrow_id" in self._data:
            del self._data["arrow_id"]
        if "label_id" in self._data:
            del self._data["label_id"]
        if "label_bg_id" in self._data:
            del self._data["label_bg_id"]
