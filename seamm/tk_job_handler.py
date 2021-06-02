#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
The graphical interface for submitting SEAMM jobs.

A job in SEAMM is composed of a flowchart and any other files that the
flowchart requires. This module provides the TkJobHandler class, which
provides a use interface and the machinery to gather the necessary
files and submit the job to a dashboard.
"""

import configparser
import logging
from pathlib import Path
import pkg_resources
import requests
import tkinter as tk
from tkinter import messagebox
import tkinter.ttk as ttk

import Pmw

import seamm_util
import seamm_widgets as sw

logger = logging.getLogger(__name__)


class TkJobHandler(object):
    def __init__(self, root=None):
        """Setup the Job Handler object.

        Parameters
        ----------
        root : Tk window
            The root Tk window.
        """
        self._root = root
        self.config = configparser.ConfigParser()
        self.dialog = None
        self._widgets = {}
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
        self.timeout = self.config.get("GENERAL", "timeout", fallback=0.5)

        s = ttk.Style()
        s.configure("Border.TLabel", relief="ridge", anchor=tk.W, padding=5)

    @property
    def dashboards(self):
        """The list of dashboards."""
        result = []
        for dashboard in self.config:
            if dashboard not in ("GENERAL", self.config.default_section):
                result.append(dashboard)
        return sorted(result)

    def submit_with_dialog(self, flowchart=None):
        """
        Allow the user to choose the dashboard and other parameters,
        and submit the job as requested.

        Parameters
        ----------
        flowchart : text, optional
            The flowchart to use. If not given, prompt the user for
            one.

        Returns
        -------
        job_id : integer
            The id of the submitted job.
        """
        if self.dialog is None:
            self.create_submit_dialog()

        result = self.dialog.activate(geometry="centerscreenfirst")

        if result is not None:
            job_id = self.submit(flowchart, **result)
            return job_id
        else:
            return None

    def submit(self, flowchart, dashboard, **job):
        """Submit the job to the given dashboard."""
        job["flowchart"] = flowchart
        job["path"] = "unset"

        url = self.config[dashboard]["url"]

        logger.info(f"Submitting job to {dashboard} ({url})")
        logger.debug(f"flowchart:\n{flowchart}\n\n")

        response = requests.post(url + "/api/jobs", json=job)
        if response.status_code != 201:
            raise RuntimeError("POST /api/jobs {}".format(response.status_code))
        job_id = response.json()["id"]
        logger.info("Submitted job #{}".format(job_id))
        return job_id

    def create_submit_dialog(self):
        """Create the dialog for submitting a job."""
        logger.debug("Creating submit dialog")
        self.dialog = Pmw.Dialog(
            self._root,
            buttons=("OK", "Cancel"),
            master=self._root,
            title="Submit job to SEAMM",
            command=self.handle_dialog,
        )
        self.dialog.withdraw()

        w = self._widgets
        d = self.dialog.interior()

        # Dashboard
        dashboards = self.dashboards
        w["dashboard"] = sw.LabeledCombobox(
            d, labeltext="Dashboard:", values=dashboards
        )
        w["dashboard"].combobox.bind("<<ComboboxSelected>>", self.dashboard_cb)

        w["add"] = ttk.Button(d, text="add dashboard...", command=self.add_dashboard_cb)

        # User and project
        w["username"] = sw.LabeledEntry(d, labeltext="User:")
        w["username"].set(self.configfile.owner())
        w["project"] = sw.LabeledCombobox(d, labeltext="Project:")

        # Title
        w["title"] = sw.LabeledEntry(d, labeltext="Title:", width=100)

        # Description
        frame = sw.ScrolledFrame(
            d, scroll_vertically=True, borderwidth=2, relief=tk.SUNKEN
        )
        f = frame.interior()
        w["description"] = tk.Text(f)
        w["description"].grid(sticky=tk.EW)

        f.rowconfigure(0, weight=1)
        f.columnconfigure(0, weight=1)

        # Set up the dashboard and projects if needed
        if len(dashboards) > 0:
            tmp = self.config.get(
                "GENERAL", "current_dashboard", fallback=dashboards[0]
            )
            if tmp not in dashboards:
                tmp = dashboards[0]

            if self.current_dashboard != tmp:
                self.current_dashboard = tmp
                self.save_configuration()

            w["dashboard"].set(tmp)
            self.dashboard_cb()

        # Grid the widgets into rows and columns
        w["dashboard"].grid(row=0, column=0, sticky=tk.EW)
        w["add"].grid(row=0, column=1, sticky=tk.W)
        w["username"].grid(row=1, column=0, sticky=tk.EW)
        w["project"].grid(row=1, column=1, sticky=tk.EW)
        w["title"].grid(row=2, column=0, columnspan=2, sticky=tk.W)
        frame.grid(row=3, column=0, columnspan=2, sticky=tk.NSEW)

        sw.align_labels([w["dashboard"], w["username"], w["title"]])

        d.rowconfigure(3, weight=1)
        d.columnconfigure(1, weight=1)

    def handle_dialog(self, result):
        """Handle the submit dialog being completed."""
        if result is None or result == "Cancel":
            self.dialog.deactivate(None)
        else:
            w = self._widgets
            self.dialog.deactivate(
                {
                    "username": w["username"].get(),
                    "project": w["project"].get(),
                    "title": w["title"].get(),
                    "dashboard": w["dashboard"].get(),
                    "description": w["description"].get(1.0, tk.END),
                }
            )

    def get_configuration(self):
        """Get the list of dashboards from the config file."""
        # The path to the configfile
        if self.configfile.exists():
            self.config.read(self.configfile)
        else:
            self.config.clear()

    def save_configuration(self):
        """Save the list of dashboards to disk."""
        # Make sure the directory exists
        self.configfile.parent.mkdir(exist_ok=True)

        # Update the current dashboard
        if self.current_dashboard is not None:
            if "GENERAL" not in self.config:
                self.config["GENERAL"] = {}
            defaults = self.config["GENERAL"]
            defaults["current_dashboard"] = self.current_dashboard

        with self.configfile.open("w") as fd:
            self.config.write(fd)

    def add_dashboard_cb(self):
        """Post a dialog for adding a dashboard to the list."""
        dialog = Pmw.Dialog(
            self._root,
            buttons=("OK", "Cancel"),
            master=self._root,
            title="Add Dashboard to list",
            command=self.handle_add_dialog,
        )
        dialog.withdraw()
        w = self._widgets["add"] = {"dialog": dialog}

        d = dialog.interior()
        name = sw.LabeledEntry(d, labeltext="Name", width=50)
        url = sw.LabeledEntry(d, labeltext="URL")
        protocol = sw.LabeledCombobox(
            d, labeltext="Protocol", values=["http", "sshtunnel"]
        )
        protocol.set("http")

        w["name"] = name
        w["url"] = url
        w["protocol"] = protocol

        name.grid(row=0, column=0, sticky=tk.EW)
        url.grid(row=1, column=0, sticky=tk.EW)
        protocol.grid(row=2, column=0, sticky=tk.W)

        sw.align_labels([name, url, protocol])

        dialog.activate(geometry="centerscreenfirst")

    def handle_add_dialog(self, result):
        """Handle the dialog to add a dashboard to the list."""
        w = self._widgets["add"]
        dialog = w["dialog"]
        if result is None or result == "Cancel":
            dialog.deactivate(result)
        else:
            name = w["name"].get()
            url = w["url"].get()
            protocol = w["protocol"].get()

            if name in self.config:
                messagebox.showwarning(
                    "Duplicate name",
                    (
                        "There is already a dashboard called '{}'\n"
                        "Use a different name."
                    ).format(name),
                )
                return

            dialog.deactivate(result)
        dialog.destroy()
        del self._widgets["add"]

        # Now add to the configuration
        self.config[name] = {"url": url, "protocol": protocol}

        self.save_configuration()

        # And reset the list in the dashboard combobox
        c = self._widgets["dashboard"]
        c.combobox.config({"value": self.dashboards})
        c.set(name)

    def dashboard_cb(self, event=None):
        """The selected dashboard has been changed"""
        w = self._widgets
        dashboard = w["dashboard"].get()

        url = self.config[dashboard]["url"]

        try:
            response = requests.get(url + "/api/projects", timeout=self.timeout)
            if response.status_code != 200:
                logger.warning(
                    (
                        "Encountered an error getting the status from "
                        "dashboard '{}', error code: {}"
                    ).format(dashboard, response.status_code)
                )
                messagebox.showerror(
                    title="Dashboard error",
                    message="Dashboard '{}' returned an error: {}".format(
                        dashboard, response.status_code
                    ),
                )
                if self.current_dashboard is not None:
                    w["dashboard"].set(self.current_dashboard)
                return
            else:
                data = response.json()
        except requests.exceptions.Timeout:
            logger.warning("A timeout occurred contacting the dashboard " + dashboard)
            messagebox.showerror(
                title="Dashboard error",
                message="Could not reach dashboard '{}'".format(dashboard),
            )
            if self.current_dashboard is not None:
                w["dashboard"].set(self.current_dashboard)
            return
        except requests.exceptions.ConnectionError:
            logger.warning(
                "A connection error occurred contacting the dashboard " + dashboard
            )
            messagebox.showerror(
                title="Dashboard error",
                message=("A connection error occured reaching dashboard '{}'").format(
                    dashboard
                ),
            )  # yapf: disable
            if self.current_dashboard is not None:
                w["dashboard"].set(self.current_dashboard)
            return

        # get the projects
        projects = [i["name"] for i in data]

        # All OK, changed the widgets
        w["project"].combobox.config({"value": projects})
        if len(projects) > 0:
            w["project"].set(projects[0])
        else:
            w["project"].set("")
        self.current_dashboard = dashboard
        self.save_configuration()

    def display_dashboards(self):
        """Display a list of all the dashboards with their status.

        Allow users to edit, remove and add dashboards.
        """
        # statuses = self.get_all_status(master=self._root)

        dialog = Pmw.Dialog(
            self._root,
            buttons=("OK", "Edit", "Remove", "Cancel"),
            master=self._root,
            title="Dashboards",
            command=self.handle_dashboard_dialog,
        )
        dialog.withdraw()
        w = self._widgets["display"] = {"dialog": dialog}

        d = dialog.interior()
        w["table"] = sw.ScrolledColumns(
            d,
            columns=[
                "Select",
                "Dashboard",
                "URL",
                "Status",
            ],
            header_style="Border.TLabel",
        )
        w["table"].grid(row=0, column=0, sticky=tk.NSEW)
        d.columnconfigure(0, weight=1)
        d.rowconfigure(0, weight=1)

        # Button to update all status
        w["update all"] = ttk.Button(
            d, text="Update Status of All Dashboards", command=self.fill_statuses
        )
        w["update all"].grid()

        # Fill in the dashboards
        table = w["table"]
        f = table.interior()
        row = 0
        w["selected"] = tk.StringVar()
        if self.current_dashboard is not None:
            w["selected"].set(self.current_dashboard)
        for dashboard in self.dashboards:
            table[row, 0] = ttk.Radiobutton(
                f,
                variable=w["selected"],
                value=dashboard,
            )
            table[row, 1] = ttk.Label(f, text=dashboard, style="Border.TLabel")
            table[row, 2] = ttk.Label(
                f, text=self.config[dashboard]["url"], style="Border.TLabel"
            )
            state = self.config.get(dashboard, "state", fallback="active")
            if state == "active":
                table[row, 3] = ttk.Label(f, width=16, style="Border.TLabel")
            else:
                table[row, 3] = ttk.Label(
                    f, text=state, width=16, style="Border.TLabel"
                )
            table[row, 0].grid(sticky=tk.EW)
            table[row, 1].grid(sticky=tk.EW)
            table[row, 2].grid(sticky=tk.EW)
            table[row, 3].grid(sticky=tk.EW)
            row += 1

        self.fit_dialog(dialog)

        dialog.activate(geometry="centerscreenfirst")

        dialog.destroy()
        del self._widgets["display"]

    def fill_statuses(self):
        w = self._widgets["display"]
        dialog = w["dialog"]
        table = w["table"]

        dialog.configure(title="Dashboards -- Updating Status")
        progress = ttk.Progressbar(
            dialog.interior(),
            orient=tk.HORIZONTAL,
            maximum=table.nrows + 1,
            mode="determinate",
            value=1,
        )
        progress.grid(sticky=tk.EW)

        for row in range(table.nrows):
            current_status = table[row, 3].cget("text")
            if current_status != "inactive":
                table[row, 3].configure(text="...")
                table.update()
                status = self.status(table[row, 1].cget("text"))
                table[row, 3].configure(text=status)
            progress.step()
            table.update()
        progress.destroy()
        dialog.configure(title="Dashboards")

    def status(self, dashboard, timeout=1):
        """The status of the given dashboard.

        Contact the given dashboard, checking for errors, timeouts,
        etc. and report back the current status.

        Return
        ------
        status : enum (a string...)
            'up'
            'down'
            'error'
        """

        url = self.config[dashboard]["url"]

        try:
            response = requests.get(url + "/api/status", timeout=timeout)
            if response.status_code != 200:
                logger.info(
                    (
                        "Encountered an error getting the status from "
                        "dashboard '{}', error code: {}"
                    ).format(dashboard, response.status_code)
                )
                result = "dashboard error"
            else:
                result = response.text
        except requests.exceptions.Timeout:
            logger.info("A timeout occurred contacting the dashboard " + dashboard)
            result = "down"
        except requests.exceptions.ConnectionError as e:
            logger.info(
                "A connection error occurred contacting the dashboard " + dashboard
            )
            if e.response is not None:
                logger.info(
                    "Status code = {}, {}".format(
                        e.response.status_code, e.response.text
                    )
                )
            result = "connection error"

        return result

    def handle_dashboard_dialog(self, result):
        """Handle the dialog to add a dashboard to the list."""
        w = self._widgets["display"]
        dialog = w["dialog"]
        dashboard = w["selected"].get()
        if result is None or result == "Cancel":
            dialog.deactivate(None)
        elif result == "Edit":
            self.edit_cb(dashboard)
        elif result == "Remove":
            self.remove_cb(dashboard)
        else:
            dialog.deactivate(None)

    def edit_cb(self, dashboard):
        """Edit the information for a dashboard."""
        table = self._widgets["display"]["table"]
        for trow in range(table.nrows):
            if table[trow, 1].cget("text") == dashboard:
                break

        dialog = Pmw.Dialog(
            self._root,
            buttons=("OK", "Cancel"),
            title="Edit " + dashboard.title(),
        )
        dialog.withdraw()
        w = self._widgets["edit dashboard"] = {"dialog": dialog, "dashboard": dashboard}

        d = dialog.interior()
        name = sw.LabeledEntry(d, labeltext="Name:", width=50)
        name.set(table[trow, 1].cget("text"))
        url = sw.LabeledEntry(d, labeltext="URL:", width=50)
        url.set(table[trow, 2].cget("text"))
        state = sw.LabeledCombobox(d, labeltext="State:", values=["active", "inactive"])
        current_status = table[trow, 3].cget("text")
        if current_status == "inactive":
            state.set("inactive")
        else:
            state.set("active")
        status = sw.LabeledEntry(d, labeltext="Status:", width=16)
        status.set(current_status)
        check_status = ttk.Button(d, text="Check Status", command=self.check_status_cb)
        w["status"] = status

        name.grid(row=0, columnspan=2, sticky=tk.EW)
        url.grid(row=1, columnspan=2, sticky=tk.EW)
        state.grid(row=2, columnspan=2, sticky=tk.EW)
        status.grid(row=3, sticky=tk.EW)
        check_status.grid(row=3, column=1)

        widgets = [name, url, state, status]

        # If there are any other items in the config file, put them in
        row = 3
        for key, value in self.config.items(dashboard):
            if key not in ("url", "state", "status"):
                row += 1
                w[key] = sw.LabeledEntry(d, labeltext=key + ":")
                w[key].set(value)
                w[key].grid(row=row, columnspan=2, sticky=tk.EW)
                widgets.append(w[key])

        sw.align_labels(widgets)

        result = dialog.activate(geometry="centerscreenfirst")

        if result == "OK":
            if name.get() != dashboard:
                # Changed the name. Move the section in the config file
                tmp = {}
                for key, value in self.config.items(dashboard):
                    tmp[key] = value
                self.config.remove_section(dashboard)
                dashboard = name.get()
                self.config[dashboard] = tmp
                table[trow, 1].configure(text=dashboard)
                table[trow, 0].configure(value=dashboard)
                self._widgets["display"]["selected"].set(dashboard)
                self.current_dashboard = dashboard

            db_config = self.config[dashboard]

            table[trow, 2].configure(text=url.get())
            db_config["url"] = url.get()
            if state.get() == "active":
                if status.get() == "inactive":
                    table[trow, 3].configure(text="")
                else:
                    table[trow, 3].configure(text=status.get())
            else:
                table[trow, 3].configure(text=state.get())
            db_config["state"] = state.get()

            for key, value in self.config.items(dashboard):
                if key not in ("url", "state", "status"):
                    db_config[key] = w[key].get()

            self.save_configuration()

    def check_status_cb(self):
        """Helper for checking the status of a dashboard."""
        w = self._widgets["edit dashboard"]
        dashboard = w["dashboard"]
        status = self.status(dashboard)
        w["status"].set(status)

    def fit_dialog(self, dialog):
        """Resize and fit the dialog to the current contents and the
        constraint of the window.
        """
        logger.debug("Entering fit_dialog")

        widget = self._widgets["display"]["table"].interior()
        logger.debug("  widget = {}".format(widget))
        widget.update_idletasks()

        frame = dialog.interior()
        frame.update_idletasks()
        width = frame.winfo_width()
        height = frame.winfo_height()
        sw = frame.winfo_screenwidth()
        sh = frame.winfo_screenheight()

        logger.debug(
            "  frame wxh = {} x {}, screen = {} x {}".format(width, height, sw, sh)
        )

        mw = frame.winfo_reqwidth()
        mh = frame.winfo_reqheight()
        logger.debug("  frame requested = {} x {}".format(mw, mh))

        # Need to handle scrolledtable using its inside frame
        ww = widget.winfo_width()
        hh = widget.winfo_height()
        w = widget.winfo_reqwidth()
        h = widget.winfo_reqheight()
        logger.debug("  table wxh = {} x {}, requested = {} x {}".format(ww, hh, w, h))
        h += 20  # Add a bit of space...
        if w > mw:
            mw = w
        if h > mh:
            mh = h
        if ww > width:
            width = ww
        if hh > height:
            height = hh

        if width < mw:
            width = mw
        width += 70
        if width > 0.9 * sw:
            width = int(0.9 * sw)
        if height < mh:
            height = mh
        height += 70
        if height > 0.9 * sh:
            height = int(0.9 * sh)

        dialog.geometry("{}x{}".format(width, height))

    def get_all_status(self, show_progress=True, master=None):
        """Get the status of all the dashboards.

        Parameters
        ----------
        show_progress : Boolean, optional
            Show a dialog with progress, default is True
        """
        if show_progress:
            dialog = tk.Toplevel(master=master)
            dialog.focus_set()  # set focus on the ProgressWindow
            dialog.grab_set()  # make a modal window
            dialog.transient(master)  # show only one window in the task bar

            dialog.title("Getting Status of Dashboards")
            dialog.resizable(False, False)  # window is not resizable
            # dialog.close gets fired when the window is destroyed
            # dialog.protocol(u'WM_DELETE_WINDOW', dialog.close)
            dialog.geometry("400x200+200+200")
            # cancel progress when <Escape> key is pressed
            # dialog.bind(u'<Escape>', self.close)

            progress = ttk.Progressbar(
                dialog,
                orient=tk.HORIZONTAL,
                length=len(self.dashboards) + 1,
                maximum=len(self.dashboards),
                mode="determinate",
                value=1,
            )
            progress.grid(ipady=20, sticky=tk.NSEW)
            label = ttk.Label(dialog, text="Dashboard")
            label.grid()
            dialog.rowconfigure(0, minsize=30)
            dialog.columnconfigure(0, weight=1)
            dialog.update_idletasks()
            dialog.after(50)

        result = []
        for dashboard in self.dashboards:
            if show_progress:
                label.configure({"text": dashboard})
                dialog.update_idletasks()
                dialog.after(50)
            status = self.status(dashboard)
            result.append((dashboard, status))
            if show_progress:
                progress.step()
                label.configure({"text": dashboard})
                dialog.update_idletasks()
                dialog.after(50)

        if show_progress:
            master.focus_set()
            dialog.destroy()

        return result
