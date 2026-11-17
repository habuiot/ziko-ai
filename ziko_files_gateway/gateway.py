#!/usr/bin/env python3
"""ZikoFiles HA Ingress gateway: identity-checking, TLS-pinned CT104 proxy.
The backend still enforces its own password/session and mount permissions.
"""
from __future__ import annotations
import hashlib
import http.client
import ipaddress
import logging
import re
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

BACKEND_HOST = "192.168.10.100"
BACKEND_PORT = 8787
LISTEN_PORT = 8098
SUPERVISOR_PEER = "172.30.32.2"
PIN_SHA256 = "e8ede8fedbf006aac3ec8ceec248910363948006d85c04189d18c29fb3cff68b"
CERT = Path(__file__).with_name("backend.crt")
UPLOAD_LIMIT = 8 * 1024 ** 3 + 1024 * 1024
REQUEST_HEADERS = ("cookie", "content-length", "content-type", "x-zikofiles-request", "accept", "range")
RESPONSE_HEADERS = ("content-length", "content-type", "content-disposition", "cache-control", "etag", "last-modified", "content-range")
INGRESS_RE = re.compile(r"/api/hassio_ingress/[A-Za-z0-9_-]{8,200}/")
LOG = logging.getLogger("ziko-files-ingress")

def ingress_identity(peer: str, headers) -> bool:
    try:
        if ipaddress.ip_address(peer) != ipaddress.ip_address(SUPERVISOR_PEER):
            return False
    except ValueError:
        return False
    uid = headers.get("X-Remote-User-Id", "")
    return isinstance(uid, str) and 0 < len(uid) <= 128 and all(33 <= ord(c) <= 126 for c in uid)

def ingress_prefix(headers) -> str | None:
    prefix = (headers.get("X-Ingress-Path") or "").rstrip("/") + "/"
    return prefix if INGRESS_RE.fullmatch(prefix) else None

def allowed_upstream_path(path: str) -> bool:
    if not path.startswith("/") or path.startswith("//") or any(c in path for c in ("\r", "\n", "\\", "\x00", "#")):
        return False
    decoded = unquote(path)
    if "\\" in decoded or any(segment in (".", "..") for segment in decoded.split("/")):
        return False
    return path == "/" or path.startswith(("/api/", "/static/"))

def rewritten_cookie(cookie: str, prefix: str, secure: bool) -> str | None:
    if not cookie.startswith("ziko_session="):
        return None
    parts = [part.strip() for part in cookie.split(";") if part.strip()]
    parts = [p for p in parts if not p.lower().startswith(("path=", "samesite=")) and p.lower() not in ("secure", "partitioned")]
    parts += ["Path=" + prefix, "SameSite=Lax"]
    if secure:
        parts += ["Secure"]
    return "; ".join(parts)

class Handler(BaseHTTPRequestHandler):
    server_version = "ZikoFiles-Ingress/0.1.0"
    sys_version = ""
    def log_message(self, fmt, *args):
        LOG.info("request completed")  # Never log bearer-like ingress URLs or file paths.
    def reply(self, status: int, body: bytes):
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
    def do_GET(self):
        self.proxy()
    def do_POST(self):
        self.proxy()
    def do_HEAD(self):
        self.proxy()
    def do_PUT(self):
        self.reply(405, b"method_not_allowed")
    def do_DELETE(self):
        self.reply(405, b"method_not_allowed")
    def do_PATCH(self):
        self.reply(405, b"method_not_allowed")
    def proxy(self):
        if not ingress_identity(self.client_address[0], self.headers):
            return self.reply(403, b"forbidden")
        prefix = ingress_prefix(self.headers)
        if not prefix:
            return self.reply(403, b"missing_ingress_context")
        parsed = urlsplit(self.path)
        if not allowed_upstream_path(parsed.path):
            return self.reply(400, b"invalid_path")
        endpoint = parsed.path + ("?" + parsed.query if parsed.query else "")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > UPLOAD_LIMIT:
                return self.reply(413, b"request_too_large")
            if self.command == "POST" and length == 0:
                return self.reply(411, b"missing_content_length")
            if self.headers.get("Transfer-Encoding"):
                return self.reply(400, b"chunked_request_not_supported")
        except ValueError:
            return self.reply(400, b"invalid_content_length")
        conn, headers_sent = None, False
        try:
            context = ssl.create_default_context(cafile=str(CERT))
            conn = http.client.HTTPSConnection(BACKEND_HOST, BACKEND_PORT, timeout=90, context=context)
            conn.connect()
            if hashlib.sha256(conn.sock.getpeercert(binary_form=True)).hexdigest() != PIN_SHA256:
                raise ssl.SSLError("backend_certificate_fingerprint_mismatch")
            conn.putrequest(self.command, endpoint, skip_host=True, skip_accept_encoding=True)
            conn.putheader("Host", BACKEND_HOST)
            conn.putheader("Connection", "close")
            for key in REQUEST_HEADERS:
                val = self.headers.get(key)
                if val is not None:
                    conn.putheader(key, val)
            conn.endheaders()
            remaining = length
            while remaining:
                chunk = self.rfile.read(min(262144, remaining))
                if not chunk:
                    raise OSError("upload_body_incomplete")
                conn.send(chunk)
                remaining -= len(chunk)
            resp = conn.getresponse()
            self.send_response(resp.status)
            for key in RESPONSE_HEADERS:
                for value in resp.headers.get_all(key, []):
                    self.send_header(key, value)
            secure = self.headers.get("X-Forwarded-Proto", "").lower() == "https"
            for original in resp.headers.get_all("Set-Cookie", []):
                cookie = rewritten_cookie(original, prefix, secure)
                if cookie:
                    self.send_header("Set-Cookie", cookie)
            self.send_header("X-Frame-Options", "SAMEORIGIN")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'self'")
            self.send_header("Connection", "close")
            self.end_headers()
            headers_sent = True
            if self.command != "HEAD":
                while True:
                    data = resp.read(262144)
                    if not data:
                        break
                    self.wfile.write(data)
        except (ssl.SSLError, OSError, http.client.HTTPException, ValueError) as exc:
            LOG.warning("backend failure: %s", type(exc).__name__)
            if not headers_sent:
                try:
                    self.reply(502, b"ZikoFiles backend unavailable")
                except OSError:
                    pass
        finally:
            if conn:
                conn.close()

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ThreadingHTTPServer(("0.0.0.0", LISTEN_PORT), Handler).serve_forever()

if __name__ == "__main__":
    main()
