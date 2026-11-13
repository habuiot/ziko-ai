# Ziko™ ● Todo · Home Assistant Ingress + Project ACL Gateway (v0.3)

**Current status (2026-11-13): installed and started on Házikó as `29b31cdc_ziko_todo_gateway`, version **0.3.0**.** The Vikunja app remains in `error` state and was not restarted. This gateway is a separate read-only component; the existing ZikoTodo frontend and all native tasks remain untouched.

**Verification:** GitHub Actions: **38/38 Python security and UI tests passed**; Docker container boot and direct spoofed-header rejection passed. Live direct and spoofed-header API requests were rejected with HTTP 403, as designed. **Authenticated ingress via the owner's actual browser has NOT yet been confirmed**, and no project memberships exist in the live gateway database.

## First milestone — no second login

- Exposes only Home Assistant Supervisor Ingress (not a host port).
- Authenticated browser session provides `X-Remote-User-Id` and optional display name.
- Refuses requests not originating from the Supervisor proxy `172.30.32.2`. Direct requests with forged headers are denied.
- Refuses requests with missing, control-character or oversized user IDs. It does not infer a default administrator.
- `GET /`: safe minimal identity-view UI.
- `GET /api/me`: authenticated identity check (no role or permission claims).
- `GET /api/backend`: Vikunja health probe only, returns availability and **connected=false**.
- `GET /api/projects`: read-only projects filtered by the Home Assistant stable user ID.
- `GET /api/projects/<slug>`: read-only per-project access; unauthorized projects return 404 without leaking their existence.
- Role levels are `viewer` (read), `editor` (read, future task writes) and `manager` (read, future task writes, future membership management); **no write HTTP endpoints exist today**.
- Project ACL is stored in the gateway's private `/data/acl.sqlite3` database; no automatic owner, no default grants, no shared administrator token.
- All mutating HTTP methods return 405. No user provisioning, API tokens, project reads or task writes yet.
- No host port exposure, no /config mount, no HA API token, no secrets in frontend. Runs under an unprivileged container user after preparing private /data.
- No background agent or monitoring implied.
- HTML-escapes display names; no cache, no CORS, restrictive CSP; no sensitive URL/header logging.

## Security gate for full project and task API (v0.3+)

Before any project/task endpoints:
1. Confirm the authenticated Ingress peer IP / headers on the owner's actual Házikó browser session. The direct-client rejection is tested, but valid end-to-end ingress is not yet verified.
2. **Done at source level:** server-enforced, read-only project ACL keyed by Home Assistant stable user ID, deny-by-default. Require additional authenticated UI and multi-user tests before enabling mutations.
3. Decide whether to provision per-user Vikunja identities or to keep identity and authorization in the ZIKO gateway. No single shared token may bypass authorization.
4. Store server-to-server secrets in restricted /data (never in browser or GitHub).
5. Do not offer a raw arbitrary upstream reverse proxy to Vikunja; use explicit path allowlists and operations.
6. Confirm a passwordless internal Vikunja service identity setup, not a forced user registration.
7. Verify no public exposure of 3456, use TLS/private VPN before any remote integration.
8. Put audit logging, backup/restore and permission denial tests in place before changing real user data.

## Commands for developers

```sh
cd ziko_todo_gateway
python3 -m unittest discover -v -p 'test_*.py'
```

Upstream docs:
- Home Assistant: https://developers.home-assistant.io/docs/add-ons/presentation/#ingress
- HA Supervisor Ingress: https://contributors.home-assistant.io/apps/guides/ingress/
- Vikunja API v2: https://vikunja.io/docs/api-v2/

## Important
Installed and started **only** the new read-only gateway after CI and container smoke verification. No change to `/ziko-todo`, OldTodo, existing native todo entities or Vikunja's stopped app. The gateway remains `boot: manual`, `watchdog: false`, with no public mapped port.

A trusted, local administrative bootstrap can later use `admin_cli.py` to create a project and grant an explicit stable Home Assistant user ID, e.g. `python admin_cli.py create-project haziko "Házikó"` and `python admin_cli.py grant haziko <HA_USER_ID> manager`. This is intentionally **not** accessible to browsers, and no real user ID has been assigned yet.


## User workspace and dashboard entry (v0.3)

- New mobile-first, dark/neon server-rendered project access portal: `panel.py`. No external assets or browser-side JavaScript.
- Displays the logged-in HA display name, stable user ID and only projects granted to that ID in the local SQLite ACL. Roles: viewer / editor / manager. A new user sees a clearly labeled empty state, not other people's projects.
- Uses a single-pass template replacement to prevent token interpolation and HTML markup injection; markup and identity values are escaped.
- Added test suite: `test_panel.py`, 10 UI/rendering/authorization tests; cumulative **38/38** verified via GitHub Actions. Container boot and private SQLite file permissions passed as well.
- Installed Supervisor gateway version **0.3.0** with Ingress; no mapped host ports and `boot: manual`, `watchdog: false`.
- HA ZikoTodo dashboard now includes **Hozzáférések** view (`/ziko-todo/hozzaferesek`), which links to the gateway add-on page. From there select **Open Web UI / Webes felület megnyitása**; this opens the authenticated Ingress portal.
- Live direct API requests with forged `X-Remote-User-Id` headers to `/api/me` and `/api/projects` both returned HTTP 403 as designed.
- **Not yet verified:** authenticated end-user ingress session on the owner's Android browser, actual per-user membership assignment in the live database, and end-to-end task interaction with Vikunja.
- Vikunja remains `state:error` and was **not** restarted or modified. Neither the ZikoTodo Kanban nor OldTodo records were migrated or modified.
