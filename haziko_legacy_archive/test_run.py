import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SPEC = importlib.util.spec_from_file_location("legacy_archive", Path(__file__).parent / "run.py")
job = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(job)


class ArchiveTests(unittest.TestCase):
    def fixture(self, root):
        base = Path(root)
        src = base / "local_apps" / "ziko_ai"
        src.mkdir(parents=True)
        (src / "config.yaml").write_text('slug: ziko_ai\nversion: "0.2.4"\n')
        (src / "src").mkdir()
        (src / "src" / "app.py").write_text("print('old version')")
        out = base / "share" / "ziko_legacy_archives"
        return src, out

    def test_two_phase_archive_preserves_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            src, out = self.fixture(temp)
            with mock.patch.object(job, "SOURCE", src), mock.patch.object(job, "OUT", out), mock.patch.object(job, "TAR", out / "ziko_024_source.tar.gz"), mock.patch.object(job, "MANIFEST", out / "ziko_024_source.manifest.json"):
                job.archive_only()
                self.assertTrue(src.exists())
                self.assertTrue(job.TAR.is_file())
                self.assertTrue(job.MANIFEST.is_file())
                job.retire_verified()
                self.assertFalse(src.exists())
                self.assertTrue(job.TAR.is_file())
                self.assertTrue(job.MANIFEST.is_file())

    def test_changed_source_refuses_retirement(self):
        with tempfile.TemporaryDirectory() as temp:
            src, out = self.fixture(temp)
            with mock.patch.object(job, "SOURCE", src), mock.patch.object(job, "OUT", out), mock.patch.object(job, "TAR", out / "ziko_024_source.tar.gz"), mock.patch.object(job, "MANIFEST", out / "ziko_024_source.manifest.json"):
                job.archive_only()
                (src / "src" / "app.py").write_text("CHANGED")
                with self.assertRaises(ValueError):
                    job.retire_verified()
                self.assertTrue(src.exists())

    def test_unexpected_version_refuses_archive(self):
        with tempfile.TemporaryDirectory() as temp:
            src, out = self.fixture(temp)
            (src / "config.yaml").write_text('slug: ziko_ai\nversion: "0.4.0"\n')
            with mock.patch.object(job, "SOURCE", src), mock.patch.object(job, "OUT", out), mock.patch.object(job, "TAR", out / "ziko_024_source.tar.gz"), mock.patch.object(job, "MANIFEST", out / "ziko_024_source.manifest.json"):
                with self.assertRaises(ValueError):
                    job.archive_only()
                self.assertTrue(src.exists())


if __name__ == "__main__":
    unittest.main()
