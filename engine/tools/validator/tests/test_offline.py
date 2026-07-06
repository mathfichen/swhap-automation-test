"""CM-3 / network discipline: the JSON-LD loader is strictly offline."""
import json

import pytest

from swhap_validate.checks import codemeta
from swhap_validate.report import Report

CANON = "https://doi.org/10.5063/schema/codemeta-2.0"


def test_offline_loader_refuses_unknown_url():
    accepted, newer, vendored = codemeta._accepted()
    loader = codemeta._offline_loader(vendored)
    # vendored URLs resolve locally
    assert loader(CANON)["document"] is not None
    # anything else is refused (no network)
    with pytest.raises(RuntimeError):
        loader("https://example.org/anything")


def test_cm3_runs_with_sockets_disabled(monkeypatch):
    pytest.importorskip("pyld")
    import socket

    def _no_socket(*a, **k):
        raise OSError("network disabled in test")

    monkeypatch.setattr(socket, "socket", _no_socket)
    rep = Report("strict-P", "build")
    doc = {"@context": CANON, "name": "x", "author": [{"name": "a"}],
           "funder": {"name": "y"}}
    codemeta.run(rep, None, codemeta_bytes=json.dumps(doc).encode())
    # CM-3 must complete (no network) and not FAIL
    assert not [f for f in rep.findings if f.check_id == "CM-3"]
