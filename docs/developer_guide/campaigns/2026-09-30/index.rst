2026-09-30 -- Building flowcharts programmatically, and flowchart format 3.0
============================================================================

Status (2026-09-30): **phase 1 done (committed on dev, not released).** Q1, Q4 and Q7 decided by Paul
(``seamm`` core; keep ``.flow``; rename originals in job directories). The decisions
reached in discussion are recorded under *Decided*; the ones still open are under *Open
questions* and are Paul's.

**Phase 0 result** (``NOTES_phase0.rst``): only a node's parameters are settings. Every
other attribute in a 2.0 file is a constant, run-time state, or a GUI cache derivable
from the parameters. The one legacy exception that needs handling is lammps_step
Minimization before 2025.3.16 (settings kept as attributes; 11 nodes, 2 of them
non-default), mapped by the converter. TinkerCliffs holds about 53,000 job copies of 56
flowcharts, so migration converts by content hash.

**Phase 1 result** (``NOTES_phase1.rst``): ``seamm.catalog``, ``seamm.builder``,
``seamm.layout`` and the ``seamm-flowchart`` command; a built loop flowchart ran and
opened unchanged in the editor. Found that ``Flowchart.digest()`` stops at the first
loop, so the datastore can link a job to the wrong flowchart; left for D2 and the phase 3
migration rather than fixed now.

**Where the work happens (Paul, 2026-09-30):** all of this campaign is developed and
tested in the development installation, ``~/SEAMM_DEV``, with ``seamm`` installed
editable from the checkout into ``~/SEAMM_DEV/venv``. No PRs or releases until the
whole switch is ready, so no other installation changes before then.

Contents:

.. toctree::
   :glob:
   :maxdepth: 2

   NOTES_*

Goal
----

Programmers and AI systems can create, read and edit SEAMM flowcharts without the
graphical editor, with the same guarantees the editor gives: only real steps, only real
parameters, only valid values, and a layout the editor opens cleanly.

Along the way, the heavy, hard-to-read format 2.0 is replaced by a YAML format 3.0 that
is readable and still complete enough to reproduce a calculation. Format 2.0 is then
removed from SEAMM; a small frozen converter remains for old files.

What happens today
------------------

Checked in the code and on this Mac on 2026-09-30.

**Building works without Tk.** ``seamm_exec`` loads and runs flowcharts with no Tk root
(``seamm_exec/exec_flowchart.py``: ``seamm.Flowchart(...)`` then ``flowchart.read()``).
Step nodes can be created headlessly through ``Flowchart.create_node(extension)`` or the
step's factory; ``node.parameters[key].value = ...`` works, and ``Flowchart.write()``
serializes correctly. A few scripts and tests already do this for single nodes
(``model_chemistry_step/tests/test_model_chemistries.py``; the BSSE validation scripts
in ``orca_step/docs/developer_guide/campaigns/2026-08-03/``), but nothing wires nodes and
edges together and writes a flowchart. ``import seamm`` imports ``tkinter``, so tkinter
must be installed, but no display is needed.

**Nothing checks values when they are set.** ``Parameter.value`` just stores what it is
given (``parameters.py``); ``enumeration`` is used only for widgets and for formatting
in ``get()``. Only units are checked (the ``units`` setter checks dimensionality). The
rules that keep invalid combinations out of a step (the "prevent, don't catch" rule in
``CLAUDE.md``) live in each plug-in's ``tk_*.reset_dialog``, which a script cannot use.
The headless run-time checks are the only backstop.

**Easy things to get wrong by hand:**

- ``Flowchart.add_edge`` defaults to ``edge_type=None``; every real edge is
  ``"execution"``.
- The headless ``Node.default_edge_subtype()`` returns ``""``; ``TkNode``'s returns
  ``"next"``. ``Node.next()`` follows only ``"next"`` edges.
