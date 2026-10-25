"""Run a Python script inside the selected Pixi environment."""

from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, Optional

from .. import i18n
from ..models import WorkspaceData


class PythonTab(ttk.Frame):
    def __init__(self, master, app, colors: Dict[str, str]):
        super().__init__(master, padding=(14, 12))
        self.app = app
        self.colors = colors
        self.workspace: Optional[WorkspaceData] = None
        self.env_name = ""
        self._auto_cwd = ""
        self._loading = False

        header = ttk.Frame(self)
        header.pack(fill="x")
        ttk.Label(header, text="Run Python", style="Title.TLabel").pack(side="left")
        self.headline_var = tk.StringVar(value="No environment")
        ttk.Label(
            header, textvariable=self.headline_var, style="Muted.TLabel"
        ).pack(side="left", padx=(10, 0), pady=(6, 0))
        self.base_hint_var = tk.StringVar(value="")
        self.base_hint = ttk.Label(
            self, textvariable=self.base_hint_var, style="Muted.TLabel"
        )

        form = ttk.LabelFrame(self, text="Program", padding=(12, 10))
        self.form = form
        form.pack(fill="x", pady=(12, 0))
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Script path", style="MutedCard.TLabel").grid(
            row=0, column=0, sticky="w", pady=3
        )
        self.script_var = tk.StringVar()
        self.script_entry = ttk.Entry(form, textvariable=self.script_var)
        self.script_entry.grid(row=0, column=1, sticky="ew", padx=(8, 6), pady=3)
        ttk.Button(form, text="Browse…", command=self._browse_script).grid(
            row=0, column=2, pady=3
        )
        ttk.Button(form, text="Open Folder", command=self._open_script_folder).grid(
            row=0, column=3, padx=(6, 0), pady=3
        )

        ttk.Label(form, text="Arguments", style="MutedCard.TLabel").grid(
            row=1, column=0, sticky="w", pady=3
        )
        self.args_var = tk.StringVar()
        self.args_entry = ttk.Entry(form, textvariable=self.args_var)
        self.args_entry.grid(
            row=1, column=1, columnspan=3, sticky="ew", padx=(8, 0), pady=3
        )
        ttk.Label(
            form,
            text="Use Windows command-line quoting; wrap paths containing spaces in double quotes.",
            style="MutedCard.TLabel",
        ).grid(row=2, column=1, columnspan=3, sticky="w", padx=(8, 0))

        ttk.Label(form, text="Working directory", style="MutedCard.TLabel").grid(
            row=3, column=0, sticky="w", pady=3
        )
        self.cwd_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.cwd_var).grid(
            row=3, column=1, sticky="ew", padx=(8, 6), pady=3
        )
        ttk.Button(form, text="Browse…", command=self._browse_cwd).grid(
            row=3, column=2, pady=3
        )
        ttk.Button(form, text="Use Script Folder", command=self._use_script_dir).grid(
            row=3, column=3, padx=(6, 0), pady=3
        )

        ttk.Label(form, text="Environment", style="MutedCard.TLabel").grid(
            row=4, column=0, sticky="w", pady=3
        )
        self.env_var = tk.StringVar(value="—")
        ttk.Label(form, textvariable=self.env_var, style="Card.TLabel").grid(
            row=4, column=1, columnspan=3, sticky="w", padx=(8, 0), pady=3
        )

        preview_frame = ttk.LabelFrame(self, text="Command Preview", padding=(10, 8))
        preview_frame.pack(fill="x", pady=(10, 0))
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

        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(12, 0))
        self.run_button = ttk.Button(
            actions,
            text="Run",
            style="Accent.TButton",
            command=lambda: self._run(terminal=False),
        )
        self.run_button.pack(side="left")
        self.terminal_button = ttk.Button(
            actions,
            text="Run in Terminal",
            command=lambda: self._run(terminal=True),
        )
        self.terminal_button.pack(side="left", padx=(7, 0))
        ttk.Button(
            actions,
            text="Clear Form",
            command=self._clear_form,
        ).pack(side="right")

        self.status_var = tk.StringVar(value="")
        self.status_label = ttk.Label(
            self, textvariable=self.status_var, style="Muted.TLabel", wraplength=900
        )
        self.status_label.pack(fill="x", pady=(10, 0))

        tip = ttk.Label(
            self,
            text="Tip: runs appear under “Python Programs” on the left with their saved arguments.",
            style="Muted.TLabel",
            wraplength=900,
        )
        tip.pack(fill="x", pady=(6, 0))

        for variable in (self.script_var, self.args_var, self.cwd_var):
            variable.trace_add("write", lambda *_: self._update_preview())
        self.apply_theme(colors)
        self._update_preview()

    def apply_theme(self, colors: Dict[str, str]) -> None:
        self.colors = colors
        self.preview.configure(
            background=colors["panel_alt"],
            foreground=colors["text"],
            insertbackground=colors["text"],
            selectbackground=colors["selected"],
        )

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
                "Base-dependency view: Python still runs in {}".format(env_name)
            )
            self.base_hint.pack(fill="x", pady=(6, 0), before=self.form)
        else:
            self.base_hint_var.set("")
            self.base_hint.pack_forget()
        if workspace:
            self.headline_var.set(
                "{} / {}".format(workspace.name or workspace.root.name, env_name)
            )
            self.env_var.set(env_name or "—")
        else:
            self.headline_var.set("No environment")
            self.env_var.set("—")
        self._update_preview()

    def focus_script(self) -> None:
        self.script_entry.focus_set()

    def load_run(self, run: dict) -> None:
        self._loading = True
        try:
            self.script_var.set(str(run.get("script") or ""))
            self.args_var.set(str(run.get("args") or ""))
            self.cwd_var.set(str(run.get("cwd") or ""))
            self._auto_cwd = self.cwd_var.get()
        finally:
            self._loading = False
        self._update_preview()

    def _clear_form(self) -> None:
        self.script_var.set("")
        self.args_var.set("")
        self.cwd_var.set("")
        self._auto_cwd = ""
        self._update_preview()

    def _browse_script(self) -> None:
        initial = self.script_var.get().strip()
        initial_dir = str(Path(initial).parent) if initial else str(Path.home())
        path = filedialog.askopenfilename(
            parent=self,
            title="Choose Python script",
            initialdir=initial_dir,
            filetypes=[("Python script", "*.py"), ("All files", "*.*")],
        )
        if path:
            self.script_var.set(path)
            current_cwd = self.cwd_var.get().strip()
            if not current_cwd or current_cwd == self._auto_cwd:
                self.cwd_var.set(str(Path(path).parent))
                self._auto_cwd = self.cwd_var.get()

    def _browse_cwd(self) -> None:
        initial = self.cwd_var.get().strip() or str(Path.home())
        path = filedialog.askdirectory(
            parent=self, title="Choose working directory", initialdir=initial
        )
        if path:
            self.cwd_var.set(path)
            self._auto_cwd = ""

    def _use_script_dir(self) -> None:
        script = self.script_var.get().strip()
        if script:
            self.cwd_var.set(str(Path(script).parent))
            self._auto_cwd = self.cwd_var.get()

    def _open_script_folder(self) -> None:
        script = self.script_var.get().strip()
        if not script:
            messagebox.showinfo("Open Folder", "Specify a script first.", parent=self)
            return
        self.app.open_path(str(Path(script).parent))

    def _update_preview(self) -> None:
        if self._loading:
            return
        if not self.workspace:
            self._set_preview(i18n.t("(Open an environment to see the command)"))
            return
        script = self.script_var.get().strip().strip('"')
        if not script:
            self._set_preview(i18n.t("(Choose a Python script to see the command)"))
            return
        try:
            argv = self.app.python_command_args(script, self.args_var.get())
            self._set_preview(self.app.pixi.command_line(argv))
        except Exception as exc:  # defensive: preview must never break typing
            self._set_preview("Failed to build command: {}".format(exc))

    def _set_preview(self, text: str) -> None:
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        self.preview.configure(state="disabled")

    def _validate(self) -> Optional[tuple]:
        if not self.workspace:
            messagebox.showinfo("Run Python", "Open an environment first.", parent=self)
            return None
        script_raw = self.script_var.get().strip().strip('"')
        if not script_raw:
            messagebox.showinfo("Run Python", "Choose or enter a Python script path.", parent=self)
            return None
        script = Path(os.path.expanduser(script_raw))
        if not script.is_absolute():
            base = Path(self.cwd_var.get().strip() or self.workspace.root)
            script = base / script
        try:
            script = script.resolve()
        except OSError:
            script = script.absolute()
        if not script.is_file():
            messagebox.showerror(
                "Script not found", "Script not found:\n{}".format(script), parent=self
            )
            return None
        cwd_raw = self.cwd_var.get().strip().strip('"')
        cwd = Path(os.path.expanduser(cwd_raw)) if cwd_raw else script.parent
        if not cwd.is_absolute():
            cwd = (self.workspace.root / cwd).resolve()
        if not cwd.is_dir():
            messagebox.showerror(
                "Working directory not found", "Directory not found:\n{}".format(cwd), parent=self
            )
            return None
        return script, cwd

    def _run(self, terminal: bool) -> None:
        validated = self._validate()
        if not validated:
            return
        script, cwd = validated
        self.app.run_python_program(
            script=script,
            args_text=self.args_var.get(),
            cwd=cwd,
            terminal=terminal,
        )

    def set_status(self, text: str, danger: bool = False) -> None:
        self.status_var.set(text)
        self.status_label.configure(style="Danger.TLabel" if danger else "Muted.TLabel")
