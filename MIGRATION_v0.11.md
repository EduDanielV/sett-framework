# Migrating from SETT 0.10.x to 0.11.0

SETT 0.11.0 is source-compatible with normal 0.10.x agents, experts,
pipelines, memory calls, and executor handlers. No existing method signature
must be changed.

## Existing code remains valid

```python
result = orchestrator.process(data, domain="support")
```

Custom implementations remain:

```python
class MyExpert(SETTExpert):
    def resolve(self, context):
        return {"value": context["value"]}


class MyAgent(SETTAgent):
    def process(self, input_data):
        result = self.get_expert("main").resolve(input_data)
        self._publish_to_universal(result)
        return result
```

Registered expert calls are instrumented without replacing the public
`resolve(context)` contract.

## Retrieve an automatic trace

```python
result = orchestrator.process(data, domain="support")
trace_id = orchestrator.last_trace_id

events = orchestrator.get_trace(trace_id)
safe_export = orchestrator.export_trace(trace_id)
assert orchestrator.verify_traces(trace_id)
```

`last_trace_id` is a sequential-debugging convenience. Concurrent applications
should create a context explicitly or use `process_traced()`.

## Pass correlation identifiers

```python
from sett import ExecutionContext

context = ExecutionContext.create(
    application_id="support-service",
    instance_id="worker-2",
    subject_id="opaque-subject",
    session_id="opaque-session",
    turn_id="turn-17",
    metadata={"channel": "web"},
)

result = orchestrator.process(
    data,
    domain="support",
    execution_context=context,
)
```

Identifiers are opaque. SETT does not create sessions, persist conversations,
or interpret user identity.

## Return result and trace identity together

```python
traced = orchestrator.process_traced(data, domain="support")
print(traced.result)
print(traced.trace_id)
```

## Read the active context inside an extension

Agents and experts can inspect `self._execution_context` while they execute.
The public helper is also available:

```python
from sett import current_execution_context

context = current_execution_context()
```

Do not save that object as mutable application state. Pass explicit identifiers
at the next external boundary instead.

## Register a trace exporter

```python
def append_to_sink(event):
    external_sink.append(event)


orchestrator.register_trace_exporter(append_to_sink)
```

The callback receives a defensive sanitized dictionary. Payloads and private
memory are not included. Exporter failures are best-effort for diagnostics,
but failure at the pre-effect `handler.authorized` event records
`handler.blocked` and blocks the real-world handler. `handler.started` is
emitted only after that boundary succeeds.

## Metadata validation

Context metadata:

- must be JSON-safe;
- is recursively frozen;
- allows at most 32 top-level keys;
- has maximum depth 8;
- has a maximum serialized size of 16 KiB;
- rejects sensitive key fragments and the reserved `sett.` prefix.

Keep prompts, payloads, credentials, personal records, and model outputs out of
metadata.

The same limits apply to attributes submitted directly through
`TraceRecorder.record()`. Nested mappings and sequences are deeply frozen;
non-finite floats, sensitive keys, unsupported objects, excessive depth, key
count, or serialized size raise `SETTValidationError`.

## Explicitly deferred

SETT 0.11.0 does not introduce cancellation, deadlines, timeout states,
idempotency, durable trace storage, adapter capabilities, or structured
`PolicyDecision`. These belong to later releases and are not required for this
migration.
