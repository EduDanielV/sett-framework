"""
SETT Framework — OpenAI (GPT) Adapter
==============================
LLM adapter for OpenAI's GPT models.

Implements the LLMBase interface — fully interchangeable with
AnthropicAdapter or GeminiAdapter.

Requires: pip install sett-framework[openai]
"""
from __future__ import annotations
import os
from typing import Any

from sett.services_llm.base import LLMBase
from sett.exceptions import SETTLLMAdapterError


class OpenAIAdapter(LLMBase):
    """
    LLM adapter for OpenAI's GPT models.

    Usage:
        from sett.services_llm.openai import OpenAIAdapter

        llm = OpenAIAdapter(
            api_key="your-key",
            model="gpt-4o"
        )
        response = llm.complete("What is SETT?")
    """

    DEFAULT_MODEL = "gpt-4o"
    DEFAULT_MAX_TOKENS = 1024
    DEFAULT_TEMPERATURE = 0.75

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> None:
        try:
            import openai as _openai
            self._openai = _openai
        except ImportError:
            raise SETTLLMAdapterError(
                "The 'openai' package is required to use the OpenAIAdapter. "
                "Install it with: pip install sett-framework[openai]"
            )

        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "").strip()
        if not self._api_key:
            raise SETTLLMAdapterError(
                "OpenAI API key not found. "
                "Pass api_key= or set the OPENAI_API_KEY environment variable."
            )

        self._model = model
        self._max_tokens = max_tokens
        self._temperature = min(1.0, max(0.0, temperature))
        self._client = self._openai.OpenAI(api_key=self._api_key)

    @property
    def model_name(self) -> str:
        return self._model

    def complete(self, prompt: str, system: str = "", **kwargs: Any) -> str:
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                max_tokens=kwargs.get("max_tokens", self._max_tokens),
                temperature=kwargs.get("temperature", self._temperature),
                messages=[
                    {"role": "system", "content": system or "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            raise SETTLLMAdapterError(
                f"OpenAI API error during complete(): {e}"
            ) from e

    def chat(
        self,
        messages: list[dict[str, str]],
        system: str = "",
        **kwargs: Any,
    ) -> str:
        try:
            full_messages = []
            if system:
                full_messages.append({"role": "system", "content": system})
            full_messages.extend(messages)

            resp = self._client.chat.completions.create(
                model=self._model,
                max_tokens=kwargs.get("max_tokens", self._max_tokens),
                temperature=kwargs.get("temperature", self._temperature),
                messages=full_messages,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            raise SETTLLMAdapterError(
                f"OpenAI API error during chat(): {e}"
            ) from e

    def __repr__(self) -> str:
        return f"OpenAIAdapter(model={self._model!r})"
