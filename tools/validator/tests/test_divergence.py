"""DV-1 — published-remote divergence (revised-D3 rebuild-and-replace).

Exercises the four contract cases against a LOCAL bare remote (standing in for
the published origin) and a MOCK archiver (Save Code Now) — no network:

1. fast-forward append           -> DV-1 PASS (no finding)
2. recorded supersession         -> DV-1 PASS (explained WARN; exit not FAIL)
3. divergence, no rewrite-event  -> DV-1 FAIL (accidental clobber)
4. divergence, forged prior snp  -> DV-1 FAIL (mismatched lineage pointer)

Plus a CLI-wiring test: DV-1 runs at ``--gate publish``, is skipped at
``--gate build``, and is skipped in the legacy profile.

State is produced by the REAL publish flow (``swhap_core.publish``); the prior
snapshot SWHID DV-1 recomputes from the remote is cross-checked against the one
the publisher journaled.
"""
from __future__ import annotations

import os
import subprocess

import pytest

jsonschema = pytest.importorskip("jsonschema")
pytest.importorskip("swh.model")

from swhap_core.gitio import GitRunner  # noqa: E402
from swhap_core.history import do_build  # noqa: E402
from swhap_core.model import CurationTimestamp  # noqa: E402
from swhap_core.publish import (  # noqa: E402
    SOURCECODE_REF,
    LocalBarePushTarget,
    SaveResult,
    do_publish,
    do_publish_supersede,
)
from swhap_core.swhid import snapshot_swhid  # noqa: E402

from swhap_validate.checks import divergence  # noqa: E402
from swhap_validate.context import RepoContext  # noqa: E402
from swhap_validate.report import FAIL, WARN, Report  # noqa: E402

CURATION = CurationTimestamp(1781082136, "+0000")
FINAL_REPO = "https://forge.example.org/institution/wildlife"

_HEADER = (
    "directory name,date,author name,author email,curator name,curator email,release tag,commit message\n"
)
_ROWS = {
    "0.90": "0.90,1993-08-09,Wild_LIFE authors,wildlife-authors@noreply.example.org,Roberto Di Cosmo,roberto@dicosmo.org,v0.90,Wild_LIFE 0.90\n",
    "0.91": "0.91,1993-08-09,Wild_LIFE authors,wildlife-authors@noreply.example.org,Roberto Di Cosmo,roberto@dicosmo.org,v0.91,Wild_LIFE 0.91\n",
    "0.9.999": "0.9.999,1993-12-01,Wild_LIFE authors,wildlife-authors@noreply.example.org,Roberto Di Cosmo,roberto@dicosmo.org,v0.9.999,Wild_LIFE 0.9.999 (late-surfacing interim release)\n",
    "1.0": "1.0,1994-03-24,Wild_LIFE authors,wildlife-authors@noreply.example.org,Roberto Di Cosmo,roberto@dicosmo.org,v1.0,Wild_LIFE 1.0\n",
    "2.0": "2.0,1995-05-01,Wild_LIFE authors,wildlife-authors@noreply.example.org,Roberto Di Cosmo,roberto@dicosmo.org,v2.0,Wild_LIFE 2.0\n",
}
_CONTENT = {
    "0.90": {"README": b"life 0.90\n", "src/life.ml": b"let x = 1\n"},
    "0.91": {"README": b"life 0.91\n", "src/life.ml": b"let x = 2\n"},
    "0.9.999": {"README": b"life 0.9.999\n", "src/life.ml": b"let x = 25\n"},
    "1.0": {"README": b"life 1.0\n", "src/life.ml": b"let x = 3\n"},
    "2.0": {"README": b"life 2.0\n", "src/life.ml": b"let x = 4\n"},
}

_CURATOR = {
    "kind": "curator",
    "name": "Roberto Di Cosmo",
    "tool": "swhap-intake",
    "version": "0.1.0",
    "login": "rdicosmo",
    "role": "curator",
    "verified_via": "team-membership",
}


def _write_dirs(root, dirnames):
    sc = os.path.join(root, "source_code")
    for d in dirnames:
        for rel, data in _CONTENT[d].items():
            full = os.path.join(sc, d, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "wb") as fh:
                fh.write(data)


