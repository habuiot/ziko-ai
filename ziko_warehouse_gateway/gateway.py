#!/usr/bin/env python3
"""ZIKO Warehouse HA Supervisor Ingress-only proxy. Separate Warehouse auth."""
import http.client
import ipaddress
import re
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, unquote

BACKEND_HOST = '192.168.10.74'
BACKEND_PORT = 8788
LISTEN_PORT = 8099
SUPERVISOR_PEER = '172.30.32.2'
PREFIX_RE = re.compile(r'^/api/hassio_ingress/[A-Za-z0-9_-]{8,200}/$')
UID_RE = re.compile(r'^/i/[0-9a-f]{24}$')
ASSETS = frozenset({'/', '/index.html', '/health', '/app.js', '/app.css',
    '/vision2126.js', '/vision2126.css', '/photo-station.js',
    '/photo-station.css', '/usability2126.js', '/usability2126.css',
    '/account2126.js', '/account2126.css',
    '/site.webmanifest', '/mobile-icon-180.png', '/mobile-icon-192.png', '/mobile-icon-512.png'})
MAX_REQUEST = 11 * 1024 * 1024
MAX_RESPONSE = 15 * 1024 * 1024

class BodyError(ValueError):
    def __init__(self, code, reason):
        super().__init__(reason)
        self.code = code
        self.reason = reason

def read_body(headers, stream):
    """Decode a bounded HTTP/1.1 request body before forwarding as Content-Length.

    Supervisor Ingress streams browser JSON POSTs using Transfer-Encoding: chunked.
    Reject ambiguous CL+TE framing, non-chunked transfer codings and trailers.
    """
    transfer = headers.get_all('Transfer-Encoding', [])
    lengths = headers.get_all('Content-Length', [])
    if transfer:
        if len(transfer) != 1 or transfer[0].strip().lower() != 'chunked' or lengths:
            raise BodyError(400, 'invalid_transfer_framing')
        chunks = []
        received = 0
        while True:
            line = stream.readline(128)
            if not line.endswith(b'\r\n'):
                raise BodyError(400, 'invalid_chunk_header')
            # Reject chunk extensions to avoid an unnecessarily broad parser.
            size_text = line[:-2]
            if not re.fullmatch(rb'[0-9A-Fa-f]{1,16}', size_text):
                raise BodyError(400, 'invalid_chunk_size')
            length = int(size_text, 16)
            if length == 0:
                if stream.read(2) != b'\r\n':
                    raise BodyError(400, 'unsupported_chunk_trailers')
                return b''.join(chunks)
            if length > MAX_REQUEST - received:
                raise BodyError(413, 'request_too_large')
            data = stream.read(length)
            if len(data) != length:
                raise BodyError(400, 'incomplete_chunk')
            if stream.read(2) != b'\r\n':
                raise BodyError(400, 'missing_chunk_delimiter')
            received += length
            chunks.append(data)
    if len(lengths) > 1:
        raise BodyError(400, 'ambiguous_content_length')
    if not lengths:
        return None
    try:
        size = int(lengths[0])
    except ValueError:
        raise BodyError(400, 'invalid_length')
    if size < 0:
        raise BodyError(400, 'invalid_length')
    if size > MAX_REQUEST:
        raise BodyError(413, 'request_too_large')
    if size == 0:
        return None
    data = stream.read(size)
    if len(data) != size:
        raise BodyError(400, 'incomplete_body')
    return data

def authorized(peer, headers):
    try:
        if ipaddress.ip_address(peer) != ipaddress.ip_address(SUPERVISOR_PEER):
            return False
    except ValueError:
        return False
    uid = headers.get('X-Remote-User-Id', '')
    return isinstance(uid, str) and 0 < len(uid) <= 128 and all(33 <= ord(c) <= 126 for c in uid)

def ingress_path(headers):
    prefix = (headers.get('X-Ingress-Path') or '').rstrip('/') + '/'
    return prefix if PREFIX_RE.fullmatch(prefix) else None

def valid_path(path):
    if not path.startswith('/') or path.startswith('//') or len(path) > 500:
        return False
    if any(c in path for c in ('\\', '\r', '\n', '\x00', '#', '%')):
        return False
    if any(x in ('.', '..') for x in unquote(path).split('/')):
        return False
    return path in ASSETS or path.startswith('/api/') or bool(UID_RE.fullmatch(path))

