"""FIX-2 (AX5 / validator T10) — the legacy audit profile must tolerate the
documented installed-base convention of a **root-level** ``codemeta.json``
(external.md C8: SWH indexing expects codemeta at the repo root). DT2SG-era
acquisitions (e.g. Unipisa/CMM-Workbench) ship ``codemeta.json`` at the repo
root and NO ``metadata/codemeta.json``; the strict reader then raised a CM-1
"missing" FALSE failure under the legacy profile.

The fix (cli.run_validation) adds a legacy-only root fallback. These tests pin:
  * a root codemeta no longer FAILs CM-1 in the legacy profile (the false alarm);
  * detection is not weakened — a truly absent codemeta still FAILs CM-1, a
    bogus @context at the root still FAILs CM-2 (the real defect), and the strict
    profiles do NOT honour the root fallback (codemeta MUST live in metadata/).
"""
from conftest import make_git_repo

from swhap_validate import report as R
from swhap_validate.cli import run_validation

# Minimal legacy workbench files (the CSV is incidental here; CM is isolated via
# only=["CM-1"], which also disables PC-1 preflight so no repo scaffolding is
# required beyond a default branch).
_LEGACY_CSV = (
    "directory name,author name,author email,date,"
    "curator name,curator email,release tag,commit message\n"
    "1.1,A,a@noreply.example.org,1994-03-24,C,c@noreply.example.org,1.1,init\n"
).encode("utf-8")

_GOOD_CODEMETA = (
    '{\n  "@context": "https://doi.org/10.5063/schema/codemeta-2.0",\n'
    '  "@type": "SoftwareSourceCode",\n  "name": "CMM"\n}\n'
).encode("utf-8")

# A valid CodeMeta version SWH does not yet accept → CM-2 true defect (CM-2 fires
# on any @context outside the accepted set, regardless of file location).
_BOGUS_CONTEXT_CODEMETA = (
    '{\n  "@context": "https://not-a-real-context.example/v9",\n'
    '  "@type": "SoftwareSourceCode",\n  "name": "CMM"\n}\n'
).encode("utf-8")


def _cm_findings(repo, profile):
    rep = run_validation(repo, profile, "build", only=["CM-1"])
    return rep


def _fails(rep, cid):
    return [f for f in rep.findings if f.check_id == cid and f.severity == R.FAIL]


def test_FIX2_root_codemeta_no_cm1_fail_in_legacy(tmp_path):
    """The false alarm: a present-at-root codemeta no longer reports 'missing'."""
    repo = make_git_repo(str(tmp_path / "r"), {
        "metadata/version_history.csv": _LEGACY_CSV,
        "codemeta.json": _GOOD_CODEMETA,  # root, NOT metadata/
    })
    rep = _cm_findings(repo, "legacy")
    assert not _fails(rep, "CM-1"), "root codemeta must satisfy CM-1 in legacy"


def test_FIX2_missing_codemeta_still_fails_cm1_in_legacy(tmp_path):
    """Detection preserved: a truly absent codemeta still FAILs CM-1 in legacy."""
    repo = make_git_repo(str(tmp_path / "r"), {
        "metadata/version_history.csv": _LEGACY_CSV,
    })
    rep = _cm_findings(repo, "legacy")
    assert _fails(rep, "CM-1"), "a genuinely missing codemeta must still FAIL"


def test_FIX2_root_codemeta_bogus_context_still_cm2_in_legacy(tmp_path):
    """Detection preserved: the root fallback is still held to CM-2 — a bogus
    @context (the real defect that survives the legacy profile) still FAILs."""
    repo = make_git_repo(str(tmp_path / "r"), {
        "metadata/version_history.csv": _LEGACY_CSV,
        "codemeta.json": _BOGUS_CONTEXT_CODEMETA,
    })
    rep = _cm_findings(repo, "legacy")
    assert not _fails(rep, "CM-1"), "file is present at root → CM-1 passes"
    assert _fails(rep, "CM-2"), "bogus @context is a true defect, must FAIL CM-2"


def test_FIX2_root_codemeta_not_honoured_in_strict(tmp_path):
    """The root fallback is legacy-only: under strict, codemeta MUST live in
    metadata/, so a root-only codemeta still FAILs CM-1."""
    repo = make_git_repo(str(tmp_path / "r"), {
        "metadata/version_history.csv": _LEGACY_CSV,
        "codemeta.json": _GOOD_CODEMETA,
    })
    for prof in ("strict-P", "strict-G"):
        rep = _cm_findings(repo, prof)
        assert _fails(rep, "CM-1"), f"{prof} must not honour the root fallback"