def _write_csv(root, order):
    with open(os.path.join(root, "metadata", "version_history.csv"), "w") as fh:
        fh.write(_HEADER + "".join(_ROWS[d] for d in order))


def _make_workbench(root, order):
    os.makedirs(os.path.join(root, "metadata"))
    _write_dirs(root, order)
    _write_csv(root, order)
    with open(os.path.join(root, "metadata", "codemeta.json"), "wb") as fh:
        fh.write(b'{\n  "@context": "https://doi.org/10.5063/schema/codemeta-2.0",\n  "@type": "SoftwareSourceCode",\n  "name": "Wild_LIFE"\n}\n')
    subprocess.run(["git", "init", "-q", root], check=True)
    return root


def _bare_remote(path):
    subprocess.run(["git", "init", "-q", "--bare", path], check=True)
    return path


class _MockArchiver:
    """Stand-in for Save Code Now: returns the snapshot SWHID the bare remote
    currently presents (so the prior-snapshot lineage pointer is real)."""

    def __init__(self, bare_remote):
        self.bare = bare_remote

    def save(self, origin_url):
        snp = snapshot_swhid(self.bare)
        return SaveResult(request_url="mock://save/" + origin_url,
                          visit_status="full", snapshot_swhid=snp)


class _NoOpPushTarget:
    """Push target that does nothing — keeps the remote at the prior published
    state while ``do_publish_supersede`` rewrites the LOCAL refs + journal, so we
    can validate the pre-push divergent workbench against the still-prior remote."""

    def push(self, repo, refs, *, force=False):
        return None


def _journal_bytes(workbench):
    with open(os.path.join(workbench, "metadata", "journal.jsonl"), "rb") as fh:
        return fh.read()


def _set_local_sourcecode(workbench, build):
    """Point the workbench's published refs at ``build`` (a freshly-built
    candidate) — simulates the pre-push state where the curator has rebuilt and
    is about to (super)publish."""
    git = GitRunner(workbench, allow_publish=True)
    git.update_ref(SOURCECODE_REF, build.branch_tip)
    for t in build.tags:
        git.update_ref(f"refs/tags/{t['release_tag']}", t["tag"])


def _run_dv(workbench, remote, journal_bytes):
    report = Report("strict-P", "publish")
    divergence.run(report, RepoContext(workbench), published_remote=remote,
                   journal_bytes=journal_bytes)
    return report


def _dv_findings(report):
    return [f for f in report.findings if f.check_id == "DV-1"]


# --------------------------------------------------------------------------- #
# 1. fast-forward append -> PASS
# --------------------------------------------------------------------------- #
def test_dv1_fast_forward_append_passes(tmp_path):
    wb = _make_workbench(str(tmp_path / "wb"), ["0.90", "0.91", "1.0"])
    bare = _bare_remote(str(tmp_path / "remote.git"))
    push = LocalBarePushTarget(bare)
    _, build1 = do_build(wb, "P", CURATION, run_id="0000000000000000000000000A")
    do_publish(wb, candidate_ref=build1.branch_ref, final_repo=FINAL_REPO,
               push_target=push, archiver=_MockArchiver(bare))

    # rebuild with a release appended at the END (pure append) and point the
    # local SourceCode at it — a fast-forward over the published remote.
    _write_dirs(wb, ["2.0"])
    _write_csv(wb, ["0.90", "0.91", "1.0", "2.0"])
    _, build2 = do_build(wb, "P", CURATION, run_id="0000000000000000000000000B")
    _set_local_sourcecode(wb, build2)

    report = _run_dv(wb, bare, _journal_bytes(wb))
    assert "DV-1" in report.checks_run
    assert _dv_findings(report) == []  # fast-forward => clean PASS
    assert report.exit_code() == 0


