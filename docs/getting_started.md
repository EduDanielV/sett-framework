# Getting Started with SETT

Get a working SETT system running in under 5 minutes.

---

## Requirements

- Python 3.10 or higher
- pip

The SETT core has **zero mandatory dependencies**. LLM support is optional and installed separately.

---

## Installation

```bash
# Core framework — no LLM required
pip install sett-framework

# With Claude support (recommended)
pip install sett-framework[anthropic]

# With GPT support
pip install sett-framework[openai]

# With Gemini support
pip install sett-framework[gemini]

# All adapters at once
pip install sett-framework[all]
```

---

## Your first SETT system

Copy and run the following. No API key required for this example.

```python
from sett import SETTOrchestrator, SETTAgent, SETTExpert, EthicalFilter


# 1. Define an expert — the most atomic unit in SETT.
#    It handles exactly one task and writes results to private memory.

class GreetingExpert(SETTExpert):
    def resolve(self, context):
        name = context.get("name", "world")
        if self._private_memory:
            self._private_memory.write("last_greeted", name)
        return {"greeting": f"Hello, {name}! Welcome to SETT."}


# 2. Define an agent — a domain specialist made up of one or more experts.
#    It coordinates its experts and publishes only the final result outward.

class WelcomeAgent(SETTAgent):
    def __init__(self):
        super().__init__(name="WelcomeAgent", domain="welcome")
        self.register_expert(GreetingExpert(name="greeting"))

    def process(self, input_data):
        result = self.get_expert("greeting").resolve(input_data)
        self._publish_to_universal(result)   # passes through EthicalFilter
        return result


# 3. Build the system and run it.

orchestrator = SETTOrchestrator(ethical_filter=EthicalFilter())
orchestrator.register_agent(WelcomeAgent())

result = orchestrator.process({"name": "Dan"}, domain="welcome")
print(result["greeting"])
# Hello, Dan! Welcome to SETT.
```

---

## What just happened

The `GreetingExpert` resolved the task and wrote intermediate state to the agent's **private memory** — a workspace no other component can access.

The `WelcomeAgent` took that result and published it to **universal memory** via `_publish_to_universal()`. Before the result was committed, the `EthicalFilter` evaluated it and issued an `ALLOW` verdict.

The `SETTOrchestrator` routed your input to the right agent, applied the filter, and returned the final result.

Three levels, one clear responsibility each.

---

## Using a real LLM

To connect an expert to Claude, add an `AnthropicAdapter` and call it inside `resolve()`:

```python
import os
from sett import SETTExpert
from sett.services_llm.anthropic import AnthropicAdapter


class SmartExpert(SETTExpert):
    def __init__(self, name):
        super().__init__(name=name)
        self.llm = AnthropicAdapter(api_key=os.getenv("ANTHROPIC_API_KEY"))

    def resolve(self, context):
        question = context.get("question", "")
        answer = self.llm.complete(prompt=question, system="You are a helpful assistant.")
        if self._private_memory:
            self._private_memory.write("last_answer", answer)
        return {"answer": answer}
```

Swap `AnthropicAdapter` for `OpenAIAdapter` or `GeminiAdapter` and nothing else in your system changes. That is principle 4 of SETT in practice.

---

## Inspecting the audit log

Every decision the EthicalFilter makes is logged. You can inspect it at any time:

```python
for entry in orchestrator.get_ethical_audit_log():
    print(f"[{entry['verdict'].upper()}] {entry['action']} — score: {entry['harm_score']:.2f}")
```

---

## Next steps

| I want to… | Go to… |
|---|---|
| Understand the architecture and philosophy | [`docs/concepts.md`](concepts.md) |
| See a multi-agent system with health, schedule, and environment agents | [`examples/multi_agent.py`](../examples/multi_agent.py) |
| See the EthicalFilter in action with ALLOW / WARN / REJECT scenarios | [`examples/with_ethics.py`](../examples/with_ethics.py) |
| Look up every public class and method | [`docs/api_reference.md`](api_reference.md) |
