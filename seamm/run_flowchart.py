# -*- coding: utf-8 -*-

"""Run a SEAMM flowchart.

SEAMM flowcharts have a 'magic' line, so that they can be executed directly.
Or, run_flowchart can be invoked with the name of flowchart.
"""

import configargparse
import cpuinfo
import datetime
import fasteners
import json
import locale
import logging
import seamm
import seamm_util.printing as printing
import os
import os.path
import re
import shutil
import sys
import time

logger = logging.getLogger(__name__)
variables = seamm.Variables()


class cd:
    """Context manager for changing the current working directory"""

    def __init__(self, newPath):
        self.newPath = os.path.expanduser(newPath)

    def __enter__(self):
        self.savedPath = os.getcwd()
        os.chdir(self.newPath)

    def __exit__(self, etype, value, traceback):
        os.chdir(self.savedPath)


def run(job_id=None, wdir=None, setup_logging=True):
    """The standalone flowchart app
    """

    parser = configargparse.ArgParser(
        auto_env_var_prefix='',
        default_config_files=[
            '/etc/seamm/seamm.ini',
            '~/.seamm/seamm.ini',
        ],
        description='Execute a SEAMM flowchart'
    )

    parser.add_argument(
        "--standalone",
        action='store_true',
        help="Run this workflow as-is without using the datastore, etc."
    )
    parser.add_argument(
        '--seamm-configfile',
        is_config_file=True,
        default=None,
        help='a configuration file to override others'
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose_count",
        action="count",
        default=0,
        help="increases log verbosity for each occurence."
    )
    parser.add_argument(
        "--title",
        dest="title",
        default='',
        action="store",
        env_var='SEAMM_TITLE',
        help="The title for this run."
    )
    parser.add_argument(
        "--datastore",
        dest="datastore",
        default='.',
        action="store",
        env_var='SEAMM_DATASTORE',
        help="The datastore (directory) for this run."
    )
    parser.add_argument(
        "--job-id-file",
        dest="job_id_file",
        default=None,
        action="store",
        help="The job_id file to use."
    )
    parser.add_argument(
        "--project",
        dest="projects",
        action="append",
        env_var='SEAMM_PROJECT',
        help="The project(s) for this job."
    )
    parser.add_argument("--force", dest="force", action='store_true')
    parser.add_argument(
        "--output",
        choices=['files', 'stdout', 'both'],
        default='files',
        help='whether to put the output in files, direct to stdout, or both'
    )
    parser.add_argument(
        "filename",
        nargs='?',
        help='the filename of the flowchart'
    )  # yapf: disable

    args, unknown = parser.parse_known_args()

    # Whether to just run as-is, without getting a job_id, using the
    # datastore, etc.
    standalone = 'standalone' in args and args.standalone

    if setup_logging:
        # Set up logging level to WARNING by default, going more verbose
        # for each new -v, to INFO and then DEBUG and finally ALL with 3 -v's

        numeric_level = max(3 - args.verbose_count, 0) * 10
        logging.basicConfig(level=numeric_level)

    # Create the working directory where files, output, etc. go.
    # At the moment this is datastore/job_id

    if standalone:
        print('Running in standalone mode.')
        wdir = os.getcwd()
    else:
        datastore = os.path.expanduser(args.datastore)

        if job_id is None:
            if args.job_id_file is None:
                job_id_file = os.path.join(datastore, 'job.id')

            # Get the job_id from the file, creating the file if necessary
            job_id = get_job_id(job_id_file)
        if wdir is None:
            if args.projects is None:
                projects = ['default']
            else:
                projects = args.projects

            # And put it all together
            wdir = os.path.abspath(
                os.path.join(
                    datastore, 'projects', projects[0],
                    'Job_{:06d}'.format(job_id)
                )
            )

            if os.path.exists(wdir):
                if args.force:
                    shutil.rmtree(wdir)
                else:
                    msg = "Directory '{}' exists, use --force to overwrite"\
                          .format(wdir)

                    logging.critical(msg)
                    sys.exit(msg)

            os.makedirs(wdir, exist_ok=False)

    logging.info("The working directory is '{}'".format(wdir))

    # Set up the root printer, and add handlers to print to the file
    # 'job.out' in the working directory and to stdout, as requested
    # in the options. Since all printers are children of the root
    # printer, all output at the right levels will flow here

    printer = printing.getPrinter()

    # Set up our formatter
    formatter = logging.Formatter(fmt='{message:s}', style='{')

    # A handler for stdout
    if standalone or wdir is None:
        console_handler = logging.StreamHandler()
        # console_handler.setLevel(printing.JOB)
        console_handler.setLevel(printing.NORMAL)
        console_handler.setFormatter(formatter)
        printer.addHandler(console_handler)

    # A handler for the file
    file_handler = logging.FileHandler(os.path.join(wdir, 'job.out'))
    file_handler.setLevel(printing.NORMAL)
    file_handler.setFormatter(formatter)
    printer.addHandler(file_handler)

    # And ... finally ... run!
    printer.job("Running in directory '{}'".format(wdir))

    flowchart_path = os.path.join(wdir, 'flowchart.flow')
    if args.filename is not None:
        # copy the flowchart to the root directory for later reference
        shutil.copy2(args.filename, flowchart_path)

    flowchart = seamm.Flowchart(directory=wdir, output=args.output)
    flowchart.read(flowchart_path)

    # Change to the working directory and run the flowchart
    with cd(wdir):
        if os.path.exists('job_data.json'):
            with open('job_data.json', 'r') as fd:
                data = json.load(fd)
        else:
            data = {}

        # Set up the initial metadata for the job.
        data.update(cpuinfo.get_cpu_info())
        if 'command line' not in data:
            data['command line'] = sys.argv
        if 'title' not in data:
            data['title'] = args.title
        data['working directory'] = wdir
        data['start time'] = time.strftime("%Y-%m-%d %H:%M:%S %Z")
        data['state'] = 'started'
        if not standalone:
            if 'projects' not in data:
                data['projects'] = projects
            data['datastore'] = datastore
            data['job id'] = job_id

        # Output the initial metadate for the job.
        with open('job_data.json', 'w') as fd:
            json.dump(data, fd, indent=3, sort_keys=True)

        t0 = time.time()
        pt0 = time.process_time()

        # And run the flowchart
        try:
            exec = seamm.ExecFlowchart(flowchart)
            exec.run(root=wdir)
            data['state'] = 'finished'
        except Exception as e:
            data['state'] = 'error'
            data['error type'] = type(e).__name__
            data['error message'] = str(e)

        # Wrap things up
        t1 = time.time()
        pt1 = time.process_time()
        data['end time'] = time.strftime("%Y-%m-%d %H:%M:%S %Z")
        t = t1 - t0
        pt = pt1 - pt0
        data['elapsed time'] = t
        data['process time'] = pt

        with open('job_data.json', 'w') as fd:
            json.dump(data, fd, indent=3, sort_keys=True)

        printer.job(
            "\nProcess time: {} ({:.3f} s)".format(
                datetime.timedelta(seconds=pt), pt
            )
        )
        printer.job(
            "Elapsed time: {} ({:.3f} s)".format(
                datetime.timedelta(seconds=t), t
            )
        )


