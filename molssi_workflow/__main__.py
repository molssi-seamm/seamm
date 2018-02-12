import argparse
import molssi_workflow
import locale
import logging
import os
import platform
import subprocess
import sys
import tkinter as tk


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

    parser = argparse.ArgumentParser(
        description='MolSSI Workflow')
    parser.add_argument("-v", "--verbose", dest="verbose_count",
                        action="count", default=0,
                        help="increases log verbosity for each occurence.")
    args = parser.parse_args()

    # Sets log level to WARN going more verbose for each new -v.
    numeric_level = max(3 - args.verbose_count, 0) * 10
    logging.basicConfig(level=numeric_level)

    ##################################################
    # Initialize Tk
    ##################################################
    root = tk.Tk()

    ##############################################################
    # Create the various objects that we need: the model, the view
    # and the data
    ##############################################################

    workflow = molssi_workflow.Workflow()
    tk_workflow = molssi_workflow.TkWorkflow(master=root, workflow=workflow)
    # The data is implicitly initialized to none...

    ##################################################
    # Initialize the rest of teh GUI, such as menus
    ##################################################
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
    filemenu.add_command(label="Run", command=tk_workflow.run)
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
    root.bind_all('<'+CmdKey+'S>', tk_workflow.save_file)
    root.bind_all('<'+CmdKey+'s>', tk_workflow.save_file)

    # Work out and set the window size to nicely fit the screen
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    w = int(0.9 * sw)
    h = int(0.8 * sh)
    x = int(0.1 * sw / 2)
    y = int(0.2 * sh / 2)

    root.geometry('{}x{}+{}+{}'.format(w, h, x, y))

    # Draw the flowchart
    tk_workflow.draw()

    # bring it to the top of all windows
    root.lift()
    raise_app(root)

    # enter the event loop
    root.mainloop()


if __name__ == "__main__":
    locale.setlocale(locale.LC_ALL, '')

    flowchart()
