"""Small hash-chain utility for append-only audit records.

The chain is tamper-evident, not cryptographically signed: modifying,
removing, reordering, or inserting an entry is detectable with
``verify_chain``. Authenticity against an attacker who can rewrite the
whole process state still requires an external signature or trusted sink.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any

_GENESIS_HASH = "0" * 64


def _canonical_bytes(entry: dict[str, Any]) -> bytes:
    payload = {k: v for k, v in entry.items() if k != "entry_hash"}
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def append_chained_entry(
    log: list[dict[str, Any]], entry: dict[str, Any]
) -> dict[str, Any]:
    """Append a defensive copy with sequence and hash-chain metadata."""
    chained = deepcopy(entry)
    chained["sequence"] = len(log) + 1
    chained["previous_hash"] = log[-1]["entry_hash"] if log else _GENESIS_HASH
    chained["entry_hash"] = sha256(_canonical_bytes(chained)).hexdigest()
    log.append(chained)
    return deepcopy(chained)


def verify_chain(log: list[dict[str, Any]]) -> bool:
    """Return ``True`` only when the full log's sequence and hashes match."""
    expected_previous = _GENESIS_HASH
    for index, raw in enumerate(log, start=1):
        entry = deepcopy(raw)
        if entry.get("sequence") != index:
            return False
        if entry.get("previous_hash") != expected_previous:
            return False
        expected_hash = sha256(_canonical_bytes(entry)).hexdigest()
        if entry.get("entry_hash") != expected_hash:
            return False
        expected_previous = expected_hash
    return True
