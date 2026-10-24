import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.jobs import (
    JobManager,
    build_terminal_argv,
    cmd_command_line,
    terminal_command_line,
)
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

    def test_terminal_defaults_to_powershell(self):
        args = ["pixi", "run", "demo"]
        command = build_terminal_argv(
            args, cwd=Path(r"C:\ws"), title="Demo", terminal=""
        )
        self.assertEqual(command[0], "powershell.exe")
        self.assertEqual(command[1:3], ["-NoExit", "-Command"])
        self.assertEqual(command[3], terminal_command_line(args, "Demo"))

    def test_terminal_cmd(self):
        args = ["pixi", "run", "demo"]
        command = build_terminal_argv(
            args, cwd=Path(r"C:\ws"), title="Demo", terminal="cmd.exe"
        )
        self.assertEqual(command[0], "cmd.exe")
        self.assertEqual(command[1], "/K")
        self.assertEqual(command[2], cmd_command_line(args, "Demo"))

    def test_terminal_windows_terminal(self):
        args = ["pixi", "run", "demo"]
        command = build_terminal_argv(
            args, cwd=Path(r"C:\ws"), title="Demo", terminal="wt.exe"
        )
        self.assertEqual(command[:4], ["wt.exe", "-d", r"C:\ws", "powershell.exe"])
        self.assertIn("-Command", command)

    def test_terminal_template(self):
        args = ["pixi", "run", "demo"]
        command = build_terminal_argv(
            args,
            cwd=Path(r"C:\ws"),
            title="Demo",
            terminal='wt.exe -d {cwd} powershell.exe -NoExit -Command "{command}"',
        )
        self.assertEqual(command[:4], ["wt.exe", "-d", r"C:\ws", "powershell.exe"])
        self.assertEqual(command[4:6], ["-NoExit", "-Command"])
        self.assertEqual(command[6], terminal_command_line(args, "Demo"))

    def test_terminal_extra_arguments(self):
        command = build_terminal_argv(
            ["pixi"],
            cwd=Path(r"C:\ws"),
            terminal="powershell.exe -NoLogo",
        )
        self.assertEqual(command[:3], ["powershell.exe", "-NoLogo", "-NoExit"])

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
