"""Ziko Command — durable, conservative coordinator core (stdlib only).

ZikoTodo owns the canonical *task*; this database owns only execution
attempts, decisions, approvals and outbound briefings. It is NOT a second
task list and does not write Home Assistant or Vikunja task states.

The engine does not make LLM calls or execute shell commands. Dispatch is
allowed only when an independently authenticated executor connects.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import os
import re
import secrets
import sqlite3
import time
import uuid

ALLOWED_KINDS = frozenset({"research", "analysis", "planning", "documentation", "readonly_audit"})
VALID_RISKS = frozenset({"low", "medium", "high"})
VALID_STATES = frozenset({"queued", "waiting_approval", "running", "review", "done", "blocked"})
TZ = ZoneInfo("Europe/Budapest")
MAX_PROPOSALS_PER_DAY = 3
MAX_ATTEMPTS = 3
LEASE_SECONDS = 600
MAX_QUEUE = 300
SOURCE_ID = re.compile(r"[A-Za-z0-9_:\-]{1,180}\Z")


def now_ts() -> int:
    return int(time.time())


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=5, isolation_level='DEFERRED')
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


class CommandStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with closing(connect(self.path)) as con:
            con.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    source_task_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    priority INTEGER NOT NULL CHECK(priority BETWEEN 0 AND 100),
                    risk TEXT NOT NULL CHECK(risk IN ('low','medium','high')),
                    state TEXT NOT NULL CHECK(state IN ('queued','waiting_approval','running','review','done','blocked')),
                    idempotency_key TEXT NOT NULL UNIQUE,
                    attempt INTEGER NOT NULL DEFAULT 0,
                    not_before INTEGER NOT NULL DEFAULT 0,
                    lease_until INTEGER,
                    lease_token TEXT,
                    output TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT '',
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS jobs_ready ON jobs(state,not_before,priority);
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    at INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    job_id TEXT,
                    actor TEXT NOT NULL,
                    detail TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    client_key TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'awaiting_ai',
                    created_at INTEGER NOT NULL,
                    UNIQUE(user_id, client_key)
                );
                CREATE INDEX IF NOT EXISTS messages_by_user ON messages(user_id,created_at);
                CREATE TABLE IF NOT EXISTS proposals (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    proposed_at INTEGER NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('proposed','accepted','dismissed'))
                );
                CREATE TABLE IF NOT EXISTS briefings (
                    date TEXT PRIMARY KEY,
                    prepared_at INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    delivery_state TEXT NOT NULL DEFAULT 'pending'
                );
                CREATE TABLE IF NOT EXISTS runtime (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """)
        os.chmod(self.path, 0o600)

    def event(self, kind: str, detail: str, job_id: str | None = None,
              actor: str = "command", now: int | None = None) -> None:
        now = now_ts() if now is None else now
        with closing(connect(self.path)) as con:
            with con:
                con.execute(
                    "INSERT INTO events(at,kind,job_id,actor,detail) VALUES (?,?,?,?,?)",
                    (now, kind[:50], job_id, actor[:80], detail[:1000]),
                )

    def enqueue(self, source_task_id: str, title: str, kind: str,
                priority: int = 50, risk: str = "low",
                idempotency_key: str | None = None,
                now: int | None = None) -> dict:
        """No invented execution: all jobs reference a canonical external task."""
        now = now_ts() if now is None else now
        if not isinstance(source_task_id, str) or not SOURCE_ID.fullmatch(source_task_id):
            raise ValueError("invalid external Todo task reference")
        if kind not in ALLOWED_KINDS or risk not in VALID_RISKS:
            raise ValueError("unapproved job kind or risk")
        if type(priority) is not int or not (0 <= priority <= 100):
            raise ValueError("invalid priority")
        if not isinstance(title, str) or not (1 <= len(title.strip()) <= 220):
            raise ValueError("invalid title")
        key = idempotency_key or (source_task_id + ":" + kind)
        if not isinstance(key, str) or not (1 <= len(key) <= 250):
            raise ValueError("invalid idempotency key")
        job_id = str(uuid.uuid4())
        state = "queued" if risk == "low" else "waiting_approval"
        with closing(connect(self.path)) as con:
            con.execute("BEGIN IMMEDIATE")
            try:
                existing = con.execute(
                    "SELECT * FROM jobs WHERE idempotency_key=?", (key,)
                ).fetchone()
                if existing:
                    con.execute("COMMIT")
                    return dict(existing)
                n = con.execute(
                    "SELECT COUNT(*) FROM jobs WHERE state NOT IN ('done','blocked')"
                ).fetchone()[0]
                if n >= MAX_QUEUE:
                    raise ValueError("queue full")
                con.execute(
                    "INSERT INTO jobs(id,source_task_id,kind,title,priority,risk,state,"
                    "idempotency_key,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (job_id, source_task_id, kind, title.strip(), priority, risk,
                     state, key, now, now),
                )
                con.execute(
                    "INSERT INTO events(at,kind,job_id,actor,detail) VALUES (?,?,?,?,?)",
                    (now,"job_enqueued",job_id,"command",state),
                )
                con.execute("COMMIT")
            except BaseException:
                con.execute("ROLLBACK")
                raise
        return self.get(job_id)

    def get(self, job_id: str) -> dict | None:
        with closing(connect(self.path)) as con:
            row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            return dict(row) if row else None

    def jobs(self, limit: int = 100) -> list[dict]:
        limit = max(1, min(int(limit), 100))
        with closing(connect(self.path)) as con:
            return [dict(row) for row in con.execute(
                "SELECT * FROM jobs ORDER BY "
                "CASE state WHEN 'waiting_approval' THEN 0 "
                "WHEN 'running' THEN 1 ELSE 2 END,"
                "priority DESC, created_at ASC LIMIT ?", (limit,))]

    def approve(self, job_id: str, user_id: str, now: int | None = None) -> bool:
        """Only call from a verified HA operator endpoint, never from the agent."""
        now = now_ts() if now is None else now
        if not user_id or len(user_id) > 128 or user_id == "agent":
            raise ValueError("verified human operator required")
        with closing(connect(self.path)) as con:
            with con:
                cursor = con.execute(
                    "UPDATE jobs SET state='queued',updated_at=? "
                    "WHERE id=? AND state='waiting_approval'", (now, job_id)
                )
                if cursor.rowcount:
                    con.execute(
                        "INSERT INTO events(at,kind,job_id,actor,detail) VALUES (?,?,?,?,?)",
                        (now, "approval_granted", job_id, user_id, "explicit approval"),
                    )
                return bool(cursor.rowcount)

    def claim(self, *, executor_connected: bool, now: int | None = None) -> dict | None:
        """Atomically lease a job. Claiming is not successful execution."""
        if not executor_connected:
            return None
        now = now_ts() if now is None else now
        with closing(connect(self.path)) as con:
            con.execute("BEGIN IMMEDIATE")
            try:
                row = con.execute(
                    "SELECT * FROM jobs WHERE state='queued' AND not_before<=? "
                    "AND attempt<? ORDER BY priority DESC,created_at ASC LIMIT 1",
                    (now, MAX_ATTEMPTS),
                ).fetchone()
                if row is None:
                    con.execute("COMMIT")
                    return None
                lease = secrets.token_urlsafe(28)
                con.execute(
                    "UPDATE jobs SET state='running',attempt=attempt+1,"
                    "lease_until=?,lease_token=?,updated_at=? WHERE id=?",
                    (now+LEASE_SECONDS, lease, now, row["id"]),
                )
                con.execute(
                    "INSERT INTO events(at,kind,job_id,actor,detail) VALUES (?,?,?,?,?)",
                    (now, "job_claimed", row["id"], "executor", str(row["attempt"]+1)),
                )
                con.execute("COMMIT")
                return self.get(row["id"])
            except BaseException:
                con.execute("ROLLBACK")
                raise

    def finish(self, job_id: str, lease_token: str, result: str,
               *, needs_review: bool = True, now: int | None = None) -> bool:
        """Task canonical status is *not* changed; only execution result is stored."""
        now = now_ts() if now is None else now
        if not isinstance(result,str) or not (1 <= len(result) <= 5000):
            raise ValueError("result must be 1–5000 characters")
        if not lease_token:
            return False
        state = "review" if needs_review else "done"
        with closing(connect(self.path)) as con:
            with con:
                cursor = con.execute(
                    "UPDATE jobs SET state=?,output=?,lease_token=NULL,lease_until=NULL,"
                    "updated_at=? WHERE id=? AND state='running' AND lease_token=? "
                    "AND lease_until>=?",
                    (state, result, now, job_id, lease_token, now),
                )
                if cursor.rowcount:
                    con.execute(
                        "INSERT INTO events(at,kind,job_id,actor,detail) VALUES (?,?,?,?,?)",
                        (now, "job_result_recorded", job_id, "executor", state),
                    )
                return bool(cursor.rowcount)

    def sweep(self, now: int | None = None) -> dict:
        """Recover expired leases safely after process/power loss, bounded retry."""
        now = now_ts() if now is None else now
        recovered = 0
        blocked = 0
        with closing(connect(self.path)) as con:
            con.execute("BEGIN IMMEDIATE")
            try:
                stale = con.execute(
                    "SELECT id,attempt FROM jobs WHERE state='running' AND lease_until<?",
                    (now,),
                ).fetchall()
                for row in stale:
                    exhausted = row["attempt"] >= MAX_ATTEMPTS
                    state = "blocked" if exhausted else "queued"
                    retry_at = 0 if exhausted else now + min(3600, 60 * (2 ** row["attempt"]))
                    con.execute(
                        "UPDATE jobs SET state=?,not_before=?,lease_until=NULL,"
                        "lease_token=NULL,error=?,updated_at=? WHERE id=?",
                        (state,retry_at,"executor lease expired",now,row["id"]),
                    )
                    con.execute(
                        "INSERT INTO events(at,kind,job_id,actor,detail) VALUES (?,?,?,?,?)",
                        (now, "job_blocked" if exhausted else "job_requeued",
                         row["id"], "command", "lease_expired"),
                    )
                    blocked += int(exhausted)
                    recovered += int(not exhausted)
                con.execute("COMMIT")
            except BaseException:
                con.execute("ROLLBACK")
                raise
        return {"recovered": recovered, "blocked": blocked}

    def propose(self, title: str, rationale: str, now: int | None = None) -> dict:
        """Bounded ideas; proposals never auto-enqueue executable work."""
        now = now_ts() if now is None else now
        if not isinstance(title,str) or not 1<=len(title.strip())<=220:
            raise ValueError("invalid proposal title")
        if not isinstance(rationale,str) or not 1<=len(rationale.strip())<=1500:
            raise ValueError("invalid rationale")
        day = datetime.fromtimestamp(now, TZ).strftime("%Y-%m-%d")
        start = int(datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=TZ).timestamp())
        end = int((datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=TZ) + timedelta(days=1)).timestamp())
        pid = str(uuid.uuid4())
        with closing(connect(self.path)) as con:
            con.execute("BEGIN IMMEDIATE")
            try:
                count = con.execute(
                    "SELECT COUNT(*) FROM proposals WHERE proposed_at>=? AND proposed_at<?",
                    (start,end),
                ).fetchone()[0]
                if count >= MAX_PROPOSALS_PER_DAY:
                    raise ValueError("daily proposal budget reached")
                con.execute(
                    "INSERT INTO proposals(id,title,rationale,proposed_at,state)"
                    " VALUES (?,?,?,?,'proposed')",
                    (pid,title.strip(),rationale.strip(),now),
                )
                con.execute("COMMIT")
            except BaseException:
                con.execute("ROLLBACK")
                raise
        return {"id": pid, "title": title.strip(), "state": "proposed"}


    def submit_message(self, user_id: str, text: str,
                       client_key: str, now: int | None = None) -> dict:
        """User-to-commander inbox, NOT a Todo task or an AI execution claim."""
        now = now_ts() if now is None else now
        if not isinstance(user_id,str) or not SOURCE_ID.fullmatch(user_id):
            raise ValueError("invalid Home Assistant identity")
        if not isinstance(text,str) or not 1<=len(text.strip())<=2000:
            raise ValueError("message must be 1–2000 characters")
        if not isinstance(client_key,str) or not SOURCE_ID.fullmatch(client_key):
            raise ValueError("client idempotency key required")
        start = now-86400
        with closing(connect(self.path)) as con:
            con.execute("BEGIN IMMEDIATE")
            try:
                found=con.execute(
                    "SELECT * FROM messages WHERE user_id=? AND client_key=?",
                    (user_id,client_key)
                ).fetchone()
                if found:
                    con.execute("COMMIT")
                    return dict(found)
                num=con.execute(
                    "SELECT COUNT(*) FROM messages WHERE user_id=? AND created_at>=?",
                    (user_id,start)
                ).fetchone()[0]
                if num >= 40:
                    raise ValueError("daily command limit reached")
                mid=str(uuid.uuid4())
                con.execute(
                    "INSERT INTO messages(id,user_id,text,client_key,created_at) "
                    "VALUES(?,?,?,?,?)",
                    (mid,user_id,text.strip(),client_key,now),
                )
                con.execute(
                    "INSERT INTO events(at,kind,job_id,actor,detail) VALUES (?,?,?,?,?)",
                    (now,"message_recorded",None,user_id,"awaiting_ziko_ai"),
                )
                con.execute("COMMIT")
            except BaseException:
                con.execute("ROLLBACK")
                raise
        return {"id":mid,"text":text.strip(),"status":"awaiting_ai",
                "created_at":now}

    def messages(self, user_id: str, limit: int = 30) -> list[dict]:
        """Never disclose a different user's messages."""
        if not isinstance(user_id,str) or not SOURCE_ID.fullmatch(user_id):
            return []
        limit=max(1,min(int(limit),100))
        with closing(connect(self.path)) as con:
            return [dict(x) for x in con.execute(
                "SELECT id,text,status,created_at FROM messages "
                "WHERE user_id=? ORDER BY created_at DESC,id DESC LIMIT ?",
                (user_id,limit)
            )]

    def briefing(self, now: int | None = None) -> dict:
        now = now_ts() if now is None else now
        with closing(connect(self.path)) as con:
            counts = {x["state"]:x["n"] for x in con.execute(
                "SELECT state,COUNT(*) AS n FROM jobs GROUP BY state"
            )}
            proposals = con.execute(
                "SELECT COUNT(*) FROM proposals WHERE state='proposed'"
            ).fetchone()[0]
            last = con.execute(
                "SELECT value FROM runtime WHERE key='last_heartbeat'"
            ).fetchone()
        return {
            "at": datetime.fromtimestamp(now, timezone.utc).isoformat(),
            "jobs": counts,
            "proposals_pending": proposals,
            "heartbeat_at": int(last[0]) if last else None,
            "ai_executor_connected": False,  # Never claim connected without handshake.
            "canonical_tasks": "ZikoTodo",
            "next_action": "Waiting for trusted Ziko AI executor integration",
        }

    def heartbeat(self, now: int | None = None) -> None:
        now = now_ts() if now is None else now
        with closing(connect(self.path)) as con:
            with con:
                con.execute(
                    "INSERT INTO runtime(key,value) VALUES('last_heartbeat',?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (str(now),),
                )

    def prepare_digest(self, now: int | None = None, hour: int = 19) -> bool:
        """Prepare, but do not send, one daily briefing at/after local hour."""
        now = now_ts() if now is None else now
        dt = datetime.fromtimestamp(now, TZ)
        if dt.hour < hour:
            return False
        key = dt.date().isoformat()
        payload = json.dumps(self.briefing(now), ensure_ascii=False)
        with closing(connect(self.path)) as con:
            with con:
                cursor = con.execute(
                    "INSERT OR IGNORE INTO briefings(date,prepared_at,payload)"
                    " VALUES(?,?,?)", (key,now,payload),
                )
                return bool(cursor.rowcount)
