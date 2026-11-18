#!/usr/bin/env python3
"""ZIKO Whiteboard — restricted Home Assistant Ingress reverse proxy.

One existing CT107 WBO engine, no second database or exposed host port.
Supervisor HA user authentication is mandatory before forwarding.
"""
import http.client
import ipaddress
import os
import re
import select
import socket
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

BACKEND = "192.168.10.18"
BACKEND_PORT = 80
LISTEN_PORT = 8097
SUPERVISOR_PEER = "172.30.32.2"
PREFIX = re.compile(r"/api/hassio_ingress/[A-Za-z0-9_-]{8,200}/")
COOKIE_NAME = "wbo-user-secret-v1"
MAX_BODY = 12 * 1024 * 1024
MAX_QUERY = 4096
MAX_PATH = 800
HTTP_FORWARD = ("Content-Type", "Accept", "Accept-Language",
                "Range", "If-None-Match", "If-Modified-Since",
                "X-ZIKO-Action", "Sec-Fetch-Dest")
WS_FORWARD = ("Sec-WebSocket-Key", "Sec-WebSocket-Version",
              "Sec-WebSocket-Extensions", "Sec-WebSocket-Protocol")

def valid_identity(peer, headers):
    try:
        if ipaddress.ip_address(peer) != ipaddress.ip_address(SUPERVISOR_PEER):
            return False
    except ValueError:
        return False
    user = headers.get("X-Remote-User-Id", "")
    return bool(user) and len(user) <= 128 and all(33 <= ord(c) <= 126 for c in user)

def ingress_prefix(headers):
    value = (headers.get("X-Ingress-Path") or "").rstrip("/") + "/"
    return value if PREFIX.fullmatch(value) else None

def valid_request_path(raw):
    path = urlsplit(raw)
    if path.scheme or path.netloc or path.fragment or len(raw) > MAX_PATH + MAX_QUERY:
        return False
    p = path.path or "/"
    if len(p) > MAX_PATH or len(path.query) > MAX_QUERY:
        return False
    if not p.startswith("/") or p.startswith("//") or "\x00" in p or "\\" in p:
        return False
    dec = unquote(p)
    if any(x in (".", "..") for x in dec.split("/")):
        return False
    if "\\" in dec or "\x00" in dec or dec.startswith("//"):
        return False
    # An immutable backend IP is used, with a small set of WBO and controller routes.
    return (
        p in ("/", "/favicon.ico", "/favicon.svg", "/manifest.json", "/board.css",
              "/index.css", "/healthz", "/robots.txt", "/rules", "/random")
        or p.startswith(("/boards/", "/js/", "/tools/", "/socket.io/",
                         "/ziko-api/", "/rules/", "/download/", "/preview/",
                         "/export/", "/assets/"))
        or bool(re.fullmatch(r"/[A-Za-z0-9_-]+\.(?:svg|png|ico|jpg|jpeg|js|css|webmanifest)", p))
    )

def browser_cookie(raw):
    try:
        cookie = SimpleCookie()
        cookie.load(raw or "")
        morsel = cookie.get(COOKIE_NAME)
        return COOKIE_NAME + "=" + morsel.value if morsel else None
    except Exception:
        return None

def scoped_cookie(raw, prefix, secure):
    try:
        cookie = SimpleCookie()
        cookie.load(raw)
        morsel = cookie.get(COOKIE_NAME)
        if not morsel:
            return None
        if not re.fullmatch(r"[a-z0-9_-]{1,256}", morsel.value, re.I):
            return None
        result = COOKIE_NAME + "=" + morsel.value + "; Path=" + prefix + "; HttpOnly; SameSite=Lax"
        return result + ("; Secure" if secure else "")
    except Exception:
        return None

