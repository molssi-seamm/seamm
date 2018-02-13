import argparse
import molssi_workflow
import json
import locale
import logging
import molssi_util

logger = logging.getLogger(__name__)


def run():
    """The standalone flowchart app
    """

    parser = argparse.ArgumentParser(description='Execute a MolSSI workflow')

    parser.add_argument("-v", "--verbose", dest="verbose_count",
                        action="count", default=0,
                        help="increases log verbosity for each occurence.")
    parser.add_argument("filename", help='the filename of the workflow')
    args = parser.parse_args()

    # Sets log level to WARN going more verbose for each new -v.
    numeric_level = max(3 - args.verbose_count, 0) * 10
    logging.basicConfig(level=numeric_level)

    workflow = molssi_workflow.Workflow()
    workflow.read(args.filename)
    exec = molssi_workflow.ExecWorkflow(workflow)
    exec.run()


def open_workflow(name):
    with open(name, 'r') as fd:
        line = fd.readline(256)
        # There may be exec magic as first line
        if line[0:2] == '#!':
            line = fd.readline(256)
        if line[0:7] != '!MolSSI':
            raise RuntimeError('File is not a MolSSI file! -- ' + line)
        tmp = line.split()
        if len(tmp) < 3:
            raise RuntimeError(
                'File is not a proper MolSSI file! -- ' + line)
        if tmp[1] != 'workflow':
            raise RuntimeError('File is not a workflow! -- ' + line)
        workflow_version = tmp[2]
        logger.info('Reading workflow version {} from file {}'.format(
            workflow_version, name))

        data = json.load(fd, cls=molssi_util.JSONDecoder)

    if data['class'] != 'Workflow':
        raise RuntimeError('File {} does not contain a workflow!'.format(name))
        return

    # Restore the workflow
    workflow = molssi_workflow.Workflow()
    workflow.from_dict(data)

    return workflow


if __name__ == "__main__":
    locale.setlocale(locale.LC_ALL, '')
    run()
