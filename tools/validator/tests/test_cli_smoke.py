"""End-to-end check_swhap.sh / CLI smoke, schema-sync invariant, dual-profile."""
import filecmp
import json
import os
import subprocess
import sys

from conftest import SCHEMA_PATH, VALIDATOR_ROOT

SPECS_SCHEMA = os.path.abspath(os.path.join(
    VALIDATOR_ROOT, "..", "..", "specs", "validator-report.schema.json"))


def test_schema_copy_byte_identical_to_specs():
    """validator-report §Normative: schemas/validation-report.v1.schema.json
    MUST be byte-identical to specs/validator-report.schema.json (CI sync)."""
    assert filecmp.cmp(SCHEMA_PATH, SPECS_SCHEMA, shallow=False)


def _cli(workdir, *args):
    env = dict(os.environ, PYTHONPATH=VALIDATOR_ROOT)
    p = subprocess.run(
        [sys.executable, "-m", "swhap_validate", "--workdir", workdir, *args],
        capture_output=True, text=True, env=env)
    return p


def test_cli_exit_one_on_defective(wildlife, validate_report):
    p = _cli(wildlife["defective"], "--profile", "strict-P", "--report", "-")
    assert p.returncode == 1
    doc = json.loads(p.stdout)
    validate_report(doc)
    assert doc["summary"]["exit_code"] == 1


def test_cli_dual_profile_default_writes_two_reports(wildlife, tmp_path):
    out = tmp_path / "r.json"
    p = _cli(wildlife["defective"], "--report", str(out))
    # process exit = max of the two profiles (both fail) = 1
    assert p.returncode == 1
    assert (tmp_path / "r.strict-P.json").exists()
    assert (tmp_path / "r.strict-G.json").exists()


def test_cli_dual_profile_rejects_stdout(wildlife):
    p = _cli(wildlife["defective"], "--report", "-")
    assert p.returncode == 2  # usage error


def test_cli_bash_orchestrator(wildlife):
    sh = os.path.join(VALIDATOR_ROOT, "check_swhap.sh")
    env = dict(os.environ, SWHAP_PYTHON=sys.executable)
    p = subprocess.run(
        ["bash", sh, "--profile", "strict-P", "--workdir", wildlife["defective"],
         "--report", "-"], capture_output=True, text=True, env=env)
    assert p.returncode == 1
    assert json.loads(p.stdout)["summary"]["exit_code"] == 1
