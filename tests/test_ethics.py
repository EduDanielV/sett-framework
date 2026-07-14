"""
SETT Framework — Tests: Ethics and Risk System
======================================================
Tests for the full three-layer hybrid risk evaluation:

  Layer 1 — EthicalFilter (action harm score)
  Layer 2 — RiskProfile (three-pillar user assessment)
  Layer 3 — EnvironmentalContext (RiskLevel 0–5)

Key contracts:
  - REJECT always raises SETTEthicalFilterRejectedError
  - Environmental context tightens filter thresholds automatically
  - RiskProfile composite score maps correctly to RiskLevel
  - Human at risk is detected via biometrics, profile, or environment
  - Audit log records every decision with full context
  - Privacy: RiskProfile never leaks to universal memory
"""
import pytest
from sett import (
    EthicalFilter,
    EthicalRuleset,
    EthicalRule,
    HarmCategory,
    RiskLevel,
    RiskProfile,
    EnvironmentalContext,
    SETTEthicalFilterRejectedError,
    default_ruleset,
    FilterVerdict,
)
from sett.ethics_ruler.ethic_kernel.context_analyzer import ContextAnalyzer


# ── RiskProfile tests ────────────────────────────────────────────────────────

class TestRiskProfile:

    def test_baseline_profile_has_zero_values(self):
        p = RiskProfile.baseline()
        assert p.emotional_instability == 0.0
        assert p.influence_vulnerability == 0.0
        assert p.collateral_damage_potential == 0.0

    def test_composite_score_is_weighted_combination(self):
        p = RiskProfile(
            emotional_instability=1.0,
            influence_vulnerability=0.0,
            collateral_damage_potential=0.0,
        )
        # Weight for emotional_instability is 0.45
        assert abs(p.composite_score - 0.45) < 0.001

    def test_composite_score_max_is_1(self):
        p = RiskProfile(
            emotional_instability=1.0,
            influence_vulnerability=1.0,
            collateral_damage_potential=1.0,
        )
        assert abs(p.composite_score - 1.0) < 0.001

    def test_values_out_of_range_raise_error(self):
        with pytest.raises(ValueError):
            RiskProfile(emotional_instability=1.5)
        with pytest.raises(ValueError):
            RiskProfile(influence_vulnerability=-0.1)

    def test_suggested_level_baseline_is_normal(self):
        p = RiskProfile.baseline()
        assert p.suggested_level == RiskLevel.LEVEL_0

    def test_suggested_level_high_instability_is_danger(self):
        p = RiskProfile(
            emotional_instability=0.9,
            influence_vulnerability=0.5,
            collateral_damage_potential=0.5,
        )
        # composite ≈ 0.9*0.45 + 0.5*0.25 + 0.5*0.30 = 0.405+0.125+0.15 = 0.68
        assert p.suggested_level >= RiskLevel.LEVEL_3

    def test_dominant_pillar_is_highest_value(self):
        p = RiskProfile(
            emotional_instability=0.2,
            influence_vulnerability=0.8,
            collateral_damage_potential=0.3,
        )
        assert p.dominant_pillar == "influence_vulnerability"

    def test_serialization_round_trip(self):
        p = RiskProfile(
            emotional_instability=0.4,
            influence_vulnerability=0.6,
            collateral_damage_potential=0.2,
        )
        d = p.to_dict()
        p2 = RiskProfile.from_dict(d)
        assert abs(p2.emotional_instability - 0.4) < 0.001
        assert abs(p2.influence_vulnerability - 0.6) < 0.001
        assert abs(p2.collateral_damage_potential - 0.2) < 0.001


# ── RiskLevel tests ───────────────────────────────────────────────────────────

class TestRiskLevel:

    def test_all_six_levels_exist(self):
        levels = list(RiskLevel)
        assert len(levels) == 6
        assert RiskLevel.LEVEL_0 in levels
        assert RiskLevel.LEVEL_5 in levels

    def test_level_0_is_not_elevated(self):
        assert not RiskLevel.LEVEL_0.is_elevated()

    def test_levels_1_to_5_are_elevated(self):
        for level in [RiskLevel.LEVEL_1, RiskLevel.LEVEL_2,
                      RiskLevel.LEVEL_3, RiskLevel.LEVEL_4, RiskLevel.LEVEL_5]:
            assert level.is_elevated()

    def test_only_4_and_5_are_critical(self):
        assert not RiskLevel.LEVEL_3.is_critical()
        assert RiskLevel.LEVEL_4.is_critical()
        assert RiskLevel.LEVEL_5.is_critical()

    def test_levels_are_comparable(self):
        assert RiskLevel.LEVEL_0 < RiskLevel.LEVEL_3
        assert RiskLevel.LEVEL_5 > RiskLevel.LEVEL_4
        assert RiskLevel.LEVEL_2 == RiskLevel.LEVEL_2

    def test_each_level_has_emoji(self):
        for level in RiskLevel:
            assert level.emoji  # non-empty string

    def test_each_level_has_description(self):
        for level in RiskLevel:
            assert len(level.description) > 10


