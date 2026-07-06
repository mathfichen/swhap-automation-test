# Contributing

Two very different kinds of contribution happen here. Find yours.

## A. Handing in old software (contributor — one form, browser only)

You have old software and want it preserved. **Your whole job is to fill in one
form.** You do not need Git, a terminal, a pull request, or to create any
repository — a curator sets all that up *for* you (decision D11).

1. **Open a request** at the intake front door and drag-drop your archive(s)
   (or paste URLs for large ones). Fill in what you know — project name, authors,
   approximate dates. "Unknown" and "around 1993" are fine. Submit.
2. **That's it.** A curator provisions the workbench, and the assistant drafts
   the metadata. If anything is uncertain ("we think 1.0 is March 1994 —
   confirm?"), you'll be asked in plain comments on your request.
3. **A curator reviews and publishes.** You get notified with the archived
   result and its citation.

You are always in control: the AI *proposes*; a human curator approves every
judgement call (licenses, attributions, inferred dates). The intake form and its
scaffold live in [`intake/`](intake/); the workbench machinery it feeds is
[`chassis/`](chassis/) (both are for operators to deploy — not something you
touch).

## B. Developing the tooling

You are changing the engine, the chassis, or the docs.

**Start at** [`docs/onboarding.md`](docs/onboarding.md) — it sequences the reading
(README → architecture → decisions → roadmap). The decisions (`D1`–`D11`) and the
compliance invariants in [`docs/architecture.md`](docs/architecture.md) are
binding — a change that violates one is a bug, not a feature. Unsure about a code?
[`docs/glossary.md`](docs/glossary.md).

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
