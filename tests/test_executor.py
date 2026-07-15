"""
SETT Framework — Tests: Executor and Action
======================================================
Tests for the "actions as data" pattern: Action, SETTExecutor, and
SETTAgent.submit_action().

Key contracts tested:
  - An approved action executes its registered handler and returns its result
  - A rejected action NEVER reaches the handler (fails closed on rejection)
  - Missing handler raises SETTConfigurationError, without executing anything
  - No Executor registered raises SETTConfigurationError from submit_action()
  - The Executor's audit log only contains actions that actually ran
  - Order-independent registration: agents registered before OR after the
    Executor both end up correctly wired
  - RiskProfile passed to submit_action() is used for evaluation but never
    leaks into the Executor's audit log or any persisted state
"""
import pytest
from sett import (
    SETTOrchestrator,
    SETTAgent,
    SETTExpert,
    SETTExecutor,
    EthicalFilter,
    EthicalRuleset,
    RiskProfile,
    Action,
    SETTEthicalFilterRejectedError,
    SETTConfigurationError,
)


# ── Test doubles ─────────────────────────────────────────────────────────────

class SubmittingExpert(SETTExpert):
    """Expert used only to hold a private-memory write; the agent submits."""
    def resolve(self, context):
        if self._private_memory:
            self._private_memory.write("last_payload", context)
        return dict(context)


class SubmittingAgent(SETTAgent):
    """Agent that submits an action via submit_action() instead of acting directly."""

    def __init__(self, action_type="do_thing", domain="submitting"):
        super().__init__(name=f"SubmittingAgent[{domain}]", domain=domain)
        self._action_type = action_type
        self.register_expert(SubmittingExpert("e"))

    def process(self, input_data):
        payload = self.get_expert("e").resolve(input_data)
        risk_profile = input_data.pop("_risk_profile", None) if isinstance(input_data, dict) else None
        result = self.submit_action(self._action_type, payload=payload, risk_profile=risk_profile)
        self._publish_to_universal({"submitted": True})
        return result


def make_handler(calls_list):
    """Returns a handler that records each call and returns a fixed value."""
    def handler(payload):
        calls_list.append(payload)
        return {"handled": True, "payload": payload}
    return handler


# ── Action tests ──────────────────────────────────────────────────────────

class TestAction:

    def test_action_has_defaults(self):
        a = Action(action_type="send_sms")
        assert a.payload == {}
        assert a.proposed_by == "unknown"

    def test_action_stores_payload_and_proposer(self):
        a = Action(action_type="send_sms", payload={"to": "x"}, proposed_by="notifications")
        assert a.payload == {"to": "x"}
        assert a.proposed_by == "notifications"

    def test_action_repr_does_not_leak_payload(self):
        """repr() should not dump the full payload — keep logs terse and safe."""
        a = Action(action_type="send_sms", payload={"to": "+54911234567"}, proposed_by="notifications")
        r = repr(a)
        assert "send_sms" in r
        assert "notifications" in r
        assert "+54911234567" not in r


# ── SETTExecutor unit tests ──────────────────────────────────────────────────

class TestSETTExecutorUnit:

    def test_register_handler_and_submit_without_filter(self):
        """Executor with no universal memory attached should still execute (fail-open, matches update() behavior)."""
        calls = []
        executor = SETTExecutor()
        executor.register_handler("noop", make_handler(calls))
        result = executor.submit(Action(action_type="noop", payload={"x": 1}))
        assert result == {"handled": True, "payload": {"x": 1}}
        assert calls == [{"x": 1}]

    def test_missing_handler_raises_configuration_error(self):
        executor = SETTExecutor()
        with pytest.raises(SETTConfigurationError) as exc_info:
            executor.submit(Action(action_type="unregistered_type"))
        assert "unregistered_type" in str(exc_info.value)

    def test_missing_handler_does_not_execute_anything(self):
        calls = []
        executor = SETTExecutor()
        executor.register_handler("registered", make_handler(calls))
        with pytest.raises(SETTConfigurationError):
            executor.submit(Action(action_type="different_type"))
        assert calls == []  # the registered handler for a DIFFERENT type never ran

    def test_registered_action_types_property(self):
        executor = SETTExecutor()
        executor.register_handler("a", lambda p: None)
        executor.register_handler("b", lambda p: None)
        assert set(executor.registered_action_types) == {"a", "b"}

    def test_audit_log_starts_empty(self):
        executor = SETTExecutor()
        assert executor.get_audit_log() == []

    def test_audit_log_records_only_executed_actions(self):
        calls = []
        executor = SETTExecutor()
        executor.register_handler("ok_type", make_handler(calls))
        executor.submit(Action(action_type="ok_type", proposed_by="agent_a"))
        log = executor.get_audit_log()
        assert len(log) == 1
        assert log[0]["action_type"] == "ok_type"
        assert log[0]["proposed_by"] == "agent_a"

    def test_audit_log_does_not_record_failed_configuration_attempts(self):
        executor = SETTExecutor()
        with pytest.raises(SETTConfigurationError):
            executor.submit(Action(action_type="nonexistent"))
        assert executor.get_audit_log() == []

    def test_repr_shows_registered_handlers(self):
        executor = SETTExecutor()
        executor.register_handler("send_sms", lambda p: None)
        assert "send_sms" in repr(executor)


