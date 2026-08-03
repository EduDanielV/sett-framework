# SETT v0.11.0: ExecutionContext and end-to-end trace design

Status: implemented release contract  
Target: SETT Framework v0.11.0  
Baseline: SETT v0.10.1  
Scope: framework-generic execution identity, causal trace propagation, safe trace export, and backward compatibility

## 1. Decision summary

SETT v0.11.0 will introduce:

1. An immutable, derivable `ExecutionContext`.
2. A per-orchestrator `TraceRecorder` containing structured, causally linked `TraceEvent` records.
3. Explicit context parameters at framework entry points and ambient propagation inside a run through Python `contextvars`.
4. Instrumented boundaries for orchestrator, agent, expert, pipeline stage, memory publication, policy evaluation, action submission, handler execution, result, and error.
5. Sanitized trace views and exporter hooks that never inspect or export `PrivateMemory` values.
6. A compatibility path in which existing `process(input_data)` and `resolve(context)` implementations continue to work unchanged.

This release will not add conversation persistence, a consumer-specific session model, cancellation, deadlines, idempotency, generic persistence, or `PolicyDecision`. Those remain assigned to later roadmap releases.

## 2. Why this shape fits the current code

The v0.10.1 public extension contract requires applications to override:

- `SETTAgent.process(input_data)`
- `SETTExpert.resolve(context)`

Changing those abstract signatures would force a coordinated migration in every consumer, including the current companion-assistant reference application. Conversely, keeping context only as optional metadata on `SETTOrchestrator.process()` would not propagate it through custom agent and expert code and would fail the roadmap gate.

The design therefore uses two complementary paths:

- explicit context at SETT-owned boundaries;
- a run-local `ContextVar` while legacy application-owned methods execute.

The ambient value is not application state and is never a global singleton context. It is a scoped transport mechanism: a token is set immediately before invocation and reset in `finally`. `ContextVar` gives separate values to threads and asynchronous task contexts and prevents nested runs from overwriting their parent.

## 3. Core data model

### 3.1 ExecutionContext

Proposed public module: `sett.core_ruler.execution_context`

```python
@dataclass(frozen=True, slots=True)
class ExecutionContext:
    trace_id: str
    run_id: str
    parent_id: str | None
    created_at: datetime
    application_id: str | None = None
    instance_id: str | None = None
    subject_id: str | None = None
    session_id: str | None = None
    turn_id: str | None = None
    metadata: Mapping[str, JsonValue] = field(default_factory=...)

    @classmethod
    def create(..., metadata: Mapping[str, JsonValue] | None = None) -> ExecutionContext:
        ...

    def derive(
        self,
        *,
        metadata: Mapping[str, JsonValue] | None = None,
    ) -> ExecutionContext:
        ...

    def safe_view(self) -> dict[str, JsonValue]:
        ...
```

Semantics:

- `trace_id` identifies the complete causal execution tree.
- `run_id` identifies one execution node within that tree.
- `parent_id` is the immediate parent's `run_id`; it is `None` only for a root context.
- `created_at` is timezone-aware UTC.
- `derive()` preserves `trace_id` and all optional identity fields, creates a new `run_id`, sets `parent_id` to the current `run_id`, and creates a new timestamp.
- Optional identifiers are opaque strings. SETT does not interpret consumer session or user semantics.
- IDs are generated as lowercase UUID strings by default, but callers may supply valid non-empty identifiers to continue a trace received from another boundary.

`metadata` accepts only recursively JSON-safe values: `None`, booleans, finite numbers, strings, tuples/sequences of safe values, and string-keyed mappings of safe values. Construction recursively copies and freezes it. Unsupported objects, non-string keys, non-finite floats, excessive nesting, and reserved keys raise `SETTValidationError`.

Metadata limits should be conservative and deterministic:

- maximum 32 top-level keys;
- maximum nesting depth 8;
- maximum serialized safe view 16 KiB;
- reserved prefix `sett.` for framework-owned metadata.

