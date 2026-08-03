# SETT Framework 0.11.0 audit record

Audit date: 2026-07-29  
Baseline: SETT Framework 0.10.1  
Target: SETT Framework 0.11.0

## Release gate

The 0.11.0 trace gate is satisfied:

- one `trace_id` reconstructs routing, agents, experts, pipeline stages,
  governed memory publication, policy decisions, action proposals, handlers,
  results, rejections, and errors;
- execution nodes have distinct `run_id` values and causal `parent_id` links;
- events have immediate `cause_id` links and a tamper-evident SHA-256 chain;
- independent executions do not share context;
- legacy agent and expert signatures remain valid;
- trace exports do not expose private-memory values or raw application
  payloads;
- configured exporter failure at the pre-effect boundary prevents the handler
  from running.

## Verification results

| Check | Result |
|---|---|
| SETT inherited and new tests | 340 passed |
| New 0.11 trace contract file | 50 passed |
| Reference-consumer compatibility | 841 passed |
| Ruff on all changed Python files | Passed |
| Python compile/import | Passed |
| Wheel build | Passed (`sett_framework-0.11.0-py3-none-any.whl`) |
| Isolated wheel install/import | Passed; reported version 0.11.0 |
| Version agreement (`pyproject.toml`, `sett.__version__`) | 0.11.0 |
| Public-tree language guard | Passed as part of SETT suite |
| Internal-name guard | Passed as part of SETT suite |

The compatibility suite imported SETT from this 0.11.0 source tree and did not
modify the consumer application.

## External audit remediation

The release candidate received a second, independent adversarial review. Every
reported finding was reproduced before remediation.

| Finding | Resolution | Regression evidence |
|---|---|---|
| Pipeline errors could leave open traces | All validation, transform, routing, and agent exceptions now emit stage (when applicable), pipeline, and trace failure terminals. | Empty, invalid step/domain, invalid transform result, transform exception, and agent exception tests. |
| Causes skipped immediate events | Concrete event IDs now propagate through policy/publication, action/handler, agent/route, stage/pipeline, and root completion/failure. | Exact causal-chain assertions for success, rejection, and errors. |
| Cross-trace causes and inconsistent parents passed verification | Global and per-trace verification reject cross-trace/forward causes, missing or cross-trace parents, reused run IDs, changed parents, duplicate event IDs, and invalid terminal order. | Adversarial recorder verification tests. |
| `TraceEvent.attributes` was only shallowly immutable | Recorder attributes are recursively copied and frozen; exports thaw into defensive values. | Nested mapping/list mutation tests. |
| Non-standard JSON numbers were accepted | `NaN` and infinities are rejected and canonical/export serialization uses `allow_nan=False`. | Parameterized non-finite and standards-compliant export tests. |
| Exporter failure left a false `handler.started` | `handler.authorized` is the committed pre-effect boundary; failure emits `handler.blocked`, and neither `handler.started` nor the handler invocation occurs. | Failing-exporter/no-effect test. |
| Public recorder attributes lacked privacy limits | Public `record()` now rejects sensitive keys, unsupported objects, excessive keys/depth/bytes, and non-finite numbers. | Public-recorder boundary tests. |
| Design claimed unimplemented sanitizers/digests | The release contract now documents only structural metadata and strict rejection; application sanitizers and digest fallbacks are explicitly absent from 0.11.0. | Documentation cross-check. |

The broad historical Ruff configuration reports legacy style findings outside
the 0.11.0 change set. The release gate is intentionally the established
changed-file lint command; every modified Python module and the trace contract
test pass it. No unrelated bulk style rewrite is included in this release.

## Principal implementation files

- `sett/core_ruler/execution_context.py`
- `sett/audit_ruler/trace.py`
- `sett/core_ruler/orchestrator.py`
- `sett/core_ruler/agent.py`
- `sett/core_ruler/expert.py`
- `sett/memory_ruler/universal.py`
- `sett/ethics_ruler/ethic_kernel/filter.py`
- `sett/core_ruler/action.py`
- `sett/core_ruler/executor.py`
- `sett/exceptions.py`
- `tests/test_execution_context_v011.py`

## Public additions

- `ExecutionContext`
- `TracedResult`
- `current_execution_context()`
- `TraceEvent`
- `TraceRecorder`
- `SETTOrchestrator.process_traced()`
- `SETTOrchestrator.get_trace()`
- `SETTOrchestrator.export_trace()`
- `SETTOrchestrator.register_trace_exporter()`
- `SETTOrchestrator.verify_traces()`
- `SETTOrchestrator.last_trace_id`
- `Action.action_id`

## Compatibility statement

No change is required to existing:

- `SETTAgent.process(input_data)` implementations;
- `SETTExpert.resolve(context)` implementations;
- payload-only executor handlers;
- routed and broadcast `process()` calls;
- native pipeline definitions;
- direct memory and filter calls.

The explicit `execution_context` parameter is keyword-only at orchestrator
entry points.

## Security boundaries

- Trace data is operational metadata, not a transcript.
- Private-memory values are never inspected by tracing.
- Raw inputs, action payloads, handler results, and exception messages/locals
  are excluded by default.
- Metadata is recursively frozen, size-bounded, depth-bounded, and checked for
  sensitive key fragments.
- The hash chain detects in-process mutation but is not a digital signature.
- Durable storage, retention, deletion, signing, and external access control
  remain deployment responsibilities.

## Deliberately deferred

The release does not claim cancellation, deadlines, timeout states,
idempotency, durable persistence, adapter capabilities, distributed tracing,
or structured policy decisions. These remain assigned to later roadmap
releases.

## Reproduction

Run the framework suite with development and optional adapter dependencies
available:

```text
python -m pytest -q -p no:cacheprovider
```

Run Ruff over the changed modules and the new test file:

```text
ruff check sett tests/test_execution_context_v011.py
```

Run the reference consumer with this source directory first on `PYTHONPATH`.
The compatibility run must report that `sett.__version__ == "0.11.0"` before
collecting its tests.
