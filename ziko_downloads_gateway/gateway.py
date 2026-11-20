#!/usr/bin/env python3
"""Authenticated HA Ingress -> CT108 ZIKO Downloads; no browser admin key."""
from __future__ import annotations
import hashlib
import hmac
import http.client
import ipaddress
import json
import logging
import re
import secrets
import ssl
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit,unquote

LISTEN_PORT=8097
BACKEND_PORT=8791
SUPERVISOR_PEER="172.30.32.2"
CONFIG_FILE=Path("/tmp/zdl-options.json")
CERT_FILE=Path(__file__).with_name("backend.crt")
PIN_SHA256="1f12760262d16a14fe52926fde1bd6a29426a646f58c88738cc7770249c17423"
INGRESS_RE=re.compile(r"/api/hassio_ingress/[A-Za-z0-9_-]{8,200}/")
HA_UID=re.compile(r"[A-Za-z0-9_-]{8,128}")
FILE_ID=re.compile(r"/d/[A-Za-z0-9_-]{30,80}")
FILE_OP=re.compile(r"/api/files/[A-Za-z0-9_-]{30,80}/(?:schedule|restore|permanent)")
MAX_FILE=2*1024**3
MAX_HTML=3*1024**2
LOG=logging.getLogger("ziko-downloads-ingress")

class GateError(ValueError):
    def __init__(self,status,reason):
        super().__init__(reason)
        self.status=status
        self.reason=reason

def settings():
    obj=json.loads(CONFIG_FILE.read_text("utf-8"))
    key=obj.get("sso_key","")
    host=obj.get("backend_host","192.168.10.188")
    if not isinstance(key,str) or not re.fullmatch(r"[0-9a-f]{64}",key):
        raise GateError(503,"gateway_sso_unconfigured")
    try:
        ip=ipaddress.ip_address(host)
        if not isinstance(ip,ipaddress.IPv4Address) or not ip.is_private or ip.is_loopback:
            raise ValueError("invalid private backend host")
    except (ValueError,TypeError):
        raise GateError(503,"gateway_backend_invalid")
    return key,host

def authorized(peer,headers):
    try:
        if ipaddress.ip_address(peer)!=ipaddress.ip_address(SUPERVISOR_PEER):
            return False
    except (ValueError,TypeError):
        return False
    uid=headers.get("X-Remote-User-Id","")
    return isinstance(uid,str) and bool(HA_UID.fullmatch(uid))

def ingress_prefix(headers):
    p=(headers.get("X-Ingress-Path") or "").rstrip("/")+"/"
    return p if INGRESS_RE.fullmatch(p) else None

def route_allowed(method,path):
    if not isinstance(path,str) or not path.startswith("/") or path.startswith("//") or len(path)>350:
        return False
    if any(ord(c)<32 or ord(c)==127 for c in path) or any(c in path for c in ("\\","#","%")):
        return False
    if any(p in (".","..") for p in unquote(path).split("/")):
        return False
    if method in ("GET","HEAD"):
        return path in ("/","/health","/api/files") or bool(FILE_ID.fullmatch(path))
    if method=="POST":
        return path=="/api/upload" or bool(FILE_OP.fullmatch(path))
    return False

def signed_headers(key,uid,method,path):
    ts=str(int(time.time()))
    nonce=secrets.token_hex(16)
    payload="\n".join((uid,ts,nonce,method,path)).encode()
    signature=hmac.new(bytes.fromhex(key),payload,hashlib.sha256).hexdigest()
    return {"X-ZDL-SSO-User":uid,"X-ZDL-SSO-Time":ts,
            "X-ZDL-SSO-Nonce":nonce,"X-ZDL-SSO-Signature":signature}

def body_framing(headers,method,path):
    transfer=headers.get_all("Transfer-Encoding",[])
    lengths=headers.get_all("Content-Length",[])
    if len(transfer)>1 or len(lengths)>1:
        raise GateError(400,"ambiguous_body_headers")
    if transfer and (transfer[0].strip().lower()!="chunked" or lengths):
        raise GateError(400,"unsupported_body_framing")
    if lengths:
        try:size=int(lengths[0])
        except (ValueError,TypeError):raise GateError(400,"invalid_content_length")
    elif method=="POST" and path=="/api/upload":
        try:size=int(headers.get("X-Upload-Size"))
        except (ValueError,TypeError):raise GateError(411,"upload_size_required")
    else:size=0
    if size<0 or size>MAX_FILE:
        raise GateError(413,"upload_too_large")
    if path=="/api/upload":
        claimed=headers.get("X-Upload-Size")
        if claimed is not None and str(size)!=claimed:
            raise GateError(400,"upload_size_mismatch")
    elif size:
        raise GateError(400,"unexpected_body")
    return size,bool(transfer)

def forward_body(incoming,upstream,size,chunked):
    if not chunked:
        left=size
        while left:
            block=incoming.read(min(256*1024,left))
            if not block:raise GateError(400,"incomplete_body")
            upstream.send(block)
            left-=len(block)
        return
    total=0
    while True:
        line=incoming.readline(128)
        if not re.fullmatch(rb"[0-9a-fA-F]{1,16}\r\n",line or b""):
            raise GateError(400,"invalid_chunk_header")
        n=int(line[:-2],16)
        if not n:
            if incoming.read(2)!=b"\r\n":raise GateError(400,"unexpected_chunk_trailer")
            break
        if total+n>size:raise GateError(400,"upload_size_exceeded")
        left=n
        while left:
            block=incoming.read(min(256*1024,left))
            if not block:raise GateError(400,"incomplete_chunk")
            upstream.send(block)
            left-=len(block)
        if incoming.read(2)!=b"\r\n":raise GateError(400,"invalid_chunk_delimiter")
        total+=n
    if total!=size:raise GateError(400,"incomplete_upload_body")

