"""Parity with the stdlib ``tarfile.data_filter`` baseline.

core-pipeline.md §4.1 names ``tarfile`` ``filter='data'`` as the semantic
baseline for the tar rejection rules; we re-assert the equivalent checks on the
member list directly (so zip gets identical guarantees and the verdict never
depends on extraction). For the defect classes the data filter *does* cover,
our inspect verdict must agree with it: where the filter raises, we reject.
"""

from __future__ import annotations

import tarfile

import pytest

from swhap_core.inspect import inspect_archive

# Fixtures the stdlib data filter *rejects* -> the EX code we must also emit.
_PARITY = {
    "neg-traversal-dotdot.tar": "EX-TRAVERSAL",
    "neg-symlink-escape.tar": "EX-SYMLINK-ESCAPE",
    "neg-symlink-rel-escape.tar": "EX-SYMLINK-ESCAPE",
    "neg-device-fifo.tar": "EX-DEVICE",
}


def _data_filter_rejects(path: str) -> bool:
    with tarfile.open(path) as tf:
        for ti in tf.getmembers():
            try:
                tarfile.data_filter(ti, "dest")
            except tarfile.FilterError:
                return True
    return False


@pytest.mark.parametrize("name,code", sorted(_PARITY.items()))
def test_inspect_agrees_with_data_filter(corpus, name, code):
    # the stdlib baseline rejects it ...
    assert _data_filter_rejects(corpus[name]) is True
    # ... and so does our member-list inspection, with the right code.
    r = inspect_archive(corpus[name])
    codes = {x["code"] for x in r["rejections"]}
    assert code in codes
    assert r["accepted"] is False


def test_inspect_is_stricter_than_data_filter_on_absolute_paths(corpus):
    """``tarfile.data_filter`` SILENTLY REWRITES an absolute member path to a
    relative one (``/etc/passwd`` -> ``etc/passwd``) instead of rejecting it.

    A curatorial pipeline must not silently relocate members, so our member-list
    inspection is deliberately stricter than the extraction baseline: it rejects
    with ``EX-ABS``. This is exactly why the rules are evaluated on the member
    list directly and not via extraction alone (core-pipeline.md §4.1)."""
    with tarfile.open(corpus["neg-absolute-path.tar"]) as tf:
        ti = tf.getmembers()[0]
        rewritten = tarfile.data_filter(ti, "dest")  # does NOT raise
        assert rewritten.name == "etc/passwd"
    r = inspect_archive(corpus["neg-absolute-path.tar"])
    assert "EX-ABS" in {x["code"] for x in r["rejections"]}
    assert r["accepted"] is False
