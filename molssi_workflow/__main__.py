import argparse
import molssi_workflow
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
    if platform.system() == 'Darwin':
        tmpl = 'tell application "System Events" to set frontmost of every process whose unix id is {} to true'  # nopep8
        script = tmpl.format(os.getpid())
        subprocess.check_call(['/usr/bin/osascript', '-e', script])
    root.after(100, lambda: root.attributes("-topmost", False))


def flowchart():
    """The standalone flowchart app
    """
    global app_name
    app_name = 'MolSSI Workflow'
    global dbg_level

    parser = argparse.ArgumentParser(
        description='MolSSI Workflow')
    parser.add_argument("-v", "--verbose", dest="verbose_count",
                        action="count", default=0,
                        help="increases log verbosity for each occurence.")
    args = parser.parse_args()

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

    workflow = molssi_workflow.Workflow()
    tk_workflow = molssi_workflow.TkWorkflow(master=root, workflow=workflow)
    # The data is implicitly initialized to none...

    ##################################################
    # Initialize the rest of the GUI, such as menus
    ##################################################
    logger.debug('Initializing the rest of the GUI')

    root.title(app_name)

    # The menus
    menu = tk.Menu(root)

    # Set the about and preferences menu items on Mac
    if sys.platform.startswith('darwin'):
        app_menu = tk.Menu(menu, name='apple')
        menu.add_cascade(menu=app_menu)

        app_menu.add_command(label='About ' + app_name,
                             command=tk_workflow.about)
        app_menu.add_separator()
        root.createcommand(
            'tk::mac::ShowPreferences',
            tk_workflow.preferences
        )
        root.createcommand(
            'tk::mac::OpenDocument',
            tk_workflow.open_file
        )
        CmdKey = 'Command-'
    else:
        CmdKey = 'Control-'

    root.config(menu=menu)
    filemenu = tk.Menu(menu)
    menu.add_cascade(label="File", menu=filemenu)
    filemenu.add_command(label="New",
                         command=tk_workflow.new_file,
                         accelerator=CmdKey + 'N')
    filemenu.add_command(label="Save...",
                         command=tk_workflow.save,
                         accelerator=CmdKey + 'S')
    filemenu.add_command(label="Save as...",
                         command=tk_workflow.save_file)
    filemenu.add_command(label="Open...",
                         command=tk_workflow.open_file,
                         accelerator=CmdKey + 'O')
    filemenu.add_separator()
    filemenu.add_command(label="Run", command=tk_workflow.run,
                         accelerator=CmdKey + 'R')

    # Control debugging info
    filemenu.add_separator()
    debug_menu = tk.Menu(menu)
    filemenu.add_cascade(label="Debug", menu=debug_menu)
    debug_menu.add_radiobutton(label='normal', value=30, variable=dbg_level,
                               command=lambda arg0=30: handle_dbg_level(arg0))
    debug_menu.add_radiobutton(label='info', value=20, variable=dbg_level,
                               command=lambda arg0=20: handle_dbg_level(arg0))
    debug_menu.add_radiobutton(label='debug', value=10, variable=dbg_level,
                               command=lambda arg0=10: handle_dbg_level(arg0))

    # Exiting
    filemenu.add_separator()
    filemenu.add_command(label="Exit", command=root.quit)

    helpmenu = tk.Menu(menu)
    menu.add_cascade(label="Help", menu=helpmenu)
    root.createcommand('tk::mac::ShowHelp',
                       tk_workflow.help)
    root.bind_all('<'+CmdKey+'N>', tk_workflow.new_file)
    root.bind_all('<'+CmdKey+'n>', tk_workflow.new_file)
    root.bind_all('<'+CmdKey+'O>', tk_workflow.open_file)
    root.bind_all('<'+CmdKey+'o>', tk_workflow.open_file)
    root.bind_all('<'+CmdKey+'R>', tk_workflow.run)
    root.bind_all('<'+CmdKey+'r>', tk_workflow.run)
    root.bind_all('<'+CmdKey+'S>', tk_workflow.save_file)
    root.bind_all('<'+CmdKey+'s>', tk_workflow.save_file)

    root.bind_all('<'+CmdKey+'`>', tk_workflow.print_edges)

    # Work out and set the window size to nicely fit the screen
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    w = int(0.9 * sw)
    h = int(0.8 * sh)
    x = int(0.1 * sw / 2)
    y = int(0.2 * sh / 2)

    root.geometry('{}x{}+{}+{}'.format(w, h, x, y))

    logger.debug('Finished initializing the rest of the GUI, drawing window')

    # Draw the flowchart
    tk_workflow.draw()

    logger.debug('Workflow has been drawn. Now raise it to the top')

    # bring it to the top of all windows
    root.lift()
    raise_app(root)

    logger.debug('and now enter the event loop')

    # enter the event loop
    root.mainloop()


def handle_dbg_level(level):
    global dbg_level

    dbg_level = level
    logging.getLogger().setLevel(dbg_level)


if __name__ == "__main__":
    locale.setlocale(locale.LC_ALL, '')

    flowchart()
