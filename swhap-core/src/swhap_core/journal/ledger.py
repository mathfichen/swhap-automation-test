"""Append-only, hash-chained ledger writer + verifier (journal-schema.md).

Stdlib-only at runtime (no ``jsonschema`` import here — schema validation is a
test-only / validator concern; this module enforces the structural rules it owns:
canonical form, integer-only numbers, surrogate-free strings, the hash chain, and
the genesis rule). The canonical form of an entry is exactly

    json.dumps(e, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

and the entry hash is sha256 over those line bytes (newline excluded) — §3.2.

Journal ``ts`` is real wall-clock time: the ledger is deliberately **not**
bit-reproducible (§4). D4 reproducibility is carried by the ``curation-timestamp``
entry, whose ``epoch``/``offset`` is the fixed committer/tagger date reused by
every rebuild; two deterministic rebuilds append two ``apply`` entries with
different ``ts`` and identical ``outputs[].git_object`` — that pair is the recorded
evidence of reproducibility.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone

from .. import __version__
from ..errors import JournalError

JOURNAL_SCHEMA = "swhap-journal/1"
_ZERO = "0" * 64
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


# --- ULID -------------------------------------------------------------------
def new_ulid(ts_ms: int | None = None, rand: bytes | None = None) -> str:
    """A Crockford-base32 ULID (``^[0-7][0-9A-HJKMNP-TV-Z]{25}$``)."""
    ts = int(time.time() * 1000) if ts_ms is None else ts_ms
    rnd = os.urandom(10) if rand is None else rand
    num = int.from_bytes(ts.to_bytes(6, "big") + rnd, "big")
    chars = []
    for _ in range(26):
        chars.append(_CROCKFORD[num & 0x1F])
        num >>= 5
    return "".join(reversed(chars))


# --- canonical serialization ------------------------------------------------
def _assert_serializable(value) -> None:
    """Reject non-integer numbers and lone surrogates (§3.2) before they reach
    the ledger, where they would silently break canonicality at verify time."""
    if isinstance(value, bool):
        return
    if isinstance(value, float):
        raise JournalError("ledger entries must not contain non-integer numbers", code="JL-SCHEMA")
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise JournalError("ledger string carries a lone surrogate", code="JL-SCHEMA") from exc
        return
    if isinstance(value, dict):
        for k, v in value.items():
            _assert_serializable(k)
            _assert_serializable(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _assert_serializable(v)


def canonical_bytes(entry: dict) -> bytes:
    _assert_serializable(entry)
    return json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def entry_hash(line_bytes: bytes) -> str:
    return hashlib.sha256(line_bytes).hexdigest()


# --- envelope helpers -------------------------------------------------------
def machine_actor() -> dict:
    return {"kind": "machine", "name": "swhap", "tool": "swhap-core", "version": __version__}


def _now_ts() -> str:
    # journal-schema §4 (Timestamp policy): ts is REAL wall-clock UTC, deliberately
    # OUTSIDE the D4 commit/tag-hash envelope. The journal is intentionally NOT
    # byte-reproducible (wall-clock ts + random ULID id) — do NOT "fix" this to be
    # deterministic; D4 reproducibility is carried by the curation-timestamp entry,
    # and two rebuilds with differing ts + identical outputs ARE the evidence of it.
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_entry(action: str, *, actor: dict | None = None, ts: str | None = None, **payload) -> dict:
    """Build an envelope (without ``prev_entry_sha256`` — set by ``Ledger.append``)."""
    entry = {
        "schema": JOURNAL_SCHEMA,
        "id": new_ulid(),
        "ts": ts or _now_ts(),
        "actor": actor or machine_actor(),
        "action": action,
    }
    for k in ("inputs", "outputs", "provenance_transitions", "details"):
        if k in payload and payload[k] is not None:
            entry[k] = payload[k]
    return entry


# --- the ledger -------------------------------------------------------------
class Ledger:
    """Append-only ledger backed by ``metadata/journal.jsonl``."""

    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def _lines(self) -> list[bytes]:
        if not os.path.exists(self.path):
            return []
        with open(self.path, "rb") as fh:
            return fh.read().splitlines()

    def is_empty(self) -> bool:
        return not self._lines()

    def tip_hash(self) -> str:
        lines = self._lines()
        return entry_hash(lines[-1]) if lines else _ZERO

    def ensure_genesis(self, workbench: str, *, git_version: str = "") -> dict | None:
        """Append the genesis entry if the ledger is empty; return it (or None)."""
        if not self.is_empty():
            return None
        details = {"workbench": workbench}
        if git_version:
            details["git_version"] = git_version
        entry = new_entry("genesis", details=details)
        return self.append(entry, _genesis=True)

    def append(self, entry: dict, *, _genesis: bool = False) -> dict:
        lines = self._lines()
        if not lines and entry.get("action") != "genesis":
            raise JournalError("first ledger entry must be the genesis", code="JL-CHAIN")
        if lines and entry.get("action") == "genesis":
            raise JournalError("genesis is only valid at line 1", code="JL-CHAIN")
        entry = dict(entry)
        entry["prev_entry_sha256"] = _ZERO if _genesis else self.tip_hash()
        line = canonical_bytes(entry)
        with open(self.path, "ab") as fh:
            fh.write(line + b"\n")
        return entry

    def read_entries(self) -> list[dict]:
        return [json.loads(line) for line in self._lines()]

    def verify(self) -> None:
        """Structural self-check (chain + canonical form). Raises ``JournalError``."""
        prev = _ZERO
        seen_ids: set[str] = set()
        lines = self._lines()
        for n, line in enumerate(lines):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                raise JournalError(f"line {n}: not JSON", code="JL-SCHEMA") from exc
            if canonical_bytes(entry) != line:
                raise JournalError(f"line {n}: not canonical form", code="JL-SCHEMA")
            if n == 0 and entry.get("action") != "genesis":
                raise JournalError("line 0 is not the genesis", code="JL-CHAIN")
            if n > 0 and entry.get("action") == "genesis":
                raise JournalError(f"line {n}: duplicate genesis", code="JL-CHAIN")
            if entry["id"] in seen_ids:
                raise JournalError(f"line {n}: duplicate id {entry['id']}", code="JL-CHAIN")
            seen_ids.add(entry["id"])
            if entry["prev_entry_sha256"] != prev:
                raise JournalError(f"line {n}: chain break", code="JL-CHAIN")
            prev = entry_hash(line)
