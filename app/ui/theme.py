"""Tk/ttk theme handling using only the standard library."""

from __future__ import annotations

import ctypes
import os
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass
from tkinter import ttk
from typing import Dict


LIGHT: Dict[str, str] = {
    "name": "light",
    "bg": "#f3f5f8",
    "panel": "#ffffff",
    "panel_alt": "#f8fafc",
    "border": "#d7dce3",
    "text": "#1f2937",
    "muted": "#6b7280",
    "accent": "#2563eb",
    "accent_hover": "#1d4ed8",
    "accent_text": "#ffffff",
    "selected": "#dbeafe",
    "selected_text": "#153e75",
    "success": "#15803d",
    "success_bg": "#eaf7ef",
    "warning": "#b45309",
    "warning_bg": "#fff7e6",
    "danger": "#b91c1c",
    "danger_bg": "#fdecec",
    "string": "#0f766e",
    "number": "#b45309",
    "boolean": "#7c3aed",
    "comment": "#7b8794",
    "table": "#1d4ed8",
    "key": "#0f4c81",
    "date": "#a21caf",
    "current_line": "#eef4ff",
    "console_bg": "#151a21",
    "console_fg": "#d7dde7",
    "console_muted": "#8b98a8",
}

DARK: Dict[str, str] = {
    "name": "dark",
    "bg": "#1b1d21",
    "panel": "#25282e",
    "panel_alt": "#202329",
    "border": "#3a3f47",
    "text": "#e6e9ee",
    "muted": "#9aa4b2",
    "accent": "#3b82f6",
    "accent_hover": "#60a5fa",
    "accent_text": "#ffffff",
    "selected": "#1e3a5f",
    "selected_text": "#dbeafe",
    "success": "#4ade80",
    "success_bg": "#163225",
    "warning": "#fbbf24",
    "warning_bg": "#3a2c12",
    "danger": "#f87171",
    "danger_bg": "#3b1d1d",
    "string": "#5eead4",
    "number": "#fdba74",
    "boolean": "#c4b5fd",
    "comment": "#8b98a8",
    "table": "#93c5fd",
    "key": "#7dd3fc",
    "date": "#f0abfc",
    "current_line": "#2b3442",
    "console_bg": "#121418",
    "console_fg": "#d7dde7",
    "console_muted": "#8b98a8",
}


def palette_for(name: str) -> Dict[str, str]:
    return DARK if (name or "").lower() == "dark" else LIGHT


def enable_dpi_awareness() -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


@dataclass
class Fonts:
    ui: tkfont.Font
    ui_bold: tkfont.Font
    small: tkfont.Font
    small_bold: tkfont.Font
    title: tkfont.Font
    mono: tkfont.Font
    mono_bold: tkfont.Font
    mono_small: tkfont.Font


