# -*- coding: utf-8 -*-

import json
from datetime import datetime
import logging
import seamm
import seamm_util  # MUST come after seamm
import os
import os.path
import stat
"""A flowchart, which is a set of nodes. There must be a single
'start' node, with other nodes connected via their ports to describe
the flowchart. There may be isolated nodes or groups of connected nodes;
however, the flow starts at the 'start' node and follows the connections,
so isolated nodes and fragments will not be executed."""

logger = logging.getLogger(__name__)


class Flowchart(object):
    """The class variable 'graphics' gives
    the default graphics to use for display, if needed. It defaults to
    'Tk' for the tkinter GUI.
    """

    graphics = 'Tk'

    def __init__(
        self,
        parent=None,
        data=None,
        namespace='org.molssi.seamm',
        name=None,
        directory=None,
        output='files'
    ):
        '''Initialize the flowchart

        Keyword arguments:
        '''

        self.graph = seamm.Graph()

        self.name = name
        self.parent = parent

        self.output = output  # Where to print output, files, stdout, both

        # Setup the plugin handling
        self.plugin_manager = seamm.PluginManager(namespace)

        # and make sure that the start node exists
        self.add_node(seamm.StartNode(flowchart=self))

        # And the root directory
        self.root_directory = directory

    def __iter__(self):
        return self.graph.__iter__()

    @property
    def root_directory(self):
        """The root directory for files, etc for this flowchart"""
        if self._root_directory is None:
            self._root_directory = os.path.join(
                os.getcwd(),
                datetime.now().isoformat(sep='_', timespec='seconds')
            )
        return self._root_directory

    @root_directory.setter
    def root_directory(self, value):
        self._root_directory = value

    @property
    def output(self):
        """Where to print output:
            files:  to files in subdirectories
            stdout: to standard output (for intereactive use)
            both:   to both files and standard output
        """
        return self._output

    @output.setter
    def output(self, value):
        if value in ('files', 'stdout', 'both'):
            self._output = value
        else:
            raise RuntimeError(
                "flowchart.output must be one of 'files', 'stdout', or 'both'"
                ", not '{}'".format(value)
            )

    # -------------------------------------------------------------------------
    # Node creation and deletion
    # -------------------------------------------------------------------------

    def create_node(self, extension_name):
        """Create a new node given the extension name"""
        plugin = self.plugin_manager.get(extension_name)
        node = plugin.create_node(flowchart=self, extension=extension_name)
        node.parent = self.parent
        return node

    def add_node(self, n, **attr):
        """Add a single node n, ensuring that it knows the flowchart"""
        n.flowchart = self
        return self.graph.add_node(n, **attr)

    def remove_node(self, node):
        """Delete a node from the flowchart, and from the graphics if
        necessary
        """

        # Remove the drawing of the node
        node.undraw()

        # and any edges, including graphics if appropriate
        node.remove_edge('all')

        # and the node
        self.graph.remove_node(node)

    # -------------------------------------------------------------------------
    # Finding nodes
    # -------------------------------------------------------------------------

    def tag_exists(self, tag):
        """Check if the node with a given tag exists. A tag is a string like
        'node=<uuid>', where <uuid> is the unique integer id for the node.
        """

        for node in self:
            if node.tag == tag:
                return True
        return False

    def get_node(self, uuid):
        """Return the node with a given uuid"""
        if isinstance(uuid, int):
            uuid = str(uuid)
        for node in self:
            if str(node.uuid) == uuid:
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

    def clear(self, all=False):
        """Override the underlying clear() to ensure that the start node is present
        """
        self.graph.clear()

        # and make sure that the start node exists
        if not all:
            start_node = seamm.StartNode(flowchart=self)
            self.add_node(start_node)

    def list_nodes(self):
        """List the nodes, for debugging"""
        result = []
        for node in self:
            result.append(node.__class__.__name__ + " {}".format(node))
        return result

    # -------------------------------------------------------------------------
    # Taversal
    # -------------------------------------------------------------------------

    def reset_visited(self):
        """Reset the 'visited' flag, which is used to detect
        loops during traversals
        """

        for tmp in self:
            tmp.visited = False

    def set_ids(self, node_id=()):
        """Sequentially number all nodes, and subnodes"""
        logger.debug('Setting ids')

        # Clear all ids
        for node in self:
            node.reset_id()

        # Reset the visited flag to check for loops
        self.reset_visited()

        # Get the start node
        next_node = self.get_node('1')

        # And traverse the nodes.
        n = 0
        while next_node:
            next_node = next_node.set_id((*node_id, str(n)))
            n += 1
        logger.debug('Finished setting ids')

    # -------------------------------------------------------------------------
    # Strings, reading and writing
    # -------------------------------------------------------------------------

    def to_json(self):
        """Ufff. Turn ourselves into JSON"""
        return json.dumps(self.to_dict())

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
                if key not in ('node1', 'node2', 'edge_type', 'edge_subtype'):
                    attr[key] = edge[key]
            edges.append(
                {
                    'item': 'edge',
                    'node1': edge.node1.uuid,
                    'node2': edge.node2.uuid,
                    'edge_type': edge.edge_type,
                    'edge_subtype': edge.edge_subtype,
                    'attributes': attr
                }
            )

        return data

    def from_dict(self, data):
        """recreate the flowchart from the dict. Inverse of to_dict."""
        if 'class' not in data:
            raise RuntimeError('There is no class information in the data!')
        if data['class'] != self.__class__.__name__:
            raise RuntimeError(
                'The dictionary does not contain a flowchart!'
                ' It contains a {} class'.format(data['class'])
            )

        self.clear()

        # Recreate the nodes
        for node in data['nodes']:
            if node['class'] == 'StartNode':
                new_node = self.get_node('1')
                new_node.from_dict(node)
                continue

            logger.debug('creating {} node'.format(node['extension']))
            plugin = self.plugin_manager.get(node['extension'])
            logger.debug('  plugin object: {}'.format(plugin))

            # Recreate the node
            new_node = plugin.create_node(
                flowchart=self, extension=node['extension']
            )
            new_node.parent = self.parent

            # set uuid to correct value
            new_node._uuid = node['attributes']['_uuid']

            # and add to the flowchart
            self.add_node(new_node)

            new_node.from_dict(node)

            logger.debug(
                "adding nodes: nodes:\n\t" + "\n\t".join(self.list_nodes())
            )

        # and the edges connecting them
        for edge in data['edges']:
            node1 = self.get_node(edge['node1'])
            node2 = self.get_node(edge['node2'])
            self.add_edge(
                node1,
                node2,
                edge_type=edge['edge_type'],
                edge_subtype=edge['edge_subtype'],
                **edge['attributes']
            )

            logger.debug(
                "Adding edges, nodes:\n\t" + "\n\t".join(self.list_nodes())
            )

    def write(self, filename):
        """Write the serialized form to disk"""
        with open(filename, 'w') as fd:
            fd.write('#!/usr/bin/env run_flowchart\n')
            fd.write('!MolSSI flowchart 1.0\n')
            json.dump(self.to_dict(), fd, indent=4, cls=seamm_util.JSONEncoder)
            logger.info('Wrote json to {}'.format(filename))

        permissions = stat.S_IMODE(os.lstat(filename).st_mode)
        os.chmod(filename, permissions | stat.S_IXUSR | stat.S_IXGRP)

    def read(self, filename):
        """Recreate the flowchart from the serialized form on disk"""
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
                    'File is not a proper MolSSI file! -- ' + line
                )
            if tmp[1] != 'flowchart':
                raise RuntimeError('File is not a flowchart! -- ' + line)
            flowchart_version = tmp[2]
            logger.info(
                'Reading flowchart version {} from file {}'.format(
                    flowchart_version, filename
                )
            )

            data = json.load(fd, cls=seamm_util.JSONDecoder)

        if data['class'] != 'Flowchart':
            raise RuntimeError(filename + ' does not contain a flowchart')

        self.from_dict(data)

    # -------------------------------------------------------------------------
    # Edges between nodes
    # -------------------------------------------------------------------------

    def edges(self, node=None, direction='both'):
        return self.graph.edges(node, direction)

    def add_edge(self, u, v, edge_type=None, edge_subtype='next', **attr):
        return self.graph.add_edge(u, v, edge_type, edge_subtype, **attr)

    def print_edges(self, event=None):
        '''Print all the edges. Useful for debugging!
        '''

        print('All edges in flowchart')
        for edge in self.edges():
            # print('   {}'.format(edge))
            print(
                '   {} {} {} {} {} {}'.format(
                    edge.node1.tag, edge.anchor1, edge.node2.tag, edge.anchor2,
                    edge.edge_type, edge.edge_subtype
                )
            )

    # -------------------------------------------------------------------------
    # Printing
    # -------------------------------------------------------------------------
