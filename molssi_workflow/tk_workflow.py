# -*- coding: utf-8 -*-
"""The flowchart is a visual representation of a workflow
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
import molssi_workflow
from PIL import ImageTk, Image
import pkg_resources
import pprint  # nopep8
import sys
import tkinter as tk
import tkinter.filedialog as tk_filedialog
import tkinter.ttk as ttk

logger = logging.getLogger(__name__)


def grey(value):
    return 255 - (255 - value) * 0.1


class TkWorkflow(object):
    def __init__(self,
                 master=None,
                 workflow=None,
                 namespace='org.molssi.workflow.tk'):
        '''Initialize a Flowchart object

        Keyword arguments:
        '''

        self.toplevel = None
        self.master = master
        self._workflow = workflow
        self.filename = None

        self.graph = molssi_workflow.Graph()

        # Setup the plugin handling
        self.plugin_manager = molssi_workflow.PluginManager(namespace)

        self.canvas_width = 500
        self.canvas_height = 500
        self.gap = 20
        self.halo = 5
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
                self.tree.insert(
                    group, "end", plugin, text=plugin, tags="node")
        self.tree.tag_bind(
            "node", sequence="<ButtonPress-1>", callback=self.create_node)

        # and the main canvas next to the right
        self.canvas = tk.Canvas(
            self.pw, width=self.canvas_width, height=self.canvas_height)
        self.pw.add(self.canvas)

        # background image
        filepath = pkg_resources.resource_filename(
            __name__, 'data/framework.png')
        print(filepath)

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
        self.background = self.canvas.create_image(
            self.canvas_width / 2,
            self.canvas_height / 2,
            image=self.photo,
            anchor='center')

        # The gui partner for the start node...
        self.create_start_node()

        # Set up the bindings
        self.canvas.bind('<Configure>', self.canvas_configure)
        self.canvas.bind('<Motion>', self.mouse_motion)
        self.canvas.bind('<ButtonPress-1>', self.click)
        self.canvas.bind('<Double-ButtonPress-1>', self.double_click)
        if sys.platform.startswith('darwin'):
            self.canvas.bind('<ButtonPress-2>', self.right_click)
        else:
            self.canvas.bind('<ButtonPress-3>', self.right_click)

    def __iter__(self):
        return self.graph.__iter__()

    @property
    def workflow(self):
        """The workflow, which holds the nodes"""
        return self._workflow

    @workflow.setter
    def workflow(self, value):
        self._workflow = value

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

    def last_node(self, node='1'):
        """Find the last node walking down the main execution path
        from the given node, which defaults to the start node"""

        if isinstance(node, str):
            node = self.get_node(node)

        for edge in self.graph.edges(node, direction='out'):
            if edge.edge_type == "execution":
                return self.last_node(edge.node2)

        return node

    def add_edge(self, u, v, edge_type='execution', **attr):
        edge = self.graph.add_edge(
            u, v, edge_type, edge_class=molssi_workflow.TkEdge,
            canvas=self.canvas, **attr
        )
        edge.draw()
        return edge

    def edges(self, node=None, direction='both'):
        return self.graph.edges(node, direction)

    def new_file(self, event=None):
        self.filename = None
        self.clear()

    def help(self, event=None):
        print("Help!!!!")

    def debug(self, event):
        print(event)

    def open_file(self, event=None):
        filename = tk_filedialog.askopenfilename(
            defaultextension='.flow'
        )
        if filename == '':
            return
        self.open(filename)

    def open(self, filename):
        if isinstance(filename, list):
            filename = filename[0]

        self.workflow.read(filename)
        self.from_workflow()
        self.filename = filename

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
        start_node = molssi_workflow.StartNode()
        tk_start_node = molssi_workflow.TkStartNode(
            tk_workflow=self, canvas=self.canvas, node=start_node)
        self.graph.add_node(tk_start_node)
        return tk_start_node

    def save(self, event=None):
        if self.filename is None:
            self.save_file()
        else:
            self.update_workflow()
            self.workflow.write(self.filename)
            self.workflow.clear()

    def save_file(self, event=None):
        filename = tk_filedialog.asksaveasfilename(
            defaultextension='.flow'
        )
        if filename != '':
            # suffixes = pathlib.Path(filename).suffixes
            # if len(suffixes) == 0 or '.flow' not in suffixes:
            #     filename = filename + '.flow'
            self.filename = filename
            self.save()

    def about(self, text='In about'):
        print(text)

    def preferences(self):
        print('In preferences')

    def draw(self):
        for tk_node in self:
            tk_node.draw()

    def canvas_configure(self, event):
        """Redraw the background as the canvas changes size

        Only after the process is idle!
        """
        if self.canvas_after_callback is None:
            self.canvas_after_callback = self.canvas.after_idle(
                self.canvas_configure_doit)

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
        self.canvas.coords(self.background, cw / 2, ch / 2)
        del (self.working_image)
        self.working_image = self.prepared_image.resize((w, h))
        del (self.photo)
        self.photo = ImageTk.PhotoImage(self.working_image)
        self.canvas.itemconfigure(
            self.background, image=self.photo, anchor='center')

    def click(self, event):
        """Handle a left-click on the canvas by finding out what the
        mouse is on/in/near and doing the appropriate thing, such as
        selecting to preparing to move the item.
        """

        items = self.canvas.find_closest(event.x, event.y, self.halo)
        self.selection = []
        for item in items:
            tags = self.get_tags(item)
            if 'type' in tags and \
               (tags['type'] == 'arrow_base' or tags['type'] == 'arrow_head'):
                arrow = int(tags['arrow'])
                x0, y0, x1, y1 = self.canvas.coords(arrow)
                self.data = self.get_tags(arrow)
                self.data['arrow'] = arrow
                self.data.update(self.get_tags(arrow))
                self.data['x0'] = x0
                self.data['y0'] = y0
                self.data['x1'] = x1
                self.data['y1'] = y1
                self._x0 = event.x
                self._y0 = event.y
                if tags['type'] == 'arrow_base':
                    self.data['arrow_base'] = item
                    self.data['arrow_head'] = \
                        self.canvas.find_withtag('type=arrow_head')
                    self.mouse_op = 'drag arrow base'
                    self.canvas.bind('<B1-Motion>', self.drag_arrow_base)
                    self.canvas.bind('<ButtonRelease-1>', self.drop_arrow_base)
                else:
                    self.data['arrow_base'] = \
                        self.canvas.find_withtag('type=arrow_base')
                    self.data['arrow_head'] = item
                    self.mouse_op = 'drag arrow head'
                    self.canvas.bind('<B1-Motion>', self.drag_arrow_head)
                    self.canvas.bind('<ButtonRelease-1>', self.drop_arrow_head)

            if 'node' in tags:
                node = tags['node']
                if tags['type'] == 'active_anchor':
                    # Connecting from an anchor to another node
                    x, y = node.anchor_point(tags['anchor'])
                    self.mouse_op = 'Connect'
                    arrow = self.canvas.create_line(
                        x,
                        y,
                        event.x,
                        event.y,
                        arrow=tk.LAST,
                        tags='type=active_arrow')
                    self.data = (node, tags['anchor'], x, y, arrow)
                    self.canvas.bind('<B1-Motion>', self.drag_arrow)
                    self.canvas.bind('<ButtonRelease-1>', self.drop_arrow)
                else:
                    if node.is_inside(event.x, event.y, self.halo):
                        self.selection.append(node)
                        node.selected = True
                        self._x0 = event.x
                        self._y0 = event.y
                        self.mouse_op = 'Move'
                        self.canvas.bind('<B1-Motion>', self.move)
                        self.canvas.bind('<ButtonRelease-1>', self.end_move)
                    else:
                        node.selected = False

    def double_click(self, event):
        """Handle a double-click on the canvas by finding out what the
        mouse is on/in/near and doing the appropriate thing.
        """

        result = self.find_items(event.x, event.y)
        self.selection = []
        if result is None:
            # Handle a right-click out side anything
            print('Double-click outside objects')
            return

        if result[0] == 'node':
            node = result[1]
            if node.is_inside(event.x, event.y):
                node.double_click(event)
                return

        if result[0] == 'item':
            item = result[1]
            tags = self.get_tags(item)
            if 'type' in tags and tags['type'] == 'arrow':
                self.right_click_on_arrow(event, item, tags)

    def right_click(self, event):
        """Handle a right-click on the canvas by finding out what the
        mouse is on/in/near and doing the appropriate thing, such as
        posting an action menu
        """

        result = self.find_items(event.x, event.y)
        self.selection = []
        if result is None:
            # Handle a right-click out side anything
            print('Right-click outside objects')
            return

        if result[0] == 'node':
            node = result[1]
            if node.is_inside(event.x, event.y):
                node.right_click(event)
                return

        if result[0] == 'item':
            item = result[1]
            tags = self.get_tags(item)
            if 'type' in tags and tags['type'] == 'arrow':
                self.right_click_on_arrow(event, item, tags)

    def move(self, event):
        '''Move selected items
        '''

        deltax = event.x - self._x0
        deltay = event.y - self._y0

        self._x0 = event.x
        self._y0 = event.y

        for item in self.selection:
            item.move(deltax, deltay)

    def end_move(self, event):
        '''End the move of selected items
        '''
        self.canvas.bind('<B1-Motion>', '')
        self.canvas.bind('<ButtonRelease-1>', '')

        deltax = event.x - self._x0
        deltay = event.y - self._y0

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

        item = self.tree.identify_row(event.y)
        plugin_name = self.tree.item(item, option="text")

        (last_node, x, y) = self.next_position()

        logger.debug('creating {} node'.format(plugin_name))

        # The node.
        node = self.workflow.create_node(plugin_name)

        # The graphics partner
        plugin = self.plugin_manager.get(plugin_name)
        logger.debug('  plugin object: {}'.format(plugin))
        tk_node = plugin.create_tk_node(
            tk_workflow=self, canvas=self.canvas, x=x, y=y,
            w=200, h=50, node=node
        )
        self.graph.add_node(tk_node)

        # And connect this to the last node in the existing workflow,
        # which is probably what the user wants.

        self.add_edge(
            last_node,
            tk_node,
            'execution',
            anchor1='s',
            anchor2='n'
        )

        # And update the picture on screen
        self.draw()

    def next_position(self):
        """Find a reasonable place to position the next step
        in the flowchart."""

        last_node = self.last_node()
        x0 = last_node.x
        y0 = last_node.y + last_node.h + self.gap

        return (last_node, x0, y0)

    def mouse_motion(self, event, exclude=()):
        """Track the mouse and highlight the node under the mouse

        It appears that the canvas find_closest does not work properly in
        Python. Even if you give it a tag to look below, it always returns
        the topmost item, so we cannot loop through items.

        Instead we use find_overlapping, which does return a list. However,
        if the mouse is e.g. inside a rectangle bat far enough from the edges
        find_overlapping does not find it. In this case we use the current
        tag to find the object.
        """

        if self.in_callback:
            print("IN CALLBACK!!!!!!")
            return
        self.in_callback = True

        result = None

        self.canvas.delete('type=active_anchor')
        self.canvas.delete('type=arrow_base')
        self.canvas.delete('type=arrow_head')

        active = []
        items = self.canvas.find_overlapping(
            event.x + self.halo / 2, event.y + self.halo / 2,
            event.x - self.halo / 2, event.y - self.halo / 2)
        if len(items) == 0:
            # If we are within e.g. a rectangle, it may not overlap
            # but will be the current item, so if nothing overlaps
            # use the current item (if there is one).

            items = self.canvas.find_withtag('current')

        # Loop backwards since the 'top' item is at the end of the list
        # and is probably the item we want.

        for item in items[::-1]:
            if item in exclude:
                continue
            tags = self.get_tags(item)

            # on an arrow?
            if 'type' in tags and tags['type'] == 'arrow':
                x0, y0, x1, y1 = self.canvas.coords(item)
                self.canvas.create_rectangle(
                    x0 - self.halo / 2,
                    y0 - self.halo / 2,
                    x0 + self.halo / 2,
                    y0 + self.halo / 2,
                    tags=[
                        'type=arrow_base', 'arrow=' + str(item),
                        tags['edge'].tag()
                    ],
                    outline='red',
                    fill='red')
                self.canvas.create_rectangle(
                    x1 - self.halo / 2,
                    y1 - self.halo / 2,
                    x1 + self.halo / 2,
                    y1 + self.halo / 2,
                    tags=[
                        'type=arrow_head', 'arrow=' + str(item),
                        tags['edge'].tag()
                    ],
                    outline='red',
                    fill='red')
                break
            if 'node' in tags:
                node = tags['node']
                if node.is_inside(event.x, event.y, self.halo):
                    active.append(node)
                    if node not in self.active_nodes:
                        node.activate()
                        self.active_nodes.append(node)
                    # are we close to any anchor points?
                    point = node.check_anchor_points(
                        event.x, event.y, self.halo)
                    if point is None:
                        self.canvas.delete('type=active_anchor')
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
            x + self.halo / 2, y + self.halo / 2, x - self.halo / 2,
            y - self.halo / 2)
        if len(items) == 0:
            # If we are within e.g. a rectangle, it may not overlap
            # but will be the current item, so if nothing overlaps
            # use the current item (if there is one).

            items = self.canvas.find_withtag('current')

        # Loop backwards since the 'top' item is at the end of the list
        # and is probably the item we want.

        for item in items[::-1]:
            if item in exclude:
                continue

            tags = self.get_tags(item)
            if 'node' in tags:
                node = tags['node']
                if node.is_inside(x, y, self.halo):
                    # are we close to any anchor points?
                    point = node.check_anchor_points(
                        x, y, self.halo)
                    return ('node', node, point)
            return ('item', item)
        return None

    def get_tags(self, item):
        '''Return the tags of "item" as a dict. Any added tags
        like "active" are added to the "extra" dict entry.
        '''

        tags = {}
        tags['extra'] = []
        for x in self.canvas.gettags(item):
            if '=' in x:
                key, value = x.split('=')
                if 'node' in key:
                    tags[key] = self.get_node(value)
                elif 'edge' == key:
                    tags[key] = molssi_workflow.TkEdge.str_to_object[value]
                else:
                    tags[key] = value
            else:
                tags['extra'].append(x)
        return tags

    def drag_arrow(self, event):
        '''Drag an arrow from the anchor on the node to the mouse
        '''

        node, anchor, x, y, arrow = self.data
        self.canvas.coords(arrow, x, y, event.x, event.y)
        # Check for being near another nodes anchor point
        result = self.find_items(event.x, event.y, exclude=(arrow, ))
        if result is not None and result[0] == 'node':
            if node == result[1]:
                self.canvas.delete('type=active_anchor')
                result[1].deactivate()
            else:
                self.activate_node(result[1], result[2])

    def drop_arrow(self, event):
        '''The user has dropped the arrow somewhere!
        If it is on another node, make the connection.
        If it is in empty space or on the original node,
        just cancel the operation.
        '''

        self.canvas.bind('<B1-Motion>', '')
        self.canvas.bind('<ButtonRelease-1>', '')

        node, anchor, x, y, arrow = self.data
        self.canvas.coords(arrow, x, y, event.x, event.y)
        # Check for being near another nodes anchor point
        result = self.find_items(event.x, event.y)
        self.canvas.delete(arrow)

        if result is not None and result[0] == 'node':
            other_node, point = result[1:]
            if node != other_node and point is not None:
                self.add_edge(
                    node,
                    other_node,
                    'execution',
                    anchor1=anchor,
                    anchor2=point
                )

        self.data = None
        self.mouse_op = None

    def drag_arrow_base(self, event):
        '''Drag the base of an arrow
        '''

        # move arrow
        self.canvas.coords(self.data['arrow'], event.x, event.y,
                           self.data['x1'], self.data['y1'])

        # move base icon
        deltax = event.x - self._x0
        deltay = event.y - self._y0

        self._x0 = event.x
        self._y0 = event.y

        self.canvas.move(self.data['arrow_base'], deltax, deltay)

        # Check for being near another nodes anchor point
        result = self.find_items(
            event.x,
            event.y,
            exclude=(self.data['arrow'], self.data['arrow_base']))

        if result is not None and result[0] == 'node':
            self.activate_node(
                result[1],
                result[2],
                exclude=(self.data['edge'].node2, ))

    def activate_node(self, node, point=None, exclude=()):
        '''Activate a node, i.e. display the anchor points,
        unless it is in the exclusion list. Also, if the
        anchor point is given, make it active.
        '''

        active = []
        if node in exclude:
            self.canvas.delete('type=active_anchor')
            node.deactivate()
        else:
            active.append(node)
            if node not in self.active_nodes:
                node.activate()
                self.active_nodes.append(node)
            if point is None:
                self.canvas.delete('type=active_anchor')
            else:
                node.activate_anchor_point(point, self.halo)

        # deactivate any previously active nodes
        for node in self.active_nodes:
            if node not in active:
                node.deactivate()
        self.active_nodes = active

    def drop_arrow_base(self, event):
        '''The user has dropped the arrow somewhere!
        If it is on another node, make the connection.
        If it is in empty space or on the original node,
        just cancel the operation.
        '''

        self.canvas.bind('<B1-Motion>', '')
        self.canvas.bind('<ButtonRelease-1>', '')

        # Check for being near another nodes anchor point
        result = self.find_items(event.x, event.y)

        edge = self.data['edge']

        if result is None:
            # dropped on empty space
            self.canvas.delete('type=arrow_base')
            self.canvas.delete('type=arrow_head')
            edge.draw()
        elif result[0] == 'node':
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

                self.remove_edge(self.data['arrow'])

                self.add_edge(
                    node1,
                    node2,
                    'execution',
                    anchor1=anchor1,
                    anchor2=anchor2
                )

        self.data = None
        self.mouse_op = None

    def drag_arrow_head(self, event):
        '''Drag the head of an arrow
        '''

        # move arrow
        self.canvas.coords(self.data['arrow'], self.data['x0'],
                           self.data['y0'], event.x, event.y)

        # move base icon
        deltax = event.x - self._x0
        deltay = event.y - self._y0

        self._x0 = event.x
        self._y0 = event.y

        self.canvas.move(self.data['arrow_head'], deltax, deltay)

        # Check for being near another nodes anchor point
        result = self.find_items(
            event.x,
            event.y,
            exclude=(self.data['arrow'], self.data['arrow_head']))

        if result is not None and result[0] == 'node':
            self.activate_node(
                result[1],
                result[2],
                exclude=(self.data['edge'].node1, ))

    def drop_arrow_head(self, event):
        '''The user has dropped the arrow somewhere!
        If it is on another node, make the connection.
        If it is in empty space or on the original node,
        just cancel the operation.
        '''

        self.canvas.bind('<B1-Motion>', '')
        self.canvas.bind('<ButtonRelease-1>', '')

        # Check for being near another nodes anchor point
        result = self.find_items(event.x, event.y)

        edge = self.data['edge']

        if result is None:
            # dropped on empty space
            self.canvas.delete('type=arrow_base')
            self.canvas.delete('type=arrow_head')
            edge.draw()
        elif result[0] == 'node':
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

                self.remove_edge(self.data['arrow'])

                self.add_edge(
                    node1,
                    node2,
                    'execution',
                    anchor1=anchor1,
                    anchor2=anchor2
                )

        self.data = None
        self.mouse_op = None

    def right_click_on_arrow(self, event, item, tags):
        '''Handle a right click on an arrow
        '''

        if self.popup_menu is not None:
            self.popup_menu.destroy()

        self.popup_menu = tk.Menu(self.canvas, tearoff=0)
        self.popup_menu.add_command(
            label="Delete", command=lambda: self.remove_edge(item))

        self.popup_menu.tk_popup(event.x_root, event.y_root, 0)

    def remove_edge(self, item):
        '''Remove an edge from the graph and visually
        '''

        tags = self.get_tags(item)
        edge = tags['edge']
        self.graph.remove_edge(edge.node1, edge.node2,
                               edge.edge_type)

        self.canvas.delete(item)
        self.canvas.delete('type=arrow_base')
        self.canvas.delete('type=arrow_head')

    def print_edges(self):
        '''Print all the edges. Useful for debugging!
        '''

        for edge in self.edges():
            print('{} {} {} {} {}'.format(
                edge.node1.tag(),
                edge.anchor1,
                edge.node2.tag(),
                edge.anchor2
            )
            )

    def print_items(self):
        """Print all the items on the canvas, for debugging
        """

        print()
        for item in self.canvas.find_withtag('type=arrow'):
            print('{}: {}'.format(item, self.canvas.gettags(item)))

    def run(self):
        """Run the current workflow"""

        self.update_workflow()
        exec = molssi_workflow.ExecWorkflow(self.workflow)
        exec.run()
        self.update_workflow()

    def update_workflow(self):
        """Update the non-graphical workflow"""
        wf = self.workflow

        # Make sure there is nothing in the workflow
        wf.clear(all=True)

        # Add all the non-graphical nodes, making copies so that
        # when the workflow is cleared our objects still exist
        translate = {}
        for node in self:
            translate[node] = wf.add_node(copy.copy(node.node))
            node.update_workflow()

        # And the edges
        for edge in self.edges():
            attr = {}
            for key in edge:
                if key not in ('node1', 'node2', 'edge_type', 'canvas'):
                    attr[key] = edge[key]
            node1 = translate[edge.node1]
            node2 = translate[edge.node2]
            wf.add_edge(node1, node2, edge.edge_type, **attr)

    def from_workflow(self):
        """Recreate the graphics from the non-graphical workflow"""
        wf = self.workflow

        self.clear()

        # Add all the non-graphical nodes, making copies so that
        # when the workflow is cleared our objects still exist
        translate = {}
        for node in wf:
            extension = node.extension
            if extension is None:
                # Start node
                translate[node] = self.get_node('1')
            else:
                new_node = copy.copy(node)
                logger.debug('creating {} node'.format(extension))
                plugin = self.plugin_manager.get(extension)
                logger.debug('  plugin object: {}'.format(plugin))
                tk_node = plugin.create_tk_node(
                    tk_workflow=self, canvas=self.canvas, node=new_node
                )
                translate[node] = tk_node
                tk_node.from_workflow()
                self.graph.add_node(tk_node)
                tk_node.draw()

        # And the edges
        for edge in wf.edges():
            node1 = translate[edge.node1]
            node2 = translate[edge.node2]
            attr = {}
            for key in edge:
                if key not in ('node1', 'node2'):
                    attr[key] = edge[key]
            self.add_edge(node1, node2, **attr)
