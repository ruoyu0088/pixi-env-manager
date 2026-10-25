"""Application window and integration layer."""

from __future__ import annotations

import os
import queue
import sys
import threading
import time
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable, Dict, List, Optional

from .. import i18n
from ..jobs import JobManager, open_terminal
from ..models import Package, TaskInfo, WorkspaceData, manifest_for_path
from ..pixi import PixiClient, PixiError, find_pixi
from ..state import AppState
from ..util import shorten_path, split_user_args, truncate_text
from ..workspace_init import build_init_args, default_platform
from .commands_tab import CommandsTab
from .console_panel import ConsolePanel
from .dialogs import (
    AddEnvironmentDialog,
    NewWorkspaceDialog,
    OpenEnvironmentDialog,
    RemoveEnvironmentDialog,
    SettingsDialog,
    TaskArgsDialog,
    show_error,
    show_info,
)
from .editor_tab import EditorTab
from .libraries_tab import LibrariesTab
from .overview_tab import OverviewTab
from .python_tab import PythonTab
from .sidebar import QuickSidebar
from .tasks_tab import TasksTab
from .theme import ThemeManager, enable_dpi_awareness
from .widgets import Tooltip, copy_text, open_in_explorer


class MainWindow:
    def __init__(self, root: tk.Tk, initial_path: Optional[Path] = None):
        self.root = root
        self.state = AppState()
        i18n.set_language(str(self.state.get_setting("language", "zh") or "zh"))
        i18n.install_messagebox_translation()
        self._last_localize = 0.0
        self.theme = ThemeManager(root)
        self.theme.apply(str(self.state.get_setting("theme", "light")))
        self.pixi = PixiClient(str(self.state.get_setting("pixi_path", "") or ""))
        self.job_manager = JobManager()
        self.ui_queue: "queue.Queue[Callable[[], None]]" = queue.Queue()
        self.workspace: Optional[WorkspaceData] = None
        self.environment: str = ""
        self.base_mode = False
        self._loading = False
        self._session = 0
        self._closing = False
        self._layout_ready = False
        self._layout_attempts = 0
        try:
            self._sidebar_width = int(
                self.state.get_setting("layout_sidebar_width", 300) or 300
            )
        except (TypeError, ValueError):
            self._sidebar_width = 300
        try:
            self._console_height = int(
                self.state.get_setting("layout_console_height", 245) or 245
            )
        except (TypeError, ValueError):
            self._console_height = 245
        self._sidebar_collapsed = bool(
            self.state.get_setting("layout_sidebar_collapsed", False)
        )
        self._console_collapsed = bool(
            self.state.get_setting("layout_console_collapsed", False)
        )
        self._layout_save_after: Optional[str] = None

        self.root.title("Pixi Environment Manager")
        self.root.minsize(1040, 680)
        self._restore_geometry()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._build_ui()
        i18n.localize_widget_tree(self.root)
        self.root.bind("<Control-o>", lambda _event: self.open_environment_dialog())
        self.root.bind("<F5>", lambda _event: self.refresh_current())
        self.root.bind("<Control-b>", self._toggle_sidebar_event)
        self.root.bind("<Control-j>", self._toggle_console_event)
        self._apply_theme(str(self.state.get_setting("theme", "light")))
        self._rebuild_recent_menu()
        self._refresh_pixi_badge()
        self.root.after(50, self._poll)
        self.root.after(200, self._restore_layout)

        if initial_path:
            self.root.after(150, lambda: self.open_environment(initial_path))
        else:
            self.root.after(250, self._auto_open_recent)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.topbar = ttk.Frame(self.root, style="Topbar.TFrame", padding=(10, 7))
        self.topbar.pack(fill="x")
        left = ttk.Frame(self.topbar, style="Topbar.TFrame")
        left.pack(side="left", fill="x", expand=True)
        right = ttk.Frame(self.topbar, style="Topbar.TFrame")
        right.pack(side="right")

        self.open_button = ttk.Button(
            left, text="Open Environment", style="Accent.TButton", command=self.open_environment_dialog
        )
        self.open_button.pack(side="left")
        self.recent_button = ttk.Menubutton(left, text="Recent  ▾")
        self.recent_menu = tk.Menu(self.recent_button, tearoff=0)
        self.recent_button.configure(menu=self.recent_menu)
        self.recent_button.pack(side="left", padx=(7, 0))

        ttk.Separator(left, orient="vertical").pack(
            side="left", fill="y", padx=(12, 10), pady=2
        )
        self.workspace_name_var = tk.StringVar(value="No environment")
        ttk.Label(
            left,
            textvariable=self.workspace_name_var,
            style="CardTitle.TLabel",
        ).pack(side="left")
        self.workspace_path_var = tk.StringVar(value="Open a pixi.toml / pyproject.toml")
        self.path_label = ttk.Label(
            left,
            textvariable=self.workspace_path_var,
            style="SmallCard.TLabel",
            cursor="hand2",
        )
        self.path_label.pack(side="left", padx=(8, 0), pady=(2, 0))
        self.path_tooltip = Tooltip(self.path_label, "")
        self.path_label.bind("<Button-1>", lambda _event: self._copy_workspace_path())

        self.env_var = tk.StringVar()
        self.env_combo = ttk.Combobox(
            right,
            textvariable=self.env_var,
            state="readonly",
            width=18,
        )
        self.env_combo.pack(side="left")
        self.env_combo.bind("<<ComboboxSelected>>", self._on_env_selected)
        self.env_manage_button = ttk.Menubutton(
            right, text="Environments  ▾", style="TMenubutton"
        )
        self.env_manage_menu = tk.Menu(self.env_manage_button, tearoff=0)
        self.env_manage_menu.add_command(
            label="Add Environment…", command=self.open_add_environment
        )
        self.env_manage_menu.add_command(
            label="Delete Current Environment…", command=self.open_remove_environment
        )
        self.env_manage_button.configure(menu=self.env_manage_menu)
        self.env_manage_button.pack(side="left", padx=(7, 0))
        self.theme.style_menu(self.env_manage_menu)
        self.refresh_button = ttk.Button(
            right, text="Refresh", command=self.refresh_current
        )
        self.refresh_button.pack(side="left", padx=(7, 0))
        ttk.Button(right, text="Settings", command=self.open_settings).pack(
            side="left", padx=(7, 0)
        )

        self.main_pane = ttk.Panedwindow(self.root, orient="vertical")
        self.main_pane.pack(fill="both", expand=True)
        self.top_pane = ttk.Panedwindow(self.main_pane, orient="horizontal")
        self.main_pane.add(self.top_pane, weight=1)

        self.sidebar = QuickSidebar(self.top_pane, self, self.theme.colors)
        self.top_pane.add(self.sidebar, weight=0)

        self.notebook = ttk.Notebook(self.top_pane)
        self.top_pane.add(self.notebook, weight=1)

        self.overview_tab = OverviewTab(self.notebook, self, self.theme.colors)
        self.libraries_tab = LibrariesTab(self.notebook, self, self.theme.colors)
        self.tasks_tab = TasksTab(self.notebook, self, self.theme.colors)
        self.python_tab = PythonTab(self.notebook, self, self.theme.colors)
        self.commands_tab = CommandsTab(self.notebook, self, self.theme.colors)
        self.editor_tab = EditorTab(self.notebook, self, self.theme.colors)
        for tab, label in (
            (self.overview_tab, "Overview"),
            (self.libraries_tab, "Packages"),
            (self.tasks_tab, "Task"),
            (self.python_tab, "Python"),
            (self.commands_tab, "Command"),
            (self.editor_tab, "pixi.toml"),
        ):
            self.notebook.add(tab, text=label)

        self.console = ConsolePanel(
            self.main_pane,
            colors=self.theme.colors,
            mono_font=self.theme.fonts.mono_small,
            max_lines=int(self.state.get_setting("console_max_lines", 50000)),
            on_stop=self.stop_job,
            on_stop_all=self.stop_all_jobs,
        )
        self.main_pane.add(self.console, weight=0)

        status = ttk.Frame(self.root, style="Topbar.TFrame", padding=(10, 3))
        status.pack(fill="x")
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(
            status, textvariable=self.status_var, style="Status.TLabel", anchor="w"
        )
        self.status_label.pack(side="left", fill="x", expand=True)
        self.pixi_status_var = tk.StringVar(value="Pixi: checking…")
        ttk.Label(
            status, textvariable=self.pixi_status_var, style="SmallCard.TLabel"
        ).pack(side="right", padx=(10, 0))
        self.job_status_var = tk.StringVar(value="Idle")
        ttk.Label(
            status, textvariable=self.job_status_var, style="SmallCard.TLabel"
        ).pack(side="right", padx=(10, 0))

        self._set_actions_enabled(False)

    def _restore_layout(self) -> None:
        if self._layout_ready:
            return
        self.root.update_idletasks()
        width = self.top_pane.winfo_width()
        height = self.main_pane.winfo_height()
        if width < 400 or height < 300:
            self._layout_attempts += 1
            if self._layout_attempts < 20:
                self.root.after(50, self._restore_layout)
            return
        sidebar_width = max(180, min(int(self._sidebar_width), width - 400))
        console_height = max(100, min(int(self._console_height), height - 200))
        try:
            self.top_pane.sashpos(
                0, 0 if self._sidebar_collapsed else sidebar_width
            )
            self.main_pane.sashpos(
                0,
                height - 1
                if self._console_collapsed
                else height - console_height,
            )
        except tk.TclError:
            self._layout_attempts += 1
            if self._layout_attempts < 20:
                self.root.after(50, self._restore_layout)
            return
        self._sidebar_width = sidebar_width
        self._console_height = console_height
        self._layout_ready = True
        self.top_pane.bind(
            "<ButtonRelease-1>", self._schedule_layout_save, add="+"
        )
        self.main_pane.bind(
            "<ButtonRelease-1>", self._schedule_layout_save, add="+"
        )

    def _schedule_layout_save(self, _event=None) -> None:
        if self._layout_save_after is not None:
            try:
                self.root.after_cancel(self._layout_save_after)
            except tk.TclError:
                pass
        self._layout_save_after = self.root.after(
            300, self._save_layout_state
        )

    def _save_layout_state(self, save: bool = True) -> None:
        self._layout_save_after = None
        if not self._layout_ready:
            return
        try:
            sidebar_position = self.top_pane.sashpos(0)
            sidebar_width = self.top_pane.winfo_width()
            if sidebar_position > 80:
                self._sidebar_width = sidebar_position
                self._sidebar_collapsed = False
            elif sidebar_position <= 1:
                self._sidebar_collapsed = True
            else:
                self._sidebar_width = max(180, sidebar_position)

            main_height = self.main_pane.winfo_height()
            console_position = self.main_pane.sashpos(0)
            console_height = main_height - console_position
            if console_height > 40:
                self._console_height = console_height
                self._console_collapsed = False
            elif not self._console_collapsed:
                self._console_collapsed = True

            updates = {
                "layout_sidebar_width": int(self._sidebar_width),
                "layout_console_height": int(self._console_height),
                "layout_sidebar_collapsed": self._sidebar_collapsed,
                "layout_console_collapsed": self._console_collapsed,
            }
            if save:
                self.state.update_settings(updates)
            else:
                for key, value in updates.items():
                    self.state.set_setting(key, value, save=False)
        except (tk.TclError, ValueError):
            pass

    def _toggle_sidebar_event(self, _event=None):
        self.toggle_sidebar()
        return "break"

    def _toggle_console_event(self, _event=None):
        self.toggle_console()
        return "break"

    def toggle_sidebar(self) -> None:
        if not self._layout_ready:
            return
        try:
            current = self.top_pane.sashpos(0)
            if current <= 1:
                width = self.top_pane.winfo_width()
                target = max(180, min(int(self._sidebar_width), width - 400))
                self.top_pane.sashpos(0, target)
                self._sidebar_width = target
                self._sidebar_collapsed = False
                self.set_status("Sidebar expanded")
            else:
                self._sidebar_width = max(180, current)
                self.top_pane.sashpos(0, 0)
                self._sidebar_collapsed = True
                self.set_status("Sidebar collapsed (Ctrl+B)")
            self._save_layout_state(save=True)
        except tk.TclError:
            pass

    def toggle_console(self) -> None:
        if not self._layout_ready:
            return
        try:
            height = self.main_pane.winfo_height()
            current = self.main_pane.sashpos(0)
            console_height = height - current
            if self._console_collapsed or console_height <= 40:
                target = max(100, min(int(self._console_height), height - 200))
                self.main_pane.sashpos(0, height - target)
                self._console_height = target
                self._console_collapsed = False
                self.set_status("Output panel expanded")
            else:
                self._console_height = max(100, console_height)
                self.main_pane.sashpos(0, max(1, height - 1))
                self._console_collapsed = True
                self.set_status("Output panel collapsed (Ctrl+L)")
            self._save_layout_state(save=True)
        except tk.TclError:
            pass

    def _set_actions_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.refresh_button.configure(state=state)
        self.env_combo.configure(state="readonly" if enabled else "disabled")
        self._update_env_manage_state()

    def _update_env_manage_state(self) -> None:
        if not hasattr(self, "env_manage_menu"):
            return
        busy = self._loading or self.job_manager.busy
        add_state = (
            "normal"
            if self.workspace is not None and not busy
            else "disabled"
        )
        remove_state = (
            "normal"
            if self.workspace is not None
            and bool(self.environment)
            and self.environment != "default"
            and not self.base_mode
            and not busy
            else "disabled"
        )
        try:
            self.env_manage_menu.entryconfigure(0, state=add_state)
            self.env_manage_menu.entryconfigure(1, state=remove_state)
            i18n.localize_menu(self.env_manage_menu)
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Theme / settings
    # ------------------------------------------------------------------
    def _apply_theme(self, name: str) -> None:
        self.theme.apply(name)
        self.state.set_setting("theme", self.theme.name)
        try:
            self.sidebar.apply_colors(self.theme.colors)
            self.overview_tab.apply_colors(self.theme.colors)
            self.libraries_tab.apply_theme(self.theme.colors)
            self.tasks_tab.apply_theme(self.theme.colors)
            self.python_tab.apply_theme(self.theme.colors)
            self.commands_tab.apply_theme(self.theme.colors)
            self.editor_tab.apply_theme(self.theme.colors)
            self.console.apply_colors(self.theme.colors, self.theme.fonts.mono_small)
            self.commands_tab.form_scroll.set_background(self.theme.colors["bg"])
            self.theme.style_menu(self.recent_menu)
            self.theme.style_menu(self.env_manage_menu)
            i18n.localize_menu(self.recent_menu)
            i18n.localize_menu(self.env_manage_menu)
        except tk.TclError:
            pass

    def open_settings(self) -> None:
        dialog = SettingsDialog(
            self.root,
            pixi_path=str(self.state.get_setting("pixi_path", "") or ""),
            theme_name=self.theme.name,
            console_max_lines=int(self.state.get_setting("console_max_lines", 50000)),
            history_count=len(self.state.recent()),
            language=str(self.state.get_setting("language", "zh") or "zh"),
            terminal=str(self.state.get_setting("terminal", "") or ""),
        )
        self.root.wait_window(dialog)
        if not dialog.result:
            return
        result = dialog.result
        old_language = str(self.state.get_setting("language", "zh") or "zh")
        self.state.update_settings(
            {
                "pixi_path": result["pixi_path"],
                "language": result["language"],
                "terminal": str(result.get("terminal") or ""),
                "console_max_lines": result["console_max_lines"],
                "theme": str(result["theme"]),
            }
        )
        self.pixi = PixiClient(str(result["pixi_path"]) or "")
        self.console.set_max_lines(int(result["console_max_lines"]))
        self._apply_theme(str(result["theme"]))
        if result.get("clear_history"):
            self.state.clear_recent()
            self._rebuild_recent_menu()
        self._refresh_pixi_badge()
        self.set_status("Settings saved")
        if result["language"] != old_language:
            messagebox.showinfo(
                "Language",
                "Language saved. Restart the application to apply it.",
                parent=self.root,
            )

    def _refresh_pixi_badge(self) -> None:
        if not self.pixi.available:
            self.pixi_status_var.set("Pixi: not found")
            self.set_status("Pixi not found. Click Settings to choose pixi.exe.", danger=True)
            return
        self.pixi_status_var.set("Pixi: checking…")

        def work():
            return self.pixi.version()

        def done(version: str) -> None:
            self.pixi_status_var.set("Pixi: " + (version or "Unknown version"))

        def error(exc: Exception) -> None:
            self.pixi_status_var.set("Pixi: cannot run")
            self.set_status(str(exc), danger=True)

        self.run_async(work, done, error)

    # ------------------------------------------------------------------
    # Async plumbing
    # ------------------------------------------------------------------
    def run_async(
        self,
        worker: Callable[[], object],
        on_success: Optional[Callable[[object], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        def target() -> None:
            try:
                result = worker()
            except Exception as exc:  # noqa: BLE001 - delivered to the UI
                if on_error:
                    self.ui_queue.put(lambda e=exc: on_error(e))
                else:
                    self.ui_queue.put(
                        lambda e=exc: self._report_error("Operation failed", e)
                    )
            else:
                if on_success:
                    self.ui_queue.put(lambda r=result: on_success(r))

        threading.Thread(target=target, daemon=True).start()

    def _poll(self) -> None:
        if self._closing:
            return
        try:
            while True:
                callback = self.ui_queue.get_nowait()
                try:
                    callback()
                except Exception:
                    self.console.append_system(traceback.format_exc(), "error")
        except queue.Empty:
            pass
        if self._closing:
            return
        for event in self.job_manager.drain():
            self._handle_job_event(event)
        now = time.monotonic()
        if (
            i18n.current_language() != "zh"
            and now - self._last_localize >= 0.4
        ):
            self._last_localize = now
            i18n.localize_widget_tree(self.root)
        if not self._closing:
            self.root.after(45, self._poll)

    # ------------------------------------------------------------------
    # Open / switch / refresh
    # ------------------------------------------------------------------
    def open_environment_dialog(self) -> None:
        if self._loading:
            return
        if not self._confirm_editor_before_switch():
            return
        initial = str(self.state.get_setting("last_open_dir", "") or "")
        dialog = OpenEnvironmentDialog(self.root, initial_dir=initial)
        self.root.wait_window(dialog)
        if dialog.result:
            self.open_environment(Path(dialog.result))
        elif dialog.new_workspace_path is not None:
            self.open_new_workspace_dialog(Path(dialog.new_workspace_path))

    def open_new_workspace_dialog(self, initial_path: Path) -> None:
        if self._loading or self.job_manager.busy:
            messagebox.showinfo(
                "Tasks are running",
                "Stop all running tasks and wait for refresh before creating a workspace.",
                parent=self.root,
            )
            return
        if self.workspace is not None and self.editor_tab.is_dirty:
            messagebox.showinfo(
                "Unsaved changes",
                "Save or discard changes to the current manifest before creating a workspace.",
                parent=self.root,
            )
            return
        platform = (
            self.workspace.platform if self.workspace else default_platform()
        )
        dialog = NewWorkspaceDialog(
            self.root,
            initial_path=str(initial_path),
            default_platform=platform or default_platform(),
        )
        self.root.wait_window(dialog)
        if dialog.result:
            self.create_new_workspace(dialog.result)

    def create_new_workspace(self, result: Dict[str, object]) -> None:
        if not self.pixi.available:
            messagebox.showerror(
                "Pixi not found",
                "Set pixi.exe in Settings or add Pixi to PATH first.",
                parent=self.root,
            )
            return
        if self._loading or self.job_manager.has_mutating():
            messagebox.showinfo(
                "Tasks are running",
                "Only one pixi command that modifies the environment/manifest may run at a time.\nWait for the current command to finish.",
                parent=self.root,
            )
            return
        path = Path(str(result["path"]))
        channels = [str(item) for item in result.get("channels", [])]
        platforms = [str(item) for item in result.get("platforms", [])]
        args = build_init_args(path, channels, platforms)
        title = "Create workspace {}".format(path.name)
        try:
            job = self.job_manager.start(
                title,
                [self.pixi.require()] + args,
                cwd=path.parent if path.parent.exists() else None,
                extra={
                    "workspace_init": str(path),
                    "mutating": True,
                },
            )
        except Exception as exc:
            self._report_error("Could not start command", exc)
            return
        self._job_started(job)
        self.set_status("Creating {}".format(path))

    def open_environment(
        self, path: Path, preferred_env: str = "", add_recent: bool = True
    ) -> None:
        manifest = manifest_for_path(path)
        if manifest is None:
            messagebox.showerror(
                "Manifest not found",
                "No pixi.toml or pyproject.toml under:\n{}".format(path),
                parent=self.root,
            )
            return
        if self._loading:
            # Saving a dirty editor can kick off a refresh just before the
            # user picks a new workspace.  Invalidate that refresh and let the
            # explicit open win.
            self._session += 1
            self._loading = False
        self._loading = True
        self._session += 1
        token = self._session
        self.open_button.configure(state="disabled")
        self._set_actions_enabled(False)
        self.set_status("Opening {}…".format(manifest.parent.name))
        self.state.set_setting("last_open_dir", str(manifest.parent))

        def worker() -> WorkspaceData:
            return self.pixi.workspace(manifest, preferred_env=preferred_env)

        def success(workspace: WorkspaceData) -> None:
            if token != self._session:
                return
            self._loading = False
            self.open_button.configure(state="normal")
            self._set_actions_enabled(True)
            self.workspace = workspace
            self.environment = (
                preferred_env
                if preferred_env in workspace.env_names
                else (workspace.default_env().name if workspace.default_env() else "default")
            )
            self.base_mode = self.state.is_base_mode(workspace.manifest)
            if preferred_env and preferred_env != "default":
                self.base_mode = False
                self.state.set_base_mode(workspace.manifest, False)
            if self.base_mode:
                default = workspace.default_env()
                self.environment = default.name if default else self.environment
            if add_recent:
                self.state.add_recent(
                    workspace.manifest, self.environment, workspace.name
                )
            self.commands_tab.set_context_environment(self.environment)
            self._apply_workspace()
            self.notebook.select(self.overview_tab)
            self._rebuild_recent_menu()
            self.set_status(
                "Opened {} / {}".format(
                    workspace.name,
                    self._base_label() if self.base_mode else self.environment,
                )
            )
            self.console.append_system(
                "Workspace opened: {}  [{}]".format(workspace.manifest, self.environment),
                "info",
            )
            if workspace.package_errors.get(self.environment):
                error = workspace.package_errors[self.environment]
                self.console.append_system(
                    "Failed to read packages: " + truncate_text(error, 300), "error"
                )
                self.set_status("Environment opened, but packages could not be read", danger=True)
            if workspace.task_error:
                self.console.append_system(
                    "Failed to read tasks: " + truncate_text(workspace.task_error, 300),
                    "error",
                )

        def error(exc: Exception) -> None:
            if token != self._session:
                return
            self._loading = False
            self.open_button.configure(state="normal")
            self._set_actions_enabled(self.workspace is not None)
            self._report_error("Could not open environment", exc)

        self.run_async(worker, success, error)

    def _auto_open_recent(self) -> None:
        if not self.pixi.available:
            return
        for item in self.state.recent():
            manifest = Path(str(item.get("manifest") or ""))
            if manifest.is_file():
                self.open_environment(
                    manifest,
                    preferred_env=str(item.get("environment") or ""),
                    add_recent=False,
                )
                return

    def _apply_workspace(self) -> None:
        workspace = self.workspace
        if workspace is None:
            return
        if self.environment not in workspace.env_names:
            default = workspace.default_env()
            self.environment = default.name if default else ""
        if self.base_mode:
            default = workspace.default_env()
            if default is not None:
                self.environment = default.name
        self.workspace_name_var.set(
            truncate_text(workspace.name or workspace.root.name, 30)
        )
        path_text = shorten_path(str(workspace.manifest), 62)
        self.workspace_path_var.set(path_text)
        self.path_tooltip.text = str(workspace.manifest)
        base_label = self._base_label()
        self.env_combo.configure(values=(base_label, *workspace.env_names))
        self.env_var.set(base_label if self.base_mode else self.environment)
        try:
            self.notebook.tab(self.editor_tab, text=workspace.manifest.name)
        except tk.TclError:
            pass
        display_env = base_label if self.base_mode else self.environment
        self.root.title(
            "Pixi Environment Manager - {} [{}]".format(
                workspace.name or workspace.root.name, display_env
            )
        )
        self.overview_tab.set_workspace(workspace, self.environment)
        self.libraries_tab.set_workspace(
            workspace, self.environment, base_mode=self.base_mode
        )
        self.tasks_tab.set_workspace(
            workspace, self.environment, base_mode=self.base_mode
        )
        self.python_tab.set_workspace(
            workspace, self.environment, base_mode=self.base_mode
        )
        self.commands_tab.refresh_context()
        self.editor_tab.set_workspace(workspace)
        self.sidebar.set_workspace(workspace, self.environment)
        self._set_actions_enabled(True)
        if self.base_mode:
            self.set_status(
                "Base-dependency view (shared) · Task/Python run in {}".format(
                    self.environment
                )
            )
        elif self.environment == "default":
            self.set_status(
                "Current environment: default · add/remove affects only default; switch to Base dependencies for shared dependencies"
            )

    def _base_label(self) -> str:
        return i18n.t("Base dependencies")

    def refresh_current(self, preferred_env: Optional[str] = None) -> None:
        if not self.workspace or self._loading:
            return
        workspace = self.workspace
        self._loading = True
        self._session += 1
        token = self._session
        self._set_actions_enabled(False)
        self.set_status("Refreshing environment…")
        target_hint = (
            preferred_env if preferred_env is not None else self.environment
        )

        def worker() -> WorkspaceData:
            return self.pixi.workspace(
                workspace.manifest, preferred_env=target_hint
            )

        def success(new_workspace: WorkspaceData) -> None:
            if token != self._session:
                return
            self._loading = False
            self.workspace = new_workspace
            if target_hint not in new_workspace.env_names:
                default = new_workspace.default_env()
                self.environment = default.name if default else ""
            else:
                self.environment = target_hint
            if preferred_env is not None:
                self.base_mode = False
                self.state.set_base_mode(new_workspace.manifest, False)
            elif self.base_mode:
                default = new_workspace.default_env()
                if default is not None:
                    self.environment = default.name
            if preferred_env is not None:
                self.commands_tab.set_context_environment(self.environment)
            self.state.add_recent(
                new_workspace.manifest, self.environment, new_workspace.name
            )
            self._apply_workspace()
            self._rebuild_recent_menu()
            self.editor_tab.reload_if_clean()
            self._set_actions_enabled(True)
            self.set_status("Refreshed")
            if new_workspace.package_errors.get(self.environment):
                self.set_status("Refreshed, but packages could not be read", danger=True)

        def error(exc: Exception) -> None:
            if token != self._session:
                return
            self._loading = False
            self._set_actions_enabled(True)
            self._report_error("Refresh failed", exc)

        self.run_async(worker, success, error)

    def _on_env_selected(self, _event=None) -> None:
        value = self.env_var.get().strip()
        if value == self._base_label():
            self.set_base_mode(True)
            return
        if value and value != self.environment:
            self.set_environment(value)
        elif self.base_mode:
            self.set_environment(self.environment)

    def set_base_mode(self, enabled: bool) -> None:
        if self._loading or self.workspace is None:
            return
        if enabled == self.base_mode:
            return
        default = self.workspace.default_env()
        if default is None:
            return
        self.base_mode = enabled
        self.environment = default.name
        self.state.set_base_mode(self.workspace.manifest, enabled)
        self.commands_tab.set_context_environment(self.environment)
        if enabled:
            self.state.add_recent(
                self.workspace.manifest, self.environment, self.workspace.name
            )
        self.env_var.set(
            self._base_label() if enabled else self.environment
        )
        self.overview_tab.set_workspace(self.workspace, self.environment)
        self.libraries_tab.set_workspace(
            self.workspace, self.environment, base_mode=enabled
        )
        self.tasks_tab.set_workspace(
            self.workspace, self.environment, base_mode=enabled
        )
        self.python_tab.set_workspace(
            self.workspace, self.environment, base_mode=enabled
        )
        self.sidebar.set_workspace(self.workspace, self.environment)
        self.commands_tab.refresh_context()
        self._rebuild_recent_menu()
        display_env = self._base_label() if enabled else self.environment
        self.root.title(
            "Pixi Environment Manager - {} [{}]".format(
                self.workspace.name or self.workspace.root.name, display_env
            )
        )
        self._update_env_manage_state()
        if enabled:
            self.set_status(
                "Base-dependency view (shared) · Task/Python run in {}".format(
                    self.environment
                )
            )
        else:
            self.set_status(
                "Current environment: default · add/remove affects only default; switch to Base dependencies for shared dependencies"
                if self.environment == "default"
                else "Current environment: {}".format(self.environment)
            )

    def set_environment(self, env_name: str) -> None:
        if self._loading:
            self.env_var.set(
                self._base_label() if self.base_mode else self.environment
            )
            return
        if not self.workspace:
            return
        if env_name == self.environment and not self.base_mode:
            return
        if env_name not in self.workspace.env_names:
            return
        was_base = self.base_mode
        self.base_mode = False
        if was_base:
            self.state.set_base_mode(self.workspace.manifest, False)
        self.environment = env_name
        self.env_var.set(env_name)
        self.commands_tab.set_context_environment(env_name)
        self.state.add_recent(self.workspace.manifest, env_name, self.workspace.name)
        self.overview_tab.set_workspace(self.workspace, env_name)
        self.libraries_tab.set_workspace(self.workspace, env_name)
        self.tasks_tab.set_workspace(
            self.workspace, env_name, base_mode=False
        )
        self.python_tab.set_workspace(
            self.workspace, env_name, base_mode=False
        )
        self.commands_tab.refresh_context()
        self.sidebar.set_workspace(self.workspace, env_name)
        self._rebuild_recent_menu()
        self.root.title(
            "Pixi Environment Manager - {} [{}]".format(
                self.workspace.name or self.workspace.root.name, env_name
            )
        )
        self._update_env_manage_state()
        if (
            env_name not in self.workspace.packages_by_env
            or env_name in self.workspace.package_errors
        ):
            self._load_env_packages(env_name)
        else:
            self._set_actions_enabled(True)
            self.set_status(
                "Current environment: default · add/remove affects only default; switch to Base dependencies for shared dependencies"
                if env_name == "default"
                else "Current environment: {}".format(env_name)
            )

    def _load_env_packages(self, env_name: str) -> None:
        if not self.workspace:
            return
        workspace = self.workspace
        self.libraries_tab.set_loading("Reading packages for {}…".format(env_name))
        self.set_status("Reading packages for environment {}…".format(env_name))

        def worker():
            return self.pixi.load_packages(workspace.manifest, env_name)

        def success(packages: List[Package]) -> None:
            if (
                self.workspace is not workspace
                or env_name != self.environment
            ):
                return
            workspace.packages_by_env[env_name] = packages
            workspace.package_errors.pop(env_name, None)
            self.libraries_tab.set_workspace(
                workspace, env_name, base_mode=self.base_mode
            )
            self.overview_tab.set_workspace(workspace, env_name)
            self.set_status("Switched to environment {}".format(env_name))

        def error(exc: Exception) -> None:
            if (
                self.workspace is not workspace
                or env_name != self.environment
            ):
                return
            workspace.package_errors[env_name] = str(exc)
            workspace.packages_by_env[env_name] = []
            self.libraries_tab.set_workspace(
                workspace, env_name, base_mode=self.base_mode
            )
            self.overview_tab.set_workspace(workspace, env_name)
            self.set_status("Failed to read environment packages", danger=True)
            self.console.append_system(str(exc), "error")

        self.run_async(worker, success, error)

    def _confirm_editor_before_switch(self) -> bool:
        if self.editor_tab.is_dirty:
            return self.editor_tab.maybe_save()
        return True

    # ------------------------------------------------------------------
    # Recent menu
    # ------------------------------------------------------------------
    def _rebuild_recent_menu(self) -> None:
        self.recent_menu.delete(0, "end")
        recent = self.state.recent(30)
        if not recent:
            self.recent_menu.add_command(label="(no recent environments)", state="disabled")
            i18n.localize_menu(self.recent_menu)
            return
        for item in recent:
            manifest = str(item.get("manifest") or "")
            env = str(item.get("environment") or "")
            name = str(item.get("name") or Path(manifest).parent.name)
            label = "{}  [{}]  —  {}".format(
                truncate_text(name, 30), env, shorten_path(manifest, 48)
            )
            self.recent_menu.add_command(
                label=label,
                command=lambda m=manifest, e=env: self._open_recent(m, e),
            )
        self.recent_menu.add_separator()
        self.recent_menu.add_command(label="Clear recent", command=self._clear_recent)
        i18n.localize_menu(self.recent_menu)

    def _open_recent(self, manifest: str, env: str) -> None:
        path = Path(manifest)
        if not path.is_file():
            if messagebox.askyesno(
                "Path not found",
                "This recent environment no longer exists:\n{}\n\nRemove it from history?".format(manifest),
                parent=self.root,
            ):
                self.state.remove_recent(path, env)
                self._rebuild_recent_menu()
            return
        if not self._confirm_editor_before_switch():
            return
        self.open_environment(path, preferred_env=env)

    def _clear_recent(self) -> None:
        if messagebox.askyesno(
            "Clear recent", "Clear the recent-environment list?", parent=self.root
        ):
            self.state.clear_recent()
            self._rebuild_recent_menu()
            self.set_status("Recent environments cleared")

    # ------------------------------------------------------------------
    # Commands / jobs
    # ------------------------------------------------------------------
    def _with_manifest(self, args: List[str], use_manifest: bool = True) -> List[str]:
        args = [str(item) for item in args]
        if (
            not use_manifest
            or not self.workspace
            or any(
                str(item) == "--manifest-path"
                or str(item).startswith("--manifest-path=")
                for item in args
            )
            or "-m" in args
            or (args and args[0] in ("init", "help", "--version", "--help"))
        ):
            return args
        if len(args) >= 2 and args[0] == "task":
            position = 2
        elif len(args) >= 3 and args[0] == "workspace":
            position = 3
        else:
            position = 1 if args else 0
        return (
            args[:position]
            + ["--manifest-path", str(self.workspace.manifest)]
            + args[position:]
        )

    def preview_pixi_command(self, args: List[str], use_manifest: bool = True) -> str:
        return self.pixi.command_line(self._with_manifest(args, use_manifest))

    @staticmethod
    def _is_mutating_args(args: List[str]) -> bool:
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
        if first == "task" and len(args) > 1 and args[1].lower() in ("add", "remove"):
            return True
        return False

    def run_pixi_command(
        self,
        args: List[str],
        title: str = "Pixi command",
        refresh: bool = False,
        dangerous: bool = False,
        use_manifest: bool = True,
    ) -> None:
        title = i18n.translate_dynamic(str(title))
        if not self.pixi.available:
            messagebox.showerror(
                "Pixi not found",
                "Set pixi.exe in Settings or add Pixi to PATH first.",
                parent=self.root,
            )
            return
        full_args = self._with_manifest(args, use_manifest)
        command_text = self.pixi.command_line(full_args)
        if dangerous:
            if not messagebox.askyesno(
                "Confirm Operation",
                "This operation may modify the environment:\n\n{}\n\nContinue?".format(command_text),
                parent=self.root,
            ):
                return
        manifest_mutating = bool(
            args
            and (
                args[0] in ("add", "remove", "upgrade")
                or (
                    args[0] == "task"
                    and len(args) > 1
                    and args[1] in ("add", "remove")
                )
            )
        )
        if self.editor_tab.is_dirty and manifest_mutating:
            if not messagebox.askyesno(
                "Unsaved editor changes",
                "pixi.toml has unsaved changes and this command may modify it.\nContinue?",
                parent=self.root,
            ):
                return
        mutating = self._is_mutating_args(args)
        if mutating and (self.job_manager.has_mutating() or self._loading):
            messagebox.showinfo(
                "Environment command already running",
                "Only one pixi command that modifies the environment/manifest may run at a time.\nWait for the current command to finish.",
                parent=self.root,
            )
            return
        try:
            job = self.job_manager.start(
                title,
                [self.pixi.require()] + full_args,
                cwd=self.workspace.root if self.workspace else None,
                refresh=refresh,
                extra={
                    "refresh_manifest": str(self.workspace.manifest)
                    if self.workspace and refresh
                    else "",
                    "mutating": mutating,
                },
            )
        except Exception as exc:
            self._report_error("Could not start command", exc)
            return
        self._job_started(job)
        self.set_status("Running: {}".format(title))

    def open_pixi_terminal(
        self, args: List[str], title: str = "Pixi", use_manifest: bool = True
    ) -> None:
        title = i18n.translate_dynamic(str(title))
        if not self.pixi.available:
            messagebox.showerror(
                "Pixi not found",
                "Set pixi.exe in Settings or add Pixi to PATH first.",
                parent=self.root,
            )
            return
        full_args = self._with_manifest(args, use_manifest)
        try:
            open_terminal(
                [self.pixi.require()] + full_args,
                cwd=self.workspace.root if self.workspace else None,
                title=title,
                terminal=str(self.state.get_setting("terminal", "") or ""),
            )
        except OSError as exc:
            self._report_error("Could not open terminal", exc)
            return
        self.console.append_system(
            "Opened in a new terminal: {}".format(self.pixi.command_line(full_args)), "info"
        )
        self.set_status("Opened in a new terminal: {}".format(title))

    def _job_started(self, job) -> None:
        self.console.start_job(job, job.command_line)
        self.job_status_var.set(
            "{} running".format(self.job_manager.active_count)
        )
        self._update_env_manage_state()

    def _handle_job_event(self, event) -> None:
        if event.kind == "line":
            self.console.append(event.job.job_id, event.text)
            return
        if event.kind != "done":
            return
        self.console.finish_job(
            event.job.job_id,
            event.returncode,
            event.elapsed,
            cancelled=event.job.cancelled,
        )
        active = self.job_manager.active_count
        self.job_status_var.set(
            "{} running".format(active) if active else "Idle"
        )
        self._update_env_manage_state()
        job = event.job
        python_meta = job.extra.get("python_meta")
        if python_meta:
            self.state.update_python_run_exit(
                Path(python_meta["manifest"]),
                python_meta["environment"],
                Path(python_meta["script"]),
                int(event.returncode or 0),
            )
            self.sidebar.refresh()
        if job.cancelled:
            self.set_status("{} stopped".format(job.title))
            return
        workspace_init = str(job.extra.get("workspace_init") or "")
        if workspace_init:
            target = Path(workspace_init)
            manifest = target / "pixi.toml"
            if event.returncode == 0 and manifest.is_file():
                self.state.set_base_mode(manifest, True)
                self.open_environment(
                    manifest, preferred_env="default", add_recent=True
                )
            elif event.returncode == 0:
                self.set_status(
                    "Initialization finished, but {} was not found".format(manifest), danger=True
                )
            else:
                self.set_status(
                    "{} failed with exit code {}".format(job.title, event.returncode),
                    danger=True,
                )
            return
        action = job.extra.get("environment_action") or {}
        refresh_manifest = str(job.extra.get("refresh_manifest") or "")
        same_workspace = bool(
            self.workspace
            and (
                not refresh_manifest
                or os.path.normcase(str(self.workspace.manifest))
                == os.path.normcase(refresh_manifest)
            )
        )
        if (
            action.get("type") == "remove"
            and event.returncode == 0
            and self.workspace
        ):
            removed = str(action.get("name") or "")
            self.state.remove_recent(self.workspace.manifest, removed)
            self.state.remove_python_runs_for_env(
                self.workspace.manifest, removed
            )
            self._rebuild_recent_menu()
        if job.refresh and same_workspace and (
            event.returncode == 0 or action
        ):
            preferred = job.extra.get("refresh_env")
            self.refresh_current(
                preferred_env=str(preferred) if preferred else None
            )
        if event.returncode not in (0, None):
            self.set_status(
                "{} failed with exit code {}".format(job.title, event.returncode), danger=True
            )
        else:
            self.set_status("{} completed".format(job.title))

    def stop_job(self, job_id: int) -> None:
        job = self.job_manager.get(job_id)
        if job is None:
            return
        if messagebox.askyesno(
            "Stop Task",
            "Stop “{}” and its child processes?".format(
                i18n.translate_dynamic(job.title)
            ),
            parent=self.root,
        ):
            self.job_manager.cancel(job_id)
            self.set_status("Stopping: {}".format(job.title))

    def stop_all_jobs(self) -> None:
        jobs = self.job_manager.jobs_snapshot()
        if not jobs:
            return
        if not messagebox.askyesno(
            "Stop All",
            "Stop all current tasks and their child processes?\n\n{} tasks in total.".format(
                len(jobs)
            ),
            parent=self.root,
        ):
            return
        self.job_manager.cancel_all()
        self.set_status("Stopping all tasks…")

    def _manifest_edit_ready(self) -> bool:
        if self.workspace is None:
            return False
        if self.editor_tab.is_dirty:
            messagebox.showinfo(
                "Unsaved changes",
                "Save or discard changes to pixi.toml before managing environments.",
                parent=self.root,
            )
            return False
        return True

    def open_add_environment(self) -> None:
        if not self._manifest_edit_ready():
            return
        if self._loading or self.job_manager.busy:
            messagebox.showinfo(
                "Tasks are running",
                "Stop all running tasks and wait for refresh before adding an environment.",
                parent=self.root,
            )
            return
        if not self.pixi.available:
            messagebox.showerror(
                "Pixi not found",
                "Set pixi.exe in Settings or add Pixi to PATH first.",
                parent=self.root,
            )
            return
        assert self.workspace is not None
        features = self.pixi.feature_names(self.workspace.manifest)
        dialog = AddEnvironmentDialog(
            self.root,
            existing_names=self.workspace.env_names,
            features=features,
            default_install=True,
        )
        self.root.wait_window(dialog)
        if not dialog.result:
            return
        result = dialog.result
        name = str(result["name"])
        commands: List[List[str]] = []
        add_args: List[str] = ["workspace", "environment", "add", name]
        for feature in result["features"]:  # type: ignore[union-attr]
            add_args += ["--feature", str(feature)]
        if result["solve_group"]:
            add_args += ["--solve-group", str(result["solve_group"])]
        if not result["use_default"]:
            add_args.append("--no-default-feature")
        commands.append(add_args)
        if result["install"]:
            commands.append(["install", "--environment", name])
        self._run_pixi_sequence(
            i18n.t("Add environment {}").format(name),
            commands,
            refresh=True,
            stop_on_error=True,
            extra={
                "environment_action": {"type": "add", "name": name},
                "refresh_env": name,
            },
        )

    def open_remove_environment(self) -> None:
        if not self._manifest_edit_ready():
            return
        if self.workspace is None or not self.environment or self.base_mode:
            return
        if self.environment == "default":
            messagebox.showinfo(
                "Cannot delete the current environment",
                "default is implicit and cannot be deleted.",
                parent=self.root,
            )
            return
        if self.job_manager.busy:
            messagebox.showinfo(
                "Tasks are running",
                "Stop all running tasks before deleting an environment.",
                parent=self.root,
            )
            return
        env = self.workspace.get_env(self.environment)
        has_directory = bool(
            env and env.prefix and Path(env.prefix).is_dir()
        )
        dialog = RemoveEnvironmentDialog(
            self.root,
            name=self.environment,
            has_directory=has_directory,
        )
        self.root.wait_window(dialog)
        if not dialog.result:
            return
        name = str(dialog.result["name"])
        commands: List[List[str]] = []
        if dialog.result["cleanup"] and has_directory:
            commands.append(["clean", "--environment", name])
        commands.append(["workspace", "environment", "remove", name])
        self._run_pixi_sequence(
            i18n.t("Delete environment {}").format(name),
            commands,
            refresh=True,
            stop_on_error=False,
            extra={
                "environment_action": {"type": "remove", "name": name},
            },
        )

    def _run_pixi_sequence(
        self,
        title: str,
        commands: List[List[str]],
        refresh: bool = False,
        stop_on_error: bool = True,
        extra: Optional[dict] = None,
    ) -> None:
        if not self.pixi.available:
            messagebox.showerror(
                "Pixi not found",
                "Set pixi.exe in Settings or add Pixi to PATH first.",
                parent=self.root,
            )
            return
        if self.job_manager.has_mutating() or self._loading:
            messagebox.showinfo(
                "Environment command already running",
                "Only one pixi command that modifies the environment/manifest may run at a time.\nWait for the current command to finish.",
                parent=self.root,
            )
            return
        full_commands = [
            [self.pixi.require()] + self._with_manifest(list(command))
            for command in commands
        ]
        job_extra = {
            "mutating": True,
            "refresh_manifest": str(self.workspace.manifest)
            if self.workspace and refresh
            else "",
            **dict(extra or {}),
        }
        try:
            job = self.job_manager.start_sequence(
                title,
                full_commands,
                cwd=self.workspace.root if self.workspace else None,
                refresh=refresh,
                stop_on_error=stop_on_error,
                extra=job_extra,
            )
        except Exception as exc:
            self._report_error("Could not start command", exc)
            return
        self._job_started(job)
        self.set_status("Running: {}".format(title))

    def install_env(self) -> None:
        if not self._require_workspace():
            return
        self.run_pixi_command(
            ["install", "--environment", self.environment],
            title="Install / Update {}".format(self.environment),
            refresh=True,
        )

    def lock_env(self) -> None:
        if not self._require_workspace():
            return
        self.run_pixi_command(
            ["lock"],
            title="Relock Environment",
            refresh=True,
        )

    def clean_env(self) -> None:
        if not self._require_workspace():
            return
        if not messagebox.askyesno(
            "Clean Environment",
            "This removes the .pixi environment directory for {}; pixi.toml and pixi.lock are kept.\n\nContinue?".format(
                self.environment
            ),
            parent=self.root,
        ):
            return
        self.run_pixi_command(
            ["clean", "--environment", self.environment],
            title="Clean environment {}".format(self.environment),
            refresh=True,
            dangerous=False,
        )

    # ------------------------------------------------------------------
    # Libraries / updates
    # ------------------------------------------------------------------
    def query_latest_async(
        self,
        package: Package,
        manifest: Path,
        platform: str,
        callback: Callable[[object], None],
    ) -> None:
        def worker():
            return self.pixi.latest_for(package, platform, manifest)

        def error(exc: Exception) -> None:
            callback(exc)

        self.run_async(worker, callback, error)

    def check_compatible_updates(self) -> None:
        if not self.workspace:
            messagebox.showinfo("Check for Updates", "Open an environment first.", parent=self.root)
            return
        workspace = self.workspace
        env = self.environment
        if not workspace.lock_exists:
            messagebox.showinfo(
                "Check for Updates",
                "This workspace has no pixi.lock yet. Install/lock the environment before checking compatible updates.",
                parent=self.root,
            )
            return
        self.libraries_tab.set_loading("Checking for compatible updates…")
        self.libraries_tab.compat_button.configure(state="disabled")
        self.set_status("Checking compatible updates…")

        def worker():
            return self.pixi.compatible_updates(workspace.manifest, env)

        def success(updates: Dict[str, str]) -> None:
            self.libraries_tab.compat_button.configure(state="normal")
            if self.workspace is not workspace or self.environment != env:
                return
            self.libraries_tab.apply_compatible_updates(updates)
            if updates:
                self.set_status("{} compatible updates found".format(len(updates)))
            else:
                self.set_status("No compatible updates")
            self.console.append_system(
                "Compatible update check finished: {} update(s)".format(len(updates)), "info"
            )

        def error(exc: Exception) -> None:
            self.libraries_tab.compat_button.configure(state="normal")
            self.libraries_tab.set_loading("Failed to check for updates")
            self.set_status("Compatible update check failed", danger=True)
            self.console.append_system(str(exc), "error")

        self.run_async(worker, success, error)

    def update_package(self, package: Package, upgrade: bool = False) -> None:
        if not self.workspace:
            return
        verb = i18n.t("Upgrade to Latest" if upgrade else "Update to compatible")
        args = [
            "upgrade" if upgrade else "update",
            "--environment",
            self.environment,
            package.name,
        ]
        self.run_pixi_command(
            args,
            title="{}: {}".format(verb, package.name),
            refresh=True,
            dangerous=True,
        )

    # ------------------------------------------------------------------
    # Task / Python run
    # ------------------------------------------------------------------
    def _require_workspace(self) -> bool:
        if not self.workspace or not self.environment:
            messagebox.showinfo("Environment required", "Open a Pixi environment first.", parent=self.root)
            return False
        return True

    def run_task(
        self,
        task: TaskInfo,
        extra_args: Optional[List[str]] = None,
        terminal: bool = False,
    ) -> None:
        if not self._require_workspace() or not self.workspace:
            return
        args = ["run", "--environment", self.environment, task.name]
        if extra_args:
            args += extra_args
        full_args = self._with_manifest(args)
        if terminal:
            self.open_pixi_terminal(
                args, title="Pixi task: {}".format(task.name), use_manifest=True
            )
            return
        title = i18n.translate_dynamic("Task: {}".format(task.name))
        try:
            job = self.job_manager.start(
                title,
                [self.pixi.require()] + full_args,
                cwd=self.workspace.root,
            )
        except Exception as exc:
            self._report_error("Could not start task", exc)
            return
        self._job_started(job)
        self.set_status("Running task: {}".format(task.name))

    def run_task_with_args(self, task: TaskInfo) -> None:
        if not self._require_workspace():
            return
        dialog = TaskArgsDialog(self.root, task.name)
        self.root.wait_window(dialog)
        if dialog.result is None:
            return
        args = split_user_args(dialog.result)
        self.run_task(task, extra_args=args)

    def python_command_args(self, script: str, args_text: str) -> List[str]:
        if not self.workspace:
            return ["run", "--environment", self.environment, "python", str(script)] + split_user_args(args_text)
        args = [
            "run",
            "--environment",
            self.environment,
            "python",
            str(script),
        ] + split_user_args(args_text)
        return self._with_manifest(args)

    def run_python_program(
        self,
        script: Path,
        args_text: str,
        cwd: Path,
        terminal: bool = False,
    ) -> None:
        if not self._require_workspace() or not self.workspace:
            return
        if not self.pixi.available:
            messagebox.showerror(
                "Pixi not found",
                "Set pixi.exe in Settings or add Pixi to PATH first.",
                parent=self.root,
            )
            return
        env = self.workspace.get_env(self.environment)
        if env is not None:
            if not env.installed:
                if not messagebox.askyesno(
                    "Environment not installed",
                    "Environment {} is not installed. pixi run may install it first. Continue?".format(
                        self.environment
                    ),
                    parent=self.root,
                ):
                    return
            elif env.python_path is None:
                if not messagebox.askyesno(
                    "Python may be missing",
                    "python.exe was not found in environment {}. Try anyway?".format(
                        self.environment
                    ),
                    parent=self.root,
                ):
                    return
        args = self.python_command_args(str(script), args_text)
        self.state.add_python_run(
            self.workspace.manifest,
            self.environment,
            script,
            args=args_text,
            cwd=cwd,
        )
        self.sidebar.refresh()
        if terminal:
            self.open_pixi_terminal(
                args,
                title="Python: {}".format(script.name),
                use_manifest=False,
            )
            self.python_tab.set_status("Running {} in a new terminal".format(script.name))
            return
        title = i18n.translate_dynamic("Python: {}".format(script.name))
        try:
            job = self.job_manager.start(
                title,
                [self.pixi.require()] + args,
                cwd=cwd,
                extra={
                    "python_meta": {
                        "manifest": str(self.workspace.manifest),
                        "environment": self.environment,
                        "script": str(script),
                    }
                },
            )
        except Exception as exc:
            self._report_error("Could not run Python", exc)
            return
        self._job_started(job)
        self.python_tab.set_status("Running {}".format(script.name))
        self.set_status("Running: {}".format(script.name))

    def run_python_run(self, run: dict, terminal: bool = False) -> None:
        script = Path(str(run.get("script") or ""))
        if not script.is_file():
            if messagebox.askyesno(
                "Script not found",
                "Script not found:\n{}\n\nRemove it from history?".format(script),
                parent=self.root,
            ):
                self.remove_python_run(run)
            return
        cwd = Path(str(run.get("cwd") or "")) if run.get("cwd") else script.parent
        if not cwd.is_dir():
            cwd = script.parent
        self.run_python_program(
            script=script,
            args_text=str(run.get("args") or ""),
            cwd=cwd,
            terminal=terminal,
        )

    def load_python_run(self, run: dict) -> None:
        self.notebook.select(self.python_tab)
        self.python_tab.load_run(run)
        self.python_tab.focus_script()

    def remove_python_run(self, run: dict) -> None:
        script = str(run.get("script") or "")
        if not messagebox.askyesno(
            "Remove History",
            "Remove this program from history?\n{}".format(script),
            parent=self.root,
        ):
            return
        if self.workspace:
            self.state.remove_python_run(
                self.workspace.manifest, self.environment, Path(script)
            )
        self.sidebar.refresh()
        self.set_status("Python history entry removed")

    # ------------------------------------------------------------------
    # Misc UI actions
    # ------------------------------------------------------------------
    def show_task(self, task: TaskInfo) -> None:
        self.notebook.select(self.tasks_tab)
        self.tasks_tab.search_var.set("")
        self.tasks_tab.focus_task(task)

    def _copy_workspace_path(self) -> None:
        if self.workspace:
            copy_text(self.root, str(self.workspace.manifest))

    def _copy_workspace_folder(self) -> None:
        if self.workspace:
            copy_text(self.root, str(self.workspace.root))

    def open_workspace_folder(self) -> None:
        if self.workspace:
            open_in_explorer(str(self.workspace.root))

    def open_path(self, path: str) -> None:
        if path:
            open_in_explorer(path)

    def on_manifest_saved(self, path: Path) -> None:
        if self.workspace and path.resolve() == self.workspace.manifest.resolve():
            self.set_status("Manifest saved; refreshing environment…")
            self.refresh_current()

    def help_async(self, command: List[str], callback: Callable[[str], None]) -> None:
        def worker():
            return self.pixi.help_text(command)

        self.run_async(worker, callback, lambda exc: callback(str(exc)))

    # ------------------------------------------------------------------
    # Status / errors
    # ------------------------------------------------------------------
    def set_status(self, text: str, danger: bool = False) -> None:
        self.status_var.set(i18n.translate_dynamic(text))
        try:
            self.status_label.configure(
                style="StatusDanger.TLabel" if danger else "Status.TLabel"
            )
        except tk.TclError:
            pass

    def _report_error(self, title: str, exc: Exception) -> None:
        if isinstance(exc, PixiError):
            details = exc.details
            message = str(exc).splitlines()[0] if str(exc) else "Pixi command failed"
        else:
            if exc.__traceback__ is not None:
                details = "".join(
                    traceback.format_exception(
                        type(exc), exc, exc.__traceback__
                    )
                )
            else:
                details = str(exc)
            message = str(exc) or exc.__class__.__name__
        self.console.append_system("[error] " + message, "error")
        if details:
            self.console.append_system(details, "error")
            show_error(
                self.root,
                title,
                message,
                details=details,
                colors=self.theme.colors,
            )
        else:
            show_error(self.root, title, message, colors=self.theme.colors)
        self.set_status(message, danger=True)

    def _restore_geometry(self) -> None:
        geometry = str(self.state.get_setting("window_geometry", "") or "")
        if geometry:
            try:
                self.root.geometry(geometry)
                return
            except tk.TclError:
                pass
        self.root.geometry("1280x820")

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------
    def on_close(self) -> None:
        if not self._confirm_editor_before_switch():
            return
        if self.job_manager.busy:
            if not messagebox.askyesno(
                "Tasks are running",
                "Closing will terminate {} running task(s). Continue?".format(
                    self.job_manager.active_count
                ),
                parent=self.root,
            ):
                return
            self.job_manager.cancel_all()
        self._closing = True
        try:
            self._save_layout_state(save=False)
            self.state.update_settings(
                {
                    "window_geometry": self.root.geometry(),
                    "console_max_lines": self.console.max_lines,
                    "layout_sidebar_width": int(self._sidebar_width),
                    "layout_console_height": int(self._console_height),
                    "layout_sidebar_collapsed": self._sidebar_collapsed,
                    "layout_console_collapsed": self._console_collapsed,
                }
            )
        except Exception:
            pass
        self.root.destroy()


def main() -> None:
    enable_dpi_awareness()
    root = tk.Tk()
    initial: Optional[Path] = None
    if len(sys.argv) > 1:
        initial = Path(sys.argv[1])
    MainWindow(root, initial_path=initial)
    root.mainloop()
