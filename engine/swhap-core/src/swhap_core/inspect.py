"""``swhap inspect`` — read-only crit-M6 inspection (M1a slice).

Enumerates archive members and evaluates **every** crit-M6 rejection rule on
the member list directly (no extraction, no disk writes):

  path traversal, absolute paths, symlink targets escaping root, hardlink
  targets outside the member set, device/special files, duplicate members,
  case collisions, and the decompression budgets (members / total bytes /
  compression ratio / single-file size / path length+depth).

It also reports the non-rejection observations the downstream pipeline needs:
wrapper-directory detection, the empty-directory set, the symlink inventory,
and any non-UTF-8 member names (lossless ``bytes_hex`` + a surrogate-free
``decoded`` rendering, aligned with the journal ``extract`` action).

Output is a single deterministic JSON object: no wall-clock, no absolute host
paths, content addressed by the archive's own sha256. Every emitted path goes
through ``bsafe`` so a non-UTF-8 name can never crash serialization or smuggle
a control byte into a forge-visible report (validator-report §2.5a).
"""

from __future__ import annotations

import hashlib
import os
import unicodedata
from dataclasses import dataclass, field

from . import INSPECT_SCHEMA
from . import archive as A
from .errors import Rejection, exit_code_for_codes


# --- policy -----------------------------------------------------------------
@dataclass(frozen=True)
class ExtractionPolicy:
    """Budgets and toggles (core-pipeline.md §4.1 defaults)."""

    max_members: int = 100_000
    max_total_bytes: int = 2 * 1024**3  # 2 GiB
    max_ratio: int = 200  # 1:200 overall compression ratio
    max_filesize: int = 1024**3  # 1 GiB single member
    max_path_bytes: int = 4000
    max_depth: int = 64
    filename_encoding: str = "latin-1"  # display only; bytes reach git unchanged

    @classmethod
    def from_dict(cls, data: dict) -> "ExtractionPolicy":
        fields = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in fields})

    def to_json(self) -> dict:
        return {
            "max_members": self.max_members,
            "max_total_bytes": self.max_total_bytes,
            "max_ratio": self.max_ratio,
            "max_filesize": self.max_filesize,
            "max_path_bytes": self.max_path_bytes,
            "max_depth": self.max_depth,
            "filename_encoding": self.filename_encoding,
        }


DEFAULT_POLICY = ExtractionPolicy()


# --- string safety (validator-report §2.5a bsafe) ---------------------------
def bsafe(s: str) -> str:
    """Lossless, control-free rendering of a possibly-surrogate-bearing string.

    Backslash -> ``\\\\``; a lone surrogate ``U+DC80..U+DCFF`` (an original
    invalid byte) -> ``\\xHH`` of ``cp-0xDC00``; any C0/C1 control -> ``\\xHH``
    of its codepoint; every other character is kept verbatim (valid UTF-8 stays
    real). The result is always valid, control-free Unicode.
    """
    out = []
    for ch in s:
        cp = ord(ch)
        if ch == "\\":
            out.append("\\\\")
        elif 0xDC80 <= cp <= 0xDCFF:
            out.append("\\x%02x" % (cp - 0xDC00))
        elif cp <= 0x1F or 0x7F <= cp <= 0x9F:
            out.append("\\x%02x" % cp)
        else:
            out.append(ch)
    return "".join(out)


def _fold(name: str) -> str:
    """Collision-folding key: casefold(NFC(name)) (csv-contract §7.1)."""
    return unicodedata.normalize("NFC", name).casefold()


def _components(name: str) -> list[str]:
    return [c for c in name.split("/") if c]


def _is_absolute(name: str) -> bool:
    if name.startswith("/") or name.startswith("\\"):
        return True
    # Windows drive letter (e.g. C:\ or C:/)
    if len(name) >= 2 and name[1] == ":" and name[0].isalpha():
        return True
    return False


def _has_traversal(name: str) -> bool:
    # split on both separators; ".." as a whole component is the threat.
    parts = name.replace("\\", "/").split("/")
    return ".." in parts


