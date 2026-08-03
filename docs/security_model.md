# SETT security and safety model

## Execution trace privacy

SETT 0.11 adds causal execution traces without turning the trace into a copy
of application memory. The default trace contains component names, operation
types, statuses, reason codes, correlation identifiers, safe counts, risk
decision fields, and error types. It does not contain input payloads, action
payloads, handler results, exception messages or locals, prompts, model
responses, biometric values, risk profiles, or private-memory values.

`ExecutionContext.metadata` accepts only recursively JSON-safe values. It
rejects sensitive key fragments, framework-reserved keys, non-finite numbers,
non-string mapping keys, and unsupported objects. It is bounded by key count,
depth, and serialized size. Optional subject/session identifiers are opaque;
applications should use pseudonymous values.

`export_trace()` returns defensive sanitized dictionaries. Exporter callbacks
receive the same defensive representation. Exporters are best-effort for
diagnostic events, but a failure while exporting the pre-effect
`handler.authorized` event records `handler.blocked` and blocks the handler.
`handler.started` therefore means the authorization event was committed and
exported successfully. SETT does not permit an effect it cannot trace at that
configured boundary.

Direct `TraceRecorder.record()` calls apply the same recursive constraints:
attributes are deeply frozen, limited to 32 keys, depth 8, and 16 KiB,
non-finite numbers and sensitive key fragments are rejected, and unsupported
objects are never converted with `repr()`.

The recorder's hash chain is tamper-evident, not signed. External append-only
storage, signatures, access control, retention, and deletion policy remain
deployment responsibilities.

## Fail-closed execution

A `SETTExecutor` executes a registered handler only when all of these conditions
are true:

1. it is attached through `SETTOrchestrator.register_executor()`;
2. the attached `UniversalMemory` has an `EthicalFilter`;
3. the filter approves the proposed `Action`;
4. a handler is registered for the exact action type.

Any missing condition raises and no handler runs. Agents must also be registered
before publishing results or proposing actions; detached agents no longer
silently discard governed operations.

## Situation urgency is not action harm

`SafetyAssessment` keeps four dimensions separate:

- `situation_urgency`: seriousness of the human context;
- `action_harm_risk`: expected harm caused by the proposed action;
- `omission_risk`: expected harm caused by doing nothing;
- `protective_action`: whether the action is intended to reduce omission risk.

The EthicalFilter derives its base verdict from `ContextAnalysis.risk_score`,
which a domain `ContextAnalyzer` must derive from the proposed action. High
urgency never inflates that score and does not automatically reject or warn an
action explicitly classified as protective.

As a conservative fallback, when `human_at_risk=True`, the action is **not**
classified as protective, and the score would otherwise produce `ALLOW`, the
filter promotes only that decision to `WARN`. The score remains unchanged and
the audit entry records the reason code
`human_at_risk_without_protective_classification`. This means “review-worthy
urgency without a protective classification”, not “the action is necessarily
harmful” and not necessarily “no domain analyzer exists”.

## Defensive snapshots

Universal-memory reads, history, ethical audit entries, and Executor logs return
deep copies. Mutating a returned object cannot rewrite internal state.
`PrivateMemory.read()` and `PrivateMemory.get_all()` return deep copies as well,
since v0.9.0 (a downstream integrator mutating a nested value read from an
agent's own workspace could otherwise corrupt stored data without ever calling
`write()`, with no trace in `get_history()` - the same failure mode the
Universal Memory guarantee above already closed). This paragraph previously
claimed `PrivateMemory` "intentionally retains normal Python object identity" -
that was accurate before v0.9.0, but the hardening pass changed it; the text
was never updated to match. Applications should still prefer storing immutable
values where practical, but should not rely on mutating a value read from
`PrivateMemory` to have any effect on stored state.

## Tamper-evident logs

Each history or audit entry contains a sequence number, the previous entry hash,
and its own SHA-256 hash. `verify_history()` and `verify_audit_log()` verify the
chain. Unified execution-trace verification additionally rejects duplicate
event IDs, cross-trace or forward causes, missing/cross-trace parent runs, and
instrumented starts without exactly one corresponding terminal outcome.

This detects accidental or in-process modification when verification runs. It
does **not** provide authenticity against an attacker who can rewrite both the
log and all hashes, and it is not a digital signature. Sensitive deployments
should export the chain to append-only storage and sign or externally anchor it.

## Remaining boundaries

- Harm-category weights remain policy metadata; they are not silently injected
  into numerical scoring in v0.8.
- SETT supplies mechanisms, not validated medical, legal, or emergency policy.
- Domain applications must provide analyzers, consent, regional procedures,
  verified contacts, and provider-specific reliability controls.
