"""SZ-1..5 — size / LFS feasibility ladder (crit-M7 / N1).

SZ-1 FAIL: blob ≥ 100 MiB (no GitHub+SWH path). SZ-2 FAIL: git-LFS use.
SZ-3 WARN: blob > 50 MiB. SZ-4 WARN: raw material > 25 MiB under
--intake-profile browser. SZ-5 INFO: repo > 1 GiB.
"""
from __future__ import annotations

from ..report import FAIL, INFO, WARN, Finding

SZ1 = 104857600          # 100 MiB
SZ3 = 52428800           # 50 MiB
SZ4 = 26214400           # 25 MiB
SZ5 = 1073741824         # 1 GiB
_LFS_SIG = b"version https://git-lfs"
_ROLE = "curator"


def run(report, ctx, *, refs, intake_profile=None):
    for cid in ("SZ-1", "SZ-2", "SZ-3", "SZ-5"):
        report.ran(cid)

    # Collect unique blobs across all checked refs: sha -> (size, sample_path)
    blobs = {}
    for ref in refs:
        for e in ctx.ls_tree(ref):
            if e.type != "blob":
                continue
            if e.blob not in blobs:
                blobs[e.blob] = (ctx.blob_size(e.blob), e.path)

    total = 0
    for sha, (size, path) in blobs.items():
        total += size
        if size >= SZ1:
            report.add(Finding(
                "SZ-1", FAIL, {"path": path, "size_bytes": size,
                               "threshold_bytes": SZ1}, ["path"],
                f"The file {path} is {size} bytes (≥ 100 MiB); it cannot be "
                "stored on GitHub and pushed to Software Heritage.",
                required_approver_role=_ROLE))
        elif size > SZ3:
            report.add(Finding(
                "SZ-3", WARN, {"path": path, "size_bytes": size,
                               "threshold_bytes": SZ3}, ["path"],
                f"The file {path} is large ({size} bytes, > 50 MiB).",
                required_approver_role=_ROLE))

    _sz2(report, ctx, refs, blobs)

    if total > SZ5:
        report.add(Finding(
            "SZ-5", INFO, {"size_bytes": total, "threshold_bytes": SZ5}, [],
            f"The repository is large (> 1 GiB across checked refs: {total} bytes).",
            required_approver_role="none"))

    if intake_profile == "browser":
        report.ran("SZ-4")
        _sz4(report, ctx)


def _sz2(report, ctx, refs, blobs):
    # .gitattributes lfs filter anywhere, or a blob with the LFS pointer header.
    for ref in refs:
        for e in ctx.ls_tree(ref):
            if e.path.rsplit("/", 1)[-1] == ".gitattributes":
                content = ctx.cat_blob(e.blob)
                if b"filter=lfs" in content or b"lfs " in content:
                    report.add(Finding(
                        "SZ-2", FAIL, {"path": e.path}, ["path"],
                        f"{e.path} configures git-LFS, which Software Heritage "
                        "does not archive.",
                        required_approver_role=_ROLE))
    for sha, (size, path) in blobs.items():
        if size < 1024:
            head = ctx.cat_blob(sha)[:64]
            if head.startswith(_LFS_SIG):
                report.add(Finding(
                    "SZ-2", FAIL, {"path": path}, ["path"],
                    f"The file {path} is a git-LFS pointer, not real content.",
                    required_approver_role=_ROLE))


def _sz4(report, ctx):
    default = ctx.default_branch()
    if not default:
        return
    for e in ctx.ls_tree(f"refs/heads/{default}"):
        if e.type == "blob" and e.path.startswith("raw_materials/"):
            size = ctx.blob_size(e.blob)
            if size > SZ4:
                report.add(Finding(
                    "SZ-4", WARN, {"path": e.path, "size_bytes": size,
                                   "threshold_bytes": SZ4}, ["path"],
                    f"The raw material {e.path} is {size} bytes (> 25 MiB), too "
                    "large for browser upload; route it via URL.",
                    required_approver_role=_ROLE))
