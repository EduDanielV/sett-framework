"""
SETT Framework: SETTOrchestrator
==============================
The brain and central meeting point of all agents.

The orchestrator:
- Holds all registered agents
- Manages the UniversalMemory (the only memory it can access)
- Routes input to the appropriate agent(s)
- Applies the EthicalFilter before executing actions
- Synthesizes the final system response from agent results

The orchestrator does NOT have access to agents' private memory.
It only sees what agents choose to publish to universal memory.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sett.audit_ruler.trace import TraceEvent, TraceExporter, TraceRecorder
from sett.core_ruler.agent import SETTAgent
from sett.core_ruler.execution_context import (
    ExecutionContext,
    TracedResult,
    current_execution_context,
    current_trace_cause_id,
    execution_scope,
)
from sett.core_ruler.executor import SETTExecutor
from sett.ethics_ruler.ethic_kernel.filter import EthicalFilter
from sett.exceptions import (
    SETTAgentNotFoundError,
    SETTEthicalFilterRejectedError,
    SETTValidationError,
)
from sett.memory_ruler.universal import UniversalMemory
from sett.risk_ruler.environmental_context import EnvironmentalContext
from sett.risk_ruler.risk_level import RiskLevel

if TYPE_CHECKING:
    from sett.core_ruler.pipeline import PipelineResult, PipelineStep

logger = logging.getLogger(__name__)


class SETTOrchestrator:
    """
    The SETTOrchestrator is the core of any SETT-based system.

    It coordinates all agents, manages universal memory, and ensures
    every action passes through the ethical filter before execution.

    Usage:
        orchestrator = SETTOrchestrator(ethical_filter=EthicalFilter())
        orchestrator.register_agent(HealthAgent())
        orchestrator.register_agent(CommunicationsAgent())

        result = orchestrator.process(
            input_data={"heart_rate_bpm": 110},
            domain="health"
        )
    """

    def __init__(self, ethical_filter: EthicalFilter | None = None) -> None:
        """
        Args:
            ethical_filter: The EthicalFilter to use. Defaults to a new
                            EthicalFilter with the default SETT ruleset.
        """
        self._agents: dict[str, SETTAgent] = {}
        self._universal_memory = UniversalMemory()
        self._ethical_filter = ethical_filter or EthicalFilter()
        self._executor = None  # SETTExecutor | None: set via register_executor()
        self._trace_recorder = TraceRecorder()
        self._last_trace_id: str | None = None

        # Connect the ethical filter to universal memory
        # Every write to universal memory will pass through it
        self._universal_memory.set_ethical_filter(self._ethical_filter)
        self._universal_memory.set_trace_recorder(self._trace_recorder)
        self._ethical_filter.set_trace_recorder(self._trace_recorder)

    def register_agent(self, agent: SETTAgent) -> None:
        """
        Register an agent with the orchestrator.
        Connects the agent to universal memory, and to the Executor if
        one has already been registered (order-independent: if the
        Executor is registered later via register_executor(), it is
        retroactively attached to every agent registered so far).

        Args:
            agent: A SETTAgent instance. Its domain must be unique.
        """
        agent.attach_universal_memory(self._universal_memory)
        agent.attach_trace_recorder(self._trace_recorder)
        if self._executor is not None:
            agent.attach_executor(self._executor)
        self._agents[agent.domain] = agent
        logger.info(
            "[Orchestrator] Agent registered: '%s' (domain: '%s')",
            agent.name, agent.domain
        )

    def register_executor(self, executor: SETTExecutor) -> None:
        """
        Register a SETTExecutor with this orchestrator. Gives it access
        to universal memory (so it can evaluate actions through the
        EthicalFilter and read EnvironmentalContext), and attaches it to
        every agent already registered: as well as to any agent
        registered afterward, automatically.

        Args:
            executor: A SETTExecutor instance.
        """
        self._executor = executor
        executor.attach_universal_memory(self._universal_memory)
        executor.attach_trace_recorder(self._trace_recorder)
        for agent in self._agents.values():
            agent.attach_executor(executor)
        logger.info("[Orchestrator] Executor registered.")

    def get_agent(self, domain: str) -> SETTAgent:
        """
        Retrieve a registered agent by domain.

        Args:
            domain: The domain key of the agent.

        Raises:
            SETTAgentNotFoundError: If no agent is registered for that domain.
        """
        if domain not in self._agents:
            raise SETTAgentNotFoundError(
                f"No agent registered for domain '{domain}'. "
                f"Registered domains: {list(self._agents.keys())}"
            )
        return self._agents[domain]

    def process(
        self,
        input_data: dict[str, Any],
        domain: str | None = None,
        emotional_state: str = "unknown",
        location_id: str = "global",
        *,
        execution_context: ExecutionContext | None = None,
    ) -> dict[str, Any]:
        """
        Process an input through the system.

        If domain is specified, routes directly to that agent.
        If no domain is given, broadcasts to all agents and collects results.

        v0.1.1 fix: emotional_state and location_id are now actually
        propagated to the agent (and from there, automatically, to the
        EthicalFilter via _publish_to_universal()). Previously
        emotional_state was accepted here but silently dropped before
        reaching agent.process(): every real evaluation ran with
        emotional_state="unknown" regardless of what was passed in.

        Args:
            input_data: The data to process.
            domain: Optional domain to route to a specific agent.
            emotional_state: The detected emotional state of the user.
                             When integrated with the Sentiment Analyzer agent,
                             this is passed automatically to the EthicalFilter.
            location_id: The shared space this interaction happens in.
                         Used to look up the EnvironmentalContext (Layer 3)
                         for this location. Defaults to "global".

        Returns:
            The result from the agent (or a dict of results from all agents).
        """
        if execution_context is not None and not isinstance(
            execution_context, ExecutionContext
        ):
            raise SETTValidationError(
                "execution_context must be an ExecutionContext or None."
            )
        root = execution_context or ExecutionContext.create()
        self._last_trace_id = root.trace_id
        started = self._trace_recorder.record(
            root,
            kind="trace.started",
            component_type="orchestrator",
            component_name=self.__class__.__name__,
            status="started",
            reason_codes=(
                "route.explicit_domain" if domain else "route.broadcast",
            ),
            attributes={"domain": domain, "mode": "route" if domain else "broadcast"},
        )
        with execution_scope(root, started.event_id):
            try:
                if domain:
                    result, terminal_event = self._route_to_agent(
                        domain,
                        input_data,
                        emotional_state,
                        location_id,
                        execution_context=root,
                        cause_id=started.event_id,
                        _return_event=True,
                    )
                else:
                    result, terminal_event = self._broadcast(
                        input_data,
                        emotional_state,
                        location_id,
                        execution_context=root,
                        cause_id=started.event_id,
                        _return_event=True,
                    )
            except Exception as error:
                self._trace_recorder.record(
                    root,
                    kind="trace.failed",
                    component_type="orchestrator",
                    component_name=self.__class__.__name__,
                    status="failed",
                    cause_id=(
                        getattr(error, "trace_event_id", None)
                        or started.event_id
                    ),
                    reason_codes=("component.exception",),
                    attributes={"error_type": type(error).__name__},
                )
                raise
            self._trace_recorder.record(
                root,
                kind="trace.completed",
                component_type="orchestrator",
                component_name=self.__class__.__name__,
                status="completed",
                cause_id=terminal_event.event_id,
            )
            return result

    def _route_to_agent(
        self,
        domain: str,
        input_data: dict[str, Any],
        emotional_state: str,
        location_id: str = "global",
        *,
        execution_context: ExecutionContext | None = None,
        cause_id: str | None = None,
        _return_event: bool = False,
    ) -> Any:
        """Route input to a specific agent."""
        parent = execution_context or current_execution_context() or ExecutionContext.create()
        route_event = self._trace_recorder.record(
            parent,
            kind="route.selected",
            component_type="orchestrator",
            component_name=self.__class__.__name__,
            status="completed",
            cause_id=cause_id or current_trace_cause_id(),
            reason_codes=("route.explicit_domain",),
            attributes={"domain": domain},
        )
        try:
            agent = self.get_agent(domain)
        except Exception as error:
            route_failed = self._trace_recorder.record(
                parent,
                kind="route.failed",
                component_type="orchestrator",
                component_name=self.__class__.__name__,
                status="failed",
                cause_id=route_event.event_id,
                reason_codes=("route.domain_unavailable",),
                attributes={
                    "domain": str(domain),
                    "error_type": type(error).__name__,
                },
            )
            try:
                error.trace_event_id = route_failed.event_id
            except (AttributeError, TypeError):
                pass
            raise
        agent_context = parent.derive()
        agent_started = self._trace_recorder.record(
            agent_context,
            kind="agent.started",
            component_type="agent",
            component_name=agent.name,
            status="started",
            cause_id=route_event.event_id,
            attributes={"domain": domain},
        )
        agent._current_emotional_state = emotional_state
        agent._current_location_id = location_id
        with execution_scope(agent_context, agent_started.event_id):
            try:
                logger.debug(
                    "[Orchestrator] Routing to agent '%s' (domain: '%s')",
                    agent.name, domain
                )
                result = agent.process(input_data)
            except SETTEthicalFilterRejectedError as error:
                agent_failed = self._trace_recorder.record(
                    agent_context,
                    kind="agent.failed",
                    component_type="agent",
                    component_name=agent.name,
                    status="rejected",
                    cause_id=error.trace_event_id or agent_started.event_id,
                    reason_codes=("policy.reject",),
                )
                route_failed = self._trace_recorder.record(
                    parent,
                    kind="route.failed",
                    component_type="orchestrator",
                    component_name=self.__class__.__name__,
                    status="rejected",
                    cause_id=agent_failed.event_id,
                    reason_codes=("policy.reject",),
                    attributes={"domain": domain},
                )
                error.trace_event_id = route_failed.event_id
                logger.warning(
                    "[Orchestrator] EthicalFilter blocked action from agent '%s'.",
                    agent.name
                )
                raise
            except Exception as error:
                agent_failed = self._trace_recorder.record(
                    agent_context,
                    kind="agent.failed",
                    component_type="agent",
                    component_name=agent.name,
                    status="failed",
                    cause_id=(
                        getattr(error, "trace_event_id", None)
                        or agent_started.event_id
                    ),
                    reason_codes=("component.exception",),
                    attributes={"error_type": type(error).__name__},
                )
                route_failed = self._trace_recorder.record(
                    parent,
                    kind="route.failed",
                    component_type="orchestrator",
                    component_name=self.__class__.__name__,
                    status="failed",
                    cause_id=agent_failed.event_id,
                    reason_codes=("component.exception",),
                    attributes={
                        "domain": domain,
                        "error_type": type(error).__name__,
                    },
                )
                try:
                    error.trace_event_id = route_failed.event_id
                except (AttributeError, TypeError):
                    pass
                raise
            agent_completed = self._trace_recorder.record(
                agent_context,
                kind="agent.completed",
                component_type="agent",
                component_name=agent.name,
                status="completed",
                cause_id=(
                    self._trace_recorder.last_event_id(agent_context.run_id)
                    or agent_started.event_id
                ),
            )
            route_completed = self._trace_recorder.record(
                parent,
                kind="route.completed",
                component_type="orchestrator",
                component_name=self.__class__.__name__,
                status="completed",
                cause_id=agent_completed.event_id,
                attributes={"domain": domain},
            )
            if _return_event:
                return result, route_completed
            return result

    def process_traced(
        self,
        input_data: dict[str, Any],
        domain: str | None = None,
        emotional_state: str = "unknown",
        location_id: str = "global",
        *,
        execution_context: ExecutionContext | None = None,
    ) -> TracedResult[dict[str, Any]]:
        """Process input and return the result with explicit trace identity."""
        root = execution_context or ExecutionContext.create()
        result = self.process(
            input_data,
            domain=domain,
            emotional_state=emotional_state,
            location_id=location_id,
            execution_context=root,
        )
        return TracedResult(result=result, trace_id=root.trace_id, context=root)

    def _broadcast(
        self,
        input_data: dict[str, Any],
        emotional_state: str,
        location_id: str = "global",
        *,
        execution_context: ExecutionContext | None = None,
        cause_id: str | None = None,
        _return_event: bool = False,
    ) -> Any:
        """
        Broadcast input to all registered agents and collect results.
        Agents that are blocked by the EthicalFilter have their error recorded.
        """
        parent = execution_context or current_execution_context() or ExecutionContext.create()
        broadcast_event = self._trace_recorder.record(
            parent,
            kind="broadcast.started",
            component_type="orchestrator",
            component_name=self.__class__.__name__,
            status="started",
            cause_id=cause_id or current_trace_cause_id(),
            reason_codes=("route.broadcast",),
            attributes={"domain_count": len(self._agents)},
        )
        last_cause_id = broadcast_event.event_id
        results: dict[str, Any] = {}
        for domain in self._agents:
            try:
                results[domain], route_terminal = self._route_to_agent(
                    domain,
                    input_data,
                    emotional_state,
                    location_id,
                    execution_context=parent,
                    cause_id=broadcast_event.event_id,
                    _return_event=True,
                )
                last_cause_id = route_terminal.event_id
            except SETTEthicalFilterRejectedError as e:
                results[domain] = {"blocked": True, "reason": str(e)}
                last_cause_id = e.trace_event_id or last_cause_id
                logger.warning(
                    "[Orchestrator] Agent '%s' blocked during broadcast.",
                    self._agents[domain].name,
                )
            except Exception as error:
                broadcast_failed = self._trace_recorder.record(
                    parent,
                    kind="broadcast.failed",
                    component_type="orchestrator",
                    component_name=self.__class__.__name__,
                    status="failed",
                    cause_id=(
                        getattr(error, "trace_event_id", None)
                        or last_cause_id
                    ),
                    reason_codes=("component.exception",),
                    attributes={"error_type": type(error).__name__},
                )
                try:
                    error.trace_event_id = broadcast_failed.event_id
                except (AttributeError, TypeError):
                    pass
                raise
        broadcast_completed = self._trace_recorder.record(
            parent,
            kind="broadcast.completed",
            component_type="orchestrator",
            component_name=self.__class__.__name__,
            status="completed",
            cause_id=last_cause_id,
            attributes={"domain_count": len(self._agents)},
        )
        if _return_event:
            return results, broadcast_completed
        return results

    def read_universal_memory(self) -> dict[str, Any]:
        """
        Read the current state of universal memory.
        Returns a snapshot of everything all agents have published.
        """
        return self._universal_memory.read_all()

    # ── Environmental context (multi-instance coordination) ──────────────────

    def publish_environmental_context(
        self,
        risk_level: RiskLevel,
        location_id: str = "global",
        source_domain: str = "orchestrator",
        message: str = "",
    ) -> EnvironmentalContext:
        """
        Publish an environmental risk level to a shared location slot.

        Called when an agent detects that the environment around the user
        has reached a notable risk level. Other SETT instances in the same
        location will read this and adjust their behavior.

        No personal data is published: only the RiskLevel, location,
        and the source domain that triggered it.

        Args:
            risk_level: The RiskLevel to publish for this location.
            location_id: Identifier of the shared space (e.g. "store_42").
            source_domain: Which agent domain triggered this (e.g. "health").
            message: Optional description. Must NOT contain personal data.

        Returns:
            The EnvironmentalContext that was published.
        """
        ctx = EnvironmentalContext(
            risk_level=risk_level,
            location_id=location_id,
            source_domain=source_domain,
            message=message,
        )
        self._universal_memory.publish_environmental_context(ctx)
        logger.info(
            "[Orchestrator] Environmental context published: %s @ %s",
            risk_level, location_id,
        )
        return ctx

    def read_environmental_context(
        self, location_id: str = "global"
    ) -> EnvironmentalContext | None:
        """
        Read the current EnvironmentalContext for a location.

        Returns None if no context has been published for this location.
        """
        return self._universal_memory.read_environmental_context(location_id)

    def read_all_environmental_contexts(self) -> dict[str, EnvironmentalContext]:
        """Return all published EnvironmentalContexts, keyed by location_id."""
        return self._universal_memory.read_all_environmental_contexts()

    # ── Native pipelines ─────────────────────────────────────────────────────

    def run_pipeline(
        self,
        steps: list[PipelineStep | str],
        input_data: dict[str, Any],
        emotional_state: str = "unknown",
        location_id: str = "global",
        *,
        execution_context: ExecutionContext | None = None,
    ) -> PipelineResult:
        """
        Run an ordered sequence of stages, each handled by a different
        registered agent, with explicit data flow between stages.

        This is a NEW, additive capability: process() (route-to-one /
        broadcast-to-all) is unchanged. Each stage executes through the
        exact same path as routed processing: same propagation of
        emotional_state and location_id, same EthicalFilter evaluation
        on publish, same audit log entries.

        Three guarantees define the mechanism:

        1. **Memory isolation between stages.** Each stage's input is
           passed explicitly: the previous stage's output, optionally
           reshaped by the step's ``transform``: never read from
           universal memory. Agents keep their own PrivateMemory and
           never see another stage's intermediate reasoning.

        2. **Fail-closed configuration.** All stage domains are
           validated before the first stage runs; an empty pipeline or
           an unknown domain raises before any side effect. A transform
           that returns a non-dict raises SETTConfigurationError at that
           stage.

        3. **Rejection handling as part of the mechanism.** If the
           EthicalFilter rejects a stage, that agent publishes nothing
           (the filter raises before the write), the remaining stages
           are skipped, and the rejection is returned EXPLICITLY in
           ``PipelineResult.rejection``: with the structured fields
           (action, score, threshold, principle, reasoning) taken from
           the exception's attributes. It is never written to, nor
           meant to be read from, universal memory.

        Args:
            steps: Ordered stages. Each element is a PipelineStep, or a
                   plain domain string (shorthand for
                   ``PipelineStep(domain)``).
            input_data: The pipeline's original input. The first stage
                        receives it as-is unless its transform says
                        otherwise; transforms of later stages also
                        receive it as their first argument.
            emotional_state: Propagated to every stage, same as process().
            location_id: Propagated to every stage, same as process().

        Returns:
            A PipelineResult with one StageOutcome per stage, the final
            output when completed, and the RejectionOutcome when halted.

        Raises:
            SETTConfigurationError: Empty pipeline, or a transform
                returned a non-dict.
            SETTAgentNotFoundError: A stage's domain has no registered
                agent (raised before any stage runs).
        """
        from sett.core_ruler.pipeline import (
            PipelineResult,
            PipelineStep,
            RejectionOutcome,
            StageOutcome,
        )
        from sett.exceptions import SETTConfigurationError

        if execution_context is not None and not isinstance(
            execution_context, ExecutionContext
        ):
            raise SETTValidationError(
                "execution_context must be an ExecutionContext or None."
            )
        root = execution_context or ExecutionContext.create()
        self._last_trace_id = root.trace_id
        trace_started = self._trace_recorder.record(
            root,
            kind="trace.started",
            component_type="orchestrator",
            component_name=self.__class__.__name__,
            status="started",
            reason_codes=("route.pipeline",),
            attributes={"mode": "pipeline", "stage_count": len(steps)},
        )
        pipeline_context = root.derive()
        pipeline_started = self._trace_recorder.record(
            pipeline_context,
            kind="pipeline.started",
            component_type="pipeline",
            component_name="native_pipeline",
            status="started",
            cause_id=trace_started.event_id,
            attributes={"stage_count": len(steps)},
        )

        last_pipeline_event_id = pipeline_started.event_id
        with execution_scope(root, trace_started.event_id):
            try:
                if not steps:
                    raise SETTConfigurationError(
                        "run_pipeline() requires at least one step. "
                        "An empty pipeline is a configuration error, not a no-op."
                    )

                # Normalize and validate the WHOLE pipeline before executing
                # any stage: configuration failures cannot produce effects.
                normalized: list[PipelineStep] = []
                for raw_step in steps:
                    if isinstance(raw_step, PipelineStep):
                        step = raw_step
                    elif isinstance(raw_step, str):
                        step = PipelineStep(domain=raw_step)
                    else:
                        raise SETTConfigurationError(
                            "Pipeline steps must be PipelineStep instances "
                            "or domain strings."
                        )
                    if not isinstance(step.domain, str) or not step.domain:
                        raise SETTConfigurationError(
                            "Pipeline stage domains must be non-empty strings."
                        )
                    normalized.append(step)
                for step in normalized:
                    self.get_agent(step.domain)

                outcomes: list[StageOutcome] = []
                prev_output: dict[str, Any] | None = None
                rejection: RejectionOutcome | None = None

                for index, step in enumerate(normalized):
                    stage_context = pipeline_context.derive()
                    stage_started = self._trace_recorder.record(
                        stage_context,
                        kind="pipeline.stage_started",
                        component_type="pipeline_stage",
                        component_name=step.domain,
                        status="started",
                        cause_id=last_pipeline_event_id,
                        attributes={"index": index, "domain": step.domain},
                    )
                    if rejection is not None:
                        outcomes.append(
                            StageOutcome(domain=step.domain, status="skipped")
                        )
                        stage_skipped = self._trace_recorder.record(
                            stage_context,
                            kind="pipeline.stage_skipped",
                            component_type="pipeline_stage",
                            component_name=step.domain,
                            status="skipped",
                            cause_id=stage_started.event_id,
                            reason_codes=(
                                "pipeline.previous_stage_rejected",
                            ),
                            attributes={"index": index},
                        )
                        last_pipeline_event_id = stage_skipped.event_id
                        continue

                    try:
                        # Explicit stage data flow: never through shared memory.
                        if step.transform is not None:
                            stage_input = step.transform(input_data, prev_output)
                            if not isinstance(stage_input, dict):
                                raise SETTConfigurationError(
                                    f"Pipeline stage '{step.domain}': transform "
                                    "must return a dict, got "
                                    f"{type(stage_input).__name__}."
                                )
                        else:
                            stage_input = input_data if index == 0 else prev_output

                        logger.debug(
                            "[Orchestrator] Pipeline stage %d -> '%s'",
                            index,
                            step.domain,
                        )
                        result, route_terminal = self._route_to_agent(
                            step.domain,
                            stage_input,
                            emotional_state,
                            location_id,
                            execution_context=stage_context,
                            cause_id=stage_started.event_id,
                            _return_event=True,
                        )
                    except SETTEthicalFilterRejectedError as error:
                        rejection = RejectionOutcome.from_error(
                            step.domain, error
                        )
                        outcomes.append(
                            StageOutcome(
                                domain=step.domain,
                                status="rejected",
                                rejection=rejection,
                            )
                        )
                        stage_rejected = self._trace_recorder.record(
                            stage_context,
                            kind="pipeline.stage_rejected",
                            component_type="pipeline_stage",
                            component_name=step.domain,
                            status="rejected",
                            cause_id=(
                                error.trace_event_id
                                or stage_started.event_id
                            ),
                            reason_codes=("policy.reject",),
                            attributes={"index": index},
                        )
                        last_pipeline_event_id = stage_rejected.event_id
                        logger.warning(
                            "[Orchestrator] Pipeline halted at stage %d "
                            "('%s'): EthicalFilter rejected.",
                            index,
                            step.domain,
                        )
                        continue
                    except Exception as error:
                        stage_failed = self._trace_recorder.record(
                            stage_context,
                            kind="pipeline.stage_failed",
                            component_type="pipeline_stage",
                            component_name=step.domain,
                            status="failed",
                            cause_id=(
                                getattr(error, "trace_event_id", None)
                                or stage_started.event_id
                            ),
                            reason_codes=("component.exception",),
                            attributes={
                                "index": index,
                                "error_type": type(error).__name__,
                            },
                        )
                        try:
                            error.trace_event_id = stage_failed.event_id
                        except (AttributeError, TypeError):
                            pass
                        raise

                    outcomes.append(
                        StageOutcome(
                            domain=step.domain,
                            status="completed",
                            output=result,
                        )
                    )
                    stage_completed = self._trace_recorder.record(
                        stage_context,
                        kind="pipeline.stage_completed",
                        component_type="pipeline_stage",
                        component_name=step.domain,
                        status="completed",
                        cause_id=route_terminal.event_id,
                        attributes={"index": index},
                    )
                    last_pipeline_event_id = stage_completed.event_id
                    prev_output = result

                completed = rejection is None
                result = PipelineResult(
                    completed=completed,
                    steps=tuple(outcomes),
                    output=prev_output if completed else None,
                    rejection=rejection,
                )
                pipeline_terminal = self._trace_recorder.record(
                    pipeline_context,
                    kind=(
                        "pipeline.completed"
                        if completed else "pipeline.rejected"
                    ),
                    component_type="pipeline",
                    component_name="native_pipeline",
                    status="completed" if completed else "rejected",
                    cause_id=last_pipeline_event_id,
                    reason_codes=() if completed else ("policy.reject",),
                )
                self._trace_recorder.record(
                    root,
                    kind="trace.completed",
                    component_type="orchestrator",
                    component_name=self.__class__.__name__,
                    status="completed" if completed else "rejected",
                    cause_id=pipeline_terminal.event_id,
                )
                return result
            except Exception as error:
                pipeline_failed = self._trace_recorder.record(
                    pipeline_context,
                    kind="pipeline.failed",
                    component_type="pipeline",
                    component_name="native_pipeline",
                    status="failed",
                    cause_id=(
                        getattr(error, "trace_event_id", None)
                        or last_pipeline_event_id
                    ),
                    reason_codes=("component.exception",),
                    attributes={"error_type": type(error).__name__},
                )
                trace_failed = self._trace_recorder.record(
                    root,
                    kind="trace.failed",
                    component_type="orchestrator",
                    component_name=self.__class__.__name__,
                    status="failed",
                    cause_id=pipeline_failed.event_id,
                    reason_codes=("component.exception",),
                    attributes={"error_type": type(error).__name__},
                )
                try:
                    error.trace_event_id = trace_failed.event_id
                except (AttributeError, TypeError):
                    pass
                raise

    # ── Audit and introspection ──────────────────────────────────────────────

    def get_ethical_audit_log(self) -> list[dict[str, Any]]:
        """
        Return the full audit log of all ethical decisions.
        Useful for compliance, debugging, and reporting.
        """
        return self._ethical_filter.get_audit_log()

    def verify_ethical_audit_log(self) -> bool:
        """
        Verify the sequence and hash chain of the ethical audit log
        returned by get_ethical_audit_log().

        Delegates to EthicalFilter.verify_audit_log(): the same
        tamper-evidence guarantee added in v0.8.0, made reachable from
        the orchestrator, the entry point every example in the docs
        already uses, instead of requiring access to the private
        `_ethical_filter` attribute.
        """
        return self._ethical_filter.verify_audit_log()

    def get_trace(self, trace_id: str) -> tuple[TraceEvent, ...]:
        """Return immutable events for one execution trace."""
        return self._trace_recorder.get_trace(trace_id)

    def export_trace(
        self,
        trace_id: str,
        *,
        view: str = "sanitized",
    ) -> tuple[dict[str, Any], ...]:
        """Export a defensive privacy-safe trace view."""
        return self._trace_recorder.export_trace(trace_id, view=view)

    def register_trace_exporter(self, exporter: TraceExporter) -> None:
        """Register a callable that receives each sanitized event."""
        self._trace_recorder.register_exporter(exporter)

    def verify_traces(self, trace_id: str | None = None) -> bool:
        """Verify recorder hash integrity and causal references."""
        return self._trace_recorder.verify(trace_id)

    @property
    def last_trace_id(self) -> str | None:
        """Most recently started trace; intended for sequential debugging."""
        return self._last_trace_id

    @property
    def registered_domains(self) -> list[str]:
        """List of all registered agent domains."""
        return list(self._agents.keys())

    def __repr__(self) -> str:
        return f"SETTOrchestrator(domains={self.registered_domains})"