def get_job_id(filename):
    """Get the next job id from the given file.

    This uses the fasteners module to provide locking so that
    only one job at a time can access the file, so that the job
    ids are unique and monotonically increasing.
    """

    lock_file = filename + '.lock'
    lock = fasteners.InterProcessLock(lock_file)
    locked = lock.acquire(blocking=True, timeout=5)

    if locked:
        if not os.path.isfile(filename):
            job_id = 1
            with open(filename, 'w') as fd:
                fd.write('!MolSSI job_id 1.0\n')
                fd.write('1\n')
            lock.release()
        else:
            with open(filename, 'r+') as fd:
                line = fd.readline()
                pos = fd.tell()
                if line == '':
                    lock.release()
                    raise EOFError(
                        "job_id file '{}' is empty".format(filename)
                    )
                line = line.strip()
                match = re.fullmatch(
                    r'!MolSSI job_id ([0-9]+(?:\.[0-9]+)*)', line
                )
                if match is None:
                    lock.release()
                    raise RuntimeError(
                        'The job_id file has an incorrect header: {}'
                        .format(line)
                    )
                line = fd.readline()
                if line == '':
                    lock.release()
                    raise EOFError(
                        "job_id file '{}' is truncated".format(filename)
                    )
                try:
                    job_id = int(line)
                except TypeError:
                    raise TypeError(
                        "The job_id in file '{}' is not an integer: {}".format(
                            filename, line
                        )
                    )
                job_id += 1
                fd.seek(pos)
                fd.write('{:d}\n'.format(job_id))
    else:
        raise RuntimeError(
            "Could not lock the job_id file '{}'".format(filename)
        )

    return job_id


if __name__ == "__main__":
    locale.setlocale(locale.LC_ALL, '')
    run()
