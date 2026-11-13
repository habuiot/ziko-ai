"""Read-only portal tests, including template token injection and project privacy."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import panel
import acl
import server


class DummyRequest:
    def __init__(self, user_id):
        self.client_address = ("172.30.32.2", 9876)
        self.path = "/"
        self.headers = {"X-Remote-User-Id": user_id,
                        "X-Remote-User-Display-Name": user_id}
        self.status = None
        self.body = b""

    def _reply(self, status, body, content_type):
        self.status = status
        self.body = body

    def _json(self, status, payload):
        self.status = status
        self.body = str(payload).encode()


class PortalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "acls.sqlite"
        acl.init_db(self.db)
        acl.create_project(self.db, "secret", "Szigorúan privát")
        acl.create_project(self.db, "team", "Közös fejlesztés")
        acl.grant(self.db, "secret", "alice", "manager")
        acl.grant(self.db, "team", "alice", "editor")
        acl.grant(self.db, "team", "bob", "viewer")

    def request(self, user_id):
        req = DummyRequest(user_id)
        with patch.object(server, "DEFAULT_DB", self.db):
            server.App.do_GET(req)
        self.assertEqual(req.status, 200)
        return req.body.decode("utf-8")

    def test_owner_sees_both_projects(self):
        result = self.request("alice")
        self.assertIn("Szigorúan privát", result)
        self.assertIn("Közös fejlesztés", result)
        self.assertIn("Projektkezelő", result)
        self.assertIn("Szerkesztő", result)

    def test_other_user_cannot_see_private_project(self):
        result = self.request("bob")
        self.assertIn("Közös fejlesztés", result)
        self.assertIn("Megtekintő", result)
        self.assertNotIn("Szigorúan privát", result)
        self.assertNotIn("manager", result)

    def test_new_user_only_sees_empty_state(self):
        result = self.request("new_user")
        self.assertIn("Még nincs hozzárendelt projekt", result)
        self.assertIn("Házikó-hitelesítés", result)
        self.assertNotIn("Szigorúan privát", result)
        self.assertNotIn("Közös fejlesztés", result)

    def test_empty_dashboard_renders_without_identity(self):
        result = panel.dashboard("", [], "").decode()
        self.assertIn("Házikó-felhasználó", result)
        self.assertIn("0</strong>", result)

    def test_project_name_escapes_markup(self):
        result = panel.dashboard("User", [
            {"slug":"safe","title":'<script>alert("x")</script>',"role":"manager"}])
        self.assertIn(b"&lt;script&gt;", result)
        self.assertNotIn(b"<script>alert", result)

    def test_user_name_escapes_markup(self):
        result = panel.dashboard('<img onerror=alert("x")>', [])
        self.assertIn(b"&lt;img", result)
        self.assertNotIn(b"<img onerror", result)

    def test_template_placeholder_injection_not_expanded(self):
        result = panel.dashboard("__PROJECTS__", [
            {"slug":"test","title":"Title","role":"viewer"}]).decode()
        self.assertIn('<div class="user-name">__PROJECTS__</div>', result)
        self.assertEqual(result.count('class="project"'), 1)

    def test_user_id_escapes_quote(self):
        result = panel.dashboard("Hello", [], 'alice" onfocus="alert(1)')
        self.assertNotIn(b'" onfocus="', result)
        self.assertIn(b'&quot; onfocus=&quot;', result)

    def test_mobile_styles_available(self):
        result = panel.dashboard("Owner", [])
        self.assertIn(b"max-width:600px", result)

    def test_no_external_assets_or_javascript(self):
        result = panel.dashboard("Owner", [])
        self.assertNotIn(b"<script", result)
        self.assertNotIn(b"src=", result)


if __name__ == "__main__":
    unittest.main()
