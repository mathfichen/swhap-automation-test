"""CM-1..4 — codemeta as swh-indexer consumes it (D9)."""
import json

from swhap_validate.checks import codemeta
from swhap_validate.report import Report, FAIL, INFO, WARN

CANON = "https://doi.org/10.5063/schema/codemeta-2.0"


def run(doc=None, *, raw=None):
    rep = Report("strict-P", "build")
    data = raw if raw is not None else json.dumps(doc).encode("utf-8")
    codemeta.run(rep, None, codemeta_bytes=data)
    return rep


def checks(rep, cid):
    return [f for f in rep.findings if f.check_id == cid]


def test_CM1_invalid_json():
    rep = run(raw=b"{not json")
    assert checks(rep, "CM-1") and checks(rep, "CM-1")[0].severity == FAIL


def test_CM2_bogus_sciencecodemeta_context_red():
    rep = run({"@context": "https://doi.org/10.5063/sciencecodemeta/codemeta-2.0",
               "name": "x"})
    cm = checks(rep, "CM-2")
    assert cm and cm[0].severity == FAIL


def test_CM2_canonical_context_green():
    rep = run({"@context": CANON, "name": "x", "funder": {"name": "y"}})
    assert not checks(rep, "CM-2")


def test_CM2_codemeta_4_0_not_yet_accepted_distinct_message():
    rep = run({"@context": "https://w3id.org/codemeta/4.0", "name": "x"})
    cm = checks(rep, "CM-2")
    assert cm and cm[0].severity == FAIL
    assert "not yet accepted by swh-indexer" in (cm[0].message_technical or "")


def test_CM4_funding_and_maintainer_must_pass():
    """Regression vs brief §11's false rule: funding/maintainer are valid."""
    rep = run({"@context": CANON, "name": "x",
               "funding": "grant-123", "maintainer": {"name": "m"}})
    # neither term may produce any finding
    bad = [f for f in rep.findings
           if f.object.get("term") in ("funding", "maintainer")]
    assert not bad


def test_CM4_funder_vs_funding_info():
    rep = run({"@context": CANON, "name": "x", "funder": {"name": "y"}})
    info = [f for f in checks(rep, "CM-4")
            if f.severity == INFO and f.object.get("term") == "funder"]
    assert info


def test_CM4_blacklisted_term_warn():
    rep = run({"@context": CANON, "name": "x",
               "softwareRequirements": "python"})
    w = [f for f in checks(rep, "CM-4")
         if f.severity == WARN and f.object.get("term") == "softwareRequirements"]
    assert w


def test_CM3_offline_expand_green_on_canonical():
    rep = run({"@context": CANON, "name": "x", "author": [{"name": "a"}],
               "funder": {"name": "y"}})
    assert not checks(rep, "CM-3")  # expand/compact must not FAIL
    assert "CM-3" in rep.checks_run or any(
        s["id"] == "CM-3" for s in rep.checks_skipped)


def test_CM3_skipped_when_context_not_accepted():
    rep = run({"@context": "https://example.org/bogus", "name": "x"})
    assert any(s["id"] == "CM-3" for s in rep.checks_skipped)


def test_CM3_absent_backend_warns_not_silent(monkeypatch):
    """A missing JSON-LD backend must be recorded LOUDLY (CM-3 ran + WARN),
    never a silent skip — a silently-unverified @context is the D9/C2 failure
    mode (swh-indexer drops the whole file)."""
    import sys
    monkeypatch.setitem(sys.modules, "pyld", None)  # `from pyld import ...` -> ImportError
    rep = run({"@context": CANON, "name": "x"})
    assert "CM-3" in rep.checks_run
    assert not any(s["id"] == "CM-3" for s in rep.checks_skipped)
    warns = [f for f in checks(rep, "CM-3") if f.severity == WARN]
    assert warns, "absent JSON-LD backend must emit a CM-3 WARN, not skip silently"
