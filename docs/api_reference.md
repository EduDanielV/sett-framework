# API Reference

Complete reference for all public classes and functions in the SETT framework.

All public symbols can be imported directly from the `sett` package:

```python
from sett import SETTOrchestrator, SETTAgent, SETTExpert, EthicalFilter, RiskLevel, ...
```

---

## core_ruler

### SETTOrchestrator

The central coordinator of any SETT system. Holds all registered agents, manages universal memory, and applies the EthicalFilter before any action or memory write is committed.

```python
SETTOrchestrator(ethical_filter=None)
```

| Parameter | Type | Description |
|---|---|---|
| `ethical_filter` | `EthicalFilter \| None` | The filter to use. Defaults to `EthicalFilter()` with the default SETT ruleset. |

**Methods**

---

`register_agent(agent)` → `None`

Register an agent with the orchestrator. Connects the agent to universal memory automatically.

| Parameter | Type | Description |
|---|---|---|
| `agent` | `SETTAgent` | The agent to register. Its `domain` must be unique within this orchestrator. |

---

`get_agent(domain)` → `SETTAgent`

Retrieve a registered agent by domain.

| Parameter | Type | Description |
|---|---|---|
| `domain` | `str` | The domain key of the agent to retrieve. |

Raises `SETTAgentNotFoundError` if no agent is registered for the given domain.

---

`process(input_data, domain=None, emotional_state="unknown")` → `dict`

Process input through the system. Routes to a specific agent if `domain` is given; broadcasts to all agents if not.

| Parameter | Type | Description |
|---|---|---|
| `input_data` | `dict` | The data to process. |
| `domain` | `str \| None` | If provided, routes to that agent only. |
| `emotional_state` | `str` | Detected emotional state of the user. Passed to the EthicalFilter. |

Returns the result dict from the agent (or a `{domain: result}` dict when broadcasting).

Raises `SETTEthicalFilterRejectedError` if the EthicalFilter blocks any agent's action.

---

`read_universal_memory()` → `dict`

Snapshot of all agent results currently in universal memory. Does not include environmental context entries.

---

`publish_environmental_context(risk_level, location_id="global", source_domain="orchestrator", message="")` → `EnvironmentalContext`

Publish an environmental risk level to a shared location slot. Other SETT instances reading the same `location_id` will see this context and their filters will tighten accordingly.

| Parameter | Type | Description |
|---|---|---|
| `risk_level` | `RiskLevel` | The risk level to publish. |
| `location_id` | `str` | Identifier of the shared space (e.g. `"store_42"`). Defaults to `"global"`. |
| `source_domain` | `str` | The agent domain that triggered this (e.g. `"health"`). |
| `message` | `str` | Optional description. Must NOT contain personal data. |

---

`read_environmental_context(location_id="global")` → `EnvironmentalContext | None`

Read the current environmental context for a location. Returns `None` if no context has been published for that location.

---

`read_all_environmental_contexts()` → `dict[str, EnvironmentalContext]`

Return all published environmental contexts, keyed by `location_id`.

---

`get_ethical_audit_log()` → `list[dict]`

Return the full audit log of every ethical decision made since this orchestrator was created. Each entry contains: `sequence`, `previous_hash`, `entry_hash`, `timestamp`, `action`, `harm_score`, `verdict`, `emotional_state`, `human_at_risk`, `situation_urgency`, `action_harm_risk`, `omission_risk`, `protective_action`, `env_risk_level`, `env_modifier`, `effective_reject_threshold`, `effective_warn_threshold`, `decision_reason_codes`, and `reasoning`. The first three fields are the SHA-256 hash chain added in v0.8.0 (see `verify_ethical_audit_log()` below).

---

`verify_ethical_audit_log()` → `bool`

Verify the sequence and hash chain of the log returned by `get_ethical_audit_log()`. Delegates to the underlying `EthicalFilter.verify_audit_log()`, reachable here so tamper-evidence can be checked from the orchestrator itself: the entry point every example in this document already uses, without needing access to the filter directly. Returns `True` if the chain is intact, `False` if any entry was altered outside of `append_chained_entry()`. Tamper-evident within the running process only; this is not an external cryptographic signature.

---

`registered_domains` *(property)* → `list[str]`

List of all registered agent domains.

---

`run_pipeline(steps, input_data, emotional_state="unknown", location_id="global")` → `PipelineResult`

Run an ordered sequence of stages, each handled by a different registered agent, with **explicit data flow** between stages. This is an additive capability: `process()` (route-to-one / broadcast-to-all) is unchanged. Each stage executes through the same path as routed processing: same propagation of `emotional_state` / `location_id`, same `EthicalFilter` evaluation on publish, same audit log entries.

`steps` is a list where each element is a `PipelineStep(domain, transform=None)` or a plain domain string (shorthand for a step without transform). By default the first stage receives `input_data` and every later stage receives the previous stage's output; a `transform(original_input, prev_output) -> dict` reshapes the stage's input when needed.

Three guarantees define the mechanism:

1. **Memory isolation between stages.** Stage inputs are passed hand-to-hand, never read from universal memory. Each agent keeps its own `PrivateMemory`; no stage sees another stage's intermediate reasoning.
2. **Fail-closed configuration.** All stage domains are validated *before* the first stage runs (`SETTAgentNotFoundError`), an empty pipeline raises `SETTConfigurationError`, and a transform returning a non-dict raises `SETTConfigurationError`. A misconfigured pipeline never produces partial side effects.
3. **Rejection handling as part of the mechanism.** If the `EthicalFilter` rejects a stage: that agent publishes nothing, the remaining stages are marked `"skipped"`, and the rejection is returned **explicitly** in `PipelineResult.rejection` as a `RejectionOutcome` carrying the structured fields (`action`, `score`, `threshold`, `principle`, `reasoning`, `message`) taken directly from the exception's attributes. The rejection is never written to, nor meant to be read from, universal memory: the caller that synthesizes the final response receives it directly.

