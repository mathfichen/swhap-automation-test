"""CSV-1..7 — version_history.csv contract, delegated to ``swhap_core.vhcsv``.

The frozen csv-contract.md grammar (header §2.1, RFC-4180 structure §2.4, field
allowlist §8, email §5.3, date §4, tag §6, uniqueness §7, monotonicity §7) has a
SINGLE implementation: ``swhap_core.vhcsv`` (core T4). This check is now a THIN
adapter — it no longer re-implements any grammar. It calls
``vhcsv.parse(profile='canonical')`` and maps the returned ``CSV-*`` diagnostics
onto the validator's CSV-1..7 findings per csv-contract §10:

    CSV-HEADER → CSV-1 (byte-exact header incl. BOM §2.2)
    CSV-FIELD  → CSV-2 (§2.4 structure / §3 arity-empties / §5.3 email)
              or CSV-6 (§8 field allowlist)
    CSV-DATE / CSV-TZ → CSV-3
    CSV-TAG    → CSV-4
    CSV-DUP-DIR / CSV-DUP-TAG → CSV-5
    CSV-DATE-ORDER (WARN) → CSV-7

Severity is the closed FAIL/WARN/INFO enum shared with the report schema
(validator-report §2.3). Per csv-contract §10 the two file-level **INFO** notes
(§2.4 unnecessary quoting; §4.5 skipped future-date check) "raise nothing and
never affect exit status" and reuse stable FAIL code strings — so this adapter
FILTERS BY SEVERITY (FAIL + the CSV-7 WARN), never by code, and does not surface
the INFO notes as CSV-1..7 findings (matching the M1a validator behaviour and the
frozen test contract). The only logic kept validator-LOCAL is the file-presence
precondition (a missing file is not a grammar question) and the byte-exact
header literal reused by the CLI. Runtime: stdlib only (``swhap_core.vhcsv`` is
itself stdlib-only).
"""
from __future__ import annotations

from swhap_core import vhcsv

from ..report import FAIL, WARN, Finding

# Reused by the CLI (intake_profile sniff) and the test suite. The single source
# of truth is the core module; we re-export it under the historical names.
CANONICAL_HEADER = vhcsv.CANONICAL_HEADER
CANONICAL_HEADER_BYTES = vhcsv.HEADER_BYTES

# vhcsv CSV-* code → validator check id (csv-contract §10). CSV-FIELD is the one
# code that splits across two checks; resolved by violated section below.
_CODE_TO_CHECK = {
    vhcsv.CSV_HEADER: "CSV-1",
    vhcsv.CSV_DATE: "CSV-3",
    vhcsv.CSV_TZ: "CSV-3",
    # Legacy-only WARN (§11.3): an ambiguous US slash date the converter resolved
    # to MM/DD. It is a date-grammar observation → CSV-3 (a WARN, never a FAIL):
    # the US date format is a tolerated legacy dialect, not a defect.
    vhcsv.CSV_AMBIGUOUS_US_DATE: "CSV-3",
    vhcsv.CSV_TAG: "CSV-4",
    vhcsv.CSV_DUP_DIR: "CSV-5",
    vhcsv.CSV_DUP_TAG: "CSV-5",
    vhcsv.CSV_DATE_ORDER: "CSV-7",
}


def _check_id(diag) -> str:
    cid = _CODE_TO_CHECK.get(diag.code)
    if cid is not None:
        return cid
    # CSV-FIELD: §8 allowlist violations are CSV-6; everything else (§2.x
    # structure, §3 arity/empties, §5.3 email syntax, §7 no-data-rows) is CSV-2.
    if diag.code == vhcsv.CSV_FIELD:
        return "CSV-6" if (diag.section or "").startswith("§8") else "CSV-2"
    # Defensive default: any unmapped FAIL still surfaces (never silently lost).
    return "CSV-2"


