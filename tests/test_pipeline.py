"""
Tests for SETTOrchestrator.run_pipeline() — native pipelines.

The three guarantees of the mechanism, each verified independently:

1. Explicit data flow with memory isolation between stages
   (stages never feed from universal memory; private memories stay
   private per agent).
2. Fail-closed configuration (whole pipeline validated before any
   stage runs; empty pipelines and bad transforms are errors, never
   no-ops).
3. Rejection handling as part of the mechanism (rejected agent never
   publishes; remaining stages skipped; rejection handed back
   EXPLICITLY in the result with structured fields — never via
   universal memory).

Plus: process() (route/broadcast) is byte-for-byte untouched by the
existence of pipelines.
"""

import pytest

from sett import (
    EthicalFilter,
    PipelineResult,
    PipelineStep,
    RejectionOutcome,
    SETTAgent,
    SETTAgentNotFoundError,
    SETTConfigurationError,
    SETTOrchestrator,
    StageOutcome,
)
from sett.ethics_ruler.ethic_kernel.rules import EthicalRuleset


# ── Test agents ──────────────────────────────────────────────────────────────

class TraceAgent(SETTAgent):
    """
    Appends its domain to a 'trail' list in the data it receives,
    remembers privately what it saw, and publishes its result.
    """

    def __init__(self, domain: str):
        super().__init__(name=f"{domain}_agent", domain=domain)
        self.seen_inputs: list[dict] = []

    def process(self, input_data):
        self.seen_inputs.append(dict(input_data))
        self._private_memory.write(f"secret_{self.domain}", f"internal_{self.domain}")
        result = {
            "trail": input_data.get("trail", []) + [self.domain],
            "value": input_data.get("value", 0) + 1,
        }
        self._publish_to_universal({f"{self.domain}_done": True})
        return result


class SilentAgent(SETTAgent):
    """Processes without publishing anything (returns only)."""

    def __init__(self, domain: str):
        super().__init__(name=f"{domain}_agent", domain=domain)

    def process(self, input_data):
        return {"echo": input_data}


def build_orchestrator(domains, ethical_filter=None):
    orch = SETTOrchestrator(ethical_filter=ethical_filter)
    agents = {}
    for d in domains:
        a = TraceAgent(d)
        orch.register_agent(a)
        agents[d] = a
    return orch, agents


def strict_filter():
    """A filter that rejects anything evaluated under crisis."""
    return EthicalFilter(ruleset=EthicalRuleset(
        name="strict_test", reject_threshold=0.1, warn_threshold=0.05,
    ))


# ── 1. Sequence and explicit data flow ───────────────────────────────────────

class TestSequenceAndDataFlow:

    def test_stages_run_in_order_with_explicit_dataflow(self):
        orch, _ = build_orchestrator(["price", "budget", "summary"])
        result = orch.run_pipeline(
            ["price", "budget", "summary"],
            {"trail": [], "value": 0},
        )
        assert result.completed is True
        assert result.output["trail"] == ["price", "budget", "summary"]
        assert result.output["value"] == 3
        assert [s.status for s in result.steps] == ["completed"] * 3

    def test_first_stage_receives_original_input(self):
        orch, agents = build_orchestrator(["alpha", "beta"])
        orch.run_pipeline(["alpha", "beta"], {"trail": [], "value": 10})
        assert agents["alpha"].seen_inputs[0]["value"] == 10

    def test_later_stage_receives_previous_output_not_original(self):
        orch, agents = build_orchestrator(["alpha", "beta"])
        orch.run_pipeline(["alpha", "beta"], {"trail": [], "value": 10})
        # beta received alpha's OUTPUT (value=11), not the original input
        assert agents["beta"].seen_inputs[0]["value"] == 11
        assert agents["beta"].seen_inputs[0]["trail"] == ["alpha"]

    def test_transform_reshapes_stage_input(self):
        orch, agents = build_orchestrator(["alpha", "beta"])
        step = PipelineStep(
            domain="beta",
            transform=lambda original, prev: {
                "trail": prev["trail"],
                "value": prev["value"] * 100,
                "original_value": original["value"],
            },
        )
        orch.run_pipeline(["alpha", step], {"trail": [], "value": 1})
        seen = agents["beta"].seen_inputs[0]
        assert seen["value"] == 200          # (1+1) * 100
        assert seen["original_value"] == 1   # transform also sees the original
        assert seen["trail"] == ["alpha"]

    def test_plain_strings_are_valid_steps(self):
        orch, _ = build_orchestrator(["a", "b"])
        result = orch.run_pipeline(["a", "b"], {"trail": []})
        assert isinstance(result, PipelineResult)
        assert result.completed

    def test_emotional_state_propagates_to_every_stage(self):
        orch, agents = build_orchestrator(["a", "b"])
        orch.run_pipeline(["a", "b"], {"trail": []},
                          emotional_state="calm", location_id="store_42")
        for a in agents.values():
            assert a._current_emotional_state == "calm"
            assert a._current_location_id == "store_42"


# ── 2. Fail-closed configuration ─────────────────────────────────────────────

