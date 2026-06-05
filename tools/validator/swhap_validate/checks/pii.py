"""PI-1 — personal-email lint (crit-M15). WARN per Roberto's W1 ruling.

A real (non-placeholder) personal email in the CSV author/curator fields warns;
a journaled curator-email opt-in clears it entirely. The literal address is
NEVER reproduced in the report regardless of severity (validator-report §2.5b):
findings carry the salted-HMAC redaction token, with the literal domain only for
public-provider addresses.
"""
from __future__ import annotations

import csv as _csv
import hashlib
import hmac
import io
import json
import os

from ..report import WARN, Finding

_DATA = os.path.join(os.path.dirname(__file__), "..", "data")
_FIELDS = ["directory name", "date", "author name", "author email",
           "curator name", "curator email", "release tag", "commit message"]
_ROLE = "curator"
CANON_HEADER = ("directory name,date,author name,author email,"
                "curator name,curator email,release tag,commit message")


def _domains():
    with open(os.path.join(_DATA, "placeholder_domains.json"), encoding="utf-8") as fh:
        d = json.load(fh)
    return set(d["placeholder_domains"]), set(d["public_providers"])


def compute_salt(ctx) -> bytes:
    """repo_pii_salt — content-derived for D4 determinism (validator-report
    §2.5b): sha256 over the sha256 digests of the raw_materials/ archives, in
    path-sorted order. Never emitted in the report."""
    default = ctx.default_branch()
    digests = []
    if default:
        for e in sorted(ctx.ls_tree(f"refs/heads/{default}"), key=lambda x: x.path):
            if e.type == "blob" and e.path.startswith("raw_materials/"):
                digests.append(hashlib.sha256(ctx.cat_blob(e.blob)).hexdigest())
    if not digests:
        return hashlib.sha256(b"swhap:no-raw-materials").digest()
    return hashlib.sha256("".join(digests).encode("ascii")).digest()


def _redact(addr, salt, public):
    norm = addr.strip().lower()
    token = hmac.new(salt, norm.encode("utf-8"), hashlib.sha256).hexdigest()[:12]
    domain = norm.split("@", 1)[1] if "@" in norm else ""
    if domain in public:
        return {"value_hmac12": token, "domain_class": "public-provider",
                "domain": domain}
    return {"value_hmac12": token, "domain_class": "private"}


def _opt_in_present(journal_bytes):
    """True iff the ledger carries a provenance-transition on pii.curator_email
    reaching curator-approved by a curator-kind actor (csv-contract §5.2)."""
    if not journal_bytes:
        return False
    for line in journal_bytes.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("action") != "provenance-transition":
            continue
        if e.get("actor", {}).get("kind") != "curator":
            continue
        for tr in e.get("provenance_transitions", []):
            if tr.get("item") == "pii.curator_email" and tr.get("to") == "curator-approved":
                return True
    return False


def run(report, ctx, *, csv_bytes, journal_bytes):
    report.ran("PI-1")
    if csv_bytes is None:
        return
    first = csv_bytes.split(b"\n", 1)[0].rstrip(b"\r").decode("utf-8", "replace")
    if first != CANON_HEADER:
        return  # PI-1 over CSV only meaningful on canonical columns
    placeholder, public = _domains()
    salt = compute_salt(ctx)
    opt_in = _opt_in_present(journal_bytes)

    try:
        rows = list(_csv.reader(io.StringIO(csv_bytes.decode("utf-8"))))[1:]
    except Exception:
        return
    seen = set()
    for i, row in enumerate(rows):
        if len(row) != 8:
            continue
        f = dict(zip(_FIELDS, row))
        for field in ("author email", "curator email"):
            addr = f[field].strip()
            if not addr or "@" not in addr:
                continue
            domain = addr.split("@", 1)[1].lower()
            if domain in placeholder:
                continue
            if field == "curator email" and opt_in:
                continue  # opt-in clears the finding entirely
            tok = _redact(addr, salt, public)
            key = (field, tok["value_hmac12"])
            if key in seen:
                continue
            seen.add(key)
            obj = {"field": field, "row": i + 1, **tok}
            report.add(Finding(
                "PI-1", WARN, obj, ["field", "value_hmac12"],
                f"Row {i + 1} field '{field}' contains a real personal email "
                "address; please confirm it may be published.",
                message_technical="PI-1: non-placeholder addr-spec (redacted)",
                required_approver_role=_ROLE,
                remediation="Use a noreply placeholder, or record a curator "
                "opt-in in the journal.",
            ))
