from datetime import datetime
import argparse
import json
import locale
import logging
import molssi_util
import molssi_workflow
import os
import os.path
import shutil

logger = logging.getLogger(__name__)
variables = molssi_workflow.Variables()


def run():
    """The standalone flowchart app
    """

    parser = argparse.ArgumentParser(description='Execute a MolSSI workflow')

    parser.add_argument("-v", "--verbose", dest="verbose_count",
                        action="count", default=0,
                        help="increases log verbosity for each occurence.")
    parser.add_argument("--directory", dest="directory",
                        default=None, action="store",
                        help="Directory to write output and other files.")
    parser.add_argument("--force", dest="force", action='store_true')
    parser.add_argument("filename", help='the filename of the workflow')
    args = parser.parse_args()

    if args.directory is None:
        wdir = os.path.join(
            os.getcwd(),
            datetime.now().isoformat(sep='_', timespec='seconds')
        )
    else:
        wdir = args.directory
    print("Working directory is '{}'".format(wdir))

    if os.path.exists(wdir):
        if args.force:
            shutil.rmtree(wdir)
        else:
            print('Directory {} exists, us --force to overwrite'.format(wdir))
            exit()

    # Sets log level to WARN going more verbose for each new -v.
    numeric_level = max(3 - args.verbose_count, 0) * 10
    logging.basicConfig(level=numeric_level)

    workflow = molssi_workflow.Workflow()
    workflow.read(args.filename)
    exec = molssi_workflow.ExecWorkflow(workflow)
    exec.run(root=wdir)


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
