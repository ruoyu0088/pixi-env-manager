import tempfile
import unittest
from pathlib import Path

import app.manifest as manifest_module
from app.manifest import normalize_package_name, read_manifest_scopes


TOML = """
[workspace]
channels = ["conda-forge"]
platforms = ["win-64"]

[dependencies]
python = "3.14.*"

[pypi-dependencies]
requests = "*"

[feature.test.dependencies]
numpy = "*"

[feature.test.pypi-dependencies]
pytest = "*"

[environments.test.dependencies]
pandas = "*"

[environments.default.dependencies]
sympy = "*"
"""

PYPROJECT = """
[project]
name = "demo"
version = "0.1.0"

[tool.pixi.workspace]
channels = ["conda-forge"]
platforms = ["win-64"]

[tool.pixi.dependencies]
python = "3.14.*"

[tool.pixi.feature.dev.dependencies]
ruff = "*"

[tool.pixi.environments.dev.dependencies]
pytest = "*"
"""


class ManifestScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, name: str, text: str) -> Path:
        path = Path(self.temp.name) / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_pixi_toml_scopes(self):
        path = self._write("pixi.toml", TOML)
        scopes = read_manifest_scopes(path)
        self.assertEqual(scopes.scope_for("python"), "base")
        self.assertEqual(scopes.scope_for("requests"), "base")
        self.assertEqual(scopes.scope_for("numpy"), "feature:test")
        self.assertEqual(scopes.scope_for("pytest"), "feature:test")
        self.assertEqual(scopes.scope_for("pandas"), "env:test")
        self.assertEqual(scopes.scope_for("sympy"), "env:default")
        self.assertEqual(scopes.scope_for("unknown"), "transitive")
        self.assertEqual(scopes.base["requests"].kind, "pypi")

    def test_pyproject_scopes(self):
        path = self._write("pyproject.toml", PYPROJECT)
        scopes = read_manifest_scopes(path)
        self.assertEqual(scopes.scope_for("python"), "base")
        self.assertEqual(scopes.scope_for("ruff"), "feature:dev")
        self.assertEqual(scopes.scope_for("pytest"), "env:dev")

    def test_fallback_parser(self):
        path = self._write("pixi.toml", TOML)
        saved = manifest_module.tomllib
        manifest_module.tomllib = None
        try:
            scopes = read_manifest_scopes(path)
        finally:
            manifest_module.tomllib = saved
        self.assertEqual(scopes.scope_for("python"), "base")
        self.assertEqual(scopes.scope_for("numpy"), "feature:test")
        self.assertEqual(scopes.scope_for("sympy"), "env:default")

    def test_normalize_name(self):
        self.assertEqual(normalize_package_name("scikit_image"), "scikit-image")
        self.assertEqual(normalize_package_name("Scikit-Image"), "scikit-image")


if __name__ == "__main__":
    unittest.main()
