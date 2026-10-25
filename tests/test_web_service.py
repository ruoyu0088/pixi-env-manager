import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.state import AppState
from app.web.service import WebService


class AutoOpenRecentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.manifest = root / "pixi.toml"
        self.manifest.write_text("[workspace]\nname = 'demo'\n", encoding="utf-8")
        self.state = AppState(root / "state.json")
        self.service = WebService(self.state)

    def tearDown(self):
        self.temp.cleanup()

    def test_auto_open_passes_saved_environment(self):
        self.state.add_recent(self.manifest, "test", "demo")
        with patch.object(
            self.service,
            "open_workspace",
            return_value={"opened": True},
        ) as opened:
            result = self.service.auto_open_recent()
        opened.assert_called_once_with(
            str(self.manifest), "test", add_recent=False
        )
        self.assertTrue(result["opened"])

    def test_auto_open_skips_missing_manifest(self):
        missing = Path(self.temp.name) / "missing.toml"
        self.state.add_recent(self.manifest, "default", "demo")
        self.state.add_recent(missing, "test", "missing")
        with patch.object(
            self.service,
            "open_workspace",
            return_value={"opened": True},
        ) as opened:
            self.service.auto_open_recent()
        opened.assert_called_once_with(
            str(self.manifest), "default", add_recent=False
        )


if __name__ == "__main__":
    unittest.main()