# ── EnvironmentalContext tests ───────────────────────────────────────────────

class TestEnvironmentalContext:

    def test_normal_context_factory(self):
        ctx = EnvironmentalContext.normal("zone_a")
        assert ctx.risk_level == RiskLevel.LEVEL_0
        assert ctx.location_id == "zone_a"
        assert not ctx.requires_response

    def test_critical_context_auto_notify_emergency(self):
        ctx = EnvironmentalContext(
            risk_level=RiskLevel.LEVEL_4, location_id="zone"
        )
        assert ctx.auto_notify_emergency is True
        assert ctx.requires_evacuation is True

    def test_non_critical_does_not_auto_notify(self):
        ctx = EnvironmentalContext(
            risk_level=RiskLevel.LEVEL_2, location_id="zone"
        )
        assert ctx.auto_notify_emergency is False
        assert ctx.requires_evacuation is False
        assert ctx.requires_response is True

    def test_level_0_has_no_threshold_modifier(self):
        ctx = EnvironmentalContext.normal()
        assert ctx.filter_threshold_modifier == 0.0

    def test_higher_levels_have_larger_modifiers(self):
        modifiers = [
            EnvironmentalContext(
                risk_level=lvl, location_id="x"
            ).filter_threshold_modifier
            for lvl in RiskLevel
        ]
        # Modifiers should be monotonically non-decreasing
        for i in range(len(modifiers) - 1):
            assert modifiers[i] <= modifiers[i + 1]

    def test_serialization_round_trip(self):
        ctx = EnvironmentalContext(
            risk_level=RiskLevel.LEVEL_3,
            location_id="store_42",
            source_domain="health",
            message="Test alert",
        )
        d = ctx.to_dict()
        ctx2 = EnvironmentalContext.from_dict(d)
        assert ctx2.risk_level == RiskLevel.LEVEL_3
        assert ctx2.location_id == "store_42"
        assert ctx2.source_domain == "health"

    def test_does_not_contain_personal_data_in_dict(self):
        """
        The serialized form of EnvironmentalContext must never contain
        personal identifiers — only level, location, source, and message.
        """
        ctx = EnvironmentalContext(
            risk_level=RiskLevel.LEVEL_2, location_id="loc"
        )
        d = ctx.to_dict()
        # These keys must NOT be present
        forbidden_keys = [
            "user_id", "name", "heart_rate", "temperature",
            "emotional_instability", "influence_vulnerability",
        ]
        for key in forbidden_keys:
            assert key not in d, f"Personal data key '{key}' found in EnvironmentalContext dict"


# ── EthicalFilter tests ───────────────────────────────────────────────────────

