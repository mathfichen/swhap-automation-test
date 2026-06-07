"""Snapshot-SWHID computation for the published curated history (M2 publish).

A snapshot SWHID ``swh:1:snp:<sha1>`` is the SWH-specific salted-sha1 over a
repository's *full ref state* (the named branches/tags and their targets). It is
**computable locally and offline**: the value this module computes for a set of
published refs is byte-identical to the one Software Heritage assigns when it
visits the same refs (``swh identify --type snapshot`` over a repo with exactly
those refs returns the same string — pinned by ``tests/test_swhid.py``).

This is the durable lineage pointer of the revised-D3 *rebuild-and-replace*
model (``analysis/decisions.md`` D3-RESOLVED, 2026-06-06): before a published
SourceCode history is superseded, the snapshot SWHID of the *current* published
refs is recorded in the journal so the prior, archived-in-SWH history stays
permanently citable.

The git→SWH intrinsic-identifier equality is what makes this offline:
git commit sha1 == ``swh:1:rev``, annotated-tag sha1 == ``swh:1:rel``,
tree == ``swh:1:dir``, blob == ``swh:1:cnt``. So a ref's target *type* (read with
``git cat-file -t``) and its *git oid* are exactly the SWH branch target this
module feeds to :func:`swh.model.model.Snapshot`.

Only ``swh.model`` is imported here (and only lazily) — the rest of swhap-core
stays stdlib-only (core-pipeline §2); ``swh.model`` is a dependency of the
publish path alone.
"""

from __future__ import annotations

from .errors import HistoryError
from .gitio import GitRunner

SNP_PREFIX = "swh:1:snp:"

# git object type (``cat-file -t`` / ``for-each-ref %(objecttype)``) → SWH branch
# target type. Mirrors swh.model.cli._DULWICH_TYPES so the locally-computed
# snapshot id equals what ``swh identify --type snapshot`` produces.
_GIT_TO_SWH = {
    "commit": "revision",
    "tag": "release",
    "tree": "directory",
    "blob": "content",
}


def _git(repo: str | GitRunner) -> GitRunner:
    return repo if isinstance(repo, GitRunner) else GitRunner(repo)


def _enumerate_refs(git: GitRunner) -> dict[str, tuple[str, str]]:
    """All refs in the repo → ``{refname: (oid, git_objecttype)}``."""
    out = git.run(
        ["for-each-ref", "--format=%(refname) %(objectname) %(objecttype)"]
    ).decode("utf-8", "surrogateescape")
    refs: dict[str, tuple[str, str]] = {}
    for line in out.splitlines():
        if not line.strip():
            continue
        name, oid, typ = line.rsplit(" ", 2)
        refs[name] = (oid, typ)
    return refs


def _head_symref(git: GitRunner) -> str | None:
    """The ref ``HEAD`` symbolically points at, or ``None`` if detached/absent."""
    try:
        out = git.run(["symbolic-ref", "--quiet", "HEAD"]).decode().strip()
    except HistoryError:
        return None
    return out or None


def _swh_type(git: GitRunner, oid: str) -> str:
    try:
        return _GIT_TO_SWH[git.cat_file_type(oid)]
    except KeyError as exc:  # pragma: no cover - defensive
        raise HistoryError(f"unmappable git object type for {oid}", code="HB-PLAN-DRIFT") from exc


def snapshot_branches(
    repo: str | GitRunner,
    refs: list[str] | None = None,
    *,
    head_alias: str | None = None,
    include_head: bool = True,
) -> dict[bytes, dict]:
    """Build the SWH snapshot ``branches`` mapping for a repo's refs.

    - ``refs=None`` → every ref in the repo (mirrors ``swh identify``).
    - ``refs=[...]`` → only those ref names that exist in the repo.
    - ``head_alias`` → force a ``HEAD`` alias to that ref name (independent of the
      repo's actual HEAD); used by publish so the computation does not depend on
      the working repo's HEAD pointing at ``main``.
    - ``include_head`` (and no ``head_alias``) → derive ``HEAD`` from the repo's
      symbolic ref, matching ``swh identify``'s behaviour.
    """
    git = _git(repo)
    all_refs = _enumerate_refs(git)
    selected = all_refs if refs is None else {r: all_refs[r] for r in refs if r in all_refs}

    branches: dict[bytes, dict] = {}
    for name, (oid, typ) in selected.items():
        branches[name.encode("utf-8", "surrogateescape")] = {
            "target": bytes.fromhex(oid),
            "target_type": _GIT_TO_SWH.get(typ) or _swh_type(git, oid),
        }

    if head_alias is not None:
        branches[b"HEAD"] = {
            "target": head_alias.encode("utf-8", "surrogateescape"),
            "target_type": "alias",
        }
    elif include_head:
        head = _head_symref(git)
        if head is not None and head in all_refs:
            branches[b"HEAD"] = {
                "target": head.encode("utf-8", "surrogateescape"),
                "target_type": "alias",
            }
    return branches


def compute_snapshot_swhid(branches: dict[bytes, dict]) -> str:
    """Compute ``swh:1:snp:…`` from a SWH ``branches`` mapping (swh.model)."""
    from swh.model.model import Snapshot  # lazy: keep the rest stdlib-only

    return str(Snapshot.from_dict({"branches": branches}).swhid())


def snapshot_swhid(
    repo: str | GitRunner,
    refs: list[str] | None = None,
    *,
    head_alias: str | None = None,
    include_head: bool = True,
) -> str:
    """The snapshot SWHID of ``repo`` over ``refs`` (default: all refs).

    Equals ``swh identify --type snapshot`` over a repo holding exactly those
    refs. Pure function of the ref names and their git oids/types — no network.
    """
    return compute_snapshot_swhid(
        snapshot_branches(repo, refs, head_alias=head_alias, include_head=include_head)
    )
