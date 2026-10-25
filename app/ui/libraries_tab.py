"""Installed package list, filtering, and update discovery."""

from __future__ import annotations

import tkinter as tk
from functools import cmp_to_key
from tkinter import messagebox, ttk
from typing import Dict, List, Optional, Tuple

from .. import i18n
from ..manifest import normalize_package_name
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
        self.base_mode = False
        self.packages: List[Package] = []
        self.visible: Dict[str, Package] = {}
        self._current_packages: Dict[str, Package] = {}
        self._workspace_token = 0
        self.sort_column = "name"
        self.sort_reverse = False
        self._detail_key: Optional[str] = None

        header = ttk.Frame(self)
        header.pack(fill="x")
        ttk.Label(header, text="Packages", style="Title.TLabel").pack(side="left")
        self.headline_var = tk.StringVar(value="No environment")
        ttk.Label(
            header, textvariable=self.headline_var, style="Muted.TLabel"
        ).pack(side="left", padx=(10, 0), pady=(6, 0))

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(10, 6))
        self.filter_var = tk.StringVar(value="user")
        self.user_radio = ttk.Radiobutton(
            toolbar,
            text="User-installed",
            variable=self.filter_var,
            value="user",
            command=self.refresh_view,
        )
        self.user_radio.pack(side="left")
        self.all_radio = ttk.Radiobutton(
            toolbar,
            text="All Packages",
            variable=self.filter_var,
            value="all",
            command=self.refresh_view,
        )
        self.all_radio.pack(side="left", padx=(8, 0))

        ttk.Label(toolbar, text="Search", style="Muted.TLabel").pack(
            side="left", padx=(16, 4)
        )
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=22)
        self.search_entry.pack(side="left")
        self.search_var.trace_add("write", lambda *_: self.refresh_view())

        ttk.Label(toolbar, text="Type", style="Muted.TLabel").pack(
            side="left", padx=(12, 4)
        )
        self.kind_var = tk.StringVar(value=i18n.t("All"))
        self.kind_combo = ttk.Combobox(
            toolbar,
            textvariable=self.kind_var,
            values=(i18n.t("All"), "Conda", "PyPI"),
            state="readonly",
            width=8,
        )
        self.kind_combo.pack(side="left")
        self.kind_combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh_view())

        self.refresh_button = ttk.Button(
            toolbar, text="Refresh", command=self.app.refresh_current
        )
        self.refresh_button.pack(side="right")
        self.install_button = ttk.Button(
            toolbar, text="Install Environment", command=self.app.install_env
        )
        self.install_button.pack(side="right", padx=(0, 6))
        self.compat_button = ttk.Button(
            toolbar,
            text="Check Compatible Updates",
            command=self.app.check_compatible_updates,
        )
        self.compat_button.pack(side="right", padx=(0, 6))
        self.latest_button = ttk.Button(
            toolbar, text="Check Selected Latest", command=self.query_selected_latest
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
        columns = (
            "name",
            "version",
            "latest",
            "status",
            "kind",
            "scope",
            "spec",
            "source",
            "size",
        )
        self.tree = ttk.Treeview(
            table_frame, columns=columns, show="headings", selectmode="extended"
        )
        headings = {
            "name": "Name",
            "version": "Installed",
            "latest": "Latest version",
            "status": "Status",
            "kind": "Type",
            "scope": "Scope",
            "spec": "Requested",
            "source": "Source",
            "size": "Size",
        }
        widths = {
            "name": 210,
            "version": 105,
            "latest": 105,
            "status": 95,
            "kind": 65,
            "scope": 105,
            "spec": 180,
            "source": 200,
            "size": 75,
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
            self.body_pane, text="Package Details", padding=(7, 5)
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
            ("name", "Name", 0, 0, 1),
            ("version", "Version", 0, 2, 1),
            ("build", "Build", 0, 4, 1),
            ("kind", "Type", 0, 6, 1),
            ("latest", "Latest", 1, 0, 1),
            ("spec", "Requested", 1, 2, 3),
            ("license", "License", 1, 6, 1),
            ("source", "Source", 2, 0, 3),
            ("file", "File", 2, 4, 3),
            ("extra", "Notes", 3, 0, 6),
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
            text="Full Details…",
            command=self._show_full_details,
        )
        self.detail_info_button.pack(side="right")
        self.detail_latest_button = ttk.Button(
            detail_actions,
            text="Check This Package",
            command=self.query_selected_latest,
        )
        self.detail_latest_button.pack(side="left")
        self.update_button = ttk.Button(
            detail_actions,
            text="Update to compatible",
            command=lambda: self._update_selected(False),
        )
        self.update_button.pack(side="left", padx=(6, 0))
        self.upgrade_button = ttk.Button(
            detail_actions,
            text="Upgrade to Latest",
            command=lambda: self._update_selected(True),
        )
        self.upgrade_button.pack(side="left", padx=(6, 0))
        self.copy_button = ttk.Button(
            detail_actions, text="Copy Package Name", command=self._copy_selected_name
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
        self,
        workspace: Optional[WorkspaceData],
        env_name: str,
        base_mode: bool = False,
    ) -> None:
        self.workspace = workspace
        self.env_name = env_name
        self.base_mode = base_mode
        self._workspace_token += 1
        if not workspace:
            self.packages = []
        elif base_mode:
            self.packages = self._base_packages(workspace)
        else:
            self.packages = workspace.packages_for_env(env_name)
            for package in self.packages:
                package.scope = workspace.scopes.scope_for(package.name)
        self._detail_key = None
        self._update_headline()
        self.refresh_view()

    def _base_packages(self, workspace: WorkspaceData) -> List[Package]:
        installed = {
            normalize_package_name(package.name): package
            for package in workspace.packages_for_env("default")
        }
        packages: List[Package] = []
        for spec in workspace.scopes.base_packages():
            package = installed.get(normalize_package_name(spec.name))
            if package is not None:
                package.is_explicit = True
                package.scope = "base"
                packages.append(package)
            else:
                packages.append(
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
        return packages

    def set_loading(self, message: str) -> None:
        self.status_var.set(message)
        self.status_label.configure(style="Muted.TLabel")

    def _update_headline(self) -> None:
        if not self.workspace:
            self.headline_var.set("No environment")
            return
        environment = i18n.t("Base dependencies") if self.base_mode else self.env_name
        self.headline_var.set(
            "{} / {}".format(
                self.workspace.name or self.workspace.root.name, environment
            )
        )

    def refresh_view(self) -> None:
        if not self.workspace:
            self.packages = []
            self.tree.delete(*self.tree.get_children())
            self.visible.clear()
            self.headline_var.set("No environment")
            self.status_var.set("")
            self._clear_details()
            return
        all_packages = self.packages
        user_count = sum(1 for package in all_packages if package.is_explicit)
        if self.base_mode:
            self.filter_var.set("user")
            self.user_radio.configure(text="Base dependencies ({})".format(user_count))
            self.all_radio.configure(
                text="All Packages ({})".format(len(all_packages)), state="disabled"
            )
            mode = "user"
        else:
            self.user_radio.configure(text="User-installed ({})".format(user_count))
            self.all_radio.configure(
                text="All Packages ({})".format(len(all_packages)), state="normal"
            )
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
                    package.scope_text,
                    package.requested_spec or "",
                    package.short_source(),
                    format_size(package.size),
                ),
                tags=tuple(tags),
            )
        for key in selected:
            if self.tree.exists(key):
                self.tree.selection_add(key)
        error_key = "default" if self.base_mode else self.env_name
        error = self.workspace.package_errors.get(error_key)
        if error:
            self.status_var.set(
                "Read failed: {} (try Install Environment or Refresh)".format(
                    truncate_text(error.replace("\n", " "), 180)
                )
            )
            self.status_label.configure(style="Danger.TLabel")
        elif self.base_mode:
            self.status_var.set(
                "{} base dependencies · shared by all environments".format(len(filtered))
            )
            self.status_label.configure(style="Muted.TLabel")
        else:
            self.status_var.set(
                "Showing {} / {} packages · {} explicit dependencies".format(
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
            if column == "scope":
                return package.scope_text
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
            "latest": package.latest or "Not checked",
            "spec": package.requested_spec or "—",
            "source": package.short_source() or "—",
            "license": truncate_text(package.license, 60) or "—",
            "url": package.url or "—",
            "file": truncate_text(package.file_name, 70) or "—",
            "extra": "",
        }
        extra = "{}: {}".format(i18n.t("Scope"), package.scope_text)
        if package.latest_error:
            values["latest"] = "Check failed: " + truncate_text(package.latest_error, 55)
        elif package.compatible_to:
            extra += " · {}: {}".format(
                i18n.t("Compatible update"), package.compatible_to
            )
        values["extra"] = extra
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
            i18n.t("Name: {}", package.name),
            i18n.t("Installed: {}", package.version),
            i18n.t("Latest: {}", package.latest or i18n.t("Not checked")),
            i18n.t("Status: {}", package.status_text),
            i18n.t(
                "Type: {}",
                "PyPI" if package.kind.lower() == "pypi" else "Conda",
            ),
            i18n.t("Build: {}", package.build or "—"),
            i18n.t("Requested: {}", package.requested_spec or "—"),
            i18n.t("Source: {}", package.source or "—"),
            i18n.t("License: {}", package.license or "—"),
            i18n.t("File: {}", package.file_name or "—"),
            i18n.t("URL: {}", package.url or "—"),
        ]
        if package.depends:
            lines.extend(["", i18n.t("Runtime dependencies:")])
            lines.extend("  " + item for item in package.depends)
        if package.constrains:
            lines.extend(["", i18n.t("Constraints:")])
            lines.extend("  " + item for item in package.constrains)
        if package.compatible_to:
            lines.extend(
                ["", i18n.t("Compatible update: ") + package.compatible_to]
            )
        if package.latest_error:
            lines.extend(
                ["", i18n.t("Latest-version check failed: ") + package.latest_error]
            )
        from .dialogs import DetailsDialog

        DetailsDialog(
            self,
            "Package details: {}".format(package.name),
            package.name,
            "\n".join(lines),
            colors=self.colors,
        )

    def _copy_selected_name(self) -> None:
        selected = set(self.tree.selection())
        if not selected:
            return
        names = [
            package.name
            for key, package in self.visible.items()
            if key in selected
        ]
        if names:
            self.clipboard_clear()
            self.clipboard_append(" ".join(names))

    # ------------------------------------------------------------------
    def query_selected_latest(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Check Latest", "Select one or more packages first.", parent=self)
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
        self.status_var.set("Checking the latest version of {} package(s)…".format(len(packages)))

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
        self.status_var.set("Latest-version check finished")

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
                "{} packages have compatible updates".format(len(updates))
            )
        else:
            self.status_var.set("No compatible updates (or no lock file)")

    def _update_selected(self, upgrade: bool) -> None:
        package = self._selected_package()
        if package is None:
            messagebox.showinfo(
                "Update Package", "Select a package in the list or details first.", parent=self
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
        menu.add_command(label="Check Latest", command=self.query_selected_latest)
        menu.add_command(label="Update to compatible", command=lambda: self._update_selected(False))
        menu.add_command(label="Upgrade to Latest", command=lambda: self._update_selected(True))
        menu.add_separator()
        menu.add_command(label="Copy Package Name", command=self._copy_selected_name)
        menu.add_command(label="Copy Installed Version", command=self._copy_version)
        i18n.localize_menu(menu)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _copy_version(self) -> None:
        package = self._selected_package()
        if package:
            self.clipboard_clear()
            self.clipboard_append(package.version)
