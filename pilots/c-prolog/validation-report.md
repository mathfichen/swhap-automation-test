# Validation report: `mathfichen/C-Prolog` against the toolkit

**Subject:** Mathilde's live GitHub-template run on C-Prolog (Fernando Pereira,
Edinburgh, 1984) · **Run date:** 2026-07-06 · **For:** Roberto + Mathilde

**Tooling:** `swhap-validate` v0.1.0 (swhap-toolkit @ `1399fb2`), profile
`strict-P` (Model P — the ruled branch layout, D1), gate `build`.
**Repo state:** `main` @ `20b2f4ad`, `SourceCode` @ `f5eb2c1f`.
Raw JSON alongside this file: `report-strictP.json`.

## Result: 7 FAIL · 1 WARN · 12 PASS · exit 1 (would block a merge)

The repo was produced by driving the `swhap-gh-template` **unmodified** (her
`make_synthetic_history.py` is byte-identical to the template). So this is the
template's own output, judged by our engine — a real, non-hypothetical red test.

## FAIL findings

| Check | What it means (plain) | Where | Root cause |
|---|---|---|---|
| **BP-2** | `.github` is on the pure workbench branch | `main` | template ships workflows on `main`; Model P forbids infra there |
| **BP-2** | `source_code/` is on the pure workbench branch | `main` | generated trees committed to `main` |
| **BP-2** | `.swhap/` is on the pure workbench branch | `main` | Mathilde's added template dir, on the wrong branch |
| **BP-2** | `metadata/` leaked onto `SourceCode` | `SourceCode` | the script's `keep` set preserves `metadata` on the orphan branch |
| **BP-2** | `raw_materials/` leaked onto `SourceCode` | `SourceCode` | same `keep` set — the raw tarball rides along on the source branch |
| **CSV-1** | canonical `version_history.csv` is missing | `main` | she removed it ("remove history.csv"), consolidating on `releases.yaml` |
| **JC-1a** | the journal records 0 of 1 reconstructed commits | curated refs | template writes free-text `journal.md`, not the machine `journal.jsonl` the toolkit requires |

**BP** = branch-purity (each branch holds only what it should); **CSV-1** =
canonical manifest present; **JC-1a** = every reconstructed commit/tag is
recorded in the journal.

The five **BP-2** failures are one systemic bug, not five mistakes: the template
keeps the *entire workbench* (`.github`, `scripts`, `metadata`, `raw_materials`)
on the orphan `SourceCode` branch and also commits generated `source_code/` to
`main`. Model P wants `main` = workbench/metadata only, `SourceCode` = source
only. The template produces the opposite of both.

## WARN finding

- **CM-4:** `codemeta.json` field `softwareRequirements` is silently dropped by
  Software Heritage — it won't appear in the archived metadata. (Advisory.)

Note the *good* news CM did **not** flag: the `@context` is the canonical
`codemeta-2.0` URL — the AI draft got D9 right, so the file is not silently
discarded wholesale. The problem is elsewhere (below).

## What was NOT checked — and why it matters

Three things a naïve reading of "12 PASS" would get wrong:

1. **BP-3 (missing annotated tag) is MASKED, not passed.** The `SourceCode`
   branch has **zero tags** — the exact Wild_LIFE corruption. BP-3 didn't fire
   because it enumerates expected releases *from the CSV*, and the CSV is missing
   (CSV-1). With `release_tags` empty, BP-3 has nothing to assert and passes
   vacuously. **Fix CSV-1 → BP-3 immediately fails on the zero-tags condition.**
   The two defects are chained: the missing manifest hides the missing tags.
2. **Tree-fidelity (TF-1..5) was skipped** — it needs a tree-manifest oracle
   derived from the raw archive, which is out of scope for this invocation.
   So "does the rebuilt tree faithfully match the tarball" is *not yet* asserted
   here (it can be, by feeding manifests; a follow-up).
3. **`codemeta.json` sits in `metadata/` on both branches, never promoted to the
   default-branch root** where SWH actually reads it → SWH would index **nothing**
   despite the correct `@context`. (Promotion is a publish-step concern; this
   build-gate run doesn't cover it, but it's a real gap.)

## A gap the run exposes in *our* tooling, not just the template

`swhap inspect` **accepts** her tarball with zero rejections — correctly, because
inspect is a *safety* gate (path traversal, bombs, encoding, wrapper detection),
not a content-quality judge. It rightly detected the `c-prolog/` wrapper for
auto-strip and found 53 files, no symlinks, no empty dirs.

But the source tree carries clear **curation noise** neither the template nor the
current toolkit flags: compiled objects (`arith.o`, `main.o`, …), `makefile.save`,
man-page build outputs (`*.out`), a macOS AppleDouble file (`._copyrigh.t` — the
exact cruft we excluded in the Wild_LIFE 1.02 ratification), and **stray foreign
files** (`hw1`, `hw4.pl` — someone's Prolog homework, bundled into the release
tarball). TF would *pass* these (the rebuilt tree faithfully matches the archive,
junk included); they are a curatorial call. **Recommendation:** add a
"curation-noise lint" (advisory, curator-approvable) — AppleDouble/`.o`/`.out`
heuristics + foreign-file surfacing — so a non-expert is *told* before publishing.

## Bottom line

Every FAIL traces to the **engine/template, not the user** — Mathilde drove a
real acquisition to completion competently; the tool shipped the defects. This
report is the concrete evidence for the reconciliation proposal: wiring these
same Actions to the toolkit turns all 7 FAILs into a pre-merge gate. What clears
each:

- BP-2 ×5 → `swhap build` (correct Model-P branch separation; no infra/metadata
  on `SourceCode`, no source on `main`).
- CSV-1 → adopt the canonical `version_history.csv` (D2); drop `releases.yaml` to
  an extraction-only recipe.
- JC-1a → `swhap build` writes `journal.jsonl` with full hash coverage.
- BP-3 (once unmasked) → `swhap build` creates one annotated tag per release.
- codemeta-not-indexed → `swhap publish` promotes it to the default-branch root.

**Suggested next step:** send Mathilde this report as the "why the engine swap
matters" artifact, and adopt C-Prolog as the D7 second pilot — it stresses
different failure modes than Wild_LIFE (build artifacts, a companion scanned
manual, unknown author email, foreign bundled files).
