# -*- coding: utf-8 -*-

"""The GUI for publishing -- flowcharts for the moment."""

import collections.abc
import logging
import tkinter as tk
import tkinter.ttk as ttk

import Pmw

import seamm_util
import seamm_widgets as sw

logger = logging.getLogger(__name__)


class TkPublish(collections.abc.MutableMapping):
    def __init__(self, tk_flowchart):
        self.tk_flowchart = tk_flowchart
        self._widgets = {"parent": tk_flowchart.pw}

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

    def create_dialog(self):
        """Create the dialog for publishing."""
        if "dialog" in self:
            return

        toplevel = self["parent"].winfo_toplevel()
        self["dialog"] = d = Pmw.Dialog(
            toplevel,
            buttons=("Publish", "Cancel"),
            master=toplevel,
            title="Publish the flowchart",
        )
        d.withdraw()

        frame = self["frame"] = d.interior()
        # P = self.parameters
        # for item in ("what", "destination"):
        #     self[item] = P[item].widget(frame)

        w = self["what"] = sw.LabeledCombobox(
            frame,
            labeltext="Publish the",
            values=("flowchart",),
            state="readonly",
        )
        w.set("flowchart")

        w = self["destination"] = sw.LabeledCombobox(
            frame,
            labeltext="to",
            values=("Zenodo", "Zenodo sandbox"),
            state="readonly",
        )
        w.set("Zenodo")

        for item in ("what",):
            self[item].bind("<<ComboboxSelected>>", self.reset_dialog)
            self[item].bind("<Return>", self.reset_dialog)
            self[item].bind("<FocusOut>", self.reset_dialog)

        # Need the start node for editing the flowchart metadata
        start_node = self.tk_flowchart.get_node("1")
        self["flowchart metadata"] = start_node.create_frame(frame)

        self["doi"] = ttk.Label(frame, text="")

        self.reset_dialog()

    def edit(self):
        """Present a dialog for editing the parameters."""
        # Create the dialog if it doesn't exist
        self.create_dialog()

        # update the flowchart metadata
        start_node = self.tk_flowchart.get_node("1")
        start_node.update_widgets()

        self.reset_dialog()

        # And put it on-screen, the first time centered.
        result = self["dialog"].activate(geometry="centerscreenfirst")

        if result != "Publish":
            # Reset everything!
            start_node.cleanup_authors()
        else:
            # Handle the metadata first
            start_node.capture_metadata()
            start_node.cleanup_authors()

            # Capture the parameters from the widgets
            what = self["what"].get()
            destination = self["destination"].get()

            if what == "flowchart":
                if destination == "Zenodo":
                    doi = self.publish_flowchart_to_zenodo()
                elif destination == "Zenodo sandbox":
                    doi = self.publish_flowchart_to_zenodo(sandbox=True)
                else:
                    raise RuntimeError(f"cannot handle destination '{destination}'")
                tk.messagebox.showinfo(
                    master=self["parent"],
                    title="Published",
                    message=f"Published the {what} to {destination}\nDOI = {doi}",
                )
            else:
                raise RuntimeError(f"cannot handle publishing '{what}'")

    def reset_dialog(self):
        """Layout the widgets in the dialog according to the parameters."""

        what = self["what"].get()

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
        self["what"].grid(row=row, column=0, sticky=tk.EW)
        row += 1
        self["destination"].grid(row=row, column=0, sticky=tk.EW)
        row += 1

        if what == "flowchart":
            self["flowchart metadata"].grid(row=row, column=0, sticky=tk.EW)
            row += 1

            self["doi"].grid(row=row, column=0, sticky=tk.W)
            row += 1
            metadata = self.tk_flowchart.flowchart.metadata
            if "doi" in metadata:
                self["doi"]["text"] = metadata["doi"]
            else:
                self["doi"]["text"] = "not published"

    def publish_flowchart_to_zenodo(self, sandbox=False):
        """Publish the flowchart to Zenodo.

        Parameters
        ----------
        sandbox : bool = False
            If true, publish to the Zenodo sandbox.

        Returns
        -------
        str
            The DOI.
        """
        flowchart = self.tk_flowchart.flowchart

        # Get check if the flowchart is fully released
        if sandbox:
            if flowchart.is_development:
                print("Publishing a dirty version to the Zenodo sandbox.")
                logger.warning("Publishing a dirty version to the Zenodo sandbox.")
        else:
            if flowchart.is_development:
                return None

        zenodo = seamm_util.Zenodo(use_sandbox=sandbox)

        # If this flowchart has an existing DOI, create a new version.
        metadata = flowchart.metadata
        if "doi" in metadata:
            _id = metadata["doi"].split("/zenodo.")[1]
            record = zenodo.add_version(_id)
            for filename in record.files():
                record.remove_file(filename)
        else:
            record = zenodo.create_record()

        # Set up the metadata for Zenodo.
        record.upload_type = "other"
        record.creators = metadata["creators"]
        record.title = metadata["title"]
        record.description = metadata["description"]
        record.keywords = ["seamm-flowchart", *metadata["keywords"]]

        # Update the metadata at Zenodo
        record.update_metadata()

        # Update the metadata in the flowchart
        metadata["doi"] = record.doi
        conceptdoi = record.conceptdoi
        if conceptdoi is not None:
            metadata["conceptdoi"] = conceptdoi

        # Now we can add the flowchart to Zenodo with the correct DOI, etc.
        record.add_file("flowchart.flow", contents=flowchart.to_text())

        # And, finally, can publish!
        record.publish()

        return record.doi
