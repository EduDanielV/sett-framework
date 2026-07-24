"""
SETT Framework — BiometricReading
==============================
Structural data model for physical vital-sign readings, same role in
biometric_ruler that RiskProfile/EnvironmentalContext play in
risk_ruler: a typed value object that ethics_ruler consumes, not a
component that decides anything by itself.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar


@dataclass(frozen=True)
class BiometricReading:
    """
    A single point-in-time snapshot of biometric/vital-sign data.

    Usage:
        reading = BiometricReading.from_context(context)
        if reading.is_critical:
            ...

    All fields are optional — a reading with no data present is valid
    and simply never critical (`is_critical` is False when every field
    is None), matching the original behavior in
    ContextAnalyzer._detect_human_at_risk: absence of biometric data is
    not itself a risk signal.
    """

    heart_rate_bpm: float | None = None
    temperature_celsius: float | None = None

    HEART_RATE_MAX_BPM: ClassVar[float] = 150
    HEART_RATE_MIN_BPM: ClassVar[float] = 40
    TEMPERATURE_MAX_C: ClassVar[float] = 39.5
    TEMPERATURE_MIN_C: ClassVar[float] = 35.0
    """
    Thresholds unchanged from the values ContextAnalyzer._detect_human_at_risk
    used inline before this extraction (v0.1.1 through v0.6.0) — this
    refactor relocates them, it does not recalibrate them. Recalibrating
    is a separate, deliberate decision for someone with the clinical
    basis to make it.
    """

    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        repr=False,
    )

    @property
    def is_critical(self) -> bool:
        """
        True if any present vital sign is outside the safe range.
        Mirrors exactly the two checks _detect_human_at_risk performed
        inline: heart rate outside (40, 150) bpm, or temperature
        outside (35.0, 39.5) °C. A field that is None is never
        evaluated — missing data is not itself a risk signal.
        """
        if self.heart_rate_bpm is not None and (
            self.heart_rate_bpm > self.HEART_RATE_MAX_BPM
            or self.heart_rate_bpm < self.HEART_RATE_MIN_BPM
        ):
            return True
        if self.temperature_celsius is not None and (
            self.temperature_celsius > self.TEMPERATURE_MAX_C
            or self.temperature_celsius < self.TEMPERATURE_MIN_C
        ):
            return True
        return False

    @classmethod
    def from_context(cls, context: dict[str, Any]) -> "BiometricReading":
        """
        Parse a BiometricReading out of an action's context dict.

        Reproduces exactly the v0.1.1 nested/flat fallback that lived
        inline in ContextAnalyzer._detect_human_at_risk before this
        extraction: prefer a nested "health" dict if present and
        non-empty, otherwise read the same keys directly from the
        top-level context. Centralizing this parsing in one place is
        the actual fix for the class of bug v0.1.1 patched — v0.1.1
        fixed the one call site that existed then; without a single
        shared parser, a second call site added later could silently
        reintroduce the identical bug by guessing the shape differently.

        Never raises: a context with no usable health data (missing,
        wrong type, or empty) returns a BiometricReading with both
        fields None, which is never critical.
        """
        health_data = context.get("health", {})
        if not (isinstance(health_data, dict) and health_data):
            health_data = context

        if not isinstance(health_data, dict):
            return cls()

        return cls(
            heart_rate_bpm=health_data.get("heart_rate_bpm"),
            temperature_celsius=health_data.get("temperature_celsius"),
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize for logging/storage. Deliberately does NOT include
        raw vital-sign values by default in any audit-log path this
        framework writes to — ethics_ruler only ever reads
        `is_critical` (a bool) from this class, never the raw numbers,
        so a privacy leak of biometric data into UniversalMemory or the
        audit log is structurally impossible via that path, same
        guarantee RiskProfile already has for its own pillars.
        """
        return {
            "heart_rate_bpm": self.heart_rate_bpm,
            "temperature_celsius": self.temperature_celsius,
            "is_critical": self.is_critical,
            "timestamp": self.timestamp,
        }