These limits prevent a trace context from becoming a hidden memory or payload channel.

### 3.2 TraceEvent

Proposed public module: `sett.audit_ruler.trace`

```python
@dataclass(frozen=True, slots=True)
class TraceEvent:
    event_id: str
    trace_id: str
    run_id: str
    parent_id: str | None
    cause_id: str | None
    timestamp: datetime
    sequence: int
    kind: str
    component_type: str
    component_name: str
    status: str
    reason_codes: tuple[str, ...]
    attributes: Mapping[str, JsonValue]
    previous_hash: str
    entry_hash: str
```

Identity and causality are separate:

- context `parent_id` links execution nodes;
- event `cause_id` links a decision or effect to the event that immediately caused it.

`kind`, `status`, and reason codes are stable machine-readable lowercase identifiers. Human-readable error messages may appear only in sanitized attributes.

Initial event kinds:

- `trace.started`, `trace.completed`, `trace.failed`
- `route.selected`, `route.completed`, `route.failed`, `broadcast.started`, `broadcast.completed`, `broadcast.failed`
- `agent.started`, `agent.completed`, `agent.failed`
- `expert.started`, `expert.completed`, `expert.failed`
- `pipeline.started`, `pipeline.stage_started`, `pipeline.stage_completed`, `pipeline.stage_rejected`, `pipeline.stage_skipped`, `pipeline.stage_failed`, `pipeline.completed`, `pipeline.rejected`, `pipeline.failed`
- `memory.publication_proposed`, `memory.publication_committed`, `memory.publication_rejected`
- `policy.evaluated`
- `action.proposed`, `action.approved`, `action.rejected`
- `handler.authorized`, `handler.started`, `handler.completed`, `handler.failed`, `handler.blocked`

Reason code examples:

- `route.explicit_domain`
- `route.broadcast`
- `policy.allow`, `policy.warn`, `policy.reject`
- `memory.publication`
- `pipeline.previous_stage_rejected`
- `handler.not_registered`
- `component.exception`

The reason-code vocabulary is append-only during the 0.x line. Adding a code is compatible; changing the meaning of an existing code is not.

### 3.3 TraceRecorder

`TraceRecorder` is owned by one `SETTOrchestrator`, just like its `UniversalMemory`. It:

- appends defensive, hash-chained events;
- assigns a monotonic sequence per recorder;
- indexes events by `trace_id`;
- returns immutable/defensive snapshots;
- verifies the hash chain;
- invokes registered exporter hooks with a sanitized event view.

Minimum public surface:

```python
class TraceRecorder:
    def record(...) -> TraceEvent: ...
    def get_trace(self, trace_id: str) -> tuple[TraceEvent, ...]: ...
    def export_trace(
        self,
        trace_id: str,
        *,
        view: Literal["summary", "sanitized"] = "sanitized",
    ) -> tuple[dict[str, JsonValue], ...]: ...
    def register_exporter(self, exporter: TraceExporter) -> None: ...
    def verify(self) -> bool: ...
```

Exporter failures do not alter ordinary diagnostic results. The
`handler.authorized` event is the committed pre-effect boundary: if an exporter
fails there, SETT records `handler.blocked`, raises `SETTConfigurationError`,
and does not record `handler.started` or invoke the handler. Exporters receive
defensive sanitized dictionaries, never component objects.

## 4. Context creation and propagation

### 4.1 Public entry points

Backward-compatible signatures add keyword-only context:

```python
orchestrator.process(
    input_data,
    domain=None,
    emotional_state="unknown",
    location_id="global",
    *,
    execution_context: ExecutionContext | None = None,
)

orchestrator.run_pipeline(
    steps,
    input_data,
    emotional_state="unknown",
    location_id="global",
    *,
    execution_context: ExecutionContext | None = None,
)
```

If omitted, the orchestrator creates a fresh root context. If supplied, it validates and uses that context as the root of this call; child component contexts are derived from it.

