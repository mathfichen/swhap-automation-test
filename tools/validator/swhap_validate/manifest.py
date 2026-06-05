"""Ground-truth manifest loader/comparator (exemplar-pilot §4.1 schema).

This module OWNS NO extraction or admission logic (validator plan §2.3): the
single crit-M6 admission implementation lives in swhap-core. Here a manifest is
an external oracle — the wrapper-stripped expected tree — loaded and compared in
path space.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass


@dataclass
class Entry:
    path: str
    type: str          # "file" | "symlink"
    mode: str          # "100644" | "100755" | "120000"
    blob: str          # git blob sha1 (file content, or hash of target string)
    target: str | None = None


@dataclass
class Manifest:
    release: str
    tarball: str
    sha256: str
    wrapper: str | None
    entries: dict       # path -> Entry
    empty_dirs: list    # POSIX paths of empty directories (→ .emptydir markers)
    quarantined: bool = False  # census-only oracle (e.g. 1.02): never a TF pass/fail oracle

    @property
    def files(self) -> dict:
        return {p: e for p, e in self.entries.items() if e.type == "file"}

    @property
    def symlinks(self) -> dict:
        return {p: e for p, e in self.entries.items() if e.type == "symlink"}


def load_manifest(path: str) -> Manifest:
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    return from_dict(doc)


def from_dict(doc: dict) -> Manifest:
    # Accept the frozen fixtures producer shape (swhap-tree-manifest/1, which
    # names the git blob sha1 `git_blob_sha1` and the archive digest
    # `tarball_sha256`) as well as the validator's own internal reconstruction
    # shape (`blob` / `sha256`). Entry.blob is the git blob sha1 — the TF
    # oracle joined against `git ls-tree` — so git_blob_sha1 maps onto it.
    entries = {}
    for e in doc["entries"]:
        blob = e.get("git_blob_sha1", e.get("blob"))
        if blob is None:
            raise KeyError("entry missing git_blob_sha1/blob")
        entries[e["path"]] = Entry(
            path=e["path"], type=e["type"], mode=e["mode"],
            blob=blob, target=e.get("target"),
        )
    sha256 = doc.get("tarball_sha256", doc.get("sha256"))
    empty_dirs = doc.get("empty_dirs", [])
    # swhap-tree-manifest/1 carries empty_dirs as a list of POSIX path strings;
    # the validator's reconstruction shape used the same. Tolerate either.
    empty_dirs = [e["path"] if isinstance(e, dict) else e for e in empty_dirs]
    return Manifest(
        release=doc["release"], tarball=doc["tarball"], sha256=sha256,
        wrapper=doc.get("wrapper"), entries=entries,
        empty_dirs=list(empty_dirs),
        quarantined=bool(doc.get("quarantined", False)),
    )


def _release_sort_key(release: str):
    """Order releases numerically where possible: 0.90 < 0.91 < 1.0 < 1.02."""
    key = []
    for tok in re.split(r"[._]", release):
        key.append((0, int(tok)) if tok.isdigit() else (1, tok))
    return key


def load_dir(path: str, *, include_quarantined: bool = False) -> list:
    """Load every ``swhap-tree-manifest/1`` JSON oracle under ``path`` as a
    release-ordered ``list[Manifest]``. Quarantined manifests (census-only, e.g.
    1.02) are excluded from the TF oracle unless explicitly requested. Files that
    are not tree manifests are ignored (so a directory may also carry README/
    evidence notes). Returns [] if nothing parses (caller decides to SKIP, not
    crash)."""
    out = []
    for name in sorted(os.listdir(path)):
        if not name.endswith(".json"):
            continue
        full = os.path.join(path, name)
        try:
            with open(full, encoding="utf-8") as fh:
                doc = json.load(fh)
        except (ValueError, OSError):
            continue
        if doc.get("schema") != "swhap-tree-manifest/1" and "entries" not in doc:
            continue
        try:
            man = from_dict(doc)
        except (KeyError, TypeError):
            continue
        if man.quarantined and not include_quarantined:
            continue
        out.append(man)
    out.sort(key=lambda m: _release_sort_key(m.release))
    return out
