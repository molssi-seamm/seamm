# -*- coding: utf-8 -*-

"""The seamm-flowchart command: work with flowcharts without the editor.

::

    seamm-flowchart steps [--json]              # every step, by group
    seamm-flowchart steps ORCA [--json]         # the sub-steps of a step
    seamm-flowchart describe "ORCA/Energy" [--json]
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
        name = step["name"]
        if step["extension"] != name:
            name += f" [{step['extension']}]"
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
            label = (
                "choices"
                if data["kind"] in ("enum", "enumeration", "boolean")
                else "suggestions"
            )
            print(wrapper.fill(f"{label}: " + ", ".join(choices)))
        text = data["help"] or data["description"]
        if text:
            print(wrapper.fill(" ".join(str(text).split())))
    return 0


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

    args = parser.parse_args(argv)
    logging.basicConfig(level=args.log_level)
    # The plug-ins log a lot while loading; keep it quiet unless asked.
    logging.getLogger().setLevel(args.log_level)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
