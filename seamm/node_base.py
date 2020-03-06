# -*- coding: utf-8 -*-

"""A (virtual) base class for nodes in flowcharts.

This class forms the base for both graphical and non-graphical nodes
in flowcharts. In order to separate the graphics from the underlying
non-graphical nodes both types of node contain common information
and can be serialized to and deserialized from the same file.

This base class contains the common data and functionality so that
it is not duplicated.
"""

from abc import ABC, abstractmethod
import collections.abc
import logging
import seamm_util.printing as printing
import uuid

logger = logging.getLogger(__name__)
job = printing.getPrinter()


class NodeBase(ABC, collections.abc.Hashable):

    def __init__(
        self,
        title='',
        extension=None,
        module=None,
        parameters=None,
        graphics=None
    ):
        """Initialize a node

        Keyword arguments:
        """

        self._uuid = None
        self.extension = extension

        self.parameters = None  # Object containing control parameters
        if graphics is None:  # Dictionary of data for graphics
            self.graphics = {
                'x': None,
                'y': None,
                'w': None,
                'h': None,
                'graphics': 'Tk'
            }
        else:
            self.graphics = graphics

        self.module = module
        self.parent = None
        self._title = title
        self._description = ''
        self._id = None
        self._visited = False

        self.edge = {'in': None, 'out': None}

    def __hash__(self):
        """Make iterable!"""
        return self.uuid

    def __eq__(self, other):
        return (
            self.__class__ == other.__class__ and
            self.__hash__() == other.__hash__()
        )

    @property
    @abstractmethod
    def version(self):
        """The semantic version of this module.
        """
        pass

    @property
    @abstractmethod
    def git_revision(self):
        """The git version of this module.
        """
        pass

    @property
    def id(self):
        """The heirarchical id for this node, as a tuple"""
        return self._id

    @id.setter
    def id(self, value):
        """Set the id for node to a given tuple"""
        self._id = value

    @property
    def uuid(self):
        """A unique id (uuid) for the node.

        This is used to identify nodes when serializing e.g. the edges
        of the graph.
        """
        if self._uuid is None:
            self._uuid = uuid.uuid4().int
        return self._uuid

    @uuid.setter
    def uuid(self, value):
        if self._uuid is None:
            self._uuid = value
        else:
            # The uuid is being changed for e.g. copying nodes.
            # Need to correct all edges to other nodes, etc.
            raise NotImplementedError('set_uuid not implemented yet!')

    @property
    def title(self):
        """The title to display"""
        return self._title

    @title.setter
    def title(self, value):
        self._title = value

    @property
    def tag(self):
        """The string representation of the uuid of the node"""
        return 'node=' + str(self.uuid)

    @property
    def visited(self):
        """Whether this node has been visited in a traversal"""
        return self._visited

    @visited.setter
    def visited(self, value):
        self._visited = bool(value)

    @property
    def description(self):
        """A textual description of this node"""
        return self._description

    @description.setter
    def description(self, value):
        self._description = value

    @property
    def indent(self):
        length = len(self._id)
        if length <= 1:
            return ''
        if length > 2:
            result = (length - 2) * '  .' + '   '
        else:
            result = '   '
        return result

    @property
    def header(self):
        """A printable header for this section of output"""
        return (
            'Step {}: {}  {}'.format(
                '.'.join(str(e) for e in self._id), self.title, self.version
            )
        )

    @property
    def n_edges(self):
        """How many edges connect to this node.
        """
        return len(self.edges())

    @property
    def n_outward_edges(self):
        """How many edges leave this node.
        """
        return len(self.edges(direction='out'))

    @property
    def n_inward_edges(self):
        """How many edges enter this node.
        """
        return len(self.edges(direction='in'))

    def add_out_edge(self, edge, name):
        """Store the outgoing edge of type 'name' in the correct place.
        """
        if name == 'next':
            if self.edge['out'] is None:
                self.edge['out'] = edge
            else:
                raise RuntimeError("Edge 'out' is already set.")
        else:
            raise NotImplementedError(
                "You need to override add_out_edge to handle edges of type '" +
                name + "'."
            )

    def add_in_edge(self, edge, name):
        """Store the incoming edge of type 'name' in the correct place.
        """
        if name == 'next':
            if self.edge['in'] is None:
                self.edge['in'] = edge
            else:
                raise RuntimeError("Edge 'in' is already set.")
        else:
            raise NotImplementedError(
                "You need to override add_in_edge to handle edges of type '" +
                name + "'."
            )

    def edges(self, direction='both'):
        """Return a list of edges connecting to this node.

        Parameters
        ----------
        direction: str, default: 'both'
            Whether to list edges coming 'in', 'out', or all edges.

        Returns
        -------
        ret: list of 'edges'
            A list of 'edge' objects matching the requested direction.
        """
        result = []
        for key, edge in self.edge.items():
            if edge is not None:
                if direction == 'in':
                    if edge.node2 == self:
                        result.append(edge)
                elif direction == 'out':
                    if edge.node1 == self:
                        result.append(edge)
                else:
                    result.append(edge)

        return result

    def remove_edge(self, edge):
        """Remove the edge from the node.
        """
        for key, value in self.edge.items():
            if value == edge:
                self.edge[key] = None

    def default_edge_name(self):
        """Return the default type (name) of the edge.

        Usually this is 'next' but for nodes with two or more edges
        leaving them, such as a loop, this method will return an
        appropriate default for the current edge. For example, by
        default the first edge emanating from a loop-node is the
        'loop' edge; the second, the 'next' edge.

        A return value of None indicates that the node exceeds the
        number of allowed exit edges.
        """

        # how many outgoing edges are there?
        n_edges = self.n_outward_edges

        self.logger.debug(
            'node.default_edge_label, n_edges = {}'.format(n_edges)
        )

        if n_edges == 0:
            return "next"
        else:
            return None
