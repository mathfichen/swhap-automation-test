import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(__file__)
VALIDATOR_ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, VALIDATOR_ROOT)
sys.path.insert(0, HERE)

import wildlife_fixture as wf  # noqa: E402
from swhap_validate import manifest as _manifest  # noqa: E402

SCHEMA_PATH = os.path.join(VALIDATOR_ROOT, "schemas",
                           "validation-report.v1.schema.json")


@pytest.fixture(scope="session")
def schema():
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="session")
def validate_report(schema):
    from jsonschema import Draft202012Validator
    v = Draft202012Validator(schema)

    def _check(report_or_dict):
        doc = report_or_dict if isinstance(report_or_dict, dict) \
            else report_or_dict.to_dict()
        errors = sorted(v.iter_errors(doc), key=lambda e: e.path)
        assert not errors, "schema errors:\n" + "\n".join(
            f"  {list(e.path)}: {e.message}" for e in errors)
        return doc
    return _check


@pytest.fixture(scope="session")
def wildlife(tmp_path_factory):
    """Build the Wild_LIFE fixtures once per session from REAL pinned objects.

    - ``defective`` = the real published exemplar (main=pin-main,
      SourceCode=pin-sourcecode) checked out of the bundle. No reconstruction.
    - ``clean`` = a faithful all-green regeneration from the pinned tarballs.
    - ``manifests`` = the real committed tree-manifest oracles (release order),
      excluding the quarantined 1.02 census.
    """
    root = tmp_path_factory.mktemp("wildlife")
    defective = wf.build_exemplar(str(os.path.join(str(root), "exemplar")))
    clean = wf.build_clean(str(root))
    manifests = _manifest.load_dir(wf.MANIFESTS_DIR)
    return {
        "defective": defective,
        "clean": clean,
        "manifests": manifests,
        "manifests_dir": wf.MANIFESTS_DIR,
        "order": wf.ORDER,
        "tags": wf.TAG,
    }


def make_git_repo(path, files):
    """Create a git repo at `path` with a `main` branch holding `files`
    (dict of repo-relative path -> bytes). Returns the path."""
    os.makedirs(path, exist_ok=True)
    subprocess.run(["git", "-C", path, "init", "-q", "-b", "main"], check=True)
    env = dict(os.environ, **{
        "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@noreply.example.org",
        "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@noreply.example.org",
        "GIT_AUTHOR_DATE": "2026-06-05T00:00:00+0000",
        "GIT_COMMITTER_DATE": "2026-06-05T00:00:00+0000",
    })
    for rel, content in files.items():
        full = os.path.join(path, rel)
        os.makedirs(os.path.dirname(full) or path, exist_ok=True)
        with open(full, "wb") as fh:
            fh.write(content)
    subprocess.run(["git", "-C", path, "add", "-A"], check=True, env=env)
    subprocess.run(["git", "-C", path, "commit", "-q", "-m", "init"],
                   check=True, env=env)
    return path
