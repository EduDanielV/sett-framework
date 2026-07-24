"""
SETT Framework — Sentiment Base Adapter
==============================
Abstract interface that all sentiment/emotional-tone adapters must
implement.

Same intercambiability philosophy as LLMBase/TTSBase/STTBase: an
Expert or Agent that needs a sentiment signal depends on SentimentBase,
never on a specific provider's NLU API.

Directly motivated by sett/ethics_ruler/ethic_kernel/context_analyzer.py,
whose ContextAnalyzer.analyze() has accepted an `emotional_state: str`
parameter since v0.1.1 with the docstring "Detected emotional state
(from Sentiment Analyzer)" — the slot existed before any adapter filled
it. This module is that adapter, not new plumbing.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SentenceSentiment:
    """Sentiment for a single sentence within an analyzed text."""

    text: str
    score: float
    """Polarity: -1.0 (very negative) to 1.0 (very positive)."""


@dataclass(frozen=True)
class SentimentResult:
    """
    Result of analyzing a piece of text for sentiment.

    Deliberately a raw signal, not a decision: mapping this to a
    categorical emotional_state string (see
    ContextAnalyzer.EMOTIONAL_RISK_MODIFIERS: "calm", "anxious",
    "distressed", etc.) is application logic, not the adapter's job —
    same reasoning as TTSBase not playing audio and STTBase not owning
    a microphone loop. What counts as "distressed" for one application
    may not for another; the adapter only reports what it measured.

    sentence-level detail (`sentences`) exists specifically to let an
    application compare document-level score against per-sentence
    scores — a contradiction between the two is one concrete, testable
    signal for sarcasm ("that's just great" scored positive at
    document level but negative at the one sentence carrying the
    literal complaint). Empty tuple by default: not every provider
    call needs to request sentence-level detail.
    """

    score: float
    """Overall polarity: -1.0 (very negative) to 1.0 (very positive)."""

    magnitude: float
    """
    Overall emotional intensity, regardless of polarity. Unbounded
    (longer or more emotionally charged text produces a higher
    magnitude) — 0.0 means emotionally neutral/flat text.
    """

    sentences: tuple[SentenceSentiment, ...] = field(default_factory=tuple)


class SentimentBase(ABC):
    """
    Abstract base class for all sentiment analysis adapters in SETT.

    Implement one method:
    - analyze(): text in, SentimentResult out.

    Example (minimal implementation):
        class MySentimentAdapter(SentimentBase):
            def analyze(self, text, **kwargs):
                return SentimentResult(score=0.2, magnitude=0.4)
    """

    @abstractmethod
    def analyze(self, text: str, **kwargs: Any) -> SentimentResult:
        """
        Analyze the sentiment of the given text.

        Args:
            text: The text to analyze.
            **kwargs: Provider-specific parameters (language, etc.)

        Returns:
            A SentimentResult with document-level score/magnitude and,
            when the adapter supports it, a per-sentence breakdown.
        """
        pass
