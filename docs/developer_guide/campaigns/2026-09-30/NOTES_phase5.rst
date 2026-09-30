Phase 5 -- Rules shared by the dialogs and the builder (2026-09-30, in progress)
===============================================================================

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

Next plug-ins
-------------

Plug-in by plug-in, choosing those with the most layout logic in their dialogs
(Gaussian, Psi4, MOPAC, LAMMPS, ...).
