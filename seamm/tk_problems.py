# -*- coding: utf-8 -*-

"""The editor's dialog for the problems found when checking a flowchart.

Each problem is listed with a button for each fix its check offers; a fix changes
the parameters of the steps and the flowchart is checked again. Errors stop the
job from being submitted; with only warnings left it can be submitted anyway.
"""

import tkinter as tk
import tkinter.ttk as ttk

from .problems import fixes, is_error

#: The width of the problems' text, in pixels
WRAP = 600


class ProblemsDialog(object):
    """List the problems with their fixes; return whether to submit the job.

    Parameters
    ----------
    parent : tkinter widget
        The editor's window.
    problems : [str]
        The problems, from ``seamm.builder.validate(..., warnings=True)``.
    revalidate : callable
        Checks the flowchart again after a fix and returns its problems.
    """

    def __init__(self, parent, problems, revalidate):
        self.parent = parent
        self.problems = list(problems)
        self.revalidate = revalidate
        self.applied = []
        self.result = False

        self.toplevel = tk.Toplevel(parent)
        self.toplevel.title("Checking the flowchart")
        self.toplevel.transient(parent)
        self.toplevel.protocol("WM_DELETE_WINDOW", self.cancel)
        self.frame = ttk.Frame(self.toplevel, padding=10)
        self.frame.grid(row=0, column=0, sticky=tk.NSEW)
        self.toplevel.columnconfigure(0, weight=1)
        self.toplevel.rowconfigure(0, weight=1)
        self.widgets = {}
        self.layout()

    @property
    def errors(self):
        return [p for p in self.problems if is_error(p)]

    def layout(self):
        """Lay out the problems, their fixes and the buttons."""
        for widget in self.frame.winfo_children():
            widget.destroy()
        self.widgets = {"fixes": []}
        row = 0
        if len(self.errors) > 0:
            text = "The job cannot be submitted until these are fixed:"
        elif len(self.problems) > 0:
            text = "Please check these warnings before submitting the job:"
        else:
            text = "No problems remain."
        ttk.Label(self.frame, text=text, wraplength=WRAP).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 8)
        )
        row += 1
        for problem in self.problems:
            kind = "Error" if is_error(problem) else "Warning"
            ttk.Label(
                self.frame, text=f"{kind}: {problem}", wraplength=WRAP, justify=tk.LEFT
            ).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(4, 2))
            row += 1
            for fix in fixes(problem):
                button = ttk.Button(
                    self.frame,
                    text=f"Fix: {fix.label}",
                    command=lambda fix=fix: self.apply(fix),
                )
                button.grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=(20, 0))
                self.widgets["fixes"].append((fix, button))
                row += 1
        for label in self.applied:
            ttk.Label(self.frame, text=f"Fixed: {label}", wraplength=WRAP).grid(
                row=row, column=0, columnspan=2, sticky=tk.W
            )
            row += 1

        buttons = ttk.Frame(self.frame)
        buttons.grid(row=row, column=0, columnspan=2, sticky=tk.E, pady=(12, 0))
        if len(self.errors) == 0:
            submit = "Submit" if len(self.problems) == 0 else "Submit anyway"
            self.widgets["submit"] = ttk.Button(
                buttons, text=submit, command=self.submit
            )
            self.widgets["submit"].grid(row=0, column=0, padx=4)
        self.widgets["cancel"] = ttk.Button(buttons, text="Cancel", command=self.cancel)
        self.widgets["cancel"].grid(row=0, column=1, padx=4)

    def apply(self, fix):
        """Make a fix's changes and check the flowchart again."""
        fix.apply()
        self.applied.append(fix.label)
        self.problems = list(self.revalidate())
        self.layout()

    def submit(self):
        self.result = True
        self.toplevel.destroy()

    def cancel(self):
        self.result = False
        self.toplevel.destroy()

    def show(self):
        """Wait for the user; return True to submit the job."""
        self.toplevel.grab_set()
        self.parent.wait_window(self.toplevel)
        return self.result
