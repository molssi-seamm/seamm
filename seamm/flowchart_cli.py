# -*- coding: utf-8 -*-

"""The seamm-flowchart command: work with flowcharts without the editor.

::

    seamm-flowchart steps [--json]              # every step, by group
    seamm-flowchart steps ORCA [--json]         # the sub-steps of a step
    seamm-flowchart describe "ORCA/Energy" [--json]
    seamm-flowchart build spec.yaml -o my.flow [--format 3.0]
    seamm-flowchart show my.flow                 # as a spec
    seamm-flowchart convert my.flow -o my3.flow [--format 3.0]
    seamm-flowchart tree my.flow                 # steps and their addresses
    seamm-flowchart set my.flow ORCA/Energy basis=def2-TZVP
    seamm-flowchart insert my.flow Energy method=MP2 --after ORCA/Optimization
    seamm-flowchart remove my.flow 3.2
    seamm-flowchart move my.flow 4 --before 2
    seamm-flowchart validate my.flow
    seamm-flowchart migrate --root ~/SEAMM_DEV [--apply]
"""

import argparse
import json
import logging
import sys
import textwrap

logger = logging.getLogger(__name__)


def _catalog():
    from .catalog import Catalog

    return Catalog()


def steps(args):
    """List the steps, or the sub-steps of a step."""
    from .catalog import StepNotFoundError

    catalog = _catalog()
    try:
        if args.step:
            parent, extension = catalog.find(args.step)
            catalog = parent.subcatalog(extension)
        result = catalog.steps()
    except (StepNotFoundError, ValueError) as e:
        print(e, file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=4))
        return 0

    group = None
    for step in result:
        if step["group"] != group:
            group = step["group"]
            print(f"\n{group}")
        name = step["extension"]
        if step["name"] != name:
            name += f" [{step['name']}]"
        print(f"    {name:40s} {step['description']}")
    return 0


def describe(args):
    """Describe a step and its parameters."""
    from .catalog import StepNotFoundError

    catalog = _catalog()
    try:
        result = catalog.describe(args.step)
    except (StepNotFoundError, ValueError) as e:
        print(e, file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=4, default=str))
        return 0

    print(f"{result['name']}  (extension '{result['extension']}', {result['group']})")
    if result["description"]:
        print(f"    {result['description']}")
    if "substeps" in result:
        print("\nSub-steps: " + ", ".join(result["substeps"]))
    if len(result["parameters"]) == 0:
        print("\nNo parameters.")
        return 0
    print("\nParameters:")
    wrapper = textwrap.TextWrapper(
        width=88, initial_indent=" " * 8, subsequent_indent=" " * 8
    )
    for key, data in result["parameters"].items():
        default = data["default"]
        if data["units"]:
            default = f"{default} {data['units']}"
        print(f"\n    {key!r}  ({data['kind']}, default {default!r})")
        if data["enumeration"]:
            choices = [str(c) for c in data["enumeration"]]
            if len(choices) > 30:
                choices = choices[:30] + [f"... ({len(data['enumeration'])} in all)"]
            label = "choices" if data["strict"] else "suggestions"
            print(wrapper.fill(f"{label}: " + ", ".join(choices)))
        text = data["help"] or data["description"]
        if text:
            print(wrapper.fill(" ".join(str(text).split())))
    return 0


def _read_input(path):
    """The text of a file, or of standard input for '-'."""
    if path == "-":
        return sys.stdin.read()
    with open(path) as fd:
        return fd.read()


def _write_output(text, path, executable=True):
    """Write text to a file, made executable, or to standard output."""
    if path is None or path == "-":
        sys.stdout.write(text)
        return
    with open(path, "w") as fd:
        fd.write(text)
    if executable:
        import os
        import stat

        mode = stat.S_IMODE(os.lstat(path).st_mode)
        os.chmod(path, mode | stat.S_IXUSR | stat.S_IXGRP)


def build(args):
    """Build a complete flowchart from a spec."""
    from . import spec

    try:
        fb = spec.build(_read_input(args.spec))
        text = fb.to_text(check=not args.no_check, format=args.format)
    except (spec.SpecError, ValueError) as e:
        print(e, file=sys.stderr)
        return 1
    _write_output(text, args.output)
    return 0


def _read_flowchart(path):
    import seamm

    flowchart = seamm.Flowchart()
    flowchart.from_text(_read_input(path))
    return flowchart


def show(args):
    """Show a flowchart as a spec: its steps and the parameters not at defaults."""
    from . import spec

    try:
        flowchart = _read_flowchart(args.flowchart)
    except Exception as e:
        print(f"Could not read {args.flowchart}: {e}", file=sys.stderr)
        return 1
    data = spec.reduce(flowchart)
    if args.json:
        print(json.dumps(data, indent=4, default=str))
    else:
        sys.stdout.write(spec.dump(data))
    return 0


