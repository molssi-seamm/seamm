import argparse
import molssi_workflow
import locale
import logging
import os
import platform
import subprocess
import tkinter as tk


def raise_app(root: tk):
    # root.attributes("-topmost", True)
    if platform.system() == 'Darwin':
        tmpl = 'tell application "System Events" to set frontmost of every process whose unix id is {} to true'  # nopep8
        script = tmpl.format(os.getpid())
        subprocess.check_call(['/usr/bin/osascript', '-e', script])
    # root.after(100, lambda: root.attributes("-topmost", False))


def flowchart():
    """The standalone flowchart app
    """

    parser = argparse.ArgumentParser(
        description='MolSSI Flowchart application')
    parser.add_argument(
        "--log", default='WARNING', help='the level of logging')
    args = parser.parse_args()

    numeric_level = getattr(logging, args.log.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % args.log)
    logging.basicConfig(level=numeric_level)

    # Initialize Tk, which creates the toplevel window
    root = tk.Tk()

    # bring it to the top of all windows
    root.lift()
    root.attributes('-topmost', True)
    root.after_idle(root.attributes, '-topmost', False)

    # Set title
    root.title("MolSSI Workflow")

    # This seems to have no effect.... :-(
    root.after_idle(root.lift)

    flowchart = molssi_workflow.Flowchart(root)
    flowchart.draw()

    # bring it to the top of all windows
    raise_app(root)

    root.mainloop()


if __name__ == "__main__":
    locale.setlocale(locale.LC_ALL, '')

    flowchart()
