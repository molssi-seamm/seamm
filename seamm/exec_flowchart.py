# -*- coding: utf-8 -*-

"""The ExecWorkflow object does what it name implies: it executes, or
runs, a given flowchart.

It provides the environment for running the computational tasks
locally or remotely, using what is commonly called workflow management
system (WMS).  The WMS concept, as used here, means tools that run
given tasks without knowing anything about chemistry. The chemistry
specialization is contained in the Flowchart and the nodes that it
contains."""

import logging
import os.path
import sys
import traceback

import reference_handler
import seamm
from seamm_util import to_mmcif, to_cif
import seamm_util.printing as printing
from seamm_util.printing import FormattedText as __  # noqa: F401

logger = logging.getLogger(__name__)
job = printing.getPrinter()


class ExecFlowchart(object):

    def __init__(self, flowchart=None):
        """Execute a flowchart, providing support for the actual
        execution of codes """

        self.flowchart = flowchart

    def run(self, root=None):
        if not self.flowchart:
            raise RuntimeError('There is no flowchart to run!')

        logger.debug('Creating global variables space')
        seamm.flowchart_variables = seamm.Variables()

        self.flowchart.root_directory = root

        # Correctly number the nodes
        self.flowchart.set_ids()

        # Write out an initial summary of the flowchart before doing anything
        # Reset the visited flag for traversal
        self.flowchart.reset_visited()

        # Get the start node
        next_node = self.flowchart.get_node('1')

        # describe ourselves
        job.job(
            (
                '\nDescription of the flowchart'
                '\n----------------------------'
            )
        )

        while next_node:
            try:
                next_node = next_node.describe()
            except Exception:
                message = (
                    'Error describing the flowchart\n\n' +
                    traceback.format_exc()
                )
                print(message)
                logger.critical(message)
                raise
            except:  # noqa: E722
                message = (
                    'Unexpected error describing the flowchart\n\n' +
                    traceback.format_exc()
                )
                print(message)
                logger.critical(message)
                raise

        job.job('')

        # And actually run it!
        job.job(('Running the flowchart\n' '---------------------'))

        next_node = self.flowchart.get_node('1')
        while next_node is not None:
            try:
                next_node = next_node.run()
            except DeprecationWarning as e:
                print('\nDeprecation warning: ' + str(e))
                traceback.print_exc(file=sys.stderr)
                traceback.print_exc(file=sys.stdout)
            except Exception:
                message = (
                    'Error running the flowchart\n\n' + traceback.format_exc()
                )
                print(message)
                logger.critical(message)
                break
            except:  # noqa: E722
                message = (
                    'Unexpected error running the flowchart\n\n' +
                    traceback.format_exc()
                )
                print(message)
                logger.critical(message)
                raise

        # Write the final structure
        if seamm.data.structure is not None:
            system = seamm.data.structure
            # MMCIF file has bonds
            filename = os.path.join(
                self.flowchart.root_directory, 'final_structure.mmcif'
            )
            with open(filename, 'w') as fd:
                print(to_mmcif(system), file=fd)
            job.job(
                "\nWrote the final structure to 'final_structure.mmcif' for "
                'viewing.'
            )
            # CIF file has cell
            if system['periodicity'] == 3:
                filename = os.path.join(
                    self.flowchart.root_directory, 'final_structure.cif'
                )
                with open(filename, 'w') as fd:
                    print(to_cif(seamm.data.structure), file=fd)
                job.job(
                    "\nWrote the final structure to 'final_structure.cif' for "
                    'viewing.'
                )

        # And print out the references
        filename = os.path.join(self.flowchart.root_directory, 'references.db')
        try:
            references = reference_handler.Reference_Handler(filename)
        except Exception as e:
            job.job('Error with references:')
            job.job(e)

        if references.total_citations() > 0:
            tmp = {}
            citations = references.dump(fmt='text')
            for citation, text, count, level in citations:
                if level not in tmp:
                    tmp[level] = {}
                tmp[level][citation] = (text, count)

            for level in sorted(tmp.keys()):
                ref_dict = tmp[level]
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
                        lines.append('({}) {:s}'.format(citation, text))
                    else:
                        lines.append(
                            '({}) {:s} (used {:d} times)'.format(
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
