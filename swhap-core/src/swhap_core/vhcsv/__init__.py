"""``swhap_core.vhcsv`` — the canonical ``version_history.csv`` module.

The single implementation of the FROZEN csv-contract.md (core T4). It provides:

  * a strict canonical-profile parser/validator (:func:`parse`,
    :func:`parse_canonical`),
  * a READ-ONLY legacy (Unipisa/DT2SG + guide) reader that converts into the
    canonical model, flagging every lossy/ambiguous conversion
    (:func:`convert_legacy`) — never writes legacy,
  * a typed result model (:class:`Row`, :class:`ParsedDate`,
    :class:`Diagnostic`, :class:`Worklist`, :class:`ParseResult`) with stable
    ``CSV-*`` diagnostic codes the validator consumes directly, and
  * the canonical (sole) WRITER (:func:`write`) with byte-identical,
    round-trip-stable output.

Stdlib-only at runtime.
"""

from __future__ import annotations

from .dates import parse_date, serialize_date
from .grammar import (
    CANONICAL_HEADER,
    HEADER_BYTES,
    HEADER_SHA256,
    parse_canonical,
    validate_field,
    validate_tag,
    write,
)
from .legacy import convert as convert_legacy
from .model import (
    CSV_AMBIGUOUS_US_DATE,
    CSV_DATE,
    CSV_DATE_ORDER,
    CSV_DUP_DIR,
    CSV_DUP_TAG,
    CSV_FIELD,
    CSV_HEADER,
    CSV_TAG,
    CSV_TZ,
    FAIL,
    INFO,
    WARN,
    Diagnostic,
    ParsedDate,
    ParseResult,
    Row,
    Worklist,
)


def parse(data: bytes, *, profile: str = "canonical", reference_date=None,
          **kwargs) -> ParseResult:
    """Parse ``version_history.csv`` bytes.

    ``profile='canonical'`` (default) runs the strict §2–§10 parser/validator.
    ``profile='legacy'`` runs the read-only Unipisa/guide converter (§11).
    ``reference_date`` (canonical only) is the §4.5 future-date baseline: a
    full-timestamp string, a :class:`ParsedDate`, or ``None`` (check skipped,
    one INFO note).
    """
    if profile == "canonical":
        return parse_canonical(data, reference_date=reference_date)
    if profile == "legacy":
        return convert_legacy(data, **kwargs)
    raise ValueError(f"unknown profile {profile!r} (expected 'canonical' or 'legacy')")


__all__ = [
    "parse",
    "parse_canonical",
    "convert_legacy",
    "write",
    "parse_date",
    "serialize_date",
    "validate_field",
    "validate_tag",
    "CANONICAL_HEADER",
    "HEADER_BYTES",
    "HEADER_SHA256",
    "Row",
    "ParsedDate",
    "Diagnostic",
    "Worklist",
    "ParseResult",
    "FAIL",
    "WARN",
    "INFO",
    "CSV_HEADER",
    "CSV_FIELD",
    "CSV_DATE",
    "CSV_TZ",
    "CSV_TAG",
    "CSV_DUP_DIR",
    "CSV_DUP_TAG",
    "CSV_DATE_ORDER",
    "CSV_AMBIGUOUS_US_DATE",
]
