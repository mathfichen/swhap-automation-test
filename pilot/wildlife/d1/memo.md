# Decision memo D1 — how the curated Wild_LIFE workbench is laid out in Git

**To:** Roberto Di Cosmo (curator / decision owner)
**From:** SWHAP exemplar pilot (M1c), Wild_LIFE
**Date:** 2026-06-06
**Decides:** D1 — the *branch layout* of a SWHAP workbench: where the reconstructed
source code lives in the Git repository relative to the curation metadata.

## What is being decided, in plain words

A SWHAP workbench is a Git repository. We must choose **one of two layouts**:

- **Model P ("purity", the brief's §9 design).** The default landing branch
  (`main`, the "Depository") holds *only* curation paperwork —
  `README.md`, `metadata/`, `raw_materials/` (the original tarballs, untouched),
  `scripts/`. The reconstructed source code lives on a **separate, parentless
  "orphan" branch** called `SourceCode`: one commit per release, one annotated
  tag per release, and *nothing but source* on it.
- **Model G ("guide", what the current SWHAP-on-GitHub guide does).** There is
  **one branch**. Both the metadata *and* the source code sit together on it,
  the source under a growing `source_code/<release>/` folder.

A **pre-declared tie-breaker** was fixed before we ran anything: *if the evidence
is a wash, choose Model P.* We did not have to fall back on it — P wins on merits.

## The seven evaluation axes

Five axes were executed against the real regenerated Wild_LIFE workbench; two
need your eyes (human judgement) and are marked PENDING-HUMAN with prepared
materials.

| Axis | What it asks | Verdict | One-line evidence |
|---|---|---|---|
| **AX1 — archive view** | How the Software Heritage loader/citation sees each layout | **P** | P gives a clean Depository landing + minimal one-release citable IDs; G forces path-qualified IDs into accreting mixed trees. [data](../../../../../tmp/swhap-m1c/d1/AX1-loader.md) |
| **AX2 — enforceability** | Which layout the validator can police more strictly | **P** | Source/metadata separation is *structurally undefinable* in G (one shared tree), so G's purity leaks are inexpressible; P catches them via BP-2/BP-3/JC-1a. [data](../../../../../tmp/swhap-m1c/d1/AX2-enforceability.md) |
| **AX3 — iteration** | What appending a late 4th release does to already-published IDs | **P** | P = pure fast-forward, all 3 published commit/tag hashes byte-identical; G rewrites every one (see D3 memo). [data](../../../../../tmp/swhap-m1c/d1/AX3-iteration.md) |
| **AX4 — publish** | Publish-time error/attack surface | **P** | G is 1 step lighter on raw count, but P's deposited source sits on a frozen ref separate from the mutable default branch — a botched push to `main` cannot rewrite the deposited source. [data](../../../../../tmp/swhap-m1c/d1/AX4-publish.md) |
| **AX5 — legacy false-fails** | Does the legacy-audit profile cry wolf? | **not a P/G discriminator** | 3 false failures (33%), but both are profile-precision bugs shared by both models; routed to validator T10, does not move D1. [data](../../../../../tmp/swhap-m1c/d1/AX5-legacy-falsefail.md) |
| **AX6 — review-diff ergonomics** | Which layout is easier for a curator to review by diff | **PENDING-HUMAN** | Materials prepared (below). |
| **AX7 — non-expert comprehension** | "Which branch *is* the software?" for a newcomer | **PENDING-HUMAN** | Materials prepared (below). |

### Prepared materials for AX6 and AX7 (your input needed)

Both refs are already built in the regeneration workdir
`/tmp/swhap-m1c/Wild_Life-swhap-regen` — Model P on branch
`candidate/P/...P01` (orphan `SourceCode` + tags `v0.90..v1.02`), Model G on
`candidate/G/...G01`. To make the side-by-side judgement:

- **AX6 (review diff):** in the workdir run, for each model,
  `git log --stat candidate/<P|G>/...` and
  `git diff <prev-tag> <tag>` for the 1.02 release. P shows a pure source diff;
  G shows source intermixed with a `metadata/version_history.csv` row change.
  Judge which diff a non-expert curator can sanity-check faster.
- **AX7 (comprehension):** open both refs in a Git browser (or
  `git ls-tree --name-only <branch>`). Question to a newcomer: *"point at the
  software."* Under P the answer is "the `SourceCode` branch"; under G it is
  "the `source_code/` folder on the only branch." Record which framing is
  less confusing.

## Scoreboard

- Executed axes that discriminate P vs G: **AX1, AX2, AX3, AX4 → all P (4–0)**.
- AX5 → neutral (profile bug, not a layout question).
- AX6, AX7 → pending your judgement; not expected to overturn a 4–0 result.
- Tie-breaker (Model P) was **not needed** — the merits already point to P.

## Recommendation

**Adopt Model P** (brief §9 purity: pure Depository `main`, orphan `SourceCode`
branch, one annotated tag per release). It is the cleaner archived presentation,
the only layout the validator can enforce strictly, the only one that keeps
already-cited identifiers stable across late releases, and the safer one to
publish. Confirm AX6/AX7 do not surprise us, then ratify.

## 1.02 curatorial decisions to ratify (check to approve)

These were taken during regeneration and journaled as *curator-approved pending
this memo*. Your tick ratifies them.

- [ ] **AppleDouble exclusion** — 257 macOS resource-fork `._*` companion files
  (2010/2017 mtimes, not 1994 source) removed from the curated 1.02 tree; the
  original tarball stays byte-identical in `raw_materials/`.
- [ ] **Absolute symlinks preserved as broken artifacts** — the 4 top-level
  symlinks pointing outside the tree (to the author's machine) kept verbatim as
  link blobs, never followed.
- [ ] **Relative symlinks preserved verbatim** — the other 65 symlinks resolve
  inside the tree; kept as-is.
- [ ] **Permission flattening documented** — all files arrived `0o777` (Ultrix/
  macOS artifact); exec bit collapsed systematically, documented not corrected.
- [ ] **Curator-email opt-in** — your real address `roberto@dicosmo.org`
  confirmed for publication (clears the PI-1 warning).
- [ ] **Release-date inferences** — 0.90/0.91 = 1993-08-09, 1.0 = 1994-03-24
  (CMU listing dates), 1.02 = 1994 (year-only, D10).

## Signature

Decision: ___________________________  (Model P / Model G)

Roberto Di Cosmo — date: ______________   signature: ______________
