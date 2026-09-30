# -*- coding: utf-8 -*-

"""Lay out a flowchart on the editor's grid without the graphical interface.

This follows the editor's "clean layout" (``TkFlowchart.clean_layout``): steps go down
one column, one grid row apart; the body of a loop goes one column to the right,
starting level with the loop; the step after a loop continues below the body; and an
edge that goes back up -- the return from the end of a loop body -- is routed down,
right, up and back to its target so that it does not cross the body.

Steps not connected to the flowchart are put in columns to the right of it.
"""

import logging

logger = logging.getLogger(__name__)

GRID_X = 300
GRID_Y = 70
WIDTH = 200
HEIGHT = 50

# Where the anchor points are, as fractions of the width and height from the center,
# as in seamm.TkNode.anchor_points.
_anchor_points = {
    "n": (0, -0.5),
    "ne": (0.5, -0.5),
    "e": (0.5, 0),
    "se": (0.5, 0.5),
    "s": (0, 0.5),
    "sw": (-0.5, 0.5),
    "w": (-0.5, 0),
    "nw": (-0.5, -0.5),
}


def anchor_point(node, anchor):
    """The position of an anchor point of a node, as the editor computes it."""
    a, b = _anchor_points[anchor]
    return (int(node.x + a * node.w), int(node.y + b * node.h))


def is_loop(flowchart, node):
    """Whether a node is a loop, i.e. has an outgoing 'loop' edge."""
    for edge in flowchart.edges(node, direction="out"):
        if edge.edge_type == "execution" and edge.edge_subtype == "loop":
            return True
    return False


def _structure(flowchart):
    """Find which loops each node is in, as the editor does.

    Returns
    -------
    (dict, dict, [object])
        node -> tuple of the loops it is in (outermost first); loop -> the nodes
        directly in it, in order, where the keys None and ("unconnected", i) are the
        flowchart itself and each chain of unconnected steps; and those roots in order.
    """
    loops_of = {}
    in_loop = {}

    def traverse(node, loops, root):
        loops_of[node] = loops
        in_loop[loops[-1] if loops else root].append(node)
        edges = flowchart.edges(node, direction="out")
        if is_loop(flowchart, node):
            in_loop[node] = []
            for edge in edges:
                if edge.edge_type == "execution" and edge.edge_subtype == "loop":
                    if edge.node2 not in loops_of:
                        traverse(edge.node2, loops + (node,), root)
            for edge in edges:
                if edge.edge_type == "execution" and edge.edge_subtype == "exit":
                    if edge.node2 not in loops_of:
                        traverse(edge.node2, loops, root)
        else:
            for edge in edges:
                if edge.node2 not in loops_of and edge.edge_subtype in (
                    "next",
                    "exit",
                ):
                    traverse(edge.node2, loops, root)

    roots = [None]
    in_loop[None] = []
    traverse(flowchart.get_node("1"), (), None)

    # Chains of unconnected steps
    remaining = [node for node in flowchart if node not in loops_of]
    while remaining:
        heads = [
            node
            for node in remaining
            if not any(
                e.node1 in remaining for e in flowchart.edges(node, direction="in")
            )
        ]
        root = ("unconnected", len(roots))
        roots.append(root)
        in_loop[root] = []
        traverse(heads[0] if heads else remaining[0], (), root)
        remaining = [node for node in flowchart if node not in loops_of]

    return loops_of, in_loop, roots


def _nodes_in(in_loop, loop):
    """All the nodes in a loop, including those in loops inside it."""
    result = []
    for node in in_loop[loop]:
        result.append(node)
        if node in in_loop:
            result.extend(_nodes_in(in_loop, node))
    return result


def route_edges(flowchart, structure=None, grid_x=GRID_X, grid_y=GRID_Y):
    """Anchor and route the edges of a flowchart whose nodes have positions.

    An edge that goes up -- the return from the end of a loop body -- runs down to
    below the body, right past it, up, and into its target from the right. For nodes
    on the editor's grid this gives the same coordinates as its clean layout.

    Parameters
    ----------
    flowchart : seamm.Flowchart
    structure : tuple, optional
        The result of _structure(), if already known.
    grid_x, grid_y : int
        The width of a column and the height of a row.
    """
    if structure is None:
        structure = _structure(flowchart)
    loops_of, in_loop, roots = structure

    for edge in flowchart.edges():
        node1, node2 = edge.node1, edge.node2
        if node1 not in loops_of or node2 not in loops_of:
            continue
        if edge.edge_subtype == "loop":
            anchor1, anchor2 = "e", "w"
        elif node2.y < node1.y:
            # Going back up: the return from the end of a loop body
            anchor1, anchor2 = "s", "e"
        else:
            anchor1, anchor2 = "s", "n"
        edge["anchor1"] = anchor1
        edge["anchor2"] = anchor2

        x0, y0 = anchor_point(node1, anchor1)
        x1, y1 = anchor_point(node2, anchor2)
        if y1 < y0:
            loops = loops_of[node1]
            if loops:
                inside = _nodes_in(in_loop, loops[-1])
            else:
                inside = [n for n in loops_of if not loops_of[n]]
            xmax = int(max(n.x for n in inside) + grid_x / 2)
            ymax = int(max(n.y for n in inside) + grid_y / 2)
            dx = 10 * len(loops)
            edge["coords"] = [x0, y0, x0, ymax, xmax - dx, ymax, xmax - dx, y1, x1, y1]
        else:
            edge["coords"] = [x0, y0, x1, y1]


def layout(flowchart, grid_x=GRID_X, grid_y=GRID_Y, w=WIDTH, h=HEIGHT):
    """Position the nodes of a flowchart and route its edges, recursively.

    Sets ``x``, ``y``, ``w`` and ``h`` of every node, and ``anchor1``, ``anchor2`` and
    ``coords`` of every edge. Subflowcharts (any node attribute named
    ``subflowchart``) are laid out the same way.

    Parameters
    ----------
    flowchart : seamm.Flowchart
        The flowchart to lay out.
    grid_x, grid_y : int
        The width of a column and the height of a row.
    w, h : int
        The size of a node.
    """
    structure = _structure(flowchart)
    loops_of, in_loop, roots = structure

    # Place the nodes on the grid.
    extent = {}  # loop -> the largest column and row used inside it

    def place(loop, x, y):
        for node in in_loop[loop]:
            node.x = int((x + 0.5) * grid_x)
            node.y = int((y + 0.5) * grid_y)
            node.w = w
            node.h = h
            xmax, ymax = extent[loop]
            extent[loop] = (max(x, xmax), max(y, ymax))
            if node in in_loop:
                extent[node] = (x + 1, y)
                x1, y = place(node, x + 1, y)
                extent[loop] = (max(x1, extent[node][0], extent[loop][0]), y)
            else:
                y += 1
        return x, y

    column = 0
    for root in roots:
        extent[root] = (column, 0)
        place(root, column, 0)
        # The next chain of unconnected steps goes right of everything so far
        column = max(e[0] for e in extent.values()) + 1

    route_edges(flowchart, structure, grid_x=grid_x, grid_y=grid_y)

    # And any subflowcharts
    for node in loops_of:
        subflowchart = getattr(node, "subflowchart", None)
        if subflowchart is not None and hasattr(subflowchart, "graph"):
            layout(subflowchart, grid_x=grid_x, grid_y=grid_y, w=w, h=h)
