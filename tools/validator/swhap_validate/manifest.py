"""Ground-truth manifest loader/comparator (exemplar-pilot §4.1 schema).

This module OWNS NO extraction or admission logic (validator plan §2.3): the
single crit-M6 admission implementation lives in swhap-core. Here a manifest is
an external oracle — the wrapper-stripped expected tree — loaded and compared in
path space.
"""
from __future__ import annotations

import json
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
    return Manifest(
        release=doc["release"], tarball=doc["tarball"], sha256=sha256,
        wrapper=doc.get("wrapper"), entries=entries,
        empty_dirs=list(doc.get("empty_dirs", [])),
    )
