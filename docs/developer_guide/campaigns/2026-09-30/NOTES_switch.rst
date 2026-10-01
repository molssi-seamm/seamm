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

- [x] **seamm** 2026.10.1 (released, on PyPI, checked in a clean PyPI-only environment:
  writes 2.0 by default, reads both) -- format 3.0 reader, spec, builder, layout, edit, the frozen
  converter, ``seamm-flowchart`` (incl. ``migrate`` and ``mcp``), shared rules
  (``applies_when`` and friends), the SEAMMrc race fix, the bibliography cache,
  ``from_dict``, editable-install fixes, and the user guide page "Flowcharts without the
  editor". Pins ``seamm-dashboard-client>=2026.10.1`` (seamm does not depend on
  seamm_datastore; the migration uses SQLite directly). **PR #216 open, CI green** (after
  fixing a test that assumed the installed seamm version sorted highest -- not true in
  CI's shallow checkout). Older seamm rejects a plug-in that uses ``applies_when``, so
  this must precede every plug-in below.

Wave C -- services (pin seamm_datastore):

- [x] **seamm_manager** 2026.10.1 (released, on PyPI, checked from PyPI against ~/SEAMM) -- ``datastore rebuild``; editable-install paths;
  ``flowcharts migrate``/``status`` and the update notice; Usage and Installation
  updated. **PR #20 open, CI green.**
- [x] **seamm_webui** **2026.10.1.1** released and on PyPI. 2026.10.1 was **not published**: its own Release.yaml (it adds the
  frontend build) still used the conda env file the release removed. Fixed in PR #10
  (CI green), to be released as **2026.10.1.1**. -- rebuild a missing datastore from the job directories;
  pins ``seamm-datastore>=2026.10.1``; CI moved from conda to uv. **PR #9 open, CI
  green.**

Wave D -- plug-ins (each pins ``seamm>=`` release 1):

All six opened 2026-10-01 as 2026.10.1, CI green, each pinning ``seamm>=2026.10.1``,
with HISTORY, a "Settings that depend on each other" section in the user guide, and CI
moved from conda to uv (no custom workflow used the env file). The uv move found three
undeclared dependencies, now declared: ``seamm-exec`` (psi4_step, mopac_step) and
``model-chemistry-step`` (lammps_step). The docs mock ``seamm_installer``, which the
installers import and SEAMM's manager provides.

- [x] **model_chemistry_step** 2026.10.1 -- released and on PyPI (PR #6)
- [x] **orca_step** 2026.10.1 -- released and on PyPI (PR #34)
- [x] **gaussian_step** 2026.10.1 -- released and on PyPI (PR #32)
- [x] **psi4_step** 2026.10.1 -- released and on PyPI (PR #45)
- [x] **mopac_step** 2026.10.1 -- released and on PyPI (PR #156)
- [x] **lammps_step** 2026.10.1 -- released and on PyPI (PR #113)

**The published package list** (seamm_packaging, run by hand on 2026-10-01 once all were
on PyPI): Zenodo ``10.5281/zenodo.23088483``, seamm_packaging release 2026.10.1.1. The lock
pins all ten main-environment packages at 2026.10.1; seamm-webui is a standalone package
that the manager upgrades from PyPI into ``venv-webui`` (2026.10.1.1). So a plain
``seamm-manager update --all`` now picks everything up, as it would after a nightly run.

3. Update every installation (servers before desktops)
------------------------------------------------------

For each: ``seamm-manager update``, then ``seamm-manager services restart``; submit a
small test job and check it runs and its flowchart is recorded.

- [x] ``~/SEAMM`` on this Mac -- **first**, exactly as a user would (2026-10-01). Backup in
  ``~/SEAMM_backups/2026-10-01-before-format3/`` (Jobs + venv freezes). The first plain
  ``seamm-manager update --all`` updated the main environment and the JobServer but **not
  the web interface** (``venv-webui`` was never updated by ``update``): fixed in
  seamm_manager 2026.10.1.1 (PR #21), package list refreshed (Zenodo
  ``10.5281/zenodo.23088748``), and a second plain ``update --all`` upgraded the manager
  tool itself, then the web interface (seamm-webui 2026.10.1.1, datastore 2026.10.1) and
  restarted it. Job 551 (SMILES=CCO, MOPAC PM7, -53.29 kcal/mol) finished.
- [x] ``~/SEAMM_DEV`` (2026-10-01) -- backup ``~/SEAMM_backups/2026-10-01-SEAMM_DEV-before-release-update/``
  (Jobs 43 GB clone; 2,099 jobs / 876 directories match); plain
  ``~/SEAMM_DEV/venv/bin/seamm-manager update --all`` replaced the editable installs with
  the releases, updated and restarted the web interface and the JobServer, and updated
  the development tools. Still editable: seamm-packaging (not in the package list) and
  seamm_bsse -- the lock's ``==2026.8.7.1`` is satisfied by the editable
  ``2026.8.7.1+0.gd387828.dirty`` (its code is the release's). ``mcp`` kept; the MCP server
  works over stdio; job 4000 finished. ``SEAMM_FLOWCHART_FORMAT`` not set: SEAMM_DEV writes
  2.0 until release 2 like the others, and is migrated again then.
- [ ] paul.local.
- [ ] MolSSI10.
- [ ] TinkerCliffs/ARC (``/projects/seamm``; no services).
- [ ] ChemAI -- **Paul's explicit OK for each action.**

4. Switch the writer to 3.0
---------------------------

- [ ] **seamm release 2**: ``Flowchart.write()``/``to_text()`` default to 3.0.
- [ ] Update every installation again (as in step 3).
- [ ] Run ``seamm-manager flowcharts migrate`` again on every migrated installation: jobs
  run between its migration and release 2 still write 2.0 (``~/SEAMM`` job 551 on).

5. Migrate the job directories and datastores
---------------------------------------------

Per installation: ``seamm-flowchart migrate --root ROOT`` (dry run), review the report,
stop the JobServer and web UI, ``--apply`` (backs up the datastore, writes a manifest
for undo), restart, open a few converted jobs in the web UI.

- [x] ``~/SEAMM`` on this Mac (2026-10-01): ``seamm-manager flowcharts migrate`` (dry run
  reviewed: 228 + 28 job flowcharts, 8 rows split, no problems; ``tensor_labels`` dropped
  from diffusivity steps is a constant, not a setting). Datastore backup
  ``Jobs/seamm.db.bak-2026-10-01-142410-before-format3``, manifest
  ``Jobs/format3-migration-2026-10-01-142410.json``; services stopped and restarted by the
  command. ``status``: all 3.0. Found, unrelated: 28 Docker-era jobs (ids 1-52) record
  ``/root/SEAMM/...`` paths, so the web UI cannot show their files (``datastore rebuild``
  would record the real paths).
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
- The plug-ins' installers import ``seamm_installer`` (provided by seamm-manager) without
  declaring it; fine in an installation, which always has the manager.
- An MCP endpoint in the web UI (Option 2) when someone beyond the two of us needs it.
