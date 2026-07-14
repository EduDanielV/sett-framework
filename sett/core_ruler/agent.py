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
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from sett.core_ruler.expert import SETTExpert
from sett.memory_ruler.private import PrivateMemory
from sett.exceptions import SETTExpertNotFoundError

if TYPE_CHECKING:
    from sett.memory_ruler.universal import UniversalMemory


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

    def _publish_to_universal(self, result: dict[str, Any]) -> None:
        """
        Publish the agent's final result to universal memory.
        This is the ONLY way an agent communicates outward.
        The result passes through the EthicalFilter before being stored.

        Call this at the end of process() before returning.

        Args:
            result: The final synthesized result of this agent's work.
        """
        if self._universal_memory is not None:
            self._universal_memory.update(agent=self.domain, result=result)

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
