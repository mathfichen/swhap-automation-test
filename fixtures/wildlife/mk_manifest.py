#!/usr/bin/env python3
"""Generate Wild_LIFE ground-truth tree manifests from the pinned tarballs.

Workstream: exemplar-pilot T2 (clean releases 0.90 / 0.91 / 1.0) and T3
(quarantined 1.02 census).  Emits one `swhap-tree-manifest/1` JSON document
per release into ``fixtures/wildlife/manifests/`` plus a date-evidence note
for 1.02.

Discipline (binding):

* **Read-only, no execution.**  Members are read with the stdlib ``tarfile``
  reader.  Content is pulled into memory via ``TarFile.extractfile`` (a pure
  byte read); **nothing is written to disk and nothing is executed.**  This is
  the interim stdlib census of exemplar-pilot.md S2.2 (fallback path), to be
  cross-checked by ``swhap inspect`` at M1c (manifest-diff gate).
* **Deterministic.**  No wall-clock, no absolute paths, no hostnames enter the
  output.  Entries are sorted byte-wise by path; JSON is emitted with
  ``sort_keys=True`` and a trailing newline, so a rebuild is byte-stable.

The manifest shape is documented in ``manifests/README.md`` (the contract the
validator TF-* checks code against).
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys
import tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
TARBALLS = os.path.join(HERE, "tarballs")
MANIFESTS = os.path.join(HERE, "manifests")
MANIFEST_SCHEMA = "swhap-tree-manifest/1"

# Frozen ground-truth counts from analysis/corpus/followup-2.md (cross-check).
EXPECTED = {
    "0.90": {"tarball": "life_090.tgz", "files": 1139, "symlinks": 0, "empty_dirs": 0, "wrapper": "Life/"},
    "0.91": {"tarball": "life_091.tgz", "files": 1152, "symlinks": 0, "empty_dirs": 0, "wrapper": "Life/"},
    "1.0":  {"tarball": "life_10.tgz",  "files": 1496, "symlinks": 4, "empty_dirs": 4, "wrapper": "Life1.0/"},
}
QUARANTINE = {"1.02": {"tarball": "Life1.02Ultrix.tar", "wrapper": "Life1.02Ultrix/"}}


def _norm(name: str) -> str:
    """Strip a single leading ``./`` and any trailing slash; keep the rest."""
    if name.startswith("./"):
        name = name[2:]
    return name.rstrip("/")


def _utf8_safe(s: str):
    """Return (display, bytes_hex_or_None) for a possibly non-UTF-8 path.

    tarfile decodes member names with ``surrogateescape``; a non-UTF-8 byte
    survives as a lone surrogate.  We surface the lossless byte authority as
    hex and a surrogate-free display string (never crash on serialization).
    """
    try:
        s.encode("utf-8")
        return s, None
    except UnicodeEncodeError:
        raw = s.encode("utf-8", "surrogateescape")
        return raw.decode("utf-8", "replace"), raw.hex()


def _git_blob_sha1(data: bytes) -> str:
    h = hashlib.sha1()
    h.update(b"blob " + str(len(data)).encode("ascii") + b"\0")
    h.update(data)
    return h.hexdigest()


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_mode(m: tarfile.TarInfo) -> str:
    if m.issym():
        return "120000"
    return "100755" if (m.mode & 0o111) else "100644"


def census(tarball: str):
    """Read a tarball read-only and return a structured census.

    Returns a dict with: wrapper, entries (files+symlinks, wrapper-stripped),
    empty_dirs, symlinks, stray_top_level, and anomaly tallies.
    """
    path = os.path.join(TARBALLS, tarball)
    members = []  # (norm_name, TarInfo)
    with tarfile.open(path, "r:*") as t:
        infos = t.getmembers()
        # Pre-resolve content reads inside the open context (no disk writes).
        content = {}
        for m in infos:
            nm = _norm(m.name)
            if not nm:
                continue
            members.append((nm, m))
            if m.isreg():
                f = t.extractfile(m)
                content[nm] = f.read() if f is not None else b""

    real_tops = sorted({nm.split("/", 1)[0] for nm, m in members
                        if not os.path.basename(nm).startswith("._")})
    wrapper = real_tops[0] + "/" if len(real_tops) == 1 else None
    # Stray top-level members that are NOT under the single real wrapper.
    stray_top_level = []
    if wrapper is not None:
        w = wrapper[:-1]
        for nm, m in members:
            top = nm.split("/", 1)[0]
            if top != w:
                stray_top_level.append(nm)

    def strip(nm: str) -> str:
        if wrapper and (nm == wrapper[:-1] or nm.startswith(wrapper)):
            return nm[len(wrapper):]
        return nm  # stray member: keep absolute-in-archive path

    dirset = set()
    childbearing = set()  # path prefixes that have at least one descendant
    entries = []
    symlinks = []
    appledouble = 0
    absolute_escape_symlinks = []
    relative_escape_symlinks = []
    odd_modes = set()
    mtimes = []          # all members
    content_mtimes = []  # real (non-AppleDouble) regular files only

    for nm, m in members:
        base = os.path.basename(nm)
        is_ad = base.startswith("._")
        if is_ad:
            appledouble += 1
        mtimes.append(m.mtime)
        # register ancestors as child-bearing
        parts = nm.split("/")
        for i in range(1, len(parts)):
            childbearing.add("/".join(parts[:i]))
        if m.isdir():
            dirset.add(nm)
            continue
        spath = strip(nm)
        disp, bhex = _utf8_safe(spath)
        if m.issym():
            tgt = m.linkname
            tbytes = tgt.encode("utf-8", "surrogateescape")
            ent = {
                "path": disp, "type": "symlink", "mode": "120000",
                "target": tgt,
                "sha256": hashlib.sha256(tbytes).hexdigest(),
                "git_blob_sha1": _git_blob_sha1(tbytes),
            }
            if bhex is not None:
                ent["path_bytes_hex"] = bhex
            entries.append(ent)
            symlinks.append({"path": disp, "target": tgt})
            # escape classification (relative to member dir, within wrapper)
            if tgt.startswith("/"):
                absolute_escape_symlinks.append({"path": disp, "target": tgt})
            else:
                root = nm.split("/", 1)[0]
                resolved = os.path.normpath(os.path.join(os.path.dirname(nm), tgt))
                if not (resolved == root or resolved.startswith(root + "/")):
                    relative_escape_symlinks.append({"path": disp, "target": tgt})
        elif m.isreg():
            if not is_ad:
                content_mtimes.append(m.mtime)
            data = content[nm]
            ent = {
                "path": disp, "type": "file", "mode": _git_mode(m),
                "sha256": hashlib.sha256(data).hexdigest(),
                "git_blob_sha1": _git_blob_sha1(data),
            }
            if bhex is not None:
                ent["path_bytes_hex"] = bhex
            entries.append(ent)
        else:
            odd_modes.add(m.type)

    # Empty dirs: declared directory members with no descendant member.
    empty_dirs = sorted(strip(d) for d in dirset if d not in childbearing)

    entries.sort(key=lambda e: e["path"].encode("utf-8", "surrogateescape"))
    symlinks.sort(key=lambda s: s["path"].encode("utf-8", "surrogateescape"))

    files = sum(1 for e in entries if e["type"] == "file")
    syms = sum(1 for e in entries if e["type"] == "symlink")

    return {
        "wrapper": wrapper,
        "stray_top_level": sorted(stray_top_level),
        "entries": entries,
        "empty_dirs": empty_dirs,
        "symlinks": symlinks,
        "counts": {"files": files, "symlinks": syms,
                   "empty_dirs": len(empty_dirs), "entries": len(entries)},
        "appledouble": appledouble,
        "absolute_escape_symlinks": absolute_escape_symlinks,
        "relative_escape_symlinks": relative_escape_symlinks,
        "all_mtimes": mtimes,
        "content_mtimes": content_mtimes,
    }


def _doc_header(release: str, tarball: str, c: dict, quarantined: bool) -> dict:
    return {
        "schema": MANIFEST_SCHEMA,
        "release": release,
        "tarball": tarball,
        "tarball_sha256": _sha256_file(os.path.join(TARBALLS, tarball)),
        "wrapper": c["wrapper"],
        "quarantined": quarantined,
        "counts": c["counts"],
        "empty_dirs": c["empty_dirs"],
        "symlinks": c["symlinks"],
        "entries": c["entries"],
        "generator": {"tool": "mk_manifest.py", "schema": MANIFEST_SCHEMA},
    }


def write_json(obj: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True, ensure_ascii=False)
        fh.write("\n")


def build_clean(release: str) -> dict:
    spec = EXPECTED[release]
    c = census(spec["tarball"])
    # Cross-check against followup-2 (fail loud on drift).
    assert c["wrapper"] == spec["wrapper"], (release, c["wrapper"], spec["wrapper"])
    assert c["counts"]["files"] == spec["files"], (release, c["counts"])
    assert c["counts"]["symlinks"] == spec["symlinks"], (release, c["counts"])
    assert c["counts"]["empty_dirs"] == spec["empty_dirs"], (release, c["counts"])
    assert not c["stray_top_level"], (release, c["stray_top_level"])
    doc = _doc_header(release, spec["tarball"], c, quarantined=False)
    return doc


def build_quarantine() -> tuple[dict, str]:
    spec = QUARANTINE["1.02"]
    c = census(spec["tarball"])
    doc = _doc_header("1.02", spec["tarball"], c, quarantined=True)
    # Anomaly register (crit-M6): why 1.02 is NOT a clean TF oracle.
    perm_note = "all regular-file permission bits are 0o777 (Ultrix/macOS extraction artifact); git modes normalize to 100755"
    anomalies = []
    if c["appledouble"]:
        anomalies.append({
            "class": "macos-appledouble",
            "detail": f"{c['appledouble']} AppleDouble companion files (basename '._*') — resource-fork/metadata noise from macOS packaging; not source content",
            "expected_check": "TF-1/BP-2 (curatorial-noise exclusion)",
        })
    if c["stray_top_level"]:
        anomalies.append({
            "class": "stray-top-level",
            "detail": "members not under the single real wrapper directory: " + ", ".join(c["stray_top_level"]),
            "expected_check": "BP-5 (wrapper stripping)",
        })
    if c["absolute_escape_symlinks"]:
        anomalies.append({
            "class": "symlink-escape-absolute",
            "detail": "symlinks with absolute targets escaping the extraction root",
            "members": c["absolute_escape_symlinks"],
            "expected_check": "EX-SYMLINK-ESCAPE",
        })
    if c["relative_escape_symlinks"]:
        anomalies.append({
            "class": "symlink-escape-relative",
            "detail": "symlinks whose relative target escapes the wrapper root",
            "members": c["relative_escape_symlinks"],
            "expected_check": "EX-SYMLINK-ESCAPE",
        })
    anomalies.append({"class": "perm-bits", "detail": perm_note, "expected_check": "extraction mode-normalization"})
    doc["anomalies"] = anomalies

    # Date evidence from member mtimes (feeds the Q9 year-only decision).
    def iso(ts):
        return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    from collections import Counter
    yr_all = Counter(datetime.datetime.fromtimestamp(t, datetime.timezone.utc).year for t in c["all_mtimes"])
    yr_content = Counter(datetime.datetime.fromtimestamp(t, datetime.timezone.utc).year for t in c["content_mtimes"])
    note = render_date_evidence(spec["tarball"], doc["tarball_sha256"], c, iso, yr_all, yr_content)
    return doc, note


def render_date_evidence(tarball, sha256, c, iso, yr_all, yr_content) -> str:
    cmin = iso(min(c["content_mtimes"]))
    cmax = iso(max(c["content_mtimes"]))
    amin = iso(min(c["all_mtimes"]))
    amax = iso(max(c["all_mtimes"]))
    def hist(counter):
        return ", ".join(f"{y}: {n}" for y, n in sorted(counter.items()))
    return f"""# Wild_LIFE 1.02 — date evidence from tarball member mtimes

