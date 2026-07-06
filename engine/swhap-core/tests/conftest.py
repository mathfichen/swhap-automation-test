"""Test fixtures for the inspect slice.

Negative/positive archive corpus: built **inline** as deterministic
``tarfile``/``zipfile`` byte streams (no committed binaries) — the same
discipline core-pipeline.md §6.2 mandates for ``fixtures/negative/``. Once the
shared ``fixtures/negative/`` corpus (T1) lands, these builders move there and
the tests consume it; until then they are self-contained so the suite runs.

Wild_LIFE tarballs are consumed read-only from the validator workstream's
checksummed acquisition (``fixtures/wildlife/tarballs/``); never re-acquired.
"""

from __future__ import annotations

import io
import os
import tarfile
import zipfile

import pytest

# ---------------------------------------------------------------------------
# Wild_LIFE fixture location (consumed, never written)
# ---------------------------------------------------------------------------
# Precedence: explicit override, then the CLONE-RELATIVE path (so a clean clone
# is genuinely self-isolated and never silently consumes another checkout's
# tarballs). No hardcoded absolute dev path — it shadowed the clone-relative one
# and broke clean-clone isolation on the dev machine.
_WILDLIFE_CANDIDATES = [
    os.environ.get("SWHAP_WILDLIFE_DIR"),
    os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "wildlife", "tarballs"),
]


def _wildlife_dir() -> str | None:
    for c in _WILDLIFE_CANDIDATES:
        if c and os.path.isdir(c):
            return os.path.abspath(c)
    return None


@pytest.fixture(scope="session")
def wildlife_dir() -> str:
    d = _wildlife_dir()
    if d is None:
        pytest.skip("Wild_LIFE fixtures not found (run fixtures/wildlife/acquire.sh)")
    return d


# ---------------------------------------------------------------------------
# inline tar/zip builders
# ---------------------------------------------------------------------------
def _tar_bytes(build, compression: str = "") -> bytes:
    buf = io.BytesIO()
    mode = "w:" + compression if compression else "w"
    with tarfile.open(fileobj=buf, mode=mode, format=tarfile.GNU_FORMAT) as tf:
        build(tf)
    return buf.getvalue()


def _add_file(tf: tarfile.TarFile, name: str, data: bytes = b"x", *, mode: int = 0o644) -> None:
    ti = tarfile.TarInfo(name)
    ti.size = len(data)
    ti.mode = mode
    tf.addfile(ti, io.BytesIO(data))


def _add_dir(tf: tarfile.TarFile, name: str) -> None:
    ti = tarfile.TarInfo(name.rstrip("/"))
    ti.type = tarfile.DIRTYPE
    ti.mode = 0o755
    tf.addfile(ti)


def _add_symlink(tf: tarfile.TarFile, name: str, target: str) -> None:
    ti = tarfile.TarInfo(name)
    ti.type = tarfile.SYMTYPE
    ti.linkname = target
    tf.addfile(ti)


def _add_hardlink(tf: tarfile.TarFile, name: str, target: str) -> None:
    ti = tarfile.TarInfo(name)
    ti.type = tarfile.LNKTYPE
    ti.linkname = target
    tf.addfile(ti)


def _add_special(tf: tarfile.TarFile, name: str, typeflag: bytes) -> None:
    ti = tarfile.TarInfo(name)
    ti.type = typeflag
    tf.addfile(ti)


def _write(tmp, name: str, data: bytes) -> str:
    p = os.path.join(str(tmp), name)
    with open(p, "wb") as fh:
        fh.write(data)
    return p


# A registry of negative/positive corpus builders. Each returns archive bytes.
def neg_traversal_dotdot() -> bytes:
    def b(tf):
        _add_file(tf, "good/ok.txt")
        _add_file(tf, "../evil.txt")
    return _tar_bytes(b)


def neg_absolute_path() -> bytes:
    def b(tf):
        _add_file(tf, "/etc/passwd")
    return _tar_bytes(b)


def neg_symlink_escape() -> bytes:
    def b(tf):
        _add_dir(tf, "pkg")
        _add_symlink(tf, "pkg/link", "/tmp/secret")
    return _tar_bytes(b)


def neg_symlink_rel_escape() -> bytes:
    def b(tf):
        _add_dir(tf, "pkg")
        _add_symlink(tf, "pkg/link", "../../outside")
    return _tar_bytes(b)


def neg_hardlink_outside() -> bytes:
    def b(tf):
        _add_file(tf, "pkg/a.txt")
        _add_hardlink(tf, "pkg/b.txt", "pkg/nonexistent.txt")
    return _tar_bytes(b)


def neg_device_fifo() -> bytes:
    def b(tf):
        _add_file(tf, "pkg/ok.txt")
        _add_special(tf, "pkg/pipe", tarfile.FIFOTYPE)
    return _tar_bytes(b)


def neg_device_char() -> bytes:
    def b(tf):
        ti = tarfile.TarInfo("pkg/null")
        ti.type = tarfile.CHRTYPE
        ti.devmajor = 1
        ti.devminor = 3
        tf.addfile(ti)
    return _tar_bytes(b)


def neg_duplicate_member() -> bytes:
    def b(tf):
        _add_file(tf, "pkg/dup.txt", b"first")
        _add_file(tf, "pkg/dup.txt", b"second-different-content")
    return _tar_bytes(b)


def neg_case_collision() -> bytes:
    def b(tf):
        _add_file(tf, "pkg/README")
        _add_file(tf, "pkg/readme")
    return _tar_bytes(b)


def neg_long_path() -> bytes:
    # one component longer than the 4000-byte path budget
    long_name = "pkg/" + ("a" * 4100)
    def b(tf):
        _add_file(tf, long_name)
    return _tar_bytes(b)


