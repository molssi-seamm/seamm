# -*- coding: utf-8 -*-
"""The Tk graphical representation of an edge in the graph, i.e. an
arrow connecting nodes.

The information is stored in the graph object as attributes of the
edge so that the graphical representation can be restored as needed.
"""

import collections.abc
import pprint
import tkinter as tk
import weakref


class TkEdge(collections.abc.MutableMapping):
    str_to_object = weakref.WeakValueDictionary()

    def __init__(self, canvas, edge_object):
        """Initialize the edge, ensuring that it is
        in the graph.

        Keyword arguments:
        """

        # Remember the object so can get from tags on the canvas
        TkEdge.str_to_object[str(id(self))] = self

        self.canvas = canvas
        self.edge = edge_object

        x0, y0 = self.edge.node1.anchor_point(self.edge['start_point'])
        x1, y1 = self.edge.node2.anchor_point(self.edge['end_point'])
        self.edge['coords'] = [x0, y0, x1, y1]

        # Arrange that the graphics are deleted when we are
        self._finalizer = weakref.finalize(self, self.canvas.delete,
                                           self.tag())
        self._finalizer.atexit = False

        # and draw the arrow!
        self.draw()

    def __getitem__(self, key):
        """Allow [] access to the dictionary!"""
        return self.edge[key]

    def __setitem__(self, key, value):
        """Allow x[key] access to the data"""
        self.edge[key] = value

    def __delitem__(self, key):
        """Allow deletion of keys"""
        del self.edge[key]

    def __iter__(self):
        """Allow iteration over the object"""
        return iter(self.edge)

    def __len__(self):
        """The len() command"""
        return len(self.edge)

    def __repr__(self):
        """The string representation of this object"""
        return repr(self.edge)

    def __str__(self):
        """The pretty string representation of this object"""
        return pprint.pformat(self.edge)

    def __contains__(self, item):
        """Return a boolean indicating if a key exists."""
        if item in self.edge:
            return True
        return False

    def __eq__(self, other):
        """Return a boolean if this object is equal to another"""
        return self.edge == other.data

    def copy(self):
        """Return a shallow copy of the dictionary"""
        return self.edge.copy()

    def tag(self):
        """Return a string tag for self"""
        return 'edge=' + str(id(self))

    def draw(self):
        """Draw the arrow for this edge"""

        # self.canvas.delete(self.tag() + '&& type=arrow')
        # self.canvas.create_line(
        #     self['coords'], arrow=tk.LAST, tags=[self.tag(), 'type=arrow'])

        self.move()

    def move(self):
        """Redraw the arrow when the nodes have moved"""

        x0, y0 = self.edge.node1.anchor_point(self['start_point'])
        x1, y1 = self.edge.node2.anchor_point(self['end_point'])
        coords = self.edge['coords']
        coords[0] = x0
        coords[1] = y0
        coords[-1] = y1
        coords[-2] = x1
        self['coords'] = coords

        self.canvas.delete(self.tag() + '&& type=arrow')
        self.canvas.create_line(
            self['coords'], arrow=tk.LAST, tags=[self.tag(), 'type=arrow'])

    def undraw(self):
        """Remove any graphics"""
        self.canvas.delete(self.tag())
