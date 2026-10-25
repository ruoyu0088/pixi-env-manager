"""Server-side operations shared by the Web UI.

The web layer intentionally calls the same PixiClient / JobManager / AppState
objects as the Tk application instead of shelling out from JavaScript.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from ..i18n import LANGUAGES
from ..jobs import JobHub, JobManager, open_terminal
from ..manifest import normalize_package_name
from ..models import Package, TaskInfo, WorkspaceData, manifest_for_path
from ..pixi import PixiClient, PixiError
from ..state import AppState
from ..util import split_user_args

BASE_ENVIRONMENT = "__base__"


class WebServiceError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def _with_manifest(args: Sequence[str], manifest: Path) -> List[str]:
    items = [str(item) for item in args]
    if not items:
        return items
    if len(items) >= 3 and items[0] == "workspace":
        position = 3
    elif len(items) >= 2 and items[0] == "task":
        position = 2
    else:
        position = 1
    return items[:position] + ["--manifest-path", str(manifest)] + items[position:]


def _is_mutating(args: Sequence[str]) -> bool:
    if not args:
        return False
    first = str(args[0]).lower()
    if first in {
        "add",
        "remove",
        "update",
        "upgrade",
        "install",
        "lock",
        "clean",
        "reinstall",
        "init",
    }:
        return True
    return first == "task" and len(args) > 1 and args[1].lower() in (
        "add",
        "remove",
    )


class WebService:
    def __init__(self, state: Optional[AppState] = None):
        self.state = state or AppState()
        self._pixi_path = str(self.state.get_setting("pixi_path", "") or "")
        self.pixi = PixiClient(self._pixi_path)
        self.jobs = JobManager()
        self.hub = JobHub(self.jobs)
        self.hub.ensure_started()
        self.workspace: Optional[WorkspaceData] = None
        self.environment = ""
        self.base_mode = False
        self._version_cache: Optional[str] = None
        self._pending_remove_environment = ""
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Workspace / environment
    # ------------------------------------------------------------------
    def open_workspace(
        self,
        raw_path: str,
        environment: str = "",
        add_recent: bool = True,
    ) -> Dict[str, Any]:
        self.state.reload()
        self._sync_pixi()
        raw_path = (raw_path or "").strip().strip('"')
        if not raw_path:
            raise WebServiceError("Enter a workspace path.")
        path = Path(raw_path).expanduser()
        manifest = manifest_for_path(path)
        if manifest is None:
            raise WebServiceError(
                "No pixi.toml or pyproject.toml found in that directory."
            )
        preferred = environment.strip()
        try:
            workspace = self.pixi.workspace(
                manifest, preferred_env=preferred or ""
            )
        except PixiError as exc:
            raise WebServiceError(str(exc), 500) from exc
        with self._lock:
            self.workspace = workspace
            self._pending_remove_environment = ""
            self.state.set_setting("last_open_dir", str(manifest.parent))
            self.environment = (
                preferred
                if preferred in workspace.env_names
                else (
                    workspace.default_env().name
                    if workspace.default_env()
                    else "default"
                )
            )
            self.base_mode = self.state.is_base_mode(manifest)
            if self.base_mode:
                default = workspace.default_env()
                if default is not None:
                    self.environment = default.name
            if add_recent:
                self.state.add_recent(
                    manifest, self.environment, workspace.name
                )
            return self.summary()

    def auto_open_recent(self) -> Dict[str, Any]:
        with self._lock:
            if self.workspace is not None:
                return self.summary()
        self.state.reload()
        for item in self.state.recent(30):
            manifest = Path(str(item.get("manifest") or ""))
            if not manifest.is_file():
                continue
            try:
                return self.open_workspace(
                    str(manifest),
                    str(item.get("environment") or ""),
                    add_recent=False,
                )
            except WebServiceError:
                continue
        return self.summary()

    def refresh(self, environment: str = "") -> Dict[str, Any]:
        self.state.reload()
        self._sync_pixi()
        with self._lock:
            if self.workspace is None:
                raise WebServiceError("Open a workspace first.")
            manifest = self.workspace.manifest
            preferred = environment.strip() or self.environment
            base_mode = self.base_mode
        try:
            workspace = self.pixi.workspace(
                manifest, preferred_env=preferred
            )
        except PixiError as exc:
            raise WebServiceError(str(exc), 500) from exc
        with self._lock:
            self.workspace = workspace
            previous_environment = self.environment
            self.environment = (
                preferred
                if preferred in workspace.env_names
                else (
                    workspace.default_env().name
                    if workspace.default_env()
                    else "default"
                )
            )
            removed = self._pending_remove_environment
            if removed and removed not in workspace.env_names:
                self.state.remove_recent(workspace.manifest, removed)
                self.state.remove_python_runs_for_env(workspace.manifest, removed)
                self._pending_remove_environment = ""
            if previous_environment and previous_environment not in workspace.env_names:
                self.state.remove_recent(workspace.manifest, previous_environment)
                self.state.remove_python_runs_for_env(
                    workspace.manifest, previous_environment
                )
            self.base_mode = base_mode
            if self.base_mode:
                default = workspace.default_env()
                if default is not None:
                    self.environment = default.name
            self.state.add_recent(manifest, self.environment, workspace.name)
            return self.summary()

    def set_environment(self, environment: str) -> Dict[str, Any]:
        self.state.reload()
        self._sync_pixi()
        with self._lock:
            if self.workspace is None:
                raise WebServiceError("Open a workspace first.")
            if environment == BASE_ENVIRONMENT:
                default = self.workspace.default_env()
                if default is None:
                    raise WebServiceError("Default environment not found.")
                self.base_mode = True
                self.environment = default.name
                self.state.set_base_mode(self.workspace.manifest, True)
                self.state.add_recent(
                    self.workspace.manifest, self.environment, self.workspace.name
                )
                return self.summary()
            if environment not in self.workspace.env_names:
                raise WebServiceError("Unknown environment: {}".format(environment))
            self.base_mode = False
            self.environment = environment
            self.state.set_base_mode(self.workspace.manifest, False)
            self.state.add_recent(
                self.workspace.manifest, environment, self.workspace.name
            )
            if (
                environment not in self.workspace.packages_by_env
                or environment in self.workspace.package_errors
            ):
                self._load_environment_packages(environment)
            return self.summary()

    def _sync_pixi(self) -> None:
        path = str(self.state.get_setting("pixi_path", "") or "")
        if path == self._pixi_path:
            return
        self._pixi_path = path
        self.pixi = PixiClient(path)
        self._version_cache = None

    def _version_text(self) -> str:
        if self._version_cache is not None:
            return self._version_cache
        if not self.pixi.available:
            return ""
        try:
            self._version_cache = self.pixi.version().replace("pixi ", "", 1)
        except PixiError:
            self._version_cache = ""
        return self._version_cache

    def summary(self) -> Dict[str, Any]:
        self.state.reload()
        self._sync_pixi()
        with self._lock:
            workspace = self.workspace
            if workspace is None:
                return {
                    "opened": False,
                    "recent": self.state.recent(30),
                    "pixi": self._version_text(),
                }
            envs = []
            for env in workspace.envs:
                envs.append(
                    {
                        "name": env.name,
                        "prefix": env.prefix,
                        "features": env.features,
                        "dependencies": env.dependencies,
                        "pypi_dependencies": env.pypi_dependencies,
                        "tasks": env.tasks,
                        "channels": env.channels,
                        "platform": env.platform,
                        "installed": env.installed,
                    }
                )
            packages = self._packages()
            return {
                "opened": True,
                "name": workspace.name,
                "manifest": str(workspace.manifest),
                "root": str(workspace.root),
                "platform": workspace.platform,
                "environment": self.environment,
                "base_mode": self.base_mode,
                "lock_state": workspace.lock_state,
                "envs": envs,
                "tasks": [self._task_json(task) for task in self._tasks()],
                "packages": [self._package_json(pkg) for pkg in packages],
                "package_count": len(packages),
                "package_errors": dict(workspace.package_errors),
                "task_error": workspace.task_error,
                "recent": self.state.recent(30),
                "python_runs": self.state.python_runs(
                    workspace.manifest, self.environment
                ),
                "pixi": self._version_text(),
            }

    def _tasks(self) -> List[TaskInfo]:
        with self._lock:
            if self.workspace is None:
                return []
            return self.workspace.tasks_for_env(self.environment)

    def _load_environment_packages(self, environment: str) -> None:
        if self.workspace is None:
            return
        try:
            packages = self.pixi.load_packages(
                self.workspace.manifest, environment
            )
        except PixiError as exc:
            self.workspace.package_errors[environment] = str(exc)
            self.workspace.packages_by_env[environment] = []
            return
        self.workspace.packages_by_env[environment] = packages
        self.workspace.package_errors.pop(environment, None)

    def _packages(self) -> List[Package]:
        with self._lock:
            workspace = self.workspace
            if workspace is None:
                return []
            if self.base_mode:
                return self._base_packages(workspace)
            packages = workspace.packages_for_env(self.environment)
            for package in packages:
                package.scope = workspace.scopes.scope_for(package.name)
            return sorted(packages, key=lambda item: item.name.casefold())

    def _base_packages(self, workspace: WorkspaceData) -> List[Package]:
        installed = {
            normalize_package_name(package.name): package
            for package in workspace.packages_for_env("default")
        }
        result: List[Package] = []
        for spec in workspace.scopes.base_packages():
            package = installed.get(normalize_package_name(spec.name))
            if package is not None:
                package.scope = "base"
                package.is_explicit = True
                result.append(package)
            else:
                result.append(
                    Package(
                        name=spec.name,
                        version="—",
                        kind=spec.kind,
                        is_explicit=True,
                        requested_spec=spec.spec,
                        installed=False,
                        scope="base",
                    )
                )
        return sorted(result, key=lambda item: item.name.casefold())

    def package_details(self, name: str) -> Dict[str, Any]:
        for package in self._packages():
            if package.name == name:
                return self._package_json(package)
        raise WebServiceError("Package not found: {}".format(name), 404)

    def query_latest(self, name: str) -> Dict[str, Any]:
        package = None
        for item in self._packages():
            if item.name == name:
                package = item
                break
        if package is None:
            raise WebServiceError("Package not found: {}".format(name), 404)
        with self._lock:
            workspace = self.workspace
            if workspace is None:
                raise WebServiceError("Open a workspace first.")
            platform = workspace.platform_for_env(self.environment)
            try:
                package.latest = self.pixi.latest_for(
                    package, platform, workspace.manifest
                )
                package.latest_error = ""
            except PixiError as exc:
                package.latest_error = str(exc)
        return self._package_json(package)

    def compatible_updates(self) -> Dict[str, Any]:
        with self._lock:
            workspace = self.workspace
            if workspace is None:
                raise WebServiceError("Open a workspace first.")
            environment = self.environment
        try:
            updates = self.pixi.compatible_updates(
                workspace.manifest, environment
            )
        except PixiError as exc:
            raise WebServiceError(str(exc), 500) from exc
        return {"updates": updates}

    # ------------------------------------------------------------------
    # Jobs / actions
    # ------------------------------------------------------------------
    def _require_workspace(self) -> WorkspaceData:
        if self.workspace is None:
            raise WebServiceError("Open a workspace first.")
        return self.workspace

    def _start_job(
        self,
        title: str,
        args: Sequence[str],
        *,
        mutating: bool = False,
        extra: Optional[dict] = None,
        use_manifest: bool = True,
    ) -> Dict[str, Any]:
        if not self.pixi.available:
            raise WebServiceError("pixi executable not found.")
        with self._lock:
            workspace = self.workspace
            root = workspace.root if workspace else None
        if use_manifest:
            if workspace is None:
                raise WebServiceError("Open a workspace first.")
            args = _with_manifest(args, workspace.manifest)
        is_mutating = mutating or _is_mutating(args)
        if is_mutating and self.jobs.has_mutating():
            raise WebServiceError(
                "Another environment-changing command is running.", 409
            )
        try:
            job = self.jobs.start(
                title,
                [self.pixi.require()] + [str(item) for item in args],
                cwd=root,
                extra={
                    "mutating": is_mutating,
                    **(extra or {}),
                },
            )
        except Exception as exc:
            raise WebServiceError(str(exc), 500) from exc
        self.hub.ensure_started()
        self.hub.register(job)
        return self._job_json(job)

    def _start_sequence(
        self,
        title: str,
        commands: Sequence[Sequence[str]],
        *,
        stop_on_error: bool = True,
        extra: Optional[dict] = None,
    ) -> Dict[str, Any]:
        if not self.pixi.available:
            raise WebServiceError("pixi executable not found.")
        with self._lock:
            workspace = self._require_workspace()
            root = workspace.root
            full = [
                [self.pixi.require()] + _with_manifest(command, workspace.manifest)
                for command in commands
            ]
        if self.jobs.has_mutating():
            raise WebServiceError(
                "Another environment-changing command is running.", 409
            )
        try:
            job = self.jobs.start_sequence(
                title,
                full,
                cwd=root,
                stop_on_error=stop_on_error,
                extra={"mutating": True, **(extra or {})},
            )
        except Exception as exc:
            raise WebServiceError(str(exc), 500) from exc
        self.hub.ensure_started()
        self.hub.register(job)
        return self._job_json(job)

    def add_environment(
        self,
        name: str,
        features: List[str],
        solve_group: str = "",
        use_default: bool = True,
        install: bool = True,
    ) -> Dict[str, Any]:
        name = name.strip()
        if not name:
            raise WebServiceError("Enter an environment name.")
        if name == "default":
            raise WebServiceError("default is implicit and cannot be created.")
        with self._lock:
            workspace = self._require_workspace()
            if name in workspace.env_names:
                raise WebServiceError("Environment already exists: {}".format(name))
        selected = [item.strip() for item in features if item.strip()]
        if not use_default and not selected:
            raise WebServiceError(
                "Select at least one feature when default is disabled."
            )
        add_args = ["workspace", "environment", "add", name]
        for feature in selected:
            add_args += ["--feature", feature]
        if solve_group.strip():
            add_args += ["--solve-group", solve_group.strip()]
        if not use_default:
            add_args.append("--no-default-feature")
        commands: List[List[str]] = [add_args]
        if install:
            commands.append(["install", "--environment", name])
        return self._start_sequence(
            "Add environment {}".format(name), commands
        )

    def remove_environment(self, name: str, cleanup: bool = False) -> Dict[str, Any]:
        name = name.strip()
        with self._lock:
            workspace = self._require_workspace()
            if name == "default":
                raise WebServiceError("default is implicit and cannot be removed.")
            if name not in workspace.env_names:
                raise WebServiceError("Unknown environment: {}".format(name))
            env = workspace.get_env(name)
            has_directory = bool(env and env.prefix and Path(env.prefix).is_dir())
        commands: List[List[str]] = []
        if cleanup and has_directory:
            commands.append(["clean", "--environment", name])
        commands.append(["workspace", "environment", "remove", name])
        self._pending_remove_environment = name
        return self._start_sequence(
            "Remove environment {}".format(name),
            commands,
            stop_on_error=False,
            extra={"remove_environment": name},
        )

    def feature_names(self) -> List[str]:
        with self._lock:
            workspace = self._require_workspace()
        try:
            return self.pixi.feature_names(workspace.manifest)
        except PixiError as exc:
            raise WebServiceError(str(exc), 500) from exc

    def _job_json(self, job) -> Dict[str, Any]:
        return {
            "id": job.job_id,
            "title": job.title,
            "command": job.command_line,
            "running": True,
        }

    def job_status(self, job_id: int, offset: int = 0) -> Dict[str, Any]:
        snapshot = self.hub.snapshot(job_id, offset)
        if snapshot is None:
            raise WebServiceError("Job not found.", 404)
        return snapshot

    def stop_job(self, job_id: int) -> Dict[str, Any]:
        ok = self.jobs.cancel(job_id)
        return {"stopped": ok}

    def stop_all_jobs(self) -> Dict[str, Any]:
        return {"stopped": self.jobs.cancel_all()}

    def run_task(
        self, task_name: str, args: str = "", terminal: bool = False
    ) -> Dict[str, Any]:
        with self._lock:
            workspace = self._require_workspace()
            environment = self.environment
        task = next(
            (item for item in workspace.tasks_for_env(environment) if item.name == task_name),
            None,
        )
        if task is None:
            raise WebServiceError("Task not found: {}".format(task_name), 404)
        cmd = ["run", "--environment", environment, task.name]
        cmd += split_user_args(args)
        title = "Task: {}".format(task.name)
        if terminal:
            return self.open_terminal(cmd, title)
        return self._start_job(title, cmd)

    def run_python(
        self,
        script: str,
        args: str = "",
        cwd: str = "",
        terminal: bool = False,
    ) -> Dict[str, Any]:
        path = Path(script).expanduser()
        if not path.is_file():
            raise WebServiceError("Python script not found: {}".format(path), 404)
        with self._lock:
            workspace = self._require_workspace()
            environment = self.environment
        working = Path(cwd).expanduser() if cwd else path.parent
        if not working.is_dir():
            working = path.parent
        cmd = [
            "run",
            "--environment",
            environment,
            "python",
            str(path),
        ] + split_user_args(args)
        self.state.add_python_run(
            workspace.manifest,
            environment,
            path,
            args=args,
            cwd=str(working),
        )
        title = "Python: {}".format(path.name)
        if terminal:
            return self.open_terminal(cmd, title)
        return self._start_job(title, cmd, extra={"python": str(path)})

    def run_command(self, command: str, terminal: bool = False) -> Dict[str, Any]:
        tokens = split_user_args(command)
        if not tokens:
            raise WebServiceError("Command is empty.")
        if tokens[0].lower() == "pixi":
            tokens = tokens[1:]
        if not tokens:
            raise WebServiceError("Command is empty.")
        if tokens[0].lower() in ("powershell", "cmd", "bash", "sh"):
            raise WebServiceError("Shell commands are not allowed in the Web UI.")
        use_manifest = tokens[0].lower() not in ("init", "help") and not tokens[
            0
        ].startswith("-")
        self.state.add_command_history(subprocess.list2cmdline(tokens))
        title = "Pixi: {}".format(" ".join(tokens[:2]))
        if terminal:
            return self.open_terminal(tokens, title, use_manifest=use_manifest)
        return self._start_job(title, tokens, use_manifest=use_manifest)

    def add_package(
        self,
        specs: List[str],
        *,
        pypi: bool = False,
        environment: str = "",
        feature: str = "",
        no_install: bool = False,
    ) -> Dict[str, Any]:
        specs = [item for item in specs if item]
        if not specs:
            raise WebServiceError("Enter at least one package.")
        args: List[str] = ["add"]
        if pypi:
            args.append("--pypi")
        if feature:
            args += ["--feature", feature]
        if environment:
            args += ["--environment", environment]
        if no_install:
            args.append("--no-install")
        args += specs
        return self._start_job("Add packages", args, mutating=True)

    def remove_package(
        self,
        specs: List[str],
        *,
        pypi: bool = False,
        environment: str = "",
        feature: str = "",
    ) -> Dict[str, Any]:
        specs = [item for item in specs if item]
        if not specs:
            raise WebServiceError("Enter at least one package.")
        args: List[str] = ["remove"]
        if pypi:
            args.append("--pypi")
        if feature:
            args += ["--feature", feature]
        if environment:
            args += ["--environment", environment]
        args += specs
        return self._start_job("Remove packages", args, mutating=True)

    def install(self) -> Dict[str, Any]:
        return self._start_job(
            "Install environment",
            ["install", "--environment", self.environment],
            mutating=True,
        )

    def update_package(self, name: str, upgrade: bool = False) -> Dict[str, Any]:
        args = ["upgrade" if upgrade else "update"]
        if self.environment:
            args += ["--environment", self.environment]
        args.append(name)
        return self._start_job(
            "{} {}".format("Upgrade" if upgrade else "Update", name),
            args,
            mutating=True,
        )

    # ------------------------------------------------------------------
    # Editor / terminal
    # ------------------------------------------------------------------
    def read_manifest(self) -> Dict[str, Any]:
        with self._lock:
            workspace = self._require_workspace()
            path = workspace.manifest
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise WebServiceError(str(exc), 500) from exc
        if len(text.encode("utf-8")) > 2 * 1024 * 1024:
            raise WebServiceError("Manifest is larger than 2 MB.", 413)
        return {"path": str(path), "content": text}

    def write_manifest(self, content: str) -> Dict[str, Any]:
        with self._lock:
            workspace = self._require_workspace()
            path = workspace.manifest
        data = content.encode("utf-8")
        if len(data) > 2 * 1024 * 1024:
            raise WebServiceError("Manifest is larger than 2 MB.", 413)
        if path.name == "pixi.toml":
            try:
                import tomllib

                tomllib.loads(content)
            except ImportError:
                pass
            except ValueError as exc:
                raise WebServiceError("TOML syntax error: {}".format(exc), 400)
        try:
            fd, temp_name = tempfile.mkstemp(
                prefix=".pixi-web-", suffix=".tmp", dir=str(path.parent)
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                    handle.write(content)
                os.replace(temp_name, path)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
        except OSError as exc:
            raise WebServiceError(str(exc), 500) from exc
        self.refresh()
        return {"saved": True, "path": str(path)}

    def open_terminal(
        self,
        args: Sequence[str],
        title: str = "Pixi",
        use_manifest: bool = True,
    ) -> Dict[str, Any]:
        if not self.pixi.available:
            raise WebServiceError("pixi executable not found.")
        with self._lock:
            workspace = self._require_workspace()
            cwd = workspace.root
            full_args = (
                _with_manifest(args, workspace.manifest)
                if use_manifest
                else [str(item) for item in args]
            )
        try:
            open_terminal(
                [self.pixi.require()] + full_args,
                cwd=cwd,
                title=title,
                terminal=str(self.state.get_setting("terminal", "") or ""),
            )
        except OSError as exc:
            raise WebServiceError(str(exc), 500) from exc
        return {"opened": True, "title": title}

    def settings(self) -> Dict[str, Any]:
        self.state.reload()
        self._sync_pixi()
        language = str(self.state.get_setting("language", "zh") or "zh")
        if language not in LANGUAGES:
            language = "zh"
        theme = str(self.state.get_setting("theme", "light") or "light")
        if theme not in ("light", "dark"):
            theme = "light"
        return {
            "terminal": str(self.state.get_setting("terminal", "") or ""),
            "language": language,
            "theme": theme,
        }

    def update_settings(
        self,
        terminal: Optional[str] = None,
        language: Optional[str] = None,
        theme: Optional[str] = None,
    ) -> Dict[str, Any]:
        values: Dict[str, Any] = {}
        if terminal is not None:
            values["terminal"] = terminal.strip()
        if language is not None:
            if language not in LANGUAGES:
                raise WebServiceError("Unknown language: {}".format(language))
            values["language"] = language
        if theme is not None:
            if theme not in ("light", "dark"):
                raise WebServiceError("Unknown theme: {}".format(theme))
            values["theme"] = theme
        if values:
            self.state.update_settings(values)
        return self.settings()

    def create_workspace(
        self,
        path: str,
        channels: List[str],
        platforms: List[str],
    ) -> Dict[str, Any]:
        from ..workspace_init import build_init_args

        raw_target = str(path).strip().strip('"')
        if not raw_target:
            raise WebServiceError("Enter a directory for the new workspace.")
        target = Path(raw_target).expanduser()
        self.state.set_base_mode(target / "pixi.toml", True)
        args = build_init_args(target, channels, platforms)
        job = self._start_job(
            "Create workspace",
            args,
            mutating=True,
            use_manifest=False,
        )
        job["path"] = str(target)
        job["manifest"] = str(target / "pixi.toml")
        return job

    # ------------------------------------------------------------------
    def _package_json(self, package: Package) -> Dict[str, Any]:
        return {
            "name": package.name,
            "version": package.version,
            "build": package.build,
            "kind": package.kind,
            "source": package.short_source(),
            "is_explicit": package.is_explicit,
            "requested_spec": package.requested_spec,
            "license": package.license,
            "size": package.size,
            "scope": package.scope,
            "installed": package.installed,
            "latest": package.latest,
            "latest_error": package.latest_error,
            "status": package.status_text,
            "status_level": package.status_level,
        }

    def _task_json(self, task: TaskInfo) -> Dict[str, Any]:
        return {
            "name": task.name,
            "cmd": task.cmd,
            "description": task.description,
            "cwd": task.cwd,
            "depends_on": task.depends_on,
            "args": task.args,
            "feature": task.feature,
        }
