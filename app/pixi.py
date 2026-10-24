"""Thin, testable wrapper around the Pixi command line interface."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from functools import cmp_to_key
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .models import EnvInfo, Package, TaskInfo, WorkspaceData, parse_packages, parse_tasks
from .versions import compare_versions


CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
_CREATE_FLAGS = CREATE_NO_WINDOW if os.name == "nt" else 0


class PixiError(RuntimeError):
    def __init__(
        self,
        message: str,
        command: Optional[Sequence[str]] = None,
        returncode: Optional[int] = None,
        stdout: str = "",
        stderr: str = "",
    ):
        super().__init__(message)
        self.command = list(command or [])
        self.returncode = returncode
        self.stdout = stdout or ""
        self.stderr = stderr or ""

    @property
    def details(self) -> str:
        parts: List[str] = []
        if self.command:
            parts.append("命令: " + subprocess.list2cmdline(self.command))
        if self.returncode is not None:
            parts.append("退出码: {}".format(self.returncode))
        if self.stderr.strip():
            parts.append("stderr:\n" + self.stderr.strip())
        if self.stdout.strip():
            parts.append("stdout:\n" + self.stdout.strip())
        return "\n\n".join(parts)


def find_pixi(override: str = "") -> Optional[str]:
    if override:
        candidate = Path(override).expanduser()
        if candidate.is_file():
            return str(candidate)
        found = shutil.which(override)
        if found:
            return found
    found = shutil.which("pixi")
    if found:
        return found
    # A common location used by the standalone Pixi installer.
    home = Path.home()
    for candidate in (
        home / ".pixi" / "bin" / "pixi.exe",
        home / ".pixi" / "bin" / "pixi",
        Path(os.environ.get("LOCALAPPDATA", "")) / "pixi" / "pixi.exe",
    ):
        try:
            if candidate.is_file():
                return str(candidate)
        except OSError:
            continue
    return None


def _child_env() -> Dict[str, str]:
    env = os.environ.copy()
    env["PIXI_NO_PROGRESS"] = "true"
    env["PIXI_COLOR"] = "never"
    env["NO_COLOR"] = "1"
    env["CLICOLOR"] = "0"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _extract_json(text: str) -> Any:
    text = (text or "").lstrip("\ufeff").strip()
    if not text:
        raise ValueError("命令没有返回 JSON 输出")
    try:
        return json.loads(text)
    except ValueError:
        pass
    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
            return value
        except ValueError:
            continue
    raise ValueError("无法从输出中解析 JSON")


def _version_from_change(name: str, record: Any) -> str:
    if not isinstance(record, dict):
        return ""
    version = record.get("version")
    if version:
        return str(version)
    for key in ("conda", "pypi", "url"):
        raw = record.get(key)
        if not raw:
            continue
        text = str(raw)
        # A conda URL looks like:
        # .../win-64/numpy-2.5.4-py315h...conda
        base = text.rsplit("/", 1)[-1]
        base = re.sub(r"\.(conda|tar\.bz2)$", "", base)
        marker = name + "-"
        if marker in base:
            rest = base.split(marker, 1)[1]
            candidate = rest.split("-", 1)[0]
            if candidate:
                return candidate
    return ""


class PixiClient:
    def __init__(self, executable: Optional[str] = None):
        self.executable = executable or find_pixi()
        self._help_cache: Dict[tuple, str] = {}

    @property
    def available(self) -> bool:
        return bool(self.executable and Path(self.executable).is_file())

    def require(self) -> str:
        if not self.available:
            raise PixiError(
                "找不到 pixi 可执行文件。请在“设置”中指定 pixi.exe，或把 Pixi 加入 PATH。"
            )
        return str(self.executable)

    def command_line(self, args: Sequence[str]) -> str:
        executable = self.executable or "pixi"
        return subprocess.list2cmdline([executable] + [str(item) for item in args])

    def _run(
        self,
        args: Sequence[str],
        cwd: Optional[Path] = None,
        timeout: Optional[float] = 180,
    ) -> subprocess.CompletedProcess:
        executable = self.require()
        command = [executable] + [str(item) for item in args]
        try:
            return subprocess.run(
                command,
                cwd=str(cwd) if cwd else None,
                env=_child_env(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                creationflags=_CREATE_FLAGS,
            )
        except FileNotFoundError as exc:
            raise PixiError("无法启动 pixi：{}".format(exc), command=command) from exc
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", "replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", "replace")
            raise PixiError(
                "pixi 命令超时（{} 秒）".format(timeout),
                command=command,
                stdout=stdout,
                stderr=stderr,
            ) from exc
        except OSError as exc:
            raise PixiError("无法运行 pixi：{}".format(exc), command=command) from exc

    def capture(
        self,
        args: Sequence[str],
        cwd: Optional[Path] = None,
        timeout: Optional[float] = 180,
        check: bool = True,
    ) -> str:
        result = self._run(args, cwd=cwd, timeout=timeout)
        if check and result.returncode != 0:
            message = (result.stderr or result.stdout or "pixi 命令失败").strip()
            raise PixiError(
                message,
                command=[self.executable or "pixi"] + list(args),
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        return result.stdout

    def capture_json(
        self,
        args: Sequence[str],
        cwd: Optional[Path] = None,
        timeout: Optional[float] = 180,
    ) -> Any:
        output = self.capture(args, cwd=cwd, timeout=timeout)
        try:
            return _extract_json(output)
        except ValueError as exc:
            raise PixiError(
                "pixi 返回了无法解析的 JSON：{}".format(exc),
                command=[self.executable or "pixi"] + list(args),
                stdout=output,
            ) from exc

    def version(self) -> str:
        try:
            output = self.capture(["--version"], timeout=30)
        except PixiError:
            return ""
        return output.strip().splitlines()[0] if output.strip() else ""

    # ------------------------------------------------------------------
    # Workspace data
    # ------------------------------------------------------------------
    def info(self, manifest: Path) -> Dict[str, Any]:
        data = self.capture_json(
            ["info", "--manifest-path", str(manifest), "--json"], timeout=90
        )
        if not isinstance(data, dict):
            raise PixiError("pixi info 返回的数据格式不正确。")
        return data

    def task_list(self, manifest: Path) -> Any:
        return self.capture_json(
            ["task", "list", "--manifest-path", str(manifest), "--json"], timeout=90
        )

    def packages(self, manifest: Path, environment: str) -> List[Package]:
        data = self.capture_json(
            [
                "list",
                "--manifest-path",
                str(manifest),
                "--environment",
                environment,
                "--json",
            ],
            timeout=120,
        )
        return parse_packages(data)

    def workspace(
        self,
        manifest: Path,
        preferred_env: str = "",
        include_packages: bool = True,
    ) -> WorkspaceData:
        info = self.info(manifest)
        project = info.get("project_info") or {}
        root = Path(project.get("manifest_path") or manifest).parent
        workspace = WorkspaceData(
            manifest=Path(manifest),
            root=root,
            name=str(project.get("name") or root.name),
            pixi_version=str(info.get("version") or ""),
            platform=str(info.get("platform") or ""),
        )

        for raw in info.get("environments_info") or []:
            if not isinstance(raw, dict):
                continue
            resolved = raw.get("resolved_platform") or {}
            platform = str(resolved.get("name") or resolved.get("subdir") or "")
            workspace.envs.append(
                EnvInfo(
                    name=str(raw.get("name") or "default"),
                    prefix=str(raw.get("prefix") or ""),
                    features=[str(item) for item in raw.get("features") or []],
                    dependencies=[
                        str(item) for item in raw.get("dependencies") or []
                    ],
                    pypi_dependencies=[
                        str(item) for item in raw.get("pypi_dependencies") or []
                    ],
                    tasks=[str(item) for item in raw.get("tasks") or []],
                    channels=[str(item) for item in raw.get("channels") or []],
                    platform=platform,
                )
            )

        if not workspace.envs:
            workspace.envs.append(EnvInfo(name="default"))
        if not workspace.platform:
            workspace.platform = workspace.envs[0].platform

        try:
            tasks_data = self.task_list(manifest)
            workspace.tasks = parse_tasks(tasks_data, workspace.envs)
        except PixiError as exc:
            # A broken task table should not prevent the rest of the workspace
            # from opening.  The UI shows the empty task list plus the error.
            workspace.tasks = []
            workspace.task_error = str(exc)

        selected = preferred_env
        if not selected or selected not in workspace.env_names:
            default_env = workspace.default_env()
            selected = default_env.name if default_env else "default"

        if include_packages:
            try:
                workspace.packages_by_env[selected] = self.packages(
                    manifest, selected
                )
            except PixiError as exc:
                workspace.package_errors[selected] = str(exc)
        return workspace

    def load_packages(self, manifest: Path, environment: str) -> List[Package]:
        return self.packages(manifest, environment)

    # ------------------------------------------------------------------
    # Latest versions
    # ------------------------------------------------------------------
    def latest_conda(
        self, package: Package, platform: str, manifest: Path
    ) -> str:
        args = [
            "search",
            package.name,
            "--manifest-path",
            str(manifest),
            "--json",
        ]
        if platform:
            args.extend(["--platform", platform])
        data = self.capture_json(args, timeout=180)
        if not isinstance(data, dict):
            raise PixiError("pixi search 返回的数据格式不正确。")
        records: List[Dict[str, Any]] = []
        if platform and isinstance(data.get(platform), list):
            records = [item for item in data[platform] if isinstance(item, dict)]
        else:
            for value in data.values():
                if isinstance(value, list):
                    records.extend(item for item in value if isinstance(item, dict))
        versions = [
            str(item.get("version"))
            for item in records
            if str(item.get("name", "")).lower() == package.name.lower()
            and item.get("version")
        ]
        if not versions:
            raise PixiError("在配置的频道中找不到包“{}”。".format(package.name))
        versions.sort(key=cmp_to_key(compare_versions), reverse=True)
        return versions[0]

    def latest_pypi(self, package: Package) -> str:
        source = (package.source or "").lower()
        if source and "pypi.org" not in source and "pythonhosted.org" not in source:
            raise PixiError(
                "该包来自自定义 PyPI 源，无法通过 pypi.org 公共 API 检查最新版本。"
            )
        normalized = re.sub(r"[-_.]+", "-", package.name).lower()
        url = "https://pypi.org/pypi/{}/json".format(
            urllib.parse.quote(normalized, safe="-")
        )
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "PixiEnvManager/0.1 (+https://pypi.org/)",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                payload = json.loads(response.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise PixiError("PyPI 上找不到包“{}”。".format(package.name)) from exc
            raise PixiError("PyPI 查询失败（HTTP {}）。".format(exc.code)) from exc
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise PixiError("PyPI 查询失败：{}".format(exc)) from exc
        version = ((payload or {}).get("info") or {}).get("version")
        if not version:
            raise PixiError("PyPI 返回的数据中没有版本号。")
        return str(version)

    def latest_for(self, package: Package, platform: str, manifest: Path) -> str:
        if package.kind.lower() == "pypi":
            return self.latest_pypi(package)
        return self.latest_conda(package, platform, manifest)

    def compatible_updates(self, manifest: Path, environment: str) -> Dict[str, str]:
        data = self.capture_json(
            [
                "update",
                "--manifest-path",
                str(manifest),
                "--environment",
                environment,
                "--dry-run",
                "--json",
            ],
            timeout=300,
        )
        result: Dict[str, str] = {}
        if not isinstance(data, dict):
            return result
        environments = data.get("environment") or {}
        if not isinstance(environments, dict):
            return result
        for platform_map in environments.values():
            if not isinstance(platform_map, dict):
                continue
            for changes in platform_map.values():
                if not isinstance(changes, list):
                    continue
                for change in changes:
                    if not isinstance(change, dict):
                        continue
                    name = str(change.get("name") or "")
                    if not name or change.get("before") is None:
                        # ``before`` is null for a package that would be
                        # installed for the first time, not an update.
                        continue
                    after = change.get("after")
                    version = _version_from_change(name, after)
                    if version:
                        result[name] = version
        return result

    # ------------------------------------------------------------------
    # Help
    # ------------------------------------------------------------------
    def help_text(self, command: Sequence[str]) -> str:
        key = tuple(command)
        if key in self._help_cache:
            return self._help_cache[key]
        args = list(command) + ["--help"]
        try:
            text = self.capture(args, timeout=30)
        except PixiError as exc:
            text = str(exc)
            if exc.stdout.strip():
                text += "\n\n" + exc.stdout.strip()
        self._help_cache[key] = text
        return text


def normalize_pypi_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()
