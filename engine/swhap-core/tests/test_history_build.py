"""History builder (T7) — bit-reproducibility (D4), both branch models, purity,
.emptydir handling, symlinks, pre-1970 dates, plan drift, scratch refs, ref-policy,
and journal coverage + schema conformance.

The headline test builds a synthetic 3-release acquisition **twice** (two fresh
workbenches, mimicking two machines) and asserts identical commit AND annotated-tag
object SHA-1s.
"""

from __future__ import annotations

import json
import os
import subprocess

import pytest

from swhap_core.cli import main
from swhap_core.errors import CsvContractError, HistoryError
from swhap_core.gitio import GitRunner
from swhap_core.history import build_model, do_apply, do_build, do_plan, render_g, render_p
from swhap_core.model import CurationTimestamp

jsonschema = pytest.importorskip("jsonschema")

CURATION = CurationTimestamp(1781082136, "+0000")

_CSV = (
    "directory name,date,author name,author email,curator name,curator email,release tag,commit message\n"
    "0.90,1993-08-09,Wild_LIFE authors,wildlife-authors@noreply.example.org,Roberto Di Cosmo,roberto@dicosmo.org,v0.90,Wild_LIFE 0.90 first public release\n"
    "0.91,1993-08-09,Wild_LIFE authors,wildlife-authors@noreply.example.org,Roberto Di Cosmo,roberto@dicosmo.org,v0.91,Wild_LIFE 0.91\n"
    "1.0,1994-03-24,Wild_LIFE authors,wildlife-authors@noreply.example.org,Roberto Di Cosmo,roberto@dicosmo.org,v1.0,\"Wild_LIFE 1.0\n\nCo-authored-by: Peter Van Roy <pvr@noreply.example.org>\"\n"
)


def _make_workbench(root: str, *, with_symlink: bool = True) -> str:
    os.makedirs(os.path.join(root, "metadata"))
    sc = os.path.join(root, "source_code")
    # three releases with distinct content; 1.0 has an empty dir + a symlink.
    contents = {
        "0.90": {"README": b"life 0.90\n", "src/life.ml": b"let x = 1\n"},
        "0.91": {"README": b"life 0.91\n", "src/life.ml": b"let x = 2\n"},
        "1.0": {"README": b"life 1.0\n", "src/life.ml": b"let x = 3\n"},
    }
    for d, files in contents.items():
        for rel, data in files.items():
            full = os.path.join(sc, d, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "wb") as fh:
                fh.write(data)
    os.makedirs(os.path.join(sc, "1.0", "empty"))  # preserved via .emptydir
    if with_symlink:
        os.symlink("../README", os.path.join(sc, "1.0", "src", "README.link"))
    with open(os.path.join(root, "metadata", "version_history.csv"), "w") as fh:
        fh.write(_CSV)
    with open(os.path.join(root, "README.md"), "wb") as fh:
        fh.write(b"# Wild_LIFE workbench\n")
    subprocess.run(["git", "init", "-q", root], check=True)
    return root


@pytest.fixture
def workbench(tmp_path):
    return _make_workbench(str(tmp_path / "wb"))


def _oids(result):
    return (result.commit_oids(), result.tag_oids())


# --- D4 bit-reproducibility -------------------------------------------------
@pytest.mark.parametrize("model", ["P", "G"])
def test_double_build_identical_commit_and_tag_hashes(tmp_path, model):
    a = _make_workbench(str(tmp_path / "a"))
    b = _make_workbench(str(tmp_path / "b"))
    _, ra = do_build(a, model, CURATION, run_id="00000000000000000000000001")
    _, rb = do_build(b, model, CURATION, run_id="00000000000000000000000002")  # different run-id
    assert _oids(ra) == _oids(rb)  # identical commit AND tag SHA-1s
    assert ra.branch_ref != rb.branch_ref  # run-id only changes ref names


def test_models_share_model_but_render_differently(workbench):
    model = build_model(workbench, curation_ts=CURATION)
    p = render_p(model)
    g = render_g(model)
    assert [s.dirname for s in p.steps] == [s.dirname for s in g.steps] == ["0.90", "0.91", "1.0"]
    # same model, different trees → different commit objects
    _, rp = do_apply(workbench, run_id="00000000000000000000000010", model_name="P", curation_ts=CURATION, journal=False)
    wb2 = _make_workbench(str(workbench) + "-g")
    _, rg = do_apply(wb2, run_id="00000000000000000000000011", model_name="G", curation_ts=CURATION, journal=False)
    assert rp.commit_oids() != rg.commit_oids()


