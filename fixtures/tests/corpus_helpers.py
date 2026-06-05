"""Shared loaders/paths for the fixture self-test suite.

Factored out of ``conftest.py`` so the test modules can import these helpers by a
*unique* module name. In a combined multi-suite ``pytest`` run there are several
same-named ``conftest.py`` files; a bare ``import conftest`` is ambiguous (it
resolves to whichever suite's conftest landed in ``sys.modules`` first). This
module carries a name that does not collide, and ``conftest.py`` re-exports it so
isolated fixture-suite runs keep working unchanged.
"""
import importlib.util
import os

FIXTURES = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEG = os.path.join(FIXTURES, "negative")
WILD = os.path.join(FIXTURES, "wildlife")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_build():
    return _load("swhap_neg_build", os.path.join(NEG, "build.py"))


def load_mk_manifest():
    return _load("swhap_mk_manifest", os.path.join(WILD, "mk_manifest.py"))