- A loop has a fixed shape, which the GUI builds partly by hand (the user draws the
  return arrow). From ``table_step/tests/flowcharts/test1.flow``:

  - ``... -> Join -(next)-> Loop``
  - ``Loop -(loop, anchors e->w)-> body1 -> ... -> bodyN``
  - ``bodyN -(next, anchors s->e, routed around the body)-> Join`` -- the body returns
    to the Join, not to the Loop; ``Loop.description_text`` relies on this.
  - ``Loop -(exit, anchors s->n)-> next step``

  The only edge subtypes in use are ``next``, ``loop`` and ``exit``. There are no
  if/branch/switch steps; the only control-flow steps are Loop and the built-in
  Join/Split (``seamm/builtins.py``).
- Parameter keys contain spaces and capitals (``"Hirshfeld charges"``).
- Extension names and titles differ (``FromSMILESStep`` vs "from SMILES").
- Sub-steps come from a per-plug-in namespace (``org.molssi.seamm.orca`` etc.); a
  subflowchart plug-in builds its subflowchart in ``__init__`` (MOPAC only when
  ``title == "MOPAC"``, and it needs a real ``flowchart`` argument).

**GUI placement.** Commit 5c01b94 (2026-09-29) lets the editor open files whose nodes
have no position (``place_unpositioned``, ``tk_flowchart.py``). It stacks unplaced
nodes one row below their predecessor and knows nothing about loops: body and exit land
in one column. Missing edge anchors default to ``s``/``n``. The menu action
``clean_layout()`` does know loops (body one column right, upward edges routed around
it) but is Tk code.

**What format 2.0 contains.** A header (``#!/usr/bin/env run_flowchart``,
``!MolSSI flowchart 2.0``), a ``#metadata`` JSON section and a ``#flowchart`` JSON
section (``Flowchart.to_text``). ``test.flow``, 6 steps, is 549 lines, almost all of it
default values. Each node is ``Node.to_dict()``: the node's whole ``__dict__`` minus a
short exclusion list, plus any attribute whose name contains "flowchart" as a nested
flowchart. Parameters are encoded with their class and module
(``seamm_util/seamm_json.py``) and decoded by importing that module and class, so every
plug-in's class and module names are part of the file format.

**The digest defines what matters.** ``Node.digest()`` hashes the parameter values
(defaults included), the subflowchart, and in strict mode the plug-in version.
Positions, UUIDs, module paths and the other attributes are outside it. The datastore's
``flowcharts`` table stores ``sha256``, a **unique** ``sha256_strict``, the parsed JSON
(``json`` column, i.e. the 2.0 structure), and the metadata
(``seamm_datastore/database/models.py``).

**Run-time state leaks into files.** Of the 1,370 files named ``*.flow`` on this Mac,
1,332 are flowcharts (1,330 format 2.0, 2 format 1.0); the other 38 are JavaScript
type files under ``seamm_webui/frontend/node_modules``. 1,217 of the flowcharts are in
job directories (``~/SEAMM_DEV/Jobs`` 851, ``~/SEAMM/Jobs`` 256, ``~/SEAMM/SV/Jobs``
110), 27 in ``~/SEAMM/flowcharts``, 27 in ``Testing/``, the rest in package tests and
docs. Attributes found outside the standard set (``_uuid``, ``_title``, ``extension``,
``parameters``, ``x``/``y``/``w``/``h``, ``_tables``, ``citation_level``,
``_method``):

.. list-table::
   :header-rows: 1

   * - Step
     - Extra attributes
   * - Table
     - ``calls`` (2,241 nodes)
   * - Loop
     - ``table``, ``table_handle`` (695)
   * - Diffusivity, Thermal Conductivity
     - the analysis arrays (``M``, ``Jcf``, ``GK_integral``, ``msds``, ...; 15 each)
   * - Energy, Optimization, BandStructure, DOS, ChooseParameters (dftbplus_step;
       also FHI-aims sub-steps)
     - ``results``, ``mapping_to_primitive``, ``mapping_from_primitive``
   * - Reaction Path
     - ``optimizer`` (43)
   * - Energy, Optimization, Wavefunction Stability, Thermodynamics, Thermochemistry,
       Table
     - a non-null ``_method``

