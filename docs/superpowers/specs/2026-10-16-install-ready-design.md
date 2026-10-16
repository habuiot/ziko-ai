# Ziko install-ready update design

Goal: deliver a tested native HA integration update plus a single installation bundle, minimizing manual setup. The user explicitly authorized implementation and preparation of the preceding master plan; execute natively without further generic approval gates. Live credentials, physical audio tests and final household selection remain user actions.

Baseline: public main 6f9a3e8, HA Core 2026.10.0 / Python 3.14.2+. Preserve existing Codex Assist login, pipeline, voice and read tools. No paid fallback, public server, arbitrary shell/SQL, direct credential copying or automatic global entity exposure.

## Independent deliverables

1. Exact live attributes: scoped safe projections, stable registry identity, search/pagination and timestamps. Never dump arbitrary attributes, URLs or tokens.
2. Persistent household memory and light presets: private atomic HA Store per config entry, version checks, bounded text, explicit write tools, restart persistence, revision history, export/delete from authenticated operator UI. No personal-private facts on anonymous satellites. Memory is deliberately shared household data and the UI explains provider disclosure.
3. Guarded operations: config opt-in, exposed household lights by default; other actuator entities only explicit allowlist. Active owner account remains valid. Voice requests need a real household satellite device or the configured owner identity; voice never authorizes admin changes. Plan IDs are server-generated and persisted; failure/uncertainty is never reported as verified.
4. Automation editor: typed finite JSON specification, no templates/arbitrary YAML/services/events/URLs. State/numeric/time/sun triggers, bounded conditions and light/climate/media/explicit-switch actions. Only managed rules are edited; importing an existing rule requires explicit owner review. A model can propose but cannot approve or apply. Authenticated owner UI reviews concrete config, applies, enables and rolls back. Use actual HA config view's shared mutation lock and its atomic writer, schema validator and reload; if these contracts or normal automations.yaml inclusion cannot be verified, deny instead of writing another file. Check expected hash under that lock; preserve unrelated entries; persist backup before write. Reload failure stays uncertain with recovery path.
5. Operator panel: HA authenticated websocket API, admin-only actions further bound to configured owner; custom frontend panel with no secrets or raw HTML injection. Setup checks, memory/presets, pending plans, automation revisions, write pause and bundle settings export. State/control scope enforced again after awaited I/O.
6. Optional visual LLM bridge: only named weather/Wikipedia/search providers from Voice Satellite LLM Tools; no arbitrary third-party API, no recursion to Assist. Namespace wrappers and preserve tool context for visual routing. Disabled until operator selects supported installed APIs. Entity-card backend must be household-filtered or omitted. API discovery/hook/unload tested.
7. Installation bundle: exact integration code, local integrity manifest, guarded backup/staging/install/rollback helper, Hungarian quick start, updated personality prompt, no private household identifiers, satellite/media profiles and links. Never edit .storage/configuration.yaml or install unpinned downloads silently. Detect stale/duplicate copies, HA version and verify package bytes before mutation.

## Security and behavior

Model text is untrusted data. Private HTTP/websocket owner authorization is distinct from pipeline acts-as-user. Sensitive existing native tools remain unexposed; the new layer cannot claim to intercept native Assist control. All read scope, write scope, approval, storage errors and concurrent changes fail closed. A global write pause affects only Ziko additions, not HA's existing automations/native Assist tools.

Current 0.1 history tools remain intact. Supervisor/OS/add-on logs, arbitrary HA administration, Echo raw-microphone capture, custom Ziko wake-word training and hardware-dependent room arbitration cannot be claimed shipped. Prepare their documented setup/extension boundary without inventing live validation.

## Acceptance

Exact white color/brightness saved and restored after real HA Store reload; stale version rejected; write outside house/exposure rejected; retired registry identity rejected; failed service callback not a successful restore; model cannot approve automation; native config lock rejects external edits; unrelated YAML preserved; actual HA validator rejects invalid config; rollback/reload failures explicit; websocket authorization tested; ZIP corruption cannot change installed code; final HA-native suite and package checks, one fresh whole-branch reviewer.
