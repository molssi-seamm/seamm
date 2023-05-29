# -*- coding: utf-8 -*-

"""The ExecLocal object does what it name implies: it executes, or
runs, an executable locally."""

import humanize
import logging
import os
import os.path
from pathlib import Path
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
        in_situ=False,
        directory=None,
    ):
        """Execute 'cmd' in a temporary directory. 'files' is a dict
        keyed by filename of files to write before execution."""

        # Create temporary directory and write the files, being
        # careful about both errors and security.

        if directory is not None:
            directory = Path(directory)

        if in_situ:
            if directory is None:
                tmpdir = Path.cwd()
            else:
                tmpdir = Path(directory)
        else:
            tmpdir = Path(tempfile.mkdtemp())
            # Ensure the file is read/write by the creator only
            saved_umask = os.umask(0o077)

        logging.info(f"Running locally in {tmpdir}")

        if files is not None:
            # Write locally if directory is given
            if not in_situ and directory is not None:
                for filename in files:
                    path = directory / filename
                    mode = "wb" if type(files[filename]) is bytes else "w"
                    with path.open(mode=mode) as fd:
                        fd.write(files[filename])
            for filename in files:
                path = tmpdir / filename
                mode = "wb" if type(files[filename]) is bytes else "w"
                try:
                    with path.open(mode=mode) as fd:
                        fd.write(files[filename])
                except IOError:
                    logging.exception(
                        "An I/O error occured writing file '{}'".format(path)
                    )
                    if not in_situ:
                        os.umask(saved_umask)
                        shutil.rmtree(tmpdir)
                    return None
                except Exception:
                    logging.exception(
                        "An unexpected error occured writing file '{}'".format(path)
                    )
                    path.unlink()
                    if not in_situ:
                        os.umask(saved_umask)
                        shutil.rmtree(tmpdir)
                    return None
        # get a list of all existing files so we can determine what to delete
        if in_situ:
            existing = []
            existing_directories = []
            for dirpath, dirs, files in os.walk(tmpdir):
                dirpath = Path(dirpath)
                for name in files:
                    existing.append(dirpath / name)
                for name in dirs:
                    existing_directories.append(dirpath / name)

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

        if not in_situ:
            os.umask(saved_umask)

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
        returned = []
        for pattern in return_files:
            paths = sorted(tmpdir.glob(pattern))
            for path in paths:
                returned.append(path)
                filename = path.name
                data = None
                exception = None
                result["files"].append(filename)
                try:
                    with path.open(mode="r") as fd:
                        data = fd.read()

                except UnicodeDecodeError:
                    with path.open(mode="rb") as fd:
                        data = fd.read()

                except IOError:
                    exception = sys.exc_info()
                    logging.warning(
                        f"An I/O error occurred reading file '{filename}'",
                        exc_info=exception,
                    )
                except Exception:
                    exception = sys.exc_info()
                    logging.warning(
                        f"An unexpected error occured reading file '{filename}'",
                        exc_info=exception,
                    )
                finally:
                    result[filename] = {"exception": exception, "data": data}

        # Clean up the temporary directory
        if in_situ:
            # Remove any files not originally here, or requested to return.
            for dirpath, dirs, files in os.walk(tmpdir):
                dirpath = Path(dirpath)
                for name in files:
                    filename = dirpath / name
                    if filename not in existing and filename not in returned:
                        filename.unlink()
                for name in dirs:
                    dirname = dirpath / name
                    if dirname not in existing_directories:
                        dirname.rmdir()
            # And move any files the need to go in subdirectories
            for filename in result["files"]:
                if filename[0] == "@":
                    subdir, fname = filename[1:].split("+")
                    from_path = directory / filename
                    subdir = directory / subdir
                    subdir.mkdir(parents=True, exist_ok=True)
                    from_path.rename(subdir / fname)
        else:
            shutil.rmtree(tmpdir)

            # And write the results locally
            if directory is not None:
                for filename in result["files"]:
                    if filename[0] == "@":
                        subdir, fname = filename[1:].split("+")
                        subdir = directory / subdir
                        subdir.mkdir(parents=True, exist_ok=True)
                        path = subdir / fname
                    else:
                        path = directory / filename

                    if result[filename]["data"] is not None:
                        mode = "wb" if type(result[filename]["data"]) is bytes else "w"
                        with path.open(mode=mode) as fd:
                            fd.write(result[filename]["data"])
                    else:
                        with path.open(mode="w") as fd:
                            fd.write(result[filename]["exception"])

        # Write any stdout and stderr

        if directory is not None:
            if "stdout" in result and result["stdout"] != "":
                path = directory / "stdout.txt"
                path.write_text(result["stdout"])
            if result["stderr"] != "":
                path = directory / "stderr.txt"
                path.write_text(result["stderr"])

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
