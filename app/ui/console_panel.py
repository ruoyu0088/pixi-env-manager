"""Tabbed output console: one independent output tab per job."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, Optional

from .. import i18n
from ..util import strip_ansi, truncate_text


class OutputView(ttk.Frame):
    """One output tab (a system log or a running job)."""

    def __init__(
        self,
        master,
        colors: Dict[str, str],
        mono_font,
        max_lines: int,
        title: str,
        job_id: Optional[int] = None,
        on_stop: Optional[Callable[[int], None]] = None,
        on_close: Optional[Callable[[int], None]] = None,
        running: bool = False,
        autoscroll_var: Optional[tk.BooleanVar] = None,
    ):
        super().__init__(master, padding=(0, 0))
        self.colors = colors
        self.mono_font = mono_font
        self.max_lines = max_lines
        self.job_id = job_id
        self.base_title = title
        self.on_stop = on_stop
        self.on_close = on_close
        self.running = running
        self.autoscroll_var = autoscroll_var

        header = ttk.Frame(self, style="Panel.TFrame", padding=(7, 4))
        header.pack(fill="x")
        self.status_var = tk.StringVar(
            value=i18n.t("运行中")
            if running
            else (i18n.t("系统消息") if job_id is None else i18n.t("完成"))
        )
        self.status_label = ttk.Label(
            header, textvariable=self.status_var, style="SmallCard.TLabel"
        )
        self.status_label.pack(side="left")
        self.meta_var = tk.StringVar(value="")
        ttk.Label(header, textvariable=self.meta_var, style="SmallCard.TLabel").pack(
            side="left", padx=(8, 0)
        )
        self.close_button = ttk.Button(
            header,
            text="关闭",
            style="Small.TButton",
            command=self._close,
            state="normal" if job_id is not None and not running else "disabled",
        )
        self.close_button.pack(side="right")
        ttk.Button(
            header, text="清空", style="Small.TButton", command=self.clear
        ).pack(side="right", padx=(4, 0))
        ttk.Button(
            header, text="复制", style="Small.TButton", command=self.copy
        ).pack(side="right", padx=(4, 0))
        self.stop_button = ttk.Button(
            header,
            text="停止",
            style="Small.TButton",
            command=self._stop,
            state="normal" if running else "disabled",
        )
        if job_id is not None:
            self.stop_button.pack(side="right", padx=(4, 0))

        body = ttk.Frame(self, style="Console.TFrame")
        body.pack(fill="both", expand=True)
        self.text = tk.Text(
            body,
            state="disabled",
            wrap="none",
            font=mono_font,
            padx=8,
            pady=5,
            borderwidth=0,
            highlightthickness=0,
            undo=False,
        )
        y_scroll = ttk.Scrollbar(body, orient="vertical", command=self.text.yview)
        x_scroll = ttk.Scrollbar(body, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        self.apply_colors(colors, mono_font)

    def apply_colors(self, colors: Dict[str, str], mono_font=None) -> None:
        self.colors = colors
        if mono_font is not None:
            self.mono_font = mono_font
        self.text.configure(
            background=colors["console_bg"],
            foreground=colors["console_fg"],
            insertbackground=colors["console_fg"],
            selectbackground=colors["selected"],
            selectforeground=colors["selected_text"],
            font=self.mono_font,
        )
        self.text.tag_configure(
            "command",
            foreground=colors["accent"],
            font=self.mono_font,
            spacing1=3,
        )
        self.text.tag_configure("error", foreground=colors["danger"])
        self.text.tag_configure("success", foreground=colors["success"])
        self.text.tag_configure("info", foreground=colors["console_muted"])
        self.text.tag_configure("warning", foreground=colors["warning"])
        self.text.tag_configure(
            "separator", foreground=colors["border"], spacing1=6
        )

    def _append_raw(self, text: str, tag: Optional[str] = None) -> None:
        if not text:
            return
        self.text.configure(state="normal")
        if tag:
            self.text.insert("end", text, tag)
        else:
            self.text.insert("end", text)
        self.text.configure(state="disabled")
        self._trim()
        if self.autoscroll_var is None or self.autoscroll_var.get():
            self.text.see("end")

    def append(self, text: str, tag: Optional[str] = None) -> None:
        text = strip_ansi(text)
        if not text.endswith("\n"):
            text += "\n"
        self._append_raw(text, tag)

    def _trim(self) -> None:
        try:
            end_line = int(self.text.index("end-1c").split(".")[0])
            if end_line > self.max_lines:
                remove = end_line - self.max_lines
                self.text.configure(state="normal")
                self.text.delete("1.0", "{}.0".format(remove + 1))
                self.text.configure(state="disabled")
        except (tk.TclError, ValueError):
            pass

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    def copy(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.text.get("1.0", "end-1c"))

    def start(self, command_line: str) -> None:
        self.running = True
        self.stop_button.configure(state="normal")
        self.close_button.configure(state="disabled")
        self.status_var.set(i18n.t("运行中"))
        self._append_raw("$ " + command_line + "\n", "command")

    def finish(
        self,
        returncode: Optional[int],
        elapsed: float,
        cancelled: bool = False,
    ) -> None:
        self.running = False
        self.stop_button.configure(state="disabled")
        self.close_button.configure(state="normal")
        if cancelled:
            self.status_var.set(i18n.t("已停止"))
            self._append_raw(
                i18n.t("[已停止] 用时 {:.1f}s\n", elapsed), "warning"
            )
        elif returncode == 0:
            self.status_var.set(i18n.t("完成"))
            self._append_raw(
                i18n.t("[完成] 用时 {:.1f}s\n", elapsed), "success"
            )
        else:
            self.status_var.set(i18n.t("失败（退出码 {}）", returncode))
            self._append_raw(
                i18n.t("[失败] 退出码 {}，用时 {:.1f}s\n", returncode, elapsed),
                "error",
            )
        self.meta_var.set(i18n.t("用时 {:.1f}s", elapsed))

    def _stop(self) -> None:
        if self.running and self.job_id is not None and self.on_stop:
            self.on_stop(self.job_id)

    def _close(self) -> None:
        if self.running or self.job_id is None:
            return
        if self.on_close:
            self.on_close(self.job_id)


class ConsolePanel(ttk.Frame):
    def __init__(
        self,
        master,
        colors: Dict[str, str],
        mono_font,
        max_lines: int = 50000,
        on_stop: Optional[Callable[[int], None]] = None,
        on_stop_all: Optional[Callable[[], None]] = None,
    ):
        super().__init__(master, style="Console.TFrame")
        self.colors = colors
        self.mono_font = mono_font
        self.max_lines = max_lines
        self.on_stop = on_stop
        self.on_stop_all = on_stop_all
        self.jobs: Dict[int, OutputView] = {}
        self._titles: Dict[str, int] = {}

        header = ttk.Frame(self, style="Panel.TFrame", padding=(9, 6))
        header.pack(fill="x")
        ttk.Label(header, text="输出", style="CardTitle.TLabel").pack(side="left")
        self.status_var = tk.StringVar(value="空闲")
        ttk.Label(
            header, textvariable=self.status_var, style="SmallCard.TLabel"
        ).pack(side="left", padx=(10, 0))
        self.autoscroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            header,
            text="自动滚动",
            variable=self.autoscroll_var,
            style="Card.TCheckbutton",
        ).pack(side="right", padx=(6, 0))
        self.stop_all_button = ttk.Button(
            header,
            text="全部停止",
            style="Small.TButton",
            command=self._stop_all,
            state="disabled",
        )
        self.stop_all_button.pack(side="right", padx=(6, 0))
        ttk.Button(
            header,
            text="关闭已完成",
            style="Small.TButton",
            command=self.close_completed,
        ).pack(side="right", padx=(6, 0))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)
        self.system_view = OutputView(
            self.notebook,
            colors=colors,
            mono_font=mono_font,
            max_lines=max_lines,
            title="系统",
            autoscroll_var=self.autoscroll_var,
        )
        self.notebook.add(self.system_view, text="系统")

    def apply_colors(self, colors: Dict[str, str], mono_font=None) -> None:
        self.colors = colors
        if mono_font is not None:
            self.mono_font = mono_font
        self.system_view.apply_colors(colors, mono_font)
        for view in self.jobs.values():
            view.apply_colors(colors, mono_font)

    def _update_status(self) -> None:
        running = sum(1 for view in self.jobs.values() if view.running)
        self.status_var.set(
            i18n.t("运行中 {} 个任务", running) if running else i18n.t("空闲")
        )
        self.stop_all_button.configure(state="normal" if running else "disabled")
        self.notebook.tab(self.system_view, text=i18n.t("系统"))

    def _unique_title(self, title: str) -> str:
        base = truncate_text(title, 34) or "任务"
        index = self._titles.get(base, 0) + 1
        self._titles[base] = index
        return base if index == 1 else "{} ({})".format(base, index)

    def start_job(self, job, command_line: str) -> OutputView:
        title = self._unique_title(i18n.translate_dynamic(job.title))
        view = OutputView(
            self.notebook,
            colors=self.colors,
            mono_font=self.mono_font,
            max_lines=self.max_lines,
            title=title,
            job_id=job.job_id,
            on_stop=self.on_stop,
            on_close=self.close_job,
            running=True,
            autoscroll_var=self.autoscroll_var,
        )
        self.jobs[job.job_id] = view
        self.notebook.add(view, text="● " + title)
        self.notebook.select(view)
        view.start(command_line)
        self._update_status()
        return view

    def append(self, job_id: int, text: str) -> None:
        view = self.jobs.get(job_id)
        if view is not None:
            view.append(text)

    def append_system(self, text: str, tag: str = "info") -> None:
        self.system_view.append(i18n.translate_dynamic(text), tag)

    def finish_job(
        self,
        job_id: int,
        returncode: Optional[int],
        elapsed: float,
        cancelled: bool = False,
    ) -> None:
        view = self.jobs.get(job_id)
        if view is None:
            return
        view.finish(returncode, elapsed, cancelled)
        if cancelled:
            mark = "■"
        elif returncode == 0:
            mark = "✓"
        else:
            mark = "✗"
        self.notebook.tab(view, text=mark + " " + view.base_title)
        self._update_status()

    def close_job(self, job_id: int) -> None:
        view = self.jobs.get(job_id)
        if view is None or view.running:
            return
        self.notebook.forget(view)
        view.destroy()
        self.jobs.pop(job_id, None)
        self._update_status()

    def close_completed(self) -> None:
        for job_id in list(self.jobs):
            view = self.jobs[job_id]
            if not view.running:
                self.close_job(job_id)

    def _stop_all(self) -> None:
        if self.on_stop_all and self.jobs:
            self.on_stop_all()

    def clear(self) -> None:
        current = self.notebook.select()
        if not current:
            return
        for view in [self.system_view] + list(self.jobs.values()):
            if str(view) == current:
                view.clear()
                return

    def copy_all(self) -> None:
        current = self.notebook.select()
        if not current:
            return
        for view in [self.system_view] + list(self.jobs.values()):
            if str(view) == current:
                view.copy()
                return

    def set_max_lines(self, value: int) -> None:
        self.max_lines = max(1000, int(value))
        self.system_view.max_lines = self.max_lines
        for view in self.jobs.values():
            view.max_lines = self.max_lines
