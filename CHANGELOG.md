# Changelog

All notable changes to the SETT framework are documented here.

## [0.7.0] — 2026-07-23

Three additive, backward-compatible pieces, bumped together per
Convención #21 ("no fragmentar dos piezas de trabajo ya terminadas en
releases separados si van a publicarse en el mismo momento") rather
than as three separate releases. Confirmed explicitly with Dan
(2026-07-23) — not gated on the remaining plan points of the
consumer application that motivated this work (multi-user
permissions, module-proposal self-improvement): per Convención #19,
finished work doesn't wait on decisions that have no date attached.

### Added
- `sett/services_tts_stt/base.py` — `TTSBase` and `STTBase`, the first
  concrete interfaces for the `services_tts_stt` module (previously an
  empty scaffold since v0.1.0). Same interchangeability contract as
  `LLMBase`: an Expert depends on the interface, never on a specific
  voice provider. Deliberately two separate interfaces, not one merged
  "voice" interface — a provider can implement only one (ElevenLabs has
  no STT product and gets no forced STT adapter).
- `sett/services_tts_stt/google.py` — `GoogleTTSAdapter` and
  `GoogleSTTAdapter`, backed by Google Cloud Text-to-Speech and
  Speech-to-Text. Ported from a recovered pre-SETT prototype
  (`listening.py`/`speaking.py`, Nov. 2024), reshaped to the stateless
  adapter contract — the original's UI coupling, audio playback, and
  concurrent-listen lock were left at the application layer on purpose
  (see STTBase's docstring for why).
- `sett/services_tts_stt/elevenlabs.py` — `ElevenLabsTTSAdapter`, backed
  by ElevenLabs' REST API directly via `requests` (no SDK dependency,
  same reasoning as `OllamaAdapter` using only stdlib for Ollama). Ported
  from an archived multi-engine TTS patch — only the ElevenLabs call was
  carried over, not the engine-selection/playback logic around it.
- New optional-dependency extras in `pyproject.toml`: `google-tts-stt`
  (`google-cloud-texttospeech`, `google-cloud-speech`) and `elevenlabs`
  (`requests`). Core framework still has zero mandatory dependencies.
- Convención #22 in `SETT_Convenciones_v2.md`: service adapters are
  explicitly outside the Agent/Expert growth tree (#1) — no
  `PrivateMemory`, no orchestrator registration, not a filter subject —
  and the naming taxonomy (`...Base`, `...Adapter`, `...Agent`/`...Expert`,
  `...Analyzer`, `SETT...Error`) is documented as a first-class
  convention rather than left as unwritten practice.
- 25 new tests: full mocked coverage for `ElevenLabsTTSAdapter` (HTTP
  mocked, same style as `test_ollama_adapter.py`) and for
  `GoogleTTSAdapter`/`GoogleSTTAdapter` (missing-dependency path made
  deterministic via `sys.modules`, plus full synthesize()/transcribe()
  behavior against an injected fake `google.cloud` module — the Google
  Cloud SDK itself is not installed in this environment, so this is the
  first test coverage a Google-Cloud-backed adapter has had in this
  project; Gemini/OpenAI/Anthropic still have none, unchanged from
  before). 213 tests passing (188 previous + 25 new).

- `sett/services_sentiment/base.py` — `SentimentBase`, `SentimentResult`,
  `SentenceSentiment`. Fills a slot that has existed since v0.1.1:
  `ContextAnalyzer.analyze()`'s `emotional_state` parameter was
  documented as "Detected emotional state (from Sentiment Analyzer)"
  before any adapter supplied it. Returns a raw signal (polarity score,
  magnitude, optional per-sentence breakdown) — mapping it to a
  categorical `emotional_state` string is left to the application,
  same layering choice as TTSBase/STTBase staying free of playback/UI.
- `sett/services_sentiment/google.py` — `GoogleSentimentAdapter`, backed
  by Google Cloud Natural Language. Ported from the recovered
  `sentiment_analyzer.py` prototype's `analyze_text_sentiment()` only —
  its GCS/BigQuery storage and its `enhance_response()` Gemini call
  (text generation, not sentiment analysis) were both left out on
  purpose, not merely trimmed for size.
- `google-sentiment` extra (`google-cloud-language`) in `pyproject.toml`.
- Convención #23 in `SETT_Convenciones_v2.md`: "ruler" is reserved for
  the framework's own foundational pillars (`core_ruler`, `ethics_ruler`,
  `memory_ruler`, `risk_ruler`), not for important domain Agents —
  clarifies where it sits relative to #1 (Agent/Expert) and #22 (Adapter).
