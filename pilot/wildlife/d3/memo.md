# Decision memo D3 — iteration & identifier-stability policy

**To:** Roberto Di Cosmo (curator / decision owner)
**From:** SWHAP exemplar pilot (M1c), Wild_LIFE
**Date:** 2026-06-06
**Decides:** D3 — the policy for *adding releases to an already-published
workbench* and what we promise about identifier stability.

## The problem, in plain words

Once a workbench is published, Software Heritage assigns **SWHIDs** —
intrinsic, hash-based identifiers (like a fingerprint of the exact bytes) that
people put in papers to cite a specific version. If a later edit changes those
bytes, the fingerprint changes, and any citation that pointed at the old one
**no longer resolves to the same object**. Wild_LIFE is the real case: release
**1.02 arrived *after* the first three (0.90 / 0.91 / 1.0) were already
published** (the actual PR #1 scenario). The question: when we add it, do the
already-cited identifiers survive?

We measured this directly (axis AX3) by building a 3-release "published"
workbench, then appending the curated 1.02, and comparing every hash.

## What the data showed (real Git plumbing output)

**Model P (orphan SourceCode branch, the recommended layout):**
- All three published releases kept **byte-identical** commit, tree, and tag
  hashes after the append — e.g. 1.0 commit `97be3c5c`, tag `28ad2a35`,
  unchanged.
- The new 1.02 commit `1ca90b91` has the published 1.0 tip as its **parent**;
  `git merge-base --is-ancestor` confirms a **pure fast-forward / append**. The
  three existing release tags are never touched.
- **Consequence: every previously-issued SWHID still resolves.** Citations are
  safe.

**Model G (single shared branch):**
- **All three** published releases' commit and tag hashes **changed**
  (e.g. 1.0 commit `bdca2678 → 12581758`, tag `6af9b37d → be54e2db`).
- `git merge-base --is-ancestor` shows this is **not** a fast-forward — it is a
  **history rewrite**.
- **Root cause (verified):** the source *content* of old releases is actually
  stable; what flips them is the co-located `metadata/version_history.csv` blob
  growing from 3 rows to 4. Because metadata and release live in one tree, the
  mutable curation list is welded to release identity. One new row re-hashes
  every prior release.
- **Consequence: every previously-issued revision/release SWHID is
  invalidated.** Old citations break.

Note: the directory-level SWHID (`swh:1:dir`, the fingerprint of just the
source tree) survives in **both** models. The divergence is entirely at the
revision/release identity layer — exactly the IDs people cite. A separate D4
cross-check confirmed P's stability is reproducible, not a build fluke.

## Recommended policy

**1. Adopt Model P** (decided in the D1 memo) — it is what makes append-only
possible. With metadata off the source branch, adding a release cannot disturb
prior releases' bytes.

**2. Published history is append-only.** A new release on an already-published
workbench is added as a **fast-forward** to `SourceCode` plus one new annotated
tag. The validator must confirm the new tip has the old tip as an ancestor and
that no prior tag's target changed. This is the default, unattended path.

**3. Rewrites require explicit, journaled curator sign-off.** If a genuine
correction *must* alter an already-published release (e.g. a wrongly-included
file), it is **not** done silently. It requires:
   - a journal entry recording the reason and the provenance transition, and
   - an explicit curator approval that **acknowledges a SWHID-invalidation
     warning** naming which published identifiers will no longer resolve.

This confirms the expected policy from the data: published = append-only;
rewrites = journaled curator sign-off behind an explicit invalidation warning.

## Signature

Policy adopted: ___________________________

Roberto Di Cosmo — date: ______________   signature: ______________
