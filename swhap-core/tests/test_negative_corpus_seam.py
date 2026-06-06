"""Integration seam: swhap-core inspect vs the shared fixtures/negative corpus.

The fixtures slice publishes ``fixtures/negative/`` (swhap-negative-corpus/1):
a deterministic battery of archives, each with a declared ``disposition``
(REJECT|ACCEPT) and ``expected_code`` (EX-*/BG-*). This test mounts that real
corpus (not the inline builders in conftest) and asserts that ``inspect_archive``
produces exactly the producer-declared verdict for every fixture — proving the
W2 fixtures->inspect seam end to end. It complements (does not replace) the
inline unit corpus.
"""
from __future__ import annotations

import json
import os

import pytest

from swhap_core.inspect import inspect_archive


def _repo_root() -> str | None:
    # Key on the COMMITTED index.json, not the gitignored archives/ dir, so
    # collection succeeds on a clean clone (archives/ is materialized on demand
    # by the autouse fixture below — see the order-dependence fix).
    d = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.isfile(os.path.join(d, "fixtures", "negative", "index.json")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def _corpus():
    root = _repo_root()
    if root is None:
        return None, None
    base = os.path.join(root, "fixtures", "negative")
    index = os.path.join(base, "index.json")
    if not os.path.isfile(index):
        return None, None
    with open(index, encoding="utf-8") as fh:
        doc = json.load(fh)
    return base, doc


_BASE, _DOC = _corpus()
_FIXTURES = _DOC["fixtures"] if _DOC else []


@pytest.fixture(scope="session", autouse=True)
def _materialize_negative_corpus():
    """Build the gitignored fixtures/negative/archives/ from the committed
    deterministic generator before the seam tests run, so a single clean-clone
    pytest invocation yields the full parametrized run (no order-dependent skip:
    index.json is committed → collection succeeds; archives are built here →
    test bodies find them)."""
    if _BASE is None:
        return
    archives = os.path.join(_BASE, "archives")
    if not os.path.isdir(archives) or not os.listdir(archives):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_neg_build", os.path.join(_BASE, "build.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.build_all(archives)


@pytest.mark.skipif(not _FIXTURES, reason="fixtures/negative corpus not present")
def test_corpus_schema_id():
    assert _DOC["schema"] == "swhap-negative-corpus/1"


@pytest.mark.skipif(not _FIXTURES, reason="fixtures/negative corpus not present")
@pytest.mark.parametrize("fx", _FIXTURES, ids=lambda f: f["name"])
def test_inspect_matches_corpus_verdict(fx):
    path = os.path.join(_BASE, "archives", fx["file"])
    report = inspect_archive(path)
    codes = {r["code"] for r in report["rejections"]}
    if fx["disposition"] == "REJECT":
        assert fx["expected_code"] in codes, (
            f"{fx['name']}: expected {fx['expected_code']}, got {sorted(codes)}"
        )
        assert report["accepted"] is False
        assert report["exit_code"] in (10, 11)
    else:  # ACCEPT
        assert report["accepted"] is True, (
            f"{fx['name']}: expected ACCEPT, got rejections {sorted(codes)}"
        )
        assert report["exit_code"] == 0
