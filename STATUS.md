# swhap-toolkit — build status

Milestone tracking against `swhap-automation/analysis/implementation-plan.md`.

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

## Next — M1b (per the plan's decision calendar)

CSV/Q9 envelope freeze → unblocks core T4 (`swhap_core.vhcsv`, the real CSV
module the validator currently shims) and the history builder (`build --plan/
--apply`, bit-reproducible per D4). Then M1c = the D1 branch-model + D3 ruling
on the dual-model Wild_LIFE regeneration.

## Known minor debt

- Bundle exposes the SourceCode head as `pin-sourcecode` (renamed to
  `SourceCode` at checkout by the fixture builder) — documented, not yet a
  literal `SourceCode` ref in the bundle.
- CM-3 JSON-LD contexts are compact approximations; refresh from swh-indexer
  source before relying on exact term IRIs (D9).
