"""
SETT Framework — RiskLevel
==============================
The environmental context layer of the SETT hybrid risk system.

RiskLevel describes the state of the ENVIRONMENT where the user exists,
not the user themselves. It is shared between SETT instances that operate
in the same physical or digital space.

Inspired by the alert level systems in public safety management,
and the philosophical framework of Beatless (2018) by Satoshi Hase.

The key distinction from surveillance systems:
    RiskLevel does NOT identify individuals.
    It describes the shared context they inhabit.
    A SETT instance publishing Level 4 says:
    "The environment where I am has this risk level"
    — not "this specific person is dangerous".

Levels:
    0 — NORMAL       No detected threats. System operates at baseline.
    1 — ATTENTION    Minor anomaly. Passive monitoring increased.
    2 — WARNING      Clear but controllable threat developing.
    3 — DANGER       Situation developing. Prepare for action.
    4 — CRITICAL     Out of human control. Mandatory response.
    5 — EMERGENCY    Systemic emergency. Maximum response protocol.
"""
from __future__ import annotations
from enum import IntEnum


class RiskLevel(IntEnum):
    """
    Six-level environmental risk scale for SETT.

    Environmental context shared between SETT instances
    in the same location or logical space via UniversalMemory.

    Usage:
        # Publish from one instance
        orchestrator.publish_environmental_context(
            risk_level=RiskLevel.LEVEL_3,
            location_id="store_42",
            source="health_agent",
        )

        # Read from another instance in the same space
        ctx = orchestrator.read_environmental_context("store_42")
        if ctx and ctx.risk_level >= RiskLevel.LEVEL_3:
            # adjust behavior accordingly
    """

    LEVEL_0 = 0  # NORMAL — baseline operation
    LEVEL_1 = 1  # ATTENTION — anomaly detected, passive monitoring
    LEVEL_2 = 2  # WARNING — controlled threat, access restrictions possible
    LEVEL_3 = 3  # DANGER — active threat, prepare for response
    LEVEL_4 = 4  # CRITICAL — evacuation or immediate action required
    LEVEL_5 = 5  # EMERGENCY — systemic emergency, maximum protocol

    @property
    def label(self) -> str:
        """Human-readable label for this risk level."""
        return _LEVEL_LABELS[self]

    @property
    def description(self) -> str:
        """Full description of what this level means."""
        return _LEVEL_DESCRIPTIONS[self]

    @property
    def color(self) -> str:
        """Color code associated with this level (for UI/logging)."""
        return _LEVEL_COLORS[self]

    @property
    def emoji(self) -> str:
        """Visual indicator for this level."""
        return _LEVEL_EMOJIS[self]

    def is_elevated(self) -> bool:
        """True for any level above NORMAL (>= LEVEL_1)."""
        return self >= RiskLevel.LEVEL_1

    def is_critical(self) -> bool:
        """True for LEVEL_4 or LEVEL_5."""
        return self >= RiskLevel.LEVEL_4

    def __str__(self) -> str:
        return f"{self.emoji} Level {self.value} ({self.label})"


_LEVEL_LABELS: dict[RiskLevel, str] = {
    RiskLevel.LEVEL_0: "Normal",
    RiskLevel.LEVEL_1: "Attention",
    RiskLevel.LEVEL_2: "Warning",
    RiskLevel.LEVEL_3: "Danger",
    RiskLevel.LEVEL_4: "Critical",
    RiskLevel.LEVEL_5: "Emergency",
}

_LEVEL_DESCRIPTIONS: dict[RiskLevel, str] = {
    RiskLevel.LEVEL_0: (
        "No threats detected. All SETT instances operate under standard "
        "behavioral parameters."
    ),
    RiskLevel.LEVEL_1: (
        "Minor anomaly or data fluctuation detected. "
        "Passive monitoring increased in the affected area."
    ),
    RiskLevel.LEVEL_2: (
        "Clear but controllable threat developing. "
        "Access restrictions to certain areas may be applied."
    ),
    RiskLevel.LEVEL_3: (
        "Active threat situation. SETT instances alert users "
        "and prepare for possible evacuation or emergency response."
    ),
    RiskLevel.LEVEL_4: (
        "Situation is beyond normal control parameters. "
        "Mandatory evacuation or immediate response required. "
        "Emergency services contacted automatically."
    ),
    RiskLevel.LEVEL_5: (
        "Systemic emergency. Imminent danger or mass casualty event. "
        "All SETT instances switch to emergency protocol. "
        "Systemic survival prioritized."
    ),
}

_LEVEL_COLORS: dict[RiskLevel, str] = {
    RiskLevel.LEVEL_0: "#22c55e",   # green
    RiskLevel.LEVEL_1: "#eab308",   # yellow
    RiskLevel.LEVEL_2: "#f97316",   # orange
    RiskLevel.LEVEL_3: "#ef4444",   # red
    RiskLevel.LEVEL_4: "#7f1d1d",   # dark red
    RiskLevel.LEVEL_5: "#000000",   # black
}

_LEVEL_EMOJIS: dict[RiskLevel, str] = {
    RiskLevel.LEVEL_0: "🟢",
    RiskLevel.LEVEL_1: "🟡",
    RiskLevel.LEVEL_2: "🟠",
    RiskLevel.LEVEL_3: "🔴",
    RiskLevel.LEVEL_4: "🛑",
    RiskLevel.LEVEL_5: "☠️",
}
