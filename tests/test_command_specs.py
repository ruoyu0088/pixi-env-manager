import unittest

from app.command_specs import build_command_args, command_specs


class CommandSpecTests(unittest.TestCase):
    def setUp(self):
        self.specs = {spec.key: spec for spec in command_specs()}

    def test_all_tk_commands_are_shared(self):
        self.assertEqual(len(self.specs), 15)
        self.assertIn("add", self.specs)
        self.assertIn("task-add", self.specs)
        self.assertIn("shell", self.specs)

    def test_add_builds_flags_and_packages(self):
        args, error = build_command_args(
            self.specs["add"],
            {
                "specs": "numpy pandas",
                "pypi": True,
                "feature": "dev",
                "environment": "test",
                "platform": "win-64",
                "index": "https://example.invalid/simple",
                "editable": True,
                "no_install": True,
            },
        )
        self.assertEqual(error, "")
        self.assertEqual(args[0], "add")
        self.assertIn("--pypi", args)
        self.assertIn("--feature", args)
        self.assertIn("--no-install", args)
        self.assertEqual(args[-2:], ["numpy", "pandas"])

    def test_required_field_error(self):
        args, error = build_command_args(self.specs["add"], {"specs": ""})
        self.assertEqual(args, [])
        self.assertIn("package", error)

    def test_task_add_depends_on_tokens(self):
        args, error = build_command_args(
            self.specs["task-add"],
            {
                "name": "test",
                "command": "pytest -q",
                "depends_on": "build lint",
            },
        )
        self.assertEqual(error, "")
        self.assertEqual(args[:4], ["task", "add", "test", "pytest -q"])
        self.assertIn("--depends-on", args)
        self.assertEqual(args[-2:], ["build", "lint"])

    def test_init_does_not_use_manifest(self):
        spec = self.specs["init"]
        self.assertFalse(spec.use_manifest)
        args, error = build_command_args(
            spec,
            {
                "path": "C:/tmp/demo",
                "channel": "conda-forge",
                "platform": "win-64",
                "format": "pixi",
            },
        )
        self.assertEqual(error, "")
        self.assertEqual(args[0], "init")


if __name__ == "__main__":
    unittest.main()
