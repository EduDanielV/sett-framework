"""
SETT Framework: SETTExpert
==============================
The most atomic unit in SETT.

An expert is a specialized module that lives inside an agent.
It handles one specific task, updates the agent's private memory,
and returns a result that the agent uses to compose its final output.

Several experts form one agent: that is the core of the SETT hierarchy.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any

from sett.core_ruler.execution_context import (
    current_execution_context,
    current_trace_cause_id,
    execution_scope,
)

if TYPE_CHECKING:
    from sett.audit_ruler.trace import TraceRecorder
    from sett.memory_ruler.private import PrivateMemory


class SETTExpert(ABC):
    """
    Abstract base class for all SETT experts.

    An expert:
    - Belongs to exactly one agent
    - Has access to that agent's PrivateMemory (given by the agent at registration)
    - Resolves one specific task via resolve()
    - Is responsible for writing relevant state to private memory
    - Does NOT communicate directly with other agents or the orchestrator

    To create a new expert, extend this class and implement resolve().

    Example:
        class HeartRateExpert(SETTExpert):
            def resolve(self, context):
                bpm = context.get("heart_rate_bpm", 0)
                status = "normal" if 60 <= bpm <= 100 else "abnormal"
                if self._private_memory:
                    self._private_memory.write("heart_rate_status", status)
                return {"heart_rate_status": status, "bpm": bpm}
    """

    def __init__(self, name: str):
        """
        Args:
            name: A unique name for this expert within its agent.
                  Used to retrieve the expert via agent.get_expert(name).
        """
        self.name = name
        self._private_memory: PrivateMemory | None = None
        self._trace_recorder: TraceRecorder | None = None
        self._sett_trace_wrapped = False

    def attach_memory(self, memory: PrivateMemory) -> None:
        """
        Called by the parent agent during registration.
        Gives this expert access to the agent's private memory.
        Do not call this manually.
        """
        self._private_memory = memory

    def _attach_trace_recorder(self, recorder: TraceRecorder) -> None:
        """Attach run-local tracing when the parent agent is registered."""
        self._trace_recorder = recorder

    def _install_trace_interceptor(self) -> None:
        """Instrument the existing public resolve() method once.

        The wrapper is attached to this instance, preserving subclasses'
        public ``resolve(context)`` contract and class-level method identity.
        """
        if self._sett_trace_wrapped:
            return
        implementation = self.resolve

        @wraps(implementation)
        def traced_resolve(context: dict[str, Any]) -> dict[str, Any]:
            return self._resolve_with_trace(implementation, context)

        self.resolve = traced_resolve  # type: ignore[method-assign]
        self._sett_trace_wrapped = True

    def _resolve_with_trace(
        self,
        implementation: Callable[[dict[str, Any]], dict[str, Any]],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        parent = current_execution_context()
        recorder = self._trace_recorder
        if parent is None or recorder is None:
            return implementation(context)

        child = parent.derive()
        started = recorder.record(
            child,
            kind="expert.started",
            component_type="expert",
            component_name=self.name,
            status="started",
            cause_id=current_trace_cause_id(),
        )
        with execution_scope(child, started.event_id):
            try:
                result = implementation(context)
            except Exception as error:
                failed_event = recorder.record(
                    child,
                    kind="expert.failed",
                    component_type="expert",
                    component_name=self.name,
                    status="failed",
                    cause_id=started.event_id,
                    reason_codes=("component.exception",),
                    attributes={"error_type": type(error).__name__},
                )
                try:
                    error.trace_event_id = failed_event.event_id
                except (AttributeError, TypeError):
                    pass
                raise
            recorder.record(
                child,
                kind="expert.completed",
                component_type="expert",
                component_name=self.name,
                status="completed",
                cause_id=started.event_id,
                attributes={"result_type": type(result).__name__},
            )
            return result

    @property
    def _execution_context(self):
        """Context active while this expert is resolving, if any."""
        return current_execution_context()

    @abstractmethod
    def resolve(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Main method of the expert. Must be implemented by every subclass.

        Receives a context dict, processes it, writes relevant state
        to private memory, and returns a result dict.

        Args:
            context: Input data for this expert to process.
                     Provided by the agent that owns this expert.

        Returns:
            A dict with the result of this expert's work.
            This will be used by the agent to compose its final output.
        """

    def __repr__(self) -> str:
        return f"SETTExpert(name={self.name!r})"
