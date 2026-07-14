"""
SETT Framework — SETTExpert
==============================
The most atomic unit in SETT.

An expert is a specialized module that lives inside an agent.
It handles one specific task, updates the agent's private memory,
and returns a result that the agent uses to compose its final output.

Several experts form one agent — that is the core of the SETT hierarchy.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
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

    def attach_memory(self, memory: PrivateMemory) -> None:
        """
        Called by the parent agent during registration.
        Gives this expert access to the agent's private memory.
        Do not call this manually.
        """
        self._private_memory = memory

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
        pass

    def __repr__(self) -> str:
        return f"SETTExpert(name={self.name!r})"
