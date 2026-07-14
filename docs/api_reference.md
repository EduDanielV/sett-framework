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

Return the full audit log of every ethical decision made since this orchestrator was created. Each entry contains: `timestamp`, `action`, `harm_score`, `verdict`, `emotional_state`, `human_at_risk`, `env_risk_level`, `env_modifier`, `effective_reject_threshold`, `effective_warn_threshold`, `reasoning`.

---

`registered_domains` *(property)* → `list[str]`

List of all registered agent domains.

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

`process(input_data)` → `dict` *(abstract — must be implemented)*

Main processing method. Coordinate experts, use private memory for intermediate state, compose a final result, call `_publish_to_universal(result)`, and return the result.

| Parameter | Type | Description |
|---|---|---|
| `input_data` | `dict` | The data this agent needs to process. |

---

`_publish_to_universal(result)` → `None`

Publish the agent's final result to universal memory. This is the only way an agent communicates outward. The result passes through the EthicalFilter before being stored. Call this at the end of `process()`.

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

`resolve(context)` → `dict` *(abstract — must be implemented)*

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

Six-level environmental risk scale. Describes the state of the environment a user is in — not the user themselves.

```python
class RiskLevel(IntEnum):
    LEVEL_0 = 0   # Normal — baseline operation
    LEVEL_1 = 1   # Attention — anomaly detected
    LEVEL_2 = 2   # Warning — controlled threat
    LEVEL_3 = 3   # Danger — active threat, prepare for response
    LEVEL_4 = 4   # Critical — immediate action required
    LEVEL_5 = 5   # Emergency — maximum protocol
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

**Privacy contract:** `EnvironmentalContext` never contains personal identifiers, biometric values, or `RiskProfile` data. It communicates "the environment has this level" — never "this person has this profile".

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

---

`get_audit_log()` → `list[dict]`

Full audit log of every decision. Each entry includes: `timestamp`, `action`, `harm_score`, `verdict`, `emotional_state`, `human_at_risk`, `env_risk_level`, `env_modifier`, `effective_reject_threshold`, `effective_warn_threshold`, `reasoning`.

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

Use `add_rule(EthicalRule(...))` to add rules. Use `default_ruleset()` to get the pre-configured SETT default.

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

Performs the full three-layer analysis and returns a `ContextAnalysis` with `risk_score`, `emotional_state`, `human_at_risk`, `reasoning`, `consequences`, and `risk_level`.

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

## Exceptions

All SETT exceptions inherit from `SETTError`.

| Exception | Raised when |
|---|---|
| `SETTError` | Base class for all SETT exceptions. |
| `SETTEthicalFilterRejectedError` | The EthicalFilter blocks an action or memory write. Contains the harm score, threshold, and reasoning. |
| `SETTEthicalFilterWarningError` | The EthicalFilter issues a warning. The action proceeds but is flagged. |
| `SETTMemoryAccessDeniedError` | An entity attempts to access memory it has no permission for (e.g. orchestrator reading `PrivateMemory`). |
| `SETTAgentNotFoundError` | The orchestrator cannot find a registered agent for the requested domain. |
| `SETTExpertNotFoundError` | An agent cannot find a registered expert by name. |
| `SETTLLMAdapterError` | An LLM adapter fails to respond or is misconfigured (missing API key, network error, etc.). |
| `SETTServiceAdapterError` | A TTS, STT, or generative AI adapter fails or is misconfigured. |
| `SETTConfigurationError` | The framework or a component is incorrectly configured before the system starts. |

```python
from sett import SETTEthicalFilterRejectedError

try:
    orchestrator.process(input_data, domain="emergency")
except SETTEthicalFilterRejectedError as e:
    print(f"Action blocked: {e}")
```
