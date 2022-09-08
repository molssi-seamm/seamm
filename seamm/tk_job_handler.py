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
import shlex
import tkinter as tk
from tkinter import messagebox
from tkinter import simpledialog
import tkinter.ttk as ttk

import Pmw

from .dashboard_handler import DashboardHandler
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

        self._dashboard_handler = None

        self._widgets = {}
        self._variable_value = {}
        self.resource_path = Path(pkg_resources.resource_filename(__name__, "data/"))

        s = ttk.Style()
        s.configure("Border.TLabel", relief="ridge", anchor=tk.W, padding=5)

    @property
    def current_dashboard(self):
        "The current dashboard, from dashboard_handler"
        return self.dashboard_handler.current_dashboard

    @current_dashboard.setter
    def current_dashboard(self, dashboard):
        self.current_dashboard.current_dashboard = dashboard

    @property
    def dashboard_handler(self):
        "The connection to the dashboards."
        if self._dashboard_handler is None:
            self._dashboard_handler = DashboardHandler()
        return self._dashboard_handler

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

    def ask_for_credentials(self, dashboard, user=None, password=None):
        """Prompt the user for the login for the dashboard

        Parameters
        ----------
        dashboard : str
            The name of the dashboard.
        user : str
            The username for that dashboard.
        password : str
            The password for the user.

        Returns
        -------
        (str, str)
            A tuple with the username and password.
        """
        dialog = Pmw.Dialog(
            self._root,
            buttons=("OK", "Cancel"),
            master=self._root,
            title=f"Log-in for {dashboard}",
        )
        dialog.withdraw()

        d = dialog.interior()
        w_user = sw.LabeledEntry(d, labeltext="Username:", width=50)
        w_password = sw.LabeledEntry(d, labeltext="Password:", show="*")

        w_user.grid(row=0, column=0, sticky=tk.EW)
        w_password.grid(row=1, column=0, sticky=tk.EW)

        sw.align_labels([w_user, w_password], sticky=tk.E)

        result = dialog.activate(geometry="centerscreenfirst")

        if result == "OK":
            user = w_user.get()
            password = w_password.get()

        dialog.destroy()

        return user, password

    def check_status_cb(self):
        """Helper for checking the status of a dashboard."""
        w = self._widgets["edit dashboard"]
        dashboard = w["dashboard"]
        status = self.dashboard_handler.get_dashboard(dashboard).status()
        w["status"].set(status)

    def create_submit_dialog(self, title="", description=""):
        """Create the dialog for submitting a job.

        Parameters
        ----------
        flowchart : seamm.Flowchart
            The flowchart object
        """
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
        dashboards = self.dashboard_handler.dashboards
        w["dashboard"] = sw.LabeledCombobox(
            d, labeltext="Dashboard:", values=dashboards
        )
        w["dashboard"].combobox.bind("<<ComboboxSelected>>", self.dashboard_cb)

        w["add"] = ttk.Button(d, text="add dashboard...", command=self.add_dashboard_cb)

        # User and project
        w["project"] = sw.LabeledCombobox(d, labeltext="Project:", state="readonly")
        w["project"].bind("<<ComboboxSelected>>", self.project_cb)

        # Title
        w["title"] = sw.LabeledEntry(d, labeltext="Title:", width=100)
        w["title"].set(title)

        # Description
        w["description label"] = ttk.Label(d, text="Description:")
        frame = sw.ScrolledFrame(
            d, scroll_vertically=True, borderwidth=2, relief=tk.SUNKEN
        )
        f = frame.interior()
        w["description"] = tk.Text(f)
        w["description"].grid(sticky=tk.EW)
        w["description"].insert("1.0", description)

        f.rowconfigure(0, weight=1)
        f.columnconfigure(0, weight=1)

        # Space for any parameters
        w["parameters label"] = ttk.Label(d, text="Parameters:")
        w["parameters"] = sw.ScrolledColumns(
            d,
            columns=[
                "Name",
                "Value",
                "",
                "Description",
            ],
        )

        # Set up the dashboard and projects if needed
        if len(dashboards) > 0:
            w["dashboard"].set(self.current_dashboard.name)
            self.dashboard_cb()

        # Grid the widgets into rows and columns
        w["dashboard"].grid(row=0, column=0, sticky=tk.EW)
        w["add"].grid(row=0, column=1, sticky=tk.W)
        w["project"].grid(row=1, column=0, sticky=tk.EW)
        w["title"].grid(row=2, column=0, columnspan=2, sticky=tk.W)
        w["description label"].grid(row=3, column=0, columnspan=2, sticky=tk.W)
        frame.grid(row=4, column=0, columnspan=2, sticky=tk.NSEW)
        w["parameters label"].grid(row=5, column=0, columnspan=2, sticky=tk.W)
        w["parameters"].grid(row=6, column=0, columnspan=2, sticky=tk.NSEW)

        sw.align_labels([w["dashboard"], w["project"], w["title"]])

        d.rowconfigure(4, weight=1)
        d.rowconfigure(6, weight=1)
        d.columnconfigure(1, weight=1)

    def dashboard_cb(self, event=None):
        """The selected dashboard has been changed"""
        w = self._widgets
        dashboard = w["dashboard"].get()

        projects = self.dashboard_handler.get_dashboard(dashboard).list_projects()
        if len(projects) == 0:
            if self.current_dashboard is not None:
                w["dashboard"].set(self.current_dashboard.name)
            return

        # All OK, changed the widgets
        projects.append("-- Create new project --")
        w["project"].combobox.config({"value": projects})
        if len(projects) > 0:
            w["project"].set(projects[0])
        else:
            w["project"].set("")
        self.current_dashboard = dashboard

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
            w["selected"].set(self.current_dashboard.name)
        for dashboard in self.dashboard_handler.dashboards:
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
                self.dashboard_handler.rename_dashboard(dashboard, name.get())
                # Changed the name. Move the section in the config file
                dashboard = name.get()
                table[trow, 1].configure(text=dashboard)
                table[trow, 0].configure(value=dashboard)
                self._widgets["display"]["selected"].set(dashboard)
                self.current_dashboard = dashboard

            dboard = self.dashboard_handler.get_dashboard(dashboard)

            table[trow, 2].configure(text=url.get())
            dboard["url"] = url.get()
            if state.get() == "active":
                if status.get() == "inactive":
                    table[trow, 3].configure(text="")
                else:
                    table[trow, 3].configure(text=status.get())
            else:
                table[trow, 3].configure(text=state.get())
            dboard["state"] = state.get()

            for key, value in self.config.items(dashboard):
                if key not in ("url", "state", "status"):
                    dboard[key] = w[key].get()

            self.dashboard_handler.update(dashboard)

    def file_cb(self, table, row, name, data):
        """Method to handle parameters with files

        Parameters
        ----------
        table : sw.ScrolledColumns
            The widget displaying the table of parameters.
        row : int
            The row of the table.
        name : str
            The name of the parameter.
        data : dict(str, str)
            The definition of the parameter.
        """
        multiple = data["nargs"] != "a single value"

        filetypes = [
            ("MOL", "*.mol"),
            ("MOL", "*.mol2"),
            ("SDF", "*.sdf"),
            ("XYZ", "*.xyz"),
            ("CIF", "*.cif"),
            ("MMCIF", "*.mmcif"),
            ("All files", "*"),
        ]
        filename = tk.filedialog.askopenfilename(filetypes=filetypes, multiple=multiple)
        if filename == "":
            return
        w = table[row, 1]
        if multiple:
            current = shlex.split(w.get())
            for name in filename:
                if name not in current:
                    current.append(name)
            w.delete(0, tk.END)
            w.insert(0, " " + shlex.join(current))
        else:
            w.delete(0, tk.END)
            w.insert(0, filename)

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
                dashboard = table[row, 1].cget("text")
                status = self.dashboard_handler.get_dashboard(dashboard).status()
                table[row, 3].configure(text=status)
            progress.step()
            table.update()
        progress.destroy()
        dialog.configure(title="Dashboards")

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
        dashboards = self.dashboard_handler.dashboards
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
                length=len(dashboards) + 1,
                maximum=len(dashboards),
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
        for dashboard in dashboards:
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
        self.dashboard_handler.add_dashboard(name, url, protocol)

        # And reset the list in the dashboard combobox
        c = self._widgets["dashboard"]
        c.combobox.config({"value": self.dashboard_handler.dashboards})
        c.set(name)

    def handle_dialog(self, result):
        """Handle the submit dialog being completed."""
        if result is None or result == "Cancel":
            self.dialog.deactivate(None)
        else:
            w = self._widgets
            self.dialog.deactivate(
                {
                    "project": w["project"].get(),
                    "title": w["title"].get(),
                    "dashboard": w["dashboard"].get(),
                    "description": w["description"].get(1.0, tk.END).strip("\n"),
                }
            )

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

    def project_cb(self, event=None):
        """Handle a change in the project since it might be asking for adding a project
        in which case prompt for the new project's name, create it, and sleect it in the
        widget.
        """
        w = self._widgets
        project = w["project"].get()
        if project == "-- Create new project --":
            result = simpledialog.askstring("Add Project", "Project name:")
            if result is not None and result != "":
                # Add the project
                dashboard = w["dashboard"].get()
                if self.dashboard_handler.add_project(dashboard, result):
                    pass
            self.dashboard_cb()
            w["project"].set(result)

    def submit_with_dialog(self, flowchart):
        """
        Allow the user to choose the dashboard and other parameters,
        and submit the job as requested.

        Parameters
        ----------
        flowchart : seamm.Flowchart
            The flowchart to use.

        Returns
        -------
        job_id : integer
            The id of the submitted job.
        """
        if self.dialog is None:
            title = flowchart.metadata["title"]
            description = flowchart.metadata["description"]
            self.create_submit_dialog(title=title, description=description)

        value = self._variable_value

        # Find any Parameter steps.
        parameter_steps = []
        step = flowchart.get_node("1")
        while step:
            if step.step_type == "control-parameters-step":
                parameter_steps.append(step)
            step = step.next()

        if len(parameter_steps) == 0:
            # Remove the parameter section
            self._widgets["parameters label"].grid_forget()
            self._widgets["parameters"].grid_forget()
            d = self.dialog.interior()
            d.rowconfigure(6, weight=0)
        else:
            self._widgets["parameters label"].grid(
                row=5, column=0, columnspan=2, sticky=tk.W
            )
            table = self._widgets["parameters"]
            table.clear()
            table.grid(row=6, column=0, columnspan=2, sticky=tk.NSEW)
            frame = table.interior()
            d = self.dialog.interior()
            d.rowconfigure(6, weight=1)
            row = 0
            for step in parameter_steps:
                variables = step.parameters["variables"]
                for name, data in variables.value.items():
                    table[row, 0] = name
                    if name not in value or value[name] is None:
                        value[name] = data["default"]
                    entry = ttk.Entry(frame)
                    entry.insert(0, value[name])
                    table[row, 1] = entry
                    table[row, 1].grid(sticky=tk.EW)
                    if data["type"] == "file":
                        button = tk.Button(
                            frame,
                            text="...",
                            command=(
                                lambda t=table, r=row, n=name, d=data: self.file_cb(
                                    t, r, n, d
                                )
                            ),
                        )
                        table[row, 2] = button
                    table[row, 3] = data["help"]
                    row += 1
            frame.columnconfigure(1, weight=1)

        # Post the dialog
        result = self.dialog.activate(geometry="centerscreenfirst")

        if result is not None:
            if len(parameter_steps) == 0:
                value = {}
            else:
                # Get the variable values
                table = self._widgets["parameters"]
                for row in range(table.nrows):
                    name = table[row, 0].cget("text")
                    value[name] = table[row, 1].get()

            dashboard_name = result.pop("dashboard")
            dashboard = self.dashboard_handler.get_dashboard(dashboard_name)
            job_id = dashboard.submit(flowchart, values=value, **result)
            return job_id
        else:
            return None
