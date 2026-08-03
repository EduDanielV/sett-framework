# SETT - Conventions and invariants of the framework
*Reference for writing the arXiv paper. Status: v0.5.0 + this session's revision.*

---

## A. Architectural conventions (the heart of the paper)

**1. Structural growth rule** *(the one you remembered)*
- A **new domain** of knowledge/function → a **new agent**, registered under that domain in the orchestrator.
- A **new responsibility within an existing domain** → a **new expert** inside the agent that already owns that domain. Never a new agent for a responsibility, never an expert shared between agents.
- Corollary validated in practice: when an expert accumulates two distinct phrasing responsibilities, it splits into two focused experts (precedent: the greeting expert that mixed greeting + habit recognition was split into two `PhrasingExpert` subclasses with identical observable behavior).
- **Terminology precision note** *(found while writing the paper)*: "domain" is a term technically reserved for what an Agent owns - `SETTAgent.__init__(self, name, domain)`; `SETTExpert` has no `domain` parameter at all. When describing this rule (in the paper or in any future doc), avoid phrases like "domain-specific" for what an Expert does - use "task-specific" or equivalent, to avoid colliding with the framework's own vocabulary.

**2. Experts return; Agents publish. No exceptions.**
An expert never writes to `UniversalMemory` nor executes effects on the world on its own: it returns results to its agent, and it is the agent who publishes. This is the basis for everything passing through the filter.

**3. Ethics as an architectural layer, not a prompt.** The central thesis. No component "behaves because it was asked to": the `EthicalFilter` intercepts structurally. Every design decision is evaluated against whether it reinforces or dilutes this thesis.

**4. Actions as data (`SETTExecutor`), fail-closed.**
Effects on the world are described as `Action` objects and executed only after the filter's verdict. The expert *physically has no reference* to the real client - the guarantee is structural, not disciplinary. An `action_type` with no registered handler raises `SETTConfigurationError`: "I forgot to register the handler" never degrades into "it ran anyway."
- Two paths coexist deliberately: `propose_action()` (lightweight, low risk) and `submit_action()` (structural, critical). Neither is imposed over the other.

**5. The LLM is an engine, not architecture.**
The system works completely without an LLM. Formalized in `PhrasingExpert`: deterministic logic produces the **facts**; the (optional) LLM only **phrases** them - never invents them, never alters them, never sees raw context. In the absence or failure of the LLM: deterministic `fallback_text()`, **never raises an exception**. Subclasses implement `determine_facts()` / `build_prompt()` / `fallback_text()`; they never override `resolve()`.

**6. Dual memory with asymmetric privacy.**
`PrivateMemory` per agent, inaccessible from outside - **today a Python convention (`_` prefix), not enforced at runtime**: verified against the code, `write()`/`read()` do not validate caller identity in any way. This is an explicitly documented scope decision in the class's own docstring, not an oversight. Any text (including the paper) that describes this as an absolute isolation guarantee needs that nuance - it is exactly the kind of imprecision already corrected twice before in this project (see #16). Shared `UniversalMemory` receives **only final results**, never intermediate reasoning.

**7. `RiskProfile` never leaves the device/agent that computed it.**
No `RiskProfile` value leaks into the audit log or shared memory. Verified by a contract test.

**8. Three-layer filter, with calculation/documentation separated.**
Score = `ContextAnalyzer` (keywords + `HarmCategory` weights) modulated by `RiskProfile` and `EnvironmentalContext` (which *tightens* thresholds, never relaxes them: `effective_reject = max(1.0, reject_threshold - env_modifier)`). **`EthicalRuleset.rules` is documentation/audit - it does not feed the numeric calculation** (only `reject_threshold`, `warn_threshold`, `principle` are read).

**9. Biometric safety net as an override.** `human_at_risk` forces the score to the reject threshold regardless of keywords - the human-life layer is not configurable away.

**10. Additive extensibility, always.**
Every addition to the core must leave existing code unaware that it exists. Precedents: `register_analyzer` (a specific analyzer per action_type, generic as a fallback for everything else), structured attributes on exceptions (optional kwargs, `str(e)` intact byte for byte), automatic propagation via `_current_*` (no subclass rewrites needed).

**11. Fail-honest in scaffolding.**
What doesn't exist yet is declared, not simulated: `StubDomainAgent` returns a structured `{"status": "stub", ...}` instead of crashing or fabricating. The whole system is testable end-to-end before every real piece exists, and replacing a stub with the real piece is transparent (same domain, zero changes to the rest).

