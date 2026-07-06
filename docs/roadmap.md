# Roadmap

Milestones with exit gates. Current position: **M2 in progress**.

| Milestone | Goal | Status |
|---|---|---|
| **M1** | Deterministic core: builder + validator, proven on Wild_LIFE | ✅ **complete** |
| **M2** | Non-expert intake + publish | 🔨 **in progress** |
| **M3** | Second pilot + hardening | ⏳ next |
| **M4** | Deployment / self-host packaging (D6) | ⏳ |
| **M5** | Stretch: GitLab parity, RAG package, doc set | ⏳ |

## M1 — complete

Built the validator **first** (so generator mistakes get caught), then the
builder.

- **M1a** — `check_swhap.sh` / `swhap-validate` with the TF/BP/CSV/CM/SZ/PI
  batteries; adversarially proven to catch the real corruption in the *published*
  Wild_LIFE exemplar (leaked files, stale license, missing tags).
- **M1b** — the canonical `version_history.csv` parser and the Git-history
  builder; **bit-reproducible** (D4), single-parser (D2), both proven by
  execution.
- **M1c** — regenerated Wild_LIFE under both branch layouts; ruled **Model P**
  (D1) and **rebuild-and-replace** (revised D3). The corrected workbench is
  reproducible from committed inputs and validates green.

Exit gate met: a bit-reproducible, validator-green Wild_LIFE regeneration from
committed inputs; the corrupted published exemplar formally banned as a
reference.

## M2 — in progress

- **Publish step + revised-D3 rebuild-and-replace** — ✅ done in `engine/`
  (`swhap publish [--supersede]`, DV-1 divergence guard, snapshot-SWHID lineage;
  346 tests).
- **Non-expert intake surface (D5)** — 🔨 the GitHub-native `chassis/`: web-UI
  upload → PR → Actions, wired to the engine. This is the active collaboration.
- **Curator workflow + legal go/no-go gate** — ⏳.
- **Usability test (criterion C5)** — ⏳ needs ≥2 named non-expert testers.

**Where the chassis stands:** a first end-to-end template exists and was driven
on a real acquisition (see [`../pilots/c-prolog`](../pilots/c-prolog)), which
surfaced the concrete gaps now tracked as issues. The engine-wired chassis
closes them.

## M3 — next

A second real pilot end-to-end through the reconciled chassis, plus hardening
from what the pilots teach. C-Prolog is the leading candidate — it stresses
different failure modes than Wild_LIFE (build artifacts in the tree, a companion
scanned manual, unknown author identity, foreign bundled files).

## M4 / M5

M4: package the tool so another institution can stand up its own instance (D6) —
deployment docs as first-class deliverable. M5 (stretch): GitLab parity, a
retrieval package for the AI layer, and the four-guide documentation set.
