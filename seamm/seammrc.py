# -*- coding: utf-8 -*-

"""A singleton to ensure the ~.seammrc file is always up-to-date."""

import configparser
from pathlib import Path

# Used in parser getters to indicate the default behaviour when a specific
# option is not found it to raise an exception. Created to enable `None' as
# a valid fallback value.
_UNSET = object()


class Singleton(object):
    _instances = {}

    def __new__(class_, *args, **kwargs):
        if class_ not in class_._instances:
            class_._instances[class_] = super(Singleton, class_).__new__(
                class_, *args, **kwargs
            )
        return class_._instances[class_]


class SEAMMrc(Singleton):
    def __init__(self, path="~/.seammrc"):
        self._config = configparser.ConfigParser()
        self.path = Path(path).expanduser()

        # Create the file if it doesn't exist
        if self.path.exists():
            self._config.read(self.path)
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._save()

        # Check the version and upgrade if necessary
        if "VERSION" not in self._config:
            # Rename all sections as Dashboards
            for section in self._config.sections():
                tmp = {}
                for key, value in self._config[section].items():
                    tmp[key] = value
                self._config.remove_section(section)
                self._config[f"Dashboard: {section}"] = tmp
            self._config["VERSION"] = {"file": "1.0"}
            self._save()

    def __getitem__(self, key):
        raise NotImplementedError("Please use get/set")

    def __setitem__(self, key, value):
        raise NotImplementedError("Please use get/set")

    def __delitem__(self, key):
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
        self._config.set(section, option, value)
        self._save()

    def remove_option(self, section, option):
        self._config.remove_option(section, option)
        self._save()

    def remove_section(self, section):
        self._config.remove_section(section)
        self._save()

    def _save(self):
        with open(self.path, "w") as fd:
            self._config.write(fd)

    def re_read(self):
        self._config.read(self.path)
