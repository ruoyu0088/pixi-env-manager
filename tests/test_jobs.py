import unittest

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


if __name__ == "__main__":
    unittest.main()
