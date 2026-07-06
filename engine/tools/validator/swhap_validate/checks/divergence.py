"""DV-1 — published-remote divergence (revised-D3 rebuild-and-replace).

Compares the workbench's local ``refs/heads/SourceCode`` against the history on
the published remote and decides whether any divergence is *sanctioned*:

- **fast-forward** (the published tip is an ancestor of the local tip, equal
  included) → pure append → **PASS** (no finding).
- **divergence** (the histories have been rewritten / replaced) → **FAIL**,
  *unless* the journal records an SWH-backed supersession: a two-phase
  ``rewrite-event`` whose machine ``executed`` entry cites a curator ``sign-off``
  whose ``acknowledgement == "prior-snapshot-archived-in-swh"`` AND whose
  ``supersedes_snapshot_swhid`` equals the snapshot SWHID of the *previously
  published* refs. That recorded supersession downgrades the FAIL to an
  explained **WARN** (the prior history is permanent/citable in SWH; this is the
  revised-D3 rebuild-and-replace, ``analysis/decisions.md`` D3-RESOLVED
  2026-06-06, journal-schema.md §8.2).

The prior snapshot SWHID is **recomputed** over the SAME scoped ref set the
publisher used — ``SourceCode`` + final release tags + a forced
``HEAD→refs/heads/SourceCode`` alias — via
``swhap_core.swhid.snapshot_swhid(..., head_alias="refs/heads/SourceCode")``, NOT
over all origin refs. The computation is intrinsic/offline; no network beyond
the (already-local-in-tests) fetch of the remote refs.

The workbench repo is never mutated: the remote refs and the local SourceCode
are fetched into a throwaway temp repo where the comparison and the snapshot
computation happen.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile

from ..context import GitError, git, git_text
from ..report import FAIL, WARN, Finding

SOURCECODE_REF = "refs/heads/SourceCode"
_ACK_SUPERSEDE = "prior-snapshot-archived-in-swh"
_LOCAL_SC_TMP = "refs/dv1local/SourceCode"
_ROLE = "curator"


def _resolve_remote_url(ctx, published_remote: str) -> str:
    """Resolve ``published_remote`` to a fetchable URL/path.

    Accepts either a git remote configured in the workbench, or a direct
    URL/path. A configured remote name wins (so ``--published-remote origin``
    works); otherwise the value is used verbatim (a bare-repo path or URL).
    """
    url = git_text(ctx.repo, "remote", "get-url", published_remote, check=False).strip()
    if url:
        return url
    return published_remote


def _git_rc(*args: str) -> int:
    """Run git argv-only and return only the exit status (no stdout needed)."""
    p = subprocess.run(["git", *args], capture_output=True)
    return p.returncode


def _final_tag_refs(repo: str) -> list[str]:
    """Final (non-candidate) annotated/lightweight release tag refs in ``repo``.

    Candidate tags (``refs/tags/candidate/<model>/<run>/<tag>``) carry a slash
    after ``refs/tags/`` and are excluded — the publisher only promotes flat
    ``refs/tags/<tag>`` names to the published snapshot.
    """
    out = git_text(repo, "for-each-ref", "--format=%(refname)", "refs/tags/")
    refs = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        rel = line[len("refs/tags/"):]
        if "/" in rel:  # candidate/** — not a published release tag
            continue
        refs.append(line)
    return sorted(refs)


def _parse_entries(journal_bytes: bytes | None) -> list[dict]:
    """Parse the JSONL ledger into entries; tolerate a non-JSONL (derived md)
    view by skipping unparseable lines."""
    entries: list[dict] = []
    if not journal_bytes:
        return entries
    text = journal_bytes.decode("utf-8", "surrogateescape")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(obj, dict):
            entries.append(obj)
    return entries


def _recorded_supersession(entries: list[dict], prior_snp: str) -> dict | None:
    """Find a valid executed↔sign-off rewrite-event pair sanctioning a
    divergence away from ``prior_snp``.

    Returns ``{"sign_off": <id>, "executed": <id>}`` for the first match, else
    ``None``. Keys on the contract pair: the cited sign-off's
    ``acknowledgement == "prior-snapshot-archived-in-swh"`` AND its
    ``supersedes_snapshot_swhid == prior_snp``.
    """
    signoffs: dict[str, dict] = {}
    executed: list[dict] = []
    for e in entries:
        if e.get("action") != "rewrite-event":
            continue
        details = e.get("details") or {}
        phase = details.get("phase")
        if phase == "sign-off":
            eid = e.get("id")
            if eid:
                signoffs[eid] = e
        elif phase == "executed":
            executed.append(e)

    for ex in executed:
        det = ex.get("details") or {}
        so = signoffs.get(det.get("sign_off_entry"))
        if so is None:
            continue
        sod = so.get("details") or {}
        if sod.get("acknowledgement") != _ACK_SUPERSEDE:
            continue
        if sod.get("supersedes_snapshot_swhid") != prior_snp:
            continue
        return {"sign_off": so.get("id"), "executed": ex.get("id")}
    return None


def run(report, ctx, *, published_remote: str, journal_bytes: bytes | None):
    """DV-1 entry point. Caller guarantees ``--gate publish`` and a non-empty
    ``published_remote`` (else the CLI skips DV-1 with a truthful reason)."""
    report.ran("DV-1")

    if not ctx.ref_exists(SOURCECODE_REF):
        report.skip("DV-1", "workbench has no refs/heads/SourceCode to compare")
        return
    local_tip = ctx.rev_parse(SOURCECODE_REF)

    url = _resolve_remote_url(ctx, published_remote)

    tmp = tempfile.mkdtemp(prefix="swhap-dv1-")
    try:
        try:
            git(tmp, "init", "-q", "--bare", ".")
            # Remote published state at canonical names; local SourceCode aside.
            # --no-tags disables tag AUTO-following (explicit refspecs still
            # honoured): the remote's published tags come in via the explicit
            # refspec below, and the workbench fetch must NOT drag the local
            # (rebuilt) tags in to overwrite them — that would corrupt the prior
            # snapshot recomputation.
            git(tmp, "fetch", "-q", "--no-tags", url,
                f"{SOURCECODE_REF}:{SOURCECODE_REF}", "refs/tags/*:refs/tags/*",
                check=False)
            git(tmp, "fetch", "-q", "--no-tags", os.path.abspath(ctx.repo),
                f"{SOURCECODE_REF}:{_LOCAL_SC_TMP}", check=False)
        except GitError as exc:
            report.skip("DV-1", f"cannot reach published remote {published_remote!r}: {exc}")
            return

        remote_tip = git_text(tmp, "rev-parse", "--verify", SOURCECODE_REF,
                              check=False).strip()
        if not remote_tip:
            report.skip("DV-1",
                        "published remote has no SourceCode branch (nothing published yet)")
            return

        # fast-forward (pure append) ⇒ PASS. is-ancestor is reflexive, so an
        # identical published tip is a fast-forward too.
        if _git_rc("-C", tmp, "merge-base", "--is-ancestor", remote_tip, local_tip) == 0:
            return

        # divergence: verify a recorded, SWH-backed supersession or FAIL.
        prior_snp = _prior_snapshot(tmp)
        if prior_snp is None:
            report.add(Finding(
                "DV-1", FAIL,
                {"ref": SOURCECODE_REF, "local_tip": local_tip,
                 "remote_tip": remote_tip, "divergence": True,
                 "reason": "snapshot-swhid-unavailable"},
                ["ref"],
                "The local SourceCode history diverges from the published remote, "
                "but the prior published snapshot SWHID could not be computed "
                "(swh.model unavailable), so the supersession cannot be verified.",
                message_technical="DV-1: divergence; swh.model required to recompute "
                "the prior published snapshot SWHID",
                required_approver_role=_ROLE,
                remediation="Install swh.model (the publish-path dependency) to "
                "verify the recorded supersession.",
            ))
            return

        entries = _parse_entries(journal_bytes)
        rec = _recorded_supersession(entries, prior_snp)
        if rec is not None:
            report.add(Finding(
                "DV-1", WARN,
                {"ref": SOURCECODE_REF, "local_tip": local_tip,
                 "remote_tip": remote_tip, "divergence": True,
                 "supersedes_snapshot_swhid": prior_snp,
                 "sign_off_entry": rec["sign_off"],
                 "executed_entry": rec["executed"],
                 "acknowledgement": _ACK_SUPERSEDE},
                ["ref", "supersedes_snapshot_swhid"],
                "The local SourceCode history supersedes the published remote. This "
                f"is a recorded, SWH-backed rebuild-and-replace: the prior snapshot "
                f"{prior_snp} is archived in Software Heritage (curator sign-off "
                f"{rec['sign_off']}, executed {rec['executed']}), so the prior "
                "history stays permanently citable. Divergence is sanctioned.",
                message_technical="DV-1: divergence sanctioned by recorded "
                f"supersession (supersedes {prior_snp})",
                provenance={"item": rec["sign_off"], "state": "curator-approved"},
                required_approver_role=_ROLE,
            ))
            return

        report.add(Finding(
            "DV-1", FAIL,
            {"ref": SOURCECODE_REF, "local_tip": local_tip,
             "remote_tip": remote_tip, "divergence": True,
             "supersedes_snapshot_swhid": prior_snp},
            ["ref"],
            "The local SourceCode history diverges from the published remote with "
            "no recorded, SWH-archived supersession justifying it. This is an "
            "un-journaled / un-archived divergence (an accidental clobber of the "
            f"published history, prior snapshot {prior_snp}).",
            message_technical="DV-1: un-journaled/un-archived published divergence "
            "(no rewrite-event supersedes the prior published snapshot)",
            required_approver_role=_ROLE,
            remediation="If this replacement is intended, archive the prior "
            "published snapshot in SWH and record the two-phase rewrite-event "
            "(curator sign-off + machine executed) via `swhap publish --supersede` "
            "before re-publishing.",
        ))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _prior_snapshot(tmp: str) -> str | None:
    """Snapshot SWHID of the published refs in ``tmp`` over the publisher's
    scoped ref set (SourceCode + final tags + forced HEAD→SourceCode alias).

    Returns ``None`` if ``swh.model`` is unavailable (the publish-path dep), so
    the caller can FAIL-safe rather than silently pass an unverifiable
    divergence.
    """
    try:
        from swhap_core.swhid import snapshot_swhid
    except ImportError:
        return None
    refs = [SOURCECODE_REF, *_final_tag_refs(tmp)]
    return snapshot_swhid(tmp, refs, head_alias=SOURCECODE_REF)
