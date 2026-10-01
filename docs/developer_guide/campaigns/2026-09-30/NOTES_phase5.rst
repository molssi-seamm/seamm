Phase 5 -- Rules shared by the dialogs and the builder (2026-09-30, in progress)
================================================================================

Q2 decided yes (Paul: "start phase 5").

In seamm (9ce27eb, d5be0d6)
---------------------------

``seamm.Parameters`` gains the rules a step's dialog and the flowchart builder share:

- ``applies(key, values)`` -- whether a parameter has any effect given the others. The
  default follows ``"applies_when"`` in the parameter's definition: a mapping from other
  parameters to a value, a list of values, or ``{"not": value(s)}``. Conditions chain
  (a parameter applies only if those it names do), and a variable or expression counts
  as met, since its value is known only when the flowchart runs.
- ``choices(key, values)`` -- narrowed valid choices, or None (override).
- ``implied(values)`` -- values that others imply (override).
- ``problems(values)`` -- combinations that cannot work; by default, values outside
  narrowed choices (extend in overrides).
- ``not_applicable_reason(key, values)`` -- why a parameter does not apply, following
  the chain of conditions by default ("it needs 'method', which does not apply (it
  applies when 'use model chemistry' is 'no')"); override for plug-in rules.
- ``describe_condition(key)``, ``applicable(values)``, ``current_values()``.

``values`` is any {name: value} -- the dialog passes its current widget values, the
builder the parameters' own.

Used by: the builder (refuses a setting that has no effect, with the reason; fills in
implied values, refusing a contradiction; refuses problems; restores the step when it
refuses), ``spec.reduce``/``show`` (leaves out settings that do not apply),
``describe`` ("applies when ..."), and ``edit.validate`` (reports problems, ignores
values that do not apply).

**Release note:** a parameter definition containing ``"applies_when"`` is rejected by
older seamm (``Parameter.update`` refuses unknown keys), so a plug-in using it must
require the new seamm, and seamm must be released first.

ORCA (orca_step 97a07fe)
------------------------

- ``EnergyParameters`` declares ``applies_when`` for method, functional type,
  functional, basis, basis source, basis-set extrapolation, extrapolation family, the
  checkpoint name and the two initial-guess sub-controls, and overrides the rules for
  the rest: no extrapolation for F12 methods or for steps that need a gradient or
  Hessian (``extrapolation = False`` on Optimization, Frequencies, BSSE); the
  extrapolation replaces the basis and its source; F12 methods take only the F12 bases,
  from ORCA itself; the functionals are those of the functional type, and a functional
  implies its type. Frequencies and BSSE list the Energy settings they do not use
  (``unused``); BSSE's fragment atoms apply only for specified fragments.
- The Energy dialog, and so its sub-steps, asks these rules what to show and offer;
  indentation and order stay in the dialog. The sub-steps' ``_show_cbs()`` overrides
  are gone.
- ``tests/test_gui.py`` lays out every sub-step for every choice that drives the layout
  and checks both ways that exactly the controls that apply are shown.
- Checked with the builder: the functional refused while the model chemistry is used;
  a meta-GGA functional sets its type; an F12 method gets cc-pVTZ-F12 from ORCA, and a
  non-F12 basis with it is refused; extrapolation is accepted in Energy and refused in
  Optimization with the reason; polarizability refused in Frequencies; fragment atoms
  only with specified fragments.

Model Chemistry (model_chemistry_step ec14597)
----------------------------------------------

Its dialog is a picker over what the installed programs offer, stored as one string, so
its rule is a check: the model chemistry must be offered (any basis). Discovery, the
basis-free match and the message are now module functions used by both the run-time
check and ``ModelChemistryParameters.problems()``; an unavailable model chemistry is
refused when the flowchart is built. A variable (``$mc``) passes.

Checked in ~/SEAMM_DEV
----------------------

orca_step and model_chemistry_step installed editable (their checkouts match the
installed releases); job 3984, a spec-built ORCA B3LYP/def2-SVP energy of water, ran
through the JobServer (-76.3197 E_h). Tests: seamm 205, orca_step 152 (+4 dialog; the
one failure, ``test_frequencies_ir_spectrum_graph``, predates this work: a
``line.graph_template`` lookup), model_chemistry_step 99.

