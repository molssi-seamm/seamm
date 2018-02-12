# -*- coding: utf-8 -*-
"""The Tk graphical representation of an edge in the graph, i.e. an
arrow connecting nodes.

The information is stored in the graph object as attributes of the
edge so that the graphical representation can be restored as needed.
"""

import molssi_workflow
import pprint  # nopep8
import tkinter as tk
import weakref


class TkEdge(molssi_workflow.Edge):
    str_to_object = weakref.WeakValueDictionary()

    def __init__(self, graph, node1, node2, edge_type='execution',
                 canvas=None, anchor1='s', anchor2='n', coords=None):
        """Initialize the edge, ensuring that it is
        in the graph.

        Keyword arguments:
        """
        # Initialize the parent class
        super().__init__(graph, node1, node2, edge_type)

        self._data['canvas'] = canvas
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
        self._finalizer = weakref.finalize(self, self.canvas.delete,
                                           self.tag())
        self._finalizer.atexit = False

    @property
    def canvas(self):
        return self._data['canvas']

    @property
    def anchor1(self):
        return self._data['anchor1']

    @anchor1.setter
    def anchor1(self, value):
        self._data['anchor1'] = value

    @property
    def anchor2(self):
        return self._data['anchor2']

    @anchor2.setter
    def anchor2(self, value):
        self._data['anchor2'] = value

    @property
    def coords(self):
        return self._data['coords']

    @coords.setter
    def coords(self, value):
        self._data['coords'] = value

    def tag(self):
        """Return a string tag for self"""
        return 'edge=' + str(id(self))

    def draw(self):
        """Draw the arrow for this edge"""
        self.move()

    def move(self):
        """Redraw the arrow when the nodes have moved"""

        x0, y0 = self.node1.anchor_point(self.anchor1)
        x1, y1 = self.node2.anchor_point(self.anchor2)
        self.coords[0] = x0
        self.coords[1] = y0
        self.coords[-1] = y1
        self.coords[-2] = x1

        self.canvas.delete(self.tag() + '&& type=arrow')
        self.canvas.create_line(
            self.coords, arrow=tk.LAST, tags=[self.tag(), 'type=arrow'])

    def undraw(self):
        """Remove any graphics"""
        self.canvas.delete(self.tag())
