# SIGNOFF-W1 — schema freeze signature sheet

Status: **SIGNED 2026-06-05** (Roberto Di Cosmo, in-session). The three W1
contracts are frozen; W2 parallel build proceeds against them. Resolutions
recorded in the "Resolutions" section at the foot of this sheet.
For: Roberto Di Cosmo · Date drafted: 2026-06-05

Signing this sheet **freezes the three W1 contracts** below. W2 parallel build
starts against the frozen text; any change after signature is a versioned
amendment. You sign **decisions**, not prose. Open points are split into
**RULE NOW** (blocks the freeze) and **deferred-with-default** (a default is in
force; you may override later cheaply). Each line is a checkbox: strike to reject.

---

## A. csv-contract — `version_history.csv` contract
Files: `specs/csv-contract.md` (v0.1.1-draft)

Normative decisions being signed:
- [ ] **Q9 default → binding:** year-only date pins to `YYYY-01-01T00:00:00Z`, precision=year, provenance=inferred.
- [ ] Date-only pins to UTC midnight, precision=day, flagged (documented convention; naive timestamps unrepresentable → CSV-TZ).
- [ ] Pre-1970 dates via raw `@<epoch>` GIT_AUTHOR_DATE; no floor year (floor only as later amendment if the pin fails).
- [ ] Future-dated rows (vs reference timestamp) = CSV-DATE FAIL; baseline = recorded curation ts or `--reference-date`, else check skipped with INFO (never wall-clock).
- [ ] **Q9 co-author sub-question → binding:** multi-author = single collective label `<Project> authors` + project email in CSV; per-person attribution in journal/codemeta, optionally Co-authored-by trailers.
- [ ] Leading-dash ban on fields 1–7 only; commit/tag messages exempt — apply.py MUST pass them via stdin, never argv (binding requirement on core T7).
- [ ] Length caps: 255 (dirname/names) / 254 (emails) / 128 (tag) / 16384 (message) bytes.
- [ ] v-prefix tag = INFO-only lint (bare CMM tags valid); `candidate/` and `scratch/` namespaces = CSV-TAG FAIL.
- [ ] Directory name = single path component: no `/ \ . .. :` or leading dot (traversal hygiene at CSV layer).
- [ ] Diagnostic enum closed FAIL/WARN/INFO; CSV-AMBIGUOUS-US-DATE & CSV-DATE-ORDER are WARN (exit 0); `swhap csv convert` applies US MM/DD, WARNs, writes canonical, exits 0.
- [ ] Legacy profile: read-only; naive ts = UTC-assumed precision=second marked lossy; empty messages left empty+flagged; literal `|` preserved in note; ambiguous day≤12 = US reading + WARN with both ISO candidates; uniqueness folds `casefold(NFC(·))`.
- [ ] Canonical writer renders UTC `+00:00` never `Z` (readers accept `Z`); no precision expansion; round-trip identity.
- [ ] Cc+Cf control/format chars (BOM, bidi, zero-width) forbidden in all fields; header-only CSV = CSV-FIELD FAIL; annotated tag message derived (`Version <tag>`), not a CSV field.

RULE NOW:
- [ ] Confirm the four length-cap values (255/254/128/16384) — cheap now, expensive post-freeze.
- [ ] Confirm Cf-character ban (§13.6) and `casefold(NFC)` uniqueness fold basis (§13.7) as drafter rulings.
- [ ] Ratify BOM-strict (canonical profile FAILs on BOM); leniency is a one-line flip.

Deferred-with-default (default in force unless you say otherwise):
- [ ] Q9 year-only = Jan-1-UTC pin vs explicit unknown-within-year sentinel — pin is the default.
- [x] Wild_LIFE 1.02 date — **RESOLVED 2026-06-06 (Roberto): year-only `1994`**
  from the tar-mtime evidence; the `1995` placeholder retired; conformance
  example V4 updated (decision D10 in analysis/decisions.md).

---

## B. validator-report — `validation-report` v1 + exit codes
Files: `specs/validator-report.md`, `specs/validator-report.schema.json`

