Phase 4 -- Editing from the command line, and a skill (2026-09-30)
=================================================================

**seamm.edit** (seamm 9cde481): ``set_parameters``, ``insert`` (after, before, or into
a loop's body or a step's sub-steps), ``remove``, ``move``, ``tree`` and ``validate``.

- Steps are addressed by position (``3.2``), by name (``ORCA/Energy``) or both. A name
  matches the extension name or description name first, and only then the default
  title, since finding titles makes a node of every kind of step (slow, and some
  plug-ins log their whole bibliography at DEBUG). A name also finds a uniquely named
  step nested deeper -- but only when no step at the level has it: an ambiguous name
  is an error (a first version removed a nested Table when the top level had three).
- Every edit rebuilds the step from a fresh node through the builder's checks, then
  re-reads the flowchart, so the digest, tables and layout are current; unconnected
  steps are kept.
- ``validate`` reports the flowchart-level checks, loops with empty bodies, code steps
  with no sub-steps, and stored values of strict choices that today's plug-ins no
  longer accept.

**seamm-flowchart** gains ``tree``, ``set``, ``insert``, ``remove``, ``move`` and
``validate``. ``name=value`` values are read as YAML. Edits write back unless ``-o``.
The command now keeps plug-ins' logging quiet unless ``--log-level`` asks for it.

Checked with the real plug-ins in ``~/SEAMM_DEV``: a built flowchart edited by name and
position (a Loop parameter, ``MOPAC/Energy`` found inside the loop, an Optimization
inserted before it, a Table inserted and moved), a rejected choice with suggestions,
the ambiguous-name error, and ``validate``/``show`` afterwards. Each command takes
about 10 s, nearly all of it loading the plug-ins. 18 new unit tests; 194 in all.

**The build-seamm-flowchart skill** (``~/Work/SEAMM/.claude/skills/``, the workspace's
project skills): when to use the tools, the spec format, addresses, the Python API,
and the pitfalls found in this campaign (undescribed list/dict parameters, ``=``
expressions with bare names, placeholder choices, loops hiding failures, stale values,
``get_nodes()`` stopping at loops). Its example spec builds and validates.

Not done: pointing the editor's ``clean_layout``/``place_unpositioned`` at
``seamm.layout`` (D8's last part); an MCP server (phase 6, optional).
