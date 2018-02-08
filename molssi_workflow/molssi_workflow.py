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

import json
import logging
import molssi_util
import os.path
from PIL import ImageTk, Image
# import PIL
import sys
import tkinter as tk
import tkinter.filedialog as tk_filedialog
import tkinter.messagebox as tk_messagebox
import tkinter.ttk as ttk

import molssi_workflow

logger = logging.getLogger(__name__)


def grey(value):
    return 255 - (255 - value) * 0.1


class Flowchart(object):
    def __init__(self,
                 master=None,
                 parent=None,
                 extension_namespace='molssi.workflow.tk',
                 main=True,
                 workflow=None):
        '''Initialize a Flowchart object

        Keyword arguments:
        '''

        self.toplevel = None
        self.master = master
        self.parent = parent
        self.is_main = main

        if workflow is not None:
            self.workflow = workflow
        else:
            self.workflow = molssi_workflow.Workflow(
                name='Workflow', extension_namespace=extension_namespace)
        self.workflow.gui_object = self

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

        # Make the window large and centered

        # Create the panedwindow
        self.pw = tk.PanedWindow(self.master, orient=tk.HORIZONTAL)
        self.pw.pack(fill=tk.BOTH, expand=1)

        # On the left put the tree of nodes
        self.tree = ttk.Treeview(self.pw)
        self.pw.add(self.tree)
        for group in sorted(self.workflow.extensions):
            self.tree.insert("", "end", group, text=group)
            for extension in sorted(self.workflow.extensions[group]):
                self.tree.insert(
                    group, "end", extension, text=extension, tags="node")
        self.tree.tag_bind(
            "node", sequence="<ButtonPress-1>", callback=self.create_node)

        # and the main canvas next to the right
        self.canvas = tk.Canvas(
            self.pw, width=self.canvas_width, height=self.canvas_height)
        self.pw.add(self.canvas)

        # background image
        # datapath = os.path.join(os.path.dirname(__file__), 'data')
        datapath = '/Users/psaxe/Work/Workflow/molssi_workflow/data'
        filepath = os.path.join(datapath, 'framework.png')
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
        self.create_start_node(self.workflow.get_node('1'))

        # Set up the bindings
        self.canvas.bind('<Configure>', self.canvas_configure)
        self.canvas.bind('<Motion>', self.mouse_motion)
        self.canvas.bind('<ButtonPress-1>', self.click)
        self.canvas.bind('<Double-ButtonPress-1>', self.double_click)
        if sys.platform.startswith('darwin'):
            self.canvas.bind('<ButtonPress-2>', self.right_click)
            CmdKey = 'Command-'
        else:
            self.canvas.bind('<ButtonPress-3>', self.right_click)
            CmdKey = 'Control-'

        if self.is_main:
            global app_name
            app_name = 'MolSSI Workflow'

            menu = tk.Menu(self.toplevel)

            # Set the about and preferences menu items on Mac
            if sys.platform.startswith('darwin'):
                app_menu = tk.Menu(menu, name='apple')
                menu.add_cascade(menu=app_menu)

                app_menu.add_command(label='About ' + app_name,
                                     command=self.about)
                app_menu.add_separator()
                self.toplevel.createcommand('tk::mac::ShowPreferences',
                                            self.preferences)
                self.toplevel.createcommand('tk::mac::OpenDocument',
                                            self.open_file)

            self.toplevel.config(menu=menu)
            filemenu = tk.Menu(menu)
            menu.add_cascade(label="File", menu=filemenu)
            filemenu.add_command(label="New",
                                 command=self.new_file,
                                 accelerator=CmdKey + 'N')
            filemenu.add_command(label="Save...",
                                 command=self.save_file,
                                 accelerator=CmdKey + 'S')
            filemenu.add_command(label="Open...",
                                 command=self.open_ask,
                                 accelerator=CmdKey + 'O')
            filemenu.add_separator()
            filemenu.add_command(label="Run", command=self.run)
            filemenu.add_separator()
            filemenu.add_command(label="Exit", command=self.toplevel.quit)

            helpmenu = tk.Menu(menu)
            menu.add_cascade(label="Help", menu=helpmenu)
            self.toplevel.createcommand('tk::mac::ShowHelp',
                                        self.help)
            # helpmenu.add_command(
            #     label="About...",
            #     command=lambda: self.about("This is an example of a menu"))

            self.toplevel.bind_all('<'+CmdKey+'N>', self.new_file)
            self.toplevel.bind_all('<'+CmdKey+'n>', self.new_file)
            self.toplevel.bind_all('<'+CmdKey+'O>', self.open_ask)
            self.toplevel.bind_all('<'+CmdKey+'o>', self.open_ask)
            self.toplevel.bind_all('<'+CmdKey+'S>', self.save_file)
            self.toplevel.bind_all('<'+CmdKey+'s>', self.save_file)

            sw = self.toplevel.winfo_screenwidth()
            sh = self.toplevel.winfo_screenheight()
            w = int(0.9 * sw)
            h = int(0.8 * sh)
            x = int(0.1 * sw / 2)
            y = int(0.2 * sh / 2)

            self.toplevel.geometry('{}x{}+{}+{}'.format(w, h, x, y))

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

    def new_file(self, event=None):
        print("Create a new file!")

    def help(self, event=None):
        print("Help!!!!")

    def debug(self, event):
        print(event)

    def open_ask(self, event=None):
        filename = tk_filedialog.askopenfilename()
        if filename == '':
            return
        self.open_file(filename)

    def open_file(self, filename):
        if isinstance(filename, list):
            filename = filename[0]

        with open(filename, 'r') as fd:
            line = fd.readline(256)
            # There may be exec magic as first line
            if line[0:2] == '#!':
                line = fd.readline(256)
            if line[0:7] != '!MolSSI':
                raise RuntimeError('File is not a MolSSI file! -- ' + line)
            tmp = line.split()
            if len(tmp) < 3:
                raise RuntimeError(
                    'File is not a proper MolSSI file! -- ' + line)
            if tmp[1] != 'workflow':
                raise RuntimeError('File is not a workflow! -- ' + line)
            workflow_version = tmp[2]
            logger.info('Reading workflow version {} from file {}'.format(
                workflow_version, filename))

            data = json.load(fd, cls=molssi_util.JSONDecoder)

        if data['class'] != 'Workflow':
            tk_messagebox.showwarning(
                'Open file',
                'File {} does not contain a workflow!'.format(filename))
            return

        # Restore the workflow
        self.workflow.from_dict(data)

    def clear(self):
        """Clear our graphics"""
        # self.canvas.delete('all')
        for item in self.canvas.find_all():
            if item != self.background:
                self.canvas.delete(item)

    def create_start_node(self, start_node):
        """Create the graphical start node"""
        start_node.gui_object = molssi_workflow.TkStartNode(
            canvas=self.canvas, node=start_node)

    def create_graphics_node(self, node, extension):
        """Create the graphics node counterpart for node"""
        node.gui_object = extension.factory(
            graphical=True, canvas=self.canvas, node=node)

    def save_file(self, event=None):
        name = tk_filedialog.asksaveasfilename()
        if name != '':
            with open(name, 'w') as fd:
                fd.write('#!/usr/bin/env run_workflow\n')
                fd.write('!MolSSI workflow 1.0\n')
                json.dump(self.workflow.to_dict(), fd, indent=4,
                          cls=molssi_util.JSONEncoder)
        logger.info('Wrote json to {}'.format(name))

    def about(self, text='In about'):
        print(text)

    def preferences(self):
        print('In preferences')

    def draw(self):
        for node in self.workflow:
            node.gui_object.draw()

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
            if tags['type'] == 'arrow_base' or tags['type'] == 'arrow_head':
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
                    x, y = node.gui_object.anchor_point(tags['anchor'])
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
                    if node.gui_object.is_inside(event.x, event.y, self.halo):
                        self.selection.append(node)
                        node.gui_object.selected = True
                        self._x0 = event.x
                        self._y0 = event.y
                        self.mouse_op = 'Move'
                        self.canvas.bind('<B1-Motion>', self.move)
                        self.canvas.bind('<ButtonRelease-1>', self.end_move)
                    else:
                        node.gui_object.selected = False

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
            if node.gui_object.is_inside(event.x, event.y):
                node.gui_object.double_click(event)
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
            if node.gui_object.is_inside(event.x, event.y):
                node.gui_object.right_click(event)
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
            item.gui_object.move(deltax, deltay)

    def end_move(self, event):
        '''End the move of selected items
        '''
        self.canvas.bind('<B1-Motion>', '')
        self.canvas.bind('<ButtonRelease-1>', '')

        deltax = event.x - self._x0
        deltay = event.y - self._y0

        for item in self.selection:
            item.gui_object.end_move(deltax, deltay)
            item.gui_object.selected = False

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
        extension_name = self.tree.item(item, option="text")

        (last_node, x, y) = self.next_position()

        logger.debug('creating {} node'.format(extension_name))
        extension = self.workflow.extension_manager[extension_name].obj
        logger.debug('  extension object: {}'.format(extension))

        # The node.
        node = self.workflow.create_node(extension_name)

        # The graphics partner
        gui_object = extension.factory(
            graphical=True, canvas=self.canvas, x=x, y=y, w=200, h=50,
            node=node)

        # Set the GUI partner for the node
        node.gui_object = gui_object

        # And connect this to the last node in the existing workflow,
        # which is probably what the user wants.
        edge_object = self.workflow.add_edge(
            last_node,
            node,
            edge_type='execution',
            start_point='s',
            end_point='n')
        self.create_edge(edge_object)

        # And update the picture on screen
        self.draw()

    def next_position(self):
        """Find a reasonable place to position the next step
        in the flowchart."""

        last_node = self.workflow.last_node()
        x0 = last_node.gui_object.x
        y0 = last_node.gui_object.y + last_node.gui_object.h + self.gap

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
                if node.gui_object.is_inside(event.x, event.y, self.halo):
                    active.append(node)
                    if node not in self.active_nodes:
                        node.gui_object.activate()
                        self.active_nodes.append(node)
                    # are we close to any anchor points?
                    point = node.gui_object.check_anchor_points(
                        event.x, event.y, self.halo)
                    if point is None:
                        self.canvas.delete('type=active_anchor')
                    else:
                        node.gui_object.activate_anchor_point(point, self.halo)
                        result = (node, point)
                    break

        # deactivate any previously active nodes
        for node in self.active_nodes:
            if node not in active:
                node.gui_object.deactivate()
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
                if node.gui_object.is_inside(x, y, self.halo):
                    # are we close to any anchor points?
                    point = node.gui_object.check_anchor_points(
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
                    tags[key] = self.workflow.get_node(value)
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
                result[1].gui_object.deactivate()
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
                edge_object = self.workflow.add_edge(
                    node,
                    other_node,
                    edge_type='execution',
                    start_point=anchor,
                    end_point=point)
                self.create_edge(edge_object)

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
                exclude=(self.data['edge'].edge.end_node, ))

    def activate_node(self, node, point=None, exclude=()):
        '''Activate a node, i.e. display the anchor points,
        unless it is in the exclusion list. Also, if the
        anchor point is given, make it active.
        '''

        active = []
        if node in exclude:
            self.canvas.delete('type=active_anchor')
            node.gui_object.deactivate()
        else:
            active.append(node)
            if node not in self.active_nodes:
                node.gui_object.activate()
                self.active_nodes.append(node)
            if point is None:
                self.canvas.delete('type=active_anchor')
            else:
                node.gui_object.activate_anchor_point(point, self.halo)

        # deactivate any previously active nodes
        for node in self.active_nodes:
            if node not in active:
                node.gui_object.deactivate()
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
            node, point = result[1:]
            if edge.edge.end_node == node:
                edge.draw()
            else:
                # remove current connection and create new, in
                # that order -- otherwise tend to remove edge
                # completely if it is moved on same node.

                end_node = edge.edge.end_node
                end_point = edge['end_point']

                self.remove_edge(self.data['arrow'])

                edge_object = self.workflow.add_edge(
                    node,
                    end_node,
                    start_point=point,
                    end_point=end_point,
                    edge_type='execution')
                self.create_edge(edge_object)

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
                exclude=(self.data['edge'].edge.start_node, ))

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
            node, point = result[1:]
            if edge.edge.start_node == node:
                edge.draw()
            else:
                # remove current connection and create new, in
                # that order -- otherwise tend to remove edge
                # completely if it is moved on same node.

                start_node = edge.edge.start_node
                start_point = edge['start_point']

                self.remove_edge(self.data['arrow'])

                edge_object = self.workflow.add_edge(
                    start_node,
                    node,
                    start_point=start_point,
                    end_point=point,
                    edge_type='execution')
                self.create_edge(edge_object)

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
        edge = tags['edge'].edge
        self.workflow.remove_edge(edge.start_node, edge.end_node,
                                  edge.edge_type)

        self.canvas.delete(item)
        self.canvas.delete('type=arrow_base')
        self.canvas.delete('type=arrow_head')

    def print_edges(self):
        '''Print all the edges. Useful for debugging!
        '''

        for u, v, k, data in self.workflow.edges(keys=True, data=True):
            print('{} {} {} {} {} {}'.format(u, data['start_point'], v,
                                             data['end_point'], k,
                                             data['object'].tag()))

    def print_items(self):
        """Print all the items on the canvas, for debugging
        """

        print()
        for item in self.canvas.find_withtag('type=arrow'):
            print('{}: {}'.format(item, self.canvas.gettags(item)))

    def run(self):
        """Run the current workflow"""

        exec = molssi_workflow.ExecWorkflow(self.workflow)
        exec.run()

    def create_edge(self, edge_object):
        """Create the graphical counterpart to the edge"""
        molssi_workflow.TkEdge(
            self.canvas,
            edge_object
        )
