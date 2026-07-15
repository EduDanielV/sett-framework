"""
SETT Framework — SETTAgent
==============================
An agent is a domain specialist composed of multiple experts.

Each agent:
- Is specialized in one domain (health, communications, schedule, etc.)
- Contains one or more SETTExperts that do the actual work
- Maintains its own PrivateMemory (not accessible from outside)
- Publishes ONLY the final result to the UniversalMemory
- Does not communicate directly with other agents

Agents are the building blocks that the orchestrator coordinates.

v0.1.1 fix: the orchestrator now sets self._current_emotional_state and
self._current_location_id on the agent right before calling process().
_publish_to_universal() reads them automatically and forwards them to the
EthicalFilter, together with the location's EnvironmentalContext (if any).
No existing agent subclass needs to change — process() and
_publish_to_universal(result) keep their original signatures.

v0.2.0: two mechanisms are now available for real-world side effects
(sending a message, calling an external API, contacting emergency
services, etc.), which the EthicalFilter does NOT automatically intercept
just because a result was published to universal memory:

- propose_action() — lightweight, opt-in. The developer calls it manually
  before performing the effect themselves. No setup required.
- submit_action() — stronger, structural guarantee via a registered
  SETTExecutor. The agent never touches the real client; it only
  describes intent as an Action. Requires an Executor with a handler
  registered for that action_type. See sett/core_ruler/executor.py.

Both are supported and not mutually exclusive — use propose_action() for
quick/low-stakes effects, submit_action() for the ones where "the
developer forgot to gate it" is not an acceptable failure mode.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from sett.core_ruler.expert import SETTExpert
from sett.memory_ruler.private import PrivateMemory
from sett.exceptions import SETTExpertNotFoundError, SETTConfigurationError

if TYPE_CHECKING:
    from sett.memory_ruler.universal import UniversalMemory
    from sett.risk_ruler.risk_profile import RiskProfile
    from sett.core_ruler.executor import SETTExecutor


class SETTAgent(ABC):
    """
    Abstract base class for all SETT agents.

    To create a new agent, extend this class, register your experts
    in __init__, and implement process().

    The process() method is the agent's main entry point. It should:
    1. Coordinate its experts
    2. Use private memory to store intermediate results
    3. Compose a final result
    4. Call self._publish_to_universal(result) before returning
    5. Return the final result

    Example:
        class HealthAgent(SETTAgent):
            def __init__(self):
                super().__init__(name="HealthAgent", domain="health")
                self.register_expert(HeartRateExpert(name="heart_rate"))
                self.register_expert(TemperatureExpert(name="temperature"))

            def process(self, input_data):
                hr_result = self.get_expert("heart_rate").resolve(input_data)
                temp_result = self.get_expert("temperature").resolve(input_data)
                final = {**hr_result, **temp_result, "status": "ok"}
                self._publish_to_universal(final)
                return final

    Side effects (sending a message, calling an external API, executing a
    payment, etc.) are NOT automatically intercepted by the EthicalFilter —
    the filter only evaluates what gets published to universal memory.
    If your expert performs a real side effect, gate it explicitly, using
    either propose_action() or submit_action() (see module docstring).
    """

    def __init__(self, name: str, domain: str) -> None:
        """
        Args:
            name: A human-readable name for this agent (e.g., "HealthAgent").
            domain: The domain key used by the orchestrator to route input to this
                    agent (e.g., "health", "communications", "schedule").
        """
        self.name = name
        self.domain = domain
        self._private_memory = PrivateMemory(owner=self.name)
        self._experts: dict[str, SETTExpert] = {}
        self._universal_memory: UniversalMemory | None = None

        # Set by the orchestrator immediately before calling process().
        # Read automatically by _publish_to_universal() and propose_action()
        # so existing agent subclasses don't need to change their signatures.
        self._current_emotional_state: str = "unknown"
        self._current_location_id: str = "global"

        # Set by the orchestrator via attach_executor() if a SETTExecutor
        # was registered. None means no Executor is configured — in that
        # case submit_action() raises SETTConfigurationError, since a
        # missing Executor should fail closed, not silently no-op.
        self._executor: "SETTExecutor | None" = None

    def register_expert(self, expert: SETTExpert) -> None:
        """
        Register an expert with this agent.
        Gives the expert access to this agent's private memory.

        Args:
            expert: A SETTExpert instance. Its name must be unique within this agent.
        """
        expert.attach_memory(self._private_memory)
        self._experts[expert.name] = expert

    def attach_universal_memory(self, memory: UniversalMemory) -> None:
        """
        Called by the orchestrator during agent registration.
        Connects this agent to the shared universal memory.
        Do not call this manually.
        """
        self._universal_memory = memory

    def attach_executor(self, executor: "SETTExecutor") -> None:
        """
        Called by the orchestrator when a SETTExecutor is registered.
        Connects this agent to it so submit_action() can be used.
        Do not call this manually.
        """
        self._executor = executor

    def get_expert(self, name: str) -> SETTExpert:
        """
        Retrieve a registered expert by name.

        Args:
            name: The name given to the expert at instantiation.

        Returns:
            The requested SETTExpert.

        Raises:
            SETTExpertNotFoundError: If no expert with that name is registered.
        """
        if name not in self._experts:
            raise SETTExpertNotFoundError(
                f"Expert '{name}' not found in agent '{self.name}'. "
                f"Registered experts: {list(self._experts.keys())}"
            )
        return self._experts[name]

    def _publish_to_universal(
        self,
        result: dict[str, Any],
        risk_profile: "RiskProfile | None" = None,
    ) -> None:
        """
        Publish the agent's final result to universal memory.
        This is the ONLY way an agent communicates outward.
        The result passes through the EthicalFilter before being stored.

        Automatically forwards the current emotional_state (set by the
        orchestrator before calling process()) and the EnvironmentalContext
        for the agent's current location, so the full three-layer risk
        system is actually exercised in the real flow — not just in tests.

        Call this at the end of process() before returning.

        Args:
            result: The final synthesized result of this agent's work.
            risk_profile: Optional three-pillar RiskProfile computed by this
                agent for the current user. Used only to evaluate this write —
                it is never stored in universal memory (privacy contract).
        """
        if self._universal_memory is None:
            return

        environmental_context = self._universal_memory.read_environmental_context(
            self._current_location_id
        )
        self._universal_memory.update(
            agent=self.domain,
            result=result,
            emotional_state=self._current_emotional_state,
            risk_profile=risk_profile,
            environmental_context=environmental_context,
        )

    def propose_action(
        self,
        action: str,
        action_context: dict[str, Any] | None = None,
        risk_profile: "RiskProfile | None" = None,
    ) -> None:
        """
        Gate a real-world side effect through the EthicalFilter BEFORE it
        is executed — as opposed to _publish_to_universal(), which only
        evaluates the result AFTER an action already happened.

        Call this from within resolve()/process(), before performing any
        effect with consequences outside the system: sending a message,
        calling an external API, writing to a database, executing a
        payment, contacting emergency services, etc.

        Lightweight and opt-in: the developer must remember to call this.
        For a structural guarantee where forgetting is not an option, use
        submit_action() with a registered SETTExecutor instead.

        Args:
            action: Description of the action about to be executed
                    (e.g. "send_sms", "call_external_api", "charge_payment").
            action_context: Data relevant to this specific action.
            risk_profile: Optional RiskProfile for the current user.

        Raises:
            SETTEthicalFilterRejectedError: If the action is blocked.
                The side effect must NOT be executed in that case.
        """
        if self._universal_memory is None:
            return

        environmental_context = self._universal_memory.read_environmental_context(
            self._current_location_id
        )
        self._universal_memory.evaluate_action(
            action=action,
            context=action_context or {},
            emotional_state=self._current_emotional_state,
            risk_profile=risk_profile,
            environmental_context=environmental_context,
        )

    def submit_action(
        self,
        action_type: str,
        payload: dict[str, Any] | None = None,
        risk_profile: "RiskProfile | None" = None,
    ) -> Any:
        """
        Submit a real-world side effect as data (an Action) to the
        registered SETTExecutor, instead of performing it directly.

        This is the structural alternative to propose_action(): the
        expert/agent never calls the real client (SMS provider, payment
        API, etc.) itself. It only describes intent. The Executor is the
        one and only place where the real effect can happen, and only
        after the EthicalFilter approves it.

        Requires a SETTExecutor to be registered with the orchestrator
        (via orchestrator.register_executor(executor)) with a handler
        for this action_type already registered. If either is missing,
        this fails closed — no side effect happens.

        Args:
            action_type: Must match a handler registered on the Executor
                         (e.g. "send_sms", "call_emergency_services").
            payload: Data the handler needs to perform the effect.
            risk_profile: Optional three-pillar RiskProfile for this user.

        Returns:
            Whatever the registered handler returns.

        Raises:
            SETTConfigurationError: If no Executor is registered with this
                agent, or no handler is registered for this action_type.
            SETTEthicalFilterRejectedError: If the EthicalFilter blocks
                the action. The handler is never called in that case.
        """
        from sett.core_ruler.action import Action

        if self._executor is None:
            raise SETTConfigurationError(
                f"Agent '{self.name}' tried to submit_action('{action_type}') "
                f"but no SETTExecutor is registered with this orchestrator. "
                f"Call orchestrator.register_executor(executor) first, or use "
                f"self.propose_action(...) if you don't need the Executor's "
                f"handler-execution guarantee."
            )

        action = Action(
            action_type=action_type,
            payload=payload or {},
            proposed_by=self.domain,
        )
        return self._executor.submit(
            action,
            emotional_state=self._current_emotional_state,
            risk_profile=risk_profile,
            location_id=self._current_location_id,
        )

    @abstractmethod
    def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """
        Main processing method. Must be implemented by every subclass.

        Coordinates the agent's experts, uses private memory for intermediate
        state, composes a final result, and publishes it to universal memory.

        Args:
            input_data: The data this agent needs to process.

        Returns:
            The final synthesized result of this agent's work.
        """
        pass

    @property
    def experts(self) -> list[str]:
        """Names of all registered experts."""
        return list(self._experts.keys())

    def __repr__(self) -> str:
        return (
            f"SETTAgent(name={self.name!r}, "
            f"domain={self.domain!r}, "
            f"experts={self.experts})"
        )
