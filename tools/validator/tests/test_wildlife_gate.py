"""M1a RED gate: every entry of the exemplar defect register
(exemplar-pilot §4.2 / followup-2) is caught by a NAMED test asserting the
specific check ID fires on the (reconstructed) published exemplar; v0.90 is
green and the clean regeneration is fully green.
"""
import pytest

from swhap_validate.cli import run_validation
from swhap_validate.report import FAIL


def _run_defective(wildlife, **kw):
    return run_validation(wildlife["defective"], "strict-P", "build",
                          manifests=wildlife["ordered"], **kw)


def _by_check(report, check_id):
    return [f for f in report.findings if f.check_id == check_id]


def _tf_for_tag(report, check_id, tag):
    return [f for f in _by_check(report, check_id) if f.object.get("tag") == tag]


@pytest.fixture(scope="module")
def defective_report(wildlife):
    return _run_defective(wildlife)


# -- TF battery --------------------------------------------------------------

def test_wildlife_v090_green(defective_report):
    """GREEN-v090-tree: v0.90 is the only faithful tag — no TF finding."""
    assert not _tf_for_tag(defective_report, "TF-1", "v0.90")
    assert not _tf_for_tag(defective_report, "TF-2", "v0.90")


def test_wildlife_v091_red_22_stale_entries(defective_report):
    """RED-v091-extras (TF-1, 19) + RED-v091-stale-blobs (TF-2, 3) = 22."""
    tf1 = _tf_for_tag(defective_report, "TF-1", "v0.91")
    assert tf1 and tf1[0].severity == FAIL
    assert tf1[0].object["extra_count"] == 19
    tf2 = _tf_for_tag(defective_report, "TF-2", "v0.91")
    assert tf2 and tf2[0].object["mismatch_count"] == 3


def test_wildlife_v10_red_1146_overlay_and_license_year(defective_report):
    """RED-v10-extras (TF-1, 1145) + RED-v10-license-stale (TF-2, LICENSE)."""
    tf1 = _tf_for_tag(defective_report, "TF-1", "v1.0")
    assert tf1 and tf1[0].object["extra_count"] == 1145
    tf2 = _tf_for_tag(defective_report, "TF-2", "v1.0")
    assert tf2, "stale LICENSE must trip TF-2"
    assert "LICENSE" in tf2[0].message_technical


def test_wildlife_v091_to_v10_red_zero_deletions(defective_report):
    """RED-v10-no-deletions: the v0.91→v1.0 diff has zero D entries (TF-3)."""
    tf3 = [f for f in _by_check(defective_report, "TF-3")
           if f.object.get("from") == "v0.91" and f.object.get("to") == "v1.0"]
    assert tf3 and tf3[0].severity == FAIL
    assert tf3[0].object["actual_deletions"] == 0
    assert tf3[0].object["expected_deletions"] > 0


def test_wildlife_v10_emptydir_bijection_green(defective_report):
    """GREEN-v10-emptydir: 4 ⇔ 4 bijection holds — no TF-4 finding for v1.0."""
    assert not _tf_for_tag(defective_report, "TF-4", "v1.0")


def test_wildlife_v10_symlinks_4_green(defective_report):
    """GREEN-v10-symlinks: 4 symlinks mode 120000 — no TF-5 finding for v1.0."""
    assert not _tf_for_tag(defective_report, "TF-5", "v1.0")


# -- metadata defects on the published main ----------------------------------

def test_csv_header_red_on_published_exemplar(defective_report):
    """RED-csv-header: ad-hoc 7-column header → CSV-1."""
    cs = _by_check(defective_report, "CSV-1")
    assert cs and cs[0].severity == FAIL


def test_codemeta_bogus_context_red_on_published_exemplar(defective_report):
    """RED-codemeta-context: sciencecodemeta URL → CM-2."""
    cm = _by_check(defective_report, "CM-2")
    assert cm and cm[0].severity == FAIL
    assert any("sciencecodemeta" in (f.object.get("context") or "")
               for f in cm)


def test_journal_coverage_red_on_published_exemplar(defective_report):
    """RED-journal-coverage: boilerplate 2-row journal → JC-1a."""
    jc = _by_check(defective_report, "JC-1a")
    assert jc and jc[0].severity == FAIL
    # the boilerplate references none of the curated object hashes
    assert jc[0].object["uncovered_count"] == jc[0].object["total"]


# -- defect register, exhaustively (every entry names its catching check) -----

DEFECT_REGISTER = [
    ("RED-v091-extras", "TF-1", {"tag": "v0.91"}),
    ("RED-v091-stale-blobs", "TF-2", {"tag": "v0.91"}),
    ("RED-v10-extras", "TF-1", {"tag": "v1.0"}),
    ("RED-v10-no-deletions", "TF-3", {"from": "v0.91", "to": "v1.0"}),
    ("RED-v10-license-stale", "TF-2", {"tag": "v1.0"}),
    ("RED-codemeta-context", "CM-2", {}),
    ("RED-csv-header", "CSV-1", {}),
    ("RED-journal-coverage", "JC-1a", {}),
]


@pytest.mark.parametrize("defect_id,check_id,match", DEFECT_REGISTER,
                         ids=[d[0] for d in DEFECT_REGISTER])
def test_defect_register_entry_caught(defective_report, defect_id, check_id, match):
    fs = _by_check(defective_report, check_id)
    assert fs, f"{defect_id}: no {check_id} finding fired"
    if match:
        assert any(all(f.object.get(k) == v for k, v in match.items())
                   for f in fs), f"{defect_id}: no {check_id} matching {match}"


def test_defective_exit_code_is_fail(defective_report):
    assert defective_report.exit_code() == 1  # enforced FAILs present


# -- clean regeneration is fully green ---------------------------------------

def test_clean_repo_all_green(wildlife):
    report = run_validation(wildlife["clean"], "strict-P", "build",
                            manifests=wildlife["ordered"])
    fails = [f for f in report.findings if f.severity == FAIL]
    assert not fails, "clean repo FAILs:\n" + "\n".join(
        f"  {f.check_id}: {f.message_technical or f.message_plain}" for f in fails)
    assert report.exit_code() == 0


def test_clean_repo_tf_all_green(wildlife):
    report = run_validation(wildlife["clean"], "strict-P", "build",
                            manifests=wildlife["ordered"])
    for cid in ("TF-1", "TF-2", "TF-3", "TF-4", "TF-5"):
        assert not [f for f in report.findings if f.check_id == cid], \
            f"{cid} fired on clean repo"
