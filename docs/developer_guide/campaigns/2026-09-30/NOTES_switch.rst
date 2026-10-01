The switch -- checklist (draft for Paul, 2026-10-01)
====================================================

Everything in this campaign so far is in ``~/SEAMM_DEV`` as local commits. The switch
releases it and moves every installation, flowchart and Zenodo record to format 3.0.
Nothing below is done until Paul approves; each outward step (push, PR, release,
another machine, Zenodo) is a separate, confirmed action. ChemAI needs Paul's OK for
each action.

**The ordering rule:** a machine that runs jobs must read 3.0 *before* any desktop
writes 3.0, or a job sent to it fails at once (old ``run_flowchart`` cannot read 3.0;
an old datastore cannot record it). So seamm is released twice: first able to read 3.0
but still writing 2.0, then -- once every machine has it -- writing 3.0.

0. Decisions (Paul, 2026-10-01: the recommendations)
----------------------------------------------------

- [x] **Two seamm releases**: release 1 reads 3.0 and writes 2.0; release 2 writes 3.0.
- [x] **Q3**: no spec inside a job; only complete 3.0 (or 2.0 through the converter)
  is run.
- [x] **The old seamm_dashboard is retired** everywhere; the web UI replaces it.
  *This Mac, 2026-10-01:* it was a conda-era launchd agent
  (``org.molssi.seamm.dev_dashboard``, the ``seamm-dev`` conda env, port 55066), not a
  seamm-manager service; unloaded, and its plist moved to ``~/SEAMM_DEV/retired/``.
  The ``dev`` entry in ``~/SEAMM/dashboards.ini`` points at it. Still to check: the
  other machines.
- [x] **D11** (package versions in each job): not part of the switch; later.
- [x] **Phase 5 for the other plug-ins**: not part of the switch; plug-in by plug-in.
- [x] **The first installation to update is the production ``~/SEAMM`` on this Mac,
  exactly as a user would** (``seamm-manager update`` from PyPI, then the one-command
  migration), to find what a user would meet. So the releases come first, and the
  user-facing upgrade command (step 9) is released before ``~/SEAMM`` is updated.

1. Before any release
---------------------

- [ ] Full test suites of the 11 packages pass in ``~/SEAMM_DEV`` (done piecemeal; run
  once more together).
- [x] Fix ``Flowchart.get_nodes()`` stopping at the first loop where it matters for
  submission: ``Dashboard.submit`` uses it to find Parameters steps and the files to
  upload, so a step after a loop does not get its files uploaded. *Done: the client
  (204a5fe) and the MCP server (2c8db92) follow every edge; get_nodes() itself is left,
  since the 2.0 digest uses it.*
- [ ] Update packmol_step's 11 stale test reference outputs (number formatting) --
  only when packmol_step is next released; it is not part of the switch.
- [x] Update the campaign's ``index.rst`` status line.
- [x] Prepare the seamm **writer switch** as a separate commit (2c8db92:
  ``flowchart.DEFAULT_FORMAT``, overridable with ``SEAMM_FLOWCHART_FORMAT``): release 1 keeps
  ``Flowchart.write()``/``to_text()`` defaulting to 2.0 (the builder, ``seamm-flowchart``
  and the MCP server still write 3.0 explicitly); release 2 flips the default.

2. Releases, in order
---------------------

Each with the release-seamm-plugin skill (HISTORY.rst, docs review, PR from ``dev``,
**seamm** merges, then the GitHub Release). Never chain merge and release; check that
``main`` is the merge first. After each release, install it in a clean PyPI-only
environment and check it (a library is released before anything that uses it, and that
use pins it: ``lib>=version`` in ``requirements.txt``).

Wave A -- libraries the servers need (independent of seamm):

- [x] **seamm_datastore** 2026.10.1 -- reads 3.0 flowcharts; ``build_from_jobs``.
  PR #42 merged; released and on PyPI; checked in a clean PyPI-only environment.
- [x] **seamm_dashboard_client** 2026.10.1 -- ``Job.list_files``; files inside or after
  a loop uploaded; CI moved from conda to uv. PR #18 merged; released and on PyPI.

Wave B -- seamm, release 1 (reads 3.0, writes 2.0):

- [ ] **seamm** -- format 3.0 reader, spec, builder, layout, edit, the frozen
  converter, ``seamm-flowchart`` (incl. ``migrate`` and ``mcp``), shared rules
  (``applies_when`` and friends), the SEAMMrc race fix, the bibliography cache,
  ``from_dict``, editable-install fixes. Pin ``seamm_datastore>=`` (Wave A).
  Older seamm rejects a plug-in that uses ``applies_when``, so this must precede every
  plug-in below.

Wave C -- services (pin seamm_datastore):

- [ ] **seamm_manager** -- ``datastore rebuild``; editable-install paths;
  ``flowcharts migrate``/``status`` and the update notice (2 commits).
- [ ] **seamm_webui** -- rebuild a missing datastore from the job directories (1 commit).

Wave D -- plug-ins (each pins ``seamm>=`` release 1):

- [ ] **model_chemistry_step** (first: others consume Model Chemistry)
- [ ] **orca_step** (2 commits)
- [ ] **gaussian_step** (3)
- [ ] **psi4_step** (3)
- [ ] **mopac_step** (2)
- [ ] **lammps_step** (4)

