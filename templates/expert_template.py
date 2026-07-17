"""
templates/expert_template.py
==============================
Copy this file, rename it, and fill in the three parts marked TODO.
An expert resolves ONE single task — if you find yourself wanting to
do two different things in here, you probably need two experts, not
one bigger one.

Don't register this expert anywhere yourself — that's the job of the
agent that owns it, via self.register_expert(...). See agent_template.py.
"""
from __future__ import annotations
from typing import Any

from sett import SETTExpert


# TODO: rename the class after your specific task
# (e.g. HeartRateExpert, WeatherLookupExpert, IntentClassifierExpert)
class MyExpert(SETTExpert):
    """
    TODO: one line describing WHAT specific task this expert resolves.
    Example: "Evaluates heart rate against reference ranges."
    """

    def resolve(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        All of this expert's logic lives here. Always called by its
        owning agent — never directly from outside.

        Args:
            context: the data the agent passed in (input_data, or
                     another dict the agent itself built).

        Returns:
            A dict with this expert's result. The agent will combine
            it with other experts' results, if it has more than one.
        """

        # 1. TODO — read whatever you need from `context`
        # value = context.get("my_expected_key")

        # 2. TODO — do this expert's specific calculation/logic
        # result = my_logic(value)

        # 3. (optional) if another expert in this same agent will need
        #    this data later, write it to private memory. Nobody
        #    outside this agent can read it — not the orchestrator,
        #    not other agents.
        # if self._private_memory:
        #     self._private_memory.write("my_key", result)

        # 4. TODO — return the result as a dict
        return {}
