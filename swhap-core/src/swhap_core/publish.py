"""``swhap publish`` — promote a validated candidate to the published Model-P
layout, and the revised-D3 *rebuild-and-replace* (``--supersede``) flow.

Two verbs:

- :func:`do_publish` — promote a candidate (``refs/heads/candidate/<model>/<run>``
  + its ``refs/tags/candidate/<model>/<run>/<tag>``) to the published Model-P
  layout: the orphan ``refs/heads/SourceCode`` branch and final annotated release
  tags ``refs/tags/<tag>``. Promotes ``metadata/codemeta.json`` to the
  default-branch **root** (critique C2: SWH indexes codemeta only at the
  default-branch root; a ``metadata/`` placement is invisible to the indexer).
  Pushes the published refs through an injectable :class:`PushTarget` and triggers
  Save Code Now through an injectable :class:`Archiver`; records a
  ``publish-event`` journal entry (FROZEN journal-schema §6).

- :func:`do_publish_supersede` — the revised-D3 core (``analysis/decisions.md``
  D3-RESOLVED, 2026-06-06). When a new or chronologically-*inserted* release
  changes an already-published history, the prior published history is **not**
  invalidated: its snapshot SWHID is permanent in SWH. The sequence is
  (i) compute the *current* published snapshot SWHID; (ii) ensure it is archived
  in SWH (the :class:`Archiver`; in tests a mock returns the matching snp);
  (iii) write the two-phase ``rewrite-event`` — a curator **sign-off** carrying
  ``details.supersedes_snapshot_swhid`` (the prior snp) and
  ``acknowledgement="prior-snapshot-archived-in-swh"``, then a machine
  **executed** entry citing it with ``old_hashes``/``new_hashes``; (iv) replace
  ``SourceCode`` (and the changed tags) with the freshly-rebuilt, bit-reproducible
  candidate (built via ``swhap_core.history``).

External boundaries (push, Save Code Now) are injectable adapters so the whole
flow is testable offline; the intrinsic snapshot SWHID needs no network.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from typing import Protocol

from .errors import PublishError
from .gitio import GitRunner
from .journal import Ledger, machine_actor, new_entry
from .swhid import snapshot_swhid

PUBLISH_VERB = "swhap publish"
SOURCECODE_REF = "refs/heads/SourceCode"
_CANDIDATE_BRANCH_PREFIX = "refs/heads/candidate/"


# --------------------------------------------------------------------------- #
# Injectable external adapters (push target + archiver)
# --------------------------------------------------------------------------- #
@dataclass
class SaveResult:
    """Outcome of a Save Code Now trigger."""

    request_url: str
    visit_status: str
    snapshot_swhid: str | None = None  # the snp once the visit reaches `full`

    def to_journal(self) -> dict:
        d = {"request_url": self.request_url, "visit_status": self.visit_status}
        return d


class Archiver(Protocol):
    """Triggers a Software Heritage visit of an origin (Save Code Now)."""

    def save(self, origin_url: str) -> SaveResult: ...


class PushTarget(Protocol):
    """Pushes a set of local refs to the published remote, same name → same name."""

    def push(self, repo: str, refs: list[str], *, force: bool = False) -> None: ...


@dataclass
class LocalBarePushTarget:
    """Push to a local bare repo standing in for the published remote.

    Used in tests (and valid for any reachable bare path). Sets the remote
    ``HEAD`` to ``SourceCode`` after the first push so the remote's snapshot
    matches the locally-computed published snapshot (curated source history)."""

    url: str

    def push(self, repo: str, refs: list[str], *, force: bool = False) -> None:
        git = GitRunner(repo)
        specs = [f"{'+' if force else ''}{ref}:{ref}" for ref in refs]
        args = ["push"]
        if force:
            args.append("--force")
        git.run([*args, self.url, *specs])
        # Point the remote default branch at SourceCode (the only branch we push):
        # makes ``swh identify`` over the remote include the HEAD→SourceCode alias.
        if SOURCECODE_REF in refs:
            GitRunner(self.url).run(["symbolic-ref", "HEAD", SOURCECODE_REF])


@dataclass
class RemotePushTarget:
    """Push to a real remote URL (e.g. a GitHub/GitLab origin), same name → same
    name. Does not set the remote ``HEAD`` (the forge owns the default branch)."""

    url: str

    def push(self, repo: str, refs: list[str], *, force: bool = False) -> None:  # pragma: no cover - network
        git = GitRunner(repo)
        specs = [f"{'+' if force else ''}{ref}:{ref}" for ref in refs]
        args = ["push"]
        if force:
            args.append("--force")
        git.run([*args, self.url, *specs])


@dataclass
class SaveCodeNowArchiver:
    """Thin real adapter: POST the origin to the SWH Save Code Now API.

    Kept deliberately minimal; the visit is asynchronous, so a single call
    returns the accepted/queued status and (when already available) the
    snapshot. Production callers poll until ``visit_status == "full"``."""

    api_url: str = "https://archive.softwareheritage.org/api/1/origin/save/git/url/"
    timeout: int = 30

    def save(self, origin_url: str) -> SaveResult:  # pragma: no cover - network
        import json as _json
        import urllib.request

        url = self.api_url + origin_url.rstrip("/") + "/"
        req = urllib.request.Request(url, method="POST", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
            payload = _json.loads(resp.read().decode("utf-8"))
        return SaveResult(
            request_url=url,
            visit_status=payload.get("save_task_status") or payload.get("save_request_status") or "accepted",
            snapshot_swhid=(payload.get("snapshot_swhid") or None),
        )


# --------------------------------------------------------------------------- #
# Results
# --------------------------------------------------------------------------- #
@dataclass
class PublishResult:
    final_repo: str
    sourcecode_tip: str
    final_tags: dict[str, str]  # release_tag -> tag oid
    snapshot_swhid: str
    rel_swhids: list[str]
    dir_swhid: str
    codemeta_promoted: bool
    save: SaveResult | None
    publish_entry_id: str


@dataclass
class SupersedeResult:
    final_repo: str
    prior_snapshot_swhid: str
    new_snapshot_swhid: str
    sign_off_entry_id: str
    executed_entry_id: str
    target_refs: list[str]
    old_hashes: list[str]
    new_hashes: list[str]
    publish_entry_id: str
    publish: PublishResult = field(repr=False, default=None)  # type: ignore[assignment]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _ledger_for(workbench: str) -> Ledger:
    return Ledger(os.path.join(workbench, "metadata", "journal.jsonl"))


def _parse_candidate_ref(candidate_ref: str) -> tuple[str, str]:
    """``refs/heads/candidate/<model>/<run_id>`` → ``(model, run_id)``."""
    if not candidate_ref.startswith(_CANDIDATE_BRANCH_PREFIX):
        raise PublishError(
            f"not a candidate branch ref: {candidate_ref!r}", code="PB-NO-CANDIDATE"
        )
    rest = candidate_ref[len(_CANDIDATE_BRANCH_PREFIX):]
    parts = rest.split("/")
    if len(parts) != 2:
        raise PublishError(
            f"malformed candidate ref {candidate_ref!r} (want .../<model>/<run_id>)",
            code="PB-NO-CANDIDATE",
        )
    return parts[0], parts[1]


def _candidate_tags(git: GitRunner, model: str, run_id: str) -> dict[str, str]:
    """Map ``release_tag -> candidate tag oid`` for one candidate run."""
    prefix = f"refs/tags/candidate/{model}/{run_id}/"
    out = git.run(
        ["for-each-ref", "--format=%(refname) %(objectname)", prefix + "**"]
    ).decode("utf-8", "surrogateescape")
    tags: dict[str, str] = {}
    for line in out.splitlines():
        if not line.strip():
            continue
        name, oid = line.rsplit(" ", 1)
        tags[name[len(prefix):]] = oid
    return tags


def _final_tag_refs(git: GitRunner) -> dict[str, str]:
    """Currently-published final release tags ``release_tag -> tag oid``."""
    out = git.run(
        ["for-each-ref", "--format=%(refname) %(objectname)", "refs/tags/*"]
    ).decode("utf-8", "surrogateescape")
    tags: dict[str, str] = {}
    for line in out.splitlines():
        if not line.strip():
            continue
        name, oid = line.rsplit(" ", 1)
        rel = name[len("refs/tags/"):]
        if "/" in rel:  # skip candidate/** tags
            continue
        tags[rel] = oid
    return tags


def _promote_codemeta(workbench: str) -> dict | None:
    """Copy ``metadata/codemeta.json`` to the default-branch root (critique C2).

    SWH indexes ``codemeta.json`` only at the default-branch root; a ``metadata/``
    placement is invisible. Returns the root file output record, or ``None`` if
    there is no ``metadata/codemeta.json`` to promote.
    """
    src = os.path.join(workbench, "metadata", "codemeta.json")
    if not os.path.isfile(src):
        return None
    with open(src, "rb") as fh:
        data = fh.read()
    dst = os.path.join(workbench, "codemeta.json")
    existing = None
    if os.path.isfile(dst):
        with open(dst, "rb") as fh:
            existing = fh.read()
    if existing != data:
        with open(dst, "wb") as fh:
            fh.write(data)
    return {"path": "codemeta.json", "sha256": _sha256(data), "size_bytes": len(data)}


def _materialize_published_refs(
    git: GitRunner, tip: str, tags: dict[str, str]
) -> tuple[str, dict[str, str]]:
    """Write the published Model-P refs locally; return (SourceCode tip, {tag: final_ref})."""
    git.update_ref(SOURCECODE_REF, tip)
    final_refs: dict[str, str] = {}
    for release_tag, oid in tags.items():
        final_ref = f"refs/tags/{release_tag}"
        git.update_ref(final_ref, oid)
        final_refs[release_tag] = final_ref
    return tip, final_refs


def _published_snapshot(git: GitRunner, final_tag_refs: list[str]) -> str:
    refs = [SOURCECODE_REF, *final_tag_refs]
    return snapshot_swhid(git, refs, head_alias=SOURCECODE_REF)


# --------------------------------------------------------------------------- #
# do_publish
# --------------------------------------------------------------------------- #
def do_publish(
    workbench: str,
    *,
    candidate_ref: str,
    final_repo: str,
    push_target: PushTarget,
    archiver: Archiver | None = None,
    git: GitRunner | None = None,
    journal: bool = True,
) -> PublishResult:
    git = git or GitRunner(workbench, allow_publish=True)

    model, run_id = _parse_candidate_ref(candidate_ref)
    tip = git.rev_parse(candidate_ref)
    if tip is None:
        raise PublishError(f"candidate branch {candidate_ref!r} not found", code="PB-NO-CANDIDATE")
    cand_tags = _candidate_tags(git, model, run_id)
    if not cand_tags:
        raise PublishError(
            f"candidate {candidate_ref!r} has no release tags", code="PB-NO-CANDIDATE"
        )

    sc_tip, final_refs = _materialize_published_refs(git, tip, cand_tags)
    codemeta = _promote_codemeta(workbench)

    snp = _published_snapshot(git, sorted(final_refs.values()))
    rel_swhids = sorted(f"swh:1:rel:{oid}" for oid in cand_tags.values())
    tree_oid = git.run(["rev-parse", f"{sc_tip}^{{tree}}"]).decode().strip()
    dir_swhid = f"swh:1:dir:{tree_oid}"

    # push the published source refs to the remote
    push_refs = [SOURCECODE_REF, *sorted(final_refs.values())]
    push_target.push(workbench, push_refs, force=False)

    save = archiver.save(final_repo) if archiver is not None else None

    entry_id = ""
    if journal:
        entry_id = _journal_publish_event(
            workbench,
            candidate_ref=candidate_ref,
            final_repo=final_repo,
            final_refs=final_refs,
            cand_tags=cand_tags,
            snp=snp,
            rel_swhids=rel_swhids,
            dir_swhid=dir_swhid,
            codemeta=codemeta,
            save=save,
        )

    return PublishResult(
        final_repo=final_repo,
        sourcecode_tip=sc_tip,
        final_tags=dict(cand_tags),
        snapshot_swhid=snp,
        rel_swhids=rel_swhids,
        dir_swhid=dir_swhid,
        codemeta_promoted=codemeta is not None,
        save=save,
        publish_entry_id=entry_id,
    )


def _journal_publish_event(
    workbench: str,
    *,
    candidate_ref: str,
    final_repo: str,
    final_refs: dict[str, str],
    cand_tags: dict[str, str],
    snp: str,
    rel_swhids: list[str],
    dir_swhid: str,
    codemeta: dict | None,
    save: SaveResult | None,
) -> str:
    ledger = _ledger_for(workbench)
    ledger.ensure_genesis(os.path.basename(os.path.abspath(workbench)))

    outputs: list[dict] = []
    for release_tag in sorted(final_refs):
        outputs.append(
            {"type": "tag", "git_object": cand_tags[release_tag], "ref": final_refs[release_tag]}
        )
    outputs.append({"swhid": snp})
    for rel in rel_swhids:
        outputs.append({"swhid": rel})
    if codemeta is not None:
        outputs.append(codemeta)

    swhids: dict = {"snp": snp, "rel": rel_swhids, "dir": [dir_swhid]}
    details: dict = {
        "candidate_ref": candidate_ref,
        "final_repo": final_repo,
        "swhids": swhids,
        "verb": PUBLISH_VERB,
    }
    if save is not None:
        details["save_code_now"] = save.to_journal()

    entry = ledger.append(new_entry("publish-event", outputs=outputs, details=details))
    return entry["id"]


# --------------------------------------------------------------------------- #
# do_publish_supersede (revised-D3 rebuild-and-replace)
# --------------------------------------------------------------------------- #
def do_publish_supersede(
    workbench: str,
    *,
    candidate_ref: str,
    final_repo: str,
    curator: dict,
    push_target: PushTarget,
    archiver: Archiver,
    reason: str,
    git: GitRunner | None = None,
    journal: bool = True,
    require_archived: bool = True,
) -> SupersedeResult:
    """Rebuild-and-replace a published SourceCode history (revised D3).

    ``candidate_ref`` is the freshly-rebuilt candidate (built via
    ``swhap_core.history`` from the updated, re-ordered ``version_history.csv``).
    The prior published refs (``SourceCode`` + final tags) MUST already exist in
    ``workbench`` (left there by the previous :func:`do_publish`).
    """
    git = git or GitRunner(workbench, allow_publish=True)

    # (i) snapshot SWHID of the CURRENT published history (the prior, to be superseded)
    prior_tip = git.rev_parse(SOURCECODE_REF)
    if prior_tip is None:
        raise PublishError(
            "supersede requires an already-published SourceCode branch", code="PB-NO-CANDIDATE"
        )
    prior_tags = _final_tag_refs(git)  # release_tag -> oid
    prior_tag_refs = sorted(f"refs/tags/{t}" for t in prior_tags)
    prior_snp = _published_snapshot(git, prior_tag_refs)

    # (ii) ensure the prior snapshot is archived in SWH before replacement
    save_prior = archiver.save(final_repo)
    archived = save_prior.snapshot_swhid
    if archived is not None and archived != prior_snp:
        raise PublishError(
            f"archiver reported snapshot {archived} but the prior published refs hash to "
            f"{prior_snp} — refusing to supersede an unmatched snapshot",
            code="PB-SNAPSHOT-MISMATCH",
        )
    if require_archived and archived is None:
        raise PublishError(
            "prior published snapshot is not confirmed archived in SWH; refusing supersede "
            "(revised-D3: no un-archived clobber)",
            code="PB-PRIOR-UNARCHIVED",
        )

    # resolve the NEW (rebuilt) candidate
    model, run_id = _parse_candidate_ref(candidate_ref)
    new_tip = git.rev_parse(candidate_ref)
    if new_tip is None:
        raise PublishError(f"candidate branch {candidate_ref!r} not found", code="PB-NO-CANDIDATE")
    new_cand_tags = _candidate_tags(git, model, run_id)
    if not new_cand_tags:
        raise PublishError(
            f"candidate {candidate_ref!r} has no release tags", code="PB-NO-CANDIDATE"
        )

    new_tag_refs = sorted(f"refs/tags/{t}" for t in new_cand_tags)
    # target_refs = the published refs the rewrite touches; identical for both phases
    # (sign-off and executed) so the validator's set-equality (§5.4 step 8.1) holds.
    target_refs = sorted({SOURCECODE_REF, *prior_tag_refs, *new_tag_refs})
    old_hashes = [prior_tip, *[prior_tags[t] for t in sorted(prior_tags)]]
    new_hashes = [new_tip, *[new_cand_tags[t] for t in sorted(new_cand_tags)]]

    ledger = _ledger_for(workbench) if journal else None
    if ledger is not None:
        ledger.ensure_genesis(os.path.basename(os.path.abspath(workbench)))

    # (iii) two-phase rewrite-event: sign-off (curator) then executed (machine)
    sign_off_id = ""
    executed_id = ""
    if ledger is not None:
        sign_off = ledger.append(
            new_entry(
                "rewrite-event",
                actor=curator,
                details={
                    "phase": "sign-off",
                    "target_refs": target_refs,
                    "reason": reason,
                    "supersedes_snapshot_swhid": prior_snp,
                    "acknowledgement": "prior-snapshot-archived-in-swh",
                    "note": (
                        "Revised D3 (2026-06-06): rebuild-and-replace supersedes the prior "
                        "history; its SWHIDs are permanent in SWH (not invalidated)."
                    ),
                },
            )
        )
        sign_off_id = sign_off["id"]

    # (iv) replace SourceCode + changed tags with the rebuilt candidate
    git.update_ref(SOURCECODE_REF, new_tip)
    for release_tag, oid in new_cand_tags.items():
        git.update_ref(f"refs/tags/{release_tag}", oid)

    if ledger is not None:
        executed = ledger.append(
            new_entry(
                "rewrite-event",
                actor=machine_actor(),
                details={
                    "phase": "executed",
                    "target_refs": target_refs,
                    "reason": reason,
                    "sign_off_entry": sign_off_id,
                    "old_hashes": old_hashes,
                    "new_hashes": new_hashes,
                },
            )
        )
        executed_id = executed["id"]

    # push the replaced refs (non-fast-forward → force) and re-publish
    pub = do_publish(
        workbench,
        candidate_ref=candidate_ref,
        final_repo=final_repo,
        push_target=_ForcingPushTarget(push_target),
        archiver=archiver,
        git=git,
        journal=journal,
    )

    return SupersedeResult(
        final_repo=final_repo,
        prior_snapshot_swhid=prior_snp,
        new_snapshot_swhid=pub.snapshot_swhid,
        sign_off_entry_id=sign_off_id,
        executed_entry_id=executed_id,
        target_refs=target_refs,
        old_hashes=old_hashes,
        new_hashes=new_hashes,
        publish_entry_id=pub.publish_entry_id,
        publish=pub,
    )


@dataclass
class _ForcingPushTarget:
    """Wrap a push target to force non-fast-forward pushes (supersede replace)."""

    inner: PushTarget

    def push(self, repo: str, refs: list[str], *, force: bool = False) -> None:
        self.inner.push(repo, refs, force=True)
