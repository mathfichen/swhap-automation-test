# Pilot: C-Prolog

**C-Prolog** (Fernando Pereira, EdCAAD, University of Edinburgh, 1984 — a Prolog
interpreter in C, based on Luis Damas's IMP Prolog) is a real acquisition Mathilde
drove end-to-end through the first hand-rolled GitHub template
([mathfichen/C-Prolog](https://github.com/mathfichen/C-Prolog)).

It earns its place here twice over:

1. **Proof the intake UX works.** A non-expert took a historic tarball from
   web-upload to a published `SourceCode` branch entirely through the GitHub UI —
   validating the D5/D6 direction.
2. **Proof the old template needs the engine.** Running the toolkit validator on
   the result surfaced concrete compliance defects — the evidence that drove the
   engine-wired [`chassis/`](../../chassis). See
   [`validation-report.md`](validation-report.md): **7 FAIL / 1 WARN / 12 PASS**.

Every failure traces to the template/engine, not the curator. Each is closed by
the reconciled chassis; the findings are the shared backlog in
[`../../BACKLOG.md`](../../BACKLOG.md).

C-Prolog is the leading candidate for the **M3 second pilot** — it stresses
failure modes Wild_LIFE does not: compiled build artifacts in the source tree,
a companion scanned manual PDF, unknown author identity, and foreign files
bundled into the release archive.

## Run #2 — the engine, done right (2026-07-06)

C-Prolog rebuilt through the verified engine scores **0 FAIL / 1 WARN / 21 PASS**
(exit 0) — versus pilot #1's **7 FAIL**. Bit-reproducible (identical commit + tag
hashes across two builds); one annotated `v1.5` tag; clean Model-P separation. The
lone WARN is the expected curator-email opt-in (PI-1). See
[`run-2-log.md`](run-2-log.md) for the instrumented log, the curator decisions,
and the by-hand GitHub-provisioning checklist that becomes the automation spec.

## Files

- `run-2-log.md` — the instrumented run #2 (build + validate + curator decisions
  + provisioning checklist).
- `workbench-inputs/` — reproducible inputs for run #2 (canonical CSV, extraction
  recipe, curation-epoch, codemeta, machine journal).
- `report-2-strictP.json` — run #2 raw validator output (**0 FAIL**).
- `validation-report.md` — pilot #1 human-readable findings (**7 FAIL**).
- `report-strictP.json` — pilot #1 raw `swhap-validate` output.
