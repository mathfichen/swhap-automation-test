"""TF-1..5 — tree fidelity vs the wrapper-stripped tarball manifest (C4 battery).

Compares each release's *real* git tree against its ground-truth manifest oracle
in path space (validator plan §2.3). The git tree is named by a resolved ref —
an annotated tag where one exists, OR (the published Wild_LIFE exemplar, which
ships NO tags) the SourceCode commit mapped to the release by commit message.
Findings are per-release aggregates (one finding = one subject) so a 1,145-entry
leak does not explode the report; the object carries the count and a
deterministic sample.

Mode handling (TF-2): blob CONTENT equality is the corruption signal the C4
register is defined on (0.90 clean, 0.91 +3 stale blobs, 1.0 stale LICENSE).
The 100644<->100755 exec bit is a SYSTEMATIC reconstruction artifact — the
published curator dropped it uniformly on EVERY release including the faithful
0.90 — so it is NOT a per-release corruption and must not make 0.90 red. TF-2
therefore collapses the exec bit for regular files while still catching a
type-significant mode break (a file that should be a symlink, mode 120000, or
vice-versa).
"""
from __future__ import annotations

from ..context import GitError
from ..report import FAIL, Finding

_SAMPLE = 10
_ROLE = "curator"


def _basename(p):
    return p.rsplit("/", 1)[-1]


def _file_mode_class(mode):
    """Collapse the exec bit for regular files; keep symlink (120000) distinct."""
    return "100000" if mode in ("100644", "100755") else mode


def _git_view(ctx, ref):
    """Return (files, symlinks, emptydirs) from the git tree at <ref>.
    files/symlinks: path -> (mode, blob_or_target). emptydirs: set of dir paths."""
    entries = ctx.ls_tree(ref)
    files, symlinks, emptydirs = {}, {}, set()
    for e in entries:
        if _basename(e.path) == ".emptydir":
            emptydirs.add(e.path[: -len("/.emptydir")] if "/" in e.path else "")
            continue
        if e.mode == "120000":
            target = ctx.cat_blob(e.blob).decode("utf-8", "surrogateescape")
            symlinks[e.path] = (e.mode, target)
        else:
            files[e.path] = (e.mode, e.blob)
    return files, symlinks, emptydirs


def run(report, ctx, ordered):
    """ordered: list of (release, ref, Manifest) in release order, where `ref`
    is a git ref/sha whose tree is the candidate (a release tag, or the mapped
    SourceCode commit when the exemplar ships no tags)."""
    for cid in ("TF-1", "TF-2", "TF-4", "TF-5"):
        report.ran(cid)
    if len(ordered) >= 2:
        report.ran("TF-3")

    git_views = {}
    for release, ref, man in ordered:
        try:
            git_views[release] = _git_view(ctx, ref)
        except GitError as exc:
            report.add(Finding(
                "TF-1", FAIL, {"release": release}, ["release"],
                f"The release {release} could not be read from git.",
                message_technical=str(exc), required_approver_role=_ROLE,
            ))
            continue
        _tf1_tf2(report, release, man, git_views[release])
        _tf4(report, release, man, git_views[release])
        _tf5(report, release, man, git_views[release])

    # TF-3 consecutive-release deletion check.
    for (a_rel, a_ref, a_man), (b_rel, b_ref, b_man) in zip(ordered, ordered[1:]):
        _tf3(report, ctx, a_rel, a_ref, a_man, b_rel, b_ref, b_man)


