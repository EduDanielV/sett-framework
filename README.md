# SETT Framework

**Scalable Expert-based Task Topology**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.21287133-blue)](https://doi.org/10.5281/zenodo.21287133)

SETT is a modular multi-agent AI framework built around domain-specialized
expert agents coordinated by a central orchestrator.

Inspired by the [Badger Architecture](https://arxiv.org/pdf/1912.01513)
(Rosa et al., 2019). SETT applies Badger's philosophy of coordinated expert
agents at a **macro scale**: pre-designed, domain-specialized agents working
under a single orchestrator, each maintaining independent memory,
communicating only final results through a shared universal memory layer —
with an ethical governance layer intercepting every action submitted as an
Action (via `propose_action`/`submit_action`) and every write to universal
memory, before either one takes effect.

> 📄 **Read the paper:**
> [English](https://doi.org/10.5281/zenodo.21287133) ·
> [Español](https://doi.org/10.5281/zenodo.21287355) ·
> [日本語](https://doi.org/10.5281/zenodo.21301700)

---

## Why SETT?

Unlike frameworks that treat the language model as the system itself, SETT
separates:

- **Reasoning** — pre-designed experts, one task each
- **Communication** — agents publish events, they never call each other directly
- **Memory** — private per agent, universal only for final results
- **Execution** — real-world side effects run through a single, auditable gate
- **Ethical validation** — a governance layer, not a prompt that can be skipped

This separation makes complex multi-agent systems easier to audit, extend,
and secure — instead of one large, opaque agent loop.

---

## Install

```bash
pip install sett-framework

# With LLM support
pip install sett-framework[anthropic]   # Claude
pip install sett-framework[openai]      # GPT
pip install sett-framework[all]         # All adapters
```

> 💡 Want a free, offline, local LLM instead? `OllamaAdapter` needs no
> extra `pip install` at all — just [Ollama](https://ollama.com) itself
> running on your machine. See `docs/api_reference.md`.

## Quick start

```python
from sett import SETTOrchestrator, SETTAgent, SETTExpert, EthicalFilter, SETTExecutor

# 1. Define an expert
class MyExpert(SETTExpert):
    def resolve(self, context):
        result = {"answer": f"Processed: {context.get('input')}"}
        if self._private_memory:
            self._private_memory.write("last_input", context.get("input"))
        return result

# 2. Define an agent that submits a real-world side effect as data
class MyAgent(SETTAgent):
    def __init__(self):
        super().__init__(name="MyAgent", domain="my_domain")
        self.register_expert(MyExpert(name="my_expert"))

    def process(self, input_data):
        analysis = self.get_expert("my_expert").resolve(input_data)
        self._publish_to_universal(analysis)

        # Actions as Data: describe intent, don't perform it directly.
        # The Executor is the only thing that can call the real handler,
        # and only after the EthicalFilter approves it.
        result = self.submit_action("send_notification", payload={"msg": analysis["answer"]})
        return {**analysis, **result}

# 3. Define the handler that performs the real side effect
def handle_notification(payload):
    print(f"Real-world side effect executed: {payload.get('msg')}")
    return {"delivered": True}

# 4. Build and wire the system
orchestrator = SETTOrchestrator(ethical_filter=EthicalFilter())
executor = SETTExecutor()
executor.register_handler("send_notification", handle_notification)

orchestrator.register_executor(executor)   # order-independent
orchestrator.register_agent(MyAgent())

# 5. Run — fails closed if the EthicalFilter rejects the action
result = orchestrator.process({"input": "hello"}, domain="my_domain")
print(result)
# Real-world side effect executed: Processed: hello
# {'answer': 'Processed: hello', 'delivered': True}

# 6. Every decision the EthicalFilter makes is logged — nothing happens
#    silently, whether it was allowed, warned, or rejected.
for entry in orchestrator.get_ethical_audit_log():
    print(f"[{entry['verdict'].upper()}] {entry['action']} — score: {entry['harm_score']:.2f}")
# [ALLOW] memory_write — score: 0.50
# [ALLOW] send_notification — score: 1.50
```

## Key features

- ✔ Expert-based multi-agent architecture
- ✔ Independent private memory per agent
- ✔ Universal shared memory for final results only
- ✔ Actions as Data execution model
- ✔ Ethical governance layer intercepting submitted actions and memory writes
- ✔ Fail-closed execution — no handler, no Executor, no approval → nothing runs
- ✔ Swappable LLM adapters (Claude, GPT, Gemini)

## Core concepts

| Concept | Description |
|---|---|
| `SETTOrchestrator` | Brain of the system. Coordinates agents, manages universal memory. |
| `SETTAgent` | Domain specialist composed of experts. Has its own private memory. |
| `SETTExpert` | Atomic unit. Resolves one specific task. |
| `SETTExecutor` | The only component allowed to execute real-world side effects, and only after ethical approval. |
| `Action` | A real-world side effect described as data, not code. |
| `UniversalMemory` | Shared state. Agents publish only final results here. |
| `PrivateMemory` | Each agent's internal workspace. Not accessible from outside. |
| `EthicalFilter` | Governance layer. Every action passes through it before execution. |
| `ContextAnalyzer` | Evaluates the emotional, biometric, and situational context of each action. |

## Four principles of SETT

**1. Pre-designed experts** — Experts know their domain before the system runs.
They are not trained on the fly; they are built with purpose.

**2. Independent memory per agent** — Each agent has private memory invisible
to the orchestrator and other agents. Only final results are shared.

**3. Communication by events** — Agents don't call each other directly.
They publish to universal memory. The orchestrator synthesizes.

**4. LLM as engine, not architecture** — The language model is a tool inside
an expert, not the system itself. Swap Claude for GPT or any local model
by changing the adapter.

## SETT Architecture

```
┌─────────────────────────────────────────────────────┐
│                   SETTOrchestrator                  │
│  ┌───────────────────────────────────────────────┐  │
│  │              EthicalFilter (ring)             │  │
│  └───────────────────────────────────────────────┘  │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │  Agent A │  │  Agent B │  │     Agent C       │  │
│  │ Expert 1 │  │ Expert 1 │  │    Expert 1       │  │
│  │ Expert 2 │  │ Expert 2 │  │    Expert 2       │  │
│  │[private] │  │[private] │  │   [private]       │  │
│  └────┬─────┘  └────┬─────┘  └────────┬──────────┘  │
│       │             │                 │             │
│  ┌────▼─────────────▼─────────────────▼──────────┐  │
│  │               UniversalMemory                 │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

Real-world side effects (`submit_action`) follow a separate, fail-closed path:

```
Agent ──Action──▶ EthicalFilter ──approved?──▶ SETTExecutor ──▶ real client
                       │
                       └──rejected──▶ nothing runs (fail closed)
```

## Roadmap

A full reference implementation built on SETT is currently in development.
It will be published here when ready and will demonstrate the framework
in a real-world application covering health monitoring, empathic interaction,
schedule management, and emergency response.

## Contributing

This is an independent, solo project — issues, ideas, and pull requests
are welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

MIT License

Copyright (c) 2026 Eduardo Daniel Viñales

Academic inspiration: [BADGER: Learning to (Learn [Learning Algorithms] through Multi-Agent Communication)](https://arxiv.org/pdf/1912.01513) — Marek Rosa et al., GoodAI, 2019
