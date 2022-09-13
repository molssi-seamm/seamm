# -*- coding: utf-8 -*-

"""A node in a flowchart


"""

import bibtexparser
import calendar
import collections.abc
import hashlib

try:
    import importlib.metadata as implib
except Exception:
    import importlib_metadata as implib
import jinja2
import json
import logging
import os.path
from pathlib import Path
import pprint
import string
import traceback

import numpy as np
import pandas
import uuid

import reference_handler
import seamm
import seamm_util
from seamm_util.printing import FormattedText as __
import seamm_util.printing as printing

logger = logging.getLogger(__name__)
job = printing.getPrinter()


class Node(collections.abc.Hashable):
    def __init__(
        self,
        flowchart=None,
        title="",
        extension=None,
        module=None,
        logger=logger,
        uid=None,
    ):
        """Initialize a node

        Keyword arguments:
        """

        if uid is None:
            uid = uuid.uuid4().int

        self._uuid = uid
        self.logger = logger
        self.parent = None
        self.flowchart = flowchart
        self._title = title
        self._description = ""
        self._id = None
        self.extension = extension
        self._visited = False
        self._references = None
        self._jinja_env = None
        self._graphs = None
        self._options = {}  # Command-line options for this step
        self._global_options = {}  # Command-line global options
        self._step_type = None

        self.parameters = None  # Object containing control parameters

        self.x = None
        self.y = None
        self.w = None
        self.h = None

        # Set up our formatter for printing
        self.formatter = logging.Formatter(fmt="{message:s}", style="{")

        # Setup the bibliography
        self._bibliography = {}
        package = self.__module__.split(".")[0]
        files = [p for p in implib.files(package) if "references.bib" in str(p)]
        if len(files) > 0:
            path = files[0].locate()
            self.logger.info(f"bibliography file path = '{path}'")

            data = path.read_text()
            tmp = bibtexparser.loads(data).entries_dict
            writer = bibtexparser.bwriter.BibTexWriter()
            for key, data in tmp.items():
                self.logger.info(f"      {key}")
                self._bibliography[key] = writer._entry_to_bibtex(data)
            self.logger.debug("Bibliography\n" + pprint.pformat(self._bibliography))

    def __hash__(self):
        """Make iterable!"""
        return self._uuid

    def __eq__(self, other):
        return self.__class__ == other.__class__ and self.digest() == other.digest()

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
        return "node=" + str(self._uuid)

    @property
    def directory(self):
        """Return the directory we should write output to"""
        return os.path.join(self.flowchart.root_directory, *self._id)

    @property
    def job_path(self):
        """Return the path to the job's top-level directory"""
        return Path(self.flowchart.root_directory)

    @property
    def visited(self):
        """Whether this node has been visited in a traversal"""
        return self._visited

    @visited.setter
    def visited(self, value):
        self._visited = bool(value)

    @property
    def step_type(self):
        """The step type, e.g. 'lammps-step', used for e.g. options"""
        if self._step_type is None:
            name = self.__module__.split(".")[0].replace("_", "-")
            if name == "seamm":
                name = self.__module__.split(".")[1].replace("_", "-")
                name += "-step"
            self._step_type = name

        return self._step_type

    @property
    def options(self):
        """Dictionary of options for this step"""
        return self._options

    @options.setter
    def options(self, value):
        self._options = value

    @property
    def global_options(self):
        """Dictionary of global options"""
        return self._global_options

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

    @property
    def indent(self):
        length = len(self._id)
        if length <= 1:
            return ""
        if length > 2:
            result = (length - 2) * (3 * " " + ".") + 4 * " "
        else:
            result = 4 * " "
        return result

    @property
    def header(self):
        """A printable header for this section of output"""
        return "Step {}: {}  {}".format(
            ".".join(str(e) for e in self._id), self.title, self.version
        )

    @property
    def references(self):
        """The reference handle for citations."""
        if self._references is None:
            filename = os.path.join(self.flowchart.root_directory, "references.db")
            self._references = reference_handler.Reference_Handler(filename)

        return self._references

    @references.setter
    def references(self, value):
        if self._references is not None:
            self._references.conn.commit()

        self._references = value

    @staticmethod
    def is_expr(value):
        """Return whether the value is an expression or constant.

        Parameters
        ----------
        value : str
            The value to test

        Returns
        -------
        bool
           True for an expression, False otherwise.
        """
        return len(value) > 0 and value[0] == "$"

    def set_uuid(self):
        self._uuid = uuid.uuid4().int

        # Need to correct all edges to other nodes
        raise NotImplementedError("set_uuid not implemented yet!")

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

    def get_system_configuration(
        self,
        P,
        structure_handling=False,
        same_as=None,
        same_atoms=True,
        same_bonds=True,
        same_cell=True,
    ):
        """Get the current system and configuration.

        Optionally use the standard structure handling to create new
        configuration or new system and configuration based on user
        input.

        Note that if the system or configuration do not exist, they are
        automatically created as needed. This allows flowcharts to be started
        with and empty system database and "do the right" thing if a plug-in
        wants to use the curent configuration.

        Parameters
        ----------
        P : dict(str, any)
            The diction of options and values.
        structure_handling : bool = False
            Use the standard structure handling to determine whether to
            create new configuration or new system.
        same_as : _Configuration = None
            Share atoms, bonds, or cell with this configuration, depending
            on other flags. Defaults to None, meaning ignore.
        same_atoms : bool = True
            Whether to share atoms with the <same_as> configuration
        same_bonds : bool = True
            Whether to share bonds with the <same_as> configuration.
        same_cells : bool = True
            Whether to share the cell with the <same_as> configuration.

        Returns
        -------
        (System, Configuration)
            The system and configuration.
        """
        # Get the system
        system_db = self.get_variable("_system_db")

        if structure_handling:
            # Honor the user's request for how to handle the structure.
            # If the system or configuration do not exist they are automatically
            # created.
            handling = P["structure handling"]
            if handling == "Overwrite the current configuration":
                system = system_db.system
                if system is None:
                    system = system_db.create_system()
                configuration = system.configuration
                if configuration is None:
                    configuration = system.create_configuration()
                configuration.clear()
            elif handling == "Create a new configuration":
                system = system_db.system
                if system is None:
                    system = system_db.create_system()
                # See if sharing atoms, bonds and/or cell
                if same_as is None:
                    configuration = system.create_configuration()
                else:
                    atoms = same_as.atomset if same_atoms else None
                    bonds = same_as.bondset if same_bonds else None
                    cell = same_as.cell_id if same_cell else None

                    configuration = system.create_configuration(
                        cell_id=cell, atomset=atoms, bondset=bonds
                    )
            elif handling == "Create a new system and configuration":
                system = system_db.create_system()
                configuration = system.create_configuration()
            else:
                raise ValueError(
                    f"Do not understand how to handle the structure: '{handling}'"
                )
        else:
            # Just return the current system and configuration, creating if needed.
            system = system_db.system
            if system is None:
                system = system_db.create_system()
            configuration = system.configuration
            if configuration is None:
                configuration = system.create_configuration()

        return (system, configuration)

    def connections(self):
        """Return a list of all the incoming and outgoing edges
        for this node, giving the anchor points and other node
        """

        result = self.flowchart.edges(self)
        return result

    def remove_edge(self, edge):
        """Remove a given edge, or all edges if 'all' is given"""

        if isinstance(edge, str) and edge == "all":
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
            "This node has no specific description. "
            "Override the method 'description_text' "
            "to provide the description."
        )

    def describe(self):
        """Write out information about what this node will do"""

        self.visited = True

        # The description
        job.job(__(self.description_text(), indent=self.indent))

        next_node = self.next()

        if next_node is None or next_node.visited:
            return None
        else:
            return next_node

    def digest(self, strict=False):
        """Generate a unique hash key for this node.

        Parameters
        ----------
        strict: bool
            Whether to include version information. Default: False

        Returns
        -------
        string
        """
        hasher = hashlib.sha256()
        if strict:
            hasher.update(bytes(self.version, "utf-8"))

        for key in self.__dict__:
            if key == "subflowchart":
                # Have a subflowchart!
                hasher.update(bytes(self.__dict__[key].digest(strict=strict), "utf-8"))
            elif key == "parameters":
                if self.parameters is not None:
                    hasher.update(bytes(str(self.parameters.to_dict()), "utf-8"))
                else:
                    if self.__class__.__name__ not in (
                        "StartNode",
                        "LAMMPS",
                        "MOPAC",
                        "Psi4",
                        "Join",
                        "Table",
                    ):
                        print(f"{self.__class__.__name__} has no parameters")

        return hasher.hexdigest()

    def run(self, printer=None):
        """Do whatever we need to do! The base class does nothing except
        return the next node.
        """

        # Create the directory for writing output and files
        os.makedirs(self.directory, exist_ok=True)

        if printer is not None:
            # Setup up the printing for this step
            self.setup_printing(printer)

        # Add a citation for this plug-in
        package = self.__module__.split(".")[0]
        if package in self._bibliography:
            try:
                template = string.Template(self._bibliography[package])

                version = self.version
                year, month = version.split(".")[0:2]
                month = calendar.month_abbr[int(month)].lower()
                citation = template.substitute(month=month, version=version, year=year)

                title = package.split("_")
                title = " ".join([s.capitalize() for s in title[0:-2]])
                self.references.cite(
                    raw=citation,
                    alias=package,
                    module=package,
                    level=2,
                    note=(f"The principle citation for the {title} step in " "SEAMM."),
                )

            except Exception as e:
                printer.important(f"Exception in citation {type(e)}: {e}")
                printer.important(traceback.format_exc())

        next_node = self.next()
        if next_node:
            self.logger.debug("returning next_node: {}".format(next_node))
        else:
            self.logger.debug("returning next_node: None")

        self.close_printing(printer)

        return next_node

    def next(self):
        """Return the next node in the flow"""

        for edge in self.flowchart.edges(self, direction="out"):
            if edge.edge_subtype == "next":
                self.logger.debug("Next node is: {}".format(edge.node2))
                return edge.node2

        self.logger.debug("Reached the end of the flowchart")
        return None

    def previous(self):
        """Return the previous node in the flow"""

        for edge in self.flowchart.edges(self, direction="in"):
            if edge.edge_type == "execution" and edge.edge_subtype == "next":
                return edge.node1

        return None

    def get_input(self):
        """Return the input from this subnode, usually used for
        building up the input for the executable."""

        return ""

    def to_json(self):
        return json.dumps(self.to_dict(), cls=seamm_util.JSONEncoder)

    def to_dict(self):
        """serialize this object and everything it contains as a dict"""
        data = {
            "item": "object",
            "module": self.__module__,
            "class": self.__class__.__name__,
            "version": self.version,
            "extension": self.extension,
        }
        data["attributes"] = {}
        for key in self.__dict__:
            # Remove unneeded variables
            if key[0] == "_" and key not in ("_uuid", "_method", "_title"):
                # _method needed because forcefield_step/forcefield.py does not
                # use parameters yet!
                continue
            if key in (
                "bibliography",
                "flowchart",
                "formatter",
                "logger",
                "options",
                "parent",
                "parser",
                "tmp_table",
                "unknown",
            ):  # yapf: disable
                continue

            if "flowchart" in key:
                # Have a subflowchart!
                data[key] = self.__dict__[key].to_dict()
            else:
                data["attributes"][key] = self.__dict__[key]
        return data

    def from_dict(self, data):
        """un-serialize object and everything it contains from a dict"""
        if data["item"] != "object":
            raise RuntimeError("The data for restoring the object is invalid")
        if data["class"] != self.__class__.__name__:
            raise RuntimeError(
                "Trying to restore a {}".format(self.__class__.__name__)
                + " from data for a {}".format(data["class"])
            )
        for key in data:
            if key == "attributes":
                attributes = data["attributes"]
                for subkey in attributes:
                    self.__dict__[subkey] = attributes[subkey]
            elif "flowchart" in key:
                self.__dict__[key].from_dict(data[key])

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
        n_edges = len(self.flowchart.edges(self, direction="out"))

        self.logger.debug("node.default_edge_subtype, n_edges = {}".format(n_edges))

        if n_edges == 0:
            return ""
        else:
            return "too many"

    def analyze(self, indent="", **kwargs):
        """Analyze the output of the calculation"""
        return

    def file_path(self, filename):
        """Remove any prefix from a filename and return the path.

        Parameters
        ----------
        filename : str
            The filename with optional prefix such as 'job:'

        Returns
        -------
        pathlib.Path
            The normalized, full path.
        """
        path = str(filename)
        if path[0:4] == "job:":
            path = path[4:]
            path = self.job_path / path
        else:
            path = Path(filename)

        path = path.expanduser().resolve()

        return path

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
        """Get the value of a variable, which must exist"""

        return seamm.flowchart_variables.get_variable(variable)

    def set_variable(self, variable, value):
        """Set the value of a variable in the workspace. The name of the
        variable maybe a plain string, or be $<name> or ${<name>}
        """

        seamm.flowchart_variables.set_variable(variable, value)

    def variable_exists(self, variable):
        """Return whether a varable exists in the workspace"""

        return seamm.flowchart_variables.exists(variable)

    def delete_variable(self, variable):
        """Delete a variable in the workspace"""

        seamm.flowchart_variables.delete(variable)

    def setup_printing(self, printer):
        """Establish the handlers for printing as controlled by
        options
        """

        # Control output going to the main job printer
        # If we are in a loop, don't print to the job output, except
        # at the JOB level
        # job.setLevel(printing.NORMAL)
        # for segment in self._id:
        #     if str(segment)[0:5] == 'iter_':
        #         job.setLevel(printing.JOB)
        #         break

        # First remove an existing handlers
        self.close_printing(printer)

        # A handler for stdout
        console_handler = logging.StreamHandler()
        console_handler.setLevel(printing.JOB)
        console_handler.setFormatter(self.formatter)
        printer.addHandler(console_handler)

        # A handler for the file
        file_handler = logging.FileHandler(
            os.path.join(self.directory, "step.out"), delay=True
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
        if printer is not None:
            for handler in printer.handlers:
                handler.close()
                printer.removeHandler(handler)

    def job_output(self, text):
        """Temporary!"""
        job.job(text)

    def store_results(self, data={}, properties=None, results=None, create_tables=True):
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
            if "variable" in value:
                variable = self.get_value(value["variable"])
                self.logger.debug(
                    f"results: setting '{variable}' = {data[key]} (key={key})"
                )
                self.set_variable(variable, data[key])

            # and table
            if "table" in value:
                tablename = value["table"]
                column = self.get_value(value["column"])
                # Does the table exist?
                if not self.variable_exists(tablename):
                    if create_tables:
                        table = pandas.DataFrame()
                        self.set_variable(
                            tablename,
                            {
                                "type": "pandas",
                                "table": table,
                                "defaults": {},
                                "loop index": False,
                                "current index": 0,
                            },
                        )
                    else:
                        raise RuntimeError(
                            "Table '{}' does not exist.".format(tablename)
                        )

                table_handle = self.get_variable(tablename)
                table = table_handle["table"]

                # create the column as needed
                if column not in table.columns:
                    kind = properties[key]["type"]
                    if kind == "boolean":
                        default = False
                    elif kind == "integer":
                        default = 0
                    elif kind == "float":
                        default = np.nan
                    else:
                        default = ""

                    table_handle["defaults"][column] = default
                    table[column] = default

                # and put the value in (finally!!!)
                row_index = table_handle["current index"]
                if key in data:
                    if data[key] is not None:
                        table.at[row_index, column] = data[key]

    def create_figure(self, title="", template="line.graph_template", module_path=None):
        """Create a new figure.

        Parameters
        ----------
        title : str, optional
        template : str, optional
            The Jinja template for the desired graph. Defaults to
            'line.graph_template'

        Returns
        -------
        seamm_util.Figure
        """

        if self._jinja_env is None:
            # The order of the loaders is important! They are searched
            # in order, so the first has precedence. This searches the
            # current package first, then looks in the main SEAMM
            # templates.
            if module_path is None:
                self.logger.info("Reading graph templates from 'seamm'")
                loaders = [jinja2.PackageLoader("seamm")]
            else:
                self.logger.info(
                    "Reading graph templates from the following modules, in order"
                )
                loaders = []
                for module in module_path:
                    paths = []
                    for p in implib.files(module):
                        if p.parent.name == "templates":
                            paths.append(p)
                            break

                    if len(paths) == 0:
                        self.logger.info(f"\t{module} -- found no templates directory")
                    else:
                        path = paths[0].locate().parent
                        self.logger.info(f"\t{ module} --> {path}")
                        loaders.append(jinja2.FileSystemLoader(path))

            self._jinja_env = jinja2.Environment(loader=jinja2.ChoiceLoader(loaders))

        figure = seamm_util.Figure(
            jinja_env=self._jinja_env, template=template, title=title
        )
        return figure

    def create_parser(self, name=None):
        """Create the parser for this node.

        All nodes have at least --log-level, which is setup here,

        Parameters
        ----------
        name : str
            The name of the parser. Defaults to a name derived from the module.

        Returns
        -------
        seamm.Node()
            The next node in the flowchart.
        """
        if self.visited:
            return None

        self.visited = True
        result = self.next()

        if name is None:
            name = self.step_type
        parser = seamm_util.seamm_parser()

        if not parser.exists(name):
            parser.add_parser(name)

            parser.add_argument_group(
                name,
                "debugging options",
                "Options for turning on debugging output and tools",
            )

            parser.add_argument(
                name,
                "--log-level",
                group="debugging options",
                default="WARNING",
                type=str.upper,
                choices=["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                help=(
                    "The level of informational output, defaults to " "'%(default)s'"
                ),
            )

        return result
