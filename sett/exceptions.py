"""
SETT Framework — Exceptions
==============================
All custom exceptions raised by the framework.
When something goes wrong in SETT, the developer receives a specific,
descriptive error rather than a generic Python exception.
"""


class SETTError(Exception):
    """Base exception for all SETT framework errors."""
    pass


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
    ) -> None:
        super().__init__(message)
        self.action = action
        self.score = score
        self.threshold = threshold
        self.principle = principle
        self.reasoning = reasoning


class SETTEthicalFilterWarningError(SETTError):
    """
    Raised when the EthicalFilter issues a warning about an action.
    The action is allowed but flagged for review.
    """
    pass


class SETTMemoryAccessDeniedError(SETTError):
    """
    Raised when an entity tries to access memory it has no permission to.
    Example: the orchestrator trying to read an agent's PrivateMemory.
    """
    pass


class SETTAgentNotFoundError(SETTError):
    """
    Raised when the orchestrator cannot find a registered agent
    for the requested domain.
    """
    pass


class SETTExpertNotFoundError(SETTError):
    """
    Raised when an agent cannot find a registered expert by name.
    """
    pass


class SETTLLMAdapterError(SETTError):
    """
    Raised when an LLM adapter fails to respond or is misconfigured.
    """
    pass


class SETTServiceAdapterError(SETTError):
    """
    Raised when a TTS, STT, or generative AI adapter fails or is misconfigured.
    """
    pass


class SETTConfigurationError(SETTError):
    """
    Raised when the framework or any of its components is incorrectly configured
    before the system starts running.
    """
    pass
