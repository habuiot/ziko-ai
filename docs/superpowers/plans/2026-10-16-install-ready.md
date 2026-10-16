# Ziko install-ready implementation plan

> For implementers: execute natively using executing-plans. User authorized the preceding architecture and implementation; no repeated method/permission questions. Each new behavior is tested RED then GREEN. One fresh final reviewer.

**Goal:** Tested installable Ziko update with precise state, durable memory/presets, guarded automation drafts, operator panel and install kit.

**Architecture:** Extend the existing native Assist LLM platform; shared Scope plus a per-entry runtime Store. Owner websocket UI controls privileged state transitions. Native HA automation view is the only config adapter. Ready-made voice/media components remain external with prepared profiles.

**Tech Stack:** HA 2026.10.0, Python 3.14.8, probatio, HA Store, native websocket API, plain JS custom panel, Python standard-library installer.

**Spec:** docs/superpowers/specs/2026-10-16-install-ready-design.md

## Global Constraints

- Keep public 6f9a3e8 baseline and existing read tool interfaces; no unrelated old app change.
- No public ports, credentials in package, automatic paid API, raw code/YAML tools or global exposure.
- Explicit options for memory/writes/automation drafts; final config writing only authenticated owner UI.
- Use real HA source/native contracts; local tests do not prove household deployment.

## Review Focus

- A satellite configured to act as admin is still not interactive owner approval.
- Entity rename/replacement and scope revocation during awaits cannot apply a saved preset to the wrong device.
- Write success followed by reload/storage failure must remain recoverable and never trigger an automatic duplicate.
- Native UI editing the automation concurrently must not lose any user's changes.
- A corrupt ZIP or symlinked install target cannot overwrite unrelated HA configuration.

### Task 1: Live catalogue and durable memory

Files: new catalog.py, memory.py, tools_tests/test_memory.py, test_catalog.py; update __init__.py, scope.py.
Interfaces: Catalogue.snapshot(ids)->dict; Memory.async_load(), async_put(kind,key,value,expected_version), async_get(kind,key), async_list(kind,search), async_delete(kind,key,expected_version); Scope owns runtime memory reference.
- [ ] Tests first: actual HA Store reopen, stale version, bounded records, save failure preserves previous state; sensitive attributes omitted and out-of-scope denied.
- [ ] Run focused tests and verify RED.
- [ ] Implement atomic versioned store and safe live projection.
- [ ] Run focused and existing tools suites; commit.

### Task 2: Light preset and guarded operation tools

Files: new policy.py, presets.py, assistant_tools.py, tools_tests/test_presets.py; update llm.py/tools.py/config_flow.py/translations.
Interfaces: policy.require_access(ctx,write=False); Presets.capture(entity_id,name,expected_version), restore(name,request_id); build_assistant_tools(scope,ctx).
- [ ] Tests first: full CCT/RGB+brightness capture, unavailable/missing mode, actual service state verification, scope revocation, registry identity replacement, duplicate request, write pause, anonymous unknown satellite.
- [ ] Verify RED, implement bounded services and conservative statuses, native schemas, tool hook.
- [ ] Existing read tools remain read-only. Run full tools suite; commit.

### Task 3: Structured automation editor

Files: automation_editor.py, tools_tests/test_automation_editor.py.
Interfaces: validate_spec(scope,spec)->native_config; Editor.propose(spec,id=None,expected_version=None), apply(plan_id,request), rollback(revision_id,request), enable(automation_id,request).
- [ ] Tests first: finite schema rejects templates/unknown keys/arbitrary services; household references checked; actual HA config validation; shared lock hash conflict; backups and unrelated entries; reload failure; write pause; owner HTTP request required.
- [ ] Verify RED, implement drafts/store, native view adapter with fail-closed compatibility check, bounded revisions.
- [ ] Native integration tests and full suite; commit.

### Task 4: Operator panel and optional API bridge

Files: websocket.py, frontend/ziko-panel.js, bridge.py, tools_tests/test_operator.py/test_bridge.py; update setup/config translations.
Interfaces: authenticated websocket ziko_ha_tools/status, memory, plans, apply, rollback, enable, pause; native Tool wrappers for explicit installed Voice Satellite APIs.
- [ ] Tests first: nonowner/admin denial, no model approval path, no leak after unload, no arbitrary API bridge/Assist recursion, round-trip tool schema and context.
- [ ] Verify RED; implement UI with textContent, no stored token or raw HTML, endpoint setup report; no calls that change working login/pipeline.
- [ ] Run tools suite, JS syntax check and panel contract check; commit.

### Task 5: Ready-to-install bundle and release preparation

Files: tools/install_ziko.py, tools/pack_ha_tools.py, install-kit/, tools_tests/test_installer.py; README, changelog, workflow.
- [ ] Tests first: dry-run clean install, existing config untouched, backup/rollback, corrupt archive/path traversal/symlink rejection, version check, declared asset coverage.
- [ ] Verify RED; implement local verified installer and prepared voice/media guide, prompt, native dashboard/config links.
- [ ] Run full repository suite plus HA tools, compile, JS syntax, ZIP checksum/source equality, install/rollback in temp HA config; final fresh review and corrections; produce verified bundle and GitHub update proposal.

## Execution ledger

See docs/ziko-install-progress.md. Skill workspace scripts are not exposed as executable local resources; use this committed ledger and scoped tmp directory, preserving the same task/baseline/test record. Native execution and one review are inherited from the established project workflow.