class TestEthicalFilter:

    def test_safe_action_is_allowed(self):
        f = EthicalFilter()
        verdict = f.evaluate(action="read_schedule", context={})
        assert verdict == FilterVerdict.ALLOW

    def test_reject_raises_error(self):
        """A high-risk action must raise SETTEthicalFilterRejectedError."""
        strict = EthicalRuleset(
            name="strict_test",
            reject_threshold=1.0,
            warn_threshold=0.5,
        )
        f = EthicalFilter(ruleset=strict)
        with pytest.raises(SETTEthicalFilterRejectedError):
            f.evaluate(action="any_action", context={}, emotional_state="crisis")

    def test_audit_log_records_every_decision(self):
        f = EthicalFilter()
        f.evaluate("action_a", {})
        f.evaluate("action_b", {})
        log = f.get_audit_log()
        assert len(log) == 2
        assert log[0]["action"] == "action_a"
        assert log[1]["action"] == "action_b"

    def test_audit_log_contains_verdict(self):
        f = EthicalFilter()
        f.evaluate("safe_action", {})
        entry = f.get_audit_log()[0]
        assert "verdict" in entry
        assert entry["verdict"] in ("allow", "warn", "reject")

    def test_audit_log_contains_harm_score(self):
        f = EthicalFilter()
        f.evaluate("action", {})
        entry = f.get_audit_log()[0]
        assert "harm_score" in entry
        assert isinstance(entry["harm_score"], float)

    def test_environmental_context_tightens_thresholds(self):
        """
        With a high environmental risk level, the filter should reject
        actions that would be allowed under normal conditions.
        """
        # Under normal conditions, this action is allowed (score ~1.5)
        f_normal = EthicalFilter()
        verdict_normal = f_normal.evaluate(
            action="send_message",
            context={},
            emotional_state="distressed",
        )
        # Under a LEVEL_5 environment, same action with same state should be rejected
        f_strict = EthicalFilter()
        env_ctx = EnvironmentalContext(
            risk_level=RiskLevel.LEVEL_5, location_id="zone"
        )
        with pytest.raises(SETTEthicalFilterRejectedError):
            f_strict.evaluate(
                action="send_message",
                context={},
                emotional_state="distressed",
                environmental_context=env_ctx,
            )

    def test_risk_profile_increases_harm_score(self):
        """A high-risk profile should increase the final harm score."""
        f = EthicalFilter()
        # Evaluate the same action with a baseline vs high-risk profile
        f.evaluate("send_message", {}, risk_profile=RiskProfile.baseline())
        f.evaluate("send_message", {}, risk_profile=RiskProfile(
            emotional_instability=0.9,
            influence_vulnerability=0.9,
            collateral_damage_potential=0.9,
        ))
        log = f.get_audit_log()
        score_baseline = log[0]["harm_score"]
        score_high_risk = log[1]["harm_score"]
        assert score_high_risk > score_baseline

    def test_human_at_risk_escalates_score_significantly(self):
        """
        When human_at_risk is detected, score escalates close to reject threshold.
        This test verifies the escalation mechanism works — not that it always rejects.
        The actual rejection depends on the combination of all three layers.
        """
        f_baseline = EthicalFilter()
        f_biometric = EthicalFilter()

        # Baseline: safe action, no biometrics
        f_baseline.evaluate("memory_write", {})
        baseline_score = f_baseline.get_audit_log()[0]["harm_score"]

        # With dangerous biometrics: score should escalate significantly
        f_biometric.evaluate(
            "memory_write",
            context={"health": {"heart_rate_bpm": 180, "temperature_celsius": 40.5}},
        )
        biometric_score = f_biometric.get_audit_log()[0]["harm_score"]

        # The score with dangerous biometrics must be much higher
        assert biometric_score > baseline_score
        assert biometric_score >= 7.0  # escalated close to reject threshold

    def test_three_layers_combined_cause_reject(self):
        """
        The REJECT verdict requires the combined score from all three layers
        to exceed the reject threshold.

        crisis (+5.0) + max risk profile (+3.0) = 8.0 = reject threshold → REJECT

        This is intentional design: human_at_risk alone produces a severe WARN
        (score escalates to threshold - 0.01), but REJECT requires the full
        combination of factors. This prevents false positives.
        """
        from sett import RiskProfile
        f = EthicalFilter()
        with pytest.raises(SETTEthicalFilterRejectedError):
            f.evaluate(
                action="memory_write",
                context={},
                emotional_state="crisis",          # +5.0
                risk_profile=RiskProfile(          # +3.0 (all pillars at max)
                    emotional_instability=1.0,
                    influence_vulnerability=1.0,
                    collateral_damage_potential=1.0,
                ),
            )

    def test_ruleset_can_be_replaced(self):
        """The EthicalFilter should accept a custom ruleset."""
        custom = EthicalRuleset(
            name="permissive",
            reject_threshold=9.5,
            warn_threshold=8.0,
        )
        f = EthicalFilter(ruleset=custom)
        assert f.principle == custom.principle
        assert f._ruleset.name == "permissive"

    def test_principle_is_accessible(self):
        f = EthicalFilter()
        assert len(f.principle) > 10

    def test_audit_log_records_env_level(self):
        """Audit log should record the environmental risk level used."""
        f = EthicalFilter()
        ctx = EnvironmentalContext(
            risk_level=RiskLevel.LEVEL_2, location_id="zone"
        )
        f.evaluate("safe_action", {}, environmental_context=ctx)
        entry = f.get_audit_log()[0]
        assert entry["env_risk_level"] == 2

    def test_reject_error_message_contains_useful_info(self):
        """The rejection error should tell the developer what happened."""
        strict = EthicalRuleset(name="strict", reject_threshold=0.1)
        f = EthicalFilter(ruleset=strict)
        try:
            f.evaluate("blocked_action", {}, emotional_state="crisis")
        except SETTEthicalFilterRejectedError as e:
            msg = str(e)
            assert "blocked_action" in msg
            assert "Score" in msg or "score" in msg


