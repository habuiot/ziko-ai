#!/usr/bin/env python3
"""ZIKO Kiosk Pad bridge: limited HA surface for legacy iPad Safari (ES5)."""
from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LOG = logging.getLogger("ziko-kiosk")
DATA = Path(os.environ.get("ZIKO_DATA_DIR", "/data"))
PORT = int(os.environ.get("ZIKO_PORT", "8096"))
HA_BASE = os.environ.get("ZIKO_HA_URL", "http://supervisor/core/api").rstrip("/")
HA_TOKEN = os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("ZIKO_HA_TOKEN", "")
CACHE_TTL = 5.0
SESSION_AGE = 90 * 24 * 3600

LIGHTS = (
    ("light.awox_eglo_zm_rgb_tw", "Konyha - EGLO"),
    ("light.led_izzo_wifi_2", "Nappali"),
    ("light.led_izzo_wifi", "Nagyszoba"),
    ("light.furdoszoba_furdoszoba_lampa_hb_1_kapcsolo", "Furdoszoba"),
    ("light.nagyszoba_osszes_feny", "Nagyszoba - osszes"),
)
CONTACTS = (
    ("binary_sensor.ewelink_snzb_04p_contact", "Bejarati ajto"),
    ("binary_sensor.ewelink_snzb_04p_contact_2", "Erkelyajto"),
    ("binary_sensor.door_sensor_ajto", "Furdoszoba ajto"),
    ("binary_sensor.nagyszoba_kis_ablak_ajto", "Nagyszoba kis ablak"),
    ("binary_sensor.nagyszoba_nagyszoba_nagy_ablak_ajto", "Nagyszoba nagy ablak"),
    ("binary_sensor.myggbett_door_window_sensor_ajto", "Nappali nagy ablak"),
    ("binary_sensor.nappali_nappali_kis_ablak_bal_ajto_2", "Nappali bal ablak"),
    ("binary_sensor.nappali_jobb_kis_ablak_ajto", "Nappali jobb ablak"),
)
MEDIA = (
    ("media_player.nagyszoba_nagyszoba_tv", "Nagyszoba TV"),
    ("media_player.nagyszoba_nagyoszoba_tv_felso", "Nagyszoba felso TV"),
    ("media_player.iroda_iroda_tv", "Iroda TV"),
    ("media_player.nagyszoba_smartbox", "Telekom SmartBox"),
)
CAMERAS = (
    ("camera.p2", "Kukucskalo"),
    ("camera.nagyszoba_kamera_2_mainstream", "Nagyszoba kamera"),
    ("camera.nappali_kamera_mainstream", "Nappali kamera"),
)
LOCKS = (("lock.eloszoba_bejarati_ajto_also_zar", "Bejarati zar"),)
CLIMATE = (("climate.sonoff_trvzb", "Nagyszoba radiator"),)
SCENES = (("scene.lampak_fel", "Lampak fel"), ("scene.lampak_ki_2", "Lampak ki"))
ENERGY = (
    ('sensor.kozlekedo_legtisztito_teljesitmeny', 'Média felső fogyasztásmérő'),
    ('sensor.szimulator_teljesitmeny', 'Ágy fogyasztásmérő'),
    ('sensor.eloszoba_szerver_fogyasztasmero_teljesitmeny', 'Szerver fogyasztásmérő'),
    ('sensor.konyha_huto_teljesitmeny', 'Hűtő fogyasztásmérő'),
    ('sensor.eloszoba_consuela_fogyasztasmero_teljesitmeny', 'Consuela fogyasztásmérő'),
    ('sensor.nagyszoba_fokapcsolo_teljesitmeny', 'Törölközőszárító fogyasztásmérő'),
    ('sensor.eloszoba_3d_nyomtato_fogyasztasmero_teljesitmeny', '3D nyomtató fogyasztásmérő'),
    ('sensor.3d_nyomtato_teljesitmeny', 'Média alsó fogyasztásmérő'),
)
SCENE_IDS = {x[0] for x in SCENES}
VISIBLE = LIGHTS + CONTACTS + MEDIA + CAMERAS + LOCKS + CLIMATE + SCENES + ENERGY
LIGHT_IDS = {item[0] for item in LIGHTS}
MEDIA_IDS = {item[0] for item in MEDIA}
CAMERA_IDS = {item[0] for item in CAMERAS}


def _atomic_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


