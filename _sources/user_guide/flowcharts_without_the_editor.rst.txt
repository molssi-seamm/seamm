.. _flowcharts-without-the-editor:

*****************************
Flowcharts without the editor
*****************************

Flowcharts can be built, read, changed, checked and run without the graphical editor:
from the command line with ``seamm-flowchart``, from Python, or by an AI assistant
through SEAMM's MCP server. All of them check every step, parameter, choice, number and
unit as the editor does, and write a complete flowchart that the editor opens and the
JobServer runs.

Flowchart format 3.0
====================

Flowcharts (``.flow`` files) now have a second, readable format, 3.0, written in YAML.
It holds the flowchart's metadata, the versions of the plug-ins it was made with, a
digest that identifies its content, every parameter of every step, steps that are not
connected (kept for the editor), and the layout. Format 2.0, the JSON format, is still
read: it is converted to 3.0 as it is loaded, by a converter that never changes.

Format 3.0 was introduced in two releases, so that every installation could read it
before any wrote it: SEAMM 2026.10.1 read 3.0 but still wrote 2.0 from the editor, and
since 2026.10.2 everything writes 3.0. Setting the environment variable
``SEAMM_FLOWCHART_FORMAT`` to ``2.0`` writes the old format, for an installation that
must still exchange flowcharts with one older than 2026.10.1.

Jobs run between updating to 2026.10.1 and to 2026.10.2 still saved 2.0 flowcharts;
``seamm-manager flowcharts migrate`` converts them (see below).

The seamm-flowchart command
===========================

``seamm-flowchart`` is installed with SEAMM. Each command loads the installed plug-ins
first, which takes several seconds.

.. code-block:: text

    seamm-flowchart steps [--json]                  # every step, by group
    seamm-flowchart steps ORCA                      # the sub-steps of a step
    seamm-flowchart describe "ORCA/Energy"          # parameters, choices, defaults, help
    seamm-flowchart build spec.yaml -o my.flow      # build a flowchart from a spec
    seamm-flowchart show my.flow                    # what a flowchart does, as a spec
    seamm-flowchart tree my.flow                    # its steps and their addresses
    seamm-flowchart set my.flow ORCA/Energy basis=def2-TZVP
    seamm-flowchart insert my.flow Energy method=MP2 --after ORCA/Optimization
    seamm-flowchart remove my.flow 3.2
    seamm-flowchart move my.flow 4 --before 2
    seamm-flowchart validate my.flow
    seamm-flowchart convert old.flow -o new.flow    # e.g. 2.0 to 3.0
    seamm-flowchart migrate --root ~/SEAMM          # see below
    seamm-flowchart mcp                             # the MCP server, see below

``set``, ``insert``, ``remove`` and ``move`` write the flowchart back unless ``-o`` is
given. Values are ``name=value``, read as YAML, so ``10``, ``[1, 2]`` and
``{energy: {table: table1, column: E}}`` work; quote names with spaces or use
underscores. A step is addressed by position (``3``, ``3.2`` for the second step inside
step 3), by name (``ORCA/Energy``), or both (``3/Energy``).

Specs
-----

A *spec* is a short YAML description of a flowchart that gives only what differs from
the defaults. ``seamm-flowchart build`` turns it into a complete flowchart, and
``seamm-flowchart show`` turns a flowchart back into one:

.. code-block:: yaml

    title: Water optimization and frequencies
    description: B3LYP/def2-SVP optimization, then frequencies
    steps:
    - Model Chemistry: {model chemistry: "ORCA:DFT@B3LYP/bse:def2-SVP"}
    - FromSMILESStep: {smiles string: O}
    - ORCA:
        steps:
        - Optimization
        - Frequencies
    - Loop:
        type: Foreach
        variable: SMILES
        values: C CC CCC
        body:
        - FromSMILESStep: {smiles string: $SMILES}

