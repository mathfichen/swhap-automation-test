"""SZ-1..5 — size/LFS ladder; thresholds exact at the boundary (crit-M7)."""
import os

from conftest import make_git_repo
from swhap_validate.checks import size_lfs
from swhap_validate.context import RepoContext
from swhap_validate.report import Report, FAIL, WARN


def _run(repo, **kw):
    rep = Report("strict-P", "build")
    ctx = RepoContext(repo)
    size_lfs.run(rep, ctx, refs=["refs/heads/main"], **kw)
    return rep


def _sparse(size):
    # logical size `size`, minimal disk use; git reads it as `size` bytes.
    return size


def make_repo_with_sized_blob(path, name, size):
    os.makedirs(path, exist_ok=True)
    import subprocess
    subprocess.run(["git", "-C", path, "init", "-q", "-b", "main"], check=True)
    full = os.path.join(path, name)
    with open(full, "wb") as fh:
        if size:
            fh.seek(size - 1)
            fh.write(b"\0")
    env = dict(os.environ, GIT_AUTHOR_NAME="T",
               GIT_AUTHOR_EMAIL="t@noreply.example.org", GIT_COMMITTER_NAME="T",
               GIT_COMMITTER_EMAIL="t@noreply.example.org",
               GIT_AUTHOR_DATE="2026-06-05T00:00:00+0000",
               GIT_COMMITTER_DATE="2026-06-05T00:00:00+0000")
    subprocess.run(["git", "-C", path, "add", "-A"], check=True, env=env)
    subprocess.run(["git", "-C", path, "commit", "-q", "-m", "x"], check=True,
                   env=env)
    return path


def test_SZ1_at_100MiB_boundary_fail(tmp_path):
    repo = make_repo_with_sized_blob(str(tmp_path / "r"), "big.bin", size_lfs.SZ1)
    rep = _run(repo)
    assert [f for f in rep.findings if f.check_id == "SZ-1" and f.severity == FAIL]


def test_SZ1_one_below_boundary_no_fail(tmp_path):
    repo = make_repo_with_sized_blob(str(tmp_path / "r"), "big.bin",
                                     size_lfs.SZ1 - 1)
    rep = _run(repo)
    assert not [f for f in rep.findings if f.check_id == "SZ-1"]
    # but it is > 50 MiB → SZ-3 WARN
    assert [f for f in rep.findings if f.check_id == "SZ-3" and f.severity == WARN]


def test_SZ2_lfs_gitattributes_fail(tmp_path):
    repo = make_git_repo(str(tmp_path / "r"), {
        ".gitattributes": b"*.bin filter=lfs diff=lfs merge=lfs -text\n",
        "a.txt": b"hi\n"})
    rep = _run(repo)
    assert [f for f in rep.findings if f.check_id == "SZ-2"]


def test_SZ2_lfs_pointer_blob_fail(tmp_path):
    repo = make_git_repo(str(tmp_path / "r"), {
        "model.bin": b"version https://git-lfs.github.com/spec/v1\n"
                     b"oid sha256:abc\nsize 100\n"})
    rep = _run(repo)
    assert [f for f in rep.findings if f.check_id == "SZ-2"]


def test_SZ4_browser_raw_material_warn(tmp_path):
    repo = make_git_repo(str(tmp_path / "r"), {
        "raw_materials/big.tar": b"x" * (size_lfs.SZ4 + 10)})
    rep = Report("strict-P", "build")
    ctx = RepoContext(repo)
    size_lfs.run(rep, ctx, refs=["refs/heads/main"], intake_profile="browser")
    assert [f for f in rep.findings if f.check_id == "SZ-4" and f.severity == WARN]


def test_SZ4_not_run_without_browser_profile(tmp_path):
    repo = make_git_repo(str(tmp_path / "r"), {
        "raw_materials/big.tar": b"x" * (size_lfs.SZ4 + 10)})
    rep = _run(repo)  # no intake_profile
    assert not [f for f in rep.findings if f.check_id == "SZ-4"]