def _symlink_escapes(member_dir: list[str], target: str) -> bool:
    """True iff a symlink at ``member_dir`` pointing to ``target`` resolves
    outside the extraction root."""
    if _is_absolute(target):
        return True
    resolved = list(member_dir)
    for comp in target.replace("\\", "/").split("/"):
        if comp in ("", "."):
            continue
        if comp == "..":
            if not resolved:
                return True
            resolved.pop()
        else:
            resolved.append(comp)
    return False


# --- report containers ------------------------------------------------------
@dataclass
class _Acc:
    rejections: list[Rejection] = field(default_factory=list)
    symlinks: list[dict] = field(default_factory=list)
    non_utf8: list[dict] = field(default_factory=list)
    empty_dirs: list[str] = field(default_factory=list)


def _sha256_and_size(path: str) -> tuple[str, int]:
    h = hashlib.sha256()
    size = 0
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def inspect_archive(path: str, policy: ExtractionPolicy | None = None) -> dict:
    """Inspect one archive and return a deterministic JSON-able report dict.

    Never raises for archive *content* problems — those become ``rejections``.
    A genuinely unreadable file is reported as a single ``EX-FORMAT`` rejection.
    """
    policy = policy or DEFAULT_POLICY
    sha256, size_bytes = _sha256_and_size(path)
    base = os.path.basename(path)

    report: dict = {
        "schema": INSPECT_SCHEMA,
        "archive": bsafe(base),
        "sha256": sha256,
        "size_bytes": size_bytes,
        "policy": policy.to_json(),
    }

    # --- open + enumerate ---------------------------------------------------
    try:
        info = A.sniff(path)
    except A.ArchiveFormatError as exc:
        report.update(_format_error_report(str(exc)))
        report["accepted"] = False
        report["exit_code"] = exit_code_for_codes(["EX-FORMAT"])
        return report

    report["format"] = info.container
    report["compression"] = info.compression

    try:
        members = A.enumerate_members(path, info)
    except A.ArchiveFormatError as exc:
        report.update(_format_error_report(str(exc)))
        report["accepted"] = False
        report["exit_code"] = exit_code_for_codes(["EX-FORMAT"])
        return report

    acc = _Acc()
    names_seen: dict[bytes, int] = {}
    fold_map: dict[str, list[str]] = {}
    member_name_set = {m.name_bytes for m in members}

    n_files = n_dirs = n_sym = n_hard = n_special = 0
    total_uncompressed = 0
    max_single = 0
    max_path_len = 0
    max_depth = 0

    for m in members:
        comps = _components(m.name)
        depth = len(comps)
        path_len = len(m.name_bytes)
        max_path_len = max(max_path_len, path_len)
        max_depth = max(max_depth, depth)

        # encoding observation (not a rejection by itself; bytes reach git)
        if not m.is_utf8:
            acc.non_utf8.append(
                {
                    "path_bsafe": bsafe(m.name),
                    "bytes_hex": m.name_bytes.hex(),
                    "declared_encoding": policy.filename_encoding,
                    "decoded": m.name_bytes.decode(policy.filename_encoding, "replace"),
                }
            )

        # --- structural rejection rules ------------------------------------
        if _is_absolute(m.name):
            acc.rejections.append(
                Rejection("EX-ABS", "member path is absolute", {"path": bsafe(m.name)})
            )
        if _has_traversal(m.name):
            acc.rejections.append(
                Rejection("EX-TRAVERSAL", "member path contains a '..' component", {"path": bsafe(m.name)})
            )
        if path_len > policy.max_path_bytes:
            acc.rejections.append(
                Rejection(
                    "BG-PATH",
                    "member path length exceeds budget",
                    {"path": bsafe(m.name), "path_bytes": path_len, "limit": policy.max_path_bytes},
                )
            )
        elif depth > policy.max_depth:
            acc.rejections.append(
                Rejection(
                    "BG-PATH",
                    "member path depth exceeds budget",
                    {"path": bsafe(m.name), "depth": depth, "limit": policy.max_depth},
                )
            )

        # duplicates (byte-identical path)
        names_seen[m.name_bytes] = names_seen.get(m.name_bytes, 0) + 1

        # case/normalization collision bucket
        fold_map.setdefault(_fold(m.name), [])
        if m.name not in fold_map[_fold(m.name)]:
            fold_map[_fold(m.name)].append(m.name)

        # --- per-kind handling ---------------------------------------------
        if m.kind == A.DIR:
            n_dirs += 1
        elif m.kind == A.SYMLINK:
            n_sym += 1
            target = m.linkname if m.linkname is not None else ""
            escapes = _symlink_escapes(comps[:-1], target)
            acc.symlinks.append(
                {"path": bsafe(m.name), "target": bsafe(target), "escapes_root": escapes}
            )
            if escapes:
                acc.rejections.append(
                    Rejection(
                        "EX-SYMLINK-ESCAPE",
                        "symlink target resolves outside the extraction root",
                        {"path": bsafe(m.name), "target": bsafe(target)},
                    )
                )
        elif m.kind == A.HARDLINK:
            n_hard += 1
            tgt_bytes = m.link_bytes if m.link_bytes is not None else b""
            if tgt_bytes not in member_name_set:
                acc.rejections.append(
                    Rejection(
                        "EX-HARDLINK-OUT",
                        "hardlink target is not a member of the archive",
                        {"path": bsafe(m.name), "target": bsafe(m.linkname or "")},
                    )
                )
        elif m.kind in A.SPECIAL_KINDS:
            n_special += 1
            acc.rejections.append(
                Rejection(
                    "EX-DEVICE",
                    f"member is a special file ({m.kind})",
                    {"path": bsafe(m.name), "kind": m.kind},
                )
            )
        else:  # FILE
            n_files += 1
            total_uncompressed += m.size
            max_single = max(max_single, m.size)
            if m.size > policy.max_filesize:
                acc.rejections.append(
                    Rejection(
                        "BG-FILESIZE",
                        "single member exceeds the per-file size budget",
                        {"path": bsafe(m.name), "size_bytes": m.size, "limit": policy.max_filesize},
                    )
                )

    # --- write-through-symlink guard (an ancestor dir is itself a symlink) --
    symlink_paths = {bs.rstrip(b"/") for m in members if m.kind == A.SYMLINK for bs in [m.name_bytes]}
    if symlink_paths:
        for m in members:
            if m.kind == A.SYMLINK:
                continue
            ancestors = _ancestor_byte_paths(m.name_bytes)
            hit = next((a for a in ancestors if a in symlink_paths), None)
            if hit is not None:
                acc.rejections.append(
                    Rejection(
                        "EX-SYMLINK-ESCAPE",
                        "member would be written through a symlinked ancestor directory",
                        {"path": bsafe(m.name), "via": bsafe(hit.decode("utf-8", "surrogateescape"))},
                    )
                )

    # --- duplicates ---------------------------------------------------------
    for name_bytes, count in names_seen.items():
        if count > 1:
            acc.rejections.append(
                Rejection(
                    "EX-DUP",
                    "duplicate member path",
                    {"path": bsafe(name_bytes.decode("utf-8", "surrogateescape")), "count": count},
                )
            )

    # --- case collisions ----------------------------------------------------
    for fold_key, variants in fold_map.items():
        if len(variants) > 1:
            acc.rejections.append(
                Rejection(
                    "EX-CASE-COLLISION",
                    "distinct member paths collide under casefold(NFC(.))",
                    {"paths": sorted(bsafe(v) for v in variants)},
                )
            )

    # --- empty dirs ---------------------------------------------------------
    all_norm = {m.name.rstrip("/") for m in members}
    for m in members:
        if m.kind != A.DIR:
            continue
        d = m.name.rstrip("/")
        prefix = d + "/"
        if not any(p != d and p.startswith(prefix) for p in all_norm):
            acc.empty_dirs.append(bsafe(d))

    # --- budgets (whole-archive) -------------------------------------------
    n_members = len(members)
    if n_members > policy.max_members:
        acc.rejections.append(
            Rejection(
                "BG-MEMBERS",
                "member count exceeds budget",
                {"members": n_members, "limit": policy.max_members},
            )
        )
    if total_uncompressed > policy.max_total_bytes:
        acc.rejections.append(
            Rejection(
                "BG-BYTES",
                "total uncompressed size exceeds budget",
                {"total_uncompressed_bytes": total_uncompressed, "limit": policy.max_total_bytes},
            )
        )
    ratio = (total_uncompressed / size_bytes) if size_bytes else 0.0
    ratio_str = "%.2f" % ratio
    if size_bytes and ratio > policy.max_ratio:
        acc.rejections.append(
            Rejection(
                "BG-RATIO",
                "overall compression ratio exceeds budget (decompression bomb)",
                {"ratio": ratio_str, "limit": policy.max_ratio},
            )
        )

    # --- wrapper detection --------------------------------------------------
    report["wrapper"] = _detect_wrapper(members)

    # --- assemble (deterministic ordering) ---------------------------------
    report["summary"] = {
        "members": n_members,
        "files": n_files,
        "dirs": n_dirs,
        "symlinks": n_sym,
        "hardlinks": n_hard,
        "special_files": n_special,
        "total_uncompressed_bytes": total_uncompressed,
        "max_single_file_bytes": max_single,
        "compression_ratio": ratio_str,
        "max_path_bytes": max_path_len,
        "max_depth": max_depth,
        "non_utf8_names": len(acc.non_utf8),
        "case_collisions": sum(1 for r in acc.rejections if r.code == "EX-CASE-COLLISION"),
    }
    report["empty_dirs"] = sorted(acc.empty_dirs)
    report["symlinks"] = sorted(acc.symlinks, key=lambda s: s["path"])
    report["non_utf8_names"] = sorted(acc.non_utf8, key=lambda r: r["bytes_hex"])
    report["rejections"] = sorted(
        (r.to_json() for r in acc.rejections),
        key=lambda r: (r["code"], r.get("path", ""), str(r.get("paths", ""))),
    )
    codes = [r.code for r in acc.rejections]
    report["accepted"] = len(codes) == 0
    report["exit_code"] = exit_code_for_codes(codes)
    return report


