"""
SETT Framework — RiskProfile
==============================
The user assessment layer of the SETT hybrid risk system.

A RiskProfile evaluates the STATE OF A SPECIFIC USER at a given moment
using three independent pillars. It is stored in the agent's PrivateMemory
and influences how the EthicalFilter weighs its decisions.

This is NOT a permanent label — it is a dynamic, moment-to-moment evaluation
that changes as the user's situation changes. A person in crisis today
may have a completely different profile tomorrow.

The three pillars (inspired by the SGR-IC concept and Beatless):

  1. emotional_instability (0.0–1.0)
     How likely the user is to act irrationally, violently, or self-destructively
     under their current stress level. NOT a moral judgment — a contextual signal.
     Example: 0.9 = user is in acute emotional crisis.

  2. influence_vulnerability (0.0–1.0)
     How susceptible the user is to external manipulation or social engineering
     in their current state. High vulnerability means their decisions may not
     fully reflect their own intentions — they may be being influenced.
     Example: 0.7 = user shows signs of distress-driven decision making.

  3. collateral_damage_potential (0.0–1.0)
     The potential impact of the user's decisions on their environment.
     Not about who they are, but about their current context:
     are they alone? Do they have critical medication pending?
     Are others depending on them right now?
     Example: 0.8 = user is primary caregiver, decisions affect others directly.

Privacy note:
    RiskProfile values are stored exclusively in PrivateMemory.
    They are NEVER published directly to UniversalMemory.
    Only the resulting RiskLevel (environmental context) is shared —
    and without any identifying information about the individual.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sett.risk_ruler.risk_level import RiskLevel


@dataclass
class RiskProfile:
    """
    Three-pillar user risk assessment.

    All values are floats in the range [0.0, 1.0]:
        0.0 = no concern in this dimension
        1.0 = maximum concern in this dimension

    The composite_score property combines the three pillars into a single
    weighted score that the EthicalFilter uses to adjust its thresholds.

    Usage:
        profile = RiskProfile(
            emotional_instability=0.8,
            influence_vulnerability=0.3,
            collateral_damage_potential=0.6,
        )
        print(profile.composite_score)   # weighted combination
        print(profile.suggested_level)   # suggested RiskLevel for environment
    """

    emotional_instability: float = 0.0
    """
    Propensity to irrational, violent, or self-destructive behavior
    under current stress. Range: 0.0 (calm and stable) to 1.0 (acute crisis).
    """

    influence_vulnerability: float = 0.0
    """
    Susceptibility to external manipulation or social engineering.
    Range: 0.0 (fully autonomous decisions) to 1.0 (highly manipulable).
    """

    collateral_damage_potential: float = 0.0
    """
    Potential impact of user's decisions on their environment.
    Range: 0.0 (decisions affect only themselves) to 1.0 (decisions affect many).
    """

    # Weights for the composite score calculation
    # Emotional instability is weighted highest because it directly
    # affects immediate safety decisions
    _weights: dict[str, float] = field(
        default_factory=lambda: {
            "emotional_instability": 0.45,
            "influence_vulnerability": 0.25,
            "collateral_damage_potential": 0.30,
        },
        repr=False,
    )

    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        repr=False,
    )

    def __post_init__(self) -> None:
        """Validate that all pillar values are within [0.0, 1.0]."""
        for attr in ("emotional_instability", "influence_vulnerability",
                     "collateral_damage_potential"):
            value = getattr(self, attr)
            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"RiskProfile.{attr} must be between 0.0 and 1.0, got {value}"
                )

    @property
    def composite_score(self) -> float:
        """
        Weighted combination of the three pillars.
        Returns a float between 0.0 and 1.0.
        """
        w = self._weights
        return (
            self.emotional_instability * w["emotional_instability"]
            + self.influence_vulnerability * w["influence_vulnerability"]
            + self.collateral_damage_potential * w["collateral_damage_potential"]
        )

    @property
    def suggested_level(self) -> RiskLevel:
        """
        Suggests an environmental RiskLevel based on the composite score.
        This is a recommendation — the orchestrator makes the final decision.

        Score → Level:
            0.00–0.15  → LEVEL_0 (Normal)
            0.16–0.30  → LEVEL_1 (Attention)
            0.31–0.50  → LEVEL_2 (Warning)
            0.51–0.70  → LEVEL_3 (Danger)
            0.71–0.85  → LEVEL_4 (Critical)
            0.86–1.00  → LEVEL_5 (Emergency)
        """
        score = self.composite_score
        if score <= 0.15:
            return RiskLevel.LEVEL_0
        elif score <= 0.30:
            return RiskLevel.LEVEL_1
        elif score <= 0.50:
            return RiskLevel.LEVEL_2
        elif score <= 0.70:
            return RiskLevel.LEVEL_3
        elif score <= 0.85:
            return RiskLevel.LEVEL_4
        else:
            return RiskLevel.LEVEL_5

    @property
    def dominant_pillar(self) -> str:
        """Returns the name of the pillar with the highest value."""
        pillars = {
            "emotional_instability": self.emotional_instability,
            "influence_vulnerability": self.influence_vulnerability,
            "collateral_damage_potential": self.collateral_damage_potential,
        }
        return max(pillars, key=lambda k: pillars[k])

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for storage in PrivateMemory."""
        return {
            "emotional_instability": self.emotional_instability,
            "influence_vulnerability": self.influence_vulnerability,
            "collateral_damage_potential": self.collateral_damage_potential,
            "composite_score": round(self.composite_score, 4),
            "suggested_level": self.suggested_level.value,
            "dominant_pillar": self.dominant_pillar,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RiskProfile":
        """Reconstruct a RiskProfile from a dict stored in PrivateMemory."""
        return cls(
            emotional_instability=data["emotional_instability"],
            influence_vulnerability=data["influence_vulnerability"],
            collateral_damage_potential=data["collateral_damage_potential"],
        )

    @classmethod
    def baseline(cls) -> "RiskProfile":
        """Returns a neutral baseline profile with all pillars at 0."""
        return cls(
            emotional_instability=0.0,
            influence_vulnerability=0.0,
            collateral_damage_potential=0.0,
        )

    def __str__(self) -> str:
        level = self.suggested_level
        return (
            f"{level.emoji} RiskProfile("
            f"composite={self.composite_score:.2f}, "
            f"level={level.label}, "
            f"dominant={self.dominant_pillar})"
        )
