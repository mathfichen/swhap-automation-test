"""Assemble an ``AcquisitionModel`` from a workbench (already-extracted trees).

The history builder consumes **already-extracted** release trees — it never
extracts or executes archive contents (that is ``swhap extract``'s hardened job,
crit-M6). Each release named in ``metadata/version_history.csv`` corresponds to a
directory ``<workbench>/<source_root>/<dirname>`` (the guide's ``source_code/v1``
layout). This module walks those trees deterministically and reads the canonical
CSV to produce the model the renderers consume.

Determinism (D4) and curatorial invariants applied here:

- **sorted, explicit-mode tree assembly**: entries are emitted in bytewise path
  order with explicit git modes (0644 / 0755+x / 120000).
- **``.emptydir`` preservation**: every directory empty after extraction gets a
  ``.emptydir`` empty marker (brief §10) — the only way git records an empty dir.
- **symlinks preserved, never followed**: a symlink becomes a 120000 blob whose
  body is the link target bytes.
- **byte-faithful paths**: names are read as bytes and round-tripped through
  surrogateescape, so a non-UTF-8 1990s filename reaches the git tree unchanged.
"""

from __future__ import annotations

import csv
import hashlib
import io
import os

from ..errors import CsvContractError, HistoryError
from ..model import (
    EMPTYDIR_MARKER,
    MODE_EXEC,
    MODE_FILE,
    MODE_SYMLINK,
    AcquisitionModel,
    CurationTimestamp,
    Identity,
    Release,
    TreeEntry,
)
from .dates import parse_date

CANONICAL_HEADER = (
    "directory name,date,author name,author email,"
    "curator name,curator email,release tag,commit message"
)
_COLS = [
    "directory name",
    "date",
    "author name",
    "author email",
    "curator name",
    "curator email",
    "release tag",
    "commit message",
]


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _walk_release_tree(root: str) -> tuple[TreeEntry, ...]:
    """Walk an extracted release directory → sorted ``TreeEntry`` tuple.

    Empty directories yield a ``.emptydir`` marker. Symlinks become 120000 blobs.
    """
    entries: list[TreeEntry] = []
    root = os.path.abspath(root)

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        rel_dir = os.path.relpath(dirpath, root)
        rel_dir = "" if rel_dir == "." else rel_dir.replace(os.sep, "/")

        # symlinked subdirectories are entries, not directories to descend.
        real_subdirs = []
        for dn in list(dirnames):
            full = os.path.join(dirpath, dn)
            if os.path.islink(full):
                target = os.readlink(full).encode("utf-8", "surrogateescape")
                p = f"{rel_dir}/{dn}" if rel_dir else dn
                entries.append(
                    TreeEntry(p, MODE_SYMLINK, "symlink", _sha256(target), len(target), target)
                )
                dirnames.remove(dn)
            else:
                real_subdirs.append(dn)

        has_children = bool(real_subdirs) or bool(filenames)
        if not has_children and rel_dir:
            # empty directory → .emptydir marker (brief §10)
            p = f"{rel_dir}/{EMPTYDIR_MARKER}"
            entries.append(TreeEntry(p, MODE_FILE, "blob", _sha256(b""), 0, b""))

        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            p = f"{rel_dir}/{fn}" if rel_dir else fn
            if os.path.islink(full):
                target = os.readlink(full).encode("utf-8", "surrogateescape")
                entries.append(
                    TreeEntry(p, MODE_SYMLINK, "symlink", _sha256(target), len(target), target)
                )
                continue
            with open(full, "rb") as fh:
                data = fh.read()
            mode = MODE_EXEC if (os.stat(full).st_mode & 0o100) else MODE_FILE
            entries.append(TreeEntry(p, mode, "blob", _sha256(data), len(data), data))

    entries.sort(key=lambda e: e.path.encode("utf-8", "surrogateescape"))
    if not entries:
        raise HistoryError(
            f"release tree {root!r} is empty (no files, no preservable empty dirs)",
            code="HB-DIR-MISSING",
            path=root,
        )
    return tuple(entries)


