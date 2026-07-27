# Migrating from SETT 0.7 to 0.8

## Detached agents now raise

Register an agent before calling code paths that publish or propose actions:

```python
orchestrator = SETTOrchestrator(ethical_filter=EthicalFilter())
orchestrator.register_agent(agent)
orchestrator.process(payload, domain=agent.domain)
```

Direct calls to `agent.process()` remain possible only when that implementation
does not publish or propose governed actions. Tests should wire the real
orchestrator when exercising those paths.

## Detached Executors now raise

```python
executor = SETTExecutor()
executor.register_handler("send_notification", handler)
orchestrator.register_executor(executor)
```

Calling `executor.submit()` before registration raises
`SETTConfigurationError`. An orchestrator without an `EthicalFilter` also cannot
execute handlers.

## Audit and memory snapshots

Code that intentionally mutated objects returned by `read()`, `read_all()`,
`get_history()`, or `get_audit_log()` must instead perform an explicit governed
write. Returned values are snapshots.

## Protective actions

Custom analyzers can return a `SafetyAssessment` to distinguish crisis urgency
from the harm of the response itself. Existing analyzers continue to work; a
default assessment is created automatically.

During the unreleased 0.8.0 hardening cycle, one conservative fallback was
added without changing the public method signatures: an otherwise `ALLOW`
decision becomes `WARN` when `human_at_risk=True` and the analyzer has not
classified the action as protective. This does not alter `risk_score`, does not
weaken a `REJECT`, and does not affect domain actions with
`protective_action=True`. Audit consumers may inspect
`decision_reason_codes` for
`human_at_risk_without_protective_classification`.
