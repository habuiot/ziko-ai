import hashlib
import hmac
import http.client
import json
import os
import pathlib
import secrets
import stat
import sys
import tempfile
import threading
import unittest
from datetime import datetime,timedelta,timezone
from http.server import ThreadingHTTPServer
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from workflow_bridge import (CommandWorkflowBridge,BridgeUnavailable,ApprovalDenied,
                             seal_feed,verify_feed,FEED_SCHEMA)
from server import App,CommandStore

OWNER="ha-user-owner-unit"
OTHER="ha-user-other"
JOB="00000000-0000-4000-8000-000000000001"
SHA="a"*64

def now():return datetime.now(timezone.utc)
def example_feed(status="meeting_ready",generated_at=None):
    return {"schema":FEED_SCHEMA,"generated_at":generated_at or now().isoformat(),
            "source":"isolated-unit-test","job_count":1,
            "model_state":"not_installed","roles":[{"role_id":"ziko","confirmed_active":False}],
            "jobs":[{"job_id":JOB,"work_id":"ziko-workflow",
                     "todo_uid":"existing-canonical-todo","phase":status,
                     "artifact_sha":SHA,"approved":False}]}

class WorkflowBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=pathlib.Path(self.tmp.name)
        self.feed_key=self.root/"feed.key"
        self.approval_key=self.root/"approval.key"
        for file in (self.feed_key,self.approval_key):
            file.write_bytes(secrets.token_bytes(48))
            os.chmod(file,0o600)
        self.feed_path=self.root/"feed.json"
        self.approvals=self.root/"approvals"
        self.approvals.mkdir(mode=0o700)
        self.write_feed()
        self.bridge=CommandWorkflowBridge(self.feed_path,self.feed_key,self.approval_key,
                                          self.approvals,OWNER)
    def tearDown(self):self.tmp.cleanup()
    def write_feed(self,feed=None):
        f=feed if feed is not None else example_feed()
        self.feed_path.write_text(json.dumps(seal_feed(f,self.feed_key.read_bytes())))
        os.chmod(self.feed_path,0o600)

    def test_owner_reads_signed_fresh_feed(self):
        d=self.bridge.read_feed(OWNER)
        self.assertEqual(d["jobs"][0]["phase"],"meeting_ready")
        self.assertEqual(d["model_state"],"not_installed")
    def test_nonowner_rejected(self):
        with self.assertRaises(ApprovalDenied):self.bridge.read_feed(OTHER)
    def test_no_owner_config_is_fail_closed(self):
        self.bridge.owner_user_id=None
        with self.assertRaises(ApprovalDenied):self.bridge.read_feed(OWNER)
    def test_unsupported_feed_path_fails(self):
        self.bridge.feed_path=str(self.root/"missing")
        with self.assertRaises(BridgeUnavailable):self.bridge.read_feed(OWNER)
    def test_tampered_signature_fails(self):
        v=json.loads(self.feed_path.read_text())
        v["body"]["jobs"][0]["phase"]="verified"
        self.feed_path.write_text(json.dumps(v))
        with self.assertRaises(BridgeUnavailable):self.bridge.read_feed(OWNER)
    def test_expired_feed_fails(self):
        self.write_feed(example_feed(generated_at=(now()-timedelta(minutes=3)).isoformat()))
        with self.assertRaises(BridgeUnavailable):self.bridge.read_feed(OWNER)
    def test_future_feed_fails(self):
        self.write_feed(example_feed(generated_at=(now()+timedelta(seconds=30)).isoformat()))
        with self.assertRaises(BridgeUnavailable):self.bridge.read_feed(OWNER)
    def test_duplicate_jobs_fail(self):
        f=example_feed();f["jobs"].append(dict(f["jobs"][0]));f["job_count"]=2
        self.write_feed(f)
        with self.assertRaises(BridgeUnavailable):self.bridge.read_feed(OWNER)
    def test_key_file_public_read_denied(self):
        os.chmod(self.feed_key,0o644)
        with self.assertRaises(BridgeUnavailable):self.bridge.read_feed(OWNER)
    def test_symlink_key_denied(self):
        link=self.root/"alias"
        link.symlink_to(self.feed_key)
        self.bridge.feed_key_path=link
        with self.assertRaises(BridgeUnavailable):self.bridge.read_feed(OWNER)
    def test_sign_and_verify_with_explicit_clock(self):
        f=example_feed()
        signed=seal_feed(f,self.feed_key.read_bytes())
        self.assertEqual(verify_feed(signed,self.feed_key.read_bytes(),
                                     now=now())["job_count"],1)
    def test_approval_emits_private_signed_receipt(self):
        result=self.bridge.issue_approval(OWNER,JOB,SHA)
        self.assertEqual(result["state"],"approval_recorded_not_deployed")
        files=list(self.approvals.glob("*.json"))
        self.assertEqual(len(files),1)
        self.assertEqual(stat.S_IMODE(files[0].stat().st_mode),0o600)
        receipt=json.loads(files[0].read_text())
        self.assertEqual(receipt["body"]["operator_user_id"],OWNER)
        self.assertEqual(receipt["body"]["decision_ref"],result["decision_ref"])
        self.assertEqual(receipt["body"]["artifact_sha"],SHA)
        self.assertEqual(receipt["hmac_sha256"],hmac.new(self.approval_key.read_bytes(),
          json.dumps(receipt["body"],ensure_ascii=False,sort_keys=True,
                     separators=(",",":"),allow_nan=False).encode(),hashlib.sha256).hexdigest())
    def test_approval_again_prevented(self):
        self.bridge.issue_approval(OWNER,JOB,SHA)
        with self.assertRaises(ApprovalDenied):self.bridge.issue_approval(OWNER,JOB,SHA)
    def test_hash_mismatch_prevented(self):
        with self.assertRaises(ApprovalDenied):self.bridge.issue_approval(OWNER,JOB,"b"*64)
        self.assertEqual(list(self.approvals.iterdir()),[])
    def test_other_phase_prevented(self):
        self.write_feed(example_feed(status="new"))
        with self.assertRaises(ApprovalDenied):self.bridge.issue_approval(OWNER,JOB,SHA)
    def test_stale_feed_cannot_approve(self):
        self.write_feed(example_feed(generated_at=(now()-timedelta(seconds=200)).isoformat()))
        with self.assertRaises(BridgeUnavailable):self.bridge.issue_approval(OWNER,JOB,SHA)
    def test_other_user_cannot_approve(self):
        with self.assertRaises(ApprovalDenied):self.bridge.issue_approval(OTHER,JOB,SHA)
    def test_unconfigured_approval_cannot_approve(self):
        self.bridge.approval_key_path=None
        with self.assertRaises(BridgeUnavailable):self.bridge.issue_approval(OWNER,JOB,SHA)

