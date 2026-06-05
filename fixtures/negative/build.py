#!/usr/bin/env python3
"""Deterministic generator for the SWHAP negative/positive archive fixture corpus.

Workstream: core-pipeline T1 (M1a).  Each fixture is a *small* archive that
isolates exactly ONE crit-M6 / crit-M3 defect (or one positive property the
hardened extractor must handle without losing bytes).  The corpus is shipped as
**builder scripts + a pinned sha256 MANIFEST**, never as committed binaries
(core-pipeline.md §6.2): the validator workstream mounts it as its
``fixtures/negative/`` admission-test set, and core runs it as the M2-entry
hardening battery.

Determinism law (so the MANIFEST is stable across machines/runs):

* Every tar member's mtime is set explicitly — **no wall-clock**.  uid/gid = 0,
  uname/gname = "".  Members are emitted in a fixed order.
* GNU tar format throughout (one format → one byte layout; it also represents
  the pre-1970 negative mtime via base-256 and raw non-UTF-8 name bytes without
  a PAX extended header).
* gzip members are produced with ``gzip.compress(..., mtime=0)`` (no embedded
  filename, fixed OS byte) so the ``.tgz`` bytes are reproducible.

Run ``python build.py`` to (re)materialize ``archives/`` + ``MANIFEST.sha256``
+ ``index.json``.  ``python build.py --check`` rebuilds into a temp dir and
verifies the bytes match the committed MANIFEST (the CI reproducibility gate).
"""
from __future__ import annotations

import argparse
import calendar
import gzip
import hashlib
import io
import json
import os
import sys
import tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVES = os.path.join(HERE, "archives")
MANIFEST = os.path.join(HERE, "MANIFEST.sha256")
INDEX = os.path.join(HERE, "index.json")

# Fixed timestamps (deterministic; never the wall clock).
MTIME = calendar.timegm((1990, 1, 1, 0, 0, 0))            # 631152000, positive
PRE1970 = calendar.timegm((1968, 1, 1, 0, 0, 0))          # negative epoch (crit-M3)


def _ti(name, *, type=tarfile.REGTYPE, mode=0o644, size=0,
        linkname="", mtime=MTIME, devmajor=0, devminor=0):
    ti = tarfile.TarInfo(name)
    ti.type = type
    ti.mode = mode
    ti.size = size
    ti.mtime = mtime
    ti.uid = ti.gid = 0
    ti.uname = ti.gname = ""
    ti.linkname = linkname
    ti.devmajor = devmajor
    ti.devminor = devminor
    return ti


def _tar(members) -> bytes:
    """Serialize (TarInfo, payload-bytes-or-None) pairs to GNU-tar bytes."""
    buf = io.BytesIO()
    # encoding/errors fixed so non-UTF-8 names round-trip as raw bytes.
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.GNU_FORMAT,
                      encoding="utf-8", errors="surrogateescape") as t:
        for ti, data in members:
            if data is not None:
                ti.size = len(data)
                t.addfile(ti, io.BytesIO(data))
            else:
                t.addfile(ti)
    return buf.getvalue()


def _gz(data: bytes) -> bytes:
    return gzip.compress(data, compresslevel=9, mtime=0)


# --------------------------------------------------------------------------- #
# Fixture builders — one isolated property each.                              #
# --------------------------------------------------------------------------- #

def neg_traversal_dotdot():
    return _tar([(_ti("../evil.txt", size=5), b"pwned")])


def neg_absolute_path():
    return _tar([(_ti("/etc/evil.txt", size=5), b"pwned")])


def neg_symlink_escape():
    # A single symlink whose absolute target escapes the extraction root.
    return _tar([(_ti("pwn", type=tarfile.SYMTYPE, mode=0o777,
                      linkname="/etc/passwd"), None)])


def neg_symlink_rel_escape():
    return _tar([(_ti("pwn", type=tarfile.SYMTYPE, mode=0o777,
                      linkname="../../../../etc/passwd"), None)])


def neg_hardlink_outside():
    # Hardlink whose target is NOT a member of the archive.
    return _tar([(_ti("hl", type=tarfile.LNKTYPE, linkname="outside/secret"), None)])


def neg_device_fifo():
    # A FIFO special member (no real device node needed — header only).
    return _tar([(_ti("dev/whoops", type=tarfile.FIFOTYPE, mode=0o644), None)])


def neg_duplicate_member():
    # Same path twice, different content (ambiguous tree).
    return _tar([
        (_ti("dup.txt", size=1), b"A"),
        (_ti("dup.txt", size=1), b"B"),
    ])


def neg_case_collision():
    # casefold-equal distinct paths — silent merge on case-insensitive FS.
    return _tar([
        (_ti("README", size=2), b"R\n"),
        (_ti("readme", size=2), b"r\n"),
    ])