`process()` continues returning the existing result type. v0.11.0 does not silently replace it with an envelope. The trace ID is available through:

- a caller-supplied context;
- `orchestrator.last_trace_id` as a convenience for sequential debugging only;
- exporter hooks;
- an additive `process_traced()` helper returning `TracedResult[T]`.

`last_trace_id` must not be used for correlation in concurrent applications.

### 4.2 Internal scope

The module exposes:

```python
def current_execution_context() -> ExecutionContext | None: ...
```

Framework base classes expose a protected convenience property:

```python
self._execution_context
```

It reads the active `ContextVar`; it does not store the context on the agent or expert instance. Application code may read it but cannot mutate it.

Every SETT-owned call boundary follows:

1. derive a child context;
2. record the boundary start event;
3. bind it with a context manager;
4. invoke application code;
5. record completion or structured error;
6. reset the context token in `finally`.

No execution context remains attached to a reusable agent, expert, memory, or executor after the call.

### 4.3 Agent and expert compatibility

Existing agent implementations remain valid:

```python
def process(self, input_data):
    result = self.get_expert("intent").resolve(input_data)
    self._publish_to_universal(result)
    return result
```

Agent invocation is instrumented by the orchestrator.

Expert invocation must also be observable even with the existing `get_expert(...).resolve(...)` idiom. At `register_expert()`, SETT will attach an internal invocation interceptor to the registered expert. The interceptor preserves the original bound `resolve(context)` signature and:

- derives an expert child context from the active agent context;
- records start/completion/failure;
- binds the expert context while the original implementation runs.

The interceptor is installed once and is idempotent. Direct calls to a registered expert outside any orchestrated run still work and do not invent a disconnected trace unless the caller explicitly binds a context. Standalone, unregistered experts behave exactly as in v0.10.1.

This is preferable to changing the abstract method to `_resolve()` in v0.11.0. A template-method migration may be reconsidered only for 1.0 API freeze.

### 4.4 Pipelines and broadcasts

- One top-level call has one root trace.
- A broadcast derives one child context per agent from the root. Sibling agents share a `trace_id`, never a `run_id`.
- A pipeline derives one context for the pipeline and one child per stage.
- The agent invoked by a stage derives from that stage context.
- A skipped stage receives a trace event but its agent is never invoked.
- Transforms execute inside the stage context and failures are recorded without exposing their input.

This yields deterministic causal order for the current sequential runtime. General concurrency remains outside v0.11.0.

## 5. Component propagation contract

### Orchestrator

Records trace lifecycle, routing choice, selected domains, completion, and errors. It owns the recorder and public trace lookup/export API.

### Agent

Reads the active context. `_publish_to_universal()`, `propose_action()`, and `submit_action()` forward it explicitly to memory/executor boundaries.

The existing mutable `_current_emotional_state` and `_current_location_id` remain for v0.11 compatibility, but are not copied into `ExecutionContext.metadata`. They are domain inputs, not trace identity. Replacing their transport can be considered with lifecycle/concurrency work.

### Expert

Receives a derived active context through the registration interceptor.
Private-memory reads, writes, keys, and values are not traced in v0.11.0. The
roadmap gate concerns governed publication to Universal Memory; private-memory
operation tracing remains a possible future opt-in capability.

### UniversalMemory

`update()` receives `execution_context` and `cause_id` as keyword-only internal/public optional arguments. It records proposal, policy decision reference, commit or rejection.

The trace stores:

- publishing domain;
- top-level field count;
- no result values, field names, or digests.

It never reads `PrivateMemory`.

### EthicalFilter

`evaluate()` adds optional keyword-only `execution_context` and `cause_id`. It emits one `policy.evaluated` event containing:

- verdict;
- existing structured risk fields;
- thresholds;
- structured reason codes;
- evidence references to prior event IDs.

The current `FilterVerdict` remains the return contract. `PolicyDecision` is not pulled forward from v0.15.0.

### Action and Executor

`Action` remains data and gains a stable generated `action_id`. Trace identity
is not embedded in its mutable payload.

