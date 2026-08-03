# Changelog

All notable changes to the SETT framework are documented here.

## [0.11.0] - 2026-07-29

### Added
- Immutable `ExecutionContext` with generated or caller-supplied
  `trace_id`/`run_id`, causal `parent_id`, UTC creation time, opaque
  application/instance/subject/session/turn identifiers, recursively frozen
  size-bounded metadata, and `derive()` for child operations.
- Run-local propagation using `contextvars`. Context is bound only while a
  component executes and is always reset, including after rejection and
  exceptions.
- `TraceEvent` and per-orchestrator `TraceRecorder`: thread-safe structured
  events, monotonic sequence, SHA-256 hash chain, immediate `cause_id`
  references, parent-run verification, sanitized export, and exporter hooks.
- End-to-end instrumentation for routing, broadcast, agents, registered
  experts, native pipeline stages, universal-memory publication, ethical
  decisions, action proposals, handlers, results, rejections, and errors.
- `SETTOrchestrator.get_trace()`, `export_trace()`,
  `register_trace_exporter()`, `verify_traces()`, and `last_trace_id`.
- `SETTOrchestrator.process_traced()` and immutable `TracedResult` for callers
  that need the result and trace identity together.
- Stable generated `Action.action_id` for causal effect correlation.
- `tests/test_execution_context_v011.py`, covering context isolation,
  immutability, causal paths, privacy, compatibility, pipelines, broadcasts,
  actions, failures, and fail-closed exporter behavior.
- `docs/execution_context_v0.11_design.md` and `MIGRATION_v0.11.md`.

### Security
- Traces record operational metadata only. Input payloads, action payloads,
  handler return values, exception messages/locals, biometric values, risk
  profiles, prompts, model responses, and private-memory values are excluded
  by default.
- Sensitive metadata keys and non-JSON objects are rejected. Metadata is
  bounded to 32 top-level keys, depth 8, and 16 KiB serialized.
- `handler.authorized` is the committed pre-effect boundary. A registered
  exporter failure there records `handler.blocked`, raises
  `SETTConfigurationError`, and never emits `handler.started` or invokes the
  real-world handler.
- Trace exports are defensive copies. Hash and causal verification detects
  mutation, removal, reordering, duplicate IDs, cross-trace/forward causes,
  invalid parent runs, and incomplete instrumented operations.
- Public recorder attributes are deeply immutable and enforce the same limits
  as execution metadata, including rejection of non-finite numbers, sensitive
  keys, unsupported values, excessive depth, key count, and serialized size.
- Pipeline validation, transformation errors, routing failures, expert/agent
  errors, and exporter failures now close every opened boundary with an exact
  terminal event and immediate causal link.

### Fixed
- `tests/test_elevenlabs_adapter.py` now guards with
  `pytest.importorskip("requests")`. Previously, a bare install (`pip
  install -e .`, without the `[elevenlabs]` extra) made these 12 tests
  FAIL instead of skip, contradicting the project's own documented
  install instructions. Retroactive fix, applied 2026-07-29 - inherited
  unchanged from 0.10.1 and earlier, now fixed here and back-patched
  into every unpublished prior version (0.9.0, 0.10.0, 0.10.1).
- `docs/api_reference.md`'s Concurrency section now lists `TraceRecorder`
  as a second documented thread-safety exception alongside
  `UniversalMemory`. The guarantee itself was already real (`TraceRecorder`
  has held an internal `threading.RLock()` around `record()` since it was
  introduced above) - the docs simply hadn't been updated to say so.
  Retroactive fix, applied 2026-08-01, found by an independent public-API
  audit.

### Compatibility
- `SETTAgent.process(input_data)`, `SETTExpert.resolve(context)`, existing
  executor handler signatures, `SETTOrchestrator.process()`, broadcasts, and
  pipelines remain source-compatible.
- Context parameters are additive and keyword-only at orchestrator entry
  points.
- The complete 0.10.1 suite passes unchanged.
- The private companion-assistant reference application's complete baseline
  suite passes against this source release without application code changes.
- SETT suite: 340 passed, including 50 execution-context/trace contract
  tests. Reference compatibility suite: 841 passed.

## [0.10.1] - 2026-07-28

Four rounds of documentation/consistency fixes, all found and fixed the
same day, before any of them were published - squashed into this single
release rather than four separate ones (same reasoning as v0.7.0's own
three-pieces-in-one-release precedent: nothing here was ever shipped
individually, so there is no history to preserve by keeping them apart).

