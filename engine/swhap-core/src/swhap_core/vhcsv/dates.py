"""Date grammar (csv-contract §4 — the frozen Q9 defaults).

Three accepted forms (§4.1): full timestamp ``YYYY-MM-DDTHH:MM:SS±HH:MM`` (``Z``
accepted on read, never emitted), date-only ``YYYY-MM-DD`` ⇒ UTC midnight
precision ``day``, year-only ``YYYY`` ⇒ ``YYYY-01-01T00:00:00+00:00`` precision
``year`` provenance **inferred**. A time component without an offset is
``CSV-TZ`` (FAIL, §4.2) — never guessed. Pre-1970 dates are first-class with a
negative epoch (§4.4); there is no floor year. Calendar validity is enforced via
the proleptic Gregorian calendar (§4.1).

The result is the internal triple ``ParsedDate(epoch_seconds, offset_minutes,
precision)`` (§4.3). The serializer lives on ``ParsedDate`` (§4.6).
"""

from __future__ import annotations

import re
from datetime import datetime

from .model import CSV_DATE, CSV_TZ, ParsedDate, _EPOCH

# §4.1: literal ``T``; 4-digit year; 2-digit M/D/H/M/S; offset ±HH:MM or Z.
_RE_FULL = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(Z|[+-]\d{2}:\d{2})$"
)
_RE_NAIVE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")  # time, no offset
_RE_DAY = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_RE_YEAR = re.compile(r"^(\d{4})$")


class _DateError(Exception):
    def __init__(self, code: str, message: str, section: str):
        super().__init__(message)
        self.code = code
        self.message = message
        self.section = section


def _parse_offset(off: str) -> int:
    """``±HH:MM`` / ``Z`` ⇒ signed minutes; range −12:00..+14:00 (§4.1)."""
    if off == "Z":
        return 0
    sign = 1 if off[0] == "+" else -1
    oh = int(off[1:3])
    om = int(off[4:6])
    if om > 59:
        raise _DateError(CSV_DATE, f"offset minutes {om:02d} out of range 00–59", "§4.1")
    signed = sign * (oh * 60 + om)
    if signed < -720 or signed > 840:
        raise _DateError(CSV_DATE, f"UTC offset {off} outside -12:00..+14:00", "§4.1")
    return signed


def _epoch(dt_local: datetime, offset_minutes: int) -> int:
    """UTC epoch seconds for a wall-clock ``dt_local`` at ``offset_minutes``.
    Done with timedelta arithmetic (not ``mktime``/``timestamp``) so pre-1970
    dates are exact and platform-independent (§4.4)."""
    return int((dt_local - _EPOCH).total_seconds()) - offset_minutes * 60


def parse_date(value: str) -> tuple[ParsedDate | None, list[tuple[str, str, str]]]:
    """Parse one date column value.

    Returns ``(ParsedDate, [])`` on success, or ``(None, [(code, message,
    section)])`` where ``code`` is ``CSV-DATE`` or ``CSV-TZ``. The future-date
    upper bound (§4.5) is NOT applied here (it needs the reference timestamp);
    the grammar layer applies it.
    """
    try:
        m = _RE_FULL.match(value)
        if m:
            y, mo, d, h, mi, se, off = m.groups()
            offset = _parse_offset(off)
            try:
                dt = datetime(int(y), int(mo), int(d), int(h), int(mi), int(se))
            except ValueError as e:
                raise _DateError(CSV_DATE, f"invalid calendar date/time: {e}", "§4.1")
            return ParsedDate(_epoch(dt, offset), offset, "second"), []

        if _RE_NAIVE.match(value):
            raise _DateError(
                CSV_TZ,
                "timestamp has a time component but no UTC offset; "
                "a naive datetime is never guessed",
                "§4.2",
            )

        m = _RE_DAY.match(value)
        if m:
            y, mo, d = m.groups()
            try:
                dt = datetime(int(y), int(mo), int(d))
            except ValueError as e:
                raise _DateError(CSV_DATE, f"invalid calendar date: {e}", "§4.1")
            return ParsedDate(_epoch(dt, 0), 0, "day"), []

        m = _RE_YEAR.match(value)
        if m:
            y = int(m.group(1))
            try:
                dt = datetime(y, 1, 1)
            except ValueError as e:
                raise _DateError(CSV_DATE, f"invalid year: {e}", "§4.1")
            return ParsedDate(_epoch(dt, 0), 0, "year"), []

        raise _DateError(
            CSV_DATE,
            f"date {value!r} does not match any accepted form "
            "(YYYY-MM-DDTHH:MM:SS±HH:MM | YYYY-MM-DD | YYYY)",
            "§4.1",
        )
    except _DateError as e:
        return None, [(e.code, e.message, e.section)]


def serialize_date(pd: ParsedDate) -> str:
    """Precision-preserving serialization (§4.6)."""
    return pd.serialize()
