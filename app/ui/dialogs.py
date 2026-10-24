"""Modal dialogs used by the application."""

from __future__ import annotations

import os
import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

from .. import i18n
from ..models import manifest_for_path


class DetailsDialog(tk.Toplevel):
    def __init__(
        self,
        parent,
        title: str,
        message: str,
        details: str = "",
        colors: Optional[Dict[str, str]] = None,
    ):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.resizable(True, True)
        self.minsize(620, 360)
        colors = colors or {}
        self.configure(bg=colors.get("bg", "#f3f5f8"))

        header = ttk.Frame(self, padding=(14, 12, 14, 6))
        header.pack(fill="x")
        ttk.Label(
            header,
            text=message,
            style="Title.TLabel" if not details else "CardTitle.TLabel",
            wraplength=740,
            justify="left",
        ).pack(anchor="w")

        body = ttk.Frame(self, padding=(14, 4, 14, 8))
        body.pack(fill="both", expand=True)
        self.text = tk.Text(
            body,
            wrap="word",
            height=16,
            font=("Consolas", 9),
            relief="flat",
            borderwidth=0,
            padx=8,
            pady=8,
        )
        self.text.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(body, command=self.text.yview)
        scrollbar.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=scrollbar.set)
        if colors:
            self.text.configure(
                background=colors.get("panel", "#ffffff"),
                foreground=colors.get("text", "#1f2937"),
                insertbackground=colors.get("text", "#1f2937"),
                selectbackground=colors.get("selected", "#dbeafe"),
            )
        self.text.insert("1.0", details or message)
        self.text.configure(state="disabled")

        footer = ttk.Frame(self, padding=(14, 0, 14, 12))
        footer.pack(fill="x")
        ttk.Button(footer, text="复制详情", command=self._copy).pack(
            side="left"
        )
        ttk.Button(footer, text="关闭", style="Accent.TButton", command=self.destroy).pack(
            side="right"
        )
        self.bind("<Escape>", lambda _event: self.destroy())
        self._center(parent)
        i18n.localize_widget_tree(self)

    def _copy(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.text.get("1.0", "end-1c"))

    def _center(self, parent) -> None:
        self.update_idletasks()
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            width = max(620, self.winfo_width())
            height = max(360, self.winfo_height())
            x = px + max(0, (pw - width) // 2)
            y = py + max(0, (ph - height) // 2)
            self.geometry("+{}+{}".format(x, y))
        except tk.TclError:
            pass
        self.grab_set()
        self.focus_set()


def show_error(
    parent,
    title: str,
    message: str,
    details: str = "",
    colors: Optional[Dict[str, str]] = None,
) -> None:
    if details:
        DetailsDialog(parent, title, message, details, colors=colors)
    else:
        messagebox.showerror(title, message, parent=parent)


def show_info(parent, title: str, message: str) -> None:
    messagebox.showinfo(title, message, parent=parent)


class OpenEnvironmentDialog(tk.Toplevel):
    def __init__(self, parent, initial_dir: str = ""):
        super().__init__(parent)
        self.title("打开 Pixi 环境")
        self.transient(parent)
        self.resizable(True, False)
        self.result: Optional[str] = None
        self.new_workspace_path: Optional[str] = None
        self.initial_dir = initial_dir or str(Path.home())

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text="选择工作区",
            style="CardTitle.TLabel",
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 4))
        ttk.Label(
            frame,
            text="可以选 pixi.toml / pyproject.toml，也可以选工作区目录。",
            style="MutedCard.TLabel",
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 10))

        self.path_var = tk.StringVar()
        entry = ttk.Entry(frame, textvariable=self.path_var, width=64)
        entry.grid(row=2, column=0, columnspan=2, sticky="ew", pady=2)
        ttk.Button(frame, text="选择清单文件…", command=self._browse_file).grid(
            row=2, column=2, padx=(8, 0), sticky="ew"
        )
        ttk.Button(frame, text="选择目录…", command=self._browse_folder).grid(
            row=2, column=3, padx=(8, 0), sticky="ew"
        )

        ttk.Label(
            frame,
            text="最近使用的工作区也可以在顶部“最近打开”菜单中快速切换。",
            style="MutedCard.TLabel",
        ).grid(row=3, column=0, columnspan=4, sticky="w", pady=(10, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(16, 0))
        ttk.Button(
            buttons, text="新建工作区…", command=self._new_workspace
        ).pack(side="left")
        ttk.Button(buttons, text="取消", command=self.destroy).pack(
            side="right", padx=(8, 0)
        )
        ttk.Button(
            buttons, text="打开", style="Accent.TButton", command=self._accept
        ).pack(side="right")

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        self.bind("<Escape>", lambda _event: self.destroy())
        entry.bind("<Return>", lambda _event: self._accept())
        self.grab_set()
        self.update_idletasks()
        self._center(parent)
        i18n.localize_widget_tree(self)
        entry.focus_set()

    def _center(self, parent) -> None:
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            width = self.winfo_width()
            height = self.winfo_height()
            self.geometry(
                "+{}+{}".format(
                    px + max(0, (pw - width) // 2), py + max(0, (ph - height) // 2)
                )
            )
        except tk.TclError:
            pass

    def _browse_file(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="选择 Pixi 清单文件",
            initialdir=self.initial_dir,
            filetypes=[
                ("Pixi 清单", "*.toml"),
                ("TOML 文件", "*.toml"),
                ("所有文件", "*.*"),
            ],
        )
        if path:
            self.path_var.set(path)

    def _browse_folder(self) -> None:
        path = filedialog.askdirectory(
            parent=self, title="选择工作区目录", initialdir=self.initial_dir
        )
        if path:
            self.path_var.set(path)

    def _new_workspace(self) -> None:
        raw = self.path_var.get().strip().strip('"')
        if raw:
            candidate = Path(raw).expanduser()
            if candidate.is_file():
                raw = str(candidate.parent)
        self.new_workspace_path = raw or self.initial_dir
        self.destroy()

    def _accept(self) -> None:
        raw = self.path_var.get().strip().strip('"')
        if not raw:
            messagebox.showwarning("路径为空", "请选择或输入工作区路径。", parent=self)
            return
        path = Path(raw).expanduser()
        if path.exists() and not path.is_dir():
            messagebox.showerror(
                "路径无效", "目标路径不是目录。", parent=self
            )
            return
        manifest = manifest_for_path(path)
        if manifest is not None:
            self.result = str(manifest)
            self.destroy()
            return
        if path.exists():
            if not messagebox.askyesno(
                "没有 Pixi 清单",
                "该目录下没有 pixi.toml 或 pyproject.toml。\n\n"
                "是否创建新的 Pixi 工作区？",
                parent=self,
            ):
                return
            self.new_workspace_path = str(path)
            self.destroy()
            return
        if not messagebox.askyesno(
            "目录不存在",
            "目录不存在：\n{}\n\n是否创建该目录并初始化 Pixi 工作区？".format(path),
            parent=self,
        ):
            return
        self.new_workspace_path = str(path)
        self.destroy()


class NewWorkspaceDialog(tk.Toplevel):
    def __init__(
        self,
        parent,
        initial_path: str = "",
        default_platform: str = "win-64",
    ):
        super().__init__(parent)
        self.title("新建 Pixi 工作区")
        self.transient(parent)
        self.resizable(True, False)
        self.result: Optional[Dict[str, object]] = None
        self.initial_path = initial_path
        self.default_platform = default_platform
        self.platform_vars: Dict[str, tk.BooleanVar] = {}

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="新建 Pixi 工作区", style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        ttk.Label(
            frame,
            text="只会创建 pixi.toml；不安装依赖，创建后进入基础依赖视图。",
            style="MutedCard.TLabel",
            wraplength=680,
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(3, 12))

        ttk.Label(frame, text="目录", style="Muted.TLabel").grid(
            row=2, column=0, sticky="w", pady=4
        )
        self.path_var = tk.StringVar(value=initial_path)
        self.path_entry = ttk.Entry(frame, textvariable=self.path_var, width=66)
        self.path_entry.grid(row=2, column=1, sticky="ew", pady=4)
        ttk.Button(frame, text="选择目录…", command=self._browse).grid(
            row=2, column=2, padx=(8, 0), pady=4
        )
        self.name_var = tk.StringVar(value="")
        ttk.Label(frame, text="工作区名称", style="Muted.TLabel").grid(
            row=3, column=0, sticky="w", pady=4
        )
        ttk.Label(
            frame,
            textvariable=self.name_var,
            style="Card.TLabel",
        ).grid(row=3, column=1, columnspan=2, sticky="w", pady=4)
        self.preview_var = tk.StringVar(value="")
        self.preview_label = ttk.Label(
            frame,
            textvariable=self.preview_var,
            style="MutedCard.TLabel",
            wraplength=680,
        )
        self.preview_label.grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(0, 8)
        )

        ttk.Label(frame, text="频道", style="Muted.TLabel").grid(
            row=5, column=0, sticky="w", pady=4
        )
        self.channels_var = tk.StringVar(value="conda-forge")
        ttk.Entry(frame, textvariable=self.channels_var, width=48).grid(
            row=5, column=1, columnspan=2, sticky="ew", pady=4
        )
        ttk.Label(
            frame,
            text="多个频道用逗号分隔，例如 conda-forge,bioconda。",
            style="MutedCard.TLabel",
        ).grid(row=6, column=1, columnspan=2, sticky="w")

        ttk.Label(frame, text="平台", style="Muted.TLabel").grid(
            row=7, column=0, sticky="nw", pady=(10, 4)
        )
        platform_frame = ttk.Frame(frame)
        platform_frame.grid(
            row=7, column=1, columnspan=2, sticky="w", pady=(10, 4)
        )
        platforms = ("win-64", "linux-64", "osx-64", "osx-arm64")
        if default_platform and default_platform not in platforms:
            platforms = (default_platform,) + platforms
        for index, name in enumerate(platforms):
            var = tk.BooleanVar(value=name == default_platform)
            self.platform_vars[name] = var
            ttk.Checkbutton(
                platform_frame, text=name, variable=var
            ).grid(row=0, column=index, sticky="w", padx=(0, 14))
        ttk.Label(
            frame,
            text="至少选择一个平台；默认使用当前系统平台。",
            style="MutedCard.TLabel",
        ).grid(row=8, column=1, columnspan=2, sticky="w")

        ttk.Label(
            frame,
            text="Pixi 会同时创建 .gitignore 和 .gitattributes；工作区名称由目录名决定。",
            style="MutedCard.TLabel",
            wraplength=680,
        ).grid(row=9, column=0, columnspan=3, sticky="w", pady=(12, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(row=10, column=0, columnspan=3, sticky="e", pady=(16, 0))
        ttk.Button(buttons, text="取消", command=self.destroy).pack(side="right")
        ttk.Button(
            buttons,
            text="创建",
            style="Accent.TButton",
            command=self._accept,
        ).pack(side="right", padx=(0, 8))

        frame.columnconfigure(1, weight=1)
        self.path_var.trace_add("write", lambda *_: self._update_preview())
        self.bind("<Escape>", lambda _event: self.destroy())
        self.grab_set()
        self.update_idletasks()
        self._center(parent)
        self._update_preview()
        i18n.localize_widget_tree(self)
        self.path_entry.focus_set()

    def _center(self, parent) -> None:
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            self.geometry(
                "+{}+{}".format(
                    px + max(0, (parent.winfo_width() - self.winfo_width()) // 2),
                    py + max(0, (parent.winfo_height() - self.winfo_height()) // 2),
                )
            )
        except tk.TclError:
            pass

    def _browse(self) -> None:
        initial = self.path_var.get().strip() or self.initial_path
        if initial:
            candidate = Path(initial).expanduser()
            if candidate.exists():
                initial = str(candidate.parent if candidate.is_file() else candidate)
            elif candidate.parent.exists():
                initial = str(candidate.parent)
            else:
                initial = str(Path.home())
        path = filedialog.askdirectory(
            parent=self,
            title="选择工作区目录",
            initialdir=initial or str(Path.home()),
            mustexist=False,
        )
        if path:
            self.path_var.set(path)

    def _update_preview(self) -> None:
        raw = self.path_var.get().strip().strip('"')
        if not raw:
            self.name_var.set("—")
            self.preview_var.set("请选择一个目录。")
            return
        path = Path(raw).expanduser()
        self.name_var.set(path.name or "—")
        if path.exists() and not path.is_dir():
            self.preview_var.set("目标路径已存在且不是目录。")
        elif path.exists() and manifest_for_path(path) is not None:
            self.preview_var.set("目录中已有 Pixi 清单，请直接打开。")
        elif path.exists() and (path / "pyproject.toml").is_file():
            self.preview_var.set(
                "目录中已有 pyproject.toml；新建向导只创建 pixi.toml。"
            )
        elif path.exists():
            try:
                nonempty = any(path.iterdir())
            except OSError:
                nonempty = False
            self.preview_var.set(
                "目录非空，创建时会追加 pixi.toml、.gitignore、.gitattributes。"
                if nonempty
                else "目录为空，将创建 pixi.toml。"
            )
        else:
            self.preview_var.set("目录不存在，创建时会自动建立。")
        i18n.localize_widget_tree(self)

    def _accept(self) -> None:
        raw = self.path_var.get().strip().strip('"')
        if not raw:
            messagebox.showwarning("路径为空", "请选择或输入工作区目录。", parent=self)
            return
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        if path.exists() and not path.is_dir():
            messagebox.showerror("路径无效", "目标路径已存在且不是目录。", parent=self)
            return
        if path.exists() and manifest_for_path(path) is not None:
            messagebox.showinfo(
                "已有 Pixi 清单",
                "该目录已有 Pixi 清单，请直接打开。",
                parent=self,
            )
            return
        if path.exists() and (path / "pyproject.toml").is_file():
            messagebox.showerror(
                "已有 pyproject.toml",
                "新建向导只创建 pixi.toml。该目录已有 pyproject.toml，"
                "请换一个目录或直接打开现有清单。",
                parent=self,
            )
            return
        name = path.name
        if not name:
            messagebox.showwarning("目录无效", "不能直接在磁盘根目录创建工作区。", parent=self)
            return
        channels = [
            item.strip()
            for item in re.split(r"[,;\n]", self.channels_var.get())
            if item.strip()
        ]
        if not channels:
            messagebox.showwarning("频道为空", "至少填写一个频道。", parent=self)
            return
        platforms = [name for name, var in self.platform_vars.items() if var.get()]
        if not platforms:
            messagebox.showwarning("平台为空", "至少选择一个平台。", parent=self)
            return
        if path.exists():
            try:
                nonempty = any(path.iterdir())
            except OSError:
                nonempty = False
            if nonempty and not messagebox.askyesno(
                "目录非空",
                "目录中已有文件。Pixi 会追加 .gitignore、.gitattributes 和 "
                "pixi.toml，但不会删除已有文件。\n\n继续创建吗？",
                parent=self,
            ):
                return
        self.result = {
            "path": str(path),
            "channels": channels,
            "platforms": platforms,
            "name": name,
        }
        self.destroy()


class TaskArgsDialog(tk.Toplevel):
    def __init__(self, parent, task_name: str, initial: str = ""):
        super().__init__(parent)
        self.title("运行任务：{}".format(task_name))
        self.transient(parent)
        self.resizable(True, False)
        self.result: Optional[str] = None

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="附加参数", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text="参数会追加到 pixi run 命令末尾；包含空格的路径请加双引号。",
            style="MutedCard.TLabel",
            wraplength=560,
        ).pack(anchor="w", pady=(3, 8))
        self.entry = ttk.Entry(frame, width=68)
        self.entry.pack(fill="x")
        self.entry.insert(0, initial)
        self.entry.bind("<Return>", lambda _event: self._accept())
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(14, 0))
        ttk.Button(buttons, text="取消", command=self.destroy).pack(side="right")
        ttk.Button(
            buttons, text="运行", style="Accent.TButton", command=self._accept
        ).pack(side="right", padx=(0, 8))
        self.grab_set()
        self.update_idletasks()
        self._center(parent)
        i18n.localize_widget_tree(self)
        self.entry.focus_set()

    def _center(self, parent) -> None:
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            self.geometry(
                "+{}+{}".format(px + 120, py + 120)
            )
        except tk.TclError:
            pass

    def _accept(self) -> None:
        self.result = self.entry.get()
        self.destroy()


class AddEnvironmentDialog(tk.Toplevel):
    def __init__(
        self,
        parent,
        existing_names: List[str],
        features: List[str],
        default_install: bool = True,
    ):
        super().__init__(parent)
        self.title(i18n.t("添加环境"))
        self.transient(parent)
        self.resizable(True, False)
        self.result: Optional[Dict[str, object]] = None
        self.existing_names = set(existing_names)
        self.features = [name for name in features if name != "default"]

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="环境名称", style="CardTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(frame, textvariable=self.name_var, width=44)
        self.name_entry.grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(4, 2)
        )
        ttk.Label(
            frame,
            text="名称不能重复，default 是隐式环境，不能作为新名称。",
            style="MutedCard.TLabel",
        ).grid(row=2, column=0, columnspan=2, sticky="w")

        ttk.Label(frame, text="Features", style="CardTitle.TLabel").grid(
            row=3, column=0, sticky="w", pady=(14, 4)
        )
        self.default_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            frame,
            text="包含 default feature",
            variable=self.default_var,
        ).grid(row=4, column=0, columnspan=2, sticky="w")

        self.feature_vars: Dict[str, tk.BooleanVar] = {}
        feature_frame = ttk.Frame(frame)
        feature_frame.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        if self.features:
            for index, feature in enumerate(self.features):
                var = tk.BooleanVar(value=False)
                self.feature_vars[feature] = var
                ttk.Checkbutton(
                    feature_frame, text=feature, variable=var
                ).grid(row=index // 3, column=index % 3, sticky="w", padx=(0, 14), pady=2)
        else:
            ttk.Label(
                feature_frame,
                text="工作区没有其他 feature。",
                style="MutedCard.TLabel",
            ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            frame,
            text="取消 default feature 时，必须至少选择一个其他 feature。",
            style="MutedCard.TLabel",
            wraplength=620,
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(4, 0))

        ttk.Label(frame, text="Solve group（可选）", style="CardTitle.TLabel").grid(
            row=7, column=0, sticky="w", pady=(14, 4)
        )
        self.solve_group_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.solve_group_var, width=32).grid(
            row=8, column=0, sticky="w"
        )

        self.install_var = tk.BooleanVar(value=default_install)
        ttk.Checkbutton(
            frame,
            text="创建后立即安装环境",
            variable=self.install_var,
        ).grid(row=9, column=0, columnspan=2, sticky="w", pady=(14, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(row=10, column=0, columnspan=2, sticky="e", pady=(18, 0))
        ttk.Button(buttons, text="取消", command=self.destroy).pack(side="right")
        ttk.Button(
            buttons,
            text="添加环境",
            style="Accent.TButton",
            command=self._accept,
        ).pack(side="right", padx=(0, 8))

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        self.bind("<Escape>", lambda _event: self.destroy())
        self.grab_set()
        self.update_idletasks()
        self._center(parent)
        i18n.localize_widget_tree(self)
        self.name_entry.focus_set()

    def _center(self, parent) -> None:
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            self.geometry(
                "+{}+{}".format(
                    px + max(0, (parent.winfo_width() - self.winfo_width()) // 2),
                    py + max(0, (parent.winfo_height() - self.winfo_height()) // 2),
                )
            )
        except tk.TclError:
            pass

    def _accept(self) -> None:
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("环境名称", "请输入环境名称。", parent=self)
            return
        if name == "default":
            messagebox.showwarning(
                "环境名称", "default 是隐式环境，不能作为新环境名称。", parent=self
            )
            return
        if name in self.existing_names:
            messagebox.showwarning(
                "环境已存在", "环境“{}”已经存在。".format(name), parent=self
            )
            return
        if re.search(r"\s", name) or '"' in name or "'" in name:
            messagebox.showwarning(
                "环境名称",
                "环境名称不能包含空格、单引号或双引号。",
                parent=self,
            )
            return
        selected = [
            feature for feature, var in self.feature_vars.items() if var.get()
        ]
        if not self.default_var.get() and not selected:
            messagebox.showwarning(
                "Features",
                "取消 default feature 后，必须至少选择一个其他 feature。",
                parent=self,
            )
            return
        self.result = {
            "name": name,
            "features": selected,
            "use_default": bool(self.default_var.get()),
            "solve_group": self.solve_group_var.get().strip(),
            "install": bool(self.install_var.get()),
        }
        self.destroy()


class RemoveEnvironmentDialog(tk.Toplevel):
    def __init__(self, parent, name: str, has_directory: bool):
        super().__init__(parent)
        self.title(i18n.t("删除环境"))
        self.transient(parent)
        self.resizable(False, False)
        self.result: Optional[Dict[str, object]] = None
        self.name = name

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text="从清单中删除环境“{}”？".format(name),
            style="CardTitle.TLabel",
            wraplength=620,
        ).pack(anchor="w")
        ttk.Label(
            frame,
            text="这会修改 pixi.toml / pyproject.toml，但不会自动更新 lock 文件。",
            style="MutedCard.TLabel",
            wraplength=620,
        ).pack(anchor="w", pady=(4, 10))

        self.cleanup_var = tk.BooleanVar(value=False)
        cleanup = ttk.Checkbutton(
            frame,
            text="同时清理已安装的环境目录（pixi clean）",
            variable=self.cleanup_var,
        )
        cleanup.pack(anchor="w")
        if not has_directory:
            cleanup.configure(state="disabled")
            ttk.Label(
                frame,
                text="该环境当前没有已安装的 .pixi 环境目录。",
                style="MutedCard.TLabel",
            ).pack(anchor="w", pady=(3, 0))

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(18, 0))
        ttk.Button(buttons, text="取消", command=self.destroy).pack(side="right")
        ttk.Button(
            buttons,
            text="删除环境",
            style="Danger.TButton",
            command=self._accept,
        ).pack(side="right", padx=(0, 8))

        self.bind("<Escape>", lambda _event: self.destroy())
        self.grab_set()
        self.update_idletasks()
        self._center(parent)
        i18n.localize_widget_tree(self)

    def _center(self, parent) -> None:
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            self.geometry(
                "+{}+{}".format(
                    px + max(0, (parent.winfo_width() - self.winfo_width()) // 2),
                    py + max(0, (parent.winfo_height() - self.winfo_height()) // 2),
                )
            )
        except tk.TclError:
            pass

    def _accept(self) -> None:
        self.result = {
            "name": self.name,
            "cleanup": bool(self.cleanup_var.get()),
        }
        self.destroy()


class SettingsDialog(tk.Toplevel):
    def __init__(
        self,
        parent,
        pixi_path: str,
        theme_name: str,
        console_max_lines: int,
        history_count: int = 0,
        language: str = "zh",
    ):
        super().__init__(parent)
        self.title("设置")
        self.transient(parent)
        self.resizable(False, False)
        self.result: Optional[Dict[str, object]] = None
        self._history_count = history_count

        frame = ttk.Frame(self, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Pixi 可执行文件", style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        self.pixi_var = tk.StringVar(value=pixi_path)
        ttk.Entry(frame, textvariable=self.pixi_var, width=58).grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(4, 2)
        )
        ttk.Button(frame, text="浏览…", command=self._browse_pixi).grid(
            row=1, column=2, padx=(8, 0)
        )
        ttk.Label(
            frame,
            text="留空则自动从 PATH 查找；修改后下次刷新或重启生效。",
            style="Muted.TLabel",
        ).grid(row=2, column=0, columnspan=3, sticky="w")

        ttk.Label(frame, text="主题", style="CardTitle.TLabel").grid(
            row=3, column=0, sticky="w", pady=(16, 4)
        )
        self.theme_var = tk.StringVar(
            value=i18n.t("深色") if theme_name == "dark" else i18n.t("浅色")
        )
        ttk.Combobox(
            frame,
            textvariable=self.theme_var,
            values=(i18n.t("浅色"), i18n.t("深色")),
            state="readonly",
            width=12,
        ).grid(row=4, column=0, sticky="w")

        ttk.Label(frame, text="界面语言", style="CardTitle.TLabel").grid(
            row=5, column=0, sticky="w", pady=(16, 4)
        )
        self.language_var = tk.StringVar(value=i18n.language_display_name(language))
        ttk.Combobox(
            frame,
            textvariable=self.language_var,
            values=tuple(
                i18n.language_display_name(code) for code in ("zh", "en", "ja")
            ),
            state="readonly",
            width=12,
        ).grid(row=6, column=0, sticky="w")
        ttk.Label(
            frame,
            text="语言修改后需要重启程序生效。",
            style="Muted.TLabel",
        ).grid(row=6, column=1, columnspan=2, sticky="w", padx=(12, 0))

        ttk.Label(frame, text="控制台最大行数", style="CardTitle.TLabel").grid(
            row=3, column=1, sticky="w", pady=(16, 4)
        )
        self.lines_var = tk.StringVar(value=str(console_max_lines))
        ttk.Spinbox(
            frame, from_=1000, to=200000, increment=1000, textvariable=self.lines_var, width=14
        ).grid(row=4, column=1, sticky="w", padx=(12, 0))

        action_frame = ttk.Frame(frame)
        action_frame.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(20, 0))
        ttk.Button(
            action_frame,
            text="清空打开历史",
            command=self._clear_history,
        ).pack(side="left")
        ttk.Button(
            action_frame, text="取消", command=self.destroy
        ).pack(side="right")
        ttk.Button(
            action_frame,
            text="保存",
            style="Accent.TButton",
            command=self._accept,
        ).pack(side="right", padx=(0, 8))

        frame.columnconfigure(0, weight=1)
        self.bind("<Escape>", lambda _event: self.destroy())
        self.grab_set()
        self.update_idletasks()
        self._center(parent)
        i18n.localize_widget_tree(self)

    def _center(self, parent) -> None:
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            self.geometry(
                "+{}+{}".format(
                    px + max(0, (parent.winfo_width() - self.winfo_width()) // 2),
                    py + max(0, (parent.winfo_height() - self.winfo_height()) // 2),
                )
            )
        except tk.TclError:
            pass

    def _browse_pixi(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="选择 pixi 可执行文件",
            filetypes=[("Pixi", "pixi.exe"), ("可执行文件", "*.exe"), ("所有文件", "*.*")],
        )
        if path:
            self.pixi_var.set(path)

    def _clear_history(self) -> None:
        if messagebox.askyesno(
            "清空历史",
            "确定清空最近打开的环境记录吗？Python 程序历史不会被删除。",
            parent=self,
        ):
            self._history_count = 0
            self._clear_requested = True

    def _accept(self) -> None:
        try:
            lines = int(self.lines_var.get())
        except ValueError:
            messagebox.showerror("设置无效", "控制台最大行数必须是整数。", parent=self)
            return
        lines = max(1000, min(200000, lines))
        language_code = "zh"
        for code in ("zh", "en", "ja"):
            if self.language_var.get() == i18n.language_display_name(code):
                language_code = code
                break
        self.result = {
            "pixi_path": self.pixi_var.get().strip(),
            "theme": "dark" if self.theme_var.get() == i18n.t("深色") else "light",
            "console_max_lines": lines,
            "clear_history": bool(getattr(self, "_clear_requested", False)),
            "language": language_code,
        }
        self.destroy()
