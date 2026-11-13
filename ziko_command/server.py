#!/usr/bin/env python3
"""Ziko Command 0.1 — HA Ingress-only command intake and durable pulse.

No autonomous LLM executor is connected here. Incoming messages are stored
locally, never falsely marked completed or written as ZikoTodo tasks.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from engine import CommandStore, now_ts

log=logging.getLogger("ziko-command")
PORT=int(os.environ.get("ZIKO_COMMAND_PORT","8100"))
PROXY=os.environ.get("ZIKO_TRUSTED_PROXY","172.30.32.2")
DATA=Path(os.environ.get("ZIKO_COMMAND_DB","/data/command.sqlite3"))
WEB=Path(__file__).parent / "web"
STORE=None
RUNNER=None


def trusted(peer: str, headers) -> str | None:
    """Only genuine HA ingress (not a client-provided X-Forwarded-For)."""
    if peer != PROXY:
        return None
    identity=(headers.get("X-Remote-User-Id") or "").strip()
    if not identity or len(identity)>128 or any(not (33<=ord(c)<=126) for c in identity):
        return None
    return identity


def safe_route(raw: str) -> str:
    return urlsplit(raw).path.rstrip("/") or "/"


def command_loop(store: CommandStore, stop: threading.Event, *, period=60) -> None:
    while not stop.is_set():
        try:
            t=now_ts()
            store.heartbeat(t)
            store.sweep(t)
            store.prepare_digest(t, hour=19)
        except Exception:
            # Never log messages, user-provided texts or private project names.
            log.exception("coordinator heartbeat failed")
        stop.wait(period)


class App(BaseHTTPRequestHandler):
    server_version="ZikoCommand"
    sys_version=""

    def send(self, status: int, body: bytes, mimetype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type",mimetype)
        self.send_header("Content-Length",str(len(body)))
        self.send_header("Cache-Control","no-store, max-age=0")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Referrer-Policy","no-referrer")
        self.send_header("X-Frame-Options","SAMEORIGIN")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; connect-src 'self'; script-src 'self'; "
            "style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'; "
            "frame-ancestors 'self'",
        )
        self.end_headers()
        if self.command!="HEAD":
            self.wfile.write(body)

    def json(self,status:int,payload:dict)->None:
        self.send(status,json.dumps(payload,ensure_ascii=False).encode("utf-8"),
                  "application/json; charset=utf-8")

    def _user(self)->str|None:
        return trusted(self.client_address[0],self.headers)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        user=self._user()
        if user is None:
            self.json(403,{"error":"forbidden"})
            return
        path=safe_route(self.path)
        if path=="/":
            self.send(200,(WEB/"index.html").read_bytes(),"text/html; charset=utf-8")
        elif path=="/app.js":
            self.send(200,(WEB/"app.js").read_bytes(),"text/javascript; charset=utf-8")
        elif path=="/style.css":
            self.send(200,(WEB/"style.css").read_bytes(),"text/css; charset=utf-8")
        elif path=="/api/status":
            global RUNNER
            snapshot=STORE.briefing()
            self.json(200,{
                "service":"active" if RUNNER and RUNNER.is_alive() else "degraded",
                "last_heartbeat_at":snapshot["heartbeat_at"],
                "ai_executor_connected":False,
                "ai_execution_enabled":False,
                "todo_linked":False,
                "pending_user_commands":len(STORE.messages(user,limit=100)),
                "safety_mode":"read-only-workflow",
                "next_digest":"19:00 Europe/Budapest",
            })
        elif path=="/api/messages":
            self.json(200,{"messages":STORE.messages(user)})
        elif path=="/api/briefing":
            snapshot=STORE.briefing()
            self.json(200,{
                "at":snapshot["at"],
                "heartbeat_at":snapshot["heartbeat_at"],
                "operator_note":"Ziko AI végrehajtó még nincs összekapcsolva.",
                "own_messages":len(STORE.messages(user,limit=100)),
                "automatic_updates":"A belső jelentés előkészül, de értesítést még nem küld.",
            })
        elif path=="/api/work":
            # Don't expose other users' task/run metadata before user ACL is connected.
            self.json(403,{"error":"work_access_not_configured"})
        else:
            self.json(404,{"error":"not_found"})

    def do_POST(self):
        user=self._user()
        if user is None:
            self.json(403,{"error":"forbidden"})
            return
        if self.headers.get("X-Ziko-Request")!="1" or self.headers.get(
                "Sec-Fetch-Site","").lower()=="cross-site":
            self.json(403,{"error":"request_origin_denied"})
            return
        if safe_route(self.path)!="/api/messages":
            self.json(405,{"error":"write_not_supported"})
            return
        rawsize=self.headers.get("Content-Length","")
        if not rawsize.isdecimal() or int(rawsize)>4096:
            self.json(413,{"error":"invalid_payload_length"})
            return
        if self.headers.get("Content-Type","").split(";")[0].strip()!="application/json":
            self.json(415,{"error":"json_required"})
            return
        try:
            payload=json.loads(self.rfile.read(int(rawsize)))
            if not isinstance(payload,dict):
                raise ValueError("object expected")
            result=STORE.submit_message(
                user,payload.get("text"),payload.get("client_key")
            )
        except (ValueError,TypeError,UnicodeError,RecursionError) as err:
            self.json(400,{"error":"invalid_command","detail":str(err)[:120]})
            return
        self.json(202,{"id":result["id"],"state":result["status"],
                       "note":"Rögzítve. Ziko AI még nem csatlakozott; végrehajtás nem indult."})

    def do_DELETE(self):
        self.json(405,{"error":"write_not_supported"})

    def do_PUT(self):
        self.json(405,{"error":"write_not_supported"})

    def do_PATCH(self):
        self.json(405,{"error":"write_not_supported"})

    def log_message(self, fmt, *args):
        # No URLs, headers or sensitive message contents in logs.
        log.info("request_response=%s", args[1] if len(args)>1 else "?")


def main():
    global STORE,RUNNER
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
    STORE=CommandStore(DATA)
    stopped=threading.Event()
    RUNNER=threading.Thread(target=command_loop,args=(STORE,stopped),
                            name="command-pulse",daemon=True)
    RUNNER.start()
    server=ThreadingHTTPServer(("0.0.0.0",PORT),App)
    try:
        server.serve_forever(poll_interval=.5)
    finally:
        stopped.set()
        server.server_close()
        RUNNER.join(timeout=5)


if __name__=="__main__":
    main()
