# -*- coding: utf-8 -*-

import abc
import copy
import logging
import seamm
import pprint  # noqa: F401
import tkinter as tk
"""A graphical node using Tk on a canvas"""

logger = logging.getLogger(__name__)


class TkNode(abc.ABC):
    """The abstract base class for all Tk-based nodes"""

    anchor_points = {
        's': (+0.00, +0.50),
        'sse': (+0.25, +0.50),
        'se': (+0.50, +0.50),
        'ese': (+0.50, +0.25),
        'e': (+0.50, +0.00),
        'ene': (+0.50, -0.25),
        'ne': (+0.50, -0.50),
        'nne': (+0.25, -0.50),
        'n': (+0.00, -0.50),
        'nnw': (-0.25, -0.50),
        'nw': (-0.50, -0.50),
        'wnw': (-0.50, -0.25),
        'w': (-0.50, +0.00),
        'wsw': (-0.50, +0.25),
        'sw': (-0.50, +0.50),
        'ssw': (-0.25, +0.50)
    }

    def __init__(
        self,
        tk_flowchart=None,
        node=None,
        canvas=None,
        x=None,
        y=None,
        w=None,
        h=None
    ):
        """Initialize a node

        Keyword arguments:
        """
        self.tk_flowchart = tk_flowchart
        self.node = node
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

        self.node_type = 'simple'

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

    def __hash__(self):
        """Make iterable!"""
        return self.node.uuid

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

    def __contains__(self, item):
        """Return a boolean indicating if a widget exists."""
        return item in self._widget

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
            self.canvas.itemconfigure(self.border, outline='red')
        else:
            self.canvas.itemconfigure(self.border, outline='black')

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

    def draw(self):
        """Draw the node on the given canvas, making it visible"""

        # Remove any graphics items
        self.undraw()

        # the outline
        x0 = self.x - self.w / 2
        x1 = x0 + self.w
        y0 = self.y - self.h / 2
        y1 = y0 + self.h
        self._border = self.canvas.create_rectangle(
            x0,
            y0,
            x1,
            y1,
            tags=[self.tag, 'type=outline'],
            fill='white',
        )

        # the label in the middle
        self.title_label = self.canvas.create_text(
            self.x, self.y, text=self.title, tags=[self.tag, 'type=title']
        )

        for direction, edge in self.connections():
            edge.move()

    def undraw(self):
        """Remove all of our visual components
        """

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
            label="Delete",
            command=lambda: self.tk_flowchart.remove_node(self)
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

        self.canvas.delete(self.tag + ' && type=anchor')
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
                fill='red',
                outline='red',
                tags=[self.tag, 'type=anchor', 'anchor=' + pt]
            )

    def deactivate(self):
        """Remove the decorations indicate the anchor points
        """

        self.canvas.delete(self.tag + ' && type=anchor')
        self.canvas.delete(self.tag + ' && type=active_anchor')

    def anchor_point(self, anchor="all"):
        """Where the anchor points are located. If "all" is given
        a dictionary of all points is returned"""

        if anchor == "all":
            result = []
            for pt in type(self).anchor_points:
                a, b = type(self).anchor_points[pt]
                result.append(
                    (pt, int(self.x + a * self.w), int(self.y + b * self.h))
                )
            return result

        if anchor in type(self).anchor_points:
            a, b = type(self).anchor_points[anchor]
            return (int(self.x + a * self.w), int(self.y + b * self.h))

        raise NotImplementedError(
            "anchor position '{}' not implemented".format(anchor)
        )

    def check_anchor_points(self, x, y, halo):
        """If the position x, y is within halo or one of the anchor points
        activate the point and return the name of the anchor point
        """

        points = []
        for direction, edge in self.connections():
            if direction == 'out':
                points.append(edge.anchor1)
            else:
                points.append(edge.anchor2)

        for point, x0, y0 in self.anchor_point():
            if x >= x0 - halo and x <= x0 + halo and \
               y >= y0 - halo and y <= y0 + halo:
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
            fill='red',
            outline='red',
            tags=[self.tag, 'type=active_anchor', 'anchor=' + point]
        )

    def remove_edge(self, edge):
        """Remove a given edge, or all edges if 'all' is given
        """

        if isinstance(edge, str) and edge == 'all':
            for direction, obj in self.connections():
                self.remove_edge(obj)
        else:
            self.tk_flowchart.graph.remove_edge(
                edge.node1, edge.node2, edge.edge_type, edge.edge_subtype
            )

    def edit(self):
        """Do-nothing base class method"""
        pass

    def to_dict(self):
        """Serialize to a dict"""
        data = {
            'x': self._x,
            'y': self._y,
            'w': self._w,
            'h': self._h,
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
                if key not in (
                    'node1', 'node2', 'edge_type', 'edge_subtype', 'canvas'
                ):
                    attr[key] = edge[key]
            node1 = translate[edge.node1]
            node2 = translate[edge.node2]
            flowchart.add_edge(
                node1, node2, edge.edge_type, edge.edge_subtype, **attr
            )

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
                translate[node] = tk_flowchart.get_node('1')
            else:
                new_node = copy.copy(node)
                logger.debug('creating {} node'.format(extension))
                plugin = tk_flowchart.plugin_manager.get(extension)
                logger.debug('  plugin object: {}'.format(plugin))
                tk_node = plugin.create_tk_node(
                    tk_flowchart=tk_flowchart,
                    canvas=tk_flowchart.canvas,
                    node=new_node
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
                if key not in ('node1', 'node2'):
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
        n_edges = len(self.tk_flowchart.edges(self, direction='out'))

        logger.debug('node.default_edge_label, n_edges = {}'.format(n_edges))

        if n_edges == 0:
            return "next"
        else:
            return "too many"

    def next_anchor(self):
        """Return where the next node should be positioned. The default is
        <gap> below the 's' anchor point.
        """

        return 's'
