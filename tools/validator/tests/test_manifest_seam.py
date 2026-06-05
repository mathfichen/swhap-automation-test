"""Integration seam: validator manifest loader vs the fixtures producer shape.

The fixtures slice publishes ``fixtures/wildlife/manifests/*.json`` in the frozen
``swhap-tree-manifest/1`` shape (entry blob field named ``git_blob_sha1``,
archive digest named ``tarball_sha256``). The validator's ``manifest.from_dict``
is the consumer/oracle loader. This test loads the real published manifests
through that loader and asserts they parse into the validator's ``Manifest`` with
entry counts matching the manifest's own ``counts`` block — proving the W2
fixtures->validator manifest seam.
"""
from __future__ import annotations

import json
import os

import pytest

from swhap_validate import manifest as M


def _repo_root() -> str | None:
    d = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.isdir(os.path.join(d, "fixtures", "wildlife", "manifests")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


_ROOT = _repo_root()
_RELEASES = ["0.90", "0.91", "1.0", "1.02"]


@pytest.mark.skipif(_ROOT is None, reason="fixtures/wildlife/manifests not present")
@pytest.mark.parametrize("release", _RELEASES)
def test_loads_published_manifest(release):
    path = os.path.join(_ROOT, "fixtures", "wildlife", "manifests", f"{release}.json")
    if not os.path.isfile(path):
        pytest.skip(f"manifest {release}.json absent")
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    assert doc["schema"] == "swhap-tree-manifest/1"

    man = M.load_manifest(path)
    # entry count round-trips against the manifest's own census
    assert len(man.entries) == doc["counts"]["entries"]
    # tarball_sha256 maps onto Manifest.sha256
    assert man.sha256 == doc["tarball_sha256"]
    # git_blob_sha1 maps onto Entry.blob (40-hex git object id)
    for entry in man.entries.values():
        assert len(entry.blob) == 40
        assert entry.type in ("file", "symlink")
