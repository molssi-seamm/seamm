# -*- coding: utf-8 -*-

"""The base class for nodes (steps) in flowcharts.
"""

import bibtexparser
import calendar
import collections.abc
from datetime import datetime, timezone
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
from seamm_util import CompactJSONEncoder, Q_
import seamm_util
from seamm_util.printing import FormattedText as __
import seamm_util.printing as printing

logger = logging.getLogger(__name__)
job = printing.getPrinter()


def scale(data, factor):
    """Recursive helper to scale e.g. nested lists by a factor."""
    result = []
    for value in data:
        if isinstance(value, list):
            result.append(scale(value, factor))
        else:
            result.append(value * factor)
    return result


class Node(collections.abc.Hashable):
    """The base class for nodes (steps) in flowcharts.

    Parameters
    __________
    flowchart : seamm.Flowchart, optional
        The Flowchart object that contained this node.
    title : str, optional
        The title of this step for use in output.
    extension : str, optional
        Data used in serializing to the flowchart.
    module : str, optional
        The module for this step.
    logger : logging.Logger, optional
        The logger to use for (debug) output. Defaults to the gloabl logger in the
        module.
    uid : str, optional
        The unigue ID for the step, used when reading a flowchart. If not given it is
        generated using uuid.uuid4().

    calculation
    description
    directory
    extension

    flowchart : seamm.Flowchart
        The flowchart that this step is part of.

    global_options
    header
    indent
    job_path

    logger : logging.Logger
        The logger for debug, etc. output.

    metadata
    method
    model
    options

    parent : seamm.Node
        The node that is the parent, usually because this node is in a subflowchart of
        the parent.

    parameters : seamm.Parameters
        The control parameters for this step.

    references
    step_type
    tables
    title

    x : int
        The x-coordinate of the step in the GUI

    y : int
        The y-coordinate of the step in the GUI

    w : int
        The width of the step in the GUI

    h : int
        The height of the step in the GUI

    uuid
    visited

    Notes
    -----
    Handling results
    ~~~~~~~~~~~~~~~~
    The `Node` class takes most or all of the effort out of handling the results of
    calculations in steps. The developer needs to specify the information about possible
    results in `metadata["results"]`. The keys are the steps internal names of the
    results, which match those in the data passed to `store_results()`. The fields of
    the dict for each key give human readable names, units, dimensions, etc.

    The results can be filtered by the `calculation` attribute, and if further filtering
    is needed, the `method` attribute. While these two attirbutes have suggestive names,
    they are simply tags that should match those in the **calculation** filed of the the
    results metadata.

    The `model` attribute is used to form the property name for the database. Often
    results depend on the model chemistry or something similar. The property names
    consist of up to three parts: the property, such as dipole moment; how the property
    was obtained, which is either experiment or the name of the code fo calculated
    results; and the model used, which is usually the model chemistry for calculated
    results.
    """

    def __init__(
        self,
        flowchart=None,
        title="",
        extension=None,
        module=None,
        logger=logger,
        uid=None,
    ):
        if uid is None:
            uid = uuid.uuid4().int

        self._all_options = {}  # All options
        self._bibliography = {}
        self._description = ""
        self._graphs = None
        self._id = None
        self._jinja_env = None
        self._references = None
        self._step_type = None
        self._tables = []
        self._title = title
        self._uuid = uid
        self._visited = False
        self.extension = extension
        self.flowchart = flowchart
        self.logger = logger
        self.parent = None
        self.citation_level = 2  # The level of citation for this code

        # for handling the properties that are results of calculations
        self._metadata = {}
        self._calculation = None  # A tag used to find with results might be created.
        self._method = None  # An optional method such as 'ccsd' or 'dft'.
        self._model = None  # A tag, like 'PM7' or 'MP2/6-31g*', for the model chemistry

        self.parameters = None  # Object containing control parameters

        # Coordinates in the GUI
        self.x = None
        self.y = None
        self.w = None
        self.h = None

        # Set up our formatter for printing
        self.formatter = logging.Formatter(fmt="{message:s}", style="{")

        # Setup the bibliography
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
    def all_options(self):
        """The complete set of all options."""
        return self._all_options

    @all_options.setter
    def all_options(self, value):
        self._all_options = value

    @property
    def calculation(self):
        """The type of calculation for filtering available results."""
        return self._calculation

    @property
    def data_path(self):
        """A path to local and user data, such as forcefields."""
        return self.flowchart.data_path

    @property
    def description(self):
        """A textual description of this node"""
        return self._description

    @description.setter
    def description(self, value):
        self._description = value

    @property
    def directory(self):
        """The directory for output and files for this step."""
        return os.path.join(self.flowchart.root_directory, *self._id)

    @property
    def global_options(self):
        """Dictionary of global options"""
        if "SEAMM" not in self.all_options:
            self.global_options = {}
        return self._all_options["SEAMM"]

    @global_options.setter
    def global_options(self, value):
        self._all_options["SEAMM"] = value

    @property
    def header(self):
        """A printable header for this section of output"""
        return "Step {}: {}  {}".format(
            ".".join(str(e) for e in self._id), self.title, self.version
        )

    @property
    def data_files(self):
        """tuples of short name and path for any data files needed"""
        return self.list_data_files()

    @property
    def in_jobserver(self):
        """Whether running in a jobserver"""
        return self.flowchart.in_jobserver

    @property
    def indent(self):
        """The amount to indent the output of this step in **job.out**."""
        length = len(self._id)
        if length <= 1:
            return ""
        if length > 2:
            result = (length - 2) * (3 * " " + ".") + 4 * " "
        else:
            result = 4 * " "
        return result

    @property
    def job_path(self):
        """Return the path to the job's top-level directory"""
        return Path(self.flowchart.root_directory)

    @property
    def metadata(self):
        """Metadata describing aspects of the calculation.

        The metadata is a dictionary of various types of metdata, often themselves
        dictionaries. Common types of metadata are:

        Parameters
        ----------
        keywords
            The keywords for programs with keyword-based input.
        results
            The results that this step can produce.
        """
        return self._metadata

    @property
    def method(self):
        """The method of a calculation, used for filtering metadata.

        A `calculation`, such as **energy** or **optimization**, might return different
        results depending on the type of calculation or how it is carried out. The
        `method` can be used in the metadata to further filter the calculation results.
        """
        return self._method

    @method.setter
    def method(self, value):
        self._method = value

    @property
    def model(self):
        """The model (chemistry) used to obtain results.

        Properties in the database use a trinomial naming scheme:
            `property`#`code`#`model`

        This is the last part of the name, or None if it is not relevant. It is often
        the `model chemistry`, such as **mp2/6-31g** or **PM7**.
        """
        return self._model

    @model.setter
    def model(self, value):
        self._model = value

    @property
    def options(self):
        """Dictionary of options for this step"""
        step_type = self.step_type
        if step_type not in self._all_options:
            self.options = {}
        return self._all_options[step_type]

    @options.setter
    def options(self, value):
        step_type = self.step_type
        self._all_options[step_type] = value

    @property
    def references(self):
        """The reference handler for citations."""
        if self._references is None:
            filename = os.path.join(self.flowchart.root_directory, "references.db")
            self._references = reference_handler.Reference_Handler(filename)

        return self._references

    @references.setter
    def references(self, value):
        if self._references is not None:
            self._references.conn.commit()

        self._references = value

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
    def tables(self):
        """Any tables this step creates.

        A list of tables this step creates. If it is not easy to decide whether the
        tables are created or just used here, add them to the list. This data is used
        by subsequent steps to present possible tables in the GUI.
        """
        return self._tables

    @tables.setter
    def tables(self, value):
        self._tables = [v for v in value if v.strip() != ""]

    @property
    def tag(self):
        """The string representation of the uuid of the node"""
        return "node=" + str(self._uuid)

    @property
    def title(self):
        """The title to display"""
        return self._title

    @title.setter
    def title(self, value):
        self._title = value

    @property
    def uuid(self):
        """The uuid of the node to give it a unique id."""
        return self._uuid

    @property
    def visited(self):
        """Whether this node has been visited in a traversal"""
        return self._visited

    @visited.setter
    def visited(self, value):
        self._visited = bool(value)

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

    def find_data_file(self, filename):
        """Using the data_path, find a file.

        Parameters
        ----------
        filename : str or pathlib.Path
            Name of the file to find -- a relative path

        Returns
        -------
        path : pathlib.Path
            The path to the file

        Exceptions
        ----------
        FileNotFoundError if the file does not exist.
        """
        for path in self.data_path:
            tmp = path / filename
            self.logger.debug(f"  trying {tmp}")
            if tmp.exists():
                return tmp.expanduser().resolve()
        self.logger.debug(f"Did not find {filename}")
        raise FileNotFoundError(f"Data file '{filename}' not found.")

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
        P=None,
        same_as="current",
        first=True,
        **kwargs,
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
        P : dict(str, any) = None
            The dictionary of options and values. If none, the default system and
            configuration are returned as-is.
        same_as : _Configuration = "current""
            Share atoms, bonds, or cell with this configuration, depending
            on other flags. Defaults to "current", which results in using the current
            configuration. If None, an empty configuration is created/used
        first : bool = True
            First configuration of several, which can have different handling than
            the subsequent ones.

        Returns
        -------
        (System, Configuration)
            The system and configuration.
        """
        # Get the system
        system_db = self.get_variable("_system_db")

        system = system_db.system
        if system is None:
            configuration = None
        else:
            configuration = system.configuration
        if same_as == "current":
            same_as = configuration

        if P is None:
            # Just return the current system and configuration, creating if needed.
            if system is None:
                system = system_db.create_system()
            if configuration is None:
                configuration = system.create_configuration()
        else:
            # Honor the user's request for how to handle the structure.
            # If the system or configuration do not exist they are automatically
            # created.
            if first:
                if "structure handling" in P:
                    handling = P["structure handling"]
                else:
                    handling = "Overwrite the current configuration"
            else:
                if "subsequent structure handling" in P:
                    handling = P["subsequent structure handling"]
                else:
                    handling = "Create a new configuration"

            if handling == "Overwrite the current configuration":
                if system is None:
                    system = system_db.create_system()
                if configuration is None:
                    configuration = system.create_configuration()
            elif handling == "Create a new configuration":
                if system is None:
                    system = system_db.create_system()
                # See if sharing atoms, bonds and/or cell
                if same_as is None:
                    configuration = system.create_configuration()
                else:
                    configuration = system.copy_configuration(
                        configuration=same_as, make_current=True
                    )
            elif handling == "Create a new system and configuration":
                system = system_db.create_system()
                if same_as is None:
                    configuration = system.create_configuration()
                else:
                    configuration = system.copy_configuration(
                        configuration=same_as, make_current=True
                    )
            else:
                raise ValueError(
                    f"Do not understand how to handle the structure: '{handling}'"
                )

            # Attend to naming
            if "system name" in P:
                if P["system name"] == "keep current name":
                    pass
                elif P["system name"] == "use SMILES string":
                    system.name = configuration.smiles
                elif P["system name"] == "use Canonical SMILES string":
                    system.name = configuration.canonical_smiles
                else:
                    # Presume it is a string, perhaps with variables.
                    if len(kwargs) == 0:
                        system.name = str(P["system name"])
                    else:
                        system.name = str(P["system name"]).format(**kwargs)
            if "configuration name" in P:
                if P["configuration name"] == "keep current name":
                    pass
                elif P["configuration name"] == "use SMILES string":
                    configuration.name = configuration.smiles
                elif P["configuration name"] == "use Canonical SMILES string":
                    configuration.name = configuration.canonical_smiles
                else:
                    # Presume it is a string, perhaps with variables.
                    if len(kwargs) == 0:
                        configuration.name = str(P["configuration name"])
                    else:
                        configuration.name = str(P["configuration name"]).format(
                            **kwargs
                        )

        return (system, configuration)

    def get_table(self, tablename, create=True):
        """Get the named table, creating if necessary"""
        if not self.variable_exists(tablename):
            # Create the table if allowed to.
            if not create:
                raise RuntimeError(f"Table {tablename} does not exist.")
            table = pandas.DataFrame()
            self.set_variable(
                tablename,
                {
                    "type": "pandas",
                    "table": table,
                    "defaults": {},
                    "loop index": False,
                    "current index": 0,
                    "index column": None,
                },
            )
        table_handle = self.get_variable(tablename)
        return table_handle["table"]

    def glob_data_files(self, pattern):
        """Using the data_path, glob for files.

        Parameters
        ----------
        filename : str or pathlib.Path
            Name of the file to find -- a relative path

        Returns
        -------
        paths : [pathlib.Path]
            A list of paths to the files

        Exceptions
        ----------
        FileNotFoundError if the file does not exist.
        """
        paths = []
        for path in self.data_path:
            paths.extend(path.glob(pattern))
        return paths

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

        Parameters
        ----------
        P :
            a dictionary of parameter values, which may be variables
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
        job.normal(__(self.description_text(), indent=self.indent))

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

    def existing_tables(self):
        """Tables from previous steps in the flowchart.

        Returns
        -------
        [str]
            Sorted list of existing tables.
        """
        tables = set()
        if self.parent is not None:
            tables.update(self.parent.existing_tables())

        for node in self.flowchart.get_nodes():
            if node == self:
                break
            tables.update(node.tables)

        return sorted(tables)

    def list_data_files(self):
        """Returns a list of auxilliary data files needed, like forcefields.

        Returns
        -------
        (shortname, pathlib.Path)
            Tuples with the local path or URI for the file, and its full pathlib.Path
        """
        return []

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
                if "untagged" in version:
                    # Development version
                    year = datetime.now().year
                    month = datetime.now().month
                else:
                    year, month = version.split(".")[0:2]
                try:
                    month = calendar.month_abbr[int(month)].lower()
                except Exception:
                    year = datetime.now().year
                    month = datetime.now().month
                    month = calendar.month_abbr[int(month)].lower()

                citation = template.substitute(
                    month=month, version=version, year=str(year)
                )

                title = package.split("_")
                title = " ".join([s.capitalize() for s in title[0:-2]])
                self.references.cite(
                    raw=citation,
                    alias=package,
                    module=package,
                    level=self.citation_level,
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
            if key[0] == "_" and key not in ("_uuid", "_method", "_tables", "_title"):
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
            ):
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
        path = Path(self.directory) / "step.out"
        path.unlink(missing_ok=True)
        file_handler = logging.FileHandler(path, delay=True)
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

    def store_results(
        self,
        configuration=None,
        data={},
        create_tables=True,
    ):
        """Store results in the database, as variables,and in tables.

        Parameters
        ----------
        configuration : molsystem._Configuration
           The configuration for storing properties in the database.
        data : dict(str, dict(str, any))
           The data resulting from running the step.
        create_tables : bool, optional
           Whether to create tables that do not yet exist, default is True.
        """
        if "results" not in self.parameters:
            return

        results = self.parameters["results"].value

        json_data = {}
        for key, value in results.items():
            if key not in data or data[key] is None:
                continue

            # The metadata describing this result
            result_metadata = self.metadata["results"][key]

            # Store the value in the database as a property.
            if "property" in value and value["property"]:
                if configuration is not None:
                    properties = configuration.properties
                    _property = value["property"].format(model=self.model)

                    self.logger.debug(
                        f"setting property '{_property}' = {data[key]} ({key=})"
                    )

                    if properties.exists(_property):
                        units = properties.units(_property)
                    else:
                        # Get the general property's info to create the model property.
                        _type, units, description = properties.metadata(
                            value["property"]
                        )
                        properties.add(
                            _property,
                            _type=_type,
                            units=units,
                            description=description.format(model=self.model),
                        )
                    # May need to convert units to those for this property.
                    if "units" in result_metadata:
                        current_units = result_metadata["units"]
                        if units != current_units:
                            if result_metadata["dimensionality"] == "scalar":
                                tmp = Q_(data[key], current_units)
                                properties.put(_property, tmp.m_as(units))
                            else:
                                factor = Q_(1, current_units).m_as(units)
                                tmp = scale(data[key], factor)
                                properties.put(
                                    _property, json.dumps(tmp, separators=(",", ":"))
                                )
                        else:
                            if result_metadata["dimensionality"] == "scalar":
                                properties.put(_property, data[key])
                            else:
                                properties.put(
                                    _property,
                                    json.dumps(data[key], separators=(",", ":")),
                                )
                    else:
                        if result_metadata["dimensionality"] == "scalar":
                            properties.put(_property, data[key])
                        else:
                            properties.put(
                                _property, json.dumps(data[key], separators=(",", ":"))
                            )

            # Store as JSON
            if "json" in value:
                json_data[key] = data[key]
                # And units if present
                if "units" in result_metadata:
                    json_data[key + ",units"] = result_metadata["units"]

            # Store in a variable
            if "variable" in value:
                # Name of the variable
                variable = self.get_value(value["variable"])

                self.logger.debug(f"setting '{variable}' = {data[key]} (key={key})")

                # Convert the value to the requested units.
                if "units" in results[key]:
                    units = results[key]["units"]
                    if "units" in result_metadata:
                        current_units = result_metadata["units"]
                        if units != current_units:
                            tmp = Q_(data[key], current_units)
                            self.set_variable(variable, tmp.m_as(units))
                        else:
                            self.set_variable(variable, data[key])
                    else:
                        raise RuntimeError("Problem with units handling results!")
                else:
                    self.set_variable(variable, data[key])

            # Store in a table
            if "table" in value:
                tablename = value["table"]
                column = self.get_value(value["column"])
                # Does the table exist?
                if not self.variable_exists(tablename):
                    # Create the table if allowed to.
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
                                "index column": None,
                            },
                        )
                    else:
                        raise RuntimeError(
                            "Table '{}' does not exist.".format(tablename)
                        )

                table_handle = self.get_variable(tablename)
                table = table_handle["table"]

                # create the column as needed handling "key"ed columns
                if "{key}" in column:
                    if not isinstance(data[key], dict):
                        raise ValueError(
                            f"Data for a keyed column '{column}' is not a dictionary. "
                            f"{type(data[key])}"
                        )
                    for ckey, value in data[key].items():
                        keyed_column = column.replace("{key}", ckey)
                        if keyed_column not in table.columns:
                            if "units" in result_metadata:
                                units = result_metadata["units"]
                                if "units" in results[key]:
                                    units = results[key]["units"]
                                keyed_column += f" ({units})"
                        if keyed_column not in table.columns:
                            if result_metadata["dimensionality"] == "scalar":
                                kind = result_metadata["type"]
                                if kind == "boolean":
                                    default = False
                                elif kind == "integer":
                                    default = 0
                                elif kind == "float":
                                    default = np.nan
                                else:
                                    default = ""
                            else:
                                kind = "json"
                                default = ""

                            table_handle["defaults"][keyed_column] = default
                            table[keyed_column] = default

                        # Convert the value to the requested units and put in table.
                        row_index = table_handle["current index"]
                        if "units" in results[key]:
                            units = results[key]["units"]
                            if "units" in result_metadata:
                                current_units = result_metadata["units"]
                                if units != current_units:
                                    if result_metadata["dimensionality"] == "scalar":
                                        tmp = Q_(value, current_units)
                                        table.at[row_index, keyed_column] = tmp.m_as(
                                            units
                                        )
                                    else:
                                        factor = Q_(1, current_units).m_as(units)
                                        tmp = scale(value, factor)
                                        table.at[row_index, keyed_column] = json.dumps(
                                            tmp, separators=(",", ":")
                                        )
                                else:
                                    if result_metadata["dimensionality"] == "scalar":
                                        table.at[row_index, keyed_column] = value
                                    else:
                                        table.at[row_index, keyed_column] = json.dumps(
                                            value, separators=(",", ":")
                                        )
                            else:
                                raise RuntimeError(
                                    "Problem with units handling results!"
                                )
                        else:
                            if result_metadata["dimensionality"] == "scalar":
                                table.at[row_index, keyed_column] = value
                            else:
                                table.at[row_index, keyed_column] = json.dumps(
                                    value, separators=(",", ":")
                                )
                else:
                    if column not in table.columns:
                        if "units" in result_metadata:
                            units = result_metadata["units"]
                            if "units" in results[key]:
                                units = results[key]["units"]
                            column += f" ({units})"
                    if column not in table.columns:
                        if result_metadata["dimensionality"] == "scalar":
                            kind = result_metadata["type"]
                            if kind == "boolean":
                                default = False
                            elif kind == "integer":
                                default = 0
                            elif kind == "float":
                                default = np.nan
                            else:
                                default = ""
                        else:
                            kind = "json"
                            default = ""

                        table_handle["defaults"][column] = default
                        table[column] = default

                    # Convert the value to the requested units and put in table.
                    row_index = table_handle["current index"]
                    if "units" in results[key]:
                        units = results[key]["units"]
                        if "units" in result_metadata:
                            current_units = result_metadata["units"]
                            if units != current_units:
                                if result_metadata["dimensionality"] == "scalar":
                                    tmp = Q_(data[key], current_units)
                                    table.at[row_index, column] = tmp.m_as(units)
                                else:
                                    factor = Q_(1, current_units).m_as(units)
                                    tmp = scale(data[key], factor)
                                    table.at[row_index, column] = json.dumps(
                                        tmp, separators=(",", ":")
                                    )
                            else:
                                if result_metadata["dimensionality"] == "scalar":
                                    table.at[row_index, column] = data[key]
                                else:
                                    table.at[row_index, column] = json.dumps(
                                        data[key], separators=(",", ":")
                                    )
                        else:
                            raise RuntimeError("Problem with units handling results!")
                    else:
                        if result_metadata["dimensionality"] == "scalar":
                            table.at[row_index, column] = data[key]
                        else:
                            table.at[row_index, column] = json.dumps(
                                data[key], separators=(",", ":")
                            )

        # Save the data as JSON
        if len(json_data) > 0:
            # Add a timestamp
            json_data["iso time"] = datetime.now(timezone.utc).isoformat()
            path = Path(self.directory) / "Results.json"
            with path.open("w") as fd:
                json.dump(
                    json_data, fd, indent=4, sort_keys=True, cls=CompactJSONEncoder
                )

    def create_figure(self, title="", template="line.graph_template", module_path=None):
        """Create a new figure.

        Parameters
        ----------
        title : str, optional
            The title of the figure
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
                        self.logger.info(f"\t{module} --> {path}")
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
        seamm.Node() :
            The next node in the flowchart.
        """
        if self.visited:
            return None

        self.visited = True
        result = self.next()

        if name is None:
            name = self.step_type
        parser = self.flowchart.parser

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