`SETTExecutor.submit()` receives optional keyword-only context and cause ID. It records proposal, evaluation linkage, authorization, handler boundaries, result type, and structured failure. It never records the payload or handler result.

Handlers remain `Callable[[payload], result]` for compatibility. An additive `register_context_handler()` may support `Callable[[payload, ExecutionContext], result]`; SETT must never infer this by catching `TypeError`, because that would confuse a handler's own bug with a signature mismatch.

## 6. Privacy and sanitization

The default trace is operational metadata, not an input/output transcript.

Hard rules:

- `PrivateMemory.get_all()` is never called by tracing code.
- No payload, prompt, model response, biometric reading, user profile, risk profile, action payload, handler result, or exception locals are exported by default.
- `subject_id`, `session_id`, and `turn_id` are opaque correlation identifiers. Applications should pass pseudonymous values.
- Metadata keys matching `password`, `secret`, `token`, `authorization`, `cookie`, `api_key`, or `credential` are rejected case-insensitively.
- Exception type and a bounded sanitized message may be traced; traceback locals are forbidden.
- Public `TraceRecorder.record()` attributes are recursively validated, deeply frozen, size-bounded, and rejected if a key is sensitive.

Sanitization has two layers in v0.11.0:

1. framework allowlist for built-in attributes;
2. final recursive safe-value, sensitive-key, finite-number, and size validation in `TraceRecorder`.

There is no application sanitizer or digest fallback in v0.11.0. Invalid public
attributes raise `SETTValidationError`; internal instrumentation uses only
framework-controlled metadata. Raw data is never used as fallback.

## 7. Trace reconstruction

Given a `trace_id`, `export_trace()` must make the following path reconstructable:

```text
trace
  -> route or pipeline stage
  -> agent
  -> expert(s)
  -> publication proposal
  -> policy evaluation
  -> publication commit/rejection
  -> action proposal
  -> policy evaluation
  -> handler execution
  -> result or error
```

Reconstruction means identifying what component ran, in what causal order, what structured decision it produced, whether an effect ran, and why a branch stopped. It does not mean reconstructing hidden reasoning or raw private data.

Each event carries both the execution node (`run_id`/`parent_id`) and immediate event cause (`cause_id`). Missing referenced events make trace verification fail even if the underlying hash chain is intact.

## 8. Error behavior

- All component boundaries record failures before re-raising existing exceptions.
- Existing exception types and return behavior remain unchanged.
- Rejected broadcasts retain their current result shape.
- Pipeline rejection retains `RejectionOutcome`; it adds trace/event identifiers as optional fields with defaults.
- A missing or invalid explicit context raises `SETTValidationError` before any agent or handler runs.
- Recorder failure must fail closed for side-effect trace events: if SETT cannot record `action.approved` or commit/export `handler.authorized`, the handler does not execute and `SETTConfigurationError` is raised.
- Recorder/exporter failure for non-effect diagnostic events does not change the application result.

The distinction above preserves the framework's structural authority guarantee: an untraceable real-world effect is not allowed.

## 9. Compatibility contract

The following v0.10.1 code must run unchanged:

- `orchestrator.process(data, domain="...")`
- `orchestrator.process(data)` broadcast
- `orchestrator.run_pipeline(steps, data)`
- custom `SETTAgent.process(input_data)`
- custom `SETTExpert.resolve(context)`
- direct `UniversalMemory.update(agent, result)`
- direct `EthicalFilter.evaluate(action, context)`
- existing executor handlers accepting only payload

New parameters are keyword-only where possible. Existing positional parameter meanings do not change. Trace additions to result dataclasses are optional and placed after existing fields.

Consumer-specific identifiers are accepted only as opaque optional fields. SETT does not create, persist, expire, or interpret sessions.

## 10. Implementation slices

### Slice A: context primitives

