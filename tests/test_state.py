import tempfile
import unittest
from pathlib import Path

from app.state import AppState


class StateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "state.json"
        self.manifest = Path(self.temp.name) / "pixi.toml"
        self.manifest.write_text("[workspace]\nname='x'\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_recent_deduplicates_and_persists(self):
        state = AppState(self.path)
        state.add_recent(self.manifest, "default", "demo")
        state.add_recent(self.manifest, "default", "demo")
        self.assertEqual(len(state.recent()), 1)
        reloaded = AppState(self.path)
        self.assertEqual(len(reloaded.recent()), 1)
        self.assertEqual(reloaded.recent()[0]["name"], "demo")

    def test_recent_environment_is_part_of_identity(self):
        state = AppState(self.path)
        state.add_recent(self.manifest, "default", "demo")
        state.add_recent(self.manifest, "test", "demo")
        self.assertEqual(len(state.recent()), 2)
        state.remove_recent(self.manifest, "test")
        self.assertEqual(state.recent()[0]["environment"], "default")

    def test_python_runs_update_latest_args(self):
        state = AppState(self.path)
        script = Path(self.temp.name) / "plot.py"
        script.write_text("print(1)\n", encoding="utf-8")
        state.add_python_run(self.manifest, "default", script, args="--one")
        state.add_python_run(self.manifest, "default", script, args="--two")
        runs = state.python_runs(self.manifest, "default")
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["args"], "--two")
        state.update_python_run_exit(self.manifest, "default", script, 0)
        self.assertEqual(state.python_runs(self.manifest, "default")[0]["last_exit"], 0)

    def test_python_runs_are_scoped_by_environment(self):
        state = AppState(self.path)
        script = Path(self.temp.name) / "plot.py"
        script.write_text("print(1)\n", encoding="utf-8")
        state.add_python_run(self.manifest, "default", script, args="--one")
        state.add_python_run(self.manifest, "test", script, args="--two")
        self.assertEqual(len(state.python_runs(self.manifest, "default")), 1)
        self.assertEqual(len(state.python_runs(self.manifest, "test")), 1)

    def test_settings_roundtrip(self):
        state = AppState(self.path)
        state.set_setting("theme", "dark")
        reloaded = AppState(self.path)
        self.assertEqual(reloaded.get_setting("theme"), "dark")


if __name__ == "__main__":
    unittest.main()