# --- Model P: orphan + purity -----------------------------------------------
def test_model_p_orphan_root_and_pure(workbench):
    _, result = do_build(workbench, "P", CURATION, run_id="0000000000000000000000000P")
    git = GitRunner(workbench)
    root_commit = result.commits[0]["commit"]
    parents = git.run(["rev-list", "--parents", "-n", "1", root_commit]).decode().split()
    assert len(parents) == 1  # orphan: root has no parent
    # subsequent commits are chained (linear history on the orphan branch)
    assert result.commits[1]["parent"] == result.commits[0]["commit"]
    # purity: no commit tree carries metadata/ or raw_materials/; source at root
    for c in result.commits:
        top = set(git.ls_tree_names(c["commit"]))
        assert "metadata" not in top
        assert "raw_materials" not in top
        assert "source_code" not in top
        assert "README" in top  # source file at the root


# --- Model G: source on default branch --------------------------------------
def test_model_g_source_with_metadata_cumulative(workbench):
    _, result = do_build(workbench, "G", CURATION, run_id="0000000000000000000000000G")
    git = GitRunner(workbench)
    for c in result.commits:
        top = set(git.ls_tree_names(c["commit"]))
        assert "metadata" in top and "source_code" in top
    # source under source_code/<dirname>/, cumulative on the tip
    tip_sc = set(git.ls_tree_names(result.branch_tip + ":source_code"))
    assert tip_sc == {"0.90", "0.91", "1.0"}
    first_sc = set(git.ls_tree_names(result.commits[0]["commit"] + ":source_code"))
    assert first_sc == {"0.90"}  # cumulative grows from the first release
    # metadata/version_history.csv present
    assert "version_history.csv" in git.ls_tree_names(result.branch_tip + ":metadata")
    # chained (non-orphan semantics): release 1 parents release 0
    assert result.commits[1]["parent"] == result.commits[0]["commit"]


# --- .emptydir handling -----------------------------------------------------
def test_emptydir_bijection(workbench):
    _, result = do_build(workbench, "P", CURATION, run_id="0000000000000000000000000E")
    git = GitRunner(workbench)
    tip = result.branch_tip  # the 1.0 release
    names = git.run(["ls-tree", "-r", "--name-only", tip]).decode().splitlines()
    assert "empty/.emptydir" in names  # empty dir preserved
    # bijection: no .emptydir marker inside a non-empty directory (src has files)
    assert "src/.emptydir" not in names
    assert not any(n.endswith("/.emptydir") and n != "empty/.emptydir" for n in names)


def test_symlink_preserved_as_mode_120000(workbench):
    _, result = do_build(workbench, "P", CURATION, run_id="0000000000000000000000000S")
    git = GitRunner(workbench)
    tip = result.branch_tip
    out = git.run(["ls-tree", "-r", tip]).decode().splitlines()
    line = next(x for x in out if x.endswith("src/README.link"))
    assert line.split()[0] == "120000"  # symlink mode


# --- pre-1970 (negative epoch, crit-M3) -------------------------------------
def test_pre1970_negative_epoch_faithful(tmp_path):
    root = str(tmp_path / "softi")
    os.makedirs(os.path.join(root, "metadata"))
    os.makedirs(os.path.join(root, "source_code", "Softi-1968"))
    with open(os.path.join(root, "source_code", "Softi-1968", "cep.txt"), "wb") as fh:
        fh.write(b"softi for CEP\n")
    with open(os.path.join(root, "metadata", "version_history.csv"), "w") as fh:
        fh.write(
            "directory name,date,author name,author email,curator name,curator email,release tag,commit message\n"
            "Softi-1968,1968-07-01,Softi authors,softi-authors@noreply.example.org,Example Curator,example-curator@noreply.example.org,v1968,Softi pre-epoch\n"
        )
    subprocess.run(["git", "init", "-q", root], check=True)
    _, result = do_build(root, "P", CURATION, run_id="0000000000000000000000001A")
    git = GitRunner(root)
    author_line = git.run(["cat-file", "-p", result.commits[0]["commit"]]).decode().splitlines()[1]
    assert " -47433600 +0000" in author_line  # 1968-07-01 stored as negative epoch
    # reproducible too
    root2 = str(tmp_path / "softi2")
    os.makedirs(os.path.join(root2, "metadata"))
    os.makedirs(os.path.join(root2, "source_code", "Softi-1968"))
    with open(os.path.join(root2, "source_code", "Softi-1968", "cep.txt"), "wb") as fh:
        fh.write(b"softi for CEP\n")
    with open(os.path.join(root2, "metadata", "version_history.csv"), "w") as fh:
        fh.write(
            "directory name,date,author name,author email,curator name,curator email,release tag,commit message\n"
            "Softi-1968,1968-07-01,Softi authors,softi-authors@noreply.example.org,Example Curator,example-curator@noreply.example.org,v1968,Softi pre-epoch\n"
        )
    subprocess.run(["git", "init", "-q", root2], check=True)
    _, result2 = do_build(root2, "P", CURATION, run_id="0000000000000000000000001B")
    assert _oids(result) == _oids(result2)


