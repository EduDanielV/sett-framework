"""
SETT Framework — Ethical Filter Example
==============================
Demonstrates the EthicalFilter governance layer in four scenarios:

1. ALLOW  — a safe action proceeds normally
2. WARN   — a borderline action proceeds but is flagged and logged
3. REJECT — a harmful action is blocked and raises SETTEthicalFilterRejectedError
4. propose_action() — a side effect is gated BEFORE execution, not just after

This is the most important differentiator of SETT:
no action reaches the outside world without passing an ethical checkpoint.

v0.1.1 note: earlier versions of this example crashed with a TypeError in
Scenario 1 because AwareContextAnalyzer.analyze() had a signature that
didn't accept risk_profile/environmental_context, which the EthicalFilter
now always passes. This has been fixed. Scenario 3 also now sends
biometric data using flat keys (heart_rate_bpm at the top level, the way
examples/multi_agent.py publishes it) instead of nested under "health",
to demonstrate that the human-at-risk detector now catches both structures.

See examples/with_executor.py for the stronger, structural alternative to
propose_action() — submitting Actions to a registered SETTExecutor.

Run with:
    cd sett-framework
    PYTHONPATH=. python examples/with_ethics.py
"""
from sett import (
    SETTOrchestrator,
    SETTAgent,
    SETTExpert,
    EthicalFilter,
    EthicalRuleset,
    EthicalRule,
    HarmCategory,
    SETTEthicalFilterRejectedError,
    default_ruleset,
)
from sett.ethics_ruler.ethic_kernel.context_analyzer import ContextAnalyzer


# ── A CUSTOM CONTEXT ANALYZER THAT USES EMOTIONAL STATE ─────────────────────

class AwareContextAnalyzer(ContextAnalyzer):
    """
    Extended ContextAnalyzer that accepts a live emotional state.

    In a real AIDA deployment, the SentimentAnalyzerAgent would publish
    the user's emotional state to UniversalMemory. The EthicalFilter
    would read it from there and pass it to this analyzer.

    Here we simulate that connection directly for clarity.

    v0.1.1 fix: analyze() now accepts risk_profile and environmental_context
    and forwards them to the parent implementation. The EthicalFilter always
    passes these two keyword arguments — any ContextAnalyzer subclass must
    accept them, even if only to pass them straight through.
    """

    def __init__(self, emotional_state: str = "unknown"):
        super().__init__()
        self._emotional_state = emotional_state

    def analyze(self, action, context, emotional_state="unknown",
                risk_profile=None, environmental_context=None):
        # Use the injected emotional state if none is passed explicitly
        effective_state = emotional_state if emotional_state != "unknown" else self._emotional_state
        return super().analyze(
            action, context,
            emotional_state=effective_state,
            risk_profile=risk_profile,
            environmental_context=environmental_context,
        )


# ── A SIMPLE AGENT FOR THIS DEMO ─────────────────────────────────────────────

class ActionExpert(SETTExpert):
    """
    Expert that proposes an action based on its configuration.
    Used to simulate safe, borderline, and dangerous actions.
    """

    def __init__(self, name: str, action_type: str):
        super().__init__(name=name)
        self.action_type = action_type

    def resolve(self, context):
        if self._private_memory:
            self._private_memory.write("proposed_action", self.action_type)
        return {"proposed_action": self.action_type, **context}


class DemoAgent(SETTAgent):
    """
    Generic demo agent that proposes one action to universal memory.
    The EthicalFilter intercepts the memory_write and evaluates it.
    """

    def __init__(self, domain: str, action_type: str):
        super().__init__(name=f"DemoAgent[{domain}]", domain=domain)
        self.register_expert(ActionExpert(name="action", action_type=action_type))

    def process(self, input_data):
        result = self.get_expert("action").resolve(input_data)
        # This publish call goes through the EthicalFilter.
        # emotional_state and the location's EnvironmentalContext are
        # forwarded automatically — see SETTAgent._publish_to_universal().
        self._publish_to_universal(result)
        return result


class SideEffectAgent(SETTAgent):
    """
    Demo agent that performs a real side effect (simulated here as a
    print statement standing in for "send an SMS" / "call an API").
    Uses propose_action() to gate the side effect BEFORE it runs — this
    is what _publish_to_universal() alone does NOT do, since it only
    evaluates a result that already happened.
    """

    def __init__(self):
        super().__init__(name="SideEffectAgent", domain="side_effect")

    def process(self, input_data):
        # Gate the side effect BEFORE performing it.
        # Raises SETTEthicalFilterRejectedError if blocked — the SMS is
        # never actually "sent" in that case.
        self.propose_action("send_sms", action_context=input_data)

        # Only reached if propose_action() did not raise:
        simulated_result = {"sms_sent": True, "to": input_data.get("to")}
        self._publish_to_universal(simulated_result)
        return simulated_result


# ── SCENARIO RUNNER ──────────────────────────────────────────────────────────

