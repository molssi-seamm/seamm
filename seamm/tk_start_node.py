# -*- coding: utf-8 -*-

"""The start node in a flowchart"""

import copy
import tkinter as tk
import tkinter.ttk as ttk

import seamm
import seamm_widgets as sw


class TkStartNode(seamm.TkNode):
    """The Tk-based graphical representation of a Start node"""

    anchor_points = {
        "s": (0, 0.5),
        "e": (0.5, 0.0),
        "w": (-0.5, 0.0),
    }

    def __init__(
        self, tk_flowchart=None, node=None, canvas=None, x=150, y=50, w=200, h=50
    ):
        """Initialize a node

        Keyword arguments:
        """
        super().__init__(
            tk_flowchart=tk_flowchart, node=node, canvas=canvas, x=x, y=y, w=w, h=h
        )

        # Temporary storage for authors
        self._author_data = []

    def right_click(self, event):
        """Display the properties of the flowchart."""
        if self.popup_menu is not None:
            self.popup_menu.destroy()

        self.popup_menu = tk.Menu(self.canvas, tearoff=0)
        self.popup_menu.add_command(label="Edit..", command=self.edit)

    def edit(self):
        """Present a dialog for editing this step's parameters.

        Subclasses can override this.
        """
        # Create the dialog if it doesn't exist
        if self.dialog is None:
            self.create_dialog()
            # After full creation, reset the dialog. This may do nothing,
            # or may layout the widgets, but can only be done after fully
            # creating the dialog.
            self.reset_dialog()
            # And resize the dialog to fit...
            self.fit_dialog()

        self.update_widgets()

        # And put it on-screen, the first time centered.
        result = self.dialog.activate(geometry="centerscreenfirst")

        if result == "OK":
            self.capture_metadata()
        self.cleanup_authors()

    def update_widgets(self):
        """Put the correct metadata into the widgets."""
        # Update the widgets with the current metadata from the flowchart
        metadata = self.tk_flowchart.flowchart.metadata

        self["title"].set(metadata["title"])
        self["description"].delete("1.0", tk.END)
        self["description"].insert("1.0", metadata["description"])
        self["keywords"].set(", ".join(metadata["keywords"]))

        # layout the authors
        self._author_data = copy.deepcopy(metadata["creators"])
        self.layout_authors()

    def cleanup_authors(self):
        """Destroy the internal widgets and reset the internal author data."""
        for data in self._author_data:
            for w in data["widgets"].values():
                w.destroy()
        self._author_data = []

    def capture_metadata(self):
        """Capture the metadata from the widgets and put to the flowchart."""
        metadata = self.tk_flowchart.flowchart.metadata

        metadata["title"] = self["title"].get()
        metadata["description"] = self["description"].get("1.0", tk.END)

        keywords = [x.strip() for x in self["keywords"].get().split(",")]
        if "seamm-flowchart" in keywords:
            keywords.remove("seamm-flowchart")
        metadata["keywords"] = keywords

        authors = []
        for data in self._author_data:
            w = data["widgets"]
            tmp = {}
            for item in ("name", "orcid", "affiliation"):
                value = w[item].get().strip()
                if value != "":
                    tmp[item] = value
            if len(tmp) > 0:
                authors.append(tmp)
        metadata["creators"] = authors

    def create_dialog(self):
        """Create a dialog for editing the flowchart properties."""
        frame = super().create_dialog("Flowchart Properties")

        f = self.create_frame(frame)
        f.grid(row=0, column=0, sticky=tk.NSEW)
        f.rowconfigure(0, weight=1)
        f.columnconfigure(0, weight=1)

    def create_frame(self, parent_widget):
        """Create a frame for editing the flowchart properties."""

        frame = self["inner frame"] = ttk.Frame(parent_widget)

        # Create the widgets and grid them in
        row = 0

        # title
        w = self["title"] = sw.LabeledEntry(frame, labeltext="Title:", width=100)
        w.grid(row=row, column=0, sticky=tk.EW)
        row += 1

        # description
        w = self["description label"] = ttk.Label(frame, text="Description")
        w.grid(row=row, column=0)
        row += 1

        w = self["description frame"] = sw.ScrolledFrame(
            frame, scroll_vertically=True, borderwidth=2, relief=tk.SUNKEN
        )
        w.grid(row=row, column=0, sticky=tk.NSEW)
        row += 1

        f = w.interior()
        w = self["description"] = tk.Text(f, wrap=tk.WORD, font=("Helvetica",))
        w.grid(sticky=tk.NSEW)
        f.rowconfigure(0, weight=1)
        f.columnconfigure(0, weight=1)

        # keywords
        w = self["keywords"] = sw.LabeledEntry(
            frame, labeltext="Keywords (comma separated):", width=100
        )
        w.grid(row=row, column=0, sticky=tk.EW)
        row += 1

        # authors
        w = self["authors label"] = ttk.Label(frame, text="Authors")
        w.grid(row=row, column=0)
        row += 1

        w = self["authors frame"] = sw.ScrolledFrame(
            frame, scroll_vertically=True, borderwidth=2, relief=tk.SUNKEN
        )
        w.grid(row=row, column=0, sticky=tk.NSEW)
        row += 1

        f = w.interior()
        self["name label"] = ttk.Label(f, text="Name (last, others)")
        self["orcid label"] = ttk.Label(f, text="ORCID")
        self["affiliation label"] = ttk.Label(f, text="Affiliation")

        frame.columnconfigure(0, weight=1)

        return frame

    def draw(self):
        """Draw the node on the given canvas, making it visible"""

        # the outline
        x0 = self.x - self.w / 2
        x1 = x0 + self.w
        y0 = self.y - self.h / 2
        y1 = y0 + self.h
        self.border = self.canvas.create_oval(
            x0,
            y0,
            x1,
            y1,
            tags=[self.tag, "type=outline"],
            fill="white",
        )

        # the label in the middle
        self.title_label = self.canvas.create_text(
            self.x, self.y, text=self.title, tags=[self.tag, "type=title"]
        )

    def handle_dialog(self, result):
        self.dialog.deactivate(result)

    def layout_authors(self):
        """Layout the table of authors."""

        frame = self["authors frame"].interior()

        # Unpack any widgets
        for slave in frame.grid_slaves():
            slave.grid_forget()

        # Put in the column headers.
        row = 0
        self["name label"].grid(row=row, column=1)
        self["orcid label"].grid(row=row, column=2)
        self["affiliation label"].grid(row=row, column=3)
        row += 1

        for data in self._author_data:
            name = data["name"]
            orcid = data.get("orcid", "")
            affiliation = data.get("affiliation", "")
            if "widgets" not in data:
                widgets = data["widgets"] = {}
            else:
                widgets = data["widgets"]

            if "remove" not in widgets:
                # The button to remove a row...
                widgets["remove"] = ttk.Button(
                    frame,
                    text="-",
                    width=2,
                    command=lambda row=row: self.remove_author(row),
                    takefocus=True,
                )

            if "name" not in widgets:
                # the authors name
                widgets["name"] = ttk.Entry(frame, width=50, takefocus=True)
                widgets["name"].insert("end", name)

            if "orcid" not in widgets:
                # The author's ORCID id
                widgets["orcid"] = ttk.Entry(frame, width=20, takefocus=True)
                widgets["orcid"].insert("end", orcid)

            if "affiliation" not in widgets:
                # The author's affiliation
                widgets["affiliation"] = ttk.Entry(frame, width=50, takefocus=True)
                widgets["affiliation"].insert("end", affiliation)

            widgets["remove"].grid(row=row, column=0, sticky=tk.W)
            widgets["name"].grid(row=row, column=1, stick=tk.EW)
            widgets["orcid"].grid(row=row, column=2, stick=tk.EW)
            widgets["affiliation"].grid(row=row, column=3, stick=tk.EW)

            row += 1

        # The button to add a row...
        if "add author" not in self:
            w = self["add author"] = ttk.Button(
                frame,
                text="+",
                width=5,
                command=self.add_author,
                takefocus=True,
            )
            w.focus_set()
        else:
            w = self["add author"]
        w.lift()
        w.grid(row=row, column=0, columnspan=3, sticky=tk.W)

        frame.grid_columnconfigure(3, weight=1)

    def add_author(self):
        """Add a new row to the author table."""
        self._author_data.append({"name": "", "orcid": "", "affiliation": ""})
        self.layout_authors()

    def remove_author(self, row):
        """Remove a author entry from the table.

        Parameters
        ----------
        row : int
            The row in the table to remove. Note the first author is at row 1.
        """
        index = row - 1
        data = self._author_data[index]
        if "widgets" in data:
            for w in data["widgets"].values():
                w.destroy()
        del self._author_data[index]

        self.layout_authors()
