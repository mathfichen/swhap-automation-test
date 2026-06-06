"""M1 exit gate, as an executable test (exemplar-pilot T11).

Runs the committed Model-P regeneration end-to-end into temp dirs and asserts the
acceptance criteria that gate the close of milestone M1:

  * validator strict-P exits 0 (green) over all four release tags;
  * D4 — rebuilding twice from the committed inputs yields byte-identical commit
    AND annotated-tag object hashes (reproducibility is real, not a constant);
  * journal coverage — JC-1a finds no uncovered curated object;
  * PI-1 is CLEARED by the journaled curator-email opt-in (ran, no finding).

The validator is exercised through its documented entrypoint
``tools/validator/check_swhap.sh`` (argv-only), exactly as the gate runs in CI.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))


def _load_regen():
    spec = importlib.util.spec_from_file_location(
        "wildlife_regen", os.path.join(HERE, "regen.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


regen_mod = _load_regen()
CHECK_SH = os.path.join(regen_mod.TOOLKIT, "tools", "validator", "check_swhap.sh")


@pytest.fixture(scope="module")
def two_runs(tmp_path_factory):
    """Regenerate twice into independent dirs (the D4 evidence)."""
    a = regen_mod.regen(str(tmp_path_factory.mktemp("runA")))
    b = regen_mod.regen(str(tmp_path_factory.mktemp("runB")))
    return a, b


@pytest.fixture(scope="module")
def validate_p_report(two_runs, tmp_path_factory):
    info = two_runs[0]
    report_path = str(tmp_path_factory.mktemp("rpt") / "report-P.json")
    env = dict(os.environ, SWHAP_PYTHON=sys.executable)
    proc = subprocess.run(
        ["bash", CHECK_SH,
         "--profile", "strict-P", "--gate", "build",
         "--workdir", info["validate_p"],
         "--manifests", info["manifests"],
         "--report", report_path,
         "--reference-date", info["reference_date"]],
        env=env, capture_output=True, text=True)
    with open(report_path, encoding="utf-8") as fh:
        report = json.load(fh)
    return proc, report


def test_validator_strict_p_green(validate_p_report):
    proc, report = validate_p_report
    assert proc.returncode == 0, f"check_swhap.sh exited {proc.returncode}\n{proc.stderr}"
    assert report["summary"]["exit_code"] == 0
    assert report["summary"]["fail"] == 0


def test_all_four_releases_checked(validate_p_report):
    _proc, report = validate_p_report
    assert set(report["run"]["refs_checked"]) >= {
        "refs/tags/v0.90", "refs/tags/v0.91", "refs/tags/v1.0", "refs/tags/v1.02"}


def test_d4_rebuild_twice_identical(two_runs):
    a, b = two_runs
    assert a["commit_oids"] == b["commit_oids"]
    assert a["tag_oids"] == b["tag_oids"]
    assert a["branch_tip"] == b["branch_tip"]
    # and all four objects are real, distinct SHAs (not a degenerate constant)
    assert len(set(a["commit_oids"])) == 4
    assert len(set(a["tag_oids"])) == 4


def test_journal_coverage_jc1a(validate_p_report):
    _proc, report = validate_p_report
    assert "JC-1a" in report["run"]["checks_run"]
    assert [f for f in report["findings"] if f["check_id"] == "JC-1a"] == []


def test_pi1_cleared_by_opt_in(validate_p_report):
    _proc, report = validate_p_report
    assert "PI-1" in report["run"]["checks_run"]
    assert [f for f in report["findings"] if f["check_id"] == "PI-1"] == []
