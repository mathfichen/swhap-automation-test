"""Internal release representation — one model, two renderers (core-pipeline.md §4.3).

The history builder (T7) reconstructs curated Git history from an
``AcquisitionModel``: an AI-free, model-agnostic description of an acquisition's
releases. Two renderers (``history.render_p`` / ``history.render_g``) turn the
*same* model into two ``BuildPlan`` shapes (D1 pilot: orphan ``SourceCode``
purity vs. source-on-default-branch). Neither renderer touches extraction or CSV
code, so supporting both branch models costs one rendering backend (plan §5).

All dataclasses are frozen: a model is an immutable, hashable, inspectable value.
Determinism (D4) lives in how these values are *rendered*, never in wall-clock
state captured here. The only timestamps a model carries are the per-release
historical author date (from ``version_history.csv``) and the single fixed
curation timestamp (committer/tagger date for every commit/tag — D4).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Tree-entry modes (git, normalized per the extraction contract).
MODE_FILE = "100644"
MODE_EXEC = "100755"
MODE_SYMLINK = "120000"
MODE_TREE = "040000"

# .emptydir marker basename (empty-directory preservation, brief §10).
EMPTYDIR_MARKER = ".emptydir"

MODEL_VERSION = "swhap-acqmodel/1"


@dataclass(frozen=True)
class Identity:
    """A git identity (author or curator). ``name``/``email`` reach git only
    inside the commit/tag object body composed on stdin (``gitio`` writes the
    identity line straight into the object via ``git hash-object --literally``) —
    never argv, and never via ``GIT_AUTHOR_*`` / ``GIT_COMMITTER_*`` env vars — so
    a leading ``-`` or other content is inert (C1)."""

    name: str
    email: str

    def to_json(self) -> dict:
        return {"name": self.name, "email": self.email}


@dataclass(frozen=True)
class CurationTimestamp:
    """The single D4 fixed curation timestamp: committer + tagger date for every
    commit and tag of the acquisition. ``offset`` is the git raw-form offset
    ``±HHMM`` (journal-schema curation-timestamp ``offset`` pattern). Never the
    wall clock — supplied explicitly and recorded in metadata."""

    epoch: int
    offset: str = "+0000"

    def git_date(self) -> str:
        """Raw git date string ``@<epoch> ±HHMM`` (handles negative epochs)."""
        return f"@{self.epoch} {self.offset}"

    def to_json(self) -> dict:
        return {"epoch": self.epoch, "offset": self.offset}


@dataclass(frozen=True)
class ReleaseDate:
    """A historical release date — the commit's author-date (csv-contract §4.3).

    Rendered as the raw ``@<epoch> ±HHMM`` author-date line written directly into
    the commit object body by ``gitio`` (``git hash-object --literally``); it is
    NOT fed through a ``GIT_AUTHOR_DATE`` env var (env vars are not load-bearing).
    ``epoch`` is the true UTC instant (negative for pre-1970, crit-M3); ``offset``
    is the preserved ``±HHMM`` for faithful author-date rendering; ``precision`` is
    ``second|day|year`` and propagates to the provenance ledger.
    """

    epoch: int
    offset: str
    precision: str  # "second" | "day" | "year"

    def git_date(self) -> str:
        return f"@{self.epoch} {self.offset}"

    def to_json(self) -> dict:
        return {"epoch": self.epoch, "offset": self.offset, "precision": self.precision}


@dataclass(frozen=True)
class TreeEntry:
    """One file in a release source tree.

    ``path`` is the source-relative path (``/``-separated, str; original bytes
    are recovered via surrogateescape when fed to git). ``kind`` is ``blob`` or
    ``symlink``. ``sha256`` is the content sha256 (drift basis, never a git oid).
    ``content`` is the raw bytes (blob body, or the link target for a symlink).
    """

    path: str
    mode: str
    kind: str  # "blob" | "symlink"
    sha256: str
    size: int
    content: bytes = field(default=b"", repr=False, compare=False)

    def to_json(self) -> dict:
        return {
            "path": self.path,
            "mode": self.mode,
            "kind": self.kind,
            "sha256": self.sha256,
            "size": self.size,
        }


@dataclass(frozen=True)
class Release:
    """One release = one commit + one annotated tag (csv-contract §1)."""

    dirname: str
    tag: str
    message: str
    author: Identity
    author_date: ReleaseDate
    entries: tuple[TreeEntry, ...]  # sorted by path

    def manifest_sha256(self) -> str:
        import hashlib

        h = hashlib.sha256()
        for e in sorted(self.entries, key=lambda x: x.path.encode("utf-8", "surrogateescape")):
            h.update(e.path.encode("utf-8", "surrogateescape"))
            h.update(b"\0")
            h.update(f"{e.mode}:{e.kind}:{e.sha256}".encode())
            h.update(b"\n")
        return h.hexdigest()


@dataclass(frozen=True)
class AcquisitionModel:
    """The model-agnostic acquisition (core-pipeline.md §4.3)."""

    releases: tuple[Release, ...]
    curator: Identity
    curation_ts: CurationTimestamp
    source_rows_sha256: str
    metadata_files: tuple[TreeEntry, ...] = ()  # workbench metadata (Model G base)
    model_version: str = MODEL_VERSION
