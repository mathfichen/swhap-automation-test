"""Pytest plugin for the fixture self-test suite.

The reusable loaders/paths live in ``corpus_helpers`` (a uniquely-named module,
safe to ``import`` in a combined multi-suite run); they are re-exported here so
existing references via this conftest keep resolving.
"""
import os

import pytest

from corpus_helpers import (  # noqa: F401  (re-exported for test convenience)
    FIXTURES,
    NEG,
    WILD,
    _load,
    load_build,
    load_mk_manifest,
)


@pytest.fixture(scope="session", autouse=True)
def _materialize_negative_corpus():
    """The negative archives are regenerable (not committed). Build them once
    before the suite runs so a fresh checkout is self-sufficient."""
    if not os.path.exists(os.path.join(NEG, "archives", "neg-traversal-dotdot.tar")):
        load_build().build_all(os.path.join(NEG, "archives"))
    yield
