# Branch-model arbitration — Model P won D1

**Status:** RESOLVED (Roberto Di Cosmo, 2026-06-06). Recorded here so the AI
assistant layer retrieves the *decided* layout, never re-litigates it, and never
emits Model-G structure as a recommendation.

## Ruling

**Model P (purity, brief §9) is the normative SWHAP branch layout.** The default
landing branch `main` (the Depository) holds only curation paperwork
(`README.md`, `metadata/`, `raw_materials/`, `scripts/`, optional `Makefile`); the
reconstructed source lives on a **separate orphan `SourceCode` branch** — one
commit per release, one annotated tag per release, nothing but source.

**Model G (source-on-default-branch, the current guide) is demoted** to a
read-only **legacy/audit profile** the same day. It is never written by the
pipeline and never proposed to a curator.

## Evidence (the M1c dual regeneration)

Model P won **4–0** across the discriminating axes; the pre-declared tie-breaker
(P) was not needed:

| Axis | Verdict | One-line evidence |
|---|---|---|
| AX1 archive view / citability | **P** | P gives a clean Depository landing + minimal one-release citable SWHIDs; G forces path-qualified IDs into accreting mixed trees. |
| AX2 validator enforceability | **P** | source/metadata separation is structurally undefinable in G (one shared tree), so G's purity leaks are inexpressible; P catches them via BP-2/BP-3/JC-1a. |
| AX3 post-publication append-stability | **P** | appending a late 4th release in P is a pure fast-forward — all prior commit/tree/tag SHAs (and cited SWHIDs) stay byte-identical; G rewrites every one. |
| AX4 publish-time surface | **P** | P's deposited source sits on a frozen ref separate from the mutable default branch — a botched push to `main` cannot rewrite the deposited source. |

Confirmatory, non-gating: AX6 (curator diff ergonomics) and AX7 (non-expert
"which branch is the software?"). AX5 (legacy false-fails) is not a P/G
discriminator — the 3 false failures (33%) are two profile-precision bugs shared
by both models, routed to the validator legacy-profile phase, not D1.

Full data: `swhap-toolkit/pilot/wildlife/d1/memo.md` and the AX1–AX5 records.

## Consequence for D3 (SWHID stability)

Model P enables the **append-only-after-publication** policy (D3-RESOLVED): new
releases append only; all prior SHAs and therefore cited SWHIDs remain
byte-identical (proven by the AX3 append test). A history rewrite requires an
explicit journaled curator sign-off behind a written SWHID-invalidation warning;
the validator's divergence check refuses divergence from a published remote
otherwise.

## Few-shot guidance for the assistant

- Recommend and generate **Model P** structure only.
- When a curator presents a Model-G repo, treat it as **legacy** (read-only audit
  profile), and offer migration to Model P — never propose new Model-G layouts.