def neg_deep_tree() -> bytes:
    deep = "/".join("d%d" % i for i in range(70)) + "/leaf.txt"
    def b(tf):
        _add_file(tf, deep)
    return _tar_bytes(b)


def neg_bomb_ratio() -> bytes:
    # 12 MiB of zeros gzips to a few KiB -> ratio well over 200, tiny on disk.
    big = b"\x00" * (12 * 1024 * 1024)
    def b(tf):
        _add_file(tf, "pkg/zeros.bin", big)
    return _tar_bytes(b, compression="gz")


def neg_bomb_members() -> bytes:
    # 50 tiny members; tested against a policy with max_members=10.
    def b(tf):
        for i in range(50):
            _add_file(tf, "pkg/f%03d.txt" % i)
    return _tar_bytes(b)


def neg_zip_central_dir_mismatch() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("pkg/a.txt", "hello")
    data = bytearray(buf.getvalue())
    # corrupt the central-directory file-header signature (PK\x01\x02) so the
    # central directory no longer matches its End-Of-Central-Directory record.
    cdh = data.find(b"PK\x01\x02")
    assert cdh != -1
    data[cdh + 1] = 0x00  # break the 'K' of the magic -> BadZipFile
    return bytes(data)


def pos_dotfiles() -> bytes:
    # dt2sg glob-loss class: dotfiles must survive (crit-M3)
    def b(tf):
        _add_dir(tf, "pkg")
        _add_file(tf, "pkg/.config")
        _add_file(tf, "pkg/.hidden/secret")
        _add_file(tf, "pkg/visible.txt")
    return _tar_bytes(b)


def pos_symlinks() -> bytes:
    # life_10 analog: in-root relative symlinks, must NOT be flagged
    def b(tf):
        _add_dir(tf, "pkg")
        _add_dir(tf, "pkg/Source")
        _add_dir(tf, "pkg/Examples")
        _add_file(tf, "pkg/Examples/e.txt")
        _add_symlink(tf, "pkg/Source/Examples", "../Examples")
    return _tar_bytes(b, compression="gz")


def pos_latin1_names() -> bytes:
    # a non-UTF-8 (latin-1) member name; bytes must be preserved/reported
    raw = "pkg/Caf".encode("utf-8") + b"\xe9" + " mode.txt".encode("utf-8")
    def b(tf):
        ti = tarfile.TarInfo(raw.decode("utf-8", "surrogateescape"))
        ti.size = 1
        tf.addfile(ti, io.BytesIO(b"x"))
    return _tar_bytes(b)


def pos_emptydirs_nested() -> bytes:
    def b(tf):
        _add_dir(tf, "pkg")
        _add_dir(tf, "pkg/full")
        _add_file(tf, "pkg/full/a.txt")
        _add_dir(tf, "pkg/empty")
        _add_dir(tf, "pkg/empty/alsoempty")
    return _tar_bytes(b)


def pos_wrapper_single() -> bytes:
    def b(tf):
        _add_dir(tf, "Wrap1.0")
        _add_file(tf, "Wrap1.0/a.txt")
        _add_file(tf, "Wrap1.0/sub/b.txt")
    return _tar_bytes(b)


def pos_wrapper_plus_stray() -> bytes:
    def b(tf):
        _add_dir(tf, "Wrap1.0")
        _add_file(tf, "Wrap1.0/a.txt")
        _add_file(tf, "stray.txt")
    return _tar_bytes(b)


def pos_two_dirs_no_wrapper() -> bytes:
    def b(tf):
        _add_file(tf, "dirA/a.txt")
        _add_file(tf, "dirB/b.txt")
    return _tar_bytes(b)


def pos_hardlink_inside() -> bytes:
    def b(tf):
        _add_file(tf, "pkg/a.txt", b"content")
        _add_hardlink(tf, "pkg/b.txt", "pkg/a.txt")
    return _tar_bytes(b)


NEGATIVE = {
    "neg-traversal-dotdot.tar": neg_traversal_dotdot,
    "neg-absolute-path.tar": neg_absolute_path,
    "neg-symlink-escape.tar": neg_symlink_escape,
    "neg-symlink-rel-escape.tar": neg_symlink_rel_escape,
    "neg-hardlink-outside.tar": neg_hardlink_outside,
    "neg-device-fifo.tar": neg_device_fifo,
    "neg-device-char.tar": neg_device_char,
    "neg-duplicate-member.tar": neg_duplicate_member,
    "neg-case-collision.tar": neg_case_collision,
    "neg-long-path.tar": neg_long_path,
    "neg-deep-tree.tar": neg_deep_tree,
    "neg-bomb-ratio.tgz": neg_bomb_ratio,
    "neg-bomb-members.tar": neg_bomb_members,
    "neg-zip-central-dir-mismatch.zip": neg_zip_central_dir_mismatch,
}

POSITIVE = {
    "pos-dotfiles.tar": pos_dotfiles,
    "pos-symlinks.tgz": pos_symlinks,
    "pos-latin1-names.tar": pos_latin1_names,
    "pos-emptydirs-nested.tar": pos_emptydirs_nested,
    "pos-wrapper-single.tar": pos_wrapper_single,
    "pos-wrapper-plus-stray.tar": pos_wrapper_plus_stray,
    "pos-two-dirs-no-wrapper.tar": pos_two_dirs_no_wrapper,
    "pos-hardlink-inside.tar": pos_hardlink_inside,
}


@pytest.fixture
def corpus(tmp_path):
    """Materialize the full inline corpus into tmp_path; return name->path."""
    paths = {}
    for name, builder in {**NEGATIVE, **POSITIVE}.items():
        paths[name] = _write(tmp_path, name, builder())
    return paths
