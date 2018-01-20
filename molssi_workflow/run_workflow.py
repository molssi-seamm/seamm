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

    parser.add_argument(
        "--log", default='WARNING', help='the level of logging')
    parser.add_argument("filename", help='the filename of the workflow')
    args = parser.parse_args()

    numeric_level = getattr(logging, args.log.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % args.log)
    logging.basicConfig(level=numeric_level)

    workflow = open_workflow(args.filename)
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
