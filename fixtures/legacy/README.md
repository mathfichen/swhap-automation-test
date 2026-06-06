# Legacy-audit fixtures (AX5 / T10 precision audit, CI-reproducible)

Synthetic, **license-clean** legacy-workbench fixtures that make the
legacy-profile precision audit re-runnable from a clean checkout, in the normal
pytest suite. They are produced by `build.py` (deterministic generator) and
pinned by `MANIFEST.sha256` + `index.json`. They are **not** copies of any
third-party repository — they reproduce the defect *shapes*, with invented
content, fixed identities, and `noreply.example.org` placeholder emails.

## Why these exist

The original AX5 audit was run **once, live**, against two REAL published
acquisitions that existed only in ephemeral `/tmp`. It demonstrated that the
two FIX-* changes turned **3 false failures → 0** under the legacy profile while
**preserving the genuine defects**:

- **FIX-1** (CSV-1): the legacy CSV dialects (Unipisa/DT2SG + guide) are tolerated
  via the read-only converter under the legacy profile (was a false `CSV-1`).
- **FIX-2** (CM-1): a root-level `codemeta.json` is tolerated under the legacy
  profile (was a false `CM-1`).

Because the targets were ephemeral, that evidence could not be re-derived in CI.
These fixtures + the e2e harness (`tools/validator/tests/test_legacy_audit_e2e.py`)
re-derive the same result deterministically.

## Mapping to the real AX5 targets

| Fixture | Stands in for (real repo) | Defect shape | Tolerated dialect (was a FALSE failure) | Genuine defect (must still FAIL) |
|---|---|---|---|---|
| `unipisa-cmm` | **Unipisa/CMM-Workbench** | wrapper-directory defect case | unipisa CSV header dialect (false `CSV-1`); `codemeta.json` at the repo root (false `CM-1`) | `BP-5` — a `SourceCode` release whose tree is a single artificial top-level wrapper directory |
| `guide-chainage` | **mathfichen/chainage_de_contour** | non-canonical-CSV-dialect case | guide `date original` CSV header dialect (false `CSV-1`) | `CM-2` — a root `codemeta.json` with an `@context` SWH does not accept |

Each fixture deliberately pairs a tolerated dialect with a genuine defect so the
harness can assert **both** halves of the precision claim at once: zero false
failures on the dialects, and the genuine defect still surfaced under the legacy
profile (FAIL severity, `enforced: false`). `test_strict_profile_still_fails_the_
tolerated_dialects` additionally shows the tolerance is **legacy-scoped** (the
same dialects FAIL under `strict-P`), i.e. not a blanket suppression.

The genuine-defect `check_id`s declared in `index.json` are the oracle the
harness compares the legacy FAIL set against (no false failures, no over-broad
suppression).

## Reproducibility

`build.py` writes each fixture as a git workbench with fixed content, identity,
and dates; the pinned fingerprint is the **git tree SHA** (date-independent) of
the most defect-bearing ref. Regenerate / verify with:

```sh
python build.py          # (re)writes MANIFEST.sha256 + index.json
python build.py --check  # rebuild twice into temp dirs; verify determinism + MANIFEST
```

`test_legacy_audit_e2e.py` runs `--check` and re-derives the tree SHAs in-suite.

## One-time live-audit evidence

The mapping above stands in for the one-time live AX5 audit recorded in the
project analysis (the T10 legacy-audit precision report referenced by
`specs/validator-report.md` §"Consumers designed for" — milestone-gate evidence
M1d/T10). These fixtures are the CI-reproducible re-derivation of that evidence;
the live run against the real repos remains the historical source.
