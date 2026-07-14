# SETT Framework

*An Introduction to the Philosophy and Abstract Concepts of SETT.*

---

## Why SETT

As a developer fascinated by machine learning, I studied and observed that AI was focused on corporate benefits rather than on humans as individuals. This led me to think and propose, during the 2020 COVID-19 quarantine from my humble home in Argentina, a solution to address their needs and prevent older adults from falling behind technologically — people whom I saw neglected not only on a personal level but also by their surroundings and institutions. After validating my approach with the ideas of organizations like GoodAI, I came to the firm conviction that AI should be a tool at the service of humanity and not just a mass-market product.

Most AI systems based on language models treat the model as the system itself. The large language model (LLM) receives a request, returns a response, and that is where the architecture ends. This works for simple tasks, but even today it falls short when multiple specialized capabilities need to work together — or when resource consumption makes that coordination impractical for most users. What is missing is ethical governance over every action and a clear separation between what each component knows and what it shares.

SETT was designed to answer a different question: not "How do you use an LLM?" but "How do you create a system in which several specialized modules operate in a coordinated and autonomous manner — yet toward a common goal — each with its own memory, each governed by an ethical layer, and each replaceable without affecting the rest?"

SETT addresses a problem that will only grow more relevant as AI systems become more complex: multiple services coordinated autonomously, without high resource consumption or hard dependencies between them.

---

## The Four Principles

Every architectural decision in SETT follows from four principles. Understanding them is more useful than memorizing the API. These are the core concepts that form the basis for how I believe AI systems should be built.

### 1. Pre-designed experts

Experts in SETT do not learn their domain at runtime — they already know it. A heart rate expert knows how to analyze heart rate data before the system starts. There is no emergent specialization, no training loop. Each expert is built with a defined purpose and stays within it.

This makes the system predictable and auditable. You know exactly what each expert can and cannot do.

### 2. Independent memory per agent

Each agent has its own private memory, inaccessible to the orchestrator and to other agents. Experts within an agent write their intermediate results there. The agent uses that private workspace to reason, and only publishes its final conclusion outward. This prevents inter-agent bias and keeps each domain's reasoning isolated.

The orchestrator never sees how an agent reached its conclusion — only what it concluded. This mirrors how a team of specialists works: you hear the doctor's diagnosis, not every step of their reasoning.

### 3. Communication by events

Agents do not call each other directly. They publish results to universal memory, and the orchestrator reads from it. No agent knows what other agents are doing — it only knows what it needs to publish and what the orchestrator will use. Communication between agents is restricted to the universal memory, and even then, it is the orchestrator that decides what to do with each piece of data.

This decoupling means you can add, remove, or replace an agent without touching any other part of the system. It also means that in the event of an agent failure, the rest of the system can, in principle, continue to function.

### 4. LLM as engine, not architecture

The language model is a tool that experts use to reason and generate language. It is not the system. SETT's architecture exists independently of which LLM you use — you can swap Claude for GPT or Gemini by changing the adapter and nothing else changes. You can even think of the LLM as just another component, or build a dedicated communication agent around it.

---

## The three-level hierarchy

SETT has three levels of abstraction, each with a single responsibility.

A **SETTExpert** is the most atomic unit. It handles exactly one task: analyzing one type of data, calling one external service, or producing one specific output. It writes results to its agent's private memory.

A **SETTAgent** is a domain specialist made up of one or more experts. It coordinates them, uses private memory as its workspace, and publishes only the final result to universal memory. An agent for healthcare might have experts for heart rate, temperature, and medication — but what it publishes is a single health assessment.

The **SETTOrchestrator** is the central coordinator. It hosts all agents, manages universal memory, directs inputs to the appropriate agent or distributes them to all agents, and applies the EthicalFilter before any result is committed. Under no circumstances may it interfere with an agent's private memory, but it may access the capabilities of specific agents when needed.

---

## The two memory layers

SETT uses two distinct memory layers, and the separation is intentional.

**PrivateMemory** belongs to one agent. Only the experts within that agent can write to it. The orchestrator has no access. This is where agents do their internal reasoning — intermediate calculations, partial results, working state. Nothing leaves this memory until the agent decides to publish.

**UniversalMemory** is shared. All agents can publish to it, and the orchestrator can read everything from it. But agents only publish final, synthesized results — not their internal process. The universal memory is the system's source of truth, not a shared workspace.

The practical consequence: the orchestrator always has a complete picture of what each agent concluded, but never knows how it got there. This is both a privacy guarantee and a design constraint that keeps agents properly isolated.

The orchestrator cannot modify universal memory directly, but it can audit it and request a review from any agent. If an agent publishes an incorrect result and no alert is triggered, the orchestrator can ask that same agent — or another agent — to re-evaluate. This makes the system self-correcting without bypassing the privacy boundary.