**12. Zero mandatory dependencies in the core.**
Pure Python. External services (LLM, TTS/STT) enter through interchangeable adapters. Ollama as the local default: zero cost, zero extra pip installs (only stdlib `urllib`), offline - consistent with the project's origin (assistance on modest hardware, no cloud required).

**13. Specific, structured errors.**
Its own hierarchy under `SETTError`; the developer gets descriptive errors, not generic exceptions. Since v0.5.0: exceptions carry their data as attributes (`.action`, `.score`, `.threshold`, `.principle`, `.reasoning`) - nobody parses `str(e)`.

**22. External services are not Agents or Experts - and the naming marks it.**
*(added 07/23, discussion about STT/TTS/sentiment - first application of the
pending task noted at the end of this document: cataloging in SETT itself
what today only lives documented on the companion-assistant application's side.)*

The structural growth rule (#1) governs the Agent → Expert tree: new domain
→ new agent, new responsibility within a domain → new expert. External
service adapters (`services_llm`, `services_tts_stt`, later `services_sentiment`)
are **deliberately outside that tree**, not by omission - #12 already says
so ("external services... enter through interchangeable adapters"): an
adapter has no `PrivateMemory`, is not registered in the orchestrator, does
not participate in routing, is not subject to the `EthicalFilter` - it is a
dependency an Expert calls, never a participant in the multi-agent system.
Forcing it into the `Agent(Expert1, Expert2...)` shape would be a category
error: it would give memory and a lifecycle to something that only needs to
be an interchangeable function.

The name already signals this in the existing code; this just makes it explicit:

- `<Modality>Base` - the abstract interface (`LLMBase`, `TTSBase`, `STTBase`).
- `<Provider><Modality>Adapter` - the concrete implementation
  (`GeminiAdapter`, `OllamaAdapter`, `GoogleTTSAdapter`, `ElevenLabsTTSAdapter`).
  Grouped by provider at the **file** level when they share credentials/client
  (`services_tts_stt/google.py` carries `GoogleTTSAdapter` and `GoogleSTTAdapter`), but
  each **class** implements only one interface - never a class that mixes
  `TTSBase` and `STTBase`, so as not to lose test isolation or interchangeability.
- `<Domain><Role>Agent` / `<SpecificTask>Expert` - the tree from #1
  (`IdentityAgent`, `UserExpert`, `PhrasingExpert`).
- `<Domain>ContextAnalyzer` - `ethics_ruler` analyzers
  (`EconomicContextAnalyzer`, `RelationalContextAnalyzer`).
- `SETT<Concept>Error` - the entire exception hierarchy.

The suffix, by itself, tells you what layer something is in before you open
the file: `...Adapter` is replaceable infrastructure, `...Agent`/`...Expert`
participates in orchestration and the ethical filter, `...Analyzer` scores
harm. Keeping it consistent is what gives the label its value, not decoration.

**23. "Ruler" is the highest level, not a synonym for Agent.**
*(added 07/23 - completes #22, same criterion: document what was
already practiced without being written down.)*

`core_ruler`, `ethics_ruler`, `memory_ruler`, `risk_ruler` are not four more
Agents - they are the four structural pillars that **govern** every
Agent/Expert/Adapter that exists, in SETT or in any application built on
SETT. The hierarchy of importance, from most to least fundamental:

```
*_ruler/      → the framework's constitution: what may exist and under what rules.
                No multiple instances, nothing registers here - it IS the
                structure itself. Adding a new ruler is the biggest change
                you can make to the framework (bigger than a new Agent,
                bigger than a new Adapter).
  Agent/Expert  → domain participants, governed BY the rulers (#1: new domain
                → new agent, new responsibility → new expert).
    Adapter     → interchangeable external capability, called BY an Expert (#22).
```

Practical consequence: the `Ruler` suffix is reserved for new pillars of the
framework itself - not for an application's important domain agent
(`IdentityAgent` is still an `Agent` even though it is central to the
companion-assistant application; it
does not become `IdentityRuler` just for being important). And for the same
reason a new Expert weighs less than a new Agent (#1), and a change to the
core weighs more than one to an app (#14, #15): a new `*_ruler` is a
candidate for an even stricter version of the two-instances rule than the
rest - it is only justified once it governs something that genuinely does
not fit within the four existing pillars, not before.

Note for work in progress (STT/TTS/sentiment): `ContextAnalyzer`'s own
docstring already mentions a `SentimentAnalyzerAgent` as a planned
integration - confirming that sentiment analysis enters as an **Adapter**
that a future domain **Agent** (probably first in the companion-assistant
application, see rule #14)
consumes and publishes as `emotional_state`, not as a new `*_ruler`. The day
emotional state stops being a string that different Agents decorate and
becomes a structure as central as `RiskProfile`, that is when evaluating a
new pillar would be worth it - not before.

**Update (same day):** `biometric_ruler` was in fact
already created - this does not contradict the paragraph above, it confirms
it. The difference isn't "biometrics matters more than sentiment," it's
that biometrics already had real evidence of use (#15): the documented v0.1.1
bug (flat vs. nested data) is a concrete conflict already found, not
anticipated. Sentiment, just added as an adapter in this same session, still
has no downstream consumer - it still doesn't meet the bar this same point
set. `biometric_ruler` is documented in `docs/api_reference.md` and is the
first real case of this convention applied, useful as a concrete reference
the next time a new pillar is evaluated.

---

## B. Process conventions (methodologically citable in the paper)

**14. The two-instances rule.**
Nothing enters the core until it has appeared **twice, independently, in real downstream use**. One instance = solved standalone in the app; two = a candidate for generalization, designing the API against both cases at once (they may reveal different requirements). Precedents: `PhrasingExpert` (promoted after 2 instances), `PrivateMemory` persistence (threshold met, awaiting its turn), `PhrasingExpert`'s verification hook (1 instance, on hold).

**15. Extracted from use, not speculated.**
Every change to the core is justified by a concrete conflict found while building a real application, not by anticipatory design. (v0.4.0 was the turning point: all three additions say "extracted from real usage.")

**16. Honest history.**
Corrections to the changelog/docs are recorded explicitly ("Corrected note"), never silently rewritten. Known limitations are documented as scope decisions. README claims are adjusted to match what the code actually does, not the other way around (precedent v0.2.1: "every action" → "every action submitted as an Action... and every write to universal memory"; precedent from this session: "inaccessible" → "inaccessible by convention, not runtime-enforced", see #6).

**17. Empirical verification of claims.**
Every release claim is verified by running the code (full suite, examples, diff between versions), not by reading it. Refactors are validated by identical observable behavior (precedent: byte-for-byte identical verdicts after migrating to `register_analyzer`).

**18. Verification with unanticipated language.**
Beyond running the existing suite, every delivery is tested against new
phrases, not present in any prior test or demo - the same method that
found both the vocabulary misalignment (in an early build of the
companion-assistant application: a domain expert recognized "note that"
phrasing that the intent classifier didn't) and the unbounded-substring
matching ("add it up" containing "sad," "depression" containing
"pressure"). A passing test confirms the code does what the author
anticipated; a new phrase confirms it does what a real user would
actually say. Direct material for the Evaluation section: neither of
these two findings would have surfaced by running only the existing
suite.

---

## C. Project process conventions (not going into the paper as thesis, but governing how it's built)

**19. Don't hold up what's finished because of what's undecided.**
A version that is ready and verified gets published when it's ready - never held back waiting for a future design decision, even if that decision concerns the same component. Waiting only makes sense when both parts already exist and are finished (see #21, "don't fragment"); waiting for something with no date or decision made is the same rule applied backwards. Precedent: v0.5.0 was published without waiting for `PrivateMemory` persistence (#14, threshold already met) to be resolved - they are two independent decisions, not a condition of one another.

---

## D. Repo governance conventions (not going into the paper, but governing how it's written)

**20. Public naming.** No internal project name appears in public SETT (nor in the paper, if the paper describes SETT generically): use "two independent projects built on SETT," "an early prototype application," "a companion-assistant application." A `grep` sweep happens before closing any new text.

**21. Versioning.** Additive with new public API → minor (0.x.0). Docs only → commit or patch, no new release if the package itself doesn't change. Nothing gets bumped without explicit confirmation backed by evidence in hand. Don't fragment two already-finished pieces of work into separate releases if they're going to be published at the same time (the flip side of #19: that protects against splitting up what's already ready; #19 protects against holding back what's already ready).

---

*Note: the original textual wording of rule #1 ended up written on the
companion-assistant application's side (its own reconstruction outline /
conventions doc), not in any SETT doc yet. If the paper cites it as a
principle of the framework, before publishing it also needs to be brought
into SETT's actual documentation - today it only lives on the application
side that practices it, not on the framework that supposedly defines it.
Pending task, separate from this revision: catalog every decision made
while building that application that should have a fixed, documented
place in SETT itself, not only in conversation memory.*
