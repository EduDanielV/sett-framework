"""
SETT Framework: Tests: PhrasingExpert
======================================================
Tests for the base class that formalizes the "LLM only phrases,
never invents" pattern found independently twice in an early prototype.
"""
import pytest
from sett import PhrasingExpert
from sett.services_llm.base import LLMBase
from sett.exceptions import SETTLLMAdapterError


class GreetingLikeExpert(PhrasingExpert):
    """Minimal concrete subclass used across these tests."""

    OUTPUT_KEY = "greeting"

    def determine_facts(self, context):
        hour = context.get("hour", 9)
        time_of_day = "morning" if hour < 12 else "afternoon"
        return {"time_of_day": time_of_day}

    def build_prompt(self, facts, context):
        return f"Greet the user. It's {facts['time_of_day']}."

    def fallback_text(self, facts, context):
        return {"morning": "Good morning.", "afternoon": "Good afternoon."}[facts["time_of_day"]]


class FakeLLM(LLMBase):
    """Always returns a fixed, recognizable phrased response."""
    @property
    def model_name(self):
        return "fake"
    def complete(self, prompt, system="", **kwargs):
        return "Hey there! Beautiful morning, isn't it?"
    def chat(self, messages, system="", **kwargs):
        return self.complete(messages[-1]["content"] if messages else "", system)


class BrokenLLM(LLMBase):
    """Always fails, simulating Ollama not running or any adapter error."""
    @property
    def model_name(self):
        return "broken"
    def complete(self, prompt, system="", **kwargs):
        raise SETTLLMAdapterError("simulated failure")
    def chat(self, messages, system="", **kwargs):
        raise SETTLLMAdapterError("simulated failure")


class EmptyStringLLM(LLMBase):
    """Returns an empty/whitespace-only string: should also fall back."""
    @property
    def model_name(self):
        return "empty"
    def complete(self, prompt, system="", **kwargs):
        return "   "
    def chat(self, messages, system="", **kwargs):
        return "   "


# ── Abstract contract enforcement ───────────────────────────────────────

class TestPhrasingExpertContract:

    def test_cannot_instantiate_without_implementing_abstract_methods(self):
        with pytest.raises(TypeError):
            PhrasingExpert(name="incomplete")

    def test_missing_one_abstract_method_still_blocks_instantiation(self):
        class Incomplete(PhrasingExpert):
            def determine_facts(self, context):
                return {}
            def build_prompt(self, facts, context):
                return ""
            # fallback_text intentionally not implemented
        with pytest.raises(TypeError):
            Incomplete(name="incomplete")


# ── Behavior without an LLM (default, zero-cost path) ───────────────────

class TestPhrasingExpertWithoutLLM:

    def test_no_llm_uses_fallback_text(self):
        expert = GreetingLikeExpert(name="greeting")
        result = expert.resolve({"hour": 8})
        assert result["greeting"] == "Good morning."

    def test_facts_are_always_included_in_result(self):
        expert = GreetingLikeExpert(name="greeting")
        result = expert.resolve({"hour": 14})
        assert result["time_of_day"] == "afternoon"

    def test_output_key_is_configurable_per_subclass(self):
        class AckExpert(PhrasingExpert):
            OUTPUT_KEY = "acknowledgment"
            def determine_facts(self, context):
                return {"noted": True}
            def build_prompt(self, facts, context):
                return "Acknowledge."
            def fallback_text(self, facts, context):
                return "Got it."

        expert = AckExpert(name="ack")
        result = expert.resolve({})
        assert result["acknowledgment"] == "Got it."
        assert "greeting" not in result


# ── Behavior with a working LLM ─────────────────────────────────────────

class TestPhrasingExpertWithWorkingLLM:

    def test_llm_output_used_when_available(self):
        expert = GreetingLikeExpert(name="greeting", llm=FakeLLM())
        result = expert.resolve({"hour": 8})
        assert result["greeting"] == "Hey there! Beautiful morning, isn't it?"

    def test_facts_still_deterministic_with_llm_present(self):
        """The LLM phrases; it never gets to alter the facts themselves."""
        expert = GreetingLikeExpert(name="greeting", llm=FakeLLM())
        result = expert.resolve({"hour": 8})
        assert result["time_of_day"] == "morning"

    def test_empty_llm_response_falls_back(self):
        expert = GreetingLikeExpert(name="greeting", llm=EmptyStringLLM())
        result = expert.resolve({"hour": 8})
        assert result["greeting"] == "Good morning."


# ── Behavior when the LLM fails ─────────────────────────────────────────

class TestPhrasingExpertWithFailingLLM:

    def test_llm_failure_falls_back_to_deterministic_text(self):
        expert = GreetingLikeExpert(name="greeting", llm=BrokenLLM())
        result = expert.resolve({"hour": 8})
        assert result["greeting"] == "Good morning."

    def test_llm_failure_never_raises_to_caller(self):
        """A broken LLM must never prevent the expert from responding."""
        expert = GreetingLikeExpert(name="greeting", llm=BrokenLLM())
        try:
            expert.resolve({"hour": 14})
        except SETTLLMAdapterError:
            pytest.fail("PhrasingExpert must swallow LLM adapter errors, not propagate them")

    def test_facts_still_present_when_llm_fails(self):
        expert = GreetingLikeExpert(name="greeting", llm=BrokenLLM())
        result = expert.resolve({"hour": 14})
        assert result["time_of_day"] == "afternoon"


# ── Integration: PhrasingExpert inside a real SETTAgent ─────────────────

