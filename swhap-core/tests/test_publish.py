"""``swhap publish`` + revised-D3 rebuild-and-replace (chronological insertion).

End-to-end against a LOCAL bare remote (standing in for the published origin) and
a MOCK archiver (standing in for Save Code Now) — no network. The mock computes
the snapshot SWHID of the remote at call time, so the test also cross-checks that
the locally-computed snapshot equals what an archiver would see.

Headline scenario (decisions.md D3-RESOLVED, 2026-06-06): publish 0.90/0.91/1.0,
then insert a synthetic 0.9.999 release *between* 0.91 and 1.0 and
``publish --supersede``. Asserts the lineage record, the SWHID stability law
(before-insertion revs identical, after-insertion revs change, all content
trees/blobs preserved), and D4 bit-reproducibility of the rebuilt history.
"""

from __future__ import annotations

import json
import os
import subprocess

import pytest

from swhap_core.gitio import GitRunner
from swhap_core.history import do_build
from swhap_core.model import CurationTimestamp
from swhap_core.publish import (
    SOURCECODE_REF,
    LocalBarePushTarget,
    SaveResult,
    do_publish,
    do_publish_supersede,
)
from swhap_core.swhid import snapshot_swhid

jsonschema = pytest.importorskip("jsonschema")
pytest.importorskip("swh.model")

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
}
_CONTENT = {
    "0.90": {"README": b"life 0.90\n", "src/life.ml": b"let x = 1\n"},
    "0.91": {"README": b"life 0.91\n", "src/life.ml": b"let x = 2\n"},
    "0.9.999": {"README": b"life 0.9.999\n", "src/life.ml": b"let x = 25\n"},
    "1.0": {"README": b"life 1.0\n", "src/life.ml": b"let x = 3\n"},
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
    # a codemeta.json under metadata/ to exercise C2 root-promotion
    with open(os.path.join(root, "metadata", "codemeta.json"), "wb") as fh:
        fh.write(b'{\n  "@context": "https://doi.org/10.5063/schema/codemeta-2.0",\n  "@type": "SoftwareSourceCode",\n  "name": "Wild_LIFE"\n}\n')
    subprocess.run(["git", "init", "-q", root], check=True)
    return root


def _bare_remote(path):
    subprocess.run(["git", "init", "-q", "--bare", path], check=True)
    return path


class MockArchiver:
    """Stand-in for Save Code Now: returns the snapshot SWHID the remote currently
    presents (so the test cross-checks local computation against the 'archived'
    state). Records every call for ordering assertions."""

    def __init__(self, bare_remote):
        self.bare = bare_remote
        self.calls = []

    def save(self, origin_url):
        snp = snapshot_swhid(self.bare)
        self.calls.append({"origin": origin_url, "snp": snp})
        return SaveResult(request_url="mock://save/" + origin_url, visit_status="full", snapshot_swhid=snp)


def _entries(workbench):
    path = os.path.join(workbench, "metadata", "journal.jsonl")
    return [json.loads(line) for line in open(path)]


def _schema_validator():
    here = os.path.dirname(__file__)
    schema_path = os.path.abspath(os.path.join(here, "..", "..", "specs", "journal-entry.schema.json"))
    return jsonschema.Draft202012Validator(json.load(open(schema_path)))


def _by_dirname(result):
    return {c["dirname"]: c for c in result.commits}


# --------------------------------------------------------------------------- #
# plain publish
# --------------------------------------------------------------------------- #
def test_publish_promotes_sourcecode_tags_and_codemeta(tmp_path):
    wb = _make_workbench(str(tmp_path / "wb"), ["0.90", "0.91", "1.0"])
    bare = _bare_remote(str(tmp_path / "remote.git"))
    _, result = do_build(wb, "P", CURATION, run_id="0000000000000000000000000A")
    candidate_ref = result.branch_ref
    archiver = MockArchiver(bare)

    res = do_publish(
        wb,
        candidate_ref=candidate_ref,
        final_repo=FINAL_REPO,
        push_target=LocalBarePushTarget(bare),
        archiver=archiver,
    )

    git = GitRunner(wb)
    # published refs materialized locally
    assert git.rev_parse(SOURCECODE_REF) == result.branch_tip
    for t in result.tags:
        assert git.rev_parse(f"refs/tags/{t['release_tag']}") == t["tag"]
    # pushed to the remote, identical snapshot
    assert snapshot_swhid(bare) == res.snapshot_swhid
    assert archiver.calls[-1]["snp"] == res.snapshot_swhid
    # codemeta promoted to the default-branch root (C2)
    assert res.codemeta_promoted
    assert os.path.isfile(os.path.join(wb, "codemeta.json"))

    # publish-event journaled; chain + schema valid
    entries = _entries(wb)
    assert entries[-1]["action"] == "publish-event"
    assert entries[-1]["details"]["swhids"]["snp"] == res.snapshot_swhid
    v = _schema_validator()
    for e in entries:
        errs = [x.message for x in v.iter_errors(e)]
        assert not errs, (e["action"], errs)
    from swhap_core.journal import Ledger

    Ledger(os.path.join(wb, "metadata", "journal.jsonl")).verify()


# --------------------------------------------------------------------------- #
# revised-D3 rebuild-and-replace: chronological insertion
# --------------------------------------------------------------------------- #
def test_supersede_chronological_insertion(tmp_path):
    wb = _make_workbench(str(tmp_path / "wb"), ["0.90", "0.91", "1.0"])
    bare = _bare_remote(str(tmp_path / "remote.git"))
    archiver = MockArchiver(bare)
    push = LocalBarePushTarget(bare)

    # --- publish the 3-release history -------------------------------------
    _, build1 = do_build(wb, "P", CURATION, run_id="0000000000000000000000000A")
    pub1 = do_publish(
        wb, candidate_ref=build1.branch_ref, final_repo=FINAL_REPO,
        push_target=push, archiver=archiver,
    )
    prior_snp = pub1.snapshot_swhid
    assert snapshot_swhid(bare) == prior_snp
    b1 = _by_dirname(build1)

    # --- insert 0.9.999 between 0.91 and 1.0, rebuild ----------------------
    _write_dirs(wb, ["0.9.999"])
    _write_csv(wb, ["0.90", "0.91", "0.9.999", "1.0"])
    _, build2 = do_build(wb, "P", CURATION, run_id="0000000000000000000000000B")
    b2 = _by_dirname(build2)

    # --- supersede ----------------------------------------------------------
    n_calls_before = len(archiver.calls)
    res = do_publish_supersede(
        wb,
        candidate_ref=build2.branch_ref,
        final_repo=FINAL_REPO,
        curator=_CURATOR,
        push_target=push,
        archiver=archiver,
        reason="0.9.999 surfaced and belongs between 0.91 and 1.0 (chronological insertion)",
    )

    # (1) the prior snapshot SWHID is recorded in the rewrite-event sign-off
    assert res.prior_snapshot_swhid == prior_snp
    entries = _entries(wb)
    signoffs = [e for e in entries if e["action"] == "rewrite-event" and e["details"]["phase"] == "sign-off"]
    executed = [e for e in entries if e["action"] == "rewrite-event" and e["details"]["phase"] == "executed"]
    assert len(signoffs) == 1 and len(executed) == 1
    so, ex = signoffs[0], executed[0]
    assert so["details"]["supersedes_snapshot_swhid"] == prior_snp
    assert so["details"]["acknowledgement"] == "prior-snapshot-archived-in-swh"
    assert so["actor"]["kind"] == "curator"
    # executed cites the sign-off; set-equal target_refs; machine actor
    assert ex["details"]["sign_off_entry"] == so["id"]
    assert set(ex["details"]["target_refs"]) == set(so["details"]["target_refs"])
    assert ex["actor"]["kind"] == "machine"
    # the prior snapshot was archived BEFORE the replacement (sign-off precedes any
    # ref change); the supersede made an extra archiver call on the prior state
    assert archiver.calls[n_calls_before]["snp"] == prior_snp

    # (2) releases BEFORE the insertion keep identical rev SWHIDs (commit hashes)
    assert b2["0.90"]["commit"] == b1["0.90"]["commit"]
    assert b2["0.91"]["commit"] == b1["0.91"]["commit"]
    # (3) releases AFTER the insertion change their rev SWHID
    assert b2["1.0"]["commit"] != b1["1.0"]["commit"]
    # (4) all unchanged file/tree (cnt/dir) SWHIDs are preserved:
    #     1.0's content tree is byte-identical (only its parent changed)
    assert b2["1.0"]["tree"] == b1["1.0"]["tree"]
    assert b2["0.90"]["tree"] == b1["0.90"]["tree"]
    assert b2["0.91"]["tree"] == b1["0.91"]["tree"]
    # blob preservation: an unchanged file keeps its blob oid across the rebuild
    g = GitRunner(wb)
    blob_before = g.run(["rev-parse", f"{b1['1.0']['commit']}:README"]).decode().strip()
    blob_after = g.run(["rev-parse", f"{b2['1.0']['commit']}:README"]).decode().strip()
    assert blob_before == blob_after

    # the new published snapshot differs from the prior, and matches the remote
    assert res.new_snapshot_swhid != prior_snp
    assert snapshot_swhid(bare) == res.new_snapshot_swhid
    assert archiver.calls[-1]["snp"] == res.new_snapshot_swhid

    # published refs now reflect the 4-release history with 0.9.999 inserted
    assert g.rev_parse(SOURCECODE_REF) == build2.branch_tip
    assert g.rev_parse("refs/tags/v0.9.999") is not None

    # journal: chain valid, schema valid, monotone publish/rewrite ordering
    v = _schema_validator()
    for e in entries:
        errs = [x.message for x in v.iter_errors(e)]
        assert not errs, (e["action"], errs)
    from swhap_core.journal import Ledger

    Ledger(os.path.join(wb, "metadata", "journal.jsonl")).verify()
    # sign-off precedes executed in chain order
    assert entries.index(so) < entries.index(ex)


def test_rebuilt_history_is_bit_reproducible(tmp_path):
    """D4: rebuilding the inserted 4-release history in two fresh workbenches
    yields identical commit AND annotated-tag object hashes."""
    order = ["0.90", "0.91", "0.9.999", "1.0"]
    a = _make_workbench(str(tmp_path / "a"), order)
    b = _make_workbench(str(tmp_path / "b"), order)
    _, ra = do_build(a, "P", CURATION, run_id="00000000000000000000000001")
    _, rb = do_build(b, "P", CURATION, run_id="00000000000000000000000002")
    assert ra.commit_oids() == rb.commit_oids()
    assert ra.tag_oids() == rb.tag_oids()


def test_supersede_refuses_unarchived_prior(tmp_path):
    """The revised-D3 'no un-archived clobber' guard: if the archiver cannot
    confirm the prior snapshot, supersede fails PB-PRIOR-UNARCHIVED (exit 16)."""
    from swhap_core.errors import PublishError

    wb = _make_workbench(str(tmp_path / "wb"), ["0.90", "0.91", "1.0"])
    bare = _bare_remote(str(tmp_path / "remote.git"))
    push = LocalBarePushTarget(bare)
    _, build1 = do_build(wb, "P", CURATION, run_id="0000000000000000000000000A")
    do_publish(wb, candidate_ref=build1.branch_ref, final_repo=FINAL_REPO,
               push_target=push, archiver=MockArchiver(bare))
    _write_dirs(wb, ["0.9.999"])
    _write_csv(wb, ["0.90", "0.91", "0.9.999", "1.0"])
    _, build2 = do_build(wb, "P", CURATION, run_id="0000000000000000000000000B")

    class NullArchiver:
        def save(self, origin_url):
            return SaveResult(request_url="mock://save", visit_status="pending", snapshot_swhid=None)

    with pytest.raises(PublishError) as ei:
        do_publish_supersede(
            wb, candidate_ref=build2.branch_ref, final_repo=FINAL_REPO, curator=_CURATOR,
            push_target=push, archiver=NullArchiver(),
            reason="x",
        )
    assert ei.value.code == "PB-PRIOR-UNARCHIVED"
    assert ei.value.exit_code == 16