class TestFailClosedConfiguration:

    def test_empty_pipeline_raises(self):
        orch, _ = build_orchestrator(["a"])
        with pytest.raises(SETTConfigurationError):
            orch.run_pipeline([], {"trail": []})

    def test_unknown_domain_raises_before_any_stage_runs(self):
        orch, agents = build_orchestrator(["a", "b"])
        with pytest.raises(SETTAgentNotFoundError):
            orch.run_pipeline(["a", "ghost", "b"], {"trail": []})
        # Fail-closed means NO partial side effects: stage 'a' — which
        # comes BEFORE the bad domain — must never have executed.
        assert agents["a"].seen_inputs == []
        assert orch.read_universal_memory().get("data", {}) in ({}, None) or \
            "a_done" not in str(orch.read_universal_memory())

    def test_transform_returning_non_dict_fails_closed(self):
        orch, _ = build_orchestrator(["a", "b"])
        bad = PipelineStep(domain="b", transform=lambda o, p: "not a dict")
        with pytest.raises(SETTConfigurationError):
            orch.run_pipeline(["a", bad], {"trail": []})


# ── 3. Rejection handling as part of the mechanism ───────────────────────────

class TestRejectionHandling:

    def _run_rejected_pipeline(self):
        """3-stage pipeline where stage 2 gets rejected (crisis + strict)."""
        orch = SETTOrchestrator(ethical_filter=strict_filter())
        first = SilentAgent("first")       # returns, publishes nothing
        second = TraceAgent("second")      # publishes -> filter rejects
        third = TraceAgent("third")
        for a in (first, second, third):
            orch.register_agent(a)
        result = orch.run_pipeline(
            ["first", "second", "third"],
            {"trail": [], "value": 0},
            emotional_state="crisis",
        )
        return orch, result, third

    def test_pipeline_halts_and_reports_rejection(self):
        _, result, _ = self._run_rejected_pipeline()
        assert result.completed is False
        assert result.output is None
        assert [s.status for s in result.steps] == \
            ["completed", "rejected", "skipped"]

    def test_rejected_agent_never_publishes(self):
        orch, _, _ = self._run_rejected_pipeline()
        snapshot = str(orch.read_universal_memory())
        assert "second_done" not in snapshot

    def test_skipped_stage_never_runs(self):
        _, _, third = self._run_rejected_pipeline()
        assert third.seen_inputs == []

    def test_rejection_is_explicit_and_structured(self):
        _, result, _ = self._run_rejected_pipeline()
        r = result.rejection
        assert isinstance(r, RejectionOutcome)
        assert r.domain == "second"
        assert isinstance(r.score, float)          # structured, not parsed
        assert isinstance(r.threshold, float)
        assert r.score >= r.threshold
        assert isinstance(r.principle, str) and r.principle
        assert isinstance(r.reasoning, str) and r.reasoning
        assert r.message  # the human-readable str(e), preserved verbatim

    def test_rejection_never_touches_universal_memory(self):
        """The hand-off is explicit: nothing about the rejection is
        written to universal memory for someone to read back."""
        orch, result, _ = self._run_rejected_pipeline()
        snapshot = str(orch.read_universal_memory())
        assert result.rejection.domain == "second"
        assert "rejected" not in snapshot
        assert "rejection" not in snapshot

    def test_stage_outcome_carries_the_same_rejection(self):
        _, result, _ = self._run_rejected_pipeline()
        rejected_stage = result.steps[1]
        assert rejected_stage.rejection is result.rejection


# ── 4. Memory isolation between stages ───────────────────────────────────────

class TestMemoryIsolation:

    def test_private_memories_stay_private_across_stages(self):
        orch, agents = build_orchestrator(["a", "b"])
        orch.run_pipeline(["a", "b"], {"trail": []})
        # b's stage input contains nothing from a's private memory
        seen_by_b = agents["b"].seen_inputs[0]
        assert "secret_a" not in str(seen_by_b)
        assert "internal_a" not in str(seen_by_b)
        # and each agent's private memory holds only its own secret
        assert agents["a"]._private_memory.read("secret_a") == "internal_a"
        assert agents["a"]._private_memory.read("secret_b") is None
        assert agents["b"]._private_memory.read("secret_a") is None

    def test_stages_do_not_feed_from_universal_memory(self):
        """A value published to universal memory by stage 1 must NOT
        appear in stage 2's input — data flows hand-to-hand only."""
        orch, agents = build_orchestrator(["a", "b"])
        orch.run_pipeline(["a", "b"], {"trail": []})
        seen_by_b = agents["b"].seen_inputs[0]
        assert "a_done" not in seen_by_b  # published by a, not passed to b


# ── 5. process() untouched ───────────────────────────────────────────────────

class TestProcessUntouched:

    def test_route_to_one_agent_unchanged(self):
        orch, _ = build_orchestrator(["solo"])
        result = orch.process({"trail": [], "value": 5}, domain="solo")
        assert result["trail"] == ["solo"]
        assert result["value"] == 6

    def test_broadcast_unchanged(self):
        orch, _ = build_orchestrator(["x", "y"])
        results = orch.process({"trail": [], "value": 0})
        assert set(results.keys()) == {"x", "y"}
        # broadcast semantics: each agent got the ORIGINAL input,
        # not a chained one — pipelines did not leak into broadcast
        assert results["x"]["value"] == 1
        assert results["y"]["value"] == 1