class HaClient:
    def __init__(self, base=HA_BASE, token=HA_TOKEN):
        self.base = base
        self.token = token

    def request(self, path, body=None):
        if not self.token:
            raise RuntimeError("Missing Home Assistant API token")
        url = self.base + path
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Authorization": "Bearer " + self.token, "Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
        with urllib.request.urlopen(req, timeout=7) as response:
            raw = response.read(4 * 1024 * 1024 + 1)
            if len(raw) > 4 * 1024 * 1024:
                raise RuntimeError("HA response exceeded size limit")
            return json.loads(raw.decode("utf-8")) if raw else None

    def states(self):
        return self.request("/states")

    def camera_image(self, entity_id):
        if not self.token:
            raise RuntimeError("Missing Home Assistant API token")
        if entity_id not in CAMERA_IDS:
            raise ValueError("Camera not allowed")
        url = self.base + "/camera_proxy/" + entity_id
        req = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + self.token, "Accept": "image/jpeg,image/png",
        }, method="GET")
        with urllib.request.urlopen(req, timeout=8) as response:
            mime = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if mime not in ("image/jpeg", "image/png"):
                raise RuntimeError("Invalid camera response content type")
            data = response.read(3 * 1024 * 1024 + 1)
            if len(data) > 3 * 1024 * 1024:
                raise RuntimeError("Camera image too large")
            return mime, data


    def service(self, domain, action, entity_id):
        return self.request("/services/%s/%s" % (domain, action), {"entity_id": entity_id})


