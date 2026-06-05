"""CSV-1..7 — version_history.csv contract (csv-contract.md, frozen grammar).

CSV-1 is a validator-LOCAL byte-exact header check (parser-independent, M1a).
CSV-2..7 implement the frozen grammar locally for the M1a slice; once
swhap_core.vhcsv lands (core T4, M1c) the grammar parse/date/legacy logic is to
be delegated there (the validator never re-implements it long term). Diagnostics
map to check ids per csv-contract §10:
  CSV-HEADER→CSV-1, CSV-FIELD→CSV-2/CSV-6, CSV-DATE/CSV-TZ→CSV-3,
  CSV-TAG→CSV-4, CSV-DUP-*→CSV-5, CSV-DATE-ORDER→CSV-7 (WARN).
"""
from __future__ import annotations

import csv as _csv
import io
import re
import unicodedata

from ..report import FAIL, WARN, Finding

CANONICAL_HEADER = (
    "directory name,date,author name,author email,"
    "curator name,curator email,release tag,commit message"
)
CANONICAL_HEADER_BYTES = CANONICAL_HEADER.encode("ascii")
BOM = b"\xef\xbb\xbf"

# Legacy dialects (csv-contract §11.0.1), field-4 label differs.
_LEGACY_TOKENS = {
    "unipisa": ["directory name", "author name", "author email", "date",
                "curator name", "curator email", "release tag", "commit message"],
    "guide": ["directory name", "author name", "author email", "date original",
              "curator name", "curator email", "release tag", "commit message"],
}

_FIELDS = ["directory name", "date", "author name", "author email",
           "curator name", "curator email", "release tag", "commit message"]

_ADDR_SPEC = re.compile(
    r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
    r"@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$"
)
_LEN_CAPS = {0: 255, 2: 255, 4: 255, 3: 254, 5: 254, 6: 128, 7: 16384}


def _legacy_match(tokens):
    norm = [t.strip().casefold() for t in tokens]
    for name, ref in _LEGACY_TOKENS.items():
        if norm == [t.casefold() for t in ref]:
            return name
    return None


def run(report, *, csv_bytes, profile, reference_date=None):
    report.ran("CSV-1")
    if csv_bytes is None:
        report.add(Finding(
            "CSV-1", FAIL, {"path": "metadata/version_history.csv"}, ["path"],
            "The metadata file version_history.csv is missing.",
            remediation="Add metadata/version_history.csv with the canonical header.",
        ))
        return

    first_line = csv_bytes.split(b"\n", 1)[0].rstrip(b"\r")

    if first_line.startswith(BOM):
        report.add(Finding(
            "CSV-1", FAIL, {"path": "metadata/version_history.csv"}, ["path"],
            "version_history.csv starts with a UTF-8 BOM, which must be removed.",
            message_technical="file starts with a UTF-8 BOM — remove it",
            remediation="Save the file as UTF-8 without a byte-order mark.",
        ))
        return

    if first_line != CANONICAL_HEADER_BYTES:
        # Canonical profile: any deviation is CSV-HEADER FAIL. Add a hint if it
        # looks like a recognized legacy dialect.
        try:
            tokens = next(_csv.reader([first_line.decode("utf-8", "replace")]))
        except Exception:
            tokens = first_line.decode("utf-8", "replace").split(",")
        legacy = _legacy_match(tokens)
        if legacy:
            hint = ("legacy Unipisa/guide dialect — use "
                    "`swhap csv convert --from unipisa`")
            tech = f"non-canonical header; matches legacy '{legacy}' dialect"
        else:
            hint = "use the canonical 8-column SWHAP header"
            tech = ("header not byte-exact; expected: " + CANONICAL_HEADER)
        report.add(Finding(
            "CSV-1", FAIL, {"path": "metadata/version_history.csv"}, ["path"],
            "version_history.csv does not use the canonical SWHAP header, so the "
            "release history cannot be read.",
            message_technical=tech,
            remediation=hint,
        ))
        return

    # Header is canonical → parse and run CSV-2..7.
    try:
        text = csv_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        report.add(Finding(
            "CSV-2", FAIL, {"path": "metadata/version_history.csv"}, ["path"],
            "version_history.csv is not valid UTF-8.",
            message_technical=f"utf-8 decode error at byte {exc.start}",
        ))
        return

    rows = list(_csv.reader(io.StringIO(text)))
    data = rows[1:]
    _check_rows(report, data, profile, reference_date)


