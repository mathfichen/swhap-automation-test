# SWHAP journal ledger contract — `swhap-journal/1`

**Status: FROZEN (W1 sign-off 2026-06-05). Changes are versioned amendments.**

- Date: 2026-06-05
- Contract id: `journal-schema` (W1 freeze; core-pipeline plan §4.6, M1b artifact)
- Owner: swhap-core (envelope); payload owners: intake-curator (`provenance-transition`,
  `escalation`, `publish-event`, `review-session`, `state-transition`), ai-layer (`ai-consent`,
  `annotation`), swhap-core (all pipeline actions)
- Machine schema: [`specs/journal-entry.schema.json`](journal-entry.schema.json) (JSON Schema 2020-12)
- Binding inputs: `analysis/decisions.md` (D3 interim, D4, Q11 default), `analysis/impl/core-pipeline.md`
  §4.6/§4.7, `analysis/impl/intake-curator.md` §4.3/§4.4, `analysis/impl/ai-layer.md` §4,
  `analysis/implementation-plan.md` §3 (contracts 6 and the provenance-states row),
  `analysis/brief-critique.md` crit-M4/crit-M10/crit-M11
- Consumers: validator (JC-1a/JC-1/JC-2, LG-1, PI-1), intake ledger wiring (W7/W9),
  AI layer (read-only context; annotations; consent), pilots-validation (C5 metric extractor),
  `swhap publish` precondition chain

---

## 1. Scope and normative status (Q11)

The journal ledger is the **canonical provenance record** of a SWHAP workbench
(Q11 default, confirmed for this freeze): commit metadata, annotated tags,
`version_history.csv`, forge labels and `journal.md` prose are all *views*; when any
view disagrees with the ledger, the ledger wins.

Hard rules, restated from the plans and enforced by this contract:

- **Layer 1 authors; AI annotates, never authors.** Every entry is appended by
  deterministic Layer-1 code: either the pipeline's internal
  `swhap_core.journal.ledger` writer, or `swhap journal append --entry FILE` (the
  sole writer for curator/workflow entries). The AI layer never appends; its sole
  presence in the ledger is `actor.kind: ai` entries with `action: annotation`,
  relayed through Layer 1, carrying zero provenance transitions (schema-enforced).
- **One envelope** (M1b ruling, core-pipeline §3.3.5): every entry, whoever writes
  it, is an instance of the envelope in §3 — never a bare object. Workstream-specific
  data nests under `details`.
- **Coverage obligation** (crit-M4 fix): every commit and tag on candidate and
  published source refs has a covering entry, by hash (§5.4 step 6, §9).

## 2. Storage model

| Artifact | Path | Role |
|---|---|---|
| **Ledger (canonical)** | `metadata/journal.jsonl` | Append-only JSON Lines file; one canonically-serialized entry per line (§3.2). The only normative artifact. |
| Human view (derived) | `metadata/journal.md` | Generated deterministically from the ledger (§10). **Never hand-edited**; drift = `JL-RENDER` failure. |

Both files live in `metadata/` on the **workbench default branch**, under both D1
branch models (Model P: pure `main`; Model G: default branch with source — `metadata/`
exists in both; confirmed location is a D1-ruling check item, §13). The ledger never
appears on `SourceCode`, candidate or published source refs (branch purity), which is
what makes the self-reference rule of §9 closed.

Writers (exhaustive):

1. `swhap_core.journal.ledger` — internal appends from pipeline verbs
   (`ingest`/`extract`/`build`/`publish`/`apply-proposal`/…).
2. `swhap journal append --entry FILE` — the **sole** path for curator
   state-transition/escalation/review-session entries and workflow-emitted entries
   (intake-curator §2.5/§4.3); validates the entry against
   `journal-entry.schema.json` and this spec before appending; rejects
   `actor.kind: ai` payloads that are not `annotation`.

Nothing else writes the file. Hand edits are detectable: they break either canonical
form, the hash chain, or the published-prefix rule (§8).

## 3. Entry envelope

### 3.1 Fields

Frozen envelope (core-pipeline §4.6; field-level constraints in
`journal-entry.schema.json`, which is normative for shapes):