``Node.from_dict()`` writes all of these straight back into the node's ``__dict__`` when
a file is opened. Phase 0 (``NOTES_phase0.rst``) traced each one: none is a setting in
a current plug-in.

**Environment is not recorded.** No code in ``seamm``, ``seamm_exec`` or
``seamm_jobserver`` writes the job's package versions (a ``pip freeze`` equivalent).
Only each node's own ``version`` in the flowchart, and the citations, record versions.

**Zenodo.** 10 flowchart records (15 versions), all published by Paul between
2022-08-18 and 2024-10-31, found by the keyword ``seamm-flowchart`` that the Publish and
Open dialogs use: three DFTB+ flowcharts, two MOPAC, SEAMM Tutorials 1, 3 and 5, fluid
density with OPLSAA, and FHI-aims tutorial 1. Zenodo records cannot be changed; new
versions can be published.

**SEAMM has two users today**, so every existing flowchart can realistically be found
and converted.

Decided (2026-09-30 discussion)
-------------------------------

- **YAML, at two levels.** A *spec* holds only the choices that matter and is what
  people and AI write; a *resolved flowchart* holds every value and is what runs and is
  archived. The same split as ``pyproject.toml`` and a lock file.
- **The resolved YAML replaces format 2.0 entirely** as format 3.0. Format 2.0 is
  removed from SEAMM; a frozen converter turns old files into 3.0.
- **Conversion keeps what was recorded.** A converted job flowchart keeps the versions
  and values it ran with; it is never "refreshed" with current plug-ins or defaults.
- **The spec is never executed.** It always resolves to a 3.0 flowchart first (see Q3).
- **The code lives in** ``seamm`` **core** (Q1): ``seamm/catalog.py``,
  ``seamm/builder.py``, ``seamm/layout.py``, the 3.0 reader and writer, and a
  ``seamm-flowchart`` console script (``seamm/flowchart_cli.py``).
- **Unconnected steps are kept, outside the digest** (Paul, 2026-09-30). Steps the
  editor shows but that are not connected to the flowchart (316 in 219 of 1,320 files)
  go in an ``unconnected:`` section of a 3.0 file, at each level; they are not part of
  ``sha256`` or ``sha256_strict``, and specs leave them out since they never run.
- **Format 3.0 keeps the** ``.flow`` **extension** (Q4); readers detect the format from
  the content (``format: MolSSI flowchart 3.0`` vs the ``!MolSSI flowchart 2.0`` line).

Design
------

D1. Spec and resolved flowchart
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A spec:

.. code-block:: yaml

   title: Water optimization
   steps:
     - Parameters: {variables: {SMILES: {default: O}}}
     - Model Chemistry: {model chemistry: "ORCA:DFT@B3LYP/bse:def2-SVPD"}
     - from SMILES: {smiles string: $SMILES}
     - ORCA:
         steps:
           - Optimization: {}
           - Energy: {extra keywords: TightSCF}
     - Loop:
         type: For
         variable: i
         start: 1
         end: 10
         body:
           - ...

- A step is named by extension name, display name or title; all three resolve through
  the catalog (D5), with close-match suggestions on failure.
- Missing parameters mean "the installed plug-in's default". Resolving fills them in and
  can report which defaults were applied.
- Subflowchart steps take ``steps:``; Loop takes ``body:``. Join nodes, edge subtypes
  and anchors never appear.

A resolved flowchart (format 3.0):

.. code-block:: yaml

   #!/usr/bin/env run_flowchart
   format: MolSSI flowchart 3.0
   metadata: {title: ..., description: ..., keywords: [...], creators: [...], grants: [...]}
   requires: {seamm: 2026.9.29, orca_step: 2026.6.28, from_smiles_step: 2025.5.14}
   digest: {sha256: ..., sha256_strict: ...}
   steps:
     - id: "3"
       step: ORCA
       steps:
         - id: "3.1"
           step: Energy
           parameters:
             method: DLPNO-CCSD(T)
             basis: def2-TZVP
             temperature: [298.15, K]
             # ...every parameter
   layout:            # optional; GUI only
     "3": [150, 315]