def _check_rows(report, data, profile, reference_date):
    for cid in ("CSV-2", "CSV-3", "CSV-4", "CSV-5", "CSV-6", "CSV-7"):
        report.ran(cid)

    # drop trailing empty line artifact
    data = [r for r in data if r != []]
    if not data:
        report.add(Finding(
            "CSV-2", FAIL, {"path": "metadata/version_history.csv"}, ["path"],
            "version_history.csv has a header but no release rows.",
        ))
        return

    dir_seen, tag_seen = {}, {}
    prev_instant = None
    for i, row in enumerate(data):
        rown = i + 1  # data row number (1-based, header excluded)
        if len(row) != 8:
            report.add(Finding(
                "CSV-2", FAIL, {"row": rown, "field_count": len(row)},
                ["row"],
                f"Row {rown} of version_history.csv has {len(row)} fields "
                "instead of the required 8.",
                message_technical="CSV-FIELD: arity != 8",
            ))
            continue
        fields = dict(zip(_FIELDS, row))

        _check_field_allowlist(report, rown, row)
        _check_emails(report, rown, fields)
        instant = _check_date(report, rown, fields["date"], reference_date)
        _check_tag(report, rown, fields["release tag"])

        # uniqueness (CSV-5) via casefold(NFC) folding
        dkey = _fold(fields["directory name"])
        if dkey in dir_seen:
            report.add(Finding(
                "CSV-5", FAIL, {"rows": sorted([dir_seen[dkey], rown])},
                ["rows"],
                f"Rows {dir_seen[dkey]} and {rown} have colliding directory names.",
                message_technical="CSV-DUP-DIR: casefold(NFC) collision",
            ))
        else:
            dir_seen[dkey] = rown
        tkey = _fold(fields["release tag"])
        if tkey in tag_seen:
            report.add(Finding(
                "CSV-5", FAIL, {"rows": sorted([tag_seen[tkey], rown])},
                ["rows"],
                f"Rows {tag_seen[tkey]} and {rown} have colliding release tags.",
                message_technical="CSV-DUP-TAG: casefold(NFC) collision",
            ))
        else:
            tag_seen[tkey] = rown

        # CSV-7 monotonicity (WARN)
        if instant is not None and prev_instant is not None and instant < prev_instant:
            report.add(Finding(
                "CSV-7", WARN, {"row": rown}, ["row"],
                f"Row {rown} has an earlier date than the row before it; the "
                "curator should confirm this is the real history.",
                message_technical="CSV-DATE-ORDER",
                required_approver_role="curator",
            ))
        if instant is not None:
            prev_instant = instant


def _fold(s):
    return unicodedata.normalize("NFC", s).casefold()


