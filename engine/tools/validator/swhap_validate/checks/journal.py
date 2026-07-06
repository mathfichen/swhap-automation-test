"""JC-1a — journal hash-coverage, staged (schema-independent) form (M1a).

Every commit and annotated-tag object on the curated refs (SourceCode + release
tags) MUST be textually referenced in the journal. Catches the published
exemplar's boilerplate 2-row journal (defect RED-journal-coverage) before the
Q11 ledger schema lands. The full schema-aware JC-1/JC-2 forms are M1c.
"""
from __future__ import annotations

from ..report import FAIL, Finding

_ROLE = "curator"


def _covered(sha, text):
    # textual reference: full sha, or any short prefix git would print (≥7)
    for n in (40, 64, 12, 10, 8, 7):
        if len(sha) >= n and sha[:n] in text:
            return True
    return False


def run(report, ctx, *, journal_bytes, release_tags):
    report.ran("JC-1a")

    curated_objects = {}  # sha -> human label
    if ctx.ref_exists("refs/heads/SourceCode"):
        for c in ctx.commits_on("refs/heads/SourceCode"):
            curated_objects[c] = "commit on SourceCode"
    for tag in release_tags:
        if not ctx.ref_exists(f"refs/tags/{tag}"):
            continue
        obj = ctx.tag_object(tag)
        curated_objects[obj] = f"tag object for {tag}"
        commit = ctx.rev_parse(f"refs/tags/{tag}^{{commit}}")
        if commit:
            curated_objects[commit] = f"release commit for {tag}"

    if not curated_objects:
        return

    text = (journal_bytes or b"").decode("utf-8", "surrogateescape")
    uncovered = sorted(sha for sha in curated_objects if not _covered(sha, text))
    if uncovered:
        report.add(Finding(
            "JC-1a", FAIL,
            {"uncovered_count": len(uncovered),
             "total": len(curated_objects),
             "sample": [s[:12] for s in uncovered[:10]]},
            [],  # single global subject
            f"The journal does not record {len(uncovered)} of "
            f"{len(curated_objects)} reconstructed commits/tags; every release "
            "step must be journaled.",
            message_technical="JC-1a: hash-coverage gap (journal references no "
            "curated object hashes)" if len(uncovered) == len(curated_objects)
            else f"JC-1a: {len(uncovered)} uncovered object(s)",
            required_approver_role=_ROLE,
            remediation="Record each commit/tag in metadata/journal.jsonl.",
        ))
