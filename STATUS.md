# swhap-toolkit — build status

Milestone tracking against `swhap-automation/analysis/implementation-plan.md`.

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

## Next — M1c (needs Roberto's input)

M1c is the **first milestone's exit gate**: regenerate the corrected Wild_LIFE
workbench end-to-end with the new tooling, and decide the branch layout on the
evidence. It needs two rulings from Roberto (see `../swhap-automation/YOUR-ACTION-ITEMS.pdf`):

- **Branch-layout decision (D1):** the regeneration is built under BOTH layouts
  (purity model P / source-on-default-branch model G); a 7-point evidence memo
  is prepared, Roberto rules, the loser is demoted to a read-only legacy profile.
  Pre-declared tie-breaker: model P.
- **The 1.02 release date (question Q9):** archive evidence supports year-only
  1994; Roberto confirms or supplies a precise date.

Engineering still buildable before those rulings: wire `build` into the
extraction front-end (consume real extracted trees, `.emptydir` preservation
end-to-end) and add the remaining validator checks the regeneration will need
(RB-1 rebuild-reproducibility check at the entrypoint, JC journal coverage,
the legacy-audit profile run against the two pinned acquisitions once Roberto
fixes the target set).

## Known minor debt

- Bundle exposes the SourceCode head as `pin-sourcecode` (renamed to
  `SourceCode` at checkout by the fixture builder) — documented, not yet a
  literal `SourceCode` ref in the bundle.
- CM-3 JSON-LD contexts are compact approximations; refresh from swh-indexer
  source before relying on exact term IRIs (D9).
