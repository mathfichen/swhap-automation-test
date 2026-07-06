# chassis — GitHub-native intake surface

The surface a **non-expert** drives entirely through the GitHub web UI to curate
an acquisition: upload archives → open a PR → CI validates and builds → a curator
reviews → publish. It is the realization of decisions **D5** (forge intake) and
**D6** (self-host; each institution runs its own instance).

**This directory is a _template_ to be copied out, not run in place.** Its
workflows live under `chassis/.github/` so they do **not** execute in the
`swhap-automation` monorepo. To use it, copy `chassis/` into a new repository
(eventually: mark that repo a GitHub *template repository* and "Use this
template").

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
| `.github/workflows/archive-swh.yml` | Optional, manual, post-publish Save Code Now (automatic ingestion is out of MVP, D7). |
| `.github/ISSUE_TEMPLATE/acquisition-intake.yml` | The non-expert intake form (D5). |
| `metadata/version_history.csv` | **The authoritative manifest** (D2): order, author, date, curator, tag, message. |
| `metadata/extraction-recipe.yaml` | Extraction ONLY: how each raw archive → `source_code/<dir>/`. No authority over history. |
| `metadata/curation-epoch` | The fixed committer/tagger timestamp for bit-reproducibility (D4). |
| `scripts/extract_any.py`, `scripts/build_source_tree.py` | Materialize `source_code/` from `raw_materials/` + the recipe (wrapper-strip, `.emptydir`). |

## The two-manifest split (why there is no `releases.yaml`)

History and extraction are separated on purpose:

- **`version_history.csv`** is the single authoritative history manifest (D2). The
  engine reads it; the validator enforces its grammar. Its `directory name`
  column is the join key.
- **`extraction-recipe.yaml`** carries only the mechanical extraction detail
  (which raw file → which `source_code/<dir>`, with `strip_components`) that the
  CSV has no column for. It never decides order, author, date, or tags.

Keep the two in sync by their shared keys.

## Open seams (tracked as issues)

1. **Who owns extraction.** Today `scripts/` does it (proven in the C-Prolog
   run). Target: move it into the engine as `swhap extract` so one validated code
   path owns wrapper-strip + `.emptydir` and cannot drift from what the validator
   checks.
2. **Engine pinning.** The workflows install the engine from the monorepo
   `engine/` subdir by git ref; pin a tag (or publish to PyPI) before production.
3. **Save Code Now endpoint / credentials** — confirm against SWH API docs;
   prefer routing through the engine's own `publish --save-code-now` adapter.

The workflow files carry `# TODO(confirm)` markers at exactly these points.
