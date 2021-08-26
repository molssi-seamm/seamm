import argparse
import seamm
import locale
import logging
import os
import platform
import Pmw
import subprocess
import sys
import tkinter as tk

logger = logging.getLogger(__name__)
dbg_level = 30


def raise_app(root: tk):
    root.attributes("-topmost", True)
    if platform.system() == "Darwin":
        tmpl = (
            'tell application "System Events" to set frontmost '
            "of every process whose unix id is {} to true"
        )
        script = tmpl.format(os.getpid())
        subprocess.check_call(["/usr/bin/osascript", "-e", script])
    root.after(100, lambda: root.attributes("-topmost", False))


def flowchart():
    """The standalone flowchart app"""
    global app_name
    app_name = "MolSSI SEAMM"
    global dbg_level

    parser = argparse.ArgumentParser(description="MolSSI SEAMM")
    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose_count",
        action="count",
        default=0,
        help="increases log verbosity for each occurence.",
    )
    parser.add_argument(
        "flowcharts", nargs="*", default=[], help="flowcharts to open initially"
    )

    args, unknown = parser.parse_known_args()

    # Sets log level to WARN going more verbose for each new -v.
    dbg_level = max(3 - args.verbose_count, 0) * 10
    logging.basicConfig(level=dbg_level)

    ##################################################
    # Initialize Tk
    ##################################################
    root = tk.Tk()
    Pmw.initialise(root)

    ##############################################################
    # Create the various objects that we need: the model, the view
    # and the data
    ##############################################################

    flowchart = seamm.Flowchart()
    tk_flowchart = seamm.TkFlowchart(master=root, flowchart=flowchart)
    # The data is implicitly initialized to none...

    ##################################################
    # Initialize the rest of the GUI, such as menus
    ##################################################
    logger.debug("Initializing the rest of the GUI")

    root.title(app_name)

    # The menus
    menu = tk.Menu(root)

    # Set the about and preferences menu items on Mac
    if sys.platform.startswith("darwin"):
        app_menu = tk.Menu(menu, name="apple")
        menu.add_cascade(menu=app_menu)

        app_menu.add_command(label="About " + app_name, command=tk_flowchart.about)
        app_menu.add_separator()
        root.createcommand("tk::mac::ShowPreferences", tk_flowchart.preferences)
        root.createcommand("tk::mac::OpenDocument", tk_flowchart.open_file)
        CmdKey = "Command-"
    else:
        CmdKey = "Control-"

    root.config(menu=menu)
    filemenu = tk.Menu(menu)
    menu.add_cascade(label="File", menu=filemenu)
    filemenu.add_command(
        label="New", command=tk_flowchart.new_file, accelerator=CmdKey + "N"
    )
    filemenu.add_command(
        label="Open...", command=tk_flowchart.flowchart_search, accelerator=CmdKey + "O"
    )
    filemenu.add_command(
        label="Save...", command=tk_flowchart.save, accelerator=CmdKey + "S"
    )
    filemenu.add_command(label="Save as...", command=tk_flowchart.save_file)
    filemenu.add_command(label="Publish...", command=tk_flowchart.publish)
    filemenu.add_separator()
    filemenu.add_command(
        label="Run", command=tk_flowchart.run, accelerator=CmdKey + "R"
    )

    # Control debugging info
    filemenu.add_separator()
    debug_menu = tk.Menu(menu)
    filemenu.add_cascade(label="Debug", menu=debug_menu)
    debug_menu.add_radiobutton(
        label="normal",
        value=30,
        variable=dbg_level,
        command=lambda arg0=30: handle_dbg_level(arg0),
    )
    debug_menu.add_radiobutton(
        label="info",
        value=20,
        variable=dbg_level,
        command=lambda arg0=20: handle_dbg_level(arg0),
    )
    debug_menu.add_radiobutton(
        label="debug",
        value=10,
        variable=dbg_level,
        command=lambda arg0=10: handle_dbg_level(arg0),
    )

    # Exiting
    filemenu.add_separator()
    filemenu.add_command(label="Exit", command=root.quit)

    # Edit menu
    editmenu = tk.Menu(menu)
    menu.add_cascade(label="Edit", menu=editmenu)
    editmenu.add_command(label="Description...", command=tk_flowchart.properties)
    editmenu.add_command(
        label="Clean layout",
        command=tk_flowchart.clean_layout,
        accelerator=CmdKey + "l",
    )

    # Help menu
    helpmenu = tk.Menu(menu)
    menu.add_cascade(label="Help", menu=helpmenu)
    if sys.platform.startswith("darwin"):
        root.createcommand("tk::mac::ShowHelp", tk_flowchart.help)

    root.bind_all("<" + CmdKey + "N>", tk_flowchart.new_file)
    root.bind_all("<" + CmdKey + "n>", tk_flowchart.new_file)
    root.bind_all("<" + CmdKey + "O>", tk_flowchart.flowchart_search)
    root.bind_all("<" + CmdKey + "o>", tk_flowchart.flowchart_search)
    root.bind_all("<" + CmdKey + "R>", tk_flowchart.run)
    root.bind_all("<" + CmdKey + "r>", tk_flowchart.run)
    root.bind_all("<" + CmdKey + "S>", tk_flowchart.save)
    root.bind_all("<" + CmdKey + "s>", tk_flowchart.save)
    root.bind_all("<" + CmdKey + "L>", tk_flowchart.clean_layout)
    root.bind_all("<" + CmdKey + "l>", tk_flowchart.clean_layout)

    # Work out and set the window size to nicely fit the screen
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    w = int(0.9 * sw)
    h = int(0.8 * sh)
    x = int(0.1 * sw / 2)
    y = int(0.2 * sh / 2)

    root.geometry("{}x{}+{}+{}".format(w, h, x, y))

    logger.debug("Finished initializing the rest of the GUI, drawing window")

    # Draw the flowchart
    tk_flowchart.draw()

    logger.debug("SEAMM has been drawn. Now raise it to the top")

    # bring it to the top of all windows
    root.lift()
    raise_app(root)

    # Check to see if the command line has flowcharts to open
    if len(args.flowcharts) > 0:
        logger.debug("open the following flowcharts:")
        if len(args.flowcharts) > 1:
            raise RuntimeError("Currently handle only one flowchart at a time")
        for filename in args.flowcharts:
            tk_flowchart.open(filename)

    logger.debug("and now enter the event loop")

    # enter the event loop
    root.mainloop()


def handle_dbg_level(level):
    global dbg_level

    dbg_level = level
    logging.getLogger().setLevel(dbg_level)


if __name__ == "__main__":
    locale.setlocale(locale.LC_ALL, "")

    flowchart()
