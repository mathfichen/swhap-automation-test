"""Report model, canonical serialization, finding ids, exit-code mapping.

Codes the validator-report v1 contract (specs/validator-report.md +
validator-report.schema.json) EXACTLY. Stdlib only at runtime; schema
self-validation is best-effort (uses jsonschema if importable, else skipped —
the test suite validates against the schema unconditionally).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

SCHEMA_VERSION = "1"
TOOL_NAME = "swhap-validate"
TOOL_VERSION = "0.1.0"

# Closed severity enum (validator-report §2.3).
FAIL = "FAIL"
WARN = "WARN"
INFO = "INFO"

# Provenance-state vocabulary (validator-report §2.9).
PROV_STATES = {"observed", "computed", "inferred", "user-provided", "curator-approved"}


def _canon_bytes(obj: Any) -> bytes:
    """Canonical JSON for the finding-id hash (§2.1): sorted keys, compact
    separators, non-ASCII unescaped."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def bsafe(b: bytes) -> str:
    """Byte-safe, lossless string encoding (validator-report §2.5a).

    Renders non-UTF-8 bytes and ALL control/terminal bytes as ``\\xHH`` text so
    no raw control char ever reaches a forge-visible report and
    ``json.dumps(..., ensure_ascii=False)`` can never raise.
    """
    s = b.decode("utf-8", errors="surrogateescape")
    return bsafe_str(s)


def bsafe_str(s: str) -> str:
    out = []
    for ch in s:
        cp = ord(ch)
        if ch == "\\":
            out.append("\\\\")
        elif 0xDC80 <= cp <= 0xDCFF:  # lone surrogate = original invalid byte
            out.append("\\x%02x" % (cp - 0xDC00))
        elif cp <= 0x1F or 0x7F <= cp <= 0x9F:  # C0 / DEL / C1 controls
            out.append("\\x%02x" % cp)
        else:
            out.append(ch)
    return "".join(out)


def make_finding_id(check_id: str, subject: dict) -> str:
    digest = hashlib.sha256(_canon_bytes(subject)).hexdigest()[:12]
    return f"{check_id}:{digest}"


@dataclass
class Finding:
    check_id: str
    severity: str
    object: dict
    subject_keys: list  # subset of object keys identifying the subject (§2.1)
    message_plain: str
    required_approver_role: str = "curator"
    state: str = "open"
    message_technical: str | None = None
    provenance: dict | None = None
    remediation: str | None = None
    enforced: bool = True

    def subject(self) -> dict:
        if not self.subject_keys:
            return {}
        return {k: self.object[k] for k in self.subject_keys if k in self.object}

    def id(self) -> str:
        return make_finding_id(self.check_id, self.subject())

    def _message_plain(self) -> str:
        """Guarantee a non-empty, human-readable ``message_plain`` (schema
        ``minLength: 1``; validator-report §2.6 "Required, non-empty").

        A finding that serialized with an empty message left a forge-visible
        result self-describing only by severity+id (the GAP-2 auditability hole).
        The producer owns this invariant: if a check ever leaves ``message_plain``
        empty, fall back to ``message_technical``; if that is empty too, synthesize
        a generic but truthful line from the stable ``check_id`` + ``severity`` so
        no finding is ever message-less. Findings that already carry a message are
        unaffected (byte-identical output)."""
        mp = self.message_plain
        if mp is not None and str(mp).strip():
            return mp
        mt = self.message_technical
        if mt is not None and str(mt).strip():
            return mt
        return (f"Check {self.check_id} reported a {self.severity}-level finding; "
                "see the finding object and report details.")

    def to_dict(self) -> dict:
        d = {
            "id": self.id(),
            "check_id": self.check_id,
            "severity": self.severity,
            "enforced": self.enforced,
            "object": self.object,
            "message_plain": self._message_plain(),
            "required_approver_role": self.required_approver_role,
            "state": self.state,
        }
        if self.message_technical is not None:
            d["message_technical"] = self.message_technical
        if self.provenance is not None:
            d["provenance"] = self.provenance
        if self.remediation is not None:
            d["remediation"] = self.remediation
        return d