- The shebang line is a YAML comment, so the file stays executable.
- ``requires`` replaces the per-node ``version``: one entry per plug-in package.
- ``id`` is short and stable within the file; it replaces the 128-bit UUID. Execution
  order is list order; loop structure is nesting. No explicit edges.
- ``layout`` holds positions only; the editor recomputes edge routing (D8). A file
  without it opens with the headless layout.
- Parameter values are typed by the catalog on reading (see D3), with units as
  ``[value, units]``.
- Dropped entirely: ``item``, ``module``, ``class``, ``__class__``/``__module__``,
  ``_tables``, ``citation_level``, UUIDs, edge coordinates, and all non-declared
  attributes (D4).

D2. Digest for format 3.0
~~~~~~~~~~~~~~~~~~~~~~~~~

Phase 1 found that today's ``Flowchart.digest()`` stops at the first loop (it follows
only ``next`` edges), so it ignores loop bodies and everything after a loop. The new
digest must walk the whole step tree. It is deliberately not fixed in 2.0: the datastore
reads the digest from each file's metadata, so changing it mid-stream would give
unchanged flowcharts new rows. The phase 3 migration recomputes all digests at once.

Redefine the digest from the resolved content rather than Python's ``str()`` of a dict:
SHA-256 of a canonical JSON serialization (sorted keys, no whitespace) of the step tree
-- step names, nesting, parameter values and units -- plus, for ``sha256_strict``, the
``requires`` versions. Metadata and layout stay outside it, as today. The datastore's
``sha256``/``sha256_strict`` columns are recomputed during migration (D10).

D3. Reading YAML safely
~~~~~~~~~~~~~~~~~~~~~~~

YAML 1.1 loaders (PyYAML's default) read unquoted ``yes``/``no``/``on``/``off`` as
booleans; SEAMM uses those strings everywhere. The reader coerces each value by the
parameter's ``kind`` from the catalog, and the writer quotes anything that would not
round-trip. A YAML 1.2 loader (``ruamel.yaml``) avoids most of this but is not required
if coercion is done.

D4. Serialize parameters only
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The 3.0 writer never walks ``__dict__``. A step is its step name, its parameters, its
sub-steps (for a subflowchart step) and, optionally, its position. Nothing else is
written; ``title`` is always the class default and is dropped. Phase 0 confirmed that no
current plug-in keeps settings outside ``parameters``, so no per-step hooks are needed.

Two GUI caches, previously restored from the file, must be rebuilt when a flowchart is
loaded: ``node.tables`` (from the ``table`` entries of the ``results`` parameter, as
``TkNode.setup_results`` does; ``Node.existing_tables()`` feeds later steps' table
dropdowns) and each step's ``method`` for the results tab (already recomputed by
``reset_dialog`` when the dialog opens).

D5. Catalog
~~~~~~~~~~~

Built at run time from:

- the plug-in entry points (``org.molssi.seamm`` and each ``org.molssi.seamm.<plugin>``
  sub-namespace) and each step's ``my_description`` (name, group, description);
- each node class's ``parameters`` definition (kind, default, enumeration, units, help);
- the plug-in's ``metadata.py`` where it has one (methods, basis sets, results).

Exposed as ``seamm-flowchart steps`` and ``seamm-flowchart describe "ORCA/Energy"``,
both with ``--json``. It also supplies the kinds for D3 and the defaults for reducing a
resolved flowchart to a spec.

D6. Python builder API
~~~~~~~~~~~~~~~~~~~~~~

A thin layer over real ``Node`` objects:

.. code-block:: python

   from seamm.builder import FlowchartBuilder

   fb = FlowchartBuilder(title="Water optimization")
   fb.add("Parameters", variables={"SMILES": {"default": "O", "help": "..."}})
   fb.add("Model Chemistry", model_chemistry="ORCA:DFT@B3LYP/bse:def2-SVPD")
   fb.add("from SMILES", smiles_string="$SMILES")
   orca = fb.add("ORCA")
   orca.add("Optimization")
   orca.add("Energy", extra_keywords="TightSCF")
   with fb.loop(type="For", variable="i", start=1, end=10) as body:
       body.add("Energy", ...)
   fb.write("water.flow")

