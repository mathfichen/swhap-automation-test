"""CLI orchestration: profile/gate selection, check dispatch, report emission,
exit codes. argv-only (no SWHAP_* env, no --ci flag) per the frozen contract.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import sys

from . import manifest as _manifest
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
                   skip=None, only=None, invocation=None,
                   manifest_skip_reason=None):
    """Run the M1a battery; return a finalized Report. `manifests` is a
    release-ordered ``list[Manifest]`` (ground-truth tree oracles); the TF
    battery maps each to its real git tree — a release tag where one exists, else
    the SourceCode commit whose message names the release — and compares them.
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
    # FIX-2 (AX5/T10): the legacy audit profile must tolerate the documented
    # installed-base convention of a root-level codemeta.json (external.md C8 —
    # SWH indexing expects codemeta at the repo root). DT2SG-era acquisitions
    # ship codemeta.json at the repo root with NO metadata/codemeta.json; the
    # strict reader then raised a CM-1 "missing" FALSE failure under the legacy
    # profile. So in legacy only, fall back to a root-level codemeta.json when
    # the canonical metadata/ location is absent. The strict-P/strict-G profiles
    # are unchanged: codemeta MUST live in metadata/ there. CM-2..4 (e.g. the
    # bogus-@context true defect) still apply to whichever file is found.
    if (profile == profiles.LEGACY and codemeta_bytes is None and default):
        codemeta_bytes = ctx.read_path(f"refs/heads/{default}", "codemeta.json")
    journal_bytes = None
    if default:
        journal_bytes = ctx.read_path(f"refs/heads/{default}", "metadata/journal.jsonl") \
            or ctx.read_path(f"refs/heads/{default}", "metadata/journal.md")

    release_tags = _release_tags(csv_bytes, manifests, ctx)

    # ---- TF ------------------------------------------------------------
    ordered, unmapped = ([], [])
    if manifests:
        ordered, unmapped = _map_releases(ctx, manifests)
    if enabled("TF-1"):
        if ordered:
            tree_fidelity.run(report, ctx, ordered)
            seen = set()
            for _rel, ref, _m in ordered:
                r = ref if ref.startswith("refs/") else "refs/heads/SourceCode"
                if r not in seen:
                    report.refs_checked.append(r)
                    seen.add(r)
            for rel, reason in unmapped:
                report.skip("TF-1", f"release {rel} not located ({reason})")
        else:
            reason = (manifest_skip_reason
                      or ("provided manifests do not map to any release tree"
                          if manifests else "no ground-truth manifest provided"))
            for cid in ("TF-1", "TF-2", "TF-3", "TF-4", "TF-5"):
                report.skip(cid, reason)

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
    # 1. the canonical CSV release-tag column is authoritative when present.
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
    # 2. otherwise the EXPECTED tag names per the ground-truth releases — the
    #    SWHAP convention is one annotated tag `v<release>` per release. On the
    #    published exemplar (no canonical CSV, no tags) this makes BP-3 record
    #    the missing-tag compliance defect instead of going silent.
    if manifests:
        return [f"v{m.release}" for m in manifests]
    # 3. fall back to all annotated tags in the repo.
    return [t for t in ctx.tags() if ctx.is_annotated_tag(t)]


def _subject_names_release(subject, release):
    """True if a SourceCode commit subject names `release` as a delimited token
    (e.g. 'Wild_LIFE 1.0 (reconstructed ...)' names '1.0' but not '1.02')."""
    return re.search(r"(?:^|\s)" + re.escape(release) + r"(?:\s|$)",
                     subject) is not None


def _map_releases(ctx, manifests):
    """Map each ground-truth Manifest to the real git tree to validate.

    Preference order per release: an annotated/lightweight tag named `v<rel>` or
    `<rel>`; else (the published exemplar ships NO tags) the unique SourceCode
    commit whose message names the release. Returns
    ``(ordered, unmapped)`` where ordered = list[(release, ref, Manifest)] and
    ref is a resolvable git ref (tag ref) or a commit sha.
    """
    ordered, unmapped = [], []
    sc_commits = []
    if ctx.ref_exists("refs/heads/SourceCode"):
        for c in ctx.commits_on("refs/heads/SourceCode"):
            sc_commits.append((c, ctx.commit_subject(c)))
    for man in manifests:
        rel = man.release
        ref = None
        for cand in (f"v{rel}", rel):
            if ctx.ref_exists(f"refs/tags/{cand}"):
                ref = f"refs/tags/{cand}"
                break
        if ref is None and sc_commits:
            matches = [c for c, subj in sc_commits
                       if _subject_names_release(subj, rel)]
            if len(matches) == 1:
                ref = matches[0]
            else:
                unmapped.append((rel, "ambiguous-commit" if matches
                                 else "no-matching-commit"))
                continue
        if ref is None:
            unmapped.append((rel, "no-tag-no-sourcecode"))
            continue
        ordered.append((rel, ref, man))
    return ordered, unmapped


def _load_oracle_manifests(manifests_dir, raw_materials):
    """Discover ground-truth tree manifests. Returns ``(manifests, skip_reason)``
    where manifests is a release-ordered list[Manifest] or None (no oracle dir
    given). A given-but-empty directory yields ([], reason) so TF SKIPs with a
    truthful reason rather than silently passing.

    `--manifests <dir>` is an explicit oracle directory. `--raw-materials <dir>`
    (the workbench raw_materials/) is also honoured: if it carries tree
    manifests (or a manifests/ subdir) they are used; if it carries only
    archives the validator does NOT extract them — derivation via `swhap
    inspect` is core-owned and out of M1a scope — and TF SKIPs with that reason.
    """
    if manifests_dir:
        if not os.path.isdir(manifests_dir):
            return [], "--manifests path is not a directory"
        mans = _manifest.load_dir(manifests_dir)
        if mans:
            return mans, None
        return [], "--manifests directory carries no swhap-tree-manifest/1 oracles"
    if raw_materials:
        if not os.path.isdir(raw_materials):
            return [], "--raw-materials path is not a directory"
        for cand in (raw_materials, os.path.join(raw_materials, "manifests")):
            if os.path.isdir(cand):
                mans = _manifest.load_dir(cand)
                if mans:
                    return mans, None
        return [], ("--raw-materials carries no tree manifests; deriving them "
                    "from archives (swhap inspect) is out of M1a scope")
    return None, None


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
    # Ground-truth tree-manifest oracle for the TF battery. --manifests is the
    # explicit oracle directory; --raw-materials points at the workbench
    # raw_materials/ (honoured for manifest discovery — see _load_oracle_manifests
    # — never extracted here).
    ap.add_argument("--manifests")
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

    manifests, manifest_skip_reason = _load_oracle_manifests(
        ns.manifests, ns.raw_materials)

    if len(profs) > 1 and ns.report == "-":
        sys.stderr.write("usage error: --report - rejected in dual-profile mode\n")
        return EXIT_USAGE

    proc_exit = 0
    for prof in profs:
        try:
            report = run_validation(
                ns.workdir, prof, ns.gate, manifests=manifests,
                intake_profile=ns.intake_profile,
                published_remote=ns.published_remote,
                strict_warn=ns.strict_warn, meta_stable=ns.run_meta_stable,
                reference_date=ref_date, skip=skip, only=only,
                invocation=["swhap-validate", *argv],
                manifest_skip_reason=manifest_skip_reason)
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
