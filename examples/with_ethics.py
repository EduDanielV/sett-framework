"""
SETT Framework — Ethical Filter Example
==============================
Demonstrates the EthicalFilter governance layer in three scenarios:

1. ALLOW  — a safe action proceeds normally
2. WARN   — a borderline action proceeds but is flagged and logged
3. REJECT — a harmful action is blocked and raises SETTEthicalFilterRejectedError

This is the most important differentiator of SETT:
no action reaches the orchestrator without passing an ethical checkpoint.

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
    """

    def __init__(self, emotional_state: str = "unknown"):
        super().__init__()
        self._emotional_state = emotional_state

    def analyze(self, action, context, emotional_state="unknown"):
        # Use the injected emotional state if none is passed explicitly
        effective_state = emotional_state if emotional_state != "unknown" else self._emotional_state
        return super().analyze(action, context, emotional_state=effective_state)


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
        return {"proposed_action": self.action_type, "context": context}


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
        # This publish call goes through the EthicalFilter
        self._publish_to_universal(result)
        return result


# ── SCENARIO RUNNER ──────────────────────────────────────────────────────────

def run_scenario(title: str, orchestrator: SETTOrchestrator, domain: str, context: dict):
    """Run one scenario and print the result."""
    print(f"\n{'─' * 55}")
    print(f"  {title}")
    print(f"{'─' * 55}")
    try:
        result = orchestrator.process(input_data=context, domain=domain)
        print(f"  ✓ Action completed: {result.get('proposed_action')}")
    except SETTEthicalFilterRejectedError as e:
        print(f"  ✗ Action BLOCKED by EthicalFilter")
        print(f"    Reason: {str(e)[:120]}...")


# ── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    print("══════════════════════════════════════════════════════")
    print("  SETT EthicalFilter — Three Scenarios")
    print("══════════════════════════════════════════════════════")

    # ── Scenario 1: ALLOW ────────────────────────────────────────────────────
    # A routine action with no risk indicators — proceeds normally.

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
    # A borderline action — user is in a distressed state.
    # The emotional modifier raises the score into the warn range.
    # Action proceeds but is flagged and logged.

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

    # ── Scenario 3: REJECT ───────────────────────────────────────────────────
    # A critical health emergency detected via biometrics.
    # ContextAnalyzer detects human_at_risk = True.
    # Score escalates to just below reject threshold, then
    # human_at_risk pushes it over → REJECT with SETTEthicalFilterRejectedError.
    #
    # Note: In a real system this would NEVER block an emergency alert —
    # the ruleset would be configured to ALLOW emergency calls even at high scores.
    # Here we demonstrate the REJECT mechanism for educational purposes.

    print("\n[SCENARIO 3] Dangerous biometrics — expected: REJECT (demo)")

    # Custom ruleset with a very low reject threshold to trigger the demo
    strict_ruleset = default_ruleset()
    strict_ruleset.reject_threshold = 4.0  # lower threshold for demo
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
            "health": {"heart_rate_bpm": 170, "temperature_celsius": 40.1},
            "action": "call_911",
        },
    )

    # ── Audit log across all scenarios ───────────────────────────────────────

    print(f"\n{'═' * 55}")
    print("  Ethical Audit Logs")
    print(f"{'═' * 55}")

    for label, orchestrator in [
        ("Scenario 1 (ALLOW)", orchestrator_1),
        ("Scenario 2 (WARN)", orchestrator_2),
        ("Scenario 3 (REJECT)", orchestrator_3),
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
    print("  Every action — safe, borderline, or dangerous —")
    print("  passes through the EthicalFilter before execution.")
    print("  Nothing reaches the orchestrator without a verdict.")
    print(f"{'═' * 55}\n")
