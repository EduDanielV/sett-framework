"""
SETT Framework — SETTOrchestrator
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
from typing import Any
import logging

from sett.core_ruler.agent import SETTAgent
from sett.memory_ruler.universal import UniversalMemory
from sett.ethics_ruler.ethic_kernel.filter import EthicalFilter
from sett.risk_ruler.risk_level import RiskLevel
from sett.risk_ruler.environmental_context import EnvironmentalContext
from sett.exceptions import (
    SETTAgentNotFoundError,
    SETTEthicalFilterRejectedError,
)

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
        self._executor = None  # SETTExecutor | None — set via register_executor()

        # Connect the ethical filter to universal memory
        # Every write to universal memory will pass through it
        self._universal_memory.set_ethical_filter(self._ethical_filter)

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
        if self._executor is not None:
            agent.attach_executor(self._executor)
        self._agents[agent.domain] = agent
        logger.info(
            "[Orchestrator] Agent registered: '%s' (domain: '%s')",
            agent.name, agent.domain
        )

    def register_executor(self, executor) -> None:
        """
        Register a SETTExecutor with this orchestrator. Gives it access
        to universal memory (so it can evaluate actions through the
        EthicalFilter and read EnvironmentalContext), and attaches it to
        every agent already registered — as well as to any agent
        registered afterward, automatically.

        Args:
            executor: A SETTExecutor instance.
        """
        self._executor = executor
        executor.attach_universal_memory(self._universal_memory)
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
    ) -> dict[str, Any]:
        """
        Process an input through the system.

        If domain is specified, routes directly to that agent.
        If no domain is given, broadcasts to all agents and collects results.

        v0.1.1 fix: emotional_state and location_id are now actually
        propagated to the agent (and from there, automatically, to the
        EthicalFilter via _publish_to_universal()). Previously
        emotional_state was accepted here but silently dropped before
        reaching agent.process() — every real evaluation ran with
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
        if domain:
            return self._route_to_agent(domain, input_data, emotional_state, location_id)
        else:
            return self._broadcast(input_data, emotional_state, location_id)

    def _route_to_agent(
        self,
        domain: str,
        input_data: dict[str, Any],
        emotional_state: str,
        location_id: str = "global",
    ) -> dict[str, Any]:
        """Route input to a specific agent."""
        agent = self.get_agent(domain)
        agent._current_emotional_state = emotional_state
        agent._current_location_id = location_id
        try:
            logger.debug(
                "[Orchestrator] Routing to agent '%s' (domain: '%s')",
                agent.name, domain
            )
            result = agent.process(input_data)
            return result
        except SETTEthicalFilterRejectedError:
            logger.warning(
                "[Orchestrator] EthicalFilter blocked action from agent '%s'.",
                agent.name
            )
            raise

    def _broadcast(
        self,
        input_data: dict[str, Any],
        emotional_state: str,
        location_id: str = "global",
    ) -> dict[str, Any]:
        """
        Broadcast input to all registered agents and collect results.
        Agents that are blocked by the EthicalFilter have their error recorded.
        """
        results: dict[str, Any] = {}
        for domain, agent in self._agents.items():
            agent._current_emotional_state = emotional_state
            agent._current_location_id = location_id
            try:
                results[domain] = agent.process(input_data)
            except SETTEthicalFilterRejectedError as e:
                results[domain] = {"blocked": True, "reason": str(e)}
                logger.warning(
                    "[Orchestrator] Agent '%s' blocked during broadcast.", agent.name
                )
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

        No personal data is published — only the RiskLevel, location,
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
        steps: list["PipelineStep | str"],
        input_data: dict[str, Any],
        emotional_state: str = "unknown",
        location_id: str = "global",
    ) -> "PipelineResult":
        """
        Run an ordered sequence of stages, each handled by a different
        registered agent, with explicit data flow between stages.

        This is a NEW, additive capability: process() (route-to-one /
        broadcast-to-all) is unchanged. Each stage executes through the
        exact same path as routed processing — same propagation of
        emotional_state and location_id, same EthicalFilter evaluation
        on publish, same audit log entries.

        Three guarantees define the mechanism:

        1. **Memory isolation between stages.** Each stage's input is
           passed explicitly — the previous stage's output, optionally
           reshaped by the step's ``transform`` — never read from
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
           ``PipelineResult.rejection`` — with the structured fields
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

        if not steps:
            raise SETTConfigurationError(
                "run_pipeline() requires at least one step. "
                "An empty pipeline is a configuration error, not a no-op."
            )

        # Normalize shorthand and validate the WHOLE pipeline before
        # executing anything — fail closed, no partial side effects.
        normalized: list[PipelineStep] = [
            step if isinstance(step, PipelineStep) else PipelineStep(domain=step)
            for step in steps
        ]
        for step in normalized:
            self.get_agent(step.domain)  # raises SETTAgentNotFoundError

        outcomes: list[StageOutcome] = []
        prev_output: dict[str, Any] | None = None
        rejection: RejectionOutcome | None = None

        for index, step in enumerate(normalized):
            if rejection is not None:
                outcomes.append(StageOutcome(domain=step.domain, status="skipped"))
                continue

            # Explicit data flow — never via universal memory.
            if step.transform is not None:
                stage_input = step.transform(input_data, prev_output)
                if not isinstance(stage_input, dict):
                    raise SETTConfigurationError(
                        f"Pipeline stage '{step.domain}': transform must "
                        f"return a dict, got {type(stage_input).__name__}."
                    )
            else:
                stage_input = input_data if index == 0 else prev_output

            try:
                logger.debug(
                    "[Orchestrator] Pipeline stage %d -> '%s'",
                    index, step.domain,
                )
                result = self._route_to_agent(
                    step.domain, stage_input, emotional_state, location_id
                )
                outcomes.append(StageOutcome(
                    domain=step.domain, status="completed", output=result,
                ))
                prev_output = result
            except SETTEthicalFilterRejectedError as e:
                rejection = RejectionOutcome.from_error(step.domain, e)
                outcomes.append(StageOutcome(
                    domain=step.domain, status="rejected", rejection=rejection,
                ))
                logger.warning(
                    "[Orchestrator] Pipeline halted at stage %d ('%s'): "
                    "EthicalFilter rejected.",
                    index, step.domain,
                )

        completed = rejection is None
        return PipelineResult(
            completed=completed,
            steps=tuple(outcomes),
            output=prev_output if completed else None,
            rejection=rejection,
        )

    # ── Audit and introspection ──────────────────────────────────────────────

    def get_ethical_audit_log(self) -> list[dict[str, Any]]:
        """
        Return the full audit log of all ethical decisions.
        Useful for compliance, debugging, and reporting.
        """
        return self._ethical_filter.get_audit_log()

    @property
    def registered_domains(self) -> list[str]:
        """List of all registered agent domains."""
        return list(self._agents.keys())

    def __repr__(self) -> str:
        return f"SETTOrchestrator(domains={self.registered_domains})"
