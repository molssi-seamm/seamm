Phase 0 -- Inventory and triage (2026-09-30)
============================================

**Result: in format 2.0 flowcharts, only a node's parameters are settings.** Paul's view
holds for every current plug-in. Every other attribute is either a constant or run-time
state set in the step's ``__init__``, or a cache that the GUI derives from the
parameters. The exceptions are three kinds of *legacy* file, written before a plug-in
moved its settings into ``parameters``; only one of them needs handling in the converter.

Method
------

- Parsed every flowchart on this Mac (1,332 files; the 38 other ``*.flow`` files are
  JavaScript type files in ``seamm_webui/frontend/node_modules``) and listed each
  attribute outside ``_uuid``, ``_title``, ``extension``, ``parameters`` and
  ``x``/``y``/``w``/``h``, keeping only non-empty values (not ``None``, ``0``, ``""``,
  ``[]``, ``{}``, or ``citation_level`` 2).
- For each attribute found, traced it to the plug-in's code: where it is set, and
  whether any headless code reads it before setting it.
- Counted jobs and flowcharts in each machine's datastore (read-only queries).

Extra attributes in current plug-ins: all junk
----------------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 25 30 45

   * - Step
     - Attributes
     - Where they come from
   * - Table (table_step)
     - ``calls``
     - Counter set to 0 in ``__init__``, incremented in ``run`` (``table.py:37``,
       ``:326``). A non-zero value restored from a file would shift the ``frequency``
       test; none was found.
   * - Loop (loop_step)
     - ``table``, ``table_handle``
     - ``None`` in ``__init__``, set in ``run`` from the ``table`` variable
       (``loop.py:83-84``, ``:320-321``). Always ``None`` in files.
   * - Energy, Optimization, BandStructure, DOS, ChooseParameters (dftbplus_step);
       FHI-aims sub-steps
     - ``results``, ``mapping_to_primitive``, ``mapping_from_primitive``
     - ``None`` in ``__init__`` (``dftbplus_step/base.py:96-99``,
       ``fhi_aims_step/substep.py:44-48``), set while running. Always ``None`` in files.
   * - Reaction Path
     - ``optimizer``
     - ``None`` in ``__init__``, set while running (``reaction_path.py:182``,
       ``:1574``). Always ``None`` in files.
   * - Diffusivity, Thermal Conductivity
     - ``tensor_labels``, ``colors``, ``citation_level`` 1, the analysis arrays
     - Plotting constants and a citation level set in ``__init__``; the arrays are empty
       in every file.
   * - Every node
     - ``_tables``
     - A GUI cache: ``TkNode.setup_results`` sets ``node.tables`` from the ``table``
       entries of the ``results`` parameter (``tk_node.py:1164-1179``), and
       ``Node.existing_tables()`` gathers them so later steps can offer the tables in
       their dropdowns. **Derivable from the parameters; phase 2 must recompute it when
       a flowchart is loaded.**
   * - Gaussian Energy, Optimization, Wavefunction Stability, Thermodynamics;
       Thermochemistry
     - ``_method`` (non-null in 349 nodes)
     - A GUI cache: set by ``reset_dialog`` from the method parameter
       (``gaussian_step/tk_energy.py:226-242``) and read only by the Tk results tab to
       filter the results list (``tk_node.py:1055``, ``:1194``). The headless code uses
       ``get_method(P)``. Recomputed whenever the dialog opens. Nothing in the current
       thermochemistry_step reads it (one node, from an older version).
   * - Every node
     - ``_title``
     - Always the class's default title (12 pairs such as ``FromSMILESStep`` → "from
       SMILES", ``NVT`` → "NVT dynamics"). No plug-in or GUI code lets a user rename a
       step. Derivable; not needed in 3.0.

The comment in ``Node.to_dict()`` that keeps ``_method`` "because
forcefield_step/forcefield.py does not use parameters yet" is stale: forcefield_step
uses ``ForcefieldParameters`` (``forcefield.py:40``).

Legacy files: settings stored as attributes
-------------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 25 35 40

   * - Where
     - What
     - Handling
   * - lammps_step Minimization, versions 2023.6.17 to 2024.7.21.1 (11 nodes in job
       directories on this Mac)
     - ``convergence``, ``etol``, ``ftol`` (a Pint quantity), ``maxiters``,
       ``maxevals`` and their ``*_method`` / ``*_variable`` companions. These were the
       real settings until commit 5ee392d (2025-03-16) moved them into
       ``MinimizationParameters``. 9 nodes hold the old defaults; **2 use
       ``convergence: crude``**. All ``*_method`` values are "is" (a literal value).
     - **Map in the converter** (one small legacy table): ``convergence``, ``etol``,
       ``ftol`` → the parameters of the same name; ``maxiters`` → ``nsteps`` and
       ``maxevals`` → ``nevaluations`` (to confirm against 5ee392d in phase 3). Loading
       these files today silently runs them with the current defaults.
   * - table_step before commit acfb417 (2021-12-21): ``~/SEAMM/flowcharts/tutorial3.flow``
       only (3 Table nodes, ``parameters`` null)
     - ``_method`` ("read", "save", "print current row"), ``name``, ``filename``,
       ``index_column``, ...
     - **Replace the file** with Tutorial 3 from Zenodo (record 10108673, 2023) rather
       than mapping.
   * - ``seamm_dashboard/data/projects/MyProject/Job_000001/flowchart.flow``
     - A test fixture from before plug-in versions and Parameters: LAMMPS settings as
       attributes, ``_visited``, ``_description``, and a ``lammps_flowchart`` key.
     - Leave it or delete it; the old Dashboard is superseded by the webui.

