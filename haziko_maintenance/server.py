"""Read-only Home Assistant maintenance inventory. No command execution."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LOCAL = Path("/local_apps/ziko_ai")
SHARE = Path("/share")
SUPERVISOR_INGRESS_IP = "172.30.32.2"


def legacy_source():
    if LOCAL.is_symlink():
        return {"present": True, "version": None, "status": "symlink_refused"}
    if not LOCAL.is_dir():
        return {"present": False, "version": None, "status": "absent"}
    config = LOCAL / "config.yaml"
    if config.is_symlink() or not config.is_file() or config.stat().st_size > 8192:
        return {"present": True, "version": None, "status": "unrecognized"}
    import re
    data = config.read_text(encoding="utf-8")
    slug = re.search(r'^\s*slug:\s*["\x27]?([a-z0-9_]+)["\x27]?\s*(?:#.*)?$', data, re.M)
    ver = re.search(r'^\s*version:\s*["\x27]?([0-9A-Za-z_.-]+)["\x27]?\s*(?:#.*)?$', data, re.M)
    if not slug or slug.group(1) != "ziko_ai":
        return {"present": True, "version": None, "status": "unexpected_slug"}
    return {"present": True, "version": ver.group(1) if ver else None, "status": "identified"}


def inventory():
    shares = {"legacy_named_entries": 0, "archive_directory_present": False}
    if SHARE.is_dir():
        shares["legacy_named_entries"] = sum(
            1 for p in SHARE.iterdir()
            if p.name.startswith(("ziko_ai_", "Ziko_"))
        )
        shares["archive_directory_present"] = (SHARE / "ziko_legacy_archives").is_dir()
    return {
        "schema_version": 1,
        "legacy_local_app": legacy_source(),
        "shared_files": shares,
        "read_only": True,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "HazikoReadOnly/0.1.0"

    def log_message(self, *_):
        return

    def json_reply(self, code, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.client_address[0] != SUPERVISOR_INGRESS_IP:
            return self.json_reply(403, {"error": "ingress_only"})
        path = self.path.split("?", 1)[0].rstrip("/")
        if path in ("", "/", "/api/v1/health"):
            return self.json_reply(200, {"status": "ok", "read_only": True})
        if path == "/api/v1/inventory":
            try:
                return self.json_reply(200, inventory())
            except (OSError, UnicodeError):
                return self.json_reply(500, {"error": "inventory_unavailable"})
        return self.json_reply(404, {"error": "not_found"})

    def do_POST(self):
        self.json_reply(405, {"error": "read_only"})

    do_PUT = do_POST
    do_PATCH = do_POST
    do_DELETE = do_POST


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8096), Handler).serve_forever()
