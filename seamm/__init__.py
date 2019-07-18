# -*- coding: utf-8 -*-
"""Top-level package for SEAMM."""

import textwrap

__author__ = """Paul Saxe"""
__email__ = 'psaxe@molssi.org'
__version__ = '0.1.0'

# Text handling
from textwrap import dedent  # nopepe8
wrap_text = textwrap.TextWrapper(width=120)
wrap_stdout = textwrap.TextWrapper(width=120)

# Bring up the classes so that they appear to be directly in
# the seamm package.

from seamm.parameters import Parameter  # nopep8
from seamm.parameters import Parameters  # nopep8
from seamm.variables import Variables  # nopep8
from seamm.variables import flowchart_variables  # nopep8
from seamm.plugin_manager import PluginManager  # nopep8
from seamm.flowchart import Flowchart  # nopep8
from seamm.tk_flowchart import TkFlowchart  # nopep8
from seamm.graph import Graph  # nopep8
from seamm.graph import Edge  # nopep8
from seamm.exec_flowchart import ExecFlowchart  # nopep8
from seamm.node import Node  # nopep8
from seamm.start_node import StartNode  # nopep8
from seamm.tk_edge import TkEdge  # nopep8
from seamm.tk_node import TkNode  # nopep8
from seamm.tk_start_node import TkStartNode  # nopep8
from seamm.exec_local import ExecLocal  # nopep8
from seamm.split_node import Split  # nopep8
from seamm.tk_split_node import TkSplit  # nopep8
from seamm.builtins import SplitStep  # nopep8
from seamm.join_node import Join  # nopep8
from seamm.tk_join_node import TkJoin  # nopep8
from seamm.builtins import JoinStep  # nopep8
