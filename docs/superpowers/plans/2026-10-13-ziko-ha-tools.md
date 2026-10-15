# Ziko HA Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Native execution selected under the user's instruction to complete the work; one fresh whole-change review before delivery.

**Goal:** Add scoped, read-only HA history, statistics, logbook, traces and error tools to the existing Codex Assist.

**Architecture:** A separate custom integration contributes native tools through `llm.py` for API `assist`. Pure query/normalization logic is separate from HA registry authorization and HA 2026.10 adapters. No write actions, arbitrary SQL, arbitrary file paths or new credentials.

**Tech Stack:** Home Assistant 2026.10.0, Python >=3.14.2, probatio schemas, Recorder, native trace/logbook APIs, pytest/pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-10-13-ziko-ha-tools-design.md`

## Global Constraints

- HA Core >=2026.10.0; actual HA-supported Python >=3.14.2.
- Current Codex Assist/model/prompt/Whisper/Edge TTS remain; contribute only to `assist`.
- Household area IDs plus explicit entities; empty scope denies; optional in-scope unexposed reading; disabled entities excluded.
- Owner-bound admin authorization for diagnostic logs and detailed traces; no spoken identity authorization.
- <=5 entities/history request; <=14 days; day-sized raw queries; <=50,000 processed records; <=200 output records.
- Query conditions computed before presentation trimming; unknown/gaps and truncation must be explicit.
- Public deliverables contain no private inventory, IDs, logs, credentials or user screenshots.

## Review Focus

1. Attribute-only climate changes: return measured `current_temperature`, not the setpoint; test with actual State and dict forms.
2. Scope changes during awaits: revalidate before returning, including explicit-unexposed and admin authorization.
3. Trace/logbook related contexts can contain external entities: reject mixed traces, remove non-scoped context fields.
4. Long/high-frequency data: declared limits and uncertainty must prevent a falsely definitive last threshold match.
5. Core log text may contain credentials: fixed paths, bounded reads, secret redaction, explicit whole-system diagnostic scope.

## Task 1: Pure query contracts and normalization

Files: `custom_components/ziko_ha_tools/query.py`, `privacy.py`, `const.py`; tests `tools_tests/test_query.py`, `test_privacy.py`.

Produces: `parse_window(start, end, now, max_days)`, `normalize_state(record, attribute)`, `summarize_history(records, predicate, limit, window)`, `sanitize(value)`.

- [ ] Write tests for attribute history, exact last predicate match before trimming, timezone/naive rejection, gaps/unknown/nonfinite values, fixed limits, secret strings/keys and trace variable omission.
- [ ] Run tests before implementation; expected failing assertions/imports for missing functionality.
- [ ] Implement contracts using stdlib; preserve last_updated for attribute changes and boundary-state evidence.
- [ ] Run task tests; expected pass; commit only own files and record evidence.

## Task 2: Scope, flow and native tool contribution

Files: `scope.py`, `__init__.py`, `config_flow.py`, `llm.py`, `manifest.json`, `strings.json`, `translations/hu.json`, `translations/en.json`; tests `test_scope.py`, `test_setup.py`.

Consumes pure contracts. Produces `Scope(hass, config)`, per-call entity/automation validation, `async_require_owner(context)`, native HA integration setup and tools restricted to API `assist`.

- [ ] Test real HA State/registries: empty scope, device-area fallback, explicit IDs, exposure, disabled entries, cross-house denials, authenticated admin owner vs anonymous/user-disabled.
- [ ] Test contribution only while configured and tool schema conversion with the same probatio converter Codex Assist uses.
- [ ] Run RED, implement config/options including bulk area/entity/automation selectors and opt-in diagnostics, run GREEN and commit.

## Task 3: Recorder, statistics and activity tools

Files: `adapters.py`, `tools.py`; tests `test_history_tools.py`, `test_adapters.py`.

Produces adapter methods `history(entity_ids, start, end)`, `statistics(entity_ids, start, end, period)`, `logbook(entity_ids, start, end)` plus `ziko_ha_tools__list_sources`, `ziko_ha_tools__query_history`, `ziko_ha_tools__query_statistics`, `ziko_ha_tools__query_logbook` tool implementations.

- [ ] Tests for no implicit global queries; full search before output trimming; per-entity uncertainty; newer/older time windows; no attributes vs climate attributes; revoked scope before return; missing Recorder/logbook; schema and limits.
- [ ] Run RED; implement Recorder sessions entirely in Recorder executor; fixed keyword signatures checked against HA 2026.10; recheck scopes after await.
- [ ] Exercise at least one real SQLite-backed Recorder query and schema conversion, then task suite GREEN and commit.

## Task 4: Trace and diagnostics adapters

Files: `adapters.py`, `tools.py`, `privacy.py`; tests `test_trace_tools.py`, `test_diagnostics.py`.

Produces scoped `ziko_ha_tools__list_traces`, `ziko_ha_tools__read_trace`, `ziko_ha_tools__query_errors` with owner-gated access.

- [ ] Test actual stored trace structures, missing runs, wrong selected automations, external entity/device/area references, dynamic targets, variables containing credentials, non-owner context, authorization revoked during await.
- [ ] Test bounded structured-system-log/fixed Core-log access; missing logfile; supported-source inventory; unsupported Supervisor/OS/app logs remain explicit.
- [ ] Run RED; implement fixed native `trace.util` access and selective trace summaries; never return raw changed_variables/config; bound all output and secret masking; run GREEN and commit.

## Task 5: Packaging, review and delivery

Files: `hacs.json` or separate integration repository metadata (decide from existing repository constraints), `.github` validation workflow, `ZIKO_HA_TOOLS.md`, packaging script, installable ZIP.

- [ ] Run all new integration tests, compile, schema/config-flow checks, `git diff --check`; inspect archive member paths and absence of inventory/credentials/logs.
- [ ] One fresh reviewer checks implementation against spec and Review Focus. Fix important findings with RED→GREEN tests.
- [ ] Create a versioned ZIP and concise Hungarian installation instructions with bulk scope setup and acceptance tests.
- [ ] Preserve old app files/worktrees; publish only authorized reviewed files. Do not claim live HA installation or successful household acceptance before user's actual test.
