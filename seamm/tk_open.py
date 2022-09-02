# -*- coding: utf-8 -*-

"""The GUI for opening flowcharts."""

import collections.abc
import datetime
import json
import logging
from pathlib import Path
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
import tkinter.ttk as ttk

import dateutil
import Pmw

from .dashboard_handler import DashboardHandler
from .seammrc import SEAMMrc
from seamm_dashboard_client import DashboardConnectionError
import seamm_util
import seamm_widgets as sw

logger = logging.getLogger(__name__)

# "operators": (
#     "must be",
#     "must be like",
#     "must contain",
#     "must contain like",
#     "must not be",
#     "must not be like",
#     "must not contain",
#     "must not contain like",
#     "may be",
#     "may be like",
#     "may contain",
#     "must contain like",
# ),

zenodo_fields = {
    "any field": {
        "field": "",
        "operators": (
            "contains",
            "contains like",
        ),
    },
    "author name": {
        "field": "creators.name:",
        "operators": (
            "contains",
            "contains like",
        ),
    },
    "author orcid": {"field": "creators.orcid:", "operators": ("is", "is not")},
    "author affiliation": {
        "field": "creators.affiliation:",
        "operators": (
            "contains",
            "contains like",
        ),
    },
    "community": {
        "field": "communities:",
        "operators": ("is", "is like", "is not", "is not like"),
    },
    "date": {"field": "created", "operators": ("after", "before", "on", "between")},
    "description": {
        "field": "description:",
        "operators": (
            "contains",
            "contains like",
        ),
    },
    "keyword": {
        "field": "keywords:",
        "operators": (
            "contains",
            "contains like",
        ),
    },
    "title": {
        "field": "title:",
        "operators": (
            "contains",
            "contains like",
        ),
    },
}


