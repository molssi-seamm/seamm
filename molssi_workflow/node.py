# -*- coding: utf-8 -*-
"""A node in a workflow


"""

import abc
# from abc import ABC, abstractmethod
import molssi_workflow
import json
import logging
import molssi_util
import os.path
import uuid

logger = logging.getLogger(__name__)


class Node(abc.ABC):
    def __init__(self,
                 workflow=None,
                 title='',
                 extension=None):
        """Initialize a node

        Keyword arguments:
        """

        self._uuid = uuid.uuid4().int
        self.parent = None
        self.workflow = workflow
        self._title = title
        self._description = ''
        self._id = None
        self.extension = extension
        self._visited = False

        self.x = None
        self.y = None
        self.w = None
        self.h = None

    def __hash__(self):
        """Make iterable!"""
        return self._uuid

    @property
    def uuid(self):
        """The uuid of the node"""
        return self._uuid

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

    @property
    def directory(self):
        """Return the directory we should write output to"""
        return os.path.join(
            self.workflow.root_directory,
            *self._id
        )

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

    def set_uuid(self):
        self._uuid = uuid.uuid4().int

        # Need to correct all edges to other nodes
        raise NotImplementedError('set_uuid not implemented yet!')

    def set_id(self, node_id):
        """Set the id for node to a given tuple"""
        if self.visited:
            return None
        else:
            self.visited = True
            self._id = node_id
            return self.next()

    def reset_id(self):
        """Reset the id for node"""
        self._id = None

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
            self.workflow.graph.remove_edge(edge.node1, edge.node2,
                                            edge.edge_type)

    def describe(self, indent='', json_dict=None):
        """Write out information about what this node will do
        If json_dict is passed in, add information to that dictionary
        so that it can be written out by the controller as appropriate.
        """

        self.visited = True
        self.job_output(indent + 'Step ' + '.'.join(str(e) for e in self._id) +
                        ': ' + self.title)

        next_node = self.next()

        if next_node is None or next_node.visited:
            return None
        else:
            return next_node

    def run(self):
        """Do whatever we need to do! The base class does nothing except
        return the next node.
        """

        self.log('Step ' + '.'.join(str(e) for e in self._id) +
                 ': ' + self.title)
        self.log('')

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
            if edge['label'] == '' or edge['label'] == 'exit':
                logger.debug('Next node is: {}'.format(edge.node2))
                return edge.node2

        logger.debug('Reached the end of the workflow')
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

    def log(self, *objects, sep=' ', end='\n', flush=False):
        """Write the main output to the correct file"""
        os.makedirs(self.directory, exist_ok=True)
        filename = os.path.join(self.directory, 'out.txt')
        with open(filename, mode='a') as fd:
            print(*objects, sep=sep, end=end, file=fd, flush=flush)

    def job_output(self, *objects, sep=' ', end='\n', flush=False):
        """Write the main job output to the correct file"""
        os.makedirs(self.workflow.root_directory, exist_ok=True)
        filename = os.path.join(self.workflow.root_directory, 'job.txt')
        with open(filename, mode='a') as fd:
            print(*objects, sep=sep, end=end, file=fd, flush=flush)

    def default_edge_label(self):
        """Return the default label of the edge. Usually this is ''
        but for nodes with two or more edges leaving them, such as a loop, this
        method will return an appropriate default for the current edge. For
        example, by default the first edge emanating from a loop-node is the
        'loop' edge; the second, the 'exit' edge.

        A return value of 'too many' indicates that the node exceeds the number
        of allowed exit edges.
        """

        # how many outgoing edges are there?
        n_edges = len(self.workflow.edges(self, direction='out'))

        logger.debug('node.default_edge_label, n_edges = {}'.format(n_edges))

        if n_edges == 0:
            return ""
        else:
            return "too many"

    def analyze(self, indent='', **kwargs):
        """Analyze the output of the calculation
        """
        return

    def get_value(self, variable_or_value):
        """Return the value of the workspace variable is <variable_or_value>
        is the name of a variable. Otherwise, simply return the value of
        <variable_or_value>.

        This provides a convenient way to handle both values and variables
        in widgets. A reference to a variable is $<name> or ${name}, and is
        replaced by the contents of the variable. If the text is not a
        reference to a variable then the value passed in is returned
        unchanged.
        """

        return molssi_workflow.workflow_variables.value(variable_or_value)

    def get_variable(self, variable):
        """Get the value of a variable, which must exist
        """

        return molssi_workflow.workflow_variables.get_variable(variable)

    def set_variable(self, variable, value):
        """Set the value of a variable in the workspace. The name of the
        variable maybe a plain string, or be $<name> or ${<name>}
        """

        molssi_workflow.workflow_variables.set_variable(variable, value)

    def variable_exists(self, variable):
        """Return whether a varable exists in the workspace
        """

        return molssi_workflow.workflow_variables.exists(variable)

    def delete_variable(self, variable):
        """Delete a variable in the workspace
        """

        molssi_workflow.workflow_variables.delete(variable)