def run(report, *, csv_bytes, profile, reference_date=None):
    """Validate ``metadata/version_history.csv``.

    Profile-aware parsing (FIX-1, AX5/T10): the **legacy** audit profile is
    contractually required to *tolerate* the recognized legacy CSV dialects
    (Unipisa/DT2SG + guide: date in col 4, ``*`` tag, ``|`` message separators —
    csv-contract §11). For those targets the strict canonical parser raised a
    CSV-1 ``CSV-HEADER`` FAIL ("not byte-exact") — a FALSE failure under the
    legacy profile (validator-report §4.2 line 254: "legacy dialect accepted via
    converter … canonical-header absence not a finding"). So in the legacy
    profile we route a non-canonical header through the read-only legacy
    converter (``vhcsv.parse(profile='legacy')``), which converts a recognized
    dialect with zero FAILs and only FAILs (CSV-1) when the header matches NO
    recognized dialect — preserving detection of a genuinely broken header.

    A byte-exact canonical CSV is still held to the strict canonical grammar in
    every profile (a canonical file is valid everywhere, and legacy auditing it
    strictly catches real canonical defects). The strict-P/strict-G profiles are
    unchanged: a legacy dialect there is still a CSV-1 FAIL.

    ``reference_date`` is the §4.5 future-date baseline. The CLI passes an int
    epoch (``cli._parse_reference_date``); we wrap it as a ``ParsedDate`` so the
    core parser (which accepts ``None`` / ``str`` / ``ParsedDate``) can apply the
    check without re-deriving any date math.
    """
    report.ran("CSV-1")

    if csv_bytes is None:
        report.add(Finding(
            "CSV-1", FAIL, {"path": "metadata/version_history.csv"}, ["path"],
            "The metadata file version_history.csv is missing.",
            remediation="Add metadata/version_history.csv with the canonical header.",
        ))
        return

    # CSV-2..7 are "reachable" exactly when the header is byte-exact (otherwise
    # the core parser stops at the header diagnostic). Mirror that so the report
    # pass-count reflects which checks actually got to evaluate rows.
    first_line = csv_bytes.split(b"\n", 1)[0].rstrip(b"\r")
    is_canonical_header = first_line == CANONICAL_HEADER_BYTES
    if is_canonical_header:
        for cid in ("CSV-2", "CSV-3", "CSV-4", "CSV-5", "CSV-6", "CSV-7"):
            report.ran(cid)

    # Legacy audit profile + non-canonical header → read-only legacy converter.
    use_legacy = (profile == "legacy") and not is_canonical_header

    ref = reference_date
    if isinstance(ref, int):
        ref = vhcsv.ParsedDate(ref, 0, "second")

    if use_legacy:
        result = vhcsv.parse(csv_bytes, profile="legacy")
    else:
        result = vhcsv.parse(csv_bytes, profile="canonical", reference_date=ref)

    # Filter by SEVERITY, not code: surface FAIL + WARN (e.g. CSV-7 date order,
    # or the legacy ambiguous-US-date WARN); drop the file-level INFO notes
    # (csv-contract §10 — they affect nothing).
    for diag in result.diagnostics:
        if diag.severity not in (FAIL, WARN):
            continue
        _emit(report, diag)


def _emit(report, diag):
    check_id = _check_id(diag)
    obj, keys = _subject(diag, check_id)
    report.add(Finding(
        check_id, diag.severity, obj, keys,
        _plain(diag),
        message_technical=_technical(diag),
        required_approver_role="curator",
    ))


def _subject(diag, check_id):
    """Build the finding object + subject keys (the finding-id basis, §2.1)."""
    if check_id == "CSV-1":
        return {"path": "metadata/version_history.csv"}, ["path"]

    # Duplicate dir/tag: the subject is the colliding row PAIR (stable id).
    other = diag.extra.get("other_row") if diag.extra else None
    if other is not None and diag.row is not None:
        return {"rows": sorted([other, diag.row])}, ["rows"]

    obj: dict = {}
    keys: list[str] = []
    if diag.row is not None:
        obj["row"] = diag.row
        keys.append("row")
    if diag.field_name is not None:
        obj["field"] = diag.field_name
        keys.append("field")
    if diag.char_index is not None:
        obj["char_index"] = diag.char_index
        keys.append("char_index")
    if not keys:  # file-level (e.g. UTF-8 decode, header-only) → stable path id
        return {"path": "metadata/version_history.csv"}, ["path"]
    return obj, keys


def _plain(diag) -> str:
    """Plain-language, forge-safe message. The core diagnostics never echo a raw
    control byte (offenders are named by code point), but run through bsafe_str
    anyway so no control char can reach a forge-visible report (§2.5a)."""
    from ..report import bsafe_str

    prefix = ""
    if diag.row is not None:
        where = f"Row {diag.row}"
        if diag.field_name:
            where += f" field '{diag.field_name}'"
        prefix = where + ": "
    return bsafe_str(prefix + diag.message)


def _technical(diag) -> str:
    """Code- and section-tagged technical string. Carries the stable ``CSV-*``
    code verbatim (e.g. ``CSV-TZ``) and any named code point, which downstream
    tooling and the frozen tests key on."""
    from ..report import bsafe_str

    sec = f" {diag.section}" if diag.section else ""
    return bsafe_str(f"{diag.code}{sec}: {diag.message}")
