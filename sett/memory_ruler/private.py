"""
SETT Framework — PrivateMemory
==============================
Each agent has its own private memory.
Only the agent's experts can write to it.
The orchestrator has NO access to private memory — by design.

This is one of the two core memory layers of SETT.
"""
from __future__ import annotations
from typing import Any
from datetime import datetime, timezone


class PrivateMemory:
    """
    Private memory exclusive to a single agent.

    Key rules:
    - Only the experts that belong to the owner agent can write here.
    - The orchestrator cannot access this memory.
    - Other agents cannot access this memory.
    - Used for intermediate reasoning, working data, and internal state.
    - The agent uses this memory to compose its final result before
      publishing to UniversalMemory.

    Inspired by an early prototype's memory.py — simplified and made agent-specific.
    """

    def __init__(self, owner: str):
        """
        Args:
            owner: The name of the agent that owns this memory.
                   Used for logging and access control context.
        """
        self._owner = owner
        self._store: dict[str, Any] = {}
        self._history: list[dict[str, Any]] = []

    def write(self, key: str, value: Any) -> None:
        """
        Write a value to private memory.
        Should only be called from within an expert that belongs to this agent.

        Args:
            key: The key to store the value under.
            value: The value to store. Can be any Python object.
        """
        self._store[key] = value
        self._history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "write",
            "key": key,
        })

    def read(self, key: str, default: Any = None) -> Any:
        """
        Read a value from private memory.

        Args:
            key: The key to look up.
            default: Value to return if the key does not exist.

        Returns:
            The stored value, or default if not found.
        """
        return self._store.get(key, default)

    def get_all(self) -> dict[str, Any]:
        """
        Return a copy of all private memory contents.
        Used by the agent to compose its final output.
        """
        return dict(self._store)

    def clear(self) -> None:
        """Clear all stored values. Use with caution."""
        self._store.clear()

    def get_history(self) -> list[dict[str, Any]]:
        """Return the full write history for auditing."""
        return list(self._history)

    @property
    def owner(self) -> str:
        """The name of the agent that owns this memory."""
        return self._owner

    def __repr__(self) -> str:
        return f"PrivateMemory(owner={self._owner!r}, keys={list(self._store.keys())})"