def _ancestor_byte_paths(name_bytes: bytes) -> list[bytes]:
    parts = name_bytes.rstrip(b"/").split(b"/")
    out = []
    cur = b""
    for p in parts[:-1]:
        cur = p if not cur else cur + b"/" + p
        out.append(cur)
    return out


def _detect_wrapper(members: list[A.Member]) -> dict:
    """A single top-level directory that contains every other member is an
    artificial wrapper to be stripped (core-pipeline.md §4.1)."""
    tops = set()
    for m in members:
        comps = _components(m.name)
        if comps:
            tops.add(comps[0])
    if len(tops) != 1:
        return {"detected": False, "reason": f"{len(tops)} top-level entries"}
    top = next(iter(tops))
    # the single top-level component must correspond to a directory
    has_dir = any(_components(m.name) == [top] and m.kind == A.DIR for m in members)
    has_children = any(len(_components(m.name)) > 1 for m in members)
    if has_children and (has_dir or not _toplevel_is_file(members, top)):
        return {"detected": True, "name": bsafe(top) + "/", "rule": "single-top-level-directory"}
    return {"detected": False, "reason": "single top-level is not a wrapping directory"}


def _toplevel_is_file(members: list[A.Member], top: str) -> bool:
    return any(_components(m.name) == [top] and m.kind != A.DIR for m in members)


def _format_error_report(message: str) -> dict:
    rej = Rejection("EX-FORMAT", "archive is not a readable tar/zip", {"detail": bsafe(message)})
    return {
        "format": "unknown",
        "compression": "unknown",
        "wrapper": {"detected": False, "reason": "unreadable archive"},
        "summary": {
            "members": 0,
            "files": 0,
            "dirs": 0,
            "symlinks": 0,
            "hardlinks": 0,
            "special_files": 0,
            "total_uncompressed_bytes": 0,
            "max_single_file_bytes": 0,
            "compression_ratio": "0.00",
            "max_path_bytes": 0,
            "max_depth": 0,
            "non_utf8_names": 0,
            "case_collisions": 0,
        },
        "empty_dirs": [],
        "symlinks": [],
        "non_utf8_names": [],
        "rejections": [rej.to_json()],
    }
