"""CLI orchestration: profile/gate selection, check dispatch, report emission,
exit codes. argv-only (no SWHAP_* env, no --ci flag) per the frozen contract.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import sys

from . import profiles
from .context import RepoContext
from .report import EXIT_INTERNAL, EXIT_USAGE, Report
from .checks import (branch_purity, codemeta, csv_contract, journal, pii,
                     preflight, size_lfs, tree_fidelity)


def _now_iso():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_reference_date(s):
    import calendar
    import re
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})"
                 r"(Z|[+-]\d{2}:\d{2})$", s)
    if not m:
        raise ValueError(f"bad --reference-date {s!r}")
    y, mo, d, hh, mm, ss, off = m.groups()
    base = _dt.datetime(int(y), int(mo), int(d), int(hh), int(mm), int(ss))
    inst = calendar.timegm(base.timetuple())
    if off != "Z":
        sign = 1 if off[0] == "+" else -1
        inst -= sign * (int(off[1:3]) * 3600 + int(off[4:6]) * 60)
    return inst


def run_validation(workdir, profile, gate, *, manifests=None,
                   intake_profile=None, published_remote=None,
                   strict_warn=False, meta_stable=False, reference_date=None,
                   skip=None, only=None, invocation=None):
    """Run the M1a battery; return a finalized Report. `manifests` is an ordered
    list of (tag, Manifest) for the TF battery (oracle from the fixtures slice).
    """
    skip = set(skip or ())
    ctx = RepoContext(workdir)
    head = ctx.head()
    report = Report(profile, gate, strict_warn=strict_warn,
                    meta_stable=meta_stable,
                    timestamp=None if meta_stable else _now_iso(),
                    repo=None if meta_stable else workdir,
                    head=head, intake_profile=intake_profile,
                    published_remote=published_remote,
                    invocation=None if meta_stable else invocation)

    def enabled(cid):
        if cid in skip:
            report.skip(cid, "skipped via --skip")
            return False
        if only and cid not in only:
            return False
        if profiles.is_skipped(profile, cid):
            report.skip(cid, "not run in this profile")
            return False
        return True

    # ---- preflight (gates the rest) ------------------------------------
    if enabled("PC-1"):
        if not preflight.run(report, ctx):
            return _finalize(report, profile)

    default = ctx.default_branch()
    csv_bytes = ctx.read_path(f"refs/heads/{default}", "metadata/version_history.csv") if default else None
    codemeta_bytes = ctx.read_path(f"refs/heads/{default}", "metadata/codemeta.json") if default else None
    journal_bytes = None
    if default:
        journal_bytes = ctx.read_path(f"refs/heads/{default}", "metadata/journal.jsonl") \
            or ctx.read_path(f"refs/heads/{default}", "metadata/journal.md")

    release_tags = _release_tags(csv_bytes, manifests, ctx)

    # ---- TF ------------------------------------------------------------
    if enabled("TF-1"):
        if manifests:
            tree_fidelity.run(report, ctx, manifests)
            for tag, _m in manifests:
                report.refs_checked.append(f"refs/tags/{tag}")
        else:
            for cid in ("TF-1", "TF-2", "TF-3", "TF-4", "TF-5"):
                report.skip(cid, "no ground-truth manifest provided")

    # ---- BP ------------------------------------------------------------
    if enabled("BP-1"):
        branch_purity.run(report, ctx, profile=profile, release_tags=release_tags)

    # ---- CSV -----------------------------------------------------------
    if enabled("CSV-1"):
        csv_contract.run(report, csv_bytes=csv_bytes, profile=profile,
                         reference_date=reference_date)

    # ---- CM ------------------------------------------------------------
    if enabled("CM-1"):
        codemeta.run(report, ctx, codemeta_bytes=codemeta_bytes)

    # ---- SZ ------------------------------------------------------------
    if enabled("SZ-1"):
        refs = []
        if default:
            refs.append(f"refs/heads/{default}")
        if ctx.ref_exists("refs/heads/SourceCode"):
            refs.append("refs/heads/SourceCode")
        for t in release_tags:
            if ctx.ref_exists(f"refs/tags/{t}"):
                refs.append(f"refs/tags/{t}")
        size_lfs.run(report, ctx, refs=refs, intake_profile=intake_profile)

    # ---- PI ------------------------------------------------------------
    if enabled("PI-1"):
        pii.run(report, ctx, csv_bytes=csv_bytes, journal_bytes=journal_bytes)

    # ---- JC-1a ---------------------------------------------------------
    if enabled("JC-1a"):
        journal.run(report, ctx, journal_bytes=journal_bytes,
                    release_tags=release_tags)

    return _finalize(report, profile)


def _release_tags(csv_bytes, manifests, ctx):
    if manifests:
        return [t for t, _m in manifests]
    # derive from canonical CSV if present
    tags = []
    if csv_bytes:
        import csv as _csv
        import io
        first = csv_bytes.split(b"\n", 1)[0].rstrip(b"\r")
        if first == csv_contract.CANONICAL_HEADER_BYTES:
            try:
                rows = list(_csv.reader(io.StringIO(csv_bytes.decode("utf-8"))))[1:]
                for r in rows:
                    if len(r) == 8 and r[6]:
                        tags.append(r[6])
            except Exception:
                pass
    if tags:
        return tags
    # fall back to all annotated tags in the repo
    return [t for t in ctx.tags() if ctx.is_annotated_tag(t)]


def _finalize(report, profile):
    for f in report.findings:
        f.enforced = profiles.is_enforced(profile, f.check_id)
    return report


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="swhap-validate", add_help=True)
    ap.add_argument("--profile", choices=list(profiles.PROFILES))
    ap.add_argument("--gate", choices=["build", "publish"], default="build")
    ap.add_argument("--report", default="-")
    ap.add_argument("--skip", default="")
    ap.add_argument("--checks", default="")
    ap.add_argument("--published-remote")
    ap.add_argument("--intake-profile", choices=["browser", "cli"])
    ap.add_argument("--workdir", default=".")
    ap.add_argument("--raw-materials")
    ap.add_argument("--strict-warn", action="store_true")
    ap.add_argument("--run-meta-stable", action="store_true")
    ap.add_argument("--reference-date")
    try:
        ns = ap.parse_args(argv)
    except SystemExit:
        return EXIT_USAGE

    ref_date = None
    if ns.reference_date:
        try:
            ref_date = _parse_reference_date(ns.reference_date)
        except ValueError as exc:
            sys.stderr.write(f"usage error: {exc}\n")
            return EXIT_USAGE

    skip = [s for s in ns.skip.split(",") if s]
    only = [s for s in ns.checks.split(",") if s] or None
    profs = [ns.profile] if ns.profile else [profiles.STRICT_P, profiles.STRICT_G]

    if len(profs) > 1 and ns.report == "-":
        sys.stderr.write("usage error: --report - rejected in dual-profile mode\n")
        return EXIT_USAGE

    proc_exit = 0
    for prof in profs:
        try:
            report = run_validation(
                ns.workdir, prof, ns.gate, intake_profile=ns.intake_profile,
                published_remote=ns.published_remote,
                strict_warn=ns.strict_warn, meta_stable=ns.run_meta_stable,
                reference_date=ref_date, skip=skip, only=only,
                invocation=["swhap-validate", *argv])
        except Exception as exc:  # internal error → exit 3
            report = Report(prof, ns.gate)
            report.error = {"code": "internal", "message": str(exc)}
            _emit(report, ns.report, prof, len(profs) > 1)
            return EXIT_INTERNAL
        _emit(report, ns.report, prof, len(profs) > 1)
        proc_exit = max(proc_exit, report.exit_code())
    return proc_exit


def _emit(report, target, profile, dual):
    text = report.serialize()
    if target == "-":
        sys.stdout.write(text)
        return
    path = target
    if dual:
        if "." in target:
            stem, ext = target.rsplit(".", 1)
            path = f"{stem}.{profile}.{ext}"
        else:
            path = f"{target}.{profile}"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


if __name__ == "__main__":
    raise SystemExit(main())
