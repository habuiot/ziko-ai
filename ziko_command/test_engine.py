"""Ziko Command engine tests: reliable restart, safety and bounded autonomy."""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

from engine import CommandStore, LEASE_SECONDS, MAX_ATTEMPTS

T = 1_800_000_000


class CommandEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "command.sqlite3"
        self.store = CommandStore(self.db)

    def job(self, ref="todo:abc", *, kind="research", risk="low",
            priority=50, key=None, now=T):
        return self.store.enqueue(ref,"Tesztkutatás",kind,priority,risk,key,now=now)

    def test_no_agents_no_claims(self):
        job = self.job()
        self.assertIsNone(self.store.claim(executor_connected=False,now=T))
        self.assertEqual(self.store.get(job["id"])["state"],"queued")

    def test_only_external_canonical_task_references(self):
        with self.assertRaises(ValueError):
            self.job(ref="../secret")
        with self.assertRaises(ValueError):
            self.job(ref="")
        with self.assertRaises(ValueError):
            self.job(kind="delete_files")

    def test_high_risk_waits_for_approval(self):
        job = self.job(risk="high")
        self.assertEqual(job["state"],"waiting_approval")
        self.assertIsNone(self.store.claim(executor_connected=True,now=T))
        self.assertTrue(self.store.approve(job["id"],"ha_user",now=T))
        leased = self.store.claim(executor_connected=True,now=T)
        self.assertEqual(leased["id"],job["id"])

    def test_medium_risk_also_requires_human(self):
        job = self.job(risk="medium")
        self.assertEqual(job["state"],"waiting_approval")

    def test_agent_cannot_self_approve(self):
        job = self.job(risk="medium")
        with self.assertRaises(ValueError):
            self.store.approve(job["id"],"agent")
        self.assertEqual(self.store.get(job["id"])["state"],"waiting_approval")

    def test_approval_nonexistent_rejected(self):
        self.assertFalse(self.store.approve("missing","operator"))

    def test_idempotent_dispatch(self):
        first = self.job(key="source-1")
        second = self.job(key="source-1")
        self.assertEqual(first["id"],second["id"])
        self.assertEqual(len(self.store.jobs()),1)

    def test_priority_ordering(self):
        lo = self.job(ref="todo:lo",priority=2)
        hi = self.job(ref="todo:hi",priority=90)
        claimed = self.store.claim(executor_connected=True,now=T)
        self.assertEqual(claimed["id"],hi["id"])
        self.assertNotEqual(claimed["id"],lo["id"])

    def test_lease_blocks_duplicate_claims(self):
        job = self.job()
        claimed = self.store.claim(executor_connected=True,now=T)
        self.assertEqual(claimed["id"],job["id"])
        self.assertIsNone(self.store.claim(executor_connected=True,now=T))

    def test_wrong_lease_cannot_complete(self):
        self.job()
        claimed = self.store.claim(executor_connected=True,now=T)
        self.assertFalse(self.store.finish(claimed["id"],"wrong","Result",now=T+2))
        self.assertEqual(self.store.get(claimed["id"])["state"],"running")

    def test_expired_lease_cannot_commit(self):
        self.job()
        claimed = self.store.claim(executor_connected=True,now=T)
        self.assertFalse(self.store.finish(
            claimed["id"],claimed["lease_token"],"Stale",
            now=T+LEASE_SECONDS+1))

    def test_result_goes_to_review_not_auto_complete_todo(self):
        self.job()
        claimed = self.store.claim(executor_connected=True,now=T)
        self.assertTrue(self.store.finish(
            claimed["id"],claimed["lease_token"],"Elkészült vázlat",
            now=T+2))
        result = self.store.get(claimed["id"])
        self.assertEqual(result["state"],"review")
        self.assertEqual(result["source_task_id"],"todo:abc")
        self.assertEqual(result["output"],"Elkészült vázlat")

    def test_crash_recovery_and_backoff(self):
        self.job()
        claimed = self.store.claim(executor_connected=True,now=T)
        recovered = self.store.sweep(now=T+LEASE_SECONDS+1)
        self.assertEqual(recovered,{"recovered":1,"blocked":0})
        self.assertEqual(self.store.get(claimed["id"])["state"],"queued")
        self.assertIsNone(self.store.claim(executor_connected=True,now=T+LEASE_SECONDS+2))

    def test_repeated_timeouts_block_after_budget(self):
        original=self.job()
        now=T
        for attempt in range(MAX_ATTEMPTS):
            claimed=self.store.claim(executor_connected=True,now=now)
            self.assertIsNotNone(claimed)
            self.assertEqual(claimed["id"],original["id"])
            later=now+LEASE_SECONDS+1
            result=self.store.sweep(now=later)
            now=later+3600
        self.assertEqual(self.store.get(original["id"])["state"],"blocked")
        self.assertIsNone(self.store.claim(executor_connected=True,now=now))

    def test_daily_proposals_capped(self):
        for i in range(3):
            self.store.propose("Javaslat "+str(i),"Indoklás",now=T+i)
        with self.assertRaisesRegex(ValueError,"budget"):
            self.store.propose("Túl sok","Túl sok",now=T+4)

    def test_proposals_do_not_become_jobs(self):
        self.store.propose("Ötlet","Nem végrehajtott művelet",now=T)
        self.assertEqual(self.store.jobs(),[])
        self.assertEqual(self.store.briefing(now=T)["proposals_pending"],1)

    def test_daily_digest_created_once(self):
        dt=datetime(2026,11,13,19,5,tzinfo=ZoneInfo("Europe/Budapest"))
        ts=int(dt.timestamp())
        self.assertTrue(self.store.prepare_digest(now=ts))
        self.assertFalse(self.store.prepare_digest(now=ts+30))

    def test_digest_waits_until_evening(self):
        ts=int(datetime(2026,11,13,12,0,tzinfo=ZoneInfo("Europe/Budapest")).timestamp())
        self.assertFalse(self.store.prepare_digest(now=ts))

    def test_heartbeat_persists_restarts(self):
        self.store.heartbeat(now=T)
        reopened=CommandStore(self.db)
        self.assertEqual(reopened.briefing(now=T+10)["heartbeat_at"],T)

    def test_db_restrictive_permissions(self):
        self.assertEqual(self.db.stat().st_mode & 0o777,0o600)

    def test_audit_log_contains_approval(self):
        j=self.job(risk="high")
        self.store.approve(j["id"],"operator",now=T)
        from engine import connect
        from contextlib import closing
        with closing(connect(self.db)) as db:
            events=db.execute("SELECT kind,actor FROM events ORDER BY id").fetchall()
        self.assertEqual([(e["kind"],e["actor"]) for e in events],
                         [("job_enqueued","command"),("approval_granted","operator")])

    def test_concurrent_claim_exactly_once(self):
        self.job()
        with ThreadPoolExecutor(max_workers=4) as pool:
            claims=list(pool.map(lambda _:self.store.claim(executor_connected=True,now=T),
                                 range(4)))
        self.assertEqual(sum(1 for j in claims if j),1)


if __name__=="__main__":
    unittest.main()
