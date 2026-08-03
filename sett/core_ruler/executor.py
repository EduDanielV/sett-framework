"""
SETT Framework: SETTExecutor
==============================
The only component in a SETT system that is allowed to perform real
side effects (send a message, call an external API, contact emergency
services, move money, etc.).

Agents and experts never call the real client library directly. They
describe intent as an Action and submit it here. The Executor:

    1. Receives the Action
    2. Runs it through the EthicalFilter (Layer 1 action / Layer 2 user /
       Layer 3 environment: the same three-layer system used everywhere
       else in SETT)
    3. If approved: invokes the handler registered for that action_type:
       this is the ONLY place the real side effect happens
    4. Returns the handler's result upward, so the Orchestrator (and from
       there, the application built on SETT) can incorporate
       it into the system's response

Submitting an Action through the Executor provides the structural gate:
the expert never receives a reference to the real client. The Executor
also fails closed when it is not attached to an orchestrator, when the
shared memory has no EthicalFilter, when approval is rejected, or when no
handler is registered.

``SETTAgent.propose_action()`` remains available for evaluating an action
without executing it. It now also requires orchestrator wiring; standalone
silent approval is not permitted.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from sett.audit_ruler.chain import append_chained_entry, verify_chain
from sett.core_ruler.action import Action
from sett.core_ruler.execution_context import (
    ExecutionContext,
    current_execution_context,
    current_trace_cause_id,
    execution_scope,
)
from sett.exceptions import SETTConfigurationError, SETTEthicalFilterRejectedError

if TYPE_CHECKING:
    from sett.audit_ruler.trace import TraceRecorder
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
        self._universal_memory: UniversalMemory | None = None
        self._audit_log: list[dict[str, Any]] = []
        self._trace_recorder: TraceRecorder | None = None

    def attach_universal_memory(self, memory: UniversalMemory) -> None:
        """
        Called by the orchestrator during register_executor().
        Gives the executor access to evaluate_action() (which forwards to
        the EthicalFilter) and to the EnvironmentalContext of a location.
        Do not call this manually.
        """
        self._universal_memory = memory

    def attach_trace_recorder(self, recorder: TraceRecorder) -> None:
        """Attach the orchestrator-owned recorder."""
        self._trace_recorder = recorder

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
        risk_profile: RiskProfile | None = None,
        location_id: str = "global",
        *,
        execution_context: ExecutionContext | None = None,
        cause_id: str | None = None,
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
            SETTConfigurationError: If the Executor is unattached, its
                memory has no EthicalFilter, or no handler is registered for
                this action type. Every configuration error fails closed.
        """
        if self._universal_memory is None:
            raise SETTConfigurationError(
                "SETTExecutor is not attached to a SETTOrchestrator. "
                "Register it with orchestrator.register_executor(executor) "
                "before submitting any action."
            )
        if not self._universal_memory.has_ethical_filter:
            raise SETTConfigurationError(
                "SETTExecutor cannot run because its UniversalMemory has no "
                "EthicalFilter. Real-world actions fail closed by default."
            )

        parent = execution_context or current_execution_context()
        trace_cause = cause_id or current_trace_cause_id()
        action_context = parent.derive() if parent is not None else None
        proposed_event = None
        if action_context is not None and self._trace_recorder is not None:
            proposed_event = self._trace_recorder.record(
                action_context,
                kind="action.proposed",
                component_type="executor",
                component_name=action.action_type,
                status="proposed",
                cause_id=trace_cause,
                attributes={
                    "action_id": action.action_id,
                    "action_type": action.action_type,
                    "proposed_by": action.proposed_by,
                },
            )

        environmental_context = self._universal_memory.read_environmental_context(
            location_id
        )
        # This raises SETTEthicalFilterRejectedError if rejected:
        # the handler below is only reached if it does not raise.
        try:
            verdict, policy_event = self._universal_memory._evaluate_action_with_trace(
                action=action.action_type,
                context={
                    **deepcopy(action.payload),
                    "_proposed_by": action.proposed_by,
                },
                emotional_state=emotional_state,
                risk_profile=risk_profile,
                environmental_context=environmental_context,
                execution_context=action_context,
                cause_id=proposed_event.event_id if proposed_event else trace_cause,
            )
        except Exception as error:
            if action_context is not None and self._trace_recorder is not None:
                rejected_event = self._trace_recorder.record(
                    action_context,
                    kind="action.rejected",
                    component_type="executor",
                    component_name=action.action_type,
                    status="rejected",
                    cause_id=(
                        getattr(error, "trace_event_id", None)
                        or (
                            proposed_event.event_id
                            if proposed_event else trace_cause
                        )
                    ),
                    reason_codes=(
                        "policy.reject"
                        if isinstance(error, SETTEthicalFilterRejectedError)
                        else "component.exception",
                    ),
                    attributes={
                        "action_id": action.action_id,
                        "error_type": type(error).__name__,
                    },
                )
                try:
                    error.trace_event_id = rejected_event.event_id
                except (AttributeError, TypeError):
                    pass
            raise

        handler = self._handlers.get(action.action_type)
        if handler is None:
            failed_event = None
            if action_context is not None and self._trace_recorder is not None:
                failed_event = self._trace_recorder.record(
                    action_context,
                    kind="handler.failed",
                    component_type="handler",
                    component_name=action.action_type,
                    status="failed",
                    cause_id=(
                        self._trace_recorder.last_event_id(action_context.run_id)
                        or (
                            proposed_event.event_id
                            if proposed_event else trace_cause
                        )
                    ),
                    reason_codes=("handler.not_registered",),
                )
            error = SETTConfigurationError(
                f"No handler registered for action_type '{action.action_type}'. "
                f"Call executor.register_handler({action.action_type!r}, your_function) "
                f"before submitting this kind of action. "
                f"Registered types: {list(self._handlers.keys())}"
            )
            if failed_event is not None:
                error.trace_event_id = failed_event.event_id
            raise error

        approved_event = None
        authorized_event = None
        if action_context is not None and self._trace_recorder is not None:
            approved_event = self._trace_recorder.record(
                action_context,
                kind="action.approved",
                component_type="executor",
                component_name=action.action_type,
                status="approved",
                cause_id=(
                    policy_event.event_id if policy_event is not None else None
                ) or (
                    proposed_event.event_id if proposed_event else trace_cause
                ),
                reason_codes=(f"policy.{verdict.value}",),
                attributes={"action_id": action.action_id},
            )
            try:
                authorized_event = self._trace_recorder.record(
                    action_context,
                    kind="handler.authorized",
                    component_type="handler",
                    component_name=action.action_type,
                    status="authorized",
                    cause_id=approved_event.event_id,
                    attributes={"action_id": action.action_id},
                    effect_boundary=True,
                )
            except SETTConfigurationError as error:
                blocked_event = self._trace_recorder.record(
                    action_context,
                    kind="handler.blocked",
                    component_type="handler",
                    component_name=action.action_type,
                    status="blocked",
                    cause_id=(
                        getattr(error, "trace_event_id", None)
                        or approved_event.event_id
                    ),
                    reason_codes=("trace.exporter_failed",),
                    attributes={"action_id": action.action_id},
                )
                error.trace_event_id = blocked_event.event_id
                raise

        logger.info(
            "[Executor] Executing approved action '%s' (proposed by '%s')",
            action.action_type, action.proposed_by,
        )
        handler_event = None
        if action_context is not None and self._trace_recorder is not None:
            handler_event = self._trace_recorder.record(
                action_context,
                kind="handler.started",
                component_type="handler",
                component_name=action.action_type,
                status="started",
                cause_id=(
                    authorized_event.event_id
                    if authorized_event is not None
                    else approved_event.event_id
                ),
                attributes={"action_id": action.action_id},
            )
        try:
            if action_context is not None:
                with execution_scope(
                    action_context,
                    handler_event.event_id if handler_event else trace_cause,
                ):
                    result = handler(deepcopy(action.payload))
            else:
                result = handler(deepcopy(action.payload))
        except Exception as error:
            if action_context is not None and self._trace_recorder is not None:
                failed_event = self._trace_recorder.record(
                    action_context,
                    kind="handler.failed",
                    component_type="handler",
                    component_name=action.action_type,
                    status="failed",
                    cause_id=(
                        handler_event.event_id if handler_event else trace_cause
                    ),
                    reason_codes=("component.exception",),
                    attributes={"error_type": type(error).__name__},
                )
                try:
                    error.trace_event_id = failed_event.event_id
                except (AttributeError, TypeError):
                    pass
            raise

        append_chained_entry(self._audit_log, {
            "action_type": action.action_type,
            "proposed_by": action.proposed_by,
            "timestamp": action.timestamp,
            "executed": True,
            "action_id": action.action_id,
        })
        if action_context is not None and self._trace_recorder is not None:
            self._trace_recorder.record(
                action_context,
                kind="handler.completed",
                component_type="handler",
                component_name=action.action_type,
                status="completed",
                cause_id=handler_event.event_id if handler_event else trace_cause,
                attributes={
                    "action_id": action.action_id,
                    "result_type": type(result).__name__,
                },
            )
        return result

    def get_audit_log(self) -> list[dict[str, Any]]:
        """
        Log of every action that was actually executed (i.e. approved by
        the filter AND had a registered handler). Rejected or unhandled
        actions do not appear here: they never ran.
        """
        return deepcopy(self._audit_log)

    def verify_audit_log(self) -> bool:
        """Verify sequence and hash links in the internal execution log."""
        return verify_chain(self._audit_log)

    @property
    def registered_action_types(self) -> list[str]:
        """Action types that currently have a handler registered."""
        return list(self._handlers.keys())

    def __repr__(self) -> str:
        return f"SETTExecutor(handlers={self.registered_action_types})"
