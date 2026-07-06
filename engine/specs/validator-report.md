# Contract: validator report (`validation-report` v1) + exit codes

Status: FROZEN (W1 sign-off 2026-06-05). Changes are versioned amendments. PI-1 severity = WARN per Roberto's ruling (see SIGNOFF-W1.md).
Owner: validator workstream (`analysis/impl/validator.md`)
Date: 2026-06-05
Freeze point: M1a (schema v1, exit-code contract); `message_plain` texts reviewed by a
non-expert at M1b; exit-code map co-signed by core-pipeline and cicd-packaging at M1b
(integration resolution #4: two exit-code maps, no third).

Binding inputs: `analysis/decisions.md` (D1, D2, D4, D9), `analysis/impl/validator.md`
(§2.4 check registry, §3.1 provided contracts, §4.1 report essentials, §4.2 profile
matrix, §7 risks 5/6/8), `analysis/implementation-plan.md` §3 (resolutions #4, #6, #9;
binding shape table rows "Validator report schema" and "`check_swhap` CLI + exit map"),
`analysis/brief-critique.md` crit-M11 (the report is the carrier artifact for warnings
and the provenance state machine), crit-M8 (actionable preconditions), crit-M10 (legal
gate), crit-M15 (email lint).

Normative artifacts:

- This document (prose contract).
- `specs/validator-report.schema.json` (JSON Schema, draft 2020-12) — machine-checkable
  shape. Where prose and schema disagree, the **schema wins for shape**, this document
  wins for **semantics** (exit mapping, determinism, versioning).
- When the implementation lands (validator T1), the file
  `tools/validator/schemas/validation-report.v1.schema.json` MUST be byte-identical to
  `specs/validator-report.schema.json`; CI enforces the sync.

Consumers designed for (implementation-plan §3.2): CI gates (cicd-packaging jobs treat
any nonzero exit as job failure and classify from the report JSON), M2 intake
per-persona rendering on the issue thread (intake-curator §2.7), the gated publish step
(hard-requires exit `0` at `--gate publish`; core `swhap publish` refuses with its own
exit 16 otherwise), the AI `explain/` task (keys explanations by finding id, copies
severity/state read-only), pilots-validation's M4 AI-on/off non-interference harness
(byte-comparison of `--run-meta-stable` reports), and milestone gate evidence (M1d,
T10 legacy-audit precision report, M3 cold-start).

---

## 1. Report envelope

One report document = one validation run of one repository under one `(profile, gate)`
pair. Top-level required members: `schema_version`, `tool`, `run`, `summary`,
`findings`; optional `error` (§6.4).

```json
{
  "schema_version": "1",
  "tool": { "name": "swhap-validate", "version": "0.1.0", "commit": "abc123…" },
  "run": {
    "timestamp": "2026-06-05T14:03:22Z",
    "meta_stable": false,
    "profile": "strict-P",
    "gate": "build",
    "strict_warn": false,
    "repo": "/work/Wild_Life-swhap",
    "head": "1571ce5…(40 or 64 hex)",
    "refs_checked": ["refs/heads/SourceCode", "refs/tags/0.90", "…"],
    "intake_profile": "cli",
    "published_remote": "origin",
    "checks_run": ["BP-1", "BP-2", "…"],
    "checks_skipped": [ { "id": "RB-1", "reason": "swhap-core not installed" } ]
  },
  "summary": { "fail": 0, "warn": 2, "info": 1, "pass": 31, "exit_code": 0 },
  "findings": [ … ]
}
```

### 1.1 `tool`

`name` (const `swhap-validate`), `version` (the package version), `commit` (the
validator's own git commit, when built from a checkout; optional). These are
**build-stable**, not run-variant: two runs of the same build emit identical `tool`
blocks, so the block stays in the canonical (comparable) output.

### 1.2 `run` — and the D4 timestamp policy

The **run-variant field set** is exactly: `run.timestamp`, `run.repo`,
`run.invocation`. These are the only fields anywhere in the document that may carry
wall-clock time or machine-/invocation-specific data (absolute paths, argv echo).
Everything else — including every finding — MUST be deterministic given identical
inputs and an identical tool build (D4 discipline applied to the report itself).

- `run.timestamp`: RFC 3339 UTC, second precision, `Z` suffix (e.g.
  `2026-06-05T14:03:22Z`). Never any other timezone.
- `run.repo`: the repository path/URL as invoked.
- `run.invocation` (optional): the argv vector, for gate-evidence audit trails.
- `run.head`: the commit hash the run examined — **content-derived, not run-variant**;
  it stays in canonical output (its equality across AI-on/off runs is itself evidence).
- `run.checks_run`: every check ID executed (registry IDs, §3), sorted byte-wise
  ascending. Load-bearing for the M4 proof: identical `checks_run` proves the same
  battery ran on both sides.
- `run.checks_skipped`: `{id, reason}` entries for checks not executed — whether via
  `--skip`, profile matrix exclusion (e.g. RB-1/DV-1/JC/LG in legacy), gate selection,
  or unavailability (RB-1 when `swhap-core` is absent — "skipped, reported, never
  silent", validator plan risk 3). Sorted by `id`. `reason` strings come from a fixed
  reason vocabulary in the implementation (deterministic, no paths/timestamps).

**`--run-meta-stable` mode** (provided for the M4 byte-comparison, validator plan §1
M4 row and §4.1): the emitted document omits the run-variant field set entirely
(fields **absent**, not `null`, not empty) and sets `run.meta_stable: true`. All other
content is identical to a normal run. Two `--run-meta-stable` reports over identical
inputs with the same tool build MUST be byte-identical (§5). In normal mode
`meta_stable` is `false` (or absent) and `timestamp` + `repo` are required.

### 1.3 `summary`

- `fail` / `warn` / `info`: number of **findings** at each severity.
- `pass`: number of **executed checks** (members of `run.checks_run`) that emitted
  zero findings. (Mixed semantics — findings-counted vs check-counted — is deliberate
  and frozen: a check that emits two WARNs contributes 2 to `warn` and 0 to `pass`.)
- `exit_code`: integer `0|1|2|3|4`, MUST equal the process exit code of the run that
  emitted the report (§4; dual-profile caveat §4.3).

---

## 2. Finding object

```json
{
  "id": "TF-2:8f3a12c4d9e0",
  "check_id": "TF-2",
  "severity": "FAIL",
  "enforced": true,
  "object": { "tag": "1.0", "path": "LICENSE" },
  "message_plain": "The file LICENSE in release 1.0 does not match the original archive…",
  "message_technical": "blob 8f3a… != expected 41c2… (life_10.tgz: LICENSE, 1993 copyright)",
  "required_approver_role": "curator",
  "state": "open",
  "provenance": { "item": "release/1.0/tree", "state": "computed" },
  "remediation": "Rebuild the release from the verified tarball…"
}
```

Required: `id`, `check_id`, `severity`, `enforced`, `object`, `message_plain`,
`required_approver_role`, `state`. Optional: `message_technical`, `provenance`,
`remediation`.

### 2.1 `id` — the stable finding identifier

`id = <check_id> ":" first 12 lowercase-hex chars of SHA-256(canonical(subject))`,
where `subject` is the **registered subject-key projection** of the finding's `object`
(see below) and `canonical(subject)` is the UTF-8 bytes of the JSON serialization of
that projection with keys sorted byte-wise ascending, separators `,`/`:` (no
whitespace), non-ASCII characters unescaped (`ensure_ascii=False`), all string values
already in the byte-safe encoding (§2.5a) so serialization can never raise.

**Subject-key projection (frozen for the v1 line).** Each check declares, in the check
registry, the subset of its `object` keys that *identify the subject* (per-tag,
per-path, per-CSV-row…). The id hash is computed over **only those keys**, not the
whole `object`. This is the load-bearing rule that makes the id durable:

- Adding a **non-subject** key to a check's `object` (the MINOR event of §2.5/§6.2)
  does **not** change any `subject`, so it does **not** re-key existing findings.
- The subject-key set of a check is **frozen across the whole v1 line**. Adding,
  removing, or renaming a subject key is a **MAJOR** event (§6.3) — it changes ids by
  design and ships under `schema_version: "2"`. A builder MUST NOT add a subject key in
  a minor release.

Properties this buys (and which consumers rely on):

- **Durable across reruns over identical inputs AND across v1.x tool upgrades** — the
  AI `explain/` task keys per-finding explanations by this id (ai-layer §3.1/§4);
  intake renders findings as task-list items keyed by it (intake-curator §2.7). Because
  the id depends only on the frozen subject keys, a v0.1→v0.2 upgrade that adds an
  allowed non-subject `object` key (e.g. a `mode` annotation on TF-2) emits the **same
  id** for the same defect: intake task-lists and the AI cache do not churn. Id
  durability across versions is a **contract promise**, not merely a same-run property.
- **Unique within a report** by construction, because the subject MUST uniquely
  identify the finding's subject within its check. A derivation collision is an internal
  error (exit 3), never silently disambiguated.
- Checks with a single global subject MAY use an empty subject (`{}`) and then MUST
  emit at most one finding.

### 2.2 `check_id`

A registry ID (§3). The schema validates it against the **relaxed family pattern**
`^[A-Z]{2,5}-[0-9]+[a-z]?$` (the letter suffix covers staged forms such as `JC-1a`).
The pattern is deliberately *open at the family prefix*: the documented v1 families are
`PC|TF|BP|CSV|CM|SZ|RB|DV|JC|LG|PI`, but **adding a new check family is a MINOR event
(§6.2)** and a later-family ID (e.g. a deeper-legal-model `LM-1`) MUST validate against
an older vendored v1.0 schema copy. The closed list lives in the registry (§3) as
documentation, never as a schema constraint that would let a vendored copy reject a
newer report (§6.2 forbids exactly that rejection).

### 2.3 `severity` — closed enum `FAIL | WARN | INFO`

The check's **intrinsic classification under the active profile+gate**. It is never
downgraded to express non-enforcement (that is `enforced`'s job, §2.4): in the legacy
profile CM-2 stays FAIL-classified — a bogus `@context` is a true defect (validator
plan §4.2). Gate-dependent severity is legitimate (LG-1 is FAIL at `--gate publish`,
WARN at `--gate build`). The enum is **closed for the whole v1 line** because the exit
mapping quantifies over it (§7).

### 2.4 `enforced` — the legacy truthfulness mechanism

Boolean: does this finding participate in exit-code computation (§4)? Strict profiles:
`true` for every finding. Legacy profile: `false` for every finding except PC-\*
(§4.2). This is how "report-only" is represented **without lying anywhere**: the
severity states the truth about the artifact, `enforced: false` states the truth about
the run's enforcement posture, and the exit code follows mechanically.

### 2.5 `object` — machine data

A JSON object carrying the check-specific machine-readable data (tag, path, expected
vs actual hashes, CSV row number, threshold and measured size, ref name…). Constraints
(all MUST):

- Deterministic content only — no wall-clock values, no absolute filesystem paths
  (repo-relative POSIX paths only), no hostnames, PIDs, temp dirs, durations.
- Subject-identifying: the subject-key subset uniquely identifies the finding's subject
  (§2.1). Adding a **non-subject** key is a MINOR schema event (§6); adding/renaming a
  **subject** key is MAJOR (§2.1, §6.3).
- Per-check `object` key vocabularies (and each check's subject-key subset) are owned by
  the validator implementation and documented in the check registry as they land.
  Common keys SHOULD reuse these names: `tag`, `ref`, `path`, `row`, `field`,
  `expected`, `actual`, `size_bytes`, `threshold_bytes`, `item`.
- Every string value MUST obey the byte-safe / string-safety rules of §2.5a.
- Personal email addresses MUST be redacted per §2.5b — in **every** check that would
  otherwise carry one, not only PI-1.

#### 2.5a Byte-safe encoding and string safety (all emitted strings)

This rule governs **every** string the producer emits — `object` string values,
`message_plain`, `message_technical`, `remediation`, `error.message`, and `run`
string fields derived from subject content. The report is forge-visible: CI logs `cat`
it and intake posts message fields verbatim onto issue threads. The producer therefore
**owns** byte-level safety; the boundary is stated here so no builder can assume the
other side does it.

1. **Byte-safe string encoding (mandatory).** Subject bytes (legacy tarball filenames,
   legacy CSV fields in latin-1/cp437/…) are frequently not valid UTF-8. The producer
   MUST transform any such bytes into a JSON string with the deterministic, lossless
   **`bsafe`** encoding rather than crashing or guessing:
   - decode the raw bytes with `errors="surrogateescape"` to a Python `str` `s`;
   - emit each character of `s` as: a literal backslash `U+005C` → `\\`; a lone
     surrogate `U+DC80..U+DCFF` (i.e. an original invalid byte `0x80..0xFF`) → `\x`
     followed by two **lowercase** hex digits of `(codepoint − 0xDC00)`; any C0/C1
     control character (`U+0000..U+001F`, `U+007F..U+009F`) → `\x` + two lowercase hex
     digits of its codepoint; every other character → itself (valid UTF-8 stays real,
     e.g. `é` stays `é`, consistent with `ensure_ascii=False`).
   - The id hash (§2.1) is computed over `object` **after** this encoding, so
     `json.dumps(...).encode("utf-8")` can never raise (`UnicodeEncodeError` on a lone
     surrogate is structurally impossible) and the bytes are identical across
     implementations and machines (M4 / M1d two-machine determinism). Worked example:
     the filename `b"Caf\xe9 mode d'emploi.txt"` (latin-1) → object string
     `"Caf\xe9 mode d'emploi.txt"`. A non-UTF-8 filename is thus a *representable*
     subject, **not** a crash and **not**, by itself, a finding — closing the T10
     legacy-audit exit-3 hole.
2. **No raw control or terminal-control bytes.** Because of rule 1, no raw C0/C1 control
   character, ANSI/OSC escape, or `BEL` ever appears in any emitted string — CSV-6's
   appended `\x01` is published as the literal text `\x01`, an ANSI title-set OSC
   sequence as its `\x1b...` escapes. CI logs and terminals cannot be driven by report
   content.
3. **Markup escaping is the rendering consumer's responsibility, NOT the producer's.**
   The canonical report is plain text/JSON; the producer does **not** HTML- or
   markdown-escape message bodies (doing so would corrupt the deterministic bytes and
   the non-expert review of `message_plain`). Any consumer that renders a string field
   into a markup surface — intake posting `message_*` to a GitHub issue, an HTML report
   viewer — **MUST** escape for that surface (so a CSV-6 value like
   `[click here](https://evil.example/payload)` renders as inert text, not a live
   link). This ownership split is binding: the producer guarantees control-char-free,
   byte-safe strings; the markup-context escaping is the consumer's, and neither side
   may assume the other does the other's half.

#### 2.5b Personal-email redaction (all checks, non-reversible)

The report is forge-visible; the lint must not republish what it lints — and **no
neighbouring check may republish it either**. This rule is therefore **document-wide**,
not PI-1-scoped:

- **Scope.** *Any* finding from *any* check whose subject or message would otherwise
  contain a literal personal email address (PI-1; CSV-2 parse errors and CSV-6
  injection/control-char findings on the `author email`/`curator email` fields; BP-4
  author-identity mismatch, where a CSV `author email` *is* the subject; etc.) MUST
  replace the literal address with the redacted token below in `object`, both message
  fields, and `remediation`. For CSV-6 specifically: describe the defect by the
  **disallowed code points and their byte positions in the field** (e.g.
  `{"row": 3, "field": "author email", "ctl_codepoints": ["U+0001"], "positions": [20]}`)
  rather than echoing the cleartext value.
- **Redacted token (replaces the old unsalted `value_sha256_12` + literal `domain`).**
  `{"value_hmac12": <12 lowercase hex>, "domain_class": "public-provider" | "private",
  "domain": <literal, present ONLY when domain_class == "public-provider">}` where:
  - `value_hmac12` = first 12 lowercase-hex chars of
    `HMAC-SHA256(key = repo_pii_salt, msg = lowercased-normalized full address)`. The
    keying defeats the reversal attack the old scheme enabled: an unsalted truncated
    SHA-256 of a low-entropy `firstname.lastname@gmail.com` (whose names are listed in
    `catalogue.md`) is recoverable in milliseconds; an HMAC under a per-repo key with
    no published salt forces per-repo work and blocks cross-repo rainbow tables.
  - `repo_pii_salt` is **content-derived for D4 determinism**: SHA-256 over the
    concatenation, in `version_history.csv` row order, of the `sha256` digests of the
    `raw_materials/` archives as recorded in the journal `acquire`/`digest` entries
    (deterministic, identical across reruns / AI-on-off / two machines, so §5 byte
    determinism and the M4 comparison hold). It is **never emitted** in the report.
  - `domain_class` + conditional `domain` close the **vanity-domain** leak: a literal
    `jane@janedoe-consulting.com` identifies the person by its domain alone, so the
    literal `domain` is published **only** for addresses on the fixed public-provider
    allowlist (gmail.com, outlook.com, …, maintained in the implementation), where it
    carries no identifying information; every other address reports
    `domain_class: "private"` with **no** literal domain.
- The PI-1 curator-email **opt-in** — a journaled curator-approval
  `provenance-transition` on the curator-email item (item id
  `pii.curator_email` reaching `curator-approved` by a curator-kind actor;
  journal-schema §5.5/§6, csv-contract §5.2) — makes PI-1 *pass* (no finding)
  rather than downgrade; it does not change the redaction of any other check
  that still emits a finding over that address. (This is **not** an
  `ai-consent` entry: that action carries AI-provider consent only.)

### 2.6 Explanation fields and audience tags

Two fixed explanation fields with fixed audience tags (vocabulary `non-expert |
expert`, closed for v1; the schema annotates each field with `x-audience`):

- `message_plain` — audience **`non-expert`** (Profile A). Required, non-empty,
  plain language, self-contained ("what is wrong, in terms of the user's files"). The
  M1b freeze item "plain texts reviewed by a real non-expert" applies to these strings
  (intake W1 / pilots T3 run the session). Intake's Profile-A rendering uses **only**
  this field plus `severity`, `required_approver_role`, `state`, `remediation`.
- `message_technical` — audience **`expert`** (Profiles B/D, curators, CI logs).
  Optional; may reference blob hashes, refs, byte offsets.

Persona→audience mapping is owned by intake (§2.7 there); this contract only
guarantees the tagged fields exist and that `message_plain` never assumes git/CLI
knowledge.

### 2.7 `required_approver_role` — enum `none | curator | legal-curator`

Per crit-M11. `legal-curator` is what LG-1 emits for legal/redistribution items
(`user-provided` is never sufficient — crit-M10/Q10). **Open enum across v1.x** —
validator plan risk 6: a deeper M2 legal model extends it additively (e.g.
`data-protection-officer`). To honour that openness *under the "schema wins for shape"
precedence rule* (Normative artifacts §), the schema encodes the field as
`anyOf: [{enum: [none, curator, legal-curator]}, {type: string}]`: the enum is an
**advisory annotation** of the documented v1 values, and any string validates — so a
consumer using a vendored v1.0 schema copy does **not** reject a v1.x report that
introduces a new role (§6.2). Consumers MUST treat an unrecognized role as "escalate to
the most restrictive known role" (defensive default: `legal-curator`).

### 2.8 `state` — enum `open | acknowledged | curator-approved`

A **derived view** computed at run time from the journal ledger; the ledger is
canonical and the report is never written back (validator plan risk 8 — stated here as a
contract rule to prevent two sources of truth). **Open enum across v1.x**; the schema
encodes it as `anyOf: [{enum: [open, acknowledged, curator-approved]}, {type: string}]`
(advisory enum, any string validates, vendored-copy-safe — §6.2); consumers treat
unknown states as `open`.

**The derivation function (frozen, so two builders cannot invent two link
conventions).** `state` is *not* keyed off the optional `finding.provenance.item` (which
is absent on most checks, e.g. TF-2 carries none). Instead it reads the journal
`state-transition` action — whose frozen `details` shape is `{machine, from, to, ref?}`
(`specs/journal-entry.schema.json`, payload owned by intake-curator) — using a **reserved
per-finding machine namespace**:

- A finding's state machine is named `machine == "finding:" + <finding.id>`. The `id`
  is durable across v1.x (§2.1), so acknowledgements survive tool upgrades.
- `state(finding)` = the `to` value of the **last** (journal-chain order, §journal 5.4)
  `state-transition` entry whose `details.machine == "finding:" + finding.id`; if there
  is no such entry, `state` is `open` (also the value when no ledger exists at all —
  legacy repos, pre-M1c runs).
- **Acknowledgement.** To move a finding off `open`, intake (on the curator's behalf, or
  the curator directly) appends one `state-transition` entry with
  `details = {"machine": "finding:" + id, "from": "open", "to": "acknowledged",
  "ref": <issue/thread url>}`. `to: "curator-approved"` records full approval the same
  way. No journal-contract change is required: this uses the existing frozen
  `state-transition` action and its existing `machine/from/to/ref` keys (the
  `finding:` prefix is the reserved namespace this contract claims). The earlier
  ambiguity — "Builder A invents `annotation.finding_id`, Builder B maps
  `provenance-transition` on an item TF-2 doesn't have" — is closed: the *only*
  spec-conformant carrier of a finding acknowledgement is a `finding:`-namespaced
  `state-transition` entry, and the validator's derivation reads exactly that.
- So a TF-2 stale-`LICENSE` finding (object `{tag:"1.0", path:"LICENSE"}`, no
  `provenance` member) **can** reach `acknowledged`: its acknowledgement is the
  `state-transition` whose `machine == "finding:TF-2:<hash>"`, independent of any
  provenance item. `acknowledged` and `curator-approved` are the two documented
  non-`open` values, each produced solely by such an entry.

When no ledger exists (legacy repos, pre-M1c runs), `state` is `open`.

**`state` never feeds the exit-code computation** in v1, except indirectly through
checks whose own logic reads the ledger (LG-1 passes/fails on item approval states).
A curator cannot "approve away" a TF mismatch; approval is recorded, severity stands.

### 2.9 `provenance` — provenance-state reference

Optional `{item, state}` where `state` ∈ the frozen provenance vocabulary
`observed | computed | inferred | user-provided | curator-approved` (M1b contract
freeze; implementation-plan §3.2) and `item` is the ledger item identifier the finding
is about. REQUIRED on LG-1 findings (the legal gate is precisely about an item's
provenance state); optional elsewhere.

CSV-3 carries **no** provenance member and emits **no** finding for a
valid-but-imprecise date: per csv-contract §10 it is exactly the two FAIL codes
`CSV-DATE` and `CSV-TZ`, and year-only / date-only forms are VALID (csv-contract
§4.1). The "inferred dates require curator visibility" invariant is carried
**solely by the journal provenance ledger** — csv-contract §4.3 routes a
date-only value to a provenance note and a year-only value to provenance state
`inferred` requiring curator visibility (recorded on the date item via a
`provenance-transition`, journal-schema §7). The validator surfaces that state
through the ledger-derived provenance/state machinery, not through a CSV-3
diagnostic. csv-contract §10 and this section therefore name the **same
carrier** (the provenance ledger), so the signal cannot fall through the gap
between the two contracts.

---

## 3. Check-ID registry (reference)

The registry is owned by the validator workstream (validator plan §2.4 is the
authoritative table; this section fixes only the contract-relevant facts). Stable
identifiers; **renames or removals are schema-version (major) events** (validator plan
§3.1.4); additions are minor; retired IDs (e.g. `JC-1a` once JC-1 full lands at M1c)
are reserved forever and never reused; an ID's meaning never changes — changed
semantics means a new ID. The exemplar-pilot defect register's `expected_check` values
and all named red/green tests reference these IDs.

| Family | IDs | Domain | Default severity classification |
|---|---|---|---|
| PC | PC-1..4 | preconditions: full clone, tags fetched, git/python/pyld versions | FAIL ⇒ **exit 4** (crit-M8; shallow clone is 4, not 2) |
| TF | TF-1..5 | tree fidelity vs ground-truth manifests (C4 battery) | FAIL |
| BP | BP-1..5 | branch purity per profile (orphan, allowlist, commit/tag-per-row, identities, wrapper) | FAIL — except the `additional_materials/` admission sub-finding of BP-2: WARN until the D1 ruling (validator plan risk 5) |
| CSV | CSV-1..7 | `version_history.csv` contract (C1/D2/Q9) | FAIL; CSV-7 (row order vs date monotonicity) WARN |
| CM | CM-1..4 | codemeta as-SWH-consumes-it (C2/D9) | CM-1..3 FAIL; CM-4 term audit WARN, funder-vs-funding INFO |
| SZ | SZ-1..5 | size/LFS ladder (crit-M7/N1) | SZ-1/2 FAIL; SZ-3/4 WARN; SZ-5 INFO |
| RB | RB-1 | D4 rebuild-into-scratch-and-compare | FAIL |
| DV | DV-1 | published-remote divergence: refuse *un-journaled, un-archived* divergence (D3 revised 2026-06-06 — a rebuild-and-replace recorded by a `rewrite-event` sign-off with the prior snapshot archived in SWH is ALLOWED; only an accidental/unrecorded clobber FAILs). Implemented 2026-06-07 (M2): enforced at `--gate publish` against `--published-remote` (fast-forward ⇒ PASS; a recorded supersession whose `supersedes_snapshot_swhid` equals the recomputed prior published snapshot ⇒ explained WARN; otherwise FAIL); skipped at `--gate build` and in the legacy profile. | FAIL |
| JC | JC-1 (M1a staged form JC-1a), JC-2 | journal/ledger coverage (Q11, crit-M4/M11) | FAIL |
| LG | LG-1 | legal go/no-go gate (crit-M10/Q10) | FAIL at `--gate publish`; WARN at `--gate build` |
| PI | PI-1 | personal-email lint (crit-M15) | WARN (Roberto's W1 ruling 2026-06-05, overriding the drafter's FAIL); a journaled curator-email opt-in clears the finding entirely. Redaction still applies — the literal address is never reproduced in the report regardless of severity. |

---

## 4. Exit-code contract

The codes (validator plan §3.1.2 — one of exactly two exit maps in the system,
implementation-plan resolution #4; co-signed by core and cicd at M1b; cicd's headless
contract defers to this section by reference, no third map; inputs argv-only, no
`SWHAP_*` env, no `--ci` flag):

| Code | Meaning | Report emitted? |
|---|---|---|
| 0 | pass — no enforced FAIL; WARNs allowed unless `--strict-warn` | yes (required) |
| 1 | ≥ 1 enforced FAIL finding (or enforced WARN under `--strict-warn`) | yes (required) |
| 2 | usage/config error (bad argv, unknown profile/check ID, unwritable `--report` path) | best-effort; MAY be absent |
| 3 | internal tool error (uncaught exception, report self-validation failure, finding-id collision) | best-effort partial, with `error` block |
| 4 | precondition unmet — any PC-\* FAIL (shallow clone, missing tags, version probe); battery beyond preflight not executed | yes (required; PC findings carry the actionable message per crit-M8) |

### 4.1 The exact mapping rule (total, no ambiguity when findings mix)

Evaluated top-down; the first matching rule decides. `E` = the set of findings with
`enforced == true` and `check_id` not in the PC family.

1. If the invocation cannot be parsed/validated → **2**. (Detected before any check
   runs; cannot co-occur with the rules below.)
2. Else if the run aborts on an internal error at any later point → **3**. (3 beats 4
   and 1: a crashed run certifies nothing.)
3. Else if any PC-\* finding has severity FAIL → **4**. (4 beats 1: results computed
   over a bad clone are not trustworthy, so ordinary findings — which are not emitted
   past preflight anyway — never compete with it.)
4. Else if any finding in `E` has severity FAIL → **1**.
5. Else if `--strict-warn` was given and any finding in `E` has severity WARN → **1**.
6. Else → **0**.

Corollaries, stated so no builder has to guess:

- Mixed severities: one enforced FAIL forces 1 regardless of any number of
  WARN/INFO/pass results. FAIL beats WARN beats INFO. **Counts never matter** — the
  exit code carries class, the report carries detail.
- WARN never affects the exit code except under `--strict-warn`. INFO never affects
  it under any flag.
- `state` (incl. `curator-approved`) never enters the computation (§2.8).
- Skipped checks (`checks_skipped`) contribute nothing to the computation but MUST be
  visible in the report.
- `summary.exit_code` MUST equal the process exit code (single-profile runs; §4.3 for
  the pre-D1 dual mode).

### 4.2 Profiles and the legacy non-enforcement representation

`run.profile` ∈ `strict-P | strict-G | legacy` (validator plan §4.2 matrix governs
which checks run and how):

- **strict-P** (brief §9 model: orphan `SourceCode`, pure `main`) and **strict-G**
  (current-guide model): all findings `enforced: true`; full 0/1/2/3/4 semantics.
- **legacy** (D2/C3 read-only audit profile, the T10 precision-audit vehicle):
  TF/BP/CSV/CM/SZ/PI run **report-only** — every finding `enforced: false`, severity
  classification unchanged (CM-2 stays FAIL); RB-1/DV-1/JC-\*/LG-1 are skipped with
  reasons; BP performs structural recognition of observed models. By rule 4's empty
  `E`-set, the exit code is 0 whenever the tool ran correctly — the findings are the
  output. The exit code is therefore **not lying**: it answers "did the audit run?"
  and the report answers "what did it find?", and `enforced: false` on each finding
  plus `run.profile: "legacy"` make that contract machine-visible.
- **PC-\* stays enforced in every profile, including legacy** (drafter ruling
  interpreting the matrix row "always 0 unless tool error" as the class {2, 3, 4}): a
  legacy audit over a shallow clone would emit false findings and corrupt the T10
  zero-false-failure evidence; precondition failure is an environment error, not a
  compliance finding.

After the D1 ruling (M1c) the losing strict profile is demoted into legacy and frozen;
the enum value remains valid (reports about old runs stay parseable).

### 4.3 Pre-D1 dual-profile mode

Until D1 is ruled, the default invocation (no `--profile`) runs **both** strict
profiles (validator plan §3.1.1 "emit two report sections"). Contract: the schema has
exactly one document shape — single-profile — and a dual run emits **two complete
documents**:

- `--report out.json` writes `out.strict-P.json` and `out.strict-G.json` (profile
  inserted before the final extension). `--report -` (stdout) is rejected in dual mode
  (exit 2).
- Codes 2/3/4 are run-global (preflight and the clone are shared). Otherwise each
  document's `summary.exit_code` is its own profile's rule-4–6 result, and the
  **process** exit code is the maximum of the two (i.e. 1 if either profile fails).

This keeps every long-lived consumer (M2 intake, M4 harness — all post-D1) on a
single flat shape; the dual mode is a temporary M1a–M1c affordance that disappears
with the D1 ruling.

### 4.4 Gate selection

`run.gate` ∈ `build | publish`. The only v1 check with gate-dependent behavior is
LG-1 (§3). The publish step hard-requires exit 0 at `--gate publish` before core's
`swhap publish` proceeds (core-pipeline §4.7).

---

## 5. Determinism & canonical serialization

Required of the producer so that (a) the M4 AI-on/off comparison is a plain byte
comparison of `--run-meta-stable` reports, and (b) gate evidence is diffable:

1. Serialization: UTF-8, `\n` line endings, exactly one trailing newline, 2-space
   indent, object keys sorted byte-wise ascending at every level
   (`json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)` + `"\n"`).
2. Ordering: `findings` sorted by `id` ascending (byte-wise UTF-8 — this groups by
   check family for free); `run.checks_run`, `run.refs_checked` sorted byte-wise;
   `run.checks_skipped` sorted by `id`.
3. No environment leakage: output independent of locale, TZ (`run.timestamp` is the
   only clock read, always UTC), hash randomization, filesystem iteration order, and
   CPU count.
4. Self-validation: `report.py` validates every emitted document against the schema
   before writing; failure is exit 3 (never an invalid report on disk).
5. Determinism statement: for a fixed tool build, fixed flags, and identical inputs,
   normal-mode reports differ at most in the run-variant field set (§1.2), and
   `--run-meta-stable` reports are byte-identical. The M4 non-interference proof
   (owned by pilots-validation, its T12) compares exactly these bytes; the proof
   compares reports from the **same tool build**, so schema evolution can never
   contaminate it (§6).

---

## 6. Schema versioning policy

### 6.1 The v1 line

- `schema_version` is the constant string `"1"` for every v1.x report. Minor
  (additive) evolution is tracked in the schema file's `$id`/changelog only —
  deliberately invisible to consumers, because consumers are tolerant readers (§6.2).
- The schema keeps the default open content model (`additionalProperties` not set to
  `false`) on the envelope, `run`, `summary`, and finding objects, **and** encodes the
  open points so that a vendored v1.0 schema copy still validates a v1.x report (this is
  a hard requirement of §6.2's "never reject because the copy is older", and because
  "the schema wins for shape" it MUST be enforced in the schema, not only in prose):
  - `required_approver_role` and `state` are `anyOf: [{enum: …}, {type: string}]` — the
    enum branch is an advisory annotation, any string validates (a v1.2
    `required_approver_role: "data-protection-officer"` passes a v1.0 copy).
  - `check_id` and the `id` family prefix validate against the relaxed
    `^[A-Z]{2,5}-…` pattern, not the closed family alternation — a new family `LM-1`
    introduced in M2 passes a v1.0 copy.
  Net: the producer's §5.4 self-validation against the updated schema and an M2
  consumer's validation against a vendored v1.0 copy now agree on the *same* report —
  closing the "same report, two verdicts, both per spec" split.

### 6.2 Minor (allowed within v1, no consumer action)

New **optional** fields anywhere; new check IDs / check families; new **non-subject**
`object` keys for a check (subject keys are frozen — adding one is MAJOR, §2.1/§6.3, so
finding ids never silently re-key); new values in the **open** enums
`required_approver_role` and `state` (and the `checks_skipped` reason vocabulary). All
of these validate against an older vendored v1.0 schema copy by construction (§6.1).
Consumer obligations, binding from M2 intake onward (this is what protects M2 intake
rendering from v1.x additions):

- **Tolerant reader**: ignore unknown fields and unknown check IDs (render them
  generically from severity + `message_plain`).
- Unknown `required_approver_role` ⇒ treat as the most restrictive known role
  (`legal-curator`). Unknown `state` ⇒ treat as `open`.
- Never reject a report solely because a vendored schema copy is older than the
  producer; routing decisions key on `schema_version` major only.

### 6.3 Major (requires `"2"` and a new schema file)

Renaming/removing any field or check ID; adding a required field; changing the
meaning of an existing field; any change to the `severity` enum or to the exit-code
mapping (§4); changing the finding-id algorithm, the **subject-key set of any check**
(§2.1), the byte-safe encoding or personal-email redaction scheme (§2.5a/§2.5b), or the
canonical serialization. Process:
new file `validator-report.v2.schema.json`; the producer MUST keep emitting v1 via
`--report-version 1` for at least one full milestone after v2 ships, so M2 intake and
archived gate evidence never break mid-milestone. The M4 byte-comparison is immune by
construction (same-build comparison, §5.5), but harness pins SHOULD record
`tool.version` + `schema_version` in the evidence pack.

### 6.4 Error reporting (`error` block)

On exit 3 the producer attempts a best-effort partial report containing
`error: { code: "internal", message, check_id? }` and `summary.exit_code: 3`; on exit
2 a report MAY be absent (argv may preclude knowing `--report`); if emitted it carries
`error.code: "usage"`. Consumers MUST treat any report whose `summary.exit_code` ∈
{2, 3, 4} as **non-certifying**: it proves the run happened, not that the workbench
passed or failed.

---

## 7. Conformance checklist (producer)

- [ ] Emitted report validates against `validator-report.schema.json` (T1 round-trip).
- [ ] `summary.exit_code` == process exit code; unit tests cover every rule of §4.1
      including mixes (FAIL+WARN, WARN-only ± `--strict-warn`, PC-FAIL + would-be
      TF-FAIL ⇒ 4, legacy with FAIL-classified findings ⇒ 0).
- [ ] Finding ids stable across two runs over identical inputs; collision ⇒ exit 3.
- [ ] `--run-meta-stable` double-run byte-identical (CI matrix: 2 runners — feeds D4
      evidence and the M4 harness).
- [ ] Run-variant data appears nowhere outside §1.2's field set (grep-style test over
      a fixture report: no absolute paths, no second timestamp).
- [ ] Legacy-profile run over a defective repo: findings present with true severities,
      all `enforced: false`, exit 0.
- [ ] Personal-address redaction tested on **every** check that can carry one, not only
      PI-1 (§2.5b): assert the literal address is absent from the whole report on PI-1,
      CSV-2, CSV-6, and BP-4 fixtures; assert `value_hmac12` is HMAC-keyed (changing
      `repo_pii_salt` changes the token) and that a `private`-class domain emits no
      literal `domain`.
- [ ] Non-UTF-8 subject fixture (§2.5a): a latin-1 filename
      (`b"Caf\xe9 mode d'emploi.txt"`) and a CSV field with an appended `\x01`/ANSI-OSC
      byte both produce a valid report (no `UnicodeEncodeError`, no exit 3), with the
      bytes rendered as `\xHH` text and identical across two machines; finding id stable
      across reruns.
- [ ] Finding id durable across a tool upgrade that adds an allowed **non-subject**
      `object` key (e.g. TF-2 `mode`): id unchanged for the same defect (§2.1).
- [ ] `state` derivation: a `finding:<id>`-namespaced `state-transition` ledger entry
      with `to: "acknowledged"` makes the matching finding's `state` become
      `acknowledged` on the next run, including a TF-2 finding with no `provenance`
      member (§2.8); absent such an entry, `state` is `open`.
- [ ] Vendored-v1.0-schema forward-compat: a synthetic report carrying a new check
      family (`LM-1`), a new `required_approver_role`, and a new `state` value validates
      against the frozen v1.0 schema copy (§6.1/§6.2).

## 8. Open points (could not be settled by the drafter alone)

1. Schema `$id` uses the placeholder URN `urn:swhap:schema:validation-report:v1`
   until the D6 hosting namespace (institutional org) is fixed; switch to an https
   `$id` then (minor event).
2. PI-1 default severity = WARN (Roberto's W1 ruling, 2026-06-05, overriding the
   drafter's proposed FAIL). A real personal email warns but does not block;
   a journaled curator-email opt-in clears it; redaction in the report is
   unconditional. RESOLVED — no longer an open point.
3. The "PC stays enforced in legacy" ruling (§4.2) interprets the profile matrix's
   "always 0 unless tool error"; confirm at the M1b co-signing.
4. `message_plain` language policy (English-only v1? French rendering for some
   institutions?) — affects intake rendering, not this schema; flag for M2 entry.
5. The BP-2 `additional_materials/` WARN is a placeholder pending the D1 ruling
   (validator plan risk 5) — severity flips to the ruling's outcome at M1c.
