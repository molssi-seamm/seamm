# -*- coding: utf-8 -*-

"""The flowchart is a visual representation of a flowchart
drawn on a Tk canvas. The nodes of the graph are shown as
ovals, rectangles, etc. with the edges indicated by arrows
from one node to another.

The outline of a  node has the following Tk tags: ::

    node=xxxxx type=outline

The title: ::

    node=xxxxx type=title

When the mouse is over the node, the anchor points are activated.
They have the following tags: ::

    node=xxxxx type=anchor anchor=<point>

When the mouse is over one of the active anchor points, it is
covered with a larger circle, with tags: ::

    node=xxxxx type=active_anchor anchor=<point>

Edges are indicated by directional arrows between nodes. The
arrows have the following tags: ::

    edge=xxxxx type=arrow

When the mouse if over an arrow, it is shown to be active by placing
two red squares on the base and head of the arrow: ::

    type=arrow_base arrow=<item> edge=xxxxx
    type=arrow_head arrow=<item> edge=xxxxx

Clicking on either of these allows dragging the head or tail to
another anchor point on the same or another node (but not on the
same node as the tail/head for head/tail!). If the arrow is dropped
anywhere else it just snaps back to its original place.
"""

import copy
import logging
import math
import pkg_resources
import pprint  # nopep8
import sys
import tkinter as tk
import tkinter.filedialog as tk_filedialog
import tkinter.ttk as ttk

from PIL import ImageTk, Image

import seamm
from .tk_open import TkOpen
from .tk_publish import TkPublish

logger = logging.getLogger(__name__)


def grey(value):
    return 255 - (255 - value) * 0.1