Other findings
--------------

- **Malformed edges.** Three SEAMM_DEV jobs (3885, 3886, 3976) contain five edges with
  ``edge_type`` ``null`` (3) or ``"next"`` (2) instead of ``"execution"`` -- flowcharts
  built by scripts that called ``add_edge`` without an edge type, the exact pitfall the
  builder removes. The converter treats any edge with subtype ``next`` as an execution
  edge.
- **Edge subtypes** across all files: ``next`` 16,837, ``loop`` 695, ``exit`` 433. A
  loop at the end of a flowchart has no exit edge.
- **Subflowcharts** are stored under the key ``subflowchart`` by all 20 plug-ins that
  have one (DFTB+, LAMMPS, MOPAC, ORCA, Gaussian, Psi4, VASP, FHI-aims, TorchANI, Dimer
  Builder, Reaction Path, Structure, Subflowchart, Diffusivity, Thermal Conductivity,
  Thermochemistry, Thermomechanical, Energy Scan, Conformer Search, ...), except
  ``lammps_flowchart`` in the Dashboard fixture.
- **Parameter values** are plain JSON (str 194,538; list 5,226; float 5,006; dict 4,691;
  int 3,429). No Pint, datetime or other encoded object appears inside a parameter; the
  only Pint value found is the legacy Minimization ``ftol`` attribute.
- **YAML round trip.** PyYAML 6.0.3's ``safe_dump`` quotes ``yes``, ``no``, ``on``,
  ``null``, ``~`` and ``0.10``, and ``safe_load`` gets back exactly the same strings;
  ``ORCA:DFT@B3LYP/bse:def2-SVPD``, ``$SMILES`` and ``2026.6.28`` pass unquoted. **So the
  converter, which starts from typed JSON, needs no snapshot of parameter kinds.**
  Coercing by kind (D3) is still needed for hand-written specs.

Inventory
---------

Jobs and flowcharts in each datastore (``jobs`` rows / ``flowcharts`` rows / distinct
flowcharts used by jobs / first job), 2026-09-30:

.. list-table::
   :header-rows: 1

   * - Machine and datastore
     - Jobs
     - Flowcharts
     - Used by jobs
     - First job
   * - This Mac, ``~/SEAMM_DEV``
     - 2,076
     - 981
     - 950
     - 2022-02-24
   * - This Mac, ``~/SEAMM``
     - 322
     - 282
     - 168
     - 2023-11-07
   * - This Mac, ``~/SEAMM/SV``
     - 109
     - 127
     - 79
     - 2022-02-25
   * - ChemAI, ``seamm`` user (``/D3/psaxe/SEAMM/Jobs``)
     - 2,477
     - 321
     - 252
     - 2022-09-16
   * - ChemAI, ``psaxe``
     - 0
     - 0
     - 0
     -
   * - MolSSI10 (``/mnt/hdd2/psaxe/SEAMM/Jobs``)
     - 347
     - 237
     - 164
     - 2023-06-29
   * - TinkerCliffs/ARC (``/projects/seamm/SEAMM/Jobs``)
     - 53,081
     - 56
     - 56
     - 2025-05-28
   * - paul.local
     - 0
     - 0
     - 0
     -

Loose flowcharts outside job directories: this Mac 115 (``~/SEAMM/flowcharts`` 27,
``Testing/`` 27, package tests and docs); a few dozen on each of ChemAI (``~/ARC``,
``~/GM``, ``~/flowcharts``, ``Science_Flowcharts``), TinkerCliffs (``~/GM``,
``~/flowcharts``) and MolSSI10 (``~/Work``, tests).

Every job directory holds its own ``flowchart.flow``, so TinkerCliffs has about 53,000
copies of 56 flowcharts. **The migration converts by content**: hash each file's text,
convert each distinct flowchart once, and reuse the result.

Consequences for the design
---------------------------

- **D4 simplifies.** No settings hooks are needed: a node's settings are its
  ``parameters``, full stop. A 3.0 step is its step name, parameters, sub-steps (for
  subflowchart steps) and optional layout. ``title`` is dropped.
- **Phase 2 must rebuild the GUI caches on load**: ``node.tables`` from the ``results``
  parameter (a headless helper beside ``TkNode.setup_results``) and each step's
  ``method`` when its dialog opens (already the case). Test with the Exercise-Tk-dialogs
  pattern on a flowchart with tables.
- **D10's frozen converter is generic** apart from one legacy table (lammps_step
  Minimization before 2025.3.16). No snapshot of plug-in parameter kinds is needed.
- **Migration by content hash**, with a cache, because of the job arrays.
- Remove the stale ``_method`` exception and comment from ``Node.to_dict()`` when the 2.0
  writer is removed (phase 3).
