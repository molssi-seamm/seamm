# -*- coding: utf-8 -*-
"""Top-level package for MolSSI Workflow."""

import pint

__author__ = """Paul Saxe"""
__email__ = 'psaxe@molssi.org'
__version__ = '0.1.0'

# Unit handling!
units = pint.UnitRegistry(auto_reduce_dimensions=True)
pint.set_application_registry(units)
Q_ = units.Quantity
units_class = units('1 km').__class__

_d = pint.Context('chemistry')
_d.add_transformation('[mass]/[substance]', '[mass]',
                      lambda units, x: x / units.avogadro_number)
units.add_context(_d)
units.enable_contexts('chemistry')

# Bring up the classes so that they appear to be directly in
# the molssi_workflow package.

from molssi_workflow.plugin_manager import PluginManager  # nopep8
from molssi_workflow.workflow import Workflow  # nopep8
from molssi_workflow.tk_workflow import TkWorkflow  # nopep8
from molssi_workflow.graph import Graph  # nopep8
from molssi_workflow.exec_workflow import ExecWorkflow  # nopep8
from molssi_workflow.node import Node  # nopep8
from molssi_workflow.start_node import StartNode  # nopep8
from molssi_workflow.tk_edge import TkEdge  # nopep8
from molssi_workflow.tk_node import TkNode  # nopep8
from molssi_workflow.tk_start_node import TkStartNode  # nopep8
from molssi_workflow.exec_local import ExecLocal  # nopep8
