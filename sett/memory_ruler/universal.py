"""
SETT Framework — UniversalMemory
==============================
Shared memory accessible by the orchestrator and all agents.

Agents publish ONLY their final results here — not internal reasoning.
Every write passes through the EthicalFilter if one is configured.

Also handles EnvironmentalContext — the shared risk state that
multiple SETT instances in the same location can read and publish.
"""
from __future__ import annotations
from typing import Any, TYPE_CHECKING
from datetime import datetime, timezone
import threading

if TYPE_CHECKING:
    from sett.ethics_ruler.ethic_kernel.filter import EthicalFilter
    from sett.risk_ruler.environmental_context import EnvironmentalContext
    from sett.risk_ruler.risk_profile import RiskProfile

# Reserved key prefix for environmental context entries
_ENV_CONTEXT_PREFIX = "__env_ctx__"


class UniversalMemory:
    """
    Universal memory shared across all agents and the orchestrator.

    Two types of data live here:

    1. Agent results — published via update(), read via read()/read_all().
       Each agent publishes its final result under its domain name.

    2. Environmental context — published via publish_environmental_context(),
       read via read_environmental_context().
       Used for multi-instance coordination (the "almacén scenario"):
       one SETT instance publishes a RiskLevel for a location,
       others in the same location read it and adjust their behavior.

    Thread-safe by default.
    """

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self._history: list[dict[str, Any]] = []
        self._ethical_filter: EthicalFilter | None = None
        self._lock = threading.Lock()

    def set_ethical_filter(self, ethical_filter: EthicalFilter) -> None:
        """Attach an EthicalFilter to intercept all writes."""
        self._ethical_filter = ethical_filter

    # ── Agent results ────────────────────────────────────────────────────────

    def update(
        self,
        agent: str,
        result: dict[str, Any],
        emotional_state: str = "unknown",
        risk_profile: "RiskProfile | None" = None,
        environmental_context: "EnvironmentalContext | None" = None,
    ) -> None:
        """
        Called by an agent to publish its final result.
        Passes through the EthicalFilter before being committed.

        v0.1.1 fix: previously this only passed action="memory_write" and
        a context wrapped as {"agent": agent, "result": result} — so (a)
        emotional_state/risk_profile/environmental_context never reached
        the filter in the real flow (they silently defaulted every time),
        and (b) detectors that read biometric data expected keys directly
        in `context` but received them nested one level deeper under
        "result" instead, so they never matched.

        Now the published result's keys are spread directly into the
        context passed to the filter (so both flat and "health"-nested
        detectors can find them), and all three risk layers are forwarded.
        The publishing agent's domain is still available, namespaced as
        "_source_agent" to avoid colliding with the agent's own data.
        """
        if self._ethical_filter is not None:
            context = dict(result)
            context["_source_agent"] = agent
            self._ethical_filter.evaluate(
                action="memory_write",
                context=context,
                emotional_state=emotional_state,
                risk_profile=risk_profile,
                environmental_context=environmental_context,
            )

        with self._lock:
            self._store[agent] = result
            self._history.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent": agent,
                "action": "update",
            })

    def evaluate_action(
        self,
        action: str,
        context: dict[str, Any],
        emotional_state: str = "unknown",
        risk_profile: "RiskProfile | None" = None,
        environmental_context: "EnvironmentalContext | None" = None,
    ) -> None:
        """
        Evaluate a real-world side effect through the EthicalFilter BEFORE
        it is executed — used by SETTAgent.propose_action() and by
        SETTExecutor.submit(). Unlike update(), this does not write
        anything to universal memory; it only runs the action through the
        filter and lets a rejection propagate as
        SETTEthicalFilterRejectedError.

        If no EthicalFilter is configured, this is a no-op (fail-open),
        matching the existing behavior of update() when no filter is set.
        """
        if self._ethical_filter is not None:
            self._ethical_filter.evaluate(
                action=action,
                context=context,
                emotional_state=emotional_state,
                risk_profile=risk_profile,
                environmental_context=environmental_context,
            )

    def read(self, agent: str, default: Any = None) -> Any:
        """Read the latest published result from a specific agent."""
        return self._store.get(agent, default)

    def read_all(self) -> dict[str, dict[str, Any]]:
        """Snapshot of all agent results. Used by the orchestrator."""
        with self._lock:
            return {
                k: v for k, v in self._store.items()
                if not k.startswith(_ENV_CONTEXT_PREFIX)
            }

    # ── Environmental context (multi-instance coordination) ──────────────────

    def publish_environmental_context(
        self, context: "EnvironmentalContext"
    ) -> None:
        """
        Publish an EnvironmentalContext to a shared location slot.

        Any SETT instance that reads this location key will receive
        the current risk level — without any personal data attached.

        Args:
            context: The EnvironmentalContext to publish.
        """
        key = f"{_ENV_CONTEXT_PREFIX}{context.location_id}"
        with self._lock:
            self._store[key] = context.to_dict()
            self._history.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "env_context_update",
                "location_id": context.location_id,
                "risk_level": context.risk_level.value,
                "source_domain": context.source_domain,
            })

    def read_environmental_context(
        self, location_id: str = "global"
    ) -> "EnvironmentalContext | None":
        """
        Read the current EnvironmentalContext for a location.

        Returns None if no context has been published for this location.

        Args:
            location_id: The location to read. Defaults to "global".
        """
        from sett.risk_ruler.environmental_context import EnvironmentalContext
        key = f"{_ENV_CONTEXT_PREFIX}{location_id}"
        data = self._store.get(key)
        if data is None:
            return None
        return EnvironmentalContext.from_dict(data)

    def read_all_environmental_contexts(
        self,
    ) -> dict[str, "EnvironmentalContext"]:
        """Return all published EnvironmentalContexts, keyed by location_id."""
        from sett.risk_ruler.environmental_context import EnvironmentalContext
        result = {}
        with self._lock:
            for key, data in self._store.items():
                if key.startswith(_ENV_CONTEXT_PREFIX):
                    location_id = key[len(_ENV_CONTEXT_PREFIX):]
                    result[location_id] = EnvironmentalContext.from_dict(data)
        return result

    def get_history(self) -> list[dict[str, Any]]:
        """Full write history for auditing and debugging."""
        return list(self._history)

    def __repr__(self) -> str:
        agents = [k for k in self._store if not k.startswith(_ENV_CONTEXT_PREFIX)]
        env_keys = [k for k in self._store if k.startswith(_ENV_CONTEXT_PREFIX)]
        return (
            f"UniversalMemory("
            f"agents={agents}, "
            f"env_locations={[k[len(_ENV_CONTEXT_PREFIX):] for k in env_keys]})"
        )
