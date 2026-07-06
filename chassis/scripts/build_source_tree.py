#!/usr/bin/env python3
"""Materialize source_code/<directory name>/ trees from the extraction recipe.

Reads metadata/extraction-recipe.yaml (extraction ONLY — see that file's header)
and calls extract_any.py per source. History/author/date/tag/curator come from
version_history.csv, NOT from here (decision D2).

This is the extraction half of the chassis. The reconstruction half (building the
SourceCode branch, tagging, bit-reproducibly) is the engine's job:
    swhap build --workbench . --model P --apply --curation-epoch <N>

Open seam (tracked as an issue): extraction should eventually move into the
engine as `swhap extract`, so a single validated code path owns wrapper-strip and
.emptydir markers and cannot drift from the trees the validator checks.
"""
import argparse
import pathlib
import shutil
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_recipe(path: pathlib.Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not data or "trees" not in data:
        raise SystemExit("extraction-recipe.yaml must define 'trees:'")
    return data["trees"]


def run_extract(src: pathlib.Path, dest: pathlib.Path, strip) -> None:
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "extract_any.py"),
            "--src", str(src),
            "--dest", str(dest),
            "--strip-components", str(strip if strip is not None else "auto"),
        ],
        check=True,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", default=str(ROOT / "metadata" / "extraction-recipe.yaml"))
    ap.add_argument("--out", default=str(ROOT / "source_code"))
    ap.add_argument("--clean", action="store_true", help="delete output dir first")
    args = ap.parse_args()

    trees = load_recipe(pathlib.Path(args.recipe))
    outdir = pathlib.Path(args.out)
    if args.clean and outdir.exists():
        shutil.rmtree(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    for dirname, sources in trees.items():
        tdir = outdir / str(dirname)
        if tdir.exists():
            shutil.rmtree(tdir)
        tdir.mkdir(parents=True, exist_ok=True)
        for src in sources or []:
            run_extract(ROOT / src["path"], tdir, src.get("strip_components", "auto"))

    print(f"Built {len(trees)} tree(s) into {outdir}")


if __name__ == "__main__":
    main()
