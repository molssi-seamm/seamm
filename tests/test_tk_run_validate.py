#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The editor checks the whole flowchart before submitting it, and offers the
checks' fixes. Skipped without a display."""

from types import SimpleNamespace

import pytest

from seamm.problems import WARNING, Edit, Fix, Problem


@pytest.fixture()
def root():
    import tkinter as tk

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display available for Tk")
    root.withdraw()
    yield root
    root.destroy()


def _editor(root, submitted):
    import seamm.tk_flowchart as tkf

    tk_flowchart = tkf.TkFlowchart.__new__(tkf.TkFlowchart)
    tk_flowchart.toplevel = root
    tk_flowchart.update_flowchart = lambda: "the flowchart"
    tk_flowchart._job_handler = SimpleNamespace(
        submit_with_dialog=lambda flowchart: submitted.append(flowchart)
    )
    return tk_flowchart


def test_run_shows_the_problems_and_submits_only_when_asked(root, monkeypatch):
    import seamm.builder
    import seamm.tk_problems

    submitted = []
    tk_flowchart = _editor(root, submitted)
    shown = []

    def show(self):
        shown.append(list(self.problems))
        return answer

    monkeypatch.setattr(seamm.tk_problems.ProblemsDialog, "show", show)

    monkeypatch.setattr(
        seamm.builder, "validate", lambda f, warnings=False: ["no heat flux"]
    )
    answer = False
    tk_flowchart.run()
    assert submitted == [] and shown == [["no heat flux"]]

    monkeypatch.setattr(
        seamm.builder,
        "validate",
        lambda f, warnings=False: [Problem("overwrites", severity=WARNING)],
    )
    answer = True
    tk_flowchart.run()
    assert submitted == ["the flowchart"]

    monkeypatch.setattr(seamm.builder, "validate", lambda f, warnings=False: [])
    tk_flowchart.run()
    assert submitted == ["the flowchart"] * 2 and len(shown) == 2


class _Step:
    def __init__(self):
        self.title = "NVT"
        self.parameters = {"structure handling": SimpleNamespace(value="Overwrite")}


def test_a_fix_button_changes_the_step_and_checks_again(root):
    from seamm.tk_problems import ProblemsDialog

    step = _Step()
    fix = Fix("Discard the structure", [Edit(step, "structure handling", "Discard")])
    warning = Problem("NVT overwrites the structure", severity=WARNING, fixes=[fix])
    error = Problem("No MD before the analysis")

    def revalidate():
        problems = [error]
        if step.parameters["structure handling"].value == "Overwrite":
            problems.append(warning)
        return problems

    dialog = ProblemsDialog(root, revalidate(), revalidate)
    assert "submit" not in dialog.widgets  # an error: no submitting
    (shown, button), *_ = dialog.widgets["fixes"]
    assert shown is fix
    button.invoke()
    assert step.parameters["structure handling"].value == "Discard"
    assert dialog.problems == [error] and dialog.applied == ["Discard the structure"]
    assert dialog.widgets["fixes"] == []
    dialog.cancel()
    assert dialog.result is False


def test_only_warnings_can_be_submitted_anyway(root):
    from seamm.tk_problems import ProblemsDialog

    dialog = ProblemsDialog(root, [Problem("check this", severity=WARNING)], lambda: [])
    assert dialog.widgets["submit"].cget("text") == "Submit anyway"
    dialog.widgets["submit"].invoke()
    assert dialog.result is True
