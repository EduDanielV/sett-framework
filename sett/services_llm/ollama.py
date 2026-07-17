"""
SETT Framework — Ollama (local) Adapter
==============================
LLM adapter for locally-running models via Ollama (https://ollama.com).

No API key, no cloud, no cost — the model runs entirely on your own
machine. Requires ONLY that Ollama itself be installed and running
(`ollama serve`, usually started automatically) with at least one model
pulled (e.g. `ollama pull qwen3:1.7b`).

Unlike AnthropicAdapter/OpenAIAdapter/GeminiAdapter, this adapter has
NO extra pip dependency at all — it talks to Ollama's local REST API
using only Python's standard library (urllib). If you can run
`ollama pull <model>` and `ollama serve`, this adapter works with
nothing else to install on the Python side.

Recommended low-resource models (verified good picks as of 2026 for
machines without a dedicated GPU):
    - qwen3:1.7b     — lightest, ~4GB RAM, strong multilingual support
    - phi4-mini      — 3.8B, MIT license, built for CPU-only machines

Implements the LLMBase interface — fully interchangeable with the
cloud adapters. This is what makes SETT's principle 4 ("LLM as engine,
not architecture") concrete: swapping AnthropicAdapter for
OllamaAdapter changes zero lines anywhere else in your system.
"""
from __future__ import annotations
import json
import urllib.request
import urllib.error
from typing import Any

from sett.services_llm.base import LLMBase
from sett.exceptions import SETTLLMAdapterError


class OllamaAdapter(LLMBase):
    """
    LLM adapter for locally-running Ollama models. No API key, no cost.

    Usage:
        from sett.services_llm.ollama import OllamaAdapter

        llm = OllamaAdapter(model="qwen3:1.7b")
        response = llm.complete("What is SETT?")

    Before first use:
        1. Install Ollama: https://ollama.com/download
        2. Pull a model:   ollama pull qwen3:1.7b
        3. Make sure Ollama is running (it usually starts automatically
           as a background service after installation).
    """

    DEFAULT_MODEL = "qwen3:1.7b"
    DEFAULT_BASE_URL = "http://localhost:11434"
    DEFAULT_TEMPERATURE = 0.75
    DEFAULT_TIMEOUT_SECONDS = 30

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        temperature: float = DEFAULT_TEMPERATURE,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        """
        Args:
            model: The Ollama model tag to use (must already be pulled
                   locally — run `ollama pull <model>` first).
            base_url: Where Ollama's local server is listening. Default
                      is correct for almost everyone; only change this
                      if you moved Ollama to a different port/host.
            temperature: Sampling temperature (0.0 to 1.0).
            timeout_seconds: How long to wait for a response before
                giving up. Local CPU inference can be slow — raise this
                if you see timeouts on a low-resource machine.
        """
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._temperature = min(1.0, max(0.0, temperature))
        self._timeout_seconds = timeout_seconds

    @property
    def model_name(self) -> str:
        return self._model

    def complete(self, prompt: str, system: str = "", **kwargs: Any) -> str:
        """One-shot completion — no conversation history."""
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": kwargs.get("temperature", self._temperature)},
        }
        if system:
            payload["system"] = system

        data = self._post("/api/generate", payload)
        return data.get("response", "")

    def chat(
        self,
        messages: list[dict[str, str]],
        system: str = "",
        **kwargs: Any,
    ) -> str:
        """Multi-turn conversation completion."""
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": full_messages,
            "stream": False,
            "options": {"temperature": kwargs.get("temperature", self._temperature)},
        }

        data = self._post("/api/chat", payload)
        return data.get("message", {}).get("content", "")

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """
        POST JSON to the local Ollama server using only the standard
        library — no extra pip dependency required for this adapter.
        """
        url = f"{self._base_url}{path}"
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise SETTLLMAdapterError(
                f"Could not reach Ollama at {self._base_url}. "
                f"Is Ollama installed and running? "
                f"Try 'ollama serve' or check that the Ollama app is open. "
                f"Original error: {e}"
            ) from e
        except json.JSONDecodeError as e:
            raise SETTLLMAdapterError(
                f"Ollama returned a response that wasn't valid JSON: {e}"
            ) from e
        except TimeoutError as e:
            raise SETTLLMAdapterError(
                f"Ollama did not respond within {self._timeout_seconds}s. "
                f"Local CPU inference can be slow on the first call (the "
                f"model needs to load into memory) — try again, or raise "
                f"timeout_seconds if this keeps happening."
            ) from e

    def __repr__(self) -> str:
        return f"OllamaAdapter(model={self._model!r}, base_url={self._base_url!r})"
