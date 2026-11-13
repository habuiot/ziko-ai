"""HTTP routing tests with trusted ingress headers and a local temporary ACL DB."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import acl
import server


class Request:
    """Small stand-in for BaseHTTPRequestHandler to test the routing logic."""
    def __init__(self, path: str, user_id: str | None, peer: str = "172.30.32.2"):
        self.path = path
        self.client_address = (peer, 12345)
        self.headers = {} if user_id is None else {
            "X-Remote-User-Id": user_id,
            "X-Remote-User-Display-Name": "Tesztfelhasználó",
        }
        self.status = None
        self.response = None

    def _json(self, status, payload):
        self.status = status
        self.response = payload

    def _reply(self, status, body, content_type):
        self.status = status
        self.response = body


class ProjectAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "access.sqlite"
        acl.init_db(self.db)
        acl.create_project(self.db, "private", "Titkos projekt")
        acl.create_project(self.db, "shared", "Közös projekt")
        acl.grant(self.db, "private", "alice", "manager")
        acl.grant(self.db, "shared", "alice", "editor")
        acl.grant(self.db, "shared", "bob", "viewer")

    def request(self, path, user, peer="172.30.32.2"):
        req = Request(path, user, peer)
        with patch.object(server, "DEFAULT_DB", self.db):
            server.App.do_GET(req)
        return req.status, req.response

    def test_users_only_see_own_projects(self):
        code, result = self.request("/api/projects", "bob")
        self.assertEqual(code, 200)
        self.assertEqual([p["slug"] for p in result["projects"]], ["shared"])

    def test_unknown_user_gets_empty_projects(self):
        code, result = self.request("/api/projects", "intruder")
        self.assertEqual(code, 200)
        self.assertEqual(result["projects"], [])

    def test_details_are_not_disclosed_across_users(self):
        self.assertEqual(self.request("/api/projects/private", "bob"), (404, {"error":"not_found"}))
        code, data = self.request("/api/projects/private", "alice")
        self.assertEqual(code, 200)
        self.assertEqual(data["project"]["role"], "manager")

    def test_direct_spoofed_user_rejected(self):
        code, data = self.request("/api/projects", "alice", "192.168.10.97")
        self.assertEqual(code, 403)
        self.assertEqual(data["error"], "forbidden")

    def test_no_identity_rejected(self):
        self.assertEqual(self.request("/api/projects", None)[0], 403)

    def test_path_traversal_rejected(self):
        self.assertEqual(self.request("/api/projects/../private", "bob")[0], 404)

    def test_unknown_path_denied(self):
        self.assertEqual(self.request("/admin", "alice")[0], 404)


if __name__ == "__main__":
    unittest.main()
