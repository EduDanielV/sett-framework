"""SETT v0.11.0 execution context and end-to-end trace contracts."""
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError

import pytest

from sett import (
    EthicalFilter,
    EthicalRuleset,
    ExecutionContext,
    PipelineStep,
    SETTAgent,
    SETTAgentNotFoundError,
    SETTConfigurationError,
    SETTEthicalFilterRejectedError,
    SETTExecutor,
    SETTExpert,
    SETTOrchestrator,
    SETTValidationError,
    TraceRecorder,
    current_execution_context,
)
from sett.core_ruler.execution_context import execution_scope


class EchoExpert(SETTExpert):
    def resolve(self, context):
        if self._private_memory is not None:
            self._private_memory.write("private_sentinel", context.get("secret"))
        return {"value": context.get("value", 0)}


class EchoAgent(SETTAgent):
    def __init__(self, domain="echo"):
        super().__init__(name=f"Echo[{domain}]", domain=domain)
        self.register_expert(EchoExpert("echo_expert"))

    def process(self, input_data):
        result = self.get_expert("echo_expert").resolve(input_data)
        self._publish_to_universal(result)
        return result


class ActionAgent(SETTAgent):
    def __init__(self, action_type="perform_effect"):
        super().__init__(name="ActionAgent", domain="actions")
        self._action_type = action_type

    def process(self, input_data):
        return self.submit_action(self._action_type, input_data)


def make_echo_orchestrator(domain="echo"):
    orchestrator = SETTOrchestrator()
    orchestrator.register_agent(EchoAgent(domain))
    return orchestrator


def event_kinds(orchestrator, trace_id):
    return [event.kind for event in orchestrator.get_trace(trace_id)]


class TestExecutionContext:
    def test_root_context_has_distinct_identifiers(self):
        context = ExecutionContext.create()
        assert context.trace_id
        assert context.run_id
        assert context.trace_id != context.run_id
        assert context.parent_id is None

    def test_derived_context_preserves_trace_and_sets_parent(self):
        root = ExecutionContext.create(application_id="demo")
        child = root.derive()
        assert child.trace_id == root.trace_id
        assert child.run_id != root.run_id
        assert child.parent_id == root.run_id
        assert child.application_id == "demo"

    def test_context_and_nested_metadata_are_immutable(self):
        context = ExecutionContext.create(metadata={"labels": {"tier": "test"}})
        with pytest.raises(FrozenInstanceError):
            context.trace_id = "changed"
        with pytest.raises(TypeError):
            context.metadata["new"] = "value"
        with pytest.raises(TypeError):
            context.metadata["labels"]["tier"] = "changed"

    @pytest.mark.parametrize(
        "metadata",
        [
            {"api_key": "raw"},
            {"auth_token": "raw"},
            {"value": object()},
            {1: "non-string-key"},
            {"number": float("inf")},
        ],
    )
    def test_unsafe_metadata_is_rejected(self, metadata):
        with pytest.raises(SETTValidationError):
            ExecutionContext.create(metadata=metadata)

    def test_scope_restores_parent_and_then_clears(self):
        parent = ExecutionContext.create()
        child = parent.derive()
        assert current_execution_context() is None
        with execution_scope(parent):
            assert current_execution_context() == parent
            with execution_scope(child):
                assert current_execution_context() == child
            assert current_execution_context() == parent
        assert current_execution_context() is None

    def test_thread_scopes_do_not_share_context(self):
        contexts = [ExecutionContext.create() for _ in range(4)]

        def observe(context):
            with execution_scope(context):
                return current_execution_context().trace_id

        with ThreadPoolExecutor(max_workers=4) as pool:
            observed = list(pool.map(observe, contexts))
        assert observed == [context.trace_id for context in contexts]
        assert len(set(observed)) == 4


