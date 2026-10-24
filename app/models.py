"""Small data model used by the whole application.

The module deliberately depends only on the Python standard library.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .i18n import t
from .versions import compare_versions


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return [str(value)]


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


@dataclass
class Package:
    """One installed package from ``pixi list --json``."""

    name: str
    version: str
    build: str = ""
    kind: str = "conda"
    source: str = ""
    is_explicit: bool = False
    requested_spec: str = ""
    license: str = ""
    size: int = 0
    url: str = ""
    depends: List[str] = field(default_factory=list)
    constrains: List[str] = field(default_factory=list)
    platform: str = ""
    file_name: str = ""

    # UI-only state, never persisted.
    latest: Optional[str] = None
    latest_error: str = ""
    checking_latest: bool = False
    compatible_to: Optional[str] = None

    @property
    def key(self) -> str:
        return "{}:{}".format(self.kind, self.name)

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "Package":
        return cls(
            name=_as_text(data.get("name")),
            version=_as_text(data.get("version")),
            build=_as_text(data.get("build")),
            kind=_as_text(data.get("kind")) or "conda",
            source=_as_text(data.get("source")),
            is_explicit=bool(data.get("is_explicit")),
            requested_spec=_as_text(data.get("requested_spec")),
            license=_as_text(data.get("license")),
            size=int(data.get("size_bytes") or 0),
            url=_as_text(data.get("url")),
            depends=_as_list(data.get("depends")),
            constrains=_as_list(data.get("constrains")),
            platform=_as_text(data.get("platform")),
            file_name=_as_text(data.get("file_name")),
        )

    def compare_latest(self) -> int:
        """Return -1/0/1 comparing the latest known version with installed one."""
        if not self.latest:
            return 0
        return compare_versions(self.latest, self.version)

    @property
    def status_text(self) -> str:
        if self.checking_latest:
            return t("查询中…")
        if self.latest_error:
            return t("查询失败")
        if self.latest:
            comparison = self.compare_latest()
            if comparison > 0:
                return t("有更新")
            if comparison == 0:
                return t("已是最新")
            return t("已安装更高")
        if self.compatible_to:
            return t("可兼容更新")
        return t("未检查")

    @property
    def status_level(self) -> str:
        """One of ``update``, ``ok``, ``warning``, ``error``, ``muted``."""
        if self.checking_latest:
            return "muted"
        if self.latest_error:
            return "error"
        if self.latest:
            return "update" if self.compare_latest() > 0 else "ok"
        if self.compatible_to:
            return "warning"
        return "muted"

    def short_source(self) -> str:
        source = self.source.rstrip("/")
        if not source:
            return ""
        if "conda.anaconda.org/" in source:
            return source.split("conda.anaconda.org/", 1)[1]
        if source.startswith("https://pypi.org"):
            return "PyPI"
        return source


@dataclass
class EnvInfo:
    name: str
    prefix: str = ""
    features: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    pypi_dependencies: List[str] = field(default_factory=list)
    tasks: List[str] = field(default_factory=list)
    channels: List[str] = field(default_factory=list)
    platform: str = ""

    @property
    def installed(self) -> bool:
        return bool(self.prefix) and Path(self.prefix).is_dir()

    @property
    def python_path(self) -> Optional[Path]:
        if not self.prefix:
            return None
        for name in ("python.exe", "python"):
            candidate = Path(self.prefix) / name
            if candidate.is_file():
                return candidate
        return None


@dataclass
class TaskInfo:
    name: str
    cmd: str = ""
    description: str = ""
    cwd: str = ""
    depends_on: List[str] = field(default_factory=list)
    args: Any = None
    env: str = ""
    feature: str = ""

    @property
    def command_summary(self) -> str:
        text = " ".join(self.cmd.split()) if self.cmd else ""
        if len(text) > 80:
            text = text[:77] + "…"
        return text

    @property
    def has_args_schema(self) -> bool:
        return bool(self.args)


@dataclass
class WorkspaceData:
    manifest: Path
    root: Path
    name: str = ""
    pixi_version: str = ""
    platform: str = ""
    envs: List[EnvInfo] = field(default_factory=list)
    tasks: List[TaskInfo] = field(default_factory=list)
    packages_by_env: Dict[str, List[Package]] = field(default_factory=dict)
    package_errors: Dict[str, str] = field(default_factory=dict)
    task_error: str = ""

    @property
    def env_names(self) -> List[str]:
        return [env.name for env in self.envs]

    def get_env(self, name: str) -> Optional[EnvInfo]:
        for env in self.envs:
            if env.name == name:
                return env
        return None

    def default_env(self) -> Optional[EnvInfo]:
        if not self.envs:
            return None
        for env in self.envs:
            if env.name == "default":
                return env
        return self.envs[0]

    def tasks_for_env(self, env_name: str) -> List[TaskInfo]:
        tasks = [task for task in self.tasks if task.env == env_name]
        # A task can be listed multiple times when several features are merged.
        # Keep the first definition for each name.
        unique: List[TaskInfo] = []
        seen = set()
        for task in tasks:
            if task.name in seen:
                continue
            seen.add(task.name)
            unique.append(task)
        return sorted(unique, key=lambda task: task.name.casefold())

    def packages_for_env(self, env_name: str) -> List[Package]:
        return self.packages_by_env.get(env_name, [])

    def platform_for_env(self, env_name: str) -> str:
        env = self.get_env(env_name)
        if env and env.platform:
            return env.platform
        return self.platform

    @property
    def lock_path(self) -> Path:
        return self.root / "pixi.lock"

    @property
    def lock_exists(self) -> bool:
        return self.lock_path.is_file()

    def lock_is_stale(self) -> bool:
        if not self.lock_exists:
            return True
        try:
            return self.manifest.stat().st_mtime > self.lock_path.stat().st_mtime
        except OSError:
            return True

    def python_programs(self, env_name: str, state: Any) -> List[Dict[str, Any]]:
        return state.python_runs(str(self.manifest), env_name)


def parse_packages(data: Any) -> List[Package]:
    if not isinstance(data, list):
        return []
    packages = [Package.from_json(item) for item in data if isinstance(item, dict)]
    packages.sort(key=lambda item: item.name.casefold())
    return packages


def parse_tasks(
    data: Any,
    envs: Sequence[EnvInfo],
) -> List[TaskInfo]:
    """Parse ``pixi task list --json`` into a flat list.

    Pixi returns one object per environment.  Each object has its own tasks and
    a list of features with tasks.  Older/newer Pixi versions may omit some
    environments, so task names from ``pixi info`` are used as a fallback.
    """

    result: List[TaskInfo] = []
    detail_by_name: Dict[str, TaskInfo] = {}

    def make_task(raw: Dict[str, Any], env_name: str, feature: str) -> TaskInfo:
        task = TaskInfo(
            name=_as_text(raw.get("name")),
            cmd=_as_text(raw.get("cmd")),
            description=_as_text(raw.get("description")),
            cwd=_as_text(raw.get("cwd")),
            depends_on=_as_list(raw.get("depends_on")),
            args=raw.get("args"),
            env=env_name,
            feature=feature,
        )
        detail_by_name.setdefault(task.name, task)
        return task

    if isinstance(data, list):
        for env_obj in data:
            if not isinstance(env_obj, dict):
                continue
            env_name = _as_text(env_obj.get("environment")) or "default"
            for raw in env_obj.get("tasks") or []:
                if isinstance(raw, dict) and raw.get("name"):
                    result.append(make_task(raw, env_name, "environment"))
            for feature in env_obj.get("features") or []:
                if not isinstance(feature, dict):
                    continue
                feature_name = _as_text(feature.get("name")) or "default"
                for raw in feature.get("tasks") or []:
                    if isinstance(raw, dict) and raw.get("name"):
                        result.append(make_task(raw, env_name, feature_name))

    known = {(task.env, task.name) for task in result}
    for env in envs:
        for name in env.tasks:
            if (env.name, name) in known:
                continue
            template = detail_by_name.get(name)
            if template:
                result.append(
                    TaskInfo(
                        name=template.name,
                        cmd=template.cmd,
                        description=template.description,
                        cwd=template.cwd,
                        depends_on=list(template.depends_on),
                        args=template.args,
                        env=env.name,
                        feature=template.feature,
                    )
                )
            else:
                result.append(TaskInfo(name=name, env=env.name, feature="environment"))
            known.add((env.name, name))
    return result


def manifest_for_path(path: Path) -> Optional[Path]:
    """Return the manifest file for a file or workspace directory."""
    path = path.expanduser()
    try:
        path = path.resolve()
    except OSError:
        pass
    if path.is_file():
        return path
    if path.is_dir():
        for name in ("pixi.toml", "pyproject.toml"):
            candidate = path / name
            if candidate.is_file():
                return candidate
    return None


def env_key(env_name: str) -> str:
    return os.path.normcase(env_name)
