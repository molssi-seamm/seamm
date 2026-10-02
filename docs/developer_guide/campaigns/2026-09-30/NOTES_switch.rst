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

- [x] Full test suites of the 11 packages pass in ``~/SEAMM_DEV`` (done piecemeal; run
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
- [x] paul.local (2026-10-01): ``~/SEAMM`` and ``~/SEAMM_DEV`` (no editable installs, no old
  dashboard, nothing running), backed up in full to ``~/SEAMM_backups/2026-10-01-*-before-format3``.
  One plain ``update --all`` each (the tool in ``~/.local/bin``, not on the non-interactive
  ssh PATH; ``--root ~/SEAMM_DEV`` for the second): the tool upgraded itself from 2026.9.28.1
  (local APFS, so no self-reinstall trouble), the main environment (also fhi-aims-step and
  vasp-step, which had lagged), the web interfaces (updated and restarted), and the
  databases, which had no version recorded (stamped d7d6859198e9, then updated).
- [x] MolSSI10 (2026-10-01). Backup ``~/SEAMM_backups/2026-10-01-before-format3/`` (the
  database and every job's ``flowchart.flow``/``job_data.json`` -- what the migration
  touches -- and the venv freezes; ``Jobs`` is 125 GB on ext4, so no full copy). **The old
  dashboard retired**: systemd user unit ``org.molssi.seamm.dashboard`` (conda ``seamm``
  env, port 55055) stopped and disabled, unit file kept. One plain
  ``seamm-manager update --all`` (login shell): the tool upgraded itself to 2026.10.1.1,
  the main environment, the web interface (updated and restarted) and the JobServer.
- [x] TinkerCliffs/ARC (2026-10-01; ``/projects/seamm``, no services). Backup
  ``/projects/seamm/SEAMM_backups/2026-10-01-before-format3/`` (database + all 56,924 job
  flowcharts and job_data.json, 357 MB). The first ``update --all`` hit the known GPFS
  self-reinstall bug of the old tool (2026.9.29.1, before the 2026.9.29.2 fix): the tool
  was half-deleted, fell back to the cached package list ("Everything is up to date") and
  crashed (no ``seamm_manager.policy``). Repaired with ``uv tool install --force
  seamm-manager`` (``env.sh``); the second ``update --all`` updated everything (no web
  interface, no services).
- [x] ChemAI -- **Paul's explicit OK for each action.** Survey (2026-10-01): only
  ``/home/seamm/SEAMM`` is an installation (``/home/seamm/SEAMM_DEV`` and
  ``/home/psaxe/SEAMM`` have no venv); disk 95% full (45 GB free); 112 stale ``started``
  rows. Six xnn D4 benchmark jobs (``~/xnn_d4_bench``, sbatch, conda ``seamm-lammps`` and
  ``~/SEAMM/bin/mdi_bind.sh``) were running or pending, which ``update --all``'s plug-in
  installers could disturb, so **the update waits for them to finish** (Paul).
  Done with Paul's OK: (1) the old dashboard retired -- systemd unit
  ``org.molssi.seamm.dashboard`` (conda ``seamm``, port 55055) stopped and disabled;
  (2) backup ``/home/seamm/SEAMM_backups/2026-10-01-before-format3/`` (database, all 2,606
  job flowcharts + job_data.json, venv freezes; Paul runs no jobs until the update).
  Timing (from the mlff session, 18:00 EDT): the snapshot jobs 11749-11752 are **held**
  (``scontrol hold``, Paul's request); wait only for the density runs 11747/11748 (34.5 of
  100 ps, about 21:05 EDT). Next, each with Paul's OK: (3) ``update --all``; (4) migrate
  dry run; (5) migrate; (6) check a job can still start (seamm-lammps env, xnn, LAMMPS +
  MDI, GPUs) and a SEAMM test job on the ``ChemAI`` queue; (7)
  ``scontrol release 11749 11750 11751 11752`` so the snapshots and the queued density
  ladder run overnight.
  Done 2026-10-01, with Paul's OK after 11747/11748 completed (21:10, 21:15): (3)
  ``update --all`` at 22:08 -- one pass, tool 2026.9.28.1 -> 2026.10.1.1, web UI updated and
  restarted (https 55155 answers), JobServer restarted, ``mdi_bind.sh`` untouched; (4) dry
  run: 2,477 + 129 job flowcharts, 44 splits, 107 re-pointed, no problems; the 35 VASP
  "settings as attributes" notes are the ``potential_metadata`` cache (nothing lost).
  (5) migrated at 22:14 (backup ``Jobs/seamm.db.bak-2026-10-01-221448-before-format3``;
  services stopped and restarted; all 3.0; 2,606 originals kept); (6) the benchmark setup
  checked (seamm-lammps unchanged since 2026-09-19, torch sees both A100s idle, xnns 0.4.0,
  mdi, LAMMPS with MDI) and SEAMM job 5162 on the ``ChemAI`` queue finished; (7) the held
  snapshot jobs released: 11749/11750 running (LAMMPS started, GPUs 58%), 11751/11752
  pending for GPUs. The mlff session told. **ChemAI done; step 3 complete everywhere.**

4. Switch the writer to 3.0
---------------------------

- [x] **seamm release 2** (2026.10.2, released and on PyPI; writes 3.0 checked from PyPI): ``Flowchart.write()``/``to_text()`` default to 3.0;
  also the MCP job tools accept dashboards without credentials (PR #217).
- [x] Update every installation again (as in step 3), and run ``seamm-manager flowcharts
  migrate`` again to convert jobs saved in 2.0 in between. Package list: Zenodo
  ``10.5281/zenodo.23099647`` (seamm 2026.10.2). Done 2026-10-02, each with a test job whose
  stored flowchart is 3.0: ``~/SEAMM`` (job 552), ``~/SEAMM_DEV`` (job 4001, released
  packages only), MolSSI10 (683), paul.local ``~/SEAMM`` (4) and ``~/SEAMM_DEV`` (2) through
  the tunnel, ARC (nothing to convert; writer 3.0), and ChemAI with Paul's OK (queue
  empty; job 5162 converted; backup ``Jobs/seamm.db.bak-2026-10-02-055126-before-format3``;
  job 5163 on the ``ChemAI`` queue stored 3.0; ``mdi_bind.sh`` and seamm-lammps untouched).
  **Step 4 complete: every installation writes and holds format 3.0.**
  Note: the web UI's environment is not locked, so every ``update`` upgrades its other
  dependencies and restarts it, even when seamm-webui itself is unchanged.

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
- [x] paul.local (2026-10-01): ``~/SEAMM`` 2 job flowcharts and 1 row converted (backup
  ``Jobs/seamm.db.bak-2026-10-01-165151-before-format3``), services restarted, web UI 200;
  ``~/SEAMM_DEV`` has no jobs: nothing to convert.
  Its web UIs listen only on 127.0.0.1 without logins; reached from this Mac through an
  SSH tunnel (``ssh -f -N -L 55057:localhost:55055 -L 55058:localhost:55056 paul.local``),
  job 3 (``~/SEAMM``) and job 1 (``~/SEAMM_DEV``, its first job) finished. That needed the MCP job tools to accept a dashboard without
  credentials (seamm dev, for release 2).
- [x] MolSSI10 (2026-10-01): dry run 347 + 1 job flowcharts, 35 rows split, the known
  LAMMPS Minimization attributes (14) and ``tensor_labels`` (7); applied (backup
  ``Jobs/seamm.db.bak-2026-10-01-150006-before-format3``). Job 682 (queue ``molssi10``)
  finished; ``submit_job`` without a queue was refused, listing the two queues.
- [x] TinkerCliffs/ARC (2026-10-01): 52,736 + 4,083 job flowcharts converted, 46 rows
  split, 1,037 jobs re-pointed; backup ``Jobs/seamm.db.bak-2026-10-01-153534-before-format3``.
  The 105 "problems" are empty ``flowchart.flow`` files in GM jobs from 2025-12 that never
  ran (no ``job_data.json``); migrate skips them, unchanged. A converted job validates and
  shows with ARC's plug-ins. Moving ARC's jobs to ChemAI is a separate, later task (Paul).
- [x] ChemAI (2026-10-01 22:14) -- see step 3: 2,606 job flowcharts, 44 splits, backup
  ``Jobs/seamm.db.bak-2026-10-01-221448-before-format3``.

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
- [x] **External upgrade instructions** (docs): back up the whole ``Jobs`` directory,
  ``seamm-manager update``, then ``seamm-manager flowcharts migrate``. Warn that moving
  the database aside and restarting the web UI is *not* an upgrade: the rebuilt database
  keeps no accounts and converts nothing (``seamm-manager datastore rebuild`` keeps the
  accounts, but also converts nothing). An installation must have seamm release 1 before
  it receives any 3.0 flowchart. Done 2026-10-02: *Upgrading to flowchart format 3.0*
  in the main documentation (molssi-seamm.github.io PR #60), linked from the seamm user
  guide and the seamm_manager installation page.
- [x] User docs: format 3.0, specs, ``seamm-flowchart``, the MCP server
  (``user_guide/flowcharts_without_the_editor.rst``).
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
- The converter's message "has no parameters but has settings as attributes (a legacy
  file); the step's defaults will apply" is alarming where nothing is lost: on ChemAI it
  is the top-level VASP step (35 old job flowcharts), which has no parameters at all, and
  whose only attribute was ``potential_metadata`` -- a 751 KB cache of the POTCAR catalog,
  not a setting. Say so in the message (e.g. name the attributes dropped, and say when the
  step has no parameters to default) in a later seamm release.
- An MCP endpoint in the web UI (Option 2) when someone beyond the two of us needs it.
