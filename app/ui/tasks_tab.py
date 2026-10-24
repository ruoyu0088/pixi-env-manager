"""Task browser and launcher."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Dict, List, Optional

from .. import i18n
from ..models import TaskInfo, WorkspaceData
from ..util import truncate_text


class TasksTab(ttk.Frame):
    def __init__(self, master, app, colors: Dict[str, str]):
        super().__init__(master, padding=(14, 12))
        self.app = app
        self.colors = colors
        self.workspace: Optional[WorkspaceData] = None
        self.env_name = ""
        self.tasks: List[TaskInfo] = []
        self.visible: Dict[str, TaskInfo] = {}
        self._counter = 0

        header = ttk.Frame(self)
        header.pack(fill="x")
        ttk.Label(header, text="任务", style="Title.TLabel").pack(side="left")
        self.headline_var = tk.StringVar(value="未打开环境")
        ttk.Label(
            header, textvariable=self.headline_var, style="Muted.TLabel"
        ).pack(side="left", padx=(10, 0), pady=(6, 0))
        self.base_hint_var = tk.StringVar(value="")
        self.base_hint = ttk.Label(
            self, textvariable=self.base_hint_var, style="Muted.TLabel"
        )

        toolbar = ttk.Frame(self)
        self.toolbar = toolbar
        toolbar.pack(fill="x", pady=(10, 6))
        ttk.Label(toolbar, text="搜索", style="Muted.TLabel").pack(
            side="left", padx=(0, 4)
        )
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=24)
        self.search_entry.pack(side="left")
        self.search_var.trace_add("write", lambda *_: self.refresh_view())
        self.refresh_button = ttk.Button(
            toolbar, text="刷新", command=self.app.refresh_current
        )
        self.refresh_button.pack(side="right")
        self.terminal_button = ttk.Button(
            toolbar, text="在终端运行", command=lambda: self._launch(terminal=True)
        )
        self.terminal_button.pack(side="right", padx=(0, 6))
        self.args_button = ttk.Button(
            toolbar, text="带参数启动…", command=self._launch_with_args
        )
        self.args_button.pack(side="right", padx=(0, 6))
        self.run_button = ttk.Button(
            toolbar,
            text="启动选中任务",
            style="Accent.TButton",
            command=lambda: self._launch(terminal=False),
        )
        self.run_button.pack(side="right", padx=(0, 6))

        self.status_var = tk.StringVar(value="")
        ttk.Label(
            self, textvariable=self.status_var, style="Muted.TLabel"
        ).pack(fill="x", pady=(0, 4))

        table_frame = ttk.Frame(self)
        table_frame.pack(fill="both", expand=True)
        columns = ("name", "command", "cwd", "feature", "description")
        self.tree = ttk.Treeview(
            table_frame, columns=columns, show="headings", selectmode="browse"
        )
        headings = {
            "name": "任务",
            "command": "命令",
            "cwd": "工作目录",
            "feature": "Feature",
            "description": "描述",
        }
        widths = {
            "name": 200,
            "command": 390,
            "cwd": 300,
            "feature": 120,
            "description": 260,
        }
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(
                column,
                width=widths[column],
                anchor="w",
                stretch=column in ("command", "cwd", "description"),
            )
        y_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        x_scroll = ttk.Scrollbar(
            table_frame, orient="horizontal", command=self.tree.xview
        )
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda _event: self._launch(terminal=False))
        self.tree.bind("<Button-3>", self._context_menu)

        detail = ttk.LabelFrame(self, text="任务详情", padding=(9, 7))
        detail.pack(side="bottom", fill="x", pady=(9, 0), before=table_frame)
        self.detail_vars = {
            key: tk.StringVar(value="—")
            for key in ("name", "cmd", "cwd", "feature", "depends", "args", "description")
        }
        labels = [
            ("name", "名称", 0, 0),
            ("feature", "Feature", 0, 2),
            ("cmd", "命令", 1, 0),
            ("cwd", "工作目录", 2, 0),
            ("depends", "依赖", 3, 0),
            ("args", "参数定义", 4, 0),
            ("description", "描述", 5, 0),
        ]
        for key, label, row, column in labels:
            ttk.Label(detail, text=label, style="MutedCard.TLabel", width=8).grid(
                row=row, column=column, sticky="nw", pady=1
            )
            ttk.Label(
                detail,
                textvariable=self.detail_vars[key],
                style="Card.TLabel",
                wraplength=820,
                justify="left",
            ).grid(
                row=row,
                column=column + 1,
                columnspan=3,
                sticky="w",
                pady=1,
            )
        detail.columnconfigure(1, weight=1)

        self.apply_theme(colors)
        self.refresh_view()

    def apply_theme(self, colors: Dict[str, str]) -> None:
        self.colors = colors
        self.tree.tag_configure("feature", foreground=colors["accent"])
        self.tree.tag_configure("args", foreground=colors["warning"])

    def set_workspace(
        self,
        workspace: Optional[WorkspaceData],
        env_name: str,
        base_mode: bool = False,
    ) -> None:
        self.workspace = workspace
        self.env_name = env_name
        if base_mode:
            self.base_hint_var.set(
                "基础依赖视图：任务仍使用 {} 环境运行".format(env_name)
            )
            self.base_hint.pack(fill="x", pady=(6, 0), before=self.toolbar)
        else:
            self.base_hint_var.set("")
            self.base_hint.pack_forget()
        self.tasks = workspace.tasks_for_env(env_name) if workspace else []
        if workspace:
            self.headline_var.set(
                "{} / {}".format(workspace.name or workspace.root.name, env_name)
            )
        else:
            self.headline_var.set("未打开环境")
        self.refresh_view()

    def refresh_view(self) -> None:
        selected_name = self._selected_task_name()
        self.tree.delete(*self.tree.get_children())
        self.visible.clear()
        if not self.workspace:
            self.status_var.set("未打开环境")
            self._clear_details()
            return
        query = self.search_var.get().strip().lower()
        filtered = []
        for task in self.tasks:
            haystack = " ".join(
                (task.name, task.cmd, task.cwd, task.feature, task.description)
            ).lower()
            if query and query not in haystack:
                continue
            filtered.append(task)
        self.visible = {}
        for task in filtered:
            self._counter += 1
            iid = "task{}".format(self._counter)
            self.visible[iid] = task
            tags = []
            if task.feature and task.feature not in ("default", "environment"):
                tags.append("feature")
            if task.args:
                tags.append("args")
            self.tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    task.name,
                    truncate_text(task.cmd, 80),
                    truncate_text(task.cwd, 65),
                    task.feature,
                    truncate_text(task.description, 50),
                ),
                tags=tuple(tags),
            )
            if selected_name and task.name == selected_name:
                self.tree.selection_set(iid)
                self.tree.see(iid)
        if filtered:
            self.status_var.set("{} 个 task（当前环境 {}）".format(len(filtered), self.env_name))
        else:
            self.status_var.set("当前环境没有可显示的 task")
        if not self.tree.selection() and self.tree.get_children():
            first = self.tree.get_children()[0]
            self.tree.selection_set(first)
            self.tree.focus(first)
        self._update_details()

    def _on_select(self, _event=None) -> None:
        self._update_details()

    def _selected_task_name(self) -> str:
        selection = self.tree.selection()
        if selection and selection[0] in self.visible:
            return self.visible[selection[0]].name
        return ""

    def _selected_task(self) -> Optional[TaskInfo]:
        selection = self.tree.selection()
        if selection:
            return self.visible.get(selection[0])
        return None

    def _update_details(self) -> None:
        task = self._selected_task()
        if task is None:
            self._clear_details()
            return
        self.detail_vars["name"].set(task.name)
        self.detail_vars["feature"].set(task.feature or "—")
        self.detail_vars["cmd"].set(task.cmd or "—")
        self.detail_vars["cwd"].set(task.cwd or "—")
        self.detail_vars["depends"].set(", ".join(task.depends_on) or "—")
        self.detail_vars["args"].set(
            "有（启动时可填写参数）" if task.args else "无"
        )
        self.detail_vars["description"].set(task.description or "—")

    def _clear_details(self) -> None:
        for var in self.detail_vars.values():
            var.set("—")

    def _launch(self, terminal: bool) -> None:
        task = self._selected_task()
        if task is None:
            messagebox.showinfo("运行任务", "请先选择一个 task。", parent=self)
            return
        self.app.run_task(task, terminal=terminal)

    def _launch_with_args(self) -> None:
        task = self._selected_task()
        if task is None:
            messagebox.showinfo("运行任务", "请先选择一个 task。", parent=self)
            return
        self.app.run_task_with_args(task)

    def _context_menu(self, event) -> None:
        row = self.tree.identify_row(event.y)
        if not row:
            return
        self.tree.selection_set(row)
        self._update_details()
        menu = tk.Menu(self, tearoff=0)
        self.app.theme.style_menu(menu)
        menu.add_command(label="启动", command=lambda: self._launch(False))
        menu.add_command(label="带参数启动…", command=self._launch_with_args)
        menu.add_command(label="在终端中运行", command=lambda: self._launch(True))
        menu.add_separator()
        menu.add_command(label="复制命令", command=self._copy_command)
        i18n.localize_menu(menu)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _copy_command(self) -> None:
        task = self._selected_task()
        if task:
            self.clipboard_clear()
            self.clipboard_append(task.cmd)

    def focus_task(self, task: TaskInfo) -> None:
        """Select a task by identity or name (used by the sidebar)."""
        for iid, candidate in self.visible.items():
            if candidate is task or candidate.name == task.name:
                self.tree.selection_set(iid)
                self.tree.focus(iid)
                self.tree.see(iid)
                self._update_details()
                return
