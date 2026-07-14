"""
SETT Framework — Basic Agent Example
==============================
The simplest possible SETT system:
one orchestrator, one agent, two experts.

Run this to verify your SETT installation works correctly.
"""
from sett import (
    SETTOrchestrator,
    SETTAgent,
    SETTExpert,
    EthicalFilter,
)


# ── Step 1: Define experts ──────────────────────────────────────────────────

class GreetingExpert(SETTExpert):
    """Generates a personalized greeting."""

    def resolve(self, context):
        name = context.get("name", "world")
        greeting = f"Hello, {name}! Welcome to SETT."

        # Update this agent's private memory
        if self._private_memory:
            self._private_memory.write("last_greeted", name)

        return {"greeting": greeting}


class InfoExpert(SETTExpert):
    """Provides a brief description of SETT."""

    def resolve(self, context):
        return {
            "info": (
                "SETT (Scalable Expert-based Task Topology) is a "
                "multi-agent framework where specialized agents coordinate "
                "through an orchestrator with an ethical governance layer."
            )
        }


# ── Step 2: Define an agent ─────────────────────────────────────────────────

class WelcomeAgent(SETTAgent):
    """
    A simple agent that greets a user and provides system information.
    Domain: "welcome"
    """

    def __init__(self):
        super().__init__(name="WelcomeAgent", domain="welcome")
        self.register_expert(GreetingExpert(name="greeting"))
        self.register_expert(InfoExpert(name="info"))

    def process(self, input_data):
        # Coordinate experts
        greeting_result = self.get_expert("greeting").resolve(input_data)
        info_result = self.get_expert("info").resolve(input_data)

        # Compose final result
        final = {**greeting_result, **info_result}

        # Publish to universal memory (passes through EthicalFilter)
        self._publish_to_universal(final)

        return final


# ── Step 3: Build the system and run ────────────────────────────────────────

if __name__ == "__main__":
    # Create the orchestrator with the default ethical filter
    orchestrator = SETTOrchestrator(ethical_filter=EthicalFilter())

    # Register the agent
    orchestrator.register_agent(WelcomeAgent())

    # Process input
    result = orchestrator.process(
        input_data={"name": "Dan"},
        domain="welcome",
    )

    print("\n── Result ──────────────────────────────")
    for key, value in result.items():
        print(f"{key}: {value}")

    print("\n── Universal Memory ────────────────────")
    memory = orchestrator.read_universal_memory()
    for domain, state in memory.items():
        print(f"{domain}: {state}")

    print("\n── Ethical Audit Log ───────────────────")
    for entry in orchestrator.get_ethical_audit_log():
        print(f"[{entry['verdict']}] {entry['action']} — score: {entry['harm_score']}")