class TestEndToEndTracing:
    def test_legacy_route_is_traced_without_signature_changes(self):
        orchestrator = make_echo_orchestrator()
        assert orchestrator.process({"value": 7}, domain="echo") == {"value": 7}
        trace_id = orchestrator.last_trace_id
        assert trace_id is not None
        kinds = event_kinds(orchestrator, trace_id)
        assert kinds == [
            "trace.started",
            "route.selected",
            "agent.started",
            "expert.started",
            "expert.completed",
            "memory.publication_proposed",
            "policy.evaluated",
            "memory.publication_committed",
            "agent.completed",
            "route.completed",
            "trace.completed",
        ]
        assert orchestrator.verify_traces(trace_id)
        assert current_execution_context() is None

    def test_supplied_context_is_used_as_trace_root(self):
        orchestrator = make_echo_orchestrator()
        root = ExecutionContext.create(
            application_id="example",
            session_id="opaque-session",
        )
        orchestrator.process({"value": 1}, domain="echo", execution_context=root)
        assert orchestrator.last_trace_id == root.trace_id
        first = orchestrator.get_trace(root.trace_id)[0]
        assert first.run_id == root.run_id

    def test_process_traced_returns_explicit_trace_identity(self):
        orchestrator = make_echo_orchestrator()
        traced = orchestrator.process_traced({"value": 8}, domain="echo")
        assert traced.result == {"value": 8}
        assert traced.trace_id == traced.context.trace_id
        assert orchestrator.get_trace(traced.trace_id)

    def test_two_calls_never_share_a_context(self):
        orchestrator = make_echo_orchestrator()
        orchestrator.process({"value": 1}, domain="echo")
        first = orchestrator.last_trace_id
        orchestrator.process({"value": 2}, domain="echo")
        second = orchestrator.last_trace_id
        assert first != second
        assert {event.trace_id for event in orchestrator.get_trace(first)} == {first}
        assert {event.trace_id for event in orchestrator.get_trace(second)} == {second}

    def test_private_and_input_values_do_not_leak_to_export(self):
        orchestrator = make_echo_orchestrator()
        sentinel = "PRIVATE-TRACE-SENTINEL-917"
        orchestrator.process(
            {"value": 3, "secret": sentinel},
            domain="echo",
        )
        exported = orchestrator.export_trace(orchestrator.last_trace_id)
        assert sentinel not in json.dumps(exported)
        assert "private_sentinel" not in json.dumps(exported)

    def test_publication_commit_is_caused_by_policy_decision(self):
        orchestrator = make_echo_orchestrator()
        orchestrator.process({"value": 3}, domain="echo")
        events = orchestrator.get_trace(orchestrator.last_trace_id)
        policy = next(event for event in events if event.kind == "policy.evaluated")
        committed = next(
            event for event in events
            if event.kind == "memory.publication_committed"
        )
        assert committed.cause_id == policy.event_id

    def test_export_is_defensive(self):
        orchestrator = make_echo_orchestrator()
        orchestrator.process({"value": 1}, domain="echo")
        exported = list(orchestrator.export_trace(orchestrator.last_trace_id))
        exported[0]["kind"] = "tampered"
        assert orchestrator.get_trace(orchestrator.last_trace_id)[0].kind == "trace.started"
        assert orchestrator.verify_traces()

    def test_broadcast_agents_are_sibling_runs(self):
        orchestrator = SETTOrchestrator()
        orchestrator.register_agent(EchoAgent("one"))
        orchestrator.register_agent(EchoAgent("two"))
        result = orchestrator.process({"value": 4})
        assert set(result) == {"one", "two"}
        events = orchestrator.get_trace(orchestrator.last_trace_id)
        agent_starts = [event for event in events if event.kind == "agent.started"]
        assert len(agent_starts) == 2
        assert agent_starts[0].run_id != agent_starts[1].run_id
        assert agent_starts[0].parent_id == agent_starts[1].parent_id
        assert orchestrator.verify_traces(orchestrator.last_trace_id)

    def test_pipeline_records_stages_and_skips_after_rejection(self):
        strict = EthicalRuleset(
            name="strict",
            reject_threshold=0.5,
            warn_threshold=0.1,
        )
        orchestrator = SETTOrchestrator(
            ethical_filter=EthicalFilter(ruleset=strict)
        )
        orchestrator.register_agent(EchoAgent("first"))
        orchestrator.register_agent(EchoAgent("second"))
        result = orchestrator.run_pipeline(
            [PipelineStep("first"), PipelineStep("second")],
            {"value": 1},
            emotional_state="crisis",
        )
        assert result.completed is False
        assert [step.status for step in result.steps] == ["rejected", "skipped"]
        kinds = event_kinds(orchestrator, orchestrator.last_trace_id)
        assert "pipeline.rejected" in kinds
        assert "pipeline.stage_skipped" in kinds
        assert orchestrator.verify_traces(orchestrator.last_trace_id)

    def test_empty_pipeline_has_terminal_failure_events(self):
        orchestrator = SETTOrchestrator()
        with pytest.raises(SETTConfigurationError):
            orchestrator.run_pipeline([], {})
        kinds = event_kinds(orchestrator, orchestrator.last_trace_id)
        assert kinds == [
            "trace.started",
            "pipeline.started",
            "pipeline.failed",
            "trace.failed",
        ]
        assert orchestrator.verify_traces(orchestrator.last_trace_id)

    def test_unknown_pipeline_domain_has_terminal_failure_events(self):
        orchestrator = SETTOrchestrator()
        with pytest.raises(SETTAgentNotFoundError):
            orchestrator.run_pipeline(["missing"], {})
        kinds = event_kinds(orchestrator, orchestrator.last_trace_id)
        assert kinds[-2:] == ["pipeline.failed", "trace.failed"]
        assert orchestrator.verify_traces()
        assert orchestrator.verify_traces(orchestrator.last_trace_id)

    def test_invalid_pipeline_step_has_terminal_failure_events(self):
        orchestrator = SETTOrchestrator()
        with pytest.raises(SETTConfigurationError):
            orchestrator.run_pipeline([object()], {})
        kinds = event_kinds(orchestrator, orchestrator.last_trace_id)
        assert kinds[-2:] == ["pipeline.failed", "trace.failed"]
        assert orchestrator.verify_traces(orchestrator.last_trace_id)

    @pytest.mark.parametrize(
        ("transform", "error_type"),
        [
            (lambda original, previous: "invalid", SETTConfigurationError),
            (
                lambda original, previous: (_ for _ in ()).throw(
                    RuntimeError("transform failed")
                ),
                RuntimeError,
            ),
        ],
    )
    def test_transform_failures_close_stage_pipeline_and_trace(
        self, transform, error_type
    ):
        orchestrator = make_echo_orchestrator()
        with pytest.raises(error_type):
            orchestrator.run_pipeline(
                [PipelineStep("echo", transform=transform)],
                {"value": 1},
            )
        kinds = event_kinds(orchestrator, orchestrator.last_trace_id)
        assert kinds[-3:] == [
            "pipeline.stage_failed",
            "pipeline.failed",
            "trace.failed",
        ]
        assert orchestrator.verify_traces(orchestrator.last_trace_id)

    def test_pipeline_success_uses_immediate_causal_events(self):
        orchestrator = make_echo_orchestrator()
        result = orchestrator.run_pipeline(["echo"], {"value": 2})
        assert result.completed is True
        events = orchestrator.get_trace(orchestrator.last_trace_id)
        route_completed = next(
            event for event in events if event.kind == "route.completed"
        )
        stage_completed = next(
            event for event in events
            if event.kind == "pipeline.stage_completed"
        )
        pipeline_completed = next(
            event for event in events if event.kind == "pipeline.completed"
        )
        trace_completed = next(
            event for event in events if event.kind == "trace.completed"
        )
        assert stage_completed.cause_id == route_completed.event_id
        assert pipeline_completed.cause_id == stage_completed.event_id
        assert trace_completed.cause_id == pipeline_completed.event_id

    def test_rejected_publication_is_caused_by_policy_event(self):
        strict = EthicalRuleset(
            name="strict",
            reject_threshold=0.5,
            warn_threshold=0.1,
        )
        orchestrator = SETTOrchestrator(
            ethical_filter=EthicalFilter(ruleset=strict)
        )
        orchestrator.register_agent(EchoAgent())
        with pytest.raises(SETTEthicalFilterRejectedError) as captured:
            orchestrator.process(
                {"value": 1},
                domain="echo",
                emotional_state="crisis",
            )
        events = orchestrator.get_trace(orchestrator.last_trace_id)
        policy = next(event for event in events if event.kind == "policy.evaluated")
        rejected = next(
            event for event in events
            if event.kind == "memory.publication_rejected"
        )
        agent_failed = next(
            event for event in events if event.kind == "agent.failed"
        )
        assert rejected.cause_id == policy.event_id
        assert agent_failed.cause_id == rejected.event_id
        assert captured.value.trace_event_id in {
            event.event_id
            for event in events
            if event.kind == "route.failed"
        }

    def test_expert_failure_propagates_to_route_and_trace(self):
        class FailingExpert(SETTExpert):
            def resolve(self, context):
                raise RuntimeError("failure")

        class FailingAgent(SETTAgent):
            def __init__(self):
                super().__init__("FailingAgent", "failure_chain")
                self.register_expert(FailingExpert("failing"))

            def process(self, input_data):
                return self.get_expert("failing").resolve(input_data)

        orchestrator = SETTOrchestrator()
        orchestrator.register_agent(FailingAgent())
        with pytest.raises(RuntimeError):
            orchestrator.process({}, domain="failure_chain")
        events = orchestrator.get_trace(orchestrator.last_trace_id)
        by_kind = {event.kind: event for event in events}
        assert by_kind["agent.failed"].cause_id == by_kind["expert.failed"].event_id
        assert by_kind["route.failed"].cause_id == by_kind["agent.failed"].event_id
        assert by_kind["trace.failed"].cause_id == by_kind["route.failed"].event_id
        assert orchestrator.verify_traces(orchestrator.last_trace_id)

    def test_agent_failure_is_structured_and_context_is_reset(self):
        class FailingAgent(SETTAgent):
            def __init__(self):
                super().__init__("FailingAgent", "failure")

            def process(self, input_data):
                raise RuntimeError("sensitive value must not be exported")

        orchestrator = SETTOrchestrator()
        orchestrator.register_agent(FailingAgent())
        with pytest.raises(RuntimeError):
            orchestrator.process({}, domain="failure")
        exported = orchestrator.export_trace(orchestrator.last_trace_id)
        assert "sensitive value" not in json.dumps(exported)
        assert "agent.failed" in event_kinds(
            orchestrator, orchestrator.last_trace_id
        )
        assert "trace.failed" in event_kinds(
            orchestrator, orchestrator.last_trace_id
        )
        assert current_execution_context() is None
        assert orchestrator.verify_traces(orchestrator.last_trace_id)


