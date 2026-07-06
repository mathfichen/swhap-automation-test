# swhap-automation

Tooling to help **non-experts turn legacy source-code archives** (`.tar`,
`.tgz`, `.zip`, …) into a **SWHAP-compliant acquisition workbench** — a curated,
reproducible Git repository that Software Heritage can archive and that cites
correctly.

SWHAP is the [Software Heritage Acquisition
Process](https://www.softwareheritage.org/): the method for rescuing historic
software, reconstructing its release history, and archiving it with provenance.
Doing it by hand is expert work. This project automates the deterministic parts,
uses AI to *propose* (never impose) the metadata, and keeps a human curator in
the loop for every judgement call.

Software Heritage runs this tooling on its own acquisitions — it is **instance
zero** of a model where each institution self-hosts its own curation workbench.

## The three layers (hard separation between them)

1. **Deterministic pipeline** (`engine/`) — no AI, fully reproducible: archive
   ingestion, checksums, wrapper-stripping, extraction, Git-history
   reconstruction from a version manifest, tagging, and a compliance validator.
   Runs identically on a laptop and in CI.
2. **AI assistant layer** — infers metadata and drafts `catalogue.md` /
   `codemeta.json` / `journal` entries, explains warnings, asks guided
   questions. It **proposes** changes; it never silently mutates the result.
3. **Human-in-the-loop review** — license interpretation, attribution, inferred
   dates, release selection, and final submission always require a curator's
   approval.

Every metadata item is tagged with its provenance: **observed / computed /
inferred / user-provided / curator-approved**.

## Repository map

| Path | What it is |
|---|---|
| `engine/` | The verified deterministic toolkit (`swhap-core` builder + `swhap-validate` compliance checker). Brought in with its full history; **346 tests**. |
| `chassis/` | The GitHub-native intake surface non-experts drive through the web UI (upload → PR → Actions), wired to `engine/`. Under active co-development. |
| `docs/` | The binding decisions, architecture, roadmap, and a plain-language glossary. **Read `docs/` before proposing design changes.** |
| `pilots/` | Real acquisitions used as evidence and test cases (currently C-Prolog). |

## Status

**Milestone M2 (non-expert intake + publish) in progress.** M1 is complete: the
deterministic builder is bit-reproducible, the validator catches real history
corruption, and Wild_LIFE has been regenerated correctly under the ruled branch
layout. See [`docs/roadmap.md`](docs/roadmap.md) for where we are and what's next.

## Getting involved

- New here? Read [`docs/architecture.md`](docs/architecture.md) and
  [`docs/decisions.md`](docs/decisions.md), then [`CONTRIBUTING.md`](CONTRIBUTING.md).
- Unsure what a code like `Model P`, `BP-3`, `D4`, or `C5` means?
  [`docs/glossary.md`](docs/glossary.md) has all of them in plain terms.
- Want to curate an acquisition? The chassis workflow is in
  [`chassis/README.md`](chassis/README.md).

## License

GPL-3.0-or-later. See [`LICENSE`](LICENSE).
