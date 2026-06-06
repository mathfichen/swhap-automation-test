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
from .errors import EXIT_INTERNAL, EXIT_OK, EXIT_USAGE, SwhapError
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


def cmd_build(args: argparse.Namespace) -> int:
    # late import: keeps the inspect slice free of the history/journal modules.
    from .history import do_apply, do_build, do_plan
    from .journal import new_ulid
    from .model import CurationTimestamp

    cts = None
    if args.curation_epoch is not None:
        cts = CurationTimestamp(args.curation_epoch, args.curation_offset)

    try:
        if args.plan and args.apply:
            sys.stderr.write("swhap build: choose at most one of --plan / --apply\n")
            return EXIT_USAGE
        if args.plan:
            if cts is None:
                sys.stderr.write("swhap build --plan needs --curation-epoch\n")
                return EXIT_USAGE
            plan, _ = do_plan(args.workbench, args.model, cts, plan_out=args.plan_file)
            _emit(_plan_summary(plan))
            return EXIT_OK
        if args.apply:
            run_id = args.run_id or new_ulid()
            plan, result = do_apply(
                args.workbench,
                run_id=run_id,
                model_name=args.model,
                curation_ts=cts,
                plan_path=args.plan_file,
                scratch=args.scratch,
            )
            _emit(_apply_summary(plan, result))
            return EXIT_OK
        # full build (plan + apply)
        if cts is None:
            sys.stderr.write("swhap build needs --curation-epoch (no wall-clock fallback; D4)\n")
            return EXIT_USAGE
        if not args.model:
            sys.stderr.write("swhap build needs --model P|G\n")
            return EXIT_USAGE
        run_id = args.run_id or new_ulid()
        plan, result = do_build(
            args.workbench, args.model, cts, run_id=run_id, scratch=args.scratch, plan_out=args.plan_file
        )
        _emit(_apply_summary(plan, result))
        return EXIT_OK
    except SwhapError as exc:
        sys.stderr.write(f"swhap build: [{exc.code}] {exc.message}\n")
        return exc.exit_code
    except Exception as exc:  # pragma: no cover - defensive
        sys.stderr.write(f"swhap build: internal error: {exc}\n")
        return EXIT_INTERNAL


def _plan_summary(plan) -> dict:
    return {
        "schema": "swhap-core/build/v1",
        "phase": "plan",
        "model": plan.model,
        "curation_timestamp": {"epoch": plan.curation_epoch, "offset": plan.curation_offset},
        "releases": [{"dirname": s.dirname, "release_tag": s.release_tag} for s in plan.steps],
    }


def _apply_summary(plan, result) -> dict:
    return {
        "schema": "swhap-core/build/v1",
        "phase": "apply",
        "model": result.model,
        "run_id": result.run_id,
        "scratch": result.scratch,
        "branch_ref": result.branch_ref,
        "branch_tip": result.branch_tip,
        "commits": result.commits,
        "tags": result.tags,
    }


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

    p_build = sub.add_parser(
        "build",
        help="reconstruct curated Git history into candidate refs (plan/apply; D4 reproducible)",
    )
    p_build.add_argument("--workbench", required=True, metavar="DIR")
    p_build.add_argument("--model", choices=["P", "G"], help="branch model (P=orphan purity, G=default-branch)")
    p_build.add_argument("--plan", action="store_true", help="emit plan only; touch no refs")
    p_build.add_argument("--apply", action="store_true", help="apply (needs --plan-file or --curation-epoch+--model)")
    p_build.add_argument("--plan-file", metavar="FILE", help="plan.json path (written by --plan, read by --apply)")
    p_build.add_argument("--curation-epoch", type=int, metavar="N", help="fixed D4 curation epoch (committer/tagger date)")
    p_build.add_argument("--curation-offset", default="+0000", metavar="±HHMM")
    p_build.add_argument("--run-id", metavar="ID", help="candidate-ref run id (default: a fresh ULID)")
    p_build.add_argument("--scratch", action="store_true", help="write to refs/scratch/** (rebuild-compare; not journaled)")
    p_build.add_argument("--json", action="store_true", help="emit JSON (default and only format)")
    p_build.set_defaults(func=cmd_build)
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
