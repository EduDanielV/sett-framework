"""
SETT Framework — Tests: register_analyzer
======================================================
Tests for per-action-type ContextAnalyzer registration on EthicalFilter
(resolves the "two projects,
two ContextAnalyzers" conflict found while building two independent
prototype applications on top of the same framework).
"""
import pytest
from sett import EthicalFilter, EthicalRuleset
from sett.ethics_ruler.ethic_kernel.context_analyzer import ContextAnalyzer, ContextAnalysis


class AlwaysZeroAnalyzer(ContextAnalyzer):
    """A trivial custom analyzer: always scores 0, always allows."""
    def analyze(self, action, context, emotional_state="unknown",
                risk_profile=None, environmental_context=None):
        return ContextAnalysis(
            action=action, risk_score=0.0, emotional_state=emotional_state,
            reasoning="always zero", consequences=[], human_at_risk=False,
            risk_level=None,
        )


class AlwaysMaxAnalyzer(ContextAnalyzer):
    """A trivial custom analyzer: always scores 10, always rejects."""
    def analyze(self, action, context, emotional_state="unknown",
                risk_profile=None, environmental_context=None):
        return ContextAnalysis(
            action=action, risk_score=10.0, emotional_state=emotional_state,
            reasoning="always max", consequences=[], human_at_risk=False,
            risk_level=None,
        )


class TestRegisterAnalyzer:

    def test_unregistered_action_uses_generic_analyzer(self):
        """Baseline: no register_analyzer call, behavior identical to before it existed."""
        filt = EthicalFilter()
        verdict = filt.evaluate(action="some_action", context={})
        assert verdict.value == "allow"

    def test_registered_action_type_uses_custom_analyzer(self):
        filt = EthicalFilter()
        filt.register_analyzer("confirm_purchase", AlwaysMaxAnalyzer())

        with pytest.raises(Exception):  # SETTEthicalFilterRejectedError
            filt.evaluate(action="confirm_purchase", context={})

    def test_other_action_types_unaffected_by_registration(self):
        """Registering an analyzer for one action_type must not affect others."""
        filt = EthicalFilter()
        filt.register_analyzer("confirm_purchase", AlwaysMaxAnalyzer())

        # A different action_type should still use the generic analyzer
        verdict = filt.evaluate(action="memory_write", context={})
        assert verdict.value == "allow"

    def test_multiple_analyzers_for_different_action_types(self):
        filt = EthicalFilter()
        filt.register_analyzer("purchase", AlwaysMaxAnalyzer())
        filt.register_analyzer("routine_check", AlwaysZeroAnalyzer())

        with pytest.raises(Exception):
            filt.evaluate(action="purchase", context={})

        verdict = filt.evaluate(action="routine_check", context={})
        assert verdict.value == "allow"

    def test_unregister_analyzer_falls_back_to_generic(self):
        filt = EthicalFilter()
        filt.register_analyzer("confirm_purchase", AlwaysMaxAnalyzer())
        filt.unregister_analyzer("confirm_purchase")

        # Back to generic — a plain action string shouldn't trigger REJECT anymore
        verdict = filt.evaluate(action="confirm_purchase", context={})
        assert verdict.value == "allow"

    def test_unregister_nonexistent_action_type_does_not_raise(self):
        filt = EthicalFilter()
        filt.unregister_analyzer("never_registered")  # should not raise

    def test_generic_analyzer_can_be_passed_at_construction(self):
        """The constructor's context_analyzer remains the fallback for
        any action_type without a specific registration."""
        filt = EthicalFilter(context_analyzer=AlwaysMaxAnalyzer())
        with pytest.raises(Exception):
            filt.evaluate(action="anything", context={})

    def test_registered_analyzer_receives_full_context(self):
        """Verify the custom analyzer actually receives the real context dict."""
        received = {}

        class CapturingAnalyzer(ContextAnalyzer):
            def analyze(self, action, context, emotional_state="unknown",
                        risk_profile=None, environmental_context=None):
                received["context"] = context
                received["emotional_state"] = emotional_state
                return ContextAnalysis(
                    action=action, risk_score=0.0, emotional_state=emotional_state,
                    reasoning="", consequences=[], human_at_risk=False, risk_level=None,
                )

        filt = EthicalFilter()
        filt.register_analyzer("confirm_purchase", CapturingAnalyzer())
        filt.evaluate(
            action="confirm_purchase",
            context={"over_budget_amount": 500},
            emotional_state="calm",
        )
        assert received["context"] == {"over_budget_amount": 500}
        assert received["emotional_state"] == "calm"

    def test_audit_log_records_action_regardless_of_which_analyzer_ran(self):
        filt = EthicalFilter()
        filt.register_analyzer("confirm_purchase", AlwaysZeroAnalyzer())
        filt.evaluate(action="confirm_purchase", context={})
        log = filt.get_audit_log()
        assert log[-1]["action"] == "confirm_purchase"
        assert log[-1]["verdict"] == "allow"
