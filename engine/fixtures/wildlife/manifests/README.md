# Wild_LIFE ground-truth tree manifests — `swhap-tree-manifest/1`

These JSON documents are **the** oracle the validator's tree-fidelity (`TF-*`)
checks compare a reconstructed `SourceCode` release tree against (C4 battery;
validator consumes them per exemplar-pilot.md §3.1 / §4.1). One document per
release:

| File | Release | Tarball | Role |
|---|---|---|---|
| `0.90.json` | 0.90 | `life_090.tgz` | clean TF oracle (byte-perfect, the all-green fixture) |
| `0.91.json` | 0.91 | `life_091.tgz` | clean TF oracle |
| `1.0.json`  | 1.0  | `life_10.tgz`  | clean TF oracle (symlinks + empty dirs) |
| `1.02.json` | 1.02 | `Life1.02Ultrix.tar` | **quarantined census** (`quarantined: true`) — NOT a clean oracle; see `anomalies` and `1.02-date-evidence.md` |

Regenerate with `python ../mk_manifest.py` (read-only census of the pinned
tarballs; deterministic — a rebuild is byte-identical). Counts are asserted
against `analysis/corpus/followup-2.md` at generation time (fail-loud on drift).

## Document shape (normative for the validator slice)

Top level (all keys present):

| Key | Type | Meaning |
|---|---|---|
| `schema` | string | const `"swhap-tree-manifest/1"` |
| `release` | string | release id (`"0.90"`, `"1.02"`, …) |
| `tarball` | string | source tarball filename under `fixtures/wildlife/tarballs/` |
| `tarball_sha256` | string (64 hex) | sha256 of the source tarball (matches `tarballs.sha256`) |
| `wrapper` | string \| null | the artificial top-level directory stripped from every path (e.g. `"Life1.0/"`); `null` if none/ambiguous |
| `quarantined` | bool | `true` ⇒ census only, do not use as a TF pass/fail oracle |
| `counts` | object | `{files, symlinks, empty_dirs, entries}` where `entries == files + symlinks` |
| `empty_dirs` | string[] | wrapper-stripped POSIX paths of directories empty after extraction; each needs a `.emptydir` marker (sorted byte-wise) |
| `symlinks` | object[] | `{path, target}` summary of every symlink (sorted by `path`) |
| `entries` | object[] | the full per-path table (files **and** symlinks), sorted byte-wise by `path` |
| `generator` | object | `{tool, schema}` provenance |
| `anomalies` | object[] | **quarantined manifests only** — crit-M6 defects (see below) |

### `entries[]` — the per-path table

Sorted byte-wise by `path`. Each entry:

| Key | Present | Meaning |
|---|---|---|
| `path` | always | wrapper-stripped POSIX path. The original bytes; surrogate-safe display when not UTF-8 (then `path_bytes_hex` is the authority). |
| `path_bytes_hex` | only if `path` is not valid UTF-8 | hex of the raw path bytes (lossless authority; the Wild_LIFE releases have none) |
| `type` | always | `"file"` or `"symlink"` |
| `mode` | always | git mode: `"100644"` / `"100755"` for files (exec bit → 755), `"120000"` for symlinks |
| `sha256` | always | for a file: sha256 of the file content; for a symlink: sha256 of the **target string bytes** |
| `git_blob_sha1` | always | the git blob object id (`git hash-object`) of the same bytes — lets `TF-*` compare **directly** against `git ls-tree -r <tag>` on a SHA-1 git repo, no `cat-file` needed |
| `target` | symlinks only | the symlink target string (verbatim) |

Two content hashes are provided on purpose:

* **`git_blob_sha1`** is the cheapest TF oracle: `git ls-tree -r <tag>` yields
  `<mode> blob <git_blob_sha1>\t<path>`, so path-set + blob-id equality is a
  direct join against `entries[]` with no extraction of the candidate tree.
* **`sha256`** is the hash-algorithm-independent authority: a SHA-256 git repo,
  or a validator that prefers `git cat-file blob <id> | sha256sum`, joins on
  this. Both are computed from identical bytes, so they never disagree about a
  path's content.

### How `TF-*` is expected to use a clean manifest

1. **TF path-set equality** — the set of `entries[].path` MUST equal the set of
   non-`.emptydir` paths in `git ls-tree -r <tag>` (wrapper already stripped in
   the manifest). Extra git paths = previous-version leak (the
   `RED-v091-extras` / `RED-v10-extras` defects, followup-2 §2–3).
2. **TF blob equality** — for each shared path, `git_blob_sha1` MUST equal the
   git tree blob id (catches the stale `LICENSE` / `RED-v10-license-stale` and
   the v0.91 stale blobs).
3. **TF mode** — `mode` MUST match (`120000` symlinks, `100755` exec files).
4. **TF symlink** — `symlinks[]` count/target MUST match the `120000` blobs
   whose content is the target string.
5. **TF emptydir bijection** — `.emptydir` markers in the tag MUST be in
   bijection with `empty_dirs` (validator TF-4, implemented independently of
   the generator's self-check — core-pipeline §3.3 ruling 3).

### `anomalies[]` — quarantined manifests only

`1.02.json` carries `quarantined: true` and an `anomalies[]` register; it is a
census, not a pass/fail oracle. Each anomaly: `{class, detail, expected_check}`
(+ optional `members`). For 1.02 they are: `macos-appledouble` (257 `._*`
companion files), `stray-top-level` (`._Life1.02Ultrix` sibling to the
wrapper), `symlink-escape-absolute` (4 symlinks targeting absolute paths off
the root), and `perm-bits` (all files 0o777 → git 100755). The release date
question is settled separately in `1.02-date-evidence.md` (Q9 year-only input).
