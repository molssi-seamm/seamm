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
--------------------------------------------

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
``fragment A atoms``, one stale ``CCSD(T)-F12D``); MOPAC job 3986 (PM7, COSMO
water, built from a spec) ran.

Decisions for Paul (found by the agents, not changed)
-----------------------------------------------------

- **LAMMPS: hidden in the dialog but read at run time** -- ``kspace_smallq``,
  ``qeq convergence``/``iterations`` (ReaxFF under "default for forcefield"),
  ``Pdamp`` and the stress damping (Berendsen barostat), ``allow shear`` for fluids.
  The rules follow the dialog, so the builder refuses them too.
- **LAMMPS run-time bugs**: ``initialization.py:431`` reads ``P["kspace_style"]``
  (no such key: any explicit k-space method on a charged periodic system raises
  KeyError); Minimization ``Sxy = _P["Sxz"]``; NPT's damping times converted as a
  pressure and ``Szz1 = Szz1`` (should be ``Syy1``) in the "y and z" branch;
  ``nreset``, ``mtk`` and ``run_control`` shown or defined but never read.
- **Psi4**: BSSE shows Energy settings ``bsse.py`` ignores (could be ``unused``);
  Thermochemistry shows plot settings that have no effect with "use existing
  parameters"; ``energy.get_method`` raises KeyError for a functional's short name;
  "Thermochemistry right after Initialization" depends on position, so the builder
  cannot check it.
- **MOPAC**: ``structure`` is never shown though used at run time; Force Constants
  fails at run time if MOZYME gives more than one input (a ``problems()`` candidate).
- **Gaussian**: ``configuration name`` edits in ``__init__`` are still lost by
  ``from_dict``; a stored ``DG2`` dispersion (never offered) is now refused.
- **ORCA**: old flowcharts using ``fragment A atoms`` cannot be read (the BSSE
  redesign renamed it without a translation in ``BSSEParameters.__init__``).
