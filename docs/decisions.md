# Binding decisions

These are settled. They override any older spec where they conflict. Each has an
ID used throughout the code and docs (see [`glossary.md`](glossary.md) for the
shorthand). Reopen one only with a recorded new decision.

| # | Decision | Ruling |
|---|----------|--------|
| **D1** | Branch model | **Model P** — orphan `SourceCode` for source, `main` for workbench/metadata only (one commit + annotated tag per release). Ruled on dual-regeneration evidence, 4–0. Model G demoted to a read-only legacy/audit profile. |
| **D2** | Version-manifest format | The canonical `version_history.csv` header is authoritative going forward; the deterministic pipeline supersedes DT2SG/`dt2sg-gen.py`. The legacy Unipisa dialect is supported **read-only**, never written. |
| **D3** | Iteration / SWHID stability | **Rebuild-and-replace as a first-class operation**, made safe by SWH preservation + bit-reproducibility (not destructive invalidation). Archive prior snapshot → record its SWHID as lineage → rebuild ordered history → replace. Covers the chronological-insertion case. **Implemented** (`swhap publish --supersede`). |
| **D4** | Committer/tagger dates | **Bit-reproducible.** Committer + tagger date = a fixed curation timestamp recorded in metadata; identical inputs → identical commit/tag hashes. The validator rebuilds into a scratch ref and compares hashes. |
| **D5** | Non-expert intake surface | **Forge-issue / web-UI intake** with attachments (GitHub/GitLab); no hosted upload service; oversized archives routed via URL. A non-expert needs a forge account but no install, CLI, or git. |
| **D6** | Operations / ownership | **Self-host model.** Each adopting institution runs its own instance; Software Heritage is instance zero. Deliverables emphasize deployment/setup docs over a central hosted service. |
| **D7** | MVP scope | Core first: deterministic generator + validator (M1), non-expert guided intake (M2), a second pilot. **Deferred:** Mode 3 (web source discovery) → v2. **Excluded from MVP:** OCR/scanned sources, physical media, emulation, compilation, automatic final SWH ingestion. **Stretch:** GitLab parity, RAG package, four-guide doc set. |
| **D8** | Wild_LIFE exemplar | **Regenerate it through the pipeline** (tree-faithful, canonical CSV, fixed `@context`, PR #1's 1.02 tarball as a fourth release) — this was the M1 exit gate. The DEC-license determination proceeds in parallel and gates only republication. |
| **D9** | CodeMeta version policy | The validator's accepted-`@context` set is **vendored tracked data refreshed from swh-indexer source, never a hardcoded constant**. Today swh-indexer accepts canonical CodeMeta 2.0 (+ alternates) and the w3id 3.0 context — **not 4.0 yet**; do not emit a context until the vendored set includes it. `maintainer`/`funding` **are** valid CodeMeta terms. |
| **D10** | Wild_LIFE 1.02 release date | **Year-only 1994** (precision = year, provenance = inferred). Tar-member mtimes for real source content top out at 1994-12-01; the earlier `1995` placeholder rested on unconfirmed corroboration. |
| **D11** | Provisioning model at scale | **Provisioned, not self-service.** The contributor's entire contract is filling **one intake form** (an issue) — they never create a repo, never open a pull request. A per-acquisition workbench repo is provisioned **for** them into a dedicated org (`swhap-workbenches`, SWH's instance zero; each institution self-hosts its own under D6), by a **swappable gate: curator-click now → a GitHub App later** (short-lived minted token, Actions-only, **no webhook server**). The contributor experience is frozen as the form so curator→bot can swap without re-teaching anyone. Self-service ("Use this template") is valid **only** for an institution's own org members. Ruled 2026-07-06 on a four-advisor panel (self-service champion, provisioned champion, GitHub platform red-team, adoption/UX). |

## Open decision points (carried, not yet ruled)

- Date/identity conventions in the manifest beyond the pinned Wild_LIFE dates
  (Q9), the depth of the legal go/no-go gate, provenance source-of-truth /
  journal automation, and guide stewardship remain explicit decision points for
  the detailed plan.
- Two chassis-integration seams are tracked as issues: **who owns extraction**
  (`raw_materials → source_code`) and **where the fixed curation-epoch is
  stored** so re-runs stay bit-reproducible.

## Standing human-only action items

Some inputs can't be derived from code or docs — see the project's action-item
brief. In scope for this repo: naming ≥2 non-expert usability testers (measures
criterion **C5**), the DEC-license outreach for Wild_LIFE republication, and the
legacy-audit target pair for backward-compatibility testing.
