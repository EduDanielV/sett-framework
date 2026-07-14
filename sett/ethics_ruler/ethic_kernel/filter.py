"""
SETT Framework — EthicalFilter
==============================
The governance layer of SETT. Implements the full three-layer
hybrid risk evaluation:

  Layer 1 — Action harm score (HarmCategory weights)
  Layer 2 — User state (RiskProfile three pillars)
  Layer 3 — Environmental context (RiskLevel 0–5)

Every action and every UniversalMemory write passes through here.
The filter always prioritizes human protection.
"""
from __future__ import annotations
from enum import Enum
from typing import Any, TYPE_CHECKING
from datetime import datetime, timezone
import logging

from sett.ethics_ruler.ethic_kernel.rules import EthicalRuleset, default_ruleset
from sett.ethics_ruler.ethic_kernel.context_analyzer import ContextAnalyzer, ContextAnalysis
from sett.exceptions import SETTEthicalFilterRejectedError

if TYPE_CHECKING:
    from sett.risk_ruler.risk_profile import RiskProfile
    from sett.risk_ruler.environmental_context import EnvironmentalContext

logger = logging.getLogger(__name__)


class FilterVerdict(Enum):
    ALLOW  = "allow"
    WARN   = "warn"
    REJECT = "reject"


class EthicalFilter:
    """
    Three-layer ethical governance for SETT.

    Receives action + user RiskProfile + EnvironmentalContext
    and returns ALLOW / WARN / REJECT.

    Keeps a full audit log of every decision.
    """

    def __init__(
        self,
        ruleset: EthicalRuleset | None = None,
        context_analyzer: ContextAnalyzer | None = None,
    ) -> None:
        self._ruleset = ruleset or default_ruleset()
        self._context_analyzer = context_analyzer or ContextAnalyzer()
        self._audit_log: list[dict[str, Any]] = []

    def evaluate(
        self,
        action: str,
        context: dict[str, Any],
        emotional_state: str = "unknown",
        risk_profile: "RiskProfile | None" = None,
        environmental_context: "EnvironmentalContext | None" = None,
    ) -> FilterVerdict:
        """
        Evaluate an action through the three-layer system.

        Args:
            action: What is about to happen.
            context: Data associated with the action.
            emotional_state: Detected user emotional state.
            risk_profile: Three-pillar user assessment (Layer 2).
            environmental_context: Shared environmental state (Layer 3).

        Returns:
            FilterVerdict.ALLOW or FilterVerdict.WARN

        Raises:
            SETTEthicalFilterRejectedError: If the action is blocked.
        """
        # Full three-layer analysis
        analysis = self._context_analyzer.analyze(
            action=action,
            context=context,
            emotional_state=emotional_state,
            risk_profile=risk_profile,
            environmental_context=environmental_context,
        )

        # Effective thresholds — tightened by environmental context
        env_modifier = (
            environmental_context.filter_threshold_modifier
            if environmental_context else 0.0
        )
        effective_reject = max(1.0, self._ruleset.reject_threshold - env_modifier)
        effective_warn   = max(0.5, self._ruleset.warn_threshold - env_modifier)

        # Determine verdict
        score = analysis.risk_score
        if analysis.human_at_risk:
            score = max(score, effective_reject - 0.01)

        if score >= effective_reject:
            verdict = FilterVerdict.REJECT
        elif score >= effective_warn:
            verdict = FilterVerdict.WARN
        else:
            verdict = FilterVerdict.ALLOW

        # Log the decision
        self._log(action, score, verdict, analysis,
                  effective_reject, effective_warn, env_modifier)

        # Act on verdict
        if verdict == FilterVerdict.WARN:
            logger.warning(
                "[EthicalFilter] WARN | action='%s' score=%.2f "
                "env_modifier=%.1f reason=%s",
                action, score, env_modifier, analysis.reasoning,
            )

        if verdict == FilterVerdict.REJECT:
            logger.error(
                "[EthicalFilter] REJECT | action='%s' score=%.2f | %s",
                action, score, self._ruleset.principle,
            )
            raise SETTEthicalFilterRejectedError(
                f"Action '{action}' blocked. "
                f"Score: {score:.2f} (threshold: {effective_reject:.2f}). "
                f"Principle: {self._ruleset.principle}. "
                f"Reasoning: {analysis.reasoning}"
            )

        return verdict

    def _log(
        self,
        action: str,
        score: float,
        verdict: FilterVerdict,
        analysis: ContextAnalysis,
        effective_reject: float,
        effective_warn: float,
        env_modifier: float,
    ) -> None:
        self._audit_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "harm_score": round(score, 4),
            "verdict": verdict.value,
            "emotional_state": analysis.emotional_state,
            "human_at_risk": analysis.human_at_risk,
            "env_risk_level": analysis.risk_level.value if analysis.risk_level else 0,
            "env_modifier": env_modifier,
            "effective_reject_threshold": effective_reject,
            "effective_warn_threshold": effective_warn,
            "reasoning": analysis.reasoning,
        })

    def get_audit_log(self) -> list[dict[str, Any]]:
        """Full audit log of all ethical decisions."""
        return list(self._audit_log)

    def set_ruleset(self, ruleset: EthicalRuleset) -> None:
        self._ruleset = ruleset
        logger.info("[EthicalFilter] Ruleset updated to: %s", ruleset.name)

    def set_context_analyzer(self, analyzer: ContextAnalyzer) -> None:
        self._context_analyzer = analyzer

    @property
    def principle(self) -> str:
        return self._ruleset.principle

    def __repr__(self) -> str:
        return (
            f"EthicalFilter(ruleset={self._ruleset.name!r}, "
            f"decisions={len(self._audit_log)})"
        )
