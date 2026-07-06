"""Profile matrix (validator-report §4.2 / validator plan §4.2) as data.

Determines, per profile, which check families enforce vs report-only vs skip,
and the strict-P/strict-G branch model. The enforcement flag is what makes the
legacy 'report-only' representation truthful (§2.4): severity states the truth
about the artifact, `enforced` the truth about the run's posture.
"""
from __future__ import annotations

STRICT_P = "strict-P"
STRICT_G = "strict-G"
LEGACY = "legacy"

PROFILES = (STRICT_P, STRICT_G, LEGACY)

# Families that run report-only (enforced=False) in the legacy audit profile.
_LEGACY_REPORT_ONLY = {"TF", "BP", "CSV", "CM", "SZ", "PI"}
# Families skipped entirely in legacy (no generator inputs / no ledger).
_LEGACY_SKIPPED = {"RB", "DV", "JC", "LG"}


def family(check_id: str) -> str:
    return check_id.split("-", 1)[0]


def is_skipped(profile: str, check_id: str) -> bool:
    if profile == LEGACY and family(check_id) in _LEGACY_SKIPPED:
        return True
    return False


def is_enforced(profile: str, check_id: str) -> bool:
    """PC-* stays enforced in every profile (validator-report §4.2)."""
    fam = family(check_id)
    if fam == "PC":
        return True
    if profile == LEGACY:
        return False
    return True


def branch_model(profile: str) -> str:
    """'P' = brief §9 orphan-SourceCode model; 'G' = current-guide model."""
    return "P" if profile == STRICT_P else "G"
