"""
SETT Framework — Tests: StubDomainAgent
======================================================
Tests for the generic placeholder agent used to assemble multi-domain
systems incrementally before every domain has a real implementation.
"""
from sett import SETTOrchestrator, EthicalFilter, StubDomainAgent


class TestStubDomainAgent:

    def test_registers_under_given_domain(self):
        o = SETTOrchestrator(ethical_filter=EthicalFilter())
        o.register_agent(StubDomainAgent("health"))
        assert "health" in o.registered_domains

    def test_default_name_includes_domain(self):
        stub = StubDomainAgent("shopping")
        assert "shopping" in stub.name

    def test_custom_name_overrides_default(self):
        stub = StubDomainAgent("shopping", name="MyCustomStub")
        assert stub.name == "MyCustomStub"

    def test_process_returns_honest_stub_status(self):
        o = SETTOrchestrator(ethical_filter=EthicalFilter())
        o.register_agent(StubDomainAgent("health"))
        result = o.process({"intent": "emergency"}, domain="health")
        assert result["status"] == "stub"
        assert result["domain"] == "health"

    def test_process_echoes_received_input(self):
        o = SETTOrchestrator(ethical_filter=EthicalFilter())
        o.register_agent(StubDomainAgent("shopping"))
        result = o.process({"item": "milk", "qty": 2}, domain="shopping")
        assert result["received"] == {"item": "milk", "qty": 2}

    def test_does_not_crash_with_empty_input(self):
        o = SETTOrchestrator(ethical_filter=EthicalFilter())
        o.register_agent(StubDomainAgent("news"))
        result = o.process({}, domain="news")
        assert result["status"] == "stub"
        assert result["received"] == {}

    def test_publishes_to_universal_memory(self):
        """Like any well-behaved agent, the stub result is auditable."""
        o = SETTOrchestrator(ethical_filter=EthicalFilter())
        o.register_agent(StubDomainAgent("health"))
        o.process({"intent": "emergency"}, domain="health")
        memory = o.read_universal_memory()
        assert memory["health"]["status"] == "stub"

    def test_multiple_stubs_do_not_interfere(self):
        o = SETTOrchestrator(ethical_filter=EthicalFilter())
        for domain in ("health", "shopping", "schedule"):
            o.register_agent(StubDomainAgent(domain))

        result = o.process({"x": 1}, domain="shopping")
        assert result["domain"] == "shopping"
        assert set(o.registered_domains) == {"health", "shopping", "schedule"}

    def test_stub_can_be_replaced_by_real_agent_under_same_domain(self):
        """The whole point: swapping a stub for a real agent needs no
        other change — callers only depend on the domain string."""
        from sett import SETTAgent, SETTExpert

        class RealHealthExpert(SETTExpert):
            def resolve(self, context):
                return {"vitals": "normal"}

        class RealHealthAgent(SETTAgent):
            def __init__(self):
                super().__init__(name="HealthAgent", domain="health")
                self.register_expert(RealHealthExpert(name="vitals"))

            def process(self, input_data):
                result = self.get_expert("vitals").resolve(input_data)
                self._publish_to_universal(result)
                return result

        o = SETTOrchestrator(ethical_filter=EthicalFilter())
        o.register_agent(StubDomainAgent("health"))
        stub_result = o.process({}, domain="health")
        assert stub_result["status"] == "stub"

        # Swap: register a new agent under the same domain
        o.register_agent(RealHealthAgent())
        real_result = o.process({}, domain="health")
        assert real_result == {"vitals": "normal"}

    def test_repr_shows_domain(self):
        stub = StubDomainAgent("health")
        assert "health" in repr(stub)
