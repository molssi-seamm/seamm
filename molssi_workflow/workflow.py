# -*- coding: utf-8 -*-

import json
import logging
import molssi_util
import molssi_workflow
import os
import pprint  # nopep8
import stat

"""A workflow, which is a set of nodes. There must be a single
'start' node, with other nodes connected via their ports to describe
the workflow. There may be isolated nodes or groups of connected nodes;
however, the flow starts at the 'start' node and follows the connections,
so isolated nodes and fragments will not be executed."""

logger = logging.getLogger(__name__)


class Workflow(object):
    """The class variable 'graphics' gives
    the default graphics to use for display, if needed. It defaults to
    'Tk' for the tkinter GUI.
    """

    graphics = 'Tk'

    def __init__(self,
                 parent=None,
                 data=None,
                 namespace='org.molssi.workflow',
                 **kwargs):
        '''Initialize the workflow

        Keyword arguments:
        '''

        self.graph = molssi_workflow.Graph()

        self.parent = parent
        # Setup the plugin handling
        self.plugin_manager = molssi_workflow.PluginManager(namespace)

        # and make sure that the start node exists
        self.add_node(molssi_workflow.StartNode(workflow=self))

    def __iter__(self):
        return self.graph.__iter__()

    def tag_exists(self, tag):
        """Check if the node with a given tag exists"""
        for node in self:
            if node.tag == tag:
                return True
        return False

    def create_node(self, extension_name):
        """Create a new node given the extension name"""
        plugin = self.plugin_manager.get(extension_name)
        node = plugin.create_node(
            workflow=self,
            extension=extension_name
        )
        node.parent = self.parent
        return node

    def add_node(self, n, **attr):
        """Add a single node n, ensuring that it knows the workflow"""
        n.workflow = self
        return self.graph.add_node(n, **attr)

    def get_node(self, tag):
        """Return the node with a given tag"""
        if isinstance(tag, int):
            tag = str(tag)
        for node in self:
            if str(node.uuid) == tag:
                return node
        return None

    def last_node(self, node='1'):
        """Find the last node walking down the main execution path
        from the given node, which defaults to the start node"""

        if isinstance(node, str):
            node = self.get_node(node)

        for edge in self.graph.edges(node, direction='out'):
            if edge.edge_type == "execution":
                return self.last_node(edge.node2)

        return node

    def remove_node(self, node):
        """Delete a node from the workflow, and from the graphics if
        necessary
        """

        # Remove the drawing of the node
        node.undraw()

        # and any edges, including graphics if appropriate
        node.remove_edge('all')

        # and the node
        self.graph.remove_node(node)

    def edges(self, node=None, direction='both'):
        return self.graph.edges(node, direction)

    def to_json(self):
        """Ufff. Turn ourselves into JSON"""
        return json.dumps(self.to_dict())

    def write(self, filename):
        """Write the serialized form to disk"""
        with open(filename, 'w') as fd:
            fd.write('#!/usr/bin/env run_workflow\n')
            fd.write('!MolSSI workflow 1.0\n')
            json.dump(self.to_dict(), fd, indent=4,
                      cls=molssi_util.JSONEncoder)
            logger.info('Wrote json to {}'.format(filename))

        permissions = stat.S_IMODE(os.lstat(filename).st_mode)
        os.chmod(filename, permissions | stat.S_IXUSR | stat.S_IXGRP)

    def read(self, filename):
        """Recreate the workflow from the serialized form on disk"""
        with open(filename, 'r') as fd:
            line = fd.readline(256)
            # There may be exec magic as first line
            if line[0:2] == '#!':
                line = fd.readline(256)
            if line[0:7] != '!MolSSI':
                raise RuntimeError('File is not a MolSSI file! -- ' + line)
            tmp = line.split()
            if len(tmp) < 3:
                raise RuntimeError(
                    'File is not a proper MolSSI file! -- ' + line)
            if tmp[1] != 'workflow':
                raise RuntimeError('File is not a workflow! -- ' + line)
            workflow_version = tmp[2]
            logger.info('Reading workflow version {} from file {}'.format(
                workflow_version, filename))

            data = json.load(fd, cls=molssi_util.JSONDecoder)

        if data['class'] != 'Workflow':
            raise RuntimeError(filename + ' does not contain a workflow')

        self.from_dict(data)

    def to_dict(self):
        """Serialize the graph and everything it contains in a dict"""

        data = {
            'item': 'object',
            'module': self.__module__,
            'class': self.__class__.__name__,
            'extension': None
        }

        nodes = data['nodes'] = []
        for node in self:
            nodes.append(node.to_dict())

        edges = data['edges'] = []
        for edge in self.graph.edges():
            attr = {}
            for key in edge:
                if key not in ('node1', 'node2', 'edge_type'):
                    attr[key] = edge[key]
            edges.append({
                'item': 'edge',
                'node1': edge.node1.uuid,
                'node2': edge.node2.uuid,
                'edge_type': edge.edge_type,
                'attributes': attr
                })

        return data

    def from_dict(self, data):
        """recreate the workflow from the dict. Inverse of to_dict."""
        if 'class' not in data:
            raise RuntimeError('There is no class information in the data!')
        if data['class'] != self.__class__.__name__:
            raise RuntimeError('The dictionary does not contain a workflow!'
                               ' It contains a {} class'.format(data['class']))

        self.clear()

        # Recreate the nodes
        for node in data['nodes']:
            if node['class'] == 'StartNode':
                continue

            logger.debug('creating {} node'.format(node['extension']))
            plugin = self.plugin_manager.get(node['extension'])
            logger.debug('  plugin object: {}'.format(plugin))

            # Recreate the node
            new_node = plugin.create_node(
                workflow=self,
                extension=node['extension']
            )
            new_node.parent = self.parent

            # set uuid to correct value
            new_node._uuid = node['attributes']['_uuid']

            # and add to the workflow
            self.add_node(new_node)

            new_node.from_dict(node)

            logger.debug("adding nodes: nodes:\n\t" +
                         "\n\t".join(self.list_nodes()))

        # and the edges connecting them
        for edge in data['edges']:
            node1 = self.get_node(edge['node1'])
            node2 = self.get_node(edge['node2'])
            self.add_edge(node1, node2, edge_type=edge['edge_type'],
                          **edge['attributes'])

            logger.debug("Adding edges, nodes:\n\t" +
                         "\n\t".join(self.list_nodes()))

    def clear(self, all=False):
        """Override the underlying clear() to ensure that the start node is present
        """
        self.graph.clear()

        # and make sure that the start node exists
        if not all:
            start_node = molssi_workflow.StartNode(workflow=self)
            self.add_node(start_node)

    def list_nodes(self):
        """List the nodes, for debugging"""
        result = []
        for node in self:
            result.append(node.__class__.__name__ + " {}".format(node))
        return result

    def add_edge(self, u, v, edge_type=None, **attr):
        return self.graph.add_edge(u, v, edge_type, **attr)
