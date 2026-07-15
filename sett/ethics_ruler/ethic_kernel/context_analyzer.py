"""
SETT Framework — ContextAnalyzer
==============================
Evaluates the context of a proposed action using all three layers
of the SETT hybrid risk system:

  Layer 1 (Action)       — What is about to happen?
  Layer 2 (User)         — Who is this person right now? (RiskProfile)
  Layer 3 (Environment)  — What is the state of the space around them?
                           (EnvironmentalContext)

The ContextAnalyzer answers WHY we arrived at a potential action,
what the emotional and situational context is, and what the consequences
would be. It always prioritizes the protection of the human.

In AIDA, the SentimentAnalyzerAgent feeds the RiskProfile here.
Wearable sensors feed the health data.
The EnvironmentalContext is read from UniversalMemory.
"""
from __future__ import annotations
from typing import Any, TYPE_CHECKING
from datetime import datetime, timezone

if TYPE_CHECKING:
    from sett.risk_ruler.risk_profile import RiskProfile
    from sett.risk_ruler.environmental_context import EnvironmentalContext
    from sett.risk_ruler.risk_level import RiskLevel


class ContextAnalysis:
    """Result of a full three-layer context analysis."""

    def __init__(
        self,
        action: str,
        risk_score: float,
        emotional_state: str,
        reasoning: str,
        consequences: list[str],
        human_at_risk: bool = False,
        risk_level: "RiskLevel | None" = None,
    ) -> None:
        self.action = action
        self.risk_score = risk_score
        self.emotional_state = emotional_state
        self.reasoning = reasoning
        self.consequences = consequences
        self.human_at_risk = human_at_risk
        self.risk_level = risk_level       # environmental layer result
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def __repr__(self) -> str:
        return (
            f"ContextAnalysis(action={self.action!r}, "
            f"risk_score={self.risk_score:.2f}, "
            f"human_at_risk={self.human_at_risk}, "
            f"env_level={self.risk_level})"
        )