def read_version_history(csv_bytes: bytes) -> list[dict]:
    """Parse canonical ``version_history.csv`` bytes → ordered row dicts.

    Byte-exact header check (CSV-1); RFC-4180 quoting; CRLF tolerated on read.
    This is the builder-local reader; ``swhap_core.vhcsv`` is the canonical one.
    """
    text = csv_bytes.decode("utf-8")
    first_nl = text.find("\n")
    header = text[:first_nl] if first_nl >= 0 else text
    header = header.rstrip("\r")
    if header != CANONICAL_HEADER:
        if header.startswith("﻿"):
            raise CsvContractError("file starts with a UTF-8 BOM — remove it", code="CSV-HEADER")
        raise CsvContractError(
            f"version_history.csv header is not byte-exact (got {header!r})", code="CSV-HEADER"
        )
    rows = []
    reader = csv.reader(io.StringIO(text))
    for i, fields in enumerate(reader):
        if i == 0:
            continue
        if not fields:
            continue
        if len(fields) != 8:
            raise CsvContractError(
                f"row {i}: expected 8 fields, got {len(fields)}", code="CSV-FIELD", row=i
            )
        rows.append(dict(zip(_COLS, fields)))
    if not rows:
        raise CsvContractError("no data rows (an acquisition with zero releases)", code="CSV-FIELD")
    return rows


def build_model(
    workbench: str,
    *,
    curation_ts: CurationTimestamp,
    source_root: str = "source_code",
) -> AcquisitionModel:
    """Build the ``AcquisitionModel`` from a workbench directory."""
    wb = os.path.abspath(workbench)
    csv_path = os.path.join(wb, "metadata", "version_history.csv")
    if not os.path.isfile(csv_path):
        raise HistoryError(
            f"missing metadata/version_history.csv under {wb!r}", code="HB-DIR-MISSING", path=csv_path
        )
    with open(csv_path, "rb") as fh:
        csv_bytes = fh.read()
    rows = read_version_history(csv_bytes)

    seen_dir: set[str] = set()
    seen_tag: set[str] = set()
    releases: list[Release] = []
    for row in rows:
        dirname = row["directory name"]
        tag = row["release tag"]
        fold_d = dirname.casefold()
        fold_t = tag.casefold()
        if fold_d in seen_dir:
            raise CsvContractError(f"duplicate directory name {dirname!r}", code="CSV-DUP-DIR")
        if fold_t in seen_tag:
            raise CsvContractError(f"duplicate release tag {tag!r}", code="CSV-DUP-TAG")
        seen_dir.add(fold_d)
        seen_tag.add(fold_t)

        rel_dir = os.path.join(wb, source_root, dirname)
        if not os.path.isdir(rel_dir):
            raise HistoryError(
                f"release directory for row {dirname!r} not found at {rel_dir!r}",
                code="HB-DIR-MISSING",
                path=rel_dir,
            )
        entries = _walk_release_tree(rel_dir)
        releases.append(
            Release(
                dirname=dirname,
                tag=tag,
                message=row["commit message"],
                author=Identity(row["author name"], row["author email"]),
                author_date=parse_date(row["date"]),
                entries=entries,
            )
        )

    curator = Identity(rows[0]["curator name"], rows[0]["curator email"])
    # Model-G base metadata: the workbench metadata that co-locates with source on
    # the default branch. version_history.csv is canonical; README.md if present.
    metadata_files: list[TreeEntry] = [
        TreeEntry("metadata/version_history.csv", MODE_FILE, "blob", _sha256(csv_bytes), len(csv_bytes), csv_bytes)
    ]
    readme = os.path.join(wb, "README.md")
    if os.path.isfile(readme):
        with open(readme, "rb") as fh:
            rb = fh.read()
        metadata_files.append(TreeEntry("README.md", MODE_FILE, "blob", _sha256(rb), len(rb), rb))

    return AcquisitionModel(
        releases=tuple(releases),
        curator=curator,
        curation_ts=curation_ts,
        source_rows_sha256=_sha256(csv_bytes),
        metadata_files=tuple(metadata_files),
    )