# ---------------------------------------------------------------------------
# Exit-code mapping (validator-report §4.1) — total order, counts never matter.
# ---------------------------------------------------------------------------
EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
EXIT_INTERNAL = 3
EXIT_PRECONDITION = 4


def compute_exit_code(findings, strict_warn: bool) -> int:
    """Rules 3..6 of §4.1 (rules 1/2 — usage/internal — are handled by the CLI
    before/around check execution). PC-* FAIL ⇒ 4; else enforced FAIL ⇒ 1;
    else enforced WARN under --strict-warn ⇒ 1; else 0."""
    pc_fail = any(
        f.severity == FAIL and f.check_id.startswith("PC-") for f in findings
    )
    if pc_fail:
        return EXIT_PRECONDITION
    enforced = [
        f for f in findings if f.enforced and not f.check_id.startswith("PC-")
    ]
    if any(f.severity == FAIL for f in enforced):
        return EXIT_FAIL
    if strict_warn and any(f.severity == WARN for f in enforced):
        return EXIT_FAIL
    return EXIT_PASS


class Report:
    def __init__(self, profile: str, gate: str, *, strict_warn=False,
                 meta_stable=False, timestamp=None, repo=None, head=None,
                 invocation=None, intake_profile=None, published_remote=None,
                 tool_commit=None):
        self.profile = profile
        self.gate = gate
        self.strict_warn = strict_warn
        self.meta_stable = meta_stable
        self.timestamp = timestamp
        self.repo = repo
        self.head = head
        self.invocation = invocation
        self.intake_profile = intake_profile
        self.published_remote = published_remote
        self.tool_commit = tool_commit
        self.findings: list[Finding] = []
        self.checks_run: set[str] = set()
        self.checks_skipped: list[dict] = []
        self.refs_checked: list[str] = []
        self.error: dict | None = None

    def add(self, finding: Finding):
        self.findings.append(finding)

    def ran(self, check_id: str):
        self.checks_run.add(check_id)

    def skip(self, check_id: str, reason: str):
        self.checks_skipped.append({"id": check_id, "reason": reason})

    def exit_code(self) -> int:
        if self.error is not None:
            return EXIT_INTERNAL if self.error.get("code") == "internal" else EXIT_USAGE
        return compute_exit_code(self.findings, self.strict_warn)

    def to_dict(self) -> dict:
        n_fail = sum(1 for f in self.findings if f.severity == FAIL)
        n_warn = sum(1 for f in self.findings if f.severity == WARN)
        n_info = sum(1 for f in self.findings if f.severity == INFO)
        checks_with_findings = {f.check_id for f in self.findings}
        n_pass = sum(1 for c in self.checks_run if c not in checks_with_findings)
        exit_code = self.exit_code()

        tool = {"name": TOOL_NAME, "version": TOOL_VERSION}
        if self.tool_commit:
            tool["commit"] = self.tool_commit

        run = {
            "profile": self.profile,
            "gate": self.gate,
            "checks_run": sorted(self.checks_run),
            "checks_skipped": sorted(self.checks_skipped, key=lambda e: e["id"]),
        }
        if self.strict_warn:
            run["strict_warn"] = True
        if self.head:
            run["head"] = self.head
        if self.refs_checked:
            run["refs_checked"] = sorted(self.refs_checked)
        if self.intake_profile:
            run["intake_profile"] = self.intake_profile
        if self.published_remote:
            run["published_remote"] = self.published_remote
        if self.meta_stable:
            run["meta_stable"] = True
        else:
            if self.timestamp is not None:
                run["timestamp"] = self.timestamp
            if self.repo is not None:
                run["repo"] = self.repo
            if self.invocation is not None:
                run["invocation"] = self.invocation

        doc = {
            "schema_version": SCHEMA_VERSION,
            "tool": tool,
            "run": run,
            "summary": {
                "fail": n_fail, "warn": n_warn, "info": n_info,
                "pass": n_pass, "exit_code": exit_code,
            },
            "findings": sorted((f.to_dict() for f in self.findings),
                               key=lambda d: d["id"]),
        }
        if self.error is not None:
            doc["error"] = self.error
        return doc

    def serialize(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True,
                          ensure_ascii=False) + "\n"
