r"""
Guard test: SETT is a general-purpose framework and its own source
(code, comments, docstrings, docs) should read in English throughout -
this scans the public tree for text that looks like Spanish and fails
if it finds any that isn't on the explicit allowlist below.

Motivated by two incidents found in the same review (2026-07-28): (1) a
new test file (this session's `test_phrasing_expert.py` additions) had
several Spanish docstrings/comments, an honest mistake from working
across two projects (one bilingual, one English-only) in the same
session; (2) a Spanish paragraph had been locally introduced into
`sett/services_tts_stt/base.py`'s docstring at some point after v0.7.0's
actual release - confirmed, by comparing against the real published
source, to never have existed there. Both were caught by manual review
this time. This test exists so the next one is caught automatically,
the same day it's introduced, instead of waiting for the next external
review.

Detection strategy: Spanish orthography uses accented vowels
(áéíóúÁÉÍÓÚ), ñ/Ñ, and inverted punctuation (¿¡) far more often than
English uses any of them at all (English has none of these natively).
Any real sentence or paragraph of Spanish - as opposed to a single
word - is virtually certain to contain at least one. This is not a
grammar-aware language classifier: a short, careless Spanish phrase
with no accented characters (rare in practice, since correctly written
Spanish uses them constantly - "tambien" instead of "también" is a typo,
not the norm) could in principle slip past it. Manual review before a
release remains the backstop for that gap, the same way it caught both
incidents that motivated this test - this closes the "same mistake
introduced during normal development, unnoticed until the next
external review" gap, it does not replace review entirely.

False positives this test knows about and explicitly allows, each with
its own reason (see `_ALLOWED_SNIPPETS`): the framework author's own
name (a real name is not a language issue), the project's own
multi-language paper links (each language named in its own script:
"English, Español, 日本語" - a deliberate list, not prose), a single
Spanish word used as a necessary illustrative example in
`test_no_internal_project_names.py` (explaining a false-positive edge
case for that OTHER guard test), an example surname in a demo script,
and one historical CHANGELOG entry that quotes, for the record, a
Spanish word that was already found and fixed in an earlier version
(quoting the mistake to document the fix is not repeating it).

Adding a new exception: put the exact snippet in `_ALLOWED_SNIPPETS`
with a one-line comment saying why. Do not widen the detection pattern
itself to work around a real one-off leak - fix the source text instead
and let the test do its job.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

_SCAN_EXTENSIONS = {".py", ".md", ".toml", ".txt"}

# Directories that are never part of the shipped/public tree: nothing to
# scan there, and some (.git) aren't even valid text.
_EXCLUDED_DIR_NAMES = {".git", "__pycache__", ".pytest_cache", ".venv", "venv"}

# This file itself is exempt: its own docstring and comments above
# necessarily discuss Spanish characters and quote example words to
# explain what the test does and why, which would otherwise flag it.
_SELF = Path(__file__).resolve()

# Accented Latin vowels, ñ/Ñ, and inverted punctuation: characters
# Spanish uses constantly and English never uses natively. See the
# module docstring for why this is the detection signal, and what it
# does not catch.
_SPANISH_SIGNAL = re.compile(r"[áéíóúÁÉÍÓÚñÑ¿¡]")

# Exact substrings that are allowed to contain the signal characters
# above, each for a specific, reviewed reason - not a general escape
# hatch. A flagged line is only cleared if EVERY signal character on it
# is inside one of these substrings; anything left over still fails.
_ALLOWED_SNIPPETS = (
    # The framework author's real name - not a language issue.
    "Viñales",
    # The project's own paper is published in three languages; each is
    # named in its own script in a deliberate list ("English, Español,
    # 日本語"), never translated to "Spanish" mid-list.
    "Español",
    # Necessary illustrative example in test_no_internal_project_names.py:
    # a real word that happens to end in the same letters as a forbidden
    # name, used to explain why whole-token hashing (not substring
    # matching) is required there. Not prose.
    "recaída",
    # Example surname in a demo scenario (examples/multi_agent.py) - a
    # name, not a language choice.
    "García",
    # Historical CHANGELOG entry (v0.6.0-era) quotes, for the record, a
    # Spanish word ("almacén scenario") that was already found and fixed
    # in an earlier version. Quoting a past mistake to document its own
    # fix is not the same as repeating it.
    "almacén",
    # CHANGELOG.md/README.md (v0.10.3) quote the OLD citation label and
    # filename ("Convención #N" / SETT_Convenciones_v2.md) to describe
    # what got renamed to SETT_Conventions_v2.md and "Convention #N" -
    # same "quote the past state to document the fix" pattern as
    # "almacén" above, not a live citation.
    "Convención #N",
    "Convenciones_v2.md",
)


def _scannable_files() -> list[Path]:
    files = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in _SCAN_EXTENSIONS:
            continue
        if path.resolve() == _SELF:
            continue
        if path.name.endswith(".egg-info"):
            continue
        if any(part in _EXCLUDED_DIR_NAMES or part.endswith(".egg-info")
               for part in path.parts):
            continue
        files.append(path)
    return files


def _line_is_clean(line: str) -> bool:
    """True if every signal character on the line is accounted for by an
    allowed snippet. Removes each allowed snippet from the line first,
    then checks whether any signal character remains in what's left."""
    remainder = line
    for snippet in _ALLOWED_SNIPPETS:
        remainder = remainder.replace(snippet, "")
    return not _SPANISH_SIGNAL.search(remainder)


def test_no_unexplained_spanish_in_public_tree() -> None:
    offenders = []
    for path in _scannable_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _SPANISH_SIGNAL.search(line) and not _line_is_clean(line):
                offenders.append(
                    f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}"
                )
    assert not offenders, (
        f"Found {len(offenders)} line(s) that look like Spanish in the "
        f"public sett-framework tree (SETT is English-only; see this "
        f"test's module docstring for the allowlist mechanism if this is "
        f"a deliberate exception rather than a leak):\n"
        + "\n".join(offenders)
    )


@pytest.mark.parametrize(
    "text",
    [
        "Esto está en español, ¿no?",
        "El niño juega en el jardín.",
        "Configuración de este módulo.",
    ],
)
def test_pattern_catches_real_spanish_sentences(text: str) -> None:
    assert not _line_is_clean(text), (
        f"The Spanish-detection signal failed to catch a real Spanish "
        f"sentence: {text!r}"
    )


@pytest.mark.parametrize(
    "text",
    [
        "This is a normal English sentence.",
        "Author: Eduardo Daniel Viñales",
        "Available in English, Español, 日本語.",
        'the word "recaída" is a necessary example',
        "Doctor appointment - Dr. García",
        'a leftover Spanish word ("almacén scenario")',
    ],
)
def test_pattern_does_not_false_positive_on_allowed_content(text: str) -> None:
    assert _line_is_clean(text), (
        f"False positive: flagged allowed content as a Spanish leak: {text!r}"
    )
