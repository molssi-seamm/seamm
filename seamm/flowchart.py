# -*- coding: utf-8 -*-

"""A flowchart, which is a set of nodes. There must be a single
'start' node, with other nodes connected via their ports to describe
the flowchart. There may be isolated nodes or groups of connected nodes;
however, the flow starts at the 'start' node and follows the connections,
so isolated nodes and fragments will not be executed."""

import configparser
from datetime import datetime
import hashlib
import json
import logging
from pathlib import Path
import os
import os.path
import stat

from packaging.version import Version

import seamm
import seamm_util

logger = logging.getLogger(__name__)


class Flowchart(object):
    graphics = "Tk"
    """str: The default graphics to use for display, if
    needed. Default: 'Tk'
    """

    def __init__(
        self,
        parent=None,
        data=None,
        namespace="org.molssi.seamm",
        name="",
        description="",
        directory=None,
        output="files",
    ):
        """Initialize the flowchart.

        Parameters
        ----------
        parent : Object
            The parent of the nodes in this flowchart.
        data : dict
            An initial graph.
        namespace : str
            The namespace for locating plug-ins.
        directory : str
            The root directory for files for this flowchart.
        output : str
            Where to direct output. Currently not used.
        """

        self.graph = seamm.Graph()
        self.parent = parent
        self.output = output  # Where to print output, files, stdout, both
        self.metadata = {}
        self.reset_metadata(title=name, description=description)

        # Setup the plugin handling
        self.plugin_manager = seamm.PluginManager(namespace)

        # and make sure that the start node exists
        self.add_node(seamm.StartNode(flowchart=self))

        # And the root directory
        self.root_directory = directory

    def __iter__(self):
        return self.graph.__iter__()

    @property
    def is_development(self):
        """Check if any of nodes are development versions."""
        for node in self:
            if Version(node.version).is_prerelease:
                return True
        return False

    @property
    def root_directory(self):
        """The root directory for files, etc for this flowchart"""
        if self._root_directory is None:
            self._root_directory = os.path.join(
                os.getcwd(), datetime.now().isoformat(sep="_", timespec="seconds")
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
        if value in ("files", "stdout", "both"):
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
        node.remove_edge("all")

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

    def last_node(self, node="1"):
        """Find the last node walking down the main execution path
        from the given node, which defaults to the start node"""

        if isinstance(node, str):
            node = self.get_node(node)

        for edge in self.graph.edges(node, direction="out"):
            if edge.edge_type == "execution":
                return self.last_node(edge.node2)

        return node

    def clear(self, all=False):
        """Override the underlying clear() to ensure that the start node is present"""
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

        for tmp in self:
            tmp.visited = False

    def set_ids(self, node_id=()):
        """Sequentially number all nodes, and subnodes"""
        logger.debug("Setting ids")

        # Clear all ids
        for node in self:
            node.reset_id()

        # Reset the visited flag to check for loops
        self.reset_visited()

        # Get the start node
        next_node = self.get_node("1")

        # And traverse the nodes.
        n = 0
        while next_node:
            next_node = next_node.set_id((*node_id, str(n)))
            n += 1
        logger.debug("Finished setting ids")

    def create_parsers(self):
        """Create the argument parsers for the nodes."""
        logger.debug("Creating argument parsers.")
        # Reset the visited flag to check for loops
        self.reset_visited()

        # Get the start node
        next_node = self.get_node("1")

        # And traverse the nodes.
        while next_node:
            next_node = next_node.create_parser()
        logger.debug("Finished creating argument parsers.")

    def set_log_level(self, options):
        """Set the log level for each node based on the options"""
        logger.debug("Setting the log-level")

        for node in self:
            step_type = node.step_type
            logger.debug(f"    checking for node type {step_type}")
            if step_type in options and "log_level" in options[step_type]:
                logger.debug(f"      log_level = {options[step_type]['log_level']}")
                try:
                    node.logger.setLevel(options[step_type]["log_level"])
                    logger.debug("        set!")
                except Exception as e:
                    print(f"Exception {type(e)}: {e}")
        logger.debug("Finished setting node log levels.")

    # -------------------------------------------------------------------------
    # Strings, reading and writing
    # -------------------------------------------------------------------------

    def digest(self, strict=False):
        """Generate a unique hash key for this flowchart.

        Parameters
        ----------
        strict: bool
            Whether to include version information. Default: False

        Returns
        -------
        string
        """
        hasher = hashlib.sha256()

        # Hash the nodes and edges in the graph by traversing the graph

        # Reset the visited flag to check for loops
        self.reset_visited()

        # Get the start node
        next_node = self.get_node("1")

        # And traverse the nodes.
        while next_node:
            if next_node.visited:
                break
            next_node.visited = True
            hasher.update(bytes(next_node.digest(strict=strict), "utf-8"))
            next_node = next_node.next()

        return hasher.hexdigest()

    def to_json(self):
        """Ufff. Turn ourselves into JSON"""
        return json.dumps(self.to_dict())

    def to_dict(self):
        """Serialize the graph and everything it contains in a dict"""

        data = {
            "item": "object",
            "module": self.__module__,
            "class": self.__class__.__name__,
            "extension": None,
        }

        nodes = data["nodes"] = []
        for node in self:
            nodes.append(node.to_dict())

        edges = data["edges"] = []
        for edge in self.graph.edges():
            attr = {}
            for key in edge:
                if key not in ("node1", "node2", "edge_type", "edge_subtype"):
                    attr[key] = edge[key]
            edges.append(
                {
                    "item": "edge",
                    "node1": edge.node1.uuid,
                    "node2": edge.node2.uuid,
                    "edge_type": edge.edge_type,
                    "edge_subtype": edge.edge_subtype,
                    "attributes": attr,
                }
            )

        return data

    def from_dict(self, data):
        """recreate the flowchart from the dict. Inverse of to_dict."""
        if "class" not in data:
            raise RuntimeError("There is no class information in the data!")
        if data["class"] != self.__class__.__name__:
            raise RuntimeError(
                "The dictionary does not contain a flowchart!"
                " It contains a {} class".format(data["class"])
            )

        self.clear()

        # Recreate the nodes
        for node in data["nodes"]:
            if node["class"] == "StartNode":
                new_node = self.get_node("1")
                new_node.from_dict(node)
                continue

            logger.debug("creating {} node".format(node["extension"]))
            plugin = self.plugin_manager.get(node["extension"])
            logger.debug("  plugin object: {}".format(plugin))

            # Recreate the node
            new_node = plugin.create_node(flowchart=self, extension=node["extension"])
            new_node.parent = self.parent

            # set uuid to correct value
            new_node._uuid = node["attributes"]["_uuid"]

            # and add to the flowchart
            self.add_node(new_node)

            new_node.from_dict(node)

            logger.debug("adding nodes: nodes:\n\t" + "\n\t".join(self.list_nodes()))

        # and the edges connecting them
        for edge in data["edges"]:
            node1 = self.get_node(edge["node1"])
            node2 = self.get_node(edge["node2"])
            self.add_edge(
                node1,
                node2,
                edge_type=edge["edge_type"],
                edge_subtype=edge["edge_subtype"],
                **edge["attributes"],
            )

            logger.debug("Adding edges, nodes:\n\t" + "\n\t".join(self.list_nodes()))

    def write(self, filename):
        """Write the serialized form to disk"""
        with open(filename, "w") as fd:
            fd.write(self.to_text())

        logger.info(f"Wrote flowchart to {filename}")

        permissions = stat.S_IMODE(os.lstat(filename).st_mode)
        os.chmod(filename, permissions | stat.S_IXUSR | stat.S_IXGRP)

    def to_text(self):
        """Return the text for the flowchart.

        This is the representation written to disk, submitted
        as jobs, etc. There are two header lines followed by json
        representing the flowchart.

        Returns
        -------
        str : the text representation.
        """
        text = "#!/usr/bin/env run_flowchart\n"
        text += "!MolSSI flowchart 2.0\n"
        text += "#metadata\n"
        self.metadata["sha256"] = self.digest()
        self.metadata["sha256_strict"] = self.digest(strict=True)
        text += json.dumps(self.metadata, indent=4)
        text += "\n"
        text += "#flowchart\n"
        text += json.dumps(self.to_dict(), indent=4, cls=seamm_util.JSONEncoder)
        text += "\n"
        text += "#end\n"

        return text

    def from_text(self, text):
        """Recreate the flowchart from text"""
        lines = iter(text.splitlines())

        line = next(lines)
        # There may be exec magic as first line
        if line[0:2] == "#!":
            line = next(lines)
        if line[0:7] != "!MolSSI":
            raise RuntimeError("File is not a MolSSI file! -- " + line)
        tmp = line.split()
        if len(tmp) < 3:
            raise RuntimeError("File is not a proper MolSSI file! -- " + line)
        if tmp[1] != "flowchart":
            raise RuntimeError("File is not a flowchart! -- " + line)
        flowchart_version = tmp[2]
        version = Version(flowchart_version)
        logger.info(f"Reading flowchart version {flowchart_version}")

        if version < Version("2.0"):
            self.metadata = {}
            rest = "\n".join([x for x in lines])
            data = json.loads(rest, cls=seamm_util.JSONDecoder)
        else:
            sections = {}
            in_section = False
            for line in lines:
                if line.strip() == "":
                    continue
                if line[0] == "#":
                    section = line.strip()[1:]
                    if section == "end":
                        in_section = False
                    else:
                        tmp = sections[section] = []
                        in_section = True
                    continue
                elif in_section:
                    tmp.append(line)

            self.metadata = json.loads("\n".join(sections["metadata"]))
            data = json.loads("\n".join(tmp), cls=seamm_util.JSONDecoder)

        if "class" not in data or data["class"] != "Flowchart":
            raise RuntimeError("Text does not contain a flowchart")

        self.from_dict(data)

    def read(self, filename):
        """Recreate the flowchart from the serialized form on disk"""
        with open(filename, "r") as fd:
            text = fd.read()

        self.from_text(text)

    def reset_metadata(self, **kwargs):
        """Setup the metadata initially."""
        self.metadata = {
            "title": "",
            "description": "",
            "keywords": [],
            "creators": [],
        }
        # See if the user info is in the SEAMM.ini file...
        path = Path("~/SEAMM/seamm.ini").expanduser()
        if path.exists:
            config = configparser.ConfigParser()
            config.read(path)
            if "USER" in config:
                user = config["USER"]
                if "name" in user:
                    author = {"name": user["name"]}
                    for key in ("orcid", "affiliation"):
                        if key in user:
                            author[key] = user[key]
                    self.metadata["creators"].append(author)

        self.metadata.update(kwargs)

    # -------------------------------------------------------------------------
    # Edges between nodes
    # -------------------------------------------------------------------------

    def edges(self, node=None, direction="both"):
        return self.graph.edges(node, direction)

    def add_edge(self, u, v, edge_type=None, edge_subtype="next", **attr):
        return self.graph.add_edge(u, v, edge_type, edge_subtype, **attr)

    def print_edges(self, event=None):
        """Print all the edges. Useful for debugging!"""

        print("All edges in flowchart")
        for edge in self.edges():
            # print('   {}'.format(edge))
            print(
                "   {} {} {} {} {} {}".format(
                    edge.node1.tag,
                    edge.anchor1,
                    edge.node2.tag,
                    edge.anchor2,
                    edge.edge_type,
                    edge.edge_subtype,
                )
            )

    # -------------------------------------------------------------------------
    # Printing
    # -------------------------------------------------------------------------
