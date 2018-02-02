# -*- coding: utf-8 -*-
"""A node in a workflow


"""

import molssi_workflow
import json
import logging
import molssi_util
import uuid

logger = logging.getLogger(__name__)


class Node(object):
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
        self.gui_object = None
        if gui_object is not None:
            self.gui_object = gui_object
        self.extension = extension

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

        result = []
        # outgoing edges
        for me, neighbor, obj in self.workflow.graph.out_edges(
                self, data='object'):
            result.append(('out', obj))
        # incoming edges
        for neighbor, me, obj in self.workflow.graph.in_edges(
                self, data='object'):
            result.append(('in', obj))
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

        for me, next_node, edge_type in self.workflow.out_edges(self,
                                                                keys=True):
            if edge_type == 'execution':
                return next_node

        return None

    def previous(self):
        """Return the previous node in the flow
        """

        for previous_node, me, edge_type in self.workflow.in_edges(self,
                                                                   keys=True):
            if edge_type == 'execution':
                return previous_node

        return None

    def get_input(self):
        """Return the input from this subnode, usually used for
        building up the input for the executable."""

        return None

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
            if key == 'gui_object':
                continue
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
