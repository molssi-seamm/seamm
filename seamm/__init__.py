# -*- coding: utf-8 -*-

"""Top-level package for SEAMM."""

import textwrap

__author__ = """Paul Saxe"""
__email__ = 'psaxe@molssi.org'
__version__ = '0.1.0'

# Text handling
from textwrap import dedent  # noqa: F401

# Bring up the classes so that they appear to be directly in
# the seamm package.

from seamm.parameters import Parameter  # noqa: F401
from seamm.parameters import Parameters  # noqa: F401
from seamm.variables import Variables  # noqa: F401
from seamm.variables import flowchart_variables  # noqa: F401
from seamm.plugin_manager import PluginManager  # noqa: F401
from seamm.flowchart import Flowchart  # noqa: F401
from seamm.tk_flowchart import TkFlowchart  # noqa: F401
from seamm.graph import Graph  # noqa: F401
from seamm.graph import Edge  # noqa: F401
from seamm.exec_flowchart import ExecFlowchart  # noqa: F401
from seamm.node import Node  # noqa: F401
from seamm.start_node import StartNode  # noqa: F401
from seamm.tk_edge import TkEdge  # noqa: F401
from seamm.tk_node import TkNode  # noqa: F401
from seamm.tk_start_node import TkStartNode  # noqa: F401
from seamm.exec_local import ExecLocal  # noqa: F401
from seamm.split_node import Split  # noqa: F401
from seamm.tk_split_node import TkSplit  # noqa: F401
from seamm.builtins import SplitStep  # noqa: F401
from seamm.join_node import Join  # noqa: F401
from seamm.tk_join_node import TkJoin  # noqa: F401
from seamm.builtins import JoinStep  # noqa: F401

wrap_text = textwrap.TextWrapper(width=120)
wrap_stdout = textwrap.TextWrapper(width=120)