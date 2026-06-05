"""Reconstruct the Wild_LIFE ground truth + the *defective published exemplar*
from the pinned tarballs, for the M1a red/green gate.

WHY THIS EXISTS (dependency note): the pinned ``fixtures/wildlife/wildlife.bundle``
contains only ``pin-main`` (1571ce5) and ``pin-pr1`` (5e05003) — it does NOT carry
the ``SourceCode`` branch or the release tags whose trees hold the v0.91/v1.0
defects (followup-2). The exemplar-pilot ground-truth manifests + defect register
(its T2–T4) and a bundle carrying SourceCode are not present in this checkout.
So this module rebuilds, deterministically and read-only, exactly the documented
corruption from the real tarballs:

  * manifests = the wrapper-stripped tarball census (the C4 oracle),
  * a ``defective`` repo whose SourceCode tags reproduce the leak
    (v0.91: 19 extras + 3 stale; v1.0: 1145-entry leak + stale LICENSE; the
    v0.91→v1.0 diff has zero deletions), with ``main`` = the real exemplar
    metadata (7-col CSV, sciencecodemeta @context, boilerplate journal),
  * a ``clean`` repo whose tags == their manifests, with canonical metadata and a
    coverage-complete journal.jsonl.

Tarballs are extracted with the ``data`` filter (no path traversal) and NEVER
executed. Once exemplar-pilot delivers its manifests + a SourceCode-bearing
bundle, this reconstruction is replaced by consuming those oracles directly.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tarfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                         "..", "..", ".."))
TARBALLS = os.path.join(REPO_ROOT, "fixtures", "wildlife", "tarballs")
BUNDLE = os.path.join(REPO_ROOT, "fixtures", "wildlife", "wildlife.bundle")
SHA256 = {
    "0.90": "928453daa1ae1477113f323b2d98d3920d15999d8ed7d496f0b606598592df19",
    "0.91": "dbf206afbd22b57070a484687e24548efd66754397b81661121bc2de70ae5ce6",
    "1.0": "c8d3d7c72e9eeab2b6124348bc5e4b8f15d69c1fd29b35768251751a505a670e",
}
TARBALL_FILE = {"0.90": "life_090.tgz", "0.91": "life_091.tgz",
                "1.0": "life_10.tgz"}
TAG = {"0.90": "v0.90", "0.91": "v0.91", "1.0": "v1.0"}
ORDER = ["0.90", "0.91", "1.0"]

# Fixed identities/dates for D4 determinism in the fixture.
_ENV = {
    "GIT_AUTHOR_NAME": "Wild_LIFE authors",
    "GIT_AUTHOR_EMAIL": "wildlife-authors@noreply.example.org",
    "GIT_AUTHOR_DATE": "1994-03-24T00:00:00+0000",
    "GIT_COMMITTER_NAME": "Example Curator",
    "GIT_COMMITTER_EMAIL": "example-curator@noreply.example.org",
    "GIT_COMMITTER_DATE": "2026-06-05T00:00:00+0000",
}

# The 3 stale paths in v0.91 and the stale LICENSE in v1.0 (followup-2 §2/§3).
_V091_STALE = ["Examples/hamming.lf", "Tests/choice.out", "Tests/choice.ref"]


def _git_blob_sha1(content: bytes) -> str:
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(content))
    h.update(content)
    return h.hexdigest()


def _git(repo, *args, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    subprocess.run(["git", "-C", repo, *args], check=True, env=e,
                   capture_output=True)


def _extract(release, dest):
    name = TARBALL_FILE[release]
    with tarfile.open(os.path.join(TARBALLS, name)) as t:
        # verify wrapper is a single top component
        t.extractall(dest, filter="data")
    tops = os.listdir(dest)
    assert len(tops) == 1, f"{name}: expected single wrapper dir, got {tops}"
    wrapper = tops[0]
    return os.path.join(dest, wrapper), wrapper + "/"


def _census(root):
    """Walk a wrapper-stripped tree → (files {path:bytes}, symlinks {path:target},
    empty_dirs [paths])."""
    files, symlinks, empty_dirs = {}, {}, []
    for dirpath, dirnames, filenames in os.walk(root):
        # Symlinks-to-directories appear in dirnames; capture them as symlinks
        # and stop os.walk from descending into them.
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


def _manifest_dict(release, files, symlinks, empty_dirs, wrapper):
    entries = []
    for p, content in files.items():
        mode = "100755" if False else "100644"  # tarballs here are all 100644
        entries.append({"path": p, "type": "file", "mode": mode,
                        "blob": _git_blob_sha1(content)})
    for p, target in symlinks.items():
        entries.append({"path": p, "type": "symlink", "mode": "120000",
                        "blob": _git_blob_sha1(target.encode("utf-8")),
                        "target": target})
    entries.sort(key=lambda e: e["path"])
    return {
        "release": release, "tarball": TARBALL_FILE[release],
        "sha256": SHA256[release], "wrapper": wrapper,
        "entry_count": len(entries), "entries": entries,
        "empty_dirs": empty_dirs, "encoding_notes": [],
        "generator": {"tool": "wildlife_fixture.py", "extractor_version": "stdlib"},
    }


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


def build(tmp_root):
    """Build the fixture set under tmp_root. Returns a dict with repo paths,
    manifests (release→dict), and ordered tag list."""
    work = os.path.join(tmp_root, "work")
    os.makedirs(work, exist_ok=True)

    # 1. extract + census all three releases.
    roots, census, manifests = {}, {}, {}
    for rel in ORDER:
        root, wrapper = _extract(rel, os.path.join(work, "x" + rel))
        roots[rel] = root
        files, symlinks, empty = _census(root)
        census[rel] = (files, symlinks, empty)
        manifests[rel] = _manifest_dict(rel, files, symlinks, empty, wrapper)

    f90, _, _ = census["0.90"]
    f91, s91, e91 = census["0.91"]
    f10, s10, e10 = census["1.0"]

    # 2. reconstruct the documented leak trees.
    extras91 = set(f90) - set(f91)                 # 19 v0.90-only paths
    v091_git_files = dict(f91)
    for p in extras91:                              # leak the deletions
        v091_git_files[p] = f90[p]
    for p in _V091_STALE:                           # 3 stale overwrites
        if p in f90:
            v091_git_files[p] = f90[p]

    leak10 = set(v091_git_files) - set(f10)         # 1145 paths leaked into v1.0
    v10_git_files = dict(f10)
    for p in leak10:
        v10_git_files[p] = v091_git_files[p]
    # stale LICENSE: v1.0 carries v0.91's LICENSE content
    if "LICENSE" in f10 and "LICENSE" in f91:
        v10_git_files["LICENSE"] = f91["LICENSE"]

    defective = _build_repo(
        os.path.join(tmp_root, "defective"),
        main_from="origin/pin-main",
        trees=[
            ("0.90", f90, {}, []),
            ("0.91", v091_git_files, {}, []),
            ("1.0", v10_git_files, s10, e10),
        ],
        journal=None,  # main carries the real boilerplate journal.md from pin-main
    )
    clean = _build_repo(
        os.path.join(tmp_root, "clean"),
        main_from=None,
        trees=[
            ("0.90", f90, {}, []),
            ("0.91", f91, {}, e91),
            ("1.0", f10, s10, e10),
        ],
        journal="coverage",  # journal.jsonl referencing every commit/tag
        canonical_metadata=True,
    )

    return {"manifests": manifests, "order": ORDER, "tags": TAG,
            "defective": defective, "clean": clean}


def _build_repo(path, *, main_from, trees, journal, canonical_metadata=False):
    os.makedirs(path, exist_ok=True)
    if main_from:
        subprocess.run(["git", "clone", "-q", BUNDLE, path],
                       check=True, capture_output=True)
        _git(path, "checkout", "-q", "-b", "main", main_from)
    else:
        _git(path, "init", "-q", "-b", "main")
        # minimal placeholder so main exists; replaced below if canonical
        with open(os.path.join(path, "README.md"), "w") as fh:
            fh.write("# Wild_LIFE workbench\n")
        _git(path, "add", "-A", env=_ENV)
        _git(path, "commit", "-m", "init", env=_ENV)

    # Build SourceCode as an orphan branch.
    _git(path, "checkout", "-q", "--orphan", "SourceCode")
    _git(path, "rm", "-rf", "-q", ".")
    tag_for = {}
    for rel, files, symlinks, empty in trees:
        _write_tree(path, files, symlinks, empty)
        _commit_tag(path, TAG[rel], f"Wild_LIFE {rel}")
        tag_for[rel] = TAG[rel]

    # Collect curated object hashes for coverage journal.
    hashes = []
    for c in subprocess.run(["git", "-C", path, "rev-list", "SourceCode"],
                            check=True, capture_output=True,
                            text=True).stdout.split():
        hashes.append(c)
    for rel in tag_for:
        obj = subprocess.run(["git", "-C", path, "rev-parse",
                              f"refs/tags/{TAG[rel]}"], check=True,
                             capture_output=True, text=True).stdout.strip()
        hashes.append(obj)

    _git(path, "checkout", "-q", "main")
    if canonical_metadata:
        _write_canonical_metadata(path)
    if journal == "coverage":
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
                 '  "funder": {"@type": "Organization", "name": "DEC PRL"},\n'
                 '  "maintainer": {"@type": "Person", "name": "Example Curator"}\n}\n')


def _write_coverage_journal(path, hashes):
    md = os.path.join(path, "metadata")
    os.makedirs(md, exist_ok=True)
    lines = []
    for h in hashes:
        lines.append('{"schema":"swhap-journal/1","action":"apply","git_object":'
                     f'"{h}"}}')
    with open(os.path.join(md, "journal.jsonl"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
