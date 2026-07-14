# SETT Framework

**Scalable Expert-based Task Topology**

A multi-agent AI development framework inspired by the
[Badger Architecture](https://arxiv.org/pdf/1912.01513) (Rosa et al., 2019).

SETT applies Badger's philosophy of coordinated expert agents at a **macro scale**:
pre-designed, domain-specialized agents working under a single orchestrator,
each maintaining independent memory, communicating only final results through
a shared universal memory layer, with an ethical governance layer intercepting
every action before execution.

> 📄 **Read the paper:**
> [English](https://doi.org/10.5281/zenodo.21287133) ·
> [Español](https://doi.org/10.5281/zenodo.21287355) ·
> [日本語](https://doi.org/10.5281/zenodo.21301700)

---

## Install

```bash
pip install sett-framework

# With LLM support
pip install sett-framework[anthropic]   # Claude
pip install sett-framework[openai]      # GPT
pip install sett-framework[all]         # All adapters
```

## Quick start

```python
from sett import SETTOrchestrator, SETTAgent, SETTExpert, EthicalFilter

# 1. Define an expert
class MyExpert(SETTExpert):
    def resolve(self, context):
        result = {"answer": f"Processed: {context.get('input')}"}
        if self._private_memory:
            self._private_memory.write("last_input", context.get("input"))
        return result

# 2. Define an agent
class MyAgent(SETTAgent):
    def __init__(self):
        super().__init__(name="MyAgent", domain="my_domain")
        self.register_expert(MyExpert(name="my_expert"))

    def process(self, input_data):
        result = self.get_expert("my_expert").resolve(input_data)
        self._publish_to_universal(result)
        return result

# 3. Build the system
orchestrator = SETTOrchestrator(ethical_filter=EthicalFilter())
orchestrator.register_agent(MyAgent())

result = orchestrator.process({"input": "hello"}, domain="my_domain")
print(result)
# {'answer': 'Processed: hello'}
```

## Core concepts

| Concept | Description |
|---|---|
| `SETTOrchestrator` | Brain of the system. Coordinates agents, manages universal memory |
| `SETTAgent` | Domain specialist composed of experts. Has its own private memory |
| `SETTExpert` | Atomic unit. Resolves one specific task |
| `UniversalMemory` | Shared state. Agents publish only final results here |
| `PrivateMemory` | Each agent's internal workspace. Not accessible from outside |
| `EthicalFilter` | Governance layer. Every action passes through it before execution |
| `ContextAnalyzer` | Evaluates the emotional and situational context of each action |

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
│  │ [private]│  │ [private]│  │    [private]      │  │
│  └────┬─────┘  └────┬─────┘  └────────┬──────────┘  │
│       │             │                 │             │
│  ┌────▼─────────────▼─────────────────▼───────────┐ │
│  │               UniversalMemory                  │ │
│  └────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

## Four principles of SETT

**1. Pre-designed experts** Experts know their domain before the system runs.
They are not trained on the fly; they are built with purpose.

**2. Independent memory per agent** Each agent has private memory invisible
to the orchestrator and other agents. Only final results are shared.

**3. Communication by events** Agents don't call each other directly.
They publish to universal memory. The orchestrator synthesizes.

**4. LLM as engine, not architecture** The language model is a tool inside
an expert, not the system itself. Swap Claude for GPT or any local model
by changing the adapter.

## Reference implementation

A full reference implementation built on SETT is currently in development.
It will be published here when ready and will demonstrate the framework
in a real-world application covering health monitoring, empathic interaction,
schedule management, and emergency response.

## License

MIT: Eduardo Daniel Viñales

Inspired by: [BADGER: Learning to (Learn [Learning Algorithms] through Multi-Agent Communication)](https://arxiv.org/pdf/1912.01513) Marek Rosa et al., GoodAI, 2019