class Bridge:
    def __init__(self, data_dir=DATA, ha=None, clock=time.time):
        self.dir = Path(data_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.ha = ha if ha is not None else HaClient()
        self.clock = clock
        self.lock = threading.RLock()
        self.last_read = 0
        self.cache = None
        self.last_error = "Nem sikerult a Haziko adatait lekerdezni"
        self.pairing_code = self._load_pairing_code()
        self.sessions = self._load_sessions()
        self.failed_pairs = {}

    def _load_pairing_code(self):
        path = self.dir / "pairing.json"
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
            if len(stored["code"]) == 8 and stored["code"].isdigit():
                return stored["code"]
        except (FileNotFoundError, KeyError, ValueError, TypeError):
            pass
        code = "%08d" % secrets.randbelow(10**8)
        _atomic_json(path, {"code": code})
        return code

    def _load_sessions(self):
        try:
            sessions = json.loads((self.dir / "sessions.json").read_text(encoding="utf-8"))
            if isinstance(sessions, dict):
                return sessions
        except (OSError, TypeError, ValueError):
            pass
        return {}

    def pair(self, code, pad, ip):
        if pad not in ("KIOSK-01", "KIOSK-02", "KIOSK-03", "KIOSK-04"):
            return None
        with self.lock:
            now = self.clock()
            tries = [t for t in self.failed_pairs.get(ip, []) if now - t < 900]
            if len(tries) >= 5:
                self.failed_pairs[ip] = tries
                return None
            if not isinstance(code, str) or not hmac.compare_digest(code, self.pairing_code):
                tries.append(now)
                self.failed_pairs[ip] = tries
                return None
            self.failed_pairs.pop(ip, None)
            token = secrets.token_urlsafe(32)
            self.sessions[hashlib.sha256(token.encode("ascii")).hexdigest()] = {"pad": pad, "expires": now + SESSION_AGE}
            self.sessions = {k:v for k,v in self.sessions.items() if v.get("expires", 0) > now}
            _atomic_json(self.dir / "sessions.json", self.sessions)
            return token

    def authenticate(self, cookie_header):
        try:
            parsed = cookies.SimpleCookie()
            parsed.load(cookie_header or "")
            token = parsed["zkp_session"].value
            hashed = hashlib.sha256(token.encode("ascii")).hexdigest()
        except (KeyError, cookies.CookieError, UnicodeError, ValueError):
            return None
        with self.lock:
            session = self.sessions.get(hashed)
            if not session or session.get("expires", 0) <= self.clock():
                return None
            return session["pad"]

    def snapshot(self):
        """Read only explicitly approved HA entities. Never infer unknown readings."""
        with self.lock:
            now = self.clock()
            if self.cache is None or now - self.last_read >= CACHE_TTL:
                self.last_read = now
                try:
                    states = self.ha.states()
                    allowed = {entity_id for entity_id, _ in VISIBLE}
                    self.cache = {r["entity_id"]: r for r in states if r.get("entity_id") in allowed}
                    self.last_error = ""
                except Exception as exc:
                    LOG.warning("Home Assistant state read failed: %s", type(exc).__name__)
                    self.cache = None
                    self.last_error = "A Haziko nem erheto el"
            items = {}
            if self.cache is not None:
                groups = (("lights", LIGHTS), ("contacts", CONTACTS),
                          ("media", MEDIA), ("cameras", CAMERAS), ("locks", LOCKS),
                          ("climate", CLIMATE), ("scenes", SCENES), ("energy", ENERGY))
                subtotal, fresh_count = 0.0, 0
                for typ, collection in groups:
                    items[typ] = []
                    for entity_id, label in collection:
                        src = self.cache.get(entity_id, {})
                        attrs = src.get("attributes") or {}
                        record = {"id": entity_id, "label": label,
                                  "state": src.get("state", "unavailable"),
                                  "brightness": attrs.get("brightness") if typ == "lights" else None}
                        if typ == "climate":
                            record["current_temperature"] = attrs.get("current_temperature")
                            record["target_temperature"] = attrs.get("temperature")
                        if typ == "energy":
                            record["unit"] = attrs.get("unit_of_measurement")
                            record["last_updated"] = src.get("last_updated")
                            record["watts"] = None
                            record["fresh"] = False
                            try:
                                value = float(src.get("state"))
                                stamp = datetime.datetime.fromisoformat(str(src.get("last_updated", "")).replace("Z", "+00:00"))
                                age = now - stamp.timestamp()
                                if 0 <= value <= 100000 and -60 <= age <= 900 and record["unit"] == "W":
                                    record["watts"], record["fresh"] = round(value, 2), True
                                    fresh_count += 1
                                    subtotal += value
                            except (TypeError, ValueError, OverflowError):
                                pass
                        items[typ].append(record)
                items["energy_summary"] = {
                    "partial_w": round(subtotal, 1) if fresh_count else None,
                    "fresh_meters": fresh_count,
                    "known_meters": len(ENERGY),
                    "scope": "known_independent_meter_partial_not_whole_home",
                }
            return {"ok": self.cache is not None, "error": self.last_error,
                    "ts": int(self.clock()), "items": items}

    def command(self, entity_id, action):
        if entity_id in LIGHT_IDS and action in ("on", "off"):
            domain, service, group = "light", ("turn_on" if action == "on" else "turn_off"), "lights"
        elif entity_id in MEDIA_IDS and action in ("on", "off", "play_pause", "volume_up", "volume_down"):
            domain, group = "media_player", "media"
            service = {"on": "turn_on", "off": "turn_off",
                       "play_pause": "media_play_pause",
                       "volume_up": "volume_up", "volume_down": "volume_down"}[action]
        elif entity_id in SCENE_IDS and action == "activate":
            domain, service, group = "scene", "turn_on", "scenes"
        else:
            raise ValueError("Operation not allowed")
        snap = self.snapshot()
        if not snap.get("ok"):
            raise RuntimeError("No live HA state")
        item = next((x for x in snap["items"][group] if x["id"] == entity_id), None)
        if not item or item["state"] in ("unavailable", "unknown", None):
            raise RuntimeError("Entity not available")
        self.ha.service(domain, service, entity_id)
        with self.lock:
            self.last_read = 0
        return True

    def camera_image(self, entity_id):
        if entity_id not in CAMERA_IDS:
            raise ValueError("Camera not allowed")
        snapshot = self.snapshot()
        if not snapshot.get("ok"):
            raise RuntimeError("No live HA state")
        item = next((x for x in snapshot["items"]["cameras"] if x["id"] == entity_id), None)
        if not item or item["state"] in ("unavailable", "unknown", None):
            raise RuntimeError("Camera unavailable")
        return self.ha.camera_image(entity_id)


HTML = Path(__file__).with_name("index.html").read_bytes()


def secure_html():
    """Owner-controlled private HTTPS-only HMI. Source stays in /data, not GitHub.

    The legacy HTTP listener must continue serving the old safe HTML. On invalid
    owner content, fall back to the shipped, already-tested interface.
    """
    path = DATA / "kiosk_2126_live.html"
    try:
        content = path.read_bytes()
        if 1024 <= len(content) <= 2_000_000 and content.lstrip().lower().startswith(b"<!doctype html>") and b"ACCESS 2126 LIVE" in content:
            LOG.info("Private HTTPS 2126 HMI loaded from persistent addon data")
            return content
        LOG.warning("Invalid private HTTPS HMI, using default instead")
    except FileNotFoundError:
        LOG.info("Private HTTPS HMI not installed, using default")
    except OSError as exc:
        LOG.warning("Private HTTPS HMI not readable: %s", type(exc).__name__)
    return HTML


def make_handler(bridge):
    class Handler(BaseHTTPRequestHandler):
        server_version = "ZIKO Kiosk Bridge/0.2"
        sys_version = ""

        def log_message(self, fmt, *args):
            LOG.info("%s - %s", self.address_string(), fmt % args)

        def headers_common(self, mime):
            self.send_header("Content-Type", mime)
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'self'; base-uri 'none'; form-action 'self'")

        def send_json(self, status, payload, extra_headers=None):
            raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.headers_common("application/json; charset=utf-8")
            if extra_headers:
                for k, v in extra_headers.items():
                    self.send_header(k, v)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            path = urllib.parse.urlsplit(self.path).path
            if path in ("/", "/index.html"):
                self.send_response(200)
                self.headers_common("text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(HTML)))
                self.end_headers()
                self.wfile.write(HTML)
                return
            if path == "/api/status":
                pad = bridge.authenticate(self.headers.get("Cookie"))
                self.send_json(200, {"paired": bool(pad), "pad": pad})
                return
            if path == "/api/state":
                pad = bridge.authenticate(self.headers.get("Cookie"))
                if not pad:
                    self.send_json(401, {"error": "Parositas szukseges"})
                    return
                snap = bridge.snapshot()
                snap["pad"] = pad
                self.send_json(200 if snap["ok"] else 503, snap)
                return
            self.send_json(404, {"error": "Not found"})

        def do_POST(self):
            path = urllib.parse.urlsplit(self.path).path
            host = self.headers.get("Host", "")
            origin = self.headers.get("Origin")
            if (origin and urllib.parse.urlsplit(origin).netloc != host) or self.headers.get("X-ZIKO-Request") != "1":
                self.send_json(403, {"error": "Forbidden"})
                return
            if not self.headers.get("Content-Type", "").lower().startswith("application/json"):
                self.send_json(415, {"error": "Expected JSON"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size < 1 or size > 2048:
                    self.send_json(413, {"error": "Invalid body size"})
                    return
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ValueError
            except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
                self.send_json(400, {"error": "Invalid JSON"})
                return
            if path == "/api/pair":
                token = bridge.pair(data.get("code"), data.get("pad"), self.client_address[0])
                if not token:
                    self.send_json(403, {"error": "Hibas kod vagy tul sok proba"})
                    return
                ck = "zkp_session=" + token + "; HttpOnly; Path=/; Max-Age=" + str(SESSION_AGE) + "; SameSite=Strict"
                self.send_json(200, {"ok": True}, {"Set-Cookie": ck})
                return
            if path == "/api/unlock":
                pad = bridge.authenticate(self.headers.get("Cookie"))
                if not pad:
                    self.send_json(401, {"error": "Parositas szukseges"})
                    return
                # Legacy iPad plain HTTP transport is not secure for exterior-door unlock.
                # Do not activate this service until TLS and stronger authentication exist.
                self.send_json(423, {"error": "Zárnyitás védett HTTPS kapcsolat és további hitelesítés nélkül tiltva."})
                return
            if path == "/api/command":
                if not bridge.authenticate(self.headers.get("Cookie")):
                    self.send_json(401, {"error": "Parositas szukseges"})
                    return
                try:
                    bridge.command(data.get("id"), data.get("action"))
                except ValueError:
                    self.send_json(403, {"error": "Ez a vezerles nincs engedelyezve"})
                    return
                except Exception as exc:
                    LOG.warning("HA command failed: %s", type(exc).__name__)
                    self.send_json(503, {"error": "Vezerles sikertelen"})
                    return
                self.send_json(200, {"ok": True})
                return
            self.send_json(404, {"error": "Not found"})

    return Handler


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    bridge = Bridge()
    LOG.info("ZIKO Kiosk Pad active; setup pairing code: %s", bridge.pairing_code)
    LOG.info("Legacy HTTP exposes no lock/unlock or alarm actions; HTTPS requires KIOSK-01 + PIN")
    # Preserve legacy HTTP and keep physical unlock exclusively on independent HTTPS.
    try:
        from secure import start_secure
        start_secure(bridge, secure_html())
    except Exception as exc:
        LOG.error("HTTPS unavailable, legacy HTTP still available: %s", type(exc).__name__)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), make_handler(bridge))
    server.serve_forever(poll_interval=0.5)


if __name__ == "__main__":
    main()

