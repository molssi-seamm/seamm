# -*- coding: utf-8 -*-

"""Tests for seamm.Node helpers that don't need a full flowchart."""

import seamm


class _Chain:
    """Minimal stand-in exposing previous(), to exercise previous_nodes()."""

    def __init__(self, prev):
        self._prev = prev

    def previous(self):
        return self._prev


class _A(_Chain):
    pass


class _B(_Chain):
    pass


def test_previous_nodes_order():
    a = _A(None)
    b = _B(a)
    c = _A(b)
    # previous_nodes only uses previous(); call it with our stand-in as self.
    assert seamm.Node.previous_nodes(c) == [b, a]
    assert seamm.Node.previous_nodes(a) == []


def test_previous_nodes_type_filter():
    a = _A(None)
    b = _B(a)
    c = _A(b)
    assert seamm.Node.previous_nodes(c, _A) == [a]
    assert seamm.Node.previous_nodes(c, _B) == [b]
    assert seamm.Node.previous_nodes(c, (_A, _B)) == [b, a]
