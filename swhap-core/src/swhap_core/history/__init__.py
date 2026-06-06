"""History builder (T7) — bit-reproducible reconstruction of curated Git history.

PLAN (``plan.py``) renders one model-agnostic ``AcquisitionModel`` (``model.py``)
through two backends (Model P orphan purity / Model G source-on-default-branch)
into a deterministic ``BuildPlan``; APPLY (``apply.py``) writes it into candidate
(or scratch) refs via git plumbing with the fixed curation timestamp (D4). The
``build.py`` verbs add machine-appended journal entries.
"""

from __future__ import annotations

from .apply import BuildResult, execute_plan
from .build import do_apply, do_build, do_plan
from .plan import PLAN_SCHEMA, BuildPlan, render, render_g, render_p
from .source import build_model

__all__ = [
    "PLAN_SCHEMA",
    "BuildPlan",
    "BuildResult",
    "build_model",
    "do_apply",
    "do_build",
    "do_plan",
    "execute_plan",
    "render",
    "render_g",
    "render_p",
]
