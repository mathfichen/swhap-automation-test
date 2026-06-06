# swhap-toolkit — build status

Milestone tracking against `swhap-automation/analysis/implementation-plan.md`.

## M1 — COMPLETE (2026-06-06)

The whole first milestone is closed with no open gaps. From a **clean clone**:
**331 tests pass, 0 skipped**, no scratch-dir or network dependency.

- **M1c (branch-layout decision + full regeneration)**: Wild_LIFE rebuilt under
  both layouts; Roberto ruled **Model P** (decision D1, 4–0 on the evidence) and
  **append→ rebuild-and-replace** iteration policy (decision D3, revised — see
  below). The corrected Model-P workbench is reproducible from committed inputs
  (`pilot/wildlife/regen/regen.py`) and validates green; the corrupted published
  exemplar is formally banned (`pilot/wildlife/rag-corpus/BANNED.md`).
- **Backward-compatibility audit** (reading old-format workbenches without false
  alarms): two false-failure bugs fixed; now CI-reproducible from synthetic
  license-clean fixtures (`fixtures/legacy/`, `test_legacy_audit_e2e.py`) — both
  zero-false-failure and genuine-defect detection asserted.
- **D3 revised** to *rebuild-and-replace* (supersession with a permanent SWH
  pointer, not invalidation) per Roberto's correction; specs amended, enforcement
  lands with the M2 publish step.

## M1b — DONE (2026-06-06)

The pipeline can now *rebuild* curated history, not just check it. In `main`;
the full suite is **309 tests, all passing, 0 skips** (168 `swhap-core` +
106 validator + 35 fixtures, all collected by the root `pytest` that CI runs);
single-parser (D2) and bit-reproducibility (D4) adversarially proven by
execution.

| Delivered | What it is |
|---|---|
| `swhap_core.vhcsv` | The canonical `version_history.csv` parser/validator/writer (frozen format) + a read-only reader for the legacy Pisa/DT2SG dialect. The **sole** CSV grammar implementation; both the validator and the builder delegate to it. |
| `swhap_core.history` (`build --plan/--apply`) | Reconstructs Git history from release trees + the CSV. Writes only to safe candidate refs. **Bit-reproducible** (decision D4): identical inputs → identical commit AND tag hashes across runs/machines (committer+tagger dates from a fixed curation timestamp; object bytes written directly, no wall-clock). Both branch layouts (P/G) behind one model. |
| Machine-appended journal | `metadata/journal.jsonl` per the frozen journal format (wall-clock timestamps deliberately outside the D4 hash guarantee, per journal-schema §13). |

**Gate evidence:** build-twice-into-two-dirs → byte-identical commit+tag SHA-1s;
perturb one byte → hash changes (determinism real, not a constant); a malformed
release tag / argv-shaped field is rejected at ingestion (exit 12, zero refs
written) — not late inside Git. No CSV-derived value reaches a shell.

## M1a — DONE (2026-06-06)

The validator-first core is in `main`; the tree-fidelity gate is adversarially
proven on the **real** published Wild_LIFE exemplar at the documented
`check_swhap.sh` entrypoint. 206 tests pass; CI on the toolkit itself is live.

| Workstream | Delivered |
|---|---|
| W1 contracts | `specs/csv-contract.md`, `validator-report.md`+schema, `journal-schema.md`+schema — FROZEN, signed (`specs/SIGNOFF-W1.md`) |
| fixtures | negative-archive corpus (1 per crit-M6 class) + Wild_LIFE tarball manifests + quarantined 1.02 census |
| swhap-core | `swhap inspect --json` (read-only rejection-rule evaluation) |
| validator | `check_swhap.sh` + `swhap_validate`: TF-1..5, BP-*, CSV-1..7, CM-1..4, SZ-1..5, PI-1 (WARN), JC-1a |

**Gate evidence (real exemplar, at the entrypoint):** 0.90 clean; 0.91 TF-1 +19
leaked / TF-3 0-of-19 deletions; 1.0 TF-1 +1145 leaked / TF-2 stale LICENSE;
BP-3 ×3 records the missing-annotated-tag defect (the published exemplar has a
SourceCode branch but no tags). TF data side = real published commit trees;
assert side = tarball-derived manifests (independent provenance, non-circular).

## Open items for Roberto (carried from W1 sign-off + M1a)

- **Q9 / 1.02 release date** — tarball mtimes support **year-only 1994** (max
  1994-12-01); the csv-contract example uses `1995`, which rests on external
  (djdarland/WildLIFE) corroboration the tarball cannot confirm. Pin the value
  at exemplar T5. See `fixtures/wildlife/manifests/1.02-date-evidence.md`.
- **Offline (your earlier list):** name the ≥2 C5 usability testers; fix the
  legacy-audit target set (default: Unipisa/CMM-Workbench + mathfichen/
  chainage_de_contour) and the toolkit's institutional namespace (D6); start
  the DEC license outreach for Wild_LIFE republication; rotate the
  `stories.k2.services` key printed in `SWHAP@Paris.md`.

## Next — M2 (non-expert intake + publish)

The second milestone: the forge-issue intake surface for non-expert holders
(decision D5), the curator workflow + legal go/no-go gate, the usability test
(criterion C5), and the **publish step** — which is where the revised D3
rebuild-and-replace flow (archive prior snapshot to SWH → record its SWHID as
lineage → replace SourceCode) and the retargeted divergence check (DV-1) get
implemented.

Needs Roberto's offline-brief items (`../swhap-automation/YOUR-ACTION-ITEMS.pdf`):
the ≥2 usability testers (C5), the operator/namespace decision (D6 — where the
toolkit and acquisitions live), and the DEC licence outreach (gates Wild_LIFE
re-publication only).

## Known minor debt

- Bundle exposes the SourceCode head as `pin-sourcecode` (renamed to
  `SourceCode` at checkout by the fixture builder) — documented, not yet a
  literal `SourceCode` ref in the bundle.
- CM-3 JSON-LD contexts are compact approximations; refresh from swh-indexer
  source before relying on exact term IRIs (D9).