# ── Integration: SETTAgent.submit_action() + orchestrator wiring ────────────

class TestSubmitActionIntegration:

    def test_approved_action_executes_handler_and_returns_result(self):
        calls = []
        executor = SETTExecutor()
        executor.register_handler("do_thing", make_handler(calls))

        o = SETTOrchestrator(ethical_filter=EthicalFilter())
        o.register_executor(executor)
        o.register_agent(SubmittingAgent())

        result = o.process({"x": 42}, domain="submitting")
        assert result["handled"] is True
        assert calls == [{"x": 42}]

    def test_rejected_action_never_reaches_handler(self):
        calls = []
        executor = SETTExecutor()
        executor.register_handler("do_thing", make_handler(calls))

        strict = EthicalRuleset(name="strict", reject_threshold=0.5, warn_threshold=0.1)
        o = SETTOrchestrator(ethical_filter=EthicalFilter(ruleset=strict))
        o.register_executor(executor)
        o.register_agent(SubmittingAgent())

        with pytest.raises(SETTEthicalFilterRejectedError):
            o.process({"x": 1}, domain="submitting", emotional_state="crisis")

        assert calls == []  # handler never ran
        assert executor.get_audit_log() == []  # nothing recorded as executed

    def test_no_executor_registered_raises_configuration_error(self):
        """submit_action() must fail closed when no Executor exists at all."""
        o = SETTOrchestrator(ethical_filter=EthicalFilter())
        o.register_agent(SubmittingAgent())  # no register_executor() call

        with pytest.raises(SETTConfigurationError) as exc_info:
            o.process({"x": 1}, domain="submitting")
        assert "SETTExecutor" in str(exc_info.value) or "Executor" in str(exc_info.value)

    def test_executor_registered_after_agent_still_gets_wired(self):
        """Order independence: agent registered BEFORE the executor must still work."""
        calls = []
        executor = SETTExecutor()
        executor.register_handler("do_thing", make_handler(calls))

        o = SETTOrchestrator(ethical_filter=EthicalFilter())
        o.register_agent(SubmittingAgent())   # agent first
        o.register_executor(executor)         # executor second

        result = o.process({"y": 7}, domain="submitting")
        assert result["handled"] is True
        assert calls == [{"y": 7}]

    def test_executor_registered_before_agent_also_works(self):
        """Order independence: agent registered AFTER the executor must also work."""
        calls = []
        executor = SETTExecutor()
        executor.register_handler("do_thing", make_handler(calls))

        o = SETTOrchestrator(ethical_filter=EthicalFilter())
        o.register_executor(executor)          # executor first
        o.register_agent(SubmittingAgent())    # agent second

        result = o.process({"z": 9}, domain="submitting")
        assert result["handled"] is True
        assert calls == [{"z": 9}]

    def test_risk_profile_influences_evaluation_but_does_not_leak(self):
        """
        A high-risk RiskProfile passed to submit_action() should be used to
        evaluate the action (and can cause rejection), but must never
        appear in the Executor's audit log or in universal memory.
        """
        calls = []
        executor = SETTExecutor()
        executor.register_handler("do_thing", make_handler(calls))

        strict = EthicalRuleset(name="strict", reject_threshold=2.0, warn_threshold=0.5)
        o = SETTOrchestrator(ethical_filter=EthicalFilter(ruleset=strict))
        o.register_executor(executor)
        o.register_agent(SubmittingAgent())

        high_risk_profile = RiskProfile(
            emotional_instability=0.9,
            influence_vulnerability=0.9,
            collateral_damage_potential=0.9,
        )

        with pytest.raises(SETTEthicalFilterRejectedError):
            o.process(
                {"x": 1, "_risk_profile": high_risk_profile},
                domain="submitting",
            )

        assert calls == []
        # Privacy contract: no RiskProfile pillar values anywhere in the
        # executor's audit log (it's empty, since the action was rejected)
        # or in universal memory.
        assert executor.get_audit_log() == []
        memory_dump = str(o.read_universal_memory())
        assert "emotional_instability" not in memory_dump
        assert "0.9" not in memory_dump

    def test_two_different_agents_share_one_executor(self):
        """Multiple agents can submit different action types to the same Executor."""
        sms_calls, email_calls = [], []
        executor = SETTExecutor()
        executor.register_handler("send_sms", make_handler(sms_calls))
        executor.register_handler("send_email", make_handler(email_calls))

        o = SETTOrchestrator(ethical_filter=EthicalFilter())
        o.register_executor(executor)
        o.register_agent(SubmittingAgent(action_type="send_sms", domain="sms_agent"))
        o.register_agent(SubmittingAgent(action_type="send_email", domain="email_agent"))

        o.process({"to": "a"}, domain="sms_agent")
        o.process({"to": "b"}, domain="email_agent")

        assert sms_calls == [{"to": "a"}]
        assert email_calls == [{"to": "b"}]
        assert len(executor.get_audit_log()) == 2