# --- plan determinism + drift -----------------------------------------------
def test_plan_is_deterministic_and_touches_no_refs(workbench):
    p1, b1 = do_plan(workbench, "P", CURATION, journal=False)
    p2, b2 = do_plan(workbench, "P", CURATION, journal=False)
    assert b1 == b2  # byte-identical plan.json
    git = GitRunner(workbench)
    # no candidate/scratch refs created by planning
    assert git.rev_parse("refs/heads/candidate/P/x") is None
    refs = git.run(["for-each-ref", "--format=%(refname)"]).decode().splitlines()
    assert not any(r.startswith(("refs/heads/candidate", "refs/tags/candidate")) for r in refs)


def test_plan_drift_detected(workbench, tmp_path):
    plan_file = str(tmp_path / "plan.json")
    do_plan(workbench, "P", CURATION, plan_out=plan_file, journal=False)
    # mutate the inspected source after planning
    with open(os.path.join(workbench, "source_code", "1.0", "README"), "ab") as fh:
        fh.write(b"tampered\n")
    with pytest.raises(HistoryError) as ei:
        do_apply(workbench, run_id="0000000000000000000000000D", plan_path=plan_file, journal=False)
    assert ei.value.code == "HB-PLAN-DRIFT"
    assert ei.value.exit_code == 13


# --- scratch refs (rebuild-compare; not journaled) --------------------------
def test_scratch_matches_candidate_and_is_not_journaled(workbench):
    _, cand = do_build(workbench, "P", CURATION, run_id="0000000000000000000000000C")
    journal_path = os.path.join(workbench, "metadata", "journal.jsonl")
    before = len(open(journal_path).read().splitlines())
    _, scratch = do_apply(workbench, run_id="0000000000000000000000000R", model_name="P", curation_ts=CURATION, scratch=True)
    after = len(open(journal_path).read().splitlines())
    assert _oids(cand) == _oids(scratch)  # same objects (D4 rebuild-compare primitive)
    assert scratch.branch_ref.startswith("refs/scratch/")
    assert before == after  # scratch runs append nothing to the ledger


# --- ref-policy guard -------------------------------------------------------
def test_ref_policy_guard_refuses_protected_refs(workbench):
    git = GitRunner(workbench)
    for bad in ["refs/heads/SourceCode", "refs/tags/v1.0", "refs/heads/main", "refs/heads/ai/proposal/x"]:
        with pytest.raises(HistoryError) as ei:
            git.update_ref(bad, "0" * 40)
        assert ei.value.code == "HB-REF-POLICY"
        assert ei.value.exit_code == 14


# --- journal coverage + schema ----------------------------------------------
def test_journal_covers_objects_and_validates(workbench):
    _, result = do_build(workbench, "P", CURATION, run_id="0000000000000000000000000J")
    journal_path = os.path.join(workbench, "metadata", "journal.jsonl")
    entries = [json.loads(line) for line in open(journal_path)]
    actions = [e["action"] for e in entries]
    assert actions == ["genesis", "curation-timestamp", "plan", "apply"]

    # schema conformance
    here = os.path.dirname(__file__)
    schema_path = os.path.abspath(os.path.join(here, "..", "..", "specs", "journal-entry.schema.json"))
    validator = jsonschema.Draft202012Validator(json.load(open(schema_path)))
    for e in entries:
        errs = [err.message for err in validator.iter_errors(e)]
        assert not errs, (e["action"], errs)

    # coverage: every commit + tag object appears in some outputs[].git_object
    journaled = {
        o["git_object"]
        for e in entries
        for o in e.get("outputs", [])
        if "git_object" in o
    }
    for c in result.commit_oids():
        assert c in journaled
    for t in result.tag_oids():
        assert t in journaled

    # chain self-check passes
    from swhap_core.journal import Ledger

    Ledger(journal_path).verify()


