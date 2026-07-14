"""
SETT Framework — Tests: Orchestrator, Agent, Expert
======================================================
Unit tests for the core_ruler layer.

Strategy (following the 70/20/10 approach):
  - Test each component in isolation first (unit)
  - Then test interactions between components (integration)
  - Test from the perspective of an external developer using the framework

Each test documents a contract. If a test breaks, a contract broke.
"""
import pytest
from sett import (
    SETTOrchestrator,
    SETTAgent,
    SETTExpert,
    EthicalFilter,
    SETTAgentNotFoundError,
    SETTExpertNotFoundError,
)


# ── Test doubles (minimal implementations for testing) ──────────────────────

class CountingExpert(SETTExpert):
    """Expert that counts how many times it has been called."""

    def __init__(self, name: str, return_value: dict = None):
        super().__init__(name=name)
        self.call_count = 0
        self._return = return_value or {"status": "ok"}

    def resolve(self, context):
        self.call_count += 1
        if self._private_memory:
            self._private_memory.write(f"{self.name}_calls", self.call_count)
        return self._return


class SimpleAgent(SETTAgent):
    """Minimal agent that delegates to one expert and publishes the result."""

    def __init__(self, domain: str = "test", expert_result: dict = None):
        super().__init__(name=f"SimpleAgent[{domain}]", domain=domain)
        self._expert = CountingExpert("main", expert_result or {"result": "done"})
        self.register_expert(self._expert)

    def process(self, input_data):
        result = self.get_expert("main").resolve(input_data)
        self._publish_to_universal(result)
        return result


class TwoExpertAgent(SETTAgent):
    """Agent with two experts to test coordination."""

    def __init__(self):
        super().__init__(name="TwoExpertAgent", domain="two_expert")
        self.register_expert(CountingExpert("first",  {"from": "first"}))
        self.register_expert(CountingExpert("second", {"from": "second"}))

    def process(self, input_data):
        r1 = self.get_expert("first").resolve(input_data)
        r2 = self.get_expert("second").resolve(input_data)
        result = {**r1, **r2}
        self._publish_to_universal(result)
        return result


# ── SETTExpert tests ─────────────────────────────────────────────────────────

class TestSETTExpert:

    def test_expert_has_name(self):
        expert = CountingExpert("my_expert")
        assert expert.name == "my_expert"

    def test_expert_resolve_returns_dict(self):
        expert = CountingExpert("e", {"x": 1})
        result = expert.resolve({})
        assert isinstance(result, dict)
        assert result["x"] == 1

    def test_expert_call_count_increments(self):
        expert = CountingExpert("e")
        expert.resolve({})
        expert.resolve({})
        assert expert.call_count == 2

    def test_expert_without_memory_does_not_crash(self):
        """Expert should work even if not attached to an agent's memory."""
        expert = CountingExpert("e")
        assert expert._private_memory is None
        result = expert.resolve({"input": "test"})
        assert result is not None

    def test_expert_writes_to_private_memory_when_attached(self):
        """After being registered with an agent, expert can write to private memory."""
        agent = SimpleAgent()
        expert = agent._expert
        assert expert._private_memory is not None
        expert.resolve({"data": "test"})
        val = expert._private_memory.read("main_calls")
        assert val == 1

    def test_expert_repr(self):
        expert = CountingExpert("test_e")
        assert "test_e" in repr(expert)


# ── SETTAgent tests ──────────────────────────────────────────────────────────

class TestSETTAgent:

    def test_agent_has_name_and_domain(self):
        agent = SimpleAgent(domain="health")
        assert agent.domain == "health"
        assert "health" in agent.name

    def test_agent_lists_registered_experts(self):
        agent = TwoExpertAgent()
        assert "first" in agent.experts
        assert "second" in agent.experts
        assert len(agent.experts) == 2

    def test_agent_get_expert_returns_correct_expert(self):
        agent = TwoExpertAgent()
        expert = agent.get_expert("first")
        assert expert.name == "first"

    def test_agent_get_expert_raises_when_not_found(self):
        agent = SimpleAgent()
        with pytest.raises(SETTExpertNotFoundError) as exc_info:
            agent.get_expert("nonexistent")
        assert "nonexistent" in str(exc_info.value)

    def test_agent_process_returns_dict(self):
        agent = SimpleAgent()
        result = agent.process({})
        assert isinstance(result, dict)

    def test_agent_does_not_publish_without_universal_memory(self):
        """
        Agent should not crash if process() is called before
        attach_universal_memory(). PrivateMemory still works.
        """
        agent = SimpleAgent()
        assert agent._universal_memory is None
        result = agent.process({})
        assert result is not None  # should not raise

    def test_agent_private_memory_is_not_accessible_from_outside(self):
        """
        Verify that private memory is a separate instance per agent
        and cannot be read by another agent.
        """
        agent_a = SimpleAgent(domain="a")
        agent_b = SimpleAgent(domain="b")
        agent_a._expert.resolve({})  # writes "main_calls" = 1 to A's private memory
        # B's private memory should not have A's data
        assert agent_b._private_memory.read("main_calls") is None

    def test_agent_repr_contains_domain(self):
        agent = SimpleAgent(domain="mydom")
        assert "mydom" in repr(agent)


# ── SETTOrchestrator tests ───────────────────────────────────────────────────