- ``smiles_string`` maps to ``"smiles string"``; ``params={...}`` also works.
- Values are checked as they are set: unknown key (with suggestions), value outside the
  enumeration unless it is a ``$variable`` or expression, wrong kind, incompatible
  units.
- The builder creates Join nodes, sets edge types and subtypes, and computes the layout.
- ``FlowchartBuilder.from_spec()`` / ``.to_spec()`` and ``.read()`` connect it to D1.

D7. CLI
~~~~~~~

::

   seamm-flowchart steps [--json]
   seamm-flowchart describe <step> [--json]
   seamm-flowchart build spec.yaml -o x.flow        # resolve a spec
   seamm-flowchart show x.flow                      # reduce to a spec
   seamm-flowchart set x.flow "ORCA/Energy" basis=def2-TZVP
   seamm-flowchart insert|remove|move x.flow ...
   seamm-flowchart validate x.flow
   seamm-flowchart convert old.flow [-o new.flow]   # the frozen 2.0 converter (D10)

Steps are addressed by path of titles or ids (``ORCA/Energy``, ``3.1``). Every command
has ``--json`` so an AI can drive it through a shell.

D8. Shared layout
~~~~~~~~~~~~~~~~~

Move the logic of ``clean_layout()`` into a headless function (grid 300 x 70, loop body
one column right, exit below, return edge routed around the body back to the Join) that
the builder, the 3.0 reader and the editor's ``clean_layout`` / ``place_unpositioned``
all call. That also fixes the loop gap in ``place_unpositioned``.

D9. Validation
~~~~~~~~~~~~~~

- **Phase 1:** per parameter (name, enumeration, kind, units) and per flowchart, e.g.
  ``use model chemistry = yes`` with no Model Chemistry step earlier in the flow
  (``Node.previous_nodes()`` already supports this). The run-time checks in each step
  remain the backstop.
- **Phase 2 (Q2):** headless rules in the parameter definitions -- ``visible_when`` /
  ``valid_when``, or a ``Parameters.validate(P)`` hook -- used by both ``reset_dialog``
  and the builder, so neither can build what the other forbids. The builder can then
  also warn about settings that have no effect (a ``functional`` when the method is not
  DFT). Adopted plug-in by plug-in, starting with ORCA and Model Chemistry.

D10. Retiring format 2.0
~~~~~~~~~~~~~~~~~~~~~~~~

**The frozen converter** reads a 1.0 or 2.0 file as plain JSON and writes a 3.0 file.

- It imports no plug-in. Everything it needs is in the file: extension names, versions,
  every parameter value and its units, edges, subflowcharts, positions.
- It needs no snapshot of plug-in parameter kinds: it starts from typed JSON, and a
  YAML dumper quotes ``yes``/``no`` and the like (checked in phase 0). Its only
  plug-in-specific knowledge is one legacy table: lammps_step Minimization before
  2025.3.16, whose ``convergence``, ``etol``, ``ftol``, ``maxiters`` and ``maxevals``
  attributes become parameters. It never changes after release.
- It treats any edge with subtype ``next`` as an execution edge, whatever its
  ``edge_type`` (phase 0 found scripted flowcharts with ``null`` and ``"next"``).
- It turns edges into list order and nesting (Loop body, Join removed), UUIDs into short
  ids, per-node versions into ``requires`` (if two nodes of one package disagree, the
  newer is recorded and the disagreement reported).
- It copies structure, parameters and positions, drops everything else, and reports
  any non-empty dropped attribute per step.
- Migration converts by content: each distinct file text is converted once and the
  result reused (TinkerCliffs has about 53,000 job copies of 56 flowcharts).
- It lives permanently in a place that never changes (Q5), and the GUI, run_flowchart
  and the Dashboard call it automatically when they meet a 2.0 header. That is an
  import path only; no 2.0 code remains in ``Flowchart``, ``Node`` or the plug-ins.