def content_body(stream, headers):
    transfers = headers.get_all("Transfer-Encoding", [])
    lengths = headers.get_all("Content-Length", [])
    if transfers:
        if len(transfers) != 1 or transfers[0].strip().lower() != "chunked" or lengths:
            raise ValueError("invalid_transfer_encoding")
        chunks = []
        received = 0
        while True:
            size_line = stream.readline(80)
            if not size_line.endswith(b"\r\n") or not re.fullmatch(rb"[0-9a-fA-F]{1,12}", size_line[:-2]):
                raise ValueError("invalid_chunk_size")
            length = int(size_line[:-2], 16)
            if length == 0:
                if stream.read(2) != b"\r\n":
                    raise ValueError("chunk_trailers_not_supported")
                return b"".join(chunks)
            if length > MAX_BODY - received:
                raise OverflowError()
            chunk = stream.read(length)
            if len(chunk) != length or stream.read(2) != b"\r\n":
                raise ValueError("invalid_chunk_content")
            received += length
            chunks.append(chunk)
    if len(lengths) > 1:
        raise ValueError("ambiguous_length")
    if not lengths:
        return None
    try:
        size = int(lengths[0])
    except ValueError as error:
        raise ValueError("bad_length") from error
    if not 0 <= size <= MAX_BODY:
        raise OverflowError()
    data = stream.read(size)
    if len(data) != size:
        raise ValueError("truncated_body")
    return data

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ZIKO-Whiteboard-HA-Ingress/0.5.0"
    sys_version = ""

    def log_message(self, fmt, *args):
        # Never log HA ingress access tokens or user IDs.
        pass

    def answer(self, status, reason):
        data = reason.encode("utf8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def do_GET(self): self.handle_request()
    def do_HEAD(self): self.handle_request()
    def do_POST(self): self.handle_request()

    def handle_request(self):
        if not valid_identity(self.client_address[0], self.headers):
            return self.answer(403, "ingress_identity_required")
        prefix = ingress_prefix(self.headers)
        if prefix is None:
            return self.answer(403, "ingress_context_required")
        if not valid_request_path(self.path):
            return self.answer(400, "invalid_route")
        upgrade = self.headers.get("Upgrade", "").lower()
        if upgrade == "websocket":
            if self.command != "GET" or not self.path.startswith("/socket.io/"):
                return self.answer(400, "websocket_route_not_allowed")
            return self.proxy_websocket()
        return self.proxy_http(prefix)

    def proxy_http(self, prefix):
        conn = None
        sent = False
        try:
            data = content_body(self.rfile, self.headers)
            headers = {"Host": BACKEND, "Connection": "close", "Accept-Encoding": "identity"}
            for key in HTTP_FORWARD:
                value = self.headers.get(key)
                if value:
                    headers[key] = value
            cookie = browser_cookie(self.headers.get("Cookie"))
            if cookie:
                headers["Cookie"] = cookie
            if self.command == "POST":
                # Supervisor session is validated above; preserve the existing
                # ZIKO controller's explicit origin/header CSRF validation.
                headers["Origin"] = "http://" + BACKEND
            conn = http.client.HTTPConnection(BACKEND, BACKEND_PORT, timeout=90)
            conn.request(self.command, self.path, data, headers=headers)
            response = conn.getresponse()
            length = response.headers.get("Content-Length")
            has_length = length is not None and length.isdigit()
            self.send_response(response.status)
            for key in ("Content-Type", "Content-Disposition", "ETag",
                        "Last-Modified", "Content-Range"):
                val = response.headers.get(key)
                if val is not None:
                    self.send_header(key, val)
            for raw in response.headers.get_all("Set-Cookie", []):
                value = scoped_cookie(
                    raw, prefix, self.headers.get("X-Forwarded-Proto", "").lower() == "https")
                if value:
                    self.send_header("Set-Cookie", value)
            location = response.headers.get("Location")
            if location:
                parsed = urlsplit(location)
                if not parsed.scheme and not parsed.netloc and parsed.path.startswith("/"):
                    self.send_header("Location", prefix + location.lstrip("/"))
            self.send_header("Content-Length", length if has_length else "0") if self.command == "HEAD" else None
            streamed = not has_length and self.command != "HEAD"
            if has_length and self.command != "HEAD":
                self.send_header("Content-Length", length)
            if streamed:
                self.send_header("Transfer-Encoding", "chunked")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "same-origin")
            self.send_header("X-Frame-Options", "SAMEORIGIN")
            # The upstream currently embeds JS/CSS in its HTML; allow only
            # same-origin code, including its existing inline bootstrap.
            self.send_header("Content-Security-Policy",
                "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
                "connect-src 'self' wss: ws:; font-src 'self' data:; "
                "frame-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'")
            self.end_headers()
            sent = True
            if self.command == "HEAD":
                return
            while True:
                chunk = response.read1(65536)
                if not chunk:
                    break
                if streamed:
                    self.wfile.write(("%x\r\n" % len(chunk)).encode("ascii"))
                    self.wfile.write(chunk + b"\r\n")
                else:
                    self.wfile.write(chunk)
                self.wfile.flush()
            if streamed:
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
        except OverflowError:
            if not sent: self.answer(413, "request_too_large")
        except ValueError:
            if not sent: self.answer(400, "invalid_request")
        except (OSError, TimeoutError, http.client.HTTPException) as error:
            print("WB_INGRESS_BACKEND_ERROR",type(error).__name__,flush=True)
            if not sent:
                try: self.answer(502, "whiteboard_unavailable")
                except OSError: pass
        finally:
            if conn is not None:
                conn.close()
            self.close_connection = True

    def proxy_websocket(self):
        backend = None
        try:
            backend = socket.create_connection((BACKEND, BACKEND_PORT), timeout=10)
            headers = [
                "GET " + self.path + " HTTP/1.1",
                "Host: " + BACKEND,
                "Connection: Upgrade",
                "Upgrade: websocket",
            ]
            for key in WS_FORWARD:
                value = self.headers.get(key)
                if value:
                    headers.append(key + ": " + value)
            cookie = browser_cookie(self.headers.get("Cookie"))
            if cookie:
                headers.append("Cookie: " + cookie)
            headers.append("Origin: http://" + BACKEND)
            backend.sendall(("\r\n".join(headers) + "\r\n\r\n").encode("latin1"))
            header = b""
            while b"\r\n\r\n" not in header and len(header) < 16384:
                block = backend.recv(4096)
                if not block:
                    break
                header += block
            if not header.startswith(b"HTTP/1.1 101 ") and not header.startswith(b"HTTP/1.0 101 "):
                return self.answer(502, "websocket_upgrade_failed")
            # Handshake and the earliest binary frames are relayed verbatim.
            self.connection.sendall(header)
            backend.settimeout(None)
            self.connection.settimeout(None)
            self.close_connection = True
            while True:
                ready, _, _ = select.select([backend, self.connection], [], [], 240)
                if not ready:
                    break
                for source in ready:
                    chunk = source.recv(65536)
                    if not chunk:
                        return
                    (self.connection if source is backend else backend).sendall(chunk)
        except (OSError, TimeoutError) as error:
            print("WB_INGRESS_WS_ERROR",type(error).__name__,flush=True)
        finally:
            if backend is not None:
                backend.close()
            self.close_connection = True

if __name__ == "__main__":
    # QA can run against localhost only in a copied script with patched
    # constants. Production never accepts anonymous LAN traffic.
    ThreadingHTTPServer(("0.0.0.0", LISTEN_PORT), Handler).serve_forever()
