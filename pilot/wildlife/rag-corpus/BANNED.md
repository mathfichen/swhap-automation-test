# BANNED few-shot material — the corrupted published Wild_LIFE exemplar

**Hard rule.** The published `SoftwareHeritage/Wild_Life-swhap` repository (and
any artifact derived from it) is **formally barred** as RAG retrieval context and
as few-shot exemplar material for the AI assistant layer. It is fixture material
for what the validator must **catch**, not a model of correct output. Use the
corrected sources pinned in `manifest.json` instead.

## What is banned

| Banned artifact | Pin (do not treat as a moving target) |
|---|---|
| Published `main` tree | `1571ce554b575ddacb750fa8135d6df4841d0090` |
| Published `SourceCode` tip (3 commits, **no annotated tags**) | `24051137387e57d0bcd419e37fa1dba90d88c0eb` |
| Its `metadata/codemeta.json` (bogus `@context`) | as of the `main` pin above |
| Its `v0.91` / `v1.0` release trees (previous-version leaks) | on the `SourceCode` pin above |
| Its boilerplate 2-row `metadata/journal.md` | as of the `main` pin above |

## Why — the concrete defects (do NOT learn these)

1. **Bogus CodeMeta `@context`.** The published file declares
   `https://doi.org/10.5063/sciencecodemeta/codemeta-2.0` — a malformed,
   non-existent context. The canonical, swh-indexer-accepted value is
   `https://doi.org/10.5063/schema/codemeta-2.0`. The bogus context is the C2
   failure mode: swh-indexer would **silently drop** the metadata. An LLM that
   few-shots on this file will reproduce the typo. (Corrected file:
   `pilot/wildlife/regen/codemeta.json`.)

2. **Leaked release trees (tree-fidelity corruption).** The published `v0.91`
   tag tree carries +19 files leaked from a previous version with 0-of-19 proper
   deletions; the `v1.0` tree leaks +1145 files and a stale `LICENSE`. These trees
   are NOT tree-faithful to the release tarballs — they are exactly what the TF-1
   / TF-3 checks fire on. (Corrected, tree-faithful source:
   `pilot/wildlife/regen/` Model-P SourceCode branch + tags.)

3. **No annotated tags.** The published `SourceCode` branch ships zero annotated
   release tags (release→commit was guessed by commit message). This is the BP-3
   defect. The corrected workbench has one annotated tag per release.

4. **Boilerplate journal (no hash coverage).** The published `metadata/journal.md`
   is a 2-row stub that references none of the reconstructed commit/tag hashes —
   the JC-1a hash-coverage gap. The corrected workbench journals every object.

## Enforcement

- Retrieval / few-shot loaders MUST exclude every artifact reachable from the
  pins above (and any fork/mirror of `SoftwareHeritage/Wild_Life-swhap`).
- Only the sources in `manifest.json` (`approved_sources`) are admissible.
- If the published exemplar is ever needed, it is admissible ONLY as a **negative
  example** explicitly labelled "corrupted — what to catch", never as a target to
  imitate.