class ContextAnalyzer:
    """
    Three-layer context analyzer for the EthicalFilter.

    Subclass this and override analyze() to integrate with:
    - The SentimentAnalyzerAgent (emotional state + RiskProfile)
    - Wearable biometric data (health indicators)
    - UniversalMemory (EnvironmentalContext for the user's location)
    """

    # Emotional state → base risk modifier
    EMOTIONAL_RISK_MODIFIERS: dict[str, float] = {
        "calm": 0.0,
        "happy": 0.0,
        "neutral": 0.0,
        "sad": 1.0,
        "anxious": 1.5,
        "angry": 2.0,
        "confused": 1.5,
        "distressed": 3.0,
        "crisis": 5.0,
        "unknown": 0.5,
    }

    def analyze(
        self,
        action: str,
        context: dict[str, Any],
        emotional_state: str = "unknown",
        risk_profile: "RiskProfile | None" = None,
        environmental_context: "EnvironmentalContext | None" = None,
    ) -> ContextAnalysis:
        """
        Full three-layer analysis of a proposed action.

        Layer 1 — Action analysis: what keywords and data does this action carry?
        Layer 2 — User analysis: what does the RiskProfile say about this person now?
        Layer 3 — Environment: what is the EnvironmentalContext of the space?

        Args:
            action: Description of the action about to be executed.
            context: Data associated with this action.
            emotional_state: Detected emotional state (from Sentiment Analyzer).
            risk_profile: Three-pillar user assessment (from private memory).
            environmental_context: Shared environmental state (from universal memory).

        Returns:
            A ContextAnalysis with the combined risk assessment.
        """
        from sett.risk_ruler.risk_level import RiskLevel

        # ── Layer 1: Action base score ────────────────────────────────────────
        base_score = self._base_risk_score(action, context)

        # ── Layer 2: User emotional state modifier ───────────────────────────
        emotional_modifier = self.EMOTIONAL_RISK_MODIFIERS.get(
            emotional_state.lower(), 0.5
        )

        # ── Layer 2: RiskProfile modifier ────────────────────────────────────
        profile_modifier = 0.0
        if risk_profile is not None:
            # Composite score (0.0–1.0) scales to a modifier (0.0–3.0)
            profile_modifier = risk_profile.composite_score * 3.0

        # ── Layer 3: Environmental context modifier ──────────────────────────
        env_modifier = 0.0
        env_level = None
        if environmental_context is not None:
            env_modifier = environmental_context.filter_threshold_modifier
            env_level = environmental_context.risk_level

        # ── Combine all layers ────────────────────────────────────────────────
        combined_score = min(
            10.0,
            base_score + emotional_modifier + profile_modifier + env_modifier
        )

        # ── Detect human at risk ─────────────────────────────────────────────
        human_at_risk = self._detect_human_at_risk(
            context, combined_score, risk_profile, environmental_context
        )

        consequences = self._assess_consequences(action, context, environmental_context)
        reasoning = self._build_reasoning(
            action, base_score, emotional_modifier,
            profile_modifier, env_modifier, emotional_state,
            risk_profile, env_level,
        )

        return ContextAnalysis(
            action=action,
            risk_score=combined_score,
            emotional_state=emotional_state,
            reasoning=reasoning,
            consequences=consequences,
            human_at_risk=human_at_risk,
            risk_level=env_level,
        )

    def _base_risk_score(self, action: str, context: dict[str, Any]) -> float:
        """Layer 1: keyword-based base risk from the action itself."""
        score = 0.0
        action_lower = action.lower()

        high_risk_kw = [
            "emergency", "danger", "harm", "delete", "send_all",
            "medical", "crisis", "alert", "panic", "call_911",
        ]
        medium_risk_kw = [
            "send", "share", "publish", "contact", "notify", "execute",
        ]

        for kw in high_risk_kw:
            if kw in action_lower:
                score += 3.0
                break
        for kw in medium_risk_kw:
            if kw in action_lower:
                score += 1.0
                break

        return min(score, 10.0)

    def _detect_human_at_risk(
        self,
        context: dict[str, Any],
        risk_score: float,
        risk_profile: "RiskProfile | None",
        environmental_context: "EnvironmentalContext | None",
    ) -> bool:
        """
        Determines if a human is in immediate risk.
        Combines score threshold, biometrics, RiskProfile, and EnvironmentalContext.

        v0.1.1 fix: biometric data can arrive nested under a "health" key
        (context={"health": {"heart_rate_bpm": ...}}) OR flat at the top
        level of context (context={"heart_rate_bpm": ...}), depending on
        how the calling agent structures its published result. Previously
        only the nested form was checked, so an agent publishing flat keys
        (as the multi_agent.py example does) never triggered this check.
        Both structures are now checked.
        """
        from sett.risk_ruler.risk_level import RiskLevel

        # High combined score
        if risk_score >= 7.0:
            return True

        # Biometric indicators (only if data is actually present).
        # Prefer a nested "health" dict if present; otherwise fall back
        # to reading the same keys directly from the top-level context.
        health_data = context.get("health", {})
        if not (isinstance(health_data, dict) and health_data):
            health_data = context

        if isinstance(health_data, dict):
            heart_rate = health_data.get("heart_rate_bpm")
            temperature = health_data.get("temperature_celsius")
            if heart_rate is not None and (heart_rate > 150 or heart_rate < 40):
                return True
            if temperature is not None and (temperature > 39.5 or temperature < 35.0):
                return True

        # RiskProfile: high emotional instability alone is a signal
        if risk_profile is not None:
            if risk_profile.emotional_instability >= 0.85:
                return True

        # Environmental context: level 4+ means humans are at risk by definition
        if environmental_context is not None:
            if environmental_context.risk_level.is_critical():
                return True

        return False

    def _assess_consequences(
        self,
        action: str,
        context: dict[str, Any],
        environmental_context: "EnvironmentalContext | None" = None,
    ) -> list[str]:
        """Build a list of possible consequences for this action."""
        consequences = []
        action_lower = action.lower()

        if "send" in action_lower:
            consequences.append("Information will be transmitted to an external party.")
        if "memory_write" in action_lower:
            consequences.append("State will be persisted in universal memory.")
        if "emergency" in action_lower or "911" in action_lower:
            consequences.append("Emergency services will be contacted.")
            consequences.append("User location and health data may be shared.")

        if environmental_context and environmental_context.requires_response:
            consequences.append(
                f"Action occurs in a {environmental_context.risk_level.label} "
                f"environment — consequences may be amplified."
            )

        if not consequences:
            consequences.append("No significant external consequences identified.")

        return consequences

    def _build_reasoning(
        self,
        action: str,
        base_score: float,
        emotional_modifier: float,
        profile_modifier: float,
        env_modifier: float,
        emotional_state: str,
        risk_profile: "RiskProfile | None",
        env_level: "RiskLevel | None",
    ) -> str:
        """Build a human-readable explanation of the full analysis."""
        parts = [
            f"Action '{action}': base score {base_score:.1f}",
            f"emotional state '{emotional_state}' (+{emotional_modifier:.1f})",
        ]
        if profile_modifier > 0:
            dominant = risk_profile.dominant_pillar if risk_profile else "unknown"
            parts.append(f"risk profile (+{profile_modifier:.1f}, dominant: {dominant})")
        if env_modifier > 0 and env_level is not None:
            parts.append(f"environment {env_level.emoji} {env_level.label} (+{env_modifier:.1f})")
        parts.append("Human protection always prioritized.")
        return ". ".join(parts) + "."
