# -*- coding: utf-8 -*-
"""The ExecWorkflow object does what it name implies: it executes, or
runs, a given workflow.

It provides the environment for running the computational tasks
locally or remotely, using what is commonly called workflow management
system (WMS).  The WMS concept, as used here, means tools that run
given tasks without knowing anything about chemistry. The chemistry
specialization is contained in the Workflow and the nodes that it
contains."""

import logging

logger = logging.getLogger(__name__)


class ExecWorkflow(object):
    def __init__(self, workflow=None):
        """Execute a workflow, providing support for the actual
        execution of codes """

        self._workflow = workflow

    def run(self, root=None):
        if not self._workflow:
            raise RuntimeError('There is no workflow to run!')

        self._workflow.root_directory = root

        # Correctly number the nodes
        self._workflow.set_ids()

        # Get the start node
        next_node = self._workflow.get_node('1')

        # Write out an initial summary of the workflow before doing anything
        while next_node:
            next_node = next_node.describe()

        # And actually run it!
        next_node = self._workflow.get_node('1')
        while next_node:
            next_node = next_node.run()