Normative decisions being signed:
- [ ] One flat document shape; pre-D1 dual-profile = TWO single-profile files (`out.strict-P.json`/`out.strict-G.json`), `--report -` rejected in dual mode (exit 2); process exit = max of per-profile codes.
- [ ] Stable finding id = `<check_id>:<sha256-12 of frozen per-check subject-key projection of object>`; adding non-subject key = minor/id-preserving; changing subject-key set = MAJOR; derivation collision = exit 3.
- [ ] Legacy report-only carried by per-finding `enforced` flag (false in legacy); severity never downgraded; exit follows from quantifying over enforced findings only.
- [ ] PC-* enforced (exit 4) in ALL profiles incl. legacy (shallow clone = 4, not 2).
- [ ] Exit precedence total order: 2 → 3 → 4 → 1 → 0; FAIL>WARN>INFO; counts never matter; curator `state` never bypasses (no approval-as-bypass).
- [ ] Summary frozen: fail/warn/info count findings, pass counts zero-finding checks; `summary.exit_code` == process exit; `run.checks_run` (sorted, required); `run.head` content-derived, kept in canonical output.
- [ ] Audience fields fixed: `message_plain` (non-expert, Profile A) + `message_technical` (expert); vocabulary closed for v1.
- [ ] `schema_version` = constant `"1"` for v1.x; tolerant-reader rules binding (unknown fields ignored, unknown approver role→legal-curator, unknown state→open); severity enum closed, approver-role/state enums open.
- [ ] PI-1 redaction: personal emails never reproduced literally; `value_hmac12 = HMAC-SHA256(repo_pii_salt, normalized addr)[:12]` (salt = content-derived from raw_materials digests, never emitted) + domain-class allowlist; document-wide (PI-1/CSV-2/CSV-6/BP-4).
- [ ] **PI-1 default severity = FAIL** (journaled opt-in makes it pass, not downgrade).
- [ ] Byte-safe `bsafe` encoding for non-UTF-8 subjects & message fields (no raw C0/C1/ANSI); producer owns byte safety, consumer owns markup escaping.
- [ ] Schema `$id` = placeholder `urn:swhap:schema:validation-report:v1`; specs/ copy normative, CI-synced byte-identical to tools/ copy once T1 lands.

RULE NOW:
- [ ] Confirm **PI-1 = FAIL** (validator plan §2.4 left it unstated).
- [ ] Co-sign **PC-* enforced in legacy (exit 4)** with core + cicd-packaging at the M1b exit-code co-sign.
- [ ] Ratify finding-id derivation over the **frozen per-check subject-key subset** (changed from whole-object) and the salted-HMAC PI-1 primitive (changed from unsalted SHA-256+literal domain).

Deferred-with-default:
- [ ] BP-2 `additional_materials/` sub-finding = WARN pending D1 ruling (flips at M1c).
- [ ] Schema `$id` placeholder → https URN once D6 hosting namespace fixed (minor event).
- [ ] `message_plain` English-only v1 vs French rendering — flag at M2 entry (schema-neutral).
- [ ] Dual-mode filename convention + `--report -` rejection — validator CLI owner ratifies before T1.

---

## C. journal-schema — `swhap-journal/1` ledger contract
Files: `specs/journal-schema.md`, `specs/journal-entry.schema.json`

Normative decisions being signed:
- [ ] Canonical store = `metadata/journal.jsonl` (one canonical-JSON line/entry); `journal.md` is a deterministic render, never hand-edited.
- [ ] Entry hash = sha256 over exact JSONL line bytes; canonical = UTF-8 sorted-keys compact JSON, no non-integer numbers (stdlib-only, no RFC 8785).
- [ ] Journal `ts` = real wall-clock UTC; ledger deliberately NOT bit-reproducible (D4 quantifies over commit/tag hashes only); deterministic committer/tagger date lives only in the curation-timestamp entry.
- [ ] Action set frozen at **22** values (added `state-transition`, `annotation`, `apply-proposal`).
- [ ] **Q11 enforced in schema:** `ai`-actor forces `action=annotation` + zero provenance_transitions; transition to `curator-approved` forces curator-kind actor; never initial; machine never transitions FROM `curator-approved`.
- [ ] No-self-hash rule: entries never carry a default-branch commit id; default-branch effects = `{path, sha256}` outputs; carrier commit derived, not stored; coverage binds only source-bearing refs.
- [ ] `rewrite-event` two-phase (D3 interim): curator sign-off w/ `target_refs`+`swhid-invalidation-acknowledged` precedes the machine executed entry; sign-off single-use & scope-exact (set-equal target_refs); DV-1 without executed entry = FAIL.
- [ ] Append-only defined per-lineage vs published default-branch state; recovery genesis (`recovered_from` w/ `superseded_tip_sha256`) = JL-RECOVERED WARN; ULID dup = FAIL, id/ts monotonicity = WARN.
- [ ] Anti-forgery: `machine`/`ai` actors rejected if carrying `login`/`role`/`verified_via`; well-formed Unicode, no lone surrogates; non-UTF-8 names carry lossless `bytes_hex` + U+FFFD decoded.
- [ ] curation-timestamp uniqueness grouped by `details.acquisition` (absent→`__default__`); per-action required-payload shapes schema-enforced.
- [ ] Proposed error codes JL-SCHEMA / JL-RENDER (exit 15) pending error-taxonomy owner co-sign.