def test_cli_build_end_to_end(tmp_path, capsys):
    root = _make_workbench(str(tmp_path / "cliwb"))
    rc = main([
        "build", "--workbench", root, "--model", "P",
        "--curation-epoch", "1781082136", "--run-id", "0000000000000000000000000K",
    ])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["phase"] == "apply"
    assert out["model"] == "P"
    git = GitRunner(root)
    assert git.rev_parse("refs/heads/candidate/P/0000000000000000000000000K") == out["branch_tip"]


def test_cli_build_requires_curation_epoch(tmp_path, capsys):
    root = _make_workbench(str(tmp_path / "noepoch"))
    rc = main(["build", "--workbench", root, "--model", "P"])
    assert rc == 2  # usage: no wall-clock fallback (D4)


# --- D2: the single canonical parser rejects bad CSV at INGESTION ------------
# The builder routes through swhap_core.vhcsv (profile="canonical") as the SOLE
# parser. Tag-grammar (§6 / CSV-TAG = validator CSV-4), field-allowlist (§8 /
# CSV-FIELD = validator CSV-6) and §5.3 email syntax are therefore enforced at
# plan time, before any git plumbing runs — never deferred to a late, misleading
# HB-PLAN-DRIFT inside git. The source trees here are always well-formed, so the
# ONLY thing that can fail is the CSV contract.
_ONE_ROW_CSV = (
    "directory name,date,author name,author email,curator name,curator email,release tag,commit message\n"
    "0.90,1993-08-09,Wild_LIFE authors,{email},Roberto Di Cosmo,roberto@dicosmo.org,{tag},Wild_LIFE 0.90\n"
)


def _make_one_row_wb(root, *, tag="v0.90", email="wildlife-authors@noreply.example.org"):
    os.makedirs(os.path.join(root, "metadata"))
    sc = os.path.join(root, "source_code", "0.90")
    os.makedirs(sc)
    with open(os.path.join(sc, "README"), "wb") as fh:
        fh.write(b"life 0.90\n")
    with open(os.path.join(root, "metadata", "version_history.csv"), "w") as fh:
        fh.write(_ONE_ROW_CSV.format(tag=tag, email=email))
    subprocess.run(["git", "init", "-q", root], check=True)
    return root


def test_injection_tag_rejected_at_plan_not_plan_drift(tmp_path):
    # An argv-injection-shaped release tag is rejected up front as a CSV-contract
    # FAIL (exit 12) by the canonical vhcsv parser — NOT deferred to HB-PLAN-DRIFT
    # (exit 13) inside git, which is what the weaker builder-local reader did.
    wb = _make_one_row_wb(str(tmp_path / "inj"), tag="--upload-pack=HEAD")
    with pytest.raises(CsvContractError) as ei:
        do_plan(wb, "P", CURATION, journal=False)
    assert ei.value.exit_code == 12
    assert ei.value.code != "HB-PLAN-DRIFT"
    # `git check-ref-format refs/tags/--upload-pack=HEAD` actually *accepts* this
    # string, so the §6.1 tag grammar is clean; the leading '-' is caught by the
    # §8.1 field allowlist (validator CSV-6 / CSV-FIELD) instead.
    assert ei.value.code == "CSV-FIELD"
    # the failure happens at ingestion, so no candidate/scratch refs were created
    git = GitRunner(wb)
    refs = git.run(["for-each-ref", "--format=%(refname)"]).decode().splitlines()
    assert not any(r.startswith(("refs/heads/candidate", "refs/tags/candidate")) for r in refs)


def test_tag_grammar_violation_is_csv_tag_at_plan(tmp_path):
    # A genuine §6.1 tag-grammar violation (a space is a check-ref-format forbidden
    # char) is CSV-TAG (validator CSV-4), raised at plan time, not at apply time.
    wb = _make_one_row_wb(str(tmp_path / "badtag"), tag="v 1.0")
    with pytest.raises(CsvContractError) as ei:
        do_plan(wb, "P", CURATION, journal=False)
    assert ei.value.code == "CSV-TAG"
    assert ei.value.exit_code == 12


def test_bad_email_rejected_at_plan(tmp_path):
    # §5.3 bare addr-spec is now enforced at ingestion (the old builder-local reader
    # never validated emails). A malformed author email fails CSV-FIELD at plan time.
    wb = _make_one_row_wb(str(tmp_path / "bademail"), email="not-an-email")
    with pytest.raises(CsvContractError) as ei:
        do_plan(wb, "P", CURATION, journal=False)
    assert ei.value.code == "CSV-FIELD"
    assert ei.value.exit_code == 12
