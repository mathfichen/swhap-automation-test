# `version_history.csv` — canonical contract

**Status: FROZEN (W1 sign-off 2026-06-05). Changes are versioned amendments.**
Version: 0.1.1-draft · Date: 2026-06-05 · Owner: core-pipeline workstream (M1b freeze artifact)
Binding sources: decisions.md D2 (canonical dialect, legacy read-only), Q9 defaults
(date/identity conventions — **this document IS the Q9 sign-off table**, per
core-pipeline T2); critique C1, crit-M3, crit-M15; core-pipeline.md §4.2/§5;
validator.md CSV-1..7; exemplar-pilot.md §4.3.
Single implementation: `swhap_core.vhcsv` (core T4, M1c). The validator never
re-implements this grammar; its only local CSV logic is the byte-exact header
check (CSV-1).

This file is normative. Key words MUST / MUST NOT / SHOULD / MAY are RFC 2119.
Every W2 builder codes against this text; anything not stated here is
implementation-defined and MUST NOT be relied on across module boundaries.

---

## 1. Scope and profiles

`metadata/version_history.csv` is the **authoritative driver** of the curated
`SourceCode` history: one row = one release = one commit + one annotated tag.
Row order is the commit order (§7).

Two dialect profiles exist:

| Profile | Read | Write | Defined in |
|---|---|---|---|
| `canonical` | yes | yes (sole writer: `vhcsv.writer`) | §2–§10 |
| `legacy` (Unipisa/DT2SG) | yes (convert-on-read) | **never** (D2) | §11 |

The legacy profile exists only for `swhap csv convert --from unipisa` and the
validator's `legacy` audit profile. No tool in this toolkit ever emits the
legacy dialect.

---

## 2. File-level syntax (canonical profile)

### 2.1 Header — byte-exact

Line 1 of the file MUST be exactly these 98 bytes (then the line terminator):

```
directory name,date,author name,author email,curator name,curator email,release tag,commit message
```

- sha256 of the 98 header bytes (no terminator):
  `d8f5ae1f40f10667baa8f436b3fcfacc151d641d2fe26eb66650a6fb106e0b81`
- No quoting, no extra/missing spaces, no trailing comma, no case variation.
- Any deviation is `CSV-HEADER` (FAIL). The validator's CSV-1 compares bytes,
  not parsed tokens, so it works without the parser (M1a) and catches the
  published exemplar's ad-hoc 7-column header (defect `RED-csv-header`).

### 2.2 Encoding and BOM

- Encoding MUST be UTF-8. Non-UTF-8 byte sequences are `CSV-FIELD` (FAIL),
  reported with byte offset.
- Writers MUST NOT emit a byte-order mark. On read, a leading BOM
  (`EF BB BF`) makes the header not byte-exact and therefore fails
  `CSV-HEADER`; the error message MUST name the BOM explicitly
  ("file starts with a UTF-8 BOM — remove it") so the failure is actionable,
  not a cryptic header mismatch. (Drafter ruling; see Open points.)

### 2.3 Line endings

- Writers MUST terminate every record (including the last) with a single LF
  (`0x0A`).
- Readers MUST accept CRLF (`0x0D 0x0A`) as a record terminator and treat it
  as LF (tolerated for hand-edited files from Windows curators); a CR not
  followed by LF outside a quoted field is `CSV-FIELD` (FAIL).
- A missing terminator on the final record is tolerated on read, never written.

### 2.4 RFC 4180 profile

- Field separator: `,` (`0x2C`). Exactly 8 fields per record; more or fewer is
  `CSV-FIELD` (FAIL) — fields are never silently dropped or padded.
