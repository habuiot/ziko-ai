"""ZDR1-27 Command task reply pilot: per-user privacy and no task writes."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from engine import CommandStore
import server
from test_server import MockRequest


class TaskThreadTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.old = server.STORE
        server.STORE = CommandStore(Path(self.dir.name) / "commands.sqlite3")
        self.addCleanup(setattr, server, "STORE", self.old)
        self.root = server.STORE.submit_message("alice", "Kérdés Zikónak", "original-1")["id"]

    def call(self,user="alice",route="/api/messages/replies",payload=None,
             method="POST",headers=None,peer="172.30.32.2"):
        req = MockRequest(path=route, user=user, peer=peer, method=method,
                          payload=payload,headers=headers)
        (req.do_POST if method=="POST" else req.do_GET)()
        return req

    def test_owner_reply_and_api_roundtrip(self):
        data={"parent_id":self.root,"text":"Javaslom a következő lépést.","client_key":"reply-key-1"}
        res=self.call(payload=data)
        self.assertEqual(res.status,202)
        self.assertEqual(res.response["state"],"awaiting_ai")
        get=self.call(route="/api/messages",method="GET")
        self.assertEqual(get.status,200)
        self.assertEqual(get.response["messages"][0]["replies"][0]["text"],data["text"])
        self.assertEqual(get.response["messages"][0]["status"],"awaiting_ai")

    def test_idempotent_retry_does_not_create_duplicate(self):
        data={"parent_id":self.root,"text":"Igen","client_key":"repeat-key"}
        a=self.call(payload=data); b=self.call(payload=data)
        self.assertEqual(a.response["id"],b.response["id"])
        self.assertEqual(len(server.STORE.message_threads("alice")[0]["replies"]),1)

    def test_reuse_key_conflicting_text_fails_closed(self):
        self.call(payload={"parent_id":self.root,"text":"Igen","client_key":"one"})
        out=self.call(payload={"parent_id":self.root,"text":"Nem","client_key":"one"})
        self.assertEqual(out.status,400)
        self.assertEqual(len(server.STORE.message_threads("alice")[0]["replies"]),1)

    def test_cross_user_reply_cannot_modify_other_users_thread(self):
        out=self.call(user="bob",payload={"parent_id":self.root,"text":"bad","client_key":"other"})
        self.assertEqual(out.status,400)
        self.assertEqual(server.STORE.message_threads("bob"),[])
        self.assertEqual(server.STORE.message_threads("alice")[0]["replies"],[])

    def test_invalid_parent_rejected(self):
        out=self.call(payload={"parent_id":"anything","text":"bad","client_key":"a"})
        self.assertEqual(out.status,400)

    def test_cross_site_csrf_rejected(self):
        out=self.call(payload={"parent_id":self.root,"text":"bad","client_key":"csrf"},
                      headers={"Sec-Fetch-Site":"cross-site"})
        self.assertEqual(out.status,403)

    def test_origin_spoofing_rejected(self):
        out=self.call(peer="192.168.10.112",payload={"parent_id":self.root,"text":"bad","client_key":"spoof"})
        self.assertEqual(out.status,403)

    def test_strict_reply_fields_no_permissions_switch(self):
        out=self.call(payload={"parent_id":self.root,"text":"okay",
                               "client_key":"strict","approved":True})
        self.assertEqual(out.status,400)

    def test_html_payload_not_inserted_into_template(self):
        evil="<img src=x onerror=alert(1)>"
        out=self.call(payload={"parent_id":self.root,"text":evil,"client_key":"xss"})
        self.assertEqual(out.status,202)
        self.assertEqual(server.STORE.message_threads("alice")[0]["replies"][0]["text"],evil)
        js=(server.WEB/"app.js").read_text()
        self.assertIn('item.textContent=',js)
        self.assertNotIn("innerHTML",js)

    def test_length_rejected(self):
        out=self.call(payload={"parent_id":self.root,"text":"a"*1201,"client_key":"long"})
        self.assertEqual(out.status,400)

    def test_reply_persists_across_store_reopen(self):
        server.STORE.reply_to_message("alice",self.root,"Találkozón beszéljük","reopen")
        after=CommandStore(server.STORE.path)
        self.assertEqual(after.message_threads("alice")[0]["replies"][0]["text"],"Találkozón beszéljük")


if __name__=="__main__":
    unittest.main()
