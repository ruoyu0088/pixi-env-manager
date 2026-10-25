"""Workspace overview tab."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Dict, Optional

from .. import i18n
from ..models import WorkspaceData
from .widgets import Tooltip


class OverviewTab(ttk.Frame):
    def __init__(self, master, app, colors: Dict[str, str]):
        super().__init__(master, padding=(14, 12))
        self.app = app
        self.colors = colors
        self.workspace: Optional[WorkspaceData] = None
        self.env_name = ""

        self.header = ttk.Frame(self)
        self.header.pack(fill="x")
        ttk.Label(self.header, text="Workspace Overview", style="Title.TLabel").pack(
            side="left"
        )
        self.name_var = tk.StringVar(value="No environment")
        ttk.Label(
            self.header, textvariable=self.name_var, style="Muted.TLabel"
        ).pack(side="left", padx=(10, 0), pady=(6, 0))

        self.body = ttk.Frame(self)
        self.body.pack(fill="both", expand=True, pady=(12, 0))

        self.workspace_card = ttk.LabelFrame(
            self.body, text="Workspace", padding=(12, 10)
        )
        self.workspace_card.pack(fill="x")
        self.path_var = tk.StringVar(value="—")
        self.root_var = tk.StringVar(value="—")
        self.platform_var = tk.StringVar(value="—")
        self.pixi_var = tk.StringVar(value="—")
        self.lock_var = tk.StringVar(value="—")
        self._add_row(self.workspace_card, 0, "Manifest", self.path_var, copy=True)
        self._add_row(self.workspace_card, 1, "Directory", self.root_var, copy=True)
        self._add_row(self.workspace_card, 2, "Platform", self.platform_var)
        self._add_row(self.workspace_card, 3, "Pixi", self.pixi_var)
        self._add_row(self.workspace_card, 4, "Lock file", self.lock_var)

        actions = ttk.Frame(self.workspace_card)
        actions.grid(row=5, column=0, columnspan=3, sticky="w", pady=(10, 0))
        self.install_button = ttk.Button(
            actions,
            text="Install / Update",
            style="Accent.TButton",
            command=self.app.install_env,
        )
        self.install_button.pack(side="left")
        self.lock_button = ttk.Button(
            actions, text="Relock", command=self.app.lock_env
        )
        self.lock_button.pack(side="left", padx=(7, 0))
        self.clean_button = ttk.Button(
            actions, text="Clean Environment…", command=self.app.clean_env
        )
        self.clean_button.pack(side="left", padx=(7, 0))
        self.open_button = ttk.Button(
            actions, text="Open Folder", command=self.app.open_workspace_folder
        )
        self.open_button.pack(side="left", padx=(7, 0))

        self.warning_var = tk.StringVar(value="")
        self.warning_label = ttk.Label(
            self.body,
            textvariable=self.warning_var,
            style="Warning.TLabel",
            wraplength=860,
            justify="left",
        )
        self.warning_label.pack(fill="x", pady=(8, 0))

        env_frame = ttk.LabelFrame(
            self.body, text="Environments", padding=(10, 8)
        )
        env_frame.pack(fill="both", expand=True, pady=(10, 0))
        columns = ("name", "features", "deps", "prefix")
        self.env_tree = ttk.Treeview(
            env_frame, columns=columns, show="headings", height=6
        )
        headings = {
            "name": "Environment",
            "features": "Feature",
            "deps": "Dependency count",
            "prefix": "Environment path",
        }
        widths = {"name": 120, "features": 170, "deps": 70, "prefix": 470}
        for column in columns:
            self.env_tree.heading(column, text=headings[column])
            self.env_tree.column(
                column, width=widths[column], anchor="w", stretch=column == "prefix"
            )
        y_scroll = ttk.Scrollbar(
            env_frame, orient="vertical", command=self.env_tree.yview
        )
        self.env_tree.configure(yscrollcommand=y_scroll.set)
        self.env_tree.pack(side="left", fill="both", expand=True)
        y_scroll.pack(side="right", fill="y")
        self.env_tree.bind("<Double-1>", self._activate_env)
        self.env_tree.bind("<Button-3>", self._env_menu)

        self.stats_var = tk.StringVar(value="")
        self.stats_label = ttk.Label(
            self.body, textvariable=self.stats_var, style="Muted.TLabel"
        )
        self.stats_label.pack(
            side="bottom", fill="x", pady=(8, 0), before=env_frame
        )

    def _add_row(
        self,
        parent,
        row: int,
        label: str,
        value_var: tk.StringVar,
        copy: bool = False,
    ) -> None:
        ttk.Label(parent, text=label, style="MutedCard.TLabel", width=7).grid(
            row=row, column=0, sticky="nw", pady=2
        )
        value = ttk.Label(
            parent,
            textvariable=value_var,
            style="Card.TLabel",
            wraplength=760,
            justify="left",
        )
        value.grid(row=row, column=1, sticky="w", pady=2)
        tip = Tooltip(value, value_var.get())
        value.bind(
            "<Configure>",
            lambda _event, t=tip, v=value_var: setattr(
                t, "text", i18n.translate_dynamic(v.get())
            ),
            add="+",
        )
        if copy:
            ttk.Button(
                parent,
                text="Copy",
                style="Small.TButton",
                command=lambda v=value_var: self._copy(v.get()),
            ).grid(row=row, column=2, padx=(8, 0))
        parent.columnconfigure(1, weight=1)

    def _copy(self, text: str) -> None:
        if not text or text == "—":
            return
        self.clipboard_clear()
        self.clipboard_append(text)

    def set_workspace(
        self, workspace: Optional[WorkspaceData], env_name: str
    ) -> None:
        self.workspace = workspace
        self.env_name = env_name
        self.refresh()

    def apply_colors(self, colors: Dict[str, str]) -> None:
        self.colors = colors
        self.refresh()

    def refresh(self) -> None:
        workspace = self.workspace
        if workspace is None:
            self.name_var.set("No environment")
            for var in (
                self.path_var,
                self.root_var,
                self.platform_var,
                self.pixi_var,
                self.lock_var,
            ):
                var.set("—")
            self.env_tree.delete(*self.env_tree.get_children())
            self.stats_var.set("")
            self.warning_var.set("")
            self._set_actions(False)
            return

        self.name_var.set(workspace.name or workspace.root.name)
        self.path_var.set(str(workspace.manifest))
        self.root_var.set(str(workspace.root))
        self.platform_var.set(workspace.platform or "—")
        self.pixi_var.set(workspace.pixi_version or "—")
        if not workspace.lock_exists:
            self.lock_var.set("Missing (not installed/locked)")
        elif workspace.lock_is_stale():
            self.lock_var.set("Manifest is newer than pixi.lock (relock recommended)")
        elif workspace.lock_is_unknown():
            self.lock_var.set("Lock file exists (freshness could not be verified)")
        else:
            self.lock_var.set(str(workspace.lock_path))

        self.env_tree.delete(*self.env_tree.get_children())
        for env in workspace.envs:
            self.env_tree.insert(
                "",
                "end",
                iid=env.name,
                values=(
                    env.name,
                    ", ".join(env.features),
                    len(env.dependencies) + len(env.pypi_dependencies),
                    env.prefix or "(not installed)",
                ),
            )
        if self.env_name and self.env_tree.exists(self.env_name):
            self.env_tree.selection_set(self.env_name)
            self.env_tree.see(self.env_name)

        packages = workspace.packages_for_env(self.env_name)
        explicit = sum(1 for package in packages if package.is_explicit)
        tasks = workspace.tasks_for_env(self.env_name)
        self.stats_var.set(
            "Environment: {}  ·  {} package(s) installed ({} explicit)  ·  {} task(s)  ·  {} environment(s)".format(
                self.env_name or "—",
                len(packages),
                explicit,
                len(tasks),
                len(workspace.envs),
            )
        )

        warnings = []
        current = workspace.get_env(self.env_name)
        if current and not current.installed:
            warnings.append("The current environment is not installed; packages and run functions may be unavailable.")
        if not workspace.lock_exists:
            warnings.append("No pixi.lock yet. Run Install / Update first.")
        elif workspace.lock_is_stale():
            warnings.append("pixi.lock is stale; relock the environment.")
        elif workspace.lock_is_unknown():
            warnings.append("Could not verify whether pixi.lock is current; relocking is recommended.")
        error = workspace.package_errors.get(self.env_name)
        if error:
            warnings.append("Failed to read packages: " + error.splitlines()[0])
        if workspace.task_error:
            warnings.append("Failed to read tasks: " + workspace.task_error.splitlines()[0])
        if warnings:
            self.warning_var.set("  ".join("⚠ " + item for item in warnings))
            self.warning_label.configure(style="Warning.TLabel")
        else:
            self.warning_var.set("")
        self._set_actions(True)

    def _set_actions(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for button in (
            self.install_button,
            self.lock_button,
            self.clean_button,
            self.open_button,
        ):
            button.configure(state=state)

    def _activate_env(self, _event=None) -> None:
        selection = self.env_tree.selection()
        if selection:
            self.app.set_environment(selection[0])

    def _env_menu(self, event) -> None:
        row = self.env_tree.identify_row(event.y)
        if not row:
            return
        self.env_tree.selection_set(row)
        menu = tk.Menu(self, tearoff=0)
        self.app.theme.style_menu(menu)
        menu.add_command(
            label="Switch to this environment", command=lambda: self.app.set_environment(row)
        )
        menu.add_command(label="Copy Environment Path", command=lambda: self._copy_env_path(row))
        i18n.localize_menu(menu)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _copy_env_path(self, env_name: str) -> None:
        if not self.workspace:
            return
        env = self.workspace.get_env(env_name)
        if env:
            self._copy(env.prefix)
