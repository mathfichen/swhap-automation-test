"""Exit-code total order (validator-report §4.1): counts never matter; PC beats
FAIL beats strict-warn-WARN; state never enters."""
from swhap_validate.report import (FAIL, INFO, WARN, Finding, compute_exit_code)


def F(check_id, sev, enforced=True):
    f = Finding(check_id, sev, {"x": check_id}, ["x"], "m")
    f.enforced = enforced
    return f


def test_clean_is_zero():
    assert compute_exit_code([], False) == 0
    assert compute_exit_code([F("CM-4", INFO)], False) == 0


def test_enforced_fail_is_one():
    assert compute_exit_code([F("TF-1", FAIL)], False) == 1


def test_fail_beats_many_warns():
    fs = [F("SZ-3", WARN)] * 5 + [F("TF-1", FAIL)]
    assert compute_exit_code(fs, False) == 1


def test_warn_only_zero_without_strict():
    assert compute_exit_code([F("SZ-3", WARN), F("PI-1", WARN)], False) == 0


def test_warn_only_one_with_strict():
    assert compute_exit_code([F("SZ-3", WARN)], True) == 1


def test_pc_fail_beats_tf_fail():
    fs = [F("PC-1", FAIL), F("TF-1", FAIL)]
    assert compute_exit_code(fs, False) == 4


def test_unenforced_fail_does_not_set_one():
    """Legacy: enforced=false FAIL contributes nothing."""
    assert compute_exit_code([F("CM-2", FAIL, enforced=False)], False) == 0


def test_unenforced_pc_still_counts():
    """PC-* stays enforced in every profile — even an enforced=false PC FAIL
    drives exit 4 (the mapping keys PC on the family, not the flag)."""
    assert compute_exit_code([F("PC-1", FAIL, enforced=False)], False) == 4