def _check_field_allowlist(report, rown, row):
    for idx, val in enumerate(row):
        fname = _FIELDS[idx]
        # control chars (Cc) — LF allowed only in commit message (idx 7)
        for k, ch in enumerate(val):
            cat = unicodedata.category(ch)
            if cat == "Cc" and not (idx == 7 and ch == "\n"):
                report.add(Finding(
                    "CSV-6", FAIL, {"row": rown, "field": fname, "char_index": k},
                    ["row", "field", "char_index"],
                    f"Row {rown} field '{fname}' contains a control character "
                    "that is not allowed.",
                    message_technical=f"CSV-FIELD: Cc U+{ord(ch):04X} at char {k}",
                ))
                break
            if cat == "Cf":
                name = unicodedata.name(ch, "")
                report.add(Finding(
                    "CSV-6", FAIL, {"row": rown, "field": fname, "char_index": k},
                    ["row", "field", "char_index"],
                    f"Row {rown} field '{fname}' contains an invisible formatting "
                    "character that is not allowed.",
                    message_technical=f"CSV-FIELD: U+{ord(ch):04X} {name} at char {k}",
                ))
                break
        # empties
        if val == "":
            report.add(Finding(
                "CSV-2", FAIL, {"row": rown, "field": fname}, ["row", "field"],
                f"Row {rown} field '{fname}' is empty; all 8 fields are required.",
                message_technical="CSV-FIELD: empty field",
            ))
            continue
        # leading/trailing whitespace
        if val != val.strip():
            report.add(Finding(
                "CSV-6", FAIL, {"row": rown, "field": fname}, ["row", "field"],
                f"Row {rown} field '{fname}' has leading or trailing whitespace.",
                message_technical="CSV-FIELD: edge whitespace",
            ))
        # leading dash forbidden in fields 1-7
        if idx != 7 and val.startswith("-"):
            report.add(Finding(
                "CSV-6", FAIL, {"row": rown, "field": fname}, ["row", "field"],
                f"Row {rown} field '{fname}' starts with '-', which is not allowed.",
                message_technical="CSV-FIELD: leading dash (argv-injection hygiene)",
            ))
        # length cap
        cap = _LEN_CAPS.get(idx)
        if cap and len(val.encode("utf-8")) > cap:
            report.add(Finding(
                "CSV-6", FAIL, {"row": rown, "field": fname}, ["row", "field"],
                f"Row {rown} field '{fname}' is too long (> {cap} bytes).",
                message_technical=f"CSV-FIELD: exceeds {cap}-byte cap",
            ))
        # <> in name fields
        if fname in ("author name", "curator name") and ("<" in val or ">" in val):
            report.add(Finding(
                "CSV-6", FAIL, {"row": rown, "field": fname}, ["row", "field"],
                f"Row {rown} field '{fname}' contains '<' or '>', which are not "
                "allowed in a name.",
                message_technical="CSV-FIELD: git-ident-meaningful <> in name",
            ))
        # directory name single component / traversal
        if fname == "directory name":
            if "/" in val or "\\" in val or val in (".", "..") \
                    or val.startswith(".") or ":" in val:
                report.add(Finding(
                    "CSV-6", FAIL, {"row": rown, "field": fname}, ["row", "field"],
                    f"Row {rown} directory name '{val}' is not a single safe path "
                    "component.",
                    message_technical="CSV-FIELD: not one path component / traversal",
                ))


def _check_emails(report, rown, fields):
    for fname in ("author email", "curator email"):
        val = fields[fname]
        if val == "":
            continue
        if not _ADDR_SPEC.match(val):
            report.add(Finding(
                "CSV-2", FAIL, {"row": rown, "field": fname}, ["row", "field"],
                f"Row {rown} field '{fname}' is not a valid email address.",
                message_technical="CSV-FIELD: not a bare RFC 5322 addr-spec",
            ))


_DATE_FULL = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})"
    r"(Z|[+-]\d{2}:\d{2})$")
_DATE_DAY = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_DATE_YEAR = re.compile(r"^(\d{4})$")


