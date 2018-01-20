# -*- coding: utf-8 -*-

import molssi_workflow
import json
import logging
import networkx
import pprint
import stevedore
"""A workflow, which is a set of nodes. There must be a single
'start' node, with other nodes connected via their ports to describe
the workflow. There may be isolated nodes or groups of connected nodes;
however, the flow starts at the 'start' node and follows the connections,
so isolated nodes and fragments will not be executed."""

logger = logging.getLogger(__name__)


class Workflow(networkx.MultiDiGraph):
    """The class variable 'graphics' gives
    the default graphics to use for display, if needed. It defaults to
    'Tk' for the tkinter GUI.
    """

    graphics = 'Tk'

    def __init__(self,
                 data=None,
                 extension_namespace='molssi.workflow.tk',
                 gui_object=None,
                 **kwargs):
        '''Initialize the workflow

        Keyword arguments:
        '''

        # Initialize the parent classes
        super().__init__(data, **kwargs)

        self.gui_object = gui_object
        # Setup the extension handling
        self.extension_namespace = extension_namespace
        self.extension_manager = None
        self.extensions = {}
        self.initialize_extensions()

        # and make sure that the start node exists
        self.add_node(molssi_workflow.StartNode(workflow=self))

    def tag_exists(self, tag):
        """Check if the node with a given tag exists"""
        for node in self:
            if node.tag == tag:
                return True
        return False

    def initialize_extensions(self):
        """Get all available extensions
        """
        logger.info('Initializing extensions for {}'.format(
            self.extension_namespace))

        self.extension_manager = stevedore.extension.ExtensionManager(
            namespace=self.extension_namespace,
            invoke_on_load=True,
            on_load_failure_callback=self.load_failure,
        )

        logger.info("Found {:d} extensions in '{:s}': {}".format(
            len(self.extension_manager.names()), self.extension_namespace,
            self.extension_manager.names()))

        logger.debug('Processing extensions')
        self.extensions = {}
        for name in self.extension_manager.names():
            logger.debug('    extension name: {}'.format(
                self.extension_manager[name]))
            extension = self.extension_manager[name].obj
            logger.debug('  extension object: {}'.format(extension))
            data = extension.description()
            logger.debug('    extension data:')
            logger.debug(pprint.pformat(data))
            logger.debug('')
            group = data['group']
            if group in self.extensions:
                self.extensions[group].append(name)
            else:
                self.extensions[group] = [name]

    def load_failure(self, mgr, ep, err):
        """Called when the extension manager can't load an extension
        """
        logger.warning('Could not load %r: %s', ep.name, err)

    def create_node(self, extension_name, gui_object=None):
        """Create a new node given the extension name"""
        extension = self.extension_manager[extension_name].obj
        node = extension.factory(
            workflow=self,
            gui_object=gui_object,
            extension=extension_name
        )
        self.add_node(node)
        return node

    def add_node(self, n, **attr):
        """Add a single node n, ensuring that it knows the workflow"""
        n.workflow = self
        networkx.MultiDiGraph.add_node(self, n, **attr)

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

        for n0, neighbor, edge_type in self.out_edges(node, keys=True):
            if edge_type == "execution":
                return self.last_node(neighbor)

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
        super().remove_node(node)

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
        data['attributes'] = {'graph': self.__dict__['graph']}

        nodes = data['nodes'] = []
        for node in self:
            nodes.append(node.to_dict())

        edges = data['edges'] = []
        for node1, node2, key, edge_data in self.edges(keys=True, data=True):
            data_edge = {}
            for data_key in edge_data:
                if data_key != 'object':
                    data_edge[data_key] = edge_data[data_key]
            edges.append({
                'item': 'edge',
                'start_node': node1.uuid,
                'end_node': node2.uuid,
                'edge_type': key,
                'data': data_edge
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

        for key in data['attributes']:
            self.__dict__[key] = data['attributes'][key]

        # Recreate the nodes
        for node in data['nodes']:
            if node['class'] == 'StartNode':
                continue

            logger.debug('creating {} node'.format(node['extension']))
            extension = self.extension_manager[node['extension']].obj
            logger.debug('  extension object: {}'.format(extension))

            # Recreate the node
            new_node = extension.factory(
                workflow=self,
                extension=node['extension']
            )
            # set uuid to correct value
            new_node._uuid = node['attributes']['_uuid']

            # and add to the workflow
            self.add_node(new_node)

            # if we have graphics, create the graphics node. This needs to
            # be done *before* deserializing the node because it might have
            # a sub-flowchart.
            if self.gui_object is not None:
                self.gui_object.create_graphics_node(new_node, extension)

            new_node.from_dict(node)

            logger.debug("adding nodes: nodes:\n\t" +
                         "\n\t".join(self.list_nodes()))

        # and the edges connecting them
        for edge in data['edges']:
            start_node = self.get_node(edge['start_node'])
            end_node = self.get_node(edge['end_node'])
            edge_object = molssi_workflow.Edge(
                self,
                start_node,
                end_node,
                edge['edge_type']
            )
            for key in edge['data']:
                edge_object[key] = edge['data'][key]

            # if we have graphics, create the graphical edge
            if self.gui_object is not None:
                self.gui_object.create_edge(edge_object)

            logger.debug("Adding edges, nodes:\n\t" +
                         "\n\t".join(self.list_nodes()))

        # if we have graphics, draw
        if self.gui_object is not None:
            self.gui_object.draw()

    def clear(self):
        """Override the underlying clear() to ensure that the start node is present
        """
        super().clear()

        # and make sure that the start node exists
        start_node = molssi_workflow.StartNode(workflow=self)
        self.add_node(start_node)

        # handle the graphics, if it exists
        if self.gui_object is not None:
            self.gui_object.clear()
            self.gui_object.create_start_node(start_node)

    def list_nodes(self):
        """List the nodes, for debugging"""
        result = []
        for node in self:
            result.append(node.__class__.__name__ + " {}".format(node))
        return result
