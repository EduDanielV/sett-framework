"""
SETT Framework — biometric_ruler
==============================
Structural pillar for physical/vital-sign data, mirroring how
risk_ruler holds RiskProfile/EnvironmentalContext: a data model
consumed by ethics_ruler, not a decision-maker on its own.

Extracted from ethics_ruler/ethic_kernel/context_analyzer.py's
_detect_human_at_risk(), which since v0.1.1 has had to guess whether
biometric data arrives nested under a "health" key or flat at the top
level of an action's context — logic that belonged to a data model,
not to the ethics governance layer reading a raw dict. See
BiometricReading.from_context() for the parsing this replaces, and
SETT_Convenciones_v2.md Convención #23 for why this pillar exists
before an Emotion_Ruler does: this one already caused a real,
documented bug (v0.1.1's nested/flat mismatch); sentiment analysis has
not yet been used by anything downstream.
"""