def _check_date(report, rown, val, reference_date):
    """Return the UTC instant (epoch seconds) on success, else None.
    Emits CSV-3 findings for grammar/calendar/tz/future violations."""
    import calendar
    import datetime as dt

    def fail(msg, tech):
        report.add(Finding(
            "CSV-3", FAIL, {"row": rown, "field": "date"}, ["row", "field"],
            msg, message_technical=tech,
            remediation="Use ISO-8601: YYYY, YYYY-MM-DD, or "
            "YYYY-MM-DDTHH:MM:SS±HH:MM.",
        ))

    m = _DATE_FULL.match(val)
    if m:
        y, mo, d, hh, mm, ss, off = m.groups()
        y, mo, d, hh, mm, ss = map(int, (y, mo, d, hh, mm, ss))
        if off != "Z":
            oh, om = int(off[1:3]), int(off[4:6])
            if not (-12 <= (oh if off[0] == "+" else -oh) <= 14) or om > 59:
                fail(f"Row {rown} date has an out-of-range timezone offset.",
                     "CSV-DATE: offset out of range")
                return None
        try:
            base = dt.datetime(y, mo, d, hh, mm, ss)
        except ValueError:
            fail(f"Row {rown} date '{val}' is not a real calendar date/time.",
                 "CSV-DATE: invalid calendar value")
            return None
        offset_sec = 0
        if off != "Z":
            sign = 1 if off[0] == "+" else -1
            offset_sec = sign * (int(off[1:3]) * 3600 + int(off[4:6]) * 60)
        instant = calendar.timegm(base.timetuple()) - offset_sec
        return _future_check(report, rown, val, instant, reference_date)

    m = _DATE_DAY.match(val)
    if m:
        y, mo, d = map(int, m.groups())
        try:
            base = dt.datetime(y, mo, d)
        except ValueError:
            fail(f"Row {rown} date '{val}' is not a real calendar date.",
                 "CSV-DATE: invalid calendar value")
            return None
        instant = calendar.timegm(base.timetuple())
        return _future_check(report, rown, val, instant, reference_date)

    m = _DATE_YEAR.match(val)
    if m:
        y = int(m.group(1))
        instant = calendar.timegm(dt.datetime(y, 1, 1).timetuple())
        return _future_check(report, rown, val, instant, reference_date)

    # Not one of the three forms. Distinguish naive-time (CSV-TZ) from grammar.
    if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$", val):
        report.add(Finding(
            "CSV-3", FAIL, {"row": rown, "field": "date"}, ["row", "field"],
            f"Row {rown} date '{val}' has a time but no timezone offset; the "
            "timezone must be given explicitly.",
            message_technical="CSV-TZ: naive timestamp",
            remediation="Add a UTC offset, e.g. ...T10:00:00+00:00.",
        ))
        return None
    fail(f"Row {rown} date '{val}' is not an accepted date form.",
         "CSV-DATE: grammar")
    return None


def _future_check(report, rown, val, instant, reference_date):
    if reference_date is None:
        return instant  # §4.5: not evaluated without a reference (INFO carried elsewhere)
    if instant > reference_date:
        report.add(Finding(
            "CSV-3", FAIL, {"row": rown, "field": "date"}, ["row", "field"],
            f"Row {rown} date '{val}' is in the future relative to the "
            "acquisition; release dates must be historical.",
            message_technical="CSV-DATE: future date (reference-pinned)",
        ))
        return None
    return instant


def _check_tag(report, rown, tag):
    bad = _ref_format_violation(tag)
    if bad:
        report.add(Finding(
            "CSV-4", FAIL, {"row": rown, "field": "release tag"},
            ["row", "field"],
            f"Row {rown} release tag '{tag}' is not a valid git tag name.",
            message_technical=f"CSV-TAG: {bad}",
            remediation="Use a tag like v1.0.",
        ))
        return
    if tag.startswith("candidate/") or tag.startswith("scratch/"):
        report.add(Finding(
            "CSV-4", FAIL, {"row": rown, "field": "release tag"},
            ["row", "field"],
            f"Row {rown} release tag '{tag}' uses a reserved namespace.",
            message_technical="CSV-TAG: reserved candidate/ or scratch/ namespace",
        ))


def _ref_format_violation(tag):
    """Pure-Python equivalent of git check-ref-format refs/tags/<tag>."""
    if tag == "" or tag == "@":
        return "empty or '@'"
    if tag.startswith("/") or tag.endswith("/") or "//" in tag:
        return "leading/trailing or double slash"
    if tag.endswith("."):
        return "trailing dot"
    if ".." in tag:
        return "contains '..'"
    if "@{" in tag:
        return "contains '@{'"
    for ch in tag:
        o = ord(ch)
        if o < 0x20 or o == 0x7F or ch in " ~^:?*[\\":
            return f"forbidden character U+{o:04X}"
    for comp in tag.split("/"):
        if comp.startswith("."):
            return "component starts with '.'"
        if comp.endswith(".lock"):
            return "component ends with '.lock'"
    return None
