# -*- coding: utf-8 -*-

"""A flowchart, which is a set of nodes. There must be a single
'start' node, with other nodes connected via their ports to describe
the flowchart. There may be isolated nodes or groups of connected nodes;
however, the flow starts at the 'start' node and follows the connections,
so isolated nodes and fragments will not be executed.
"""

from datetime import datetime
import logging
import os
import os.path
import reference_handler
import seamm
import seamm_util.printing as printing
from seamm_util.printing import FormattedText as __
import sys
import traceback

logger = logging.getLogger(__name__)
job = printing.getPrinter()


class Flowchart(seamm.FlowchartBase):
    """The class variable 'graphics' gives
    the default graphics to use for display, if needed. It defaults to
    'Tk' for the tkinter GUI.
    """

    graphics = 'Tk'

    def __init__(
        self,
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

        self.output = output  # Where to print output, files, stdout, both

        # Setup the plugin handling
        self.plugin_manager = seamm.PluginManager(namespace)

        # and make sure that the start node exists
        self.add_node(seamm.StartNode())

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

    def create_node(self, plugin_name):
        """Create a new node given the plug-in name"""
        plugin = self.plugin_manager.get(plugin_name)
        node = plugin.create_node()
        return node

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

    def clear(self, all=False):
        """Override the underlying clear() to ensure that the start node is present
        """
        self.graph.clear()

        # and make sure that the start node exists
        if not all:
            self.add_node(seamm.StartNode())

    def list_nodes(self):
        """List the nodes, for debugging"""
        result = []
        for node in self:
            result.append(node.__class__.__name__ + " {}".format(node))
        return result

    # -------------------------------------------------------------------------
    # Traversal
    # -------------------------------------------------------------------------

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

    def run(self, root=None):
        """Execute the flowchart.

        Execute the flowchart, starting with the start node, and proceeding to
        next node, etc. until completion.

        Parameters
        ----------
        root    string or path
            The root directory for running the flowchart.
        """
        logger.debug('Running the flowchart, dir = ' + root)

        self.root_directory = root

        # Create the global variable space.
        logger.debug('Creating global variables space')
        seamm.flowchart_variables = seamm.Variables()

        # Correctly number the nodes
        self.set_ids()

        # Write out an initial summary of the flowchart before doing anything
        # Reset the visited flag for traversal
        self.reset_visited()

        # Describe the flowchart
        logger.debug('   Print the description of the flowchart')
        self.describe()

        # And actually run it!
        job.job(('Running the flowchart\n' '---------------------'))

        node = self.get_node('1')
        logger.debug('Running the flowchart, start node is: {}'.format(node))
        while node is not None:
            try:
                node = node.run()
            except DeprecationWarning as e:
                print('\nDeprecation warning: ' + str(e))
                traceback.print_exc(file=sys.stderr)
                traceback.print_exc(file=sys.stdout)
            except Exception as e:
                print(
                    'Error running flowchart: {} in {}'.format(
                        str(e), str(node)
                    )
                )
                traceback.print_exc(file=sys.stdout)
                logger.critical(
                    'Error running flowchart: {} in {}'.format(
                        str(e), str(node)
                    )
                )
                raise
            except:  # noqa: E722
                print(
                    "Unexpected error running flowchart: ",
                    sys.exc_info()[0]
                )
                traceback.print_exc(file=sys.stdout)
                logger.critical(
                    "Unexpected error running flowchart: ",
                    sys.exc_info()[0]
                )
                raise
            logger.debug('Next node is: {}'.format(node))

        # And print out the references
        filename = os.path.join(self.root_directory, 'references.db')
        references = reference_handler.ReferenceHandler(filename)

        if references.total_citations() > 0:
            tmp = {}
            citations = references.dump(fmt='text')
            for citation, text, count, level in citations:
                if level not in tmp:
                    tmp[level] = {}
                tmp[level][citation] = (text, count)

            for level, ref_dict in sorted(tmp.items(), key=lambda x: x[0]):
                if level == 1:
                    job.job('\nPrimary references:\n')
                elif level == 2:
                    job.job('\nSecondary references:\n')
                else:
                    job.job('\nLess important references:\n')

                lines = []
                for citation in sorted(ref_dict.keys()):
                    text, count = ref_dict[citation]
                    if count == 1:
                        lines.append('\t({:s}) {:s}'.format(citation, text))
                    else:
                        lines.append(
                            '\t({:s}) {:s} (used {:d} times)'.format(
                                citation, text, count
                            )
                        )
                job.job(
                    __(
                        '\n\n'.join(lines),
                        indent=4 * ' ',
                        indent_initial=False
                    )
                )
        # Close the reference handler, which should force it to close the
        # connection.
        del references

    # -------------------------------------------------------------------------
    # Strings, reading and writing
    # -------------------------------------------------------------------------

    def describe(self):
        """Print a description of the flowchart.
        """
        for node in self:
            node.visitied = False

        # Get the start node
        node = self.get_node('1')

        job.job(
            (
                '\nDescription of the flowchart'
                '\n----------------------------'
            )
        )

        while node is not None:
            try:
                logger.debug('      Describing node ' + str(node))
                node.visited = True
                node = node.describe()
            except Exception as e:
                print(
                    'Error describing flowchart: {} in {}'.format(
                        str(e), str(node)
                    )
                )
                logger.critical(
                    'Error describing flowchart: {} in {}'.format(
                        str(e), str(node)
                    )
                )
                raise
            except:  # noqa: E722
                print(
                    "Unexpected error describing flowchart: {} in {}".format(
                        sys.exc_info()[0], str(node)
                    )
                )
                logger.critical(
                    "Unexpected error describing flowchart: {} in {}".format(
                        sys.exc_info()[0], str(node)
                    )
                )
                raise

            logger.debug('  next node is ' + str(node))
            # Get the next node and check if we have visited it already.
            if node is None or node.visited:
                break
        job.job('')

    # -------------------------------------------------------------------------
    # Edges between nodes
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # Printing
    # -------------------------------------------------------------------------
