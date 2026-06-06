# Wild_LIFE Model-P regeneration — runbook (exemplar-pilot T11, M1 exit gate)

This regenerates the `Wild_Life-swhap` exemplar as a **Model P** SWHAP workbench
(brief §9 orphan-purity; D1-RESOLVED) — tree-faithful, canonical CSV, canonical
CodeMeta 2.0 `@context`, integrating PR #1's author-supplied 1.02 tarball as the
fourth release — **reproducibly from committed inputs**. There is no `/tmp`
dependency: everything needed lives in this directory plus the byte-frozen
release tarballs under `fixtures/wildlife/tarballs/`.

## Committed inputs (this directory)

| Path | What |
|---|---|
| `regen.py` | the single deterministic driver (stdlib + `swhap_core` only) |
| `version_history.csv` | the canonical 4-release history (vhcsv-written; authoritative) |
| `codemeta.json` | canonical CodeMeta 2.0 (`https://doi.org/10.5063/schema/codemeta-2.0`, `funder` not `funding`) |
| `curation-manifest.json` | the six **curator-approved** curatorial decisions (drives the journal) |
| `manifests/1.02.json` | the derived 1.02 TF validation oracle (curated Model-P tag tree) |
| `test_m1_exit_gate.py` | the M1 exit gate as an executable test |

The 0.90 / 0.91 / 1.0 TF oracles are the frozen tarball-derived fixtures under
`fixtures/wildlife/manifests/` (independent provenance, non-circular); `regen.py`
copies them into the validation oracle dir at build time. The quarantined census
`fixtures/wildlife/manifests/1.02.json` stays UNTOUCHED as the forensic record;
the curated, non-quarantined 1.02 oracle is the committed `manifests/1.02.json`.

## Reproduce (one command + one gate)

```bash
# from the toolkit root, inside the venv (stdlib runtime + swhap_core)
python3 pilot/wildlife/regen/regen.py OUTDIR
```

`regen.py OUTDIR` runs the full pipeline into `OUTDIR/`:

1. **acquire** — verify the four committed tarballs against the sha256s pinned in
   `curation-manifest.json` (the "acquired bundle").
2. **extract** — read-only extraction with a hardened tar filter: regular members
   pass the stdlib `data` filter (path-traversal / device / setuid protection);
   symlinks are re-emitted verbatim and NEVER followed; nothing is ever executed.
   Wrapper directories (`Life/`, `Life1.0/`, `Life1.02Ultrix/`) are stripped.
3. **curate** — per the manifest: 1.02 AppleDouble exclusion (256 `._*` + the
   stray `._Life1.02Ultrix` = 257), 4 absolute-target symlinks preserved as
   documented broken-link artifacts, 65 in-tree relative symlinks preserved,
   0o777 perm flattening documented. The ratified expected counts are asserted.
4. **metadata** — copy the canonical CSV (self-checked FAIL-free against the
   `canonical` vhcsv profile) + codemeta; write README; seed `journal.jsonl` from
   the manifest's six curator-approved decisions + the author-identity provenance.
5. **build** — `swhap build --model P --apply` (`do_build`): orphan `SourceCode`
   source history, one commit + one annotated tag per release, with the D4 fixed
   curation timestamp (epoch `1781049600` `+0000` = 2026-06-10T00:00:00Z).
6. **materialize** — the validator's published layout in `OUTDIR/validate-P/`
   (a separate repo so the build-time ref-policy guard is never touched): `main`
   = Depository (README + metadata + raw_materials + scripts), `SourceCode` =
   orphan source tip, `v<rel>` = the verbatim candidate tag objects (no rebuild;
   D4 intact).
7. **oracles** — `OUTDIR/manifests-validation/` = frozen 0.90/0.91/1.0 + the
   committed derived 1.02.

Then run the validator gate:

```bash
SWHAP_PYTHON="$(command -v python3)" bash tools/validator/check_swhap.sh \
  --profile strict-P --gate build \
  --workdir OUTDIR/validate-P \
  --manifests OUTDIR/manifests-validation \
  --report OUTDIR/report-P.json \
  --reference-date 2026-06-10T00:00:00+00:00
```

## Expected result (validated green)

`check_swhap.sh --profile strict-P` exits **0**: 0 FAIL, 25 PASS, 1 WARN, 1 INFO.

- TF-1..5 GREEN on all four releases including the curated 1.02.
- PI-1: ran, **no finding** — the journaled curator-email opt-in
  (`pii.curator_email` → `curator-approved`, curator actor) clears the WARN.
- JC-1a: ran, **no finding** — the apply entry covers every commit + tag object.
- WARN = CSV-7 (1.02 year-only `1994` precedes 1.0 `1994-03-24`; legitimate per
  csv-contract §7, never blocks). INFO = CM-4 (`funder` vs `funding` note).

D4: running `regen.py` twice into two output dirs yields byte-identical commit
AND annotated-tag object SHAs. All of the above is asserted by
`test_m1_exit_gate.py` (run with `pytest pilot/wildlife/regen/`).

## Provenance of the committed SHAs (for cross-checks)

```
SourceCode tip  1ca90b91af38a11e4ab928133ee34bcb04b2e2ef
commits         v0.90 b3fc04c6  v0.91 60076a85  v1.0 97be3c5c  v1.02 1ca90b91
tag objects     v0.90 ee70107e  v0.91 916de73b  v1.0 28ad2a35  v1.02 57d79ac3
```

These are stable across runs by D4 (the curation timestamp is fixed and no
wall-clock enters the hashed objects; the journal's wall-clock timestamps are
deliberately outside the hash guarantee per journal-schema §13).
