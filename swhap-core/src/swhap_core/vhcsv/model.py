"""Typed result model for the ``version_history.csv`` contract (csv-contract.md).

This module is pure data: the parsed-row, parsed-date, diagnostic, worklist and
result types that both the canonical grammar (``grammar.py``) and the read-only
legacy reader (``legacy.py``) produce, and that the validator consumes directly.

Diagnostic ``code`` values are the stable ``CSV-*`` codes named verbatim in
csv-contract §10. ``severity`` is the closed FAIL / WARN / INFO enum shared with
the validator report schema (validator-report §2.3). FAIL diagnostics map to
``CsvContractError`` (``errors.py``) and ``swhap`` exit 12; WARN/INFO raise
nothing (§10).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterable

from .. import errors as _errors

# --- closed severity enum (validator-report §2.3) --------------------------
FAIL = "FAIL"
WARN = "WARN"
INFO = "INFO"

# Stable CSV-* codes (csv-contract §10). WARN codes are deliberately ABSENT
# from errors._CSV / CsvContractError (they raise nothing).
CSV_HEADER = "CSV-HEADER"
CSV_FIELD = "CSV-FIELD"
CSV_DATE = "CSV-DATE"
CSV_TZ = "CSV-TZ"
CSV_TAG = "CSV-TAG"
CSV_DUP_DIR = "CSV-DUP-DIR"
CSV_DUP_TAG = "CSV-DUP-TAG"
CSV_DATE_ORDER = "CSV-DATE-ORDER"  # WARN (§7, §10)
CSV_AMBIGUOUS_US_DATE = "CSV-AMBIGUOUS-US-DATE"  # WARN, legacy profile only (§11.3)

# FAIL codes that raise CsvContractError (§10, two disjoint classes by severity).
RAISING_CODES = frozenset(
    {CSV_HEADER, CSV_FIELD, CSV_DATE, CSV_TZ, CSV_TAG, CSV_DUP_DIR, CSV_DUP_TAG}
)

_EPOCH = datetime(1970, 1, 1)  # naive anchor for deterministic epoch math


def _fmt_offset(offset_minutes: int) -> str:
    """``±HH:MM`` (UTC is ``+00:00``, never ``Z`` — §4.6)."""
    sign = "+" if offset_minutes >= 0 else "-"
    a = abs(offset_minutes)
    return f"{sign}{a // 60:02d}:{a % 60:02d}"


def _fmt_raw_offset(offset_minutes: int) -> str:
    """``±HHMM`` for raw ``@<epoch> <offset>`` git author dates (§4.4)."""
    sign = "+" if offset_minutes >= 0 else "-"
    a = abs(offset_minutes)
    return f"{sign}{a // 60:02d}{a % 60:02d}"


@dataclass(frozen=True)
class ParsedDate:
    """The internal date triple (§4.3): the true UTC instant, the preserved
    offset for faithful ``GIT_AUTHOR_DATE`` rendering, and the stored
    precision. ``epoch_seconds`` is negative for pre-1970 dates (§4.4)."""

    epoch_seconds: int
    offset_minutes: int
    precision: str  # 'second' | 'day' | 'year'

    @property
    def inferred(self) -> bool:
        """Year-only ⇒ provenance state **inferred** requiring curator
        visibility (§4.3)."""
        return self.precision == "year"

    @property
    def utc_offset(self) -> str:
        return _fmt_offset(self.offset_minutes)

    def git_author_date(self) -> str:
        """Raw ``@<epoch> ±HHMM`` form passed to git plumbing via env (§4.4) —
        never a formatted date string (the crit-M3 DT2SG/libgit2 failure
        class)."""
        return f"@{self.epoch_seconds} {_fmt_raw_offset(self.offset_minutes)}"

    def serialize(self) -> str:
        """Precision-preserving serialization back to the date column (§4.6).
        Precision expansion is forbidden: a ``year`` value renders as ``YYYY``,
        never an expanded timestamp."""
        if self.precision == "second":
            local = _EPOCH + timedelta(seconds=self.epoch_seconds + self.offset_minutes * 60)
            return local.strftime("%Y-%m-%dT%H:%M:%S") + _fmt_offset(self.offset_minutes)
        utc = _EPOCH + timedelta(seconds=self.epoch_seconds)
        if self.precision == "day":
            return utc.strftime("%Y-%m-%d")
        if self.precision == "year":
            return f"{utc.year:04d}"
        raise ValueError(f"unknown precision {self.precision!r}")


@dataclass(frozen=True)
class Row:
    """One canonical release row (= one commit + one annotated tag, §1)."""

    directory_name: str
    date: ParsedDate
    author_name: str
    author_email: str
    curator_name: str
    curator_email: str
    release_tag: str
    commit_message: str
    row_number: int = 0  # 1-based among data rows; row order = commit order (§7)
    date_raw: str = ""  # original date bytes (provenance / round-trip aid)
    provenance: str = "user-provided"  # canonical default; legacy rows = 'computed'
    notes: tuple[str, ...] = ()  # provenance / precision / conversion notes

    def fields(self) -> list[str]:
        """The 8 column values in canonical order, date precision-serialized."""
        return [
            self.directory_name,
            self.date.serialize(),
            self.author_name,
            self.author_email,
            self.curator_name,
            self.curator_email,
            self.release_tag,
            self.commit_message,
        ]


@dataclass(frozen=True)
class Diagnostic:
    """One CSV-contract diagnostic with a stable ``CSV-*`` code (§10)."""

    code: str
    severity: str  # FAIL | WARN | INFO
    message: str
    section: str = ""  # violated csv-contract section, e.g. "§4.2"
    row: int | None = None  # 1-based data row
    column: int | None = None  # 1-based field number
    field_name: str | None = None
    char_index: int | None = None  # index within the field value
    code_point: str | None = None  # e.g. "U+202E RIGHT-TO-LEFT OVERRIDE"
    byte_offset: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def template_id(self) -> str:
        spec = _errors.CODES.get(self.code)
        return spec.template_id if spec else "tmpl." + self.code.lower().replace("_", "-")

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "section": self.section,
            "template_id": self.template_id,
        }
        for k in ("row", "column", "field_name", "char_index", "code_point", "byte_offset"):
            v = getattr(self, k)
            if v is not None:
                out[k] = v
        if self.extra:
            out.update(self.extra)
        return out


@dataclass(frozen=True)
class Worklist:
    """A legacy-conversion review item (§11.4). Not a CSV-* diagnostic: the
    converter still exits 0 (§10). The curator decides (repair → re-run, or
    accept the omission)."""

    kind: str  # e.g. 'empty-tag', 'real-email', 'empty-message', 'undated', 'invalid-tag'
    message: str
    row: int | None = None
    field_name: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"kind": self.kind, "message": self.message}
        if self.row is not None:
            out["row"] = self.row
        if self.field_name is not None:
            out["field_name"] = self.field_name
        if self.extra:
            out.update(self.extra)
        return out


@dataclass
class ParseResult:
    """Parsed rows + diagnostics (+ legacy worklist). The validator consumes
    this directly; ``raise_on_fail`` is the fail-fast entry point."""

    profile: str  # 'canonical' | 'legacy'
    rows: list[Row]
    diagnostics: list[Diagnostic]
    worklist: list[Worklist] = field(default_factory=list)

    @property
    def failures(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.severity == FAIL]

    @property
    def warnings(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.severity == WARN]

    @property
    def infos(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.severity == INFO]

    @property
    def ok(self) -> bool:
        """True iff there is no FAIL diagnostic (WARN/INFO never block)."""
        return not self.failures

    def codes(self) -> list[str]:
        return [d.code for d in self.diagnostics]

    def raise_on_fail(self) -> None:
        """Raise the ``CsvContractError`` subtype for the first FAIL (§10).
        WARN/INFO are never raised."""
        for d in self.failures:
            raise _errors.error_for_code(
                d.code,
                d.message,
                section=d.section,
                row=d.row,
                column=d.column,
                field_name=d.field_name,
                char_index=d.char_index,
                code_point=d.code_point,
                byte_offset=d.byte_offset,
            )

    def to_json(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "ok": self.ok,
            "rows": [
                {
                    "row_number": r.row_number,
                    "directory_name": r.directory_name,
                    "date": r.date.serialize(),
                    "date_epoch_seconds": r.date.epoch_seconds,
                    "date_offset": r.date.utc_offset,
                    "date_precision": r.date.precision,
                    "author_name": r.author_name,
                    "author_email": r.author_email,
                    "curator_name": r.curator_name,
                    "curator_email": r.curator_email,
                    "release_tag": r.release_tag,
                    "commit_message": r.commit_message,
                    "provenance": r.provenance,
                    "notes": list(r.notes),
                }
                for r in self.rows
            ],
            "diagnostics": [d.to_json() for d in self.diagnostics],
            "worklist": [w.to_json() for w in self.worklist],
        }


def rows_to_bytes(rows: Iterable[Row]) -> bytes:  # convenience re-export hook
    from .grammar import write  # local import to avoid a cycle

    return write(rows)
