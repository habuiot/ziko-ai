# Ziko™ ● Todo · Home Assistant Ingress Identity Gateway (v0.1)

**Status: SOURCE ONLY / NOT INSTALLED.** The Vikunja add-on currently reports `state: error`. This separate identity bridge can be tested and reviewed without modifying existing task data.

## First milestone — no second login

- Exposes only Home Assistant Supervisor Ingress (not a host port).
- Authenticated browser session provides `X-Remote-User-Id` and optional display name.
- Refuses requests not originating from the Supervisor proxy `172.30.32.2`. Direct requests with forged headers are denied.
- Refuses requests with missing, control-character or oversized user IDs. It does not infer a default administrator.
- `GET /`: safe minimal identity-view UI.
- `GET /api/me`: authenticated identity check (no role or permission claims).
- `GET /api/backend`: Vikunja health probe only, returns a boolean status with **connected=false**.
- All mutating HTTP methods return 405. No user provisioning, API tokens, project reads or task writes yet.
- No network port exposure, no /config mount, no HA API token, no secrets in frontend.
- No background agent or monitoring implied.
- HTML-escapes display names; no cache, no CORS, restrictive CSP; no sensitive URL/header logging.

## Security gate for v0.2

Before any project/task endpoints:
1. Confirm the real Ingress peer IP / headers on the deployed environment. The IP is taken from Home Assistant official docs, not yet runtime-tested locally.
2. Implement separate **server-enforced project ACL** keyed by HA stable user ID with deny-by-default. Do not derive roles from display names.
3. Decide whether to provision per-user Vikunja identities or to keep identity and authorization in the ZIKO gateway. No single shared token may bypass authorization.
4. Store server-to-server secrets in restricted /data (never in browser or GitHub).
5. Do not offer a raw arbitrary upstream reverse proxy to Vikunja; use explicit path allowlists and operations.
6. Confirm a passwordless internal Vikunja service identity setup, not a forced user registration.
7. Verify no public exposure of 3456, use TLS/private VPN before any remote integration.
8. Put audit logging, backup/restore and permission denial tests in place before changing real user data.

## Commands for developers

```sh
cd ziko_todo_gateway
python3 -m unittest -v test_server.py
```

Upstream docs:
- Home Assistant: https://developers.home-assistant.io/docs/add-ons/presentation/#ingress
- HA Supervisor Ingress: https://contributors.home-assistant.io/apps/guides/ingress/
- Vikunja API v2: https://vikunja.io/docs/api-v2/

## Important
No change to `/ziko-todo`, OldTodo, existing local_todo entities, Vikunja app, app boot settings or HA host resources. Installing this app is a separate gate after security and actual device tests. No restart was requested or performed.