Gaussian, Psi4, MOPAC and LAMMPS (2026-09-30)
---------------------------------------------

Done in parallel, each following the ORCA implementation; each is committed locally
on its ``dev`` and installed editable in ``~/SEAMM_DEV``:

.. list-table::
   :header-rows: 1

   * - Plug-in
     - Commit
     - Rules
     - Tests
   * - gaussian_step
     - 397bd97, f1d1d3a
     - level/method/functional, DFT-only (functional, grid, dispersion), dispersion
       narrowed to the functional's list, freeze-cores by method, basis only for
       methods with one, Optimization/Thermodynamics/Stability specifics, ``unused``
       per sub-step; Stability's ``advanced_method`` implied from ``method``
     - 34 (17 new)
   * - psi4_step
     - 78c5330
     - level/method/functional, freeze-cores by method, dispersion narrowed and
       implied, convergence sub-switches, Thermochemistry's "use existing
       parameters", BSSE fragment atoms
     - 29 (15 new)
   * - mopac_step
     - 8ab92e9
     - all simple conditions: HF-only and CI-only settings, MOZYME, COSMO,
       convergence, optimization method, lattice optimization
     - 26 (13 new)
   * - lammps_step
     - 72035b0
     - Initialization (k-space, charges), Velocities, Minimization and NPT stresses
       (one ``pressure_keys`` override), NVE run control and trajectories, NVT
       thermostats, NPT barostats
     - 104 (+3 skipped; 39 new)

Each dialog now asks the rules what to show (and, for Gaussian and Psi4, what to offer
and set); a dialog test lays out every sub-step for every layout-driving choice and
checks both ways. Layout logic that duplicated conditions was removed (LAMMPS: about
500 lines of stress-table branches replaced by one helper; Gaussian Stability's copy of
the calculation layout replaced by an override). One deliberate change everywhere:
when a driving choice is a variable, the controls depending on it are shown (the old
dialogs hid some of them, so they could not be set at all).

**Dialog bugs fixed on the way:** Gaussian's dispersion list did not follow the
functional, ``input only`` did not hide ``file handling`` until reopened, the
dispersion choices had a typo (``DG2``) and lacked ``GD2``/``PFD``, and a built
Stability flowchart could run the wrong method; Psi4's dispersion update raised
TypeError (``value`` used as a method) and a typed method name raised KeyError;
LAMMPS's Heat Flux dialog could not open (KeyError), plus stress-table and label
fixes.