def cookie_for_backend(header):
    try:
        parsed = SimpleCookie()
        parsed.load(header or '')
        val = parsed.get('warehouse_session')
        return 'warehouse_session=' + val.value if val else None
    except Exception:
        return None

def cookie_for_browser(original, prefix, secure=False):
    # Do not expose the Warehouse session cookie outside this Ingress path.
    try:
        cookie = SimpleCookie()
        cookie.load(original)
        val = cookie.get('warehouse_session')
        if not val:
            return None
        result = 'warehouse_session=' + val.value + '; Path=' + prefix + '; HttpOnly; SameSite=Strict'
        return result + ('; Secure' if secure else '')
    except Exception:
        return None

class Handler(BaseHTTPRequestHandler):
    server_version = 'ZIKO-Warehouse-Ingress/0.1.4'
    sys_version = ''

    def log_message(self, fmt, *args):
        pass  # Never log Ingress session tokens, filenames or passwords.

    def deny(self, code, reason):
        if self.command == 'POST':
            print('WAREHOUSE_INGRESS_POST_DENIED', code, reason, flush=True)
        body = reason.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def do_GET(self): self.proxy()
    def do_HEAD(self): self.proxy()
    def do_POST(self): self.proxy()
    def do_PATCH(self): self.proxy()
    def do_DELETE(self): self.proxy()

    def proxy(self):
        if not authorized(self.client_address[0], self.headers):
            return self.deny(403, 'ingress_auth_required')
        prefix = ingress_path(self.headers)
        if prefix is None:
            return self.deny(403, 'ingress_context_required')
        u = urlsplit(self.path)
        if u.scheme or u.netloc or not valid_path(u.path or '/') or len(u.query) > 3000:
            return self.deny(400, 'invalid_route')
        path = (u.path or '/') + (('?' + u.query) if u.query else '')
        # Supervisor verifies the HA user. Do not forward HA auth cookies.
        # Warehouse keeps HttpOnly session cookies + explicit CSRF checks.
        # HA Origin is not passed to the different private upstream hostname.
        headers = {'Host': BACKEND_HOST + ':' + str(BACKEND_PORT),
                   'Accept': self.headers.get('Accept', '*/*'),
                   'Connection': 'close'}
        for key in ('Content-Type', 'X-CSRF-Token', 'Range', 'If-None-Match'):
            val = self.headers.get(key)
            if val is not None:
                headers[key] = val
        cookie = cookie_for_backend(self.headers.get('Cookie'))
        if cookie:
            headers['Cookie'] = cookie
        try:
            data = read_body(self.headers, self.rfile)
        except BodyError as error:
            return self.deny(error.code, error.reason)
        conn = None
        try:
            conn = http.client.HTTPConnection(BACKEND_HOST, BACKEND_PORT, timeout=25)
            conn.request(self.command, path, body=data, headers=headers)
            upstream = conn.getresponse()
            if self.command == 'POST':
                print('WAREHOUSE_INGRESS_POST_UPSTREAM', upstream.status, flush=True)
            body = upstream.read(MAX_RESPONSE + 1)
            if len(body) > MAX_RESPONSE:
                return self.deny(502, 'upstream_response_too_large')
            self.send_response(upstream.status)
            for key in ('Content-Type', 'Content-Disposition', 'ETag', 'Last-Modified'):
                for value in upstream.headers.get_all(key, []):
                    self.send_header(key, value)
            for raw in upstream.headers.get_all('Set-Cookie', []):
                newcookie = cookie_for_browser(raw, prefix,
                    self.headers.get('X-Forwarded-Proto', '').lower() == 'https')
                if newcookie:
                    self.send_header('Set-Cookie', newcookie)
            redir = upstream.headers.get('Location')
            if redir:
                if redir.startswith('/?inventory='):
                    self.send_header('Location', prefix + redir[1:])
                else:
                    self.send_header('Location', prefix)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Frame-Options', 'SAMEORIGIN')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'same-origin')
            self.send_header('Content-Security-Policy',
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: blob:; connect-src 'self'; media-src 'self' blob:; "
                "font-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'self'")
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(body)
        except (OSError, TimeoutError, http.client.HTTPException):
            try:
                self.deny(502, 'warehouse_unavailable')
            except (OSError, RuntimeError):
                pass
        finally:
            if conn is not None:
                conn.close()

if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', LISTEN_PORT), Handler).serve_forever()
