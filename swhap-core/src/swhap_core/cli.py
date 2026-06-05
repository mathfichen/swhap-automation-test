"""``swhap`` CLI surface (M1a slice: only ``swhap inspect``).

Deterministic ``--json`` output; exit codes per core-pipeline.md §3.1.1:
0 ok, 2 usage, 10 extraction-contract violation, 11 budget exceeded,
1 internal error.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .errors import EXIT_INTERNAL, EXIT_OK, EXIT_USAGE
from .inspect import ExtractionPolicy, inspect_archive


def _load_policy(path: str | None) -> ExtractionPolicy:
    if not path:
        return ExtractionPolicy()
    with open(path, "rb") as fh:
        data = json.load(fh)
    return ExtractionPolicy.from_dict(data)


def _emit(obj, fh=None) -> None:
    # resolve stdout at call time (not import time) so capture/redirect works
    fh = fh if fh is not None else sys.stdout
    # canonical, deterministic serialization (no env leakage)
    fh.write(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False))
    fh.write("\n")


def cmd_inspect(args: argparse.Namespace) -> int:
    try:
        policy = _load_policy(args.policy)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"swhap inspect: cannot read policy: {exc}\n")
        return EXIT_USAGE

    reports = []
    worst = EXIT_OK
    for archive in args.archives:
        try:
            report = inspect_archive(archive, policy)
        except FileNotFoundError:
            sys.stderr.write(f"swhap inspect: no such file: {archive}\n")
            return EXIT_USAGE
        except Exception as exc:  # pragma: no cover - defensive
            sys.stderr.write(f"swhap inspect: internal error on {archive}: {exc}\n")
            return EXIT_INTERNAL
        reports.append(report)
        worst = max(worst, report["exit_code"])

    if len(reports) == 1:
        _emit(reports[0])
    else:
        _emit({"schema": "swhap-core/inspect/v1", "reports": reports})
    return worst


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="swhap", description="SWHAP Layer-1 toolkit")
    parser.add_argument("--version", action="version", version=f"swhap-core {__version__}")
    sub = parser.add_subparsers(dest="command")

    p_inspect = sub.add_parser(
        "inspect", help="read-only crit-M6 inspection of an archive (no extraction)"
    )
    p_inspect.add_argument("archives", nargs="+", metavar="ARCHIVE")
    p_inspect.add_argument("--json", action="store_true", help="emit JSON (default and only format)")
    p_inspect.add_argument("--policy", metavar="FILE", help="JSON policy/budget overrides")
    p_inspect.set_defaults(func=cmd_inspect)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help(sys.stderr)
        return EXIT_USAGE
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
