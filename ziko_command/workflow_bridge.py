"""ZIKO Workflow -> HA Command owner-only signed inbox.

This is a transport contract, not a new task database or command executor.
No HTTP listeners, token provisioning, or HA privileges are created here.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import stat
import uuid

FEED_SCHEMA="ziko-command-workflow-feed/v1"
APPROVAL_SCHEMA="ziko-command-approval/v1"
ISSUER="ziko-command-ingress"
SHA=re.compile(r"[a-f0-9]{64}\Z")
JOB_ID=re.compile(r"[a-fA-F0-9-]{32,40}\Z")
RECEIPT_FIELDS=frozenset({
    "schema","issuer","job_id","artifact_sha","decision_ref",
    "operator_user_id","decision","issued_at","expires_at","nonce"})
MAX_FEED_BYTES=512*1024

class BridgeUnavailable(Exception):
    pass

class ApprovalDenied(Exception):
    pass

def _json_object_pairs(items):
    out={}
    for k,v in items:
        if k in out: raise BridgeUnavailable("Duplicate field")
        out[k]=v
    return out

def _json_bytes(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,
                      separators=(",",":"),allow_nan=False).encode("utf8")

def _secure_read(path,limit):
    p=Path(path)
    if p.is_symlink():
        raise BridgeUnavailable("Symlink refused")
    try:
        st=p.stat()
    except (OSError,ValueError) as exc:
        raise BridgeUnavailable("Source missing") from exc
    if not stat.S_ISREG(st.st_mode) or st.st_uid!=os.geteuid() or stat.S_IMODE(st.st_mode)&0o077:
        raise BridgeUnavailable("Owner-only file required")
    if st.st_size<=0 or st.st_size>limit:
        raise BridgeUnavailable("File size invalid")
    try:
        with p.open("rb") as f:
            if os.fstat(f.fileno()).st_ino!=st.st_ino:
                raise BridgeUnavailable("Source changed")
            raw=f.read(limit+1)
    except OSError as exc:
        raise BridgeUnavailable("Cannot read source") from exc
    if len(raw)>limit:raise BridgeUnavailable("Source oversized")
    return raw

def key_from_file(path):
    key=_secure_read(path,256)
    if len(key)<32:raise BridgeUnavailable("Signing key too short")
    return key

def utc(value):
    try:
        obj=datetime.fromisoformat(value.replace("Z","+00:00"))
    except (TypeError,ValueError,AttributeError) as exc:
        raise BridgeUnavailable("Invalid timestamp") from exc
    if obj.tzinfo is None or obj.utcoffset() is None:
        raise BridgeUnavailable("Timezone required")
    return obj.astimezone(timezone.utc)

def _mac(body,key):
    return hmac.new(key,_json_bytes(body),hashlib.sha256).hexdigest()

def seal_feed(feed,key):
    if not isinstance(feed,dict) or feed.get("schema")!=FEED_SCHEMA:
        raise BridgeUnavailable("Invalid Workflow source")
    if not isinstance(feed.get("jobs"),list) or len(feed["jobs"])>500:
        raise BridgeUnavailable("Workflow job count invalid")
    if not isinstance(feed.get("generated_at"),str):
        raise BridgeUnavailable("Workflow generation timestamp missing")
    if len(key)<32:raise BridgeUnavailable("Weak transport key")
    return {"body":feed,"hmac_sha256":_mac(feed,key)}

def verify_feed(envelope,key,*,now=None,max_age=90):
    if not isinstance(envelope,dict) or set(envelope)!={"body","hmac_sha256"}:
        raise BridgeUnavailable("Invalid feed envelope")
    feed=envelope["body"]
    tag=envelope["hmac_sha256"]
    if not isinstance(tag,str) or not SHA.fullmatch(tag) or len(key)<32:
        raise BridgeUnavailable("Feed verification failed")
    if not hmac.compare_digest(tag,_mac(feed,key)):
        raise BridgeUnavailable("Feed signature mismatch")
    if not isinstance(feed,dict) or feed.get("schema")!=FEED_SCHEMA:
        raise BridgeUnavailable("Wrong feed schema")
    instant=datetime.now(timezone.utc) if now is None else now
    age=(instant-utc(feed.get("generated_at"))).total_seconds()
    if not (0<=age<=max_age):
        raise BridgeUnavailable("Workflow feed stale or future-dated")
    jobs=feed.get("jobs")
    if not isinstance(jobs,list) or len(jobs)>500 or feed.get("job_count")!=len(jobs):
        raise BridgeUnavailable("Workflow payload inconsistent")
    seen=set()
    for j in jobs:
        if not isinstance(j,dict) or not isinstance(j.get("job_id"),str):
            raise BridgeUnavailable("Malformed job")
        if j["job_id"] in seen:raise BridgeUnavailable("Duplicate job")
        seen.add(j["job_id"])
        sha=j.get("artifact_sha")
        if sha is not None and (not isinstance(sha,str) or not SHA.fullmatch(sha)):
            raise BridgeUnavailable("Malformed artifact")
    return feed

class CommandWorkflowBridge:
    def __init__(self, feed_path=None, feed_key_path=None, approval_key_path=None,
                 approval_dir=None, owner_user_id=None):
        self.feed_path=feed_path
        self.feed_key_path=feed_key_path
        self.approval_key_path=approval_key_path
        self.approval_dir=approval_dir
        self.owner_user_id=owner_user_id

    @classmethod
    def from_environment(cls):
        configured=os.environ.get("ZIKO_COMMAND_OWNER_USER_ID")
        if not configured:
            try:
                opts=json.loads(Path("/data/options.json").read_text(encoding="utf8"))
                configured=opts.get("owner_user_id") if isinstance(opts,dict) else None
            except (OSError,ValueError,UnicodeError):
                configured=None
        return cls(
            os.environ.get("ZIKO_WORKFLOW_SIGNED_FEED",
                           "/data/workflow_signed_feed.json"),
            os.environ.get("ZIKO_WORKFLOW_FEED_KEY",
                           "/data/keys/workflow-feed.key"),
            os.environ.get("ZIKO_COMMAND_APPROVAL_KEY",
                           "/data/keys/command-approval.key"),
            os.environ.get("ZIKO_COMMAND_APPROVAL_DIR","/data/approvals"),
            configured)

    def approval_ready(self):
        if not all((self.owner_user_id,self.approval_key_path,self.approval_dir)):
            return False
        try:
            key_from_file(self.approval_key_path)
            dest=Path(self.approval_dir)
            if dest.is_symlink():return False
            st=dest.stat()
            return dest.is_dir() and st.st_uid==os.geteuid() and                    not stat.S_IMODE(st.st_mode)&0o077
        except (BridgeUnavailable,OSError,ValueError):
            return False

    def require_owner(self,verified_user):
        if not self.owner_user_id or not isinstance(verified_user,str) \
                or not hmac.compare_digest(self.owner_user_id,verified_user):
            raise ApprovalDenied("Owner-only route")

    def read_feed(self,verified_user):
        self.require_owner(verified_user)
        if not self.feed_path or not self.feed_key_path:
            raise BridgeUnavailable("Workflow transport not provisioned")
        raw=_secure_read(self.feed_path,MAX_FEED_BYTES)
        try:
            envelope=json.loads(raw,object_pairs_hook=_json_object_pairs)
        except (ValueError,UnicodeError,TypeError) as exc:
            raise BridgeUnavailable("Invalid Workflow JSON") from exc
        return verify_feed(envelope,key_from_file(self.feed_key_path))

    def issue_approval(self,verified_user,job_id,artifact_sha):
        self.require_owner(verified_user)
        if not isinstance(job_id,str) or not JOB_ID.fullmatch(job_id):
            raise ApprovalDenied("Invalid job ID")
        if not isinstance(artifact_sha,str) or not SHA.fullmatch(artifact_sha):
            raise ApprovalDenied("Invalid artifact SHA")
        feed=self.read_feed(verified_user)
        eligible=[j for j in feed["jobs"] if j["job_id"]==job_id]
        if len(eligible)!=1 or eligible[0].get("phase")!="meeting_ready" \
                or eligible[0].get("approved") or eligible[0].get("artifact_sha")!=artifact_sha:
            raise ApprovalDenied("Not eligible for owner approval")
        if not self.approval_key_path or not self.approval_dir:
            raise BridgeUnavailable("Owner decision transport not provisioned")
        key=key_from_file(self.approval_key_path)
        target=Path(self.approval_dir)
        if target.is_symlink() or not target.is_dir():
            raise BridgeUnavailable("Private approval directory missing")
        st=target.stat()
        if st.st_uid!=os.geteuid() or stat.S_IMODE(st.st_mode)&0o077:
            raise BridgeUnavailable("Owner-only decision directory required")
        now=datetime.now(timezone.utc)
        ref=str(uuid.uuid4())
        body={
            "schema":APPROVAL_SCHEMA,"issuer":ISSUER,
            "job_id":job_id,"artifact_sha":artifact_sha,
            "decision_ref":ref,"operator_user_id":verified_user,
            "decision":"approve","issued_at":now.isoformat(),
            "expires_at":(now+timedelta(seconds=240)).isoformat(),
            "nonce":secrets.token_urlsafe(24)}
        if set(body)!=RECEIPT_FIELDS:
            raise BridgeUnavailable("Invalid approval schema")
        envelope={"body":body,"hmac_sha256":_mac(body,key)}
        path=target/(job_id+"-"+artifact_sha+".json")
        try:
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        except FileExistsError as exc:
            raise ApprovalDenied("Already approved for this artifact") from exc
        try:
            with os.fdopen(fd,"wb") as f:
                f.write(_json_bytes(envelope))
                f.flush()
                os.fsync(f.fileno())
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return {"decision_ref":ref,"job_id":job_id,
                "artifact_sha":artifact_sha,"state":"approval_recorded_not_deployed"}

