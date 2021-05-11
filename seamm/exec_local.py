# -*- coding: utf-8 -*-

"""The ExecLocal object does what it name implies: it executes, or
runs, an executable locally."""

import glob
import humanize
import logging
import os
import os.path
import platform
import pprint
import pyuca
import shutil
import stat
import subprocess
import sys
import tempfile
import time

if platform.system() != "Windows":
    import grp
    import pwd

logger = logging.getLogger(__name__)


class ExecLocal(object):
    def __init__(self):
        """Execute a flowchart, providing support for the actual
        execution of codes"""

        # times for formating 'ls' like output
        self.now = int(time.time())
        self.recent = self.now - (6 * 30 * 24 * 60 * 60)  # 6 months ago

    def run(
        self,
        cmd=[],
        input_data=None,
        files=None,
        env={},
        return_files=[],
        shell=False,
    ):
        """Execute 'cmd' in a temporary directory. 'files' is a dict
        keyed by filename of files to write before execution."""

        # Create temporary directory and write the files, being
        # careful about both errors and security.

        tmpdir = tempfile.mkdtemp()
        # Ensure the file is read/write by the creator only
        saved_umask = os.umask(0o077)
        logging.info("Runnning locally in {}".format(tmpdir))

        if files is not None:
            for filename in files:
                path = os.path.join(tmpdir, filename)
                mode = "wb" if type(files[filename]) is bytes else "w"
                try:
                    with open(path, mode) as fd:
                        fd.write(files[filename])
                except IOError:
                    logging.exception(
                        "An I/O error occured writing file '{}'".format(path)
                    )
                    os.umask(saved_umask)
                    shutil.rmtree(tmpdir)
                    return None
                except Exception:
                    logging.exception(
                        "An unexpected error occured writing file '{}'".format(path)
                    )
                    os.remove(path)
                    os.umask(saved_umask)
                    shutil.rmtree(tmpdir)
                    return None

        os.umask(saved_umask)

        # Now execute the program in the temp directory
        logger.debug("about to run " + " ".join(cmd))

        p = subprocess.run(
            cmd,
            input=input_data,
            env=dict(os.environ, **env),
            cwd=tmpdir,
            universal_newlines=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=shell,
        )

        logger.debug("\n" + pprint.pformat(p))

        # capture the return code and output
        result = {
            "returncode": p.returncode,
            "stdout": p.stdout,
            "stderr": p.stderr,
        }

        # capture the list of files in the directory
        c = pyuca.Collator()
        listing = ""
        self.now = int(time.time())
        self.recent = self.now - (6 * 30 * 24 * 60 * 60)  # 6 months ago
        for dirpath, dirs, files in os.walk(tmpdir):
            # Do locale sensitive sort of files to list
            listing += (
                dirpath
                + "\n"
                + "\n\t".join(self.ls_format(dirpath, sorted(files, key=c.sort_key)))
            )
        result["listing"] = listing

        # capture the requested files
        result["files"] = []
        for pattern in return_files:
            filenames = glob.glob(os.path.join(tmpdir, pattern))
            for path in filenames:
                filename = os.path.basename(path)
                data = None
                exception = None
                result["files"].append(filename)
                try:
                    with open(path, "r") as fd:
                        data = fd.read()

                except UnicodeDecodeError:
                    with open(path, "rb") as fd:
                        data = fd.read()

                except IOError:
                    exception = sys.exc_info()
                    logging.warning(
                        "An I/O error occured reading file '{}'".format(filename),
                        exc_info=exception,
                    )
                except Exception:
                    exception = sys.exc_info()
                    logging.warning(
                        "An unexpected error occured reading file '{}'".format(
                            filename
                        ),
                        exc_info=exception,
                    )
                finally:
                    result[filename] = {"exception": exception, "data": data}

        # Clean up the temporary directory
        shutil.rmtree(tmpdir)

        return result

    def get_mode_info(self, filename, mode):
        """Get the mode information for 'ls' like listing"""

        perms = "-"
        link = ""

        if stat.S_ISDIR(mode):
            perms = "d"
        elif stat.S_ISLNK(mode):
            perms = "l"
            link = os.readlink(filename)
        mode = stat.S_IMODE(mode)
        for who in "USR", "GRP", "OTH":
            for what in "R", "W", "X":
                # lookup attributes at runtime using getattr
                if mode & getattr(stat, "S_I" + what + who):
                    perms = perms + what.lower()
                else:
                    perms = perms + "-"
        # return multiple bits of info in a tuple
        return (perms, link)

    def ls_format(self, path, files):
        """Format a list of files as in 'ls'"""

        result = []
        for filename in files:
            try:  # exceptions
                # Get all the file info
                stat_info = os.lstat(os.path.join(path, filename))
            except Exception:
                result.append("{}: No such file or directory".format(filename))
                continue

            perms, link = self.get_mode_info(
                os.path.join(path, filename), stat_info.st_mode
            )

            nlink = "%4d" % stat_info.st_nlink  # formatting strings

            if platform.system() == "Windows":
                name = 8 * " "
                group = 8 * " "
            else:
                try:
                    name = "%-8s" % pwd.getpwuid(stat_info.st_uid)[0]
                except KeyError:
                    name = "%-8s" % stat_info.st_uid

                try:
                    group = "%-8s" % grp.getgrgid(stat_info.st_gid)[0]
                except KeyError:
                    group = "%-8s" % stat_info.st_gid

            size = humanize.naturalsize(stat_info.st_size)

            # Get time stamp of file
            ts = stat_info.st_mtime
            if (ts < self.recent) or (ts > self.now):  # boolean operators
                time_fmt = "%b %e  %Y"
            else:
                time_fmt = "%b %e %R"
            time_str = time.strftime(time_fmt, time.gmtime(ts))

            # Format the result
            tmp = "{} {} {} {} {} {} {}".format(
                perms, nlink, name, group, size, time_str, filename
            )

            if link:
                tmp += " -> " + link

            result.append(tmp)

        return result
