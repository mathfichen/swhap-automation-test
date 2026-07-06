# Start here (for collaborators)

Welcome. This repo initializes the shared SWHAP-automation effort. Here's the
fastest path in.

## Read, in order

1. [`../README.md`](../README.md) — what the project is and the three layers.
2. [`architecture.md`](architecture.md) — the model and the compliance
   invariants (the rules a change must not break).
3. [`decisions.md`](decisions.md) — the binding decisions `D1`–`D10`.
4. [`roadmap.md`](roadmap.md) — where we are (M2) and what's next.

Keep [`glossary.md`](glossary.md) open for any code you don't recognise.

## See it concretely

- The intake surface we're building together: [`../chassis`](../chassis).
- Why it's shaped this way: the C-Prolog pilot
  [`../pilots/c-prolog`](../pilots/c-prolog) — a real acquisition that proved both
  that the web-UI flow works and that the first template needed the verified
  engine behind it.
- What to pick up: [`../BACKLOG.md`](../BACKLOG.md).

## How we work

- The **AI proposes, a human curator approves** — nothing outward-facing happens
  without a person's yes.
- The **validator is the gate** — a change ships with a check or test that would
  catch its failure.
- Curating an acquisition needs only a browser (no git/CLI); developing the
  tooling follows [`../CONTRIBUTING.md`](../CONTRIBUTING.md).

## Good first steps

- Run the engine locally: `cd engine && pip install -e swhap-core -e tools/validator pytest jsonschema pyld && pytest -q`.
- Skim the C-Prolog report, then look at how the chassis workflows close each
  finding.
- Pick a `B*`/`S*` item from the backlog.
