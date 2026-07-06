# Architecture & compliance invariants

This is the shared mental model. If a design or code change would violate one of
the invariants below, it is wrong — raise it as a decision instead.

## Three layers, strictly separated

```
   raw archives ──► [1] deterministic pipeline ──► curated workbench ──► SWH
                          ▲            │
                          │            ▼
                    [3] human      [2] AI assistant
                     curator  ◄──   (proposes only)
```

1. **Deterministic pipeline** (`engine/`, no AI). Reproducible archive
   ingestion, checksum/size computation, wrapper stripping, extraction,
   `.emptydir` preservation, Git-history reconstruction, tagging, and
   validation. The **only** path by which anything reaches a curated Git ref.
2. **AI assistant** — infers metadata and drafts documents; **proposes** patches,
   never writes to protected refs, never touches secrets.
3. **Human curator** — approves every judgement call; provenance is tracked so a
   reviewer can see what was observed vs inferred vs approved.

**Design invariant:** *no path exists by which AI output or user input reaches a
curated ref except through the validated deterministic apply step.*

## Branch model — Model P (decision D1)

The curated result uses **Model P** (strict separation):

- **`main`** holds only the workbench and metadata (`metadata/`, `raw_materials/`,
  README, scripts) — never reconstructed source.
- an orphan **`SourceCode`** branch holds only the reconstructed source tree at
  its root — never metadata or infra — with **one commit + one annotated tag per
  release**.

Model G (source on the default branch, as some legacy guide practice) is kept
only as a read-only legacy/audit profile.

## Key compliance invariants

- **`metadata/version_history.csv` is authoritative** for the curated history.
  Canonical header (a deliberate, dated break from the legacy DT2SG dialect —
  decision D2):
  `directory name,date,author name,author email,curator name,curator email,release tag,commit message`
  The legacy Unipisa dialect (US dates, `*` tags, `\|` separators) is supported
  **read-only**, never written.
- **Bit-reproducibility (decision D4).** Author/date come from the CSV (release
  date = Git author date); committer = curator; committer/tagger dates = a fixed
  *curation timestamp* so rebuilding twice yields **identical commit and tag
  hashes**. No wall-clock, ever, in the object bytes.
- **Wrapper stripping.** Artificial top-level directories inside tarballs (e.g.
  `Life1.0/`, `c-prolog/`) must not appear at the root of curated commits.
- **Empty directories** are preserved with `.emptydir` marker files; original
  tarballs stay byte-identical in `raw_materials/`.
- **`codemeta.json` `@context` must be in the swh-indexer accepted set**
  (decision D9) — the indexer silently drops the *entire file* on any other URL.
  The accepted set is vendored data refreshed from swh-indexer source, never a
  hardcoded constant. Validate via JSON-LD expansion, not JSON syntax. SWH reads
  `codemeta.json` only at the **repo root of the default branch**, so publishing
  must promote it there.
- **History rewrites are supersession, not destruction (revised decision D3).**
  When a release surfaces that belongs mid-history, the current SourceCode
  snapshot is archived to SWH (its `swh:1:snp:…` recorded as durable lineage),
  the full ordered history is rebuilt bit-reproducibly, and the branch is
  replaced. A divergence check (DV-1) refuses an un-journaled clobber. SWHIDs are
  intrinsic and permanent — a rebuild produces a *new* history alongside the
  archived old one, never invalidating it.
- **Untrusted input.** Archives are arbitrary old uploads: sandbox extraction,
  guard against path traversal, preserve (don't follow) symlinks, never execute
  extracted code by default.

## Validation is the gate

The validator (`engine/tools/validator`, entrypoint `check_swhap.sh`) runs a
battery of checks — tree-fidelity (**TF**), branch-purity (**BP**), CSV grammar
(**CSV**), CodeMeta (**CM**), size (**SZ**), personal-info lint (**PI**), journal
coverage (**JC**), and divergence (**DV**). A red report blocks. It was built
*before* the generator on purpose: any generator mistake gets caught, not
rubber-stamped. See [`glossary.md`](glossary.md) for what each family checks.