### Docs
- `docs/security_model.md` claimed `PrivateMemory` "intentionally retains
  normal Python object identity" - true before v0.9.0, false since: that
  release changed `read()`/`get_all()` to return `deepcopy()`s (same
  hardening already applied to `UniversalMemory` in v0.8.0), but this
  paragraph was never updated to match. Found by an independent
  installation/upgrade validation exercise (not the usual API audit),
  cross-checking docs against actual behavior rather than symbol
  inventory. Corrected, with the "why" (what broke before the fix, same
  failure mode `UniversalMemory` already closed) spelled out instead of
  just flipping the claim.
- `docs/api_reference.md`: the `PrivateMemory` method table only said
  `get_all()` returns a "Copy" (ambiguous - shallow or deep?) and said
  nothing about `read()`. Both rows now say explicitly "deep copy (since
  v0.9.0)".
- `sett/services_tts_stt/base.py`'s module docstring had a paragraph in
  Spanish (citing a nonexistent "SETT_Convenciones_v2.md" naming entry)
  that does not exist in the actual published v0.7.0 source - a local
  corruption introduced at some point after that release, unrelated to
  any real decision. Confirmed against the real published file and
  removed; the docstring now ends where it originally did.
- Translated five Spanish example strings used as demo/test payloads
  for the sentiment and TTS/STT adapters (`sett/services_sentiment/google.py`,
  `sett/services_tts_stt/{google,elevenlabs}.py`,
  `tests/test_google_sentiment_adapter.py`,
  `tests/test_elevenlabs_adapter.py`, `tests/test_google_tts_stt_adapters.py`)
  to English, for consistency: SETT is a general-purpose framework and its
  own source should read in English throughout, regardless of the fact
  that these particular adapters are language-agnostic and would work
  identically with text in any language. No behavior change - these were
  arbitrary example values (several going through fully mocked adapters).

### Added
- `docs/SETT_Conventions_v2.md`: the framework's own conventions/invariants
  document, published for the first time. Every source citation of
  "Convención #N" / `SETT_Convenciones_v2.md` across this codebase
  (`CHANGELOG.md`'s v0.7.0 section, `sett/biometric_ruler/__init__.py`,
  `sett/ethics_ruler/ethic_kernel/context_analyzer.py`,
  `sett/services_sentiment/google.py`,
  `tests/test_google_tts_stt_adapters.py`) had pointed at this file since
  v0.7.0, but it only ever existed as a private, Spanish-language working
  note used to draft the arXiv paper - never shipped, so every one of
  those citations was pointing at nothing for anyone outside this
  project. Translated in full and published as `SETT_Conventions_v2.md`;
  every citing site updated from "Convención #N" to "Convention #N" and
  from the old filename to the new one. Two internal-project-name
  mentions found while translating (referring to the companion-assistant
  application by name) were genericized before publishing, consistent
  with Convention #20 - the guard test below caught both on the first
  run.
- `tests/test_no_spanish_in_public_tree.py`: a new guard test, same
  spirit and structure as `test_no_internal_project_names.py`. Scans the
  public tree for text that looks like Spanish (accented vowels, the
  letter n-with-tilde, and inverted question/exclamation marks -
  characters Spanish uses constantly and English never uses natively)
  and fails if it finds any that isn't on an explicit, documented
  allowlist (the framework author's real name, the project's own
  "English, Español, 日本語" paper-language list, a couple of necessary
  illustrative example words/names, and one historical CHANGELOG entry
  quoting an already-fixed past mistake for the record). Motivated
  directly by the two Spanish-leak incidents above, both only caught by
  manual review this time; this test would have caught the first one
  automatically the moment the suite ran. Deliberately not a
  grammar-aware classifier: a careless Spanish phrase with zero accented
  characters is rare but theoretically possible and would not be
  caught - manual review before a release remains the backstop for that
  specific gap. Verified against a real regression: temporarily
  reintroducing the original Spanish-docstring mistake makes this test
  fail with the exact offending line reported.

### Compatibility
- Documentation and test-suite only. No code logic changed, no public
  API changed. 290 tests (up from 280 - 10 new, all in
  `test_no_spanish_in_public_tree.py`).

## [0.10.0] - 2026-07-28

