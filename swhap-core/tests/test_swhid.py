"""Snapshot-SWHID correctness — pinned against ``swh identify --type snapshot``.

The whole revised-D3 lineage guarantee rests on the locally-computed snapshot
SWHID equalling what Software Heritage assigns. These tests build a repo holding
exactly the published refs (orphan ``SourceCode`` + annotated release tags +
``HEAD``→``SourceCode``) and assert ``swhap_core.swhid.snapshot_swhid`` agrees
with the reference tool, byte for byte.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

import pytest

from swhap_core.swhid import SNP_PREFIX, snapshot_swhid

pytest.importorskip("swh.model")

SOURCECODE_REF = "refs/heads/SourceCode"


def _find_swh() -> str | None:
    """Prefer the ``swh`` next to the running interpreter (the test venv, which
    has dulwich); a system ``swh`` may lack the ``[cli]`` extra."""
    cand = os.path.join(os.path.dirname(sys.executable), "swh")
    if os.path.exists(cand):
        return cand
    return shutil.which("swh")


_SWH = _find_swh()


def _git(repo, *args, env_extra=None):
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "A",
            "GIT_AUTHOR_EMAIL": "a@example.org",
            "GIT_COMMITTER_NAME": "A",
            "GIT_COMMITTER_EMAIL": "a@example.org",
            "GIT_AUTHOR_DATE": "@1781082136 +0000",
            "GIT_COMMITTER_DATE": "@1781082136 +0000",
        }
    )
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["git", "-C", repo, *args], env=env, check=True, capture_output=True, text=True
    ).stdout.strip()


def _published_repo(root: str, *, n_releases: int = 2) -> tuple[str, list[str]]:
    """A repo with an orphan SourceCode branch + one annotated tag per release."""
    os.makedirs(root)
    _git(root, "init", "-q", "-b", "SourceCode")
    tags = []
    for i in range(n_releases):
        with open(os.path.join(root, "f.txt"), "w") as fh:
            fh.write(f"release {i}\n")
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", f"release {i}")
        tag = f"v{i}.0"
        _git(root, "tag", "-a", tag, "-m", f"Version {tag}")
        tags.append(tag)
    _git(root, "symbolic-ref", "HEAD", SOURCECODE_REF)
    return root, tags


def _swh_identify_snapshot(repo: str) -> str:
    out = subprocess.run(
        [_SWH, "identify", "--type", "snapshot", repo],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return out.split("\t", 1)[0].strip()


@pytest.mark.skipif(not (_SWH and os.path.exists(_SWH)), reason="swh CLI not available")
def test_snapshot_swhid_matches_swh_identify(tmp_path):
    repo, tags = _published_repo(str(tmp_path / "pub"))
    reference = _swh_identify_snapshot(repo)
    # all refs + the actual HEAD symref — mirrors swh identify exactly
    assert snapshot_swhid(repo) == reference
    assert reference.startswith(SNP_PREFIX)


def test_explicit_refs_with_head_alias_equals_all_refs(tmp_path):
    """The publish-path computation (explicit refs + forced HEAD alias) equals the
    whole-repo computation when the repo holds exactly the published refs."""
    repo, tags = _published_repo(str(tmp_path / "pub"))
    refs = [SOURCECODE_REF, *(f"refs/tags/{t}" for t in tags)]
    scoped = snapshot_swhid(repo, refs, head_alias=SOURCECODE_REF)
    whole = snapshot_swhid(repo)
    assert scoped == whole


def test_changing_a_tag_changes_the_snapshot(tmp_path):
    repo, tags = _published_repo(str(tmp_path / "pub"))
    base = snapshot_swhid(repo)
    # add another annotated tag → different ref state → different snapshot
    _git(repo, "tag", "-a", "v9.9", "-m", "Version v9.9")
    assert snapshot_swhid(repo) != base


@pytest.mark.skipif(not (_SWH and os.path.exists(_SWH)), reason="swh CLI not available")
def test_subset_of_refs_matches_identify_on_subset_repo(tmp_path):
    """Computing over a subset of refs equals swh identify over a repo holding
    only that subset — the curated-source scoping (SourceCode + tags, no main)."""
    repo, tags = _published_repo(str(tmp_path / "full"))
    # add an unrelated branch that the scoped computation must ignore
    _git(repo, "branch", "main")
    refs = [SOURCECODE_REF, *(f"refs/tags/{t}" for t in tags)]
    scoped = snapshot_swhid(repo, refs, head_alias=SOURCECODE_REF)

    # materialize a repo holding ONLY the scoped refs and HEAD→SourceCode
    sub = str(tmp_path / "sub")
    os.makedirs(sub)
    _git(sub, "init", "-q", "-b", "throwaway")  # not SourceCode: avoid fetch-into-checked-out
    _git(sub, "fetch", repo, f"{SOURCECODE_REF}:{SOURCECODE_REF}", *[f"refs/tags/{t}:refs/tags/{t}" for t in tags])
    _git(sub, "symbolic-ref", "HEAD", SOURCECODE_REF)
    assert _swh_identify_snapshot(sub) == scoped
