"""
Regression tests for the public API audit performed after v0.8.0.

Covers the four code-level decisions from that audit: an orchestrator-
level delegate for audit log verification, a validation exception with
deliberate multiple inheritance, defensive copies on PrivateMemory
matching what UniversalMemory already had, and a non-blocking warning
when PhrasingExpert.resolve() is overridden against its own documented
contract. The removal of the empty sett/services_gen_ai/ module is
also covered here as a smoke test.
"""
from __future__ import annotations

import logging

import pytest

from sett import (
    Action,
    EthicalFilter,
    PhrasingExpert,
    PrivateMemory,
    RiskProfile,
    SETTError,
    SETTExecutor,
    SETTOrchestrator,
    SETTValidationError,
)
from sett.services_llm.base import LLMBase


# ── Point 2: SETTOrchestrator.verify_ethical_audit_log() ────────────────────

def test_orchestrator_verify_ethical_audit_log_delegates_to_filter():
    ethical_filter = EthicalFilter()
    orchestrator = SETTOrchestrator(ethical_filter=ethical_filter)
    executor = SETTExecutor()
    executor.register_handler("noop", lambda payload: {"ok": True})
    orchestrator.register_executor(executor)
    executor.submit(Action("noop"))

    assert orchestrator.verify_ethical_audit_log() is True
    assert (
        orchestrator.verify_ethical_audit_log()
        == ethical_filter.verify_audit_log()
    )


def test_orchestrator_verify_ethical_audit_log_reflects_tampering():
    ethical_filter = EthicalFilter()
    orchestrator = SETTOrchestrator(ethical_filter=ethical_filter)
    ethical_filter.evaluate("memory_write", {})

    # Reach past the public getter to corrupt the filter's own internal
    # log, the same way test_public_logs_are_defensive_and_chains_verify
    # (test_hardening_v080.py) tampers with it: get_audit_log() itself
    # returns a defensive copy, so this mutates the real internal state
    # directly, not a snapshot.
    ethical_filter._audit_log[0]["verdict"] = "tampered"

    assert orchestrator.verify_ethical_audit_log() is False


# ── Point 3: SETTValidationError(SETTError, ValueError) ─────────────────────

def test_risk_profile_out_of_range_raises_sett_validation_error():
    with pytest.raises(SETTValidationError):
        RiskProfile(emotional_instability=1.5)


def test_sett_validation_error_is_caught_as_sett_error():
    try:
        RiskProfile(influence_vulnerability=-0.1)
    except SETTError:
        pass
    else:
        pytest.fail("SETTValidationError was not caught by except SETTError")


def test_sett_validation_error_is_caught_as_value_error():
    try:
        RiskProfile(collateral_damage_potential=2.0)
    except ValueError:
        pass
    else:
        pytest.fail("SETTValidationError was not caught by except ValueError")


def test_other_data_carriers_are_not_touched_by_this_change():
    """
    Explicitly not extended per the audit decision: Action and
    BiometricReading still accept any payload without validation.
    Documents the decision as a passing test, not just a comment.
    """
    from sett import Action, BiometricReading

    Action(action_type="anything", payload={"whatever": "goes"})
    BiometricReading(heart_rate_bpm=-999)  # nonsensical, not validated


# ── Point 4: PrivateMemory defensive copies ──────────────────────────────────

def test_private_memory_read_returns_defensive_copy():
    mem = PrivateMemory(owner="test_agent")
    mem.write("data", {"list": [1, 2, 3]})

    value = mem.read("data")
    value["list"].append(999)
    value["injected_key"] = "should not persist"

    assert mem.read("data") == {"list": [1, 2, 3]}
    history = mem.get_history()
    assert len(history) == 1  # the mutation left no phantom entry
    assert history[0]["action"] == "write"


def test_private_memory_get_all_returns_defensive_copy():
    mem = PrivateMemory(owner="test_agent")
    mem.write("data", {"list": [1, 2, 3]})

    snapshot = mem.get_all()
    snapshot["data"]["list"].append(12345)
    snapshot["new_top_level_key"] = "injected"

    assert mem.get_all() == {"data": {"list": [1, 2, 3]}}


# ── Point 5: PhrasingExpert override warning ─────────────────────────────────

class FakeLLM(LLMBase):
    @property
    def model_name(self):
        return "fake"

    def complete(self, prompt, system="", **kwargs):
        return "irrelevant"

    def chat(self, messages, system="", **kwargs):
        return "irrelevant"


class WellBehavedExpert(PhrasingExpert):
    """Follows the contract: only implements the three template hooks."""

    def determine_facts(self, context):
        return {}

    def build_prompt(self, facts, context):
        return "prompt"

    def fallback_text(self, facts, context):
        return "fallback"


class ContractViolatingExpert(PhrasingExpert):
    """Overrides resolve() directly, bypassing the template entirely."""

    def determine_facts(self, context):
        return {"x": 1}

    def build_prompt(self, facts, context):
        return "unused"

    def fallback_text(self, facts, context):
        return "unused"

    def resolve(self, context):
        return {"invented": "never went through the contract"}


def test_well_behaved_expert_instantiates_without_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="sett.core_ruler.phrasing_expert"):
        WellBehavedExpert(name="fine")
    assert not caplog.records


def test_overriding_resolve_logs_a_warning_but_does_not_raise(caplog):
    with caplog.at_level(logging.WARNING, logger="sett.core_ruler.phrasing_expert"):
        expert = ContractViolatingExpert(name="bad")  # must not raise
    assert any("overrides PhrasingExpert.resolve()" in r.message for r in caplog.records)
    # Warned, not blocked: the override still works exactly as written.
    assert expert.resolve({}) == {"invented": "never went through the contract"}


# ── Point 7: sett/services_gen_ai/ removed ──────────────────────────────────

def test_services_gen_ai_module_no_longer_exists():
    with pytest.raises(ModuleNotFoundError):
        import sett.services_gen_ai  # noqa: F401
