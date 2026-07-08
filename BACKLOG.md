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

## Provisioning at scale (decision D11)

- **P1 — Stand up the intake front door** `intake` `chassis`
  Deploy [`intake/`](intake/) as its own repo (`SWHAP-workbenches/swhap-intake`,
  internal): the reachable "Acquire legacy software" form. Contributor's whole
  contract is one issue — no repo creation, no PR.
- **P2 — Provisioning: curator-click → GitHub App** `chassis` `security`
  One code path with a swappable gate. Start manual (curator "Use this template");
  later a GitHub App using the generate-from-template API with a **short-lived
  minted token, Actions-only, no webhook server** (App scales per-org for D6).
  Derive the App's exact token scopes from the instrumented C-Prolog #2 run.
- **P3 — Per-acquisition repos are org-owned** `chassis`
  Provision into `SWHAP-workbenches` (not contributor personal accounts —
  outsiders can't create in the org anyway); apply branch protection post-create
  (templates carry none).

## Chassis engineering seams

- **S1 — Move extraction into the engine (`swhap extract`)** `engine` `chassis`
  Today `chassis/scripts/` owns `raw_materials → source_code` (wrapper-strip,
  `.emptydir`). A second extractor can drift from what the validator checks;
  one validated code path should own it.
- **S2 — Thin caller + versioned engine (C5)** `chassis` `ci`
  Move all logic behind a **versioned reusable workflow / packaged engine** pinned
  to a tag, so 100s of workbenches update by version bump (a copied-in workflow
  never auto-updates). Workflows currently install from `engine/` by `@main`.
- **S3 — Confirm the Save Code Now endpoint / credentials** `chassis`
  Verify the SWH API path; prefer routing through the engine's
  `publish --save-code-now` adapter over a raw curl.
- **S4 — Split untrusted build from the token (C1/C2)** `chassis` `security`
  build-and-publish must become two jobs: a **secrets-free** build (ephemeral
  runner, read-only token) and a **curator-Environment-gated** publish that never
  checks out or runs archive content. The token must never share a job with
  untrusted extraction.
- **S5 — Candidate re-validation mechanics** `chassis` `engine`
  Resolve how `swhap-validate` validates a candidate ref (checkout vs a new flag).
- **S6 — GitLab / platform abstraction (C6, D6)** `engine`
  Keep the engine a plain CLI/container behind an interface; Actions, the
  generate API, Environments, and typed issue-forms are GitHub-only and won't
  port to a self-hosted GitLab instance.

## Quality gap surfaced by the pilot (engine)

- **Q1 — Curation-noise + PII lint (advisory)** `engine` `enhancement` `security`
  Neither the template nor the engine flags in-tree build artifacts (`.o`, `.out`,
  `*.save`), macOS AppleDouble files (`._*`), or foreign bundled files. Tree-
  fidelity *passes* faithful junk. Add a curator-approvable heuristic lint —
  **including a PII content-scan** (C-Prolog #2 shipped a stranger's SSN in
  `hw4.pl`; PI-1 only lints the CSV today, not file contents).
- **W1 — BP-2 allowlist must permit `codemeta.json` at root** `engine` `bug`
  Architecture B5 promotes `codemeta.json` to the default-branch root (SWH indexes
  only there), but `_MAIN_ALLOW` rejects it → BP-2 FAIL (found on C-Prolog #2). Add
  `codemeta.json` to the allowlist so a published, indexable workbench validates.
- **W2 — Workbench self-CI vs branch-purity** `engine` `chassis`
  `.github/` is not in `_MAIN_ALLOW`, so a provisioned workbench can't carry its
  own CI workflows without failing BP-2. Decide how a workbench runs its own
  validation (reusable-workflow caller allowed on main? separate CI ref?).
- **W3 — Curation-exclusion manifest** `engine`
  Record the curator's noise/PII exclusions so the curated tree is reproducible
  from raw + extraction-recipe + exclusions (today the exclusions are hand-applied
  and only documented in the journal).

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
