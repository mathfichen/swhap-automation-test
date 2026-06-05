"""Wild_LIFE fixtures for the M1a TF gate — built from REAL pinned objects.

This module no longer reconstructs the corruption. The published exemplar's real
``SourceCode`` history (3 commits, one per release, NO tags) is pinned in
``fixtures/wildlife/wildlife.bundle`` as ``pin-sourcecode`` alongside the real
``main`` (``pin-main``). ``build_exemplar`` checks those real refs out, so the TF
gate compares the REAL release trees against the REAL tarball-derived manifests
(``fixtures/wildlife/manifests/*.json``). The defect register (0.90 clean, 0.91
+19 / 3 stale, 1.0 +1145 / stale LICENSE, zero deletions between releases) is
therefore DERIVED from the live repo, not injected here.

``build_clean`` is a *faithful regeneration* (not a defect model): it extracts
the pinned tarballs read-only and writes one annotated tag per release with the
correct trees + canonical metadata + a coverage-complete journal, so the
all-green positive fixture is real too. Tarballs are extracted with the ``data``
filter (no path traversal) and NEVER executed.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tarfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                         "..", "..", ".."))
TARBALLS = os.path.join(REPO_ROOT, "fixtures", "wildlife", "tarballs")
MANIFESTS_DIR = os.path.join(REPO_ROOT, "fixtures", "wildlife", "manifests")
BUNDLE = os.path.join(REPO_ROOT, "fixtures", "wildlife", "wildlife.bundle")

TARBALL_FILE = {"0.90": "life_090.tgz", "0.91": "life_091.tgz",
                "1.0": "life_10.tgz"}
TAG = {"0.90": "v0.90", "0.91": "v0.91", "1.0": "v1.0"}
ORDER = ["0.90", "0.91", "1.0"]

# Fixed identities/dates for D4 determinism in the clean fixture.
_ENV = {
    "GIT_AUTHOR_NAME": "Wild_LIFE authors",
    "GIT_AUTHOR_EMAIL": "wildlife-authors@noreply.example.org",
    "GIT_AUTHOR_DATE": "1994-03-24T00:00:00+0000",
    "GIT_COMMITTER_NAME": "Example Curator",
    "GIT_COMMITTER_EMAIL": "example-curator@noreply.example.org",
    "GIT_COMMITTER_DATE": "2026-06-05T00:00:00+0000",
}


def _git(repo, *args, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    subprocess.run(["git", "-C", repo, *args], check=True, env=e,
                   capture_output=True)


# --------------------------------------------------------------------------
# Real published exemplar (from the pinned bundle) — the TF gate oracle target.
# --------------------------------------------------------------------------
def build_exemplar(dest):
    """Check out the REAL pinned exemplar: ``main`` = published metadata (the
    7-col CSV, sciencecodemeta @context, boilerplate journal — all real
    defects), ``SourceCode`` = the real 3-commit corrupted history (no tags)."""
    os.makedirs(dest, exist_ok=True)
    subprocess.run(["git", "clone", "-q", BUNDLE, dest], check=True,
                   capture_output=True)
    _git(dest, "checkout", "-q", "-b", "main", "origin/pin-main")
    _git(dest, "branch", "-q", "SourceCode", "origin/pin-sourcecode")
    return dest


# --------------------------------------------------------------------------
# Faithful clean regeneration (positive fixture) — tarballs -> tagged trees.
# --------------------------------------------------------------------------
def _extract(release, dest):
    name = TARBALL_FILE[release]
    with tarfile.open(os.path.join(TARBALLS, name)) as t:
        t.extractall(dest, filter="data")
    tops = os.listdir(dest)
    assert len(tops) == 1, f"{name}: expected single wrapper dir, got {tops}"
    wrapper = tops[0]
    return os.path.join(dest, wrapper)


def _census(root):
    """Walk a wrapper-stripped tree -> (files {path:bytes}, symlinks
    {path:target}, empty_dirs [paths])."""
    files, symlinks, empty_dirs = {}, {}, []
    for dirpath, dirnames, filenames in os.walk(root):
        real_dirs = []
        for d in dirnames:
            full = os.path.join(dirpath, d)
            if os.path.islink(full):
                rel = os.path.relpath(full, root).replace(os.sep, "/")
                symlinks[rel] = os.readlink(full)
            else:
                real_dirs.append(d)
        dirnames[:] = real_dirs
        rel_dir = os.path.relpath(dirpath, root)
        if not dirnames and not filenames and rel_dir != ".":
            empty_dirs.append(rel_dir.replace(os.sep, "/"))
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if os.path.islink(full):
                symlinks[rel] = os.readlink(full)
            else:
                with open(full, "rb") as fh:
                    files[rel] = fh.read()
    return files, symlinks, sorted(empty_dirs)


def _clear_worktree(repo):
    for name in os.listdir(repo):
        if name == ".git":
            continue
        full = os.path.join(repo, name)
        if os.path.isdir(full) and not os.path.islink(full):
            shutil.rmtree(full)
        else:
            os.remove(full)


def _write_tree(repo, files, symlinks, empty_dirs):
    _clear_worktree(repo)
    for p, content in files.items():
        full = os.path.join(repo, p)
        os.makedirs(os.path.dirname(full) or repo, exist_ok=True)
        with open(full, "wb") as fh:
            fh.write(content)
    for p, target in symlinks.items():
        full = os.path.join(repo, p)
        os.makedirs(os.path.dirname(full) or repo, exist_ok=True)
        if os.path.lexists(full):
            os.remove(full)
        os.symlink(target, full)
    for d in empty_dirs:
        full = os.path.join(repo, d)
        os.makedirs(full, exist_ok=True)
        with open(os.path.join(full, ".emptydir"), "wb") as fh:
            fh.write(b"")


def _commit_tag(repo, tag, message):
    _git(repo, "add", "-A", env=_ENV)
    _git(repo, "commit", "-m", message, env=_ENV)
    _git(repo, "tag", "-a", tag, "-m", f"Version {tag}", env=_ENV)


def build_clean(tmp_root):
    """Build a fully-correct workbench: orphan SourceCode with one annotated tag
    per release whose trees == the tarballs, canonical metadata, coverage
    journal. Returns the repo path."""
    work = os.path.join(tmp_root, "work")
    os.makedirs(work, exist_ok=True)
    census = {}
    for rel in ORDER:
        root = _extract(rel, os.path.join(work, "x" + rel))
        census[rel] = _census(root)

    path = os.path.join(tmp_root, "clean")
    os.makedirs(path, exist_ok=True)
    _git(path, "init", "-q", "-b", "main")
    with open(os.path.join(path, "README.md"), "w") as fh:
        fh.write("# Wild_LIFE workbench\n")
    _git(path, "add", "-A", env=_ENV)
    _git(path, "commit", "-m", "init", env=_ENV)

    _git(path, "checkout", "-q", "--orphan", "SourceCode")
    _git(path, "rm", "-rf", "-q", ".")
    for rel in ORDER:
        files, symlinks, empty = census[rel]
        _write_tree(path, files, symlinks, empty)
        _commit_tag(path, TAG[rel], f"Wild_LIFE {rel}")

    hashes = subprocess.run(["git", "-C", path, "rev-list", "SourceCode"],
                            check=True, capture_output=True,
                            text=True).stdout.split()
    for rel in ORDER:
        obj = subprocess.run(["git", "-C", path, "rev-parse",
                              f"refs/tags/{TAG[rel]}"], check=True,
                             capture_output=True, text=True).stdout.strip()
        hashes.append(obj)

    _git(path, "checkout", "-q", "main")
    _write_canonical_metadata(path)
    _write_coverage_journal(path, hashes)
    _git(path, "add", "-A", env=_ENV)
    _git(path, "commit", "-m", "metadata", env=_ENV)
    return path


def _write_canonical_metadata(path):
    md = os.path.join(path, "metadata")
    os.makedirs(md, exist_ok=True)
    header = ("directory name,date,author name,author email,"
              "curator name,curator email,release tag,commit message\n")
    rows = (
        "0.90,1993-08-09,Wild_LIFE authors,wildlife-authors@noreply.example.org,"
        "Example Curator,example-curator@noreply.example.org,v0.90,Wild_LIFE 0.90\n"
        "0.91,1993-08-09,Wild_LIFE authors,wildlife-authors@noreply.example.org,"
        "Example Curator,example-curator@noreply.example.org,v0.91,Wild_LIFE 0.91\n"
        "1.0,1994-03-24,Wild_LIFE authors,wildlife-authors@noreply.example.org,"
        "Example Curator,example-curator@noreply.example.org,v1.0,Wild_LIFE 1.0\n"
    )
    with open(os.path.join(md, "version_history.csv"), "w", encoding="utf-8") as fh:
        fh.write(header + rows)
    with open(os.path.join(md, "codemeta.json"), "w", encoding="utf-8") as fh:
        fh.write('{\n  "@context": "https://doi.org/10.5063/schema/codemeta-2.0",\n'
                 '  "@type": "SoftwareSourceCode",\n'
                 '  "name": "Wild_LIFE",\n'
                 '  "funder": {"@type": "Organization", "name": "DEC PRL"}\n}\n')


def _write_coverage_journal(path, hashes):
    md = os.path.join(path, "metadata")
    os.makedirs(md, exist_ok=True)
    lines = []
    for h in hashes:
        lines.append('{"schema":"swhap-journal/1","action":"apply","git_object":'
                     f'"{h}"}}')
    with open(os.path.join(md, "journal.jsonl"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