class TestPhrasingExpertWithAgent:

    def test_works_as_expert_inside_an_agent(self):
        from sett import SETTAgent

        class MyAgent(SETTAgent):
            def __init__(self, llm=None):
                super().__init__(name="MyAgent", domain="greeter_test")
                self.register_expert(GreetingLikeExpert(name="greeting", llm=llm))

            def process(self, input_data):
                result = self.get_expert("greeting").resolve(input_data)
                self._publish_to_universal(result)
                return result

        from sett import SETTOrchestrator, EthicalFilter
        o = SETTOrchestrator(ethical_filter=EthicalFilter())
        o.register_agent(MyAgent(llm=FakeLLM()))
        result = o.process({"hour": 8}, domain="greeter_test")
        assert result["greeting"] == "Hey there! Beautiful morning, isn't it?"
        assert result["time_of_day"] == "morning"

    def test_verify_facts_default_is_a_pass_through(self):
        """Sin override, verify_facts() no cambia nada - el default de
        v0.10.0 debe ser indistinguible del comportamiento pre-v0.10.0."""
        expert = GreetingLikeExpert(name="greeting", llm=FakeLLM())
        result = expert.resolve({"hour": 8})
        assert result["greeting"] == "Hey there! Beautiful morning, isn't it?"

    def test_private_memory_still_accessible_from_within(self):
        class MemoWritingExpert(PhrasingExpert):
            OUTPUT_KEY = "text"
            def determine_facts(self, context):
                if self._private_memory:
                    self._private_memory.write("last_context", context)
                return {"ok": True}
            def build_prompt(self, facts, context):
                return "Say ok."
            def fallback_text(self, facts, context):
                return "ok"

        from sett import SETTAgent, SETTOrchestrator, EthicalFilter

        class MyAgent(SETTAgent):
            def __init__(self):
                super().__init__(name="MyAgent", domain="memo_test")
                self.register_expert(MemoWritingExpert(name="memo"))

            def process(self, input_data):
                result = self.get_expert("memo").resolve(input_data)
                self._publish_to_universal(result)
                return result

        o = SETTOrchestrator(ethical_filter=EthicalFilter())
        agent = MyAgent()
        o.register_agent(agent)
        o.process({"some": "data"}, domain="memo_test")
        assert agent._private_memory.read("last_context") == {"some": "data"}


# ── verify_facts() (v0.10.0): the 4th, optional hook ─────────────────────
# Motivated by two independent subclasses in a downstream project that
# needed exactly this and ended up overriding resolve() wholesale to
# get it - see the class docstring.

class StrictGreetingExpert(PhrasingExpert):
    """Same as GreetingLikeExpert, but rejects any phrasing that
    contradicts the real time_of_day - the same shape independently
    needed by the two subclasses that motivated this hook (see the
    class docstring)."""

    OUTPUT_KEY = "greeting"

    def determine_facts(self, context):
        hour = context.get("hour", 9)
        time_of_day = "morning" if hour < 12 else "afternoon"
        return {"time_of_day": time_of_day}

    def build_prompt(self, facts, context):
        return f"Greet the user. It's {facts['time_of_day']}."

    def fallback_text(self, facts, context):
        return {"morning": "Good morning.", "afternoon": "Good afternoon."}[facts["time_of_day"]]

    def verify_facts(self, phrased, facts, context):
        wrong_word = {"morning": "afternoon", "afternoon": "morning"}[facts["time_of_day"]]
        if wrong_word in phrased.lower():
            return self.fallback_text(facts, context)
        return phrased


class ContradictingLLM(LLMBase):
    """Well-formed phrasing, but deliberately contradicts the real fact."""
    @property
    def model_name(self):
        return "contradicting"
    def complete(self, prompt, system="", **kwargs):
        return "Good afternoon, hope you slept well!"
    def chat(self, messages, system="", **kwargs):
        return self.complete(messages[-1]["content"] if messages else "", system)


class TestPhrasingExpertVerifyFacts:

    def test_override_can_discard_a_contradicting_llm_response(self):
        expert = StrictGreetingExpert(name="greeting", llm=ContradictingLLM())
        result = expert.resolve({"hour": 8})   # real morning
        assert result["greeting"] == "Good morning."   # fallback, not the LLM's

    def test_override_lets_a_correct_llm_response_through(self):
        expert = StrictGreetingExpert(name="greeting", llm=FakeLLM())   # says "morning"
        result = expert.resolve({"hour": 8})   # real morning, matches
        assert result["greeting"] == "Hey there! Beautiful morning, isn't it?"

    def test_verify_facts_also_runs_on_fallback_text_not_only_llm_output(self):
        """verify_facts() always runs after _phrase(), even with no LLM
        configured - fallback_text() is already correct by construction
        here, so it should pass through unchanged."""
        expert = StrictGreetingExpert(name="greeting")   # no LLM
        result = expert.resolve({"hour": 8})
        assert result["greeting"] == "Good morning."

    def test_overriding_verify_facts_does_not_trigger_the_resolve_override_warning(self):
        """The whole point of the hook: you don't need to touch resolve()
        to get this, so the "overrides resolve()" warning should not
        fire - unlike an older subclass that does override resolve()
        directly."""
        import logging

        class NoisyRecorder(logging.Handler):
            def __init__(self):
                super().__init__()
                self.records = []
            def emit(self, record):
                self.records.append(record.getMessage())

        handler = NoisyRecorder()
        logger = logging.getLogger("sett.core_ruler.phrasing_expert")
        logger.addHandler(handler)
        try:
            StrictGreetingExpert(name="greeting")
        finally:
            logger.removeHandler(handler)

        assert not any("overrides PhrasingExpert.resolve()" in m for m in handler.records)