Generated by `mk_manifest.py` (read-only census of `{tarball}`,
sha256 `{sha256}`).  Feeds the Q9 year-only date decision (csv-contract §4.1,
exemplar-pilot.md T3 / §4.3); **no date is invented** — this note records only
what the tar member mtimes assert.

## What the mtimes say

* **Real source content** (regular files, AppleDouble `._*` excluded):
  `{cmin}` .. `{cmax}`.
  Per-year file count: {hist(yr_content)}.
* **All members** (including directories, symlinks and AppleDouble files,
  whose mtimes are macOS *repackaging* artifacts, not release dates):
  `{amin}` .. `{amax}`.
  Per-year member count: {hist(yr_all)}.

## Reading

The tarball is a macOS re-packaging (AppleDouble companion files, all-0777
permission bits) of a 1994-era Ultrix source tree.  The directory/symlink/
AppleDouble mtimes in 2010 and 2017 are **packaging timestamps** and carry no
release-date signal.  The defensible release-date evidence is the **real source
file** range, which lands entirely in **1994** (latest content file
`{cmax}`).

## Consequence for the CSV `date` (Q9)

* The tarball evidence supports at most a **year-only `1994`** value
  (precision `year`, provenance **inferred** — csv-contract §4.1 row 3), since
  no single release *day* is assertable from these mtimes.
* The csv-contract §12.1 example row V4 carries `1995`; that figure rests on
  **external corroboration** (the `djdarland/WildLIFE` `mk-1.02.sh` lineage,
  exemplar-pilot.md §4.4), **not** on this tarball.  The discrepancy
  (tar evidence 1994 vs external 1995) is exactly the kind of inferred-date
  ambiguity Q9 routes to curator visibility; the curator selects the final
  value and the journal records the evidence basis.  This note is the tar-side
  half of that record.
"""


def main() -> int:
    os.makedirs(MANIFESTS, exist_ok=True)
    for release in ("0.90", "0.91", "1.0"):
        doc = build_clean(release)
        write_json(doc, os.path.join(MANIFESTS, f"{release}.json"))
        print(f"[mk_manifest] {release}: {doc['counts']}")
    qdoc, note = build_quarantine()
    write_json(qdoc, os.path.join(MANIFESTS, "1.02.json"))
    with open(os.path.join(MANIFESTS, "1.02-date-evidence.md"), "w", encoding="utf-8") as fh:
        fh.write(note)
    print(f"[mk_manifest] 1.02 (quarantined): {qdoc['counts']}, anomalies={len(qdoc['anomalies'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
