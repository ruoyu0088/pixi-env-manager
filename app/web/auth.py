"""Single-password authentication for the optional Web UI."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import secrets
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

PASSWORD_ITERATIONS = 600_000
MIN_PASSWORD_LENGTH = 8


def auth_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "PixiEnvManager" / "web_auth.json"
    return Path.home() / ".pixi-env-manager" / "web_auth.json"


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return "pbkdf2_sha256${}${}${}".format(
        PASSWORD_ITERATIONS, _b64(salt), _b64(digest)
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        rounds = int(iterations)
        salt = _unb64(salt_b64)
        expected = _unb64(digest_b64)
    except (ValueError, TypeError, binascii.Error):
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, rounds
    )
    return hmac.compare_digest(actual, expected)


class AuthStore:
    """Persist a password hash and a session signing secret."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else auth_path()
        self._data: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        self._data = payload

    def reload(self) -> None:
        self.load()

    @property
    def configured(self) -> bool:
        return bool(self._data.get("password_hash")) and bool(
            self._data.get("secret_key")
        )

    @property
    def secret_key(self) -> str:
        return str(self._data.get("secret_key") or "")

    @property
    def session_days(self) -> int:
        try:
            return max(1, min(30, int(self._data.get("session_days", 7))))
        except (TypeError, ValueError):
            return 7

    def set_password(self, password: str, session_days: int = 7) -> None:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError(
                "Password must be at least {} characters.".format(
                    MIN_PASSWORD_LENGTH
                )
            )
        self._data = {
            "password_hash": hash_password(password),
            "secret_key": secrets.token_urlsafe(48),
            "session_days": max(1, min(30, int(session_days))),
        }
        self.save()

    def verify(self, password: str) -> bool:
        encoded = str(self._data.get("password_hash") or "")
        return bool(encoded) and verify_password(password, encoded)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self._data, ensure_ascii=False, indent=2)
        fd, temp_name = tempfile.mkstemp(
            prefix="web_auth-", suffix=".tmp", dir=str(self.path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
                handle.write("\n")
            os.replace(temp_name, self.path)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)


def set_password_interactive() -> int:
    import getpass
    import sys

    print("Set the password for the Pixi Environment Manager Web UI.")
    print("The password is stored as a PBKDF2-SHA256 hash, never as plain text.")
    first = getpass.getpass("New password: ")
    second = getpass.getpass("Confirm password: ")
    if first != second:
        print("Passwords do not match.", file=sys.stderr)
        return 1
    try:
        store = AuthStore()
        store.set_password(first)
    except (OSError, ValueError) as exc:
        print("Could not save the password: {}".format(exc), file=sys.stderr)
        return 1
    print("Password saved to {}.".format(store.path))
    print("Start the Web UI with: start.bat --web --host 127.0.0.1 --port 8010")
    return 0


def authenticate(store: AuthStore, password: str) -> bool:
    return store.verify(password)
