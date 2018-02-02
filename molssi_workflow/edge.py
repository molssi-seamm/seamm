# -*- coding: utf-8 -*-
"""The object representation of an edge in the graph.

The necessary information is stored in the graph object as attributes
of the edge so that the graphical representation can be restored as
needed. The data is: ::

    start_point: The anchor that the edge starts at
    end_point:   The anchor that the edge ends at
    coords:      An array of 2N points, where the arrow has N-1 line segments
    object:      The reference to this object.

The object also stores the node and edgy type information as instance
variables: ::

    workflow
    start_node
    end_node
    edge_type
"""

import molssi_workflow
import collections.abc
import logging
import pprint

logger = logging.getLogger(__name__)


class Edge(collections.abc.MutableMapping):
    def __init__(self,
                 workflow,
                 start_node,
                 end_node,
                 edge_type='execution',
                 start_point='s',
                 end_point='n',
                 gui_object=None):
        """Initialize the edge, ensuring that it is
        in the graph.

        Keyword arguments:
        """

        self.workflow = workflow
        self.start_node = start_node
        self.end_node = end_node
        self.edge_type = edge_type
        self._gui_object = {}
        if gui_object is not None:
            self.gui_object = gui_object

        if self.workflow.graph.has_edge(start_node, end_node, key=edge_type):
            self.data = self.workflow.graph[start_node][end_node][edge_type]
        else:
            self.data = {}
            logger.debug('Adding edge {} - {}, {}'.format(
                start_node, end_node, edge_type))
            logger.debug('first node is in workflow'
                         if start_node in self.workflow.graph else
                         'first node is not in the workflow')
            logger.debug('second node is in workflow'
                         if end_node in self.workflow.graph else
                         'second node is not in the workflow')
            self.workflow.graph.add_edge(start_node, end_node, edge_type)
            self['start_point'] = start_point
            self['end_point'] = end_point

        # Record (or perhaps overwrite) that this object is the edge
        self['object'] = self

    def __getitem__(self, key):
        """Allow [] access to the dictionary!"""
        return self.data[key]

    def __setitem__(self, key, value):
        """Allow x[key] access to the data"""
        self.data[key] = value
        self.workflow.graph.add_edge(self.start_node, self.end_node,
                                     self.edge_type, **self.data)

    def __delitem__(self, key):
        """Allow deletion of keys"""
        del self.data[key]
        self.workflow.graph.add_edge(self.start_node, self.end_node,
                                     self.edge_type, **self.data)

    def __iter__(self):
        """Allow iteration over the object"""
        return iter(self.data)

    def __len__(self):
        """The len() command"""
        return len(self.data)

    def __repr__(self):
        """The string representation of this object"""
        return repr(self.data)

    def __str__(self):
        """The pretty string representation of this object"""
        return pprint.pformat(self.data)

    def __contains__(self, item):
        """Return a boolean indicating if a key exists."""
        if item in self.data:
            return True
        return False

    def __eq__(self, other):
        """Return a boolean if this object is equal to another"""
        return self.data == other.data

    def copy(self):
        """Return a shallow copy of the dictionary"""
        return self.data.copy()

    @property
    def gui_object(self):
        """The current GUI node"""
        if molssi_workflow.Workflow.graphics in self._gui_object:
            return self._gui_object[molssi_workflow.Workflow.graphics]
        else:
            return None

    @gui_object.setter
    def gui_object(self, gui_object):
        self._gui_object[molssi_workflow.Workflow.graphics] = gui_object
