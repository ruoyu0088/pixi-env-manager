import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.jobs import JobManager
from app.ui.main_window import MainWindow


class MutatingCommandTests(unittest.TestCase):
    def test_environment_mutations(self):
        for args in (
            ["add", "numpy"],
            ["remove", "numpy"],
            ["update"],
            ["upgrade", "numpy"],
            ["install"],
            ["lock"],
            ["clean"],
            ["reinstall"],
            ["init", "C:\\tmp\\ws"],
            ["task", "add", "x", "echo"],
            ["task", "remove", "x"],
        ):
            self.assertTrue(MainWindow._is_mutating_args(args), args)

    def test_read_only_commands(self):
        for args in (
            ["run", "task"],
            ["search", "numpy"],
            ["info"],
            ["--version"],
            ["task", "list"],
        ):
            self.assertFalse(MainWindow._is_mutating_args(args), args)

    def test_manifest_path_for_nested_workspace_commands(self):
        fake = MainWindow.__new__(MainWindow)
        fake.workspace = SimpleNamespace(manifest=Path(r"C:\ws\pixi.toml"))
        self.assertEqual(
            fake._with_manifest(["workspace", "environment", "add", "test"]),
            [
                "workspace",
                "environment",
                "add",
                "--manifest-path",
                r"C:\ws\pixi.toml",
                "test",
            ],
        )
        self.assertEqual(
            fake._with_manifest(["install", "--environment", "test"]),
            [
                "install",
                "--manifest-path",
                r"C:\ws\pixi.toml",
                "--environment",
                "test",
            ],
        )

    def test_sequence_runs_commands_in_order(self):
        manager = JobManager()
        job = manager.start_sequence(
            "sequence",
            [
                [sys.executable, "-c", "print('one')"],
                [sys.executable, "-c", "print('two')"],
            ],
        )
        output = []
        done = None
        deadline = time.time() + 15
        while time.time() < deadline and done is None:
            for event in manager.drain():
                if event.kind == "line":
                    output.append(event.text)
                elif event.kind == "done":
                    done = event
            if done is None:
                time.sleep(0.05)
        self.assertIsNotNone(done)
        self.assertEqual(done.job.job_id, job.job_id)
        self.assertEqual(done.returncode, 0)
        self.assertTrue(any("one" in line for line in output))
        self.assertTrue(any("two" in line for line in output))


if __name__ == "__main__":
    unittest.main()
