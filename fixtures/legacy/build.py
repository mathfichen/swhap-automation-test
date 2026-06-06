#!/usr/bin/env python3
"""Deterministic generator for the LEGACY-AUDIT fixture workbenches (AX5 / T10).

These fixtures make the legacy-profile precision audit **CI-reproducible**. The
original AX5 audit was run once, live, against two REAL published acquisitions
that exist only in ephemeral ``/tmp`` (see ``README.md`` for the mapping); the
"3 false failures -> 0 after FIX-1/FIX-2, genuine defects preserved" evidence
therefore could not be re-run from a clean checkout. This module rebuilds the two
defect **shapes** as SYNTHETIC, license-clean git workbenches (NOT copies of the
third-party repos), so the e2e harness (``tools/validator/tests/
test_legacy_audit_e2e.py``) can re-derive the same precision result in the normal
pytest suite.

Two shapes, each a self-contained git repo:

* **unipisa-cmm** (stands in for Unipisa/CMM-Workbench, the wrapper-directory
  defect case): a legacy ``version_history.csv`` in the **unipisa** dialect
  (non-canonical header, ``*`` tag, ``|`` message separators, US slash date) and
  a ``codemeta.json`` at the **repo root** (NOT ``metadata/``). Both were FALSE
  failures before FIX-1 (CSV-1) / FIX-2 (CM-1) and must now pass under the legacy
  profile. It ALSO carries a *genuine* defect: a ``SourceCode`` release whose
  tree is a single artificial top-level wrapper directory -> a real BP-5 that the
  legacy profile must still surface (severity FAIL, ``enforced: false``).

* **guide-chainage** (stands in for mathfichen/chainage_de_contour, the
  non-canonical-CSV-dialect case): a legacy ``version_history.csv`` in the
  **guide** dialect (``date original`` header). The dialect was a FALSE CSV-1
  before FIX-1 and must now pass under legacy. It ALSO carries a *genuine* defect:
  a root ``codemeta.json`` with a bogus ``@context`` -> a real CM-2 the legacy
  profile must still surface (a bogus context is a true defect, validator-report
  §2.3/§4.2). This proves the legacy tolerance is NOT a blanket suppression.

Determinism law (so the pinned tree SHAs are stable across machines/runs):

* All file content is fixed bytes (no wall-clock, no host data).
* Commits use a fixed author/committer identity + fixed dates (``_ENV``); git
  tree object hashes depend only on content + mode + name, so the pinned MANIFEST
  records the **tree SHAs** (date-independent) for a robust reproducibility gate.
* The workbenches are rebuilt fresh into a caller-supplied directory (the test
  uses a tmp dir); nothing binary is committed to the repo.

Run ``python build.py`` to print the fixtures' tree SHAs and (re)write
``index.json`` + ``MANIFEST.sha256``. ``python build.py --check`` rebuilds twice
into temp dirs and verifies the tree SHAs are byte-stable and match the pinned
MANIFEST (the CI reproducibility gate).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "MANIFEST.sha256")
INDEX = os.path.join(HERE, "index.json")

# Fixed identities/dates for D4 determinism (commit hashes reproducible; tree
# hashes are date-independent anyway).
_ENV = {
    "GIT_AUTHOR_NAME": "Legacy Authors",
    "GIT_AUTHOR_EMAIL": "legacy-authors@noreply.example.org",
    "GIT_AUTHOR_DATE": "1994-07-11T00:00:00+0000",
    "GIT_COMMITTER_NAME": "Example Curator",
    "GIT_COMMITTER_EMAIL": "example-curator@noreply.example.org",
    "GIT_COMMITTER_DATE": "2026-06-06T00:00:00+0000",
}

# A valid, SWH-accepted CodeMeta 2.0 context (the tolerated root-codemeta case).
_GOOD_CODEMETA = (
    '{\n'
    '  "@context": "https://doi.org/10.5063/schema/codemeta-2.0",\n'
    '  "@type": "SoftwareSourceCode",\n'
    '  "name": "CMM (synthetic legacy fixture)"\n'
    '}\n'
).encode("utf-8")

# A valid JSON codemeta whose @context SWH does not recognize -> genuine CM-2.
_BOGUS_CODEMETA = (
    '{\n'
    '  "@context": "https://not-a-real-context.example/v9",\n'
    '  "@type": "SoftwareSourceCode",\n'
    '  "name": "chainage (synthetic legacy fixture)"\n'
    '}\n'
).encode("utf-8")

# --- legacy CSV dialects (csv-contract §11) -------------------------------- #
# unipisa: non-canonical header, `*` tag (-> derived from dir), `|` message
# separators, ambiguous US MM/DD slash date. All tolerated under legacy.
_UNIPISA_CSV = (
    "directory name,author name,author email,date,"
    "curator name,curator email,release tag,commit message\n"
    "1.0,CMM Authors,cmm-authors@noreply.example.org,11/07/1994 17:36:34,"
    "CMM Curation Team,example-curator@noreply.example.org,*,"
    '"|Initial release| - synthetic fixture"\n'
).encode("utf-8")

# guide: the `date original` header dialect (mathfichen/chainage shape).
_GUIDE_CSV = (
    "directory name,author name,author email,date original,"
    "curator name,curator email,release tag,commit message\n"
    "1.0,Chainage Authors,chainage-authors@noreply.example.org,1998-05-04,"
    "Example Curator,example-curator@noreply.example.org,1.0,"
    "initial synthetic release\n"
).encode("utf-8")


def _git(repo, *args, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    subprocess.run(["git", "-C", repo, *args], check=True, env=e,
                   capture_output=True)


def _write(repo, rel, content: bytes):
    full = os.path.join(repo, rel)
    os.makedirs(os.path.dirname(full) or repo, exist_ok=True)
    with open(full, "wb") as fh:
        fh.write(content)


def _init(repo):
    os.makedirs(repo, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")


def _tree_sha(repo, ref) -> str:
    out = subprocess.run(["git", "-C", repo, "rev-parse", f"{ref}^{{tree}}"],
                         check=True, capture_output=True, text=True)
    return out.stdout.strip()


# --------------------------------------------------------------------------- #
# Shape A: unipisa-cmm — tolerated unipisa CSV + root codemeta; genuine BP-5.   #
# --------------------------------------------------------------------------- #
def build_unipisa_cmm(dest: str) -> str:
    _init(dest)
    # main: README + legacy unipisa CSV + ROOT codemeta (no metadata/codemeta).
    _write(dest, "README.md", b"# CMM workbench (synthetic legacy fixture)\n")
    _write(dest, "metadata/version_history.csv", _UNIPISA_CSV)
    _write(dest, "codemeta.json", _GOOD_CODEMETA)  # ROOT, not metadata/
    _write(dest, "raw_materials/cmm-1.0.txt",
           b"synthetic placeholder for the original CMM 1.0 archive\n")
    _git(dest, "add", "-A", env=_ENV)
    _git(dest, "commit", "-q", "-m", "CMM workbench", env=_ENV)

    # SourceCode orphan: one release commit whose tree is a SINGLE artificial
    # top-level wrapper directory `CMM1.0/` -> genuine BP-5 (never stripped).
    _git(dest, "checkout", "-q", "--orphan", "SourceCode")
    _git(dest, "rm", "-rf", "-q", ".")
    _write(dest, "CMM1.0/main.c", b"int main(void){return 0;}\n")
    _write(dest, "CMM1.0/README", b"CMM 1.0 sources (synthetic)\n")
    _git(dest, "add", "-A", env=_ENV)
    _git(dest, "commit", "-q", "-m", "CMM 1.0 (reconstructed)", env=_ENV)
    _git(dest, "tag", "-a", "1.0", "-m", "Version 1.0", env=_ENV)

    _git(dest, "checkout", "-q", "main")
    return dest


# --------------------------------------------------------------------------- #
# Shape B: guide-chainage — tolerated guide CSV; genuine CM-2 (bogus @context). #
# --------------------------------------------------------------------------- #
def build_guide_chainage(dest: str) -> str:
    _init(dest)
    _write(dest, "README.md",
           b"# chainage_de_contour workbench (synthetic legacy fixture)\n")
    _write(dest, "metadata/version_history.csv", _GUIDE_CSV)
    _write(dest, "codemeta.json", _BOGUS_CODEMETA)  # ROOT, bogus @context
    _write(dest, "raw_materials/chainage-1.0.txt",
           b"synthetic placeholder for the original chainage 1.0 archive\n")
    _git(dest, "add", "-A", env=_ENV)
    _git(dest, "commit", "-q", "-m", "chainage workbench", env=_ENV)
    return dest


# (name, builder, stands_for, real_repo, tolerated, genuine, note)
FIXTURES = [
    (
        "unipisa-cmm", build_unipisa_cmm,
        "wrapper-directory defect case",
        "Unipisa/CMM-Workbench",
        ["CSV-1 (unipisa legacy CSV dialect)",
         "CM-1 (codemeta.json at repo root, not metadata/)"],
        ["BP-5 (artificial top-level wrapper directory in the release tree)"],
        "Tolerated dialects were the FALSE CSV-1/CM-1 before FIX-1/FIX-2; the "
        "wrapper directory is a genuine BP-5 the legacy profile must still "
        "surface (FAIL severity, enforced:false).",
    ),
    (
        "guide-chainage", build_guide_chainage,
        "non-canonical-CSV-dialect case",
        "mathfichen/chainage_de_contour",
        ["CSV-1 (guide `date original` legacy CSV dialect)"],
        ["CM-2 (root codemeta.json with an @context SWH does not accept)"],
        "The guide dialect was a FALSE CSV-1 before FIX-1; the bogus @context is "
        "a genuine CM-2 the legacy profile must still surface — proving the "
        "tolerance is dialect-scoped, not a blanket suppression.",
    ),
]


def build_all(root: str) -> "dict[str, str]":
    """Build every fixture into ``root/<name>`` and return {name: SourceCode-or-
    main tree SHA} — the date-independent reproducibility fingerprint."""
    os.makedirs(root, exist_ok=True)
    out = {}
    for name, builder, *_ in FIXTURES:
        repo = builder(os.path.join(root, name))
        # Fingerprint the most defect-bearing tree: SourceCode tag tree when a
        # release exists, else the main tree.
        ref = "1.0" if name == "unipisa-cmm" else "main"
        out[name] = _tree_sha(repo, ref)
    return out


def write_manifest(sums: "dict[str, str]") -> None:
    with open(MANIFEST, "w", encoding="utf-8") as fh:
        for name, _b, *_ in FIXTURES:
            fh.write(f"{sums[name]}  {name}\n")


def write_index(sums: "dict[str, str]") -> None:
    doc = {
        "schema": "swhap-legacy-audit-corpus/1",
        "description": (
            "Synthetic, license-clean legacy-workbench fixtures that reproduce "
            "the AX5 / T10 legacy-profile precision-audit defect SHAPES (not "
            "copies of the third-party repos). Each maps to a real published "
            "acquisition the live audit targeted; see README.md."),
        "tree_sha_algo": "git-sha1-tree (date-independent)",
        "fixtures": [
            {
                "name": name,
                "stands_for": stands_for,
                "real_repo": real_repo,
                "tree_sha": sums[name],
                "tolerated_dialects": tolerated,
                "genuine_defects": genuine,
                "note": note,
            }
            for (name, _b, stands_for, real_repo, tolerated, genuine, note)
            in FIXTURES
        ],
    }
    with open(INDEX, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True, ensure_ascii=False)
        fh.write("\n")


def cmd_check() -> int:
    if not os.path.exists(MANIFEST):
        print("MANIFEST.sha256 absent — run 'python build.py' first",
              file=sys.stderr)
        return 1
    pinned = {}
    with open(MANIFEST, encoding="utf-8") as fh:
        for ln in fh:
            sha, name = ln.split()
            pinned[name] = sha
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        s1 = build_all(a)
        s2 = build_all(b)
    if s1 != s2:
        print(f"NON-DETERMINISTIC: {s1} != {s2}", file=sys.stderr)
        return 1
    bad = [n for n in s1 if s1[n] != pinned.get(n)]
    missing = [n for n in pinned if n not in s1]
    if bad or missing:
        for n in bad:
            print(f"DRIFT {n}: {s1[n]} != pinned {pinned.get(n)}", file=sys.stderr)
        for n in missing:
            print(f"MISSING {n}", file=sys.stderr)
        return 1
    print(f"[build] OK — {len(s1)} legacy fixtures reproduce the pinned MANIFEST")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Build the legacy-audit fixture workbenches.")
    ap.add_argument("--check", action="store_true",
                    help="rebuild twice into temp dirs and verify determinism "
                         "and the pinned MANIFEST")
    args = ap.parse_args(argv)
    if args.check:
        return cmd_check()
    with tempfile.TemporaryDirectory() as tmp:
        sums = build_all(tmp)
    write_manifest(sums)
    write_index(sums)
    for name, _b, *_ in FIXTURES:
        print(f"[build] {sums[name][:12]}  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
