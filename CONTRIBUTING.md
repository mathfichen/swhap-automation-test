# Contributing

Two very different kinds of contribution happen here. Find yours.

## A. Curating an acquisition (non-expert, GitHub-only)

You have old software and want to turn it into an archival-ready workbench. You
do **not** need Git, a terminal, or programming — just a GitHub account and a web
browser. The [`chassis/`](chassis/) intake surface walks you through it:

1. Start from the intake issue template (or the template repository).
2. Upload your archive(s) through the GitHub web UI.
3. Fill in what you know (project name, authors, release dates) — the assistant
   drafts the rest and asks you about anything uncertain.
4. Open a pull request. CI validates it and shows you exactly what, if anything,
   needs fixing. A curator reviews before anything is published.

You are always in control: the AI *proposes*, and a human curator approves every
judgement call (licenses, attributions, inferred dates).

## B. Developing the tooling

You are changing the engine, the chassis, or the docs.

**Read first:** [`docs/architecture.md`](docs/architecture.md) and
[`docs/decisions.md`](docs/decisions.md). The decisions (`D1`–`D10`) and the
compliance invariants are binding — a change that violates one is a bug, not a
feature. Unsure about a code? [`docs/glossary.md`](docs/glossary.md).

**Ground rules that come up constantly:**

- **The validator is the gate.** New behavior needs a check or a test that would
  catch its failure. The validator was built before the generator on purpose.
- **Bit-reproducibility (D4) is non-negotiable.** No wall-clock time reaches a
  commit/tag object. Build twice → identical hashes.
- **The AI layer proposes, never writes to protected refs or reads secrets.**
- **The canonical `version_history.csv` (D2) is the single manifest.** Don't
  introduce a competing format.

**Working on the engine:**

```bash
cd engine
python -m pip install -e swhap-core -e tools/validator pytest jsonschema pyld
python -m pytest -q        # 346 tests
```

**Validating a workbench:**

```bash
engine/tools/validator/check_swhap.sh --profile strict-P --gate build --workdir <path>
```

**Pull requests:** keep them scoped, explain which decision/invariant they serve,
and make sure CI is green. Reviewers look for compliance first, then correctness,
then style.
