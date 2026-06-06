# `swhap-validate`

Read-only SWHAP-compliance validator. Emits a `validation-report` v1 document
(frozen contract: `specs/validator-report.md` + `specs/validator-report.schema.json`)
and an exit code; it never mutates the workbench. Runtime is stdlib-only (`pyld`
is an optional `jsonld` extra that lets CM-3 enforce; absent, CM-3 WARNs loudly
rather than silently skipping).

## Profiles

| Profile | Model | Enforcement |
|---|---|---|
| `strict-P` | brief §9 (orphan `SourceCode`, pure `main`) | all findings `enforced: true` |
| `strict-G` | current-guide model | all findings `enforced: true` |
| `legacy` | D2/C3 read-only audit (the AX5/T10 precision vehicle) | every finding `enforced: false` except `PC-*`; severities unchanged |

The legacy profile **tolerates documented installed-base dialects** (non-canonical
CSV headers via the read-only converter — FIX-1; a root-level `codemeta.json` —
FIX-2) so they do not raise FALSE failures, while still surfacing genuine defects
(e.g. a wrapper directory → BP-5, a bogus `@context` → CM-2) as FAIL-classified,
`enforced: false` findings. The exit code answers "did the audit run?"; the
findings answer "what did it find?" (validator-report §4.2).

## PI-1 personal-email lint — opt-in clearing, never default clearing

PI-1 (`swhap_validate/checks/pii.py`) WARNs on a real (non-placeholder) personal
email in the `version_history.csv` author/curator fields. It is cleared **only**
by an EXPLICIT curator-approved opt-in and is **never cleared by default**:

- The **only** thing that clears a PI-1 finding is a journal opt-in entry: a
  `provenance-transition` action, by a `curator`-kind actor, moving the item
  `pii.curator_email` to state `curator-approved` (journal-schema §5.5/§6;
  csv-contract §5.2; validator-report §2.5b).
- That opt-in is **per-repo** (the journal is the repo's ledger) and **per-item**
  (`pii.curator_email` only — it clears the *curator email*, never an *author
  email*). There is no environment flag, no CLI switch, and no global default.
- Consequence (the property this guarantees): a real email is **never silently
  published** for some other acquisition because an unrelated repo once opted in.
  Absent the exact `pii.curator_email → curator-approved` entry in *this* repo's
  journal, the finding is always emitted.
- The literal address is **never** reproduced in the report regardless of opt-in
  or severity: findings carry the salted-HMAC redaction token, with the literal
  domain only for public-provider addresses (validator-report §2.5b). The opt-in
  is **not** an `ai-consent` entry (that carries AI-provider consent only).

## Legacy-audit fixtures and the e2e harness

`fixtures/legacy/` holds synthetic, license-clean fixture workbenches that
reproduce the two AX5/T10 legacy-profile defect SHAPES (not copies of the
third-party repos). `tools/validator/tests/test_legacy_audit_e2e.py` runs the
validator's legacy profile against them and asserts the precision result — zero
false failures on the tolerated dialects, genuine defects still FAIL — so the
audit is re-derivable in the normal pytest suite from a clean checkout. See
`fixtures/legacy/README.md` for the mapping to the real published acquisitions.
