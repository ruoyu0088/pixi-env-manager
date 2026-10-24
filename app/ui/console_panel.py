"""Shared output console."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, Optional

from ..util import strip_ansi


class ConsolePanel(ttk.Frame):
    def __init__(
        self,
        master,
        colors: Dict[str, str],
        mono_font,
        max_lines: int = 50000,
        on_stop: Optional[Callable[[], None]] = None,
    ):
        super().__init__(master, style="Console.TFrame")
        self.colors = colors
        self.mono_font = mono_font
        self.max_lines = max_lines
        self.on_stop = on_stop
        self._running = False

        header = ttk.Frame(self, style="Panel.TFrame", padding=(9, 6))
        header.pack(fill="x")
        ttk.Label(header, text="输出", style="CardTitle.TLabel").pack(side="left")
        self.status_var = tk.StringVar(value="就绪")
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
        ttk.Button(
            header, text="清空", style="Small.TButton", command=self.clear
        ).pack(side="right", padx=(6, 0))
        ttk.Button(
            header, text="复制", style="Small.TButton", command=self.copy_all
        ).pack(side="right", padx=(6, 0))
        self.stop_button = ttk.Button(
            header,
            text="停止",
            style="Small.TButton",
            command=self._stop,
            state="disabled",
        )
        self.stop_button.pack(side="right", padx=(6, 0))

        body = ttk.Frame(self, style="Console.TFrame")
        body.pack(fill="both", expand=True)
        self.text = tk.Text(
            body,
            state="disabled",
            wrap="none",
            font=mono_font,
            padx=9,
            pady=7,
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

    # ------------------------------------------------------------------
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
            spacing1=4,
        )
        self.text.tag_configure("error", foreground=colors["danger"])
        self.text.tag_configure("success", foreground=colors["success"])
        self.text.tag_configure("info", foreground=colors["console_muted"])
        self.text.tag_configure("warning", foreground=colors["warning"])
        self.text.tag_configure(
            "separator", foreground=colors["border"], spacing1=8
        )

    # ------------------------------------------------------------------
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
        if self.autoscroll_var.get():
            self.text.see("end")

    def append(self, text: str, tag: Optional[str] = None) -> None:
        text = strip_ansi(text)
        if not text.endswith("\n"):
            text += "\n"
        self._append_raw(text, tag)

    def append_system(self, text: str, tag: str = "info") -> None:
        self.append(text, tag)

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

    def start_job(self, title: str, command_line: str) -> None:
        self._running = True
        self.status_var.set("运行中：{}".format(title))
        self.stop_button.configure(state="normal")
        self._append_raw("\n" + "─" * 78 + "\n", "separator")
        self._append_raw("$ " + command_line + "\n", "command")

    def finish_job(
        self,
        returncode: Optional[int],
        elapsed: float,
        cancelled: bool = False,
    ) -> None:
        self._running = False
        self.stop_button.configure(state="disabled")
        if cancelled:
            self.status_var.set("已停止")
            self._append_raw(
                "[已停止] 用时 {:.1f}s\n".format(elapsed),
                "warning",
            )
            return
        if returncode == 0:
            self.status_var.set("完成")
            self._append_raw(
                "[完成] 用时 {:.1f}s\n".format(elapsed),
                "success",
            )
        else:
            self.status_var.set("失败，退出码 {}".format(returncode))
            self._append_raw(
                "[失败] 退出码 {}，用时 {:.1f}s\n".format(returncode, elapsed),
                "error",
            )

    def set_ready(self, text: str = "就绪") -> None:
        if not self._running:
            self.status_var.set(text)

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        self.status_var.set("就绪")

    def copy_all(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.text.get("1.0", "end-1c"))

    def _stop(self) -> None:
        if self.on_stop:
            self.on_stop()
