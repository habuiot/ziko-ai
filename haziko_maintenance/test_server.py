import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SPEC = importlib.util.spec_from_file_location(
    "haziko_maintenance", Path(__file__).parent / "server.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class InventoryTests(unittest.TestCase):
    def test_old_and_new_are_separated(self):
        with tempfile.TemporaryDirectory() as root:
            local = Path(root) / "local" / "ziko_ai"
            local.mkdir(parents=True)
            (local / "config.yaml").write_text(
                'slug: ziko_ai\nversion: "0.2.4"\n', encoding="utf-8")
            share = Path(root) / "share"
            share.mkdir()
            (share / "ziko_ai_archive.tgz").write_text("x")
            with mock.patch.object(module, "LOCAL", local), mock.patch.object(
                    module, "SHARE", share):
                result = module.inventory()
                self.assertTrue(result["read_only"])
                self.assertEqual(result["legacy_local_app"]["version"], "0.2.4")
                self.assertEqual(result["shared_files"]["legacy_named_entries"], 1)

    def test_symlink_refused(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "destination"
            destination.mkdir()
            link = Path(root) / "ziko_ai"
            link.symlink_to(destination, target_is_directory=True)
            with mock.patch.object(module, "LOCAL", link):
                self.assertEqual(module.legacy_source()["status"], "symlink_refused")

    def test_unexpected_slug(self):
        with tempfile.TemporaryDirectory() as root:
            local = Path(root)
            (local / "config.yaml").write_text(
                'slug: something_else\nversion: "0.2.4"\n', encoding="utf-8")
            with mock.patch.object(module, "LOCAL", local):
                self.assertEqual(module.legacy_source()["status"], "unexpected_slug")


    def test_internal_api_requires_strong_secret(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as root:
            options = Path(root) / "options.json"
            options.write_text('{"maintenance_key": "' + "a" * 64 + '"}')
            with mock.patch.object(module, "OPTIONS", options):
                handler = SimpleNamespace(
                    client_address=("172.30.33.8", 5566),
                    headers={"X-Haziko-Maintenance-Key": "a" * 64})
                self.assertTrue(module.authorized(handler))
                handler.headers = {"X-Haziko-Maintenance-Key": "wrong"}
                self.assertFalse(module.authorized(handler))
                handler.client_address = ("10.0.0.8", 5566)
                handler.headers = {"X-Haziko-Maintenance-Key": "a" * 64}
                self.assertFalse(module.authorized(handler))
                handler.client_address = ("172.30.32.2", 5566)
                handler.headers = {}
                self.assertTrue(module.authorized(handler))

if __name__ == "__main__":
    unittest.main()
