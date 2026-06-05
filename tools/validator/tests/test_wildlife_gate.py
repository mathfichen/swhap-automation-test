"""M1a RED gate, grounded in the REAL published exemplar.

The defect register is no longer injected by a hand-coded reconstruction: it is
DERIVED here by diffing the REAL SourceCode commit trees (from the pinned
bundle) against the REAL tarball-derived manifests, and the validator's report
is asserted to agree. The headline numbers (0.90 clean, 0.91 +19 extras / 3
stale blobs, 1.0 +1145 extras / stale LICENSE, zero deletions between releases)
are the live published numbers settled against SoftwareHeritage/Wild_Life-swhap
on 2026-06-06 — asserting them asserts against reality, not against a fixture.
"""
import subprocess

import pytest

from swhap_validate.cli import run_validation
from swhap_validate.report import FAIL


# ---- independent oracle: diff real tree vs real manifest, via raw git --------

def _sourcecode_commit_for(repo, release):
    out = subprocess.run(
        ["git", "-C", repo, "log", "--format=%H%x09%s", "refs/heads/SourceCode"],
        check=True, capture_output=True, text=True).stdout
    hits = []
    for line in out.splitlines():
        sha, _, subj = line.partition("\t")
        toks = subj.split()
        if release in toks:
            hits.append(sha)
    assert len(hits) == 1, f"{release}: expected 1 SourceCode commit, got {hits}"
    return hits[0]


def _git_tree(repo, ref):
    raw = subprocess.run(["git", "-C", repo, "ls-tree", "-r", "-z", ref],
                         check=True, capture_output=True).stdout
    files, symlinks, emptydirs = {}, {}, set()
    for rec in raw.split(b"\x00"):
        if not rec:
            continue
        meta, _, path = rec.partition(b"\t")
        mode, _, rest = meta.partition(b" ")
        _, _, sha = rest.partition(b" ")
        p = path.decode("utf-8", "surrogateescape")
        mode = mode.decode()
        sha = sha.decode()
        if p.rsplit("/", 1)[-1] == ".emptydir":
            emptydirs.add(p[: -len("/.emptydir")] if "/" in p else "")
        elif mode == "120000":
            symlinks[p] = sha
        else:
            files[p] = (mode, sha)
    return files, symlinks, emptydirs


def _derive_register(repo, manifests):
    by_release = {m.release: m for m in manifests}
    reg = {}
    for rel, man in by_release.items():
        commit = _sourcecode_commit_for(repo, rel)
        files, syms, _ = _git_tree(repo, commit)
        git_paths = set(files) | set(syms)
        man_paths = set(man.entries)
        blob_mis = sum(1 for p in (git_paths & man_paths)
                       if p in files and files[p][1] != man.entries[p].blob)
        reg[rel] = {
            "commit": commit,
            "extra": len(git_paths - man_paths),
            "missing": len(man_paths - git_paths),
            "blob_mismatch": blob_mis,
        }
    return reg


@pytest.fixture(scope="module")
def report(wildlife):
    return run_validation(wildlife["defective"], "strict-P", "build",
                          manifests=wildlife["manifests"])


@pytest.fixture(scope="module")
def register(wildlife):
    return _derive_register(wildlife["defective"], wildlife["manifests"])


def _tf(report, check_id, release):
    return [f for f in report.findings
            if f.check_id == check_id and f.object.get("release") == release]


def _by_check(report, check_id):
    return [f for f in report.findings if f.check_id == check_id]


# -- the derived register IS the real published corruption -------------------

def test_derived_register_matches_published_numbers(register):
    """Independent diff (raw git vs committed manifests) reproduces the settled
    published numbers — proving the oracle is real, not reconstructed."""
    assert register["0.90"] == {**register["0.90"], "extra": 0, "missing": 0,
                                "blob_mismatch": 0}
    assert register["0.91"]["extra"] == 19
    assert register["0.91"]["blob_mismatch"] == 3
    assert register["1.0"]["extra"] == 1145
    assert register["1.0"]["blob_mismatch"] == 1


def test_validator_tf1_agrees_with_derived(report, register):
    for rel, exp in register.items():
        tf1 = _tf(report, "TF-1", rel)
        if exp["extra"] or exp["missing"]:
            assert tf1, f"TF-1 must fire on {rel}"
            assert tf1[0].object["extra_count"] == exp["extra"]
            assert tf1[0].object["missing_count"] == exp["missing"]
        else:
            assert not tf1, f"TF-1 must NOT fire on clean {rel}"


