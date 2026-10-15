#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The editor checks the whole flowchart before submitting it. Skipped without a
display."""

from types import SimpleNamespace

import pytest


def test_run_refuses_a_flowchart_with_problems(monkeypatch):
    import tkinter as tk

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display available for Tk")
    root.withdraw()
    try:
        import seamm
        import seamm.builder
        import seamm.tk_flowchart as tkf

        shown = {}
        submitted = []
        tk_flowchart = tkf.TkFlowchart.__new__(tkf.TkFlowchart)
        tk_flowchart.toplevel = root
        tk_flowchart.update_flowchart = lambda: "the flowchart"
        tk_flowchart._job_handler = SimpleNamespace(
            submit_with_dialog=lambda flowchart: submitted.append(flowchart)
        )
        monkeypatch.setattr(
            tkf.tk_messagebox, "showerror", lambda **kw: shown.update(kw)
        )

        monkeypatch.setattr(seamm.builder, "validate", lambda f: ["no heat flux"])
        tk_flowchart.run()
        assert submitted == []
        assert "no heat flux" in shown["message"]

        monkeypatch.setattr(seamm.builder, "validate", lambda f: [])
        tk_flowchart.run()
        assert submitted == ["the flowchart"]
    finally:
        root.destroy()
