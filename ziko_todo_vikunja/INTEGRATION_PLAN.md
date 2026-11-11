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