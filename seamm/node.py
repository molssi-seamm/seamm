# -*- coding: utf-8 -*-

"""A node in a flowchart


"""

import bibtexparser
import collections.abc
import json
import logging
import pkg_resources
import reference_handler
import seamm
import seamm_util  # MUST come after seamm
from seamm_util.printing import FormattedText as __
import seamm_util.printing as printing
import numpy as np
import os.path
import pandas
import uuid

logger = logging.getLogger(__name__)
job = printing.getPrinter()


class Node(seamm.NodeBase, collections.abc.Hashable):

    def __init__(self, flowchart=None, title='', module=None):
        """Initialize a node

        Keyword arguments:
        """
        super().__init__()

        self._references = None

        # Set up our formatter for printing
        self.formatter = logging.Formatter(fmt='{message:s}', style='{')

        # Setup the bibliography
        self.bibliography = {}
        if self.module:
            filepath = pkg_resources.resource_filename(
                self.module, 'data/references.bib'
            )
            logger.info("bibliography file path = '{}'".format(filepath))

            if os.path.exists(filepath):
                with open(filepath) as fd:
                    tmp = bibtexparser.load(fd).entries_dict
                writer = bibtexparser.bwriter.BibTexWriter()
                for key, data in tmp.items():
                    self.bibliography[key] = writer._entry_to_bibtex(data)

    @property
    def directory(self):
        """Return the directory we should write output to"""
        return os.path.join(self.flowchart.root_directory, *self._id)

    @property
    def references(self):
        """The reference handle for citations."""
        if self._references is None:
            filename = os.path.join(
                self.flowchart.root_directory, 'references.db'
            )
            self._references = reference_handler.Reference_Handler(filename)

        return self._references

    @references.setter
    def references(self, value):
        if self._references is not None:
            self._references.conn.commit()
            self._references.__del__()

        self._references = value

    def set_uuid(self):
        self._uuid = uuid.uuid4().int

        # Need to correct all edges to other nodes
        raise NotImplementedError('set_uuid not implemented yet!')

    def get_gui_data(self, key, gui=None):
        """Return an element from the GUI dictionary"""
        if gui is None:
            return self._gui_data[seamm.Flowchart.graphics][key]
        else:
            return self._gui_data[gui][key]

    def set_gui_data(self, key, value, gui=None):
        """Set an element of the GUI dictionary"""
        if gui is None:
            if seamm.Flowchart.graphics not in self._gui_data:
                self._gui_data[seamm.Flowchart.graphics] = {}
            self._gui_data[seamm.Flowchart.graphics][key] = value
        else:
            if gui not in self._gui_data:
                self._gui_data[gui] = {}
            self._gui_data[gui][key] = value

    def connections(self):
        """Return a list of all the incoming and outgoing edges
        for this node, giving the anchor points and other node
        """

        result = self.flowchart.edges(self)
        return result

    def remove_edge(self, edge):
        """Remove a given edge, or all edges if 'all' is given
        """

        if isinstance(edge, str) and edge == 'all':
            for direction, obj in self.connections():
                self.remove_edge(obj)
        else:
            self.flowchart.graph.remove_edge(
                edge.node1, edge.node2, edge.edge_type, edge.edge_subtype
            )

    def description_text(self, P=None):
        """Return a short description of this step.

        Return a nicely formatted string describing what this step will
        do.

        Keyword arguments:
            P: a dictionary of parameter values, which may be variables
                or final values. If None, then the parameters values will
                be used as is.
        """
        return (
            'This node has no specific description. '
            "Override the method 'description_text' "
            'to provide the description.'
        )

    def describe(self):
        """Write out information about what this node will do
        """

        # The description
        job.job(__(self.description_text(), indent=self.indent))

        return self.next()

    def run(self, printer=None):
        """Do whatever we need to do!

        The base class creates the working directory, sets up printing and
        returns the default edge to the next node. It should be called by all
        run methods, but they may wish to override the edge to return.
        """

        # Create the directory for writing output and files
        os.makedirs(self.directory, exist_ok=True)

        if printer is not None:
            # Setup up the printing for this step
            self.setup_printing(printer)

        return self.next()

    def get_input(self):
        """Return the input from this subnode, usually used for
        building up the input for the executable."""

        return ''

    def to_json(self):
        return json.dumps(self.to_dict(), cls=seamm_util.JSONEncoder)

    def default_edge_subtype(self):
        """Return the default subtype of the edge. Usually this is 'next'
        but for nodes with two or more edges leaving them, such as a loop, this
        method will return an appropriate default for the current edge. For
        example, by default the first edge emanating from a loop-node is the
        'loop' edge; the second, the 'exit' edge.

        A return value of 'too many' indicates that the node exceeds the number
        of allowed exit edges.
        """

        # how many outgoing edges are there?
        n_edges = len(self.flowchart.edges(self, direction='out'))

        logger.debug('node.default_edge_subtype, n_edges = {}'.format(n_edges))

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

        return seamm.flowchart_variables.value(variable_or_value)

    def get_variable(self, variable):
        """Get the value of a variable, which must exist
        """

        return seamm.flowchart_variables.get_variable(variable)

    def set_variable(self, variable, value):
        """Set the value of a variable in the workspace. The name of the
        variable maybe a plain string, or be $<name> or ${<name>}
        """

        seamm.flowchart_variables.set_variable(variable, value)

    def variable_exists(self, variable):
        """Return whether a varable exists in the workspace
        """

        return seamm.flowchart_variables.exists(variable)

    def delete_variable(self, variable):
        """Delete a variable in the workspace
        """

        seamm.flowchart_variables.delete(variable)

    def setup_printing(self, printer):
        """Establish the handlers for printing as controlled by
        options
        """

        # Control output going to the main job printer
        # If we are in a loop, don't print to the job output, except
        # at the JOB level
        job.setLevel(printing.NORMAL)
        for segment in self._id:
            if str(segment)[0:5] == 'iter_':
                job.setLevel(printing.JOB)
                break

        # First remove an existing handlers
        self.close_printing(printer)

        # A handler for stdout
        console_handler = logging.StreamHandler()
        console_handler.setLevel(printing.JOB)
        console_handler.setFormatter(self.formatter)
        printer.addHandler(console_handler)

        # A handler for the file
        file_handler = logging.FileHandler(
            os.path.join(self.directory, 'step.out'), delay=True
        )
        file_handler.setLevel(printing.NORMAL)
        file_handler.setFormatter(self.formatter)
        printer.addHandler(file_handler)

        # # A handler for the job file
        # wdir = self.flowchart.root_directory
        # job_file_handler = logging.FileHandler(os.path.join(wdir, 'job.out'))
        # # job_file_handler.setLevel(printing.JOB)
        # job_file_handler.setLevel(printing.NORMAL)
        # job_file_handler.setFormatter(self.formatter)
        # printer.addHandler(job_file_handler)

    def close_printing(self, printer):
        """Close the handlers for printing, so that buffers are
        flushed, files closed, etc.
        """
        for handler in printer.handlers:
            printer.removeHandler(handler)

    def job_output(self, text):
        """Temporary!"""
        job.job(text)

    def store_results(
        self, data={}, properties=None, results=None, create_tables=True
    ):
        """Store results in variables and tables, as requested

        Keywords:

        properties (dict): a dictionary of properties
        results (dict): a dictionary of results from the calculation
        create_tables (bool): whether to create tables as needed

        Each item in 'results' is itself a dictionary. If the following keys
        are in the dictionary, the appropriate action is taken:

        'variable' -- is the name of a variable to store the result in
        'table' -- the name of the table, and
        'column' -- is the column name for the result in the table.
        """

        for key, value in results.items():
            # Check for storing in a variable
            if 'variable' in value:
                self.set_variable(value['variable'], data[key])

            # and table
            if 'table' in value:
                tablename = value['table']
                column = value['column']
                # Does the table exist?
                if not self.variable_exists(tablename):
                    if create_tables:
                        table = pandas.DataFrame()
                        self.set_variable(
                            tablename, {
                                'type': 'pandas',
                                'table': table,
                                'defaults': {},
                                'loop index': False,
                                'current index': 0
                            }
                        )
                    else:
                        raise RuntimeError(
                            "Table '{}' does not exist.".format(tablename)
                        )

                table_handle = self.get_variable(tablename)
                table = table_handle['table']

                # create the column as needed
                if column not in table.columns:
                    kind = properties[key]['type']
                    if kind == 'boolean':
                        default = False
                    elif kind == 'integer':
                        default = 0
                    elif kind == 'float':
                        default = np.nan
                    else:
                        default = ''

                    table_handle['defaults'][column] = default
                    table[column] = default

                # and put the value in (finally!!!)
                row_index = table_handle['current index']
                if key in data:
                    table.at[row_index, column] = data[key]
