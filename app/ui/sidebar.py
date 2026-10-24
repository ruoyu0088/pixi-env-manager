"""Left sidebar: quick tasks and Python programs run in the current env."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Dict, List, Optional

from ..models import TaskInfo, WorkspaceData
from ..util import shorten_path, truncate_text
from .widgets import ScrollableFrame, Tooltip, clear_children


class QuickSidebar(ttk.Frame):
    def __init__(self, master, app, colors: Dict[str, str]):
        super().__init__(master, style="Sidebar.TFrame")
        self.app = app
        self.colors = colors
        self.workspace: Optional[WorkspaceData] = None
        self.env_name = ""
        self._task_rows: List[tk.Widget] = []

        self.paned = ttk.Panedwindow(self, orient="vertical")
        self.paned.pack(fill="both", expand=True)

        self.task_section = self._make_section("快速任务")
        self.python_section = self._make_section("Python 程序")
        self.paned.add(self.task_section["frame"], weight=1)
        self.paned.add(self.python_section["frame"], weight=1)

        self.apply_colors(colors)
        self.refresh()
        self._sash_done = False
        self.bind("<Configure>", self._set_initial_sash, add="+")
        self.after(500, self._set_initial_sash)

    def _set_initial_sash(self, _event=None) -> None:
        if self._sash_done:
            return
        try:
            height = self.paned.winfo_height()
            if height > 300:
                self.paned.sashpos(0, int(height * 0.56))
                self._sash_done = True
        except tk.TclError:
            pass

    def _make_section(self, title: str):
        outer = ttk.Frame(self.paned, style="Sidebar.TFrame", padding=(9, 8, 9, 8))
        header = ttk.Frame(outer, style="Sidebar.TFrame")
        header.pack(fill="x")
        title_label = ttk.Label(header, text=title, style="Section.TLabel")
        title_label.pack(side="left")
        count_label = ttk.Label(header, text="0", style="SmallCard.TLabel")
        count_label.pack(side="left", padx=(7, 0))
        ttk.Label(
            header,
            text="当前环境",
            style="SmallCard.TLabel",
        ).pack(side="right")
        scroll = ScrollableFrame(outer, style="Sidebar.TFrame")
        scroll.pack(fill="both", expand=True, pady=(7, 0))
        return {
            "frame": outer,
            "header": header,
            "count": count_label,
            "scroll": scroll,
        }

    def apply_colors(self, colors: Dict[str, str]) -> None:
        self.colors = colors
        for section in (self.task_section, self.python_section):
            section["scroll"].set_background(colors["panel"])
        self.refresh()

    def set_workspace(self, workspace: Optional[WorkspaceData], env_name: str) -> None:
        self.workspace = workspace
        self.env_name = env_name
        self.refresh()

    def refresh(self) -> None:
        self._refresh_tasks()
        self._refresh_python_runs()

    def _refresh_tasks(self) -> None:
        inner = self.task_section["scroll"].inner
        clear_children(inner)
        tasks = (
            self.workspace.tasks_for_env(self.env_name)
            if self.workspace and self.env_name
            else []
        )
        self.task_section["count"].configure(text=str(len(tasks)))
        if not self.workspace:
            self._empty(inner, "打开一个环境后显示可用 task")
            return
        if not tasks:
            self._empty(inner, "当前环境没有 task")
            return
        for task in tasks:
            self._make_task_row(inner, task)

    def _make_task_row(self, parent, task: TaskInfo) -> None:
        row = ttk.Frame(parent, style="Row.TFrame", padding=(6, 4))
        row.pack(fill="x", pady=(0, 3))
        play = ttk.Button(
            row,
            text="▶",
            width=2,
            style="Play.TButton",
            command=lambda t=task: self.app.run_task(t),
        )
        play.pack(side="left", padx=(0, 6), anchor="n")
        text_frame = ttk.Frame(row, style="Row.TFrame")
        text_frame.pack(side="left", fill="x", expand=True)
        name = ttk.Label(
            text_frame,
            text=truncate_text(task.name, 34),
            style="RowTitle.TLabel",
            anchor="w",
        )
        name.pack(fill="x")
        command = ttk.Label(
            text_frame,
            text=truncate_text(task.command_summary, 38) or "（无命令）",
            style="RowMuted.TLabel",
            anchor="w",
        )
        command.pack(fill="x")
        if task.feature and task.feature not in ("environment", "default"):
            feature = ttk.Label(
                text_frame,
                text="feature: " + task.feature,
                style="RowAccent.TLabel",
                anchor="w",
            )
            feature.pack(fill="x")
        tooltip = "\n".join(
            item
            for item in (
                task.name,
                task.cmd,
                "目录: " + task.cwd if task.cwd else "",
                "所属: " + task.feature if task.feature else "",
                "依赖: " + ", ".join(task.depends_on) if task.depends_on else "",
            )
            if item
        )
        Tooltip(name, tooltip)
        Tooltip(command, tooltip)

        def show_details(_event=None):
            self.app.show_task(task)

        for widget in (row, text_frame, name, command):
            widget.bind("<Button-1>", show_details, add="+")
        for widget in (row, name, command):
            widget.bind(
                "<Button-3>",
                lambda event, t=task: self._task_menu(event, t),
                add="+",
            )
        play.bind(
            "<Button-3>",
            lambda event, t=task: self._task_menu(event, t),
            add="+",
        )
        self._task_rows.append(row)

    def _task_menu(self, event, task: TaskInfo) -> None:
        menu = tk.Menu(self, tearoff=0)
        self.app.theme.style_menu(menu)
        menu.add_command(label="启动", command=lambda: self.app.run_task(task))
        menu.add_command(
            label="带参数启动…",
            command=lambda: self.app.run_task_with_args(task),
        )
        menu.add_command(
            label="在终端中运行",
            command=lambda: self.app.run_task(task, terminal=True),
        )
        menu.add_separator()
        menu.add_command(label="查看详情", command=lambda: self.app.show_task(task))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _refresh_python_runs(self) -> None:
        inner = self.python_section["scroll"].inner
        clear_children(inner)
        runs: List[dict] = []
        if self.workspace and self.env_name:
            runs = self.workspace.python_programs(self.env_name, self.app.state)
        self.python_section["count"].configure(text=str(len(runs)))
        if not self.workspace:
            self._empty(inner, "打开一个环境后显示运行历史")
            return
        if not runs:
            self._empty(inner, "还没有用此环境运行过 Python 程序")
            return
        for run in runs:
            self._make_python_row(inner, run)

    def _make_python_row(self, parent, run: dict) -> None:
        script = str(run.get("script") or "")
        args = str(run.get("args") or "")
        exists = bool(script) and Path(script).is_file()
        row = ttk.Frame(parent, style="Row.TFrame", padding=(6, 4))
        row.pack(fill="x", pady=(0, 3))
        play = ttk.Button(
            row,
            text="▶",
            width=2,
            style="Play.TButton",
            command=lambda r=run: self.app.run_python_run(r),
        )
        play.pack(side="left", padx=(0, 6), anchor="n")
        text_frame = ttk.Frame(row, style="Row.TFrame")
        text_frame.pack(side="left", fill="x", expand=True)
        name = ttk.Label(
            text_frame,
            text=truncate_text(Path(script).name, 34) if script else "（无脚本）",
            style="RowTitle.TLabel",
            anchor="w",
        )
        name.pack(fill="x")
        args_label = ttk.Label(
            text_frame,
            text=truncate_text(args, 42) if args else "（无参数）",
            style="RowMuted.TLabel" if exists else "RowDanger.TLabel",
            anchor="w",
        )
        args_label.pack(fill="x")
        path_label = ttk.Label(
            text_frame,
            text=shorten_path(script, 44) if script else "",
            style="RowMuted.TLabel",
            anchor="w",
        )
        path_label.pack(fill="x")
        tooltip = "\n".join(
            item
            for item in (
                script,
                "参数: " + args if args else "参数: （无）",
                "工作目录: " + str(run.get("cwd") or ""),
                "上次运行: " + str(run.get("last_run") or ""),
                "" if exists else "⚠ 脚本文件不存在",
            )
            if item
        )
        for widget in (name, args_label, path_label):
            Tooltip(widget, tooltip)

        def load(_event=None):
            self.app.load_python_run(run)

        for widget in (row, text_frame, name, args_label, path_label):
            widget.bind("<Button-1>", load, add="+")
        for widget in (row, name, args_label, path_label):
            widget.bind(
                "<Button-3>",
                lambda event, r=run: self._python_menu(event, r),
                add="+",
            )
        play.bind(
            "<Button-3>",
            lambda event, r=run: self._python_menu(event, r),
            add="+",
        )

    def _python_menu(self, event, run: dict) -> None:
        menu = tk.Menu(self, tearoff=0)
        self.app.theme.style_menu(menu)
        menu.add_command(
            label="运行（使用保存的参数）",
            command=lambda: self.app.run_python_run(run),
        )
        menu.add_command(
            label="编辑参数…",
            command=lambda: self.app.load_python_run(run),
        )
        menu.add_command(
            label="在终端中运行",
            command=lambda: self.app.run_python_run(run, terminal=True),
        )
        menu.add_separator()
        menu.add_command(
            label="从历史中移除",
            command=lambda: self.app.remove_python_run(run),
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _empty(self, parent, text: str) -> None:
        label = ttk.Label(
            parent,
            text=text,
            style="RowMuted.TLabel",
            wraplength=220,
            justify="left",
        )
        label.pack(fill="x", padx=4, pady=8)
