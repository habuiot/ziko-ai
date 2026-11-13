#!/usr/bin/env python3
"""ZikoTodo ingress identity bridge.

Read-only v0.2 with project-level ACL. Ingress is the only entry point.
No arbitrary Vikunja proxy and no access tokens in browser.
"""
from __future__ import annotations

import html
import ipaddress
import json
import logging
import os
import socket
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Mapping
from urllib.parse import urlsplit
from acl import DEFAULT_DB, init_db, accessible_projects, get_project

PORT = int(os.environ.get("ZIKO_GATEWAY_PORT", "8099"))
TRUSTED_PROXY = os.environ.get("ZIKO_TRUSTED_PROXY", "172.30.32.2")
# This is the fixed internal container hostname, not a user-supplied URL.
VIKUNJA_HEALTH = "http://29b31cdc-ziko-todo-vikunja.local.hass.io:3456/api/v2/health"
MAX_USER_ID = 128

log = logging.getLogger("ziko-todo-gateway")


def ingress_identity(peer_ip: str, headers: Mapping[str, str]) -> dict | None:
    """Reject all non-Supervisor peers, spoofed and missing identity headers."""
    try:
        if ipaddress.ip_address(peer_ip) != ipaddress.ip_address(TRUSTED_PROXY):
            return None
    except ValueError:
        return None

    user_id = (headers.get("X-Remote-User-Id") or "").strip()
    if not user_id or len(user_id) > MAX_USER_ID:
        return None
    if any(ord(c) < 33 or ord(c) > 126 for c in user_id):
        return None

    name = (headers.get("X-Remote-User-Display-Name") or "").strip()
    # Display name is presentation-only, never a permission input.
    return {"id": user_id, "display_name": name[:100]}


def check_backend(timeout: float = 1.2) -> bool:
    """Read-only health probe, without exposing the upstream address."""
    try:
        req = urllib.request.Request(
            VIKUNJA_HEALTH,
            headers={"Accept": "application/json", "User-Agent": "ZikoTodo-Gateway/0.1"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return False


def safe_path(raw_path: str) -> str:
    parsed = urlsplit(raw_path)
    return parsed.path.rstrip("/") or "/"


def dashboard(name: str) -> bytes:
    user = html.escape(name or "Home Assistant-felhasználó", quote=True)
    page = """<!doctype html>
<html lang="hu"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ZikoTodo · Kapcsolat</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}
body{background:#0c1622;color:#e2f7fb;font:14px system-ui,Arial;margin:0;padding:22px}
main{max-width:700px;margin:0 auto;border:1px solid #345063;
border-radius:16px;padding:24px;background:linear-gradient(145deg,#142b3b,#151b30)}
header{color:#86dcf0;font-size:12px;letter-spacing:.12em}
h1{font-size:30px;letter-spacing:-.04em;margin:8px 0 18px}
strong{color:#a2f0e0}p{line-height:1.5;color:#bed2dd}
small{color:#8ca8b8}.tag{padding:7px 11px;border-radius:9px;background:#244051;
display:inline-block;font-size:12px}.badge{color:#98e2f5}
</style></head><body><main><header>ZIKO TECHNOLOGY / INTERNAL INGRESS</header>
<h1>Ziko™ ● Todo <span class="badge">· API-híd</span></h1>
<div class="tag">Home Assistant-bejelentkezés ellenőrizve</div>
<p>Belépett felhasználó: <strong>__USERNAME__</strong></p>
<p>Ez a biztonsági ellenőrző felület még nem a Vikunja teljes
projektkezelője. A projektek, feladatok és csapatjogosultságok
bekötése külön, ellenőrzött fejlesztés.</p>
<small>Külön Vikunja-fiókot a felület használatához nem kérünk.</small>
</main></body></html>"""
    return page.replace("__USERNAME__", user).encode("utf-8")


class App(BaseHTTPRequestHandler):
    server_version = "ZikoTodoGateway"
    sys_version = ""

    def _reply(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'self'; base-uri 'none'; form-action 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        self._reply(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    "application/json; charset=utf-8")

    def do_GET(self) -> None:
        # Only the HA Supervisor ingress proxy is allowed.
        ident = ingress_identity(self.client_address[0], self.headers)
        if ident is None:
            self._json(403, {"error": "forbidden"})
            return

        path = safe_path(self.path)
        if path == "/":
            self._reply(200, dashboard(ident["display_name"]),
                        "text/html; charset=utf-8")
        elif path == "/api/me":
            self._json(200, {"user_id": ident["id"],
                             "display_name": ident["display_name"]})
        elif path == "/api/backend":
            self._json(200, {"vikunja": "online" if check_backend() else "unavailable",
                             "bridge": "read-only-project-acl", "connected": False})
        elif path == "/api/projects":
            self._json(200, {"projects": accessible_projects(DEFAULT_DB, ident["id"])})
        elif path.startswith("/api/projects/"):
            slug = path[len("/api/projects/"):]
            project = get_project(DEFAULT_DB, ident["id"], slug)
            if project is None:
                self._json(404, {"error": "not_found"})
            else:
                self._json(200, {"project": project})
        else:
            self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        self._json(405, {"error": "read_only"})

    def do_PUT(self) -> None:
        self.do_POST()

    def do_PATCH(self) -> None:
        self.do_POST()

    def do_DELETE(self) -> None:
        self.do_POST()

    def log_message(self, fmt: str, *args: object) -> None:
        # Don't log URLs, query strings, session headers or full user IDs.
        log.info("request status=%s", args[1] if len(args) > 1 else "?")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    init_db(DEFAULT_DB)
    # Intentionally bind only inside the Docker network; no host port exposed.
    ThreadingHTTPServer(("0.0.0.0", PORT), App).serve_forever()