class TestActionTrace:
    def test_approved_action_links_policy_handler_and_result(self):
        calls = []
        executor = SETTExecutor()
        executor.register_handler(
            "perform_effect",
            lambda payload: calls.append(dict(payload)) or {"ok": True},
        )
        orchestrator = SETTOrchestrator()
        orchestrator.register_executor(executor)
        orchestrator.register_agent(ActionAgent())
        assert orchestrator.process({"secret": "payload-hidden"}, domain="actions") == {
            "ok": True
        }
        assert calls == [{"secret": "payload-hidden"}]
        kinds = event_kinds(orchestrator, orchestrator.last_trace_id)
        for required in (
            "action.proposed",
            "policy.evaluated",
            "action.approved",
            "handler.authorized",
            "handler.started",
            "handler.completed",
        ):
            assert required in kinds
        assert "payload-hidden" not in json.dumps(
            orchestrator.export_trace(orchestrator.last_trace_id)
        )
        events = orchestrator.get_trace(orchestrator.last_trace_id)
        policy = next(
            event for event in events
            if event.kind == "policy.evaluated"
            and event.attributes["action"] == "perform_effect"
        )
        approved = next(event for event in events if event.kind == "action.approved")
        handler_authorized = next(
            event for event in events if event.kind == "handler.authorized"
        )
        handler_started = next(
            event for event in events if event.kind == "handler.started"
        )
        handler_completed = next(
            event for event in events if event.kind == "handler.completed"
        )
        assert approved.cause_id == policy.event_id
        assert handler_authorized.cause_id == approved.event_id
        assert handler_started.cause_id == handler_authorized.event_id
        assert handler_completed.cause_id == handler_started.event_id
        assert orchestrator.verify_traces(orchestrator.last_trace_id)

    def test_rejected_action_has_no_handler_event_or_effect(self):
        calls = []
        executor = SETTExecutor()
        executor.register_handler(
            "perform_effect", lambda payload: calls.append(payload)
        )
        strict = EthicalRuleset(
            name="strict",
            reject_threshold=0.5,
            warn_threshold=0.1,
        )
        orchestrator = SETTOrchestrator(
            ethical_filter=EthicalFilter(ruleset=strict)
        )
        orchestrator.register_executor(executor)
        orchestrator.register_agent(ActionAgent())
        with pytest.raises(SETTEthicalFilterRejectedError):
            orchestrator.process(
                {"value": 1},
                domain="actions",
                emotional_state="crisis",
            )
        kinds = event_kinds(orchestrator, orchestrator.last_trace_id)
        assert "action.rejected" in kinds
        assert "handler.started" not in kinds
        assert calls == []
        events = orchestrator.get_trace(orchestrator.last_trace_id)
        policy = next(
            event for event in events
            if event.kind == "policy.evaluated"
            and event.attributes["action"] == "perform_effect"
        )
        rejected = next(
            event for event in events if event.kind == "action.rejected"
        )
        agent_failed = next(
            event for event in events if event.kind == "agent.failed"
        )
        assert rejected.cause_id == policy.event_id
        assert agent_failed.cause_id == rejected.event_id

    def test_missing_handler_records_failure_without_effect(self):
        executor = SETTExecutor()
        orchestrator = SETTOrchestrator()
        orchestrator.register_executor(executor)
        orchestrator.register_agent(ActionAgent("missing"))
        with pytest.raises(SETTConfigurationError):
            orchestrator.process({}, domain="actions")
        kinds = event_kinds(orchestrator, orchestrator.last_trace_id)
        assert "handler.failed" in kinds
        assert "handler.started" not in kinds
        events = orchestrator.get_trace(orchestrator.last_trace_id)
        handler_failed = next(
            event for event in events if event.kind == "handler.failed"
        )
        agent_failed = next(
            event for event in events if event.kind == "agent.failed"
        )
        assert agent_failed.cause_id == handler_failed.event_id

    def test_exporter_failure_blocks_real_world_effect(self):
        calls = []
        executor = SETTExecutor()
        executor.register_handler(
            "perform_effect", lambda payload: calls.append(payload)
        )
        orchestrator = SETTOrchestrator()
        orchestrator.register_executor(executor)
        orchestrator.register_agent(ActionAgent())

        def unavailable_exporter(event):
            raise OSError("sink unavailable")

        orchestrator.register_trace_exporter(unavailable_exporter)
        with pytest.raises(SETTConfigurationError):
            orchestrator.process({}, domain="actions")
        assert calls == []
        kinds = event_kinds(orchestrator, orchestrator.last_trace_id)
        assert "handler.authorized" in kinds
        assert "handler.blocked" in kinds
        assert "handler.started" not in kinds
        assert orchestrator.verify_traces(orchestrator.last_trace_id)


