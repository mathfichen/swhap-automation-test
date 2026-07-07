# intake — the contributor front door (scaffold)

This directory is the **scaffold for the standing intake repository** — the one
place a contributor goes to hand in old software. It is deployed as its own repo
(e.g. `SWHAP-workbenches/swhap-intake`), **not** run from this development hub and
**not** part of the per-acquisition workbench template (`../chassis`).

Why it lives in its own repo (decision **D11**): the front door must exist
*before* any per-acquisition repo does. A contributor files one issue here; a
curator (later, a bot) provisions the workbench repo *for* them. The contributor
never creates a repo and never opens a pull request.

## Contents

- `.github/ISSUE_TEMPLATE/acquisition-intake.yml` — the typed intake form
  ("Acquire legacy software"). Jargon-free, browser-only: name, authors, license
  note, releases with approximate dates, drag-drop archives or URLs.
- `.github/ISSUE_TEMPLATE/config.yml` — disables blank issues so the form is the
  single reachable entry, and links developers back to the dev hub.

## To deploy (curator/operator)

1. Create the intake repo in your acquisition org (`SWHAP-workbenches/swhap-intake`).
   Recommended **internal/private** — old archives may carry personal data.
2. Copy this `.github/` into it. The "Acquire legacy software" form then appears
   under **Issues → New issue**.
3. Wire provisioning (curator-click first; a GitHub App later — see
   [`../BACKLOG.md`](../BACKLOG.md)). The provisioning step, not the contributor,
   creates the per-acquisition workbench from [`../chassis`](../chassis).

Until the intake repo is live, a contributor is routed here by the project's
contributor guideline; the provisioning is done by hand (see the C-Prolog #2
run plan).
