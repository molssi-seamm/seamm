Phase 6 -- The MCP server (2026-10-01)
======================================

**Result:** ``seamm-flowchart mcp`` serves the flowchart tools to AI clients over stdio
(``seamm/mcp_server.py``, optional ``seamm[mcp]``, mcp >= 2.2). Local only (Option 1
of the design); a web UI endpoint is left for later. Committed on ``dev`` (eda33ae),
not pushed. ``mcp`` 2.2.0 installed in ``~/SEAMM_DEV/venv`` (only additions;
pre-install freeze in ``~/SEAMM_DEV/venv-freeze-2026-10-01-before-mcp.txt``).

Tools
-----

``list_steps``, ``describe_step``, ``show_flowchart``, ``flowchart_tree`` and
``validate_flowchart`` (read only); ``build_flowchart`` (will not replace a file unless
``overwrite``), ``set_parameters``, ``insert_step``, ``remove_step`` (marked
destructive), ``move_step`` and ``convert_flowchart``. Thin wrappers over ``catalog``,
``spec`` and ``edit``. The files stay the source of truth: each tool reads the
``.flow`` it is given and writes the result back (or to ``output``) in 3.0, and the
editing tools return the new step tree and any problems. Errors users can fix
(unknown step, bad value, no-effect setting) come back as tool errors with the
builder's message. The server's instructions carry the skill's workflow (look up,
spec, build, validate, show).

Design points
-------------

- **stdout is the protocol.** mcp 2's stdio transport diverts fd 1 to stderr while
  serving, so the plug-ins are loaded after serving starts (a background warm-up in the
  lifespan), never before. The client connects in about 1.5 s; the first call waits for
  the warm-up (about 4 s).
- **One lock** around every tool and the warm-up: SEAMM's objects are not thread safe,
  and the SDK runs synchronous tools in worker threads.

Speed
-----

Warm calls first took 4-6 s. Profiling found two costs in SEAMM itself, now fixed in
core (874c90e): every new step re-parsed its plug-in's ``references.bib`` (cached by
path and modification time) and every 3.0 read called
``importlib.metadata.packages_distributions()`` (cached per process). Warm calls now
take 0.2-0.8 s (edit 0.8 s, tree 0.5 s, validate 0.2 s); the editor, the builder and
job start-up gain too. MOPAC's step ``__init__`` still runs ``cpuinfo`` (a subprocess)
for every MOPAC step created -- a plug-in fix for later.

Checked
-------

- 9 tests through a real MCP client in-process (``tests/test_mcp_server.py``, skipped
  without ``mcp`` or the plug-ins); the full suite: 227 passed.
- End to end over real stdio, starting ``~/SEAMM_DEV/venv/bin/seamm-flowchart mcp``:
  all 11 tools, a loop flowchart built, a step inserted and edited, "PM9" refused with
  the closest choices.

Incident: ~/.seamm.d/seammrc wiped
----------------------------------

The first stdio test wiped ``~/.seamm.d/seammrc`` down to ``[VERSION]`` (06:34), losing
the dashboard credentials and Zenodo tokens. Cause: a latent race in ``SEAMMrc`` --
every new Flowchart creates one, its ``__init__`` re-ran on the singleton, emptying the
shared parser before re-reading, and a second thread could find it empty, "upgrade" it
and save it. The warm-up thread ran outside the lock while a tool call created
flowcharts. Reproduced 3/3 with four threads (under a fake ``HOME``). **Fixed** in core
(d6c9feb): one lock, read into a new parser, never save over a file that reads as empty,
atomic saves keeping the mode; ``SEAMMrc(path)`` no longer raises ``TypeError``. 5/5
clean after the fix; 6 tests, all with their own ``HOME``. The warm-up now holds the
server's lock too.

The real file was **not** restored automatically (blocked as an overwrite): Paul to
restore it from ``~/.seamm.d/seammrc~`` (2026-08-11, 16 sections), re-adding anything
added since. Time Machine's disk could not be mounted and there are no local snapshots.

Next
----

Job tools (submit to a dashboard queue, status, results) through
``seamm_dashboard_client`` and ``~/.seamm.d/seammrc``; registering the server with
Claude Code / Claude Desktop; the skill pointing at the server where available.
