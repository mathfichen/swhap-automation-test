"""Integration: inspect the real Wild_LIFE tarballs (consumed read-only)."""

from __future__ import annotations

import json
import os

import pytest

from swhap_core.inspect import inspect_archive


def _inspect(wildlife_dir, name):
    return inspect_archive(os.path.join(wildlife_dir, name))


@pytest.mark.parametrize(
    "name,wrapper,members",
    [
        ("life_090.tgz", "Life/", 1146),
        ("life_091.tgz", "Life/", 1156),
        ("life_10.tgz", "Life1.0/", 1518),
    ],
)
def test_classic_tarballs_inspect_cleanly(wildlife_dir, name, wrapper, members):
    r = _inspect(wildlife_dir, name)
    assert r["accepted"] is True, r["rejections"]
    assert r["rejections"] == []
    assert r["wrapper"]["detected"] is True
    assert r["wrapper"]["name"] == wrapper
    assert r["summary"]["members"] == members
    assert r["exit_code"] == 0


def test_life10_reports_empty_dirs_and_inroot_symlinks(wildlife_dir):
    r = _inspect(wildlife_dir, "life_10.tgz")
    # 4 empty dirs preserved as .emptydir at extraction time
    assert set(r["empty_dirs"]) == {
        "Life1.0/Tests/OUT",
        "Life1.0/Tests/ERR",
        "Life1.0/Tests/REFDIFF",
        "Life1.0/Tests/ERRDIFF",
    }
    # 4 in-root relative symlinks, none escaping
    assert r["summary"]["symlinks"] == 4
    assert all(not s["escapes_root"] for s in r["symlinks"])


def test_life090_no_symlinks_no_empties(wildlife_dir):
    r = _inspect(wildlife_dir, "life_090.tgz")
    assert r["summary"]["symlinks"] == 0
    assert r["empty_dirs"] == []
    assert r["compression"] == "gzip"
    assert r["format"] == "tar"


def test_life102ultrix_quarantine_census(wildlife_dir):
    # The PR #1 author-supplied tarball is the messy one: AppleDouble '._' top
    # level (so no clean wrapper) + symlinks with absolute targets escaping
    # root. It must still produce a full report (the quarantined census use),
    # and must be correctly REJECTED rather than silently accepted.
    r = _inspect(wildlife_dir, "Life1.02Ultrix.tar")
    assert r["accepted"] is False
    codes = {x["code"] for x in r["rejections"]}
    assert "EX-SYMLINK-ESCAPE" in codes
    assert r["summary"]["symlinks"] == 69
    assert r["wrapper"]["detected"] is False  # two top-level entries
    # report is still well-formed JSON, byte-safe, no host paths
    blob = json.dumps(r)
    assert "/home/dicosmo" not in blob


def test_wildlife_sha256_matches_manifest(wildlife_dir):
    # the report's content-address must match the pinned manifest
    manifest = {}
    mpath = os.path.join(os.path.dirname(wildlife_dir), "tarballs.sha256")
    with open(mpath) as fh:
        for line in fh:
            h, n = line.split()
            manifest[n] = h
    for name in ("life_090.tgz", "life_10.tgz"):
        r = _inspect(wildlife_dir, name)
        assert r["sha256"] == manifest[name]