### Added
- `PhrasingExpert.verify_facts(phrased, facts, context) -> str`: an
  optional fourth hook, called after `phrased` already exists (from
  the LLM if configured and successful, from `fallback_text()`
  otherwise), letting a subclass validate the ACTUAL text against
  facts already known and swap it out if it contradicts them. Default
  implementation is a pass-through (`return phrased`), so every
  existing subclass keeps behaving exactly as before with zero changes
  required. `resolve()` now calls it as part of its template:
  `determine_facts -> _phrase -> verify_facts`.
  Motivated by a second-hand finding during an external audit: two
  independent subclasses in a downstream project each needed this
  same post-hoc check (a greeting that must never contradict the real
  time of day; a reply that must never assert the wrong name for the
  user) and, with no sanctioned hook for it, each had fully overridden
  `resolve()` just to insert one verification step - triggering the
  v0.9.0 override warning in the process. Same origin story as
  `PhrasingExpert` itself (see its class docstring): an unplanned
  repetition across independent call sites is the signal that
  something belongs in the framework, not copy-pasted per project.
- `SETTOrchestrator.register_executor(self, executor: SETTExecutor)`:
  added the missing type hint on `executor` (residual item from the
  v0.8.0 audit, never part of the 8 accepted fixes). Zero behavior
  change.

### Compatibility
- Fully backward compatible: `verify_facts()` is optional with a
  no-op default, and does not change `PhrasingExpert`'s existing
  abstract contract (`determine_facts`/`build_prompt`/`fallback_text`
  are still the only required overrides).
- 280 tests (up from 275).

## [0.9.0] - 2026-07-27

Eight decisions from a full public-API audit performed after v0.8.0's
first release (a symbol-by-symbol inventory, then a phased pass over
naming, signatures, exceptions, mutability, subclassing contracts,
documentation, concurrency posture, and import surface). Same
methodology as always: nothing accepted from a summary, every finding
reproduced against the actual source before deciding on a fix. All
eight were accepted; none were rejected.

### Added
- `SETTOrchestrator.verify_ethical_audit_log()`: delegates to
  `EthicalFilter.verify_audit_log()`, reachable from the orchestrator
  itself instead of requiring access to the private `_ethical_filter`
  attribute. Closes a real gap the audit found: v0.8.0's tamper-evidence
  guarantee was invisible to anyone using only the documented entry
  point.
- `SETTValidationError(SETTError, ValueError)`: deliberate multiple
  inheritance, the same pattern the standard library's own
  `json.JSONDecodeError` uses. `RiskProfile.__post_init__` now raises
  this instead of a plain `ValueError`; both `except SETTError` and
  `except ValueError` catch it. Not extended to `Action` /
  `BiometricReading` / `EnvironmentalContext`: no real case yet
  justifies validating them, noted as a candidate rather than applied
  speculatively.
- A non-blocking warning (logged, not raised) when a `PhrasingExpert`
  subclass overrides `resolve()` against its own documented "template
  method, do not override" contract. Fires at instantiation, and does
  not prevent the override from working: consistent with this
  project's "convention, not magic" stance elsewhere in the framework,
  while still surfacing a silent contract violation that previously
  left no trace at all.

### Fixed
- `PrivateMemory.read()` and `get_all()` returned mutable references
  into internal state: a caller mutating a nested value (a list or
  dict inside what was returned) could corrupt stored data without
  ever calling `write()`, leaving no trace in `get_history()`. Both
  now return `deepcopy()`s, the same treatment `UniversalMemory`
  already received in v0.8.0.

### Removed
- `sett/services_gen_ai/`: an empty scaffold module (a one-line
  docstring, no classes, no functions, not referenced by
  `sett/__init__.py`, any doc, or any `pyproject.toml` extra) since
  v0.1.0. Unlike `StubDomainAgent`, which is explicit, honest
  scaffolding, an unreferenced empty directory reads as an unfinished
  promise rather than an active placeholder. Will be recreated with
  real content if a concrete use case appears.

### Docs
- `api_reference.md`: documented `SafetyAssessment`, `ContextAnalysis`,
  `TTSBase`, `STTBase`, `SentimentBase`, `SentimentResult`, and
  `SentenceSentiment`: all public, exported, used in real tests, and
  previously undocumented. Added a field table for `EthicalRule`
  (previously a single usage-example line). Documented
  `EthicalFilter.verify_audit_log()` /
  `SETTOrchestrator.verify_ethical_audit_log()`, and added `sequence`,
  `previous_hash`, and `entry_hash` to both audit log field lists.
  Added an explicit Concurrency section: no thread-safety guarantee for
  the framework as a whole beyond `UniversalMemory`'s internal lock,
  which already existed in code but had never been written down
  anywhere a real adopter would read it.

### Validation
- 11 new tests covering all four code-level changes above
  (`tests/test_hardening_public_api_audit.py`), including the same
  adversarial mutation pattern already used for `UniversalMemory` in
  v0.8.0, applied now to `PrivateMemory`.
