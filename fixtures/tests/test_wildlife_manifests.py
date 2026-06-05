"""Self-tests for the Wild_LIFE ground-truth tree manifests.

Covers: schema validity, the followup-2 count cross-check (1139 / 1152 /
1496+4+4), deterministic regeneration (committed JSON == fresh render), the
1.02 quarantine census + anomaly register, and a git_blob_sha1 spot-check
against real `git hash-object` (skipped if git is unavailable).
"""
import json
import os
import re
import shutil
import subprocess
import tarfile

import pytest

import corpus_helpers as conftest

MANIFESTS = os.path.join(conftest.WILD, "manifests")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")

# followup-2.md ground truth (the cross-check oracle).
EXPECTED = {
    "0.90": {"files": 1139, "symlinks": 0, "empty_dirs": 0, "wrapper": "Life/", "tarball": "life_090.tgz"},
    "0.91": {"files": 1152, "symlinks": 0, "empty_dirs": 0, "wrapper": "Life/", "tarball": "life_091.tgz"},
    "1.0":  {"files": 1496, "symlinks": 4, "empty_dirs": 4, "wrapper": "Life1.0/", "tarball": "life_10.tgz"},
}


def _load(release):
    with open(os.path.join(MANIFESTS, f"{release}.json"), encoding="utf-8") as fh:
        return json.load(fh)


@pytest.mark.parametrize("release", ["0.90", "0.91", "1.0", "1.02"])
def test_schema_valid(release):
    d = _load(release)
    for key in ("schema", "release", "tarball", "tarball_sha256", "wrapper",
                "quarantined", "counts", "empty_dirs", "symlinks", "entries", "generator"):
        assert key in d, f"{release} missing top-level key {key}"
    assert d["schema"] == "swhap-tree-manifest/1"
    assert d["release"] == release
    assert HEX64.match(d["tarball_sha256"])
    c = d["counts"]
    assert c["entries"] == c["files"] + c["symlinks"]
    assert len(d["entries"]) == c["entries"]
    # entries well-formed and byte-sorted
    prev = b""
    files = syms = 0
    for e in d["entries"]:
        assert e["type"] in ("file", "symlink")
        assert e["mode"] in ("100644", "100755", "120000")
        assert HEX64.match(e["sha256"])
        assert HEX40.match(e["git_blob_sha1"])
        if e["type"] == "symlink":
            assert e["mode"] == "120000" and "target" in e
            syms += 1
        else:
            assert e["mode"] in ("100644", "100755")
            files += 1
        cur = e["path"].encode("utf-8", "surrogateescape")
        assert cur >= prev, f"{release} entries not byte-sorted at {e['path']!r}"
        prev = cur
    assert files == c["files"] and syms == c["symlinks"]


@pytest.mark.parametrize("release", ["0.90", "0.91", "1.0"])
def test_counts_cross_check_followup2(release):
    d = _load(release)
    exp = EXPECTED[release]
    assert d["wrapper"] == exp["wrapper"]
    assert d["tarball"] == exp["tarball"]
    assert d["counts"]["files"] == exp["files"]
    assert d["counts"]["symlinks"] == exp["symlinks"]
    assert d["counts"]["empty_dirs"] == exp["empty_dirs"]
    assert d["quarantined"] is False


def test_tarball_sha256_matches_pinned_manifest():
    pinned = {}
    with open(os.path.join(conftest.WILD, "tarballs.sha256")) as fh:
        for ln in fh:
            sha, fn = ln.split()
            pinned[fn] = sha
    for release in ("0.90", "0.91", "1.0", "1.02"):
        d = _load(release)
        assert d["tarball_sha256"] == pinned[d["tarball"]]


def test_v10_symlinks_and_emptydirs_exact():
    d = _load("1.0")
    assert d["empty_dirs"] == ["Tests/ERR", "Tests/ERRDIFF", "Tests/OUT", "Tests/REFDIFF"]
    targets = {s["path"]: s["target"] for s in d["symlinks"]}
    assert targets == {
        "Source/Examples": "../Examples",
        "Source/Tools": "../Tools",
        "Source/Lib": "../Lib",
        "CLife/c_life.doc": "../Doc/c_life.doc",
    }


@pytest.mark.parametrize("release", ["0.90", "0.91", "1.0"])
def test_deterministic_regeneration(release):
    """Committed JSON == a fresh in-memory render (byte determinism)."""
    mk = conftest.load_mk_manifest()
    doc = mk.build_clean(release)
    rendered = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    on_disk = open(os.path.join(MANIFESTS, f"{release}.json"), encoding="utf-8").read()
    assert rendered == on_disk, f"{release}.json is not a byte-stable render"


def test_1_02_quarantine_and_anomalies():
    d = _load("1.02")
    assert d["quarantined"] is True
    assert d["wrapper"] == "Life1.02Ultrix/"
    assert "anomalies" in d and d["anomalies"]
    classes = {a["class"] for a in d["anomalies"]}
    # the crit-M6 anomalies the census must surface
    for required in ("macos-appledouble", "stray-top-level", "symlink-escape-absolute", "perm-bits"):
        assert required in classes, f"1.02 anomaly register missing {required}"
    # absolute-escape symlinks enumerated
    abs_esc = [a for a in d["anomalies"] if a["class"] == "symlink-escape-absolute"][0]
    assert len(abs_esc["members"]) == 4
    for m in abs_esc["members"]:
        assert m["target"].startswith("/")


def test_1_02_date_evidence_note_present():
    note = os.path.join(MANIFESTS, "1.02-date-evidence.md")
    assert os.path.exists(note)
    text = open(note, encoding="utf-8").read()
    assert "1994" in text and "year-only" in text


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_git_blob_sha1_matches_real_git():
    """Spot-check: manifest git_blob_sha1 == `git hash-object` for sample paths
    from the byte-perfect v0.90 tarball (followup-2 §1)."""
    d = _load("0.90")
    wrapper = d["wrapper"]
    checked = 0
    with tarfile.open(os.path.join(conftest.WILD, "tarballs", d["tarball"]), "r:*") as t:
        by_path = {e["path"]: e for e in d["entries"]}
        for m in t.getmembers():
            if not m.isreg():
                continue
            spath = m.name[len(wrapper):] if m.name.startswith(wrapper) else m.name
            if spath not in by_path:
                continue
            data = t.extractfile(m).read()
            got = subprocess.run(["git", "hash-object", "--stdin"], input=data,
                                 capture_output=True).stdout.decode().strip()
            assert got == by_path[spath]["git_blob_sha1"], spath
            assert got == by_path[spath]["git_blob_sha1"]
            checked += 1
            if checked >= 25:
                break
    assert checked >= 25
