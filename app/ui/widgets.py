"""Reusable Tk widgets and small UI helpers."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, Optional


class ScrollableFrame(ttk.Frame):
    """A vertically scrollable frame.

    Tk has no native scrollable frame; a Canvas with an embedded frame is the
    standard-library solution.
    """

    def __init__(self, master, style: str = "TFrame", **kwargs):
        super().__init__(master, **kwargs)
        self.canvas = tk.Canvas(
            self,
            highlightthickness=0,
            borderwidth=0,
            background="#ffffff",
        )
        self.scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview
        )
        self.inner = ttk.Frame(self.canvas, style=style)
        self.window_id = self.canvas.create_window(
            (0, 0), window=self.inner, anchor="nw"
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel, add="+")

    def _on_inner_configure(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        self.canvas.itemconfigure(self.window_id, width=event.width)

    def _on_mousewheel(self, event) -> None:
        try:
            x, y = self.winfo_pointerxy()
            target = self.winfo_containing(x, y)
            if target is None:
                return
            widget = target
            while widget is not None:
                if widget is self:
                    break
                widget = getattr(widget, "master", None)
            if widget is not self:
                return
            delta = int(-1 * (event.delta / 120)) if event.delta else 0
            if delta:
                self.canvas.yview_scroll(delta, "units")
        except (tk.TclError, ValueError):
            pass

    def set_style(self, style: str) -> None:
        self.inner.configure(style=style)

    def set_background(self, color: str) -> None:
        self.canvas.configure(background=color)


class Tooltip:
    def __init__(self, widget: tk.Widget, text: str, delay: int = 500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self._after_id: Optional[str] = None
        self._window: Optional[tk.Toplevel] = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None) -> None:
        self.cancel()
        if not self.text:
            return
        self._after_id = self.widget.after(self.delay, self._show)

    def cancel(self) -> None:
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _show(self) -> None:
        if self._window is not None or not self.text:
            return
        x = self.widget.winfo_rootx() + 14
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        window = tk.Toplevel(self.widget)
        window.wm_overrideredirect(True)
        window.attributes("-topmost", True)
        label = tk.Label(
            window,
            text=self.text,
            justify="left",
            background="#ffffe0",
            foreground="#222222",
            relief="solid",
            borderwidth=1,
            wraplength=520,
            padx=6,
            pady=4,
        )
        label.pack()
        window.wm_geometry("+{}+{}".format(x, y))
        self._window = window

    def _hide(self, _event=None) -> None:
        self.cancel()
        if self._window is not None:
            try:
                self._window.destroy()
            except tk.TclError:
                pass
            self._window = None


def clear_children(widget: tk.Widget) -> None:
    for child in widget.winfo_children():
        child.destroy()


def open_in_explorer(path: str) -> None:
    if not path:
        return
    path = os.path.abspath(path)
    if os.name == "nt":
        import subprocess

        if os.path.isfile(path):
            subprocess.Popen(
                ["explorer.exe", "/select,", path],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        elif os.path.isdir(path):
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            parent = os.path.dirname(path)
            if os.path.isdir(parent):
                os.startfile(parent)  # type: ignore[attr-defined]
    else:
        import subprocess

        subprocess.Popen(["xdg-open", os.path.dirname(path) or path])


def copy_text(widget: tk.Misc, text: str) -> None:
    widget.clipboard_clear()
    widget.clipboard_append(text)
    widget.update_idletasks()


def section_title(
    master,
    text: str,
    count: int = 0,
    style: str = "Section.TLabel",
) -> ttk.Frame:
    frame = ttk.Frame(master, style="Card.TFrame")
    label = ttk.Label(frame, text=text, style=style)
    label.pack(side="left")
    count_label = ttk.Label(frame, text=str(count), style="SmallCard.TLabel")
    count_label.pack(side="left", padx=(7, 0))
    # The caller may want to update the count label; expose it dynamically.
    frame.count_label = count_label  # type: ignore[attr-defined]
    return frame