**Migration targets:**

- Job directories on every machine: the 3.0 file sits beside the original, whose
  content stays untouched as the record: the original is renamed ``flowchart.v2.flow``
  and the 3.0 file is written as ``flowchart.flow`` (Q7). This Mac has 1,217.
  The other machines are MolSSI10, paul.local, TinkerCliffs/ARC and ChemAI (ChemAI
  needs Paul's explicit OK for each action).
- Each datastore's ``flowcharts`` table: rewrite ``json`` to the 3.0 structure,
  recompute ``sha256``/``sha256_strict`` (D2), and resolve any collisions the new digest
  creates (two old rows that differed only in leaked state now match).
- ``~/SEAMM/flowcharts`` (27), ``Testing/`` (27), the plug-ins' ``tests/`` and docs
  flowcharts, and the two format-1.0 files.
- Zenodo: publish a new 3.0 version of each of the 10 records. The DOIs of the older 15
  versions keep serving 2.0 files forever, which is why the converter must stay
  available. Check the tutorials' links: any that cite a version DOI rather than the
  concept DOI need updating.
- Downstream readers that look for the ``!MolSSI flowchart`` header line: the Dashboard
  (``seamm_dashboard/routes/jobs/views.py``), the webui, and the datastore's
  ``get_or_create_from_file``.

**Verification:** for every converted file, load the 3.0 file with the current
plug-ins and compare each parameter value with the value recorded in the 2.0 file.
Mismatches and drops go in a report; the digest is not used for this, since D2 changes
its definition.

D11. Record the environment in each job
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A complete flowchart still does not reproduce a calculation under newer plug-in code.
Each job directory should record the installed package versions (e.g.
``environment.txt`` from ``importlib.metadata``) at start. Small, independent of the
rest, and can go in any phase.

D12. AI access
~~~~~~~~~~~~~~

The CLI with ``--json`` is enough for Claude Code and any agent with a shell. A
``build-seamm-flowchart`` skill documents it. An MCP server exposing the same
operations as tools is optional and last; it is worthwhile only for AI clients without
a shell (a desktop or web chat, or an assistant inside the webui).

Open questions (Paul's)
-----------------------

Q1. **Location.** *Decided 2026-09-30:* ``seamm`` core.

Q2. **Phase-2 validation.** Worth it, given it touches every plug-in's parameter
    definitions over time?

Q3. **Spec in jobs.** Recommended: no. run_flowchart, the JobServer and the Dashboard
    accept only resolved 3.0 (and 2.0 through the converter). A spec is always resolved
    first.

Q4. **File extension for 3.0.** *Decided 2026-09-30:* keep ``.flow``, detect the
    format from the content. File associations, the Open dialog's filters, the
    Dashboard's upload and ``flowchart.flow`` in job directories keep working.

Q5. *Decided 2026-09-30:* a frozen module in ``seamm`` (``seamm/convert_v2.py``), with
    a test that forbids any import from SEAMM or plug-ins. **Where the frozen converter
    lives.** A module in ``seamm`` that is never edited, or
    a tiny separate package (e.g. ``seamm_flowchart_v2``) pinned forever. The separate
    package is more clearly "frozen" and can be installed on its own to read an old
    Zenodo file.

Q6. *Decided 2026-09-30:* each job points at the row made from its own
    ``flowchart.flow`` -- rows that now match are merged, rows the loop bug merged are
    split -- and rows left unused are deleted after a backup. **Datastore digest
    collisions.** When the new digest merges rows that differed only
    in leaked state, re-point their jobs to one row (recommended) or keep both rows with
    the strict digest cleared on the later one? The reverse also happens: rows that the
    loop bug merged must be split, each job pointing at a row made from its own
    ``flowchart.flow``.

Q7. **File names in converted job directories** (follows from Q4).
    *Decided 2026-09-30: the recommendation.* Rename the original to ``flowchart.v2.flow`` (content unchanged) and write the 3.0 file as
    ``flowchart.flow``, so everything that opens a job's ``flowchart.flow`` gets 3.0.
    Alternative: leave ``flowchart.flow`` as 2.0 and write ``flowchart.v3.flow``, relying
    on the converter's import path whenever the standard name is read.

Phases
------

Each phase is released before the next starts; shared libraries are released before
the plug-ins that use them, with the minimum version pinned.

**Phase 0 -- Inventory and triage.** *Done 2026-09-30* (``NOTES_phase0.rst``). Only
parameters are settings; one legacy map for the converter; inventory of every machine's
datastore.

**Phase 1 -- Catalog and builder.** *Done 2026-09-30* (``NOTES_phase1.rst``). D5, D6
with per-parameter and flow-level validation (D9 phase 1), writing through today's
``Flowchart.write()`` (format 2.0). Tested by building ``Testing/builder_loop.flow``,
running it, and opening it in the editor; ``test.flow``'s structure was rebuilt but not
run (its ORCA DLPNO-CCSD(T) optimization is too expensive for a check).

**Phase 2 -- Format 3.0.** D1-D4 and D8: the 3.0 reader and writer (parameters only,
rebuilding ``node.tables`` on load), the new digest, spec resolution and reduction, the headless layout. Test:
every flowchart in ``Testing/`` and the plug-ins' ``tests/`` goes 3.0 → spec → 3.0 with
identical content, and runs.

**Phase 3 -- Converter and migration.** D10: the frozen converter; the 2.0 import path
in the GUI, run_flowchart and the Dashboard; migrate this Mac (job directories,
datastores, local flowcharts), then the other machines; publish the 10 Zenodo versions;
update tutorial links; remove the 2.0 reader and writer from ``Flowchart``/``Node``;
change the default writer to 3.0. Test: value-by-value verification report with no
unexplained mismatches.

**Phase 4 -- CLI editing.** D7's ``set``/``insert``/``remove``/``move``/``validate``,
and the ``build-seamm-flowchart`` skill (D12).

**Phase 5 -- Shared validation rules** (if Q2 is yes), plug-in by plug-in.

**Phase 6 -- Optional MCP server.**

D11 (environment record) can be done at any point.

Risks
-----

- **Leaked state that was really a setting.** Phase 0 found only the lammps_step
  Minimization legacy case on this Mac; other machines' files may hold more. Mitigation:
  the converter reports every non-empty dropped attribute, and the value-by-value
  check.
- **Digest change and the datastore.** ``sha256_strict`` is unique; the migration must
  handle collisions (Q6) inside one transaction, after a backup.
- **Half-migrated machines.** A 3.0 file reaching a machine whose SEAMM predates phase 3
  cannot be read. Mitigation: upgrade every machine's SEAMM before writing 3.0 by
  default; keep writing 2.0 until then.
- **Plug-ins whose nodes need a real flowchart to construct** (MOPAC reads
  ``flowchart.root_directory``). The builder always passes one.

Key files
---------

- ``seamm/seamm/{flowchart.py, node.py, graph.py, parameters.py, plugin_manager.py,
  builtins.py, join_node.py}``
- ``seamm/seamm/{tk_flowchart.py, tk_node.py, tk_edge.py}`` -- placement, layout, edges
- ``loop_step/loop_step/{loop.py, tk_loop.py}`` -- loop edges
- ``orca_step/orca_step/{orca.py, tk_orca.py, metadata.py, energy_parameters.py}`` -- a
  step with a subflowchart
- ``seamm_util/seamm_util/seamm_json.py`` -- how parameters are encoded in 2.0
- ``seamm_exec/seamm_exec/exec_flowchart.py`` -- headless loading and execution
- ``seamm_datastore/seamm_datastore/database/models.py`` -- the ``flowcharts`` table
- ``seamm_dashboard/seamm_dashboard/routes/jobs/views.py``,
  ``seamm_webui/seamm_webui/util.py`` -- readers of the header
- ``table_step/tests/flowcharts/test1.flow`` -- reference loop structure