def neg_non_utf8_name():
    # Member name with a raw latin-1 byte 0xe9 (not valid UTF-8).
    raw = b"caf\xe9.txt"
    name = raw.decode("utf-8", "surrogateescape")  # carries a lone surrogate
    return _tar([(_ti(name, size=4), b"data")])


def neg_bomb_ratio():
    # 16 MiB of zeros → gzip ratio well past the 1:200 budget; one member only,
    # so ONLY the ratio budget is what trips (single-file/total/members all ok).
    return _gz(_tar([(_ti("zeros.bin", size=16 << 20), b"\x00" * (16 << 20))]))


def pos_bom_crlf():
    # Positive: a text file with a UTF-8 BOM and CRLF line endings.  The
    # extractor MUST preserve these bytes verbatim (no normalization).
    body = b"\xef\xbb\xbfline one\r\nline two\r\n"
    return _tar([(_ti("notes.txt", size=len(body)), body)])


def pos_dotfile_root():
    # Positive: a dotfile at the archive root (dt2sg `git rm -rf *` glob-loss
    # class, crit-M3) — must be preserved, not dropped.
    return _tar([
        (_ti(".hidden", size=7), b"secret\n"),
        (_ti("visible.txt", size=3), b"ok\n"),
    ])


def pos_wrapper_dir():
    # Positive: a single artificial top-level wrapper directory to be stripped.
    return _tar([
        (_ti("Wrapper/", type=tarfile.DIRTYPE, mode=0o755), None),
        (_ti("Wrapper/main.c", size=4), b"int\n"),
        (_ti("Wrapper/README", size=3), b"hi\n"),
    ])


def pos_emptydir():
    # Positive: an empty directory that must round-trip via a .emptydir marker.
    return _tar([
        (_ti("keep/", type=tarfile.DIRTYPE, mode=0o755), None),
        (_ti("empty/", type=tarfile.DIRTYPE, mode=0o755), None),
        (_ti("keep/file.txt", size=3), b"x\n\n"[:3]),
    ])


def pos_pre1970_mtime():
    # Positive: a member with a pre-epoch (1968) mtime — crit-M3 negative-epoch
    # class; must build (raw @<epoch> git author date), never crash.
    return _tar([(_ti("ancient.txt", size=4, mtime=PRE1970), b"old\n")])


# (name, filename, builder, isolates, disposition, crit, note)
FIXTURES = [
    ("neg-traversal-dotdot", "neg-traversal-dotdot.tar", neg_traversal_dotdot,
     "path traversal via a '..' component", "REJECT", "EX-TRAVERSAL", "crit-M6",
     "member path '../evil.txt' would write outside the extraction root"),
    ("neg-absolute-path", "neg-absolute-path.tar", neg_absolute_path,
     "absolute member path", "REJECT", "EX-ABS", "crit-M6",
     "member path '/etc/evil.txt' is absolute"),
    ("neg-symlink-escape", "neg-symlink-escape.tar", neg_symlink_escape,
     "symlink with absolute target escaping the root", "REJECT", "EX-SYMLINK-ESCAPE",
     "crit-M6", "symlink 'pwn' -> '/etc/passwd'"),
    ("neg-symlink-rel-escape", "neg-symlink-rel-escape.tar", neg_symlink_rel_escape,
     "symlink whose relative target escapes the root", "REJECT", "EX-SYMLINK-ESCAPE",
     "crit-M6", "symlink 'pwn' -> '../../../../etc/passwd'"),
    ("neg-hardlink-outside", "neg-hardlink-outside.tar", neg_hardlink_outside,
     "hardlink whose target is outside the member set", "REJECT", "EX-HARDLINK-OUT",
     "crit-M6", "hardlink 'hl' -> 'outside/secret' (not an archive member)"),
    ("neg-device-fifo", "neg-device-fifo.tar", neg_device_fifo,
     "device / special (FIFO) member", "REJECT", "EX-DEVICE", "crit-M6",
     "FIFO member 'dev/whoops'"),
    ("neg-duplicate-member", "neg-duplicate-member.tar", neg_duplicate_member,
     "duplicate member path with differing content", "REJECT", "EX-DUP", "crit-M6",
     "'dup.txt' appears twice (content 'A' then 'B')"),
    ("neg-case-collision", "neg-case-collision.tar", neg_case_collision,
     "casefold-equal distinct paths", "REJECT", "EX-CASE-COLLISION", "crit-M6",
     "'README' and 'readme' collide on a case-insensitive filesystem"),
    ("neg-non-utf8-name", "neg-non-utf8-name.tar", neg_non_utf8_name,
     "non-UTF-8 filename bytes", "ACCEPT", "(byte-preserved)", "crit-M6",
     "member name b'caf\\xe9.txt' (latin-1); bytes reach the git tree unchanged, "
     "encoding recorded in the journal (core §4.1.4)"),
    ("neg-bomb-ratio", "neg-bomb-ratio.tgz", neg_bomb_ratio,
     "decompression-bomb compression ratio", "REJECT", "BG-RATIO", "crit-M6",
     "16 MiB of zeros compresses past the 1:200 ratio budget; only the ratio trips"),
    ("pos-bom-crlf", "pos-bom-crlf.tar", pos_bom_crlf,
     "BOM + CRLF text byte-preservation", "ACCEPT", "(byte-preserved)", "crit-M6",
     "UTF-8 BOM and CRLF line endings must survive verbatim"),
    ("pos-dotfile-root", "pos-dotfile-root.tar", pos_dotfile_root,
     "dotfile at archive root", "ACCEPT", "(preserved)", "crit-M3",
     "'.hidden' at root must not be dropped (dt2sg glob-loss class)"),
    ("pos-wrapper-dir", "pos-wrapper-dir.tar", pos_wrapper_dir,
     "single artificial wrapper directory", "ACCEPT", "(wrapper-stripped)", "crit-M6",
     "'Wrapper/' is stripped; 'main.c'/'README' surface at the root"),
    ("pos-emptydir", "pos-emptydir.tar", pos_emptydir,
     "empty directory needing a .emptydir marker", "ACCEPT", "(.emptydir)", "crit-M6",
     "'empty/' has no children; preserved via a .emptydir marker"),
    ("pos-pre1970-mtime", "pos-pre1970-mtime.tar", pos_pre1970_mtime,
     "pre-1970 (negative-epoch) mtime", "ACCEPT", "(negative epoch)", "crit-M3",
     "member mtime 1968-01-01; must build via raw @<epoch> author date"),
]


