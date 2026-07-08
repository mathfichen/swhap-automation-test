# C-Prolog #2 — instrumented run log

**Purpose:** run one real acquisition end-to-end *by hand*, build nothing, and
record every step / decision / permission — so the manual step-list becomes the
provisioning-automation spec and the GitHub App's exact token scopes (the
four-advisor panel's core recommendation, decision D11).

**Date:** 2026-07-06 · **Corpus:** C-Prolog 1.5 (Fernando Pereira, EdCAAD,
University of Edinburgh, 1984) · **Contrast:** the *published* first pilot
([mathfichen/C-Prolog](https://github.com/mathfichen/C-Prolog)) was built through
the old hand-rolled template and scored **7 FAIL** on the validator
([validation-report.md](validation-report.md)).

---

## Part A — local build + validate (done; needs no org/token)

Ran the verified engine on the real C-Prolog 1.5 tarball. Reproducible inputs are
committed under [`workbench-inputs/`](workbench-inputs/).

| Step | Command / action | Result |
|---|---|---|
| Extract + wrapper-strip | `c-prolog/` wrapper auto-stripped → `source_code/1.5/` | ✓ |
| Build Model-P history | `swhap build --model P --apply --curation-epoch 1700000000` | ✓ one orphan commit `72e071…` + **annotated tag `v1.5`** `f27b57…` |
| Bit-reproducibility (D4) | second independent build | **identical** commit + tag hashes |
| Compliance gate | `swhap-validate --profile strict-P --gate build` | **0 FAIL / 1 WARN / 21 PASS, exit 0** |

**Headline:** pilot #1 **7 FAIL** → pilot #2 **0 FAIL**. Every earlier failure is
cleared by construction:

- **BP-2 ×5** (workbench leaked onto `SourceCode`, source on `main`) → gone:
  `SourceCode` holds source only, `main` holds workbench only.
- **BP-3** (no annotated tag) → gone: `v1.5` annotated tag present (and now
  *unmasked* — pilot #1 hid it behind the missing CSV).
- **CSV-1** (no manifest) → gone: canonical `version_history.csv` (98-byte header).
- **JC-1a** (journal) → gone: `journal.jsonl` hash-chain covers the commit + tag.

The single **WARN is PI-1** on the curator email `roberto@dicosmo.org` — a *real*
address (opt-in), exactly the confirmation Roberto already gave for Wild_LIFE.

**Not covered locally (honest gaps):** tree-fidelity (TF-*) still needs a manifest
oracle to run (backlog); and the actual publish-to-remote + `codemeta.json`
root-promotion + Save-Code-Now are the outward-facing steps in Part C.

---

## Part B — curator decisions (human-in-the-loop; Roberto/Mathilde to confirm)

The run surfaced exactly the judgement calls SWHAP reserves for a human. Defaults
were chosen to be *faithful and reversible*; each is flagged for ruling.

| # | Decision | Chosen (provisional) | Needs |
|---|---|---|---|
| C-1 | Release set | Single release **1.5** (only source in hand). More releases can be inserted later — that exercises the D3 rebuild-and-replace path. | confirm |
| C-2 | Release date | **1984-02-20** (day precision), from the CMU listing / pilot-#1 evidence. | confirm the exact day's source |
| C-3 | Authorship | Collective **"C-Prolog authors"** + placeholder `c-prolog-authors@noreply.example.org` (Pereira primary per `copyrigh.t`; Damas & Byrd credited in codemeta). | individual vs collective attribution |
| C-4 | Curator identity | Roberto Di Cosmo, `roberto@dicosmo.org` (real → PI-1 opt-in). | confirm publish |
| C-5 | License | **Undetermined** — `copyrigh.t` present (looks like an Edinburgh/academic notice); `codemeta` license field intentionally omitted pending determination. | license call (gates republication, like Wild_LIFE's DEC) |
| C-6 | Curation noise | **Excluded:** `._copyrigh.t` (macOS AppleDouble resource fork — filesystem metadata, not content; Wild_LIFE precedent). **Preserved but flagged:** `.o` object files, `makefile.save` / `man/makefile.save` (editor backups), `man/app.out` / `man/cprolog.out` (nroff output of the `.me` sources), and — most notably — `hw1`, `hw4.pl` (**foreign: student homework**, not C-Prolog). | rule: exclude build artifacts + foreign homework? (recommend yes) |

The raw tarball in `raw_materials/` stays **byte-identical**; all curation happens
in the curated tree only.

---

## Part C — by-hand GitHub provisioning checklist (Roberto executes; = the automation spec)

Each step records the **permission it requires** — that column *is* the future
GitHub App's token-scope list (derived empirically, not guessed). Do these by hand
for #2; the App later automates steps 3–5, 8.

| # | Action | Permission required → App scope |
|---|---|---|
| 0 | Create the org (`SWHAP-workbenches` or chosen name) | org creation (human owner) |
| 1 | Push `chassis/` as `SWHAP-workbenches/chassis`; Settings → **Template repository** | repo admin |
| 2 | Create `SWHAP-workbenches/swhap-intake` (internal); add `intake/.github/` | **Administration: write** (create repo in org) |
| 3 | Provision: **Use this template** → `SWHAP-workbenches/c-prolog` | **Administration: write** (generate-from-template) |
| 4 | Put `raw_materials/` + `metadata/*` (the committed inputs) in place | **Contents: write** |
| 5 | Confirm **Actions are enabled** (not blocked by org policy/SSO) | Actions settings |
| 6 | PR-validate CI runs → confirm report matches the local **0 FAIL** | — |
| 7 | Resolve C-1…C-6 + PI-1; add `SWH_TOKEN` behind Environment `publish` (reviewer = curator) — **C2: token never shares a job with untrusted extraction** | Secrets: write; Environments |
| 8 | Run build-and-publish → `main` + `SourceCode` + `v1.5` + `codemeta.json` at repo root | Contents: write; protected-ref |
| 9 | (optional) Save-Code-Now | SWH API token |
| 10 | Register back: topic `swhap` + link the origin | — |

**What to measure on the run:** (a) did Actions run on the fresh org repo without a
manual enable (step 5)? (b) how many privileged clicks did steps 7–8 cost? Those two
numbers decide whether the GitHub App is worth building before onboarding real
outsiders.

---

## Finalization — PII-redacted & published (2026-07-08)

Opening the flagged files turned C-6 from tidiness into a **privacy finding**:
`hw1`/`hw4.pl` are a 1988 student's homework (CSE 511) containing a real **SSN**
(`245-29-5485`) — foreign to C-Prolog, and unpublishable.

Ruling applied (Roberto, 2026-07-08):
- **Curated tree:** excluded `hw1`, `hw4.pl`, `*.o`, `man/*.out`, `*.save`
  (and the AppleDouble `._*`); kept source, headers, `pl/` library, man sources,
  `copyrigh.t`, runtime files.
- **Raw archive:** repackaged minus the two homework files (**D12** — journaled
  PII-redaction, not silent alteration); verified 0 SSN occurrences, 0 homework
  members in the new tarball.
- **Rebuilt + re-validated:** still **0 FAIL / 1 WARN / 21 PASS** (WARN = the
  curator-email opt-in). Published layout: `main` (README + metadata +
  raw_materials), orphan `SourceCode`, annotated `v1.5`.

### Two engine/spec findings this surfaced (filed in BACKLOG)

1. **`codemeta.json` at root vs BP-2.** Architecture B5 says publish must promote
   `codemeta.json` to the default-branch root (SWH indexes only there), but the
   validator's `_MAIN_ALLOW` rejects it → BP-2 FAIL. The allowlist must add
   `codemeta.json`. For now C-Prolog #2 keeps codemeta in `metadata/` (validator-
   clean) and root-promotion is deferred.
2. **Workbench self-CI vs BP-2.** `.github/` is not in `_MAIN_ALLOW` either, so a
   workbench cannot carry its own CI workflows without failing branch-purity —
   the "how does a provisioned workbench run its own validation" design question.
3. **Curation-exclusion manifest gap.** The curated tree differs from what the
   extraction-recipe reproduces (noise removed by hand). The engine needs a
   recorded exclusion list so the curated tree is reproducible from
   raw + recipe + exclusions.

## Outputs of this run

- Reproducible inputs: [`workbench-inputs/`](workbench-inputs/) (CSV, extraction
  recipe, curation-epoch, codemeta, and the machine journal).
- Full validator report: [`report-2-strictP.json`](report-2-strictP.json).
- A *correct* C-Prolog workbench recipe (0 FAIL) to contrast against pilot #1.
- This checklist → the P2 provisioning spec + the App token scopes (BACKLOG).
