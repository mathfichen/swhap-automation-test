"""Self-tests for the negative/positive archive fixture corpus.

Covers: deterministic rebuild (sha256 stable, byte-identical twice),
MANIFEST/index consistency, full crit-M6/crit-M3 class coverage, and that each
archive actually exhibits the single property it claims to isolate.
"""
import hashlib
import json
import os
import tarfile

import corpus_helpers as conftest


def _sums(dest):
    return {fn: hashlib.sha256(open(os.path.join(dest, fn), "rb").read()).hexdigest()
            for fn in os.listdir(dest)}


def _pinned():
    out = {}
    with open(os.path.join(conftest.NEG, "MANIFEST.sha256")) as fh:
        for ln in fh:
            sha, fn = ln.split()
            out[fn] = sha
    return out


def test_rebuild_matches_manifest(tmp_path):
    build = conftest.load_build()
    got = build.build_all(str(tmp_path))
    pinned = _pinned()
    assert got == pinned, "rebuilt fixtures drift from the pinned MANIFEST"


def test_rebuild_byte_identical(tmp_path):
    build = conftest.load_build()
    a, b = tmp_path / "a", tmp_path / "b"
    s1 = build.build_all(str(a))
    s2 = build.build_all(str(b))
    assert s1 == s2
    for fn in s1:
        assert open(a / fn, "rb").read() == open(b / fn, "rb").read()


def test_check_command_passes():
    build = conftest.load_build()
    assert build.cmd_check() == 0


def test_committed_archives_match_manifest():
    pinned = _pinned()
    arch = os.path.join(conftest.NEG, "archives")
    got = _sums(arch)
    assert got == pinned


def test_index_consistent_with_manifest_and_fixtures():
    build = conftest.load_build()
    pinned = _pinned()
    idx = json.load(open(os.path.join(conftest.NEG, "index.json")))
    by_file = {f["file"]: f for f in idx["fixtures"]}
    assert set(by_file) == set(pinned)
    for name, fn, _b, isolates, disp, code, crit, note in build.FIXTURES:
        rec = by_file[fn]
        assert rec["sha256"] == pinned[fn]
        assert rec["disposition"] == disp
        assert rec["expected_code"] == code
        assert rec["isolates"] == isolates


def test_all_defect_classes_present():
    build = conftest.load_build()
    names = {n for n, *_ in build.FIXTURES}
    required = {
        "neg-traversal-dotdot", "neg-absolute-path", "neg-symlink-escape",
        "neg-hardlink-outside", "neg-device-fifo", "neg-duplicate-member",
        "neg-case-collision", "neg-non-utf8-name", "neg-bomb-ratio",
        "pos-bom-crlf", "pos-dotfile-root", "pos-wrapper-dir",
        "pos-emptydir", "pos-pre1970-mtime",
    }
    missing = required - names
    assert not missing, f"missing defect-class fixtures: {sorted(missing)}"


# --- per-fixture property assertions (read-only) ------------------------- #

def _members(fn):
    with tarfile.open(os.path.join(conftest.NEG, "archives", fn), "r:*") as t:
        return t.getmembers()


def test_traversal_has_dotdot():
    assert any(".." in m.name.split("/") for m in _members("neg-traversal-dotdot.tar"))


def test_absolute_path_is_absolute():
    assert any(m.name.startswith("/") for m in _members("neg-absolute-path.tar"))


def test_symlink_escapes():
    m = _members("neg-symlink-escape.tar")[0]
    assert m.issym() and m.linkname.startswith("/")
    m = _members("neg-symlink-rel-escape.tar")[0]
    assert m.issym() and m.linkname.startswith("../")


def test_hardlink_target_outside():
    m = _members("neg-hardlink-outside.tar")[0]
    members = {x.name for x in _members("neg-hardlink-outside.tar")}
    assert m.islnk() and m.linkname not in members


def test_device_is_special():
    assert _members("neg-device-fifo.tar")[0].isfifo()


def test_duplicate_member_same_path_diff_content():
    ms = _members("neg-duplicate-member.tar")
    assert len(ms) == 2 and ms[0].name == ms[1].name


def test_case_collision_pair():
    names = sorted(m.name for m in _members("neg-case-collision.tar"))
    assert names == ["README", "readme"]
    assert names[0].casefold() == names[1].casefold()


def test_non_utf8_name_bytes():
    m = _members("neg-non-utf8-name.tar")[0]
    raw = m.name.encode("utf-8", "surrogateescape")
    assert b"\xe9" in raw
    try:
        m.name.encode("utf-8")
        assert False, "name unexpectedly valid UTF-8"
    except UnicodeEncodeError:
        pass


def test_bomb_ratio_exceeds_budget():
    fn = os.path.join(conftest.NEG, "archives", "neg-bomb-ratio.tgz")
    comp = os.path.getsize(fn)
    with tarfile.open(fn, "r:gz") as t:
        unc = t.getmembers()[0].size
    assert unc / comp > 200  # default 1:200 ratio budget (core §4.1)


def test_bom_crlf_preserved():
    fn = os.path.join(conftest.NEG, "archives", "pos-bom-crlf.tar")
    with tarfile.open(fn) as t:
        data = t.extractfile(t.getmembers()[0]).read()
    assert data.startswith(b"\xef\xbb\xbf") and b"\r\n" in data


def test_dotfile_at_root():
    names = {m.name for m in _members("pos-dotfile-root.tar")}
    assert ".hidden" in names


def test_wrapper_single_top():
    tops = {m.name.split("/", 1)[0] for m in _members("pos-wrapper-dir.tar")}
    assert tops == {"Wrapper"}


def test_emptydir_has_no_children():
    ms = _members("pos-emptydir.tar")
    files = [m.name for m in ms if m.isreg()]
    dirs = [m.name for m in ms if m.isdir()]
    assert "empty" in dirs
    assert not any(f.startswith("empty/") for f in files)


def test_pre1970_negative_epoch():
    m = _members("pos-pre1970-mtime.tar")[0]
    assert m.mtime < 0
