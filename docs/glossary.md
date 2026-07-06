# Glossary

Plain-language meaning of the shorthand used across this repo.

## Concepts

| Term | Meaning |
|---|---|
| **SWHAP** | Software Heritage Acquisition Process — the method for rescuing and curating legacy source code. |
| **Workbench** | The curated Git repository this tooling produces: raw materials + metadata + reconstructed history. |
| **Model P / Model G** | Branch layouts. **P** (chosen, D1): source on an orphan `SourceCode` branch, metadata on `main`. **G** (legacy): source on the default branch. |
| **Provenance tags** | Every metadata item is marked **observed / computed / inferred / user-provided / curator-approved**. |
| **SWHID** | Software Heritage intrinsic identifier (`swh:1:…`) — permanent, content-derived. |
| **Curation timestamp / epoch** | A fixed committer/tagger date (D4) that makes rebuilds bit-identical. |

## Web-UI & provisioning terms

For anyone meeting these in the browser, not the code.

| Term | Plain meaning |
|---|---|
| **Front door / intake repo** | The one place a contributor goes to hand in software: a standing repo whose only job is the "Acquire legacy software" form. |
| **Provisioning** | A curator (later a bot) creating the per-acquisition workbench repo *for* the contributor, so they never have to. |
| **Workbench** | The per-acquisition repo the provisioning step creates from the template. |
| **Pull request (PR)** | GitHub's "propose these changes" mechanism. Used *internally* by curators/CI — a contributor never opens one. |
| **CI / GitHub Actions** | Automatic checks GitHub runs on a submission (here: extract, build, validate). |
| **Template repository / "Use this template"** | A repo marked so others can create a fresh copy of it. Used by operators, not contributors. |
| **GitHub App / minted token** | A least-privilege identity that provisions repos with a short-lived token (no standing password, no server). |

## Decisions (D-codes)

`D1`–`D11` are the binding decisions — see [`decisions.md`](decisions.md). Quick
index: **D1** Model P · **D2** canonical CSV · **D3** rebuild-and-replace · **D4**
bit-reproducibility · **D5** forge intake · **D6** self-host · **D7** MVP scope ·
**D8** Wild_LIFE regeneration · **D9** CodeMeta context policy · **D10** 1.02 date ·
**D11** provisioned (not self-service) intake.

## Milestones

| Code | Meaning |
|---|---|
| **M1 / M2 / …** | Project milestones — see [`roadmap.md`](roadmap.md). |
| **M1a / M1b / M1c** | M1 sub-steps: validator · builder · branch-layout decision + regeneration. |
| **C5** | The headline success criterion: a real non-expert produces a valid package unaided. |

## Validator check families

The validator emits findings tagged by family + number (e.g. `BP-2`, `TF-1`).

| Family | Checks | Example |
|---|---|---|
| **TF** | Tree fidelity — does the rebuilt tree match the source archive (nothing leaked, nothing missing)? | `TF-1` extra/leaked files |
| **BP** | Branch purity — does each branch hold only what it should? | `BP-2` metadata leaked onto `SourceCode`; `BP-3` a release has no annotated tag |
| **CSV** | Manifest grammar — canonical header, ISO dates, well-formed rows. | `CSV-1` `version_history.csv` missing |
| **CM** | CodeMeta validity — accepted `@context`, indexed fields. | `CM-4` a field SWH will silently drop |
| **SZ** | Size / count budgets on archives and trees. | `SZ-*` oversized member |
| **PI** | Personal-information lint — stray private emails. | `PI-1` (warning) |
| **JC** | Journal coverage — every commit/tag is recorded in `journal.jsonl`. | `JC-1a` uncovered commit |
| **DV** | Divergence — refuses an un-journaled clobber of a published history (checked at publish). | `DV-1` |

## Prior art

| Term | Meaning |
|---|---|
| **DT2SG** | The earlier Pisa-era tool ("Directory Tree to Source Git") whose workbench format we must still be able to *read* (D2, legacy read-only). |
| **SWHAP-PROMPT** | The curator-agent prompt (AI Layer-2 prior art). |