class TestTraceRecorderHardening:
    def test_cross_trace_cause_is_invalid(self):
        recorder = TraceRecorder()
        first = ExecutionContext.create()
        first_event = recorder.record(
            first,
            kind="custom.first",
            component_type="test",
            component_name="first",
            status="completed",
        )
        second = ExecutionContext.create()
        recorder.record(
            second,
            kind="custom.second",
            component_type="test",
            component_name="second",
            status="completed",
            cause_id=first_event.event_id,
        )
        assert recorder.verify() is False
        assert recorder.verify(second.trace_id) is False

    def test_missing_parent_is_invalid_globally_and_per_trace(self):
        recorder = TraceRecorder()
        context = ExecutionContext(
            parent_id="missing-run",
        )
        recorder.record(
            context,
            kind="custom.child",
            component_type="test",
            component_name="child",
            status="completed",
        )
        assert recorder.verify() is False
        assert recorder.verify(context.trace_id) is False

    def test_one_run_cannot_change_parent(self):
        recorder = TraceRecorder()
        root = ExecutionContext.create()
        recorder.record(
            root,
            kind="custom.root",
            component_type="test",
            component_name="root",
            status="completed",
        )
        first_parent = root.derive()
        recorder.record(
            first_parent,
            kind="custom.parent",
            component_type="test",
            component_name="first_parent",
            status="completed",
        )
        child = root.derive()
        recorder.record(
            child,
            kind="custom.child",
            component_type="test",
            component_name="child",
            status="completed",
        )
        inconsistent = ExecutionContext(
            trace_id=root.trace_id,
            run_id=child.run_id,
            parent_id=first_parent.run_id,
        )
        recorder.record(
            inconsistent,
            kind="custom.inconsistent",
            component_type="test",
            component_name="child",
            status="completed",
        )
        assert recorder.verify() is False
        assert recorder.verify(root.trace_id) is False

    def test_terminal_event_cannot_precede_its_start(self):
        recorder = TraceRecorder()
        context = ExecutionContext.create()
        recorder.record(
            context,
            kind="route.completed",
            component_type="orchestrator",
            component_name="test",
            status="completed",
        )
        recorder.record(
            context,
            kind="route.selected",
            component_type="orchestrator",
            component_name="test",
            status="completed",
        )
        assert recorder.verify() is False

    def test_nested_event_attributes_are_deeply_immutable(self):
        recorder = TraceRecorder()
        context = ExecutionContext.create()
        event = recorder.record(
            context,
            kind="custom.immutable",
            component_type="test",
            component_name="immutable",
            status="completed",
            attributes={
                "nested": {"value": "original"},
                "items": ["one"],
            },
        )
        with pytest.raises(TypeError):
            event.attributes["nested"]["value"] = "changed"
        with pytest.raises(AttributeError):
            event.attributes["items"].append("two")
        assert recorder.verify()

    @pytest.mark.parametrize(
        "value",
        [float("nan"), float("inf"), float("-inf")],
    )
    def test_non_finite_trace_attributes_are_rejected(self, value):
        recorder = TraceRecorder()
        with pytest.raises(SETTValidationError):
            recorder.record(
                ExecutionContext.create(),
                kind="custom.invalid_number",
                component_type="test",
                component_name="invalid",
                status="failed",
                attributes={"value": value},
            )

    @pytest.mark.parametrize(
        "key",
        ["password", "api_token", "medical_record", "biometric_value"],
    )
    def test_sensitive_public_attributes_are_rejected(self, key):
        recorder = TraceRecorder()
        with pytest.raises(SETTValidationError):
            recorder.record(
                ExecutionContext.create(),
                kind="custom.sensitive",
                component_type="test",
                component_name="sensitive",
                status="failed",
                attributes={key: "raw"},
            )

    @pytest.mark.parametrize(
        "attributes",
        [
            {f"key_{index}": index for index in range(33)},
            {"value": object()},
            {"oversized": "x" * (16 * 1024)},
        ],
    )
    def test_public_attribute_limits_are_enforced(self, attributes):
        recorder = TraceRecorder()
        with pytest.raises(SETTValidationError):
            recorder.record(
                ExecutionContext.create(),
                kind="custom.invalid_attributes",
                component_type="test",
                component_name="invalid",
                status="failed",
                attributes=attributes,
            )

    def test_public_attribute_depth_is_enforced(self):
        nested = {}
        cursor = nested
        for index in range(9):
            cursor["level"] = {}
            cursor = cursor["level"]
            cursor["index"] = index
        with pytest.raises(SETTValidationError):
            TraceRecorder().record(
                ExecutionContext.create(),
                kind="custom.too_deep",
                component_type="test",
                component_name="invalid",
                status="failed",
                attributes=nested,
            )

    def test_standard_json_export_rejects_no_values(self):
        orchestrator = make_echo_orchestrator()
        orchestrator.process({"value": 1}, domain="echo")
        exported = orchestrator.export_trace(orchestrator.last_trace_id)
        json.dumps(exported, allow_nan=False)

    def test_incomplete_instrumented_trace_is_invalid(self):
        recorder = TraceRecorder()
        context = ExecutionContext.create()
        recorder.record(
            context,
            kind="trace.started",
            component_type="orchestrator",
            component_name="test",
            status="started",
        )
        assert recorder.verify() is False
        assert recorder.verify(context.trace_id) is False
