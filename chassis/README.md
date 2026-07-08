# chassis — GitHub-native intake surface

The **per-acquisition workbench template**. A curator provisions one copy of it
per acquisition (decision **D11**); inside that copy, uploaded archives are
extracted, built into a Model-P history by the engine, validated, and published.
The **contributor never touches this** — they only file the intake form (see
[`../intake`](../intake)). This realizes **D5** (forge intake) and **D6**
(self-host).

**This directory is a _template_ to be copied out, not run in place.** Its
workflows live under `chassis/.github/` so they do **not** execute in the
`swhap-automation` monorepo. It is provisioned into a new per-acquisition repo
(via "Use this template" / the generate API — by a curator or bot, per D11).

> **The workflows here are DRAFT.** They show the intended shape but are not
> production-safe: the build-and-publish flow still co-locates untrusted
> extraction with the SWH token and must be split per security constraints
> **C1/C2** (see [`../docs/architecture.md`](../docs/architecture.md)), and all
> logic should move behind a versioned reusable workflow / packaged engine
> (**C5**). The production shape is derived from the instrumented C-Prolog #2 run.

## How it differs from the first hand-rolled template

The early template produced a plausible-looking workbench that a compliance check
rejects (no release tags, metadata leaked onto the source branch, non-reproducible
dates, a bespoke manifest). See [`../pilots/c-prolog`](../pilots/c-prolog) for the
validator report on a real run. This chassis keeps the good shell (web-UI upload,
PR flow, wide-format extraction) and **delegates the history reconstruction to the
verified engine** so those defects cannot recur.

## The pieces

| Path | Role |
|---|---|
| `.github/workflows/pr-validate.yml` | On every PR: inspect uploads → extract → engine dry-run build (`--plan`, no refs) → **`check_swhap.sh` compliance gate (red fails)** → upload plan + report. |
| `.github/workflows/build-and-publish.yml` | Maintainer dispatch: engine `build --apply` to a candidate ref → re-validate → `swhap publish` (DV-1- and supersede-safe). **No force-push.** |
| `.github/workflows/self-validate.yml` | Compliance heartbeat: re-runs the strict-P gate on any push (read-only, secrets-free) so a **published** workbench proves it stays compliant, not only at acquisition time. |
| `.github/workflows/archive-swh.yml` | Optional, manual, post-publish Save Code Now (automatic ingestion is out of MVP, D7). |
| `metadata/version_history.csv` | **The authoritative manifest** (D2): order, author, date, curator, tag, message. |
| `metadata/extraction-recipe.yaml` | Extraction ONLY: how each raw archive → `source_code/<dir>/`. No authority over history. |
| `metadata/curation-epoch` | The fixed committer/tagger timestamp for bit-reproducibility (D4). |
| `scripts/extract_any.py`, `scripts/build_source_tree.py` | Materialize `source_code/` from `raw_materials/` + the recipe (wrapper-strip, `.emptydir`). |

## Why the workbench may carry its own `.github/` (W2)

A provisioned workbench needs to run its own compliance check, so it carries
`.github/workflows/`. Branch purity (BP-2) permits `.github/` **on the workbench
branch** — it is workbench infrastructure, like `metadata/` and `scripts/`. It is
**forbidden on `SourceCode`**, which holds reconstructed source alone; the
validator now FAILs BP-2 if `.github/` leaks there. The workflows should become
thin callers of a versioned reusable workflow (C5 / BACKLOG S2) so hundreds of
workbenches update by a version bump rather than a per-repo edit.

## The two-manifest split (why there is no `releases.yaml`)

History and extraction are separated on purpose:

- **`version_history.csv`** is the single authoritative history manifest (D2). The
  engine reads it; the validator enforces its grammar. Its `directory name`
  column is the join key.
- **`extraction-recipe.yaml`** carries only the mechanical extraction detail
  (which raw file → which `source_code/<dir>`, with `strip_components`) that the
  CSV has no column for. It never decides order, author, date, or tags.

Keep the two in sync by their shared keys.

## Open seams (tracked in [`../BACKLOG.md`](../BACKLOG.md))

1. **Split untrusted build from the token (C1/C2).** The build-and-publish
   workflow must become two jobs: a secrets-free build (ephemeral runner) and a
   curator-Environment-gated publish that never runs archive content.
2. **Thin caller + versioned engine (C5).** Move logic behind a reusable workflow
   / packaged engine pinned to a tag, so hundreds of workbenches update by version
   bump instead of a per-repo edit.
3. **Who owns extraction.** Today `scripts/` does it; target is `swhap extract`
   in the engine so one validated path owns wrapper-strip + `.emptydir`.
4. **Save Code Now endpoint / credentials** — confirm against SWH API docs;
   prefer the engine's `publish --save-code-now` adapter.
5. **Candidate re-validation mechanics** — resolve how `swhap-validate` checks a
   candidate ref (checkout vs a new flag).

The workflow files carry a **DRAFT** banner; the production shape is derived from
the instrumented C-Prolog #2 run.