def convert(args):
    """Write a flowchart in another format."""
    try:
        flowchart = _read_flowchart(args.flowchart)
    except Exception as e:
        print(f"Could not read {args.flowchart}: {e}", file=sys.stderr)
        return 1
    _write_output(flowchart.to_text(format=args.format), args.output)
    return 0


def migrate(args):
    """Migrate an installation's jobs and datastore to format 3.0 (dry run default)."""
    from . import migrate3

    try:
        the_plan = migrate3.plan(args.root, datastore=args.datastore)
    except migrate3.MigrationError as e:
        print(e, file=sys.stderr)
        return 1
    print(migrate3.text_report(the_plan))
    if args.plan:
        slim = {k: v for k, v in the_plan.items() if k not in ("files", "data")}
        slim["files"] = {p: d["report"] for p, d in the_plan["files"].items()}
        with open(args.plan, "w") as fd:
            json.dump(slim, fd, indent=2, default=str)
        print(f"The full plan is in {args.plan}")
    if not args.apply:
        print("Dry run: nothing was changed. Use --apply to migrate.")
        return 0
    result = migrate3.apply(the_plan)
    print(f"Datastore backup: {result.get('backup')}")
    print(f"Manifest of file changes: {result['manifest']}")
    return 0


def _assignments(items):
    """Parameter values from 'name=value' words; values are read as YAML."""
    from .format3 import load_yaml

    params = {}
    for item in items or []:
        if "=" not in item:
            raise ValueError(f"'{item}' is not name=value")
        name, text = item.split("=", 1)
        try:
            value = load_yaml(text) if text.strip() != "" else ""
        except Exception:
            value = text
        if value is None:
            value = ""
        params[name.strip()] = value
    return params


def _edit(args, action):
    """Read the flowchart, make an edit, and write it back (or to --output)."""
    from . import edit

    try:
        flowchart = edit.read(args.flowchart)
    except Exception as e:
        print(f"Could not read {args.flowchart}: {e}", file=sys.stderr)
        return 1
    try:
        message = action(edit, flowchart)
    except (edit.EditError, ValueError, KeyError) as e:
        print(str(e).strip('"'), file=sys.stderr)
        return 1
    output = args.output or args.flowchart
    _write_output(flowchart.to_text(format=args.format), output)
    if message:
        print(message)
    return 0


def tree(args):
    """List the steps of a flowchart with their addresses."""
    from . import edit

    try:
        flowchart = edit.read(args.flowchart)
    except Exception as e:
        print(f"Could not read {args.flowchart}: {e}", file=sys.stderr)
        return 1
    print("\n".join(edit.tree(flowchart)))
    return 0


def set_command(args):
    """Set parameters of a step."""
    return _edit(
        args,
        lambda edit, fc: edit.set_parameters(fc, args.step, _assignments(args.values))
        and None,
    )


def insert_command(args):
    """Insert a step."""

    def action(edit, flowchart):
        address = edit.insert(
            flowchart,
            args.new_step,
            _assignments(args.values),
            after=args.after,
            before=args.before,
            into=args.into,
        )
        return f"Inserted {args.new_step} as step {address}"

    return _edit(args, action)


def remove_command(args):
    """Remove a step."""
    return _edit(args, lambda edit, fc: edit.remove(fc, args.step) and None)


def move_command(args):
    """Move a step."""

    def action(edit, flowchart):
        address = edit.move(
            flowchart, args.step, after=args.after, before=args.before, into=args.into
        )
        return f"Moved it to step {address}"

    return _edit(args, action)


def validate_command(args):
    """Check a flowchart."""
    from . import edit

    try:
        flowchart = edit.read(args.flowchart)
    except Exception as e:
        problems = [f"Could not read the flowchart: {e}"]
    else:
        problems = edit.validate(flowchart)
    if args.json:
        print(json.dumps({"valid": not problems, "problems": problems}, indent=4))
    elif problems:
        print("\n".join(problems))
    else:
        print("No problems found.")
    return 1 if problems else 0