3. Update every installation (servers before desktops)
-----------------------------------------------------

For each: ``seamm-manager update``, then ``seamm-manager services restart``; submit a
small test job and check it runs and its flowchart is recorded.

- [ ] ``~/SEAMM`` on this Mac -- **first**, exactly as a user would (256 job flowcharts
  in 2.0 found by ``seamm-manager flowcharts status``).
- [ ] ``~/SEAMM_DEV`` -- replace the editable installs with the released versions; set
  ``SEAMM_FLOWCHART_FORMAT=3.0`` there to keep writing 3.0 (it is already migrated).
- [ ] paul.local.
- [ ] MolSSI10.
- [ ] TinkerCliffs/ARC (``/projects/seamm``; no services).
- [ ] ChemAI -- **Paul's explicit OK for each action.**

4. Switch the writer to 3.0
---------------------------

- [ ] **seamm release 2**: ``Flowchart.write()``/``to_text()`` default to 3.0.
- [ ] Update every installation again (as in step 3).

5. Migrate the job directories and datastores
---------------------------------------------

Per installation: ``seamm-flowchart migrate --root ROOT`` (dry run), review the report,
stop the JobServer and web UI, ``--apply`` (backs up the datastore, writes a manifest
for undo), restart, open a few converted jobs in the web UI.

- [ ] ``~/SEAMM`` on this Mac (about 1,200 job directories).
- [ ] paul.local.
- [ ] MolSSI10.
- [ ] TinkerCliffs/ARC (about 53,000 job copies of 56 flowcharts; converts by content).
- [ ] ChemAI -- with Paul's OK.

(``~/SEAMM_DEV`` was migrated on 2026-09-30.)

6. Other flowcharts
-------------------

- [ ] ``~/SEAMM/flowcharts`` (27) and ``Testing/`` (27): ``seamm-flowchart convert``.
- [ ] The plug-ins' ``tests/`` and docs flowcharts: as each plug-in is next released.
- [ ] The two format-1.0 files.

7. Zenodo and tutorials
-----------------------

- [ ] Publish a 3.0 version of each of the 10 flowchart records (Paul's records; each
  publication confirmed). The older 15 versions keep serving 2.0, which is why the
  frozen converter stays.
- [ ] Tutorials: any link to a version DOI rather than the concept DOI gets updated.

8. Remove the old 2.0 code (seamm release 3)
--------------------------------------------

- [ ] Remove the previous 2.0 reader from ``Flowchart`` (``flowchart.py:549``) and the
  2.0 writer; 2.0 is read only through the frozen ``convert_v2``.
- [ ] Only after every installation is migrated and nothing writes 2.0.

9. Documentation and housekeeping
---------------------------------

- [x] **One command to upgrade an installation's flowcharts** (seamm_manager, local), for users outside the two
  of us (e.g. Hasnain at GM): ``seamm-manager flowcharts migrate [--root ROOT]``. It
  stops the JobServer and web UI, runs ``seamm-flowchart migrate`` as a dry run and shows
  the summary, asks for confirmation, applies (database backup + undo manifest), restarts
  the services and says where the backup is. Released with seamm_manager before external
  users are told to upgrade.
- [x] **``seamm-manager update`` notices format 2.0 job directories** and prints a short
  notice pointing at that command (report only; it never migrates by itself).
- [ ] **External upgrade instructions** (docs): back up the whole ``Jobs`` directory,
  ``seamm-manager update``, then ``seamm-manager flowcharts migrate``. Warn that moving
  the database aside and restarting the web UI is *not* an upgrade: the rebuilt database
  keeps no accounts and converts nothing (``seamm-manager datastore rebuild`` keeps the
  accounts, but also converts nothing). An installation must have seamm release 1 before
  it receives any 3.0 flowchart.
- [ ] User docs: format 3.0, specs, ``seamm-flowchart``, the MCP server.
- [ ] The build-seamm-flowchart skill: drop the "SEAMM_DEV only, no PRs" caveat; point
  the registered MCP server at ``~/SEAMM`` instead of ``~/SEAMM_DEV``.
- [ ] Memory and the campaign status.

Rollback
--------

- Datastores: each migration keeps a backup and a manifest; ``migrate3``'s undo puts the
  job files back.
- Packages: pin the previous versions with ``seamm-manager``; the two-release order means
  release 1 can stay while release 2 is rolled back (2.0 is written again and 3.0 still
  read).

Loose ends (not blocking)
-------------------------

- The queue configuration on this Mac is ignored since the hostname became
  ``PaulVT.local`` (the JobServer and web UI look for ``<hostname>.ini``, the file is
  ``PaulsPersonal.local.ini``).
- ``molssi10``/``molssi10-old`` in ``~/SEAMM/dashboards.ini`` have no credentials in
  ``~/.seamm.d/seammrc``.
- MOPAC's step ``__init__`` runs ``cpuinfo`` (a subprocess) for every MOPAC step.
- ``ChemAI_WebUI`` and ``MacMini`` report errors from this Mac (not investigated).
- An MCP endpoint in the web UI (Option 2) when someone beyond the two of us needs it.
