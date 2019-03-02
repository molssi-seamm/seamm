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
import molssi_workflow

logger = logging.getLogger(__name__)


class ExecWorkflow(object):
    def __init__(self, flowchart=None):
        """Execute a flowchart, providing support for the actual
        execution of codes """

        self.flowchart = flowchart

    def run(self, root=None):
        if not self.flowchart:
            raise RuntimeError('There is no flowchart to run!')

        logger.debug('Creating global variables space')
        molssi_workflow.workflow_variables = molssi_workflow.Variables()
        
        self.flowchart.root_directory = root

        # Correctly number the nodes
        self.flowchart.set_ids()

        # Write out an initial summary of the flowchart before doing anything
        # Reset the visited flag for traversal
        self.flowchart.reset_visited()

        # Get the start node
        next_node = self.flowchart.get_node('1')

        # describe ourselves
        self.flowchart.job_output('\nDescription of the flowchart')
        self.flowchart.job_output('----------------------------')

        while next_node:
            next_node = next_node.describe()
        self.flowchart.job_output('')

        # And actually run it!
        self.flowchart.job_output('Running the flowchart')
        self.flowchart.job_output('---------------------')

        next_node = self.flowchart.get_node('1')
        while next_node:
            next_node = next_node.run()
