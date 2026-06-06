"""Orchestration: PLAN → APPLY with machine-appended journal entries.

The three public verbs the CLI ``swhap build`` wraps:

- ``do_plan`` — render a deterministic ``plan.json`` (no refs touched); journal a
  ``curation-timestamp`` (the canonical D4 store) and a ``plan`` entry.
- ``do_apply`` — re-derive the plan from the workbench, refuse on **plan drift**
  (exit 13 — the HITL guarantee that what the curator inspected is what is built),
  write the history into candidate (or scratch) refs, and journal one ``apply``
  entry listing every commit and annotated tag created (coverage anchor, JC-1).
- ``do_build`` — plan then apply in one pass.

Scratch runs (the D4 rebuild-compare primitive) are deliberately **not** journaled
(journal-schema §4): they are ephemeral verification, produce no curated artifact.
"""

from __future__ import annotations

import hashlib
import json
import os

from ..errors import HistoryError
from ..gitio import GitRunner
from ..journal import Ledger, new_entry, new_ulid
from ..model import CurationTimestamp
from .apply import BuildResult, execute_plan
from .plan import BuildPlan, render
from .source import build_model


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _ledger_for(workbench: str) -> Ledger:
    return Ledger(os.path.join(workbench, "metadata", "journal.jsonl"))


def _ensure_curation_ts(ledger: Ledger, cts: CurationTimestamp) -> str:
    """Append the ``curation-timestamp`` entry once; return its id (the canonical
    D4 store — at most one per acquisition, journal-schema §5.4 step 8)."""
    for e in ledger.read_entries():
        if e.get("action") == "curation-timestamp":
            d = e.get("details", {})
            if d.get("epoch") == cts.epoch and d.get("offset") == cts.offset:
                return e["id"]
            raise HistoryError(
                "a different curation-timestamp is already recorded for this acquisition",
                code="HB-PLAN-DRIFT",
            )
    entry = ledger.append(
        new_entry(
            "curation-timestamp",
            details={
                "epoch": cts.epoch,
                "offset": cts.offset,
                "note": "D4 fixed curation timestamp; committer/tagger date for every rebuild",
            },
        )
    )
    return entry["id"]


def do_plan(
    workbench: str,
    model_name: str,
    curation_ts: CurationTimestamp,
    *,
    plan_out: str | None = None,
    journal: bool = True,
) -> tuple[BuildPlan, bytes]:
    model = build_model(workbench, curation_ts=curation_ts)
    plan = render(model, model_name)
    plan_bytes = plan.to_json_bytes()
    rel = "metadata/plan.json"
    if plan_out:
        with open(plan_out, "wb") as fh:
            fh.write(plan_bytes)
        rel = os.path.relpath(os.path.abspath(plan_out), os.path.abspath(workbench))
    if journal:
        ledger = _ledger_for(workbench)
        ledger.ensure_genesis(os.path.basename(os.path.abspath(workbench)))
        _ensure_curation_ts(ledger, curation_ts)
        ledger.append(
            new_entry(
                "plan",
                outputs=[{"path": rel, "sha256": _sha256(plan_bytes), "size_bytes": len(plan_bytes)}],
            )
        )
    return plan, plan_bytes


def do_apply(
    workbench: str,
    *,
    run_id: str,
    model_name: str | None = None,
    curation_ts: CurationTimestamp | None = None,
    plan_path: str | None = None,
    scratch: bool = False,
    git: GitRunner | None = None,
    journal: bool = True,
) -> tuple[BuildPlan, BuildResult]:
    loaded = None
    if plan_path:
        with open(plan_path, "rb") as fh:
            loaded = json.loads(fh.read())
        ct = loaded["curation_timestamp"]
        curation_ts = CurationTimestamp(int(ct["epoch"]), ct["offset"])
        model_name = loaded["model"]
    if curation_ts is None or model_name is None:
        raise HistoryError(
            "apply needs a curation timestamp and a model (supply --plan, or --curation-epoch + --model)",
            code="HB-PLAN-DRIFT",
        )

    model = build_model(workbench, curation_ts=curation_ts)
    plan = render(model, model_name)
    if loaded is not None and plan.to_json() != loaded:
        raise HistoryError(
            "plan drift: the workbench no longer renders the inspected plan.json",
            code="HB-PLAN-DRIFT",
        )
    plan_bytes = plan.to_json_bytes()

    git = git or GitRunner(workbench)
    result = execute_plan(git, plan, run_id, scratch=scratch)

    if journal and not scratch:
        ledger = _ledger_for(workbench)
        ledger.ensure_genesis(os.path.basename(os.path.abspath(workbench)))
        cid = _ensure_curation_ts(ledger, curation_ts)
        outputs: list[dict] = []
        for c in result.commits:
            obj = {"type": "commit", "git_object": c["commit"]}
            if c["commit"] == result.branch_tip:
                obj["ref"] = result.branch_ref
            outputs.append(obj)
        for t in result.tags:
            outputs.append({"type": "tag", "git_object": t["tag"], "ref": t["tag_ref"]})
        ledger.append(
            new_entry(
                "apply",
                inputs=[{"path": "metadata/plan.json", "sha256": _sha256(plan_bytes)}],
                outputs=outputs,
                details={
                    "model": result.model,
                    "run_id": result.run_id,
                    "curation_ts_entry": cid,
                    "releases": [
                        {"dirname": c["dirname"], "release_tag": t["release_tag"], "commit": c["commit"]}
                        for c, t in zip(result.commits, result.tags)
                    ],
                    "verb": "swhap build",
                },
            )
        )
    return plan, result


def do_build(
    workbench: str,
    model_name: str,
    curation_ts: CurationTimestamp,
    *,
    run_id: str | None = None,
    scratch: bool = False,
    plan_out: str | None = None,
    git: GitRunner | None = None,
    journal: bool = True,
) -> tuple[BuildPlan, BuildResult]:
    run_id = run_id or new_ulid()
    do_plan(workbench, model_name, curation_ts, plan_out=plan_out, journal=journal and not scratch)
    return do_apply(
        workbench,
        run_id=run_id,
        model_name=model_name,
        curation_ts=curation_ts,
        scratch=scratch,
        git=git,
        journal=journal,
    )