- 10 more new tests for `GoogleSentimentAdapter` (same sys.modules
  injection strategy as the TTS/STT Google tests). 223 tests passing
  (213 previous + 10 new).

- `sett/biometric_ruler/biometric_reading.py` — `BiometricReading`, a
  new structural pillar mirroring how `risk_ruler` holds
  `RiskProfile`/`EnvironmentalContext`. Extracted from
  `ContextAnalyzer._detect_human_at_risk`, which read
  `context["health"]`/`context["heart_rate_bpm"]` directly via ad hoc
  dict access — including the nested-vs-flat fallback added in v0.1.1
  to fix a real bug where an agent publishing flat biometric keys was
  invisible to risk detection. That parsing now lives in
  `BiometricReading.from_context()`, in one place instead of inline in
  the ethics layer, closing off the specific way a second call site
  could have reintroduced the same class of bug. Thresholds unchanged
  (150/40 bpm, 39.5/35.0°C) — this is a relocation, not a
  recalibration. `_detect_human_at_risk`'s behavior is unchanged byte
  for byte; `test_ethics.py` was not modified and still passes.
- Convención #23 amended with the concrete reasoning for why
  `biometric_ruler` was built now while an `Emotion_Ruler` for
  sentiment was deliberately not: biometrics already caused a real,
  documented bug (v0.1.1) — actual "extraído del uso" (#15) evidence —
  while the sentiment adapter added in this same release has zero
  downstream consumers yet.
- 21 new tests for `BiometricReading` (parsing, thresholds, boundaries,
  serialization), independent of `ethics_ruler`. 244 tests passing (223
  previous + 21 new).

### Fixed
- Eight literal mentions of a consumer application's internal codename
  (in CHANGELOG.md, two adapter example docstrings, and three test
  fixtures) that had accumulated across this same release, in
  violation of Convención #20 — found by a manual sweep ahead of
  preparing this release for public visibility. Docs/tests only, no
  public API touched — stays under this same 0.7.0, per Convención #21
  ("solo docs → sin release nuevo si el paquete no cambia").
- Second incident, found AFTER the fix above had already been pushed:
  a ninth mention (`services_tts_stt/elevenlabs.py`'s docstring,
  a file path containing the codename) had slipped past the new guard
  test because its `\b` (word-boundary) pattern treats underscore as a
  "word" character, so it never matched a codename directly adjacent
  to `_`. Fixed the docstring, and closed the gap in the pattern itself
  (letters-only boundary instead of `\b`) so this class of miss can't
  recur. 7 new regression tests fix both the catch (underscore/digit-
  adjacent variants) and the non-regression (no new false positives on
  unrelated words).
- `tests/test_no_internal_project_names.py`: new guard test, same
  spirit as `test_version_consistency.py` — scans the whole public
  tree for any casing of a consumer application's codename and fails
  the suite if one leaks in again. Deliberately excluded from the
  published tree via `.gitignore` (it necessarily names, in its own
  source, the codename it audits for) — run it locally before every
  release, it is not part of the 244 tests below.

### Notes
- Motivated directly by the STT/TTS/sentiment gap identified while
  reviewing a recovered pre-SETT prototype and by the decision to close
  it before a v1.0.0 release — not by the "two independent instances"
  rule (#14), which this deliberately does not wait for; foundational
  I/O and perception infrastructure was judged not safely deferrable to
  after a public release, same reasoning already written into #12's
  origin (Ollama as zero-dependency default).
- What `GoogleSentimentAdapter` does NOT do yet, on purpose: decide what
  counts as "distressed" vs "anxious" for `EMOTIONAL_RISK_MODIFIERS`,
  or connect to `PhrasingExpert` so generation reflects the detected
  tone. Both are the next step (an application-level
  `SentimentAnalyzerAgent`, per Convención #23) — this release is the
  adapter the slot has been waiting for, not the agent that will use
  it.

## [0.6.0] — 2026-07-22

### Added
- **Native pipelines**: `SETTOrchestrator.run_pipeline(steps, input_data, ...)`
  runs an ordered sequence of stages, each handled by a different
  registered agent, with explicit hand-to-hand data flow between stages.
  New types `PipelineStep`, `StageOutcome`, `RejectionOutcome` and
  `PipelineResult` (frozen dataclasses, exported from `sett`).
  Three guarantees define the mechanism:
  1. **Memory isolation between stages** — stage inputs are passed
     explicitly (previous stage's output, optionally reshaped by a
     per-step `transform`), never read from universal memory; each
     agent keeps its own `PrivateMemory`.
  2. **Fail-closed configuration** — every stage domain is validated
     before the first stage runs; empty pipelines and transforms that
     return non-dicts raise instead of silently no-oping. A
     misconfigured pipeline never produces partial side effects.
  3. **Rejection handling as part of the mechanism** — when the
     `EthicalFilter` rejects a stage, that agent publishes nothing,
     the remaining stages are skipped, and the rejection is returned
     explicitly in `PipelineResult.rejection` with the structured
     fields introduced in v0.5.0 (`action`, `score`, `threshold`,
     `principle`, `reasoning`). Applications no longer need to wrap
     each chain in hand-written try/except and pass the outcome to
     their synthesizer manually — the mechanism does it.

  Motivated by real downstream usage: an application built on SETT
  chains seven agents by hand in a routing function, preserving memory
  isolation between stages — the property that made flattening the
  chain into a single agent unacceptable. That hand-written chain was
  studied as the living specification for this API. Introducing native
  pipelines before v1.0 (rather than after) avoids conflicting with
  sequencing logic developers would otherwise write by hand against a
  stable API.

### Fixed
- Version consistency: `sett.__version__` had fallen one version behind
  `pyproject.toml` in the v0.6.0 preparation (it still reported the
  previous version). Both now read 0.6.0, and a new guard test
  (`tests/test_version_consistency.py`) asserts they always match, so
  this class of mismatch can never ship silently again.

### Notes
- 188 tests passing (19 for native pipelines, covering the three
  guarantees independently plus explicit verification that `process()`
  routing and broadcast behavior is untouched; 1 version-consistency
  guard).
- Purely additive: `process()` is unchanged; no existing code needs
  to change a line. Only a "halt" rejection policy is provided —
  a "continue" policy waits for a real downstream case to need it.

## [0.5.0] — 2026-07-21

### Added
- `SETTEthicalFilterRejectedError` now carries structured attributes —
  `.action`, `.score`, `.threshold`, `.principle`, `.reasoning` — in
  addition to its human-readable message. `str(e)` returns exactly the
  same message as before, byte for byte; the attributes expose the same
  data without string parsing. `.score` and `.threshold` are full-precision
  floats (the message renders the score rounded to 2 decimals).
  Motivated by real downstream usage, not theory: an application built
  on SETT needed the score and principle separately and had to parse
  `str(e)` by hand, which caused an actual bug — splitting the message
  on `"."` truncated a decimal score. All attributes default to `None`,
  so any code constructing the exception with only a message keeps
  working unchanged. 10 new tests covering both guarantees separately:
  message compatibility and structured access.

### Notes
- 168 tests passing. No breaking changes. The only `raise` site in the
  framework (`EthicalFilter.evaluate()` on REJECT) now passes the
  structured data alongside the unchanged message.

## [0.4.0] — 2026-07-17

### Docs (post-release correction, 2026-07-20)
- **Corrected note**: the originally published v0.4.0 entry of this
  changelog named specific private downstream projects built on SETT.
  Those references have been replaced with generic descriptions
  ("two independent projects", "an early prototype application",
  "a companion-assistant application"), in line with the repository's
  policy of not naming private projects in public documentation. The
  technical content of the entry is unchanged; noted here to keep the
  version history accurate rather than silently rewriting it.

### Added
- `EthicalFilter.register_analyzer(action_type, analyzer)` /
  `unregister_analyzer(action_type)` — register a domain-specific
  `ContextAnalyzer` for one exact action type, with the generic
  analyzer as fallback for everything else. Resolves a real conflict
  found building two independent projects on SETT: `EthicalFilter`
  only accepted a single analyzer for the whole system, so a project
  needing domain-specific scoring (e.g. economic harm for
  `"confirm_purchase"`) had to fully replace the generic analyzer for
  every action, not just the one that needed it.
  Additive and safe — existing code that never calls this is
  unaffected. 9 new tests. Verified in one of those projects: switching
  from a full analyzer replacement to `register_analyzer("confirm_purchase", ...)`
  produced byte-for-byte identical verdicts across all four demo
  scenarios, with the added correctness that every other action now
  uses the real generic analyzer instead of borrowing the economic one.
- `docs/api_reference.md` now documents `PhrasingExpert` — the base
  class formalizing the "LLM only phrases deterministic facts, never
  invents them, always has a fallback" pattern discovered independently
  twice while building an early prototype application, before either
  instance was planned as reusable. (The class itself already existed
  in the codebase; this release adds its documentation and its first
  real-world validation.) Verified by refactoring that prototype's
  greeting expert to use it — splitting one expert that mixed two
  phrasing responsibilities (greeting + habit acknowledgment) into two
  focused `PhrasingExpert` subclasses, with identical observable
  behavior before and after.
- `StubDomainAgent` — a generic, ready-to-use placeholder agent for a
  domain that isn't built yet. No subclassing needed. Register one per
  domain your router/synthesizer needs to call, so a multi-agent
  system's full flow is testable end to end before every real agent
  exists; swap in the real agent later under the same domain with no
  other change required. Extracted from a companion-assistant application built on top
  of SETT (first used to build and test a router and a multi-domain
  synthesizer before any of six domains had a real implementation).
  10 new tests, including one verifying a stub can be transparently
  replaced by a real agent under the same domain.

### Fixed
- `default_ruleset()` was missing a rule for `HarmCategory.AMBIGUITY`,
  even though the category and its weight (2.0) were already defined
  in `DEFAULT_HARM_WEIGHTS` — an inconsistency between what the
  framework declares and what its own default ruleset actually uses.
  Confirmed safe to add: `EthicalRuleset.rules` is not read anywhere
  in the actual score computation (only `reject_threshold`,
  `warn_threshold`, and `principle` are), so this changes no existing
  numeric behavior for anyone using the default ruleset — it only
  completes it. Found because a real downstream project had
  already worked around the gap by adding the rule to its own custom
  ruleset.

### Notes
- 158 tests passing. No breaking changes.
- This is Phase 0 and Phase 0.5 of a larger companion-assistant reconstruction
  schema — both were blockers for later phases (Shopping integration
  needed register_analyzer; any user-facing expert benefits from
  PhrasingExpert).

## [0.3.1] — 2026-07-17

### Fixed
- `templates/agent_template.py`, `templates/expert_template.py`, and
  `templates/README.md` were mistakenly published with all comments,
  docstrings, and TODOs in Spanish (Dan's own working language) while
  the rest of the repository is in English. This was an oversight —
  the working notes weren't translated back before publishing. All
  three files are now in English; the code itself never changed (it
  was already English throughout — class names, imports, logic).
  Verified the templates still instantiate and run correctly after
  translation.
- Fixed a leftover Spanish word ("almacén scenario") inside otherwise
  English comments in `sett/memory_ruler/universal.py`,
  `sett/risk_ruler/environmental_context.py`, and `tests/test_ethics.py`
  — now "warehouse scenario" throughout.
- Translated Spanish test data strings in `tests/test_ollama_adapter.py`
  (e.g. sample prompts like `"hola"`) to English for consistency. These
  were arbitrary example values with no effect on test behavior.

### Notes
- No functional changes in this release — code logic, the public API,
  and test coverage are identical to v0.3.0. 126 tests passing.

## [0.3.0] — 2026-07-16

### Added
- `CONTRIBUTING.md` — welcoming guide for issues and pull requests.
  Explicitly invites contributions in English, Español, or 日本語.
  Honest about what doesn't exist yet (no Discord/chat server, no
  translated docs) rather than implying infrastructure that isn't there.
- `sett/services_llm/ollama.py` — `OllamaAdapter`, for free, local,
  offline LLM inference via [Ollama](https://ollama.com). Unlike the
  cloud adapters, it requires **no extra pip dependency** — talks to
  Ollama's local REST API using only the Python standard library
  (`urllib`). Recommended low-resource models: `qwen3:1.7b` (lightest)
  or `phi4-mini` (MIT license, built for CPU-only machines). 17 new
  tests (HTTP mocked — Ollama itself is an external local service, not
  something a test environment can assume is installed).
- `templates/` — blank, copy-and-fill `agent_template.py` and
  `expert_template.py`. Both are real, runnable code as-is (verified:
  they instantiate, register, and process an empty result without
  errors before any customization) — not pseudocode. `agent_template.py`
  documents the three valid ways to close `process()`
  (`_publish_to_universal`, `propose_action`, `submit_action` +
  Executor) as commented, mutually-exclusive options.
- `docs/getting_started.md` and `docs/api_reference.md` updated for
  both of the above; README notes `OllamaAdapter` needs no extra
  install.

### Fixed
- README intro and Key Features wording overclaimed what the
  EthicalFilter intercepts — it said "every action," which read as
  "every line inside an expert's `resolve()`." Corrected to say what
  is actually true: every action submitted as an `Action`
  (`propose_action`/`submit_action`) and every write to universal
  memory, before either takes effect.
- README Quick Start had dropped the `get_ethical_audit_log()`
  demonstration at some point — the part that makes the governance
  story tangible instead of just claimed. Re-added; verified the
  exact code block in the README produces the two audit log lines
  shown (`memory_write` from `_publish_to_universal`, and
  `send_notification` from `submit_action`).

### Status
126 tests passing (109 previous + 17 for OllamaAdapter). No breaking
changes to any existing public API.

## [0.2.1] — 2026-07-14

### Fixed
- `README.md` Quick Start example was still showing the pre-Executor
  code from v0.1.x — it never used `SETTExecutor`/`Action`, so it did
  not reflect the "Actions as Data" pattern shipped in v0.2.0. Updated
  to the verified, working example using `submit_action()`.
- Minor README improvements: badges, a short "Why SETT?" section, a
  "Key features" checklist, corrected license formatting, and
  `ContextAnalyzer`'s description now says "biometric" instead of the
  broader (and less accurate) "biological".

### Notes
- No code changes in this release — `sett/` is identical to v0.2.0.
  Only `README.md` and `pyproject.toml` (keywords) were updated.

## [0.2.0] — 2026-07-14

### Added
- `SETTExecutor` (`sett/core_ruler/executor.py`) and `Action`
  (`sett/core_ruler/action.py`): the "actions as data" pattern. Agents
  describe real-world side effects (send a message, call an emergency
  API, charge a payment) as data instead of performing them directly.
  Only a handler registered on the `SETTExecutor` — the sole component
  allowed to touch the real client — can execute the effect, and only
  after the `EthicalFilter` approves it.
- `SETTOrchestrator.register_executor()`: wires a `SETTExecutor` to
  universal memory and to every registered agent, order-independent
  (works whether agents are registered before or after the Executor).
- `SETTAgent.submit_action()`: submits an `Action` through the
  registered Executor. Raises `SETTConfigurationError` if no Executor
  or no matching handler is registered — fails closed, not open.
- `examples/with_executor.py`: full demonstration of the Executor
  pattern across four scenarios (approved notification, approved
  emergency dispatch, blocked-before-execution, missing handler).
- `tests/test_executor.py`: 18 new tests covering the Executor,
  `Action`, and `submit_action()` end to end, including the privacy
  contract (RiskProfile values never leak into the audit log) and
  order-independent registration.

### Fixed (0.1.1, folded into this release)
- **Corrected note**: an earlier draft of this changelog claimed
  `sett/__init__.py` was corrupted in the published v0.1.0 package. That
  was inaccurate — the file on GitHub was correct. The corruption was
  present only in a local verification zip generated during this
  changelog's audit process, not in the actual published release. No
  fix was needed for this; noted here only to correct the record.
- `examples/with_ethics.py` crashed with `TypeError` in Scenario 1:
  `AwareContextAnalyzer.analyze()` had a signature that didn't accept
  `risk_profile`/`environmental_context`, which `EthicalFilter` always
  passes. Fixed.
- `emotional_state`, `RiskProfile`, and `EnvironmentalContext` never
  actually reached the `EthicalFilter` in the real orchestrated flow —
  `orchestrator.process()` accepted `emotional_state` but never
  forwarded it to `agent.process()`, and `_publish_to_universal()` /
  `UniversalMemory.update()` never forwarded any of the three risk
  layers either. Every real evaluation silently ran with
  `emotional_state="unknown"` and no `RiskProfile`/`EnvironmentalContext`,
  regardless of what was passed in — only direct calls to
  `filter.evaluate()` (as in the test suite) exercised the full system.
  Fixed via automatic propagation: the orchestrator sets
  `agent._current_emotional_state` / `agent._current_location_id`
  before calling `process()`, and `_publish_to_universal()` reads them
  automatically. No existing agent subclass needs to change.
- Biometric risk detection (`ContextAnalyzer._detect_human_at_risk`)
  only checked `context["health"]["heart_rate_bpm"]` (nested), but
  agents publish flat results (`context["heart_rate_bpm"]`, as in
  `examples/multi_agent.py`) — so dangerous vitals (HR=155,
  temp=39.8°C) were silently evaluated as `ALLOW`. Now checks both
  nested and flat structures.

### Notes
- `propose_action()` (added in 0.1.1) remains available as the
  lightweight, no-setup alternative to `submit_action()` — use it for
  low-stakes side effects; use the Executor pattern for the ones where
  "the developer forgot to gate it" is not an acceptable failure mode.
- `SETTEthicalFilterWarningError` and `SETTMemoryAccessDeniedError`
  remain defined but unused — kept intentionally for future use rather
  than removed; `SETTConfigurationError` gained its first real use in
  this release (missing Executor/handler).
- `PrivateMemory` access restriction remains a Python convention
  (leading underscore), not a runtime-enforced boundary. This is a
  deliberate scope decision, not an oversight — revisit only if a
  concrete exploit path is identified.

## [0.1.0] — 2026-07-09

Initial public release. Core hierarchy (`SETTOrchestrator` /
`SETTAgent` / `SETTExpert`), dual memory (`PrivateMemory` /
`UniversalMemory`), `EthicalFilter` with three-layer risk evaluation
(`HarmCategory` / `RiskProfile` / `EnvironmentalContext`), LLM adapters
for Anthropic, OpenAI, and Gemini. 91 tests. Published alongside the
SETT preprint on Zenodo (English, Español, 日本語).