def main(argv=None):
    """The seamm-flowchart command."""
    parser = argparse.ArgumentParser(
        prog="seamm-flowchart",
        description="Work with SEAMM flowcharts without the graphical editor.",
    )
    parser.add_argument(
        "--log-level",
        default="ERROR",
        type=str.upper,
        choices=["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="The level of informational output, defaults to '%(default)s'",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p = subparsers.add_parser("steps", help="List the steps, or a step's sub-steps")
    p.add_argument("step", nargs="?", help="A step with sub-steps, e.g. ORCA")
    p.add_argument("--json", action="store_true", help="Output JSON")
    p.set_defaults(func=steps)

    p = subparsers.add_parser("describe", help="Describe a step and its parameters")
    p.add_argument("step", help="A step, or a path to a sub-step, e.g. ORCA/Energy")
    p.add_argument("--json", action="store_true", help="Output JSON")
    p.set_defaults(func=describe)

    p = subparsers.add_parser(
        "build", help="Build a complete flowchart from a spec (YAML)"
    )
    p.add_argument("spec", help="The spec file, or - for standard input")
    p.add_argument("-o", "--output", help="The flowchart to write (default: stdout)")
    p.add_argument(
        "--format", default="3.0", choices=["2.0", "3.0"], help="Flowchart format"
    )
    p.add_argument(
        "--no-check",
        action="store_true",
        help="Write the flowchart even if it has problems as a whole",
    )
    p.set_defaults(func=build)

    p = subparsers.add_parser(
        "show", help="Show a flowchart as a spec: the parameters that are not defaults"
    )
    p.add_argument("flowchart", help="The flowchart, or - for standard input")
    p.add_argument("--json", action="store_true", help="Output JSON")
    p.set_defaults(func=show)

    p = subparsers.add_parser("convert", help="Write a flowchart in another format")
    p.add_argument("flowchart", help="The flowchart, or - for standard input")
    p.add_argument("-o", "--output", help="The flowchart to write (default: stdout)")
    p.add_argument(
        "--format", default="3.0", choices=["2.0", "3.0"], help="Flowchart format"
    )
    p.set_defaults(func=convert)

    p = subparsers.add_parser("tree", help="List a flowchart's steps and addresses")
    p.add_argument("flowchart", help="The flowchart, or - for standard input")
    p.set_defaults(func=tree)

    def editing(p):
        p.add_argument("flowchart", help="The flowchart to edit")
        p.add_argument(
            "-o", "--output", help="Write here instead of back to the flowchart"
        )
        p.add_argument(
            "--format", default="3.0", choices=["2.0", "3.0"], help="Flowchart format"
        )

    def where(p):
        group = p.add_mutually_exclusive_group()
        group.add_argument("--after", help="After this step")
        group.add_argument("--before", help="Before this step")
        group.add_argument(
            "--into", help="At the end of this loop's body or step's sub-steps"
        )

    p = subparsers.add_parser("set", help="Set parameters of a step")
    editing(p)
    p.add_argument("step", help="The step, e.g. 3.2 or ORCA/Energy")
    p.add_argument("values", nargs="+", help="name=value (value is YAML)")
    p.set_defaults(func=set_command)

    p = subparsers.add_parser("insert", help="Insert a step")
    editing(p)
    p.add_argument("new_step", help="The step to insert, e.g. Energy")
    p.add_argument("values", nargs="*", help="name=value (value is YAML)")
    where(p)
    p.set_defaults(func=insert_command)

    p = subparsers.add_parser("remove", help="Remove a step (and steps inside it)")
    editing(p)
    p.add_argument("step", help="The step, e.g. 3.2 or ORCA/Energy")
    p.set_defaults(func=remove_command)

    p = subparsers.add_parser("move", help="Move a step (and steps inside it)")
    editing(p)
    p.add_argument("step", help="The step, e.g. 3.2 or ORCA/Energy")
    where(p)
    p.set_defaults(func=move_command)

    p = subparsers.add_parser(
        "validate", help="Check a flowchart's structure and values"
    )
    p.add_argument("flowchart", help="The flowchart, or - for standard input")
    p.add_argument("--json", action="store_true", help="Output JSON")
    p.set_defaults(func=validate_command)

    p = subparsers.add_parser(
        "migrate",
        help="Migrate an installation's jobs and datastore to format 3.0 "
        "(a dry run unless --apply)",
    )
    p.add_argument("--root", required=True, help="The SEAMM root, e.g. ~/SEAMM_DEV")
    p.add_argument("--datastore", help="The datastore (default <root>/Jobs/seamm.db)")
    p.add_argument("--plan", help="Write the full plan as JSON to this file")
    p.add_argument(
        "--apply",
        action="store_true",
        help="Make the changes (stop the JobServer and web UI first)",
    )
    p.set_defaults(func=migrate)

    args = parser.parse_args(argv)
    logging.basicConfig(level=args.log_level)
    # The plug-ins log a lot while loading, and some set their own loggers to DEBUG;
    # keep it quiet unless asked.
    logging.getLogger().setLevel(args.log_level)
    for handler in logging.getLogger().handlers:
        handler.setLevel(args.log_level)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
