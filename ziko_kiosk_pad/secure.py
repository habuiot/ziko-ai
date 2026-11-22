#!/usr/bin/env python3
"""ZIKO Kiosk Pad HTTPS extension: separate authenticated session and guarded U200 unlock.

Only the HTTPS listener exposes lock.unlock. The legacy HTTP listener keeps
its original read/light/media permissions and always rejects unlocking.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import os
import plistlib
import secrets
import shutil
import ssl
import subprocess
import threading
import time
import datetime
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
    lan_ip = str(ipaddress.ip_address(os.environ.get("ZIKO_KIOSK_LAN_IP", "192.168.10.230")))
    ext = root / "extensions.cnf"

    def cmd(args):
        subprocess.run(args, cwd=str(root), check=True, timeout=40,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    def write_extensions():
        ext.write_text(
            "subjectAltName=DNS:homeassistant.local,IP:" + lan_ip + "\n"
            "basicConstraints=critical,CA:FALSE\n"
            "keyUsage=critical,digitalSignature,keyEncipherment\n"
            "extendedKeyUsage=serverAuth\n", encoding="ascii")

    if not all(p.exists() for p in required):
        if any(p.exists() for p in required):
            raise RuntimeError("Incomplete TLS material: not regenerating over existing files")
        cmd(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
             "-sha256", "-days", "3650", "-keyout", "ca.key", "-out", "ca.pem",
             "-subj", "/CN=ZIKO Kiosk Pad Local CA",
             "-addext", "basicConstraints=critical,CA:TRUE",
             "-addext", "keyUsage=critical,keyCertSign,cRLSign"])
        cmd(["openssl", "req", "-new", "-newkey", "rsa:2048", "-nodes",
             "-sha256", "-keyout", "server.key", "-out", "server.csr",
             "-subj", "/CN=homeassistant.local"])
        write_extensions()
        cmd(["openssl", "x509", "-req", "-in", "server.csr",
             "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial",
             "-out", "server.pem", "-days", "730", "-sha256",
             "-extfile", "extensions.cnf"])
        for private in (ca_key, key):
            os.chmod(private, 0o600)
        (root / "server.csr").unlink(missing_ok=True)
        ext.unlink(missing_ok=True)
    else:
        # Preserve the existing CA and its trusted fingerprint; only refresh the
        # server leaf certificate when old versions lack the LAN IP address.
        sans = ssl._ssl._test_decode_cert(str(cert)).get("subjectAltName", [])
        if ("IP Address", lan_ip) not in sans:
            pending_cert = root / "server.pem.next"
            try:
                write_extensions()
                cmd(["openssl", "req", "-new", "-key", "server.key",
                     "-out", "server.csr", "-subj", "/CN=homeassistant.local"])
                cmd(["openssl", "x509", "-req", "-in", "server.csr",
                     "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial",
                     "-out", "server.pem.next", "-days", "730", "-sha256",
                     "-extfile", "extensions.cnf"])
                cmd(["openssl", "verify", "-CAfile", "ca.pem", "server.pem.next"])
                issued_sans = ssl._ssl._test_decode_cert(str(pending_cert)).get("subjectAltName", [])
                if ("IP Address", lan_ip) not in issued_sans:
                    raise RuntimeError("Reissued certificate lacks the expected LAN IP")
                backup = root / "server.pem.pre-ip-san"
                if not backup.exists():
                    shutil.copy2(cert, backup)
                os.replace(pending_cert, cert)
                LOG.info("HTTPS certificate updated for local IP %s; original CA preserved", lan_ip)
            finally:
                (root / "server.csr").unlink(missing_ok=True)
                ext.unlink(missing_ok=True)
                pending_cert.unlink(missing_ok=True)
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

    def ipad_entry_state(self):
        """Fresh, limited U200/door/timer snapshot. A missing input disables actions."""
        ids = (
            "binary_sensor.ewelink_snzb_04p_contact",
            "lock.eloszoba_bejarati_ajto_also_zar",
            "automation.haziko_kulcs_belepes_ajtofigyeles_es_automatikus_visszazaras",
            "timer.haziko_kulcs_belepesi_idoablak",
            "input_select.haziko_kulcs_belepesi_folyamat",
        )
        try:
            rows = self.bridge.ha.states()
            if not isinstance(rows, list):
                raise ValueError("Invalid HA states")
            lookup = {r.get("entity_id"): r for r in rows if isinstance(r, dict) and r.get("entity_id") in ids}
            def state(e):
                r = lookup.get(e) or {}
                return r.get("state", "unknown")
            door, lock, guard, timer, phase = [state(i) for i in ids]
            remaining = None
            timer_row = lookup.get(ids[3]) or {}
            if timer == "active" and phase == "varakozas_ajtonyitasra":
                finish = (timer_row.get("attributes") or {}).get("finishes_at")
                if finish:
                    try:
                        t = datetime.datetime.fromisoformat(str(finish).replace("Z", "+00:00")).timestamp()
                        remaining = int(max(0, min(60, t - time.time() + 0.999)))
                    except (TypeError, ValueError, OverflowError):
                        remaining = None
            return 200, {"ok": True, "ts": int(time.time()), "door": door, "lock": lock,
                         "guard": guard, "timer": timer, "phase": phase, "remaining": remaining}
        except Exception as exc:
            LOG.warning("iPad entry state unavailable: %s", type(exc).__name__)
            return 503, {"ok": False, "error": "A zár és az ajtó állapota nem ellenőrizhető",
                         "door": "unknown", "lock": "unknown", "guard": "unknown",
                         "timer": "unknown", "phase": "unknown", "remaining": None}

    def ipad_entry_action(self, pad, ip, action, confirmation):
        """Mirror Node03: short tap closes; 750 ms touch hold opens, fail closed."""
        if pad != "KIOSK-01":
            return 403, {"error": "Csak párosított KIOSK-01 terminál vezérelheti a zárat"}
        if (action, confirmation) not in (("unlock", "hold"), ("lock", "tap")):
            return 403, {"error": "Nem engedélyezett zárművelet vagy érintési gesztus"}
        status, snapshot = self.ipad_entry_state()
        if status != 200:
            return status, snapshot
        if snapshot["door"] != "off":
            return 423, {"error": "Az ajtó nyitva vagy ismeretlen: zárvezérlés tiltva"}
        if action == "unlock":
            if snapshot["lock"] != "locked":
                return 423, {"error": "Nyitás csak igazoltan zárt U200 állapotból"}
            if snapshot["guard"] != "on" or snapshot["timer"] in ("unknown", "unavailable", None):
                return 423, {"error": "A visszazárási automatika vagy időzítő nem elérhető"}
            if not self.swipe_without_pin():
                return 423, {"error": "A PIN nélküli nyitás nincs engedélyezve; nyitás tiltva"}
            # Reuse existing KIOSK-01/IP-bound unlock rate limit and state confirmation.
            return self.unlock(pad, ip, None)
        if snapshot["lock"] == "locked":
            return 200, {"ok": True, "state": "locked", "already_locked": True}
        if snapshot["lock"] != "unlocked":
            return 423, {"error": "A zár mozog vagy állapota ismeretlen; zárás tiltva"}
        with self.unlock_mutex:
            # Re-read immediately before acting to reject stale screen state.
            status, latest = self.ipad_entry_state()
            if status != 200:
                return status, latest
            if latest["door"] != "off" or latest["lock"] != "unlocked":
                return 423, {"error": "Ajtó vagy U200 állapota megváltozott; zárás tiltva"}
            try:
                self.bridge.ha.service("lock", "lock", LOCK_ENTITY)
                for attempt in range(6):
                    actual = self.bridge.ha.request("/states/" + LOCK_ENTITY).get("state")
                    if actual == "locked":
                        self.bridge.last_read = 0
                        return 200, {"ok": True, "state": "locked"}
                    if attempt < 5:
                        time.sleep(0.7)
                return 503, {"error": "Zárási parancs elküldve, de az U200 nem igazolta a zárást"}
            except Exception as exc:
                LOG.warning("iPad U200 lock action failed: %s", type(exc).__name__)
                return 503, {"error": "A zárás nem sikerült vagy nem ellenőrizhető"}

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
            parsed = urllib.parse.urlsplit(self.path)
            path = parsed.path
            if path == "/api/camera":
                pad = security.identity(self.headers.get("Cookie"), self.client_address[0])
                if pad != "KIOSK-01":
                    self.json_result(401, {"error": "HTTPS KIOSK-01 pairing required"})
                    return
                ids = urllib.parse.parse_qs(parsed.query).get("id", [])
                if len(ids) != 1:
                    self.json_result(400, {"error": "Camera id required"})
                    return
                try:
                    mime, image_data = bridge.camera_image(ids[0])
                except ValueError:
                    self.json_result(403, {"error": "Camera not allowed"})
                    return
                except Exception as exc:
                    LOG.warning("Camera snapshot unavailable: %s", type(exc).__name__)
                    self.json_result(503, {"error": "Camera unavailable"})
                    return
                self.send_response(200)
                self.headers_common(mime)
                self.send_header("Content-Length", str(len(image_data)))
                self.end_headers()
                try:
                    self.wfile.write(image_data)
                except (OSError, ssl.SSLError):
                    pass
                return
            if path == "/kiosk-2026":
                try:
                    body = Path(__file__).with_name("ipad_kiosk_2026.html").read_bytes()
                    if not (body.startswith(b"<!doctype html>") and 10000 < len(body) < 100000):
                        raise ValueError("Invalid iPad Kiosk package")
                except (OSError, ValueError):
                    self.json_result(503, {"error": "ZIKO Kiosk iPad frontend nem elérhető"})
                    return
                self.send_response(200)
                self.headers_common("text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if path == "/access-2226":
                try:
                    body = Path(__file__).with_name("access_2226_live.html").read_bytes()
                    if not (body.startswith(b"<!doctype html>") and 6000 < len(body) < 100000):
                        raise ValueError("Invalid HMI 2226 package")
                except (OSError, ValueError):
                    self.json_result(503, {"error": "ACCESS 2226 HMI unavailable"})
                    return
                self.send_response(200)
                self.headers_common("text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if path == "/api/map":
                pad = security.identity(self.headers.get("Cookie"), self.client_address[0])
                if pad != "KIOSK-01":
                    self.json_result(401, {"error": "HTTPS KIOSK-01 pairing required"})
                    return
                try:
                    svg = Path(__file__).with_name("canonical_digitaltwin_v012.svg").read_text(encoding="utf-8")
                    if not (10000 < len(svg) < 130000 and '<svg' in svg and '</svg>' in svg):
                        raise ValueError("Invalid trusted map")
                    mode = urllib.parse.parse_qs(parsed.query).get("mode", ["tilt"])[0]
                    if mode == "flat":
                        style = "<style>#tiltedScene{display:none!important}#flatScene{display:inline!important}</style>"
                        svg = svg.replace(">", ">" + style, 1)
                    elif mode != "tilt":
                        self.json_result(400, {"error": "Invalid map mode"})
                        return
                    body = svg.encode("utf-8")
                except (OSError, ValueError):
                    self.json_result(503, {"error": "Canonical DigitalTwin not available"})
                    return
                self.send_response(200)
                self.headers_common("image/svg+xml; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
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
            if path == "/api/entry":
                pad = security.identity(self.headers.get("Cookie"), self.client_address[0])
                if pad != "KIOSK-01":
                    self.json_result(401, {"error": "Párosított HTTPS KIOSK-01 szükséges"})
                    return
                status, result = security.ipad_entry_state()
                self.json_result(status, result)
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
            if path == "/api/entry":
                status, result = security.ipad_entry_action(
                    pad, self.client_address[0], data.get("action"), data.get("confirm"))
                self.json_result(status, result)
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

