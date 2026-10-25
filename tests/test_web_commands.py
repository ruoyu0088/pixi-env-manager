import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.state import AppState
from app.web.auth import AuthStore
from app.web.server import create_app
from app.web.service import WebService


class _Scopes:
    def __init__(self, values):
        self.values = values

    def scope_for(self, name):
        return self.values.get(name, "transitive")


class WebCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        auth = AuthStore(root / "web_auth.json")
        auth.set_password("password123")
        self.state = AppState(root / "state.json")
        self.service = WebService(self.state)
        self.app = create_app(self.service, auth)
        self.client = self.app.test_client()
        self.csrf = self._login()

    def tearDown(self):
        self.temp.cleanup()

    def _login(self):
        response = self.client.get("/login")
        match = re.search(rb'name="csrf" value="([^"]+)"', response.data)
        token = match.group(1).decode("ascii")
        response = self.client.post(
            "/login", data={"csrf": token, "password": "password123"}
        )
        self.assertEqual(response.status_code, 302)
        return self.client.get("/api/session").get_json()["csrf"]

    def test_command_center_specs(self):
        response = self.client.get("/api/commands")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(len(payload["specs"]), 15)
        self.assertIn("context", payload)
        self.assertFalse(payload["context"]["opened"])

    def test_init_preview_without_workspace(self):
        response = self.client.post(
            "/api/commands/preview",
            json={
                "key": "init",
                "values": {
                    "path": str(Path(self.temp.name) / "new"),
                    "channel": "conda-forge",
                    "platform": "",
                    "format": "pixi",
                },
            },
            headers={"X-CSRF-Token": self.csrf},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["error"], "")
        self.assertIn("init", payload["preview"])

    def test_required_argument_error(self):
        response = self.client.post(
            "/api/commands/preview",
            json={"key": "add", "values": {"specs": ""}},
            headers={"X-CSRF-Token": self.csrf},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("package", response.get_json()["error"])

    def test_base_remove_scope_requires_confirmation(self):
        scopes = _Scopes({"numpy": "base"})
        workspace = SimpleNamespace(scopes=scopes)
        with patch.object(self.service, "_require_workspace", return_value=workspace):
            args, error, needs, message = self.service._remove_scope(
                ["remove", "--environment", "test", "numpy"],
                {"specs": "numpy"},
                False,
            )
            self.assertEqual(error, "")
            self.assertTrue(needs)
            self.assertIn("numpy", message)
            resolved, error, needs, _ = self.service._remove_scope(
                ["remove", "--environment", "test", "numpy"],
                {"specs": "numpy"},
                True,
            )
            self.assertEqual(error, "")
            self.assertFalse(needs)
            self.assertNotIn("--environment", resolved)

    def test_mixed_remove_scope_is_rejected(self):
        scopes = _Scopes({"numpy": "base", "pandas": "env:test"})
        workspace = SimpleNamespace(scopes=scopes)
        with patch.object(self.service, "_require_workspace", return_value=workspace):
            _, error, needs, _ = self.service._remove_scope(
                ["remove", "numpy", "pandas"],
                {"specs": "numpy pandas"},
                False,
            )
        self.assertIn("cannot remove both", error)
        self.assertFalse(needs)


if __name__ == "__main__":
    unittest.main()
