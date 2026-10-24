import unittest
from pathlib import Path

from app.models import EnvInfo, Package, parse_packages, parse_tasks
from app.pixi import _extract_json, _version_from_change, latest_conda_version


class PixiParsingTests(unittest.TestCase):
    def test_extract_json_with_prefix_logs(self):
        value = _extract_json('some warning\n{"version": 1}\n')
        self.assertEqual(value, {"version": 1})

    def test_extract_json_array(self):
        value = _extract_json('noise\n[{"name": "x"}]')
        self.assertEqual(value, [{"name": "x"}])

    def test_version_from_change_url(self):
        after = {
            "conda": "https://conda.anaconda.org/conda-forge/win-64/numpy-2.5.4-py315h123_0.conda"
        }
        self.assertEqual(_version_from_change("numpy", after), "2.5.4")

    def test_version_from_change_field(self):
        self.assertEqual(_version_from_change("numpy", {"version": "2.5.4"}), "2.5.4")

    def test_latest_conda_merges_noarch_and_platform(self):
        data = {
            "win-64": [
                {"name": "awkward", "version": "1.10.3"},
                {"name": "awkward", "version": "1.10.2"},
            ],
            "noarch": [
                {"name": "awkward", "version": "2.14.0"},
                {"name": "awkward", "version": "2.13.0"},
            ],
        }
        self.assertEqual(latest_conda_version(data, "awkward", "win-64"), "2.14.0")

    def test_latest_conda_keeps_platform_specific_numpy(self):
        data = {
            "win-64": [{"name": "numpy", "version": "2.5.4"}],
            "noarch": [{"name": "numpy", "version": "1.0.0"}],
        }
        self.assertEqual(latest_conda_version(data, "numpy", "win-64"), "2.5.4")

    def test_latest_conda_prefers_newer_noarch(self):
        data = {
            "win-64": [{"name": "beautifulsoup4", "version": "4.9.1"}],
            "noarch": [{"name": "beautifulsoup4", "version": "4.15.0"}],
        }
        self.assertEqual(
            latest_conda_version(data, "beautifulsoup4", "win-64"), "4.15.0"
        )

    def test_parse_packages(self):
        packages = parse_packages(
            [
                {
                    "name": "numpy",
                    "version": "2.0.0",
                    "build": "py312_0",
                    "kind": "conda",
                    "is_explicit": True,
                    "requested_spec": "*",
                    "size_bytes": 100,
                }
            ]
        )
        self.assertEqual(len(packages), 1)
        self.assertTrue(packages[0].is_explicit)
        self.assertEqual(packages[0].status_text, "未检查")

    def test_parse_tasks_merges_environments_and_features(self):
        data = [
            {
                "environment": "default",
                "tasks": [],
                "features": [
                    {
                        "name": "default",
                        "tasks": [
                            {
                                "name": "build",
                                "cmd": "python build.py",
                                "description": None,
                                "depends_on": [],
                                "cwd": "C:/work",
                                "args": None,
                            }
                        ],
                    }
                ],
            },
            {
                "environment": "test",
                "tasks": [{"name": "test", "cmd": "pytest"}],
                "features": [],
            },
        ]
        envs = [EnvInfo(name="default"), EnvInfo(name="test")]
        tasks = parse_tasks(data, envs)
        self.assertEqual(len(tasks), 2)
        self.assertEqual([task.name for task in tasks if task.env == "test"], ["test"])

    def test_parse_tasks_falls_back_to_info_names(self):
        envs = [EnvInfo(name="default", tasks=["hello"])]
        tasks = parse_tasks([], envs)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].name, "hello")


if __name__ == "__main__":
    unittest.main()
