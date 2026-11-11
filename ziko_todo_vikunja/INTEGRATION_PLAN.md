# Ziko™ ● Todo — Full integration blueprint
Date: 2026-11-11
Backend: official Vikunja 2.8.0, self-hosted as Home Assistant app `29b31cdc_ziko_todo_vikunja`.

## Verified deployment
- HTTP web UI: `http://homeassistant.local:3456/` (trusted LAN only).
- `GET /api/v1/info` and `GET /api/v2/info`: 200, version `v2.8.0`.
- HA sidebar: `/ziko-todo/attekintes`, with shortcut to full Vikunja.
- Existing HA native todo entities remain intact: `todo.zikotodo_ai_feladatok`, `todo.zikotodo_emberi_feladatok`.
- Host app boot=manual, watchdog=false, isolated /data, no /config mount or host networking.

## Required owner identity
1. One trusted person completes Vikunja's first signup using their own email and strong secret.
2. Disable `enable_registration` in the app options immediately after, then restart only this app.
3. Invite additional coworkers by individual account, project membership or teams; never share owner credentials.
4. Enable TOTP 2FA, configure HTTPS for remote access, and SMTP if password reset / email reminders are required.

## Project model
Vikunja is *not limited to two users*.
- `ZIKO Technology`: brand, legal, operations.
- `Házikó`: HA, Atlasz, automations, repairs.
- `Ziko Mobil`: Android / Kotlin.
- `ZikoTodo`: product development, integrations.
- Further projects created as needed without assuming a module exists.
- Teams for real human colleagues and partners. Roles follow least privilege.
- Bot identity `ziko-ai` as separately managed bot user with restricted token.
- Labels: `ai`, `emberi`, `kozos`, `jovahagyas`, `blokkolt`, `teszteles`.

## Workflow contract
Suggested stages: `Beérkezett` -> `Besorolva` -> `Folyamatban` -> `Ellenőrzés` -> `Kész`; `Blokkolt` is an exceptional state.
- Every task: project, assignees, priority, due date, status, provenance.
- AI can classify and propose; it must not claim autonomous execution merely because it is assigned.
- Hardware changes, access changes, security, external publishing, purchases, deletes and production deployments require explicit human approval.
- Maintain append-only progress notes and links to commits/tests for work evidence.

## API and MCP
- REST API v2 supports CRUD, memberships, labels, projects etc. OAuth/token provisioning by owner first.
- Built-in MCP: `/api/v2/mcp` supports bearer tokens; official Vikunja documentation states direct ChatGPT MCP is currently unsupported because OAuth is missing.
- An **OAuth-capable, authenticated connector/gateway** is the path to direct full ChatGPT access. Its public endpoint must be HTTPS, authenticate each caller, safeguard its scoped Vikunja token, and never expose Tailscale or HA credentials in frontend code.
- Alternative narrower path: Vikunja HA integration exposes per-project `todo` entities, callable through existing HA MCP; advanced team/permission operations still require the full gateway.
- Agent background execution requires an explicitly configured scheduler/event trigger and tool permissions. A chat session is not a perpetual daemon.

## Migration (one-way, non-destructive)
Current HA lists contain 7 tasks. Once owner API token exists:
1. Read tasks from both native lists, preserving UID, title, description, due/status.
2. Create/update projects and tasks in Vikunja with an idempotent import key in metadata/description.
3. Compare source/destination counts and statuses.
4. Keep original HA lists until accepted; only then decide which remains source of truth.

## Test matrix
- Health, login/signup and registration closure.
- Permissions (user, team, bot) and denial cases.
- Project sharing, assignment, Kanban, list/table/Gantt, dates, recurrence, comments, attachments, CalDAV, webhooks.
- REST CRUD (read, create, update, delete with safe test data).
- MCP token limited to test project.
- Backup/restore `/data` and service-secret, after confirming consistent SQLite snapshot.
- Resource consumption and watchdog kept off until stable.
- HTTPS/Tailscale external security before remote invitations.

## Licenses
Vikunja AGPL-3.0-or-later; no license key required for core self-hosted app. Pro-exclusive features are not included unless legitimately licensed. Keep notices and source obligations for modified AGPL distribution/network use.

## Current status
Installed and API smoke-tested; no owner account, scoped token, authenticated ChatGPT connector, task import or end-to-end AI execution yet.

## Product decision 2026-11-11: no separate Vikunja login for end users

The user explicitly rejected having to register a second account in Vikunja. The official product user interface is **Ziko™ ● Todo** inside the Home Assistant UI. Vikunja is the **internal task engine**, never the public identity system or required login interface.

### Zero-extra-login implementation architecture

- Make a **separate ingress-enabled ZIKO frontend/gateway app**. Do **not** blindly expose the raw Vikunja user interface through Ingress: Vikunja still requires its own login, and Ingress alone does not create a Vikunja session.
- Use Home Assistant Supervisor Ingress as the **only browser entry point**: authentication is performed by HA. Supervisor injects sanitized `X-Remote-User-Id` / `X-Remote-User-Name` headers to apps. Accept these headers only from Supervisor proxy 172.30.32.2; reject missing user ID and all direct/forged header requests. No public unauthenticated 3456 port on the finished architecture.
- Maintain access policies mapping Home Assistant user IDs to ZikoTodo project memberships/roles. Provide invite / assign / revoke functionality for other people; never collapse all human users into one backend user. Audit actor and operation.
- The internal Vikunja service identity and per-user task identities (if needed for Vikunja's assignee model) are provisioned **server-side**. No user manually enters a Vikunja email/password. Credentials and API tokens are stored only in the gateway secret store; use short-lived scoped tokens and rotate them.
- Use native HA sidebar as entry, and later implement visually branded Kanban, Gantt, list, table, files, comments, reminders and team management through the Vikunja REST API.
- AI identity is distinct from human users and only has narrow project permissions. ChatGPT requires its own authenticated integration; never embed bot API tokens in Javascript, HTML, a dashboard or an LLM prompt.
- The old Home Assistant `todo.zikotodo_ai_feladatok` and `todo.zikotodo_emberi_feladatok` entities remain until an idempotent, fully verified import has completed.
- Preserve AGPL-3.0 licensing for the Vikunja server (self-hosting allowed; source obligations apply when legally triggered). ZIKO gateway/front-end source-licensing decisions should be reviewed separately.

### Security issue fixed now

The native app initially enabled unauthenticated signups for first-admin creation. A bug in startup shell `jq -r '.enable_registration // true'` treated the boolean `false` as missing. Fixed to `jq -r 'if has("enable_registration") then .enable_registration else true end'`, shipped ZIKO wrapper `2.8.0-2`; HA and Vikunja `GET /api/v2/info` both report `registration_enabled: false` after update.

### Acceptance tests before switching to the new system

1. One existing HA user opens the integrated panel without entering any additional password, and the server identifies the actual HA user by a trusted ingress header.
2. A different HA user cannot read or change the first user's private tasks unless explicitly shared.
3. A project owner can add human participants, assign and revoke access, and changes are enforced server-side.
4. The AI bot operates on a limited test project; unauthorized mutations are rejected; every action records a trace.
5. No raw Vikunja port is internet-accessible, and direct access to the integration gateway with forged headers is denied.
6. Task import is idempotent and does not delete HA source records.
7. Mobile UI, backup/restore and HA restarts tested without affecting existing Házikó applications.
