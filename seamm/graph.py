# -*- coding: utf-8 -*-

import collections.abc
import logging
import seamm
import pprint

"""A simple graph structure for holding the flowchart. This handles a
directed graph -- all edges have a direction implied -- with zero or
more edges from or to each node.
"""

logger = logging.getLogger(__name__)


class Graph(object):
    """A datastructure for holding a directed graph with multiple (parallel) edges."""

    def __init__(self):
        """Create the graph object"""

        self._node = {}
        self._edge = {}

    def __iter__(self):
        return self._node.values().__iter__()

    def __contains__(self, node):
        return node.uuid in self._node

    def add_node(self, node):
        if node in self:
            raise RuntimeError("node is already in the graph")
        self._node[node.uuid] = node
        return node

    def remove_node(self, node):
        if node not in self:
            raise RuntimeError("node is not in the graph")
        del self._node[node.uuid]

    def clear(self):
        self._node = {}
        self._edge = {}

    def add_edge(
        self, u, v, edge_type=None, edge_subtype=None, edge_class=None, **kwargs
    ):

        if u not in self:
            self.add_node(u)

        if v not in self:
            self.add_node(v)

        key = (u.uuid, v.uuid, edge_type, edge_subtype)
        if edge_class is None:
            self._edge[key] = seamm.Edge(
                self, u, v, edge_type=edge_type, edge_subtype=edge_subtype, **kwargs
            )
        else:
            self._edge[key] = edge_class(
                self, u, v, edge_type=edge_type, edge_subtype=edge_subtype, **kwargs
            )
        return self._edge[key]

    def remove_edge(self, u, v, edge_type=None, edge_subtype=None):
        key = (u.uuid, v.uuid, edge_type, edge_subtype)
        if key not in self._edge:
            raise RuntimeError("edge does not exist!")
        del self._edge[key]

    def edges(self, node=None, direction="both"):
        result = []
        if node is None:
            return self._edge.values()
        else:
            h = node.uuid
            if direction == "both":
                for key in self._edge:
                    h1, h2, edge_type, edge_subtype = key
                    if h1 == h:
                        result.append(("out", self._edge[key]))
                    if h2 == h:
                        result.append(("in", self._edge[key]))
            elif direction == "out":
                for key in self._edge:
                    h1, h2, edge_type, edge_subtype = key
                    if h1 == h:
                        result.append(self._edge[key])
            elif direction == "in":
                for key in self._edge:
                    h1, h2, edge_type, edge_subtype = key
                    if h2 == h:
                        result.append(self._edge[key])
            else:
                return RuntimeError("Don't recognize direction '{}'!".format(direction))

        return result

    def has_edge(self, u, v, edge_type=None, edge_subtype=None):
        key = (u.uuid, v.uuid, edge_type, edge_subtype)
        return key in self._edge


class Edge(collections.abc.MutableMapping):
    def __init__(
        self, graph, node1, node2, edge_type="execution", edge_subtype="next", **kwargs
    ):
        self.graph = graph
        self._data = dict(**kwargs)
        self._data["node1"] = node1
        self._data["node2"] = node2
        self._data["edge_type"] = edge_type
        self._data["edge_subtype"] = edge_subtype

    def __getitem__(self, key):
        """Allow [] access to the dictionary!"""
        return self._data[key]

    def __setitem__(self, key, value):
        """Allow x[key] access to the data"""
        self._data[key] = value

    def __delitem__(self, key):
        """Allow deletion of keys"""
        del self._data[key]

    def __iter__(self):
        """Allow iteration over the object"""
        return iter(self._data)

    def __len__(self):
        """The len() command"""
        return len(self._data)

    def __repr__(self):
        """The string representation of this object"""
        return repr(self._data)

    def __str__(self):
        """The pretty string representation of this object"""
        return pprint.pformat(self._data)

    def __contains__(self, item):
        """Return a boolean indicating if a key exists."""
        if item in self._data:
            return True
        return False

    def __eq__(self, other):
        """Return a boolean if this object is equal to another"""
        return self._data == other._data

    def copy(self):
        """Return a shallow copy of the dictionary"""
        return self._data.copy()

    @property
    def node1(self):
        return self._data["node1"]

    @property
    def node2(self):
        return self._data["node2"]

    @property
    def edge_type(self):
        return self._data["edge_type"]

    @property
    def edge_subtype(self):
        return self._data["edge_subtype"]


if __name__ == "__main__":

    class Node(object):
        def __init__(self, **kwargs):
            self.data = dict(**kwargs)

        def __str__(self):
            return pprint.pformat(self.data)

    graph = Graph()

    start = Node(title="start")
    node1 = Node(title="node1")
    node2 = Node(title="node2")

    edge1 = graph.add_edge(start, node1)
    print("edge1 = {}".format(edge1))
    edge2 = graph.add_edge(node1, node2)
    print("edge2 = {}".format(edge2))

    print("nodes:")
    for node in graph:
        print(" node = {}".format(node))
        print()

    print("edges:")
    for edge in graph.edges():
        print(edge)
        print()