def _tf1_tf2(report, release, man, view):
    files, symlinks, _ = view
    git_paths = set(files) | set(symlinks)
    man_paths = set(man.entries)
    extras = sorted(git_paths - man_paths)
    missing = sorted(man_paths - git_paths)
    if extras or missing:
        report.add(Finding(
            "TF-1", FAIL,
            {"release": release, "extra_count": len(extras),
             "missing_count": len(missing),
             "extra_sample": extras[:_SAMPLE], "missing_sample": missing[:_SAMPLE]},
            ["release"],
            f"Release {release} does not contain exactly the files from the "
            f"original archive: {len(extras)} extra and {len(missing)} missing.",
            message_technical=(
                f"path-set mismatch: +{len(extras)} extra, -{len(missing)} missing"),
            required_approver_role=_ROLE,
            remediation="Rebuild the release tree from the verified tarball.",
        ))
    # TF-2 blob equality (+ type-significant mode) on matched paths.
    mismatches = []
    for p in sorted(git_paths & man_paths):
        e = man.entries[p]
        if p in files:
            gmode, gblob = files[p]
        else:
            gmode, gtarget = symlinks[p]
            gblob = None
        if e.type == "file":
            if gblob != e.blob or _file_mode_class(gmode) != _file_mode_class(e.mode):
                mismatches.append(p)
        else:  # symlink subject: target handled in TF-5; mode/type here
            if gmode != e.mode:
                mismatches.append(p)
    if mismatches:
        report.add(Finding(
            "TF-2", FAIL,
            {"release": release, "mismatch_count": len(mismatches),
             "sample": mismatches[:_SAMPLE]},
            ["release"],
            f"Release {release} has {len(mismatches)} file(s) whose content does "
            "not match the original archive.",
            message_technical=f"blob/type-mode mismatch on {len(mismatches)} "
            "path(s): " + ", ".join(mismatches[:_SAMPLE]),
            required_approver_role=_ROLE,
            remediation="Rebuild the affected files from the verified tarball.",
        ))


def _tf3(report, ctx, a_rel, a_ref, a_man, b_rel, b_ref, b_man):
    expected = set(a_man.entries) - set(b_man.entries)
    try:
        actual = ctx.diff_deletions(a_ref, b_ref)
    except GitError as exc:
        report.add(Finding(
            "TF-3", FAIL, {"from": a_rel, "to": b_rel}, ["from", "to"],
            f"Could not diff releases {a_rel} and {b_rel}.",
            message_technical=str(exc), required_approver_role=_ROLE))
        return
    actual = set(actual)
    missing_deletions = sorted(expected - actual)
    if missing_deletions:
        report.add(Finding(
            "TF-3", FAIL,
            {"from": a_rel, "to": b_rel,
             "expected_deletions": len(expected),
             "actual_deletions": len(actual),
             "missing_deletion_sample": missing_deletions[:_SAMPLE]},
            ["from", "to"],
            f"Going from {a_rel} to {b_rel}, {len(missing_deletions)} file(s) that "
            "the archive removed were never removed (previous-version leak).",
            message_technical=(
                f"expected {len(expected)} deletions, git diff shows "
                f"{len(actual)}; {len(missing_deletions)} not deleted"),
            required_approver_role=_ROLE,
            remediation="Rebuild each release tree from its own tarball.",
        ))


def _tf4(report, release, man, view):
    _, _, git_emptydirs = view
    man_emptydirs = set(man.empty_dirs)
    if git_emptydirs != man_emptydirs:
        report.add(Finding(
            "TF-4", FAIL,
            {"release": release,
             "git_only": sorted(git_emptydirs - man_emptydirs)[:_SAMPLE],
             "manifest_only": sorted(man_emptydirs - git_emptydirs)[:_SAMPLE]},
            ["release"],
            f"Release {release}'s empty-directory markers do not match the "
            "archive's empty directories.",
            message_technical=(".emptydir bijection broken: git="
                               f"{sorted(git_emptydirs)} manifest="
                               f"{sorted(man_emptydirs)}"),
            required_approver_role=_ROLE,
        ))


def _tf5(report, release, man, view):
    _, git_syms, _ = view
    man_syms = man.symlinks
    git_map = {p: t for p, (m, t) in git_syms.items()}
    man_map = {p: e.target for p, e in man_syms.items()}
    if set(git_map) != set(man_map) or any(
            git_map.get(p) != man_map.get(p) for p in man_map):
        report.add(Finding(
            "TF-5", FAIL,
            {"release": release, "git_count": len(git_map),
             "manifest_count": len(man_map)},
            ["release"],
            f"Release {release}'s symbolic links do not match the archive "
            f"({len(git_map)} in git vs {len(man_map)} expected).",
            message_technical=f"symlink set/target mismatch: git={sorted(git_map)} "
            f"manifest={sorted(man_map)}",
            required_approver_role=_ROLE,
        ))