class TkOpen(collections.abc.MutableMapping):
    def __init__(self, toplevel):
        self._widgets = {"toplevel": toplevel}

        self._data = dict()
        self.zenodo = None
        self._dashboard_handler = None
        self.dashboards = None
        self.current_dashboard = None
        self.current_project = "any"
        self._projects = None
        self.config = SEAMMrc()
        if "SEAMM open" not in self.config:
            self.config.add_section("SEAMM open")

    # Provide dict like access to the widgets to make
    # the code cleaner

    def __getitem__(self, key):
        """Allow [] access to the widgets!"""
        return self._widgets[key]

    def __setitem__(self, key, value):
        """Allow x[key] access to the data"""
        self._widgets[key] = value

    def __delitem__(self, key):
        """Allow deletion of keys"""
        if key in self._widgets:
            self._widgets[key].destroy()
        del self._widgets[key]

    def __iter__(self):
        """Allow iteration over the object"""
        return iter(self._widgets)

    def __len__(self):
        """The len() command"""
        return len(self._widgets)

    @property
    def dashboard_handler(self):
        "The connection to the dashboards."
        if self._dashboard_handler is None:
            self._dashboard_handler = DashboardHandler()
        return self._dashboard_handler

    def clear_tree(self):
        """Remove any contents from the tree."""
        tree = self["tree"]
        children = tree.get_children()
        if len(children) > 0:
            tree.delete(*children)
        self._data = {}

    def create_dialog(self):
        """Create the dialog for opening."""
        if "dialog" in self:
            return

        self["dialog"] = d = Pmw.Dialog(
            self["toplevel"],
            buttons=("Open", "Cancel"),
            master=self["toplevel"],
            title="Open Flowchart",
        )
        d.withdraw()

        frame = self["frame"] = d.interior()

        w = self["what"] = sw.LabeledCombobox(
            frame,
            labeltext="Open a",
            values=("flowchart",),
            state="readonly",
        )
        w.set("flowchart")

        if not self.config.has_option("SEAMM open", "source"):
            self.config.set("SEAMM open", "source", "local files")
            path = Path("~/SEAMM/flowcharts").expanduser()
            path.mkdir(parents=True, exist_ok=True)
        source = self.config.get("SEAMM open", "source")

        w = self["source"] = sw.LabeledCombobox(
            frame,
            labeltext="from",
            values=("local files", "previous jobs", "Zenodo", "Zenodo sandbox"),
            state="readonly",
        )
        w.set(source)

        # For local files, a directory to start from
        if not self.config.has_option("SEAMM open", "directory"):
            self.config.set(
                "SEAMM open", "directory", json.dumps(["~/SEAMM/flowcharts"])
            )
            path = Path("~/SEAMM/flowcharts").expanduser()
            path.mkdir(parents=True, exist_ok=True)
        directories = json.loads(self.config.get("SEAMM open", "directory"))
        directory = directories[0]

        w = self["directory"] = sw.LabeledCombobox(
            frame,
            labeltext="directory",
            values=directories,
        )
        w.set(directory)

        self["get directory"] = ttk.Button(
            frame, text="...", command=self.directory_cb, width=3
        )

        # From dashboard
        if not self.config.has_option("SEAMM open", "dashboard"):
            self.config.set("SEAMM open", "dashboard", "")
        w = self["dashboard"] = sw.LabeledCombobox(
            frame,
            labeltext="Dashboard",
        )
        if not self.config.has_option("SEAMM open", "project"):
            self.config.set("SEAMM open", "project", "any")
        w = self["project"] = sw.LabeledCombobox(
            frame,
            labeltext="Project",
        )

        self["criteria"] = sw.SearchCriteria(
            frame,
            text="Show flowcharts where",
            labelanchor=tk.NW,
            inclusiontext="",
            inclusionvalues=(
                "must have",
                "must not have",
                "may have",
                "and",
                "or",
                "(",
                ")",
                "ignore",
            ),
            operatorvalues=(
                "contains",
                "contains like",
            ),
            fieldvalues=[*zenodo_fields.keys()],
            two_values=("between",),
            command=self.zenodo_callback,
        )

        self["search"] = ttk.Button(frame, text="Search", command=self.search_cb)
        w = self["tree"] = ttk.Treeview(frame, selectmode="browse")
        w.bind("<ButtonRelease-1>", self.select_record)
        w.bind(
            "<Double-Button-1>", lambda e=None: self["dialog"].deactivate(result="Open")
        )
        # Add scrollbars
        self["tree ysb"] = ttk.Scrollbar(frame, orient="vertical", command=w.yview)
        self["tree xsb"] = ttk.Scrollbar(frame, orient="horizontal", command=w.xview)
        w.configure(yscroll=self["tree ysb"].set, xscroll=self["tree xsb"].set)

        detail = self["detail"] = ttk.LabelFrame(
            frame,
            borderwidth=5,
            relief=tk.SUNKEN,
            text="Flowchart Details",
            labelanchor=tk.N,
        )

        row = 0
        w = self["title"] = ttk.Label(detail)
        w.grid(row=row, column=0)
        row += 1
        w = self["description"] = ScrolledText(
            detail, wrap=tk.WORD, font=("Helvetica",), height=6
        )
        w.grid(row=row, column=0, sticky=tk.NSEW)
        detail.rowconfigure(row, weight=1)
        detail.columnconfigure(0, weight=1)
        row += 1
        w = self["version"] = ttk.Label(detail)
        w.grid(row=row, column=0, sticky=tk.W)

        for item in ("what", "source"):
            self[item].bind("<<ComboboxSelected>>", self.reset_dialog)

        for item in ("directory",):
            self[item].bind("<<ComboboxSelected>>", self.reset_tree)
            self[item].bind("<Return>", self.reset_tree)
            self[item].bind("<FocusOut>", self.reset_tree)

        for item in ("dashboard", "project"):
            self[item].bind("<<ComboboxSelected>>", self.update_dashboard)

        # Fill the window with the dialog!
        swidth = frame.winfo_screenwidth()
        sheight = frame.winfo_screenheight()
        d.geometry(f"{int(0.8 * swidth)}x{int(0.8 * sheight)}")

    def directory_cb(self, event=None):
        """Invoked by the ... button to get new directory."""
        d = self["directory"]
        current = Path(d.get()).expanduser().resolve()
        if not current.exists() or not current.is_dir():
            current = Path("~").expanduser()
        directory = tk.filedialog.askdirectory(
            parent=self["toplevel"],
            title="Change directory",
            initialdir=current,
            mustexist=True,
        )

        if directory is None or current.samefile(directory):
            return

        d.set(directory)
        self.reset_tree()

    def fill_tree(self, job_list):
        """Fill the tree with a job list

        The job list looks is a list of Job objects that are dicts like::

            {
                'description': 'test of api',
                'finished': '2022-02-24 10:06',
                'flowchart_id': '1',
                'group': None,
                'group_id': None,
                'id': 18,
                'last_update': '2022-02-24 10:05',
                'owner': 'psaxe',
                'owner_id': 2,
                'parameters': {
                     'cmdline': ['job:data/Users_psaxe_SEAMM_data_TiO2--anatase.cif']
                },
                'path': '/Users/psaxe/SEAMM_DEV/Jobs/projects/default/Job_000018',
                'projects': [{'id': 1, 'name': 'default'}],
                'started': '2022-02-24 10:06',
                'status': 'finished',
                'submitted': '2022-02-24 10:05',
                'title': 'test of api'
            }

        Parameters
        ----------
        job_list : [seamm_dashboard_client._Job]
            List of Job objects contain info about the jobs
        """
        # Remove any current data
        self.clear_tree()
        self._data = {}
        tree = self["tree"]
        for job in job_list:
            iid = tree.insert("", "end", text=f"Job_{job['id']:0>6d}: {job['title']}")
            self._data[iid] = job

    def insert_node(self, parent, text, path, open=False):
        """Insert a new node in the tree, corresponding to a file or directory.

        Parameters
        ----------
        parent : str
            The parent node in the tree, "" for toplevel.
        text : str
            The text to display for the node.
        path : pathlib.Path
            The absolute path of the file or directory.
        """
        tree = self["tree"]
        node = tree.insert(parent, "end", text=text, open=open)
        self._data[node] = path
        if path.is_dir():
            tree.insert(node, "end")
        return node

    def open_node(self, event=None):
        tree = self["tree"]
        node = tree.focus()
        path = self._data.get(node, None)
        if path is not None:
            tree.delete(*tree.get_children(node))
            for p in sorted(path.iterdir(), key=lambda p: p.name):
                if p.is_dir() or p.suffix == ".flow":
                    self.insert_node(node, p.name, p)

    def reset_dialog(self, event=None):
        """Layout the widgets in the dialog according to the parameters."""

        frame = self["frame"]
        what = self["what"].get()
        source = self["source"].get()

        # Temporary
        if what != "flowchart":
            what = "flowchart"
            self["what"].set(what)

        # Remove all the widgets
        frame = self["frame"]
        for slave in frame.grid_slaves():
            slave.grid_forget()

        # and put them back in as needed.
        row = 0
        self["what"].grid(row=row, column=0, sticky=tk.W)
        self["source"].grid(row=row, column=1, sticky=tk.W)
        if source == "local files":
            self["directory"].grid(row=row, column=2, sticky=tk.EW)
            self["get directory"].grid(row=row, column=3, columnspan=2, sticky=tk.E)
        elif source == "previous jobs":
            self["dashboard"].grid(row=row, column=2, sticky=tk.EW)
            self["project"].grid(row=row, column=3, columnspan=2, sticky=tk.E)

            self.dashboards = self.dashboard_handler.dashboards

            # Remove any dashboards that we cannot access
            for dashboard, status in self.dashboard_handler.get_all_status():
                if status != "running":
                    self.dashboards.remove(dashboard)
            if len(self.dashboards) == 0:
                self.current_dashboard = None
                tk.messagebox.showwarning(
                    title="No Dashboards available",
                    message="The are no Dashboards that can be connected to.",
                )
            else:
                dashboard_name = self.config.get("SEAMM open", "dashboard")
                if dashboard_name not in self.dashboards:
                    dashboard_name = self.dashboards[0]
                if (
                    self.current_dashboard is None
                    or self.current_dashboard.name != dashboard_name
                ):
                    self.current_dashboard = self.dashboard_handler.get_dashboard(
                        dashboard_name
                    )
                self._projects = None
                projects = ["any"]
                try:
                    self._projects = self.current_dashboard.projects()
                    projects += [*self._projects.keys()]
                except DashboardConnectionError:
                    projects = []

                self["dashboard"].bind("<<ComboboxSelected>>", "")

                self["dashboard"].config(values=self.dashboards, state="readonly")
                self["dashboard"].set(self.current_dashboard.name)

                self["dashboard"].bind("<<ComboboxSelected>>", self.update_dashboard)

                self["project"].config(values=projects, state="readonly")

                project = self.config.get("SEAMM open", "project")
                if project not in projects:
                    project = projects[0]
                if self.current_project is None or self.current_project != project:
                    self.current_project = project
                self["project"].set(self.current_project)
        row += 1

        if what == "flowchart":
            if "Zenodo" in source:
                self["criteria"].grid(row=row, column=0, columnspan=5, sticky=tk.NSEW)
                frame.rowconfigure(row, weight=1)
                frame.columnconfigure(1, weight=1)
                row += 1
                self["tree"].bind("<<TreeviewOpen>>", "")
                self["search"].grid(row=row, column=0, sticky=tk.W)
                row += 1
                self.clear_tree()
            elif source == "previous jobs":
                self.clear_tree()
                self["tree"].bind("<<TreeviewOpen>>", "")

                # Get the jobs from the Dashboard.
                if self.current_dashboard is not None:
                    if self.current_project == "any":
                        job_list = self.current_dashboard.jobs()
                    else:
                        job_list = self._projects[self.current_project].jobs()
                    self.fill_tree(job_list)
            elif source == "local files":
                self.reset_tree()

            self["tree"].grid(row=row, column=0, columnspan=4, sticky=tk.NSEW)
            self["tree ysb"].grid(row=row, column=4, sticky=tk.NS + tk.W)
            frame.rowconfigure(row, weight=1)
            row += 1

            self["tree xsb"].grid(row=row, column=0, columnspan=4, sticky=tk.EW)
            row += 1

            self["detail"].grid(row=row, column=0, columnspan=5, sticky=tk.NSEW)
            row += 1
        frame.columnconfigure(2, weight=1)

    def reset_tree(self, event=None):
        """Reset the file tree to start with the given directory."""
        directory = self["directory"].get()
        path = Path(directory).expanduser().resolve()

        # Fixes issue #131
        if not path.exists():
            tk.messagebox.showwarning(
                title="Invalid directory",
                message=f"The directory given '{path}' does not exist!",
            )
            return
        elif not path.is_dir():
            if path.is_file():
                path = path.parent
                self["directory"].set(str(path))
            else:
                tk.messagebox.showwarning(
                    title="Not a directory",
                    message=f"The path '{path}' exists, but is not a directory!",
                )
                return
        self.clear_tree()
        node = self.insert_node("", path, path, open=True)
        self["tree"].focus(node)
        self.open_node()
        self["tree"].bind("<<TreeviewOpen>>", self.open_node)

    def open(self):
        """Present a dialog for opening."""
        # Reread the configuration file in case it has changed
        self.config.re_read()

        # Create the dialog if it doesn't exist
        self.create_dialog()

        self.reset_dialog()

        # And put it on-screen, the first time centered.
        result = self["dialog"].activate(geometry="centerscreenfirst")

        if result == "Open":
            what = self["what"].get()
            source = self["source"].get()

            if what == "flowchart":
                tree = self["tree"]
                selected = tree.selection()
                if source != self.config.get("SEAMM open", "source"):
                    self.config.set("SEAMM open", "source", source)
                if source == "Zenodo" or source == "Zenodo sandbox":
                    if len(selected) > 0:
                        record = self._data[selected[0]]
                        data = record.get_file("flowchart.flow")
                        return data
                elif "previous jobs" == source:
                    if len(selected) > 0:
                        self.config.set(
                            "SEAMM open", "dashboard", self.current_dashboard.name
                        )
                        self.config.set("SEAMM open", "project", self.current_project)
                        job = self._data[selected[0]]
                        job_id = job["id"]
                        job = self.current_dashboard.job(job_id)
                        data = job.get_file("flowchart.flow")
                        return data
                elif "local files" in source:
                    if len(selected) > 0:
                        path = self._data[selected[0]]
                        directory = str(path.parent)
                        directories = json.loads(
                            self.config.get("SEAMM open", "directory")
                        )
                        if directory != directories[0]:
                            if directory in directories:
                                directories.remove(directory)
                            directories.insert(0, directory)
                            self.config.set(
                                "SEAMM open", "directory", json.dumps(directories)
                            )
                            w = self["directory"]
                            w.configure(values=directories)
                            w.set(directory)
                        if path.suffix == ".flow":
                            data = path.read_text()
                            return data
                else:
                    raise RuntimeError(f"cannot handle source '{source}'")
            else:
                raise RuntimeError(f"cannot handle opening '{what}'")
        return None

    def search_cb(self):
        """Handle the search."""
        what = self["what"].get()
        source = self["source"].get()

        if what == "flowchart":
            if source == "Zenodo":
                self.search_zenodo_for_flowcharts()
            elif source == "Zenodo sandbox":
                self.search_zenodo_for_flowcharts(sandbox=True)
            else:
                raise RuntimeError(f"Can't handle source '{source}'")
        else:
            raise RuntimeError(f"Can't handle searching for '{what}'")

    def search_zenodo_for_flowcharts(self, sandbox=False):
        """Search for flowcharts in Zenodo.

        Parameters
        ----------
        sandbox : bool = False
            If true, search the Zenodo sandbox.
        """
        self.zenodo = seamm_util.Zenodo(use_sandbox=sandbox)

        criteria = self["criteria"].get()

        query = ""
        after_parenthesis = False
        for i, search_criteria in enumerate(criteria):
            inclusion, field, operator, value, value2 = search_criteria

            logger.debug(f"{inclusion=} {field=} {operator=} {value=} {value2=}")

            zf = zenodo_fields[field]["field"]

            if i == 0:
                # query += " AND ("
                after_parenthesis = True

            pre = ""
            if inclusion == "and":
                if not after_parenthesis:
                    query += " AND"
                continue
            elif inclusion == "or":
                if not after_parenthesis:
                    query += " OR"
                continue
            elif inclusion == "(":
                query += " ("
                after_parenthesis = True
                continue
            elif inclusion == ")":
                query += " )"
                after_parenthesis = False
                continue
            elif inclusion == "must have":
                pre = "+"
            elif inclusion == "must not have":
                pre = "-"
            elif inclusion == "may have":
                pre = ""
            elif inclusion == "ignore":
                continue
            else:
                raise RuntimeError(f"{inclusion=}")

            after_parenthesis = False

            if " " in value:
                value = f'"{value}"'

            if field == "date":
                try:
                    date = dateutil.parser.parse(value).isoformat()
                except Exception:
                    tk.messagebox.showwarning(
                        title="Invalid date format",
                        message=(
                            f"The date given '{value}' can't be handled. Try formats "
                            "like '2022-04-23' or '4/23/2022' or '23 Apr 2022'"
                        ),
                    )
                else:
                    if operator == "after":
                        query += (
                            f" (+keywords:seamm-flowchart AND {pre}{zf}[{date} TO *]"
                        )
                    elif operator == "before":
                        query += (
                            f" (+keywords:seamm-flowchart AND {pre}{zf}[* TO {date}]"
                        )
                    elif operator == "on":
                        query += f" (+keywords:seamm-flowchart AND {pre}{zf}{date}"
                    elif operator == "between":
                        try:
                            date2 = dateutil.parser.parse(value2).isoformat()
                        except Exception:
                            tk.messagebox.showwarning(
                                title="Invalid date format",
                                message=(
                                    f"The date given '{value}' can't be handled. Try "
                                    "formats like '2022-04-23' or '4/23/2022' or "
                                    "'23 Apr 2022'"
                                ),
                            )
                        else:
                            query += (
                                f" (+keywords:seamm-flowchart AND {pre}{zf}[{date} to "
                                f"{date2}])"
                            )
                    else:
                        raise RuntimeError(f"Don't recognize operator '{operator}'")
            else:
                if operator == "is":
                    query += f" (+keywords:seamm-flowchart AND {pre}{zf}/{value}/)"
                elif operator == "is like":
                    query += f" (+keywords:seamm-flowchart AND {pre}{zf}{value}~)"
                elif operator == "contains":
                    query += f" (+keywords:seamm-flowchart AND {pre}{zf}{value})"
                elif operator == "contains like":
                    query += f" (+keywords:seamm-flowchart AND {pre}{zf}{value}~)"
                elif operator == "is not":
                    query += f" (+keywords:seamm-flowchart AND -{zf}/{value}/)"
                elif operator == "is not like":
                    query += f" (+keywords:seamm-flowchart AND -{zf}{value}~)"
                elif operator == "does not contain":
                    query += f" (+keywords:seamm-flowchart AND -{zf}{value})"
                elif operator == "does not contain like":
                    query += f" (+keywords:seamm-flowchart AND -{zf}{value}~)"
                else:
                    raise RuntimeError(f"Don't recognize operator '{operator}'")

        if len(query) == 0:
            query = "+keywords:seamm-flowchart"

        logger.debug(f"query = {query}")

        try:
            n_hits, records = self.zenodo.search(query=query, all_versions=True)
        except RuntimeError as e:
            tk.messagebox.showwarning(title="Invalid Zenodo query", message=str(e))
            return

        # Find all related records using conceptrecid
        concepts = {}
        for record in records:
            concept_id = record["conceptrecid"]
            if concept_id not in concepts:
                concepts[concept_id] = {}
            data = concepts[concept_id]
            version = record["metadata"]["relations"]["version"][0]["index"]
            data[version] = record

        # Remove any current data
        self.clear_tree()
        self._data = {}
        tree = self["tree"]
        for concept_id, data in concepts.items():
            first = True
            for version in sorted(data.keys(), reverse=True):
                record = data[version]
                if first:
                    first = False
                    iid = tree.insert("", "end", text=record.title)
                    self._data[iid] = record
                if len(data) > 1:
                    text = f"Version {version + 1}: {record.title}"
                    jid = tree.insert(iid, "end", text=text)
                    self._data[jid] = record

    def select_record(self, event):
        """The user clicked on the tree-view ... handle the selected record."""
        tree = self["tree"]
        selected = tree.selection()
        if len(selected) == 0:
            return

        source = self["source"].get()

        if "Zenodo" in source:
            data = self._data[selected[0]]["metadata"]
            self["title"].configure(text=data["title"])
            self["description"].delete("1.0", "end")
            self["description"].insert("1.0", data["description"])
            info = data["relations"]["version"][0]
            if "publication_data" in data:
                date = data["publication_data"]
                version = f"Version {info['index'] + 1} of {info['count']} -- {date}"
            else:
                version = f"Version {info['index'] + 1} of {info['count']}"
            self["version"].configure(text=version)
        elif "previous jobs" == source:
            job = self._data[selected[0]]
            self["title"].configure(text=job["title"])
            self["description"].delete("1.0", "end")
            self["description"].insert("1.0", job["description"])
        elif source == "local files":
            self["title"].configure(text="")
            self["description"].delete("1.0", "end")
            self["version"].configure(text="")
            path = self._data[selected[0]]
            if path.suffix == ".flow":
                capture = False
                lines = []
                with path.open() as fd:
                    for line in fd:
                        line = line.strip()
                        if line[0] == "#":
                            if line == "#metadata":
                                capture = True
                            elif capture:
                                break
                        elif capture:
                            lines.append(line)
                if len(lines) > 0:
                    mtime = path.stat().st_mtime
                    date = datetime.datetime.fromtimestamp(mtime).isoformat(" ")
                    data = json.loads("\n".join(lines))
                    if "title" in data:
                        self["title"].configure(text=data["title"])
                    if "description" in data:
                        self["description"].insert("1.0", data["description"])
                    if "version" in data:
                        line = f"Version {data['version']} -- {date}"
                    else:
                        line = f"Version <none> -- {date}"
                    self["version"].configure(text=line)
        else:
            raise RuntimeError(f"Can't handle source '{source}'")

    def update_dashboard(self, event=None):
        """The dashboard has been changed!"""

        dashboard = self["dashboard"].get()
        project = self["project"].get()

        if dashboard != self.current_dashboard.name:
            projects = ["any"]
            try:
                dashboard = self.dashboard_handler.get_dashboard(dashboard)
                self._projects = self.current_dashboard.projects()
                projects += [*self._projects.keys()]
            except DashboardConnectionError:
                self.dashboards.remove(dashboard)
                self["dashboard"].config(values=self.dashboards, state="readonly")
                self["dashboard"].set(self.current_dashboard.name)
                tk.messagebox.showwarning(
                    title="Cannot access Dashboard",
                    message=f"Cannot access Dashboard {dashboard}. Resetting!",
                )
            else:
                self.current_dashboard = dashboard
                self["project"].config(values=projects, state="readonly")

                if self.current_project is None or project not in projects:
                    self.current_project = projects[0]
                self["project"].set(self.current_project)
        elif project != self.current_project:
            self.current_project = project

        self.clear_tree()
        # Get the jobs from the Dashboard.
        if self.current_project == "any":
            job_list = self.current_dashboard.jobs()
        else:
            job_list = self._projects[self.current_project].jobs()
        self.fill_tree(job_list)

    def zenodo_callback(self, widget, criterion, event, what):
        if criterion is not None:
            inclusion, field, operator, value, value2 = criterion.get()

            if what == "field":
                operators = zenodo_fields[field]["operators"]
                w = criterion.operator
                w.configure(values=operators)
                if operator in operators:
                    w.set(operator)
                else:
                    w.set(operators[0])