# ── Integration: three-layer system ─────────────────────────────────────────

class TestThreeLayerIntegration:

    def test_all_three_layers_combine_correctly(self):
        """
        Verify that all three layers contribute to the final score
        by testing with each layer isolated and then combined.
        """
        analyzer = ContextAnalyzer()

        # Only action (Layer 1)
        a1 = analyzer.analyze("send", {})
        # Action + emotional state (Layer 1 + 2 partial)
        a2 = analyzer.analyze("send", {}, emotional_state="distressed")
        # Action + profile (Layer 1 + 2 full)
        a3 = analyzer.analyze("send", {}, risk_profile=RiskProfile(
            emotional_instability=0.8, influence_vulnerability=0.5,
            collateral_damage_potential=0.5,
        ))
        # All three layers
        a4 = analyzer.analyze(
            "send", {},
            emotional_state="distressed",
            risk_profile=RiskProfile(
                emotional_instability=0.8, influence_vulnerability=0.5,
                collateral_damage_potential=0.5,
            ),
            environmental_context=EnvironmentalContext(
                risk_level=RiskLevel.LEVEL_3, location_id="zone"
            ),
        )
        # Each additional layer should increase the score
        assert a2.risk_score >= a1.risk_score
        assert a3.risk_score >= a1.risk_score
        assert a4.risk_score >= a3.risk_score

    def test_almacen_scenario(self):
        """
        The 'almacén scenario': Instance A detects a critical risk,
        publishes EnvironmentalContext Level 4.
        Instance B reads it and its filter becomes more strict.
        """
        from sett.memory_ruler.universal import UniversalMemory

        # Shared memory simulating the same location
        shared_mem = UniversalMemory()

        # Instance A detects critical risk and publishes
        ctx_published = EnvironmentalContext(
            risk_level=RiskLevel.LEVEL_4,
            location_id="store_42",
            source_domain="health",
            message="Critical biometric indicators in environment.",
        )
        shared_mem.publish_environmental_context(ctx_published)

        # Instance B reads the context
        ctx_read = shared_mem.read_environmental_context("store_42")
        assert ctx_read is not None
        assert ctx_read.risk_level == RiskLevel.LEVEL_4
        assert ctx_read.auto_notify_emergency is True

        # Instance B's filter with this context rejects normally-safe actions
        f_b = EthicalFilter()
        with pytest.raises(SETTEthicalFilterRejectedError):
            f_b.evaluate(
                action="send_message",
                context={},
                emotional_state="distressed",
                environmental_context=ctx_read,
            )

    def test_privacy_contract_risk_profile_never_in_universal_memory(self):
        """
        The most important privacy test:
        A RiskProfile must NEVER appear in UniversalMemory.
        Only EnvironmentalContext (anonymized) is shared.
        """
        from sett import SETTOrchestrator, SETTAgent, SETTExpert

        class HealthExpert(SETTExpert):
            def resolve(self, context):
                profile = RiskProfile(
                    emotional_instability=0.9,
                    influence_vulnerability=0.7,
                    collateral_damage_potential=0.8,
                )
                # Store profile in PRIVATE memory only
                if self._private_memory:
                    self._private_memory.write("risk_profile", profile.to_dict())
                # Return ONLY anonymized result
                return {
                    "alert": True,
                    "suggested_env_level": profile.suggested_level.value,
                }

        class HealthAgent(SETTAgent):
            def __init__(self):
                super().__init__("HealthAgent", "health")
                self.register_expert(HealthExpert("health_expert"))

            def process(self, input_data):
                result = self.get_expert("health_expert").resolve(input_data)
                self._publish_to_universal(result)
                return result

        o = SETTOrchestrator()
        o.register_agent(HealthAgent())
        o.process({}, domain="health")

        universal = o.read_universal_memory()

        # The raw RiskProfile pillar values must NOT be in universal memory
        health_result = universal.get("health", {})
        forbidden = [
            "emotional_instability", "influence_vulnerability",
            "collateral_damage_potential", "composite_score",
        ]
        for key in forbidden:
            assert key not in health_result, (
                f"Privacy violation: '{key}' found in universal memory"
            )
