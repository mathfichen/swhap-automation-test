"""CM-1..4 — codemeta.json as SWH (swh-indexer) consumes it (C2 / D9).

CM-1 JSON parse; CM-2 @context in the vendored accepted-context set (tracked
DATA, not a constant) with the distinct not-yet-accepted message; CM-3 headless
JSON-LD expand with pyld against vendored contexts (network forbidden) — clearly
skipped if pyld is absent; CM-4 term audit (funding/maintainer MUST pass;
funder-vs-funding INFO).
"""
from __future__ import annotations

import json
import os

from ..report import FAIL, INFO, WARN, Finding

_DATA = os.path.join(os.path.dirname(__file__), "..", "data")

# Indexer-blacklisted terms (validator plan CM-4): present but dropped by SWH.
_BLACKLIST = {"softwareRequirements", "softwareSuggestions", "creator"}


def _load_data(name):
    with open(os.path.join(_DATA, name), encoding="utf-8") as fh:
        return json.load(fh)


def _accepted():
    d = _load_data("accepted-contexts.json")
    return set(d["accepted"]), set(d["known_newer_not_yet_accepted"]), d["vendored_context_files"]


def _contexts_of(doc):
    ctx = doc.get("@context")
    if ctx is None:
        return []
    if isinstance(ctx, str):
        return [ctx]
    if isinstance(ctx, list):
        return [c for c in ctx if isinstance(c, str)]
    return []


def run(report, repo_ctx, *, codemeta_bytes):
    """Run CM checks over the codemeta.json bytes from the default branch."""
    report.ran("CM-1")
    if codemeta_bytes is None:
        report.add(Finding(
            "CM-1", FAIL, {"path": "metadata/codemeta.json"}, ["path"],
            "The metadata file codemeta.json is missing from the workbench.",
            remediation="Add metadata/codemeta.json (CodeMeta 2.0).",
        ))
        return

    try:
        doc = json.loads(codemeta_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        report.add(Finding(
            "CM-1", FAIL, {"path": "metadata/codemeta.json"}, ["path"],
            "The metadata file codemeta.json is not valid JSON and cannot be read.",
            message_technical=f"json parse error: {exc}",
            remediation="Fix the JSON syntax in metadata/codemeta.json.",
        ))
        return

    accepted, newer, vendored = _accepted()
    contexts = _contexts_of(doc)

    # ---- CM-2: @context membership -------------------------------------
    report.ran("CM-2")
    unknown = [c for c in contexts if c not in accepted]
    cm2_ok = bool(contexts) and not unknown
    if not contexts:
        report.add(Finding(
            "CM-2", FAIL, {"path": "metadata/codemeta.json"}, ["path"],
            "codemeta.json has no @context, so Software Heritage would silently "
            "drop ALL of its metadata.",
            remediation="Set @context to the CodeMeta 2.0 context "
            "https://doi.org/10.5063/schema/codemeta-2.0 .",
        ))
    for c in unknown:
        if c in newer:
            report.add(Finding(
                "CM-2", FAIL, {"context": c}, ["context"],
                "The @context is a valid CodeMeta version that Software Heritage "
                "does not accept yet, so all metadata would be silently dropped.",
                message_technical=(
                    "valid CodeMeta but not yet accepted by swh-indexer — "
                    "metadata would be silently dropped; regenerate with an "
                    "accepted context or wait for indexer support"),
                remediation="Regenerate with an accepted context "
                "(default: https://doi.org/10.5063/schema/codemeta-2.0).",
            ))
        else:
            report.add(Finding(
                "CM-2", FAIL, {"context": c}, ["context"],
                "The @context is not one Software Heritage recognizes, so SWH "
                "will silently drop ALL metadata for this software.",
                message_technical=f"unknown @context {c!r}; not in accepted set",
                remediation="Use the CodeMeta 2.0 context "
                "https://doi.org/10.5063/schema/codemeta-2.0 .",
            ))

    # ---- CM-3: headless JSON-LD expand (pyld, offline) -----------------
    _run_cm3(report, doc, contexts, vendored, cm2_ok)

    # ---- CM-4: term audit ----------------------------------------------
    report.ran("CM-4")
    keys = {k for k in doc.keys() if not k.startswith("@")}
    for term in sorted(keys & _BLACKLIST):
        report.add(Finding(
            "CM-4", WARN, {"term": term}, ["term"],
            f"The field '{term}' is ignored by Software Heritage and will not "
            "appear in the archived metadata.",
            required_approver_role="curator",
            remediation=f"Remove '{term}' or accept that SWH will drop it.",
        ))
    # funder vs funding: INFO only; funding & maintainer MUST pass (no finding).
    if "funder" in keys and "funding" not in keys:
        report.add(Finding(
            "CM-4", INFO, {"term": "funder"}, ["term"],
            "This record uses 'funder' (the funding organization). 'funding' "
            "(the grant) is a distinct, optional field.",
            required_approver_role="none",
        ))


def _run_cm3(report, doc, contexts, vendored, cm2_ok):
    try:
        from pyld import jsonld
    except Exception:  # pragma: no cover - environment dependent
        # Do NOT silently skip: an absent JSON-LD backend means the one check
        # that reproduces swh-indexer's @context processing did not run, and a
        # silently-dropped codemeta.json is the D9 / critique-C2 failure mode.
        # Record the non-enforcement loudly as a WARN so the report never
        # claims coverage it does not have.
        report.ran("CM-3")
        report.add(Finding(
            "CM-3", WARN, {"path": "metadata/codemeta.json"}, ["path"],
            "codemeta.json was NOT checked the way Software Heritage processes "
            "it (the JSON-LD engine is unavailable), so a context that SWH "
            "would silently reject could pass unnoticed.",
            message_technical="pyld not installed; CM-3 JSON-LD expand/compact "
            "not performed. Install the 'jsonld' extra so CM-3 enforces.",
            required_approver_role="curator",
            remediation="Install pyld (validator 'jsonld' extra) and re-run, "
            "or accept the unverified @context at your own risk.",
        ))
        return
    if not cm2_ok:
        report.skip("CM-3", "context not in accepted set (CM-2 FAIL); cannot expand offline")
        return

    report.ran("CM-3")
    loader = _offline_loader(vendored)
    try:
        expanded = jsonld.expand(doc, options={"documentLoader": loader})
        jsonld.compact(expanded, doc.get("@context"),
                       options={"documentLoader": loader})
    except Exception as exc:
        report.add(Finding(
            "CM-3", FAIL, {"path": "metadata/codemeta.json"}, ["path"],
            "codemeta.json could not be processed as JSON-LD the way Software "
            "Heritage processes it.",
            message_technical=f"pyld expand/compact failed: {exc}",
            remediation="Check the @context and the field structure.",
        ))


def _offline_loader(vendored):
    """A pyld document loader that serves ONLY vendored context files and
    raises on any other URL (network forbidden, validator plan CM-3)."""
    cache = {}
    base = os.path.join(_DATA)
    for url, rel in vendored.items():
        with open(os.path.join(base, rel), encoding="utf-8") as fh:
            cache[url] = json.load(fh)

    def loader(url, options=None):
        if url in cache:
            return {"contextUrl": None, "documentUrl": url, "document": cache[url]}
        raise RuntimeError(f"offline loader refused network fetch of {url!r}")

    return loader
