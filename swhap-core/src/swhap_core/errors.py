"""Stable error taxonomy for swhap-core (core-pipeline.md §5).

Every error carries a stable machine code, an exception family, the ``swhap``
exit code it maps to (§3.1.1), and a plain-language template id (the crit-M11
warning-rendering hook). Codes are aligned with the csv-contract / validator
naming where the families overlap (``CSV-*`` mirrors csv-contract §10).

For the M1a inspect slice only the ``EX-*`` (ExtractionContractError) and
``BG-*`` (BudgetError) families are *evaluated*; the rest of the taxonomy is
declared here so the code set is frozen and stable for downstream slices and
so the exit-code map never has to be re-derived.

The inspect path does **not** raise these exceptions: it reports rejections as
data (``Rejection`` records carrying a code). ``exit_code_for_codes`` then maps
the set of observed rejection codes to a single process exit code. Callers that
want fail-fast semantics can raise via ``error_for_code``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# --- exit codes (core-pipeline.md §3.1.1) ----------------------------------
EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_USAGE = 2
EXIT_EXTRACTION = 10  # extraction-contract violation (EX-*)
EXIT_BUDGET = 11  # budget exceeded (BG-*)
EXIT_CSV = 12
EXIT_PLAN_DRIFT = 13
EXIT_REF_POLICY = 14
EXIT_JOURNAL = 15
EXIT_PUBLISH_PRECOND = 16


@dataclass(frozen=True)
class CodeSpec:
    """Static metadata for one stable error code."""

    code: str
    family: str  # exception class name
    exit_code: int
    template_id: str  # crit-M11 plain-language template hook


def _spec(code: str, family: str, exit_code: int) -> CodeSpec:
    # template id is derived deterministically from the code so the warning
    # renderer (M2) has a stable key per code without a second registry.
    return CodeSpec(code, family, exit_code, "tmpl." + code.lower())


# --- the registry ----------------------------------------------------------
# Order is documentation only; lookups are by code.
_EXTRACTION = [
    "EX-FORMAT",  # archive is not a readable tar/zip, or central dir mismatch
    "EX-ABS",  # member path is absolute
    "EX-TRAVERSAL",  # member path contains a ".." component
    "EX-SYMLINK-ESCAPE",  # symlink target resolves outside the extraction root
    "EX-HARDLINK-OUT",  # hardlink target is not itself a member of the archive
    "EX-DEVICE",  # device / FIFO / socket / special member
    "EX-DUP",  # two members share a byte-identical path
    "EX-CASE-COLLISION",  # casefold(NFC(a)) == casefold(NFC(b)), a != b
]
_BUDGET = [
    "BG-MEMBERS",  # member count over budget
    "BG-BYTES",  # total uncompressed size over budget
    "BG-RATIO",  # overall compression ratio over budget (decompression bomb)
    "BG-FILESIZE",  # a single member's uncompressed size over budget
    "BG-PATH",  # path length or depth over budget
]
# Declared-but-not-evaluated-here families (frozen for downstream slices).
_CSV = [
    "CSV-HEADER",
    "CSV-FIELD",
    "CSV-DATE",
    "CSV-TZ",
    "CSV-TAG",
    "CSV-DUP-TAG",
    "CSV-DUP-DIR",
]
_HISTORY = ["HB-DIR-MISSING", "HB-PLAN-DRIFT", "HB-REF-POLICY", "HB-GIT-VERSION"]
_JOURNAL = ["JL-APPEND-ONLY", "JL-CHAIN", "JL-COVERAGE", "JL-SCHEMA", "JL-RENDER"]
_PROPOSAL = ["PP-BUNDLE-SCHEMA", "AP-NO-APPROVAL", "AP-MANIFEST-MISMATCH", "AP-ALLOWLIST"]

CODES: dict[str, CodeSpec] = {}
for _c in _EXTRACTION:
    CODES[_c] = _spec(_c, "ExtractionContractError", EXIT_EXTRACTION)
for _c in _BUDGET:
    CODES[_c] = _spec(_c, "BudgetError", EXIT_BUDGET)
for _c in _CSV:
    CODES[_c] = _spec(_c, "CsvContractError", EXIT_CSV)
for _c in _HISTORY:
    CODES[_c] = _spec(_c, "HistoryError", EXIT_REF_POLICY if _c == "HB-REF-POLICY" else EXIT_PLAN_DRIFT)
for _c in _JOURNAL:
    CODES[_c] = _spec(_c, "JournalError", EXIT_JOURNAL)
for _c in _PROPOSAL:
    CODES[_c] = _spec(_c, "ProposalError", EXIT_EXTRACTION if _c == "PP-BUNDLE-SCHEMA" else EXIT_REF_POLICY)

# The codes the M1a inspect slice may actually emit.
INSPECT_CODES = tuple(_EXTRACTION + _BUDGET)


# --- exception hierarchy ---------------------------------------------------
class SwhapError(Exception):
    """Base of the swhap-core exception hierarchy."""

    code: str = "SWHAP-INTERNAL"
    exit_code: int = EXIT_INTERNAL

    def __init__(self, message: str, *, code: str | None = None, **fields: Any):
        super().__init__(message)
        if code is not None:
            self.code = code
        # exit code follows the stable code when known (e.g. HB-REF-POLICY → 14,
        # other HB-* → 13), else the family default.
        spec = CODES.get(self.code)
        if spec is not None:
            self.exit_code = spec.exit_code
        self.message = message
        self.fields = fields

    @property
    def template_id(self) -> str:
        spec = CODES.get(self.code)
        return spec.template_id if spec else "tmpl.internal"


class ExtractionContractError(SwhapError):
    exit_code = EXIT_EXTRACTION


class BudgetError(SwhapError):
    exit_code = EXIT_BUDGET


class CsvContractError(SwhapError):
    exit_code = EXIT_CSV


class HistoryError(SwhapError):
    exit_code = EXIT_PLAN_DRIFT


class JournalError(SwhapError):
    exit_code = EXIT_JOURNAL


class ProposalError(SwhapError):
    exit_code = EXIT_EXTRACTION


_FAMILY_CLASSES = {
    "ExtractionContractError": ExtractionContractError,
    "BudgetError": BudgetError,
    "CsvContractError": CsvContractError,
    "HistoryError": HistoryError,
    "JournalError": JournalError,
    "ProposalError": ProposalError,
}


def exit_code_for_code(code: str) -> int:
    spec = CODES.get(code)
    return spec.exit_code if spec else EXIT_INTERNAL


def error_for_code(code: str, message: str, **fields: Any) -> SwhapError:
    """Construct the exception of the right family for a stable code."""
    spec = CODES.get(code)
    if spec is None:
        return SwhapError(message, code=code, **fields)
    cls = _FAMILY_CLASSES[spec.family]
    return cls(message, code=code, **fields)


def exit_code_for_codes(codes: list[str]) -> int:
    """Reduce a set of observed rejection codes to one process exit code.

    Extraction-contract violations (10) take precedence over budget
    violations (11): a path-traversal archive is structurally unsafe
    regardless of whether it also blows a budget.
    """
    seen = {exit_code_for_code(c) for c in codes}
    if EXIT_EXTRACTION in seen:
        return EXIT_EXTRACTION
    if EXIT_BUDGET in seen:
        return EXIT_BUDGET
    if seen:
        # any other declared family that somehow appears
        return sorted(seen)[0]
    return EXIT_OK


@dataclass(frozen=True)
class Rejection:
    """One crit-M6 rejection finding (reported as data, never raised on the
    inspect path)."""

    code: str
    message: str
    fields: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "code": self.code,
            "family": CODES[self.code].family if self.code in CODES else "SwhapError",
            "exit_code": exit_code_for_code(self.code),
            "template_id": CODES[self.code].template_id if self.code in CODES else "tmpl.internal",
            "message": self.message,
        }
        out.update(self.fields)
        return out
