"""Regression tests for SETT v0.8.0 hardening guarantees."""
from __future__ import annotations

import pytest

from sett import (
    Action,
    ContextAnalyzer,
    EthicalFilter,
    SETTAgent,
    SETTConfigurationError,
    SETTExecutor,
    SETTOrchestrator,
    UniversalMemory,
)


class PublishingAgent(SETTAgent):
    def __init__(self):
        super().__init__(name="PublishingAgent", domain="publishing")

    def process(self, input_data):
        result = {"nested": {"value": input_data.get("value", 1)}}
        self._publish_to_universal(result)
        return result


def test_universal_memory_copies_input_and_reads():
    mem = UniversalMemory()
    source = {"nested": {"value": 1}}
    mem.update("agent", source)
    source["nested"]["value"] = 2
    assert mem.read("agent")["nested"]["value"] == 1

    read = mem.read("agent")
    read["nested"]["value"] = 3
    assert mem.read("agent")["nested"]["value"] == 1

    snapshot = mem.read_all()
    snapshot["agent"]["nested"]["value"] = 4
    assert mem.read("agent")["nested"]["value"] == 1


def test_public_logs_are_defensive_and_chains_verify():
    ethical_filter = EthicalFilter()
    orchestrator = SETTOrchestrator(ethical_filter=ethical_filter)
    executor = SETTExecutor()
    executor.register_handler("noop", lambda payload: {"ok": True})
    orchestrator.register_executor(executor)
    executor.submit(Action("noop"))

    external = ethical_filter.get_audit_log()
    external[0]["verdict"] = "tampered"
    assert ethical_filter.get_audit_log()[0]["verdict"] != "tampered"
    assert ethical_filter.verify_audit_log() is True

    external_exec = executor.get_audit_log()
    external_exec[0]["executed"] = False
    assert executor.get_audit_log()[0]["executed"] is True
    assert executor.verify_audit_log() is True


def test_history_is_defensive_and_chain_verifies():
    mem = UniversalMemory()
    mem.update("a", {"x": 1})
    history = mem.get_history()
    history[0]["action"] = "tampered"
    assert mem.get_history()[0]["action"] == "update"
    assert mem.verify_history() is True


def test_evaluate_action_without_filter_fails_closed():
    mem = UniversalMemory()
    with pytest.raises(SETTConfigurationError):
        mem.evaluate_action("send_message", {})


def test_unregistered_agent_cannot_propose_or_publish():
    agent = PublishingAgent()
    with pytest.raises(SETTConfigurationError):
        agent.process({})
    with pytest.raises(SETTConfigurationError):
        agent.propose_action("send_message", {})


def test_memory_write_analyzes_explicit_proposed_action():
    analyzer = ContextAnalyzer()
    analysis = analyzer.analyze(
        "memory_write",
        {"proposed_action": "publish_private_medical_data"},
        emotional_state="neutral",
    )
    assert analysis.risk_score >= 4.0
    assert analysis.safety_assessment.action_harm_risk == analysis.risk_score


def test_human_at_risk_without_protective_classification_promotes_allow_to_warn():
    """Urgency is review-worthy without being added to action harm."""
    ethical_filter = EthicalFilter()

    verdict = ethical_filter.evaluate(
        "memory_write",
        {"health": {"heart_rate_bpm": 180}},
        emotional_state="neutral",
    )
    entry = ethical_filter.get_audit_log()[-1]

    assert verdict.value == "warn"
    assert entry["human_at_risk"] is True
    assert entry["protective_action"] is False
    assert entry["harm_score"] == 0.0
    assert entry["decision_reason_codes"] == [
        "human_at_risk_without_protective_classification"
    ]


def test_human_at_risk_protective_action_remains_allow():
    """A domain analyzer may allow an urgent protective response immediately."""
    from sett import ContextAnalysis, SafetyAssessment

    class ProtectiveAnalyzer(ContextAnalyzer):
        def analyze(self, action, context, emotional_state="unknown",
                    risk_profile=None, environmental_context=None):
            return ContextAnalysis(
                action=action,
                risk_score=1.0,
                emotional_state=emotional_state,
                reasoning="Urgent protective response.",
                consequences=[],
                human_at_risk=True,
                risk_level=None,
                safety_assessment=SafetyAssessment(
                    situation_urgency=9.0,
                    action_harm_risk=1.0,
                    omission_risk=9.0,
                    protective_action=True,
                ),
            )

    ethical_filter = EthicalFilter()
    ethical_filter.register_analyzer("protective_call", ProtectiveAnalyzer())

    verdict = ethical_filter.evaluate("protective_call", {})
    entry = ethical_filter.get_audit_log()[-1]

    assert verdict.value == "allow"
    assert entry["human_at_risk"] is True
    assert entry["protective_action"] is True
    assert entry["decision_reason_codes"] == []


def test_human_at_risk_promotion_does_not_downgrade_existing_reject():
    """The review promotion cannot weaken a score-based rejection."""
    from sett import ContextAnalysis, SafetyAssessment, SETTEthicalFilterRejectedError

    class HarmfulAnalyzer(ContextAnalyzer):
        def analyze(self, action, context, emotional_state="unknown",
                    risk_profile=None, environmental_context=None):
            return ContextAnalysis(
                action=action,
                risk_score=9.0,
                emotional_state=emotional_state,
                reasoning="High action harm.",
                consequences=[],
                human_at_risk=True,
                risk_level=None,
                safety_assessment=SafetyAssessment(
                    situation_urgency=9.0,
                    action_harm_risk=9.0,
                    omission_risk=0.0,
                    protective_action=False,
                ),
            )

    ethical_filter = EthicalFilter(context_analyzer=HarmfulAnalyzer())

    with pytest.raises(SETTEthicalFilterRejectedError):
        ethical_filter.evaluate("harmful_action", {})

    entry = ethical_filter.get_audit_log()[-1]
    assert entry["verdict"] == "reject"
    assert entry["decision_reason_codes"] == []


def test_existing_warn_is_not_reclassified_by_human_risk_promotion():
    """The rule is specifically an ALLOW -> WARN promotion."""
    from sett import ContextAnalysis, SafetyAssessment

    class WarningAnalyzer(ContextAnalyzer):
        def analyze(self, action, context, emotional_state="unknown",
                    risk_profile=None, environmental_context=None):
            return ContextAnalysis(
                action=action,
                risk_score=5.0,
                emotional_state=emotional_state,
                reasoning="Moderate action harm.",
                consequences=[],
                human_at_risk=True,
                risk_level=None,
                safety_assessment=SafetyAssessment(
                    situation_urgency=8.0,
                    action_harm_risk=5.0,
                    omission_risk=0.0,
                    protective_action=False,
                ),
            )

    ethical_filter = EthicalFilter(context_analyzer=WarningAnalyzer())
    verdict = ethical_filter.evaluate("moderate_action", {})
    entry = ethical_filter.get_audit_log()[-1]

    assert verdict.value == "warn"
    assert entry["decision_reason_codes"] == []
