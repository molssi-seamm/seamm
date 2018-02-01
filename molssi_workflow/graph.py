# -*- coding: utf-8 -*-

import logging
import networkx

"""A wrapper around the networkx MultiDiGraph to insulate the workflow object
from the implementation of the graph.
"""

logger = logging.getLogger(__name__)


class Graph(object):
    """The class variable 'graphics' gives
    the default graphics to use for display, if needed. It defaults to
    'Tk' for the tkinter GUI.
    """

    def __init__(self):
        """Create the graph object that we are wrapping"""

        self.graph = networkx.MultiDiGraph()

    def add_node(self, node):
        self.graph.add_node(node)

    def remove_node(self, node):
        self.graph.remove_node(node)

    def clear(self):
        self.graph.clear()

    def __iter__(self):
        return self.graph.__iter__()

    def __contains__(self, node):
        return self.graph.__contains__(node)

    def out_edges(self, node):
        return self.graph.out_edges(nbunch=node, keys=True)

    def edges(self, node):
        return self.graph.edges(nbunch=node, data=True, keys=True)

    def has_edge(self, u, v, key=None):
        return self.graph.has_edge(u, v, key)

    def add_edge(self, u, v, key=None, **attr):
        return self.graph.edd_edge(u, y, key, **attr)
