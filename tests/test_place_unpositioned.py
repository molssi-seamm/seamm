#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Nodes without a position (e.g. from a script) are placed before drawing."""

from types import SimpleNamespace as Node

from seamm.tk_flowchart import place_unpositioned


def node(x=None, y=None, w=200, h=50):
    return Node(x=x, y=y, w=w, h=h)


def test_positioned_nodes_are_left_alone():
    a, b = node(150, 35), node(150, 105)
    place_unpositioned([a, b], [(a, b)])
    assert (a.x, a.y, b.x, b.y) == (150, 35, 150, 105)


def test_new_node_goes_below_the_one_before_it():
    start, ff, pk = node(150, 35), node(150, 105), node(w=None, h=None)
    place_unpositioned([start, ff, pk], [(start, ff), (ff, pk)])
    assert (pk.x, pk.y, pk.w, pk.h) == (150, 175, 200, 50)


def test_inserted_node_pushes_the_rest_down():
    """Start -> Init -> Minimization (new) -> Velocities -> NVT."""
    start, init = node(150, 35), node(150, 105)
    vel, nvt, mn = node(150, 175), node(150, 245), node(w=None, h=None)
    place_unpositioned(
        [start, init, vel, nvt, mn],
        [(start, init), (init, mn), (mn, vel), (vel, nvt)],
    )
    assert [n.y for n in (start, init, mn, vel, nvt)] == [35, 105, 175, 245, 315]


def test_chain_of_new_nodes():
    start, a, b = node(150, 35), node(), node()
    place_unpositioned([start, b, a], [(start, a), (a, b)])  # any order
    assert (a.y, b.y) == (105, 175)


def test_node_with_nothing_before_it_goes_below_the_lowest():
    start, low, lone = node(150, 35), node(150, 385), node()
    place_unpositioned([start, low, lone], [(start, low)])
    assert (lone.x, lone.y) == (150, 455)


def test_other_columns_are_not_moved():
    """Only the column the node is inserted into shifts down."""
    start, a, side, new = node(150, 35), node(150, 105), node(450, 105), node()
    place_unpositioned([start, a, side, new], [(start, new), (new, a)])
    assert (new.y, a.y, side.y) == (105, 175, 105)
