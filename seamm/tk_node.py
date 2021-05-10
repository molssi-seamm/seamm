# -*- coding: utf-8 -*-

import collections.abc
import copy
import logging
import json
import Pmw
import seamm
import seamm_widgets as sw
import tkinter as tk
import tkinter.ttk as ttk

"""A graphical node using Tk on a canvas"""

logger = logging.getLogger(__name__)


class TkNode(collections.abc.MutableMapping):
    """The abstract base class for all Tk-based nodes"""

    anchor_points = {
        "s": (+0.00, +0.50),
        "sse": (+0.25, +0.50),
        "se": (+0.50, +0.50),
        "ese": (+0.50, +0.25),
        "e": (+0.50, +0.00),
        "ene": (+0.50, -0.25),
        "ne": (+0.50, -0.50),
        "nne": (+0.25, -0.50),
        "n": (+0.00, -0.50),
        "nnw": (-0.25, -0.50),
        "nw": (-0.50, -0.50),
        "wnw": (-0.50, -0.25),
        "w": (-0.50, +0.00),
        "wsw": (-0.50, +0.25),
        "sw": (-0.50, +0.50),
        "ssw": (-0.25, +0.50),
    }

    def __init__(
        self,
        tk_flowchart=None,
        node=None,
        node_type="simple",
        canvas=None,
        x=None,
        y=None,
        w=None,
        h=None,
        my_logger=logger,
        keyword_metadata=None,
        keywords=None,
    ):
        """Initialize a node

        Keyword arguments:
        """
        self.logger = my_logger
        self.tk_flowchart = tk_flowchart
        self.tk_subflowchart = None
        self.node = node
        self._keyword_metadata = keyword_metadata
        self.toplevel = None
        self.canvas = canvas

        if self.node is not None:
            if self.node.x is None:
                self.node.x = x
            if self.node.y is None:
                self.node.y = y
            if self.node.w is None:
                self.node.w = w
            if self.node.h is None:
                self.node.h = h

        self.node_type = node_type

        self._border = None
        self.title_label = None
        self._selected = False
        self.popup_menu = None
        self._tmp = None
        self.dialog = None
        self.previous_grab = None

        # Widget information
        self._widget = {}
        self.tk_var = {}
        self.results_widgets = None

    def __hash__(self):
        """Make iterable!"""
        return self.node.uuid

    def __eq__(self, other):
        return self.__class__ == other.__class__ and self.__hash__() == other.__hash__()

    # Provide dict like access to the widgets to make
    # the code cleaner

    def __getitem__(self, key):
        """Allow [] access to the widgets!"""
        return self._widget[key]

    def __setitem__(self, key, value):
        """Allow x[key] access to the data"""
        self._widget[key] = value

    def __delitem__(self, key):
        """Allow deletion of keys"""
        if key in self._widget:
            self._widget[key].destroy()
        del self._widget[key]

    def __iter__(self):
        """Allow iteration over the object"""
        return iter(self._widget)

    def __len__(self):
        """The len() command"""
        return len(self._widget)

    @property
    def uuid(self):
        """The uuid of the node"""
        return self.node.uuid

    @property
    def title(self):
        """The title to display"""
        return self.node.title

    @title.setter
    def title(self, value):
        self.node.title = value
        if self.title_label is not None:
            self.canvas.itemconfigure(self.title_label, text=value)

    @property
    def tag(self):
        """The string representation of the uuid of the node"""
        return self.node.tag

    @property
    def flowchart(self):
        """The flowchart object"""
        return self.node.flowchart

    @flowchart.setter
    def flowchart(self, value):
        """The flowchart object"""
        self.node.flowchart = value

    @property
    def x(self):
        """The x-position of the center of the graphical node"""
        return self.node.x

    @x.setter
    def x(self, value):
        self.node.x = value

    @property
    def y(self):
        """The y-position of the center of the graphical node"""
        return self.node.y

    @y.setter
    def y(self, value):
        self.node.y = value

    @property
    def w(self):
        """The width of the graphical node"""
        return self.node.w

    @w.setter
    def w(self, value):
        self.node.w = value

    @property
    def h(self):
        """The height of the graphical node"""
        return self.node.h

    @h.setter
    def h(self, value):
        self.node.h = value

    def set_uuid(self):
        self.node.set_uuid()

    def connections(self):
        """Return a list of all the incoming and outgoing edges
        for this node, giving the anchor points and other node
        """

        return self.tk_flowchart.edges(self)

    @property
    def selected(self):
        """Whether I am selected or not"""
        return self._selected

    @selected.setter
    def selected(self, value):
        self._selected = value
        if value:
            self.canvas.itemconfigure(self.border, outline="red")
        else:
            self.canvas.itemconfigure(self.border, outline="black")

    @property
    def canvas(self):
        """The canvas for drawing the node"""
        return self._canvas

    @canvas.setter
    def canvas(self, value):
        if value:
            self.toplevel = value.winfo_toplevel()
        self._canvas = value

    @property
    def border(self):
        """The border of the picture in the flowchart"""
        return self._border

    @border.setter
    def border(self, value):
        self._border = value

    @staticmethod
    def is_expr(value):
        """Return whether the value is an expression or constant.

        Parameters
        ----------
        value : str
            The value to test

        Returns
        -------
        bool
           True for an expression, False otherwise.
        """
        return len(value) > 0 and value[0] == "$"

    def draw(self):
        """Draw the node on the given canvas, making it visible"""

        # Remove any graphics items
        self.undraw()

        # the outline
        x0 = self.x - self.w / 2
        x1 = x0 + self.w
        y0 = self.y - self.h / 2
        y1 = y0 + self.h
        self.border = self.canvas.create_rectangle(
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

        for direction, edge in self.connections():
            edge.move()

    def undraw(self):
        """Remove all of our visual components"""

        self.canvas.delete(self.tag)

    def move(self, deltax, deltay):
        if self._tmp is None:
            self._tmp = self.connections()

        self.x += deltax
        self.y += deltay

        self.canvas.move(self.tag, deltax, deltay)

        for connection in self._tmp:
            direction, edge = connection
            edge.move()

    def end_move(self, deltax, deltay):
        self.move(deltax, deltay)
        self._x0 = None
        self._y0 = None
        self._tmp = None

    def right_click(self, event):
        """Do whatever needs to be done for a right-click on this
        item in the flowchart.

        Subclasses should override this as appropriate! The menu
        created in this base method is accessible in subclasses
        which should make it relatively easy to override.
        """

        if self.popup_menu is not None:
            self.popup_menu.destroy()

        self.popup_menu = tk.Menu(self.canvas, tearoff=0)
        self.popup_menu.add_command(
            label="Delete", command=lambda: self.tk_flowchart.remove_node(self)
        )

        if type(self) is seamm.tk_node.TkNode:
            self.popup_menu.tk_popup(event.x_root, event.y_root, 0)

    def double_click(self, event):
        """Do whatever needs to be done for a double-click on this
        item in the flowchart.

        Subclasses should override this as appropriate!
        """

        self.edit()

    def activate(self):
        """Add active handles at the anchor points and change the
        cursor
        """

        self.canvas.delete(self.tag + " && type=anchor")
        for pt, x, y in self.anchor_point("all"):
            x0 = x - 2
            y0 = y - 2
            x1 = x + 2
            y1 = y + 2
            self.canvas.create_oval(
                x0,
                y0,
                x1,
                y1,
                fill="red",
                outline="red",
                tags=[self.tag, "type=anchor", "anchor=" + pt],
            )

    def deactivate(self):
        """Remove the decorations indicate the anchor points"""

        self.canvas.delete(self.tag + " && type=anchor")
        self.canvas.delete(self.tag + " && type=active_anchor")

    def anchor_point(self, anchor="all"):
        """Where the anchor points are located. If "all" is given
        a dictionary of all points is returned"""

        if anchor == "all":
            result = []
            for pt in type(self).anchor_points:
                a, b = type(self).anchor_points[pt]
                result.append((pt, int(self.x + a * self.w), int(self.y + b * self.h)))
            return result

        if anchor in type(self).anchor_points:
            a, b = type(self).anchor_points[anchor]
            return (int(self.x + a * self.w), int(self.y + b * self.h))

        raise NotImplementedError("anchor position '{}' not implemented".format(anchor))

    def check_anchor_points(self, x, y, halo):
        """If the position x, y is within halo or one of the anchor points
        activate the point and return the name of the anchor point
        """

        points = []
        for direction, edge in self.connections():
            if direction == "out":
                points.append(edge.anchor1)
            else:
                points.append(edge.anchor2)

        for point, x0, y0 in self.anchor_point():
            if x >= x0 - halo and x <= x0 + halo and y >= y0 - halo and y <= y0 + halo:
                if point in points:
                    return None
                else:
                    return point
        return None

    def is_inside(self, x, y, halo=0):
        """Return a boolean indicating whether the point x, y is inside
        this node, using halo as a size around the point
        """
        if x < self.x - self.w / 2 - halo:
            return False
        if x > self.x + self.w / 2 + halo:
            return False

        if y < self.y - self.h / 2 - halo:
            return False
        if y > self.y + self.h / 2 + halo:
            return False

        return True

    def activate_anchor_point(self, point, halo):
        """Put a marker on the anchor point to indicate it is
        active
        """

        x, y = self.anchor_point(point)
        self.canvas.create_oval(
            x - halo,
            y - halo,
            x + halo,
            y + halo,
            fill="red",
            outline="red",
            tags=[self.tag, "type=active_anchor", "anchor=" + point],
        )

    def remove_edge(self, edge):
        """Remove a given edge, or all edges if 'all' is given"""

        if isinstance(edge, str) and edge == "all":
            for direction, obj in self.connections():
                self.remove_edge(obj)
        else:
            self.tk_flowchart.graph.remove_edge(
                edge.node1, edge.node2, edge.edge_type, edge.edge_subtype
            )

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

        # And put it on-screen, the first time centered. If it contains
        # a subflowchart, save it so it can be restored on a 'Cancel'
        if self.tk_subflowchart is not None:
            self.tk_subflowchart.push()

        self.dialog.activate(geometry="centerscreenfirst")

    def create_dialog(
        self,
        title="Edit step",
        widget="frame",
        results_tab=False,
    ):
        """Create the base dialog for editing the parameters for a step.

        At the moment I have removed the Help button.
        """
        self.logger.debug("Create dialog in tk_node base class")
        self.dialog = Pmw.Dialog(
            self.toplevel,
            buttons=("OK", "Cancel"),
            master=self.toplevel,
            title=title,
            command=self.handle_dialog,
        )
        self.dialog.withdraw()

        if widget == "frame":
            # Create a frame to hold everything
            frame = ttk.Frame(self.dialog.interior())
            frame.pack(expand=tk.YES, fill=tk.BOTH)
            self["frame"] = frame
            return frame
        elif widget == "notebook" or results_tab or self._keyword_metadata is not None:
            # A tabbed notebook
            notebook = ttk.Notebook(self.dialog.interior())
            notebook.pack(side="top", fill=tk.BOTH, expand=tk.YES)
            self["notebook"] = notebook

            # Main frame holding the widgets
            frame = ttk.Frame(notebook)
            self["frame"] = frame
            notebook.add(frame, text="Parameters", sticky=tk.NW)

        if results_tab:
            # Second tab for results if requested
            rframe = self["results frame"] = ttk.Frame(notebook)
            notebook.add(rframe, text="Results", sticky=tk.NSEW)

            # Shortcut for parameters
            P = self.node.parameters

            var = self.tk_var["create tables"] = tk.IntVar()
            if P["create tables"].value == "yes":
                var.set(1)
            else:
                var.set(0)
            self["create tables"] = ttk.Checkbutton(
                rframe, text="Create tables if needed", variable=var
            )
            self["create tables"].grid(row=0, column=0, sticky=tk.W)

            self["results"] = sw.ScrolledColumns(
                rframe,
                columns=[
                    "Result",
                    "Save",
                    "Variable name",
                    "In table",
                    "Column name",
                ],
            )
            self["results"].grid(row=1, column=0, sticky=tk.NSEW)
            rframe.columnconfigure(0, weight=1)
            rframe.rowconfigure(1, weight=1)

        if self._keyword_metadata is not None:
            # Next tab to handle adding keywords manually
            self.logger.debug("Adding the keyword tab")
            kframe = self["add_to_input"] = ttk.Frame(notebook)
            notebook.add(kframe, text="Add to input", sticky=tk.NSEW)
            self["keywords"] = sw.Keywords(
                kframe,
                metadata=self._keyword_metadata,
                keywords=self.node.parameters["extra keywords"].value,
            )
            self["keywords"].pack(expand="yes", fill="both")

        return frame

    def setup_results(self, properties, calculation="energy", method=None):
        """Layout the results tab of the dialog"""
        results = self.node.parameters["results"].value

        self.results_widgets = []
        table = self["results"]

        table.clear()

        frame = table.interior()

        row = 0
        for key, entry in properties.items():
            if "calculation" not in entry:
                continue
            if calculation not in entry["calculation"]:
                continue
            if "dimensionality" not in entry:
                continue
            if method is not None and "methods" in entry:
                if method not in entry["methods"]:
                    continue

            widgets = []
            widgets.append(key)

            table.cell(row, 0, entry["description"])

            # variable
            var = self.tk_var[key] = tk.IntVar()
            var.set(0)
            w = ttk.Checkbutton(frame, variable=var)
            table.cell(row, 1, w)
            widgets.append(w)
            e = ttk.Entry(frame, width=15)
            e.insert(0, key.lower())
            table.cell(row, 2, e)
            widgets.append(e)

            if key in results:
                if "variable" in results[key]:
                    var.set(1)
                    e.delete(0, tk.END)
                    e.insert(0, results[key]["variable"])

            if entry["dimensionality"] == "scalar":
                # table
                w = ttk.Combobox(frame, width=10)
                table.cell(row, 3, w)
                widgets.append(w)
                e = ttk.Entry(frame, width=15)
                e.insert(0, key.lower())
                table.cell(row, 4, e)
                widgets.append(e)

                if key in results:
                    if "table" in results[key]:
                        w.set(results[key]["table"])
                        e.delete(0, tk.END)
                        e.insert(0, results[key]["column"])
            else:
                widgets.append(None)
                widgets.append(None)

            self.results_widgets.append(widgets)
            row += 1

    def fit_dialog(self):
        """Resize and fit the dialog to the current contents and the
        constraint of the window.
        """
        self.logger.debug("Entering fit_dialog")
        frame = self["frame"]
        frame.update_idletasks()
        width = frame.winfo_width()
        height = frame.winfo_height()
        sw = frame.winfo_screenwidth()
        sh = frame.winfo_screenheight()

        self.logger.debug(
            "  frame wxh = {} x {}, screen = {} x {}".format(width, height, sw, sh)
        )

        mw = 0
        mh = 0
        if "notebook" in self:
            for tab in self["notebook"].tabs():
                widget = frame.nametowidget(tab)
                widget.update_idletasks()
                self.logger.debug("  widget = {}".format(widget))
                ww = widget.winfo_width()
                hh = widget.winfo_height()
                w = widget.winfo_reqwidth()
                h = widget.winfo_reqheight()
                self.logger.debug(
                    "  tab {} wxh = {} x {}, requested = {} x {}".format(
                        tab, ww, hh, w, h
                    )
                )
                if w > mw:
                    mw = w
                if h > mh:
                    mh = h
                if ww > width:
                    width = ww
                if hh > height:
                    height = hh
            # Need to do results again using the inside of the scrolled table..
            if "results" in self:
                widget = self["results"].interior()
                self.logger.debug("  widget = {}".format(widget))
                widget.update_idletasks()
                ww = widget.winfo_width()
                hh = widget.winfo_height()
                w = widget.winfo_reqwidth()
                h = widget.winfo_reqheight()
                self.logger.debug(
                    "  tab {} wxh = {} x {}, requested = {} x {}".format(
                        tab, ww, hh, w, h
                    )
                )
                if w > mw:
                    mw = w
                if h > mh:
                    mh = h
                if ww > width:
                    width = ww
                if hh > height:
                    height = hh
        else:
            mw = frame.winfo_reqwidth()
            mh = frame.winfo_reqheight()
            self.logger.debug("  frame requested = {} x {}".format(mw, mh))

        if width < mw:
            width = mw
        width += 70
        if width + 70 > 0.9 * sw:
            width = int(0.9 * sw)
        if height < mh:
            height = mh
        height += 70
        if height > 0.9 * sh:
            height = int(0.9 * sh)

        self.dialog.geometry("{}x{}".format(width, height))

    def reset_dialog(self, widget=None):
        """Reset the layout of the dialog as needed for the parameters.

        In this base class this does nothing. Override as needed in the
        subclasses derived from this class.
        """
        pass

    def handle_dialog(self, result):
        """Do the right thing when the dialog is closed."""
        if result is None or result == "Cancel":
            self.dialog.deactivate(result)

            # If there is a subflowchart, revert to the saved copy
            if self.tk_subflowchart is not None:
                self.tk_subflowchart.pop()

            # Reset the results widgets if they exist
            if self.results_widgets is not None:
                results = self.node.parameters["results"]["value"]
                self.logger.debug("Resetting results on Cancel")
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug("  results dict\n---------")
                    for key, item in results.items():
                        self.logger.debug(key)
                        self.logger.debug(
                            json.dumps(results[key], sort_keys=True, indent=3)
                        )

                for (
                    key,
                    w_check,
                    w_variable,
                    w_table,
                    w_column,
                ) in self.results_widgets:  # noqa: E501
                    self.logger.debug("  key: {}".format(key))
                    w_variable.delete(0, tk.END)
                    if w_table is not None:
                        w_table.delete(0, tk.END)
                    if w_column is not None:
                        w_column.delete(0, tk.END)
                    if key in results:
                        tmp = results[key]
                        self.logger.debug(
                            "  key dict\n---------\n"
                            + json.dumps(tmp, sort_keys=True, indent=3)
                            + "\n-----"
                        )
                        if "variable" in tmp:
                            self.tk_var[key].set(1)
                            w_variable.insert(0, tmp["variable"])
                        else:
                            self.tk_var[key].set(0)
                            w_variable.insert(0, key.lower())

                        if w_table is not None:
                            if "table" in tmp:
                                w_table.insert(0, tmp["table"])
                                w_column.insert(0, tmp["column"])
                            else:
                                w_table.set("")
                                w_column.insert(0, key.lower())
                    else:
                        self.logger.debug("  resetting widgets")
                        self.tk_var[key].set(0)
                        w_variable.insert(0, key.lower())
                        if w_column is not None:
                            w_column.insert(0, key.lower())

            # Reset the parameters, if any
            if self.node.parameters is not None:
                self.node.parameters.reset_widgets()

            # Reset any keywords
            if "keywords" in self:
                self["keywords"].reset()

            # Reset the layout to make sure it is correct
            self.reset_dialog()

        elif result == "Help":
            self.help()
        elif result == "OK":
            self.dialog.deactivate(result)

            # Capture the parameters from the widgets
            if self.node.parameters is not None:
                self.node.parameters.set_from_widgets()

            # If there is a subflowchart, throw the saved copy away
            if self.tk_subflowchart is not None:
                self.tk_subflowchart.pop_and_discard()

            # Get what results to store, if the results tab exists
            if self.results_widgets is not None:
                # Shortcut for parameters
                P = self.node.parameters

                # and from the results tab...
                if self.tk_var["create tables"].get():
                    P["create tables"].value = "yes"
                else:
                    P["create tables"].value = "no"

                results = P["results"].value = {}
                for (
                    key,
                    w_check,
                    w_variable,
                    w_table,
                    w_column,
                ) in self.results_widgets:  # noqa: E501

                    if self.tk_var[key].get():
                        tmp = results[key] = dict()
                        tmp["variable"] = w_variable.get()
                    if w_table is not None:
                        table = w_table.get()
                        if table != "":
                            if key not in results:
                                tmp = results[key] = dict()
                            tmp["table"] = table
                            tmp["column"] = w_column.get()
            # And any keywords
            if "keywords" in self:
                P = self.node.parameters
                P["extra keywords"].value = self["keywords"].get_keywords()
                self["keywords"].keywords = P["extra keywords"].value
        else:
            self.dialog.deactivate(result)
            raise RuntimeError("Don't recognize dialog result '{}'".format(result))

    def help(self):
        """Base class for presenting help, does nothing.

        Subclasses should override this.
        """
        pass

    def to_dict(self):
        """Serialize to a dict"""
        data = {
            "x": self._x,
            "y": self._y,
            "w": self._w,
            "h": self._h,
        }

        return data

    def update_flowchart(self, tk_flowchart=None, flowchart=None):
        """Update the nongraphical flowchart. Only used in nodes that contain
        flowcharts"""
        if tk_flowchart is None or flowchart is None:
            return

        # Make sure there is nothing in the flowchart
        flowchart.clear(all=True)

        # Add all the non-graphical nodes, making copies so that
        # when the flowchart is cleared our objects still exist
        translate = {}
        for node in tk_flowchart:
            translate[node] = flowchart.add_node(copy.copy(node.node))
            node.update_flowchart()

        # And the edges
        for edge in tk_flowchart.edges():
            attr = {}
            for key in edge:
                if key not in ("node1", "node2", "edge_type", "edge_subtype", "canvas"):
                    attr[key] = edge[key]
            node1 = translate[edge.node1]
            node2 = translate[edge.node2]
            flowchart.add_edge(node1, node2, edge.edge_type, edge.edge_subtype, **attr)

    def from_flowchart(self, tk_flowchart=None, flowchart=None):
        """Recreate the graphics from the non-graphical flowchart.
        Only used in nodes that contain flowchart"""

        if tk_flowchart is None or flowchart is None:
            return

        tk_flowchart.clear()

        # Add all the non-graphical nodes, making copies so that
        # when the flowchart is cleared our objects still exist
        translate = {}
        for node in flowchart:
            extension = node.extension
            if extension is None:
                # Start node
                translate[node] = tk_flowchart.get_node("1")
            else:
                new_node = copy.copy(node)
                self.logger.debug("creating {} node".format(extension))
                plugin = tk_flowchart.plugin_manager.get(extension)
                self.logger.debug("  plugin object: {}".format(plugin))
                tk_node = plugin.create_tk_node(
                    tk_flowchart=tk_flowchart, canvas=tk_flowchart.canvas, node=new_node
                )
                translate[node] = tk_node
                tk_node.from_flowchart()
                tk_flowchart.graph.add_node(tk_node)
                tk_node.draw()

        # And the edges
        for edge in flowchart.edges():
            node1 = translate[edge.node1]
            node2 = translate[edge.node2]
            attr = {}
            for key in edge:
                if key not in ("node1", "node2"):
                    attr[key] = edge[key]
            tk_flowchart.add_edge(node1, node2, **attr)

    def default_edge_subtype(self):
        """Return the default subtype of the edge. Usually this is ''
        but for nodes with two or more edges leaving them, such as a loop, this
        method will return an appropriate default for the current edge. For
        example, by default the first edge emanating from a loop-node is the
        'loop' edge; the second, the 'exit' edge.

        A return value of 'too many' indicates that the node exceeds the number
        of allowed exit edges.
        """

        # how many outgoing edges are there?
        n_edges = len(self.tk_flowchart.edges(self, direction="out"))

        self.logger.debug("node.default_edge_label, n_edges = {}".format(n_edges))

        if n_edges == 0:
            return "next"
        else:
            return "too many"

    def next_anchor(self):
        """Return where the next node should be positioned. The default is
        <gap> below the 's' anchor point.
        """

        return "s"