class TestSETTOrchestrator:

    def test_orchestrator_starts_empty(self):
        o = SETTOrchestrator()
        assert o.registered_domains == []

    def test_register_agent_adds_domain(self):
        o = SETTOrchestrator()
        o.register_agent(SimpleAgent(domain="health"))
        assert "health" in o.registered_domains

    def test_register_multiple_agents(self):
        o = SETTOrchestrator()
        o.register_agent(SimpleAgent(domain="health"))
        o.register_agent(SimpleAgent(domain="schedule"))
        o.register_agent(SimpleAgent(domain="environment"))
        assert len(o.registered_domains) == 3

    def test_get_agent_returns_correct_agent(self):
        o = SETTOrchestrator()
        agent = SimpleAgent(domain="health")
        o.register_agent(agent)
        retrieved = o.get_agent("health")
        assert retrieved is agent

    def test_get_agent_raises_when_not_found(self):
        o = SETTOrchestrator()
        with pytest.raises(SETTAgentNotFoundError) as exc_info:
            o.get_agent("nonexistent")
        assert "nonexistent" in str(exc_info.value)

    def test_process_with_domain_routes_to_correct_agent(self):
        o = SETTOrchestrator()
        agent_a = SimpleAgent(domain="a", expert_result={"from": "agent_a"})
        agent_b = SimpleAgent(domain="b", expert_result={"from": "agent_b"})
        o.register_agent(agent_a)
        o.register_agent(agent_b)

        result = o.process(input_data={}, domain="a")
        assert result["from"] == "agent_a"
        assert agent_a._expert.call_count == 1
        assert agent_b._expert.call_count == 0  # B was not called

    def test_process_without_domain_broadcasts_to_all(self):
        o = SETTOrchestrator()
        agent_a = SimpleAgent(domain="a")
        agent_b = SimpleAgent(domain="b")
        o.register_agent(agent_a)
        o.register_agent(agent_b)

        results = o.process(input_data={})
        assert "a" in results
        assert "b" in results
        assert agent_a._expert.call_count == 1
        assert agent_b._expert.call_count == 1

    def test_universal_memory_contains_agent_result_after_process(self):
        o = SETTOrchestrator()
        o.register_agent(SimpleAgent(domain="health", expert_result={"hr": 80}))
        o.process(input_data={}, domain="health")
        memory = o.read_universal_memory()
        assert "health" in memory
        assert memory["health"]["hr"] == 80

    def test_universal_memory_does_not_contain_private_data(self):
        """
        The universal memory snapshot should only contain agent domains,
        not internal private memory keys or environmental context keys.
        """
        o = SETTOrchestrator()
        o.register_agent(TwoExpertAgent())
        o.process(input_data={}, domain="two_expert")
        memory = o.read_universal_memory()
        # No private memory keys should leak into universal memory
        assert "first_calls" not in memory
        assert "second_calls" not in memory

    def test_orchestrator_has_ethical_filter_by_default(self):
        o = SETTOrchestrator()
        assert o._ethical_filter is not None

    def test_ethical_audit_log_is_empty_before_any_process(self):
        o = SETTOrchestrator()
        assert o.get_ethical_audit_log() == []

    def test_ethical_audit_log_grows_with_each_process(self):
        o = SETTOrchestrator()
        o.register_agent(SimpleAgent(domain="test"))
        o.process(input_data={}, domain="test")
        o.process(input_data={}, domain="test")
        # Each process call triggers one memory_write → one audit entry
        assert len(o.get_ethical_audit_log()) == 2

    def test_repr_contains_domains(self):
        o = SETTOrchestrator()
        o.register_agent(SimpleAgent(domain="mydom"))
        assert "mydom" in repr(o)


# ── Integration: developer perspective ──────────────────────────────────────

class TestDeveloperPerspective:
    """
    Tests written from the perspective of an external developer
    using SETT to build their own system.
    Follows the 'build a real project with the framework' approach.
    """

    def test_complete_minimal_system(self):
        """
        A developer should be able to build a working system in ~10 lines.
        This is the most important integration test.
        """
        class MyExpert(SETTExpert):
            def resolve(self, context):
                return {"answer": f"processed: {context.get('input', '?')}"}

        class MyAgent(SETTAgent):
            def __init__(self):
                super().__init__(name="MyAgent", domain="mine")
                self.register_expert(MyExpert(name="processor"))

            def process(self, input_data):
                result = self.get_expert("processor").resolve(input_data)
                self._publish_to_universal(result)
                return result

        orchestrator = SETTOrchestrator()
        orchestrator.register_agent(MyAgent())
        result = orchestrator.process({"input": "hello"}, domain="mine")

        assert result["answer"] == "processed: hello"
        assert orchestrator.read_universal_memory()["mine"]["answer"] == "processed: hello"

    def test_replacing_agent_with_different_implementation(self):
        """
        A developer should be able to swap one agent implementation
        for another in the same domain without breaking anything.
        """
        class ImplV1(SETTAgent):
            def __init__(self):
                super().__init__("V1", "service")
                self.register_expert(CountingExpert("e", {"version": 1}))
            def process(self, data):
                r = self.get_expert("e").resolve(data)
                self._publish_to_universal(r)
                return r

        class ImplV2(SETTAgent):
            def __init__(self):
                super().__init__("V2", "service")
                self.register_expert(CountingExpert("e", {"version": 2}))
            def process(self, data):
                r = self.get_expert("e").resolve(data)
                self._publish_to_universal(r)
                return r

        o1 = SETTOrchestrator()
        o1.register_agent(ImplV1())
        r1 = o1.process({}, domain="service")

        o2 = SETTOrchestrator()
        o2.register_agent(ImplV2())
        r2 = o2.process({}, domain="service")

        assert r1["version"] == 1
        assert r2["version"] == 2

    def test_multiple_experts_in_one_agent_produce_combined_result(self):
        agent = TwoExpertAgent()
        o = SETTOrchestrator()
        o.register_agent(agent)
        result = o.process({}, domain="two_expert")
        assert "from" in result
        assert agent.get_expert("first").call_count == 1
        assert agent.get_expert("second").call_count == 1
