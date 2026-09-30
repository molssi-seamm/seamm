Phase 1 -- Catalog and builder (2026-09-30)
===========================================

**Result:** flowcharts can be built from Python and looked up from the command line.
The builder writes today's format 2.0 through ``Flowchart.write()``, so nothing
downstream changes. Not yet released.

What was added
--------------

All in ``seamm`` core, as plain modules rather than the ``seamm/builder/`` package the
plan sketched (``setup.py`` only packages ``seamm`` itself, and four modules do not need
a package):

``seamm/catalog.py``
    ``Catalog``: the steps of a flowchart's plug-in namespace, from the installed
    plug-ins. ``steps()``, ``resolve(name)`` (extension name, description name or default
    title; ignores case, spaces, underscores and hyphens; suggests close matches),
    ``describe(path)`` (``"ORCA/Energy"`` reaches sub-steps), ``subcatalog(step)``.
    ``enumeration_of()`` treats a string enumeration as one choice (see below).

``seamm/builder.py``
    ``FlowchartBuilder`` / ``Sequence`` / ``Step``: ``add(step, params, **kwargs)``,
    ``with loop(...) as body``, ``step.add(...)`` for sub-steps, ``validate()``,
    ``layout()``, ``to_text()``, ``write()``. ``set_parameters()`` and
    ``check_value()`` check every value as it is set:

    - unknown parameter → error naming the closest parameters;
    - ``enum``/``enumeration``/``boolean`` kinds → must be a choice (case corrected);
      ``string`` kinds with an enumeration take anything (the list is suggestions);
    - Python ``True``/``False`` → ``"yes"``/``"no"`` for any yes/no choice;
    - integers and floats → must be numbers (or a choice such as ``"default"``);
      stored as text, as the editor stores them;
    - units as ``(value, units)``, a Pint quantity, or ``"300 degC"``; compared by
      dimensionality (see below);
    - ``$variables`` and ``=expressions`` pass unchecked.

    A step whose parameters fail is not added. The builder makes the Join in front of
    each loop and sets every edge's type and subtype. ``validate()`` checks that a step
    with ``use model chemistry = yes`` follows a Model Chemistry step (for a sub-step:
    before the step holding it); ``to_text()``/``write()`` refuse a flowchart with
    problems unless ``check=False``.

``seamm/layout.py``
    ``layout(flowchart)``: the editor's clean layout, headless -- 300 × 70 grid, loop
    body one column right starting level with the loop, step after the loop below the
    body, return edge routed down, right, up and into the Join's east side (the same
    coordinates ``TkFlowchart.clean_layout`` computes), loop edge ``e→w``, subflowcharts
    recursively. Phase 4 can point ``clean_layout`` and ``place_unpositioned`` at it.

``seamm/flowchart_cli.py``
    The ``seamm-flowchart`` console script: ``steps [STEP] [--json]`` and
    ``describe STEP [--json]``.

Tests: ``tests/test_builder.py`` (50 tests with stand-in steps, no plug-ins needed) and
``tests/test_builder_plugins.py`` (3 tests with the real loop_step, table_step,
from_smiles_step and mopac_step, skipped when they are missing; builds a flowchart,
reads it back with ``Flowchart.from_text`` and compares every parameter). Full suite:
116 passed.

Checked live
------------

- Rebuilt the structure of ``Testing/test.flow`` (Parameters, Model Chemistry, from
  SMILES, ORCA with Optimization and Energy). Wrong names and choices were caught with
  suggestions (``extra_keyword`` → "extra keywords"; ``DLPNO-CCSD`` → the ORCA method
  list; ``Frm SMILES`` → "from SMILES").
- Built ``Testing/builder_loop.flow`` (a table, a Foreach loop over C, CC, CCC with
  from SMILES and MOPAC PM7 energies written to the table, then Save as) and ran it:
  three energies in ``energies.csv``.
- Opened it in the real ``TkFlowchart`` (``open()``) and rendered the canvas: the
  editor moved no node on opening, and the drawing matches a hand-made clean layout.
- ``seamm-flowchart`` against all installed plug-ins: 46 main steps; ``describe
  orca/energy`` lists the parameters, choices and help.

Tested in ~/SEAMM_DEV (2026-09-30)
----------------------------------

``seamm`` installed editable from the checkout into ``~/SEAMM_DEV/venv`` (``uv pip
install --no-deps -e``; the only change to the venv, ``uv pip check`` clean; the
pre-install freeze is kept for rollback). With that Python and its plug-ins:

- the full test suite passes (123 tests, including the real-plug-in ones);
- **job 3979** (project *test*, ``local`` queue, submitted through the web UI on port
  55155 and run by SEAMM_DEV's JobServer): a built flowchart with a Table, a ``For i``
  loop choosing the molecule with an ``=`` expression, MOPAC PM7 energies into the
  table, and Save as. Finished, no loop errors; ``energies.csv`` has the same three
  energies as the earlier run (-13.43, -14.52, -17.43 kcal/mol);
- its ``flowchart.flow`` opens in the editor code with no node moved.

Two earlier jobs failed, and both taught something:

- **Job 3977** (the Foreach/SMILES version) failed in every iteration with
  ``KeyError: 'SMILES'`` in table_step's "Append a row to" -- a table_step bug with
  pandas 3, not a builder problem (finding 7).
- **Job 3978** used ``=('C', 'CC', 'CCC')[int($i) - 1]``. In an ``=`` expression the
  variables are bare Python names (``Parameter.get`` passes the text to ``eval``), so the
  ``$`` is a syntax error at run time. The builder now compiles every ``=`` expression
  when it is set and explains the bare-name rule if it finds a ``$``.

Findings
--------

1. **Flowchart.digest() stops at the first loop.** ``Flowchart.digest`` (and
   ``get_nodes``) walk the flowchart with ``Node.next()``, which follows only ``next``
   edges; ``Loop`` does not override it. The digest therefore ignores the loop body and
   everything after the loop: two flowcharts that differ only there have the same
   ``sha256`` *and* ``sha256_strict`` (checked with the builder). The datastore
   deduplicates flowcharts by the unique ``sha256_strict``, so a job whose flowchart
   differs only inside or after a loop is linked to the first such flowchart's row.
   Each job directory's own ``flowchart.flow`` is right, so jobs run correctly; the
   datastore's record of the flowchart can be wrong.

   **Not fixed now (Paul, 2026-09-30).** The datastore takes ``sha256_strict`` from the
   file's own metadata (written when it was saved), not by recomputing it, so a fix
   would split the world: files saved before keep the old digest, files saved after get
   a new one, and an unchanged flowchart with a loop would get a second row. Instead the
   format 3.0 digest (D2) walks the whole flowchart, and the phase 3 migration
   recomputes every digest from the job directories' own files at once -- which must
   also *split* rows that the bug merged (Q6).
2. **Units: any conversion SEAMM's registry allows is valid.** ``seamm_util``'s unit
   registry deliberately enables contexts, so energy converts to temperature,
   wavenumbers and frequency (kcal/mol → K, cm⁻¹ → K, THz → K), as is common in
   chemistry; the editor's ``Parameter.units`` allows the same. The builder checks
   ``Q_(1, units).to(default_units)``. (A first version compared dimensionality and
   wrongly rejected kcal/mol for a temperature; corrected after Paul's review.) The
   contexts also chain -- Å and even kg convert to K -- so the check stops only truly
   incompatible units such as Pa for a temperature, and unknown ones.
3. **Parameter.units setter bug -- fixed.** When the new units differ in
   dimensionality it converted from ``self._data["units"]``, which raises ``KeyError``
   if the units were never read or set. With context conversions allowed, the builder
   reached it (a temperature in kcal/mol). It now converts from ``self.units``.
4. **table_step enumerations** (fixed in table_step 2026.9.30). ``index column``, ``row`` and ``column`` use
   ``tuple("--none--")`` / ``tuple("current")`` -- tuples of letters, so the editor's
   dropdowns offer single characters. Should be ``("--none--",)`` / ``("current",)``.
   The catalog now treats a string enumeration as one choice, but ``tuple("current")``
   is already a tuple of letters and cannot be told apart.
5. **The structure of list and dict parameters is undocumented.** Table's ``columns``
   holds ``{"name", "type", "default"}`` for Create but ``{"name", "value"}`` for
   Append a row; results dicts hold ``{"table", "column"}`` or ``{"property"}``. The
   catalog can only show "The column definitions." A first test flowchart appended
   empty rows because of this. Phase 5's shared rules (or better help text in the
   plug-ins) should describe these structures.
6. **Loading the plug-ins takes 6 s warm, 25 s cold** on this Mac (lammps_step 1.9 s,
   read_structure_step 1.5 s, qcarchive_step 1.0 s the largest). Every
   ``seamm.Flowchart()`` pays it, so a Catalog is shared where possible
   (``FlowchartBuilder(catalog=...)``); a cached step list could make ``seamm-flowchart
   steps`` instant later.
7. **table_step "Append a row to" fails with pandas 3 for any text column -- in
   production too.** It maps column dtypes to types with ``== "object"``, but pandas 3
   gives a text column ``StringDtype``, so the column is missing from ``column_types``
   and the step raises ``KeyError``. ``~/SEAMM/venv`` and ``~/SEAMM_DEV/venv`` both have
   pandas 3.0.6 (the old conda ``seamm-dev`` has 2.2.3, which is why it worked there).
   **Fixed and released** in table_step 2026.9.30 (PR #97, with the dropdown fix of
   finding 4): types
   now come from the kind of dtype; regression flowchart (built with this builder) in
   ``table_step/tests/flowcharts/append_text_rows.flow``; job 3977's flowchart reran
   cleanly in SEAMM_DEV as job 3980.
8. **The ``WebUI-Dev`` entry in ``~/.seamm.d/seammrc`` is stale**: the web UI on port
   55155 rejects its username or password (401); the ``dev`` entry's credentials work.
