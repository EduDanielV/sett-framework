"""
SETT Framework — TTS/STT Base Adapters
==============================
Abstract interfaces that all text-to-speech and speech-to-text
adapters must implement.

Same intercambiability philosophy as LLMBase (sett/services_llm/base.py):
swap Google Cloud for ElevenLabs, or any future provider, by changing
the adapter — no other code needs to change. An Expert or Agent that
needs voice depends on TTSBase/STTBase, never on a specific provider's
SDK.

TTSBase and STTBase are deliberately two separate interfaces, not one
merged "voice" interface — a provider is free to implement only one of
them (ElevenLabs, historically TTS-only, implements TTSBase and has no
STTBase adapter; nothing about the interface forces it to pretend
otherwise). See SETT_Convenciones_v2.md, entrada sobre nomenclatura de
servicios: los adapters de un mismo proveedor se agrupan por archivo
(sett/services_tts_stt/google.py trae GoogleTTSAdapter Y
GoogleSTTAdapter, comparten credenciales), no por clase — cada clase
implementa una sola interfaz, para que el aislamiento de tests y la
intercambiabilidad no se pierdan.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any


class TTSBase(ABC):
    """
    Abstract base class for all text-to-speech adapters in SETT.

    Implement one method:
    - synthesize(): text in, audio bytes out.

    Deliberately does NOT play audio, write files, or touch any UI —
    that is an application-layer concern (see the recovered
    Virtual-assistant-1st-attempt Speaker/Listener classes for why:
    they mixed playback and UI updates into the adapter itself, which
    is exactly the coupling this interface avoids). Returning raw
    bytes keeps the adapter a pure function, testable without a
    speaker, a UI, or a filesystem.

    Example (minimal implementation):
        class MyTTSAdapter(TTSBase):
            @property
            def audio_format(self):
                return "mp3"

            def synthesize(self, text, **kwargs):
                return my_api.speak(text)
    """

    @abstractmethod
    def synthesize(self, text: str, **kwargs: Any) -> bytes:
        """
        Convert text to speech audio.

        Args:
            text: The text to synthesize.
            **kwargs: Provider-specific parameters (voice, language,
                stability, etc.)

        Returns:
            Raw audio bytes, encoded as `audio_format`.
        """
        pass

    @property
    @abstractmethod
    def audio_format(self) -> str:
        """Return the audio encoding this adapter produces (e.g. 'mp3', 'wav')."""
        pass


class STTBase(ABC):
    """
    Abstract base class for all speech-to-text adapters in SETT.

    Implement one method:
    - transcribe(): audio bytes in, text out.

    Deliberately does not own a microphone, a listening loop, or any
    concurrency guard (the recovered Listener class's asyncio.Lock
    against overlapping listens is real and worth keeping — but it is
    orchestration, not transcription, so it belongs in the
    application/Expert layer that calls this adapter, not inside it).

    Example (minimal implementation):
        class MySTTAdapter(STTBase):
            def transcribe(self, audio, **kwargs):
                return my_api.transcribe(audio)
    """

    @abstractmethod
    def transcribe(self, audio: bytes, **kwargs: Any) -> str:
        """
        Convert speech audio to text.

        Args:
            audio: Raw audio bytes (encoding expected by the specific
                adapter — check its docstring, e.g. LINEAR16 WAV for
                GoogleSTTAdapter).
            **kwargs: Provider-specific parameters (language_code, etc.)

        Returns:
            The transcribed text. Empty string if nothing was
            recognized — adapters raise SETTServiceAdapterError only
            for actual failures (network, auth, malformed audio), not
            for silence or unrecognized speech.
        """
        pass
