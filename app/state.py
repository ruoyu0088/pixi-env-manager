"""Persistent application state (history, recent scripts, settings)."""

from __future__ import annotations

import copy
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_SETTINGS: Dict[str, Any] = {
    "language": "zh",
    "theme": "light",
    "pixi_path": "",
    "window_geometry": "",
    "console_max_lines": 50000,
    "last_open_dir": "",
    "command_history": [],
}

DEFAULT_STATE: Dict[str, Any] = {
    "version": 1,
    "recent": [],
    "python_runs": [],
    "settings": DEFAULT_SETTINGS,
}


def default_state_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "PixiEnvManager" / "state.json"
    return Path.home() / ".pixi-env-manager" / "state.json"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _clean_text(value: Any) -> str:
    return str(value) if value is not None else ""


def _norm_path(value: Any) -> str:
    text = _clean_text(value).strip()
    if not text:
        return ""
    try:
        path = Path(text).expanduser()
        if not path.is_absolute():
            path = path.absolute()
        return os.path.normcase(str(path.resolve()))
    except OSError:
        return os.path.normcase(os.path.abspath(text))


class AppState:
    """A tiny JSON-backed store.

    The file is intentionally human-readable so users can inspect or delete it
    when troubleshooting.  Writes are atomic.
    """

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else default_state_path()
        self.data: Dict[str, Any] = copy.deepcopy(DEFAULT_STATE)
        self.load()

    def load(self) -> None:
        try:
            raw = self.path.read_text(encoding="utf-8")
            loaded = json.loads(raw)
        except (OSError, ValueError, TypeError):
            return
        if not isinstance(loaded, dict):
            return

        data = copy.deepcopy(DEFAULT_STATE)
        settings = loaded.get("settings")
        if isinstance(settings, dict):
            data["settings"].update(settings)
        recent = loaded.get("recent")
        if isinstance(recent, list):
            data["recent"] = [item for item in recent if isinstance(item, dict)]
        runs = loaded.get("python_runs")
        if isinstance(runs, list):
            data["python_runs"] = [item for item in runs if isinstance(item, dict)]
        self.data = data

    def save(self) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(self.data, ensure_ascii=False, indent=2)
            fd, temp_name = tempfile.mkstemp(
                prefix="state-", suffix=".tmp", dir=str(self.path.parent)
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                    handle.write(payload)
                    handle.write("\n")
                os.replace(temp_name, self.path)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
            return True
        except OSError:
            return False

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    @property
    def settings(self) -> Dict[str, Any]:
        settings = self.data.setdefault("settings", {})
        for key, value in DEFAULT_SETTINGS.items():
            settings.setdefault(key, value)
        return settings

    def get_setting(self, key: str, default: Any = None) -> Any:
        return self.settings.get(key, default)

    def set_setting(self, key: str, value: Any, save: bool = True) -> None:
        self.settings[key] = value
        if save:
            self.save()

    def add_command_history(self, command: str) -> None:
        command = command.strip()
        if not command:
            return
        history = self.settings.get("command_history")
        if not isinstance(history, list):
            history = []
        history = [item for item in history if item != command]
        history.insert(0, command)
        self.settings["command_history"] = history[:30]
        self.save()

    # ------------------------------------------------------------------
    # Recent workspaces / environments
    # ------------------------------------------------------------------
    def recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        items = [item for item in self.data.get("recent", []) if isinstance(item, dict)]
        items.sort(key=lambda item: _clean_text(item.get("last_opened")), reverse=True)
        return items[:limit]

    def add_recent(
        self,
        manifest: Path,
        environment: str,
        name: str = "",
        save: bool = True,
    ) -> None:
        manifest_text = str(Path(manifest))
        normalized = _norm_path(manifest_text)
        entries = [
            item
            for item in self.data.get("recent", [])
            if not (
                _norm_path(item.get("manifest")) == normalized
                and _clean_text(item.get("environment")) == environment
            )
        ]
        entries.insert(
            0,
            {
                "manifest": manifest_text,
                "environment": environment,
                "name": name or Path(manifest).parent.name,
                "last_opened": _now(),
            },
        )
        self.data["recent"] = entries[:50]
        if save:
            self.save()

    def remove_recent(self, manifest: Path, environment: str) -> None:
        normalized = _norm_path(manifest)
        self.data["recent"] = [
            item
            for item in self.data.get("recent", [])
            if not (
                _norm_path(item.get("manifest")) == normalized
                and _clean_text(item.get("environment")) == environment
            )
        ]
        self.save()

    def clear_recent(self) -> None:
        self.data["recent"] = []
        self.save()

    # ------------------------------------------------------------------
    # Python programs
    # ------------------------------------------------------------------
    def python_runs(self, manifest: Path, environment: str) -> List[Dict[str, Any]]:
        normalized = _norm_path(manifest)
        runs = [
            item
            for item in self.data.get("python_runs", [])
            if _norm_path(item.get("manifest")) == normalized
            and _clean_text(item.get("environment")) == environment
        ]
        runs.sort(key=lambda item: _clean_text(item.get("last_run")), reverse=True)
        return runs

    def add_python_run(
        self,
        manifest: Path,
        environment: str,
        script: Path,
        args: str = "",
        cwd: Optional[Path] = None,
        exit_code: Optional[int] = None,
        save: bool = True,
    ) -> None:
        manifest_text = str(Path(manifest))
        normalized_manifest = _norm_path(manifest_text)
        normalized_script = _norm_path(script)
        runs = [
            item
            for item in self.data.get("python_runs", [])
            if not (
                _norm_path(item.get("manifest")) == normalized_manifest
                and _clean_text(item.get("environment")) == environment
                and _norm_path(item.get("script")) == normalized_script
            )
        ]
        runs.insert(
            0,
            {
                "manifest": manifest_text,
                "environment": environment,
                "script": str(Path(script)),
                "args": args,
                "cwd": str(Path(cwd)) if cwd else str(Path(script).parent),
                "last_run": _now(),
                "last_exit": exit_code,
            },
        )
        self.data["python_runs"] = runs[:200]
        if save:
            self.save()

    def update_python_run_exit(
        self,
        manifest: Path,
        environment: str,
        script: Path,
        exit_code: int,
        save: bool = True,
    ) -> None:
        normalized_manifest = _norm_path(manifest)
        normalized_script = _norm_path(script)
        for item in self.data.get("python_runs", []):
            if (
                _norm_path(item.get("manifest")) == normalized_manifest
                and _clean_text(item.get("environment")) == environment
                and _norm_path(item.get("script")) == normalized_script
            ):
                item["last_exit"] = exit_code
                item["last_run"] = _now()
                if save:
                    self.save()
                return

    def remove_python_runs_for_env(
        self, manifest: Path, environment: str
    ) -> None:
        normalized = _norm_path(manifest)
        self.data["python_runs"] = [
            item
            for item in self.data.get("python_runs", [])
            if not (
                _norm_path(item.get("manifest")) == normalized
                and _clean_text(item.get("environment")) == environment
            )
        ]
        self.save()

    def remove_python_run(
        self, manifest: Path, environment: str, script: Path
    ) -> None:
        normalized_manifest = _norm_path(manifest)
        normalized_script = _norm_path(script)
        self.data["python_runs"] = [
            item
            for item in self.data.get("python_runs", [])
            if not (
                _norm_path(item.get("manifest")) == normalized_manifest
                and _clean_text(item.get("environment")) == environment
                and _norm_path(item.get("script")) == normalized_script
            )
        ]
        self.save()

    def find_python_run(
        self, manifest: Path, environment: str, script: Path
    ) -> Optional[Dict[str, Any]]:
        normalized_manifest = _norm_path(manifest)
        normalized_script = _norm_path(script)
        for item in self.data.get("python_runs", []):
            if (
                _norm_path(item.get("manifest")) == normalized_manifest
                and _clean_text(item.get("environment")) == environment
                and _norm_path(item.get("script")) == normalized_script
            ):
                return item
        return None
