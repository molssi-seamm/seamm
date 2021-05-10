# -*- coding: utf-8 -*-

"""Helper class needed for the stevedore integration. Needs to provide
a description() method that returns a dict containing a description of
this node, and a factory() method for creating the graphical and non-graphical
nodes."""

import seamm


class SplitStep(object):
    my_description = {
        "description": "An interface for a node to split the control flow",
        "group": "Control",
        "name": "Split",
    }

    def __init__(self, flowchart=None, gui=None):
        """Initialize this helper class, which is used by
        the application via stevedore to get information about
        and create node objects for the flowchart
        """
        pass

    def description(self):
        """Return a description of what this extension does"""
        return SplitStep.my_description

    def create_node(self, flowchart=None, **kwargs):
        """Return the new node object"""
        return seamm.Split(flowchart=flowchart, **kwargs)

    def create_tk_node(self, canvas=None, **kwargs):
        """Return the graphical Tk node object"""
        return seamm.TkSplit(canvas=canvas, **kwargs)


class JoinStep(object):
    my_description = {
        "description": "An interface for a node to join the control flow",
        "group": "Control",
        "name": "Join",
    }

    def __init__(self, flowchart=None, gui=None):
        """Initialize this helper class, which is used by
        the application via stevedore to get information about
        and create node objects for the flowchart
        """
        pass

    def description(self):
        """Return a description of what this extension does"""
        return JoinStep.my_description

    def create_node(self, flowchart=None, **kwargs):
        """Return the new node object"""
        return seamm.Join(flowchart=flowchart, **kwargs)

    def create_tk_node(self, canvas=None, **kwargs):
        """Return the graphical Tk node object"""
        return seamm.TkJoin(canvas=canvas, **kwargs)