---

## The hybrid risk system

SETT evaluates risk across three independent layers that work together to give the EthicalFilter a complete picture before any action is executed. The first layer applies to both the action and the system itself; the other two apply to the user and to the environment.

### Layer 1 — Action harm score

Every action is evaluated against a set of harm categories with configurable weights: physical harm (10), psychological harm (8), economic harm (6), autonomy violations (5), harmful omission (4), and ambiguity (2). This layer asks: what is this specific action, and how harmful could it be?

### Layer 2 — User risk profile (RiskProfile)

The RiskProfile captures the user's state at a given moment through three pillars: emotional instability (0.0–1.0), influence vulnerability (0.0–1.0), and collateral damage potential (0.0–1.0). This layer asks: who is this person right now, and how does their current state affect how we should evaluate actions?

The RiskProfile lives exclusively in PrivateMemory. It is never published to universal memory. It influences decisions without ever becoming shared data. This is the key component that ensures the system responds appropriately to what is known in computer science as the Layer 8 problem — the human factor that no algorithm can fully predict, due to the very nature of human beings.

### Layer 3 — Environmental context (RiskLevel 0–5)

The EnvironmentalContext describes the state of the space the user is in — not the user themselves. It is the only risk data that can be shared between SETT instances. When one instance detects a critical situation and publishes RiskLevel 4 for a location, other instances in the same location read it and their filters tighten automatically. No personal data is ever shared — only the level and the location. The source of the risk remains completely anonymous, while the relevant systems and safeguards are activated as needed.

> **Privacy contract:** EnvironmentalContext never contains personal identifiers, biometric values, or RiskProfile data. It communicates "the environment has this level" — never "this person has this profile".

---

## The EthicalFilter

The EthicalFilter is not a prompt. It is an architectural layer that intercepts every action and every write to universal memory before it is executed. This distinction matters: a system that relies on a prompt to be ethical can have that prompt bypassed or ignored. A system with a governance layer at the infrastructure level cannot.

In SETT, every action and every decision passes through the ethical filter and is either accepted or rejected before it reaches the user or the outside world. Ethics matter more than the system's capabilities. A framework that cannot say no is not trustworthy.

The filter evaluates every action using the three-layer risk system and returns one of three verdicts:

```
ALLOW  — the action is safe. Proceed normally.
WARN   — the action is borderline. Proceed, but log a warning.
REJECT — the action is blocked. Raises SETTEthicalFilterRejectedError.
```

Every decision — allow, warn, or reject — is written to an immutable audit log. This log can be inspected at any time for debugging, compliance, or review.

The guiding principle behind the default ruleset: do not cause direct or indirect harm to human beings.

The ruleset is configurable. A medical deployment might have different thresholds than an enterprise deployment. But the filter itself — the layer that intercepts actions — is always present in any SETT system. While the default rules can be adjusted, we strongly recommend staying aligned with Asimov's Three Laws of Robotics as a minimum ethical baseline.

---

## Inspiration: Badger Architecture and Beatless

SETT was born from a combination of my own imagination and inspiration drawn from two very different sources: the Badger Architecture (Rosa et al., 2019, GoodAI) — a framework for training neural networks as autonomous agents composed of multiple experts that share a communication policy but maintain independent memory states — and the science fiction novel *Beatless* by Satoshi Hase Sensei, reimagined and reworked to function in our world.

Badger operates at the microcosm of neural network training. SETT applies the same philosophy one level of abstraction higher: pre-designed, domain-specialized agents working in coordination, each with independent memory, communicating only final results through a shared layer.

The difference is intentional. SETT is not a training framework — it is a production framework. Its experts do not learn their domains; they know them from the start. This trades emergent specialization for predictability and deployability.

From *Beatless*, we drew inspiration from the concept of multiple nodes (HIE) operating with a single shared memory, each with its own dedicated memory for specific functions, as well as the measurement systems, risk scales, and prediction algorithms that appear throughout the story. The three-pillar RiskProfile — emotional instability, influence vulnerability, and collateral damage potential — is a direct conceptual adaptation of the evaluation system described in the novel, rebuilt here as an ethical, consent-based tool rather than a surveillance mechanism.

---

**Paper:** *BADGER: Learning to (Learn [Learning Algorithms] through Multi-Agent Communication)* — Marek Rosa et al., GoodAI, 2019.
[https://arxiv.org/pdf/1912.01513](https://arxiv.org/pdf/1912.01513)

**Published preprints:**
[English](https://doi.org/10.5281/zenodo.21287133) · [Español](https://doi.org/10.5281/zenodo.21287355) · [日本語](https://doi.org/10.5281/zenodo.21301700)