def rewrite_html(raw,prefix):
    html=raw.decode("utf-8")
    html=html.replace('"/api/', '"'+prefix+'api/')
    html=html.replace('"/d/', '"'+prefix+'d/')
    html=html.replace('+"/d/"','+"'+prefix+'d/"')
    html=html.replace('location="/login"','location.reload()')
    html=html.replace('"X-Folder-Path":encodeURIComponent(folder||""),',
                      '"X-Folder-Path":encodeURIComponent(folder||""),"X-Upload-Size":String(file.size),')
    html=html.replace('id="logout"','id="logout" hidden')
    html=html.replace('PRIVATE LIBRARY · 0.2.8','HÁZIKÓ · KULCS NÉLKÜL')
    return html.encode("utf-8")

class Handler(BaseHTTPRequestHandler):
    server_version="ZIKO-Downloads-Ingress/0.1.0"
    sys_version=""
    protocol_version="HTTP/1.1"
    def log_message(self,fmt,*args):pass
    def error(self,status,message):
        body=message.encode()
        self.send_response(status)
        self.send_header("Content-Type","text/plain; charset=utf-8")
        self.send_header("Content-Length",str(len(body)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Connection","close")
        self.end_headers()
        if self.command!="HEAD":self.wfile.write(body)
    def common(self):
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Referrer-Policy","no-referrer")
        self.send_header("X-Frame-Options","SAMEORIGIN")
        self.send_header("Content-Security-Policy",
          "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
          "connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'self'; "
          "frame-ancestors 'self'")
        self.send_header("Connection","close")
    def do_GET(self):self.proxy()
    def do_HEAD(self):self.proxy()
    def do_POST(self):self.proxy()
    def do_PUT(self):self.error(405,"method_not_allowed")
    def do_DELETE(self):self.error(405,"method_not_allowed")
    def do_PATCH(self):self.error(405,"method_not_allowed")
    def proxy(self):
        if not authorized(self.client_address[0],self.headers):
            return self.error(403,"hass_ingress_identity_required")
        prefix=ingress_prefix(self.headers)
        if not prefix:return self.error(403,"hass_ingress_context_required")
        parsed=urlsplit(self.path)
        if parsed.scheme or parsed.netloc or parsed.query or not route_allowed(self.command,parsed.path or "/"):
            return self.error(404,"route_not_allowed")
        route=parsed.path or "/"
        try:
            key,host=settings()
            size,chunked=body_framing(self.headers,self.command,route)
        except (OSError,ValueError,GateError) as exc:
            return self.error(exc.status if isinstance(exc,GateError) else 503,
                              exc.reason if isinstance(exc,GateError) else "gateway_unavailable")
        outgoing={"Host":host+":"+str(BACKEND_PORT),"Accept":"*/*","Connection":"close"}
        for header in ("Content-Type","X-CSRF","X-Filename","X-Folder-Path","X-Confirm"):
            val=self.headers.get(header)
            if val is not None:outgoing[header]=val
        if self.command=="POST":outgoing["Content-Length"]=str(size)
        outgoing.update(signed_headers(key,self.headers["X-Remote-User-Id"],self.command,route))
        connection=None;started=False
        try:
            ctx=ssl.create_default_context(cafile=str(CERT_FILE))
            connection=http.client.HTTPSConnection(host,BACKEND_PORT,timeout=300,context=ctx)
            connection.connect()
            fingerprint=hashlib.sha256(connection.sock.getpeercert(binary_form=True)).hexdigest()
            if fingerprint!=PIN_SHA256:raise ssl.SSLError("backend_certificate_mismatch")
            connection.putrequest(self.command,route,skip_host=True,skip_accept_encoding=True)
            for h,val in outgoing.items():connection.putheader(h,val)
            connection.endheaders()
            if self.command=="POST":forward_body(self.rfile,connection,size,chunked)
            response=connection.getresponse()
            if route=="/" and self.command=="GET" and response.status==200:
                html=response.read(MAX_HTML+1)
                if len(html)>MAX_HTML:raise GateError(502,"response_too_large")
                body=rewrite_html(html,prefix)
                self.send_response(200)
                self.send_header("Content-Type","text/html; charset=utf-8")
                self.send_header("Content-Length",str(len(body)))
                self.common();self.end_headers();started=True
                self.wfile.write(body)
                return
            self.send_response(response.status)
            for field in ("Content-Type","Content-Length","Content-Disposition","ETag","Last-Modified"):
                for val in response.headers.get_all(field,[]):self.send_header(field,val)
            # No original admin cookies, framing headers, or CT108 CSP escape HA.
            self.common();self.end_headers();started=True
            if self.command!="HEAD":
                while True:
                    block=response.read(256*1024)
                    if not block:break
                    self.wfile.write(block)
        except (OSError,ssl.SSLError,http.client.HTTPException,ValueError,GateError) as ex:
            LOG.warning("upstream_failed_%s",type(ex).__name__)
            if not started:
                try:self.error(ex.status if isinstance(ex,GateError) else 502,
                               ex.reason if isinstance(ex,GateError) else "backend_unavailable")
                except OSError:pass
        finally:
            if connection:connection.close()

def main():
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
    settings()
    ThreadingHTTPServer(("0.0.0.0",LISTEN_PORT),Handler).serve_forever()

if __name__=="__main__":
    main()

