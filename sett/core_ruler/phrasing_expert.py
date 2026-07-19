"""
SETT Framework — PhrasingExpert
==============================
Base class for any expert whose job includes producing text the user
will actually read or hear.

This formalizes a pattern that emerged independently twice while
building a companion-assistant prototype on top of SETT (its greeting expert, and its
weather-question acknowledgment) — before either one was planned as a
reusable pattern. That repetition, unplanned, is the signal that this
belongs in the framework itself, not copy-pasted per project.

The contract:

    1. Deterministic logic produces the FACTS (a dict). This never
       involves the LLM — implement determine_facts().
    2. The LLM (optional) only PHRASES those facts — it never invents
       them, never alters them, never decides what's true. Implement
       build_prompt() to describe what the LLM should say, based only
       on the facts already computed.
    3. Without an LLM, or if the adapter fails for any reason, falls
       back to a deterministic text — implement fallback_text(). The
       LLM is an enhancement, never a requirement for this expert to
       do its job.
    4. The result is RETURNED to the owning Agent; a PhrasingExpert
       never publishes anything itself — same as every SETTExpert.
"""
from __future__ import annotations
from abc import abstractmethod
from typing import Any
import logging

from sett.core_ruler.expert import SETTExpert
from sett.services_llm.base import LLMBase
from sett.exceptions import SETTLLMAdapterError

logger = logging.getLogger(__name__)


class PhrasingExpert(SETTExpert):
    """
    Extend this instead of SETTExpert directly whenever your expert's
    job includes talking to the user — a greeting, an acknowledgment,
    a synthesized summary, a redacted alert. Anything a human will
    read or hear.

    Subclasses implement three methods instead of resolve() directly:

        determine_facts(context) -> dict
            Pure deterministic logic. No LLM involved. This is the
            "what is true" step — e.g. what time of day it is, what
            habit was detected, what the budget calculation concluded.

        build_prompt(facts, context) -> str
            Describes, in natural language, what the LLM should say
            based on the facts already computed. The LLM never sees
            raw context it could misinterpret as license to invent
            new facts — only what you explicitly put in the prompt.

        fallback_text(facts, context) -> str
            The deterministic text to use when there's no LLM
            configured, or when the LLM call fails for any reason.
            This is what the user gets today, with zero LLM cost —
            the LLM only makes it sound better, never makes it work.

    The phrased text is merged into the facts dict under the key named
    by OUTPUT_KEY (override it per subclass — e.g. "greeting",
    "acknowledgment", "summary").

    Example:
        class GreetingExpert(PhrasingExpert):
            OUTPUT_KEY = "greeting"

            def determine_facts(self, context):
                hour = context.get("hour", 9)
                return {"time_of_day": self._time_of_day(hour)}

            def build_prompt(self, facts, context):
                return f"Greet the user. It's {facts['time_of_day']}."

            def fallback_text(self, facts, context):
                return {"morning": "Good morning.", ...}[facts["time_of_day"]]

        expert = GreetingExpert(name="greeting", llm=OllamaAdapter())
        result = expert.resolve({"hour": 8})
        # {"time_of_day": "morning", "greeting": "<LLM-phrased or fallback text>"}
    """

    OUTPUT_KEY: str = "text"

    SYSTEM_PROMPT: str = (
        "You are a helpful, warm assistant. Respond naturally and "
        "concisely, in a single short sentence unless asked for more. "
        "Never state anything as fact that wasn't given to you."
    )

    def __init__(self, name: str, llm: "LLMBase | None" = None) -> None:
        """
        Args:
            name: Unique name within the parent agent (same as any
                  SETTExpert).
            llm: Optional LLMBase adapter (e.g. OllamaAdapter,
                 AnthropicAdapter) used to phrase the facts naturally.
                 If None, or if it fails, falls back to fallback_text().
        """
        super().__init__(name=name)
        self._llm = llm

    def resolve(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Template method: computes facts deterministically, then
        phrases them (via LLM if available, else the fallback text),
        and returns both merged together.

        Subclasses should not override this — implement
        determine_facts(), build_prompt(), and fallback_text() instead.
        """
        facts = self.determine_facts(context)
        phrased = self._phrase(facts, context)
        return {**facts, self.OUTPUT_KEY: phrased}

    @abstractmethod
    def determine_facts(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Pure deterministic logic — no LLM involved. Returns the facts
        that are true regardless of how they end up being phrased.
        """
        ...

    @abstractmethod
    def build_prompt(self, facts: dict[str, Any], context: dict[str, Any]) -> str:
        """
        Builds the prompt sent to the LLM, describing what to say
        based on the facts already computed. Never include raw,
        unprocessed context the LLM could misread as license to
        invent additional facts.
        """
        ...

    @abstractmethod
    def fallback_text(self, facts: dict[str, Any], context: dict[str, Any]) -> str:
        """
        The deterministic text used when there's no LLM configured, or
        when the LLM call fails. Must always produce a valid result on
        its own — this is what makes the LLM optional, not required.
        """
        ...

    def _phrase(self, facts: dict[str, Any], context: dict[str, Any]) -> str:
        """
        Returns LLM-phrased text if an LLM is configured and it
        succeeds; otherwise falls back to fallback_text(). Never
        raises — a failure here should never stop the agent from
        responding to the user.
        """
        if self._llm is None:
            return self.fallback_text(facts, context)

        try:
            prompt = self.build_prompt(facts, context)
            phrased = self._llm.complete(prompt=prompt, system=self.SYSTEM_PROMPT)
            phrased = phrased.strip()
            return phrased if phrased else self.fallback_text(facts, context)
        except SETTLLMAdapterError as e:
            logger.warning(
                "[%s] LLM phrasing failed, using fallback_text() instead. "
                "Reason: %s", self.__class__.__name__, e,
            )
            return self.fallback_text(facts, context)