class ThemeManager:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.name = "light"
        self.colors = dict(LIGHT)
        self.fonts = self._make_fonts()

    def _make_fonts(self) -> Fonts:
        families = set(tkfont.families(self.root))
        ui_family = "Segoe UI" if "Segoe UI" in families else "TkDefaultFont"
        if "Microsoft YaHei UI" in families:
            # Segoe UI falls back to a CJK font on Windows, but YaHei has a
            # slightly more consistent look for mixed Chinese/English labels.
            ui_family = "Microsoft YaHei UI"
        mono_candidates = (
            "Cascadia Mono",
            "Cascadia Code",
            "Consolas",
            "JetBrains Mono",
            "Courier New",
        )
        mono_family = next(
            (family for family in mono_candidates if family in families), "TkFixedFont"
        )
        return Fonts(
            ui=tkfont.Font(root=self.root, family=ui_family, size=10),
            ui_bold=tkfont.Font(root=self.root, family=ui_family, size=10, weight="bold"),
            small=tkfont.Font(root=self.root, family=ui_family, size=9),
            small_bold=tkfont.Font(root=self.root, family=ui_family, size=9, weight="bold"),
            title=tkfont.Font(root=self.root, family=ui_family, size=16, weight="bold"),
            mono=tkfont.Font(root=self.root, family=mono_family, size=10),
            mono_bold=tkfont.Font(
                root=self.root, family=mono_family, size=10, weight="bold"
            ),
            mono_small=tkfont.Font(root=self.root, family=mono_family, size=9),
        )

    def apply(self, name: str) -> None:
        self.name = "dark" if (name or "").lower() == "dark" else "light"
        self.colors = palette_for(self.name)
        colors = self.colors
        root = self.root
        root.configure(bg=colors["bg"])
        root.option_add("*Font", self.fonts.ui)
        root.option_add("*Menu.background", colors["panel"])
        root.option_add("*Menu.foreground", colors["text"])
        root.option_add("*Menu.activeBackground", colors["selected"])
        root.option_add("*Menu.activeForeground", colors["selected_text"])
        root.option_add("*Menu.selectColor", colors["accent"])
        root.option_add("*Text.selectBackground", colors["selected"])
        root.option_add("*Text.selectForeground", colors["selected_text"])
        root.option_add("*TCombobox*Listbox.background", colors["panel"])
        root.option_add("*TCombobox*Listbox.foreground", colors["text"])
        root.option_add("*TCombobox*Listbox.selectBackground", colors["selected"])
        root.option_add("*TCombobox*Listbox.selectForeground", colors["selected_text"])

        style = ttk.Style(root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", background=colors["bg"], foreground=colors["text"])
        style.configure("TFrame", background=colors["bg"])
        style.configure("Card.TFrame", background=colors["panel"])
        style.configure("Panel.TFrame", background=colors["panel"])
        style.configure("Sidebar.TFrame", background=colors["panel"])
        style.configure("Topbar.TFrame", background=colors["panel"])
        style.configure("Console.TFrame", background=colors["console_bg"])
        style.configure("Row.TFrame", background=colors["panel_alt"])
        style.configure("TLabel", background=colors["bg"], foreground=colors["text"])
        style.configure(
            "Card.TLabel", background=colors["panel"], foreground=colors["text"]
        )
        style.configure(
            "Muted.TLabel", background=colors["bg"], foreground=colors["muted"]
        )
        style.configure(
            "MutedCard.TLabel", background=colors["panel"], foreground=colors["muted"]
        )
        style.configure(
            "Small.TLabel", background=colors["bg"], foreground=colors["muted"],
            font=self.fonts.small,
        )
        style.configure(
            "SmallCard.TLabel",
            background=colors["panel"],
            foreground=colors["muted"],
            font=self.fonts.small,
        )
        style.configure(
            "Title.TLabel",
            background=colors["bg"],
            foreground=colors["text"],
            font=self.fonts.title,
        )
        style.configure(
            "CardTitle.TLabel",
            background=colors["panel"],
            foreground=colors["text"],
            font=self.fonts.ui_bold,
        )
        style.configure(
            "Section.TLabel",
            background=colors["panel"],
            foreground=colors["text"],
            font=self.fonts.ui_bold,
        )
        style.configure(
            "Accent.TLabel",
            background=colors["panel"],
            foreground=colors["accent"],
            font=self.fonts.small_bold,
        )
        style.configure(
            "Success.TLabel",
            background=colors["bg"],
            foreground=colors["success"],
        )
        style.configure(
            "Warning.TLabel",
            background=colors["bg"],
            foreground=colors["warning"],
        )
        style.configure(
            "Danger.TLabel",
            background=colors["bg"],
            foreground=colors["danger"],
        )
        style.configure(
            "RowTitle.TLabel",
            background=colors["panel_alt"],
            foreground=colors["text"],
            font=self.fonts.ui_bold,
        )
        style.configure(
            "RowMuted.TLabel",
            background=colors["panel_alt"],
            foreground=colors["muted"],
            font=self.fonts.small,
        )
        style.configure(
            "RowDanger.TLabel",
            background=colors["panel_alt"],
            foreground=colors["danger"],
            font=self.fonts.small,
        )
        style.configure(
            "RowAccent.TLabel",
            background=colors["panel_alt"],
            foreground=colors["accent"],
            font=self.fonts.small,
        )
        style.configure(
            "Status.TLabel",
            background=colors["panel"],
            foreground=colors["muted"],
            font=self.fonts.small,
        )
        style.configure(
            "StatusDanger.TLabel",
            background=colors["panel"],
            foreground=colors["danger"],
            font=self.fonts.small,
        )

        style.configure(
            "TButton",
            background=colors["panel_alt"],
            foreground=colors["text"],
            bordercolor=colors["border"],
            lightcolor=colors["border"],
            darkcolor=colors["border"],
            focuscolor=colors["accent"],
            padding=(9, 5),
            relief="flat",
        )
        style.map(
            "TButton",
            background=[("active", colors["selected"]), ("disabled", colors["panel_alt"])],
            foreground=[("disabled", colors["muted"])],
        )
        style.configure(
            "Accent.TButton",
            background=colors["accent"],
            foreground=colors["accent_text"],
            bordercolor=colors["accent"],
            lightcolor=colors["accent"],
            darkcolor=colors["accent"],
            padding=(11, 6),
        )
        style.map(
            "Accent.TButton",
            background=[
                ("active", colors["accent_hover"]),
                ("disabled", colors["border"]),
            ],
            foreground=[("disabled", colors["muted"])],
        )
        style.configure(
            "Play.TButton",
            background=colors["accent"],
            foreground=colors["accent_text"],
            padding=(5, 1),
            font=self.fonts.small_bold,
        )
        style.map(
            "Play.TButton",
            background=[("active", colors["accent_hover"])],
        )
        style.configure(
            "Small.TButton",
            padding=(5, 2),
            font=self.fonts.small,
        )
        style.configure(
            "Danger.TButton",
            background=colors["danger"],
            foreground="#ffffff",
            padding=(9, 5),
        )
        style.map("Danger.TButton", background=[("active", colors["danger"])])

        style.configure(
            "TNotebook",
            background=colors["bg"],
            borderwidth=0,
            tabmargins=(0, 4, 0, 0),
        )
        style.configure(
            "TNotebook.Tab",
            background=colors["bg"],
            foreground=colors["muted"],
            padding=(13, 7),
            borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", colors["panel"])],
            foreground=[("selected", colors["accent"])],
        )

        style.configure(
            "Treeview",
            background=colors["panel"],
            fieldbackground=colors["panel"],
            foreground=colors["text"],
            bordercolor=colors["border"],
            lightcolor=colors["border"],
            darkcolor=colors["border"],
            rowheight=26,
            borderwidth=0,
        )
        style.map(
            "Treeview",
            background=[("selected", colors["selected"])],
            foreground=[("selected", colors["selected_text"])],
        )
        style.configure(
            "Treeview.Heading",
            background=colors["panel_alt"],
            foreground=colors["muted"],
            borderwidth=0,
            relief="flat",
            padding=(7, 6),
            font=self.fonts.small_bold,
        )
        style.map("Treeview.Heading", background=[("active", colors["selected"])])

        style.configure(
            "TLabelframe",
            background=colors["panel"],
            bordercolor=colors["border"],
            lightcolor=colors["border"],
            darkcolor=colors["border"],
            borderwidth=1,
        )
        style.configure(
            "TLabelframe.Label",
            background=colors["panel"],
            foreground=colors["muted"],
            font=self.fonts.small_bold,
        )
        style.configure(
            "TEntry",
            fieldbackground=colors["panel"],
            foreground=colors["text"],
            insertcolor=colors["text"],
            bordercolor=colors["border"],
            lightcolor=colors["border"],
            darkcolor=colors["border"],
            padding=(5, 4),
        )
        style.map(
            "TEntry",
            bordercolor=[("focus", colors["accent"])],
            lightcolor=[("focus", colors["accent"])],
        )
        style.configure(
            "TCombobox",
            fieldbackground=colors["panel"],
            background=colors["panel_alt"],
            foreground=colors["text"],
            arrowcolor=colors["muted"],
            bordercolor=colors["border"],
            lightcolor=colors["border"],
            darkcolor=colors["border"],
            padding=(5, 4),
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", colors["panel"])],
            foreground=[("readonly", colors["text"])],
            bordercolor=[("focus", colors["accent"])],
        )
        style.configure(
            "TCheckbutton",
            background=colors["bg"],
            foreground=colors["text"],
            indicatorcolor=colors["panel"],
        )
        style.map(
            "TCheckbutton",
            background=[("active", colors["bg"])],
            indicatorcolor=[("selected", colors["accent"])],
        )
        style.configure(
            "TRadiobutton",
            background=colors["bg"],
            foreground=colors["text"],
            indicatorcolor=colors["panel"],
        )
        style.map(
            "TRadiobutton",
            background=[("active", colors["bg"])],
            indicatorcolor=[("selected", colors["accent"])],
        )
        style.configure(
            "Card.TCheckbutton",
            background=colors["panel"],
            foreground=colors["text"],
        )
        style.configure(
            "TScrollbar",
            background=colors["panel_alt"],
            troughcolor=colors["bg"],
            bordercolor=colors["bg"],
            arrowcolor=colors["muted"],
        )
        style.map("TScrollbar", background=[("active", colors["border"])])
        style.configure("TPanedwindow", background=colors["bg"])
        style.configure("TSeparator", background=colors["border"])
        style.configure(
            "Horizontal.TProgressbar",
            background=colors["accent"],
            troughcolor=colors["panel_alt"],
            bordercolor=colors["border"],
        )
        style.configure(
            "TMenubutton",
            background=colors["panel_alt"],
            foreground=colors["text"],
            padding=(8, 4),
        )

    def style_menu(self, menu: tk.Menu) -> None:
        colors = self.colors
        menu.configure(
            background=colors["panel"],
            foreground=colors["text"],
            activebackground=colors["selected"],
            activeforeground=colors["selected_text"],
            selectcolor=colors["accent"],
            borderwidth=0,
        )

    def style_text(self, widget: tk.Text, console: bool = False) -> None:
        colors = self.colors
        if console:
            background = colors["console_bg"]
            foreground = colors["console_fg"]
        else:
            background = colors["panel"]
            foreground = colors["text"]
        widget.configure(
            background=background,
            foreground=foreground,
            insertbackground=foreground,
            selectbackground=colors["selected"],
            selectforeground=colors["selected_text"],
            highlightthickness=0,
            borderwidth=0,
            relief="flat",
        )