Steps are named by extension name, as the editor's step menu shows them. ``steps:``
holds the sub-steps of a code step, and ``body:`` the steps of a loop (the Join a loop
needs is added). Units are written ``300 K`` or ``[300, K]``, and SEAMM's conversions
between energy, temperature, wavenumbers and frequency are allowed. ``$name`` uses a
variable; an ``=`` expression is Python with bare variable names. A spec is never run
itself: it is always built into a complete flowchart first.

From Python
===========

.. code-block:: python

    from seamm.builder import FlowchartBuilder

    fb = FlowchartBuilder(title="Methane to propane")
    fb.add("Model Chemistry", model_chemistry="ORCA:DFT@B3LYP/bse:def2-SVP")
    with fb.loop(type="Foreach", variable="SMILES", values="C CC CCC") as body:
        body.add("FromSMILESStep", smiles_string="$SMILES")
        orca = body.add("ORCA")
        orca.add("Optimization")
    fb.write("alkanes.flow")             # checks the flowchart first

``seamm.spec`` builds and reduces specs (``spec.build(text)``, ``spec.reduce(fc)``), and
``seamm.edit`` reads and changes existing flowcharts (``read``, ``set_parameters``,
``insert``, ``remove``, ``move``, ``tree``, ``validate``).

Settings that depend on each other
==================================

A step can say which of its parameters apply given the others, narrow a list of choices,
and fill in a value that follows from another. The step's dialog and these tools share
the same rules, so a setting with no effect is refused, with the reason (for example
"it applies when 'use model chemistry' is 'no'"), and a value that contradicts another is
refused too. Set the controlling parameters in the same command. ``describe`` shows when
each parameter applies, and ``validate`` reports combinations that cannot work.

Converting an installation's flowcharts
=======================================

The flowchart of every job (``flowchart.flow`` in its directory) and the datastore's
record of it can be converted to format 3.0 in one step:

.. code-block:: bash

    seamm-manager flowcharts status       # how many job flowcharts are still 2.0
    seamm-manager flowcharts migrate      # dry run, confirm, convert

``migrate`` shows what it would change, asks for confirmation, stops the JobServer and
web UI, backs up the datastore, renames each job's original flowchart to
``flowchart.v2.flow`` (unchanged) beside the new ``flowchart.flow``, converts the
datastore, and restarts the services. Back up the ``Jobs`` directory first. Moving the
datastore aside and letting the web UI rebuild it is *not* a conversion: the rebuilt
datastore keeps no accounts and converts nothing.

The step-by-step guide to upgrading an installation, including what the messages
mean, how to undo the conversion and how to convert your own flowcharts, is
`Upgrading to flowchart format 3.0 <https://molssi-seamm.github.io/getting_started/installation/upgrading_format3.html>`_ in the main SEAMM documentation.

AI assistants: the MCP server
=============================

``seamm-flowchart mcp`` serves these operations as tools to AI assistants that support
the Model Context Protocol, such as Claude Desktop and Claude Code. It needs the
optional ``mcp`` package (``pip install 'seamm[mcp]'``). It keeps the plug-ins loaded,
so each call takes under a second. For Claude Code:

.. code-block:: bash

    claude mcp add --scope user seamm -- ~/SEAMM/venv/bin/seamm-flowchart mcp

Its tools list and describe steps; build, show, check, convert and edit flowcharts; and
run them through a dashboard: list the dashboards and their projects and queues, submit
a job, follow it, and read its files. Submitting checks the flowchart first and needs a
queue when the dashboard has queues. The dashboards and credentials are read from the
installation's ``dashboards.ini`` and ``~/.seamm.d/seammrc``, never written, and the
credentials are never shown. An assistant should confirm the dashboard, project and
queue with you before submitting, since a submission starts a real calculation.

The server also tells the assistant when to offer SEAMM. Asked to calculate a molecular
or materials property, or asked about one that can be computed, it offers -- after
giving any known values and their source -- to calculate it with SEAMM, in a line or
two: a method suited to the property and the size of the system, roughly how long it
will take, and a cheaper or a more accurate alternative. It proposes only methods that
your installed plug-ins provide, builds nothing until you agree, and does not offer for
purely conceptual questions. SEAMM is offered, not imposed: the assistant may have other
ways to calculate a property.
