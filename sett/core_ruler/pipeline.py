"""
SETT Framework — Native pipelines
==============================
Data structures for SETTOrchestrator.run_pipeline().

A pipeline is an ordered sequence of stages, each handled by a different
registered agent. Three properties define the mechanism:

1. **Explicit data flow.** Each stage receives its input explicitly —
   the previous stage's output (optionally transformed) — never by
   reading UniversalMemory. Memory isolation between stages is the
   reason this mechanism exists: each agent keeps its own PrivateMemory
   and never sees another stage's intermediate reasoning.

2. **Fail-closed configuration.** Every stage's domain is validated
   before the first stage runs. A misconfigured pipeline never produces
   partial side effects.

3. **Rejection handling as part of the mechanism.** When the
   EthicalFilter rejects a stage, the rejected agent never publishes
   (guaranteed by the filter raising before the write), the remaining
   stages are skipped, and the rejection outcome is handed back
   EXPLICITLY in the PipelineResult — never read from universal
   memory. Applications no longer wrap each chain in try/except by
   hand.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from sett.exceptions import SETTEthicalFilterRejectedError

# A transform receives (original_input, previous_stage_output) and
# returns the input dict for its stage. It lets an application reshape
# data between stages without any stage reading shared memory.
StageTransform = Callable[[dict[str, Any], dict[str, Any] | None], dict[str, Any]]


@dataclass(frozen=True)
class PipelineStep:
    """
    One stage of a pipeline.

    Attributes:
        domain: The domain of the registered agent that handles this stage.
        transform: Optional callable ``(original_input, prev_output) ->
            stage_input``. When None, the first stage receives the
            pipeline's original input and every later stage receives the
            previous stage's output unchanged.
    """
    domain: str
    transform: StageTransform | None = None


@dataclass(frozen=True)
class RejectionOutcome:
    """
    The structured record of an EthicalFilter rejection inside a
    pipeline. Built from the structured attributes of
    SETTEthicalFilterRejectedError — no string parsing anywhere.

    This object is handed back explicitly in the PipelineResult so the
    caller (typically whatever synthesizes the final response) receives
    it directly. It is never written to, nor read from, universal
    memory.
    """
    domain: str
    action: str | None
    score: float | None
    threshold: float | None
    principle: str | None
    reasoning: str | None
    message: str

    @classmethod
    def from_error(
        cls, domain: str, error: SETTEthicalFilterRejectedError
    ) -> "RejectionOutcome":
        return cls(
            domain=domain,
            action=error.action,
            score=error.score,
            threshold=error.threshold,
            principle=error.principle,
            reasoning=error.reasoning,
            message=str(error),
        )


@dataclass(frozen=True)
class StageOutcome:
    """
    What happened at one stage of a pipeline run.

    status is one of:
        "completed" — the agent processed and returned normally.
        "rejected"  — the EthicalFilter blocked the stage; the agent
                      published nothing. ``rejection`` is populated.
        "skipped"   — a previous stage was rejected; this stage never ran.
    """
    domain: str
    status: str
    output: dict[str, Any] | None = None
    rejection: RejectionOutcome | None = None


@dataclass(frozen=True)
class PipelineResult:
    """
    The full outcome of a pipeline run.

    Attributes:
        completed: True if every stage completed.
        steps: One StageOutcome per stage, in execution order
               (rejected and skipped stages included).
        output: The final stage's output when completed, else None.
        rejection: The RejectionOutcome of the rejecting stage when the
                   pipeline halted, else None. This is the explicit
                   hand-off: the caller receives the rejection here,
                   never via universal memory.
    """
    completed: bool
    steps: tuple[StageOutcome, ...] = field(default_factory=tuple)
    output: dict[str, Any] | None = None
    rejection: RejectionOutcome | None = None
