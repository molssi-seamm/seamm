# -*- coding: utf-8 -*-

from abc import ABC, abstractmethod

import json
import logging
import packaging.version
import pprint
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


class FlowchartBase(ABC):
    """The class variable 'graphics' gives
    the default graphics to use for display, if needed. It defaults to
    'Tk' for the tkinter GUI.
    """

    def __init__(
        self,
        data=None,
        namespace='org.molssi.seamm',
        name=None,
    ):
        '''Initialize the flowchart

        Keyword arguments:
        '''

        self.graph = seamm.Graph()

        self.name = name

        # Setup the plugin handling
        self.plugin_manager = seamm.PluginManager(namespace)

    def __iter__(self):
        return self.graph.__iter__()

    @property
    def base_module(self):
        """The module name for the object.

        This should be the non-graphical module, so graphical nodes need to
        override this method and correct the module name.
        """
        return self.__module__

    @property
    def base_class(self):
        """The class name for this object.

        This should be the non-graphical class name, so graphical nodes need to
        override this method and correct the class name.
        """
        return self.__class__.__name__

    # -------------------------------------------------------------------------
    # Node creation and deletion
    # -------------------------------------------------------------------------

    @abstractmethod
    def create_node(self, extension_name):
        """Create a new node given the extension name"""
        pass

    def create_start_node(self):
        """Create the start node"""
        start_node = seamm.StartNode()

        self.graph.add_node(start_node)
        logger.debug('Created start node {}'.format(start_node))

        return start_node

    def add_node(self, n, **attr):
        """Add a single node n, ensuring that it knows the flowchart"""
        n.flowchart = self
        return self.graph.add_node(n, **attr)

    def remove_node(self, node):
        """Delete a node from the flowchart, and from the graphics if
        necessary
        """

        # and edges
        for edge in node.edges():
            # remove reference to edge in the other node
            if edge.node1 == node:
                edge.node2.remove_edge(edge)
            else:
                edge.node1.remove_edge(edge)

        # and the node itself
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
    # Traversal
    # -------------------------------------------------------------------------

    def reset_visited(self):
        """Reset the 'visited' flag, which is used to detect
        loops during traversals
        """
        for node in self:
            node.visited = False

    def set_ids(self, node_id=()):
        """Sequentially number all nodes, and subnodes"""
        logger.debug('Setting ids')

        # Clear all ids
        for node in self:
            node.reset_id()

        # Reset the visited flag to check for loops
        self.reset_visited()

        # Get the start node
        node = self.get_node('1')

        # And traverse the nodes.
        logger.debug('Setting the ids, start node is ' + str(node))
        n = 0
        while node is not None:
            node.visited = True
            try:
                n += 1
                node = node.set_id((*node_id, str(n)))
            except Exception as e:
                print(e)
                raise

            logger.debug('   next node is ' + str(node))
            if node is None or node.visited:
                break

        logger.debug('Finished setting ids')

    def next_node(self, node, edge_subtype='next'):
        """Return the next node from this one, following the given edge.

        This method returns the next node in the graph connected to the
        current node via the edge of the given subtype. For simple nodes
        the edge subtype is 'next', which is the default for this method.

        Parameters:
            node: The current node on the graph.
            edge_subtype: The subtype label for the desired edge. Defaults t0
               'next'.

        Returns:
            next_node: the next node in the graph, or None if at the end.
        """
        for edge in self.edges(node, direction='out'):
            if edge.edge_subtype == 'next':
                logger.debug('Next node is: {}'.format(edge.node2))
                return edge.node2

        logger.debug('Reached the end of the flowchart')
        return None

    # -------------------------------------------------------------------------
    # Strings, reading and writing
    # -------------------------------------------------------------------------

    def to_json(self):
        """Ufff. Turn ourselves into JSON"""
        return json.dumps(self.to_dict())

    def to_dict(self):
        """Serialize the graph and everything it contains in a dict"""
        logger.debug('\nflowchart_base::to_dict')

        data = {
            'item': 'object',
            'module': self.base_module,
            'class': self.base_class,
        }

        nodes = data['nodes'] = []
        for node in self:
            logger.debug('  serializing node {}'.format(node))
            nodes.append(node.to_dict())

        edges = data['edges'] = []
        for edge in self.graph.edges():
            attr = {}
            for key in edge:
                if key not in ('node1', 'node2', 'name'):
                    if key[0] != '_':
                        attr[key] = edge[key]
            edges.append(
                {
                    'item': 'edge',
                    'node1': edge.node1.uuid,
                    'node2': edge.node2.uuid,
                    'name': edge.name,
                    'attributes': attr
                }
            )

        return data

    def from_dict(self, data):
        """Recreate a flowchart from a dict. Inverse of to_dict."""
        if 'class' not in data:
            raise RuntimeError('There is no class information in the data!')
        if data['class'] != self.base_class:
            raise RuntimeError(
                'The dictionary does not contain a flowchart!'
                ' It contains a {} class'.format(data['class'])
            )

        self.clear()

        # Recreate the nodes
        for node in data['nodes']:
            if node['class'] == 'StartNode':
                # The Start node is special ... just update it.
                new_node = self.get_node('1')
                new_node.from_dict(node)
            else:
                new_node = self.create_node(node['class'])

                # set uuid to correct value
                new_node._uuid = node['uuid']
                new_node.from_dict(node)

                # and add to the flowchart
                self.add_node(new_node)

        logger.debug(
            "Added nodes: nodes:\n\t" + "\n\t".join(self.list_nodes())
        )

        # and the edges connecting them
        logger.debug("\nAdding edges, nodes:")
        logger.debug(pprint.pformat(data['edges']))

        for edge in data['edges']:
            node1 = self.get_node(edge['node1'])
            node2 = self.get_node(edge['node2'])
            logger.debug(
                '\tedge: ' + str(node1) + ' - ' + str(node2) + ' name = ' +
                edge['name']
            )
            self.add_edge(
                node1, node2, name=edge['name'], **edge['attributes']
            )

    def write(self, filename):
        """Write the serialized form to disk"""
        with open(filename, 'w') as fd:
            fd.write('#!/usr/bin/env run_flowchart\n')
            fd.write('!MolSSI flowchart 2.0\n')
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
            version = packaging.version.parse(flowchart_version)
            logger.debug("Packaging version is '{}'".format(version))
            logger.debug('  release = {}'.format(version.release))
            if version.release[0] != 2:
                raise RuntimeError(
                    '{} contains a flowchart version {} which cannot be read'
                    .format(filename, version)
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

    def add_edge(self, u, v, **attr):
        edge = self.graph.add_edge(u, v, **attr)
        u.add_out_edge(edge, edge.name)
        v.add_in_edge(edge, edge.name)
        return edge

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
