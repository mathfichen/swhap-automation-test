"""Journal ledger (swhap-journal/1): canonical form, hash chain, schema conformance.

Validates the build-time entry builders against the FROZEN
``specs/journal-entry.schema.json`` (jsonschema is test-only — the runtime stays
stdlib-only).
"""

from __future__ import annotations

import json
import os

import pytest

from swhap_core.errors import JournalError
from swhap_core.journal import (
    Ledger,
    canonical_bytes,
    entry_hash,
    machine_actor,
    new_entry,
    new_ulid,
)

jsonschema = pytest.importorskip("jsonschema")

_ULID_RE = r"^[0-7][0-9A-HJKMNP-TV-Z]{25}$"


def _repo_root() -> str:
    here = os.path.dirname(__file__)
    return os.path.abspath(os.path.join(here, "..", ".."))


@pytest.fixture(scope="session")
def schema():
    with open(os.path.join(_repo_root(), "specs", "journal-entry.schema.json"), "rb") as fh:
        return json.load(fh)


@pytest.fixture(scope="session")
def validator(schema):
    return jsonschema.Draft202012Validator(schema)


def test_ulid_format():
    import re

    for _ in range(200):
        assert re.match(_ULID_RE, new_ulid())
    # deterministic when seeded
    u = new_ulid(ts_ms=0x123456789A, rand=b"\x00" * 10)
    assert re.match(_ULID_RE, u)
    assert new_ulid(ts_ms=0x123456789A, rand=b"\x00" * 10) == u


def test_canonical_serialization_is_sorted_compact():
    e = {"schema": "swhap-journal/1", "b": 1, "a": 2}
    out = canonical_bytes(e)
    assert out == b'{"a":2,"b":1,"schema":"swhap-journal/1"}'
    # round-trips through json
    assert json.loads(out) == e


def test_float_and_surrogate_rejected():
    with pytest.raises(JournalError) as ei:
        canonical_bytes({"x": 1.5})
    assert ei.value.code == "JL-SCHEMA"
    with pytest.raises(JournalError):
        canonical_bytes({"x": "lone\udc80surrogate"})


def test_chain_and_verify(tmp_path):
    led = Ledger(str(tmp_path / "metadata" / "journal.jsonl"))
    g = led.ensure_genesis("wb")
    assert g["prev_entry_sha256"] == "0" * 64
    e1 = led.append(new_entry("inspect", inputs=[{"path": "raw_materials/a.tar", "sha256": "a" * 64}]))
    e2 = led.append(new_entry("plan", outputs=[{"path": "metadata/plan.json", "sha256": "b" * 64}]))
    lines = (tmp_path / "metadata" / "journal.jsonl").read_bytes().splitlines()
    assert e1["prev_entry_sha256"] == entry_hash(lines[0])
    assert e2["prev_entry_sha256"] == entry_hash(lines[1])
    led.verify()  # no raise


def test_genesis_rules(tmp_path):
    led = Ledger(str(tmp_path / "metadata" / "journal.jsonl"))
    with pytest.raises(JournalError):
        led.append(new_entry("inspect", inputs=[{"path": "x", "sha256": "a" * 64}]))  # no genesis yet
    led.ensure_genesis("wb")
    with pytest.raises(JournalError):
        led.append(new_entry("genesis", details={"workbench": "wb"}))  # second genesis


def test_tamper_detected(tmp_path):
    path = tmp_path / "metadata" / "journal.jsonl"
    led = Ledger(str(path))
    led.ensure_genesis("wb")
    led.append(new_entry("inspect", inputs=[{"path": "x", "sha256": "a" * 64}]))
    raw = path.read_bytes().splitlines()
    # flip a byte in the genesis line → chain break / non-canonical
    tampered = raw[0].replace(b'"workbench":"wb"', b'"workbench":"XX"')
    path.write_bytes(tampered + b"\n" + raw[1] + b"\n")
    with pytest.raises(JournalError):
        Ledger(str(path)).verify()


def test_build_time_entries_validate_against_schema(validator):
    actor = machine_actor()
    entries = [
        new_entry("genesis", actor=actor, details={"workbench": "wb", "git_version": "2.47.3"}),
        new_entry(
            "curation-timestamp",
            actor=actor,
            details={"epoch": 1781082136, "offset": "+0000", "note": "D4"},
        ),
        new_entry(
            "plan",
            actor=actor,
            outputs=[{"path": "metadata/plan.json", "sha256": "0" * 64, "size_bytes": 12}],
        ),
        new_entry(
            "apply",
            actor=actor,
            inputs=[{"path": "metadata/plan.json", "sha256": "0" * 64}],
            outputs=[
                {"type": "commit", "git_object": "a" * 40, "ref": "refs/heads/candidate/P/01TESTRUN0000000000000000"},
                {"type": "tag", "git_object": "b" * 40, "ref": "refs/tags/candidate/P/01TESTRUN0000000000000000/v1.0"},
            ],
            details={"model": "P", "run_id": "01TESTRUN0000000000000000"},
        ),
    ]
    for e in entries:
        e["prev_entry_sha256"] = "0" * 64
        errors = sorted(validator.iter_errors(e), key=str)
        assert not errors, [err.message for err in errors]
