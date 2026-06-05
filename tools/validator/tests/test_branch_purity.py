"""BP-1..5 — branch purity on synthetic strict-P fixtures (C3/D1)."""
import os
import subprocess

from swhap_validate.checks import branch_purity
from swhap_validate.context import RepoContext
from swhap_validate.report import Report

_ENV = dict(os.environ, GIT_AUTHOR_NAME="T",
            GIT_AUTHOR_EMAIL="t@noreply.example.org", GIT_COMMITTER_NAME="T",
            GIT_COMMITTER_EMAIL="t@noreply.example.org",
            GIT_AUTHOR_DATE="2026-06-05T00:00:00+0000",
            GIT_COMMITTER_DATE="2026-06-05T00:00:00+0000")


def _g(repo, *a):
    subprocess.run(["git", "-C", repo, *a], check=True, env=_ENV,
                   capture_output=True)


def _write(repo, rel, content=b"x"):
    full = os.path.join(repo, rel)
    os.makedirs(os.path.dirname(full) or repo, exist_ok=True)
    with open(full, "wb") as fh:
        fh.write(content)


def build_repo(path, main_files, source_files, *, orphan=True):
    os.makedirs(path, exist_ok=True)
    _g(path, "init", "-q", "-b", "main")
    for rel, c in main_files.items():
        _write(path, rel, c)
    _g(path, "add", "-A")
    _g(path, "commit", "-q", "-m", "main")
    if orphan:
        _g(path, "checkout", "-q", "--orphan", "SourceCode")
        _g(path, "rm", "-rf", "-q", ".")
        for rel, c in source_files.items():
            _write(path, rel, c)
        _g(path, "add", "-A")
        _g(path, "commit", "-q", "-m", "src")
        _g(path, "tag", "-a", "v1.0", "-m", "Version v1.0")
    else:
        # SourceCode shares history with main (NOT an orphan)
        _g(path, "branch", "SourceCode")
    _g(path, "checkout", "-q", "main")
    return path


def _run(repo, release_tags=("v1.0",)):
    rep = Report("strict-P", "build")
    branch_purity.run(rep, RepoContext(repo), profile="strict-P",
                      release_tags=list(release_tags))
    return rep


def _bp(rep, cid):
    return [f for f in rep.findings if f.check_id == cid]


def test_bp1_green_when_orphan(tmp_path):
    repo = build_repo(str(tmp_path / "r"),
                      {"README.md": b"x", "metadata/x": b"y"},
                      {"Source/a.c": b"int main(){}"}, orphan=True)
    assert not _bp(_run(repo), "BP-1")


def test_bp1_red_when_sourcecode_shares_history(tmp_path):
    repo = build_repo(str(tmp_path / "r"),
                      {"README.md": b"x"}, {}, orphan=False)
    assert _bp(_run(repo, release_tags=()), "BP-1")


def test_bp2_red_forbidden_entry_on_main(tmp_path):
    repo = build_repo(str(tmp_path / "r"),
                      {"README.md": b"x", "secret.txt": b"oops",
                       "metadata/x": b"y"},
                      {"Source/a.c": b"x"}, orphan=True)
    bp2 = _bp(_run(repo), "BP-2")
    assert any(f.object.get("path") == "secret.txt" and f.severity == "FAIL"
               for f in bp2)


def test_bp2_additional_materials_warn(tmp_path):
    repo = build_repo(str(tmp_path / "r"),
                      {"README.md": b"x", "additional_materials/h.ps": b"y",
                       "metadata/x": b"z"},
                      {"Source/a.c": b"x"}, orphan=True)
    bp2 = _bp(_run(repo), "BP-2")
    assert any(f.object.get("path") == "additional_materials"
               and f.severity == "WARN" for f in bp2)


def test_bp3_annotated_tag_required(tmp_path):
    repo = build_repo(str(tmp_path / "r"),
                      {"README.md": b"x", "metadata/x": b"y"},
                      {"Source/a.c": b"x"}, orphan=True)
    # add a lightweight tag for a phantom release
    _g(repo, "tag", "v2.0")  # lightweight
    rep = _run(repo, release_tags=("v1.0", "v2.0"))
    assert any(f.object.get("tag") == "v2.0" for f in _bp(rep, "BP-3"))
