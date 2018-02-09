# -*- coding: utf-8 -*-
"""A node in a workflow


"""

import abc
# from abc import ABC, abstractmethod
import molssi_workflow
import json
import logging
import molssi_util
import uuid

anchor_points = {
    's': (0, 1),
    'sse': (0.25, 1),
    'se': (0.5, 1),
    'ese': (0.5, 0.75),
    'e': (0.5, 0.5),
    'ene': (0.5, 0.25),
    'ne': (0.5, 0),
    'nne': (0.25, 0),
    'n': (0, 0),
    'nnw': (-0.25, 0),
    'nw': (-0.5, 0),
    'wnw': (-0.5, 0.25),
    'w': (-0.5, 0.5),
    'wsw': (-0.5, 0.75),
    'sw': (-0.5, 1),
    'ssw': (-0.25, 1)
}

logger = logging.getLogger(__name__)


class Node(abc.ABC):
    def __init__(self,
                 workflow=None,
                 title='',
                 gui_object=None,
                 extension=None):
        """Initialize a node

        Keyword arguments:
        """

        self._uuid = uuid.uuid4().int
        self.parent = None
        self.workflow = workflow
        self._title = title
        self._gui_data = {}
        self.extension = extension

        self.x = 0.0
        self.y = 0.0
        self.w = 100
        self.h = 100

    def __hash__(self):
        """Make iterable!"""
        return self._uuid

    @property
    def uuid(self):
        """The uuid of the node"""
        return self._uuid

    @property
    def gui_data(self):
        """The current GUI data"""
        if molssi_workflow.Workflow.graphics in self._gui:
            return self._gui_data[molssi_workflow.Workflow.graphics]
        else:
            return None

    @gui_data.setter
    def gui_data(self, data):
        self._gui_data[molssi_workflow.Workflow.graphics] = data

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
        return 'node=' + str(self._uuid)

    def set_uuid(self):
        self._uuid = uuid.uuid4().int

        # Need to correct all edges to other nodes
        raise NotImplementedError('set_uuid not implemented yet!')

    def get_gui_data(self, key, gui=None):
        """Return an element from the GUI dictionary"""
        if gui is None:
            return self._gui_data[molssi_workflow.Workflow.graphics][key]
        else:
            return self._gui_data[gui][key]

    def set_gui_data(self, key, value, gui=None):
        """Set an element of the GUI dictionary"""
        if gui is None:
            if molssi_workflow.Workflow.graphics not in self._gui_data:
                self._gui_data[molssi_workflow.Workflow.graphics] = {}
            self._gui_data[molssi_workflow.Workflow.graphics][key] = value
        else:
            if gui not in self._gui_data:
                self._gui_data[gui] = {}
            self._gui_data[gui][key] = value

    def connections(self):
        """Return a list of all the incoming and outgoing edges
        for this node, giving the anchor points and other node
        """

        result = self.workflow.edges(self)
        return result

    def remove_edge(self, edge):
        """Remove a given edge, or all edges if 'all' is given
        """

        if isinstance(edge, str) and edge == 'all':
            for direction, obj in self.connections():
                self.remove_edge(obj)
        else:
            self.workflow.graph.remove_edge(edge.start_node, edge.end_node,
                                            edge.edge_type)

    def run(self):
        """Do whatever we need to do! The base class does nothing except
        return the next node.
        """

        next_node = self.next()
        if next_node:
            logger.debug('returning next_node: {}'.format(next_node))
        else:
            logger.debug('returning next_node: None')

        return next_node

    def next(self):
        """Return the next node in the flow
        """

        for edge in self.workflow.edges(self, direction='out'):
            if edge.edge_type == 'execution':
                return edge.node2

        return None

    def previous(self):
        """Return the previous node in the flow
        """

        for edge in self.workflow.edges(self, direction='in'):
            if edge.edge_type == 'execution':
                return edge.node1

        return None

    def get_input(self):
        """Return the input from this subnode, usually used for
        building up the input for the executable."""

        return ''

    def to_json(self):
        return json.dumps(self.to_dict(), cls=molssi_util.JSONEncoder)

    def to_dict(self):
        """serialize this object and everything it contains as a dict"""
        data = {
            'item': 'object',
            'module': self.__module__,
            'class': self.__class__.__name__,
            'extension': self.extension
        }
        data['attributes'] = {}
        for key in self.__dict__:
            if key == 'workflow':
                continue
            if key == 'parent':
                continue
            if 'workflow' in key:
                # Have a subworkflow!
                data[key] = self.__dict__[key].to_dict()
            else:
                data['attributes'][key] = self.__dict__[key]
        return data

    def from_dict(self, data):
        """un-serialize object and everything it contains from a dict"""
        if data['item'] != 'object':
            raise RuntimeError('The data for restoring the object is invalid')
        if data['class'] != self.__class__.__name__:
            raise RuntimeError(
                'Trying to restore a {}'.format(self.__class__.__name__) +
                ' from data for a {}'.format(data['class']))
        for key in data:
            if key == 'attributes':
                attributes = data['attributes']
                for key in attributes:
                    self.__dict__[key] = attributes[key]
            elif 'workflow' in key:
                self.__dict__[key].from_dict(data[key])

    def anchor_point(self, anchor="all"):
        """Where the anchor points are located. If "all" is given
        a dictionary of all points is returned"""

        if anchor == "all":
            result = []
            for pt in anchor_points:
                a, b = anchor_points[pt]
                result.append((pt, int(self.x + a * self.w),
                               int(self.y + b * self.h)))
            return result

        if anchor in anchor_points:
            a, b = anchor_points[anchor]
            return (int(self.x + a * self.w), int(self.y + b * self.h))

        raise NotImplementedError(
            "anchor position '{}' not implemented".format(anchor))

    def check_anchor_points(self, x, y, halo):
        """If the position x, y is within halo or one of the anchor points
        activate the point and return the name of the anchor point
        """

        points = []
        for direction, edge in self.connections():
            if direction == 'out':
                points.append(edge.gui_object['start_point'])
            else:
                points.append(edge.gui_object['end_point'])

        for point, x0, y0 in self.anchor_point():
            if x >= x0 - halo and x <= x0 + halo and \
               y >= y0 - halo and y <= y0 + halo:
                if point in points:
                    return None
                else:
                    return point
        return None