def test_validator_tf2_agrees_with_derived(report, register):
    for rel, exp in register.items():
        tf2 = _tf(report, "TF-2", rel)
        if exp["blob_mismatch"]:
            assert tf2, f"TF-2 must fire on {rel}"
            assert tf2[0].object["mismatch_count"] == exp["blob_mismatch"]
        else:
            assert not tf2, f"TF-2 must NOT fire on clean {rel}"


# -- 0.90 clean --------------------------------------------------------------

def test_wildlife_v090_green(report):
    assert not _tf(report, "TF-1", "0.90")
    assert not _tf(report, "TF-2", "0.90")
    assert not _tf(report, "TF-3", "0.90")
    assert not _tf(report, "TF-4", "0.90")
    assert not _tf(report, "TF-5", "0.90")


# -- 0.91 red ----------------------------------------------------------------

def test_wildlife_v091_red(report):
    tf1 = _tf(report, "TF-1", "0.91")
    assert tf1 and tf1[0].severity == FAIL and tf1[0].object["extra_count"] == 19
    tf2 = _tf(report, "TF-2", "0.91")
    assert tf2 and tf2[0].object["mismatch_count"] == 3


# -- 1.0 red incl. stale LICENSE, green emptydir/symlink ---------------------

def test_wildlife_v10_red(report):
    tf1 = _tf(report, "TF-1", "1.0")
    assert tf1 and tf1[0].object["extra_count"] == 1145
    tf2 = _tf(report, "TF-2", "1.0")
    assert tf2 and "LICENSE" in tf2[0].message_technical


def test_wildlife_v10_emptydir_and_symlinks_green(report):
    assert not _tf(report, "TF-4", "1.0")
    assert not _tf(report, "TF-5", "1.0")


# -- TF-3 previous-version leak (zero deletions applied) ---------------------

def test_tf3_zero_deletions_between_releases(report):
    for to in ("0.91", "1.0"):
        tf3 = [f for f in _by_check(report, "TF-3") if f.object.get("to") == to]
        assert tf3 and tf3[0].severity == FAIL
        assert tf3[0].object["actual_deletions"] == 0
        assert tf3[0].object["expected_deletions"] > 0


# -- real metadata defects on the published main -----------------------------

def test_csv_header_red(report):
    cs = _by_check(report, "CSV-1")
    assert cs and cs[0].severity == FAIL


def test_codemeta_sciencecodemeta_context_red(report):
    cm = _by_check(report, "CM-2")
    assert cm and cm[0].severity == FAIL
    assert any("sciencecodemeta" in (f.object.get("context") or "") for f in cm)


def test_journal_coverage_red(report):
    jc = _by_check(report, "JC-1a")
    assert jc and jc[0].severity == FAIL


# -- no-tags compliance defect (Task 4) --------------------------------------

def test_no_annotated_tags_recorded(report):
    """The published exemplar maps releases to SourceCode commits with NO tags;
    the brief requires one annotated tag per release. BP-3 records it."""
    bp3 = _by_check(report, "BP-3")
    assert bp3, "BP-3 must record the missing per-release annotated tags"
    assert all(f.severity == FAIL for f in bp3)
    # one per release tag name (v0.90/v0.91/v1.0)
    tags = {f.object.get("tag") for f in bp3}
    assert {"v0.90", "v0.91", "v1.0"} <= tags


def test_defective_exit_code_is_fail(report):
    assert report.exit_code() == 1


# -- clean regeneration is fully green ---------------------------------------

def test_clean_repo_all_green(wildlife):
    report = run_validation(wildlife["clean"], "strict-P", "build",
                            manifests=wildlife["manifests"])
    fails = [f for f in report.findings if f.severity == FAIL]
    assert not fails, "clean repo FAILs:\n" + "\n".join(
        f"  {f.check_id}: {f.message_technical or f.message_plain}" for f in fails)
    assert report.exit_code() == 0


def test_clean_repo_tf_all_green(wildlife):
    report = run_validation(wildlife["clean"], "strict-P", "build",
                            manifests=wildlife["manifests"])
    for cid in ("TF-1", "TF-2", "TF-3", "TF-4", "TF-5"):
        assert not [f for f in report.findings if f.check_id == cid], \
            f"{cid} fired on clean repo"
