"""
templates/agent_template.py
==============================
Copy this file, rename it, and fill in the parts marked TODO.

An agent:
1. Registers once with the orchestrator: orchestrator.register_agent(MyAgent())
2. Coordinates one or more experts (see expert_template.py)
3. Closes process() in ONE of three ways — pick whichever fits your
   case, explained below at the point where it applies.

You don't need to touch anything in the framework to add or remove an
agent. Removing one is simply not calling register_agent() with it.
"""
from __future__ import annotations
from typing import Any

from sett import SETTAgent

# TODO: import your real expert(s). This example import assumes you
# copied expert_template.py next to this file as my_expert.py.
# from .my_expert import MyExpert


# TODO: rename the class and the domain after your specialty
# (e.g. HealthAgent/"health", WeatherAgent/"weather")
class MyAgent(SETTAgent):
    """
    TODO: one line describing what domain this agent specializes in.
    Example: "Monitors vital signs and evaluates health risk."
    """

    def __init__(self) -> None:
        super().__init__(name="MyAgent", domain="my_domain")

        # TODO: register each expert this agent coordinates here.
        # You can have just one, or several — there's no fixed correct
        # number, it depends on how many distinct tasks your domain
        # needs. See CONVENTIONS.md once it exists.
        # self.register_expert(MyExpert(name="my_expert"))
        pass

    def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        # TODO: call your expert(s) and combine their results.
        # result = self.get_expert("my_expert").resolve(input_data)
        result: dict[str, Any] = {}

        # ── Pick ONE of these three ways to close process() ───────────
        #
        # (A) This agent only reports a state — it doesn't execute any
        #     real-world effect (doesn't send anything, doesn't call
        #     anyone). The most common case. The result passes through
        #     the EthicalFilter before being stored in universal memory.
        #
        # self._publish_to_universal(result)
        # return result

        # (B) This agent DOES produce a real effect (sending a message,
        #     calling an API), but you haven't configured a
        #     SETTExecutor yet, or it's something low-stakes / quick
        #     prototyping. It's evaluated against the EthicalFilter
        #     BEFORE you execute the real effect yourself, right after
        #     this call.
        #
        # self.propose_action("my_action", action_context=input_data)
        # (only reached here if it wasn't blocked — now execute the
        #  real effect yourself)
        # return result

        # (C) This agent produces a real effect and you want the full
        #     structural guarantee: this agent NEVER touches the real
        #     client (SMS, API, whatever it is) — it only describes
        #     intent. Requires a SETTExecutor with a handler registered
        #     for "my_action" (see docs/api_reference.md → SETTExecutor).
        #
        # delivery = self.submit_action("my_action", payload=result)
        # return {**result, **delivery}

        return result
