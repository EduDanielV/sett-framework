r"""
Guard test: no internal codename of a consumer application built on
SETT should ever appear in the public sett-framework tree.

Convention #20 ("Public naming"): SETT is published generically.
Consumer applications are described as "two independent projects built
on SETT", "an early prototype application", "a companion-assistant
application", never by their real internal name. A `grep` sweep is
supposed to happen before closing any new text, but "supposed to
happen" is exactly the kind of rule that's easy to follow sometimes and
easy to forget needs re-checking on the next change.

The forbidden names themselves are represented here only as SHA-256
hashes, never as plaintext, and matching is done by hashing whole
letter-only tokens extracted from each line, not by searching for a
plaintext substring. This matters for a reason specific to this file:
its own source code is itself part of the public tree it scans. If the
forbidden names were written here as literal strings (as an earlier
version of this file did), the guard test would defeat its own
purpose the moment it shipped: a reader, a search engine, or a `grep`
of the public repository would find the exact codenames this file
exists to keep out, sitting in plain text inside the file whose job is
to prevent that. Hashing means the mechanism works (compare a
candidate token's hash against a set of known-bad hashes) without ever
writing the protected value itself anywhere a casual reader could read
it back out.

History, described generically since the specifics involve the actual
codenames:

- First incident (2026-07-23): a routine sweep ahead of a public
  release found literal mentions of one codename already merged into
  a changelog, adapter example docstrings, and test fixtures. None
  were malicious or even wrong when written; they accumulated silently
  because nothing checked automatically. Same shape of problem as
  `test_version_consistency.py` guards against for version strings.
- Second incident, same day, found after the release above had already
  been pushed: the original pattern used `\b` (regex word boundary) on
  both sides of the name. `\b` only breaks at a transition between a
  "word" character (letters, digits, and underscore) and a non-word
  character. Since underscore counts as a word character, a `\b`
  based pattern does not catch a codename immediately followed by an
  underscore (e.g. inside a path like "<codename>_elevenlabs_patch.zip"
  that had slipped into a docstring). Fixed by extracting maximal runs
  of ASCII letters only, treating digits, underscores, and hyphens as
  boundaries the same as whitespace or punctuation, then hashing each
  run as a whole token. This has a useful side effect: because the
  comparison is against an entire token rather than a substring search
  inside it, a word that merely contains a forbidden name as a
  substring (for example a Spanish word ending in the same four
  letters) can never match, since the whole token hashes to something
  else. No separate false-positive carve-out logic is needed for that
  case; it falls out of comparing whole tokens instead of substrings.
- Third incident found while preparing this guard for public release
  (2026-07-26): the guard test itself, exempted from its own scan so
  it could discuss what it protects against, necessarily contained the
  plaintext codenames in its forbidden-name list and its regression
  fixtures. Shipping it as-is to the public repository would have
  leaked exactly what it exists to prevent. Rewritten to this
  hash-based, whole-token design so it can ship publicly.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# SHA-256 hex digests of the internal codenames this guard protects,
# each computed from the lowercased name. Do not add a plaintext name
# anywhere in this file, including in comments or fixtures: see the
# module docstring (third incident) for why that would defeat the
# guard's purpose the moment it ships.
_FORBIDDEN_NAME_HASHES = {
    "a3f9a909aa816e10ace873b59ad22164424f63b1987f0624803739475c94c255",
    "0821310426ea2c8731c1c5a53bda9551135a7562f402aa245e66953311bf3fb0",
}

_SCAN_EXTENSIONS = {".py", ".md", ".toml", ".txt"}

# Directories that are never part of the shipped/public tree: nothing
# to scan there, and some (.git) aren't even valid text.
_EXCLUDED_DIR_NAMES = {".git", "__pycache__", ".pytest_cache", ".venv", "venv"}

# This file itself is exempt from the scan: its own hash constants and
# fixtures would otherwise flag it. It never spells out a forbidden
# name in plaintext (see module docstring), so the exemption is not
# hiding a leak, it just avoids the file matching its own hash values
# in the "not accidentally empty" and regression tests below.
_SELF = Path(__file__).resolve()

# A maximal run of ASCII letters, bounded on both sides by a non-letter
# (digit, underscore, hyphen, punctuation, whitespace) or the start/end
# of the line. Hashing the run as a whole, rather than searching for a
# substring within it, is what makes "recaída" or a similar word that
# merely ends in the same letters as a forbidden name safe: the run in
# that case is the entire word, not just its last few letters.
_LETTER_RUN = re.compile(r"[A-Za-z]+")


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


def _token_hashes(line: str) -> list[str]:
    return [
        hashlib.sha256(token.lower().encode("utf-8")).hexdigest()
        for token in _LETTER_RUN.findall(line)
    ]


@pytest.mark.parametrize("forbidden_hash", sorted(_FORBIDDEN_NAME_HASHES))
def test_no_internal_project_name_leaks_into_public_tree(forbidden_hash: str) -> None:
    offenders = []
    for path in _scannable_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if forbidden_hash in _token_hashes(line):
                offenders.append(
                    f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}"
                )
    assert not offenders, (
        f"Found {len(offenders)} mention(s) of a forbidden internal "
        f"project name (hash {forbidden_hash[:12]}...) in the public "
        f"sett-framework tree (Convention #20: describe consumer "
        f"applications generically, never by their real name):\n"
        + "\n".join(offenders)
    )


def test_forbidden_hashes_set_is_not_accidentally_empty():
    """Guard against the guard: an empty hash set would make the test
    above vacuously pass without checking anything."""
    assert _FORBIDDEN_NAME_HASHES


# The two tests below verify the detection mechanism itself (boundary
# handling and whole-token comparison) using made-up stand-in words
# that are not the real forbidden names, so this file never needs to
# spell out a real codename to prove the logic works.

_FIXTURE_HASHES = {
    hashlib.sha256(b"zorbix").hexdigest(),
    hashlib.sha256(b"quantia").hexdigest(),
}


@pytest.mark.parametrize(
    "text",
    [
        "ZORBIX_full_test",
        "zorbix_example_patch.zip",
        "ZORBIX2024",
        "quantia_export_v2.csv",
    ],
)
def test_pattern_catches_underscore_and_digit_adjacent_names(text: str) -> None:
    assert any(h in _FIXTURE_HASHES for h in _token_hashes(text)), (
        f"Whole-token hashing failed to catch a known-bad string: {text!r}"
    )


@pytest.mark.parametrize("text", ["prezorbixo", "rezorbixed", "quantianaso"])
def test_pattern_does_not_false_positive_on_letter_flanked_substrings(
    text: str,
) -> None:
    assert not any(h in _FIXTURE_HASHES for h in _token_hashes(text)), (
        f"False positive: whole-token hashing matched inside a word "
        f"({text!r}) that merely contains a stand-in name as a "
        f"substring, not the whole token."
    )
