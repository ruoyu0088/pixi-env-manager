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
        ttk.Button(footer, text="Copy Details", command=self._copy).pack(
            side="left"
        )
        ttk.Button(footer, text="Close", style="Accent.TButton", command=self.destroy).pack(
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
        self.title("Open Pixi Environment")
        self.transient(parent)
        self.resizable(True, False)
        self.result: Optional[str] = None
        self.new_workspace_path: Optional[str] = None
        self.initial_dir = initial_dir or str(Path.home())

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text="Open Workspace",
            style="CardTitle.TLabel",
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 4))
        ttk.Label(
            frame,
            text="Choose pixi.toml / pyproject.toml or a workspace directory.",
            style="MutedCard.TLabel",
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 10))

        self.path_var = tk.StringVar()
        entry = ttk.Entry(frame, textvariable=self.path_var, width=64)
        entry.grid(row=2, column=0, columnspan=2, sticky="ew", pady=2)
        ttk.Button(frame, text="Choose Manifest…", command=self._browse_file).grid(
            row=2, column=2, padx=(8, 0), sticky="ew"
        )
        ttk.Button(frame, text="Choose Folder…", command=self._browse_folder).grid(
            row=2, column=3, padx=(8, 0), sticky="ew"
        )

        ttk.Label(
            frame,
            text="Recently used workspaces can also be switched from the “Recent” menu at the top.",
            style="MutedCard.TLabel",
        ).grid(row=3, column=0, columnspan=4, sticky="w", pady=(10, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(16, 0))
        ttk.Button(
            buttons, text="New Workspace…", command=self._new_workspace
        ).pack(side="left")
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(
            side="right", padx=(8, 0)
        )
        ttk.Button(
            buttons, text="Open", style="Accent.TButton", command=self._accept
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
            title="Choose Pixi manifest file",
            initialdir=self.initial_dir,
            filetypes=[
                ("Pixi manifest", "*.toml"),
                ("TOML file", "*.toml"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.path_var.set(path)

    def _browse_folder(self) -> None:
        path = filedialog.askdirectory(
            parent=self, title="Choose workspace directory", initialdir=self.initial_dir
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
            messagebox.showwarning("Empty path", "Choose or enter a workspace path.", parent=self)
            return
        path = Path(raw).expanduser()
        if path.exists() and not path.is_dir():
            messagebox.showerror(
                "Invalid path", "The target path is not a directory.", parent=self
            )
            return
        manifest = manifest_for_path(path)
        if manifest is not None:
            self.result = str(manifest)
            self.destroy()
            return
        if path.exists():
            if not messagebox.askyesno(
                "No Pixi manifest",
                "This directory has no pixi.toml or pyproject.toml.\n\nCreate a new Pixi workspace?",
                parent=self,
            ):
                return
            self.new_workspace_path = str(path)
            self.destroy()
            return
        if not messagebox.askyesno(
            "Directory does not exist",
            "The directory does not exist:\n{}\n\nCreate it and initialize a Pixi workspace?".format(path),
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
        self.title("New Pixi Workspace")
        self.transient(parent)
        self.resizable(True, False)
        self.result: Optional[Dict[str, object]] = None
        self.initial_path = initial_path
        self.default_platform = default_platform
        self.platform_vars: Dict[str, tk.BooleanVar] = {}

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="New Pixi Workspace", style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        ttk.Label(
            frame,
            text="Creates only pixi.toml; dependencies are not installed. The workspace opens in the Base dependencies view.",
            style="MutedCard.TLabel",
            wraplength=680,
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(3, 12))

        ttk.Label(frame, text="Directory", style="Muted.TLabel").grid(
            row=2, column=0, sticky="w", pady=4
        )
        self.path_var = tk.StringVar(value=initial_path)
        self.path_entry = ttk.Entry(frame, textvariable=self.path_var, width=66)
        self.path_entry.grid(row=2, column=1, sticky="ew", pady=4)
        ttk.Button(frame, text="Choose Folder…", command=self._browse).grid(
            row=2, column=2, padx=(8, 0), pady=4
        )
        self.name_var = tk.StringVar(value="")
        ttk.Label(frame, text="Workspace name", style="Muted.TLabel").grid(
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

        ttk.Label(frame, text="Channel", style="Muted.TLabel").grid(
            row=5, column=0, sticky="w", pady=4
        )
        self.channels_var = tk.StringVar(value="conda-forge")
        ttk.Entry(frame, textvariable=self.channels_var, width=48).grid(
            row=5, column=1, columnspan=2, sticky="ew", pady=4
        )
        ttk.Label(
            frame,
            text="Separate multiple channels with commas, e.g. conda-forge,bioconda.",
            style="MutedCard.TLabel",
        ).grid(row=6, column=1, columnspan=2, sticky="w")

        ttk.Label(frame, text="Platform", style="Muted.TLabel").grid(
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
            text="Select at least one platform; the current platform is selected by default.",
            style="MutedCard.TLabel",
        ).grid(row=8, column=1, columnspan=2, sticky="w")

        ttk.Label(
            frame,
            text="Pixi also creates .gitignore and .gitattributes; the workspace name comes from the directory name.",
            style="MutedCard.TLabel",
            wraplength=680,
        ).grid(row=9, column=0, columnspan=3, sticky="w", pady=(12, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(row=10, column=0, columnspan=3, sticky="e", pady=(16, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(
            buttons,
            text="Create",
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
            title=i18n.t("Choose workspace directory"),
            initialdir=initial or str(Path.home()),
            mustexist=False,
        )
        if path:
            self.path_var.set(path)

    def _update_preview(self) -> None:
        raw = self.path_var.get().strip().strip('"')
        if not raw:
            self.name_var.set("—")
            self.preview_var.set("Choose a directory.")
            return
        path = Path(raw).expanduser()
        self.name_var.set(path.name or "—")
        if path.exists() and not path.is_dir():
            self.preview_var.set("The target path exists and is not a directory.")
        elif path.exists() and manifest_for_path(path) is not None:
            self.preview_var.set("This directory already has a Pixi manifest; open it directly.")
        elif path.exists() and (path / "pyproject.toml").is_file():
            self.preview_var.set(
                "This directory already has pyproject.toml; the new-workspace wizard only creates pixi.toml."
            )
        elif path.exists():
            try:
                nonempty = any(path.iterdir())
            except OSError:
                nonempty = False
            self.preview_var.set(
                "The directory is not empty; pixi.toml, .gitignore and .gitattributes will be added."
                if nonempty
                else "The directory is empty; pixi.toml will be created."
            )
        else:
            self.preview_var.set("The directory does not exist and will be created.")
        i18n.localize_widget_tree(self)

    def _accept(self) -> None:
        raw = self.path_var.get().strip().strip('"')
        if not raw:
            messagebox.showwarning("Empty path", "Choose or enter a workspace directory.", parent=self)
            return
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        if path.exists() and not path.is_dir():
            messagebox.showerror("Invalid path", "The target path exists and is not a directory.", parent=self)
            return
        if path.exists() and manifest_for_path(path) is not None:
            messagebox.showinfo(
                "Pixi manifest already exists",
                "This directory already has a Pixi manifest; open it directly.",
                parent=self,
            )
            return
        if path.exists() and (path / "pyproject.toml").is_file():
            messagebox.showerror(
                "pyproject.toml already exists",
                "The new-workspace wizard only creates pixi.toml. This directory already has pyproject.toml; choose another directory or open the existing manifest.",
                parent=self,
            )
            return
        name = path.name
        if not name:
            messagebox.showwarning("Invalid directory", "A workspace cannot be created directly in a disk root.", parent=self)
            return
        channels = [
            item.strip()
            for item in re.split(r"[,;\n]", self.channels_var.get())
            if item.strip()
        ]
        if not channels:
            messagebox.showwarning("No channels", "Enter at least one channel.", parent=self)
            return
        platforms = [name for name, var in self.platform_vars.items() if var.get()]
        if not platforms:
            messagebox.showwarning("No platforms", "Select at least one platform.", parent=self)
            return
        if path.exists():
            try:
                nonempty = any(path.iterdir())
            except OSError:
                nonempty = False
            if nonempty and not messagebox.askyesno(
                "Directory is not empty",
                "The directory already contains files. Pixi will add .gitignore, .gitattributes and pixi.toml without deleting existing files.\n\nContinue?",
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
        self.title("Run task: {}".format(task_name))
        self.transient(parent)
        self.resizable(True, False)
        self.result: Optional[str] = None

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Extra arguments", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text="Arguments are appended to pixi run; wrap paths containing spaces in double quotes.",
            style="MutedCard.TLabel",
            wraplength=560,
        ).pack(anchor="w", pady=(3, 8))
        self.entry = ttk.Entry(frame, width=68)
        self.entry.pack(fill="x")
        self.entry.insert(0, initial)
        self.entry.bind("<Return>", lambda _event: self._accept())
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(14, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(
            buttons, text="Run", style="Accent.TButton", command=self._accept
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
        self.title(i18n.t("Add Environment"))
        self.transient(parent)
        self.resizable(True, False)
        self.result: Optional[Dict[str, object]] = None
        self.existing_names = set(existing_names)
        self.features = [name for name in features if name != "default"]

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Environment name", style="CardTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(frame, textvariable=self.name_var, width=44)
        self.name_entry.grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(4, 2)
        )
        ttk.Label(
            frame,
            text="Names must be unique; default is implicit and cannot be used.",
            style="MutedCard.TLabel",
        ).grid(row=2, column=0, columnspan=2, sticky="w")

        ttk.Label(frame, text="Features", style="CardTitle.TLabel").grid(
            row=3, column=0, sticky="w", pady=(14, 4)
        )
        self.default_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            frame,
            text="Include default feature",
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
                text="This workspace has no other features.",
                style="MutedCard.TLabel",
            ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            frame,
            text="When default is disabled, at least one other feature must be selected.",
            style="MutedCard.TLabel",
            wraplength=620,
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(4, 0))

        ttk.Label(frame, text="Solve group (optional)", style="CardTitle.TLabel").grid(
            row=7, column=0, sticky="w", pady=(14, 4)
        )
        self.solve_group_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.solve_group_var, width=32).grid(
            row=8, column=0, sticky="w"
        )

        self.install_var = tk.BooleanVar(value=default_install)
        ttk.Checkbutton(
            frame,
            text="Install the environment after creation",
            variable=self.install_var,
        ).grid(row=9, column=0, columnspan=2, sticky="w", pady=(14, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(row=10, column=0, columnspan=2, sticky="e", pady=(18, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(
            buttons,
            text="Add Environment",
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
            messagebox.showwarning("Environment name", "Enter an environment name.", parent=self)
            return
        if name == "default":
            messagebox.showwarning(
                "Environment name", "default is implicit and cannot be used as a new environment name.", parent=self
            )
            return
        if name in self.existing_names:
            messagebox.showwarning(
                "Environment already exists", "Environment “{}” already exists.".format(name), parent=self
            )
            return
        if re.search(r"\s", name) or '"' in name or "'" in name:
            messagebox.showwarning(
                "Environment name",
                "The environment name cannot contain spaces, single quotes or double quotes.",
                parent=self,
            )
            return
        selected = [
            feature for feature, var in self.feature_vars.items() if var.get()
        ]
        if not self.default_var.get() and not selected:
            messagebox.showwarning(
                "Features",
                "When default is disabled, at least one other feature must be selected.",
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
        self.title(i18n.t("Delete Environment"))
        self.transient(parent)
        self.resizable(False, False)
        self.result: Optional[Dict[str, object]] = None
        self.name = name

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text="Delete environment “{}” from the manifest?".format(name),
            style="CardTitle.TLabel",
            wraplength=620,
        ).pack(anchor="w")
        ttk.Label(
            frame,
            text="This modifies pixi.toml / pyproject.toml but does not update the lock file automatically.",
            style="MutedCard.TLabel",
            wraplength=620,
        ).pack(anchor="w", pady=(4, 10))

        self.cleanup_var = tk.BooleanVar(value=False)
        cleanup = ttk.Checkbutton(
            frame,
            text="Also clean the installed environment directory (pixi clean)",
            variable=self.cleanup_var,
        )
        cleanup.pack(anchor="w")
        if not has_directory:
            cleanup.configure(state="disabled")
            ttk.Label(
                frame,
                text="This environment has no installed .pixi directory.",
                style="MutedCard.TLabel",
            ).pack(anchor="w", pady=(3, 0))

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(18, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(
            buttons,
            text="Delete Environment",
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
        terminal: str = "",
    ):
        super().__init__(parent)
        self.title("Settings")
        self.transient(parent)
        self.resizable(False, False)
        self.result: Optional[Dict[str, object]] = None
        self._history_count = history_count

        frame = ttk.Frame(self, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Pixi executable", style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        self.pixi_var = tk.StringVar(value=pixi_path)
        ttk.Entry(frame, textvariable=self.pixi_var, width=58).grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(4, 2)
        )
        ttk.Button(frame, text="Browse…", command=self._browse_pixi).grid(
            row=1, column=2, padx=(8, 0)
        )
        ttk.Label(
            frame,
            text="Leave blank to find Pixi on PATH; applies after refresh or restart.",
            style="Muted.TLabel",
        ).grid(row=2, column=0, columnspan=3, sticky="w")

        ttk.Label(frame, text="Theme", style="CardTitle.TLabel").grid(
            row=3, column=0, sticky="w", pady=(16, 4)
        )
        self.theme_var = tk.StringVar(
            value=i18n.t("Dark") if theme_name == "dark" else i18n.t("Light")
        )
        ttk.Combobox(
            frame,
            textvariable=self.theme_var,
            values=(i18n.t("Light"), i18n.t("Dark")),
            state="readonly",
            width=12,
        ).grid(row=4, column=0, sticky="w")

        ttk.Label(frame, text="Interface Language", style="CardTitle.TLabel").grid(
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
            text="Language changes take effect after restarting the application.",
            style="Muted.TLabel",
        ).grid(row=6, column=1, columnspan=2, sticky="w", padx=(12, 0))

        ttk.Label(frame, text="Terminal (optional)", style="CardTitle.TLabel").grid(
            row=7, column=0, sticky="w", pady=(16, 4)
        )
        self.terminal_var = tk.StringVar(value=terminal)
        ttk.Combobox(
            frame,
            textvariable=self.terminal_var,
            values=("", "powershell.exe", "pwsh.exe", "cmd.exe", "wt.exe"),
            state="normal",
            width=48,
        ).grid(row=8, column=0, columnspan=2, sticky="ew", pady=(4, 2))
        ttk.Button(frame, text="Browse…", command=self._browse_terminal).grid(
            row=8, column=2, padx=(8, 0)
        )
        ttk.Label(
            frame,
            text="Leave empty for PowerShell. You can enter powershell.exe, cmd.exe, wt.exe, a full path, or a custom template using {command}/{cmd}/{cwd}/{title}.",
            style="Muted.TLabel",
            wraplength=680,
        ).grid(row=9, column=0, columnspan=3, sticky="w")

        ttk.Label(frame, text="Console max lines", style="CardTitle.TLabel").grid(
            row=3, column=1, sticky="w", pady=(16, 4)
        )
        self.lines_var = tk.StringVar(value=str(console_max_lines))
        ttk.Spinbox(
            frame, from_=1000, to=200000, increment=1000, textvariable=self.lines_var, width=14
        ).grid(row=4, column=1, sticky="w", padx=(12, 0))

        action_frame = ttk.Frame(frame)
        action_frame.grid(row=10, column=0, columnspan=3, sticky="ew", pady=(20, 0))
        ttk.Button(
            action_frame,
            text="Clear Open History",
            command=self._clear_history,
        ).pack(side="left")
        ttk.Button(
            action_frame, text="Cancel", command=self.destroy
        ).pack(side="right")
        ttk.Button(
            action_frame,
            text="Save",
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
            title="Choose pixi executable",
            filetypes=[("Pixi", "pixi.exe"), ("Executable", "*.exe"), ("All files", "*.*")],
        )
        if path:
            self.pixi_var.set(path)

    def _browse_terminal(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title=i18n.t("Choose terminal program"),
            filetypes=[
                (i18n.t("Program"), "*.exe"),
                ("Windows Terminal", "wt.exe"),
                (i18n.t("All files"), "*.*"),
            ],
        )
        if path:
            self.terminal_var.set('"{}"'.format(path) if " " in path else path)

    def _clear_history(self) -> None:
        if messagebox.askyesno(
            "Clear History",
            "Clear the recent-environment list? Python program history will be kept.",
            parent=self,
        ):
            self._history_count = 0
            self._clear_requested = True

    def _accept(self) -> None:
        try:
            lines = int(self.lines_var.get())
        except ValueError:
            messagebox.showerror("Invalid settings", "Console max lines must be an integer.", parent=self)
            return
        lines = max(1000, min(200000, lines))
        language_code = "zh"
        for code in ("zh", "en", "ja"):
            if self.language_var.get() == i18n.language_display_name(code):
                language_code = code
                break
        self.result = {
            "pixi_path": self.pixi_var.get().strip(),
            "theme": "dark" if self.theme_var.get() == i18n.t("Dark") else "light",
            "console_max_lines": lines,
            "clear_history": bool(getattr(self, "_clear_requested", False)),
            "language": language_code,
            "terminal": self.terminal_var.get().strip(),
        }
        self.destroy()
