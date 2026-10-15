# SDD ledger — plan: docs/superpowers/plans/2026-10-13-ziko-ha-tools.md

User scope: general household history/activity/statistics/automation traces/HA errors, approved with „Csináld meg”. Native implementation with one final fresh review.

Ruling: proceed through the authorized implementation without further generic approval gates — user explicitly asked to complete the agreed work and repeatedly rejects redundant confirmations; cost if wrong: editable design/settings.

Ruling: Python >=3.14.2 is the actual HA 2026.10 package requirement — initial 3.13 summary was stale; verified by the package resolver; cost if wrong: test runtime mismatch.

Pre-flight: Task 1 query/normalization is consumed by Tasks 3–4. Scope from Task 2 is consumed by every tool and checked again after awaited reads. Adapters return raw structured data, never tool-ready unrestricted global payloads. No unresolved shared interfaces.

Baseline: worktree `ziko-ha-tools` at eb876d4. New integration is an independent subproject; old app's uncommitted changes remain in `ziko-health` and are not included here. Current external release source must be used at publication, with only explicit new integration/docs paths applied.

Task 1: complete. Tests: 11 assertions failed for missing query/privacy implementation, then 11 passed on Python 3.14.8. Commit: pure query and privacy contracts.
Task 2: pending.
Task 3: pending.
Task 4: pending.
Task 5: pending.

Task 2: complete. Real HA registry/exposure/auth tests, bulk-flow admin/empty-scope tests, schema conversion, native platform discovery and unload revocation passed.
Task 3: complete. Actual HA 2026.10 SQLite Recorder wrote attribute-only climate changes and the adapter returned both measurements; full-series predicate search, 50,000-row uncertainty, cross-house/revocation and logbook projection passed.
Task 4: complete. Actual RestoredTrace/native trace API and LogErrorHandler formats exercised; bounded fixed Core file tests, owner revalidation, missing/mixed/dynamic/device targets, variable omission and expanded credential masking passed.
Ruling: overlapping Tasks 2–4 are committed together — native platform integration tests consume the finished shared tool module; separate partial commits would not represent the tested runtime — cost if wrong: larger review unit.
Ruling: use HA-native `ziko_ha_tools__` tool names — HA 2026.10 explicitly deprecates unprefixed contributions for 2027.3 — cost if wrong: callers must rediscover tool names, no persisted user configuration depends on them.
Ruling: no early threshold-query exit — scan the requested period up to the processing cap so returned extrema/coverage are consistent; per-day reads and a 30s caller timeout apply — cost if wrong: more database work for long/high-frequency requests.
Ruling: traces with missing config, any template or mixed device membership are rejected — exact household target resolution is not provable without executing templates — cost if wrong: fewer diagnosable automations, explicitly documented.
Ruling: current diagnostics implement only structured HA errors and fixed Core log — no available authenticated Supervisor connector; unsupported OS/Supervisor/add-on sources are explicit in UI/tool docs — cost if wrong: these diagnostics need an additional future adapter, not an architectural rewrite.
Ruling: retain HA Recorder retention/exclusions — history that was never saved or already purged cannot be reconstructed — cost if wrong: old exact events may remain unavailable; use existing statistics where possible.
Task 5: in progress. Manual ZIP plus HACS metadata and CI prepared; fresh review and delivery remain.

Final review: fresh gpt-6-astra reviewer found 4 Important issues, no Critical/Minor issues. Reviewed commit 3d7ad21; package matched source. Review declined live household acceptance, provider round trip, future HA and remote HACS installation.
Final: fixed synthetic Recorder boundary timestamps — actual SQLite test_real_recorder_sqlite_reads_attribute_changes RED→GREEN; boundary kept separately with unknown measurement time, strict native API bounds overlapped by 1us; suite 52/52.
Final: fixed unresolved label/floor target verification — test_unresolved_target_forms_are_denied RED→GREEN for both forms; suite 52/52.
Final: fixed buffered trace-list scope revocation — test_trace_list_revalidates_earlier_buffered_runs_after_final_await RED→GREEN; all raw traces validated after final await; suite 52/52.
Final: fixed quoted JSON/Python credential fields — test_quoted_json_and_python_repr_secret_fields_are_masked RED→GREEN; suite 52/52.
Final: Ruling: native HA SQLite/platform/schema tests support package delivery, not a claim of live household/provider success — no authenticated live HA interface is available; first household acceptance must compare the tool with the existing HA graph — cost if wrong: installation-specific behavior may need adjustment.
Final: Ruling: HA 2026.10.0 is the verified target; later HA compatibility and actual HACS install remain unverified — minimum-version metadata and native future-compatible tool prefix are provided, but remote release/application validation requires publication/installation — cost if wrong: a future HA/HACS change could require a focused adapter/packaging update.
Final: Ruling: deliver installable ZIP and a draft GitHub PR on the current public baseline, preserving main — user authorized this extension and prior repo workflow; draft preparation is reversible and avoids overwriting the newer 0.4.0 app — cost if wrong: HACS main installation waits for PR integration.

Publication preparation: draft PR https://github.com/habuiot/ziko-ai/pull/1 applied only 32 explicit new subproject files atop public main 451bd98; existing app unchanged. First ZIP saved, then withheld from final delivery pending clean-run CI.
Additional verification found two issues: GitHub Recorder fixture waited on a conditional barrier that races an in-flight writer; replaced with unconditional native SynchronizeTask. HA frontend Config/Options flows omit context.user_id; authenticated current_request is now the owner source, with unauthenticated/non-admin HTTP identity denying fallback. Actual frontend context regression RED→GREEN; final full suite 56/56.
The CI failure was confined to fixture synchronization, not a production database query failure. No arbitrary sleeps/retries mask it.
