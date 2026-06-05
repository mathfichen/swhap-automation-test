# swhap-core

Deterministic Layer-1 SWHAP workbench generator. **M1a slice shipped: the
read-only inspection pass** (`swhap inspect`). No extraction to disk; member
enumeration + crit-M6 rejection-rule evaluation on the member list directly.

## Install / run

stdlib-only at runtime (Python ≥ 3.11). For development:

```sh
PYTHONPATH=src python3 -m swhap_core.cli inspect ARCHIVE [ARCHIVE…] [--policy FILE]
# or, installed:  swhap inspect ARCHIVE --json
```

`--json` is the default and only output format. Output is deterministic: no
wall-clock, no absolute host paths; the archive is content-addressed by its own
sha256, and every emitted path is `bsafe`-encoded (validator-report §2.5a) so a
non-UTF-8 name can neither crash serialization nor smuggle a control byte into a
forge-visible report.

## `swhap inspect` JSON shape (`swhap-core/inspect/v1`)

```jsonc
{
  "schema": "swhap-core/inspect/v1",
  "archive": "life_10.tgz",          // basename only (bsafe)
  "sha256": "<64 hex>",              // content address of the archive bytes
  "size_bytes": 1372240,
  "format": "tar",                  // tar | zip | unknown
  "compression": "gzip",            // none | gzip | bzip2 | xz | unknown
  "policy": { "max_members": 100000, "max_total_bytes": 2147483648,
              "max_ratio": 200, "max_filesize": 1073741824,
              "max_path_bytes": 4000, "max_depth": 64,
              "filename_encoding": "latin-1" },
  "summary": { "members": 1518, "files": 1496, "dirs": 18, "symlinks": 4,
               "hardlinks": 0, "special_files": 0,
               "total_uncompressed_bytes": 0, "max_single_file_bytes": 708405,
               "compression_ratio": "0.00", "max_path_bytes": 80, "max_depth": 6,
               "non_utf8_names": 0, "case_collisions": 0 },
  "wrapper": { "detected": true, "name": "Life1.0/",
               "rule": "single-top-level-directory" },
  "empty_dirs": ["Life1.0/Tests/OUT", "…"],          // get .emptydir markers
  "symlinks": [ { "path": "…", "target": "…", "escapes_root": false } ],
  "non_utf8_names": [ { "path_bsafe": "…", "bytes_hex": "…",
                        "declared_encoding": "latin-1", "decoded": "…" } ],
  "rejections": [ { "code": "EX-SYMLINK-ESCAPE", "family": "ExtractionContractError",
                    "exit_code": 10, "template_id": "tmpl.ex-symlink-escape",
                    "message": "…", "path": "…", "target": "…" } ],
  "accepted": true,                 // false iff any rejection present
  "exit_code": 0                    // mirrors the process exit code
}
```

(For multiple archives the CLI emits `{ "schema": "…", "reports": [ … ] }`.)

## Rejection-rule → error-code map (`errors.py`)

Extraction-contract family (exit **10**):

| code | rule |
|---|---|
| `EX-FORMAT` | not a readable tar/zip; zip central-directory mismatch |
| `EX-ABS` | member path is absolute (`/…`, `C:\…`) |
| `EX-TRAVERSAL` | member path contains a `..` component |
| `EX-SYMLINK-ESCAPE` | symlink target resolves outside root (abs or `..`), or a member is written through a symlinked ancestor |
| `EX-HARDLINK-OUT` | hardlink target is not itself a member of the archive |
| `EX-DEVICE` | char/block device, FIFO, or socket member |
| `EX-DUP` | two members share a byte-identical path |
| `EX-CASE-COLLISION` | distinct paths collide under `casefold(NFC(·))` (csv-contract §7.1) |

Budget family (exit **11**):

| code | rule (default) |
|---|---|
| `BG-MEMBERS` | member count > 100 000 |
| `BG-BYTES` | total uncompressed > 2 GiB |
| `BG-RATIO` | overall compression ratio > 1:200 (decompression bomb) |
| `BG-FILESIZE` | single member > 1 GiB |
| `BG-PATH` | path length > 4000 bytes or depth > 64 |

Exit codes: `0` clean · `10` extraction-contract violation · `11` budget
exceeded · `2` usage · `1` internal. When both an `EX-*` and a `BG-*` fire,
`10` wins (an unsafe path is unsafe regardless of budget).

## Tests

```sh
PYTHONPATH=src python3 -m pytest -q
```

Negative/positive corpus is built **inline** (no committed binaries) pending the
shared `fixtures/negative/` corpus (core-pipeline T1); the real Wild_LIFE
tarballs are consumed read-only from `fixtures/wildlife/tarballs/`.
