import unittest
from pathlib import Path

from app.workspace_init import (
    build_init_args,
    default_platform,
    normalize_channels,
    workspace_name,
)


class WorkspaceInitTests(unittest.TestCase):
    def test_build_init_args(self):
        args = build_init_args(
            Path(r"C:\work\my project"),
            ["conda-forge", "bioconda", "conda-forge"],
            ["win-64", "linux-64", "win-64"],
        )
        self.assertEqual(
            args,
            [
                "init",
                r"C:\work\my project",
                "--format",
                "pixi",
                "--channel",
                "conda-forge",
                "--channel",
                "bioconda",
                "--platform",
                "win-64",
                "--platform",
                "linux-64",
            ],
        )

    def test_normalize_channels(self):
        self.assertEqual(
            normalize_channels([" conda-forge ", "", "bioconda"]),
            ["conda-forge", "bioconda"],
        )

    def test_workspace_name(self):
        self.assertEqual(workspace_name(Path(r"C:\work\demo")), "demo")

    def test_default_platform(self):
        self.assertIn(
            default_platform(), ("win-64", "linux-64", "osx-64", "osx-arm64")
        )


if __name__ == "__main__":
    unittest.main()