def run_scenario(title, orchestrator, domain, context, emotional_state="unknown"):
    """Run one scenario and print the result."""
    print(f"\n{'─' * 55}")
    print(f"  {title}")
    print(f"{'─' * 55}")
    try:
        result = orchestrator.process(
            input_data=context, domain=domain, emotional_state=emotional_state
        )
        print(f"  ✓ Action completed: {result}")
    except SETTEthicalFilterRejectedError as e:
        print(f"  ✗ Action BLOCKED by EthicalFilter")
        print(f"    Reason: {str(e)[:160]}...")


# ── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    print("══════════════════════════════════════════════════════")
    print("  SETT EthicalFilter — Four Scenarios")
    print("══════════════════════════════════════════════════════")

    # ── Scenario 1: ALLOW ────────────────────────────────────────────────────

    print("\n[SCENARIO 1] Normal action — expected: ALLOW")

    orchestrator_1 = SETTOrchestrator(
        ethical_filter=EthicalFilter(
            context_analyzer=AwareContextAnalyzer(emotional_state="calm")
        )
    )
    orchestrator_1.register_agent(
        DemoAgent(domain="routine", action_type="read_schedule")
    )
    run_scenario(
        title="Reading the user's daily schedule (calm user)",
        orchestrator=orchestrator_1,
        domain="routine",
        context={"user": "Dan", "request": "show today's agenda"},
    )

    # ── Scenario 2: WARN ─────────────────────────────────────────────────────

    print("\n[SCENARIO 2] Borderline action — expected: WARN")

    orchestrator_2 = SETTOrchestrator(
        ethical_filter=EthicalFilter(
            context_analyzer=AwareContextAnalyzer(emotional_state="distressed")
        )
    )
    orchestrator_2.register_agent(
        DemoAgent(domain="comms", action_type="send_message")
    )
    run_scenario(
        title="Sending a message while user is distressed",
        orchestrator=orchestrator_2,
        domain="comms",
        context={"recipient": "family", "message": "I need help"},
    )

    # ── Scenario 3: REJECT via biometrics (flat keys, the realistic case) ───
    # Same shape multi_agent.py publishes: heart_rate_bpm/temperature_celsius
    # at the TOP LEVEL, not nested under a "health" key. This previously
    # never triggered human_at_risk — now it does.

    print("\n[SCENARIO 3] Dangerous biometrics (flat keys) — expected: REJECT (demo)")

    strict_ruleset = default_ruleset()
    strict_ruleset.reject_threshold = 4.0  # lowered for demo purposes
    strict_ruleset.warn_threshold = 2.0

    orchestrator_3 = SETTOrchestrator(
        ethical_filter=EthicalFilter(
            ruleset=strict_ruleset,
            context_analyzer=AwareContextAnalyzer(emotional_state="crisis"),
        )
    )
    orchestrator_3.register_agent(
        DemoAgent(domain="emergency", action_type="call_911")
    )
    run_scenario(
        title="Emergency call triggered while user is in crisis state",
        orchestrator=orchestrator_3,
        domain="emergency",
        context={
            "heart_rate_bpm": 170,
            "temperature_celsius": 40.1,
        },
    )

    # ── Scenario 4: propose_action() — gating a side effect BEFORE it runs ──
    # _publish_to_universal() only evaluates a result AFTER something
    # happened. propose_action() evaluates BEFORE the side effect executes,
    # so a rejected action never actually runs.

    print("\n[SCENARIO 4] Side effect gated before execution — expected: REJECT")

    orchestrator_4 = SETTOrchestrator(
        ethical_filter=EthicalFilter(
            ruleset=strict_ruleset,
            context_analyzer=AwareContextAnalyzer(emotional_state="crisis"),
        )
    )
    orchestrator_4.register_agent(SideEffectAgent())
    run_scenario(
        title="Attempting to send an SMS while the user is in crisis",
        orchestrator=orchestrator_4,
        domain="side_effect",
        context={"to": "+54 9 11 0000 0000", "message": "test"},
    )

    # ── Audit log across all scenarios ───────────────────────────────────────

    print(f"\n{'═' * 55}")
    print("  Ethical Audit Logs")
    print(f"{'═' * 55}")

    for label, orchestrator in [
        ("Scenario 1 (ALLOW)", orchestrator_1),
        ("Scenario 2 (WARN)", orchestrator_2),
        ("Scenario 3 (REJECT — biometrics)", orchestrator_3),
        ("Scenario 4 (REJECT — pre-execution gate)", orchestrator_4),
    ]:
        print(f"\n  {label}:")
        for entry in orchestrator.get_ethical_audit_log():
            print(
                f"    [{entry['verdict'].upper():6}] "
                f"score={entry['harm_score']:4.1f}  "
                f"emotion={entry['emotional_state']:10}  "
                f"human_at_risk={entry['human_at_risk']}"
            )

    print(f"\n{'═' * 55}")
    print("  Key takeaway:")
    print("  Results published to universal memory (Scenarios 1–3) and")
    print("  side effects gated via propose_action() (Scenario 4) both")
    print("  pass through the EthicalFilter. Nothing reaches the outside")
    print("  world, or becomes system state, without a verdict.")
    print(f"{'═' * 55}\n")
