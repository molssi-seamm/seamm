Phase 3 -- Converter and migration (2026-09-30, in progress)
============================================================

Done so far: the frozen converter, reading 2.0 through it, 3.0 as the default format,
the datastore and web UI reading 3.0, a datastore rebuild from the job directories, and
the migration of ``~/SEAMM_DEV``. Still to do, at the switch: production ``~/SEAMM`` and
the other machines, the Zenodo records and tutorial links, removing the old 2.0 code,
and the releases. Nothing has been pushed; see "Where the work happens" in the plan.

The frozen converter (``seamm/convert_v2.py``)
----------------------------------------------

- Converts 1.0/2.0 to 3.0 from the file's data alone; imports nothing from SEAMM or
  plug-ins (a test forbids it), so it can stay unchanged for old Zenodo versions (Q5).
- Gives exactly what the live 3.0 writer gives, digests included.
- Maps lammps_step Minimization's old ``convergence`` attribute into the parameters.
  Commit 5ee392d showed that the other old attributes (``etol``, ``ftol``,
  ``maxiters``, ``maxevals``) were used only for the energy/forces criteria, and the old
  ``etol`` was relative and unitless while the new one is in kcal/mol, so they are
  reported, not mapped.
- Reports every non-empty attribute it drops.

``Flowchart.from_text`` reads 2.0 and 1.0 through the converter, so every flowchart is
read one way; the old object reader is kept, unused, as ``_from_text_objects``.
``format3.apply_parameters`` builds each step's parameters with the plug-in's own
class, ``type(node.parameters)(data=...)``, as 2.0 did, so the fixes that ten
plug-ins make in ``__init__`` for renamed parameters still apply (e.g. NPT turns
``keep orthorhombic`` into ``allow shear``).

Checks of the converter
-----------------------

Every flowchart on this Mac was converted and loaded with today's plug-ins:

.. list-table::
   :header-rows: 1

   * - Set
     - Converted
     - Load today
     - Every recorded value kept
     - Same as today's 2.0 reader
   * - Loose flowcharts
     - 94
     - 77
     - 77
     - 76
   * - Job directories
     - 1,223
     - 1,121
     - 1,121
     - 1,111

The files that do not load fail with today's 2.0 reader too (a plug-in that is not
installed, e.g. PySCF, ThermalConductivity or TorchANI; parameters since removed, e.g.
``molecule source``). Where 3.0 differs from today's 2.0 reader, 3.0 is right: old
lammps_step versions (e.g. 2023.9.6) saved Minimization's parameters as the base
``EnergyParameters``, and the 2.0 reader rebuilds that old class, so the step loses its
current parameters (``convergence``, pressure, stress, ...); 3.0 builds the step's own
``MinimizationParameters`` with every recorded value. ``tutorial3.flow`` (Table before
Parameters) is the known legacy file.

Step 1: format 3.0 by default (seamm 7ca0572)
---------------------------------------------

- ``Flowchart.to_text()``/``write()``, the builder and ``seamm-flowchart build``
  write 3.0 unless ``format="2.0"`` is asked for.
- seamm_datastore reads 3.0 (``parse_flowchart_file``): metadata, the file's digests,
  the flowchart's data (stored in the ``json`` column); ``yes``/``no`` stay strings.
