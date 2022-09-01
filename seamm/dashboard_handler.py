#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
The interface for submitting SEAMM jobs.

A job in SEAMM is composed of a flowchart and any other files that the
flowchart requires. This module provides the JobHandler class, which
provides a use interface and the machinery to gather the necessary
files and submit the job to a dashboard.
"""

import configparser
import logging
from pathlib import Path
import pkg_resources

import seamm_dashboard_client
import seamm_util

logger = logging.getLogger(__name__)


def safe_filename(filename):
    if filename[0] == "~":
        path = Path(filename).expanduser()
    else:
        path = Path(filename)
    if path.anchor == "":
        result = "_".join(path.parts)
    else:
        result = "_".join(path.parts[1:])
    return "job:data/" + result


class DashboardHandler(object):
    def __init__(self, user_agent=None):
        """Setup the handler for Dashboards.

        Parameters
        ----------
        """
        self.config = configparser.ConfigParser()

        if user_agent is None:
            import seamm

            self.user_agent = f"SEAMM/{seamm.__version__}"
        else:
            self.user_agent = user_agent

        self._credentials = None
        self._current_dashboard = None
        self.resource_path = Path(pkg_resources.resource_filename(__name__, "data/"))

        # Get the location of the dashboards configuration file
        parser = seamm_util.seamm_parser()
        options = parser.get_options()
        if "dashboards" in options:
            self.configfile = Path(options["dashboards"]).expanduser()
        else:
            self.configfile = Path.home() / "SEAMM" / "dashboards.ini"

        # Create the file if it doesn't exist
        if not self.configfile.exists():
            self.configfile.parent.mkdir(parents=True, exist_ok=True)
            path = self.resource_path / "dashboards.ini"
            text = path.read_text()
            self.configfile.write_text(text)

        # Read in the dashboard information if present
        self.get_configuration()
        self.current_dashboard = self.config.get(
            "GENERAL", "current_dashboard", fallback=None
        )
        self.timeout = self.config.get("GENERAL", "timeout", fallback=1)

    @property
    def credentials(self):
        """The data from ~/.seammrc, if it exists."""
        if self._credentials is None:
            self._credentials = configparser.ConfigParser()
            path = Path("~/.seammrc").expanduser()
            if path.exists():
                self._credentials.read(path)
        return self._credentials

    @property
    def current_dashboard(self):
        "The currently selected dashboard"
        if self._current_dashboard is None:
            dashboards = self.dashboards

            dashboard = self.config.get(
                "GENERAL", "current_dashboard", fallback=dashboards[0]
            )
            if dashboard not in dashboards:
                dashboard = dashboards[0]

            self._current_dashboard = self.get_dashboard(dashboard)
            self.save_configuration()
        return self._current_dashboard

    @current_dashboard.setter
    def current_dashboard(self, dashboard):
        if isinstance(dashboard, str):
            self._current_dashboard = self.get_dashboard(dashboard)
        else:
            if dashboard.name in self.dashboards:
                self._current_dashboard = dashboard
            else:
                raise ValueError(f"Dashboard {dashboard.name} does not exist!")

    @property
    def dashboards(self):
        """The list of dashboards."""
        result = []
        for dashboard in self.config:
            if dashboard not in ("GENERAL", self.config.default_section):
                result.append(dashboard)
        return sorted(result)

    def add_dashboard(self, name, url, protocol):
        "Add a new dashboard to the config file"
        self.config[name] = {"url": url, "protocol": protocol}
        self.save_configuration()

    def get_all_status(self):
        """Get the status of all the dashboards.

        Parameters
        ----------
        """
        result = []
        for dashboard in self.dashboards:
            status = self.get_dashboard(dashboard).status()
            result.append((dashboard, status))

        return result

    def get_configuration(self):
        """Get the list of dashboards from the config file."""
        # The path to the configfile
        if self.configfile.exists():
            self.config.read(self.configfile)
        else:
            self.config.clear()

    def get_credentials(self, dashboard, ask=None):
        """The user for the dashboard.

        Parameters
        ----------
        dashboard : str
            The name of the dashboard to use.

        Returns
        -------
        str, str
            The user name and password
        ask : function
            A function or method to call to get the user name and passwd.
        """
        user = None
        password = None
        if dashboard not in self.credentials:
            self.credentials[dashboard] = {}

        if "user" in self.credentials[dashboard]:
            user = self.credentials[dashboard]["user"]

        if "password" in self.credentials[dashboard]:
            password = self.credentials[dashboard]["password"]

        if ask is not None and (user is None or password is None):
            user, password = ask(dashboard, user=user, password=password)
            if user is not None and password is not None:
                self.credentials[dashboard]["user"] = user
                self.credentials[dashboard]["password"] = password

                path = Path("~/.seammrc").expanduser()
                with open(path, "w") as fd:
                    self.credentials.write(fd)
        return user, password

    def get_dashboard(self, name):
        """Get the given dashboard object.

        Parameters
        ----------
        name : str
            The name of the Dashboard

        Returns
        -------
        seamm_dashboard_client.Dashboard :
            The Dashboard client object.
        """
        user, passwd = self.get_credentials(name)
        url = self.config[name]["url"]

        return seamm_dashboard_client.Dashboard(
            name, url, username=user, password=passwd, user_agent=self.user_agent
        )

    def rename_dashboard(self, old, new):
        "Rename a dashboard from 'old' to 'new'."
        tmp = {}
        for key, value in self.config[old].items():
            tmp[key] = value
        self.config.remove_section(old)
        self.config[new] = tmp

    def save_configuration(self):
        """Save the list of dashboards to disk."""
        # Make sure the directory exists
        self.configfile.parent.mkdir(exist_ok=True)

        # Update the current dashboard
        if self.current_dashboard is not None:
            if "GENERAL" not in self.config:
                self.config["GENERAL"] = {}
            defaults = self.config["GENERAL"]
            defaults["current_dashboard"] = self.current_dashboard.name

        with self.configfile.open("w") as fd:
            self.config.write(fd)

    def update(self, dashboard):
        "Update the dashboard with that given."
        self.config[dashboard.name] = {
            "url": dashboard.url,
            "protocol": "http",
        }
        self.save_configuration()