- Add safe immutable metadata implementation.
- Add `ExecutionContext`, validation, derivation, safe view, and scoped binding.
- Export public symbols from `sett.__init__`.
- Unit-test immutability, deep freezing, IDs, timestamps, nested scopes, thread/task isolation, and invalid metadata.

### Slice B: unified trace

- Add `TraceEvent`, `TraceRecorder`, hash/cause verification, safe export, and exporter protocol.
- Reuse the existing audit-chain canonicalization where possible without changing v0.10.1 chain semantics.
- Add orchestrator trace lookup and verification.

### Slice C: routing, agents, experts, and pipelines

- Add root-context creation at entry points.
- Instrument routing/broadcast/pipeline boundaries.
- Add scoped agent invocation.
- Add idempotent registered-expert interceptor.
- Verify every branch resets the active context after success, rejection, and exception.

### Slice D: memory and policy

- Forward context through agent publication and action evaluation.
- Record publication and policy events with causal references.
- Add strict recorder attribute validation and prove no private-memory values enter events.

### Slice E: actions and effects

- Add `action_id`.
- Instrument executor and handler boundaries.
- Require successful effect-boundary recording before handler execution.
- Add context-aware handler registration without changing existing handlers.

### Slice F: migration and documentation

- Update API reference, concepts, security model, getting started, README, changelog, and examples.
- Add a v0.11 migration guide showing unchanged legacy code and opt-in traced code.
- Integrate the reference consumer only after the SETT contract suite passes.

## 11. Required tests for the release gate

### Identity and isolation

- Two calls without explicit contexts have different `trace_id` and `run_id`.
- Derived contexts share only the intended immutable values.
- Broadcast siblings share a trace but not a run ID.
- Nested calls restore the outer context.
- Exceptions and rejections leave no active context behind.
- Concurrent threads/tasks do not observe one another's contexts.

### Complete causal paths

- Routed success: route -> agent -> expert -> policy -> publication -> completion.
- Broadcast with one rejection: independent child paths and explicit rejection.
- Multi-stage pipeline: stage/agent/expert/publication links and deterministic skipped stages.
- Approved action: proposal -> policy -> approval -> handler -> result.
- Rejected action: no handler event and no handler call.
- Missing handler: structured error and no effect.
- Handler exception: started/failed events and preserved exception behavior.

### Privacy

- Sentinel secrets placed in private memory, metadata, input, action payload, handler result, and exception locals never appear in exported traces.
- Unsafe metadata is rejected.
- Invalid, sensitive, oversized, or non-finite recorder attributes are rejected.
- Exporters receive defensive values and cannot mutate the recorder.

### Compatibility

- The full v0.10.1 suite passes unchanged.
- Representative legacy subclasses need no signature edits.
- Direct standalone component calls keep their prior behavior.
- The reference consumer's full baseline suite passes against SETT v0.11 compatibility mode before its next integration release begins.

### Integrity

- Sequence/hash tampering is detected.
- Missing, reordered, or cross-trace causal references are detected.
- Effect execution is blocked when the recorder cannot commit its pre-effect event.

## 12. Gate interpretation

v0.11.0 is complete when, from one `trace_id`, a caller can safely reconstruct:

- routing;
- agents and experts invoked;
- published-memory proposals and commits;
- policy verdicts and structured reasons;
- actions and their proposers;
- selected handlers;
- results, rejections, and errors;
- immediate and parent causal links.

The gate is not met by merely adding IDs to existing independent logs. The same context and causal event references must propagate end to end, and two executions must never share a context accidentally.

## 13. Deferred decisions

The following are deliberately deferred:

- cancellation/deadline fields: v0.12.0;
- idempotency keys and retry attempts: v0.12.0;
- adapter capability and provider-attempt events: v0.13.0;
- durable trace storage and restoration: v0.14.0;
- `PolicyDecision`, consent, conditions, and human review: v0.15.0;
- distributed trace-header standards and concurrency fan-out: conditional/post-validation.

The v0.11 data model leaves room for these through derivation, reason codes, and exporter interfaces without pretending they already exist.
