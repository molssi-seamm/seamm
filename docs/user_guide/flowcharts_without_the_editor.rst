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
    seamm-flowchart validate my.flow [--fix]          # see Checking a flowchart
    seamm-flowchart convert old.flow -o new.flow    # e.g. 2.0 to 3.0
    seamm-flowchart migrate --root ~/SEAMM          # see below
    seamm-flowchart mcp                             # the MCP server, see below

``set``, ``insert``, ``remove`` and ``move`` write the flowchart back unless ``-o`` is
given. Values are ``name=value``, read as YAML, so ``10``, ``[1, 2]`` and
``{energy: {table: table1, column: E}}`` work; quote names with spaces or use
underscores. A step is addressed by position (``3``, ``3.2`` for the second step inside
step 3), by name (``ORCA/Energy``), or both (``3/Energy``).

Checking a flowchart
--------------------

``seamm-flowchart validate`` checks a flowchart's structure and every value, and asks
the steps to check themselves against the steps before them: an analysis step, for
example, checks that the MD before it samples what it needs. It reports two kinds of
problem:

- **Errors** stop a job: it is not submitted, and ``run_flowchart`` stops before any
  step runs.
- **Warnings** do not. A parallel Loop warns about a step in its body that writes its
  structure over the configuration all the iterations share, since that usually
  stops the job when the iterations are merged.

Where a check knows how to fix a problem, it gives the fix as parameters to set, and
``validate`` prints each as the ``seamm-flowchart set`` commands that make it.
``--fix`` applies the first fix offered for each problem and writes the flowchart back
(or to ``-o``). It applies one fix at a time and checks again after each, since fixes
can overlap: here both analysis steps need the same MD, sampled at least every 0.5 ps
and every 1 ps, and the first fix meets both needs:

.. code-block:: text

    $ seamm-flowchart validate nacl.flow
    'Dielectric Constant': all/position is not sampled in LAMMPS / NVT dynamics, but is
    needed for the dipole.
        Fix -- Turn on sampling of all/position every 500 fs in NVT dynamics:
            seamm-flowchart set nacl.flow 3.1.4 'atomic positions=by time interval'
            seamm-flowchart set nacl.flow 3.1.4 'atomic positions rate=500 fs'
    'Ionic Conductivity': all/position is not sampled in LAMMPS / NVT dynamics, but is
    needed for the displacement of the ions.
        Fix -- Turn on sampling of all/position every 1000 fs in NVT dynamics:
            seamm-flowchart set nacl.flow 3.1.4 'atomic positions=by time interval'
            seamm-flowchart set nacl.flow 3.1.4 'atomic positions rate=1000 fs'

    '--fix' applies the first fix of each, checking again after each fix.
    $ seamm-flowchart validate --fix nacl.flow
    Fixed: Turn on sampling of all/position every 500 fs in NVT dynamics
    No problems found.

The editor runs the same checks when you submit a job. It lists the problems with a
button for each fix; errors must be fixed before the job can be submitted, while with
only warnings left it can be submitted anyway. The MCP tool ``validate_flowchart``
returns the errors, the warnings and the fixes, each as the step's address, the
parameter and its value, which ``set_parameters`` applies; check again after
applying one.

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
variable, with units as ``$T K`` or ``[$T, K]``; an ``=`` expression is Python with
bare variable names. Both are checked as Python when set, so a mistake is reported then
rather than when the job runs. A spec is never run itself: it is always built into a
complete flowchart first.

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

Checking the flowchart as a whole
=================================

Beyond each value, ``validate`` checks the flowchart as a whole:

* a step that uses the model chemistry must come after a Model Chemistry step;
* a step can check itself against the steps before it. Analysis steps such as
  Diffusivity and Thermal Conductivity use this to check that the MD before them will
  sample what they need, for example the heat flux every two steps.

The same check runs when the editor submits a job, which shows the problems and does
not submit it, and when a job starts (``run_flowchart``), which then stops before
running any step. A problem is thus found before the MD runs rather than after it.

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

A job that is waiting or running can be stopped with ``kill_job``. It asks the job's
JobServer to stop it -- the local process, or the job in the queueing system, as the
user the JobServer runs as -- and the job is marked "killed", keeping its files and
record. A job that has finished, failed or been killed is refused. Stopping a job with
the queueing system directly (``scancel``) does not work as well: the JobServer takes
it for an interruption and runs the job again. A job that was killed or failed can be
run again with ``resume_job``: it continues from the last step it completed, and the
step it stopped in runs again from its start. If the flowchart's checkpoint no longer
matches -- the flowchart or its command line has changed -- nothing is run, the job's
files are left as they were, and ``job.out`` says why; resubmit it without asking to
resume to run it from the top. Settings that say only how a step runs, not what it
computes -- e.g. a parallel Loop's cores, memory and time per iteration -- may be
changed before resuming, except for a job checkpointed before seamm 2026.10.22, which
needs them as they were. There is no tool to delete a job.

The server also tells the assistant when to offer SEAMM. Asked to calculate a molecular
or materials property, or asked about one that can be computed, it offers -- after
giving any known values and their source -- to calculate it with SEAMM, in a line or
two: a method suited to the property and the size of the system, roughly how long it
will take, and a cheaper or a more accurate alternative. It proposes only methods that
your installed plug-ins provide, builds nothing until you agree, and does not offer for
purely conceptual questions. SEAMM is offered, not imposed: the assistant may have other
ways to calculate a property.