**Core fixes from their reports** (seamm e862b43, 4b364c6, b4fbc40): "is neither A
nor B" for negated lists; the builder restores only values when refusing
(``from_dict`` lost plug-ins' ``__init__`` changes, e.g. Gaussian Stability's narrowed
methods); ``Parameter.__repr__`` returned a non-string; ``validate`` warns about empty
sub-steps only for code steps (Dimer Builder's are optional); and a plug-in's
``references.bib`` is found for an editable install too (MOPAC job 3985 failed with
``KeyError: 'Stewart_2012'`` until then; job 3986 then finished).

Checked in ``~/SEAMM_DEV``: the 30 most recent job flowcharts all validate; the
Testing flowcharts show only old problems (8 with ORCA's renamed BSSE parameter
``fragment A atoms``, one stale ``CCSD(T)-F12D``; both since fixed); MOPAC job 3986 (PM7, COSMO
water, built from a spec) ran.

Run-time bugs fixed (2026-09-30)
--------------------------------

Committed locally on each ``dev``; not pushed.

- **LAMMPS** (7950681): an explicit k-space method on a charged system raised
  KeyError (``P["kspace_style"]``); the pair style and ``kspace_style`` line now come
  from a testable ``explicit_kspace()``. Minimization's ``Sxy`` was read from ``Sxz``.
  NPT's six damping times were converted as pressures (now times), the "y and z"
  branch set ``Szz1 = Szz1`` (now ``Syy1``), and ``mtk`` and ``nreset`` are now
  written to the ``fix npt`` line. NVE's ``run_control`` / ``maximum_time`` /
  ``control_properties`` are marked not implemented (``not_implemented``), so the
  builder refuses them with that reason, rather than being implemented. Also:
  Velocities' ``remove_momentum`` default ended in a period, so was not one of its
  own choices; old flowcharts' spelling is translated.
- **Psi4** (293719a): ``energy.get_method`` raised KeyError when the functional was
  given by its short name (the dispersion check looked it up by that name).
- **ORCA** (0170ba3): old flowcharts' ``fragment A atoms`` becomes ``fragment
  atoms: "X; rest"`` (a last group ``rest`` = the remaining atoms) and ``auto (2
  molecules)`` becomes ``auto (molecules)``; the method ``CCSD(T)-F12D``, renamed
  ``CCSD(T)-F12D/RI`` in da696be, is translated too.
- **seamm** (b56a2c9): ``problems()`` no longer flags a variable inside a named
  value (Model Chemistry's basis ``{'name': '$basis'}``).

After these, all 58 Testing and recent-job flowcharts in the sweep validate.

LAMMPS settings hidden but used at run time (2026-10-01)
--------------------------------------------------------

Paul chose all four suggestions (lammps_step 9929131):

- ``kspace_smallq`` applies whenever there is a k-space method (it always sets which
  atoms count as charged; "automatic" may use ``msm/cg`` with it).
- The QEq convergence and iterations apply to "default for forcefield" too.
- ``Pdamp`` and the stress damping times apply to the Berendsen barostat too
  (``press/berendsen`` requires them; the default 1000 fs was always used).
- ``allow shear`` applies only to a solid with the Nose-Hoover barostat
  (``press/berendsen`` cannot control a triclinic cell, per the LAMMPS docs), and is
  ignored at run time where it does not apply.

Found by running the check job in ``~/SEAMM_DEV``:

- LAMMPS writes one box for all the steps of a LAMMPS step, so a Berendsen NPT
  followed by a step allowing shear (or on a non-orthorhombic cell) failed in LAMMPS
  ("Cannot use fix press/berendsen with triclinic box"). This is now caught before
  running, with a clear message (job 3988). A builder check would need to look
  across sub-steps and at the structure, so it is left to run time.
- Graph templates were not found for an editable seamm (seamm 560429e), the cause of
  ORCA's long-failing ``test_frequencies_ir_spectrum_graph`` too.
- Job 3991 (Berendsen with ``Pdamp`` 500 fs; then, in its own LAMMPS step, Nose-Hoover
  with shear) finished.
- When LAMMPS itself failed (e.g. "Lost atoms", job 3989), lammps_step did not notice
  and failed later in the trajectory analysis with an unrelated ``IndexError``. It now
  finds the ``ERROR`` in ``log.lammps`` (or the screen output, for other processes) and
  stops with the sub-step, LAMMPS's message, the last command, advice for common
  errors and where the log is; no ``success.dat`` is written (lammps_step bda3a70,
  job 3993).

Smaller gaps fixed (2026-10-01)
-------------------------------

The last of the agents' findings, each checked with a job in ``~/SEAMM_DEV``:

- **Psi4** (6d9e07b): BSSE's 17 ignored Energy settings are ``unused`` (hidden,
  refused); Thermochemistry's plots apply only with its own settings (the Output tab
  hides); right after Initialization, "use existing parameters" falls back to its own
  settings at run time, as the dialog does (job 3995). The builder still needs
  ``use existing parameters: no`` to set Energy settings there.
- **MOPAC** (f6e5c81): ``structure`` is shown; an explicit ``initial`` after the first
  sub-step crashed (UnboundLocalError); Force Constants with MOZYME raised
  NotImplementedError -- MOPAC's FORCE works with MOZYME (checked directly), so only
  the main input is used and ``structure``/``MOZYME follow-up`` are unused there, and
  Energy's analysis no longer expects a follow-up that does not apply (job 3994 failed
  on that, 3997 finished). Also ``["MOZYME"] == "always"`` (always False) and the
  "will be che Hartree-Fock" description.
- **Gaussian** (bfee70f): the ``system name`` edit had been applied to
  ``configuration name`` (choice listed twice, "keep current name" lost); old ``DG2``
  is translated to ``GD2`` (job 3996).
- **seamm** (1ebcff6): ``Parameters.from_dict`` keeps ``__init__`` edits.
  (packmol_step's 11 failing output comparisons are a pre-existing number-format
  difference, the same with the old code.)
