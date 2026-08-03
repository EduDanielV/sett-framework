"""
SETT Framework: Exceptions
==============================
All custom exceptions raised by the framework.
When something goes wrong in SETT, the developer receives a specific,
descriptive error rather than a generic Python exception.
"""


class SETTError(Exception):
    """Base exception for all SETT framework errors."""


class SETTEthicalFilterRejectedError(SETTError):
    """
    Raised when the EthicalFilter blocks an action or a memory write.

    ``str(e)`` returns the same human-readable message it always has.
    In addition, the structured data behind that message is available
    as instance attributes, so downstream code never needs to parse
    the message string:

    Attributes:
        action (str | None): The action type that was blocked.
        score (float | None): The computed harm score.
        threshold (float | None): The effective reject threshold the
            score was compared against (environmental modifiers already
            applied).
        principle (str | None): The ruleset principle in effect.
        reasoning (str | None): The analyzer's reasoning for the score.
        trace_event_id (str | None): The latest causal trace event associated
            with the rejection, when tracing is active.

    All attributes default to ``None``, so code that raises this
    exception with only a message keeps working unchanged.
    """

    def __init__(
        self,
        message: str,
        *,
        action: str | None = None,
        score: float | None = None,
        threshold: float | None = None,
        principle: str | None = None,
        reasoning: str | None = None,
        trace_event_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.action = action
        self.score = score
        self.threshold = threshold
        self.principle = principle
        self.reasoning = reasoning
        self.trace_event_id = trace_event_id


class SETTEthicalFilterWarningError(SETTError):
    """
    Raised when the EthicalFilter issues a warning about an action.
    The action is allowed but flagged for review.
    """


class SETTMemoryAccessDeniedError(SETTError):
    """
    Raised when an entity tries to access memory it has no permission to.
    Example: the orchestrator trying to read an agent's PrivateMemory.
    """


class SETTAgentNotFoundError(SETTError):
    """
    Raised when the orchestrator cannot find a registered agent
    for the requested domain.
    """


class SETTExpertNotFoundError(SETTError):
    """
    Raised when an agent cannot find a registered expert by name.
    """


class SETTLLMAdapterError(SETTError):
    """
    Raised when an LLM adapter fails to respond or is misconfigured.
    """


class SETTServiceAdapterError(SETTError):
    """
    Raised when a TTS, STT, sentiment, or generative AI adapter fails
    or is misconfigured.
    """


class SETTConfigurationError(SETTError):
    """
    Raised when the framework or any of its components is incorrectly configured
    before the system starts running.
    """


class SETTValidationError(SETTError, ValueError):
    """
    Raised when a data-carrying value fails its own validation (e.g. a
    RiskProfile pillar outside its documented [0.0, 1.0] range).

    Inherits from both SETTError and ValueError on purpose, the same
    pattern the standard library's own json.JSONDecodeError uses for
    ValueError. Code written against this framework's own convention
    (`except SETTError`) and code written against the standard Python
    idiom for constructor validation (`except ValueError`) both catch
    the same exception: neither has to know about the other.
    """