class TkFlowchart(object):
    def __init__(self, master=None, flowchart=None, namespace="org.molssi.seamm.tk"):
        """Initialize a Flowchart object

        Keyword arguments:
        """

        self.toplevel = None
        self.master = master
        self._flowchart = flowchart
        self.filename = None
        self._stack = []

        self.graph = seamm.Graph()

        # Setup the plugin handling
        self.plugin_manager = seamm.PluginManager(namespace)

        # Job handler
        self._job_handler = seamm.TkJobHandler()

        self.canvas_width = 500
        self.canvas_height = 500
        self.grid_x = 300  # Width of the columns for the step display
        self.grid_y = 70  # Height of the rows for the step display
        self.gap = 50
        self.halo = 8  # How many pixels to consider 'near'
        self.data = None
        self._x0 = None
        self._y0 = None
        self.selection = None
        self.active_nodes = []
        self.in_callback = False
        self.canvas_after_callback = None
        self.popup_menu = None

        # Create the panedwindow
        self.pw = tk.PanedWindow(self.master, orient=tk.HORIZONTAL)
        self.pw.pack(fill=tk.BOTH, expand=1)

        # On the left put the tree of nodes
        self.tree = ttk.Treeview(self.pw)
        self.pw.add(self.tree)
        for group in self.plugin_manager.groups():
            self.tree.insert("", "end", group, text=group)
            for plugin in self.plugin_manager.plugins(group):
                self.tree.insert(group, "end", plugin, text=plugin, tags="node")
        self.tree.tag_bind(
            "node", sequence="<ButtonPress-1>", callback=self.create_node
        )

        # and the main canvas with scrollbars next to the right
        self.canvas_frame = ttk.Frame(self.pw)

        self.canvas_frame.grid_rowconfigure(0, weight=1)
        self.canvas_frame.grid_columnconfigure(0, weight=1)

        self.xscrollbar = tk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL)
        self.xscrollbar.grid(row=1, column=0, sticky=tk.EW)

        self.yscrollbar = tk.Scrollbar(self.canvas_frame)
        self.yscrollbar.grid(row=0, column=1, sticky=tk.NS)

        self.canvas = tk.Canvas(
            self.canvas_frame,
            width=self.canvas_width,
            height=self.canvas_height,
            xscrollcommand=self.xscrollbar.set,
            yscrollcommand=self.yscrollbar.set,
            scrollregion=(0, 0, 2000, 2000),
        )
        self.canvas.grid(row=0, column=0, sticky=tk.NSEW)
        self.xscrollbar.config(command=self.xview)
        self.yscrollbar.config(command=self.yview)

        self.pw.add(self.canvas_frame)

        # Set up scrolling on the canvas with the mouse scrollwheel or similar
        self.canvas.bind("<Enter>", self._bound_to_mousewheel)
        self.canvas.bind("<Leave>", self._unbound_to_mousewheel)

        # background image
        filepath = pkg_resources.resource_filename(__name__, "data/SEAMM.png")
        logger.info(filepath)

        self.image = Image.open(filepath)
        self.prepared_image = Image.eval(self.image.convert("RGB"), grey)
        w, h = self.image.size
        r_w = self.canvas_width / w
        r_h = self.canvas_height / h
        factor = r_w if r_w < r_h else r_h
        w = int(factor * w)
        h = int(factor * h)
        self.working_image = self.prepared_image.resize((w, h))
        self.photo = ImageTk.PhotoImage(self.working_image)
        # self.background = self.canvas.create_image(
        #     self.canvas_width / 2,
        #     self.canvas_height / 2,
        #     image=self.photo,
        #     anchor='center')
        self.background = self.canvas.create_image(
            0, 0, image=self.photo, anchor="center"
        )

        # The gui partner for the start node...
        self.create_start_node()

        # Set up the bindings
        self.canvas.bind("<Configure>", self.canvas_configure)
        self.canvas.bind("<Motion>", self.mouse_motion)
        self.canvas.bind("<ButtonPress-1>", self.click)
        self.canvas.bind("<Double-ButtonPress-1>", self.double_click)
        if sys.platform.startswith("darwin"):
            self.canvas.bind("<ButtonPress-2>", self.right_click)
        else:
            self.canvas.bind("<ButtonPress-3>", self.right_click)

        logger.debug("Finished initializing tk_flowchart")

    def __iter__(self):
        return self.graph.__iter__()

    @property
    def flowchart(self):
        """The flowchart, which holds the nodes"""
        return self._flowchart

    @flowchart.setter
    def flowchart(self, value):
        self._flowchart = value

    @property
    def master(self):
        """The window that is our master"""
        return self._master

    @master.setter
    def master(self, value):
        if value:
            self.toplevel = value.winfo_toplevel()
        self._master = value

    def tag_exists(self, tag):
        """Check if the node with a given tag exists"""
        for node in self:
            if node.tag == tag:
                return True
        return False

    def get_node(self, tag):
        """Return the node with a given tag"""
        if isinstance(tag, int):
            tag = str(tag)
        for node in self:
            if str(node.uuid) == tag:
                return node
        return None

    def last_node(self, tk_node="1"):
        """Find the last node walking down the main execution path
        from the given node, which defaults to the start node"""

        logger.debug("Finding last node")
        # Handle loops!
        for node in self:
            node.node.visited = False
            logger.debug(
                "   reset visited {} {} = {}".format(
                    node.node.visited, node.title, node
                )
            )

        return self.last_node_helper(tk_node)

    def last_node_helper(self, tk_node):
        """Helper routine to handle the recursion"""

        # get the node to start the traversal
        if isinstance(tk_node, str):
            tk_node = self.get_node(tk_node)

        logger.debug(
            "   last tk_node helper: {} {} = {}".format(
                tk_node.node.visited, tk_node.title, tk_node
            )
        )

        tk_node.node.visited = True
        next_tk_node = None
        for edge in self.graph.edges(tk_node, direction="out"):
            if edge.edge_type == "execution":

                if edge.node2.node.visited:
                    logger.debug(
                        "\ttk_node {} {} has been visited".format(
                            edge.node2.title, edge.node2
                        )
                    )
                    next_tk_node = edge.node2
                else:
                    logger.debug(
                        "\trecursing to tk_node {} {}".format(
                            edge.node2.title, edge.node2
                        )
                    )
                    return self.last_node_helper(edge.node2)

        if next_tk_node is not None:
            tk_node = next_tk_node
            logger.debug(
                "\tchecking visited tk_node {} {} for new nodes".format(
                    tk_node.title, tk_node
                )
            )
            if tk_node.node.extension == "Join":
                logger.debug("\t  tk_node is a join node, so look at next")
                for edge in self.graph.edges(tk_node, direction="out"):
                    if edge.edge_type == "execution":
                        logger.debug(
                            "\ttk_node after join node is {} {}".format(
                                edge.node2.title, edge.node2
                            )
                        )
                        tk_node = edge.node2

            for edge in self.graph.edges(tk_node, direction="out"):
                if edge.edge_type == "execution":
                    if edge.node2.node.visited:
                        logger.debug(
                            "\tnode {} {} has been visited".format(
                                edge.node2.title, edge.node2
                            )
                        )
                    else:
                        logger.debug(
                            "\trecursing to tk_node {} {}".format(
                                edge.node2.title, edge.node2
                            )
                        )
                        return self.last_node_helper(edge.node2)

        logger.debug("\treturning {} {}".format(tk_node.title, tk_node))
        return tk_node

    def add_edge(self, u, v, edge_type="execution", edge_subtype="next", **kwargs):
        edge = self.graph.add_edge(
            u,
            v,
            edge_type,
            edge_subtype,
            edge_class=seamm.TkEdge,
            canvas=self.canvas,
            **kwargs,
        )
        edge.draw()
        return edge

    def edges(self, node=None, direction="both"):
        return self.graph.edges(node, direction)

    def new_file(self, event=None):
        self.filename = None
        self.clear()
        # Reset the metadata
        self.flowchart.reset_metadata()

    def help(self, event=None):
        print("Help!!!!")

    def debug(self, event):
        print(event)

    def open_file(self, event=None):
        filename = tk_filedialog.askopenfilename(defaultextension=".flow")
        if filename == "":
            return
        self.open(filename)

    def open(self, filename):
        if isinstance(filename, list):
            filename = filename[0]

        self.flowchart.read(filename)
        self.from_flowchart()
        self.filename = filename

    def flowchart_search(self, event=None):
        """Open a flowchart from Zenodo."""
        opener = TkOpen(self.toplevel)
        data = opener.open()
        if data is not None:
            self.flowchart.from_text(data)
            self.filename = None
            self.from_flowchart()

    def clear(self, all=False):
        """Clear our graphics"""
        for item in self.canvas.find_all():
            if item != self.background:
                self.canvas.delete(item)
        # and the graph
        self.graph.clear()

        # recreate the start node
        if not all:
            self.create_start_node()
            self.draw()

    def create_start_node(self):
        """Create the start node"""
        # Check if the start node exists
        start_node = self.flowchart.get_node("1")
        if start_node is None:
            start_node = seamm.StartNode()

        tk_start_node = seamm.TkStartNode(
            tk_flowchart=self,
            canvas=self.canvas,
            node=start_node,
            x=self.grid_x / 2,
            y=self.grid_y / 2,
        )

        self.graph.add_node(tk_start_node)
        logger.debug(
            "Created start node {} at {}, {}".format(
                tk_start_node, start_node.x, start_node.y
            )
        )
        return tk_start_node

    def properties(self):
        """Get and set the properties of the flowchart."""
        start_node = self.get_node("1")
        start_node.edit()

    def publish(self, event=None):
        """Publish the flowchart to a repository such as Zenodo."""
        self.update_flowchart()

        publisher = TkPublish(self)
        publisher.edit()

    def save(self, event=None):
        if self.filename is None:
            self.save_file()
        else:
            self.update_flowchart()
            self.flowchart.write(self.filename)
            self.flowchart.clear()

    def save_file(self, event=None):
        filename = tk_filedialog.asksaveasfilename(defaultextension=".flow")
        if filename != "":
            # suffixes = pathlib.Path(filename).suffixes
            # if len(suffixes) == 0 or '.flow' not in suffixes:
            #     filename = filename + '.flow'
            self.filename = filename
            self.save()

    def about(self, text="In about"):
        print(text)

    def preferences(self):
        print("In preferences")

    def draw(self):
        for tk_node in self:
            tk_node.draw()

    def canvas_configure(self, event):
        """Redraw the background as the canvas changes size

        Only after the process is idle!
        """
        if self.canvas_after_callback is None:
            self.canvas_after_callback = self.canvas.after_idle(
                self.canvas_configure_doit
            )

    def canvas_configure_doit(self):
        """Redraw the background as the canvas changes size

        This keeps the background image as large as possible and
        centered in the flowchart canvas.
        """
        if self.canvas_after_callback is not None:
            self.canvas.after_cancel(self.canvas_after_callback)
        self.canvas_after_callback = None

        w, h = self.image.size
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()

        r_w = cw / w
        r_h = ch / h
        factor = r_w if r_w < r_h else r_h
        w = int(factor * w)
        h = int(factor * h)

        self.canvas.itemconfigure(self.background, image=None)
        # self.canvas.coords(self.background, cw / 2, ch / 2)
        self.canvas.coords(self.background, 0, 0)
        del self.working_image
        self.working_image = self.prepared_image.resize((w, h))
        del self.photo
        self.photo = ImageTk.PhotoImage(self.working_image)
        # self.canvas.itemconfigure(
        #     self.background, image=self.photo, anchor='center')
        self.canvas.itemconfigure(self.background, image=self.photo, anchor="nw")

    def click(self, event):
        """Handle a left-click on the canvas by finding out what the
        mouse is on/in/near and doing the appropriate thing, such as
        selecting to preparing to move the item.
        """

        cx = int(self.canvas.canvasx(event.x))
        cy = int(self.canvas.canvasy(event.y))
        items = self.canvas.find_closest(cx, cy, self.halo)
        self.selection = []
        for item in items:
            tags = self.get_tags(item)
            if "type" in tags and (
                tags["type"] == "arrow_base" or tags["type"] == "arrow_head"
            ):
                arrow = int(tags["arrow"])
                xys = self.canvas.coords(item)
                x0 = xys[0]
                y0 = xys[1]
                x1 = xys[-2]
                y1 = xys[-1]
                self.data = self.get_tags(arrow)
                self.data["arrow"] = arrow
                self.data.update(self.get_tags(arrow))
                self.data["x0"] = x0
                self.data["y0"] = y0
                self.data["x1"] = x1
                self.data["y1"] = y1
                self._x0 = cx
                self._y0 = cy

                logger.debug("self.data for dragging arrow head or base")
                logger.debug("{}".format(self.data))

                if tags["type"] == "arrow_base":
                    self.data["arrow_base"] = item
                    self.data["arrow_head"] = self.canvas.find_withtag(
                        "type=arrow_head"
                    )
                    self.mouse_op = "drag arrow base"
                    self.canvas.bind("<B1-Motion>", self.drag_arrow_base)
                    self.canvas.bind("<ButtonRelease-1>", self.drop_arrow_base)
                else:
                    self.data["arrow_base"] = self.canvas.find_withtag(
                        "type=arrow_base"
                    )
                    self.data["arrow_head"] = item
                    self.mouse_op = "drag arrow head"
                    self.canvas.bind("<B1-Motion>", self.drag_arrow_head)
                    self.canvas.bind("<ButtonRelease-1>", self.drop_arrow_head)

            if "node" in tags:
                node = tags["node"]
                if tags["type"] == "active_anchor":
                    # Connecting from an anchor to another node
                    x, y = node.anchor_point(tags["anchor"])
                    self.mouse_op = "Connect"
                    arrow = self.canvas.create_line(
                        x, y, cx, cy, arrow=tk.LAST, tags="type=active_arrow"
                    )
                    self.data = (node, tags["anchor"], x, y, arrow)
                    self.canvas.bind("<B1-Motion>", self.drag_arrow)
                    self.canvas.bind("<ButtonRelease-1>", self.drop_arrow)
                else:
                    if node.is_inside(cx, cy, self.halo):
                        self.selection.append(node)
                        node.selected = True
                        self._x0 = cx
                        self._y0 = cy
                        self.mouse_op = "Move"
                        self.canvas.bind("<B1-Motion>", self.move)
                        self.canvas.bind("<ButtonRelease-1>", self.end_move)
                    else:
                        node.selected = False

    def double_click(self, event):
        """Handle a double-click on the canvas by finding out what the
        mouse is on/in/near and doing the appropriate thing.
        """

        cx = int(self.canvas.canvasx(event.x))
        cy = int(self.canvas.canvasy(event.y))
        result = self.find_items(cx, cy)
        self.selection = []
        if result is None:
            # Handle a right-click out side anything
            print("Double-click outside objects")
            return

        if result[0] == "node":
            node = result[1]
            if node.is_inside(cx, cy):
                node.double_click(event)
                return

        if result[0] == "item":
            item = result[1]
            tags = self.get_tags(item)
            if "type" in tags and tags["type"] == "arrow":
                self.right_click_on_arrow(event, item, tags)

    def right_click(self, event):
        """Handle a right-click on the canvas by finding out what the
        mouse is on/in/near and doing the appropriate thing, such as
        posting an action menu
        """

        cx = int(self.canvas.canvasx(event.x))
        cy = int(self.canvas.canvasy(event.y))
        result = self.find_items(cx, cy)
        self.selection = []
        if result is None:
            # Handle a right-click out side anything
            print("Right-click outside objects")
            return

        if result[0] == "node":
            node = result[1]
            if node.is_inside(cx, cy):
                node.right_click(event)
                return

        if result[0] == "item":
            item = result[1]
            tags = self.get_tags(item)
            if "type" in tags and tags["type"] == "arrow":
                self.right_click_on_arrow(event, item, tags)

    def move(self, event):
        """Move selected items"""

        cx = int(self.canvas.canvasx(event.x))
        cy = int(self.canvas.canvasy(event.y))
        deltax = cx - self._x0
        deltay = cy - self._y0

        self._x0 = cx
        self._y0 = cy

        for item in self.selection:
            item.move(deltax, deltay)

    def end_move(self, event):
        """End the move of selected items"""
        self.canvas.bind("<B1-Motion>", "")
        self.canvas.bind("<ButtonRelease-1>", "")

        cx = int(self.canvas.canvasx(event.x))
        cy = int(self.canvas.canvasy(event.y))
        deltax = cx - self._x0
        deltay = cy - self._y0

        for item in self.selection:
            item.end_move(deltax, deltay)
            item.selected = False

        self._x0 = None
        self._y0 = None
        self.mouse_op = None
        self.selection = None

    def create_node(self, event):
        """Create a node using the type in menu. This is a bit tricky because
        we need to create both the node and its graphical partner, each of
        which needs to know the other.
        """

        # not scrolling the left pane yet
        item = self.tree.identify_row(event.y)
        plugin_name = self.tree.item(item, option="text")

        (last_node, x, y, anchor1, anchor2) = self.next_position()
        edge_subtype = last_node.default_edge_subtype()

        logger.debug("creating {} node".format(plugin_name))

        # The node.
        node = self.flowchart.create_node(plugin_name)

        # The graphics partner
        plugin = self.plugin_manager.get(plugin_name)
        logger.debug("  plugin object: {}".format(plugin))
        tk_node = plugin.create_tk_node(
            tk_flowchart=self, canvas=self.canvas, x=0, y=0, node=node
        )
        self.graph.add_node(tk_node)

        # And figure out where the node should be
        # Use the grid approach
        x0 = last_node.x
        y0 = last_node.y

        if anchor1 == "s":
            tk_node.x = x0
            tk_node.y = y0 + self.grid_y
        elif anchor1 == "e":
            tk_node.x = x0 + self.grid_x
            tk_node.y = y0
        else:
            dx, dy = tk_node.anchor_point(anchor2)

            # flip sign to get direction right
            tk_node.x = x - dx
            tk_node.y = y - dy

        # And connect this to the last node in the existing flowchart,
        # which is probably what the user wants.

        self.add_edge(
            last_node,
            tk_node,
            "execution",
            anchor1=anchor1,
            anchor2=anchor2,
            edge_subtype=edge_subtype,
        )

        # And update the picture on screen
        self.draw()

    def remove_node(self, node):
        """Remove the given node"""

        # remove the graphical rendering
        node.undraw()

        # and edges
        node.remove_edge("all")

        # and the node itself
        self.graph.remove_node(node)

    def next_position(self):
        """Find a reasonable place to position the next step
        in the flowchart."""

        last_node = self.last_node()

        # center of node
        x0 = last_node.x
        y0 = last_node.y

        # Get the anchor point the last node wants to use
        anchor1 = last_node.next_anchor()
        # and the inverse for the new node
        anchor2 = anchor1.translate("".maketrans("news", "swen"))

        # Find the point 'gap' past the anchor point of the last
        # node, looking from the center (0, 0)

        x1, y1 = last_node.anchor_point(anchor1)
        dx = x1 - x0
        dy = y1 - y0
        norm = math.sqrt(dx * dx + dy * dy)

        x = x1 + self.gap * (dx / norm)
        y = y1 + self.gap * (dy / norm)

        return (last_node, x, y, anchor1, anchor2)

    def mouse_motion(self, event, exclude=()):
        """Track the mouse and highlight the node under the mouse

        It appears that the canvas find_closest does not work properly in
        Python. Even if you give it a tag to look below, it always returns
        the topmost item, so we cannot loop through items.

        Instead we use find_overlapping, which does return a list. However,
        if the mouse is e.g. inside a rectangle but far enough from the edges
        find_overlapping does not find it. In this case we use the current
        tag to find the object.
        """

        if self.in_callback:
            print("IN CALLBACK!!!!!!")
            return
        self.in_callback = True

        result = None

        self.canvas.delete("type=active_anchor")
        self.canvas.delete("type=arrow_base")
        self.canvas.delete("type=arrow_head")

        cx = int(self.canvas.canvasx(event.x))
        cy = int(self.canvas.canvasy(event.y))

        active = []
        items = self.canvas.find_overlapping(
            cx + self.halo / 2,
            cy + self.halo / 2,
            cx - self.halo / 2,
            cy - self.halo / 2,
        )
        if len(items) == 0:
            # If we are within e.g. a rectangle, it may not overlap
            # but will be the current item, so if nothing overlaps
            # use the current item (if there is one).

            items = self.canvas.find_withtag("current")

        # Loop backwards since the 'top' item is at the end of the list
        # and is probably the item we want.

        for item in items[::-1]:
            if item in exclude:
                continue
            tags = self.get_tags(item)

            # on an arrow?
            if "type" in tags and tags["type"] == "arrow":
                xys = self.canvas.coords(item)
                x0 = xys[0]
                y0 = xys[1]
                x1 = xys[-2]
                y1 = xys[-1]
                self.canvas.create_rectangle(
                    x0 - self.halo / 2,
                    y0 - self.halo / 2,
                    x0 + self.halo / 2,
                    y0 + self.halo / 2,
                    tags=["type=arrow_base", "arrow=" + str(item), tags["edge"].tag()],
                    outline="red",
                    fill="red",
                )
                self.canvas.create_rectangle(
                    x1 - self.halo / 2,
                    y1 - self.halo / 2,
                    x1 + self.halo / 2,
                    y1 + self.halo / 2,
                    tags=["type=arrow_head", "arrow=" + str(item), tags["edge"].tag()],
                    outline="red",
                    fill="red",
                )
                break
            if "node" in tags:
                node = tags["node"]
                if node.is_inside(cx, cy, self.halo):
                    active.append(node)
                    if node not in self.active_nodes:
                        node.activate()
                        self.active_nodes.append(node)
                    # are we close to any anchor points?
                    point = node.check_anchor_points(cx, cy, self.halo)
                    if point is None:
                        self.canvas.delete("type=active_anchor")
                    else:
                        node.activate_anchor_point(point, self.halo)
                        result = (node, point)
                    break

        # deactivate any previously active nodes
        for node in self.active_nodes:
            if node not in active:
                node.deactivate()
        self.active_nodes = active

        self.in_callback = False

        return result

    def find_items(self, x, y, exclude=()):
        """Return the 'top' node under the mouse coordinates x, y

        It appears that the canvas find_closest does not work properly in
        Python. Even if you give it a tag to look below, it always returns
        the topmost item, so we cannot loop through items.

        Instead we use find_overlapping, which does return a list. However,
        if the mouse is e.g. inside a rectangle bat far enough from the edges
        find_overlapping does not find it. In this case we use the current
        tag to find the object.
        """

        items = self.canvas.find_overlapping(
            x + self.halo / 2, y + self.halo / 2, x - self.halo / 2, y - self.halo / 2
        )
        if len(items) == 0:
            # If we are within e.g. a rectangle, it may not overlap
            # but will be the current item, so if nothing overlaps
            # use the current item (if there is one).

            items = self.canvas.find_withtag("current")

        # Loop backwards since the 'top' item is at the end of the list
        # and is probably the item we want.

        for item in items[::-1]:
            if item in exclude:
                continue

            tags = self.get_tags(item)
            if "node" in tags:
                node = tags["node"]
                if node.is_inside(x, y, self.halo):
                    # are we close to any anchor points?
                    point = node.check_anchor_points(x, y, self.halo)
                    return ("node", node, point)
            return ("item", item)
        return None

    def get_tags(self, item):
        """Return the tags of "item" as a dict. Any added tags
        like "active" are added to the "extra" dict entry.
        """

        tags = {}
        tags["extra"] = []
        for x in self.canvas.gettags(item):
            if "=" in x:
                key, value = x.split("=")
                if "node" in key:
                    tags[key] = self.get_node(value)
                elif "edge" == key:
                    tags[key] = seamm.TkEdge.str_to_object[value]
                else:
                    tags[key] = value
            else:
                tags["extra"].append(x)
        return tags

    def drag_arrow(self, event):
        """Drag an arrow from the anchor on the node to the mouse
        Used when creating a new edge.
        """

        logger.debug("drag arrow")
        node, anchor, x, y, arrow = self.data
        cx = int(self.canvas.canvasx(event.x))
        cy = int(self.canvas.canvasy(event.y))
        logger.debug(
            "  x = {}, y = {}, cx = {}, cy = {}, arrow = {}".format(x, y, cx, cy, arrow)
        )
        self.canvas.coords(arrow, x, y, cx, cy)
        # Check for being near another nodes anchor point
        result = self.find_items(cx, cy, exclude=(arrow,))
        logger.debug("  result = {}".format(result))
        if result is not None and result[0] == "node":
            logger.debug("       node = {}".format(node))
            logger.debug("  result[1] = {}".format(result[1]))
            if node == result[1]:
                self.canvas.delete("type=active_anchor")
                logger.debug("  deactivate {}".format(result[1]))
                result[1].deactivate()
            else:
                logger.debug("  activate_node {} {}".format(result[1], result[2]))
                self.activate_node(result[1], result[2])

    def drop_arrow(self, event):
        """The user has dropped a new arrow somewhere!
        If it is on another node, make the connection.
        If it is in empty space or on the original node,
        just cancel the operation.
        """

        self.canvas.bind("<B1-Motion>", "")
        self.canvas.bind("<ButtonRelease-1>", "")

        node, anchor, x, y, arrow = self.data
        cx = int(self.canvas.canvasx(event.x))
        cy = int(self.canvas.canvasy(event.y))
        self.canvas.coords(arrow, x, y, cx, cy)
        # Check for being near another nodes anchor point
        result = self.find_items(cx, cy)
        self.canvas.delete(arrow)

        if result is not None and result[0] == "node":
            other_node, point = result[1:]
            if node != other_node and point is not None:
                edge_subtype = node.default_edge_subtype()
                self.add_edge(
                    node,
                    other_node,
                    "execution",
                    anchor1=anchor,
                    anchor2=point,
                    edge_subtype=edge_subtype,
                )

        self.data = None
        self.mouse_op = None

    def drag_arrow_base(self, event):
        """Drag the base of an exisiting arrow"""

        # move arrow
        cx = int(self.canvas.canvasx(event.x))
        cy = int(self.canvas.canvasy(event.y))
        self.canvas.coords(self.data["arrow"], cx, cy, self.data["x1"], self.data["y1"])

        # move base icon
        deltax = cx - self._x0
        deltay = cy - self._y0

        self._x0 = cx
        self._y0 = cy

        self.canvas.move(self.data["arrow_base"], deltax, deltay)

        # move the label if there is one
        edge = self.data["edge"]
        if edge.has_label:
            self.canvas.coords(
                edge.label_id,
                edge.label_position(cx, cy, self.data["x1"], self.data["y1"]),
            )
            self.canvas.coords(edge.label_bg_id, self.canvas.bbox(edge.label_id))

        # Check for being near another nodes anchor point
        result = self.find_items(
            cx, cy, exclude=(self.data["arrow"], self.data["arrow_base"])
        )

        if result is not None and result[0] == "node":
            self.activate_node(result[1], result[2], exclude=(self.data["edge"].node2,))

    def activate_node(self, node, point=None, exclude=()):
        """Activate a node, i.e. display the anchor points,
        unless it is in the exclusion list. Also, if the
        anchor point is given, make it active.
        """

        active = []
        if node in exclude:
            self.canvas.delete("type=active_anchor")
            node.deactivate()
        else:
            active.append(node)
            if node not in self.active_nodes:
                node.activate()
                self.active_nodes.append(node)
            if point is None:
                self.canvas.delete("type=active_anchor")
            else:
                node.activate_anchor_point(point, self.halo)

        # deactivate any previously active nodes
        for node in self.active_nodes:
            if node not in active:
                node.deactivate()
        self.active_nodes = active

    def drop_arrow_base(self, event):
        """The user has dropped the arrow somewhere!
        If it is on another node, make the connection.
        If it is in empty space or on the original node,
        just cancel the operation.
        """

        self.canvas.bind("<B1-Motion>", "")
        self.canvas.bind("<ButtonRelease-1>", "")

        # Check for being near another nodes anchor point
        cx = int(self.canvas.canvasx(event.x))
        cy = int(self.canvas.canvasy(event.y))
        result = self.find_items(cx, cy)

        edge = self.data["edge"]

        if result is None:
            # dropped on empty space
            self.canvas.delete("type=arrow_base")
            self.canvas.delete("type=arrow_head")
            edge.draw()
        elif result[0] == "node":
            # dropped on another node
            node1, anchor1 = result[1:]
            if edge.node1 == node1:
                edge.anchor1 = anchor1
                edge.draw()
            else:
                # remove current connection and create new, in
                # that order -- otherwise tend to remove edge
                # completely if it is moved on same node.

                node2 = edge.node2
                anchor2 = edge.anchor2
                edge_subtype = edge.edge_subtype

                self.remove_edge(self.data["arrow"])

                self.add_edge(
                    node1,
                    node2,
                    edge_type="execution",
                    edge_subtype=edge_subtype,
                    anchor1=anchor1,
                    anchor2=anchor2,
                )

        self.data = None
        self.mouse_op = None

    def drag_arrow_head(self, event):
        """Drag the head of an arrow"""

        # move arrow
        cx = int(self.canvas.canvasx(event.x))
        cy = int(self.canvas.canvasy(event.y))
        self.canvas.coords(self.data["arrow"], self.data["x0"], self.data["y0"], cx, cy)

        # move base icon
        deltax = cx - self._x0
        deltay = cy - self._y0

        self._x0 = cx
        self._y0 = cy

        self.canvas.move(self.data["arrow_head"], deltax, deltay)

        # move the label if there is one
        edge = self.data["edge"]
        if edge.has_label:
            self.canvas.coords(
                edge.label_id,
                edge.label_position(self.data["x0"], self.data["y0"], cx, cy),
            )
            self.canvas.coords(edge.label_bg_id, self.canvas.bbox(edge.label_id))

        # Check for being near another nodes anchor point
        result = self.find_items(
            cx, cy, exclude=(self.data["arrow"], self.data["arrow_head"])
        )

        if result is not None and result[0] == "node":
            self.activate_node(result[1], result[2], exclude=(self.data["edge"].node1,))

    def drop_arrow_head(self, event):
        """The user has dropped the arrow somewhere!
        If it is on another node, make the connection.
        If it is in empty space or on the original node,
        just cancel the operation.
        """

        self.canvas.bind("<B1-Motion>", "")
        self.canvas.bind("<ButtonRelease-1>", "")

        # Check for being near another nodes anchor point
        cx = int(self.canvas.canvasx(event.x))
        cy = int(self.canvas.canvasy(event.y))
        result = self.find_items(cx, cy)

        edge = self.data["edge"]

        if result is None:
            # dropped on empty space
            self.canvas.delete("type=arrow_base")
            self.canvas.delete("type=arrow_head")
            edge.draw()
        elif result[0] == "node":
            # dropped on another node
            node2, anchor2 = result[1:]
            if edge.node2 == node2:
                edge.anchor2 = anchor2
                edge.draw()
            else:
                # remove current connection and create new, in
                # that order -- otherwise tend to remove edge
                # completely if it is moved on same node.

                node1 = edge.node1
                anchor1 = edge.anchor1

                self.remove_edge(self.data["arrow"])

                self.add_edge(
                    node1, node2, "execution", anchor1=anchor1, anchor2=anchor2
                )

        self.data = None
        self.mouse_op = None

    def right_click_on_arrow(self, event, item, tags):
        """Handle a right click on an arrow"""

        if self.popup_menu is not None:
            self.popup_menu.destroy()

        self.popup_menu = tk.Menu(self.canvas, tearoff=0)
        self.popup_menu.add_command(
            label="Delete", command=lambda: self.remove_edge(item)
        )

        self.popup_menu.tk_popup(event.x_root, event.y_root, 0)

    def remove_edge(self, item):
        """Remove an edge from the graph and visually"""

        tags = self.get_tags(item)
        edge = tags["edge"]
        tag = edge.tag()
        self.graph.remove_edge(
            edge.node1, edge.node2, edge.edge_type, edge.edge_subtype
        )

        # Delete the tag, not item, so that we get all labels, etc.
        self.canvas.delete(tag)
        self.canvas.delete("type=arrow_base")
        self.canvas.delete("type=arrow_head")

    def print_edges(self, event=None):
        """Print all the edges. Useful for debugging!"""

        print("All edges in tk_flowchart")
        for edge in self.edges():
            print(
                "   {} {} {} {} {} {}".format(
                    edge.node1.tag,
                    edge.anchor1,
                    edge.node2.tag,
                    edge.anchor2,
                    edge.edge_type,
                    edge.edge_subtype,
                )
            )

    def print_items(self):
        """Print all the items on the canvas, for debugging"""

        print()
        for item in self.canvas.find_withtag("type=arrow"):
            print("{}: {}".format(item, self.canvas.gettags(item)))

    def run(self, event=None):
        """Run the current flowchart"""

        # Ensure that the flowchart is up-to-date
        flowchart = self.update_flowchart()

        # Do the graphical "stuff"
        self._job_handler.submit_with_dialog(flowchart=flowchart)

    def push(self):
        """Save a copy of the current flowchart on the stack."""
        self.update_flowchart()
        self._stack.append(self.flowchart.to_dict())

    def pop(self):
        """Replace the current flowchart with the version on the stack."""
        self.flowchart.from_dict(self._stack.pop())
        self.from_flowchart()

    def pop_and_discard(self):
        """Remove the saved copy from the stack"""
        self._stack.pop()

    def update_flowchart(self):
        """Update the non-graphical flowchart"""
        wf = self.flowchart

        # Make sure there is nothing in the flowchart
        wf.clear(all=True)

        # Add all the non-graphical nodes, making copies so that
        # when the flowchart is cleared our objects still exist
        translate = {}
        for node in self:
            translate[node] = wf.add_node(copy.copy(node.node))
            node.update_flowchart()

        # And the edges
        for edge in self.edges():
            attr = {}
            for key in edge:
                if key not in ("node1", "node2", "edge_type", "edge_subtype", "canvas"):
                    attr[key] = edge[key]
            node1 = translate[edge.node1]
            node2 = translate[edge.node2]
            wf.add_edge(node1, node2, edge.edge_type, edge.edge_subtype, **attr)

        return wf

    def from_flowchart(self):
        """Recreate the graphics from the non-graphical flowchart"""
        wf = self.flowchart

        self.clear()

        # Add all the non-graphical nodes, making copies so that
        # when the flowchart is cleared our objects still exist
        translate = {}
        for node in wf:
            extension = node.extension
            if extension is None:
                # Start node
                translate[node] = self.get_node("1")
            else:
                new_node = copy.copy(node)
                logger.debug("creating {} node".format(extension))
                plugin = self.plugin_manager.get(extension)
                logger.debug("  plugin object: {}".format(plugin))
                tk_node = plugin.create_tk_node(
                    tk_flowchart=self, canvas=self.canvas, node=new_node
                )
                translate[node] = tk_node
                tk_node.from_flowchart()
                self.graph.add_node(tk_node)
                tk_node.draw()

        # And the edges
        for edge in wf.edges():
            node1 = translate[edge.node1]
            node2 = translate[edge.node2]
            attr = {}
            for key in edge:
                if key not in ("node1", "node2"):
                    attr[key] = edge[key]
            self.add_edge(node1, node2, **attr)

    def _bound_to_mousewheel(self, event):
        """Set the bindings on the canvas, used when the
        mouse enters the canvas
        """
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        # self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        # self.canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _unbound_to_mousewheel(self, event):
        """Remove the bindings on the canvas, used when the
        mouse leaves the canvas
        """
        self.canvas.unbind_all("<MouseWheel>")
        # self.canvas.unbind_all("<Button-4>")
        # self.canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        """Handle the mousewheel or similar events.
        There are two choices for how to scroll, and it
        may differ from OS to OS.

        As set up here on a Mac the mouse drags the canvas in
        the direction of travel, thus to go down in the canvas
        you drag upwards, and vice versa.

        Flip the signs to change this
        """

        if event.num == 5 or event.delta < 0:
            delta = 1
        else:
            delta = -1

        self.canvas.yview_scroll(delta, "units")

        x0, y0, x1, y1 = self.canvas.cget("scrollregion").split(" ")
        f0, f1 = self.canvas.yview()
        y = (int(y1) - int(y0)) * f0

        tk._default_root.tk.call(self.canvas, "moveto", self.background, 0, y)

    def xview(self, command, amount, *args):
        """Scroll in the x direction, keeping the background picture stationary"""
        self.canvas.xview(command, amount, *args)

        x0, y0, x1, y1 = self.canvas.cget("scrollregion").split(" ")
        f0, f1 = self.canvas.xview()
        x = (int(x1) - int(x0)) * f0
        f0, f1 = self.canvas.yview()
        y = (int(y1) - int(y0)) * f0

        tk._default_root.tk.call(self.canvas, "moveto", self.background, x, y)

    def yview(self, command, amount, *args):
        """Scroll in the y direction, keeping the background picture stationary"""
        self.canvas.yview(command, amount, *args)

        x0, y0, x1, y1 = self.canvas.cget("scrollregion").split(" ")
        f0, f1 = self.canvas.xview()
        x = (int(x1) - int(x0)) * f0
        f0, f1 = self.canvas.yview()
        y = (int(y1) - int(y0)) * f0

        tk._default_root.tk.call(self.canvas, "moveto", self.background, x, y)

    def clean_layout(self, event=None):
        """Clean the visual layout of the flowchart"""

        # clear the visited flag
        for node in self:
            node.node.visited = False

        # get the node to start the traversal
        node = self.get_node("1")

        # traverse the nodes, finding what loops they are in
        self._loops = {}  # what loops a node is in
        self._in_loop = {"start": []}  # ordered list of nodes directly in a loop
        loops = tuple()

        self._loop_helper(loops, node)

        logger.debug("\nloops\n\n{}".format(pprint.pformat(self._loops)))
        logger.debug("\nin loops\n\n{}".format(pprint.pformat(self._in_loop)))

        # Move the nodes to the correct place on the grid
        x = 0
        y = 0
        self._loopxy = {"start": (0, 0)}
        self._layout_nodes("start", x, y)

        logger.debug("\nmax x,y\n\n{}".format(pprint.pformat(self._loopxy)))

        # Fix the edges
        for edge in self.edges():
            # only work on edges that go upwards
            x0, y0 = edge.node1.anchor_point(edge.anchor1)
            x1, y1 = edge.node2.anchor_point(edge.anchor2)
            logger.debug("   edge {}: {}, {} to {}, {}".format(edge, x0, y0, x1, y1))
            if y1 < y0:
                edge.coords = [x0, y0]
                logger.debug("   edge.node1 = {}".format(edge.node1))
                loop = self._loops[edge.node1][-1]
                xmax, ymax = self._loopxy[loop]
                xmax = (xmax + 1) * self.grid_x
                ymax = (ymax + 1) * self.grid_y

                dx = 10 * len(self._loops[edge.node1])
                dy = 0

                # Down far enough
                edge.coords.append(x0)
                edge.coords.append(ymax - dy)
                # Right far enough
                edge.coords.append(xmax - dx)
                edge.coords.append(ymax - dy)
                # up
                edge.coords.append(xmax - dx)
                edge.coords.append(y1)
                # and to the node
                edge.coords.append(x1)
                edge.coords.append(y1)
            else:
                edge.coords = [x0, y0, x1, y1]

        # Redraw everything
        self.draw()

        del self._loops
        del self._in_loop
        del self._loopxy

    def _layout_nodes(self, loop, x, y):
        """Recursively position nodes"""
        for node in self._in_loop[loop]:
            x0 = int(node.x)
            y0 = int(node.y)
            node.x = int((x + 0.5) * self.grid_x)
            node.y = int((y + 0.5) * self.grid_y)

            logger.debug(
                "node {} {} = {:3d} {:3d} ({:3d} {:3d}) {}".format(
                    x, y, int(node.x), int(node.y), x0, y0, node
                )
            )

            xmax, ymax = self._loopxy[loop]
            if x > xmax:
                xmax = x
            if y > ymax:
                ymax = y
            self._loopxy[loop] = (xmax, ymax)

            if node in self._in_loop:
                self._loopxy[node] = (x + 1, y)
                x1, y = self._layout_nodes(node, x + 1, y)
                self._loopxy[loop] = (x1, y)
            else:
                y += 1

        return x, y

    def _loop_helper(self, loops, node):
        """A helper to traverse graph finding the grid locations of the nodes"""
        node.node.visited = True
        self._loops[node] = loops

        logger.debug("node = {}, loops = {}".format(node, loops))

        if len(loops) == 0:
            self._in_loop["start"].append(node)
        else:
            self._in_loop[loops[-1]].append(node)

        if node.node_type == "loop":
            loops = loops + (node,)
            self._in_loop[node] = []
            # nodes in the loop
            for edge in self.graph.edges(node, direction="out"):
                if edge.edge_type == "execution" and edge.edge_subtype == "loop":
                    node2 = edge.node2
                    if not node2.node.visited:
                        self._loop_helper(loops, node2)
            loops = loops[0:-1]
            # end exiting the loop
            for edge in self.graph.edges(node, direction="out"):
                if edge.edge_type == "execution" and edge.edge_subtype == "exit":
                    node2 = edge.node2
                    if not node2.node.visited:
                        self._loop_helper(loops, node2)
        else:
            for edge in self.graph.edges(node, direction="out"):
                if edge.edge_type == "execution":
                    node2 = edge.node2
                    if not node2.node.visited:
                        self._loop_helper(loops, node2)
