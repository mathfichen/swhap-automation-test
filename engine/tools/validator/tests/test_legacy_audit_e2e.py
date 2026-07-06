"""End-to-end LEGACY-PROFILE precision audit (AX5 / T10), CI-reproducible.

The original AX5 audit ran ONCE, live, against two REAL published acquisitions
(Unipisa/CMM-Workbench — a wrapper-directory defect; mathfichen/chainage_de_contour
— a non-canonical-CSV-dialect case) that exist only in ephemeral ``/tmp``. That
"3 false failures -> 0 after FIX-1/FIX-2, genuine defects preserved" evidence
could not be re-run from a clean checkout. This harness rebuilds the two defect
SHAPES as synthetic, license-clean fixture workbenches (``fixtures/legacy/
build.py``) and re-derives the same precision result in the normal pytest suite:

  * the tolerated legacy dialects produce ZERO false FAILs under the legacy
    profile (the FALSE CSV-1/CM-1 that FIX-1/FIX-2 removed), AND
  * the genuine defects (BP-5 wrapper; CM-2 bogus @context) are still surfaced as
    FAIL-classified findings (no blanket suppression) — while every finding is
    ``enforced: false`` and the run exits 0 (validator-report §4.2).

See ``fixtures/legacy/README.md`` for the mapping to the real AX5 targets and the
one-time live-audit evidence this harness stands in for.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re

import pytest

from swhap_validate import report as R
from swhap_validate.cli import run_validation

HERE = os.path.dirname(__file__)
LEGACY_DIR = os.path.abspath(os.path.join(HERE, "..", "..", "..",
                                          "fixtures", "legacy"))


def _load_legacy_build():
    spec = importlib.util.spec_from_file_location(
        "swhap_legacy_fixtures_build", os.path.join(LEGACY_DIR, "build.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def legacy_build():
    return _load_legacy_build()


@pytest.fixture(scope="module")
def legacy_fixtures(legacy_build, tmp_path_factory):
    """Build both synthetic legacy workbenches once for the module."""
    root = tmp_path_factory.mktemp("legacy")
    repos = {}
    for name, builder, *_ in legacy_build.FIXTURES:
        repos[name] = builder(os.path.join(str(root), name))
    return repos


@pytest.fixture(scope="module")
def legacy_index():
    with open(os.path.join(LEGACY_DIR, "index.json"), encoding="utf-8") as fh:
        return json.load(fh)


def _fails(rep):
    return [f for f in rep.findings if f.severity == R.FAIL]


def _fail_ids(rep):
    return sorted({f.check_id for f in _fails(rep)})


# --- the precision result: zero false failures, genuine defects preserved --- #

def test_unipisa_cmm_legacy_zero_false_failures_genuine_bp5_preserved(
        legacy_fixtures):
    """Stands in for Unipisa/CMM-Workbench. Tolerated: unipisa CSV dialect
    (was false CSV-1) + root codemeta (was false CM-1). Genuine: BP-5 wrapper."""
    rep = run_validation(legacy_fixtures["unipisa-cmm"], "legacy", "build")
    fails = _fail_ids(rep)
    # ZERO false failures on the tolerated-dialect parts.
    assert not [c for c in fails if c.startswith("CSV-")], \
        f"tolerated unipisa CSV dialect must not FAIL under legacy; got {fails}"
    assert not [c for c in fails if c.startswith("CM-")], \
        f"tolerated root codemeta must not FAIL under legacy; got {fails}"
    # Genuine wrapper defect still surfaced (no blanket suppression).
    assert "BP-5" in fails, f"genuine BP-5 wrapper must still FAIL; got {fails}"
    # Legacy posture: every finding report-only, run exits 0.
    assert all(f.enforced is False for f in rep.findings)
    assert rep.exit_code() == 0


def test_guide_chainage_legacy_zero_false_failures_genuine_cm2_preserved(
        legacy_fixtures):
    """Stands in for mathfichen/chainage_de_contour. Tolerated: guide
    `date original` CSV dialect (was false CSV-1). Genuine: CM-2 bogus @context."""
    rep = run_validation(legacy_fixtures["guide-chainage"], "legacy", "build")
    fails = _fail_ids(rep)
    assert not [c for c in fails if c.startswith("CSV-")], \
        f"tolerated guide CSV dialect must not FAIL under legacy; got {fails}"
    # Root codemeta is present (CM-1 tolerated) but its @context is bogus (CM-2).
    assert "CM-1" not in fails, "root codemeta presence must satisfy CM-1 in legacy"
    assert "CM-2" in fails, f"genuine CM-2 bogus @context must still FAIL; got {fails}"
    assert all(f.enforced is False for f in rep.findings)
    assert rep.exit_code() == 0


def test_no_blanket_suppression_every_legacy_fail_is_a_declared_genuine_defect(
        legacy_fixtures, legacy_index):
    """The audit's headline claim: under the legacy profile, the ONLY FAILs are
    the genuine defects each fixture declares in index.json. No false failures,
    and the suppression of dialects is not a blanket one (genuine FAILs remain)."""
    declared = {f["name"]: {re.match(r"([A-Z]{2,5}-[0-9]+[a-z]?)", d).group(1)
                            for d in f["genuine_defects"]}
                for f in legacy_index["fixtures"]}
    for name, repo in legacy_fixtures.items():
        rep = run_validation(repo, "legacy", "build")
        fails = set(_fail_ids(rep))
        assert fails == declared[name], (
            f"{name}: legacy FAIL set {sorted(fails)} != declared genuine "
            f"defects {sorted(declared[name])}")


# --- detection NOT weakened: the tolerance is legacy-scoped ------------------ #

def test_strict_profile_still_fails_the_tolerated_dialects(legacy_fixtures):
    """Under strict-P the same legacy dialects are real defects: CSV-1 FAILs for
    both, and the root-codemeta fixture FAILs CM-1 (root fallback is legacy-only).
    This proves the legacy tolerance is a scoped acceptance, never a global
    weakening of the checks."""
    for name, repo in legacy_fixtures.items():
        rep = run_validation(repo, "strict-P", "build")
        fails = _fail_ids(rep)
        assert "CSV-1" in fails, f"{name}: legacy dialect must FAIL CSV-1 in strict"
        assert rep.exit_code() == 1
    # The unipisa fixture's root codemeta also FAILs CM-1 under strict.
    rep = run_validation(legacy_fixtures["unipisa-cmm"], "strict-P", "build")
    assert "CM-1" in _fail_ids(rep), "root codemeta must FAIL CM-1 in strict"


# --- the fixtures are reproducible (CI determinism gate) --------------------- #

def test_legacy_fixtures_reproduce_pinned_manifest(legacy_build):
    assert legacy_build.cmd_check() == 0


def test_legacy_fixtures_tree_sha_matches_index(legacy_build, legacy_index,
                                                tmp_path):
    sums = legacy_build.build_all(str(tmp_path))
    by_name = {f["name"]: f["tree_sha"] for f in legacy_index["fixtures"]}
    assert sums == by_name


# --- legacy reports are schema-valid ---------------------------------------- #

def test_legacy_reports_schema_valid(legacy_fixtures, validate_report):
    for repo in legacy_fixtures.values():
        rep = run_validation(repo, "legacy", "build")
        validate_report(rep)


# --- GAP 2: every emitted finding carries a non-empty human-readable message - #

def _scan_empty_messages(rep):
    """Return findings whose serialized human-readable message is empty."""
    bad = []
    for f in rep.findings:
        d = f.to_dict()
        mp = d.get("message_plain")
        mt = d.get("message_technical")
        plain_empty = (mp is None) or (str(mp).strip() == "")
        tech_empty = (mt is None) or (str(mt).strip() == "")
        if plain_empty or (plain_empty and tech_empty):
            bad.append((f.check_id, f.severity, repr(mp), repr(mt)))
    return bad


def test_no_finding_serializes_with_empty_message_legacy(legacy_fixtures):
    """No emitted finding (the defective legacy fixtures, which exercise CM-4,
    CSV-7, BP-5, CM-2 …) may serialize with an empty message_plain — that would
    leave a forge-visible finding self-describing only by severity+id."""
    for name, repo in legacy_fixtures.items():
        for profile in ("legacy", "strict-P", "strict-G"):
            rep = run_validation(repo, profile, "build")
            bad = _scan_empty_messages(rep)
            assert not bad, f"{name} [{profile}] empty-message findings: {bad}"


def test_no_finding_serializes_with_empty_message_wildlife(wildlife):
    """Same invariant across the real Wild_LIFE clean + defective exemplars under
    every profile — a representative run that exercises the full battery."""
    for key in ("clean", "defective"):
        for profile in ("legacy", "strict-P", "strict-G"):
            rep = run_validation(wildlife[key], profile, "build",
                                 manifests=wildlife["manifests"])
            bad = _scan_empty_messages(rep)
            assert not bad, f"{key} [{profile}] empty-message findings: {bad}"
