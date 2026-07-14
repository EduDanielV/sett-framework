"""
SETT Framework — LLM Base Adapter
==============================
Abstract interface that all LLM adapters must implement.

This ensures SETT is not tied to any specific language model.
Swap Claude for GPT, Gemini, or a local model by changing
the adapter — no other code needs to change.

Following the same intercambiability philosophy for TTS/STT in services_tts_stt/
and generative AI in services_gen_ai/.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any


class LLMBase(ABC):
    """
    Abstract base class for all LLM adapters in SETT.

    Any language model must implement this interface to be used
    as the reasoning engine inside a SETTExpert or SETTAgent.

    Implement two methods:
    - complete(): for one-shot prompts (no conversation history)
    - chat(): for multi-turn conversations

    Example (minimal implementation):
        class MyCustomAdapter(LLMBase):
            @property
            def model_name(self):
                return "my-model-v1"

            def complete(self, prompt, system="", **kwargs):
                return my_api.generate(prompt)

            def chat(self, messages, system="", **kwargs):
                return my_api.chat(messages)
    """

    @abstractmethod
    def complete(self, prompt: str, system: str = "", **kwargs: Any) -> str:
        """
        Generate a single completion without conversation history.
        Use this for one-shot tasks: summarization, classification, extraction.

        Args:
            prompt: The user prompt.
            system: Optional system instruction that sets the model's behavior.
            **kwargs: Model-specific parameters (temperature, max_tokens, etc.)

        Returns:
            The model's text response.
        """
        pass

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],
        system: str = "",
        **kwargs: Any,
    ) -> str:
        """
        Generate a response in a multi-turn conversation.
        Use this for agents that maintain conversation history.

        Args:
            messages: List of {"role": "user"|"assistant", "content": str}.
            system: Optional system instruction.
            **kwargs: Model-specific parameters.

        Returns:
            The model's text response.
        """
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the name or identifier of the underlying model."""
        pass