# --------------------------------------------------------------------------- #
# 2. recorded supersession -> PASS (explained WARN)
# --------------------------------------------------------------------------- #
def test_dv1_recorded_supersession_passes_as_warn(tmp_path):
    wb = _make_workbench(str(tmp_path / "wb"), ["0.90", "0.91", "1.0"])
    bare = _bare_remote(str(tmp_path / "remote.git"))
    push = LocalBarePushTarget(bare)
    _, build1 = do_build(wb, "P", CURATION, run_id="0000000000000000000000000A")
    pub1 = do_publish(wb, candidate_ref=build1.branch_ref, final_repo=FINAL_REPO,
                      push_target=push, archiver=_MockArchiver(bare))
    prior_snp = pub1.snapshot_swhid

    # insert 0.9.999 between 0.91 and 1.0, rebuild, and run supersede with a
    # NO-OP push so the remote stays at the prior 3-release state: the workbench
    # now DIVERGES from the remote but carries the recorded supersession.
    _write_dirs(wb, ["0.9.999"])
    _write_csv(wb, ["0.90", "0.91", "0.9.999", "1.0"])
    _, build2 = do_build(wb, "P", CURATION, run_id="0000000000000000000000000B")
    res = do_publish_supersede(
        wb, candidate_ref=build2.branch_ref, final_repo=FINAL_REPO,
        curator=_CURATOR, push_target=_NoOpPushTarget(),
        archiver=_MockArchiver(bare),
        reason="0.9.999 belongs between 0.91 and 1.0 (chronological insertion)",
    )
    assert res.prior_snapshot_swhid == prior_snp

    report = _run_dv(wb, bare, _journal_bytes(wb))
    finds = _dv_findings(report)
    assert len(finds) == 1
    f = finds[0]
    assert f.severity == WARN  # sanctioned divergence: explained, not blocking
    assert f.object["supersedes_snapshot_swhid"] == prior_snp
    assert f.object["divergence"] is True
    assert report.exit_code() == 0  # WARN does not fail the gate (no --strict-warn)


# --------------------------------------------------------------------------- #
# 3. divergence with NO rewrite-event -> FAIL
# --------------------------------------------------------------------------- #
def test_dv1_divergence_without_rewrite_event_fails(tmp_path):
    wb = _make_workbench(str(tmp_path / "wb"), ["0.90", "0.91", "1.0"])
    bare = _bare_remote(str(tmp_path / "remote.git"))
    push = LocalBarePushTarget(bare)
    _, build1 = do_build(wb, "P", CURATION, run_id="0000000000000000000000000A")
    do_publish(wb, candidate_ref=build1.branch_ref, final_repo=FINAL_REPO,
               push_target=push, archiver=_MockArchiver(bare))
    journal_before = _journal_bytes(wb)  # only genesis + publish-event

    # insert 0.9.999 and rebuild, but clobber the local SourceCode WITHOUT any
    # rewrite-event sign-off (the accidental-clobber case).
    _write_dirs(wb, ["0.9.999"])
    _write_csv(wb, ["0.90", "0.91", "0.9.999", "1.0"])
    _, build2 = do_build(wb, "P", CURATION, run_id="0000000000000000000000000B")
    _set_local_sourcecode(wb, build2)

    report = _run_dv(wb, bare, journal_before)
    finds = _dv_findings(report)
    assert len(finds) == 1
    assert finds[0].severity == FAIL
    assert finds[0].object["divergence"] is True
    assert report.exit_code() == 1


# --------------------------------------------------------------------------- #
# 4. divergence with a forged/mismatched prior snapshot -> FAIL
# --------------------------------------------------------------------------- #
def test_dv1_mismatched_prior_snapshot_fails(tmp_path):
    wb = _make_workbench(str(tmp_path / "wb"), ["0.90", "0.91", "1.0"])
    bare = _bare_remote(str(tmp_path / "remote.git"))
    push = LocalBarePushTarget(bare)
    _, build1 = do_build(wb, "P", CURATION, run_id="0000000000000000000000000A")
    pub1 = do_publish(wb, candidate_ref=build1.branch_ref, final_repo=FINAL_REPO,
                      push_target=push, archiver=_MockArchiver(bare))
    prior_snp = pub1.snapshot_swhid

    _write_dirs(wb, ["0.9.999"])
    _write_csv(wb, ["0.90", "0.91", "0.9.999", "1.0"])
    _, build2 = do_build(wb, "P", CURATION, run_id="0000000000000000000000000B")
    do_publish_supersede(
        wb, candidate_ref=build2.branch_ref, final_repo=FINAL_REPO,
        curator=_CURATOR, push_target=_NoOpPushTarget(),
        archiver=_MockArchiver(bare), reason="insertion",
    )

    # Forge the lineage pointer: rewrite the journal's recorded prior snapshot to
    # a DIFFERENT (well-formed) snp. DV-1 recomputes the real prior snp from the
    # remote, finds no sign-off matching it, and FAILs.
    forged = "swh:1:snp:" + "0" * 40
    assert prior_snp != forged
    tampered = _journal_bytes(wb).replace(prior_snp.encode(), forged.encode())
    assert forged.encode() in tampered

    report = _run_dv(wb, bare, tampered)
    finds = _dv_findings(report)
    assert len(finds) == 1
    assert finds[0].severity == FAIL
    assert report.exit_code() == 1


