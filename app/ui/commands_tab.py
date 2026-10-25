"""Form-based command center plus a manual command line."""

from __future__ import annotations

import tkinter as tk
import webbrowser
from dataclasses import dataclass, field
from tkinter import messagebox, ttk
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .. import i18n
from ..util import split_user_args
from .widgets import ScrollableFrame, Tooltip, clear_children


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


def _codes() -> List[CommandSpec]:
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


class CommandsTab(ttk.Frame):
    def __init__(self, master, app, colors: Dict[str, str]):
        super().__init__(master, padding=(14, 12))
        self.app = app
        self.colors = colors
        self.specs = _codes()
        self.spec_by_key = {spec.key: spec for spec in self.specs}
        self.current_spec: Optional[CommandSpec] = None
        self.vars: Dict[str, tk.Variable] = {}
        self.field_widgets: Dict[str, tk.Widget] = {}
        self.shared_environment: Optional[str] = None
        self._help_cache: Dict[str, str] = {}
        self._help_request = 0

        header = ttk.Frame(self)
        header.pack(fill="x")
        ttk.Label(header, text="Command Center", style="Title.TLabel").pack(side="left")
        ttk.Button(
            header, text="Pixi CLI Docs", command=self._open_docs
        ).pack(side="right")

        paned = ttk.Panedwindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, pady=(10, 0))

        left = ttk.Frame(paned, width=210)
        self.tree = ttk.Treeview(left, show="tree", selectmode="browse")
        self.tree.pack(fill="both", expand=True)
        self.tree.column("#0", width=205, stretch=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        paned.add(left, weight=0)

        right = ttk.Frame(paned)
        paned.add(right, weight=1)

        self.title_var = tk.StringVar(value="")
        self.summary_var = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.title_var, style="Title.TLabel").pack(
            anchor="w"
        )
        ttk.Label(
            right,
            textvariable=self.summary_var,
            style="Muted.TLabel",
            wraplength=800,
            justify="left",
        ).pack(anchor="w", pady=(2, 8))

        middle = ttk.Panedwindow(right, orient="horizontal")
        middle.pack(fill="both", expand=True)
        self.middle_pane = middle
        self._middle_sash_set = False
        middle.bind("<Configure>", self._on_middle_configure, add="+")
        self.form_scroll = ScrollableFrame(middle, style="TFrame")
        middle.add(self.form_scroll, weight=2)

        help_frame = ttk.LabelFrame(middle, text="Command Help", padding=(8, 6))
        middle.add(help_frame, weight=1)
        self.help_text = tk.Text(
            help_frame,
            width=40,
            wrap="word",
            state="disabled",
            font=self.app.theme.fonts.mono_small,
            relief="flat",
            borderwidth=0,
            padx=6,
            pady=5,
        )
        help_scroll = ttk.Scrollbar(
            help_frame, orient="vertical", command=self.help_text.yview
        )
        self.help_text.configure(yscrollcommand=help_scroll.set)
        self.help_text.pack(side="left", fill="both", expand=True)
        help_scroll.pack(side="right", fill="y")

        preview_frame = ttk.LabelFrame(right, text="Command Preview", padding=(8, 6))
        preview_frame.pack(fill="x", pady=(8, 0))
        self.preview = tk.Text(
            preview_frame,
            height=3,
            wrap="word",
            font=self.app.theme.fonts.mono_small,
            relief="flat",
            borderwidth=0,
            padx=6,
            pady=4,
            state="disabled",
        )
        self.preview.pack(fill="x")

        action_frame = ttk.Frame(right)
        action_frame.pack(fill="x", pady=(8, 0))
        self.run_button = ttk.Button(
            action_frame,
            text="Run",
            style="Accent.TButton",
            command=self._run_current,
        )
        self.run_button.pack(side="left")
        ttk.Button(
            action_frame, text="Copy Command", command=self._copy_preview
        ).pack(side="left", padx=(6, 0))

        manual = ttk.LabelFrame(self, text="Manual Command", padding=(9, 7))
        manual.pack(fill="x", pady=(10, 0))
        manual_row = ttk.Frame(manual)
        manual_row.pack(fill="x")
        ttk.Label(
            manual_row,
            text="pixi",
            style="MutedCard.TLabel",
            font=self.app.theme.fonts.mono,
        ).pack(side="left", padx=(0, 5))
        self.manual_var = tk.StringVar()
        self.manual_combo = ttk.Combobox(
            manual_row,
            textvariable=self.manual_var,
            values=self._command_history(),
            height=12,
        )
        self.manual_combo.pack(side="left", fill="x", expand=True)
        self.manual_combo.bind("<Return>", lambda _event: self._run_manual())
        self.auto_manifest_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            manual_row,
            text="Use current workspace",
            variable=self.auto_manifest_var,
            style="Card.TCheckbutton",
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            manual_row,
            text="Run",
            style="Accent.TButton",
            command=self._run_manual,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            manual_row, text="Copy", command=self._copy_manual
        ).pack(side="left", padx=(4, 0))
        ttk.Label(
            manual,
            text="Enter arguments after pixi, e.g. add numpy; a full pixi command is also accepted. Commands run directly without a shell.",
            style="MutedCard.TLabel",
            wraplength=960,
        ).pack(anchor="w", pady=(5, 0))

        self.apply_theme(colors)
        self._populate_tree()
        self._select_default()

    # ------------------------------------------------------------------
    def _on_middle_configure(self, event) -> None:
        if self._middle_sash_set or event.width < 500:
            return
        try:
            self.middle_pane.sashpos(0, int(event.width * 0.54))
            self._middle_sash_set = True
        except tk.TclError:
            pass

    def apply_theme(self, colors: Dict[str, str]) -> None:
        self.colors = colors
        for widget in (self.help_text, self.preview):
            widget.configure(
                background=colors["panel_alt"],
                foreground=colors["text"],
                insertbackground=colors["text"],
                selectbackground=colors["selected"],
                selectforeground=colors["selected_text"],
            )

    def _open_docs(self) -> None:
        webbrowser.open("https://pixi.sh/latest/reference/cli/")

    def refresh_context(self) -> None:
        """Rebuild the current form after the workspace/environment changed."""
        if self.current_spec is not None:
            self._build_form(self.current_spec)

    def _populate_tree(self) -> None:
        groups: Dict[str, str] = {}
        for spec in self.specs:
            if spec.group not in groups:
                group_id = "group:" + spec.group
                groups[spec.group] = group_id
                self.tree.insert(
                    "",
                    "end",
                    iid=group_id,
                    text=i18n.t(spec.group),
                    open=True,
                )
            self.tree.insert(
                groups[spec.group],
                "end",
                iid="cmd:" + spec.key,
                text=i18n.t(spec.title),
            )

    def _select_default(self) -> None:
        first = next(
            (spec for spec in self.specs if spec.key == "add"),
            self.specs[0] if self.specs else None,
        )
        if first:
            self.tree.selection_set("cmd:" + first.key)
            self.tree.see("cmd:" + first.key)
            self.current_spec = first
            self._build_form(first)

    def _on_tree_select(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        key = selection[0]
        if not key.startswith("cmd:"):
            return
        spec_key = key.split(":", 1)[1]
        spec = self.spec_by_key.get(spec_key)
        if spec:
            self.current_spec = spec
            self._build_form(spec)

    # ------------------------------------------------------------------
    def _env_display_values(self) -> Tuple[str, ...]:
        workspace = self.app.workspace
        names = workspace.env_names if workspace else []
        return tuple([i18n.t("(not specified)")] + names)

    def _platform_values(self) -> Tuple[str, ...]:
        workspace = self.app.workspace
        values = {"win-64", "linux-64", "osx-64", "osx-arm64"}
        if workspace:
            for env in workspace.envs:
                if env.platform:
                    values.add(env.platform)
            values.add(workspace.platform)
        return tuple(
            [i18n.t("(not specified)")] + sorted(value for value in values if value)
        )

    def _task_values(self) -> Tuple[str, ...]:
        workspace = self.app.workspace
        env = self.app.environment
        if not workspace or not env:
            return ()
        return tuple(task.name for task in workspace.tasks_for_env(env))

    def set_context_environment(self, environment: str) -> None:
        self.shared_environment = environment
        if not self.current_spec:
            return
        if "environment" not in self.vars:
            return
        value = self._environment_value(self.current_spec)
        self.vars["environment"].set(value)
        widget = self.field_widgets.get("environment")
        if widget is not None:
            try:
                widget.configure(
                    state="disabled"
                    if self._base_target(self.current_spec)
                    else "readonly"
                )
            except tk.TclError:
                pass

    def _base_target(self, spec: CommandSpec) -> bool:
        return bool(self.app.base_mode and spec.key in ("add", "remove"))

    def _remember_environment(self, variable: tk.Variable) -> None:
        value = str(variable.get())
        self.shared_environment = "" if value == i18n.t("(not specified)") else value

    def _environment_value(self, spec: CommandSpec) -> str:
        placeholder = i18n.t("(not specified)")
        if self._base_target(spec):
            return placeholder
        values = self._env_display_values()
        if self.shared_environment == "" and spec.key in ("add", "remove"):
            return placeholder
        if self.shared_environment and self.shared_environment in values:
            return str(self.shared_environment)
        if self.app.environment in values:
            return self.app.environment
        return placeholder

    def _field_default(self, field: FieldSpec, spec: CommandSpec) -> str:
        if field.kind == "env":
            return self._environment_value(spec)
        if field.default == "current":
            return self.app.environment or i18n.t("(not specified)")
        return field.default

    def _build_form(self, spec: CommandSpec) -> None:
        self.title_var.set(i18n.t(spec.title))
        self.summary_var.set(i18n.t(spec.summary))
        inner = self.form_scroll.inner
        clear_children(inner)
        self.vars = {}
        self.field_widgets = {}
        row = 0
        for field in spec.fields:
            label_text = field.label + (" *" if field.required else "")
            label = ttk.Label(inner, text=label_text, style="Muted.TLabel")
            label.grid(row=row, column=0, sticky="nw", pady=4, padx=(0, 8))
            if field.help:
                Tooltip(label, field.help)
            if field.kind == "check":
                var = tk.BooleanVar(value=False)
                widget = ttk.Checkbutton(inner, variable=var, text="Enabled")
                widget.grid(row=row, column=1, sticky="w", pady=4)
                self.vars[field.key] = var
                self.field_widgets[field.key] = widget
            elif field.kind in ("env", "platform"):
                values = (
                    self._env_display_values()
                    if field.kind == "env"
                    else self._platform_values()
                )
                var = tk.StringVar(value=self._field_default(field, spec))
                widget = ttk.Combobox(
                    inner,
                    textvariable=var,
                    values=values,
                    state=(
                        "disabled"
                        if field.kind == "env" and self._base_target(spec)
                        else "readonly"
                    ),
                    width=34,
                )
                widget.grid(row=row, column=1, sticky="ew", pady=4)
                self.vars[field.key] = var
                self.field_widgets[field.key] = widget
            elif field.kind == "combo":
                var = tk.StringVar(value=field.default)
                widget = ttk.Combobox(
                    inner,
                    textvariable=var,
                    values=field.values,
                    state="readonly",
                    width=34,
                )
                widget.grid(row=row, column=1, sticky="ew", pady=4)
                self.vars[field.key] = var
                self.field_widgets[field.key] = widget
            elif field.kind == "task":
                var = tk.StringVar(value=field.default)
                widget = ttk.Combobox(inner, textvariable=var, values=self._task_values())
                widget.grid(row=row, column=1, sticky="ew", pady=4)
                self.vars[field.key] = var
                self.field_widgets[field.key] = widget
            else:
                var = tk.StringVar(value=self._field_default(field, spec))
                widget = ttk.Entry(inner, textvariable=var, width=field.width)
                if field.key == "feature" and self._base_target(spec):
                    var.set("")
                    widget.configure(state="disabled")
                widget.grid(row=row, column=1, sticky="ew", pady=4)
                self.vars[field.key] = var
                self.field_widgets[field.key] = widget
            if field.help:
                hint = ttk.Label(
                    inner,
                    text=field.help,
                    style="Muted.TLabel",
                    wraplength=520,
                    justify="left",
                )
                hint.grid(row=row + 1, column=1, sticky="w", pady=(0, 2))
                row += 2
            else:
                row += 1
            var.trace_add("write", lambda *_: self._update_preview())
            if field.key == "environment" and not self._base_target(spec):
                var.trace_add(
                    "write",
                    lambda *_args, variable=var: self._remember_environment(
                        variable
                    ),
                )
        if self._base_target(spec):
            ttk.Label(
                inner,
                text="Base-dependency mode: this command affects all environments.",
                style="Muted.TLabel",
                wraplength=520,
                justify="left",
            ).grid(row=row, column=1, sticky="w", pady=(4, 0))
        inner.columnconfigure(1, weight=1)
        self.form_scroll.canvas.yview_moveto(0)
        if spec.terminal:
            self.run_button.configure(text="Open Terminal")
        else:
            self.run_button.configure(text="Run")
        self._update_preview()
        self._load_help(spec)
        i18n.localize_widget_tree(self)

    # ------------------------------------------------------------------
    def _value(self, key: str) -> str:
        variable = self.vars.get(key)
        if isinstance(variable, tk.BooleanVar):
            return bool(variable.get())
        value = variable.get() if variable is not None else ""
        value = str(value).strip()
        if value == i18n.t("(not specified)"):
            return ""
        return value

    def _tokens(self, key: str) -> List[str]:
        value = self._value(key)
        return split_user_args(str(value)) if value else []

    def _check(self, key: str) -> bool:
        variable = self.vars.get(key)
        return bool(variable.get()) if isinstance(variable, tk.BooleanVar) else False

    def _build_args(self, spec: CommandSpec) -> Tuple[List[str], str]:
        key = spec.key
        args: List[str] = []
        if key == "add":
            specs = self._tokens("specs")
            if not specs:
                return [], "Enter package(s) to add."
            args = ["add"]
            if self._check("pypi"):
                args.append("--pypi")
            for field_key, flag in (
                ("feature", "--feature"),
                ("environment", "--environment"),
                ("platform", "--platform"),
                ("index", "--index"),
            ):
                value = self._value(field_key)
                if value:
                    args += [flag, value]
            if self._check("editable"):
                args.append("--editable")
            if self._check("no_install"):
                args.append("--no-install")
            args += specs
        elif key == "remove":
            specs = self._tokens("specs")
            if not specs:
                return [], "Enter package(s) to remove."
            args = ["remove"]
            if self._check("pypi"):
                args.append("--pypi")
            for field_key, flag in (
                ("feature", "--feature"),
                ("environment", "--environment"),
                ("platform", "--platform"),
            ):
                value = self._value(field_key)
                if value:
                    args += [flag, value]
            args += specs
        elif key == "update":
            args = ["update"]
            env = self._value("environment")
            if env:
                args += ["--environment", env]
            platform = self._value("platform")
            if platform:
                args += ["--platform", platform]
            if self._check("dry_run"):
                args.append("--dry-run")
            args += self._tokens("packages")
        elif key == "upgrade":
            args = ["upgrade"]
            feature = self._value("feature")
            if feature:
                args += ["--feature", feature]
            env = self._value("environment")
            if env:
                args += ["--environment", env]
            if self._check("dry_run"):
                args.append("--dry-run")
            args += self._tokens("packages")
        elif key == "search":
            package = self._value("package")
            if not package:
                return [], "Enter a package name."
            args = ["search", package]
            channel = self._value("channel")
            if channel:
                args += ["--channel", channel]
            platform = self._value("platform")
            if platform:
                args += ["--platform", platform]
            limit = self._value("limit")
            if limit:
                args += ["--limit", limit]
        elif key == "install":
            args = ["install"]
            env = self._value("environment")
            if env:
                args += ["--environment", env]
            if self._check("frozen"):
                args.append("--frozen")
            if self._check("locked"):
                args.append("--locked")
        elif key == "lock":
            args = ["lock"]
            if self._check("check"):
                args.append("--check")
            if self._check("dry_run"):
                args.append("--dry-run")
        elif key == "clean":
            args = ["clean"]
            env = self._value("environment")
            if env:
                args += ["--environment", env]
            if self._check("activation_cache"):
                args.append("--activation-cache")
        elif key == "reinstall":
            args = ["reinstall"]
            env = self._value("environment")
            if env:
                args += ["--environment", env]
            if self._check("all"):
                args.append("--all")
            args += self._tokens("packages")
        elif key == "run":
            task = self._value("task")
            if not task:
                return [], "Enter a task name or command."
            args = ["run"]
            env = self._value("environment")
            if env:
                args += ["--environment", env]
            if self._check("clean_env"):
                args.append("--clean-env")
            if self._check("skip_deps"):
                args.append("--skip-deps")
            if self._check("dry_run"):
                args.append("--dry-run")
            args += split_user_args(task)
        elif key == "task-add":
            name = self._value("name")
            command = self._value("command")
            if not name or not command:
                return [], "Task name and command cannot be empty."
            args = ["task", "add", name, command]
            for field_key, flag in (
                ("description", "--description"),
                ("cwd", "--cwd"),
                ("feature", "--feature"),
                ("environment", "--environment"),
            ):
                value = self._value(field_key)
                if value:
                    args += [flag, value]
            depends = self._tokens("depends_on")
            if depends:
                args += ["--depends-on"] + depends
        elif key == "task-remove":
            names = self._tokens("names")
            if not names:
                return [], "Enter task name(s) to remove."
            args = ["task", "remove"] + names
            for field_key, flag in (
                ("feature", "--feature"),
                ("environment", "--environment"),
            ):
                value = self._value(field_key)
                if value:
                    args += [flag, value]
        elif key == "info":
            args = ["info"]
            if self._check("extended"):
                args.append("--extended")
        elif key == "shell":
            args = ["shell"]
            env = self._value("environment")
            if env:
                args += ["--environment", env]
        elif key == "init":
            args = ["init"]
            path = self._value("path")
            if not path:
                return [], "Enter a new workspace path."
            args.append(path)
            channel = self._value("channel")
            if channel:
                args += ["--channel", channel]
            platform = self._value("platform")
            if platform:
                args += ["--platform", platform]
            fmt = self._value("format")
            if fmt:
                args += ["--format", fmt]
        return args, ""

    def _update_preview(self) -> None:
        if not self.current_spec:
            return
        args, error = self._build_args(self.current_spec)
        if error:
            self._set_preview("（" + error + "）")
            return
        try:
            preview = self.app.preview_pixi_command(
                args, use_manifest=self.current_spec.use_manifest
            )
            self._set_preview(preview)
        except Exception as exc:
            self._set_preview("Failed to build command: {}".format(exc))

    def _set_preview(self, text: str) -> None:
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        self.preview.configure(state="disabled")

    def _copy_preview(self) -> None:
        text = self.preview.get("1.0", "end-1c").strip()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)

    def _load_help(self, spec: CommandSpec) -> None:
        cached = self._help_cache.get(spec.key)
        if cached:
            self._set_help(cached)
            return
        self._set_help("Loading help…")
        self._help_request += 1
        request_id = self._help_request
        self.app.help_async(
            list(spec.help_args),
            lambda text: self._on_help_loaded(spec, request_id, text),
        )

    def _on_help_loaded(self, spec: CommandSpec, request_id: int, text: str) -> None:
        if request_id != self._help_request or self.current_spec is not spec:
            return
        self._help_cache[spec.key] = text
        self._set_help(text)

    def _set_help(self, text: str) -> None:
        self.help_text.configure(state="normal")
        self.help_text.delete("1.0", "end")
        self.help_text.insert("1.0", text)
        self.help_text.configure(state="disabled")

    # ------------------------------------------------------------------
    def _run_current(self) -> None:
        spec = self.current_spec
        if not spec:
            return
        args, error = self._build_args(spec)
        if error:
            messagebox.showinfo("Command arguments", error, parent=self)
            return
        if spec.key == "remove":
            args = self._resolve_remove_scope(args)
            if args is None:
                return
        if not args:
            return
        if spec.terminal:
            self.app.open_pixi_terminal(
                args, title=spec.title, use_manifest=spec.use_manifest
            )
        else:
            self.app.run_pixi_command(
                args,
                title=spec.title,
                refresh=spec.refresh,
                dangerous=spec.dangerous,
                use_manifest=spec.use_manifest,
            )

    def _resolve_remove_scope(self, args: List[str]) -> Optional[List[str]]:
        """Avoid ``remove --environment default`` for a base dependency."""
        workspace = self.app.workspace
        if workspace is None or "--feature" in args:
            return args
        target = ""
        for index, value in enumerate(args):
            if value == "--environment" and index + 1 < len(args):
                target = args[index + 1]
                break
        names = split_user_args(self._value("specs"))
        if not names:
            return args
        scopes = workspace.scopes
        base_names = []
        env_names = []
        other_names = []
        for name in names:
            scope = scopes.scope_for(name)
            if scope == "base":
                base_names.append(name)
            elif scope.startswith("env:"):
                env_names.append(name)
            else:
                other_names.append(name)
        if not target:
            if base_names and (env_names or other_names):
                messagebox.showinfo(
                    "Remove scope conflict",
                    i18n.t("A single command cannot remove both base and environment-only dependencies."),
                    parent=self,
                )
                return None
            if not base_names:
                messagebox.showinfo(
                    "Remove base dependency",
                    i18n.t("These packages are not base dependencies: {}").format(", ".join(names)),
                    parent=self,
                )
                return None
            if not messagebox.askyesno(
                "Remove base dependency",
                i18n.t(
                    "{} is a base dependency. Removing it affects all environments.\n\nRemove it from the base dependencies?"
                ).format(", ".join(base_names)),
                parent=self,
            ):
                return None
            return args
        if base_names and (env_names or other_names):
            messagebox.showinfo(
                "Remove scope conflict",
                "{}\n{}\n{}".format(
                    i18n.t("A single command cannot remove both base and environment-only dependencies."),
                    i18n.t("Base dependencies: {}").format(", ".join(base_names)),
                    i18n.t("Other dependencies: {}").format(
                        ", ".join(env_names + other_names)
                    ),
                ),
                parent=self,
            )
            return None
        if not base_names:
            return args
        if not messagebox.askyesno(
            "Remove base dependency",
            i18n.t(
                "{} is a base dependency. Removing it affects all environments.\n\nRemove it from the base dependencies?"
            ).format(", ".join(base_names)),
            parent=self,
        ):
            return None
        index = args.index("--environment")
        return args[:index] + args[index + 2 :]

    def _command_history(self) -> Tuple[str, ...]:
        history = self.app.state.get_setting("command_history", [])
        if not isinstance(history, list):
            return ()
        return tuple(str(item) for item in history[:30])

    def _manual_tokens(self) -> List[str]:
        raw = self.manual_var.get().strip()
        if not raw:
            return []
        tokens = split_user_args(raw)
        if tokens and PathLikeName(tokens[0]) == "pixi":
            tokens = tokens[1:]
        return tokens

    def _run_manual(self) -> None:
        tokens = self._manual_tokens()
        if not tokens:
            messagebox.showinfo("Manual Command", "Enter a pixi command.", parent=self)
            return
        self.app.state.add_command_history(subprocess_line(tokens))
        self.manual_combo.configure(values=self._command_history())
        self.app.run_pixi_command(
            tokens,
            title="Manual Command",
            refresh=False,
            dangerous=False,
            use_manifest=bool(self.auto_manifest_var.get()),
        )

    def _copy_manual(self) -> None:
        text = self.manual_var.get().strip()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)


def PathLikeName(value: str) -> str:
    """Small helper to compare a command token without importing pathlib in UI."""
    text = str(value).strip()
    if text.lower().endswith(".exe"):
        text = text[:-4]
    return text.rsplit("\\", 1)[-1].rsplit("/", 1)[-1].lower()


def subprocess_line(tokens: Sequence[str]) -> str:
    import subprocess

    return subprocess.list2cmdline([str(item) for item in tokens])
