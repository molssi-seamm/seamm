# -*- coding: utf-8 -*-

"""A singleton to ensure the ~.seammrc file is always up-to-date."""

import configparser
import os
from pathlib import Path
import tempfile
import threading

# Used in parser getters to indicate the default behaviour when a specific
# option is not found it to raise an exception. Created to enable `None' as
# a valid fallback value.
_UNSET = object()


# Reading and writing the file, from any thread. Every new Flowchart creates a SEAMMrc,
# and each one re-runs __init__, so threads did so at the same time: one could find
# the configuration another had just emptied to re-read it, and save that over the
# file, losing every dashboard and token in it.
_lock = threading.RLock()


class Singleton(object):
    _instances = {}

    def __new__(class_, *args, **kwargs):
        with _lock:
            if class_ not in class_._instances:
                class_._instances[class_] = super(Singleton, class_).__new__(class_)
            return class_._instances[class_]


class SEAMMrc(Singleton):
    def __init__(self, path="~/.seamm.d/seammrc"):
        with _lock:
            self._init(Path(path).expanduser())

    def _init(self, path):
        # Read into a new parser, and only then use it, so that no other thread ever
        # sees an empty configuration.
        config = configparser.ConfigParser()
        created = False
        if path.exists():
            config.read(path)
        else:
            # Initially used ~/.seammrc but this doesn't play well with Docker
            # containers, so moved to ~/seamm.d/seammrc Check for the old file and move
            # to new
            tmp = Path("~/.seammrc").expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            if tmp.exists():
                path.write_text(tmp.read_text())
                config.read(path)
                tmp.unlink()
            else:
                created = True
        self.path = path
        self._config = config

        # Check the version and upgrade if necessary. A file that exists but reads as
        # empty is left alone: another program may be writing it.
        if "VERSION" not in config and (created or len(config.sections()) > 0):
            # Rename all sections as Dashboards
            for section in config.sections():
                tmp = {}
                for key, value in config[section].items():
                    tmp[key] = value
                config.remove_section(section)
                config[f"Dashboard: {section}"] = tmp
            config["VERSION"] = {"file": "1.0"}
            self._save()

    def __getitem__(self, key):
        raise NotImplementedError("Please use get/set")

    def __setitem__(self, key, value):
        raise NotImplementedError("Please use get/set")

    def __delitem__(self, key):
        with _lock:
            del self._config[key]
            self._save()

    def __contains__(self, key):
        return key in self._config

    def __len__(self):
        return len(self._config)

    def __iter__(self):
        return self._config.__iter__()

    def defaults(self):
        return self._config.defaults()

    def sections(self):
        return self._config.sections()

    def add_section(self, section):
        with _lock:
            self._config.add_section(section)
            self._save()

    def has_section(self, section):
        return self._config.has_section(section)

    def options(self, section):
        return self._config.options(section)

    def has_option(self, section, option):
        return self._config.has_option(section, option)

    def get(self, section, option, raw=False, vars=None, fallback=_UNSET):
        return self._config.get(section, option, raw=raw, vars=vars, fallback=fallback)

    def getint(self, section, option, *, raw=False, vars=None, fallback=_UNSET):
        return self._config.getint(
            section, option, raw=raw, vars=vars, fallback=fallback
        )

    def getfloat(self, section, option, *, raw=False, vars=None, fallback=_UNSET):
        return self._config.getfloat(
            section, option, raw=raw, vars=vars, fallback=fallback
        )

    def getboolean(self, section, option, *, raw=False, vars=None, fallback=_UNSET):
        return self._config.getboolean(
            section, option, raw=raw, vars=vars, fallback=fallback
        )

    def items(self, section=_UNSET, raw=False, vars=None):
        return self._config.items(section=section, raw=raw, vars=vars)

    def set(self, section, option, value):
        with _lock:
            self._config.set(section, option, value)
            self._save()

    def remove_option(self, section, option):
        with _lock:
            self._config.remove_option(section, option)
            self._save()

    def remove_section(self, section):
        with _lock:
            self._config.remove_section(section)
            self._save()

    def _save(self):
        """Write the file atomically: a reader, in this or another program, sees the
        old file or the new one, never an empty one."""
        with _lock:
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".seammrc.")
            try:
                with os.fdopen(fd, "w") as stream:
                    self._write(stream)
                if self.path.exists():
                    os.chmod(tmp, os.stat(self.path).st_mode & 0o7777)
                os.replace(tmp, self.path)
            except BaseException:
                if os.path.exists(tmp):
                    os.unlink(tmp)
                raise

    def _write(self, fd):
        """The text of the file, with templates for the sections not used."""
        # Added commented sections if they don't exist
        if "USER" not in self:
            fd.write("""
# [USER]
# Default user and grant information for flowcharts

# name = Last, First
# ORCID = xxxx-xxxx-xxxx-xxxx
# affiliation = Your instititution
# grants = <as DOIs like Zenodo uses, e.g 10.13039/100000001::2136142 10.13...>
""")
        if "ZENODO" not in self:
            fd.write("""
# [ZENODO]
# API token for Zenodo

# token = xxxx....
""")
        if "SANDBOX" not in self:
            fd.write("""
# [SANDBOX]
# API token for Zenodo's sandbox

# token = xxxxx....
""")

        # And write the config file data
        self._config.write(fd)

    def re_read(self):
        with _lock:
            config = configparser.ConfigParser()
            config.read(self.path)
            self._config = config
