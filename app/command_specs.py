"""Tk-free command specifications and argument builders."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from .util import split_user_args


@dataclass
class FieldSpec:
    key: str
    label: str
    kind: str = "entry"
    default: str = ""
    required: bool = False
    help: str = ""
    values: Tuple[str, ...] = ()
    width: int = 38


@dataclass
class CommandSpec:
    key: str
    title: str
    group: str
    summary: str
    fields: List[FieldSpec] = field(default_factory=list)
    help_args: Tuple[str, ...] = ()
    dangerous: bool = False
    refresh: bool = False
    use_manifest: bool = True
    terminal: bool = False


def command_specs() -> List[CommandSpec]:
    env_field = FieldSpec(
        key="environment",
        label="Environment",
        kind="env",
        default="current",
        help="Named environment to use or modify.",
    )
    platform_field = FieldSpec(
        key="platform",
        label="Platform",
        kind="platform",
        help="For example win-64 or linux-64; leave blank for the default platform.",
    )
    return [
        CommandSpec(
            key="add",
            title="Add Dependency",
            group="Dependencies",
            summary="Add conda or PyPI dependencies to the workspace.",
            help_args=("add",),
            refresh=True,
            fields=[
                FieldSpec(
                    "specs",
                    "Package specification",
                    required=True,
                    help="Space-separated, e.g. numpy pandas or numpy=2.0; PyPI packages may use pkg==1.2.",
                ),
                FieldSpec("pypi", "Use PyPI", kind="check", help="Add a PyPI dependency instead of a conda dependency."),
                FieldSpec("feature", "Feature", help="Write to a specific feature; leave blank for default."),
                env_field,
                platform_field,
                FieldSpec("index", "PyPI index", help="PyPI only: custom index URL."),
                FieldSpec("editable", "Editable", kind="check", help="PyPI only: add a local package in editable mode."),
                FieldSpec("no_install", "Manifest only (no install)", kind="check", help="Corresponds to --no-install."),
            ],
        ),
        CommandSpec(
            key="remove",
            title="Remove Dependency",
            group="Dependencies",
            summary="Remove dependencies from the workspace.",
            help_args=("remove",),
            dangerous=True,
            refresh=True,
            fields=[
                FieldSpec("specs", "Package specification", required=True, help="Space-separated package names."),
                FieldSpec("pypi", "Use PyPI", kind="check"),
                FieldSpec("feature", "Feature"),
                env_field,
                platform_field,
            ],
        ),
        CommandSpec(
            key="update",
            title="Update (compatible)",
            group="Dependencies",
            summary="Update dependencies within current constraints and write the lock file.",
            help_args=("update",),
            refresh=True,
            fields=[
                FieldSpec("packages", "Package name", help="Leave blank to update all; separate multiple packages with spaces."),
                env_field,
                platform_field,
                FieldSpec("dry_run", "Plan only (dry-run)", kind="check"),
            ],
        ),
        CommandSpec(
            key="upgrade",
            title="Upgrade (latest)",
            group="Dependencies",
            summary="Relax constraints and upgrade dependencies. This may modify pixi.toml.",
            help_args=("upgrade",),
            dangerous=True,
            refresh=True,
            fields=[
                FieldSpec("packages", "Package name", help="Leave blank to upgrade all; separate multiple packages with spaces."),
                FieldSpec("feature", "Feature"),
                env_field,
                FieldSpec("dry_run", "Plan only (dry-run)", kind="check"),
            ],
        ),
        CommandSpec(
            key="search",
            title="Search Packages",
            group="Dependencies",
            summary="Search packages in configured conda channels.",
            help_args=("search",),
            fields=[
                FieldSpec("package", "Package name", required=True),
                FieldSpec("channel", "Channel", help="Optional, e.g. conda-forge."),
                platform_field,
                FieldSpec("limit", "Version count", default="5", help="Number of versions to show (default 5)."),
            ],
        ),
        CommandSpec(
            key="install",
            title="Install / Update",
            group="Environment",
            summary="Install or update the environment from the manifest and lock file.",
            help_args=("install",),
            refresh=True,
            fields=[
                env_field,
                FieldSpec("frozen", "Frozen", kind="check", help="Use the lock file strictly; do not update it."),
                FieldSpec("locked", "Locked", kind="check", help="Check that the lock file is current; fail otherwise."),
            ],
        ),
        CommandSpec(
            key="lock",
            title="Lock Environment",
            group="Environment",
            summary="Solve the environment and update pixi.lock without installing.",
            help_args=("lock",),
            refresh=True,
            fields=[
                FieldSpec("check", "Check only", kind="check"),
                FieldSpec("dry_run", "Compute only, do not write", kind="check"),
            ],
        ),
        CommandSpec(
            key="clean",
            title="Clean Environment",
            group="Environment",
            summary="Remove the environment directory under .pixi; manifest and lock files are kept.",
            help_args=("clean",),
            dangerous=True,
            refresh=True,
            fields=[
                env_field,
                FieldSpec("activation_cache", "Activation cache only", kind="check"),
            ],
        ),
        CommandSpec(
            key="reinstall",
            title="Reinstall Environment",
            group="Environment",
            summary="Update the lock file and reinstall the selected environment.",
            help_args=("reinstall",),
            dangerous=True,
            refresh=True,
            fields=[
                env_field,
                FieldSpec("all", "All environments", kind="check", help="Reinstall all environments, ignoring the Environment field."),
                FieldSpec("packages", "Specific packages", help="Reinstall only these packages; leave blank for the whole environment."),
            ],
        ),
        CommandSpec(
            key="run",
            title="Run Task / Command",
            group="Task",
            summary="Run a task or arbitrary command in the selected environment.",
            help_args=("run",),
            fields=[
                FieldSpec(
                    "task",
                    "Task / Command",
                    kind="task",
                    required=True,
                    help="Enter a task name or a command such as python script.py.",
                ),
                env_field,
                FieldSpec("clean_env", "Clean env", kind="check", help="Ignore the current shell environment."),
                FieldSpec("skip_deps", "Skip task dependencies", kind="check"),
                FieldSpec("dry_run", "Print only, do not execute", kind="check"),
            ],
        ),
        CommandSpec(
            key="task-add",
            title="Add Task",
            group="Task",
            summary="Add a task to the workspace.",
            help_args=("task", "add"),
            refresh=True,
            fields=[
                FieldSpec("name", "Task name", required=True),
                FieldSpec("command", "Command", required=True, help="For example pytest -q or python build.py."),
                FieldSpec("description", "Description"),
                FieldSpec("cwd", "Working directory", help="Relative to the workspace root."),
                FieldSpec("depends_on", "Depends on tasks", help="Space-separated task names."),
                FieldSpec("feature", "Feature"),
                env_field,
            ],
        ),
        CommandSpec(
            key="task-remove",
            title="Remove Task",
            group="Task",
            summary="Remove a task from the workspace.",
            help_args=("task", "remove"),
            dangerous=True,
            refresh=True,
            fields=[
                FieldSpec("names", "Task name", required=True, help="Space-separated."),
                FieldSpec("feature", "Feature"),
                env_field,
            ],
        ),
        CommandSpec(
            key="info",
            title="Environment Info",
            group="Environment",
            summary="Show Pixi, workspace and environment information.",
            help_args=("info",),
            fields=[FieldSpec("extended", "Include cache and environment sizes", kind="check")],
        ),
        CommandSpec(
            key="shell",
            title="Open Pixi Shell",
            group="Workspace",
            summary="Activate the environment and open a shell in a new terminal.",
            help_args=("shell",),
            use_manifest=True,
            terminal=True,
            fields=[env_field],
        ),
        CommandSpec(
            key="init",
            title="Initialize Workspace",
            group="Workspace",
            summary="Create a new Pixi workspace.",
            help_args=("init",),
            use_manifest=False,
            fields=[
                FieldSpec(
                    "path",
                    "Path",
                    required=True,
                    help="New workspace directory; an absolute path is recommended.",
                ),
                FieldSpec("channel", "Channel", default="conda-forge"),
                FieldSpec("platform", "Platform", help="For example win-64; leave blank for Pixi to decide."),
                FieldSpec(
                    "format",
                    "Format",
                    kind="combo",
                    default="pixi",
                    values=("pixi", "pyproject"),
                ),
            ],
        ),
    ]




def _text(values: Dict[str, Any], key: str) -> str:
    value = values.get(key, "")
    if isinstance(value, bool):
        return value
    text = str(value or "").strip()
    if text == "(not specified)":
        return ""
    return text


def _tokens(values: Dict[str, Any], key: str) -> List[str]:
    value = _text(values, key)
    return split_user_args(value) if value else []


def _check(values: Dict[str, Any], key: str) -> bool:
    return bool(values.get(key))


def build_command_args(
    spec: CommandSpec, values: Dict[str, Any]
) -> Tuple[List[str], str]:
    """Build pixi arguments from a command spec and form values."""
    key = spec.key
    args: List[str] = []
    if key == "add":
        specs = _tokens(values, "specs")
        if not specs:
            return [], "Enter package(s) to add."
        args = ["add"]
        if _check(values, "pypi"):
            args.append("--pypi")
        for field_key, flag in (
            ("feature", "--feature"),
            ("environment", "--environment"),
            ("platform", "--platform"),
            ("index", "--index"),
        ):
            value = _text(values, field_key)
            if value:
                args += [flag, value]
        if _check(values, "editable"):
            args.append("--editable")
        if _check(values, "no_install"):
            args.append("--no-install")
        args += specs
    elif key == "remove":
        specs = _tokens(values, "specs")
        if not specs:
            return [], "Enter package(s) to remove."
        args = ["remove"]
        if _check(values, "pypi"):
            args.append("--pypi")
        for field_key, flag in (
            ("feature", "--feature"),
            ("environment", "--environment"),
            ("platform", "--platform"),
        ):
            value = _text(values, field_key)
            if value:
                args += [flag, value]
        args += specs
    elif key == "update":
        args = ["update"]
        env = _text(values, "environment")
        if env:
            args += ["--environment", env]
        platform = _text(values, "platform")
        if platform:
            args += ["--platform", platform]
        if _check(values, "dry_run"):
            args.append("--dry-run")
        args += _tokens(values, "packages")
    elif key == "upgrade":
        args = ["upgrade"]
        feature = _text(values, "feature")
        if feature:
            args += ["--feature", feature]
        env = _text(values, "environment")
        if env:
            args += ["--environment", env]
        if _check(values, "dry_run"):
            args.append("--dry-run")
        args += _tokens(values, "packages")
    elif key == "search":
        package = _text(values, "package")
        if not package:
            return [], "Enter a package name."
        args = ["search", package]
        channel = _text(values, "channel")
        if channel:
            args += ["--channel", channel]
        platform = _text(values, "platform")
        if platform:
            args += ["--platform", platform]
        limit = _text(values, "limit")
        if limit:
            args += ["--limit", limit]
    elif key == "install":
        args = ["install"]
        env = _text(values, "environment")
        if env:
            args += ["--environment", env]
        if _check(values, "frozen"):
            args.append("--frozen")
        if _check(values, "locked"):
            args.append("--locked")
    elif key == "lock":
        args = ["lock"]
        if _check(values, "check"):
            args.append("--check")
        if _check(values, "dry_run"):
            args.append("--dry-run")
    elif key == "clean":
        args = ["clean"]
        env = _text(values, "environment")
        if env:
            args += ["--environment", env]
        if _check(values, "activation_cache"):
            args.append("--activation-cache")
    elif key == "reinstall":
        args = ["reinstall"]
        env = _text(values, "environment")
        if env:
            args += ["--environment", env]
        if _check(values, "all"):
            args.append("--all")
        args += _tokens(values, "packages")
    elif key == "run":
        task = _text(values, "task")
        if not task:
            return [], "Enter a task name or command."
        args = ["run"]
        env = _text(values, "environment")
        if env:
            args += ["--environment", env]
        if _check(values, "clean_env"):
            args.append("--clean-env")
        if _check(values, "skip_deps"):
            args.append("--skip-deps")
        if _check(values, "dry_run"):
            args.append("--dry-run")
        args += split_user_args(task)
    elif key == "task-add":
        name = _text(values, "name")
        command = _text(values, "command")
        if not name or not command:
            return [], "Task name and command cannot be empty."
        args = ["task", "add", name, command]
        for field_key, flag in (
            ("description", "--description"),
            ("cwd", "--cwd"),
            ("feature", "--feature"),
            ("environment", "--environment"),
        ):
            value = _text(values, field_key)
            if value:
                args += [flag, value]
        depends = _tokens(values, "depends_on")
        if depends:
            args += ["--depends-on"] + depends
    elif key == "task-remove":
        names = _tokens(values, "names")
        if not names:
            return [], "Enter task name(s) to remove."
        args = ["task", "remove"] + names
        for field_key, flag in (
            ("feature", "--feature"),
            ("environment", "--environment"),
        ):
            value = _text(values, field_key)
            if value:
                args += [flag, value]
    elif key == "info":
        args = ["info"]
        if _check(values, "extended"):
            args.append("--extended")
    elif key == "shell":
        args = ["shell"]
        env = _text(values, "environment")
        if env:
            args += ["--environment", env]
    elif key == "init":
        args = ["init"]
        path = _text(values, "path")
        if not path:
            return [], "Enter a new workspace path."
        args.append(path)
        channel = _text(values, "channel")
        if channel:
            args += ["--channel", channel]
        platform = _text(values, "platform")
        if platform:
            args += ["--platform", platform]
        fmt = _text(values, "format")
        if fmt:
            args += ["--format", fmt]
    return args, ""


def spec_to_dict(spec: CommandSpec) -> Dict[str, Any]:
    return {
        "key": spec.key,
        "title": spec.title,
        "group": spec.group,
        "summary": spec.summary,
        "help_args": list(spec.help_args),
        "dangerous": spec.dangerous,
        "refresh": spec.refresh,
        "use_manifest": spec.use_manifest,
        "terminal": spec.terminal,
        "fields": [
            {
                "key": item.key,
                "label": item.label,
                "kind": item.kind,
                "default": item.default,
                "required": item.required,
                "help": item.help,
                "values": list(item.values),
                "width": item.width,
            }
            for item in spec.fields
        ],
    }