RULE NOW:
- [ ] Confirm action-set freeze at 22 (the three additions ratify already-mandated flows; no decision reversed).
- [ ] Confirm Model-G ledger location = `metadata/journal.jsonl` on the default branch (needs check against renderer-G archaeology at the D1 ruling).

Deferred-with-default:
- [ ] Dedicated metadata/ mirror of the D4 curation timestamp beyond plan.json — additive either way (M1b).
- [ ] `plan.json` home path — fixed by plan.json schema owner at M1b (this contract references by path+sha256 only).
- [ ] D3 final ruling (M1c) may restrict `rewrite-event` to pre-archived state — config change, schema unchanged.
- [ ] JL-SCHEMA / JL-RENDER need co-signature from specs/error-codes.md owner (core T2).

---

## D. Cross-spec blockers — RULE NOW (must resolve before freeze)
- [ ] **Curator-email opt-in carrier:** standardize on a `provenance-transition` entry on item id `pii.curator_email` reaching `curator-approved` by a curator-kind actor. Fix validator-report §2.5b to read that (delete the `ai-consent` reference), name the action in journal-schema §5.5 + §6, confirm JC-2/PI-1 read exactly that transition. Do NOT overload `ai-consent`.
- [ ] **Inferred-date visibility carrier:** csv-contract routes year/day-precision flags to the journal provenance ledger, while validator-report §2.9 presumes a CSV-3 finding. Pick ONE: (a) add CSV-DATE-INFERRED/CSV-DATE-IMPRECISE INFO/WARN to csv-contract §10, or (b) drop the §2.9 CSV-3 clause and carry the signal solely via journal provenance. Name the same carrier in both.

---

## E. Curator-email examples — confirm before regenerated CSV/report ship
- [ ] Curator real-email opt-in (`roberto@dicosmo.org`) shown in valid examples per brief §8 precedent — exemplar T5 must confirm the opt-in; intake `questions.yaml` wording must mirror it.

---

## Signature

By signing, I freeze csv-contract, validator-report, and journal-schema as the W1
interface contracts. W2 parallel build proceeds against the signed text. The
RULE-NOW and Cross-spec items above are resolved as marked; deferred-with-default
items run on their stated defaults until I amend them.

Roberto Di Cosmo ___[signed in-session 2026-06-05]___  Date __2026-06-05__

## Resolutions / overrides

1. **PI-1 default severity = WARN, NOT FAIL** (override of drafter B's proposal
   and of sheet items B "PI-1 = FAIL" / RULE-NOW "Confirm PI-1 = FAIL").
   Rationale: lower curator friction; a real curator email warns but does not
   block a build. Redaction of literal addresses in the report stays
   unconditional (privacy preserved); a journaled `pii.curator_email →
   curator-approved` opt-in clears the finding. Applied to validator-report.md
   (registry row + open-point note). csv-contract.md already specified WARN, so
   the two specs are now consistent. GDPR posture (crit-M15) rests on redaction
   + retention policy, not on the lint severity.

2. **All other sheet items (A, B, C, and the engineering RULE-NOW items)
   ratified as drafted.** This includes: length caps 255/254/128/16384; Cf-char
   ban + casefold(NFC) uniqueness fold; BOM-strict canonical profile;
   finding-id over the frozen per-check subject-key subset; salted-HMAC PI-1
   redaction primitive; action-set frozen at 22; PC-* enforced (exit 4) in all
   profiles incl. legacy. Any of these may be revisited later as a versioned
   amendment. Items flagged for M1b co-sign with core/cicd (PC-*-in-legacy,
   Model-G ledger location, exit-code co-sign) remain scheduled there; the
   default stands until then.

3. **Cross-spec blockers (sheet section D) — resolved by the W1 consistency
   pass, confirmed:** (D-1) curator-email opt-in carrier standardized on a
   `pii.curator_email → curator-approved` provenance transition (the
   `ai-consent` overload deleted) — named identically in csv-contract §5,
   validator-report §2.5b, journal-schema §5.5/§6. (D-2) inferred/imprecise-date
   visibility carried **solely via the journal provenance ledger**, not a CSV-3
   finding (option b) — stated consistently in csv-contract §10 and
   validator-report §2.9.

4. **Section E (curator-email in shipped examples) — deferred to exemplar T5**
   as drafted (non-blocking for W2). With PI-1=WARN the spec examples may show a
   real opted-in address or a placeholder; T5 confirms before the regenerated
   CSV ships.
