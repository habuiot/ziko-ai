"""Unit tests for the read-only ZikoTodo ingress identity gateway."""
import importlib.util
import unittest
from unittest.mock import patch
from pathlib import Path

spec = importlib.util.spec_from_file_location("server", Path(__file__).parent / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class IdentityTests(unittest.TestCase):
    def test_accepts_real_proxy_identity(self):
        ident = server.ingress_identity("172.30.32.2",
           {"X-Remote-User-Id": "a5e0b6", "X-Remote-User-Display-Name": "ZIKO Admin"})
        self.assertEqual(ident, {"id": "a5e0b6", "display_name": "ZIKO Admin"})

    def test_rejects_direct_client_with_forged_header(self):
        self.assertIsNone(server.ingress_identity("192.168.10.97",
           {"X-Remote-User-Id": "admin"}))

    def test_rejects_missing_identity(self):
        self.assertIsNone(server.ingress_identity("172.30.32.2", {}))

    def test_rejects_blank_and_overlong_ids(self):
        for value in ["", "   ", "A"*129, "a\nb"]:
            with self.subTest(value=value):
                self.assertIsNone(server.ingress_identity("172.30.32.2",
                    {"X-Remote-User-Id": value}))

    def test_no_fallback_for_unknown_user(self):
        self.assertIsNone(server.ingress_identity("172.30.32.3",
            {"X-Remote-User-Name": "admin"}))

    def test_escapes_html_display_name(self):
        page = server.dashboard('<img src=x onerror="alert(1)">')
        self.assertIn(b"&lt;img", page)
        self.assertNotIn(b'<img src=x', page)

    def test_check_backend_offline(self):
        with patch.object(server.urllib.request, "urlopen",
                          side_effect=server.urllib.error.URLError("offline")):
            self.assertFalse(server.check_backend())

    def test_route_path(self):
        self.assertEqual(server.safe_path("/api/me?x=y"), "/api/me")
        self.assertEqual(server.safe_path("/"), "/")


if __name__ == "__main__":
    unittest.main()
