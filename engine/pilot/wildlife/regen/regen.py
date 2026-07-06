#!/usr/bin/env python3
"""Deterministic Model-P regeneration of the Wild_LIFE SWHAP workbench.

Exemplar-pilot T11 (M1 exit gate). Reproducible FROM COMMITTED INPUTS — this
script and the files alongside it (``version_history.csv``, ``codemeta.json``,
``curation-manifest.json``, ``manifests/1.02.json``) plus the byte-frozen
release tarballs under ``fixtures/wildlife/tarballs/`` are the only inputs. No
network, no /tmp dependency, no wall-clock in the hashed objects.

Pipeline (single command, into a given output dir):

  acquire   verify the four committed release tarballs against the sha256s
            pinned in curation-manifest.json (the "acquired bundle")
  extract   read-only extraction with a hardened tar filter (stdlib ``data``
            filter for regular members; symlinks re-emitted verbatim and NEVER
            followed; nothing is ever executed) + wrapper-strip
  curate    per the manifest: 1.02 AppleDouble exclusion, symlink preservation,
            documented perm flattening; assert the ratified expected counts
  metadata  copy the canonical CSV + codemeta, seed the journal from the
            manifest's six CURATOR-APPROVED decisions (the ledger is a pure
            function of the committed manifest)
  build     swhap build --model P --apply (do_build): orphan SourceCode source
            history, one commit + one annotated tag per release, D4-reproducible
  materialize  the validator's published layout in a separate repo (main =
            Depository, SourceCode = orphan source, v<rel> tags) so the build's
            ref-policy guard is never touched
  oracles   manifests-validation/ = frozen 0.90/0.91/1.0 fixture oracles +
            committed derived 1.02 oracle

Run: ``python3 regen.py OUTDIR``  (stdlib + swhap_core only).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile

from swhap_core import vhcsv
from swhap_core.history import do_build
from swhap_core.journal import Ledger, new_entry
from swhap_core.model import CurationTimestamp

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLKIT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
TARBALLS = os.path.join(TOOLKIT, "fixtures", "wildlife", "tarballs")
FIXTURE_MANIFESTS = os.path.join(TOOLKIT, "fixtures", "wildlife", "manifests")

MANIFEST = os.path.join(HERE, "curation-manifest.json")
CSV_INPUT = os.path.join(HERE, "version_history.csv")
CODEMETA_INPUT = os.path.join(HERE, "codemeta.json")
DERIVED_102 = os.path.join(HERE, "manifests", "1.02.json")

# Frozen fixture oracles for the three uncurated releases (tarball-derived,
# independent provenance). The 1.02 oracle is the committed derived manifest.
FROZEN_ORACLES = ("0.90", "0.91", "1.0")


# --------------------------------------------------------------------------- #
# hardened, read-only extraction
# --------------------------------------------------------------------------- #
def _safe_filter(member, path):
    """Apply the stdlib ``data`` filter to regular members (path-traversal /
    device / setuid protection). Symlinks are re-emitted verbatim with the
    ownership/mode noise stripped: the ``data`` filter REJECTS absolute / escaping
    link targets, but our ratified curatorial policy PRESERVES them as documented
    broken-link artifacts (a 120000 blob = the link bytes; never dereferenced)."""
    if member.issym():
        m = member.replace(deep=False)
        m.mode = 0o777
        m.uid = m.gid = 0
        m.uname = m.gname = ""
        return m
    return tarfile.data_filter(member, path)


def _extract_strip(tarball, dest):
    """Read-only extract + wrapper-strip. Returns (wrapper_root, top_entries)."""
    with tarfile.open(os.path.join(TARBALLS, tarball)) as t:
        t.extractall(dest, filter=_safe_filter)
    tops = list(os.listdir(dest))
    real = [n for n in tops if not n.startswith("._")]
    if len(real) != 1:
        raise SystemExit(f"{tarball}: expected one wrapper dir, got {real}")
    return os.path.join(dest, real[0]), tops


def _curate_appledouble(root):
    """Remove every AppleDouble ._* companion under the tree. Returns the count."""
    removed = 0
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in list(filenames):
            if fn.startswith("._"):
                os.remove(os.path.join(dirpath, fn))
                removed += 1
        for dn in list(dirnames):
            if dn.startswith("._"):
                full = os.path.join(dirpath, dn)
                if not os.path.islink(full):
                    shutil.rmtree(full)
                    removed += 1
                    dirnames.remove(dn)
    return removed


def _census_symlinks(root):
    """Classify symlinks: absolute-target (escape) vs relative (in-tree)."""
    absolute, relative = [], []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in list(_dirnames) + filenames:
            full = os.path.join(dirpath, name)
            if os.path.islink(full):
                tgt = os.readlink(full)
                rel = os.path.relpath(full, root).replace(os.sep, "/")
                (absolute if tgt.startswith("/") else relative).append((rel, tgt))
    return sorted(absolute), sorted(relative)


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# pipeline stages
# --------------------------------------------------------------------------- #
def acquire(manifest):
    """Verify the four committed tarballs against the manifest sha256s."""
    for rel in manifest["releases"]:
        path = os.path.join(TARBALLS, rel["tarball"])
        got = _sha256(path)
        if got != rel["sha256"]:
            raise SystemExit(f"acquire: {rel['tarball']} sha256 {got} != "
                             f"pinned {rel['sha256']}")


def stage_source(workbench, manifest):
    """Extract + wrapper-strip + curate every release into source_code/<dir>/.
    Asserts the ratified expected counts. Returns a curation report dict."""
    sc = os.path.join(workbench, "source_code")
    tmp = os.path.join(workbench, ".extract")
    report = {}
    for rel in manifest["releases"]:
        name = rel["directory_name"]
        d = os.path.join(tmp, "x" + name)
        os.makedirs(d, exist_ok=True)
        wroot, tops = _extract_strip(rel["tarball"], d)
        rep = {"wrapper": os.path.basename(wroot) + "/"}
        if rel["curate"].get("exclude_appledouble"):
            removed = _curate_appledouble(wroot)
            stray = [n for n in tops if n.startswith("._")]
            for s in stray:
                p = os.path.join(d, s)
                if os.path.isfile(p) or os.path.islink(p):
                    os.remove(p)
                    removed += 1
            absolute, relative = _census_symlinks(wroot)
            rep.update(appledouble_removed=removed, stray_removed=stray,
                       abs_symlinks=[{"path": p, "target": t} for p, t in absolute],
                       rel_symlink_count=len(relative))
            _assert_expected(name, rep, rel["expected"])
        target = os.path.join(sc, name)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.move(wroot, target)
        report[name] = rep
    shutil.rmtree(tmp, ignore_errors=True)
    return report


def _assert_expected(name, rep, expected):
    if not expected:
        return
    exp_total = expected["appledouble_removed"] + len(expected["stray_removed"])
    if rep["appledouble_removed"] != exp_total:
        raise SystemExit(f"{name}: appledouble removed {rep['appledouble_removed']}"
                         f" != expected {exp_total}")
    if rep["rel_symlink_count"] != expected["rel_symlink_count"]:
        raise SystemExit(f"{name}: rel symlinks {rep['rel_symlink_count']} != "
                         f"expected {expected['rel_symlink_count']}")
    got_abs = sorted((s["path"], s["target"]) for s in rep["abs_symlinks"])
    exp_abs = sorted((s["path"], s["target"]) for s in expected["abs_symlinks"])
    if got_abs != exp_abs:
        raise SystemExit(f"{name}: absolute symlinks {got_abs} != expected {exp_abs}")


def write_metadata(workbench, manifest):
    """Copy the canonical (authoritative) CSV + codemeta; write README. The CSV
    is self-checked against the canonical vhcsv profile (FAIL-free required)."""
    md = os.path.join(workbench, "metadata")
    os.makedirs(md, exist_ok=True)
    with open(CSV_INPUT, "rb") as fh:
        csv_bytes = fh.read()
    vhcsv.parse(csv_bytes, profile="canonical").raise_on_fail()
    with open(os.path.join(md, "version_history.csv"), "wb") as fh:
        fh.write(csv_bytes)
    shutil.copy(CODEMETA_INPUT, os.path.join(md, "codemeta.json"))
    with open(os.path.join(workbench, "README.md"), "w", encoding="utf-8") as fh:
        fh.write("# Wild_LIFE — SWHAP acquisition workbench\n\n"
                 "Regenerated through the SWHAP Layer-1 pipeline (Model P, brief "
                 "§9). The reconstructed source history lives on the orphan "
                 "`SourceCode` branch with one annotated tag per release; `main` "
                 "(the Depository) holds only metadata + raw materials.\n")


def _curator_actor():
    # journal-schema $defs.actor: kind/name/tool/version, additionalProperties:false
    return {"kind": "curator", "name": "Roberto Di Cosmo",
            "tool": "swhap-curator-cli", "version": "m1-finalize"}


def seed_journal(workbench, manifest):
    """Seed the ledger from the manifest's CURATOR-APPROVED decisions + the
    author-identity provenance. The build appends genesis-adjacent build entries
    (curation-timestamp / plan / apply) idempotently after."""
    ledger = Ledger(os.path.join(workbench, "metadata", "journal.jsonl"))
    ledger.ensure_genesis(os.path.basename(os.path.abspath(workbench)))
    rat = manifest["ratification"]
    for spec in manifest["decisions"] + manifest["provenance"]:
        tr = spec["provenance_transition"]
        details = dict(spec["details"])
        details.setdefault("decision_id", spec["id"])
        details.setdefault("summary", spec["summary"])
        if tr["to"] == "curator-approved":
            details["ratification"] = {
                "ratified": True, "by": rat["by"], "on": rat["on"],
                "ref": rat["ref"]}
        ledger.append(new_entry(
            "provenance-transition",
            actor=_curator_actor(),
            provenance_transitions=[{"item": tr["item"], "from": tr["from"],
                                     "to": tr["to"]}],
            details=details,
        ))
    return ledger


def _append_apply_objects(ledger, result, model):
    """Apply entry covering every commit+tag object (JC-1a coverage)."""
    outputs = [{"type": "commit", "git_object": c["commit"]} for c in result.commits]
    outputs += [{"type": "tag", "git_object": t["tag"]} for t in result.tags]
    ledger.append(new_entry(
        "apply",
        details={"model": model, "run_id": result.run_id,
                 "note": f"Model {model} candidate build object coverage."},
        outputs=outputs,
    ))


# --------------------------------------------------------------------------- #
# materialize the validator's published layout (argv-only git)
# --------------------------------------------------------------------------- #
def _git(repo, *args, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run(["git", "-C", repo, *args], check=True, env=e,
                          capture_output=True).stdout


def materialize_p(out_dir, workbench, result, manifest):
    """Build main (Depository) + SourceCode (orphan) + v<rel> tags pointing at
    the already-built candidate objects (no rebuild; D4 intact)."""
    ts = manifest["curation_timestamp"]
    env = {k: v for pair in (
        ("GIT_AUTHOR_NAME", manifest["curator"]["name"]),
        ("GIT_AUTHOR_EMAIL", manifest["curator"]["email"]),
        ("GIT_AUTHOR_DATE", f"{ts['epoch']} {ts['offset']}"),
        ("GIT_COMMITTER_NAME", manifest["curator"]["name"]),
        ("GIT_COMMITTER_EMAIL", manifest["curator"]["email"]),
        ("GIT_COMMITTER_DATE", f"{ts['epoch']} {ts['offset']}"),
    ) for k, v in (pair,)}

    dest = os.path.join(out_dir, "validate-P")
    if os.path.exists(dest):
        shutil.rmtree(dest)
    os.makedirs(dest)
    _git(dest, "init", "-q", "-b", "main")
    _git(dest, "fetch", "-q", workbench,
         "refs/heads/candidate/*:refs/candsrc/heads/*",
         "refs/tags/candidate/*:refs/candsrc/tags/*")
    # SourceCode -> candidate P branch tip
    _git(dest, "update-ref", "refs/heads/SourceCode", result.branch_tip)
    # v<rel> tags -> verbatim candidate annotated-tag objects
    for t in result.tags:
        _git(dest, "update-ref", f"refs/tags/{t['release_tag']}", t["tag"])
    # main = Depository (README + metadata + raw_materials + scripts)
    _build_depository_main(dest, workbench, manifest, env)
    _git(dest, "symbolic-ref", "HEAD", "refs/heads/main")
    return dest


def _build_depository_main(dest, workbench, manifest, env):
    shutil.copy(os.path.join(workbench, "README.md"),
                os.path.join(dest, "README.md"))
    md = os.path.join(dest, "metadata")
    os.makedirs(md)
    for f in ("version_history.csv", "codemeta.json", "journal.jsonl"):
        shutil.copy(os.path.join(workbench, "metadata", f), os.path.join(md, f))
    rm = os.path.join(dest, "raw_materials")
    os.makedirs(rm)
    for rel in manifest["releases"]:
        shutil.copy(os.path.join(TARBALLS, rel["tarball"]),
                    os.path.join(rm, rel["tarball"]))
    scripts = os.path.join(dest, "scripts")
    os.makedirs(scripts)
    with open(os.path.join(scripts, "regenerate.sh"), "w", encoding="utf-8") as fh:
        fh.write("#!/usr/bin/env bash\n"
                 "# Regeneration entrypoint — see pilot/wildlife/regen/runbook.md\n"
                 "exec python3 pilot/wildlife/regen/regen.py \"$@\"\n")
    _git(dest, "add", "-A", env=env)
    _git(dest, "commit", "-q", "-m",
         "Wild_LIFE Depository (metadata + raw_materials)", env=env)


def build_oracles(out_dir):
    """manifests-validation/ = frozen 0.90/0.91/1.0 + committed derived 1.02."""
    out = os.path.join(out_dir, "manifests-validation")
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    for rel in FROZEN_ORACLES:
        shutil.copy(os.path.join(FIXTURE_MANIFESTS, f"{rel}.json"),
                    os.path.join(out, f"{rel}.json"))
    shutil.copy(DERIVED_102, os.path.join(out, "1.02.json"))
    return out


# --------------------------------------------------------------------------- #
# driver
# --------------------------------------------------------------------------- #
def regen(out_dir, *, verbose=False):
    """Rebuild the Model-P workbench + validation view into ``out_dir``.
    Returns a dict with paths and the commit/tag SHAs (for D4 checks)."""
    def log(*a):
        if verbose:
            print(*a)

    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    ts = manifest["curation_timestamp"]
    curation = CurationTimestamp(ts["epoch"], ts["offset"])
    run_id = manifest["build"]["run_id"]

    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    workbench = os.path.join(out_dir, "Wild_Life-swhap-regen")
    if os.path.exists(workbench):
        shutil.rmtree(workbench)
    os.makedirs(workbench)

    log("== acquire (verify committed tarballs) ==")
    acquire(manifest)

    log("== extract + wrapper-strip + curate ==")
    subprocess.run(["git", "init", "-q", workbench], check=True)
    curation_report = stage_source(workbench, manifest)

    log("== metadata (canonical CSV + codemeta) ==")
    write_metadata(workbench, manifest)

    log("== seed curatorial journal (6 curator-approved decisions) ==")
    ledger = seed_journal(workbench, manifest)

    log("== build Model P (swhap build --model P --apply) ==")
    _, result = do_build(workbench, manifest["build"]["model"], curation,
                         run_id=run_id)
    _append_apply_objects(ledger, result, manifest["build"]["model"])
    ledger.verify()

    log("== materialize main + SourceCode + tags ==")
    validate_p = materialize_p(out_dir, workbench, result, manifest)

    log("== build TF oracles (manifests-validation) ==")
    manifests_dir = build_oracles(out_dir)

    info = {
        "out_dir": out_dir,
        "workbench": workbench,
        "validate_p": validate_p,
        "manifests": manifests_dir,
        "curation_epoch": ts["epoch"],
        "curation_offset": ts["offset"],
        "reference_date": ts["iso"],
        "model": result.model,
        "run_id": result.run_id,
        "branch_tip": result.branch_tip,
        "commit_oids": [c["commit"] for c in result.commits],
        "tag_oids": [t["tag"] for t in result.tags],
        "release_tags": [t["release_tag"] for t in result.tags],
        "curation_report": curation_report,
    }
    with open(os.path.join(out_dir, "build-result.json"), "w",
              encoding="utf-8") as fh:
        json.dump(info, fh, indent=2)
    log("== regen complete ==")
    return info


def main(argv=None):
    ap = argparse.ArgumentParser(description="Regenerate the Model-P Wild_LIFE "
                                 "SWHAP workbench from committed inputs.")
    ap.add_argument("out_dir", help="output directory (created if absent)")
    ap.add_argument("-q", "--quiet", action="store_true")
    ns = ap.parse_args(argv)
    info = regen(ns.out_dir, verbose=not ns.quiet)
    print(json.dumps({k: info[k] for k in (
        "branch_tip", "commit_oids", "tag_oids", "release_tags",
        "validate_p", "manifests", "reference_date")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
