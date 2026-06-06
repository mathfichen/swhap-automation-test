"""Canonical ``version_history.csv`` date parsing for the history builder.

Implements exactly the three accepted forms of csv-contract §4.1 and produces
the ``(epoch_seconds, offset, precision)`` triple of §4.3:

  ``YYYY-MM-DDTHH:MM:SS±HH:MM`` / ``…Z``  → precision ``second``
  ``YYYY-MM-DD``                          → UTC midnight, precision ``day``
  ``YYYY``                                → ``YYYY-01-01T00:00:00+00:00``, ``year``

``epoch_seconds`` is the true UTC instant (negative for pre-1970, crit-M3 — the
1968 Softi exercise). The offset is preserved in git raw form ``±HHMM`` so
``GIT_AUTHOR_DATE='@<epoch> ±HHMM'`` renders faithfully. Naive timestamps (time
with no offset) are rejected (CSV-TZ); a space separator, fractional seconds or
any other shape is CSV-DATE. This is the builder-local reader of the §4 grammar;
the canonical single implementation is ``swhap_core.vhcsv`` (core T4) — this
module codes to the same frozen contract and is kept byte-compatible with it.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from ..errors import CsvContractError
from ..model import ReleaseDate

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

_RE_YEAR = re.compile(r"^\d{4}$")
_RE_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_RE_FULL = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})"
    r"(Z|[+-]\d{2}:\d{2})$"
)


def _instant(dt: datetime) -> int:
    return int((dt - _EPOCH).total_seconds())


def parse_date(raw: str) -> ReleaseDate:
    """Parse a canonical date string → ``ReleaseDate``. Raises ``CsvContractError``."""
    m = _RE_FULL.match(raw)
    if m:
        y, mo, d, hh, mm, ss, off = m.groups()
        if off == "Z":
            offset_min = 0
            off_raw = "+0000"
        else:
            sign = 1 if off[0] == "+" else -1
            oh, om = int(off[1:3]), int(off[4:6])
            if om > 59 or not (-12 * 60 <= sign * (oh * 60 + om) <= 14 * 60):
                raise CsvContractError(f"date offset out of range: {raw!r}", code="CSV-DATE", value=raw)
            offset_min = sign * (oh * 60 + om)
            off_raw = f"{off[0]}{oh:02d}{om:02d}"
        try:
            tz = timezone.utc if offset_min == 0 else _fixed_tz(offset_min)
            dt = datetime(int(y), int(mo), int(d), int(hh), int(mm), int(ss), tzinfo=tz)
        except ValueError as exc:
            raise CsvContractError(f"invalid calendar date {raw!r}: {exc}", code="CSV-DATE", value=raw) from exc
        return ReleaseDate(epoch=_instant(dt), offset=off_raw, precision="second")

    m = _RE_DATE.match(raw)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        try:
            dt = datetime(y, mo, d, tzinfo=timezone.utc)
        except ValueError as exc:
            raise CsvContractError(f"invalid calendar date {raw!r}: {exc}", code="CSV-DATE", value=raw) from exc
        return ReleaseDate(epoch=_instant(dt), offset="+0000", precision="day")

    if _RE_YEAR.match(raw):
        dt = datetime(int(raw), 1, 1, tzinfo=timezone.utc)
        return ReleaseDate(epoch=_instant(dt), offset="+0000", precision="year")

    # a naive timestamp (time component, no offset) is the one we name specially.
    if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$", raw):
        raise CsvContractError(
            f"naive timestamp (time without UTC offset): {raw!r}", code="CSV-TZ", value=raw
        )
    raise CsvContractError(f"unrecognized date form: {raw!r}", code="CSV-DATE", value=raw)


def _fixed_tz(offset_min: int):
    from datetime import timedelta

    return timezone(timedelta(minutes=offset_min))
