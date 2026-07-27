# SETT v0.8 security and safety model

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
`PrivateMemory` intentionally retains normal Python object identity because it
is an agent-local workspace; applications should store immutable values there
when stronger guarantees are required.

## Tamper-evident logs

Each history or audit entry contains a sequence number, the previous entry hash,
and its own SHA-256 hash. `verify_history()` and `verify_audit_log()` verify the
chain.

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
