"""PC-* — environment & clone-shape preconditions (crit-M8).

A PC-* FAIL ⇒ exit 4 (shallow clone is 4, not 2): results computed over a bad
clone are not trustworthy, so the battery beyond preflight is not executed.
M1a implements PC-1 (shallow-clone detection); the version probes are M3.
"""
from __future__ import annotations

import os

from ..report import FAIL, Finding


def run(report, ctx) -> bool:
    """Return True if preconditions hold (battery may proceed)."""
    report.ran("PC-1")
    if os.path.exists(os.path.join(ctx.repo, ".git", "shallow")) or \
            os.path.exists(os.path.join(ctx.repo, "shallow")):
        report.add(Finding(
            "PC-1", FAIL, {"repo": "."}, ["repo"],
            "This is a shallow clone; the full history is needed to validate. "
            "Re-clone with full history (no --depth).",
            message_technical="PC-1: .git/shallow present",
            required_approver_role="none",
            remediation="git fetch --unshallow, or clone without --depth.",
        ))
        return False
    return True
