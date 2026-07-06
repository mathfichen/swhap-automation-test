# swhap-toolkit

Tooling for the AI-assisted **SWHAP** (Software Heritage Acquisition Process)
automation pipeline: a deterministic workbench generator (`swhap-core`), a
compliance validator (`swhap-validate` / `check_swhap.sh`), forge intake, and a
proposal-only AI assistant layer.

**Status: M1a (fixtures + scaffolding).** The normative plan lives in the
`swhap-automation` workspace: `analysis/implementation-plan.md` binds seven
workstream plans (`analysis/impl/*.md`); decisions D1–D9 in
`analysis/decisions.md` are binding. Design invariant: *no path exists by which
AI output or user input reaches a curated ref except through the validated
Layer-1 apply step.*

## Layout

```
fixtures/wildlife/   Pinned Wild_LIFE ground truth (acquire.sh: git bundle of
                     the published exemplar @1571ce5 + PR #1 head @5e05003,
                     four release tarballs, frozen sha256 manifest).
                     NOTE: the published exemplar is fixture material for what
                     the validator must CATCH (corrupted v0.91/v1.0 tag trees,
                     critique C4) — not a correct reference.
.github/workflows/   CI on the toolkit itself (crit-M13: starts at M1a).
```

Packages (`swhap-core`, `swhap-validate`) land next, per
`analysis/impl/core-pipeline.md` and `analysis/impl/validator.md`.

## Pending decisions

- **Hosting namespace**: local repo until Roberto fixes the institutional home
  (decision D6: self-host model; SWH is instance #0 — a SoftwareHeritage org
  repo is the natural target, with CI on itself as an acceptance criterion).
- **License**: Roberto's call (SWH tooling convention suggests GPL-3.0-or-later).
