#!/usr/bin/env python3
"""ZIKO Kiosk Pad HTTPS extension: separate authenticated session and guarded U200 unlock.

Only the HTTPS listener exposes lock.unlock. The legacy HTTP listener keeps
its original read/light/media permissions and always rejects unlocking.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import plistlib
import secrets
import ssl
import subprocess
import threading
import time
import urllib.parse
import uuid
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LOG = logging.getLogger("ziko-kiosk-secure")
LOCK_ENTITY = "lock.eloszoba_bejarati_ajto_also_zar"
SESSION_TTL = 30 * 24 * 3600
MAX_ATTEMPTS = 3
WINDOW = 15 * 60


def tls_assets(directory):
    root = Path(directory) / "tls"
    root.mkdir(parents=True, exist_ok=True)
    ca_key, ca_cert = root / "ca.key", root / "ca.pem"
    key, cert = root / "server.key", root / "server.pem"
    required = (ca_key, ca_cert, key, cert)
    if not all(p.exists() for p in required):
        if any(p.exists() for p in required):
            raise RuntimeError("Incomplete TLS material: not regenerating over existing files")
        def cmd(args):
            subprocess.run(args, cwd=str(root), check=True, timeout=40,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        cmd(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
             "-sha256", "-days", "3650", "-keyout", "ca.key", "-out", "ca.pem",
             "-subj", "/CN=ZIKO Kiosk Pad Local CA",
             "-addext", "basicConstraints=critical,CA:TRUE",
             "-addext", "keyUsage=critical,keyCertSign,cRLSign"])
        cmd(["openssl", "req", "-new", "-newkey", "rsa:2048", "-nodes",
             "-sha256", "-keyout", "server.key", "-out", "server.csr",
             "-subj", "/CN=homeassistant.local"])
        ext = root / "extensions.cnf"
        ext.write_text(
            "subjectAltName=DNS:homeassistant.local\n"
            "basicConstraints=critical,CA:FALSE\n"
            "keyUsage=critical,digitalSignature,keyEncipherment\n"
            "extendedKeyUsage=serverAuth\n", encoding="ascii")
        cmd(["openssl", "x509", "-req", "-in", "server.csr",
             "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial",
             "-out", "server.pem", "-days", "730", "-sha256",
             "-extfile", "extensions.cnf"])
        for private in (ca_key, key):
            os.chmod(private, 0o600)
        (root / "server.csr").unlink(missing_ok=True)
        ext.unlink(missing_ok=True)
    ca_der = ssl.PEM_cert_to_DER_cert(ca_cert.read_text(encoding="ascii"))
    profile = {
        "PayloadContent": [{
            "PayloadCertificateFileName": "ZIKO-Kiosk-CA.cer",
            "PayloadContent": ca_der,
            "PayloadDisplayName": "ZIKO Kiosk CA",
            "PayloadIdentifier": "hu.ziko.kiosk.ca",
            "PayloadType": "com.apple.security.root",
            "PayloadUUID": str(uuid.uuid4()),
            "PayloadVersion": 1,
        }],
        "PayloadDescription": "ZIKO Kiosk Pad local HTTPS certificate",
        "PayloadDisplayName": "ZIKO Kiosk Pad TLS",
        "PayloadIdentifier": "hu.ziko.kiosk.profile",
        "PayloadOrganization": "ZIKO Technology",
        "PayloadType": "Configuration",
        "PayloadUUID": str(uuid.uuid4()),
        "PayloadVersion": 1,
    }
    return {
        "key": str(key),
        "cert": str(cert),
        "ca_sha256": hashlib.sha256(ca_der).hexdigest().upper(),
        "profile": plistlib.dumps(profile, fmt=plistlib.FMT_XML),
    }


class Security:
    def __init__(self, bridge):
        self.bridge = bridge
        self.data = bridge.dir
        self.lock = threading.RLock()
        self.unlock_mutex = threading.Lock()
        self.sessions_path = self.data / "secure_sessions.json"
        try:
            self.sessions = json.loads(self.sessions_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            self.sessions = {}
        self.failed_pair = {}
        self.failed_pin = {}
        self.last_swipe_unlock = {}

    def _attempt(self, table, ip, ok, limit):
        now = time.time()
        with self.lock:
            attempts = [t for t in table.get(ip, []) if now - t < WINDOW]
            if len(attempts) >= limit:
                table[ip] = attempts
                return False
            if ok:
                table.pop(ip, None)
                return True
            attempts.append(now)
            table[ip] = attempts
            return False

    def pair(self, code, pad, ip):
        if pad not in ("KIOSK-01", "KIOSK-02", "KIOSK-03", "KIOSK-04"):
            return None
        correct = isinstance(code, str) and hmac.compare_digest(code, self.bridge.pairing_code)
        if not self._attempt(self.failed_pair, ip, correct, 5):
            return None
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode("ascii")).hexdigest()
        with self.lock:
            self.sessions = {k: v for k, v in self.sessions.items() if v.get("expires", 0) > time.time()}
            self.sessions[digest] = {"pad": pad, "expires": time.time() + SESSION_TTL, "ip": ip}
            tmp = self.sessions_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.sessions), encoding="utf-8")
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.sessions_path)
        return token

    def swipe_without_pin(self):
        """PIN-free mode is explicitly enabled by the owner, not by the web client."""
        try:
            value = json.loads((self.data / "options.json").read_text(encoding="utf-8")).get("swipe_without_pin", False)
            return value is True
        except (OSError, ValueError, TypeError):
            return False

    def identity(self, cookie, ip=None):
        try:
            c = cookies.SimpleCookie()
            c.load(cookie or "")
            token = c["zkp_tls"].value
            digest = hashlib.sha256(token.encode("ascii")).hexdigest()
        except (KeyError, ValueError, UnicodeError, cookies.CookieError):
            return None
        with self.lock:
            s = self.sessions.get(digest)
            if not s or s.get("expires", 0) <= time.time():
                return None
            if s.get("pad") == "KIOSK-01" and self.swipe_without_pin():
                # IP-bind the HTTPS pairing. Legacy unbound sessions must re-pair.
                if not ip or s.get("ip") != ip:
                    return None
            return s.get("pad")

    def expected_pin(self):
        try:
            configured = json.loads((self.data / "options.json").read_text(encoding="utf-8")).get("unlock_pin", "")
            return configured if isinstance(configured, str) and configured.isdigit() and 8 <= len(configured) <= 12 else ""
        except (OSError, ValueError, TypeError):
            return ""

    def unlock(self, pad, ip, supplied):
        if pad != "KIOSK-01":
            return 403, {"error": "Csak KIOSK-01 terminalon lehet nyitni"}
        no_pin = self.swipe_without_pin()
        if not no_pin:
            expected = self.expected_pin()
            if not expected:
                return 423, {"error": "Allits be 8-12 szamjegyu nyitasi PIN-t az alkalmazasban"}
            correct = isinstance(supplied, str) and hmac.compare_digest(supplied, expected)
            if not self._attempt(self.failed_pin, ip, correct, MAX_ATTEMPTS):
                return 403, {"error": "Hibas PIN vagy tul sok probalkozas; varj 15 percet"}
        with self.unlock_mutex:
            if no_pin:
                # Deliberate swipes only; guard accidental repeated/replayed requests.
                now = time.monotonic()
                last = self.last_swipe_unlock.get(ip, 0)
                if now - last < 12:
                    return 429, {"error": "Varj 12 masodpercet a kovetkezo nyitasig"}
                self.last_swipe_unlock[ip] = now
            try:
                previous = self.bridge.ha.request("/states/" + LOCK_ENTITY).get("state")
                if previous == "unlocked":
                    return 200, {"ok": True, "state": "unlocked", "already_unlocked": True}
                if previous != "locked":
                    return 423, {"error": "A zar allapota nem egyertelmu, nyitas letiltva"}
                self.bridge.ha.service("lock", "unlock", LOCK_ENTITY)
                for attempt in range(6):
                    new_state = self.bridge.ha.request("/states/" + LOCK_ENTITY).get("state")
                    if new_state == "unlocked":
                        self.bridge.last_read = 0
                        return 200, {"ok": True, "state": "unlocked"}
                    if attempt < 5:
                        time.sleep(0.7)
                LOG.warning("U200 unlock requested, but not confirmed by Home Assistant")
                return 503, {"error": "Parancs elkuldve, de a zar nem igazolta a nyitast"}
            except Exception as exc:
                LOG.error("Secure unlock failed: %s", type(exc).__name__)
                return 503, {"error": "A zarnyitas nem sikerult vagy nem ellenorizheto"}


def secure_handler(security, html):
    bridge = security.bridge

    class Handler(BaseHTTPRequestHandler):
        server_version = "ZIKO Kiosk Secure/0.3.2"
        sys_version = ""

        def log_message(self, fmt, *args):
            LOG.info("%s - %s", self.address_string(), fmt % args)

        def headers_common(self, mime):
            self.send_header("Content-Type", mime)
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("Strict-Transport-Security", "max-age=2592000")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'self'; base-uri 'none'; form-action 'self'")

        def json_result(self, status, payload, cookie=None):
            data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.headers_common("application/json; charset=utf-8")
            if cookie:
                self.send_header("Set-Cookie", cookie)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = urllib.parse.urlsplit(self.path).path
            if path in ("/", "/index.html"):
                self.send_response(200)
                self.headers_common("text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)
                return
            if path == "/api/status":
                pad = security.identity(self.headers.get("Cookie"), self.client_address[0])
                self.json_result(200, {"paired": bool(pad), "pad": pad,
                                       "secure": True, "unlock_ready": bool(security.swipe_without_pin() or security.expected_pin())})
                return
            if path == "/api/state":
                pad = security.identity(self.headers.get("Cookie"), self.client_address[0])
                if not pad:
                    self.json_result(401, {"error": "HTTPS terminalparositas szukseges"})
                    return
                snapshot = bridge.snapshot()
                snapshot["pad"] = pad
                self.json_result(200 if snapshot.get("ok") else 503, snapshot)
                return
            self.json_result(404, {"error": "Not found"})

        def do_POST(self):
            path = urllib.parse.urlsplit(self.path).path
            origin = self.headers.get("Origin")
            if (origin and (urllib.parse.urlsplit(origin).netloc != self.headers.get("Host")
                            or urllib.parse.urlsplit(origin).scheme != "https")) or self.headers.get("X-ZIKO-Request") != "1":
                self.json_result(403, {"error": "Forbidden"})
                return
            if not self.headers.get("Content-Type", "").lower().startswith("application/json"):
                self.json_result(415, {"error": "Expected JSON"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size < 1 or size > 2048:
                    self.json_result(413, {"error": "Invalid size"})
                    return
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ValueError
            except (ValueError, UnicodeDecodeError):
                self.json_result(400, {"error": "Invalid JSON"})
                return
            if path == "/api/pair":
                token = security.pair(data.get("code"), data.get("pad"), self.client_address[0])
                if not token:
                    self.json_result(403, {"error": "Hibas parositas vagy tul sok proba"})
                    return
                cookie = "zkp_tls=" + token + "; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=" + str(SESSION_TTL)
                self.json_result(200, {"ok": True}, cookie=cookie)
                return
            pad = security.identity(self.headers.get("Cookie"), self.client_address[0])
            if not pad:
                self.json_result(401, {"error": "HTTPS terminalparositas szukseges"})
                return
            if path == "/api/command":
                try:
                    bridge.command(data.get("id"), data.get("action"))
                    self.json_result(200, {"ok": True})
                except ValueError:
                    self.json_result(403, {"error": "Nem engedelyezett vezerles"})
                except Exception:
                    self.json_result(503, {"error": "Parancs nem hajthato vegre"})
                return
            if path == "/api/unlock":
                if data.get("confirm") != "slide":
                    self.json_result(403, {"error": "Hianyzik a teljes nyitasi gesztus"})
                    return
                status, reply = security.unlock(pad, self.client_address[0], data.get("pin"))
                self.json_result(status, reply)
                return
            self.json_result(404, {"error": "Not found"})

    return Handler


def start_secure(bridge, html, port=8097, profile_port=8098):
    material = tls_assets(bridge.dir)
    security = Security(bridge)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.minimum_version = ssl.TLSVersion.TLSv1_2
    tls.load_cert_chain(material["cert"], material["key"])
    server = ThreadingHTTPServer(("0.0.0.0", port), secure_handler(security, html))
    server.socket = tls.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True, name="ziko-kiosk-https").start()

    profile_bytes = material["profile"]

    class ProfileHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            LOG.info("Local certificate endpoint request")

        def do_GET(self):
            if urllib.parse.urlsplit(self.path).path != "/ca.mobileconfig":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/x-apple-aspen-config")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(profile_bytes)))
            self.end_headers()
            self.wfile.write(profile_bytes)

        def do_POST(self):
            self.send_error(405)

    profile_server = ThreadingHTTPServer(("0.0.0.0", profile_port), ProfileHandler)
    threading.Thread(target=profile_server.serve_forever, daemon=True, name="ziko-kiosk-ca").start()
    LOG.info("Secure local HTTPS ready at :%s, certificate installer at :%s", port, profile_port)
    LOG.info("ZIKO Kiosk CA SHA256 fingerprint: %s", material["ca_sha256"])
    LOG.info("Unlock mode: %s; do not forward these ports to the internet", "paired KIOSK-01 swipe" if security.swipe_without_pin() else "PIN required")
    return server, profile_server