def build_all(dest: str) -> "dict[str, str]":
    os.makedirs(dest, exist_ok=True)
    sums = {}
    for name, fn, builder, *_ in FIXTURES:
        data = builder()
        with open(os.path.join(dest, fn), "wb") as fh:
            fh.write(data)
        sums[fn] = hashlib.sha256(data).hexdigest()
    return sums


def write_manifest(sums: "dict[str, str]") -> None:
    lines = [f"{sums[fn]}  {fn}\n" for _, fn, *_ in FIXTURES]
    with open(MANIFEST, "w", encoding="utf-8") as fh:
        fh.writelines(lines)


def write_index(sums: "dict[str, str]") -> None:
    doc = {
        "schema": "swhap-negative-corpus/1",
        "description": "Deterministic crit-M6/crit-M3 archive fixture corpus. "
                       "Each fixture isolates one property; REJECT fixtures must "
                       "be refused with the named error code, ACCEPT fixtures must "
                       "be handled without losing bytes.",
        "fixtures": [
            {
                "name": name, "file": fn, "sha256": sums[fn],
                "isolates": isolates, "disposition": disp,
                "expected_code": code, "crit": crit, "note": note,
            }
            for (name, fn, _b, isolates, disp, code, crit, note) in FIXTURES
        ],
    }
    with open(INDEX, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True, ensure_ascii=False)
        fh.write("\n")


def cmd_check() -> int:
    import tempfile
    if not os.path.exists(MANIFEST):
        print("MANIFEST.sha256 absent — run 'python build.py' first", file=sys.stderr)
        return 1
    pinned = {}
    with open(MANIFEST, encoding="utf-8") as fh:
        for ln in fh:
            sha, fn = ln.split()
            pinned[fn] = sha
    with tempfile.TemporaryDirectory() as tmp:
        got = build_all(tmp)
    bad = [fn for fn in got if got[fn] != pinned.get(fn)]
    missing = [fn for fn in pinned if fn not in got]
    if bad or missing:
        for fn in bad:
            print(f"DRIFT {fn}: {got[fn]} != pinned {pinned.get(fn)}", file=sys.stderr)
        for fn in missing:
            print(f"MISSING {fn}", file=sys.stderr)
        return 1
    print(f"[build] OK — {len(got)} fixtures reproduce the pinned MANIFEST")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build the negative archive fixture corpus.")
    ap.add_argument("--check", action="store_true",
                    help="rebuild into a temp dir and verify against MANIFEST.sha256")
    args = ap.parse_args(argv)
    if args.check:
        return cmd_check()
    sums = build_all(ARCHIVES)
    write_manifest(sums)
    write_index(sums)
    for _, fn, *_ in FIXTURES:
        print(f"[build] {sums[fn][:12]}  {fn}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