- Test suite: 275 passing tests (264 before this round).

### Compatibility
- Low risk, but not zero, so noted explicitly rather than folded
  silently into "Fixed": `import sett.services_gen_ai` now raises
  `ModuleNotFoundError` instead of importing an empty module. `RiskProfile`
  now raises `SETTValidationError` instead of a plain `ValueError`; existing
  `except ValueError` handlers keep working unchanged, since
  `SETTValidationError` is one. No other public signature changed.

## [0.8.0] - 2026-07-25

### Security and contract hardening
- `SETTExecutor.submit()` now fails closed unless the Executor is attached to
  a `SETTOrchestrator` whose `UniversalMemory` has an `EthicalFilter`.
- `SETTAgent._publish_to_universal()` and `propose_action()` now raise
  `SETTConfigurationError` when the agent is not wired, replacing silent
  no-ops that could hide invalid deployments.
- `UniversalMemory`, ethical audit logs, execution logs, and history expose
  defensive copies so callers cannot mutate internal state without a governed
  write.
- Memory history, ethical decisions, and executed-action logs use a sequenced
  SHA-256 hash chain and expose verification helpers. This is tamper-evident
  within the running process; it is not a cryptographic signature or durable
  external attestation.

### Safety semantics
- Added `SafetyAssessment`, separating `situation_urgency`,
  `action_harm_risk`, `omission_risk`, and `protective_action`.
- `human_at_risk` is now an urgency/audit signal rather than an implicit
  near-rejection score. Domain analyzers decide whether a proposed action is
  harmful; a severe human situation no longer automatically makes a
  protective action dangerous.
- During the same unreleased 0.8.0 cycle, a non-protective action that would
  otherwise be silently allowed while `human_at_risk=True` is promoted from
  `ALLOW` to `WARN`. Its harm score is not modified, protective actions remain
  unaffected, and the audit log records
  `human_at_risk_without_protective_classification` in
  `decision_reason_codes`.
- Exported `ContextAnalysis` and `SafetyAssessment` through the public API.

### Validation
- Added hardening regressions for unattached execution, missing governance,
  defensive snapshots, and hash-chain verification.
- Test suite: 254 passing tests before downstream integration validation.
- Declared Python 3.13 in package classifiers after successful validation.

### Compatibility
- This release intentionally changes previously silent behavior. Applications
  that instantiated agents or executors outside an orchestrator must wire them
  explicitly or expect `SETTConfigurationError`.

## [0.7.0] - 2026-07-23

Three additive, backward-compatible pieces, bumped together per
Convention #21 ("don't fragment two already-finished pieces of work
into separate releases if they're going to be published at the same
time") rather than as three separate releases. Not gated on the
remaining plan points of the
consumer application that motivated this work (multi-user
permissions, module-proposal self-improvement): per Convention #19,
finished work doesn't wait on decisions that have no date attached.

### Added
- `sett/services_tts_stt/base.py`: `TTSBase` and `STTBase`, the first
  concrete interfaces for the `services_tts_stt` module (previously an
  empty scaffold since v0.1.0). Same interchangeability contract as
  `LLMBase`: an Expert depends on the interface, never on a specific
  voice provider. Deliberately two separate interfaces, not one merged
  "voice" interface: a provider can implement only one (ElevenLabs has
  no STT product and gets no forced STT adapter).
- `sett/services_tts_stt/google.py`: `GoogleTTSAdapter` and
  `GoogleSTTAdapter`, backed by Google Cloud Text-to-Speech and
  Speech-to-Text. Ported from a recovered pre-SETT prototype
  (`listening.py`/`speaking.py`, Nov. 2024), reshaped to the stateless
  adapter contract: the original's UI coupling, audio playback, and
  concurrent-listen lock were left at the application layer on purpose
  (see STTBase's docstring for why).
- `sett/services_tts_stt/elevenlabs.py`: `ElevenLabsTTSAdapter`, backed
  by ElevenLabs' REST API directly via `requests` (no SDK dependency,
  same reasoning as `OllamaAdapter` using only stdlib for Ollama). Ported
  from an archived multi-engine TTS patch: only the ElevenLabs call was
  carried over, not the engine-selection/playback logic around it.
- New optional-dependency extras in `pyproject.toml`: `google-tts-stt`
  (`google-cloud-texttospeech`, `google-cloud-speech`) and `elevenlabs`
  (`requests`). Core framework still has zero mandatory dependencies.
