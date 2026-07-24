"""
SETT Framework — services_sentiment
==============================
Sentiment/emotional-tone analysis adapters. See base.py (SentimentBase,
SentimentResult) for the interface every provider implements, and
google.py for the first concrete adapter.

This module produces a raw signal (polarity score, magnitude, optional
per-sentence breakdown) — it does not decide what any consumer
application does with it. Mapping a SentimentResult to a categorical
emotional_state string (see
sett/ethics_ruler/ethic_kernel/context_analyzer.py's
EMOTIONAL_RISK_MODIFIERS) is application logic, deliberately kept out
of the adapter, same reasoning as TTSBase/STTBase staying free of UI
and playback concerns.
"""
