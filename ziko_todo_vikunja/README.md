# Ziko™ ● Todo — hardened Vikunja Home Assistant App

**Upstream:** [Vikunja 2.8.0](https://github.com/go-vikunja/vikunja/releases/tag/v2.8.0), AGPL-3.0-or-later. This wrapper does not fork or modify Vikunja's source code. Its license obligations remain in effect.

## Security design

- No `/config` mount, no access to Home Assistant config or Supervisor token.
- No privileged mode, no Docker socket or host networking.
- Persistent local SQLite database, files and a randomly generated signing secret inside the app's dedicated `/data`.
- Run the Vikunja server as unprivileged user UID/GID 1000.
- Default `boot: manual`; never enable an autorestart/watchdog before health and storage tests.
- Port 3456 serves **unencrypted HTTP** on the trusted LAN. Never forward it to the public internet. Use HTTPS or a private VPN before inviting remote users.
- `public_url` must match the actual accessible URL for browser sign-in, links and CORS.
- Registration is enabled *only for the first owner account*. Turn it off immediately afterwards using the app settings, then invite users explicitly in Vikunja.
- Email notifications and password resets require a mailer later; use TOTP 2FA for each user.
- Include this app's `/data` in system backups. Do not include media recordings unnecessarily.

## Functional scope

Use the complete official Vikunja web interface: projects and nested projects, tasks and subtasks, labels, custom filters, assignees, teams, list / Kanban / Gantt / table views, dates and recurrence, attachments, comments, time tracking, history, notifications, REST API v2, webhooks, CalDAV and MCP.

Vikunja Cloud/Pro services are outside this app. Features exclusive to Pro cannot be obtained by self-hosting without a valid entitlement.

## AI connection

The built-in Vikunja MCP endpoint is `/api/v2/mcp` and accepts bearer API tokens. Vikunja's official documentation says direct ChatGPT MCP connection is not supported yet (OAuth mismatch). A separately authenticated adapter or custom ChatGPT plugin is needed for full two-way ChatGPT control. Create a dedicated bot user with only the necessary project permissions; do not hand out an owner token. Token provisioning requires an initial owner login.

The existing native Home Assistant to-do lists remain unchanged until a separately reviewed, one-way import or integration is proven. No automatic task deletion or migration.

## Brand

New work uses `Ziko™ ● <module>` where the `Ziko™` part will be read from one central brand setting once the cross-app configuration service exists. This wrapper does **not** change the names of any existing Házikó dashboards.