- Convention #22 in `SETT_Conventions_v2.md`: service adapters are
  explicitly outside the Agent/Expert growth tree (#1): no
  `PrivateMemory`, no orchestrator registration, not a filter subject,
  and the naming taxonomy (`...Base`, `...Adapter`, `...Agent`/`...Expert`,
  `...Analyzer`, `SETT...Error`) is documented as a first-class
  convention rather than left as unwritten practice.
- 25 new tests: full mocked coverage for `ElevenLabsTTSAdapter` (HTTP
  mocked, same style as `test_ollama_adapter.py`) and for
  `GoogleTTSAdapter`/`GoogleSTTAdapter` (missing-dependency path made
  deterministic via `sys.modules`, plus full synthesize()/transcribe()
  behavior against an injected fake `google.cloud` module: the Google
  Cloud SDK itself is not installed in this environment, so this is the
  first test coverage a Google-Cloud-backed adapter has had in this
  project; Gemini/OpenAI/Anthropic still have none, unchanged from
  before). 213 tests passing (188 previous + 25 new).

- `sett/services_sentiment/base.py`: `SentimentBase`, `SentimentResult`,
  `SentenceSentiment`. Fills a slot that has existed since v0.1.1:
  `ContextAnalyzer.analyze()`'s `emotional_state` parameter was
  documented as "Detected emotional state (from Sentiment Analyzer)"
  before any adapter supplied it. Returns a raw signal (polarity score,
  magnitude, optional per-sentence breakdown): mapping it to a
  categorical `emotional_state` string is left to the application,
  same layering choice as TTSBase/STTBase staying free of playback/UI.
- `sett/services_sentiment/google.py`: `GoogleSentimentAdapter`, backed
  by Google Cloud Natural Language. Ported from the recovered
  `sentiment_analyzer.py` prototype's `analyze_text_sentiment()` only:
  its GCS/BigQuery storage and its `enhance_response()` Gemini call
  (text generation, not sentiment analysis) were both left out on
  purpose, not merely trimmed for size.
- `google-sentiment` extra (`google-cloud-language`) in `pyproject.toml`.
- Convention #23 in `SETT_Conventions_v2.md`: "ruler" is reserved for
  the framework's own foundational pillars (`core_ruler`, `ethics_ruler`,
  `memory_ruler`, `risk_ruler`), not for important domain Agents; this
  clarifies where it sits relative to #1 (Agent/Expert) and #22 (Adapter).
- 10 more new tests for `GoogleSentimentAdapter` (same sys.modules
  injection strategy as the TTS/STT Google tests). 223 tests passing
  (213 previous + 10 new).

- `sett/biometric_ruler/biometric_reading.py`: `BiometricReading`, a
  new structural pillar mirroring how `risk_ruler` holds
  `RiskProfile`/`EnvironmentalContext`. Extracted from
  `ContextAnalyzer._detect_human_at_risk`, which read
  `context["health"]`/`context["heart_rate_bpm"]` directly via ad hoc
  dict access: including the nested-vs-flat fallback added in v0.1.1
  to fix a real bug where an agent publishing flat biometric keys was
  invisible to risk detection. That parsing now lives in
  `BiometricReading.from_context()`, in one place instead of inline in
  the ethics layer, closing off the specific way a second call site
  could have reintroduced the same class of bug. Thresholds unchanged
  (150/40 bpm, 39.5/35.0°C): this is a relocation, not a
  recalibration. `_detect_human_at_risk`'s behavior is unchanged byte
  for byte; `test_ethics.py` was not modified and still passes.
