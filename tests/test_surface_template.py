#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The surface (3-D) graph template gives valid Plotly JSON."""

import json

import seamm


def test_surface_graph_is_valid_json():
    """A 2-D energy scan's surface: the scene's axes are xaxis, yaxis and zaxis,
    and the file is valid JSON (the z axis's domain was empty, and the keys were
    'xaxi', ...)."""
    node = seamm.Node(flowchart=None, title="test")
    figure = node.create_figure(
        module_path=("seamm",), template="surface.graph_template", title="Scan"
    )
    plot = figure.add_plot("EnergyScan")
    x_axis = plot.add_axis("x", label="phi 1 (º)")
    y_axis = plot.add_axis("y", label="phi 2 (º)")
    x_axis.anchor = y_axis
    z_axis = plot.add_axis("z", label="Energy (kJ/mol)", anchor=x_axis)
    plot.add_trace(
        x_axis=x_axis,
        y_axis=y_axis,
        z_axis=z_axis,
        name="scan",
        x=[0.0, 10.0],
        xlabel="phi 1",
        xunits="º",
        y=[0.0, 10.0],
        ylabel="phi 2",
        yunits="º",
        z=[[0.0, 1.0], [1.0, 2.0]],
        zlabel="E",
        zunits="kJ/mol",
    )
    figure.grid_plots("EnergyScan")
    graph = json.loads(figure.dumps())
    scene = graph["layout"]["scene"]
    assert set(scene) == {"xaxis", "yaxis", "zaxis"}
    assert scene["zaxis"]["title"]["text"] == "Energy (kJ/mol)"
    assert graph["data"][0]["type"] == "surface"