# --------------------------------------------------------------------------- #
# CLI wiring: gate publish runs DV-1; gate build skips it; legacy skips it.
# --------------------------------------------------------------------------- #
def _commit_metadata_to_main(workbench):
    """Commit metadata/ on the default branch so the CLI can read the journal
    from refs (the rest of the validator reads metadata from the default
    branch)."""
    env = dict(os.environ, GIT_AUTHOR_NAME="C",
               GIT_AUTHOR_EMAIL="c@noreply.example.org",
               GIT_COMMITTER_NAME="C", GIT_COMMITTER_EMAIL="c@noreply.example.org",
               GIT_AUTHOR_DATE="2026-06-07T00:00:00+0000",
               GIT_COMMITTER_DATE="2026-06-07T00:00:00+0000")
    subprocess.run(["git", "-C", workbench, "add", "metadata"], check=True, env=env,
                   capture_output=True)
    subprocess.run(["git", "-C", workbench, "commit", "-q", "-m", "metadata"],
                   check=True, env=env, capture_output=True)


def _supersede_state(tmp_path):
    wb = _make_workbench(str(tmp_path / "wb"), ["0.90", "0.91", "1.0"])
    bare = _bare_remote(str(tmp_path / "remote.git"))
    push = LocalBarePushTarget(bare)
    _, build1 = do_build(wb, "P", CURATION, run_id="0000000000000000000000000A")
    do_publish(wb, candidate_ref=build1.branch_ref, final_repo=FINAL_REPO,
               push_target=push, archiver=_MockArchiver(bare))
    _write_dirs(wb, ["0.9.999"])
    _write_csv(wb, ["0.90", "0.91", "0.9.999", "1.0"])
    _, build2 = do_build(wb, "P", CURATION, run_id="0000000000000000000000000B")
    do_publish_supersede(
        wb, candidate_ref=build2.branch_ref, final_repo=FINAL_REPO,
        curator=_CURATOR, push_target=_NoOpPushTarget(),
        archiver=_MockArchiver(bare), reason="insertion",
    )
    _commit_metadata_to_main(wb)
    return wb, bare


def test_cli_dv1_runs_at_publish_gate(tmp_path):
    from swhap_validate.cli import run_validation
    wb, bare = _supersede_state(tmp_path)
    report = run_validation(wb, "strict-P", "publish", only=["DV-1"],
                            published_remote=bare)
    assert "DV-1" in report.checks_run
    finds = [f for f in report.findings if f.check_id == "DV-1"]
    assert len(finds) == 1 and finds[0].severity == WARN
    assert report.exit_code() == 0
    # the DV-1 report (incl. the WARN provenance) is schema-valid
    import json
    import os as _os

    import jsonschema
    schema_path = _os.path.join(_os.path.dirname(__file__), "..", "schemas",
                                "validation-report.v1.schema.json")
    with open(schema_path, encoding="utf-8") as fh:
        v = jsonschema.Draft202012Validator(json.load(fh))
    assert list(v.iter_errors(report.to_dict())) == []


def test_cli_dv1_skipped_at_build_gate(tmp_path):
    from swhap_validate.cli import run_validation
    wb, bare = _supersede_state(tmp_path)
    report = run_validation(wb, "strict-P", "build", only=["DV-1"],
                            published_remote=bare)
    assert "DV-1" not in report.checks_run
    skipped = {e["id"] for e in report.checks_skipped}
    assert "DV-1" in skipped


def test_cli_dv1_skipped_in_legacy_profile(tmp_path):
    from swhap_validate.cli import run_validation
    wb, bare = _supersede_state(tmp_path)
    report = run_validation(wb, "legacy", "publish", only=["DV-1"],
                            published_remote=bare)
    assert "DV-1" not in report.checks_run
    skipped = {e["id"] for e in report.checks_skipped}
    assert "DV-1" in skipped