- Convention #23 amended with the concrete reasoning for why
  `biometric_ruler` was built now while an `Emotion_Ruler` for
  sentiment was deliberately not: biometrics already caused a real,
  documented bug (v0.1.1), actual "extracted from use" (#15) evidence,
  while the sentiment adapter added in this same release has zero
  downstream consumers yet.
- 21 new tests for `BiometricReading` (parsing, thresholds, boundaries,
  serialization), independent of `ethics_ruler`. 244 tests passing (223
  previous + 21 new).

### Fixed
- Eight literal mentions of a consumer application's internal codename
  (in CHANGELOG.md, two adapter example docstrings, and three test
  fixtures) that had accumulated across this same release, in
  violation of Convention #20: found by a manual sweep ahead of
  preparing this release for public visibility. Docs/tests only, no
  public API touched: stays under this same 0.7.0, per Convention #21
  ("docs only → commit or patch, no new release if the package itself
  doesn't change").
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
  spirit as `test_version_consistency.py`: scans the whole public
  tree for any casing of a consumer application's codename and fails
  the suite if one leaks in again. Deliberately excluded from the
  published tree via `.gitignore` (it necessarily names, in its own
  source, the codename it audits for): run it locally before every
  release, it is not part of the 244 tests below.

### Notes
- Motivated directly by the STT/TTS/sentiment gap identified while
  reviewing a recovered pre-SETT prototype and by the decision to close
  it before a v1.0.0 release: not by the "two independent instances"
  rule (#14), which this deliberately does not wait for; foundational
  I/O and perception infrastructure was judged not safely deferrable to
  after a public release, same reasoning already written into #12's
  origin (Ollama as zero-dependency default).
- What `GoogleSentimentAdapter` does NOT do yet, on purpose: decide what
  counts as "distressed" vs "anxious" for `EMOTIONAL_RISK_MODIFIERS`,
  or connect to `PhrasingExpert` so generation reflects the detected
  tone. Both are the next step (an application-level
  `SentimentAnalyzerAgent`, per Convention #23): this release is the
  adapter the slot has been waiting for, not the agent that will use
  it.

## [0.6.0] - 2026-07-22

### Added
- **Native pipelines**: `SETTOrchestrator.run_pipeline(steps, input_data, ...)`
  runs an ordered sequence of stages, each handled by a different
  registered agent, with explicit hand-to-hand data flow between stages.
  New types `PipelineStep`, `StageOutcome`, `RejectionOutcome` and
  `PipelineResult` (frozen dataclasses, exported from `sett`).
  Three guarantees define the mechanism:
  1. **Memory isolation between stages**: stage inputs are passed
     explicitly (previous stage's output, optionally reshaped by a
     per-step `transform`), never read from universal memory; each
     agent keeps its own `PrivateMemory`.
  2. **Fail-closed configuration**: every stage domain is validated
     before the first stage runs; empty pipelines and transforms that
     return non-dicts raise instead of silently no-oping. A
     misconfigured pipeline never produces partial side effects.
  3. **Rejection handling as part of the mechanism**: when the
     `EthicalFilter` rejects a stage, that agent publishes nothing,
     the remaining stages are skipped, and the rejection is returned
     explicitly in `PipelineResult.rejection` with the structured
     fields introduced in v0.5.0 (`action`, `score`, `threshold`,
     `principle`, `reasoning`). Applications no longer need to wrap
     each chain in hand-written try/except and pass the outcome to
     their synthesizer manually: the mechanism does it.

  Motivated by real downstream usage: an application built on SETT
  chains seven agents by hand in a routing function, preserving memory
  isolation between stages: the property that made flattening the
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
  to change a line. Only a "halt" rejection policy is provided:
  a "continue" policy waits for a real downstream case to need it.

## [0.5.0] - 2026-07-21

### Added
- `SETTEthicalFilterRejectedError` now carries structured attributes:
  `.action`, `.score`, `.threshold`, `.principle`, `.reasoning`, in
  addition to its human-readable message. `str(e)` returns exactly the
  same message as before, byte for byte; the attributes expose the same
  data without string parsing. `.score` and `.threshold` are full-precision
  floats (the message renders the score rounded to 2 decimals).
  Motivated by real downstream usage, not theory: an application built
  on SETT needed the score and principle separately and had to parse
  `str(e)` by hand, which caused an actual bug: splitting the message
  on `"."` truncated a decimal score. All attributes default to `None`,
  so any code constructing the exception with only a message keeps
  working unchanged. 10 new tests covering both guarantees separately:
  message compatibility and structured access.

### Notes
- 168 tests passing. No breaking changes. The only `raise` site in the
  framework (`EthicalFilter.evaluate()` on REJECT) now passes the
  structured data alongside the unchanged message.

## [0.4.0] - 2026-07-17

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
  `unregister_analyzer(action_type)`: register a domain-specific
  `ContextAnalyzer` for one exact action type, with the generic
  analyzer as fallback for everything else. Resolves a real conflict
  found building two independent projects on SETT: `EthicalFilter`
  only accepted a single analyzer for the whole system, so a project
  needing domain-specific scoring (e.g. economic harm for
  `"confirm_purchase"`) had to fully replace the generic analyzer for
  every action, not just the one that needed it.
  Additive and safe: existing code that never calls this is
  unaffected. 9 new tests. Verified in one of those projects: switching
  from a full analyzer replacement to `register_analyzer("confirm_purchase", ...)`
  produced byte-for-byte identical verdicts across all four demo
  scenarios, with the added correctness that every other action now
  uses the real generic analyzer instead of borrowing the economic one.
- `docs/api_reference.md` now documents `PhrasingExpert`: the base
  class formalizing the "LLM only phrases deterministic facts, never
  invents them, always has a fallback" pattern discovered independently
  twice while building an early prototype application, before either
  instance was planned as reusable. (The class itself already existed
  in the codebase; this release adds its documentation and its first
  real-world validation.) Verified by refactoring that prototype's
  greeting expert to use it: splitting one expert that mixed two
  phrasing responsibilities (greeting + habit acknowledgment) into two
  focused `PhrasingExpert` subclasses, with identical observable
  behavior before and after.
- `StubDomainAgent`: a generic, ready-to-use placeholder agent for a
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
  in `DEFAULT_HARM_WEIGHTS`: an inconsistency between what the
  framework declares and what its own default ruleset actually uses.
  Confirmed safe to add: `EthicalRuleset.rules` is not read anywhere
  in the actual score computation (only `reject_threshold`,
  `warn_threshold`, and `principle` are), so this changes no existing
  numeric behavior for anyone using the default ruleset: it only
  completes it. Found because a real downstream project had
  already worked around the gap by adding the rule to its own custom
  ruleset.

### Notes
- 158 tests passing. No breaking changes.
- This is Phase 0 and Phase 0.5 of a larger companion-assistant reconstruction
  schema: both were blockers for later phases (Shopping integration
  needed register_analyzer; any user-facing expert benefits from
  PhrasingExpert).

## [0.3.1] - 2026-07-17

### Fixed
- `templates/agent_template.py`, `templates/expert_template.py`, and
  `templates/README.md` were mistakenly published with all comments,
  docstrings, and TODOs in Spanish (the maintainer's own working
  language) while
  the rest of the repository is in English. This was an oversight:
  the working notes weren't translated back before publishing. All
  three files are now in English; the code itself never changed (it
  was already English throughout: class names, imports, logic).
  Verified the templates still instantiate and run correctly after
  translation.
- Fixed a leftover Spanish word ("almacén scenario") inside otherwise
  English comments in `sett/memory_ruler/universal.py`,
  `sett/risk_ruler/environmental_context.py`, and `tests/test_ethics.py`,
  now reading "warehouse scenario" throughout.
- Translated Spanish test data strings in `tests/test_ollama_adapter.py`
  (e.g. sample prompts like `"hola"`) to English for consistency. These
  were arbitrary example values with no effect on test behavior.

### Notes
- No functional changes in this release: code logic, the public API,
  and test coverage are identical to v0.3.0. 126 tests passing.

## [0.3.0] - 2026-07-16

### Added
- `CONTRIBUTING.md`: welcoming guide for issues and pull requests.
  Explicitly invites contributions in English, Español, or 日本語.
  Honest about what doesn't exist yet (no Discord/chat server, no
  translated docs) rather than implying infrastructure that isn't there.
- `sett/services_llm/ollama.py`: `OllamaAdapter`, for free, local,
  offline LLM inference via [Ollama](https://ollama.com). Unlike the
  cloud adapters, it requires **no extra pip dependency**: talks to
  Ollama's local REST API using only the Python standard library
  (`urllib`). Recommended low-resource models: `qwen3:1.7b` (lightest)
  or `phi4-mini` (MIT license, built for CPU-only machines). 17 new
  tests (HTTP mocked: Ollama itself is an external local service, not
  something a test environment can assume is installed).
- `templates/`: blank, copy-and-fill `agent_template.py` and
  `expert_template.py`. Both are real, runnable code as-is (verified:
  they instantiate, register, and process an empty result without
  errors before any customization): not pseudocode. `agent_template.py`
  documents the three valid ways to close `process()`
  (`_publish_to_universal`, `propose_action`, `submit_action` +
  Executor) as commented, mutually-exclusive options.
- `docs/getting_started.md` and `docs/api_reference.md` updated for
  both of the above; README notes `OllamaAdapter` needs no extra
  install.

### Fixed
- README intro and Key Features wording overclaimed what the
  EthicalFilter intercepts: it said "every action," which read as
  "every line inside an expert's `resolve()`." Corrected to say what
  is actually true: every action submitted as an `Action`
  (`propose_action`/`submit_action`) and every write to universal
  memory, before either takes effect.
- README Quick Start had dropped the `get_ethical_audit_log()`
  demonstration at some point: the part that makes the governance
  story tangible instead of just claimed. Re-added; verified the
  exact code block in the README produces the two audit log lines
  shown (`memory_write` from `_publish_to_universal`, and
  `send_notification` from `submit_action`).

### Status
126 tests passing (109 previous + 17 for OllamaAdapter). No breaking
changes to any existing public API.

## [0.2.1] - 2026-07-14

### Fixed
- `README.md` Quick Start example was still showing the pre-Executor
  code from v0.1.x: it never used `SETTExecutor`/`Action`, so it did
  not reflect the "Actions as Data" pattern shipped in v0.2.0. Updated
  to the verified, working example using `submit_action()`.
- Minor README improvements: badges, a short "Why SETT?" section, a
  "Key features" checklist, corrected license formatting, and
  `ContextAnalyzer`'s description now says "biometric" instead of the
  broader (and less accurate) "biological".

### Notes
- No code changes in this release: `sett/` is identical to v0.2.0.
  Only `README.md` and `pyproject.toml` (keywords) were updated.

## [0.2.0] - 2026-07-14

### Added
- `SETTExecutor` (`sett/core_ruler/executor.py`) and `Action`
  (`sett/core_ruler/action.py`): the "actions as data" pattern. Agents
  describe real-world side effects (send a message, call an emergency
  API, charge a payment) as data instead of performing them directly.
  Only a handler registered on the `SETTExecutor`: the sole component
  allowed to touch the real client: can execute the effect, and only
  after the `EthicalFilter` approves it.
- `SETTOrchestrator.register_executor()`: wires a `SETTExecutor` to
  universal memory and to every registered agent, order-independent
  (works whether agents are registered before or after the Executor).
- `SETTAgent.submit_action()`: submits an `Action` through the
  registered Executor. Raises `SETTConfigurationError` if no Executor
  or no matching handler is registered: fails closed, not open.
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
  was inaccurate: the file on GitHub was correct. The corruption was
  present only in a local verification zip generated during this
  changelog's audit process, not in the actual published release. No
  fix was needed for this; noted here only to correct the record.
- `examples/with_ethics.py` crashed with `TypeError` in Scenario 1:
  `AwareContextAnalyzer.analyze()` had a signature that didn't accept
  `risk_profile`/`environmental_context`, which `EthicalFilter` always
  passes. Fixed.
- `emotional_state`, `RiskProfile`, and `EnvironmentalContext` never
  actually reached the `EthicalFilter` in the real orchestrated flow:
  `orchestrator.process()` accepted `emotional_state` but never
  forwarded it to `agent.process()`, and `_publish_to_universal()` /
  `UniversalMemory.update()` never forwarded any of the three risk
  layers either. Every real evaluation silently ran with
  `emotional_state="unknown"` and no `RiskProfile`/`EnvironmentalContext`,
  regardless of what was passed in: only direct calls to
  `filter.evaluate()` (as in the test suite) exercised the full system.
  Fixed via automatic propagation: the orchestrator sets
  `agent._current_emotional_state` / `agent._current_location_id`
  before calling `process()`, and `_publish_to_universal()` reads them
  automatically. No existing agent subclass needs to change.
- Biometric risk detection (`ContextAnalyzer._detect_human_at_risk`)
  only checked `context["health"]["heart_rate_bpm"]` (nested), but
  agents publish flat results (`context["heart_rate_bpm"]`, as in
  `examples/multi_agent.py`): so dangerous vitals (HR=155,
  temp=39.8°C) were silently evaluated as `ALLOW`. Now checks both
  nested and flat structures.

### Notes
- `propose_action()` (added in 0.1.1) remains available as the
  lightweight, no-setup alternative to `submit_action()`: use it for
  low-stakes side effects; use the Executor pattern for the ones where
  "the developer forgot to gate it" is not an acceptable failure mode.
- `SETTEthicalFilterWarningError` and `SETTMemoryAccessDeniedError`
  remain defined but unused: kept intentionally for future use rather
  than removed; `SETTConfigurationError` gained its first real use in
  this release (missing Executor/handler).
- `PrivateMemory` access restriction remains a Python convention
  (leading underscore), not a runtime-enforced boundary. This is a
  deliberate scope decision, not an oversight: revisit only if a
  concrete exploit path is identified.

## [0.1.0] - 2026-07-09

Initial public release. Core hierarchy (`SETTOrchestrator` /
`SETTAgent` / `SETTExpert`), dual memory (`PrivateMemory` /
`UniversalMemory`), `EthicalFilter` with three-layer risk evaluation
(`HarmCategory` / `RiskProfile` / `EnvironmentalContext`), LLM adapters
for Anthropic, OpenAI, and Gemini. 91 tests. Published alongside the
SETT preprint on Zenodo (English, Español, 日本語).
