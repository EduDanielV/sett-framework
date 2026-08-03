"""
SETT Framework: PhrasingExpert
==============================
Base class for any expert whose job includes producing text the user
will actually read or hear.

This formalizes a pattern that emerged independently twice while
building a companion-assistant prototype on top of SETT (its greeting expert, and its
weather-question acknowledgment): before either one was planned as a
reusable pattern. That repetition, unplanned, is the signal that this
belongs in the framework itself, not copy-pasted per project.

The contract:

    1. Deterministic logic produces the FACTS (a dict). This never
       involves the LLM: implement determine_facts().
    2. The LLM (optional) only PHRASES those facts: it never invents
       them, never alters them, never decides what's true. Implement
       build_prompt() to describe what the LLM should say, based only
       on the facts already computed.
    3. Without an LLM, or if the adapter fails for any reason, falls
       back to a deterministic text: implement fallback_text(). The
       LLM is an enhancement, never a requirement for this expert to
       do its job.
    4. Optionally, once the LLM HAS produced text, verify it against
       facts already known and swap it out if it contradicts them:
       implement verify_facts(). Most subclasses don't need this and
       can skip it entirely (default: no-op, the phrased text passes
       through unchanged).
    5. The result is RETURNED to the owning Agent; a PhrasingExpert
       never publishes anything itself: same as every SETTExpert.

v0.10.0 added step 4 (verify_facts()), for the same reason the whole
class exists: it emerged independently twice more in that same
downstream project (a greeting that must never contradict the real
time of day, and a reply that must never assert the wrong name for the
user), each time as a full override of resolve() just to insert one
check after the LLM already answered. That repetition - the same
signal that created this class in the first place - is why the hook is
now part of the contract instead of something every subclass has to
reinvent by breaking it.
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
    job includes talking to the user: a greeting, an acknowledgment,
    a synthesized summary, a redacted alert. Anything a human will
    read or hear.

    Subclasses implement up to four methods instead of resolve()
    directly - the first three are required, the fourth is optional:

        determine_facts(context) -> dict
            Pure deterministic logic. No LLM involved. This is the
            "what is true" step: e.g. what time of day it is, what
            habit was detected, what the budget calculation concluded.

        build_prompt(facts, context) -> str
            Describes, in natural language, what the LLM should say
            based on the facts already computed. The LLM never sees
            raw context it could misinterpret as license to invent
            new facts: only what you explicitly put in the prompt.

        fallback_text(facts, context) -> str
            The deterministic text to use when there's no LLM
            configured, or when the LLM call fails for any reason.
            This is what the user gets today, with zero LLM cost:
            the LLM only makes it sound better, never makes it work.

        verify_facts(phrased, facts, context) -> str
            Optional. Called AFTER the LLM (or fallback_text()) has
            already produced `phrased` - the LLM answered fine from
            SETT's point of view, but what it actually said might
            still be wrong (e.g. it agreed with the user's own wrong
            assumption instead of the fact it was given). Return
            `phrased` unchanged if it holds up; return
            `self.fallback_text(facts, context)` (or anything else) to
            replace it. Default: returns `phrased` unchanged - most
            subclasses don't need this at all.

    The phrased text is merged into the facts dict under the key named
    by OUTPUT_KEY (override it per subclass: e.g. "greeting",
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
        if type(self).resolve is not PhrasingExpert.resolve:
            logger.warning(
                "[%s] overrides PhrasingExpert.resolve(), which its "
                "own docstring documents as a template method that "
                "subclasses should not override (implement "
                "determine_facts(), build_prompt(), and fallback_text() "
                "instead). This is a warning, not a block: SETT "
                "enforces this contract by convention, not by runtime "
                "restriction, but bypassing it means the LLM-proposes/"
                "logic-disposes separation this class exists to "
                "guarantee no longer holds for this expert.",
                self.__class__.__name__,
            )

    def resolve(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Template method: computes facts deterministically, phrases
        them (via LLM if available, else the fallback text), verifies
        the result against facts (no-op unless overridden), and
        returns everything merged together.

        Subclasses should not override this: implement
        determine_facts(), build_prompt(), fallback_text(), and
        (optionally) verify_facts() instead.
        """
        facts = self.determine_facts(context)
        phrased = self._phrase(facts, context)
        verified = self.verify_facts(phrased, facts, context)
        return {**facts, self.OUTPUT_KEY: verified}

    @abstractmethod
    def determine_facts(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Pure deterministic logic: no LLM involved. Returns the facts
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
        its own: this is what makes the LLM optional, not required.
        """
        ...

    def verify_facts(
        self, phrased: str, facts: dict[str, Any], context: dict[str, Any]
    ) -> str:
        """
        Optional fourth hook (see class docstring), called once
        `phrased` already exists - from the LLM if it was configured
        and succeeded, from fallback_text() otherwise. Default: no
        verification, `phrased` passes through unchanged.

        Override when the LLM succeeding isn't enough of a guarantee:
        what it actually said still needs to be checked against facts
        already known (never against free-form interpretation - this
        should be closed, deterministic pattern matching, same spirit
        as everything else in this class). Return `phrased` if it's
        fine, or replace it (typically with
        `self.fallback_text(facts, context)`) if it isn't.
        """
        return phrased

    def _phrase(self, facts: dict[str, Any], context: dict[str, Any]) -> str:
        """
        Returns LLM-phrased text if an LLM is configured and it
        succeeds; otherwise falls back to fallback_text(). Never
        raises: a failure here should never stop the agent from
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
