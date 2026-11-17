"""ZikoFiles signed Home Assistant identity and protected role registry.

No implicit access: a HA identity is never an owner until explicitly bound
by the existing ZikoFiles admin password in an HA Ingress session.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
import threading
import time
from pathlib import Path

ID = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
NONCE = re.compile(r"^[a-f0-9]{32}$")
SIG = re.compile(r"^[a-f0-9]{64}$")
HEADERS = ("X-ZikoFiles-SSO-User", "X-ZikoFiles-SSO-Time",
           "X-ZikoFiles-SSO-Nonce", "X-ZikoFiles-SSO-Signature")


def valid_id(uid):
    return isinstance(uid, str) and bool(ID.fullmatch(uid))


def signature(key_hex, uid, timestamp, nonce, method, path):
    msg = "\n".join((uid, str(timestamp), nonce, method, path)).encode()
    return hmac.new(bytes.fromhex(key_hex), msg, hashlib.sha256).hexdigest()


def signed_headers(key_hex, uid, method, path, timestamp=None, nonce=None):
    if not valid_id(uid):
        raise ValueError("invalid identity")
    timestamp = int(time.time()) if timestamp is None else int(timestamp)
    nonce = nonce or secrets.token_hex(16)
    if not NONCE.fullmatch(nonce):
        raise ValueError("invalid nonce")
    return dict(zip(HEADERS, (uid, str(timestamp), nonce,
                              signature(key_hex, uid, timestamp, nonce, method, path))))


class AssertionVerifier:
    def __init__(self):
        self.seen = {}
        self.lock = threading.Lock()

    def verify(self, headers, method, path, key_hex, now=None):
        present = [headers.get(k) for k in HEADERS]
        if not any(present):
            return None
        if not all(present):
            raise PermissionError("incomplete HA identity")
        uid, ts, nonce, mac = present
        if not valid_id(uid) or not NONCE.fullmatch(nonce or "") or not SIG.fullmatch(mac or ""):
            raise PermissionError("invalid HA identity")
        try:
            when = int(ts)
        except (ValueError, TypeError):
            raise PermissionError("invalid timestamp")
        now = int(time.time()) if now is None else int(now)
        if abs(now - when) > 45:
            raise PermissionError("expired HA identity")
        try:
            expected = signature(key_hex, uid, when, nonce, method, path)
        except (ValueError, TypeError):
            raise PermissionError("invalid SSO key")
        if not hmac.compare_digest(mac, expected):
            raise PermissionError("incorrect HA signature")
        identifier = uid + ":" + nonce
        with self.lock:
            self.seen = {k: v for k, v in self.seen.items() if v > now}
            if identifier in self.seen:
                raise PermissionError("replayed HA identity")
            self.seen[identifier] = now + 90
        return uid


class RoleRegistry:
    """Privileged, non-web-mounted 0600 JSON; explicit owner-approved ACL."""

    def __init__(self, path="/var/lib/zikofiles/sso-users.json"):
        self.path = Path(path)
        self.lock = threading.Lock()

    def state(self):
        if not self.path.exists():
            return {"version": 1, "users": {}, "pending": []}
        data = json.loads(self.path.read_text("utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("users"), dict):
            raise RuntimeError("SSO role file damaged")
        data.setdefault("pending", [])
        if not isinstance(data["pending"], list):
            raise RuntimeError("SSO request list damaged")
        if any(not valid_id(uid) or role not in ("owner", "viewer")
               for uid, role in data["users"].items()):
            raise RuntimeError("Invalid stored SSO role")
        if any(not isinstance(req, dict) or not valid_id(req.get("uid"))
               for req in data["pending"]):
            raise RuntimeError("Invalid stored access request")
        return data

    def read(self):
        return self.state()["users"]

    def role(self, uid):
        return self.read().get(uid)

    def _write(self, state):
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)
        fd, name = tempfile.mkstemp(dir=self.path.parent, prefix=".sso-", text=True)
        os.fchmod(fd, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(state, file, ensure_ascii=False, sort_keys=True)
                file.flush()
                os.fsync(file.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def enroll_owner(self, uid):
        if not valid_id(uid):
            raise PermissionError("invalid HA ID")
        with self.lock:
            state = self.state()
            users = state["users"]
            if any(role == "owner" and other != uid for other, role in users.items()):
                raise PermissionError("owner already linked")
            if users.get(uid) not in (None, "owner"):
                raise PermissionError("cannot elevate existing role")
            users[uid] = "owner"
            state["pending"] = [p for p in state["pending"] if p["uid"] != uid]
            self._write(state)
            return "owner"

    def request_viewer(self, uid, label=""):
        if not valid_id(uid):
            raise PermissionError("invalid HA ID")
        if not isinstance(label, str) or len(label) > 64 or any(not c.isprintable() for c in label):
            raise ValueError("invalid display label")
        label = label.strip() or "Házikó-felhasználó"
        with self.lock:
            state = self.state()
            if uid in state["users"]:
                return "granted"
            if any(p["uid"] == uid for p in state["pending"]):
                return "pending"
            if len(state["pending"]) >= 25:
                raise PermissionError("pending request limit reached")
            state["pending"].append({"uid": uid, "label": label, "requested_at": int(time.time())})
            self._write(state)
            return "pending"

    def view_for_owner(self):
        state = self.state()
        return {
            "pending": state["pending"],
            "users": [{"uid": u, "role": r} for u, r in state["users"].items()],
        }

    def approve_viewer(self, uid):
        if not valid_id(uid):
            raise PermissionError("invalid HA ID")
        with self.lock:
            state = self.state()
            if not any(p["uid"] == uid for p in state["pending"]):
                raise PermissionError("no pending request")
            if uid in state["users"]:
                raise PermissionError("already authorized")
            state["users"][uid] = "viewer"
            state["pending"] = [p for p in state["pending"] if p["uid"] != uid]
            self._write(state)
            return "viewer"

    def revoke_viewer(self, uid):
        with self.lock:
            state = self.state()
            if state["users"].get(uid) != "viewer":
                raise PermissionError("only viewer roles may be revoked")
            state["users"].pop(uid)
            self._write(state)
            return True