- Quoting — the reader rule and the writer rule are distinct and MUST NOT be
  conflated:
  - **Readers** MUST accept any RFC 4180-valid quoting. A field MAY be
    enclosed in double quotes (`"`) whether or not its content requires it;
    a double quote inside a quoted field is escaped by doubling (`""`).
    Unnecessary quoting (e.g. LibreOffice's "quote all text cells" export, a
    single hand-quoted field, an AI-drafted `csv_proposal`) is **not an
    error**: the field is parsed normally and the quotes are not part of the
    value. `swhap csv validate` reports a file containing unnecessarily
    quoted fields with a single file-level **INFO** note ("not in canonical
    writer form — re-serialize with the vhcsv writer for diff-stable bytes");
    it never FAILs for this. Malformed quoting — a `"` inside an unquoted
    field, an unterminated quoted field, or content between a closing quote
    and the next separator/terminator — is `CSV-FIELD` (FAIL).
  - **Writers** MUST enclose a field in double quotes iff it contains a
    comma, a double quote, or a line break, and MUST NOT quote fields that
    do not require it (deterministic, diff-stable output; §2.5).
- Embedded line breaks are permitted **only inside the quoted
  `commit message` field** (§9). Inside a quoted message, both LF and CRLF are
  accepted on read and normalized to LF; writers emit LF. A line break in any
  quoted field other than `commit message` is `CSV-FIELD` (FAIL).
- No comment lines, no blank lines (a blank line anywhere, including trailing,
  is `CSV-FIELD` FAIL), no leading/trailing whitespace around separators
  (whitespace is field content and §8 forbids it at field edges).

### 2.5 Canonical writer bytes (determinism law)

Two conforming writers given the same parsed rows MUST produce **byte-identical
files**. Everything a writer emits is pinned: UTF-8, no BOM (§2.2), LF
terminators on every record including the last (§2.3), minimal quoting (§2.4),
LF inside quoted messages (§2.4), and the precision-preserving date
serialization of §4.6. Byte-comparison consumers (conversion round-trip
fixtures, validator expected-output fixtures, exemplar T5 diff review) rely on
this; any writer freedom ("MAY emit X") is a conformance bug in this contract,
not a latitude.

---

## 3. Column semantics

| # | Column | Meaning | Maps to |
|---|---|---|---|
| 1 | `directory name` | Name of the release directory under the depository's source area; also the extraction target of one raw-material archive | tree selected for the release commit |
| 2 | `date` | Historical release date (§4) | `GIT_AUTHOR_DATE` (raw `@<epoch> <offset>`) |
| 3 | `author name` | Display label for the historical author(s) (§5) | `GIT_AUTHOR_NAME` |
| 4 | `author email` | Author email, placeholder by default (§5) | `GIT_AUTHOR_EMAIL` |
| 5 | `curator name` | Curator performing the acquisition | `GIT_COMMITTER_NAME` and tag tagger name |
| 6 | `curator email` | Curator email, real address opt-in (§5) | `GIT_COMMITTER_EMAIL` and tagger email |
| 7 | `release tag` | Annotated tag name for the release (§6) | `refs/tags/<release tag>` (via candidate namespace until publish) |
| 8 | `commit message` | Commit subject/body for the release commit (§9) | commit message (tag message is derived: `Version <release tag>`) |

Committer/tagger **date** is NOT in the CSV: it is the fixed curation
timestamp recorded in metadata (D4 bit-reproducibility), applied uniformly by
`apply.py`. The CSV carries identity only for the curator.

All 8 fields are mandatory and non-empty (`CSV-FIELD` FAIL on empty), with no
exceptions — the legacy `*` tag and `|` message conventions are converted away
on read (§11), never present in canonical files.

---

## 4. Date grammar (Q9 defaults — frozen here)

### 4.1 Accepted forms

Exactly three forms, in order of preference:

| Form | Grammar | Interpretation | Precision | Provenance flag |
|---|---|---|---|---|
| Full timestamp | `YYYY-MM-DDTHH:MM:SS±HH:MM` or `YYYY-MM-DDTHH:MM:SSZ` | as written; `Z` ≡ `+00:00` (normalized to `+00:00` internally; readers accept `Z`, writers MUST NOT emit it — §4.6) | `second` | none (as asserted) |
| Date only | `YYYY-MM-DD` | UTC midnight: `T00:00:00+00:00` | `day` | flagged: time-of-day not asserted |
| Year only | `YYYY` | `YYYY-01-01T00:00:00+00:00` | `year` | flagged **inferred**: month/day not asserted |

- Separator is literal `T` (uppercase). A space separator, fractional seconds,
  `YYYY-MM` month-only form, or any other shape is `CSV-DATE` (FAIL).
- `YYYY` is exactly 4 ASCII digits; `MM`/`DD`/`HH`/`MM`/`SS` exactly 2.
  Calendar validity is enforced (no Feb 30, no `24:00`, leap years per
  proleptic Gregorian): violations are `CSV-DATE` (FAIL).
- Offset range: `-12:00` … `+14:00`; minutes `00`–`59`.

### 4.2 Timezone policy

A time component without a UTC offset (naive datetime) is `CSV-TZ` (FAIL) —
never guessed, never defaulted. This is the structural fix for dt2sg-gen.py's
silent tz-drop (C1, `swhap-tools/dt2sg-gen.py:13`): the codebase contains no
naive datetimes (lint-enforced in core), and the grammar makes one
unrepresentable. Date-only and year-only forms are pinned to UTC *by this
contract* (the table above), which is a documented convention, not a guess.

### 4.3 Internal representation

Every parsed date becomes the triple
`(epoch_seconds: int, utc_offset: ±HH:MM, precision: second|day|year)`.
`epoch_seconds` is the true UTC instant; `utc_offset` is preserved for
faithful `GIT_AUTHOR_DATE` rendering. Precision and the §4.1 flags propagate
to the provenance ledger (journal entries, Q11): `day` → provenance note,
`year` → provenance state **inferred** requiring curator visibility.

### 4.4 Pre-1970 dates

Pre-epoch dates (Pisa corpus reaches 1968: Softi/CEP) are first-class:
`epoch_seconds` is negative, and `apply.py` passes
`GIT_AUTHOR_DATE='@<epoch> <±HHMM>'` (raw-epoch form) to git plumbing via
environment — never a formatted date string, never libgit2 (the documented
DT2SG failure class, crit-M3). A startup check enforces the pinned git
version; the 1968 conformance fixture (§12, row V6) proves the pin accepts
negative epochs. There is **no floor year in this grammar**. Fallback only if
the pinned-git mitigation ever fails: a documented floor year failing loud
with `CSV-DATE` — that would be a versioned amendment to this contract, not a
silent behavior change.

### 4.5 Upper bound — future dates (reference-timestamp rule)

Release dates are historical by definition. A date is `CSV-DATE` (FAIL) iff
its UTC instant (`epoch_seconds`, §4.3) is **strictly greater** than the UTC
instant of the **reference timestamp** in effect. `date == reference` is
valid (same-day acquisition of a just-released tarball is legitimate).

The reference timestamp is **never the wall clock** — wall-clock comparison
makes the same bytes FAIL today and PASS next year, rots conformance fixtures
by construction, and breaks the validator's `--run-meta-stable` byte-stable
report mode and D4 reproducibility of gate evidence. The baseline is resolved
deterministically:

1. **Workbench / pipeline context** (`swhap plan|apply|build`; validator
   CSV-3 running over a workbench): the fixed curation timestamp recorded in
   metadata (`plan.json` / journal, core §4.6). Same bytes + same recorded
   curation timestamp ⇒ same verdict, on any machine, on any date.
2. **Standalone `swhap csv validate FILE`** (bare file, no workbench): the
   future-date check is evaluated **only if** `--reference-date <§4.1 full
   timestamp>` is supplied. Without it, the check is **not evaluated** and
   the report carries one INFO note ("future-date check skipped: no
   reference timestamp — pass `--reference-date` or validate inside a
   workbench"); it is never silently counted as passed, and never falls back
   to the wall clock.

Conformance fixtures for this rule MUST pin the baseline explicitly (the §12
red fixture for §4.5 is defined as the file *plus*
`--reference-date 2026-06-05T00:00:00+00:00`); a fixture whose verdict
depends on the run date is non-conforming by construction.

### 4.6 Date serialization on write (normative bytes)

The writer renders the internal triple (§4.3) back into the date column **by
stored precision**, byte-exactly:

| Stored precision | Output bytes | Notes |
|---|---|---|
| `second` | `YYYY-MM-DDTHH:MM:SS±HH:MM` | offset = preserved `utc_offset`; UTC is rendered `+00:00`, **never `Z`**; sign always present; all tokens zero-padded |
| `day` | `YYYY-MM-DD` | never expanded to a timestamp |
| `year` | `YYYY` | never expanded to a date or timestamp |

Precision expansion is forbidden: re-serializing a `year`-precision value
(e.g. row V4's `1994`) as `1994-01-01T00:00:00+00:00` destroys the
precision/provenance signal in the published CSV and is a conformance
violation, even though the bytes would re-parse. Round-trip laws: parse →
write → parse is the identity on `(epoch_seconds, utc_offset, precision)`;
write → parse → write is the identity on bytes. The §12.2 conversion
fixture's expected date bytes are exactly `1994-10-27T12:26:20+00:00` — a
writer emitting `1994-10-27T12:26:20Z` does not conform.

---

## 5. Identity rules (Q9 defaults, crit-M15)

### 5.1 Author identity

- `author name` is a single display label. For a single known author, use the
  person's name (`Giuseppe Attardi`). For **multiple authors**, the canonical
  convention is a collective label — `<Project> authors`
  (e.g. `Wild_LIFE authors`) — NOT a `;`-joined list: per-person attribution
  lives in the journal provenance ledger and `codemeta.json`, and MAY
  additionally be surfaced as `Co-authored-by:` trailers in the commit message
  body (§9.3). The CSV is a git-ident carrier, not the attribution record.
- `author email` defaults to a **placeholder noreply address**:
  `<project-slug>-authors@noreply.example.org` for collective labels, or
  `<name-slug>@noreply.example.org` for individuals whose address is unknown
  or must not be published. The placeholder domain set is shared, tracked data
  (validator `data/placeholder_domains.json`); `noreply.example.org` is the
  default member. Real (deceased or non-consenting living) third-party
  addresses MUST NOT appear: the CSV is published into immutable SWH-archived
  history (crit-M15). Real author addresses are recorded in the journal
  provenance entry only (exemplar precedent: Peter Van Roy's address stays in
  the ledger, never in the CSV).
- A real, non-placeholder author email is permitted by the grammar (an author
  may have consented) but triggers the validator's PI-1 email lint (WARN +
  curator confirmation required); it is never the default.

### 5.2 Curator identity

- `curator name`/`curator email` identify the acquiring curator; they become
  committer and tagger ident on every release commit/tag.
- Default is the same placeholder scheme (`<curator-slug>@noreply.example.org`).
  A **real curator email is opt-in**: the curator explicitly confirms
  publication of their address. The opt-in is recorded by a
  `provenance-transition` ledger entry on the stable item id
  `pii.curator_email` reaching state `curator-approved` by a curator-kind
  actor (journal-schema §5.5/§6). This single transition is the **sole**
  carrier of the opt-in: the validator's PI-1 reads exactly it (and JC-2
  verifies it as a provenance transition); no `ai-consent` entry is involved
  (that action records AI-provider consent only). Roberto's brief-§8 example
  opted in; the regenerated Wild_LIFE CSV confirms at exemplar T5.

### 5.3 Email syntax

Both email fields MUST parse as a bare RFC 5322 `addr-spec`
(`local@domain`, exactly one `@`, non-empty dot-atom local part and domain;
no display name, no angle brackets, no comments). Violation: `CSV-FIELD`.

---

## 6. Release tag grammar

1. **Hard validity** (`CSV-TAG` FAIL if violated): the tag MUST be accepted by
   `git check-ref-format refs/tags/<tag>` (executed argv-only, plus the
   equivalent pure-Python pre-check in `vhcsv` so validation works without
   git). Consequences, spelled out: no ASCII control chars, space, `~`, `^`,
   `:`, `?`, `*`, `[`, `\`; no component starting with `.` or ending with
   `.lock`; no `..`; no `@{`; not `@`; no leading/trailing `/`, no `//`; no
   trailing `.`.
2. **Reserved namespaces** (`CSV-TAG` FAIL): the tag MUST NOT start with
   `candidate/` or `scratch/` — those collide with the frozen candidate-ref
   namespace (`refs/tags/candidate/<model>/<run-id>/<release-tag>`,
   implementation-plan §3.1 resolution 5).
3. **Project convention** (lint, not failure): new acquisitions SHOULD use
   `v<version>` (`v0.90`, `v1.02`). Bare-version tags (`1.1` … `1.9`, CMM
   precedent) are valid — a validator that required `v*` would fail every
   existing acquisition (critique C7) — and produce an INFO-level note only.
4. Length: ≤ 128 bytes (§8 caps).

The tag in column 7 is the **final published name**; during the build it
materializes under the candidate namespace and is renamed to
`refs/tags/<tag>` at publish.

---

## 7. Uniqueness and ordering

| Rule | Severity | Code |
|---|---|---|
| `directory name` values pairwise distinct under §7.1 collision folding | FAIL | `CSV-DUP-DIR` |
| `release tag` values pairwise distinct under §7.1 collision folding | FAIL | `CSV-DUP-TAG` |
| Row order = commit order on `SourceCode` (row N is the parent of row N+1) | normative semantics, not a check | — |
| Dates non-decreasing in row order | **WARN** | `CSV-DATE-ORDER` |

### 7.1 Comparison basis — collision folding (not byte equality)

Byte equality is NOT the uniqueness basis. Two values **collide** iff

```
casefold(NFC(a)) == casefold(NFC(b))
```

(Unicode NFC normalization, then full Unicode case folding, computed with the
pinned Python `unicodedata`/`str.casefold` of the toolkit's pinned
interpreter.) Byte-distinct but collision-folded-equal values are
`CSV-DUP-TAG` / `CSV-DUP-DIR` (FAIL) — the same posture as the extraction
contract's `EX-CASE-COLLISION` (core §4.1), deliberately aligned inside this
M1b freeze: tags `v1.0` and `V1.0` build green on the pinned case-sensitive
CI but collide as loose-ref files on a default-APFS macOS clone; directory
names `café` (NFC) and `café` (NFD) are distinct bytes that silently merge on
the normalizing filesystems of the very Windows/macOS curator machines §2.3
already accommodates. The diagnostic names both rows and both byte sequences,
spelling out code points wherever the two values differ only invisibly.

Row order is authoritative and is NOT derived from dates. Equal dates are
legitimate (Wild_LIFE 0.90 and 0.91 share listing date 1993-08-09 — the order
between them is curatorial knowledge the CSV records). A date regression
(row N+1 earlier than row N) is suspicious but can be true history, hence
WARN: the curator acknowledges it in review; it never blocks the build.
`CSV-DATE-ORDER` is a warning identifier (validator CSV-7), deliberately
absent from the `CsvContractError` exception codes — it raises nothing.

At least one data row MUST be present (a header-only file is `CSV-FIELD`
FAIL: an acquisition with zero releases is not buildable).

---

## 8. Field allowlist (C1 — the dt2sg-gen.py injection classes)

dt2sg-gen.py interpolated raw CSV fields into shell text
(`swhap-tools/dt2sg-gen.py:24-35`: `git checkout master -- source/{}`,
`git commit -m '{}'`, unquoted `mv source/{}/* .`), making every field a shell
/ argv / path-traversal vector. The canonical pipeline executes argv-only with
no `shell=True` anywhere (CI grep-lint), and this allowlist makes the field
values inert even if they ever reach a weaker consumer:

### 8.1 All fields

- Valid UTF-8; Unicode **control characters (category Cc)** forbidden — C0
  (`U+0000`–`U+001F`), DEL (`U+007F`), C1 (`U+0080`–`U+009F`) — with the
  single exception of LF in `commit message` (§9). Includes the ESC-sequence
  class (terminal injection via logs/review UIs). Violation: `CSV-FIELD`.
- Unicode **format characters (category Cf)** forbidden in **every** field,
  no exceptions: bidirectional controls (`U+061C`, `U+200E`/`U+200F`,
  `U+202A`–`U+202E` incl. RLO, `U+2066`–`U+2069`), zero-width characters
  (`U+200B` ZWSP, `U+200C` ZWNJ, `U+200D` ZWJ, `U+2060` WJ, `U+FEFF` at any
  position including interior), soft-hyphen-class invisibles, and the rest of
  category Cf per the pinned interpreter's Unicode data. Rationale — these
  defeat the review surface the HITL safety layer depends on, exactly the
  threat class the Cc ban targets: an RLO makes an author-name field render
  as `Peter Van Roy` while the git-ident bytes differ; a ZWSP yields tag or
  directory-name pairs that are visually identical in the forge tag list or
  diff a curator approves from (such pairs additionally collide under no
  rule if only Cc is banned — §7.1 folding does not strip Cf, the ban makes
  them invalid outright). Violation: `CSV-FIELD`, with the offending code
  point named in the message (e.g. `U+202E RIGHT-TO-LEFT OVERRIDE at row N,
  column M, char index K`). Names that legitimately require ZWNJ/ZWJ (e.g.
  Persian orthography) keep full fidelity in the journal provenance ledger
  and `codemeta.json`; the CSV display label omits the Cf characters (§5.1:
  the CSV is a git-ident carrier, not the attribution record). Open point
  §13.6.
- No leading or trailing whitespace (space, tab, or any Unicode whitespace).
  Canonical files are never silently stripped (dt2sg `.strip()` behavior is a
  legacy-conversion concern only): violation is `CSV-FIELD` FAIL.
- No empty fields (§3).
- **Leading `-` forbidden in fields 1–7** (argv-injection hygiene: a value
  like `--force` must never be option-parseable). `commit message` is exempt
  (a message may start with `- fix …`) — made safe by the companion
  requirement that `apply.py` passes commit/tag messages to `git commit-tree`
  / `git mktag` **via stdin, never argv** (binding on core T7). Violation:
  `CSV-FIELD`.
- Length caps (bytes of UTF-8): `directory name` ≤ 255, `author name` /
  `curator name` ≤ 255, emails ≤ 254, `release tag` ≤ 128,
  `commit message` ≤ 16 384. Violation: `CSV-FIELD`.

### 8.2 Per-field extras

- `directory name`: exactly one path component — `/` and `\` forbidden; values
  `.` and `..` forbidden; no leading `.` (hidden dirs are not release dirs);
  no `:` (Windows drive / git-pathspec ambiguity). It must name an existing
  release directory at build time (that cross-check is the history builder's
  `HB-DIR-MISSING`, not a CSV-layer check).
- `author name`, `curator name`: additionally forbid `<` and `>`
  (git-ident-meaningful: they delimit the email in ident lines and would let a
  name field smuggle a forged email — the "git-config-meaningful sequences"
  class), and `,` is permitted only via RFC 4180 quoting (§2.4). git's own
  crud-trimming never engages because edge whitespace and control chars are
  already banned.
- `author email`, `curator email`: §5.3 syntax; `<`, `>`, and whitespace are
  excluded by addr-spec already.
- `release tag`: §6.
- `date`: §4.

---

## 9. Commit message rules

1. Non-empty (§3); the dt2sg `'<empty>'` substitution hack is dead — an empty
   message is a curatorial omission and fails `CSV-FIELD`.
2. Multi-line permitted via RFC 4180 quoting; line breaks normalized to LF
   (§2.4). Structure SHOULD follow git convention: subject line, blank line,
   body. Subject ≤ 72 chars is an INFO lint, never a failure.
3. Trailers MAY be used; `Co-authored-by: Name <email>` trailers are the
   sanctioned way to surface per-person authorship in git history when the
   author column carries a collective label (§5.1). Emails inside trailers
   fall under the same placeholder policy (PI-1 lints them too).
4. Leading `-` allowed (§8.1 exemption); all other §8.1 rules (control chars,
   UTF-8, length) apply.
5. The annotated tag message is NOT in the CSV: it is derived as
   `Version <release tag>` by the builder (deterministic; D4).

---

## 10. Diagnostics (alignment with core §5 and validator CSV-1..7)

| Code | Severity | Condition | Validator check |
|---|---|---|---|
| `CSV-HEADER` | FAIL | §2.1 header not byte-exact (incl. BOM §2.2); unrecognized dialect in legacy profile | CSV-1 |
| `CSV-FIELD` | FAIL | §2.4 structure, §3 arity/empties, §8 allowlist, §5.3 email syntax | CSV-2, CSV-6 |
| `CSV-DATE` | FAIL | §4.1 grammar / calendar / §4.5 future date | CSV-3 |
| `CSV-TZ` | FAIL | §4.2 naive timestamp | CSV-3 |
| `CSV-TAG` | FAIL | §6.1–6.2 | CSV-4 |
| `CSV-DUP-DIR` | FAIL | §7 | CSV-5 |
| `CSV-DUP-TAG` | FAIL | §7 | CSV-5 |
| `CSV-DATE-ORDER` | WARN | §7 monotonicity | CSV-7 |
| `CSV-AMBIGUOUS-US-DATE` | WARN | §11.3, legacy profile only — converter proceeds (applies US `MM/DD`) and flags the row | legacy audit profile (not a canonical-profile check) |

Severity vocabulary is the **closed FAIL / WARN / INFO** enum shared with the
validator report schema (implementation-plan §3.2, validator-report.md §2.3)
and the exit maps. There is no `FLAG` severity — it existed in no other
contract and had no defined mapping; `CSV-AMBIGUOUS-US-DATE` is a **WARN**
(the curator-review signal is carried by WARN severity plus the conversion
note, exactly as `CSV-DATE-ORDER` carries its review signal).

Two disjoint classes, by severity:

- **FAIL diagnostics** (`CSV-HEADER, CSV-FIELD, CSV-DATE, CSV-TZ, CSV-TAG,
  CSV-DUP-DIR, CSV-DUP-TAG`) raise `CsvContractError` subtypes (core
  `errors.py`), carry machine fields (row, column, byte offset where
  applicable) plus a plain-language template id (crit-M11), and map to
  `swhap` exit code 12.
- **WARN diagnostics** (`CSV-DATE-ORDER`, `CSV-AMBIGUOUS-US-DATE`) raise
  **nothing**. They are deliberately absent from the `CsvContractError`
  exception codes (matching core-pipeline §5, where the parenthetical
  `[legacy]` on `CSV-AMBIGUOUS-US-DATE` marks it as a legacy-profile
  *diagnostic identifier*, not a raised exception subtype). They are emitted
  as report findings and conversion-worklist entries; they never abort a
  parse, never set exit 12, and never block the build.

This resolves the converter's behavior unambiguously: a legacy day≤12 row
(e.g. `04/05/1994`) **converts successfully** — `swhap csv convert` writes
the canonical output with the US `MM/DD` reading applied, records both
candidate ISO dates in the conversion note, emits one `CSV-AMBIGUOUS-US-DATE`
WARN per such row, and **exits 0** (a worklist of WARN/flagged rows is a
successful conversion with review items, §11.4 — not an error). It does
**not** raise `CsvContractError`, does **not** exit 12, and does **not**
suppress output. Since day≤12 dates are ~40% of real legacy dates, this is
what lets the M1-exit legacy audit (resolution 9, validator T10) run at all.

Every diagnostic names the violated section of this document. The file-level
INFO notes (§2.4 unnecessary quoting; §4.5 skipped future-date check) are
report findings only, raise nothing, and never affect exit status.

**Inferred/defaulted date precision is NOT a CSV diagnostic.** A valid
date-only (`day` precision) or year-only (`year` precision, **inferred**) value
emits **no** CSV-3 finding and **no** CSV code — CSV-3 is exactly `CSV-DATE`
and `CSV-TZ` (both FAIL). The "inferred dates require curator visibility"
invariant is carried **solely by the journal provenance ledger**: per §4.3,
`day` → provenance note, `year` → provenance state **inferred** requiring
curator visibility, recorded on the date item. The validator does **not**
mint a CSV-3 finding for this; validator-report §2.9 names the same carrier
(the provenance ledger), so the two contracts agree and the signal cannot
fall through the gap.

---

## 11. Legacy Unipisa/DT2SG dialect — READ-ONLY (D2, crit-M3)

Observed ground truth: `Unipisa/DT2SG/metadata_example.csv`,
`Unipisa/SWHAP-TEMPLATE/metadata/version_history.csv`,
`Unipisa/CMM-Workbench/metadata/version_history.csv`
(corpus/external.md §3.1). Recognition is by the legacy header line:

```
directory name,author name,author email,date,curator name,curator email,release tag,commit message
```

(same 8 columns; `date` in position 4 instead of 2). Consumers:
`swhap csv convert --from unipisa` and the validator's `legacy` audit profile.
**No writer exists and none will be built** (D2: deliberate, declared, dated
break — 2026-06-05). Conversion produces canonical in-memory rows; every
converted field carries provenance state `computed` plus a conversion note.

#### 11.0.1 Recognized legacy headers (two dialects)

The legacy profile recognizes **two** header shapes — the observed installed
base is not one dialect:

| Dialect | Header line | Field-4 label | Source |
|---|---|---|---|
| `unipisa` (DT2SG) | `directory name,author name,author email,date,curator name,curator email,release tag,commit message` | `date` | `Unipisa/*` corpus |
| `guide` | `directory name,author name,author email,date original,curator name,curator email,release tag,commit message` | `date original` | SWHAP guide, `swhapguide/SwhapGuide-SWHAPPE.md:302-315` |

The two differ only in the field-4 label (`date` vs `date original`);
positions and semantics are identical, so both map through §11.1 the same way.
`--from unipisa` accepts both (the flag name is the profile, not a single
header); a future `--from guide` alias MAY be added but is not required.

Header recognition is **whitespace- and case-tolerant on read** (hand-made
legacy files vary): a header matches a legacy dialect iff, after trimming
spaces immediately adjacent to each comma separator and casefolding, its eight
tokens equal that dialect's eight tokens. (This tolerance is legacy-read-only;
the canonical profile's header is byte-exact, §2.1, no exceptions.) A file
whose header matches neither legacy dialect under this tolerant comparison is
`CSV-HEADER` (FAIL) with a diagnostic that lists **both** recognized legacy
headers and, if the header is close to one (≤ 2 token edits), names the
nearest dialect ("looks like the SWHAP guide dialect — field 4 is `date
original`").

The reciprocal canonical-profile hint (§12.3 I3) is extended in kind: a
canonical-profile file whose header matches **either** legacy dialect emits
the hint "legacy Unipisa/guide dialect — use `swhap csv convert --from
unipisa`".

### 11.1 Per-field mapping

| Legacy field (pos) | Canonical field (pos) | Conversion | Lossy / flagged |
|---|---|---|---|
| `directory name` (1) | `directory name` (1) | `.strip()` edge whitespace (dt2sg parity), then §8.2 allowlist | flagged if stripping changed the value |
| `author name` (2) | `author name` (3) | strip; §8.2 (`<`/`>` ban may force curator edit) | flagged if `<`/`>` removed-needed |
| `author email` (3) | `author email` (4) | strip; legacy files carry real addresses (e.g. `attardi@di.unipi.it`) — kept verbatim but PI-1 flags them against the §5.1 placeholder default | **flagged** (crit-M15 review) |
| `date` (4) | `date` (2) | §11.2 US-date conversion | **lossy** (tz) + possibly **flagged** (§11.3) |
| `curator name` (5) | `curator name` (5) | strip | — |
| `curator email` (6) | `curator email` (6) | strip; real address → PI-1 flag (canonical default is opt-in) | **flagged** |
| `release tag` (7) | `release tag` (7) | three cases, §11.1.1 | — |
| `commit message` (8) | `commit message` (8) | every `\|` → LF (DT2SG line-separator convention); strip; empty → left empty and **flagged** for curator completion (the canonical grammar will reject it until filled — no silent `<empty>` substitution) | **lossy** — a literal `\|` in original text is indistinguishable from a separator; conversion note records the original string |

#### 11.1.1 Release-tag conversion (three cases)

The legacy `release tag` field has three legitimate values; canonical's
invariant is one row = one release = one tag (§1), so a non-release row has no
canonical representation and MUST NOT be fabricated into one:

1. **`*`** (DT2SG "tag = directory name" sentinel) → tag := `directory name`
   value, provenance `computed`, note `tag derived from directory name (legacy
   *)`; result then passes §6 (the `v` convention lint is suppressed for
   converted rows — bare CMM-style tags are historical fact).
2. **Non-empty, non-`*`** (an explicit tag name) → carried through verbatim,
   then validated against §6; on §6 failure the row goes to the conversion
   worklist (§11.4) for curator repair, not silently dropped.
3. **Empty** (guide-sanctioned: "a tag name if the directory contains a
   release, **empty otherwise**", `SwhapGuide-SWHAPPE.md:308`) → the row
   describes a directory that is **not a release**. There is no canonical row
   for a non-release directory. The converter **does not emit a canonical
   row** for it; instead it records a **worklist** entry (§11.4):
   `legacy row <dir> has an empty release tag (non-release directory) — no
   canonical release row produced; if this directory IS a release, supply a
   tag`. This is a worklist item, not a FAIL: the input is valid legacy data,
   the output simply has nothing to materialize. The curator decides (supply a
   tag → re-run, or accept the omission).

### 11.2 Legacy date conversion

**The observed dialect is the acceptance set of `dateutil.parser.parse`, not a
strict regex.** The real DT2SG parser is `dateutil.parser.parse`
(`swhap-tools/dt2sg-gen.py:4` import, `:13` call), so any date a published
legacy workbench legitimately contains is, by construction, a string dateutil
accepted. A strict `\d{2}/\d{2}/\d{4}` regex would hard-FAIL plausible corpus
data (`4/5/1994`, `27/10/1994`) that the original toolchain processed
successfully, blocking the T10 legacy audit on files the installed base
considers valid. The converter therefore recognizes the **dateutil
slash-date dialect**, with US (`MM/DD`) as the documented day-first/month-first
resolution order (§11.3), and pins the following — implementers MUST NOT
diverge between `strptime`-based and regex-based readings:

- **Token digit count is 1 or 2** for month and day: `M/D/YYYY`,
  `MM/DD/YYYY`, and mixed (`4/05/1994`) are all accepted. Non-zero-padded
  tokens are valid legacy input (dateutil and `strptime('%m/%d/%Y')` both
  accept `4/5/1994`; a `\d{2}/\d{2}/\d{4}` regex would not — the regex
  reading is **non-conforming**). Year is exactly 4 digits (two-digit years
  are out of scope — see below).
- `M/D/YYYY HH:MM:SS` → `YYYY-MM-DDTHH:MM:SS+00:00`, precision `second`,
  note `timezone unknown in legacy source; UTC assumed` — **lossy**: the
  original local offset is unrecoverable; the assumption is recorded, never
  silent (the exact C1 dt2sg failure, made visible instead of structural).
  Seconds component optional `HH:MM` is accepted and zero-filled to `:00` with
  a note.
- `M/D/YYYY` (no time) → `YYYY-MM-DD` canonical date-only (then §4.1
  day-precision flag applies).
- An **ISO-shaped** legacy value (`YYYY-MM-DD[THH:MM:SS[±HH:MM|Z]]`) — which
  dateutil also accepts and which appears in newer legacy files — converts as
  the corresponding canonical form unchanged (a naive ISO time still triggers
  the §4.2 UTC-assumed note in the legacy profile; it is **not** `CSV-TZ`
  FAIL on the legacy read path, since legacy tz-drop is the documented input
  condition being repaired).
- **Two-digit years** and any other dateutil-accepted shape that is **not** a
  4-digit-year slash date or an ISO date (e.g. `Oct 27 1994`, `1994/10/27`
  big-endian slashes, day-first textual months) → conversion **worklist**
  entry, not a silent guess and not a hard FAIL: dateutil's century rollover
  and field-order heuristics are exactly the ambiguity this contract refuses
  to bury. The note records the raw token and asks the curator to supply an
  unambiguous canonical date. (Rationale: the goal is to read what the
  installed base actually contains while never letting a heuristic silently
  pick a date — divergent readings become worklist items, never differing
  committed history.)

### 11.3 US-date ambiguity

For a slash date `A/B/YYYY`, let `A` and `B` be the first and second numeric
tokens. Resolution mirrors `dateutil`'s month-first-with-day-first-fallback
(the historical DT2SG behavior), made explicit so no two implementers diverge:

| `A` (1st token) | `B` (2nd token) | Reading | Flag |
|---|---|---|---|
| `1`–`12` | `1`–`12` | **ambiguous** — apply US `MM/DD` (`A`=month) | `CSV-AMBIGUOUS-US-DATE` **WARN**; both candidate ISO dates recorded in the note |
| `13`–`31` | `1`–`12` | unambiguous `DD/MM` (`A`=day) — month-first impossible, dateutil's day-first fallback | none |
| `1`–`12` | `13`–`31` | unambiguous `MM/DD` (`A`=month) | none |
| else | else | not a valid calendar date under either reading | §11.2 worklist (curator supplies date) |

So `04/05/1994` → US reading `1994-04-05` **+ `CSV-AMBIGUOUS-US-DATE` WARN**
(May 4 recorded as the alternate candidate); the row still **converts and the
conversion exits 0** (§10). `27/10/1994` → unambiguous `1994-10-27`, **no
flag** — this is the date the original dateutil-based toolchain produced and
the date the published acquisition already carries, so the T10 legacy audit
sees it converge, not FAIL. `CSV-AMBIGUOUS-US-DATE` is a WARN, never a raised
error and never an exit-12 condition (§10): ambiguity is surfaced for curator
review, it does not abort the conversion of a ~40%-of-corpus date class.

### 11.4 Legacy file-level tolerances

UTF-8 attempted first; on decode error, latin-1 with a file-level flag
(1990s-era material). CRLF tolerated. BOM tolerated on read in the legacy
profile only (stripped, flagged). Output of `swhap csv convert` is always a
fully canonical §2–§10 file — converted rows that still violate the canonical
grammar (e.g. empty message, real emails pending curator decision) are
reported as a conversion worklist, not silently written.

### 11.5 What legacy values are lossy or flagged — summary

- **Lossy**: timezone of every legacy timestamp (UTC assumed, noted); literal
  `|` characters in messages (separator collision, original preserved in
  note).
- **Flagged for curator review** (WARN / worklist, conversion still exits 0):
  ambiguous both-tokens-≤12 dates (`CSV-AMBIGUOUS-US-DATE`); real
  author/curator emails (PI-1 / §5 policy); empty messages;
  edge-whitespace-stripped fields; latin-1 fallback decode; two-digit-year and
  other non-pinned date shapes (§11.2 worklist); empty legacy release tag
  (§11.1.1 case 3 — no canonical row emitted); §6-invalid explicit tags.
- **Computed, not lossy**: `*` tag derivation; field reordering; unambiguous
  `DD/MM` (1st token ≥ 13) and `MM/DD` (2nd token ≥ 13) date readings (§11.3,
  no flag — matches the dateutil-based installed base).

---

## 12. Conformance examples

These examples are the seed of `fixtures/csv/` (core T4 / validator T6b
fixtures). Valid rows use the real Wild_LIFE regeneration data
(exemplar-pilot §4.3; curator email shown opted-in per Roberto's brief-§8
precedent — confirm at exemplar T5).

### 12.1 Valid file (canonical profile) — exercises every convention

```csv
directory name,date,author name,author email,curator name,curator email,release tag,commit message
0.90,1993-08-09,Wild_LIFE authors,wildlife-authors@noreply.example.org,Roberto Di Cosmo,roberto@dicosmo.org,v0.90,Wild_LIFE 0.90 — first public release (CMU AI-repository listing)
0.91,1993-08-09,Wild_LIFE authors,wildlife-authors@noreply.example.org,Roberto Di Cosmo,roberto@dicosmo.org,v0.91,Wild_LIFE 0.91
1.0,1994-03-24,Wild_LIFE authors,wildlife-authors@noreply.example.org,Roberto Di Cosmo,roberto@dicosmo.org,v1.0,"Wild_LIFE 1.0

License copyright year updated 1992 -> 1993.
Co-authored-by: Peter Van Roy <pvr@noreply.example.org>"
1.02,1994,Wild_LIFE authors,wildlife-authors@noreply.example.org,Roberto Di Cosmo,roberto@dicosmo.org,v1.02,Wild_LIFE 1.02 (Ultrix port; author-supplied tarball via PR #1)
Softi-1968,1968-07-01,Softi authors,softi-authors@noreply.example.org,Example Curator,example-curator@noreply.example.org,v1968,Softi for CEP — pre-epoch author date exercise
2.0-beta,1996-11-05T14:30:00+01:00,"Hervé, Jean-Claude",jc-herve@noreply.example.org,Example Curator,example-curator@noreply.example.org,2.0-beta,- full timestamp with offset; quoted comma in author name; leading-dash message
```

| Row | Conventions exercised |
|---|---|
| V1 (`0.90`) | date-only ⇒ UTC midnight, precision `day`, flagged (§4.1); collective author label + placeholder email (§5.1); curator real-email opt-in (§5.2); `v` tag convention (§6.3) |
| V2 (`0.91`) | **same date as V1** — equal dates legal, row order authoritative (§7, the Wild_LIFE case) |
| V3 (`1.0`) | RFC 4180 quoted multi-line message with blank line + `Co-authored-by` trailer (§2.4, §9.2–9.3) |
| V4 (`1.02`) | **year-only** `1994`: internal instant `1994-01-01T00:00:00+00:00`, precision `year`, provenance **inferred** (§4.1); **re-serialized back to exactly `1994`** — never expanded to a timestamp (§4.6). Value RULED by Roberto 2026-06-06 from the tar-mtime evidence (fixtures/wildlife/manifests/1.02-date-evidence.md): real source mtimes top out at 1994-12-01; the earlier `1995` placeholder rested on unconfirmed external corroboration |
| V5 (`Softi-1968`) | pre-1970 date ⇒ negative epoch via raw `@<epoch>` (§4.4, crit-M3) |
| V6 (`2.0-beta`) | full timestamp with non-UTC offset (§4.1/§4.2); quoted embedded comma in a name (§2.4); bare tag (no `v`) = INFO only (§6.3); message with leading `-` (§8.1 exemption); non-ASCII UTF-8 (`é`) |

### 12.2 Valid file (legacy profile, read-only) — conversion fixture

```csv
directory name,author name,author email,date,curator name,curator email,release tag,commit message
1.1,Giuseppe Attardi,attardi@di.unipi.it,10/27/1994 12:26:20,CMM Curation Team,guido.scatena@unipi.it,*,"|Contributors mentioned in Changelog :| - Giuseppe Attardi @attardi."
```

Converts to: date written **byte-exactly** as `1994-10-27T12:26:20+00:00`
(not `…Z`, §4.6; UTC assumed, lossy-noted; 1st token 10 ≤ 12, 2nd token 27 ≥
13 ⇒ unambiguous `MM/DD`, no flag); tag `1.1` (from `*`, computed); message
with `|` → LF (lossy-noted); both real emails PI-1-flagged. The conversion
**exits 0**. A `04/05/1994` variant of this row additionally emits a
`CSV-AMBIGUOUS-US-DATE` **WARN** (§11.3, both candidates noted) and **still
converts, still exits 0** — it does not raise `CsvContractError`.

### 12.3 Invalid rows — each names its rule

Each case is one mutation of the §12.1 file; expected diagnostic in bold.

| # | Mutated content | Violated rule → code |
|---|---|---|
| I1 | Header `version,date,source_url,filename,sha256,authors,notes` (the published exemplar's 7-column header) | §2.1 byte-exact header → **CSV-HEADER** (defect `RED-csv-header`) |
| I2 | File starts with `EF BB BF` then the correct header | §2.2 BOM → **CSV-HEADER** (message names the BOM) |
| I3 | Legacy header (date in position 4) under the canonical profile | §2.1 → **CSV-HEADER** (hint: "legacy Unipisa/guide dialect — use `swhap csv convert --from unipisa`", §11.0.1) |
| I4 | date `1994-03-24T10:00:00` (time, no offset) | §4.2 naive timestamp → **CSV-TZ** |
| I5 | date `08/09/1993` in a canonical-profile row | §4.1 grammar (US form) → **CSV-DATE** |
| I6 | date `1994-02-30` | §4.1 calendar validity → **CSV-DATE** |
| I7 | two rows with release tag `v1.0` | §7 → **CSV-DUP-TAG** |
| I8 | two rows with directory name `1.0` | §7 → **CSV-DUP-DIR** |
| I9 | release tag `v1.0..final` (also covers `candidate/v1.0`, `v1.0.lock`, `v 1.0`) | §6.1–6.2 check-ref-format / reserved ns → **CSV-TAG** |
| I10 | author name `--exec=evil` | §8.1 leading dash in fields 1–7 → **CSV-FIELD** |
| I11 | curator name `Roberto <roberto@dicosmo.org>` | §8.2 `<`/`>` git-ident-meaningful in name → **CSV-FIELD** |
| I12 | author name containing `ESC]0;pwned` (`0x1B` …) | §8.1 control chars → **CSV-FIELD** |
| I13 | directory name `../../etc` (also covers `a/b`, `.hidden`) | §8.2 single component / traversal → **CSV-FIELD** |
| I14 | empty commit message field | §3 / §9.1 → **CSV-FIELD** |
| I15 | author email `not-an-email` (no `@`) | §5.3 → **CSV-FIELD** |
| I16 | row with 7 fields (missing trailing message) | §2.4 arity → **CSV-FIELD** |
| I17 | two rows with release tags `v1.0` and `V1.0` | §7.1 casefold collision → **CSV-DUP-TAG** |
| I18 | two rows with directory names `café` (NFC) and `café` (NFD) | §7.1 NFC collision → **CSV-DUP-DIR** |
| I19 | author name `Peter‮yoR naV` (interior `U+202E` RLO) | §8.1 Cf bidi control → **CSV-FIELD** (names `U+202E`) |
| I20 | release tag `v1.0​` (trailing `U+200B` ZWSP) | §8.1 Cf zero-width → **CSV-FIELD** (names `U+200B`) |
| I21 | date `2026-12-31` validated with `--reference-date 2026-06-05T00:00:00+00:00` | §4.5 future date → **CSV-DATE** (baseline pinned, verdict run-date-independent) |
| I22 | guide-dialect 2025 acquisition (header field 4 `date original`) under canonical profile | §2.1 / §11.0.1 → **CSV-HEADER** (hint names the guide dialect) |
| W1 | row dated `1994-03-24` followed by a row dated `1993-08-09` | §7 monotonicity → **CSV-DATE-ORDER** (WARN — file still valid, build proceeds) |
| W2 (legacy) | legacy row dated `04/05/1994` | §11.3 → **CSV-AMBIGUOUS-US-DATE** (WARN, legacy profile; row converts, exit 0) |
| N1 (legacy) | legacy row dated `27/10/1994` | §11.3 unambiguous `DD/MM` → converts to `1994-10-27`, **no flag** (installed-base date preserved; T10 audit converges) |
| N2 (legacy) | guide-dialect row with **empty** `release tag` | §11.1.1 case 3 → **no canonical row**, conversion-worklist entry (not FAIL) |
| INFO1 | every field RFC-4180-quoted (LibreOffice "quote all") | §2.4 reader rule → **parses; one file-level INFO** (not CSV-FIELD) |
| INFO2 | `swhap csv validate FILE` with no `--reference-date`, file has a `2026-12-31` row | §4.5 → future-date check **skipped, INFO**; no FAIL on that row |

---

## 13. Open points for W1 sign-off

1. **Length-cap values** (§8.1: 255/254/128/16384) — drafter-chosen; cheap to
   change before the freeze, expensive after.
2. **Year-only UTC pin** (§4.1: `YYYY` ⇒ Jan 1 UTC) vs an explicit
   "unknown-within-year" sentinel — Q9 default adopted; Roberto signs.
3. **Curator real-email opt-in mechanics** (§5.2 ledger entry) — wording to be
   mirrored by intake's `questions.yaml`.
4. **`Co-authored-by` placement** (§5.1/§9.3: trailers sanctioned, journal
   canonical) — closes the Q9 "where does co-author data live" sub-question;
   Roberto signs.
5. **BOM ⇒ CSV-HEADER** (§2.2) vs tolerate-and-strip in the canonical
   profile — drafter chose strict-with-actionable-message; flip needs one line.
6. **Cf (Unicode format-character) ban** (§8.1) — drafter extended the §8
   allowlist from Cc-only to Cc+Cf to close the review-UI bidi/zero-width
   spoofing class; the only foreseen cost is Persian/Indic names that use
   ZWNJ/ZWJ in the *display* label, which keep full fidelity in the journal
   ledger and codemeta. Roberto signs the trade-off.
7. **Uniqueness folding basis** (§7.1: `casefold(NFC(·))`) — drafter aligned
   the CSV layer with extraction's `EX-CASE-COLLISION` posture rather than
   leaving byte-equality; confirm the fold (casefold vs simple lower, NFC vs
   NFKC) matches the extraction contract's chosen normal form so the two M1b
   freezes agree exactly.
8. **Future-date reference baseline** (§4.5) — drafter pinned it to the
   recorded curation timestamp in-workbench and to an explicit
   `--reference-date` (else skip+INFO) standalone, with **no wall-clock
   fallback**, to keep `--run-meta-stable` byte-stable and fixtures from
   rotting. Confirm the validator CSV-3 fixtures all pin `--reference-date`.
9. **`CSV-AMBIGUOUS-US-DATE` severity** (§10/§11.3) — drafter reclassified the
   non-existent `FLAG` severity to **WARN** (closed FAIL/WARN/INFO enum) and
   made the legacy converter proceed-and-warn (exit 0), matching
   core-pipeline §5 (`[legacy]` diagnostic identifier, not a raised
   `CsvContractError`). This is what lets the T10 legacy audit run over the
   ~40% day≤12 date corpus; Roberto signs.
10. **Guide legacy dialect** (§11.0.1) — drafter added `date original` header
    recognition (whitespace/case-tolerant) and empty-release-tag handling
    (§11.1.1 case 3 → worklist, no canonical row) so the M1-exit audit can
    read 2025-wave guide-schema acquisitions. Confirm the validator's
    `fixtures/legacy/` mirror includes one guide-dialect acquisition.
