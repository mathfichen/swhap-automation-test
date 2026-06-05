"""End-to-end TF gate THROUGH the real entrypoint.

The blocker this guards against: the M1a tree-fidelity battery being reachable
only via an in-process call with test-fabricated manifests. Here we run the
literal ``bash check_swhap.sh`` against a real-SourceCode-bearing working repo
built FROM THE PINNED BUNDLE (not a reconstruction), pointing ``--manifests`` at
the real committed tarball-derived oracles, and assert the gate fires on the
real published corruption — at the entrypoint, with a schema-valid report.
"""
import json
import os
import subprocess
import sys

import pytest
from jsonschema import Draft202012Validator

from conftest import VALIDATOR_ROOT

SPECS_SCHEMA = os.path.abspath(os.path.join(
    VALIDATOR_ROOT, "..", "..", "specs", "validator-report.schema.json"))


def _run_entrypoint(workdir, manifests_dir, *extra):
    sh = os.path.join(VALIDATOR_ROOT, "check_swhap.sh")
    env = dict(os.environ, SWHAP_PYTHON=sys.executable)
    return subprocess.run(
        ["bash", sh, "--profile", "strict-P", "--workdir", workdir,
         "--manifests", manifests_dir, "--report", "-", *extra],
        capture_output=True, text=True, env=env)


@pytest.fixture(scope="module")
def entrypoint(wildlife):
    p = _run_entrypoint(wildlife["defective"], wildlife["manifests_dir"])
    assert p.returncode != 0, f"gate must be red; stderr={p.stderr}"
    doc = json.loads(p.stdout)
    return p, doc


def test_entrypoint_exit_nonzero(entrypoint):
    p, doc = entrypoint
    assert p.returncode == 1
    assert doc["summary"]["exit_code"] == 1


def test_entrypoint_report_validates_against_specs_schema(entrypoint):
    _p, doc = entrypoint
    with open(SPECS_SCHEMA, encoding="utf-8") as fh:
        schema = json.load(fh)
    errors = sorted(Draft202012Validator(schema).iter_errors(doc),
                    key=lambda e: list(e.path))
    assert not errors, "schema errors:\n" + "\n".join(
        f"  {list(e.path)}: {e.message}" for e in errors)


def _tf(doc, check_id, release):
    return [f for f in doc["findings"]
            if f["check_id"] == check_id and f["object"].get("release") == release]


def test_entrypoint_tf_red_on_091_and_10(entrypoint):
    _p, doc = entrypoint
    tf1_091 = _tf(doc, "TF-1", "0.91")
    assert tf1_091 and tf1_091[0]["object"]["extra_count"] == 19
    tf2_091 = _tf(doc, "TF-2", "0.91")
    assert tf2_091 and tf2_091[0]["object"]["mismatch_count"] == 3

    tf1_10 = _tf(doc, "TF-1", "1.0")
    assert tf1_10 and tf1_10[0]["object"]["extra_count"] == 1145
    tf2_10 = _tf(doc, "TF-2", "1.0")
    assert tf2_10 and "LICENSE" in tf2_10[0]["message_technical"]

    tf3 = [f for f in doc["findings"]
           if f["check_id"] == "TF-3" and f["object"].get("to") in ("0.91", "1.0")]
    assert {f["object"]["to"] for f in tf3} == {"0.91", "1.0"}
    assert all(f["object"]["actual_deletions"] == 0 for f in tf3)


def test_entrypoint_v090_no_tf_finding(entrypoint):
    _p, doc = entrypoint
    for cid in ("TF-1", "TF-2", "TF-3", "TF-4", "TF-5"):
        assert not _tf(doc, cid, "0.90"), f"{cid} fired on clean 0.90"


def test_entrypoint_tf_runs_not_skipped(entrypoint):
    """TF-1..5 must appear in checks_run (reachable), not in checks_skipped."""
    _p, doc = entrypoint
    skipped = {s["id"] for s in doc["run"]["checks_skipped"]}
    for cid in ("TF-1", "TF-2", "TF-3", "TF-4", "TF-5"):
        assert cid in doc["run"]["checks_run"], f"{cid} did not run"
        assert cid not in skipped, f"{cid} was skipped at the entrypoint"
