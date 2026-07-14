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
    Includes the harm score and the principle that was violated.
    """
    pass


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
