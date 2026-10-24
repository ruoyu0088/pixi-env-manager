import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.models import WorkspaceData
from app.pixi import PixiClient


class LockStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manifest = self.root / "pixi.toml"
        self.lock = self.root / "pixi.lock"
        self.manifest.write_text("[workspace]\nname='x'\n", encoding="utf-8")
        self.client = PixiClient("pixi")

    def tearDown(self):
        self.temp.cleanup()

    def test_missing_lock(self):
        self.assertEqual(self.client.lock_state(self.manifest), "missing")

    def test_lock_newer_than_manifest_is_fresh_without_running_pixi(self):
        self.lock.write_text("lock", encoding="utf-8")
        os.utime(self.manifest, (1000, 1000))
        os.utime(self.lock, (2000, 2000))
        self.assertEqual(self.client.lock_state(self.manifest), "fresh")

    def test_manifest_newer_but_lock_check_says_current(self):
        self.lock.write_text("lock", encoding="utf-8")
        os.utime(self.lock, (1000, 1000))
        os.utime(self.manifest, (2000, 2000))
        calls = []

        def fake_run(args, cwd=None, timeout=None):
            calls.append(args)
            return SimpleNamespace(returncode=0)

        self.client._run = fake_run  # type: ignore[assignment]
        self.assertEqual(self.client.lock_state(self.manifest), "fresh")
        self.assertIn("--check", calls[0])

    def test_manifest_newer_and_lock_check_says_stale(self):
        self.lock.write_text("lock", encoding="utf-8")
        os.utime(self.lock, (1000, 1000))
        os.utime(self.manifest, (2000, 2000))

        self.client._run = lambda args, cwd=None, timeout=None: SimpleNamespace(  # type: ignore[assignment]
            returncode=1
        )
        self.assertEqual(self.client.lock_state(self.manifest), "stale")

    def test_workspace_data_uses_explicit_lock_state(self):
        workspace = WorkspaceData(self.manifest, self.root, lock_state="stale")
        self.assertTrue(workspace.lock_is_stale())
        self.assertFalse(workspace.lock_is_unknown())
        workspace.lock_state = "fresh"
        self.assertFalse(workspace.lock_is_stale())


if __name__ == "__main__":
    unittest.main()
