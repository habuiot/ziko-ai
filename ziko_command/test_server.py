"""Command Ingress API: spoofing, CSRF, cross-user privacy and safe intake."""
from __future__ import annotations
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest

import server
from engine import CommandStore


class MockRequest(server.App):
    def __init__(self,path="/api/messages",user="alice",peer="172.30.32.2",
                 method="GET",payload=None,headers=None):
        self.path=path
        self.client_address=(peer,1234)
        self.command=method
        self.response=None
        self.status=None
        body=json.dumps(payload if payload is not None else {}).encode("utf-8")
        self.rfile=io.BytesIO(body)
        self.headers={"Content-Type":"application/json",
                      "Content-Length":str(len(body)),"X-Ziko-Request":"1"}
        if user is not None:
            self.headers["X-Remote-User-Id"]=user
        if headers:
            self.headers.update(headers)

    def send(self,status,body,mimetype):
        self.status=status
        self.response=body

    def json(self,status,payload):
        self.status=status
        self.response=payload


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.previous_store=server.STORE
        self.previous_runner=server.RUNNER
        server.STORE=CommandStore(Path(self.temp.name)/"command.sqlite3")
        class Running:
            @staticmethod
            def is_alive():return True
        server.RUNNER=Running()
        self.addCleanup(setattr,server,"STORE",self.previous_store)
        self.addCleanup(setattr,server,"RUNNER",self.previous_runner)

    def call(self,**kwargs):
        req=MockRequest(**kwargs)
        if req.command=="POST":
            req.do_POST()
        else:
            req.do_GET()
        return req

    def test_ingress_only_rejects_forged_identity(self):
        r=self.call(user="admin",peer="192.168.10.22",path="/api/status")
        self.assertEqual(r.status,403)

    def test_no_identity_denied(self):
        r=self.call(user=None,path="/api/status")
        self.assertEqual(r.status,403)

    def test_strict_user_id_length(self):
        self.assertIsNone(server.trusted("172.30.32.2",{"X-Remote-User-Id":"a"*129}))
        self.assertIsNone(server.trusted("172.30.32.2",{"X-Remote-User-Id":"a\nb"}))

    def test_status_does_not_claim_ai_connected(self):
        r=self.call(path="/api/status")
        self.assertEqual(r.status,200)
        self.assertFalse(r.response["ai_executor_connected"])
        self.assertFalse(r.response["todo_linked"])
        self.assertEqual(r.response["service"],"active")

    def test_message_submission_is_durable(self):
        r=self.call(method="POST",payload={"text":" Ziko, nézd át a tervet ","client_key":"key1"})
        self.assertEqual(r.status,202)
        self.assertEqual(r.response["state"],"awaiting_ai")
        get=self.call(path="/api/messages")
        self.assertEqual(get.status,200)
        self.assertEqual(get.response["messages"][0]["text"],"Ziko, nézd át a tervet")

    def test_message_submit_retry_idempotent(self):
        data={"text":"Egyeztetés","client_key":"repeat1"}
        a=self.call(method="POST",payload=data)
        b=self.call(method="POST",payload=data)
        self.assertEqual(a.response["id"],b.response["id"])
        self.assertEqual(len(self.call(path="/api/messages").response["messages"]),1)

    def test_user_separation(self):
        data={"text":"Titkos terv","client_key":"mykey"}
        self.call(method="POST",payload=data,user="alice")
        self.assertEqual(self.call(path="/api/messages",user="bob").response["messages"],[])

    def test_csrf_header_required(self):
        r=self.call(method="POST",payload={"text":"hello","client_key":"key"},
                    headers={"X-Ziko-Request":""})
        self.assertEqual(r.status,403)

    def test_cross_site_request_rejected(self):
        r=self.call(method="POST",payload={"text":"hello","client_key":"key"},
                    headers={"Sec-Fetch-Site":"cross-site"})
        self.assertEqual(r.status,403)

    def test_unknown_write_endpoints_forbidden(self):
        r=self.call(path="/api/approvals",method="POST",
                    payload={"approved":True})
        self.assertEqual(r.status,405)

    def test_work_queue_not_exposed_without_operator_acl(self):
        r=self.call(path="/api/work")
        self.assertEqual(r.status,403)

    def test_reject_html_submission_no_execution(self):
        r=self.call(method="POST",payload={"text":"<script>alert(1)</script>","client_key":"xss"})
        self.assertEqual(r.status,202)
        m=self.call(path="/api/messages").response["messages"][0]
        self.assertEqual(m["text"],"<script>alert(1)</script>")
        # This is JSON data. The browser constructs DOM with textContent only.
        self.assertNotIn("<script", (server.WEB/"index.html").read_text())
        self.assertIn("body.textContent", (server.WEB/"app.js").read_text())

    def test_route_does_not_return_unmapped_file(self):
        r=self.call(path="/../etc/passwd")
        self.assertEqual(r.status,404)

    def test_bounded_message_length(self):
        r=self.call(method="POST",payload={"text":"x"*2001,"client_key":"too-long"})
        self.assertEqual(r.status,400)

    def test_static_web_ui_served_only_via_ingress(self):
        r=self.call(path="/")
        self.assertEqual(r.status,200)
        self.assertIn(b"ZIKO",r.response)
        s=self.call(path="/",peer="127.0.0.1")
        self.assertEqual(s.status,403)


if __name__=="__main__":
    unittest.main()