- The Open dialog reads 3.0 metadata.
- In ``~/SEAMM_DEV``: seamm_datastore editable in ``venv`` and ``venv-webui``; the
  JobServer and web UI restarted. Job 3982 went from a spec to a 3.0 file through the
  web UI, the datastore (row 985, version 3.0, the file's digests) and the JobServer;
  saving from the editor writes 3.0 with the same steps and digest.

Step 2: migrating an installation (seamm 8a2be9d, 3ce656c)
----------------------------------------------------------

``seamm-flowchart migrate --root ROOT [--plan FILE] [--apply]`` (``seamm/migrate3.py``;
SQLite directly on ``<root>/Jobs/seamm.db``). A dry run by default. Following Q6 and
Q7:

- each job's ``flowchart.flow`` is converted (each distinct text once), the original
  renamed ``flowchart.v2.flow`` with its content unchanged, the file mode kept;
- each job points at the row for its own file's digest: rows are split where the old
  digest wrongly merged flowcharts, merged where they now match, and converted from
  their own stored content where their jobs have no file; row ids are kept where
  possible; permissions, projects and DOIs carried over; unused rows deleted;
- ``--apply`` backs up the datastore (SQLite backup API), changes it in one
  transaction, then converts the files and writes a manifest for ``undo_files()``.

**~/SEAMM_DEV, migrated 2026-09-30 13:30** (services stopped around it):

.. list-table::
   :header-rows: 1

   * -
     -
   * - Job flowcharts converted
     - 855 (plus job 3982, already 3.0)
   * - Jobs whose directories are gone (rows converted from stored content)
     - 1,225, plus 1 directory with no ``flowchart.flow``
   * - Rows without jobs, converted from their own content
     - 31
   * - Rows updated in place / created by splits / deleted
     - 374 / 106 / 0
   * - Jobs pointed at another row
     - 133

The 106 splits are the old loop-digest bug: e.g. row 145 held 27 jobs with 4 different
flowcharts (differing in the loop body and after the loop), row 111's jobs differed in
a timestep inside a nested loop, and row 871 held 20 different flowcharts. Backup
``Jobs/seamm.db.bak-2026-09-30-133015-before-format3``; manifest
``Jobs/format3-migration-2026-09-30-133015.json``.

Checked after: a second plan finds nothing to do; 1,091 rows, all 3.0, no duplicate
or empty digests, every job's row exists; each of the 856 jobs with a file points at a
row holding exactly its own flowchart; the 10 DOIs kept; the web UI lists all 2,082
jobs; job 3983 re-ran job 3979's migrated flowchart with the same results and was
matched to the same row (984). A rehearsal on a copy of the datastore had given the
same result before.

The 27 "job directories not in the datastore" of the report were the jobs of project
'Water', whose datastore path differs in case from the ``water`` directory on macOS;
the second conversion was skipped because ``flowchart.v2.flow`` existed. Fixed: the tool
now compares files by identity (3ce656c).

The 1,225 jobs without directories
----------------------------------

Directories removed without their datastore rows, from 2022-02 to 2026-06: projects
'PM7 dataset' (235), 'Paper' (124) and 'Chickens' (43) are gone from disk entirely;
'default' is missing 468 and 'debug' 355. None exists elsewhere under
``~/SEAMM_DEV/Jobs``.

Rebuilding the datastore from the job directories
-------------------------------------------------

The old Dashboard imported any job directory at every start (seamm_datastore's
``import_datastore``). The new web UI did not: without ``seamm.db`` it created an
empty datastore, and ``seamm-manager``'s ``ensure`` did the same. Now (Paul's request):

- seamm_datastore ``build_from_jobs()`` (d909eb6) builds a datastore from the job
  directories, optionally keeping the accounts, the details of projects that still
  exist, and each job's owner from the datastore it replaces. ``import_datastore()``
  now creates a project a job lists that has no directory of its own (e.g. 'Water' for
  a job in 'water'), at ``<projects>/<name>`` as the job server would have.
- ``seamm-manager datastore rebuild`` (seamm_manager e2a3f4e): stops the JobServer and
  web UI, builds a new datastore, keeps the old one as
  ``seamm.db.bak-<date>-before-rebuild``, records the schema version, restarts the
  services. ``ensure`` builds a missing datastore from the jobs when there are any.
  The datastore's alembic is found for an editable install too.
- The web UI (seamm_webui c9718d7) builds the datastore from the jobs when
  ``seamm.db`` is missing but there are job directories.

Tested on a sandbox root (a copy of SEAMM_DEV's datastore, its job directories and
venv linked in): 856 of 859 job directories imported in 23 projects with the accounts,
project owners and job owners kept; the three not imported are broken (two corrupt
``job_data.json``, ``test/Job_003259`` and ``GM/Job_002858``; ``test/Job_003800`` has no
flowchart). SEAMM_DEV's own datastore was not rebuilt (that would also drop the
1,225 orphaned jobs). seamm_manager and seamm_webui are installed editable in
``~/SEAMM_DEV`` (``venv`` and ``venv-webui``); the web UI was restarted.
