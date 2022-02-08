# -*- coding: utf-8 -*-

"""Run a SEAMM flowchart.

SEAMM flowcharts have a 'magic' line, so that they can be executed directly.
Or, run_flowchart can be invoked with the name of flowchart.
"""

import argparse
import configparser
import datetime
import fasteners
import json
import locale
import logging
import os
import os.path
from pathlib import Path
import platform
import re
import shutil
import sys
import textwrap
import time
import uuid

import cpuinfo

import seamm
import seamm_datastore
import seamm_util

printer = seamm_util.printing.getPrinter()

logging.basicConfig(level="WARNING")
logger = logging.getLogger(__name__)
variables = seamm.Variables()
header_line = "!MolSSI job_data 1.0\n"


class cd:
    """Context manager for changing the current working directory"""

    def __init__(self, newPath):
        self.newPath = os.path.expanduser(newPath)

    def __enter__(self):
        self.savedPath = os.getcwd()
        os.chdir(self.newPath)

    def __exit__(self, etype, value, traceback):
        os.chdir(self.savedPath)


def run(job_id=None, wdir=None, setup_logging=True, in_jobserver=False, cmdline=None):
    """The standalone flowchart app"""
    global print

    if not in_jobserver and len(sys.argv) > 1:
        if sys.argv[1] == "--help" or sys.argv[1] == "-h":
            # Running run_flowchart by hand ...
            print("usage: run_flowchart <flowchart> [options]")
            print("")
            print("usually it is simpler to execute the flowchart file itself")
            exit()

        # Slice off 'run_flowchart' from the arguments, leaving the
        # flowchart as the thing being run.
        sys.argv = sys.argv[1:]

        filename = sys.argv[0]
    else:
        if wdir is None:
            filename = "flowchart.flow"
        else:
            filename = os.path.join(wdir, "flowchart.flow")

    if cmdline is None:
        cmdline = sys.argv[1:]

    # Set up the argument parser for this node.
    parser = seamm_util.seamm_parser()

    parser.epilog = textwrap.dedent(
        """
        The plug-ins in this flowchart are listed above.
        Options, if any, for plug-ins are placed after
        the name of the plug-in, e.g.:

           test.flow lammps-step --log-level DEBUG --np 4

        To get help for a plug-in, use --help or -h after the
        plug-in name. E.g.

           test.flow lammps-step --help
        """
    )
    parser.usage = "%(prog)s [options] plug-in [options] plug-in [options] ..."

    # Now we need to get the flowchart so that we can set up all the
    # parsers for the steps in order to provide appropriate help.
    if not os.path.exists(filename):
        raise FileNotFoundError(f"The flowchart '{filename}' does not exist.")

    logger.info(f"    reading in flowchart '{filename}'")
    flowchart = seamm.Flowchart()
    flowchart.read(filename)
    logger.info("   finished reading the flowchart")

    # Now traverse the flowchart, setting up the ids and parsers
    flowchart.set_ids()
    flowchart.create_parsers()

    # And handle the command-line arguments and ini file options.
    parser.parse_args(cmdline)
    logger.info("Parsed the command-line arguments")
    options = parser.get_options("SEAMM")

    # Whether to just run as-is, without getting a job_id, using the
    # datastore, etc.
    standalone = options["standalone"] or options["projects"] is None

    # Setup the logging
    if setup_logging:
        if "log_level" in options:
            logging.basicConfig(level=options["log_level"])

        # Set the log level for the plug-ins
        flowchart.set_log_level(parser.get_options())

    # Create the working directory where files, output, etc. go.
    # At the moment this is datastore/job_id

    if standalone:
        print("Running in standalone mode.")
        if wdir is None:
            wdir = os.getcwd()
    else:
        datastore = os.path.expanduser(options["datastore"])

        if job_id is None:
            if options["job_id_file"] is None:
                job_id_file = os.path.join(datastore, "job.id")
            else:
                job_id_file = options["job_id_file"]

            # Get the job_id from the file, creating the file if necessary
            job_id = get_job_id(job_id_file)
        if options["projects"] is None:
            projects = ["default"]
        else:
            projects = options["projects"]
        if wdir is None:
            # And put it all together
            wdir = os.path.abspath(
                os.path.join(
                    datastore, "projects", projects[0], "Job_{:06d}".format(job_id)
                )
            )

            if os.path.exists(wdir):
                if options["force"]:
                    shutil.rmtree(wdir)
                else:
                    msg = "Directory '{}' exists, use --force to overwrite".format(wdir)

                    logging.critical(msg)
                    sys.exit(msg)

            os.makedirs(wdir, exist_ok=False)

    logging.info("The working directory is '{}'".format(wdir))

    # Set up the root printer, and add handlers to print to the file
    # 'job.out' in the working directory and to stdout, as requested
    # in the options. Since all printers are children of the root
    # printer, all output at the right levels will flow here

    # Set up our formatter
    formatter = logging.Formatter(fmt="{message:s}", style="{")

    # A handler for stdout
    if not in_jobserver:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(seamm_util.printing.NORMAL)
        console_handler.setFormatter(formatter)
        printer.addHandler(console_handler)

    # A handler for the file
    file_handler = logging.FileHandler(os.path.join(wdir, "job.out"))
    file_handler.setLevel(seamm_util.printing.NORMAL)
    file_handler.setFormatter(formatter)
    printer.addHandler(file_handler)

    # And ... finally ... run!
    printer.job("Running in directory '{}'".format(wdir))

    flowchart_path = os.path.join(wdir, "flowchart.flow")

    # copy the flowchart to the root directory for later reference
    if not in_jobserver:
        shutil.copy2(sys.argv[0], flowchart_path)

    logger.info(f"    reading in flowchart '{flowchart_path}' -- 2")
    flowchart = seamm.Flowchart(directory=wdir)
    flowchart.read(flowchart_path)
    logger.info("   finished reading the flowchart -- 2")

    # Change to the working directory and run the flowchart
    with cd(wdir):
        # Set up the initial metadata for the job.
        time_now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if in_jobserver:
            with open("job_data.json", "r") as fd:
                fd.readline()
                data = json.load(fd)
        else:
            data = {
                "data_version": "1.0",
                "title": options["title"],
                "working directory": wdir,
                "submitted time": time_now,
            }
        data.update(
            {
                "command line": cmdline,
                "flowchart_digest": flowchart.digest(),
                "flowchart_digest_strict": flowchart.digest(strict=True),
                "start time": time_now,
                "state": "started",
                "uuid": uuid.uuid4().hex,
                "~cpuinfo": cpuinfo.get_cpu_info(),
            }
        )
        if not in_jobserver and not standalone:
            current_time = datetime.datetime.now(datetime.timezone.utc)
            if "projects" not in data:
                data["projects"] = projects
            data["datastore"] = datastore
            data["job id"] = job_id

            # Add to the database
            db_path = Path(datastore).expanduser().resolve() / "seamm.db"
            db_uri = "sqlite:///" + str(db_path)
            db = seamm_datastore.connect(
                database_uri=db_uri,
                datastore_location=datastore,
            )

            # Get the user information for the datastore
            path = Path("~/.seammrc").expanduser()
            if not path.exists:
                raise RuntimeError(
                    "You need a '~/.seammrc' file to run jobs from the commandline. "
                    "See the documentation for more details."
                )

            config = configparser.ConfigParser()
            config.read(path)

            user = None
            password = None

            for section in [platform.node(), "localhost"]:
                if section in config:
                    if user is None and "user" in config[section]:
                        user = config[section]["user"]
                    if password is None and "password" in config[section]:
                        password = config[section]["password"]

            if user is None or password is None:
                raise RuntimeError(
                    "You need credentials in '~/.seammrc' file to run jobs from the "
                    "commandline. See the documentation for more details."
                )

            db.login(user, password)
            db.add_job(
                job_id,
                flowchart_filename=flowchart_path,
                project_names=data["projects"],
                path=wdir,
                title=data["title"],
                submitted=current_time,
                started=current_time,
                description="Run from the command-line.",
                status="started",
            )
            del db

        # Output the initial metadate for the job.
        with open("job_data.json", "w") as fd:
            fd.write(header_line)
            json.dump(data, fd, indent=3, sort_keys=True)
            fd.write("\n")

        t0 = time.time()
        pt0 = time.process_time()

        # And run the flowchart
        logger.info("Executing the flowchart")
        try:
            exec = seamm.ExecFlowchart(flowchart)
            exec.run(root=wdir)
            data["state"] = "finished"
        except Exception as e:
            data["state"] = "error"
            data["error type"] = type(e).__name__
            data["error message"] = str(e)
            raise
        finally:
            # Wrap things up
            t1 = time.time()
            pt1 = time.process_time()
            data["end time"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            t = t1 - t0
            pt = pt1 - pt0
            data["elapsed time"] = t
            data["process time"] = pt

            with open("job_data.json", "w") as fd:
                fd.write(header_line)
                json.dump(data, fd, indent=3, sort_keys=True)
                fd.write("\n")

            printer.job(
                f"\nProcess time: {datetime.timedelta(seconds=pt)} ({pt:.3f} s)"
            )
            printer.job(f"Elapsed time: {datetime.timedelta(seconds=t)} ({t:.3f} s)")

            if not in_jobserver and not standalone:
                # Let the datastore know that the job finished.
                current_time = datetime.datetime.now(datetime.timezone.utc)

                # Add to the database
                db = seamm_datastore.connect(
                    database_uri=db_uri,
                    datastore_location=datastore,
                )
                db.login(user, password)
                db.finish_job(job_id, current_time, data["state"])
                del db


def get_job_id(filename):
    """Get the next job id from the given file.

    This uses the fasteners module to provide locking so that
    only one job at a time can access the file, so that the job
    ids are unique and monotonically increasing.
    """

    filename = os.path.expanduser(filename)

    lock_file = filename + ".lock"
    lock = fasteners.InterProcessLock(lock_file)
    locked = lock.acquire(blocking=True, timeout=5)

    if locked:
        if not os.path.isfile(filename):
            job_id = 1
            with open(filename, "w") as fd:
                fd.write("!MolSSI job_id 1.0\n")
                fd.write("1\n")
            lock.release()
        else:
            with open(filename, "r+") as fd:
                line = fd.readline()
                pos = fd.tell()
                if line == "":
                    lock.release()
                    raise EOFError("job_id file '{}' is empty".format(filename))
                line = line.strip()
                match = re.fullmatch(r"!MolSSI job_id ([0-9]+(?:\.[0-9]+)*)", line)
                if match is None:
                    lock.release()
                    raise RuntimeError(
                        "The job_id file has an incorrect header: {}".format(line)
                    )
                line = fd.readline()
                if line == "":
                    lock.release()
                    raise EOFError("job_id file '{}' is truncated".format(filename))
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
                fd.write("{:d}\n".format(job_id))
    else:
        raise RuntimeError("Could not lock the job_id file '{}'".format(filename))

    return job_id


def setup_argument_parser():
    """Setup the command-line argument parser.

    Returns
    -------
    ArgumentParser
        The seamm_util.ArgumentParser for handling commandline and
        config-file parsing.
    """
    parser = seamm_util.getParser(name="SEAMM")

    parser.add_parser(
        "SEAMM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        prog=sys.argv[0],
        usage="%(prog)s [options] plug-in [options] plug-in [options] ...",
        epilog=textwrap.dedent(
            """
            The plug-ins in this flowchart are listed above.
            Options, if any, for plug-ins are placed after
            the name of the plug-in, e.g.:

               test.flow lammps-step --log-level DEBUG --np 4

            To get help for a plug-in, use --help or -h after the
            plug-in name. E.g.

               test.flow lammps-step --help
            """
        ),
    )

    # Debugging options
    parser.add_argument_group(
        "SEAMM",
        "debugging options",
        "Options for turning on debugging output and tools",
    )

    parser.add_argument(
        "SEAMM",
        "--log-level",
        group="debugging options",
        default="WARNING",
        type=str.upper,
        choices=["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help=("The level of informational output, defaults to " "'%(default)s'"),
    )

    # Datastore options
    parser.add_argument_group(
        "SEAMM", "datastore options", "Options controlling the use of the datastore"
    )

    parser.add_argument(
        "SEAMM",
        "--standalone",
        group="datastore options",
        action="store_true",
        help="Run this workflow as-is without using the datastore, etc.",
    )
    parser.add_argument(
        "SEAMM",
        "--datastore",
        group="datastore options",
        dest="datastore",
        default=".",
        action="store",
        help="The datastore (directory) for this run.",
    )
    parser.add_argument(
        "SEAMM",
        "--title",
        group="datastore options",
        dest="title",
        default="",
        action="store",
        help="The title for this run.",
    )
    parser.add_argument(
        "SEAMM",
        "--job-id-file",
        group="datastore options",
        dest="job_id_file",
        default=None,
        action="store",
        help="The job_id file to use.",
    )
    parser.add_argument(
        "SEAMM",
        "--project",
        group="datastore options",
        dest="projects",
        action="append",
        help="The project(s) for this job.",
    )
    parser.add_argument(
        "SEAMM", "--force", group="datastore options", dest="force", action="store_true"
    )

    # Datastore options
    parser.add_argument_group(
        "SEAMM",
        "hardware options",
        (
            "Options about memory limits, parallelism and other details "
            "connected with hardware."
        ),
    )

    parser.add_argument(
        "SEAMM",
        "--parallelism",
        group="hardware options",
        default="any",
        choices=["none", "mpi", "openmp", "any"],
        help="Whether to limit parallel usage to certain types.",
    )

    parser.add_argument(
        "SEAMM",
        "--ncores",
        group="hardware options",
        default="available",
        help=(
            "The maximum number of cores/threads to use in any step. "
            "Default: all available cores."
        ),
    )

    parser.add_argument(
        "SEAMM",
        "--memory",
        group="hardware options",
        default="available",
        help=(
            "The maximum amount of memory to use in any step, which can be "
            "'all' or 'available', or a number, which may use k, Ki, "
            "M, Mi, etc. suffixes. Default: available."
        ),
    )

    return parser


if __name__ == "__main__":
    locale.setlocale(locale.LC_ALL, "")
    run()
