"""Access control tests. No Home Assistant or Vikunja dependency."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from acl import (
    init_db, create_project, grant, revoke, accessible_projects, get_project,
    permitted, valid_slug, valid_user,
)


class ACLTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "acl.sqlite"
        init_db(self.db)
        create_project(self.db, "haziko", "Házikó")
        create_project(self.db, "ziko", "Ziko Technology")
        grant(self.db, "haziko", "alice_01", "manager")
        grant(self.db, "haziko", "bob_02", "viewer")
        grant(self.db, "ziko", "alice_01", "editor")

    def test_deny_unregistered(self):
        self.assertEqual(accessible_projects(self.db, "unknown"), [])
        self.assertFalse(permitted(self.db, "unknown", "haziko", "read"))

    def test_only_visible_projects(self):
        self.assertEqual({x["slug"] for x in accessible_projects(self.db, "alice_01")}, {"haziko", "ziko"})
        self.assertEqual([x["slug"] for x in accessible_projects(self.db, "bob_02")], ["haziko"])

    def test_no_cross_project_access(self):
        self.assertIsNone(get_project(self.db, "bob_02", "ziko"))
        self.assertFalse(permitted(self.db, "bob_02", "ziko", "read"))

    def test_viewer_cannot_write(self):
        self.assertTrue(permitted(self.db, "bob_02", "haziko", "read"))
        self.assertFalse(permitted(self.db, "bob_02", "haziko", "write_tasks"))
        self.assertFalse(permitted(self.db, "bob_02", "haziko", "manage_members"))

    def test_editor_cannot_manage_members(self):
        self.assertTrue(permitted(self.db, "alice_01", "ziko", "write_tasks"))
        self.assertFalse(permitted(self.db, "alice_01", "ziko", "manage_members"))

    def test_manager_permissions(self):
        for op in ("read", "write_tasks", "manage_members"):
            self.assertTrue(permitted(self.db, "alice_01", "haziko", op))

    def test_revoke_takes_effect(self):
        revoke(self.db, "haziko", "bob_02")
        self.assertIsNone(get_project(self.db, "bob_02", "haziko"))

    def test_downgrade_takes_effect(self):
        grant(self.db, "haziko", "alice_01", "viewer")
        self.assertFalse(permitted(self.db, "alice_01", "haziko", "write_tasks"))

    def test_sql_injection_rejected(self):
        self.assertFalse(valid_slug("haziko' OR 1=1 --"))
        self.assertFalse(valid_user("bob' OR 1=1 --"))
        self.assertEqual(accessible_projects(self.db, "bob' OR 1=1 --"), [])

    def test_no_database_grants_nobody(self):
        self.assertEqual(accessible_projects(Path(self.tmp.name) / "missing.sqlite", "alice_01"), [])

    def test_database_permissions(self):
        self.assertEqual(self.db.stat().st_mode & 0o777, 0o600)

    def test_duplicate_project_rejected(self):
        with self.assertRaises(Exception):
            create_project(self.db, "haziko", "Duplicate")

    def test_bad_roles_and_user_ids_rejected(self):
        for role in ("admin", "owner", "", "root"):
            with self.subTest(role=role), self.assertRaises(ValueError):
                grant(self.db, "haziko", "attacker", role)
        with self.assertRaises(ValueError):
            grant(self.db, "haziko", "../alice", "viewer")


if __name__ == "__main__":
    unittest.main()
