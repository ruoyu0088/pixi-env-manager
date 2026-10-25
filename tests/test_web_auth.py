import re
import tempfile
import unittest
from pathlib import Path

from app.state import AppState
from app.web.auth import AuthStore, hash_password, verify_password
from app.web.server import create_app
from app.web.service import WebService


class PasswordTests(unittest.TestCase):
    def test_hash_and_verify(self):
        encoded = hash_password("correct horse battery")
        self.assertTrue(verify_password("correct horse battery", encoded))
        self.assertFalse(verify_password("wrong", encoded))
        self.assertNotIn("correct horse battery", encoded)

    def test_store_persists_hash_not_password(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "web_auth.json"
            store = AuthStore(path)
            self.assertFalse(store.configured)
            store.set_password("password123")
            self.assertTrue(store.configured)
            raw = path.read_text(encoding="utf-8")
            self.assertNotIn("password123", raw)
            self.assertTrue(AuthStore(path).verify("password123"))
            self.assertFalse(AuthStore(path).verify("bad"))

    def test_short_password_is_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            store = AuthStore(Path(temp) / "web_auth.json")
            store.set_password("1")
            self.assertTrue(store.verify("1"))
            with self.assertRaises(ValueError):
                store.set_password("")


class WebLoginTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.auth = AuthStore(root / "web_auth.json")
        self.auth.set_password("password123")
        self.state = AppState(root / "state.json")
        self.service = WebService(self.state)
        self.app = create_app(self.service, self.auth)
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def _csrf(self) -> str:
        response = self.client.get("/login")
        self.assertEqual(response.status_code, 200)
        match = re.search(rb'name="csrf" value="([^"]+)"', response.data)
        self.assertIsNotNone(match)
        return match.group(1).decode("ascii")

    def test_api_requires_login(self):
        response = self.client.get("/api/workspace")
        self.assertEqual(response.status_code, 401)

    def test_login_and_session(self):
        token = self._csrf()
        response = self.client.post(
            "/login", data={"csrf": token, "password": "password123"}
        )
        self.assertEqual(response.status_code, 302)
        session = self.client.get("/api/session")
        self.assertEqual(session.status_code, 200)
        self.assertTrue(session.get_json()["authenticated"])

    def test_bad_password(self):
        token = self._csrf()
        response = self.client.post(
            "/login", data={"csrf": token, "password": "bad"}
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.client.get("/api/workspace").status_code, 401)

    def _login(self) -> str:
        token = self._csrf()
        response = self.client.post(
            "/login", data={"csrf": token, "password": "password123"}
        )
        self.assertEqual(response.status_code, 302)
        return self.client.get("/api/session").get_json()["csrf"]

    def test_csrf_required_for_mutations(self):
        token = self._csrf()
        self.client.post(
            "/login", data={"csrf": token, "password": "password123"}
        )
        response = self.client.post("/api/workspace/refresh", json={})
        self.assertEqual(response.status_code, 403)

    def test_web_settings_are_written_to_shared_state(self):
        self.state.set_setting("terminal", "cmd.exe")
        csrf = self._login()
        response = self.client.post(
            "/api/settings",
            json={"language": "ja", "theme": "dark"},
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["language"], "ja")
        reloaded = AppState(Path(self.temp.name) / "state.json")
        self.assertEqual(reloaded.get_setting("language"), "ja")
        self.assertEqual(reloaded.get_setting("theme"), "dark")
        self.assertEqual(reloaded.get_setting("terminal"), "cmd.exe")
        session = self.client.get("/api/session").get_json()
        self.assertEqual(session["language"], "ja")
        self.assertEqual(session["theme"], "dark")

    def test_login_page_reads_shared_language_and_theme(self):
        self.state.set_setting("language", "ja")
        self.state.set_setting("theme", "dark")
        response = self.client.get("/login")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'lang="ja"', response.data)
        self.assertIn(b'data-theme="dark"', response.data)


if __name__ == "__main__":
    unittest.main()
