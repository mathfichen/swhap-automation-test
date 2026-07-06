# Backlog

The shared work list. Each item is written to become a GitHub issue once the repo
is pushed (labels suggested). Grouped by where it comes from.

## From the C-Prolog pilot (chassis correctness)

These are the defects the validator found on the first hand-rolled template
([pilots/c-prolog](pilots/c-prolog)). The engine-wired [`chassis/`](chassis)
closes them by construction; each issue is "confirm the chassis clears it + add a
regression".

- **B1 — Branch purity: workbench must not leak onto `SourceCode`** `chassis` `bug`
  The old template kept `.github/`, `scripts/`, `metadata/`, `raw_materials/` on
  the orphan branch (BP-2 ×5). Engine `build` produces clean Model-P separation;
  verify on C-Prolog and assert BP-2 = 0.
- **B2 — Every release gets one annotated tag** `chassis` `bug`
  Template produced zero tags (BP-3, masked only because the CSV was missing).
  Engine `build` tags each release; add a test that the tag count = release count.
- **B3 — Bit-reproducible dates, no noon-UTC fabrication** `chassis` `bug`
  Template defaulted year-only dates to noon UTC and set committer=author date.
  Engine uses the fixed `curation-epoch` (D4); verify identical hashes on rebuild.
- **B4 — Journal coverage (JC-1a)** `chassis`
  Template wrote free-text `journal.md`; engine writes `journal.jsonl` covering
  every commit/tag. Confirm JC-1a passes.
- **B5 — Promote `codemeta.json` to the default-branch root** `chassis` `metadata`
  SWH indexes codemeta only at the repo root of the default branch; the template
  left it in `metadata/` and it would never be indexed. Handle in the publish step.
- **B6 — Single manifest: drop `releases.yaml`** `chassis`
  Adopt `version_history.csv` (D2) as the sole history authority + the
  extraction-only `extraction-recipe.yaml`. (Seeded; ensure no `releases.yaml`
  path survives.)

## Chassis engineering seams

- **S1 — Move extraction into the engine (`swhap extract`)** `engine` `chassis`
  Today `chassis/scripts/` owns `raw_materials → source_code` (wrapper-strip,
  `.emptydir`). A second extractor can drift from what the validator checks;
  one validated code path should own it.
- **S2 — Pin the engine install** `chassis` `ci`
  Workflows install the engine from the monorepo `engine/` subdir by git ref.
  Pin a tag (or publish `swhap-core`/`swhap-validate` to PyPI) before production.
- **S3 — Confirm the Save Code Now endpoint / credentials** `chassis`
  Verify the SWH API path; prefer routing through the engine's
  `publish --save-code-now` adapter over a raw curl.

## Quality gap surfaced by the pilot (engine)

- **Q1 — Curation-noise lint (advisory)** `engine` `enhancement`
  Neither the template nor the engine flags in-tree build artifacts (`.o`, `.out`,
  `*.save`), macOS AppleDouble files (`._*`), or foreign bundled files (C-Prolog
  shipped `hw1`, `hw4.pl` — someone's homework). Tree-fidelity *passes* faithful
  junk. Add a curator-approvable heuristic lint so non-experts are warned before
  publishing.

## Milestone M2 / project (from the roadmap)

- **M1 — Name ≥2 non-expert usability testers (criterion C5)** `project`
  Recruiting is on the M2 critical path; needed to test the intake honestly.
- **M2 — Legacy-audit target pair** `project` `engine`
  Confirm two real published acquisitions to prove backward-compat reading
  (proposed: `Unipisa/CMM-Workbench` + `mathfichen/chainage_de_contour`).
- **M3 — Curator workflow + legal go/no-go gate** `chassis` `enhancement`
  The human-review + license-approval step before publish.

> Not tracked as repo issues: the Wild_LIFE DEC-license outreach and the
> `stories.k2.services` key rotation are handled outside this repo.
