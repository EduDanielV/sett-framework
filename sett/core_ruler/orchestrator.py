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

        # Connect the ethical filter to universal memory
        # Every write to universal memory will pass through it
        self._universal_memory.set_ethical_filter(self._ethical_filter)

    def register_agent(self, agent: SETTAgent) -> None:
        """
        Register an agent with the orchestrator.
        Connects the agent to universal memory.

        Args:
            agent: A SETTAgent instance. Its domain must be unique.
        """
        agent.attach_universal_memory(self._universal_memory)
        self._agents[agent.domain] = agent
        logger.info(
            "[Orchestrator] Agent registered: '%s' (domain: '%s')",
            agent.name, agent.domain
        )

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
    ) -> dict[str, Any]:
        """
        Process an input through the system.

        If domain is specified, routes directly to that agent.
        If no domain is given, broadcasts to all agents and collects results.

        Args:
            input_data: The data to process.
            domain: Optional domain to route to a specific agent.
            emotional_state: The detected emotional state of the user.
                             When integrated with the Sentiment Analyzer agent,
                             this is passed automatically to the EthicalFilter.

        Returns:
            The result from the agent (or a dict of results from all agents).
        """
        if domain:
            return self._route_to_agent(domain, input_data, emotional_state)
        else:
            return self._broadcast(input_data, emotional_state)

    def _route_to_agent(
        self,
        domain: str,
        input_data: dict[str, Any],
        emotional_state: str,
    ) -> dict[str, Any]:
        """Route input to a specific agent."""
        agent = self.get_agent(domain)
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
    ) -> dict[str, Any]:
        """
        Broadcast input to all registered agents and collect results.
        Agents that are blocked by the EthicalFilter have their error recorded.
        """
        results: dict[str, Any] = {}
        for domain, agent in self._agents.items():
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
