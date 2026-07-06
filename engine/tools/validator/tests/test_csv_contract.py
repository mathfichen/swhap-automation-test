"""CSV-1..7 over the frozen csv-contract grammar (csv-contract §12.3 cases)."""
import csv as _csv
import io

import pytest

from swhap_validate.checks import csv_contract
from swhap_validate.report import Report, FAIL, WARN

HEADER = csv_contract.CANONICAL_HEADER
GOOD = ["0.90", "1993-08-09", "Wild_LIFE authors",
        "wildlife-authors@noreply.example.org", "Example Curator",
        "example-curator@noreply.example.org", "v0.90", "Wild_LIFE 0.90"]


def csv_bytes(rows, header=HEADER):
    buf = io.StringIO()
    buf.write(header + "\n")
    w = _csv.writer(buf, lineterminator="\n")
    for r in rows:
        w.writerow(r)
    return buf.getvalue().encode("utf-8")


def run(rows=None, *, header=HEADER, profile="strict-P", reference_date=None,
        raw=None):
    rep = Report(profile, "build")
    data = raw if raw is not None else csv_bytes(rows or [GOOD], header=header)
    csv_contract.run(rep, csv_bytes=data, profile=profile,
                     reference_date=reference_date)
    return rep


def checks(rep, cid):
    return [f for f in rep.findings if f.check_id == cid]


def mutate(idx, val, base=None):
    r = list(base or GOOD)
    r[idx] = val
    return r


# -- canonical green ---------------------------------------------------------

def test_canonical_green():
    rep = run([GOOD])
    assert not [f for f in rep.findings if f.severity == FAIL]


# -- I1/I2/I3: header --------------------------------------------------------

def test_I1_bad_header_csv1():
    raw = b"version,date,source_url,filename,sha256,authors,notes\n"
    rep = run(raw=raw)
    assert checks(rep, "CSV-1") and checks(rep, "CSV-1")[0].severity == FAIL


def test_I2_bom_header_csv1_names_bom():
    raw = b"\xef\xbb\xbf" + HEADER.encode() + b"\n"
    rep = run(raw=raw)
    f = checks(rep, "CSV-1")[0]
    assert "BOM" in (f.message_technical or "")


def test_I3_legacy_header_csv1_hint():
    legacy = ("directory name,author name,author email,date,"
              "curator name,curator email,release tag,commit message")
    rep = run(raw=(legacy + "\n").encode())
    f = checks(rep, "CSV-1")[0]
    assert "legacy" in (f.message_technical or "").lower()


# -- FIX-1 (AX5/T10): legacy CSV dialect tolerated in the legacy profile -----
# A recognized Unipisa/DT2SG legacy CSV (date in col 4, `*` tag, `|` message
# separators, US slash dates) is a tolerated dialect (csv-contract §11); it must
# produce ZERO FAIL under the legacy profile, while still FAILing under strict
# and a genuinely unrecognized header must still FAIL even under legacy.

# Real installed-base shape (mirrors Unipisa/CMM-Workbench): unipisa header, a
# `*` tag, `|`-separated message, and an ambiguous US MM/DD slash date.
_LEGACY_UNIPISA = (
    "directory name,author name,author email,date,"
    "curator name,curator email,release tag,commit message\n"
    "1.3,Giuseppe Attardi,attardi@di.unipi.it,11/07/1994 17:36:34,"
    "CMM Curation Team,guido.scatena@unipi.it,*,"
    '"|Contributors:| - Giuseppe Attardi"\n'
).encode("utf-8")


def test_FIX1_legacy_dialect_zero_fail_in_legacy_profile():
    """The false alarm: a recognized legacy dialect raised CSV-1 FAIL before the
    fix. Under the legacy profile it must now produce zero FAIL of any kind."""
    rep = run(raw=_LEGACY_UNIPISA, profile="legacy")
    assert not [f for f in rep.findings if f.severity == FAIL]
    # The US slash date is surfaced informationally, never as a FAIL.
    warns = [f for f in rep.findings if f.severity == WARN]
    assert any(f.check_id == "CSV-3" for f in warns)


def test_FIX1_legacy_dialect_still_fails_in_strict():
    """Detection is not weakened: the same legacy dialect is still a CSV-1 FAIL
    under the strict profiles (the dialect is never written, D2)."""
    for prof in ("strict-P", "strict-G"):
        rep = run(raw=_LEGACY_UNIPISA, profile=prof)
        assert checks(rep, "CSV-1") and checks(rep, "CSV-1")[0].severity == FAIL


def test_FIX1_unrecognized_header_still_fails_in_legacy():
    """Detection is not weakened: a header matching NO recognized dialect is a
    real defect and must still FAIL CSV-1 even under the legacy profile."""
    raw = b"version,date,source_url,filename,sha256,authors,notes\n"
    rep = run(raw=raw, profile="legacy")
    assert checks(rep, "CSV-1") and checks(rep, "CSV-1")[0].severity == FAIL


