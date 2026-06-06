"""PLAN stage — render an ``AcquisitionModel`` into a deterministic ``BuildPlan``.

One internal model, two backends (D1 pilot):

- **Model P (orphan ``SourceCode`` purity, brief §9)** — ``render_p``. Each
  release is a commit whose tree is the *pure source at the root* (wrapper
  stripped, ``.emptydir`` markers, symlinks preserved). The chain is an **orphan**
  line: the first release commit has no parent, and no tree carries ``metadata/``
  or ``raw_materials/``. This is the reconstructed ``SourceCode`` development
  history; the Depository (``main``) — built elsewhere — holds only metadata.

- **Model G (source on the default branch, the guide/2025 layout)** — ``render_g``.
  Source lives on the default branch **alongside metadata**: each release commit's
  tree carries ``metadata/`` plus the cumulative browsable ``source_code/<dirname>/``
  folders (``SwhapGuide-GitHub-CLI.md`` §"machine readable source code"). The chain
  is parented (non-orphan), one annotated tag per release.

``BuildPlan`` is split into a JSON-able, fully deterministic view (``to_json`` —
no wall clock, no run-id, no git oids: identical inputs ⇒ identical ``plan.json``
bytes) and a runtime ``steps`` list carrying the blob bytes the APPLY stage feeds
to git plumbing. The fixed curation timestamp (D4) is recorded here and reused by
every rebuild as the committer/tagger date.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from ..model import (
    AcquisitionModel,
    Identity,
    ReleaseDate,
    TreeEntry,
)

PLAN_SCHEMA = "swhap-core/plan/v1"

CANDIDATE_BRANCH_TEMPLATE = "refs/heads/candidate/{model}/{run_id}"
CANDIDATE_TAG_TEMPLATE = "refs/tags/candidate/{model}/{run_id}/{tag}"
SCRATCH_BRANCH_TEMPLATE = "refs/scratch/{run_id}/{model}/SourceCode"
SCRATCH_TAG_TEMPLATE = "refs/scratch/{run_id}/{model}/tags/{tag}"


@dataclass(frozen=True)
class PlannedStep:
    index: int
    kind: str  # "release"
    dirname: str
    release_tag: str
    message: str
    author: Identity
    author_date: ReleaseDate
    parent_index: int | None
    entries: tuple[TreeEntry, ...]

    def tree_json(self) -> list[dict]:
        return [e.to_json() for e in sorted(self.entries, key=lambda x: x.path.encode("utf-8", "surrogateescape"))]


@dataclass(frozen=True)
class BuildPlan:
    model: str  # "P" | "G"
    model_version: str
    curator: Identity
    curation_epoch: int
    curation_offset: str
    source_rows_sha256: str
    steps: tuple[PlannedStep, ...]

    def to_json(self) -> dict:
        return {
            "schema": PLAN_SCHEMA,
            "model": self.model,
            "model_version": self.model_version,
            "curator": self.curator.to_json(),
            "curation_timestamp": {"epoch": self.curation_epoch, "offset": self.curation_offset},
            "source_rows_sha256": self.source_rows_sha256,
            "candidate_branch_template": CANDIDATE_BRANCH_TEMPLATE,
            "candidate_tag_template": CANDIDATE_TAG_TEMPLATE,
            "steps": [
                {
                    "index": s.index,
                    "kind": s.kind,
                    "dirname": s.dirname,
                    "release_tag": s.release_tag,
                    "message": s.message,
                    "author": s.author.to_json(),
                    "author_date": s.author_date.to_json(),
                    "parent_index": s.parent_index,
                    "tree": s.tree_json(),
                }
                for s in self.steps
            ],
        }

    def to_json_bytes(self) -> bytes:
        """Canonical, diff-stable plan.json bytes (sorted keys, LF, no env leak)."""
        return (json.dumps(self.to_json(), sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _reprefix(entries: tuple[TreeEntry, ...], prefix: str) -> list[TreeEntry]:
    out = []
    for e in entries:
        out.append(TreeEntry(f"{prefix}/{e.path}", e.mode, e.kind, e.sha256, e.size, e.content))
    return out


def render_p(model: AcquisitionModel) -> BuildPlan:
    """Model P: orphan ``SourceCode``, pure source at root, one tag per release."""
    steps = []
    for i, rel in enumerate(model.releases):
        steps.append(
            PlannedStep(
                index=i,
                kind="release",
                dirname=rel.dirname,
                release_tag=rel.tag,
                message=rel.message,
                author=rel.author,
                author_date=rel.author_date,
                parent_index=(i - 1) if i > 0 else None,
                entries=rel.entries,
            )
        )
    return _finish(model, "P", steps)


def render_g(model: AcquisitionModel) -> BuildPlan:
    """Model G: source on the default branch, cumulative ``source_code/<dir>/`` +
    ``metadata/``, one tag per release (parented chain — non-orphan)."""
    steps = []
    for i, rel in enumerate(model.releases):
        entries: list[TreeEntry] = list(model.metadata_files)
        for rel_j in model.releases[: i + 1]:
            entries.extend(_reprefix(rel_j.entries, f"source_code/{rel_j.dirname}"))
        steps.append(
            PlannedStep(
                index=i,
                kind="release",
                dirname=rel.dirname,
                release_tag=rel.tag,
                message=rel.message,
                author=rel.author,
                author_date=rel.author_date,
                parent_index=(i - 1) if i > 0 else None,
                entries=tuple(entries),
            )
        )
    return _finish(model, "G", steps)


def _finish(model: AcquisitionModel, model_name: str, steps: list[PlannedStep]) -> BuildPlan:
    return BuildPlan(
        model=model_name,
        model_version=model.model_version,
        curator=model.curator,
        curation_epoch=model.curation_ts.epoch,
        curation_offset=model.curation_ts.offset,
        source_rows_sha256=model.source_rows_sha256,
        steps=tuple(steps),
    )


RENDERERS = {"P": render_p, "G": render_g}


def render(model: AcquisitionModel, model_name: str) -> BuildPlan:
    try:
        return RENDERERS[model_name](model)
    except KeyError:
        raise ValueError(f"unknown branch model {model_name!r} (expected P or G)") from None