| Field | Req | Type / rule |
|---|---|---|
| `schema` | yes | const `"swhap-journal/1"` |
| `id` | yes | ULID (26-char Crockford). Unique in the ledger (FAIL otherwise). Monotonicity is WARN-only: **chain order is the authoritative order** (§5). |
| `ts` | yes | Wall-clock event time, UTC, RFC 3339 second precision, `Z` suffix (`2026-06-10T09:02:21Z`). Policy in §4. |
| `actor` | yes | `{kind: machine\|curator\|ai, name, tool, version}` + forge fields `{login, role, verified_via}` that are **curator-kind only** (intake-curator §4.3). The schema **rejects** any `machine`- or `ai`-kind actor carrying `login`/`role`/`verified_via` (anti-forgery: an AI actor cannot wear a curator's human identity — closes the "AI-annotation forgery of a human actor" threat). Mapping to the brief's triad: *pipeline* → `machine`, *human* → `curator`, *AI-annotation* → `ai`. |
| `action` | yes | One of the closed set in §6. |
| `inputs` | per action | `[{path \| url, sha256, size_bytes?}]` — every file/material the action consumed, **always with sha256** (crit-M4 "who/what/when/inputs/checksums"). |
| `outputs` | per action | Array of: file `{path, sha256, size_bytes?}` \| git object `{type: commit\|tag, git_object, ref?}` \| `{swhid}`. Git `ref` is held to a **positive allowlist** (`refs/heads/candidate/**`, `refs/tags/candidate/**`, final `refs/tags/<tag>`, `refs/heads/SourceCode`) — the default branch (`refs/heads/main`/`master`/any Model-G default head) and `refs/scratch/**` are structurally excluded (§9). The allowlist regex cannot see a `git_object` that *is* a default-branch commit under an otherwise-allowed `ref`; that residual case is caught by §5.4 step 9. |
| `provenance_transitions` | per action | `[{item, from, to}]`; `from: null` = initial state assignment. State machine in §7. |
| `prev_entry_sha256` | yes | Chain pointer (§5): sha256 hex of the previous entry's canonical line bytes; 64 zeros on genesis. |
| `details` | per action | Action-specific payload object (owners in header). Open for additive keys; required keys per action are schema-enforced. |

Top-level `additionalProperties: false`: the envelope itself is frozen; evolution
happens inside `details` or by a new `schema` version.

### 3.2 Canonical serialization and entry hash

- Canonical form of an entry = UTF-8 bytes of the JSON serialization with
  **lexicographically sorted keys, separators `","`/`":"` (no whitespace), and
  non-ASCII preserved** (Python: `json.dumps(e, sort_keys=True, separators=(",", ":"),
  ensure_ascii=False).encode("utf-8")`).
- Each `journal.jsonl` line MUST be exactly the canonical form, LF-terminated.
- **Entry hash := sha256 over the exact line bytes, newline excluded.** So
  verification needs no re-serialization logic beyond a canonical-form check, and any
  byte change to a published line is detectable.
- **No non-integer numbers, ever**: ledger entries MUST NOT contain JSON numbers that
  are not integers (floats/exponents forbidden; encode such values as strings). This
  makes the trivial sorted-compact serialization a true canonical form without
  RFC 8785 number rules — keeping the stdlib-only constraint (core-pipeline §2).
  Writer-enforced and checked at verify (`JL-SCHEMA`).
- **Well-formed Unicode only — no lone surrogates**: every string in an entry MUST be
  well-formed Unicode with no surrogate code points (`U+D800`–`U+DFFF`). The mandated
  `ensure_ascii=False ... .encode("utf-8")` is then **total**; without this rule the
  natural bytes→str decode of a non-UTF-8 archive member name (Python's
  `errors="surrogateescape"`, e.g. `b"caf\x80.c"` → `"caf\udc80.c"`) would carry a lone
  surrogate and make `.encode("utf-8")` raise `UnicodeEncodeError`, so the very
  `extract` entry that must record that name could not be written. Resolution: the
  *lossless* record of such a name is its **bytes (hex)**; any human-readable `decoded`
  rendering is produced with a **surrogate-free** error handler
  (`errors="replace"`, `U+FFFD`) — **never** `surrogateescape`. The raw bytes still
  reach the git tree unchanged via core §4.1.4's byte-oriented path; only the *journal
  string* is normalized. Writer-enforced; surrogate-bearing strings are a `JL-SCHEMA`
  failure at verify. (See §6 `extract` row and §11.3.)

## 4. Timestamp policy — coexistence with D4 bit-reproducibility

Two clocks exist; this contract keeps them strictly apart:

1. **The curation timestamp (deterministic).** The committer/tagger date for every
   commit/tag of the acquisition (D4). It is fixed **once**, recorded in a
   `curation-timestamp` entry — the **canonical store** of the D4 timestamp
   (core-pipeline §4.6; mirrored read-only into `plan.json`) — and reused unchanged
   by every rebuild. It is an *input* to git object construction.
2. **Journal `ts` (wall clock).** The real UTC time the event happened. It is a
   *witness*, never an input: `ts` flows into no git object on any source ref.

**Decision: journal timestamps are real wall-clock times; the ledger is deliberately
NOT bit-reproducible, and that does not conflict with D4.** Justification:

- D4 defines reproducible as *identical commit/tag object hashes across runs given
  identical inputs* (decisions.md). The ledger lives only on the default branch,
  outside every object the definition quantifies over; rebuild-compare (RB-1) hashes
  candidate/scratch objects, not `metadata/`.
- The ledger's job is the opposite of reproduction: it must *distinguish* runs. Two
  deterministic rebuilds append two `apply` entries with different `ts` and identical
  `outputs[].git_object` hashes — that pair of entries **is the recorded evidence of
  D4 reproducibility**, which a bit-identical journal could not express.
- Faking deterministic `ts` values would forge provenance (crit-M11 requires real
  approval timestamps) and add nothing: determinism of the artifact is carried
  entirely by the curation-timestamp entry.

Corollaries:

- `refs/scratch/**` rebuilds (the RB-1 compare primitive) are **not journaled** —
  they are ephemeral verification, produce no curated artifact, and would bloat the
  ledger; their evidence lives in the validator report. Only candidate- and
  published-ref writes are journal-covered (and only those are coverage-checked, §9).
- Granularity is one second; entries within the same second are ordered by the chain,
  not by `ts`.
- Clock skew across writers (CI runner vs curator laptop) makes `ts` regressions
  possible: non-decreasing `ts`/`id` is WARN, never FAIL (§5.4).

## 5. Hash chain

### 5.1 Genesis

The first line of every ledger is a `genesis` entry:
`prev_entry_sha256 = "0"×64`, `actor.kind = machine`, `details.workbench` naming the
workbench (plus tool/git versions). Exactly one genesis per ledger, only at line 1.
A ledger whose file is lost or corrupted is **not** re-grown in place: recovery =
preserve the damaged file as `raw_materials`-class forensic material and start a new
ledger whose genesis `details` records
`recovered_from: {path, sha256, superseded_tip_sha256}` — the break stays visible
forever. This starts a **new ledger lineage**: a recovery genesis is the only entry
that may legitimately *not* extend the previously-published ledger, so the append-only
prefix check (§5.4 step 5) is evaluated **per lineage** and grants a recorded,
verifiable exemption to a recovery genesis rather than failing forever (the blocker
this clause closes). `superseded_tip_sha256` is the entry-hash of the last published
entry of the damaged ledger (recoverable from the default branch's git history of
`metadata/journal.jsonl`); it makes the discontinuity provable, so the exemption is
auditable and cannot be used to silently fork an intact ledger.

### 5.2 Chain rule

For entry *n* (0-indexed):

```
prev_entry_sha256(0)  = "0" * 64
prev_entry_sha256(n)  = sha256( canonical line bytes of entry n−1, newline excluded )
```

The chain hash covers the **whole** previous entry (including its `prev_entry_sha256`),
so the tip hash commits to the entire history: tampering with any published line
invalidates every subsequent link.

### 5.3 Pre-publication linearization (re-chain rule)

The ledger travels in git; two clones may append concurrently, producing two entries
with the same `prev_entry_sha256` (a fork). Resolution: **append-only is defined
against the published state of the default branch** (the remote the workbench
designates). Entries not yet on the published default branch MAY be *re-chained*:
their `prev_entry_sha256` is recomputed to linearize them after the winning entry;
**all other fields, `id` and `ts` included, are unchanged**. Once a line is on the
published default branch it is immutable (`JL-APPEND-ONLY`). Merge tooling
(`swhap journal append` on a non-fast-forward state) performs re-chaining
mechanically; a hand-merged fork fails verification.

### 5.4 Verification procedure — `ledger.verify()` / `swhap journal verify`

Generator-side self-check (exit 15 on FAIL; error codes §12):

1. **Form**: file is UTF-8, LF line endings; every line parses as JSON and re-serializes
   byte-identically (canonical form, §3.2); integer-only numbers — else `JL-SCHEMA`.
2. **Schema**: every entry validates against `journal-entry.schema.json` (incl. the
   actor/action cross rules: ai⇒annotation-only, curator-approved⇒curator,
   per-action `details` requirements) — else `JL-SCHEMA`.
3. **Chain**: line 1 is the unique genesis with zero prev; for every n,
   `prev_entry_sha256(n)` equals the hash of line n−1; no duplicate `id` — else `JL-CHAIN`.
4. **Order (WARN)**: `id` and `ts` non-decreasing along the chain; violations are
   warnings (clock skew, §4) — chain order remains authoritative.
5. **Append-only (per lineage)**: within a ledger lineage, the ledger at the published
   default-branch state is a byte-prefix of the working ledger — else `JL-APPEND-ONLY`.
   **Recovery exemption (§5.1):** if the working ledger's genesis is a *recovery
   genesis* (`details.recovered_from` present), it begins a new lineage; the prefix rule
   does **not** bind it to the superseded ledger. Instead the discontinuity is verified
   — `recovered_from.superseded_tip_sha256` MUST equal the entry-hash of the last entry
   of the superseded ledger as last published on the default branch (read from git
   history of `metadata/journal.jsonl`) — and reported as a `JL-RECOVERED` **WARN**, not
   a FAIL. From the recovery genesis forward, append-only is enforced normally. Without
   this exemption the documented recovery would fail verification forever (the blocker);
   with it, an attempt to "recover" over an *intact* published ledger (no real
   discontinuity, or a mismatched `superseded_tip_sha256`) still FAILs `JL-APPEND-ONLY`.
6. **Coverage**: every commit and annotated tag reachable from
   `refs/heads/candidate/**`, `refs/tags/candidate/**` and the published source refs
   (`SourceCode`, final `refs/tags/<release-tag>`) appears as an `outputs[].git_object`
   of some entry — else `JL-COVERAGE`. Scratch refs exempt (§4).
7. **Render**: `journal.md` byte-equals a fresh render of the ledger (§10) — else `JL-RENDER`.
8. **Semantics** — else `JL-CHAIN` (semantic subclass):
   1. **Rewrite sign-off binding & single-use.** Every `rewrite-event`/`phase: executed`
      names a `sign_off_entry` that exists earlier in the chain with `phase: sign-off`,
      curator-kind actor, and a `target_refs` that is **set-equal** (exact set equality,
      neither subset nor superset) to the executed entry's `target_refs`. A `sign_off`
      entry is **single-use**: it is *consumed* by the first `executed` entry that cites
      it; any *second* `executed` entry citing the same `sign_off_entry` FAILs. One
      curator acknowledgement therefore authorizes **exactly one** rewrite of **exactly
      the signed ref set** — replay (a later force-push reusing the same sign-off) and
      scope drift are both rejected.
   2. **Curation-timestamp uniqueness, grouped by acquisition.** Group every
      `curation-timestamp` entry by its **acquisition key** := `details.acquisition` if
      present, else the reserved single-acquisition sentinel `"__default__"`. **At most
      one** `curation-timestamp` per key (a duplicate within one acquisition FAILs; a
      legitimate second acquisition — §13 — carries a distinct `details.acquisition` and
      so gets its own D4 timestamp without tripping this rule). Each entry's `epoch`/
      `offset` MUST equal the `plan.json` mirror for its acquisition.
9. **Output-ref namespace & self-reference (§9).** Beyond the schema's `ref` allowlist
   (which already excludes the default branch and `refs/scratch/**`), no
   `outputs[].git_object` may be a commit reachable on the **workbench default branch**
   (resolved from git at verify time): a default-branch commit object journaled in
   `outputs` — even under an allowed `ref` — reintroduces the §9 infinite-regress and
   FAILs `JL-COVERAGE` (self-reference subclass). Default-branch effects are recorded as
   **file outputs** `{path, sha256}` only (§9.1).

### 5.5 What the validator checks (independent implementation)

Schema shared, code not (core-pipeline §4.6):

- **JC-1a** (M1a, schema-independent): every commit/tag hash on curated refs is
  textually referenced in the journal — catches the published exemplar's boilerplate
  journal (`RED-journal-coverage`) before this schema freezes.
- **JC-1** (M1c, full form): steps 1–3 + 6 + 9 of §5.4 re-implemented against this spec
  (chain integrity from genesis to tip; coverage by hash on curated refs; the §9
  self-reference / output-ref-namespace check).
- **JC-2**: every provenance-state transition has a ledger entry carrying approver
  (`actor` + forge fields), item, prior and new state, timestamp — parsed as
  envelopes, never bare objects; same rule for **LG-1**'s reads (legal gate, §7.5)
  and **PI-1**. PI-1's curator-email opt-in is carried by **exactly one action**:
  a `provenance-transition` entry on the stable item id `pii.curator_email`
  reaching state `curator-approved` by a curator-kind actor (§6, §7.2;
  csv-contract §5.2). PI-1 reads exactly this transition and JC-2 verifies it;
  it is **not** an `ai-consent` entry (that action records AI-provider consent
  only — `details {provider, endpoint, data_classes, retention_ref}`, §6, and
  carries no provenance transition). A validator builder MUST NOT key PI-1 on
  `ai-consent`.

## 6. Action taxonomy

Closed set, **22 values**. Every "Required payload" cell below is **schema-enforced**
by `journal-entry.schema.json` (an `allOf` clause per action) — there is no
schema/prose gap, so two implementers cannot diverge on whether an entry is well-formed.
Adding a value past this freeze = a version-bump of this spec (additive, consumers
tolerate unknown values by failing the entry, not the ledger).

| `action` | Actor kinds | Emitted by | Required payload (beyond envelope) — schema-enforced |
|---|---|---|---|
| `genesis` | machine | ledger init | `details.workbench`; zero prev (§5.1) |
| `acquire` | machine | `swhap ingest` | **required** `inputs` (≥1, url/path+sha256) + `outputs` (≥1, staged `raw_materials/` files); intake context + optional `details.acquisition` (§13 discriminator) in `details` |
| `inspect` | machine | `swhap inspect` | **required** `inputs` (≥1); verdict/budget numbers in `details` |
| `extract` | machine | `swhap extract` | **required** `inputs` (≥1) + `details` (object); when present each `details.non_utf8_names[]` MUST be `{bytes_hex` (lossless authority)`, declared_encoding, decoded` (surrogate-free `errors='replace'` display, §3.2)`}` (core §4.1.4); other keys: member/rejection counts, symlink inventory, case-collision verdicts, hardlink materializations |
| `strip-wrapper` | machine | extractor | **required** `details {wrapper, rule, evidence}` |
| `emptydir` | machine | tree stage | **required** `details {paths}` (the `.emptydir` paths added) |
| `digest` | machine | `swhap digest` | **required** `outputs` (≥1): `checksums.sha256`, `filesizes.csv` with their hashes |
| `csv-validate` | machine | `swhap csv validate` | **required** `inputs` (≥1, the CSV); profile + findings in `details` |
| `csv-convert` | machine | `swhap csv convert` | **required** `inputs` (≥1, legacy CSV) + `outputs` (≥1, canonical CSV file record); converted fields are provenance-tagged `computed` (D2) |
| `curation-timestamp` | machine | plan stage | **required** `details.epoch` (int) + `details.offset`; optional `details.acquisition` (§13 grouping key, §5.4 step 8) — **canonical D4 store** (§4) |
| `plan` | machine | `swhap plan` | **required** `outputs` (≥1): `plan.json` + sha256 |
| `apply` | machine | `swhap apply`/`build` | **required** `outputs` (≥1): **all commit and annotated-tag objects created**, with candidate refs; `inputs`: plan + sha256 |
| `apply-proposal` | machine | `swhap apply-proposal` (T15, §4.8 / resolution 11) | **required** `outputs` (≥1, **file records only** `{path, sha256}` — default-branch metadata writes, §9.1) + `provenance_transitions` (≥1, seeds `inferred`, §7.1) + `details {proposal_ref, approval_entry}` (the gating curator approval; `AP-NO-APPROVAL` otherwise) |
| `validate` | machine | `check_swhap` wrapper | **required** `inputs` (≥1, report artifact + sha256); gate + exit code in `details` |
| `state-transition` | machine, curator | intake workflow | `details {machine, from, to, ref}` — workflow/label state machines (intake §4.4: labels are a view, this entry is canonical) |
| `provenance-transition` | machine, curator | `swhap journal append`; pipeline initial assignments | `provenance_transitions` ≥1; §7 rules (to `curator-approved`: curator only). **Note (PI-1 carrier):** the curator-email publication opt-in is one such entry — item `pii.curator_email`, `to: curator-approved`, curator-kind actor; this is what makes validator PI-1 *pass* (csv-contract §5.2, validator-report §2.5b). It is **not** an `ai-consent` entry. |
| `escalation` | machine, curator | intake (idk/judgment/warning) | `details {item, reason, source_question?, contact?, task_url?}` |
| `review-session` | curator, machine | label transitions + `/swhap review start\|done` | `details {phase: start\|end, ref}` — C5 active-time source |
| `ai-consent` | curator | Layer 1 on explicit consent | `details {provider, endpoint, data_classes, retention_ref}` (ai-layer §4) |
| `annotation` | **ai only** | `swhap journal append` relay of `journal_annotate` task | `details {note, target_entry? \| target_item?}`; **zero provenance transitions** (schema-enforced) — the entire Q11 AI surface |
| `publish-event` | machine | `swhap publish` | `details {candidate_ref, final_repo, swhids?, save_code_now?}` (intake §4.3); `outputs`: final tags + SWHIDs. Re-runnable on partial failure: no recorded SWHID ⇒ no `archived` state |
| `rewrite-event` | curator (sign-off), machine (executed) | §8.2 | two-phase payload, §8.2 |

Mapping to the task-brief verbs: *extract* → `extract` (+`strip-wrapper`/`emptydir`);
*build* and *tag* → `apply` (one entry per run lists **both** the commits and the
annotated tags it created — tags are not a separate entry); *validate* → `validate`;
*approve* → `provenance-transition` with `to: curator-approved`; *state-transition* →
`state-transition` (workflow states) and `provenance-transition` (item states);
*publish* → `publish-event`; *rewrite-event* → `rewrite-event`; *acquire* → `acquire`
(the `swhap ingest` verb); *apply-proposal* (the Layer-1 render of an approved AI
proposal into default-branch metadata, core §4.8 / resolution 11) → `apply-proposal`
(machine actor; file outputs + a seeded `inferred` transition + the gating approval
reference). The cross-workstream conformance fixture (one valid entry per action value)
carries one of each of the 22, this binding M4 flow included.

## 7. Provenance state machine

States (implementation-plan §3, frozen here):
`observed | computed | inferred | user-provided | curator-approved`.

### 7.1 Initial assignment

Items enter the ledger via a `provenance_transitions` element with `from: null`,
inside the entry that creates them:

| Initial state | Assigned by | Typical source |
|---|---|---|
| `observed` | machine | direct measurement: checksums, member lists, file contents (e.g. a LICENSE file's existence) |
| `computed` | machine | deterministic derivation: digests, legacy-CSV conversions (D2), wrapper verdicts |
| `inferred` | machine | heuristics, or AI drafts landing through the curator-gated `apply-proposal` path (the `*.prov.json` sidecar seeds the state; the *entry* is appended by Layer 1) |
| `user-provided` | machine | intake-record answers relayed verbatim (intake §4.2) |
| `curator-approved` | — | **never an initial state** |

### 7.2 Transition matrix (who may trigger what)

| from → to | `observed` | `computed` | `inferred` | `user-provided` | `curator-approved` |
|---|---|---|---|---|---|
| *(null — creation)* | machine | machine | machine | machine | **forbidden** |
| `observed` | — | curator | curator | curator | **curator only** |
| `computed` | curator | — | curator | curator | **curator only** |
| `inferred` | curator | curator | — | machine¹ / curator | **curator only** |
| `user-provided` | curator | curator | curator | — | **curator only** |
| `curator-approved` | curator² | curator² | curator² | curator² | — |

¹ machine may upgrade `inferred → user-provided` only when relaying a new signed
intake answer for the same item.
² revocation/correction: curator only, `details.reason` required.

Hard rules (schema- and writer-enforced):

- **AI triggers nothing.** `actor.kind: ai` entries carry zero transitions; AI output
  proposes states only inside proposal bundles, which become ledger transitions only
  through the curator-approval-gated `apply-proposal` verb (machine actor, approval
  entry referenced).
- **Only curators reach `curator-approved`** (crit-M10/M11; the schema rejects any
  entry transitioning to `curator-approved` whose actor is not curator-kind).
- **Machine never transitions FROM `curator-approved`.** If a rebuild or recompute
  changes the basis of an approved item (e.g. an observed value shifts), the machine
  appends an `escalation` entry flagging the item stale — the approval stands in the
  record until a curator acts. No silent un-approval.
- Re-assertion of the same state on recompute (e.g. `observed` re-measured equal) is
  **not** a transition and appends nothing to `provenance_transitions`.

### 7.3 Approval entry requirements (crit-M11)

Every approval — and every transition — records in one envelope: **approver**
(`actor` with forge fields `login`/`role`/`verified_via` for curator-kind),
**item** (`provenance_transitions[].item`, stable id, e.g. `legal.license`),
**prior state** (`from`), **new state** (`to`), **timestamp** (`ts`), plus optional
`details.evidence` (e.g. the forge comment URL the `/swhap approve` command came
from) and `details.note`. The worked example in §11 (entry 7) is the normative shape.
JC-2 verifies exactly this tuple.

### 7.4 Legal gate interaction (LG-1)

At `--gate publish`: every ledger item of class legal/redistribution must be
`curator-approved`; `user-provided` **never** suffices (implementation-plan §3).
LG-1 reads these states exclusively from ledger envelopes — so an item with no
creation entry simply does not exist for the gate, and publish is structurally
blocked (`swhap publish` precondition, exit 16).

## 8. Append-only semantics and the rewrite escape hatch

### 8.1 Ledger append-only

Published ledger lines are immutable (§5.3). Mistaken entries are corrected by
**appending**, never editing: a correcting entry of the same action carries
`details.supersedes: <entry id>`; consumers treat the latest non-superseded entry as
current; the error remains visible in the record. The ledger itself is **never**
subject to `rewrite-event` — that action governs git refs only.

> **AMENDMENT 2026-06-06 — D3 revised to rebuild-and-replace (see
> `analysis/decisions.md` D3-RESOLVED).** Roberto ruled that rebuild-and-replace
> is a **first-class, expected** operation, not a destructive exception: SWHIDs
> are permanent once archived in Software Heritage, so replacing the SourceCode
> branch with a freshly-rebuilt history **supersedes** the prior snapshot rather
> than "invalidating" it. The decisive case is **chronological insertion** (a
> release surfacing later that belongs *between* existing ones), which strict
> append-only cannot represent correctly.
>
> **IMPLEMENTED 2026-06-07 (M2 publish step — `swhap_core.publish`,
> `swhap publish --supersede`).** The items below are now schema-enforced
> (`journal-entry.schema.json`, additive amendment 2026-06-07; `schema` stays
> `swhap-journal/1`) and exercised by the chronological-insertion end-to-end test:
> 1. The two-phase protocol (§8.2) is **kept as the ceremony** for replacing a
>    published source ref, reframed: the curator acknowledges a *supersession*,
>    not an *invalidation*.
> 2. `details` of the sign-off carries `supersedes_snapshot_swhid` — the **SWH
>    snapshot SWHID** of the archived prior history (the durable lineage pointer),
>    computed **intrinsically/offline** from the prior published refs
>    (`swhap_core.swhid.snapshot_swhid`, equal to `swh identify --type snapshot`).
>    The prior history MUST be archived in SWH **before** replacement (the
>    `swhap publish` Save-Code-Now adapter). `acknowledgement` is
>    `"prior-snapshot-archived-in-swh"`; `invalidated_swhids` is **retired** in
>    favour of this pointer (the prior SWHIDs are *preserved*, not invalidated).
>    Legacy `"swhid-invalidation-acknowledged"` sign-offs remain schema-valid.
> 3. `DV-1` retargets from "refuse any divergence" to "refuse *un-journaled,
>    un-archived* divergence" — it blocks an accidental clobber, never a recorded
>    SWH-backed supersession. (Consumed by the validator workstream; the journaled
>    record it reads is specified in §8.2.)
> The interim wording below is retained for the legacy invalidation path, which
> the schema still accepts.

### 8.2 `rewrite-event` — D3 interim escape hatch for published refs

D3 interim default: published refs are append-only; `swhap publish` promotes
fast-forward-only and the validator's DV-1 detects divergence. The **only** sanctioned
path to rewriting a published source ref (crit-M4's "explicit journaled curator
sign-off with an SWHID-invalidation warning") is a two-phase ledger protocol:

1. **`rewrite-event` / `phase: sign-off`** — curator-kind actor; `details` MUST carry
   `target_refs`, `reason`, the full list of `invalidated_swhids`, and the literal
   `acknowledgement: "swhid-invalidation-acknowledged"` (the warning is acknowledged
   *in* the record, not alongside it). Without this entry, Layer 1 refuses any
   non-fast-forward push to a published ref (no capability is constructible).
2. **`rewrite-event` / `phase: executed`** — machine actor; references
   `sign_off_entry` and records `old_hashes` / `new_hashes`. §5.4 step 8.1 binds it:
   the cited sign-off must exist earlier in the chain (curator-kind) with a
   `target_refs` **set-equal** to this entry's `target_refs`, and it must not already
   have been consumed by an earlier `executed` entry. A sign-off is therefore
   **single-use and scope-exact**: one curator acknowledgement authorizes exactly one
   non-fast-forward rewrite of exactly the signed ref set — a months-later replay
   reusing the same sign-off, or an executed entry touching a sub/superset of the signed
   refs, both FAIL. Follow-up `publish-event` entries record the replacement SWHIDs.

**Revised-D3 supersession record (the shape DV-1 consumes) — IMPLEMENTED
2026-06-07.** For a rebuild-and-replace, the two `rewrite-event` entries are:

1. **`phase: sign-off`** — `actor.kind: curator`; `details` carries:
   - `phase: "sign-off"`
   - `target_refs`: the published refs the rewrite touches (set-equal to the
     executed entry's, §5.4 step 8.1)
   - `reason`: free text
   - `supersedes_snapshot_swhid`: the `swh:1:snp:…` of the **prior** published
     history, archived in SWH **before** replacement (the durable lineage pointer)
   - `acknowledgement: "prior-snapshot-archived-in-swh"`
2. **`phase: executed`** — `actor.kind: machine`; `details` carries
   `phase: "executed"`, the same `target_refs`, `sign_off_entry` (the sign-off's
   ULID), `old_hashes` and `new_hashes`.

DV-1 keys off the sign-off's `supersedes_snapshot_swhid` + `acknowledgement`
pair: a divergent published ref backed by such a sign-off (whose
`supersedes_snapshot_swhid` matches the snapshot SWHID of the *previously*
published refs) and a matching executed entry is an **allowed**, recorded
supersession; an un-journaled / un-archived divergence remains FAIL.

DV-1 treats a divergent published ref **without** a matching executed `rewrite-event`
as FAIL; with one, it downgrades to a flagged, explained WARN. If the D3 final ruling
(M1c) chooses strict append-only-once-archived, `rewrite-event` remains in the schema
but Layer 1 stops constructing the capability after `archived` — a config change, not
a schema change.

## 9. Self-reference rule (the ledger and the branch that carries it)

The ledger lives on the default branch; a default-branch commit therefore *contains*
the journal. Journaling that commit's hash inside itself is impossible (the hash
depends on the entry), and journaling it in the *next* entry would regress forever.
Chosen rule, in full:

1. **No-self-hash (the file-output rule, §9.1).** An entry MUST NOT contain the git
   object id of any commit on the workbench default branch. Default-branch effects
   (metadata writes, ledger appends, and the `apply-proposal` action's renders of an
   approved AI proposal into `metadata/`, §6) are recorded as **file outputs**
   `{path, sha256}` — the content is witnessed; the carrying commit is not. This is
   enforced at two layers: the schema's `ref` allowlist rejects default-branch and
   `refs/scratch/**` refs in `outputs`, and §5.4 step 9 rejects any `outputs[].git_object`
   that resolves to a default-branch commit even under an otherwise-allowed `ref` —
   closing the residual path by which the §9 infinite-regress could be reintroduced.
2. **Carrier resolution is derivation, not storage.** The *carrier commit* of entry
   N is defined as the earliest default-branch commit in which
   `metadata/journal.jsonl` ends with entry N. It is mechanically resolvable from git
   history whenever needed (audit tooling does so on demand) and therefore never
   recorded. Recommended discipline: a metadata write and its ledger entry land in
   the same commit, making the carrier the action's own commit.
3. **Coverage is scoped to source-bearing refs.** The JL-COVERAGE / JC-1 obligation
   binds exactly the refs that can never contain the ledger — candidate branches and
   tags, published `SourceCode` and final release tags (branch purity guarantees the
   disjointness). Default-branch commits carry no coverage obligation: their audit
   trail is the ledger itself plus git's own history of `journal.jsonl`, hash-chained
   independently of git.
4. **Post-hoc witnesses are post-hoc.** A snapshot SWHID minted by Save Code Now
   covers the pushed state of the default branch, including the ledger as of the
   push; the `publish-event` entry recording that SWHID necessarily lands *after* it.
   No obligation requires a snapshot to contain the entry that records it.

This closes the regress: hashes flow ledger→git only for source refs (which hold no
ledger), and git→ledger only as recorded outputs of past actions.

## 10. `journal.md` rendering rule

`metadata/journal.md` is a **generated view** (header line: `<!-- GENERATED from
journal.jsonl by swhap journal render — DO NOT EDIT -->`). Renderer (in
`swhap_core.journal`) is a pure function of the ledger bytes:

- One section per entry, in chain order: a single English sentence rendered from a
  fixed per-action template table (stable template ids, versioned with this spec;
  no locale, no render-time timestamps, no environment data), followed by a fenced
  ` ```json swhap-journal ` block containing the entry pretty-printed with sorted
  keys, two-space indent (the format core-pipeline §4.6 describes — satisfied here as
  a rendering of the canonical JSONL line, not as the storage itself).
- Determinism: identical ledger bytes ⇒ identical `journal.md` bytes. Verified by
  §5.4 step 7 (`JL-RENDER`); hand edits to `journal.md` are thereby build failures,
  not data loss — regenerate to fix.
- Persona note: `journal.md` is the Profile-B/C/D-facing view; Profile A sees
  per-persona renderings of the same ledger data in the intake issue (intake §2.4) —
  approval is only ever *recorded* in the ledger.

## 11. Worked examples

A miniature but **chain-valid** ledger for a single-release acquisition
(`Life1.02Ultrix.tar`, the PR #1 author-supplied tarball; its sha256 below is the
real pinned fixture checksum from `fixtures/wildlife/tarballs.sha256`). A production
ledger interleaves more entries (`inspect`, `emptydir`, `digest`, `csv-validate`,
`plan`, `validate`, `state-transition`, `review-session`…) — chain validity is
unaffected; coverage binds only git objects, all of which appear in `apply` /
`publish-event` entries. Entries are shown pretty-printed for readability; **the
ledger line is the canonical serialization (§3.2)**, and every `ENTRY_HASH` /
`prev_entry_sha256` below was computed over those canonical bytes — the chain is
real and re-verifiable:

```python
# reference verifier (stdlib only)
import json, hashlib
prev = "0" * 64
for line in open("metadata/journal.jsonl", "rb").read().splitlines():
    e = json.loads(line)
    assert json.dumps(e, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode() == line   # canonical form
    assert e["prev_entry_sha256"] == prev                    # chain
    prev = hashlib.sha256(line).hexdigest()
```

### 11.1 `genesis`

```json swhap-journal
{
  "action": "genesis",
  "actor": {"kind": "machine", "name": "swhap", "tool": "swhap-core", "version": "0.1.0"},
  "details": {
    "git_version": "2.49.0",
    "workbench": "wildlife-swhap",
    "workbench_url": "https://github.com/example-institution/wildlife-swhap"
  },
  "id": "01KTRC52M0HX9BEAKD0F8765GR",
  "prev_entry_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "schema": "swhap-journal/1",
  "ts": "2026-06-10T09:00:00Z"
}
```
`ENTRY_HASH: 19f114060ebd734f9e4629468dcdac5ce4deecf793ffc5e4e546117720ace6c4`

### 11.2 `acquire` (the `swhap ingest` verb; initial `observed` assignment)

```json swhap-journal
{
  "action": "acquire",
  "actor": {"kind": "machine", "name": "swhap", "tool": "swhap-core", "version": "0.1.0"},
  "details": {
    "intake": {"issue": 17, "platform": "github",
               "repo": "example-institution/swhap-intake", "submitter": "pvanroy"},
    "verb": "swhap ingest"
  },
  "id": "01KTRC92HR4CKDS7G9ZKBYJ2K8",
  "inputs": [
    {"sha256": "0e43f8296db6ba490d551d8ae4fc56eb684231b0a143e26c705076f21f543763",
     "size_bytes": 9095168,
     "url": "https://github.com/example-institution/swhap-intake/files/14/Life1.02Ultrix.tar"}
  ],
  "outputs": [
    {"path": "raw_materials/Life1.02Ultrix.tar",
     "sha256": "0e43f8296db6ba490d551d8ae4fc56eb684231b0a143e26c705076f21f543763",
     "size_bytes": 9095168}
  ],
  "prev_entry_sha256": "19f114060ebd734f9e4629468dcdac5ce4deecf793ffc5e4e546117720ace6c4",
  "provenance_transitions": [
    {"from": null, "item": "raw_materials.Life1.02Ultrix.tar", "to": "observed"}
  ],
  "schema": "swhap-journal/1",
  "ts": "2026-06-10T09:02:11Z"
}
```
`ENTRY_HASH: b2c9c1bdbd66fbebed312268c6e6d98736f2424561fde327d7dae0bf8c8fa3e3`

### 11.3 `extract`

```json swhap-journal
{
  "action": "extract",
  "actor": {"kind": "machine", "name": "swhap", "tool": "swhap-core", "version": "0.1.0"},
  "details": {
    "case_collisions": 0,
    "dest": "work/extract/Life1.02Ultrix",
    "filename_encoding_declared": "latin-1",
    "hardlinks_materialized": 0,
    "members": 213,
    "non_utf8_names": [],
    "policy_sha256": "614aa33ce14851d6a8e2c4cf548a35e738704313b0d3f4423eab5718694c87bc",
    "rejected": 0,
    "symlinks": 0,
    "verb": "swhap extract"
  },
  "id": "01KTRC95FGYH5HQBHDPN33DAR9",
  "inputs": [
    {"path": "raw_materials/Life1.02Ultrix.tar",
     "sha256": "0e43f8296db6ba490d551d8ae4fc56eb684231b0a143e26c705076f21f543763"}
  ],
  "prev_entry_sha256": "b2c9c1bdbd66fbebed312268c6e6d98736f2424561fde327d7dae0bf8c8fa3e3",
  "schema": "swhap-journal/1",
  "ts": "2026-06-10T09:02:14Z"
}
```
`ENTRY_HASH: dec78d0b48ad8bee9f32b0e56b8ec77b4464cc2bec0c755048bd564dfa7974b9`

(Were any member name non-UTF-8, `details.non_utf8_names` would carry
`{"bytes_hex": …, "declared_encoding": "latin-1", "decoded": …}` per core §4.1.4.
Concretely, a member `b"caf\x80.c"` records
`{"bytes_hex": "636166802e63", "declared_encoding": "latin-1", "decoded": "caf�.c"}`
— `decoded` is built with `errors="replace"` (U+FFFD), **never** `surrogateescape`, so
the canonical `ensure_ascii=False` serialization cannot raise `UnicodeEncodeError`
(§3.2); `bytes_hex` is the lossless authority, and the original bytes still reach the
git tree unchanged via core §4.1.4.)

### 11.4 `strip-wrapper`

```json swhap-journal
{
  "action": "strip-wrapper",
  "actor": {"kind": "machine", "name": "swhap", "tool": "swhap-core", "version": "0.1.0"},
  "details": {
    "evidence": "single top-level directory containing all 213 members",
    "rule": "auto",
    "wrapper": "Life1.02Ultrix/"
  },
  "id": "01KTRC96ER1Z5SJ23T63KH6SGD",
  "prev_entry_sha256": "dec78d0b48ad8bee9f32b0e56b8ec77b4464cc2bec0c755048bd564dfa7974b9",
  "schema": "swhap-journal/1",
  "ts": "2026-06-10T09:02:15Z"
}
```
`ENTRY_HASH: 54d595f69e18b5ae84c22f36bba7156261bb77a11209a4f12e43946b317119ce`

### 11.5 `curation-timestamp` (canonical D4 store)

```json swhap-journal
{
  "action": "curation-timestamp",
  "actor": {"kind": "machine", "name": "swhap", "tool": "swhap-core", "version": "0.1.0"},
  "details": {
    "epoch": 1781082136,
    "note": "D4 fixed curation timestamp; committer/tagger date for every rebuild of this acquisition",
    "offset": "+0000"
  },
  "id": "01KTRC97E0HPQTRJBYY6RJBAX0",
  "prev_entry_sha256": "54d595f69e18b5ae84c22f36bba7156261bb77a11209a4f12e43946b317119ce",
  "schema": "swhap-journal/1",
  "ts": "2026-06-10T09:02:16Z"
}
```
`ENTRY_HASH: d55000f67a518dbdbc88b0e2446010d194609553f2fed37e263d217edf762192`

### 11.6 `apply` (build: commits **and** annotated tags, one entry)

```json swhap-journal
{
  "action": "apply",
  "actor": {"kind": "machine", "name": "swhap", "tool": "swhap-core", "version": "0.1.0"},
  "details": {
    "curation_ts_entry": "01KTRC97E0HPQTRJBYY6RJBAX0",
    "model": "P",
    "releases": [
      {"commit": "43b4f102a4790c78c5c4442f6c75a0c3ff518fe4",
       "dirname": "Life1.02", "release_tag": "v1.02"}
    ],
    "run_id": "01KTRC9BB0CRC82R3Y8QZHA93X",
    "verb": "swhap apply"
  },
  "id": "01KTRC9CA8B95MPMVDMAFPGFWB",
  "inputs": [
    {"path": "plan.json",
     "sha256": "5ecece6cbf3500ba13cae5edc7d353d3f3321dffaf5f60e7f4af4c26c4b6e610"}
  ],
  "outputs": [
    {"git_object": "43b4f102a4790c78c5c4442f6c75a0c3ff518fe4",
     "ref": "refs/heads/candidate/P/01KTRC9BB0CRC82R3Y8QZHA93X", "type": "commit"},
    {"git_object": "1c135342171e9e93a809997a32ba6d86e494c4c0",
     "ref": "refs/tags/candidate/P/01KTRC9BB0CRC82R3Y8QZHA93X/v1.02", "type": "tag"}
  ],
  "prev_entry_sha256": "d55000f67a518dbdbc88b0e2446010d194609553f2fed37e263d217edf762192",
  "schema": "swhap-journal/1",
  "ts": "2026-06-10T09:02:21Z"
}
```
`ENTRY_HASH: c6e15d895413299bc390dad1915bf584b573aea2d798ca344a2776241b7120a5`

(Git object ids in `outputs`/`details` are illustrative; the tarball sha256 values
are real. A deterministic rebuild appends a second `apply` entry with different
`id`/`ts` and **identical** `git_object` values — the recorded D4 evidence, §4.)

### 11.7 `provenance-transition` — curator approval (crit-M11 normative shape)

```json swhap-journal
{
  "action": "provenance-transition",
  "actor": {
    "kind": "curator", "login": "ccurator", "name": "Carla Curator",
    "role": "curator", "tool": "swhap-intake", "verified_via": "team-membership",
    "version": "0.1.0"
  },
  "details": {
    "evidence": {"comment_url": "https://github.com/example-institution/swhap-intake/issues/17#issuecomment-31"},
    "note": "License statement in doc/LICENSE matches submitter answer; approved for redistribution."
  },
  "id": "01KTVHE6E8HMWZ7Y62BSYQ9F5A",
  "prev_entry_sha256": "c6e15d895413299bc390dad1915bf584b573aea2d798ca344a2776241b7120a5",
  "provenance_transitions": [
    {"from": "user-provided", "item": "legal.license", "to": "curator-approved"}
  ],
  "schema": "swhap-journal/1",
  "ts": "2026-06-11T14:30:05Z"
}
```
`ENTRY_HASH: 9423e30b031a4b54f4266c6c04ee4aba0bf575d5ce1952121fc9eaa4ff455cd1`

Approver (actor + forge fields), item, prior state, new state, timestamp — the JC-2
tuple — all in one envelope. This entry is what unblocks LG-1 at `--gate publish`.

### 11.8 `publish-event`

```json swhap-journal
{
  "action": "publish-event",
  "actor": {"kind": "machine", "name": "swhap", "tool": "swhap-core", "version": "0.1.0"},
  "details": {
    "candidate_ref": "refs/heads/candidate/P/01KTRC9BB0CRC82R3Y8QZHA93X",
    "final_repo": "https://github.com/example-institution/wildlife",
    "save_code_now": {
      "request_url": "https://archive.softwareheritage.org/api/1/origin/save/git/url/...",
      "visit_status": "full"
    },
    "swhids": {
      "dir": ["swh:1:dir:e00ecc923f521763a90a5ae768c7b9aad32439de"],
      "rel": ["swh:1:rel:2a192a7b4180c1cccb97967bba71504be58e1f2f"],
      "snp": "swh:1:snp:4d8da9fdd052b86d294c4e967465895880faf1b9"
    },
    "verb": "swhap publish"
  },
  "id": "01KTXDGXS8R5MQTARJNAFGT8DT",
  "outputs": [
    {"git_object": "3bf39a6ee1289018dcc5df871b39458912158a14",
     "ref": "refs/tags/v1.02", "type": "tag"},
    {"swhid": "swh:1:snp:4d8da9fdd052b86d294c4e967465895880faf1b9"},
    {"swhid": "swh:1:rel:2a192a7b4180c1cccb97967bba71504be58e1f2f"}
  ],
  "prev_entry_sha256": "9423e30b031a4b54f4266c6c04ee4aba0bf575d5ce1952121fc9eaa4ff455cd1",
  "schema": "swhap-journal/1",
  "ts": "2026-06-12T08:00:09Z"
}
```
`ENTRY_HASH: 12f06561419577db96c5debc6a23a42b39df93148f5553c94623246c2c63a7f5`

### 11.9 `rewrite-event` (sign-off phase; D3 interim escape hatch)

```json swhap-journal
{
  "action": "rewrite-event",
  "actor": {
    "kind": "curator", "login": "ccurator", "name": "Carla Curator",
    "role": "curator", "tool": "swhap-intake", "verified_via": "team-membership",
    "version": "0.1.0"
  },
  "details": {
    "acknowledgement": "swhid-invalidation-acknowledged",
    "invalidated_swhids": [
      "swh:1:snp:4d8da9fdd052b86d294c4e967465895880faf1b9",
      "swh:1:rel:2a192a7b4180c1cccb97967bba71504be58e1f2f"
    ],
    "note": "Published refs are otherwise append-only (D3 interim). New SWHIDs will be recorded by the follow-up rewrite-event/executed and publish-event entries.",
    "phase": "sign-off",
    "reason": "Author-reported defect: reconstructed v1.02 tree omitted dotfiles present in the original tarball (crit-M3 class); corrected rebuild required.",
    "target_refs": ["refs/tags/v1.02", "refs/heads/SourceCode"]
  },
  "id": "01M1GSTS50DTDKGT1A1M93JKNF",
  "prev_entry_sha256": "12f06561419577db96c5debc6a23a42b39df93148f5553c94623246c2c63a7f5",
  "schema": "swhap-journal/1",
  "ts": "2026-09-02T10:15:00Z"
}
```
`ENTRY_HASH: 896a49ac6415c5721dd2b988a4339eadb601a55e1d74dfbddd2496b622cb7430`

The matching `phase: executed` entry (machine actor, `sign_off_entry:
"01M1GSTS50DTDKGT1A1M93JKNF"`, `old_hashes`/`new_hashes`) follows the rebuild;
without this sign-off entry, no non-fast-forward push capability exists (§8.2).

## 12. Error codes and exit mapping

`JournalError` codes (core-pipeline §5, plus two **proposed additions** to
`specs/error-codes.md` — flagged for the error-taxonomy owner's co-sign):

| Code | Meaning | Status |
|---|---|---|
| `JL-APPEND-ONLY` | a line present in the published ledger state changed or vanished (within a lineage; a verified recovery genesis is exempt, §5.4 step 5) | frozen (core §5) |
| `JL-CHAIN` | chain-hash mismatch, fork at tip, duplicate `id`, missing/duplicate genesis, or a §5.4-step-8 semantic violation (sign-off replay / scope drift; duplicate `curation-timestamp` per acquisition key) | frozen (core §5) |
| `JL-COVERAGE` | commit/tag on a curated ref without a covering entry, **or** an `outputs[].git_object` that is a default-branch commit (§5.4 step 9 self-reference subclass) | frozen (core §5) |
| `JL-RECOVERED` | a verified recovery-lineage discontinuity (§5.1/§5.4 step 5) — **WARN**, not FAIL; surfaced so the break stays visible | **proposed** |
| `JL-SCHEMA` | non-canonical line, schema-invalid entry, or non-integer number | **proposed** |
| `JL-RENDER` | `journal.md` differs from a fresh render of the ledger | **proposed** |

CLI mapping: every **FAIL** code above ⇒ exit `15` (journal integrity failure) from
`swhap journal verify`; `JL-RECOVERED` is a WARN and does **not** change the exit code
(clean run still exits `0`, as with the step-4 ordering WARNs, §4). The validator
reports JC-1/JC-2/LG-1 findings under its own exit map (the only two maps, M1b
co-signed ruling).

## 13. Deviations from the owning plans and open points

Deviations (each listed in the W1 sign-off summary):

1. **Canonical storage split**: core §4.6 described `journal.md` with embedded JSON
   blocks; this spec stores the canonical data in `metadata/journal.jsonl` and makes
   `journal.md` a deterministic render *of the same blocks* (§10) — hand-edit-proof
   and trivially hashable. Rationale: extracting canonical bytes from hand-editable
   Markdown is fragile; the task brief endorses the JSONL-alongside layout.
2. **`state-transition` action added**: intake §4.4 mandates a ledger entry per label
   transition but named no action value for it; the named set elsewhere covers only
   provenance/escalation/publish/review-session/ai-consent.
3. **`annotation` action named** for the AI annotate-only channel (core §4.6 says
   "AI appends annotation entries" without fixing the value).
4. **`review-session` detail key is `ref`** (intake §4.3) — core §4.6's
   `issue_or_pr_ref` wording is treated as superseded by the payload owner's spec.
5. **`genesis`, `acquire`, `curation-timestamp`, `rewrite-event` action names and
   payloads fixed here** (the plans required the events but not the names/shapes);
   `acquire` is emitted by the `swhap ingest` verb.
6. **Three proposed error codes** `JL-SCHEMA`, `JL-RENDER`, `JL-RECOVERED` (§12).
7. **`apply-proposal` action added** (the 22nd value): core §4.8 / resolution 11 render
   an approved AI proposal into default-branch `metadata/`, but the closed taxonomy
   named no value for it and no clause wired the resulting file writes to §9 outputs.
   Fixed here: machine actor, file-only `outputs`, a seeded `inferred` transition, and a
   `details.approval_entry` reference. The conformance fixture now covers this M4 flow.
8. **Per-action payloads are now schema-enforced for every value.** The §6 "Required
   payload" column was previously prose for ten pipeline actions (`acquire`, `inspect`,
   `extract`, `strip-wrapper`, `emptydir`, `digest`, `csv-validate`, `csv-convert`,
   `plan`, `validate`); each now has an `allOf` clause, closing the schema/prose gap
   that silently defeated the crit-M4 checksum guarantee for the checksum-bearing
   actions.
9. **`details.acquisition` discriminator defined** (was an unbacked §13 proposal): the
   §5.4 step-8 curation-timestamp uniqueness rule now groups by an explicit acquisition
   key (`details.acquisition`, absent ⇒ `"__default__"`), so a legitimate second
   acquisition gets its own D4 timestamp and an accidental duplicate within one
   acquisition still FAILs — the two-reading divergence is removed.

Open points (could not be settled by this drafter alone):

- **Curation-timestamp dedicated mirror file**: core risk #3 leaves open whether the
  D4 timestamp is *additionally* mirrored in a dedicated `metadata/` file beyond
  `plan.json`; additive schema change either way — Roberto at M1b.
- **`plan.json` home path**: examples use workbench-root `plan.json`; the plan.json
  schema owner should fix the path at M1b (this contract only requires `inputs` to
  reference it by path+sha256, so it is robust to the ruling).
- **Model G ledger location**: `metadata/journal.jsonl` on the default branch is
  asserted for both D1 models; confirm against renderer-G layout archaeology
  (core risk #6) at the D1 ruling.
- **D3 final ruling (M1c)** may tighten `rewrite-event` to pre-`archived` only
  (config change; schema unchanged) — carried per decisions.md.
- **Per-acquisition vs per-workbench ledger scoping** for multi-acquisition
  workbenches: this spec assumes one ledger per workbench (one genesis). The grouping
  mechanism is now **settled** — `details.acquisition` is a schema-typed discriminator
  and §5.4 step 8 groups curation-timestamp uniqueness by it (absent ⇒ `"__default__"`),
  so a second acquisition is well-defined and non-divergent. What remains open (second
  pilot) is only whether a heavily multi-acquisition workbench eventually warrants a
  *separate ledger file per acquisition* rather than one shared ledger; that is a
  layout choice, not a grammar gap, and is additive either way.