class HttpBridgeTests(WorkflowBridgeTests):
    def setUp(self):
        super().setUp()
        import server
        self.server_module=server
        self.original_proxy=server.PROXY
        self.original_bridge=server.WORKFLOW
        self.original_store=server.STORE
        server.PROXY="127.0.0.1"
        server.WORKFLOW=self.bridge
        server.STORE=CommandStore(self.root/"command.sqlite3")
        self.http=ThreadingHTTPServer(("127.0.0.1",0),App)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True)
        self.thread.start()
    def tearDown(self):
        self.http.shutdown();self.http.server_close();self.thread.join(timeout=5)
        self.server_module.PROXY=self.original_proxy
        self.server_module.WORKFLOW=self.original_bridge
        self.server_module.STORE=self.original_store
        super().tearDown()
    def call(self,method,path,user=OWNER,obj=None,headers=None):
        conn=http.client.HTTPConnection("127.0.0.1",self.http.server_port,timeout=3)
        h={"X-Remote-User-Id":user}
        body=None
        if obj is not None:
            body=json.dumps(obj)
            h.update({"Content-Type":"application/json","X-Ziko-Request":"1"})
        if headers:h.update(headers)
        try:
            conn.request(method,path,body=body,headers=h)
            r=conn.getresponse()
            status=r.status
            content=r.read()
            return status,json.loads(content) if content else {}
        finally:conn.close()
    def test_get_feed_owner_200(self):
        code,v=self.call("GET","/api/work")
        self.assertEqual(code,200)
        self.assertEqual(v["workflow"]["job_count"],1)
        self.assertFalse(v["can_deploy"])
    def test_get_feed_other_403(self):
        code,v=self.call("GET","/api/work",user=OTHER)
        self.assertEqual(code,403)
    def test_get_without_provision_503(self):
        self.bridge.feed_path=None
        code,v=self.call("GET","/api/work")
        self.assertEqual(code,503)
    def test_post_approval_202_no_deployment(self):
        code,v=self.call("POST","/api/work/approve",obj={"job_id":JOB,"artifact_sha":SHA})
        self.assertEqual(code,202)
        self.assertEqual(v["state"],"approval_recorded_not_deployed")
    def test_post_other_user_403(self):
        code,v=self.call("POST","/api/work/approve",user=OTHER,obj={"job_id":JOB,"artifact_sha":SHA})
        self.assertEqual(code,403)
    def test_post_invalid_sha_403(self):
        code,v=self.call("POST","/api/work/approve",obj={"job_id":JOB,"artifact_sha":"b"*64})
        self.assertEqual(code,403)
    def test_post_no_csrf_403(self):
        code,v=self.call("POST","/api/work/approve",obj={"job_id":JOB,"artifact_sha":SHA},
                         headers={"X-Ziko-Request":"0"})
        self.assertEqual(code,403)
    def test_ha_ingress_peer_denial(self):
        self.server_module.PROXY="127.0.0.2"
        code,v=self.call("GET","/api/work")
        self.assertEqual(code,403)
    def test_prior_messages_route_unchanged(self):
        code,v=self.call("POST","/api/messages",obj={"text":"unit test only","client_key":"unit-1"})
        self.assertEqual(code,202)
        self.assertEqual(v["state"],"awaiting_ai")
        code,got=self.call("GET","/api/messages")
        self.assertEqual(code,200)
        self.assertEqual(len(got["messages"]),1)

if __name__=="__main__":unittest.main()

