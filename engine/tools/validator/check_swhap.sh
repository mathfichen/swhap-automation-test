#!/usr/bin/env bash
# check_swhap.sh — thin bash orchestrator for swhap-validate (brief §13).
#
# NO parsing, NO check logic, NO string interpolation into git here: bash only
# probes dependencies and execs the Python package, passing argv through
# unchanged and propagating its exit code (the C1/crit-M3 injection lesson is a
# design rule — dt2sg-gen.py interpolated CSV fields into shell; we never do).
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Dependency probe (git ≥ 2.39, python ≥ 3.11). Failures are config errors.
command -v git >/dev/null 2>&1 || { echo "check_swhap: git not found" >&2; exit 2; }

PY="${SWHAP_PYTHON:-python3}"
command -v "$PY" >/dev/null 2>&1 || { echo "check_swhap: $PY not found" >&2; exit 2; }

if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 11) else 1)'; then
  echo "check_swhap: python >= 3.11 required" >&2
  exit 2
fi

# Make the package importable without installation, then hand off argv verbatim.
export PYTHONPATH="${here}:${PYTHONPATH:-}"
exec "$PY" -m swhap_validate "$@"