Return types (all frozen dataclasses, importable from `sett`):

| Type | Fields |
|---|---|
| `PipelineStep` | `domain`, `transform` |
| `StageOutcome` | `domain`, `status` (`"completed"` / `"rejected"` / `"skipped"`), `output`, `rejection` |
| `RejectionOutcome` | `domain`, `action`, `score`, `threshold`, `principle`, `reasoning`, `message` |
| `PipelineResult` | `completed`, `steps`, `output` (final stage's output when completed), `rejection` |

```python
from sett import PipelineStep

result = orchestrator.run_pipeline(
    ["price", "promotions", PipelineStep(
        domain="budget",
        transform=lambda original, prev: {**prev, "limit": original["limit"]},
    )],
    input_data={"items": [...], "limit": 150.0},
    emotional_state="calm",
)

if result.completed:
    final = result.output
else:
    r = result.rejection            # explicit hand-off: not in memory
    notify_user(r.principle, r.score)   # structured, no string parsing
```

---

### SETTAgent

Abstract base class for all SETT agents. Extend this class and implement `process()` to create a domain specialist.

```python
SETTAgent(name, domain)
```

| Parameter | Type | Description |
|---|---|---|
| `name` | `str` | Human-readable name (e.g. `"HealthAgent"`). |
| `domain` | `str` | Domain key used by the orchestrator for routing (e.g. `"health"`). |

**Methods**

---

`register_expert(expert)` → `None`

Register an expert with this agent. Gives the expert access to this agent's private memory. Call this in `__init__` for each expert the agent uses.

---

`get_expert(name)` → `SETTExpert`

Retrieve a registered expert by name. Raises `SETTExpertNotFoundError` if not found.

---

`process(input_data)` → `dict` *(abstract: must be implemented)*

Main processing method. Coordinate experts, use private memory for intermediate state, compose a final result, call `_publish_to_universal(result)`, and return the result.

| Parameter | Type | Description |
|---|---|---|
| `input_data` | `dict` | The data this agent needs to process. |

---

`_publish_to_universal(result, risk_profile=None)` → `None`

Publish the agent's final result to universal memory. This is the only way an agent communicates outward. The result passes through the EthicalFilter before being stored: `emotional_state` and the `EnvironmentalContext` for the agent's current location are forwarded automatically. Call this at the end of `process()`.

Note: this only evaluates a result AFTER it exists. It does not gate real-world side effects (sending a message, calling an API) that may have already happened inside `resolve()`/`process()`. For that, use `propose_action()` or `submit_action()` below.

---

`propose_action(action, action_context=None, risk_profile=None)` → `None`

Gate a real-world side effect through the `EthicalFilter` **before** it is executed: call this from inside `resolve()`/`process()`, before performing the effect yourself. Lightweight and opt-in: the developer must remember to call it. Raises `SETTEthicalFilterRejectedError` if blocked; the side effect must not be performed in that case.

---

`submit_action(action_type, payload=None, risk_profile=None)` → `Any`

Structural alternative to `propose_action()`: describes the effect as an `Action` and submits it to the `SETTExecutor` registered with this orchestrator (see the `Action` / `SETTExecutor` section below). The agent never holds a reference to the real client: only the Executor's registered handler does, and only if the `EthicalFilter` approves. Raises `SETTConfigurationError` if no `Executor` (or no handler for this `action_type`) is registered.

---

`experts` *(property)* → `list[str]`

Names of all registered experts.

**Minimal implementation**

```python
class MyAgent(SETTAgent):
    def __init__(self):
        super().__init__(name="MyAgent", domain="my_domain")
        self.register_expert(MyExpert(name="my_expert"))

    def process(self, input_data):
        result = self.get_expert("my_expert").resolve(input_data)
        self._publish_to_universal(result)
        return result
```

---

### SETTExpert

Abstract base class for all SETT experts. Extend this class and implement `resolve()` to create a specialized module.

```python
SETTExpert(name)
```

| Parameter | Type | Description |
|---|---|---|
| `name` | `str` | Unique name within the parent agent. Used to retrieve this expert via `agent.get_expert(name)`. |

**Methods**

---

`resolve(context)` → `dict` *(abstract: must be implemented)*

Main method of the expert. Process the context, write relevant state to private memory via `self._private_memory`, and return a result dict.

| Parameter | Type | Description |
|---|---|---|
| `context` | `dict` | Input data provided by the parent agent. |

---

`attach_memory(memory)` → `None`

Called automatically by the parent agent during `register_expert()`. Do not call manually.

---

`_private_memory` *(attribute)* → `PrivateMemory | None`

The agent's private memory. Available after `attach_memory()` is called (i.e. after `register_expert()`). Always check `if self._private_memory:` before writing.

**Minimal implementation**

```python
class MyExpert(SETTExpert):
    def resolve(self, context):
        value = context.get("input", "")
        if self._private_memory:
            self._private_memory.write("last_input", value)
        return {"processed": value.upper()}
```

---

### PhrasingExpert

Base class for any expert whose job includes producing text the user will actually read or hear (a greeting, an acknowledgment, a synthesized summary, a redacted alert). Formalizes a pattern discovered independently twice while building an early companion-assistant prototype, before either instance was planned as reusable.

```python
from sett import PhrasingExpert

PhrasingExpert(name, llm=None)
```

Subclasses implement up to four methods instead of `resolve()` directly (the first three required, the fourth optional): `resolve()` is a template method you should not override:

| Method | Description |
|---|---|
| `determine_facts(context)` → `dict` | Pure deterministic logic: no LLM involved. Returns what's true regardless of how it ends up phrased. |
| `build_prompt(facts, context)` → `str` | Describes, in natural language, what the LLM should say based on the facts already computed. Never pass raw, unprocessed context the LLM could misread as license to invent additional facts. |
| `fallback_text(facts, context)` → `str` | The deterministic text used when there's no LLM configured, or when the call fails for any reason. Must always produce a valid result on its own. |
| `verify_facts(phrased, facts, context)` → `str` (optional, added in 0.10.0) | Called after `phrased` already exists (from the LLM or from `fallback_text()`), to validate the actual text against facts already known and swap it out if it contradicts them. Default: returns `phrased` unchanged. |

| Class attribute | Description |
|---|---|
| `OUTPUT_KEY` | The key the phrased text is merged under in the result dict. Override per subclass (e.g. `"greeting"`, `"summary"`). Defaults to `"text"`. |
| `SYSTEM_PROMPT` | The system prompt sent to the LLM. Override per subclass/persona. |

**Contract:** the LLM only *phrases* facts your deterministic logic already produced: it never invents or alters them. If no `llm` is given, or the adapter raises `SETTLLMAdapterError`, `PhrasingExpert` falls back to `fallback_text()` automatically; a broken or absent LLM never prevents an agent from responding.

**Minimal implementation**

```python
class GreetingExpert(PhrasingExpert):
    OUTPUT_KEY = "greeting"

    def determine_facts(self, context):
        hour = context.get("hour", 9)
        return {"time_of_day": "morning" if hour < 12 else "afternoon"}

    def build_prompt(self, facts, context):
        return f"Greet the user. It's {facts['time_of_day']}."

    def fallback_text(self, facts, context):
        return {"morning": "Good morning.", "afternoon": "Good afternoon."}[facts["time_of_day"]]

expert = GreetingExpert(name="greeting", llm=OllamaAdapter())
result = expert.resolve({"hour": 8})
# {"time_of_day": "morning", "greeting": "<LLM-phrased or fallback text>"}
```

---

### StubDomainAgent

A generic, ready-to-use placeholder agent for a domain that isn't built yet. Unlike `agent_template.py`/`expert_template.py` in `templates/`, this needs no subclassing or customization: import it and use it directly.

```python
from sett import StubDomainAgent

StubDomainAgent(domain, name=None)
```

Useful when assembling a multi-agent system incrementally: register a `StubDomainAgent` for every domain your router or synthesizer needs to be able to call, so the full flow (dispatch → collect → synthesize) is testable end to end before any of the real agents exist. Swap in the real agent later by registering it under the same domain: since `SETTOrchestrator.register_agent()` keys agents by domain, the new registration replaces the stub with no other change required anywhere else in the system.

`process()` returns `{"status": "stub", "domain": ..., "received": <input_data>}`: an honest, structured result a downstream synthesizer can narrate as "not built yet" instead of crashing or fabricating an answer.

```python
orchestrator.register_agent(StubDomainAgent("health"))
# ... later, once HealthAgent exists:
orchestrator.register_agent(HealthAgent())  # replaces the stub
```

---

## memory_ruler

### PrivateMemory

Exclusive memory belonging to one agent. Only the experts within that agent can write to it. The orchestrator has no access.

```python
PrivateMemory(owner)
```

| Parameter | Type | Description |
|---|---|---|
| `owner` | `str` | The name of the agent that owns this memory. |

**Methods**

| Method | Returns | Description |
|---|---|---|
| `write(key, value)` | `None` | Store any Python value under `key`. |
| `read(key, default=None)` | `Any` | Read a value by key. Returns `default` if not found. |
| `get_all()` | `dict` | Copy of all stored values. |
| `clear()` | `None` | Remove all values. |
| `get_history()` | `list[dict]` | Full write history for auditing. |
| `owner` *(property)* | `str` | The name of the owning agent. |

---

### UniversalMemory

Shared memory accessible by all agents and the orchestrator. Every write passes through the EthicalFilter if one is configured. Also stores environmental context for multi-instance coordination.

Instantiated automatically by `SETTOrchestrator`. You do not normally need to create one directly.

**Methods**

| Method | Returns | Description |
|---|---|---|
| `update(agent, result)` | `None` | Publish an agent's final result. Passes through EthicalFilter. |
| `read(agent, default=None)` | `Any` | Read the latest result from a specific agent. |
| `read_all()` | `dict` | Snapshot of all agent results. Excludes environmental context entries. |
| `publish_environmental_context(context)` | `None` | Publish an `EnvironmentalContext` to a shared location slot. |
| `read_environmental_context(location_id)` | `EnvironmentalContext \| None` | Read the context for a location. Returns `None` if not set. |
| `read_all_environmental_contexts()` | `dict` | All published contexts, keyed by `location_id`. |
| `get_history()` | `list[dict]` | Full write history. |

---

## risk_ruler

### RiskLevel

Six-level environmental risk scale. Describes the state of the environment a user is in: not the user themselves.

```python
class RiskLevel(IntEnum):
    LEVEL_0 = 0   # Normal: baseline operation
    LEVEL_1 = 1   # Attention: anomaly detected
    LEVEL_2 = 2   # Warning: controlled threat
    LEVEL_3 = 3   # Danger: active threat, prepare for response
    LEVEL_4 = 4   # Critical: immediate action required
    LEVEL_5 = 5   # Emergency: maximum protocol
```

**Properties**

| Property | Type | Description |
|---|---|---|
| `label` | `str` | Human-readable name (e.g. `"Critical"`). |
| `description` | `str` | Full description of what this level means. |
| `emoji` | `str` | Visual indicator (e.g. `"🛑"`). |
| `color` | `str` | Hex color code for UI use. |
| `is_elevated()` | `bool` | `True` for any level ≥ `LEVEL_1`. |
| `is_critical()` | `bool` | `True` for `LEVEL_4` and `LEVEL_5`. |

`RiskLevel` values are comparable integers: `RiskLevel.LEVEL_3 > RiskLevel.LEVEL_1`.

---

### RiskProfile

Three-pillar user risk assessment. Stored exclusively in `PrivateMemory`. Never published to `UniversalMemory`.

```python
RiskProfile(
    emotional_instability=0.0,
    influence_vulnerability=0.0,
    collateral_damage_potential=0.0,
)
```

All values are floats in `[0.0, 1.0]`. Raises `ValueError` if any value is out of range.

| Pillar | Description |
|---|---|
| `emotional_instability` | Propensity to irrational or self-destructive behavior under current stress. |
| `influence_vulnerability` | Susceptibility to external manipulation in the current state. |
| `collateral_damage_potential` | Potential impact of this user's decisions on their environment. |

**Properties**

| Property | Type | Description |
|---|---|---|
| `composite_score` | `float` | Weighted combination of the three pillars (0.0–1.0). Weights: instability 45%, collateral 30%, vulnerability 25%. |
| `suggested_level` | `RiskLevel` | Suggested environmental `RiskLevel` based on `composite_score`. |
| `dominant_pillar` | `str` | Name of the pillar with the highest value. |

**Class methods**

| Method | Description |
|---|---|
| `RiskProfile.baseline()` | Returns a neutral profile with all pillars at 0.0. |
| `RiskProfile.from_dict(data)` | Reconstruct from a dict stored in `PrivateMemory`. |

**Instance methods**

| Method | Description |
|---|---|
| `to_dict()` | Serialize for storage in `PrivateMemory`. |

---

### EnvironmentalContext

Shared environmental state published by one SETT instance and readable by all instances in the same location. Never contains personal data.

```python
EnvironmentalContext(
    risk_level,
    location_id="global",
    source_domain="unknown",
    message="",
)
```

| Parameter | Type | Description |
|---|---|---|
| `risk_level` | `RiskLevel` | The current risk level of this environment. |
| `location_id` | `str` | Identifier of the shared space (e.g. `"store_42"`). |
| `source_domain` | `str` | The agent domain that published this (e.g. `"health"`). Never a user identifier. |
| `message` | `str` | Optional description. Must NOT contain personal data. |

**Properties**

| Property | Type | Description |
|---|---|---|
| `requires_response` | `bool` | `True` for level ≥ 2. |
| `requires_evacuation` | `bool` | `True` for level ≥ 4. |
| `auto_notify_emergency` | `bool` | `True` for level ≥ 4. |
| `is_systemic_emergency` | `bool` | `True` only for level 5. |
| `filter_threshold_modifier` | `float` | How much this context tightens the EthicalFilter thresholds (0.0–4.0). |

**Class methods**

| Method | Description |
|---|---|
| `EnvironmentalContext.normal(location_id)` | Returns a baseline level-0 context for a location. |
| `EnvironmentalContext.from_dict(data)` | Reconstruct from `UniversalMemory` storage. |

**Privacy contract:** `EnvironmentalContext` never contains personal identifiers, biometric values, or `RiskProfile` data. It communicates "the environment has this level": never "this person has this profile".

---

## biometric_ruler

### BiometricReading

Structural data model for physical vital-sign readings: same role for biometrics that `RiskProfile`/`EnvironmentalContext` play in `risk_ruler`: a typed value object `ethics_ruler` consumes, not a decision-maker itself. Extracted from `ContextAnalyzer._detect_human_at_risk`, which read `context["health"]`/`context["heart_rate_bpm"]` directly before this pillar existed.

```python
BiometricReading(
    heart_rate_bpm=None,
    temperature_celsius=None,
)
```

All fields optional and immutable (`frozen=True`). A reading with no data present is valid and never critical.

**Properties**

| Property | Type | Description |
|---|---|---|
| `is_critical` | `bool` | `True` if heart rate is outside 40–150 bpm, or temperature is outside 35.0–39.5°C. |

**Class methods**

| Method | Description |
|---|---|
| `BiometricReading.from_context(context)` | Parse a reading out of an action's `context` dict. Prefers a nested `context["health"]` dict if present and non-empty; otherwise reads `heart_rate_bpm`/`temperature_celsius` directly from the top-level context. This nested/flat fallback is the fix for a real bug (v0.1.1): an agent publishing flat biometric keys was previously invisible to risk detection because only the nested form was checked. |

**Instance methods**

| Method | Description |
|---|---|
| `to_dict()` | Serialize for logging/storage. |

**Privacy note:** `ContextAnalyzer` only ever reads `is_critical` (a bool) from this class, never the raw vital-sign values, so raw biometric data cannot leak into the audit log or `UniversalMemory` through this path, the same structural guarantee `RiskProfile` has for its own pillars.

---

## ethics_ruler

### EthicalFilter

The governance layer of SETT. Intercepts every action and every `UniversalMemory` write. Returns `ALLOW`, `WARN`, or `REJECT`.

```python
EthicalFilter(ruleset=None, context_analyzer=None)
```

| Parameter | Type | Description |
|---|---|---|
| `ruleset` | `EthicalRuleset \| None` | Rules to evaluate against. Defaults to `default_ruleset()`. |
| `context_analyzer` | `ContextAnalyzer \| None` | Analyzer for the three-layer evaluation. Defaults to `ContextAnalyzer()`. |

**Methods**

---

`evaluate(action, context, emotional_state="unknown", risk_profile=None, environmental_context=None)` → `FilterVerdict`

Evaluate an action through the three-layer system.

| Parameter | Type | Description |
|---|---|---|
| `action` | `str` | Description of what is about to happen. |
| `context` | `dict` | Data associated with this action. |
| `emotional_state` | `str` | Detected emotional state of the user. |
| `risk_profile` | `RiskProfile \| None` | Three-pillar user assessment (Layer 2). |
| `environmental_context` | `EnvironmentalContext \| None` | Shared environmental state (Layer 3). |

Returns `FilterVerdict.ALLOW` or `FilterVerdict.WARN`.
Raises `SETTEthicalFilterRejectedError` if the action is blocked.

The base verdict is derived from action harm score. If `human_at_risk=True`,
`protective_action=False`, and the base verdict would be `ALLOW`, the filter
promotes it to `WARN` without changing the score. The audit entry records
`human_at_risk_without_protective_classification` in
`decision_reason_codes`. Explicitly protective actions are not promoted.

---

`register_analyzer(action_type, analyzer)` → `None`

Registers a domain-specific `ContextAnalyzer` for one exact action type. Real deployments often need more than keyword-based scoring for a specific action, e.g. an economic analyzer for `"confirm_purchase"` that reads `over_budget_amount`, or a health analyzer for `"emergency_call"` that reads vitals directly. Any `action_type` without a registered analyzer keeps using the generic one passed to `__init__` (or the default `ContextAnalyzer`), additive and safe, existing code that never calls this keeps working exactly as before.

| Parameter | Type | Description |
|---|---|---|
| `action_type` | `str` | Must match the exact `action` string passed to `evaluate()`. |
| `analyzer` | `ContextAnalyzer` | The analyzer to use for this action type only. |

```python
filt = EthicalFilter()  # generic analyzer stays the fallback for everything else
filt.register_analyzer("confirm_purchase", EconomicContextAnalyzer())
```

---

`unregister_analyzer(action_type)` → `None`

Removes a previously registered analyzer for an action type: it falls back to the generic analyzer again. Safe to call even if nothing was registered for it.

---

`get_audit_log()` → `list[dict]`

Full audit log of every decision. Each entry includes: `sequence`, `previous_hash`, `entry_hash`, `timestamp`, `action`, `harm_score`, `verdict`, `emotional_state`, `human_at_risk`, `situation_urgency`, `action_harm_risk`, `omission_risk`, `protective_action`, `env_risk_level`, `env_modifier`, `effective_reject_threshold`, `effective_warn_threshold`, `decision_reason_codes`, and `reasoning`.

---

`verify_audit_log()` → `bool`

Verify the sequence and hash chain of the audit log: `True` if every entry's `previous_hash` correctly links to the prior entry's `entry_hash` and no entry was altered outside of the internal `append_chained_entry()` call, `False` otherwise. Also reachable through `SETTOrchestrator.verify_ethical_audit_log()`, which delegates here. Tamper-evident within the running process only: it does not constitute an external cryptographic signature or a durable attestation outside that process.

```python
filt = EthicalFilter()
filt.evaluate("some_action", {})
filt.verify_audit_log()  # True

filt.get_audit_log()[0]["verdict"] = "tampered"  # a copy: does not touch internal state
filt.verify_audit_log()  # still True

filt._audit_log[0]["verdict"] = "tampered"  # reaches the real internal log
filt.verify_audit_log()  # False
```

---

`set_ruleset(ruleset)` → `None`

Replace the active ruleset at runtime.

---

`set_context_analyzer(analyzer)` → `None`

Replace the context analyzer (e.g. to integrate with a Sentiment Analyzer agent).

---

`principle` *(property)* → `str`

The guiding ethical principle of the active ruleset.

---

### FilterVerdict

```python
class FilterVerdict(Enum):
    ALLOW  = "allow"
    WARN   = "warn"
    REJECT = "reject"
```

---

### HarmCategory

```python
class HarmCategory(Enum):
    PHYSICAL       = "physical"       # weight: 10
    PSYCHOLOGICAL  = "psychological"  # weight: 8
    ECONOMIC       = "economic"       # weight: 6
    AUTONOMY       = "autonomy"       # weight: 5
    OMISSION       = "omission"       # weight: 4
    AMBIGUITY      = "ambiguity"      # weight: 2
```

---

### EthicalRuleset

A named collection of ethical rules with configurable thresholds.

```python
EthicalRuleset(
    name,
    principle="Do not cause direct or indirect harm to human beings.",
    rules=[],
    reject_threshold=8.0,
    warn_threshold=4.0,
)
```

| Parameter | Type | Description |
|---|---|---|
| `reject_threshold` | `float` | Score at or above this → `REJECT`. |
| `warn_threshold` | `float` | Score at or above this → `WARN`. |

**Methods**

| Method | Returns | Description |
|---|---|---|
| `add_rule(rule)` | `None` | Add an `EthicalRule` to this ruleset. |
| `get_active_rules()` | `list[EthicalRule]` | Only the rules currently `active`. |
| `get_rule(name)` | `EthicalRule \| None` | Find a rule by name, or `None` if not present. |

Use `default_ruleset()` to get the pre-configured SETT default.

---

### EthicalRule

A single ethical rule within a ruleset: its harm category, weight, description, and whether it is currently active.

```python
EthicalRule(name, category, weight, description, active=True)
```

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Unique identifier within the ruleset (e.g. `"no_physical_harm"`). |
| `category` | `HarmCategory` | Which harm category this rule belongs to. |
| `weight` | `float` | Severity weight for this rule. Typically one of the `DEFAULT_HARM_WEIGHTS` values, but any positive float is valid for a custom ruleset. |
| `description` | `str` | Human-readable explanation of what the rule guards against. Surfaced in audit logs and reasoning strings. |
| `active` | `bool` | Whether this rule currently participates in evaluation. Defaults to `True`. |

**Methods**

| Method | Returns | Description |
|---|---|---|
| `activate()` | `None` | Re-enable a deactivated rule. |
| `deactivate()` | `None` | Temporarily disable this rule without removing it from the ruleset. |

```python
from sett import EthicalRule, HarmCategory

rule = EthicalRule(
    name="no_physical_harm",
    category=HarmCategory.PHYSICAL,
    weight=10.0,
    description="Action must not cause or facilitate physical harm to any person.",
)
ruleset.add_rule(rule)
```

---

### default_ruleset()

```python
from sett import default_ruleset
ruleset = default_ruleset()
```

Returns the default `EthicalRuleset` with rules covering all six `HarmCategory` values. Use this as a starting point and extend it for domain-specific deployments.

---

### ContextAnalyzer

Evaluates the context of a proposed action using the three-layer system. Subclass this and override `analyze()` to integrate with the Sentiment Analyzer agent, biometric data from wearables, or domain-specific risk logic.

```python
ContextAnalyzer()
```

**Methods**

`analyze(action, context, emotional_state="unknown", risk_profile=None, environmental_context=None)` → `ContextAnalysis`

Performs the full three-layer analysis and returns a `ContextAnalysis` with `risk_score`, `emotional_state`, `human_at_risk`, `reasoning`, `consequences`, `risk_level`, and `safety_assessment`.

---

### ContextAnalysis

Result of a full three-layer context analysis. Not a dataclass (no `@dataclass` decorator), but every field below is a plain public attribute.

| Field | Type | Description |
|---|---|---|
| `action` | `str` | The action that was analyzed. |
| `risk_score` | `float` | Combined harm score (0.0-10.0) that the `EthicalFilter` compares against its thresholds. |
| `emotional_state` | `str` | The emotional state passed in to `analyze()`. |
| `reasoning` | `str` | Human-readable explanation of how the score was reached. |
| `consequences` | `list[str]` | Possible consequences identified for this action. |
| `human_at_risk` | `bool` | Whether a human was determined to be at risk. Defaults to `False`. |
| `risk_level` | `RiskLevel \| None` | The environmental risk level in effect, if any (Layer 3). |
| `safety_assessment` | `SafetyAssessment` | Separates situation urgency from action harm (see below). If not provided, defaults to a `SafetyAssessment` derived from `risk_score` and `human_at_risk` for backward compatibility with analyzers written before v0.8.0. |

---

### SafetyAssessment

Separates the urgency of a situation from the harm of the proposed action, so that a severe human situation never automatically makes a protective response look dangerous. This is the type introduced in v0.8.0 to replace the old behavior where `human_at_risk` inflated an action's harm score directly.

```python
SafetyAssessment(
    situation_urgency=0.0,
    action_harm_risk=0.0,
    omission_risk=0.0,
    protective_action=False,
)
```

| Field | Type | Description |
|---|---|---|
| `situation_urgency` | `float` | How serious the human context is, independent of what the proposed action does. Clamped to [0.0, 10.0]. |
| `action_harm_risk` | `float` | Estimated harm caused by the proposed action itself. Clamped to [0.0, 10.0]. |
| `omission_risk` | `float` | Estimated harm caused by NOT acting. Clamped to [0.0, 10.0]. |
| `protective_action` | `bool` | Set by a domain analyzer to mark an action as intended to reduce omission risk (e.g. `emergency_call`). Explicitly protective actions are never penalized for situation urgency. |

Frozen (`@dataclass(frozen=True, slots=True)`): construct a new instance rather than mutating one in place.

The `EthicalFilter`'s verdict is still based on `ContextAnalysis.risk_score`, not directly on `SafetyAssessment`: domain analyzers decide how these dimensions should feed into that score. The one exception is the conservative fallback described in the `EthicalFilter.evaluate()` section above: if `human_at_risk=True`, `protective_action=False`, and the score-based verdict is `ALLOW`, it is promoted to `WARN`.

---

## core_ruler: Action and SETTExecutor (v0.2.0)

### Action

A proposed real-world side effect, described as data rather than code.

```python
Action(action_type, payload={}, proposed_by="unknown")
```

| Field | Type | Description |
|---|---|---|
| `action_type` | `str` | Must match a handler registered on the `SETTExecutor` (e.g. `"send_sms"`). |
| `payload` | `dict` | Data the handler needs to perform the effect. |
| `proposed_by` | `str` | Domain of the agent that proposed this action. Audit only. |

---

### SETTExecutor

The only component allowed to perform real side effects. Receives `Action`s,
evaluates them through the `EthicalFilter`, and executes the registered
handler only if approved.

```python
SETTExecutor()
```

**Methods**

| Method | Returns | Description |
|---|---|---|
| `register_handler(action_type, handler)` | `None` | Registers the function that performs a given action type. This is the only code allowed to run that side effect. |
| `submit(action, emotional_state="unknown", risk_profile=None, location_id="global")` | `Any` | Evaluates the action; if approved, calls the registered handler and returns its result. |
| `get_audit_log()` | `list[dict]` | Actions that were actually approved and executed. Rejected or unhandled actions never appear here. |
| `registered_action_types` *(property)* | `list[str]` | Action types with a handler currently registered. |

Raises `SETTEthicalFilterRejectedError` if the `EthicalFilter` blocks the
action (handler never runs), or `SETTConfigurationError` if no handler is
registered for that `action_type` (fails closed, not open).

---

### SETTAgent.submit_action(): using the Executor from an agent

```python
agent.submit_action(action_type, payload=None, risk_profile=None)
```

Describes an `Action` and submits it to the `SETTExecutor` registered with
this agent's orchestrator (via `orchestrator.register_executor(executor)`).
Requires both an `Executor` and a handler for that `action_type` to be
registered: otherwise raises `SETTConfigurationError`.

This is the structural alternative to `propose_action()`: the agent never
holds a reference to the real client (SMS provider, payment API, etc.),
so there is no "forgot to call the gate" failure mode.

```python
class NotificationAgent(SETTAgent):
    def process(self, input_data):
        return self.submit_action("send_sms", payload={"to": ..., "message": ...})
```

---

## services_llm

### LLMBase

Abstract interface that all LLM adapters must implement. Extend this class to integrate any language model.

```python
class MyAdapter(LLMBase):
    @property
    def model_name(self): return "my-model"

    def complete(self, prompt, system="", **kwargs): ...
    def chat(self, messages, system="", **kwargs): ...
```

**Abstract methods**

| Method | Description |
|---|---|
| `complete(prompt, system="", **kwargs)` → `str` | One-shot completion. No conversation history. |
| `chat(messages, system="", **kwargs)` → `str` | Multi-turn completion. `messages` is a list of `{"role": "user"\|"assistant", "content": str}`. |
| `model_name` *(property)* → `str` | The name or identifier of the underlying model. |

---

### AnthropicAdapter

LLM adapter for Anthropic's Claude models.

```python
from sett.services_llm.anthropic import AnthropicAdapter

AnthropicAdapter(api_key=None, model="claude-sonnet-4-20250514", max_tokens=1024, temperature=0.75)
```

API key is read from the `ANTHROPIC_API_KEY` environment variable if `api_key` is not provided.
Raises `SETTLLMAdapterError` if the key is missing or the API call fails.

---

### OpenAIAdapter

LLM adapter for OpenAI's GPT models.

```python
from sett.services_llm.openai import OpenAIAdapter

OpenAIAdapter(api_key=None, model="gpt-4o", max_tokens=1024, temperature=0.75)
```

API key is read from the `OPENAI_API_KEY` environment variable if `api_key` is not provided.

---

### GeminiAdapter

LLM adapter for Google's Gemini models.

```python
from sett.services_llm.gemini import GeminiAdapter

GeminiAdapter(api_key=None, model="gemini-1.5-flash", max_tokens=1024, temperature=0.75)
```

API key is read from the `GOOGLE_API_KEY` environment variable if `api_key` is not provided.

---

### OllamaAdapter

LLM adapter for locally-running models via [Ollama](https://ollama.com). No API key, no cloud, no cost: inference happens entirely on your own machine.

```python
from sett.services_llm.ollama import OllamaAdapter

OllamaAdapter(model="qwen3:1.7b", base_url="http://localhost:11434", temperature=0.75, timeout_seconds=30)
```

Unlike the other three adapters, `OllamaAdapter` requires **no extra pip install**: it talks to Ollama's local REST API using only the Python standard library. You only need Ollama itself installed and running, with the target model already pulled (`ollama pull qwen3:1.7b`).

Recommended low-resource models: `qwen3:1.7b` (lightest, ~4GB RAM) or `phi4-mini` (3.8B, MIT license, built for CPU-only machines).

Raises `SETTLLMAdapterError` if Ollama isn't reachable at `base_url`, times out, or returns an unparseable response.

---

## services_tts_stt

### TTSBase

Abstract base class for all text-to-speech adapters. Same interchangeability philosophy as `LLMBase`: an Expert or Agent that needs voice output depends on `TTSBase`, never on a specific provider's SDK.

```python
class MyTTSAdapter(TTSBase):
    @property
    def audio_format(self):
        return "mp3"

    def synthesize(self, text, **kwargs):
        return my_api.speak(text)
```

**Methods**

| Method | Returns | Description |
|---|---|---|
| `synthesize(text, **kwargs)` | `bytes` | Converts text to speech audio, encoded as `audio_format`. `**kwargs` are provider-specific (voice, language, stability, etc.). |
| `audio_format` *(property)* | `str` | The audio encoding this adapter produces (e.g. `"mp3"`, `"wav"`). |

Deliberately does not play audio, write files, or touch any UI: that is an application-layer concern. Returning raw bytes keeps the adapter a pure function, testable without a speaker, a UI, or a filesystem.

Concrete adapters (not exported from `sett` directly, install their optional dependency first):

```python
from sett.services_tts_stt.google import GoogleTTSAdapter       # pip install sett-framework[google-tts-stt]
from sett.services_tts_stt.elevenlabs import ElevenLabsTTSAdapter  # pip install sett-framework[elevenlabs]
```

Both raise `SETTServiceAdapterError` on misconfiguration or provider failure (missing credentials, network error, unsupported voice, etc.).

---

### STTBase

Abstract base class for all speech-to-text adapters. Same philosophy as `TTSBase`, mirrored for the opposite direction.

```python
class MySTTAdapter(STTBase):
    def transcribe(self, audio, **kwargs):
        return my_api.transcribe(audio)
```

**Methods**

| Method | Returns | Description |
|---|---|---|
| `transcribe(audio, **kwargs)` | `str` | Converts speech audio to text. `**kwargs` are provider-specific (language_code, etc.). Returns an empty string if nothing was recognized: adapters raise `SETTServiceAdapterError` only for actual failures (network, auth, malformed audio), never for silence. |

Deliberately does not own a microphone, a listening loop, or any concurrency guard: that orchestration belongs in the application/Expert layer that calls this adapter, not inside it (see the Concurrency section below).

```python
from sett.services_tts_stt.google import GoogleSTTAdapter  # pip install sett-framework[google-tts-stt]
```

`TTSBase` and `STTBase` are deliberately two separate interfaces, not one merged "voice" interface: a provider is free to implement only one of them.

---

## services_sentiment

### SentimentBase

Abstract base class for all sentiment/emotional-tone adapters. An Expert or Agent that needs a sentiment signal depends on `SentimentBase`, never on a specific provider's NLU API. Directly feeds the `emotional_state` parameter that `ContextAnalyzer.analyze()` has accepted since v0.1.1.

```python
class MySentimentAdapter(SentimentBase):
    def analyze(self, text, **kwargs):
        return SentimentResult(score=0.2, magnitude=0.4)
```

**Methods**

| Method | Returns | Description |
|---|---|---|
| `analyze(text, **kwargs)` | `SentimentResult` | Analyzes the sentiment of `text`. `**kwargs` are provider-specific (language, etc.). |

```python
from sett.services_sentiment.google import GoogleSentimentAdapter  # pip install sett-framework[google-sentiment]
```

Raises `SETTServiceAdapterError` on misconfiguration or provider failure.

---

### SentimentResult

Result of analyzing a piece of text for sentiment. Deliberately a raw signal, not a decision: mapping this to a categorical `emotional_state` string (`"calm"`, `"anxious"`, `"distressed"`, etc.) is application logic, the adapter only reports what it measured.

```python
SentimentResult(score, magnitude, sentences=())
```

| Field | Type | Description |
|---|---|---|
| `score` | `float` | Overall polarity: -1.0 (very negative) to 1.0 (very positive). |
| `magnitude` | `float` | Overall emotional intensity, regardless of polarity. Unbounded: 0.0 means emotionally neutral/flat text. |
| `sentences` | `tuple[SentenceSentiment, ...]` | Per-sentence breakdown. Empty by default: not every provider call requests sentence-level detail. |

Frozen dataclass. Sentence-level detail exists specifically to let an application compare document-level score against per-sentence scores: a contradiction between the two (e.g. "that's just great" scored positive overall but negative on the one sentence carrying the literal complaint) is a concrete, testable signal for sarcasm.

---

### SentenceSentiment

Sentiment for a single sentence within an analyzed text.

```python
SentenceSentiment(text, score)
```

| Field | Type | Description |
|---|---|---|
| `text` | `str` | The sentence text. |
| `score` | `float` | Polarity for this sentence only: -1.0 (very negative) to 1.0 (very positive). |

Frozen dataclass.

---

## Concurrency

SETT's core components (`UniversalMemory`, `EthicalFilter`, `SETTExecutor`, `PrivateMemory`) are not evaluated under concurrent access, with one documented exception: `UniversalMemory` holds an internal lock around its store and history so that concurrent `update()` / `read()` / `publish_environmental_context()` calls do not corrupt shared state.

Outside of that one guarantee, SETT does not currently make a thread-safety claim for the framework as a whole: no adapter, agent base class, or expert base class has been tested under concurrent access, and none advertises being safe for it. This applies to `PrivateMemory`, `EthicalFilter`'s audit log, `SETTExecutor`'s audit log, and the LLM/TTS/STT/sentiment adapters equally.

Practical implications for a deployment:

- Running multiple `SETTOrchestrator` instances in separate processes or async tasks, each with its own agents, is the supported pattern for parallelism today (this is exactly what `EnvironmentalContext` and `publish_environmental_context()` exist to coordinate across instances).
- Sharing a single `SETTAgent`, `PrivateMemory`, or `EthicalFilter` instance across multiple threads or concurrent coroutines without external synchronization is not a tested configuration.
- An STT adapter's `transcribe()` being called concurrently for overlapping audio streams is an application-layer concern: guard it in the calling Expert or Agent, not inside the adapter (this mirrors why `STTBase` deliberately does not own a listening loop or a lock itself).

This is a documentation gap being closed, not a new restriction: the underlying behavior has not changed. A future release may extend the same lock-based pattern already used by `UniversalMemory` to other shared components if a real deployment need appears.

---

## Exceptions

All SETT exceptions inherit from `SETTError`.

| Exception | Raised when |
|---|---|
| `SETTError` | Base class for all SETT exceptions. |
| `SETTEthicalFilterRejectedError` | The EthicalFilter blocks an action or memory write. Carries structured attributes (see below) in addition to the readable message. |
| `SETTEthicalFilterWarningError` | The EthicalFilter issues a warning. The action proceeds but is flagged. |
| `SETTMemoryAccessDeniedError` | An entity attempts to access memory it has no permission for (e.g. orchestrator reading `PrivateMemory`). |
| `SETTAgentNotFoundError` | The orchestrator cannot find a registered agent for the requested domain. |
| `SETTExpertNotFoundError` | An agent cannot find a registered expert by name. |
| `SETTLLMAdapterError` | An LLM adapter fails to respond or is misconfigured (missing API key, network error, etc.). |
| `SETTServiceAdapterError` | A TTS, STT, or generative AI adapter fails or is misconfigured. |
| `SETTConfigurationError` | The framework or a component is incorrectly configured before the system starts. |
| `SETTValidationError` | A data-carrying value fails its own validation (e.g. a `RiskProfile` pillar outside `[0.0, 1.0]`). Also inherits from `ValueError`, on purpose: catching either `SETTError` or `ValueError` catches this, the same pattern the standard library's `json.JSONDecodeError` uses. Not raised by `Action` or `BiometricReading`, which do not validate their fields. |

```python
from sett import SETTEthicalFilterRejectedError

try:
    orchestrator.process(input_data, domain="emergency")
except SETTEthicalFilterRejectedError as e:
    print(f"Action blocked: {e}")
```

### Structured attributes on `SETTEthicalFilterRejectedError`

`str(e)` returns the same human-readable message as always. In addition,
the data behind that message is available as real attributes: downstream
code should read these instead of parsing the message string:

| Attribute | Type | Meaning |
|---|---|---|
| `e.action` | `str \| None` | The action type that was blocked. |
| `e.score` | `float \| None` | The computed harm score, full precision (the message renders it rounded to 2 decimals). |
| `e.threshold` | `float \| None` | The effective reject threshold the score was compared against, with environmental modifiers already applied. |
| `e.principle` | `str \| None` | The ruleset principle in effect. |
| `e.reasoning` | `str \| None` | The analyzer's reasoning behind the score. |

All attributes default to `None` if the exception is constructed with only
a message, so existing raising code keeps working unchanged.

```python
try:
    executor.submit_action(proposal)
except SETTEthicalFilterRejectedError as e:
    audit_ui.show(
        action=e.action,
        score=e.score,          # a float: no string parsing
        threshold=e.threshold,
        principle=e.principle,
    )
```
