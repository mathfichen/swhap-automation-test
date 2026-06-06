"""Machine-appended SWHAP journal ledger (``swhap-journal/1``).

Canonical provenance record (Q11): ``metadata/journal.jsonl``, append-only,
hash-chained, one canonically-serialized entry per line (journal-schema.md).
Layer-1 code is the sole author; the AI layer never appends. This package owns
the envelope, canonical serialization, the hash chain, and the build-time entry
builders (``genesis``, ``curation-timestamp``, ``plan``, ``apply``).
"""

from __future__ import annotations

from .ledger import (
    JOURNAL_SCHEMA,
    Ledger,
    canonical_bytes,
    entry_hash,
    machine_actor,
    new_entry,
    new_ulid,
)

__all__ = [
    "JOURNAL_SCHEMA",
    "Ledger",
    "canonical_bytes",
    "entry_hash",
    "machine_actor",
    "new_entry",
    "new_ulid",
]