# -- I4..I6 dates (CSV-3) ----------------------------------------------------

def test_I4_naive_timestamp_csv3():
    rep = run([mutate(1, "1994-03-24T10:00:00")])
    assert any("CSV-TZ" in (f.message_technical or "") for f in checks(rep, "CSV-3"))


def test_I5_us_date_csv3():
    assert checks(run([mutate(1, "08/09/1993")]), "CSV-3")


def test_I6_calendar_invalid_csv3():
    assert checks(run([mutate(1, "1994-02-30")]), "CSV-3")


def test_year_only_and_full_offset_green():
    assert not checks(run([mutate(1, "1995")]), "CSV-3")
    assert not checks(run([mutate(1, "1996-11-05T14:30:00+01:00")]), "CSV-3")


def test_I21_future_date_with_reference_csv3():
    ref = csv_contract  # noqa
    from swhap_validate.cli import _parse_reference_date
    rd = _parse_reference_date("2026-06-05T00:00:00+00:00")
    assert checks(run([mutate(1, "2026-12-31")], reference_date=rd), "CSV-3")


def test_future_date_skipped_without_reference():
    assert not checks(run([mutate(1, "2026-12-31")]), "CSV-3")


# -- I7/I8/I17: uniqueness (CSV-5) -------------------------------------------

def test_I7_dup_tag_csv5():
    r1 = mutate(6, "v1.0", mutate(0, "0.90"))
    r2 = mutate(6, "v1.0", mutate(0, "0.91"))
    assert checks(run([r1, r2]), "CSV-5")


def test_I8_dup_dir_csv5():
    r1 = mutate(6, "v0.90", mutate(0, "0.90"))
    r2 = mutate(6, "v0.91", mutate(0, "0.90"))
    assert checks(run([r1, r2]), "CSV-5")


def test_I17_casefold_collision_csv5():
    r1 = mutate(6, "v1.0", mutate(0, "0.90"))
    r2 = mutate(6, "V1.0", mutate(0, "0.91"))
    assert checks(run([r1, r2]), "CSV-5")


# -- I9: tag (CSV-4) ---------------------------------------------------------

@pytest.mark.parametrize("tag", ["v1.0..final", "candidate/v1.0", "v1.0.lock",
                                 "v 1.0", "v1.0~"])
def test_I9_bad_tags_csv4(tag):
    assert checks(run([mutate(6, tag)]), "CSV-4")


def test_bare_version_tag_ok():
    assert not checks(run([mutate(6, "1.1")]), "CSV-4")


# -- I10..I20: field allowlist (CSV-6) / CSV-2 -------------------------------

def test_I10_leading_dash_csv6():
    assert checks(run([mutate(2, "--exec=evil")]), "CSV-6")


def test_I11_angle_brackets_in_name_csv6():
    assert checks(run([mutate(4, "Roberto <roberto@dicosmo.org>")]), "CSV-6")


def test_I12_control_char_csv6():
    assert checks(run([mutate(2, "ESC\x1b]0;pwned")]), "CSV-6")


def test_I13_traversal_dirname_csv6():
    assert checks(run([mutate(0, "../../etc")]), "CSV-6")


def test_I14_empty_message_csv2():
    assert checks(run([mutate(7, "")]), "CSV-2")


def test_I15_bad_email_csv2():
    assert checks(run([mutate(3, "not-an-email")]), "CSV-2")


def test_I16_arity_csv2():
    raw = csv_bytes([GOOD[:7]])  # 7 fields
    assert checks(run(raw=raw), "CSV-2")


def test_I19_rlo_bidi_csv6_names_codepoint():
    rep = run([mutate(2, "Peter‮yoR naV")])
    f = checks(rep, "CSV-6")[0]
    assert "U+202E" in (f.message_technical or "")


def test_I20_zwsp_in_tag_csv6():
    rep = run([mutate(6, "v1.0​")])
    assert any("U+200B" in (f.message_technical or "") for f in checks(rep, "CSV-6"))


def test_leading_dash_allowed_in_message():
    assert not checks(run([mutate(7, "- fix a bug")]), "CSV-6")


# -- W1: monotonicity (CSV-7, WARN) ------------------------------------------

def test_W1_date_order_warn_csv7():
    r1 = mutate(1, "1994-03-24", mutate(6, "v1.0", mutate(0, "1.0")))
    r2 = mutate(1, "1993-08-09", mutate(6, "v0.90", mutate(0, "0.90")))
    rep = run([r1, r2])
    cs = checks(rep, "CSV-7")
    assert cs and cs[0].severity == WARN
    assert not [f for f in rep.findings if f.severity == FAIL]
