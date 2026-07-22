"""
Guard test: the version declared in pyproject.toml and the
sett.__version__ string must always match.

Motivated by a real incident: a release was prepared with
pyproject.toml bumped but sett/__init__.py still carrying the previous
version, so ``sett.__version__`` reported one version behind the
installed package. This test makes that class of mismatch impossible
to ship silently.
"""

import re
from pathlib import Path

import sett


def test_pyproject_version_matches_dunder_version():
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    assert match, "pyproject.toml has no version field"
    assert match.group(1) == sett.__version__, (
        f"Version mismatch: pyproject.toml says {match.group(1)!r} but "
        f"sett.__version__ says {sett.__version__!r}. Bump BOTH before "
        f"releasing."
    )
