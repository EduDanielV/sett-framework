"""
SETT Framework — SETTExecutor
==============================
The only component in a SETT system that is allowed to perform real
side effects (send a message, call an external API, contact emergency
services, move money, etc.).

Agents and experts never call the real client library directly. They
describe intent as an Action and submit it here. The Executor:

    1. Receives the Action
    2. Runs it through the EthicalFilter (Layer 1 action / Layer 2 user /
       Layer 3 environment — the same three-layer system used everywhere
       else in SETT)
    3. If approved: invokes the handler registered for that action_type —
       this is the ONLY place the real side effect happens
    4. Returns the handler's result upward, so the Orchestrator (and from
       there, the application built on SETT — e.g. AIDA) can incorporate
       it into the system's response

This is the structural alternative to SETTAgent.propose_action(): where
propose_action() only asks the developer to remember to call it before
doing the real thing themselves, submitting an Action through the
Executor makes it physically impossible to perform the effect any other
way, because the expert never holds a reference to the real client.

Both mechanisms are supported in SETT and are not mutually exclusive:
- propose_action() — lightweight, no setup required, good for
  prototyping or low-stakes side effects.
- SETTExecutor + Action — more setup (register a handler once), but a
  structural guarantee for your highest-stakes side effects (the ones
  where "the developer forgot to call the gate" is not an acceptable
  failure mode — emergency calls, payments, contacting a doctor, etc.)
"""
from __future__ import annotations
from typing import Any, Callable, TYPE_CHECKING
import logging

from sett.core_ruler.action import Action
from sett.exceptions import SETTConfigurationError

if TYPE_CHECKING:
    from sett.memory_ruler.universal import UniversalMemory
    from sett.risk_ruler.risk_profile import RiskProfile

logger = logging.getLogger(__name__)


class SETTExecutor:
    """
    Receives Action proposals from agents, evaluates them through the
    EthicalFilter, and executes only the approved ones via a registered
    handler.

    Usage:
        executor = SETTExecutor()
        executor.register_handler("send_sms", lambda payload: sms_client.send(**payload))

        orchestrator = SETTOrchestrator(ethical_filter=EthicalFilter())
        orchestrator.register_executor(executor)
        orchestrator.register_agent(MyAgent())

        # Inside MyAgent.process():
        #     self.submit_action("send_sms", {"to": "...", "message": "..."})
        # → evaluated by the filter; only runs sms_client.send(...) if approved.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[dict[str, Any]], Any]] = {}
        self._universal_memory: "UniversalMemory | None" = None
        self._audit_log: list[dict[str, Any]] = []

    def attach_universal_memory(self, memory: "UniversalMemory") -> None:
        """
        Called by the orchestrator during register_executor().
        Gives the executor access to evaluate_action() (which forwards to
        the EthicalFilter) and to the EnvironmentalContext of a location.
        Do not call this manually.
        """
        self._universal_memory = memory

    def register_handler(
        self, action_type: str, handler: Callable[[dict[str, Any]], Any]
    ) -> None:
        """
        Register the function that actually performs a given action type.
        This is the ONLY code in the entire system allowed to run this
        side effect.

        Args:
            action_type: Must match the action_type used in Action /
                         SETTAgent.submit_action() calls (e.g. "send_sms").
            handler: A callable that receives the Action's payload dict
                     and performs the real side effect. Its return value
                     is passed back to the caller of submit().
        """
        self._handlers[action_type] = handler

    def submit(
        self,
        action: Action,
        emotional_state: str = "unknown",
        risk_profile: "RiskProfile | None" = None,
        location_id: str = "global",
    ) -> Any:
        """
        Evaluate an Action through the EthicalFilter and, if approved,
        execute its registered handler.

        Args:
            action: The proposed Action.
            emotional_state: Detected emotional state of the user.
            risk_profile: Optional three-pillar RiskProfile for this user.
            location_id: Used to look up the EnvironmentalContext (Layer 3)
                         for where this action is being proposed.

        Returns:
            Whatever the registered handler returns.

        Raises:
            SETTEthicalFilterRejectedError: If the EthicalFilter blocks
                the action. The handler is NEVER called in that case.
            SETTConfigurationError: If no handler is registered for this
                action_type. The action is never executed in that case
                either — a missing handler fails closed, not open.
        """
        environmental_context = None
        if self._universal_memory is not None:
            environmental_context = self._universal_memory.read_environmental_context(
                location_id
            )
            # This raises SETTEthicalFilterRejectedError if rejected —
            # the handler below is only reached if it does not raise.
            self._universal_memory.evaluate_action(
                action=action.action_type,
                context={**action.payload, "_proposed_by": action.proposed_by},
                emotional_state=emotional_state,
                risk_profile=risk_profile,
                environmental_context=environmental_context,
            )

        handler = self._handlers.get(action.action_type)
        if handler is None:
            raise SETTConfigurationError(
                f"No handler registered for action_type '{action.action_type}'. "
                f"Call executor.register_handler({action.action_type!r}, your_function) "
                f"before submitting this kind of action. "
                f"Registered types: {list(self._handlers.keys())}"
            )

        logger.info(
            "[Executor] Executing approved action '%s' (proposed by '%s')",
            action.action_type, action.proposed_by,
        )
        result = handler(action.payload)

        self._audit_log.append({
            "action_type": action.action_type,
            "proposed_by": action.proposed_by,
            "timestamp": action.timestamp,
            "executed": True,
        })
        return result

    def get_audit_log(self) -> list[dict[str, Any]]:
        """
        Log of every action that was actually executed (i.e. approved by
        the filter AND had a registered handler). Rejected or unhandled
        actions do not appear here — they never ran.
        """
        return list(self._audit_log)

    @property
    def registered_action_types(self) -> list[str]:
        """Action types that currently have a handler registered."""
        return list(self._handlers.keys())

    def __repr__(self) -> str:
        return f"SETTExecutor(handlers={self.registered_action_types})"
