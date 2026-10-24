"""Installed package list, filtering, and update discovery."""

from __future__ import annotations

import tkinter as tk
from functools import cmp_to_key
from tkinter import messagebox, ttk
from typing import Dict, List, Optional, Tuple

from ..models import Package, WorkspaceData
from ..util import format_size, truncate_text
from ..versions import compare_versions
from .widgets import Tooltip


class LibrariesTab(ttk.Frame):
    def __init__(self, master, app, colors: Dict[str, str]):
        super().__init__(master, padding=(14, 12))
        self.app = app
        self.colors = colors
        self.workspace: Optional[WorkspaceData] = None
        self.env_name = ""
        self.packages: List[Package] = []
        self.visible: Dict[str, Package] = {}
        self._current_packages: Dict[str, Package] = {}
        self._workspace_token = 0
        self.sort_column = "name"
        self.sort_reverse = False
        self._detail_key: Optional[str] = None

        header = ttk.Frame(self)
        header.pack(fill="x")
        ttk.Label(header, text="库", style="Title.TLabel").pack(side="left")
        self.headline_var = tk.StringVar(value="未打开环境")
        ttk.Label(
            header, textvariable=self.headline_var, style="Muted.TLabel"
        ).pack(side="left", padx=(10, 0), pady=(6, 0))

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(10, 6))
        self.filter_var = tk.StringVar(value="user")
        self.user_radio = ttk.Radiobutton(
            toolbar,
            text="仅用户安装",
            variable=self.filter_var,
            value="user",
            command=self.refresh_view,
        )
        self.user_radio.pack(side="left")
        self.all_radio = ttk.Radiobutton(
            toolbar,
            text="全部库",
            variable=self.filter_var,
            value="all",
            command=self.refresh_view,
        )
        self.all_radio.pack(side="left", padx=(8, 0))

        ttk.Label(toolbar, text="搜索", style="Muted.TLabel").pack(
            side="left", padx=(16, 4)
        )
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=22)
        self.search_entry.pack(side="left")
        self.search_var.trace_add("write", lambda *_: self.refresh_view())

        ttk.Label(toolbar, text="类型", style="Muted.TLabel").pack(
            side="left", padx=(12, 4)
        )
        self.kind_var = tk.StringVar(value="全部")
        self.kind_combo = ttk.Combobox(
            toolbar,
            textvariable=self.kind_var,
            values=("全部", "Conda", "PyPI"),
            state="readonly",
            width=8,
        )
        self.kind_combo.pack(side="left")
        self.kind_combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh_view())

        self.refresh_button = ttk.Button(
            toolbar, text="刷新", command=self.app.refresh_current
        )
        self.refresh_button.pack(side="right")
        self.install_button = ttk.Button(
            toolbar, text="安装环境", command=self.app.install_env
        )
        self.install_button.pack(side="right", padx=(0, 6))
        self.compat_button = ttk.Button(
            toolbar,
            text="检查兼容更新",
            command=self.app.check_compatible_updates,
        )
        self.compat_button.pack(side="right", padx=(0, 6))
        self.latest_button = ttk.Button(
            toolbar, text="查询选中最新", command=self.query_selected_latest
        )
        self.latest_button.pack(side="right", padx=(0, 6))

        self.status_var = tk.StringVar(value="")
        self.status_label = ttk.Label(
            self, textvariable=self.status_var, style="Muted.TLabel"
        )
        self.status_label.pack(fill="x", pady=(0, 4))

        self.body_pane = ttk.Panedwindow(self, orient="vertical")
        self.body_pane.pack(fill="both", expand=True)
        self._body_sash_done = False
        self.body_pane.bind("<Configure>", self._on_body_configure, add="+")
        table_frame = ttk.Frame(self.body_pane)
        self.table_frame = table_frame
        self.body_pane.add(table_frame, weight=3)
        columns = ("name", "version", "latest", "status", "kind", "spec", "source", "size")
        self.tree = ttk.Treeview(
            table_frame, columns=columns, show="headings", selectmode="extended"
        )
        headings = {
            "name": "名称",
            "version": "已安装",
            "latest": "最新版本",
            "status": "状态",
            "kind": "类型",
            "spec": "请求约束",
            "source": "来源",
            "size": "大小",
        }
        widths = {
            "name": 230,
            "version": 110,
            "latest": 110,
            "status": 100,
            "kind": 70,
            "spec": 190,
            "source": 220,
            "size": 80,
        }
        for column in columns:
            self.tree.heading(
                column,
                text=headings[column],
                command=lambda c=column: self.sort_by(c),
            )
            anchor = "e" if column == "size" else "w"
            self.tree.column(
                column,
                width=widths[column],
                anchor=anchor,
                stretch=column in ("name", "spec", "source"),
            )
        y_scroll = ttk.Scrollbar(
            table_frame, orient="vertical", command=self.tree.yview
        )
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
        self.tree.bind("<Button-3>", self._context_menu)
        self.tree.bind("<Double-1>", lambda _event: self.query_selected_latest())

        self.details = ttk.LabelFrame(
            self.body_pane, text="包详情", padding=(7, 5)
        )
        self.body_pane.add(self.details, weight=1)
        self._detail_package: Optional[Package] = None
        self.after(350, self._set_body_sash)
        self.detail_vars: Dict[str, tk.StringVar] = {
            key: tk.StringVar(value="—")
            for key in (
                "name",
                "version",
                "build",
                "kind",
                "latest",
                "spec",
                "source",
                "license",
                "url",
                "file",
                "extra",
            )
        }
        detail_grid = ttk.Frame(self.details)
        detail_grid.pack(fill="x")
        positions = [
            ("name", "名称", 0, 0, 1),
            ("version", "版本", 0, 2, 1),
            ("build", "构建", 0, 4, 1),
            ("kind", "类型", 0, 6, 1),
            ("latest", "最新", 1, 0, 1),
            ("spec", "请求约束", 1, 2, 3),
            ("license", "许可证", 1, 6, 1),
            ("source", "来源", 2, 0, 3),
            ("file", "文件", 2, 4, 3),
        ]
        for key, label, row, column, span in positions:
            ttk.Label(
                detail_grid, text=label, style="MutedCard.TLabel", width=7
            ).grid(row=row, column=column, sticky="nw", pady=1)
            value = ttk.Label(
                detail_grid,
                textvariable=self.detail_vars[key],
                style="Card.TLabel",
                wraplength=250 if span <= 1 else 360,
                justify="left",
            )
            value.grid(
                row=row,
                column=column + 1,
                columnspan=span,
                sticky="w",
                padx=(0, 14),
                pady=1,
            )
        detail_grid.columnconfigure(1, weight=1)
        detail_grid.columnconfigure(3, weight=1)
        detail_grid.columnconfigure(5, weight=1)

        detail_actions = ttk.Frame(self.details)
        detail_actions.pack(fill="x", pady=(6, 0))
        self.detail_info_button = ttk.Button(
            detail_actions,
            text="完整详情…",
            command=self._show_full_details,
        )
        self.detail_info_button.pack(side="right")
        self.detail_latest_button = ttk.Button(
            detail_actions,
            text="查询此包最新版",
            command=self.query_selected_latest,
        )
        self.detail_latest_button.pack(side="left")
        self.update_button = ttk.Button(
            detail_actions,
            text="更新到兼容版本",
            command=lambda: self._update_selected(False),
        )
        self.update_button.pack(side="left", padx=(6, 0))
        self.upgrade_button = ttk.Button(
            detail_actions,
            text="升级到最新版本",
            command=lambda: self._update_selected(True),
        )
        self.upgrade_button.pack(side="left", padx=(6, 0))
        self.copy_button = ttk.Button(
            detail_actions, text="复制包名", command=self._copy_selected_name
        )
        self.copy_button.pack(side="right", padx=(0, 6))

        self.apply_theme(colors)
        self.refresh_view()

    def _on_body_configure(self, event) -> None:
        if event.height > 250:
            self._set_body_sash(event.height)

    def _set_body_sash(self, height: Optional[int] = None) -> None:
        if self._body_sash_done:
            return
        try:
            total = height or self.body_pane.winfo_height()
            if total <= 250:
                return
            target_details = min(170, max(155, int(total * 0.35)))
            self.body_pane.sashpos(0, max(100, total - target_details))
            self._body_sash_done = True
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    def apply_theme(self, colors: Dict[str, str]) -> None:
        self.colors = colors
        self.tree.tag_configure(
            "explicit", font=self.app.theme.fonts.ui_bold
        )
        self.tree.tag_configure("update", foreground=colors["success"])
        self.tree.tag_configure("compatible", foreground=colors["warning"])
        self.tree.tag_configure("error", foreground=colors["danger"])
        self.tree.tag_configure("pypi", foreground=colors["accent"])

    def set_workspace(
        self, workspace: Optional[WorkspaceData], env_name: str
    ) -> None:
        self.workspace = workspace
        self.env_name = env_name
        self._workspace_token += 1
        self.packages = workspace.packages_for_env(env_name) if workspace else []
        self._detail_key = None
        self._update_headline()
        self.refresh_view()

    def set_loading(self, message: str) -> None:
        self.status_var.set(message)
        self.status_label.configure(style="Muted.TLabel")

    def _update_headline(self) -> None:
        if not self.workspace:
            self.headline_var.set("未打开环境")
            return
        self.headline_var.set(
            "{} / {}".format(self.workspace.name or self.workspace.root.name, self.env_name)
        )

    def refresh_view(self) -> None:
        if not self.workspace:
            self.packages = []
            self.tree.delete(*self.tree.get_children())
            self.visible.clear()
            self.headline_var.set("未打开环境")
            self.status_var.set("")
            self._clear_details()
            return
        all_packages = self.packages
        user_count = sum(1 for package in all_packages if package.is_explicit)
        self.user_radio.configure(text="仅用户安装 ({})".format(user_count))
        self.all_radio.configure(text="全部库 ({})".format(len(all_packages)))
        mode = self.filter_var.get()
        query = self.search_var.get().strip().lower()
        kind = self.kind_var.get()
        selected = set(self.tree.selection())

        filtered: List[Package] = []
        for package in all_packages:
            if mode == "user" and not package.is_explicit:
                continue
            if kind == "Conda" and package.kind.lower() != "conda":
                continue
            if kind == "PyPI" and package.kind.lower() != "pypi":
                continue
            if query:
                haystack = " ".join(
                    (
                        package.name,
                        package.version,
                        package.requested_spec,
                        package.source,
                    )
                ).lower()
                if query not in haystack:
                    continue
            filtered.append(package)
        filtered = self._sort_packages(filtered)
        self.visible = {package.key: package for package in filtered}

        self.tree.delete(*self.tree.get_children())
        for package in filtered:
            tags = []
            if package.is_explicit:
                tags.append("explicit")
            if package.latest_error:
                tags.append("error")
            elif package.latest and package.compare_latest() > 0:
                tags.append("update")
            elif package.compatible_to and not package.latest:
                tags.append("compatible")
            if package.kind.lower() == "pypi":
                tags.append("pypi")
            self.tree.insert(
                "",
                "end",
                iid=package.key,
                values=(
                    package.name,
                    package.version,
                    package.latest or "",
                    package.status_text,
                    "PyPI" if package.kind.lower() == "pypi" else "Conda",
                    package.requested_spec or "",
                    package.short_source(),
                    format_size(package.size),
                ),
                tags=tuple(tags),
            )
        for key in selected:
            if self.tree.exists(key):
                self.tree.selection_add(key)
        error = self.workspace.package_errors.get(self.env_name)
        if error:
            self.status_var.set(
                "读取失败：{}  （可点击“安装环境”或“刷新”）".format(
                    truncate_text(error.replace("\n", " "), 180)
                )
            )
            self.status_label.configure(style="Danger.TLabel")
        else:
            self.status_var.set(
                "显示 {} / {} 个包 · 用户显式依赖 {} 个".format(
                    len(filtered), len(all_packages), user_count
                )
            )
            self.status_label.configure(style="Muted.TLabel")
        self._update_details()

    def _sort_packages(self, packages: List[Package]) -> List[Package]:
        column = self.sort_column
        reverse = self.sort_reverse

        def key(package: Package):
            if column == "version":
                return package.version
            if column == "latest":
                return package.latest or ""
            if column == "status":
                return package.status_text
            if column == "kind":
                return package.kind
            if column == "spec":
                return package.requested_spec
            if column == "source":
                return package.short_source()
            if column == "size":
                return package.size
            return package.name.casefold()

        if column in ("version", "latest"):
            packages = sorted(
                packages,
                key=lambda item: cmp_to_key(compare_versions)(
                    item.version if column == "version" else (item.latest or "")
                ),
                reverse=reverse,
            )
        else:
            packages = sorted(packages, key=key, reverse=reverse)
        return packages

    def sort_by(self, column: str) -> None:
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        self.refresh_view()

    # ------------------------------------------------------------------
    def _on_select(self, _event=None) -> None:
        selection = self.tree.selection()
        self._detail_key = selection[0] if selection else None
        self._update_details()

    def _selected_package(self) -> Optional[Package]:
        if self._detail_key:
            return self.visible.get(self._detail_key)
        return None

    def _update_details(self) -> None:
        package = self._selected_package()
        if package is None:
            self._clear_details()
            return
        values = {
            "name": package.name,
            "version": package.version,
            "build": package.build or "—",
            "kind": "PyPI" if package.kind.lower() == "pypi" else "Conda",
            "latest": package.latest or "未检查",
            "spec": package.requested_spec or "—",
            "source": package.short_source() or "—",
            "license": truncate_text(package.license, 60) or "—",
            "url": package.url or "—",
            "file": truncate_text(package.file_name, 70) or "—",
            "extra": "",
        }
        if package.latest_error:
            values["latest"] = "查询失败: " + truncate_text(package.latest_error, 55)
        elif package.compatible_to:
            values["extra"] = "兼容更新: {}".format(package.compatible_to)
        for key, value in values.items():
            self.detail_vars[key].set(value)
        self._detail_package = package

    def _clear_details(self) -> None:
        for var in self.detail_vars.values():
            var.set("—")
        self._detail_package = None

    def _show_full_details(self) -> None:
        package = self._selected_package()
        if package is None:
            return
        lines = [
            "名称: {}".format(package.name),
            "已安装版本: {}".format(package.version),
            "最新版本: {}".format(package.latest or "未检查"),
            "状态: {}".format(package.status_text),
            "类型: {}".format("PyPI" if package.kind.lower() == "pypi" else "Conda"),
            "构建: {}".format(package.build or "—"),
            "请求约束: {}".format(package.requested_spec or "—"),
            "来源: {}".format(package.source or "—"),
            "许可证: {}".format(package.license or "—"),
            "文件名: {}".format(package.file_name or "—"),
            "URL: {}".format(package.url or "—"),
        ]
        if package.depends:
            lines.extend(["", "运行依赖:"])
            lines.extend("  " + item for item in package.depends)
        if package.constrains:
            lines.extend(["", "约束:"])
            lines.extend("  " + item for item in package.constrains)
        if package.compatible_to:
            lines.extend(["", "兼容范围内可更新到: " + package.compatible_to])
        if package.latest_error:
            lines.extend(["", "最新版本查询失败: " + package.latest_error])
        from .dialogs import DetailsDialog

        DetailsDialog(
            self,
            "包详情：{}".format(package.name),
            package.name,
            "\n".join(lines),
            colors=self.colors,
        )

    def _copy_selected_name(self) -> None:
        package = self._selected_package()
        if package:
            self.clipboard_clear()
            self.clipboard_append(package.name)

    # ------------------------------------------------------------------
    def query_selected_latest(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("查询最新版本", "请先选择一个或多个包。", parent=self)
            return
        packages = [self.visible[key] for key in selection if key in self.visible]
        self.query_packages(packages)

    def query_packages(self, packages: List[Package]) -> None:
        if not self.workspace:
            return
        manifest = self.workspace.manifest
        platform = self.workspace.platform_for_env(self.env_name)
        token = self._workspace_token
        for package in packages:
            if package.checking_latest:
                continue
            package.checking_latest = True
            package.latest_error = ""
            self._refresh_row(package)
            self.app.query_latest_async(
                package,
                manifest,
                platform,
                lambda result, p=package, t=token: self._on_latest_result(p, result, t),
            )
        self.status_var.set("正在查询 {} 个包的最新版本…".format(len(packages)))

    def _on_latest_result(self, package: Package, result, token: int) -> None:
        if token != self._workspace_token:
            return
        package.checking_latest = False
        if isinstance(result, Exception):
            package.latest_error = str(result)
            package.latest = None
        else:
            package.latest_error = ""
            package.latest = str(result)
        self._refresh_row(package)
        if self._detail_key == package.key:
            self._update_details()
        self.status_var.set("最新版本查询完成")

    def _refresh_row(self, package: Package) -> None:
        if not self.tree.exists(package.key):
            return
        tags = []
        if package.is_explicit:
            tags.append("explicit")
        if package.latest_error:
            tags.append("error")
        elif package.latest and package.compare_latest() > 0:
            tags.append("update")
        elif package.compatible_to and not package.latest:
            tags.append("compatible")
        if package.kind.lower() == "pypi":
            tags.append("pypi")
        self.tree.item(
            package.key,
            values=(
                package.name,
                package.version,
                package.latest or "",
                package.status_text,
                "PyPI" if package.kind.lower() == "pypi" else "Conda",
                package.requested_spec or "",
                package.short_source(),
                format_size(package.size),
            ),
            tags=tuple(tags),
        )

    def apply_compatible_updates(self, updates: Dict[str, str]) -> None:
        for package in self.packages:
            package.compatible_to = updates.get(package.name)
        self.refresh_view()
        if updates:
            self.status_var.set(
                "发现 {} 个包存在兼容范围内的更新".format(len(updates))
            )
        else:
            self.status_var.set("兼容范围内没有可更新的包（或环境没有锁文件）")

    def _update_selected(self, upgrade: bool) -> None:
        package = self._selected_package()
        if package is None:
            messagebox.showinfo(
                "更新包", "请先在列表或详情中选择一个包。", parent=self
            )
            return
        self.app.update_package(package, upgrade=upgrade)

    def _context_menu(self, event) -> None:
        row = self.tree.identify_row(event.y)
        if not row:
            return
        if row not in self.tree.selection():
            self.tree.selection_set(row)
            self._detail_key = row
            self._update_details()
        menu = tk.Menu(self, tearoff=0)
        self.app.theme.style_menu(menu)
        menu.add_command(label="查询最新版本", command=self.query_selected_latest)
        menu.add_command(label="更新到兼容版本", command=lambda: self._update_selected(False))
        menu.add_command(label="升级到最新版本", command=lambda: self._update_selected(True))
        menu.add_separator()
        menu.add_command(label="复制包名", command=self._copy_selected_name)
        menu.add_command(label="复制已安装版本", command=self._copy_version)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _copy_version(self) -> None:
        package = self._selected_package()
        if package:
            self.clipboard_clear()
            self.clipboard_append(package.version)
