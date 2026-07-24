"""
SETT Framework — ElevenLabs TTS Adapter
==============================
Text-to-speech adapter for ElevenLabs (https://elevenlabs.io).

Implements TTSBase — fully interchangeable with GoogleTTSAdapter or
any other TTS provider. ElevenLabs has no STT product, so there is no
ElevenLabsSTTAdapter and none is implied by this module — see
services_tts_stt/base.py's docstring on why TTSBase/STTBase are
separate interfaces.

Talks to ElevenLabs' REST API directly via `requests` — no ElevenLabs
SDK dependency, same reasoning as OllamaAdapter using only stdlib for
Ollama's local API (services_llm/ollama.py).

Ported from the ElevenLabs patch archived in
Archivo_legado/AIDA_full_voz/aida_elevenlabs_patch.zip (originally one
engine among several in a multi-engine tts.py dispatcher). Only the
ElevenLabs HTTP call is carried over — engine selection, local
playback, and output-file pruning were application-layer concerns in
that script and do not belong in a stateless adapter.

Requires: pip install sett-framework[elevenlabs]
"""
from __future__ import annotations
import os
from typing import Any

from sett.services_tts_stt.base import TTSBase
from sett.exceptions import SETTServiceAdapterError

try:
    import requests
except ImportError:
    requests = None


class ElevenLabsTTSAdapter(TTSBase):
    """
    Text-to-speech adapter for ElevenLabs.

    Usage:
        from sett.services_tts_stt.elevenlabs import ElevenLabsTTSAdapter

        tts = ElevenLabsTTSAdapter(api_key="your-key")
        audio_bytes = tts.synthesize("Hola, ¿en qué puedo ayudarte?")
    """

    DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"
    DEFAULT_MODEL_ID = "eleven_multilingual_v2"
    DEFAULT_STABILITY = 0.5
    DEFAULT_SIMILARITY_BOOST = 0.75
    DEFAULT_STYLE = 0.35
    DEFAULT_TIMEOUT_SECONDS = 60

    def __init__(
        self,
        api_key: str | None = None,
        voice_id: str = DEFAULT_VOICE_ID,
        model_id: str = DEFAULT_MODEL_ID,
        stability: float = DEFAULT_STABILITY,
        similarity_boost: float = DEFAULT_SIMILARITY_BOOST,
        style: float = DEFAULT_STYLE,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        """
        Args:
            api_key: ElevenLabs API key. Falls back to the
                ELEVENLABS_API_KEY environment variable.
            voice_id: ElevenLabs voice ID. Defaults to a stock voice.
            model_id: ElevenLabs model ID.
            stability: Voice stability (0.0 to 1.0).
            similarity_boost: Voice similarity boost (0.0 to 1.0).
            style: Style exaggeration (0.0 to 1.0).
            timeout_seconds: HTTP request timeout.
        """
        if requests is None:
            raise SETTServiceAdapterError(
                "The 'requests' package is required to use "
                "ElevenLabsTTSAdapter. Install it with: "
                "pip install sett-framework[elevenlabs]"
            )

        self._api_key = api_key or os.getenv("ELEVENLABS_API_KEY", "").strip()
        if not self._api_key:
            raise SETTServiceAdapterError(
                "ElevenLabs API key not found. "
                "Pass api_key= or set the ELEVENLABS_API_KEY environment variable."
            )

        self._voice_id = voice_id
        self._model_id = model_id
        self._stability = min(1.0, max(0.0, stability))
        self._similarity_boost = min(1.0, max(0.0, similarity_boost))
        self._style = min(1.0, max(0.0, style))
        self._timeout_seconds = timeout_seconds

    @property
    def audio_format(self) -> str:
        return "mp3"

    def synthesize(self, text: str, **kwargs: Any) -> bytes:
        """Synthesize speech audio (MP3 bytes) for the given text."""
        voice_id = kwargs.get("voice_id", self._voice_id)
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "accept": "audio/mpeg",
            "xi-api-key": self._api_key,
            "content-type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": kwargs.get("model_id", self._model_id),
            "voice_settings": {
                "stability": kwargs.get("stability", self._stability),
                "similarity_boost": kwargs.get(
                    "similarity_boost", self._similarity_boost
                ),
                "style": kwargs.get("style", self._style),
                "use_speaker_boost": kwargs.get("use_speaker_boost", True),
            },
        }

        try:
            response = requests.post(
                url, headers=headers, json=payload, timeout=self._timeout_seconds
            )
        except requests.exceptions.RequestException as e:
            raise SETTServiceAdapterError(
                f"Could not reach ElevenLabs: {e}"
            ) from e

        if response.status_code != 200:
            raise SETTServiceAdapterError(
                f"ElevenLabs API error: {response.status_code} - "
                f"{response.text[:500]}"
            )

        return response.content

    def __repr__(self) -> str:
        return f"ElevenLabsTTSAdapter(voice_id={self._voice_id!r})"
