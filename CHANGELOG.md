# Changelog

All notable changes to the SETT framework are documented here.

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
