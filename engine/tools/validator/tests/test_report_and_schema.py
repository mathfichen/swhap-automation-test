"""Report envelope: schema conformance, finding-id stability, determinism,
byte-safe encoding, and the legacy non-enforcement representation."""
from swhap_validate import report as R
from swhap_validate.cli import run_validation


def test_defective_report_schema_valid(wildlife, validate_report):
    rep = run_validation(wildlife["defective"], "strict-P", "build",
                         manifests=wildlife["manifests"])
    validate_report(rep)


def test_clean_report_schema_valid(wildlife, validate_report):
    rep = run_validation(wildlife["clean"], "strict-P", "build",
                         manifests=wildlife["manifests"])
    validate_report(rep)


def test_meta_stable_report_schema_valid_and_no_runvariant(wildlife, validate_report):
    rep = run_validation(wildlife["defective"], "strict-P", "build",
                         manifests=wildlife["manifests"], meta_stable=True)
    doc = validate_report(rep)
    assert doc["run"]["meta_stable"] is True
    assert "timestamp" not in doc["run"]
    assert "repo" not in doc["run"]
    assert "head" in doc["run"]  # content-derived, stays


def test_meta_stable_double_run_byte_identical(wildlife):
    a = run_validation(wildlife["defective"], "strict-P", "build",
                       manifests=wildlife["manifests"], meta_stable=True).serialize()
    b = run_validation(wildlife["defective"], "strict-P", "build",
                       manifests=wildlife["manifests"], meta_stable=True).serialize()
    assert a == b


def test_finding_ids_stable_across_runs(wildlife):
    a = run_validation(wildlife["defective"], "strict-P", "build",
                       manifests=wildlife["manifests"])
    b = run_validation(wildlife["defective"], "strict-P", "build",
                       manifests=wildlife["manifests"])
    assert sorted(f.id() for f in a.findings) == sorted(f.id() for f in b.findings)


def test_finding_id_uses_subject_projection_only():
    """A non-subject object key must not change the finding id (§2.1)."""
    f1 = R.Finding("TF-2", R.FAIL, {"tag": "1.0", "path": "LICENSE"},
                   ["tag"], "x")
    f2 = R.Finding("TF-2", R.FAIL, {"tag": "1.0", "path": "OTHER", "mode": "x"},
                   ["tag"], "x")
    assert f1.id() == f2.id()  # only `tag` is the subject


def test_finding_id_format():
    f = R.Finding("CSV-1", R.FAIL, {"path": "p"}, ["path"], "x")
    fid = f.id()
    assert fid.startswith("CSV-1:")
    assert len(fid.split(":")[1]) == 12


def test_bsafe_encoding():
    assert R.bsafe(b"Caf\xe9 mode d'emploi.txt") == "Caf\\xe9 mode d'emploi.txt"
    assert R.bsafe(b"x\x01y") == "x\\x01y"
    assert R.bsafe(b"\x1b]0;pwned") == "\\x1b]0;pwned"
    assert R.bsafe("café".encode("utf-8")) == "café"  # valid utf-8 stays real


def test_message_plain_never_empty_falls_back(validate_report):
    """GAP-2: the serializer guarantees a non-empty message_plain (schema
    minLength 1). An empty message falls back to message_technical, then to a
    synthesized check_id/severity line — a finding is never message-less."""
    # empty plain, has technical -> technical is used
    f1 = R.Finding("BP-5", R.FAIL, {"tag": "1.0"}, ["tag"], "",
                   message_technical="wrapper not stripped")
    assert f1.to_dict()["message_plain"] == "wrapper not stripped"
    # empty plain AND empty technical -> synthesized, non-empty, names the check
    f2 = R.Finding("CSV-7", R.WARN, {"rows": [1, 2]}, ["rows"], "   ")
    mp = f2.to_dict()["message_plain"]
    assert mp.strip() and "CSV-7" in mp and "WARN" in mp
    # a normal finding is untouched
    f3 = R.Finding("CM-4", R.INFO, {"term": "funder"}, ["term"], "real text")
    assert f3.to_dict()["message_plain"] == "real text"
    # all three still validate against the frozen schema
    rep = R.Report("legacy", "build", meta_stable=True)
    for f in (f1, f2, f3):
        rep.add(f)
    validate_report(rep)


def test_legacy_profile_enforced_false_exit_zero(wildlife):
    """Legacy audit: findings keep true severities but enforced:false, so the
    exit code is 0 (the run succeeded; findings are the output)."""
    rep = run_validation(wildlife["defective"], "legacy", "build",
                         manifests=wildlife["manifests"])
    fails = [f for f in rep.findings if f.severity == R.FAIL]
    assert fails, "legacy run should still surface FAIL-classified findings"
    assert all(f.enforced is False for f in rep.findings)
    assert rep.exit_code() == 0


def test_summary_counts(wildlife):
    rep = run_validation(wildlife["clean"], "strict-P", "build",
                         manifests=wildlife["manifests"])
    doc = rep.to_dict()
    s = doc["summary"]
    assert s["fail"] == sum(1 for f in doc["findings"] if f["severity"] == "FAIL")
    assert s["pass"] == len(set(doc["run"]["checks_run"])
                            - {f["check_id"] for f in doc["findings"]})
