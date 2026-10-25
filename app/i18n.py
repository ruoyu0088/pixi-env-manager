"""Runtime translation layer with English source strings and JSON catalogs.

The Python and Tkinter code uses English UI strings as the source language.
Translations live in ``locales/zh.json`` and ``locales/ja.json`` and use those
English strings as keys.  Missing keys fall back to the English source.
"""

from __future__ import annotations

import json
import re
import string
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Dict, Iterable, List, Optional, Tuple

LANGUAGES: Dict[str, str] = {
    "zh": "中文",
    "en": "English",
    "ja": "日本語",
}

_LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"
_CATALOG_CACHE: Dict[str, Dict[str, str]] = {}
_CURRENT = "zh"


def _load_catalog(code: str) -> Dict[str, str]:
    if code in _CATALOG_CACHE:
        return _CATALOG_CACHE[code]
    if code not in ("zh", "ja"):
        _CATALOG_CACHE[code] = {}
        return _CATALOG_CACHE[code]
    path = _LOCALES_DIR / "{}.json".format(code)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    catalog = {
        str(key): str(value)
        for key, value in payload.items()
        if isinstance(key, str) and isinstance(value, str)
    }
    _CATALOG_CACHE[code] = catalog
    return catalog


def reload_catalogs() -> None:
    """Reload JSON files from disk (useful for development and the Web UI)."""
    _CATALOG_CACHE.clear()
    _clear_cache()


def current_language() -> str:
    return _CURRENT


def set_language(code: str) -> None:
    global _CURRENT
    code = (code or "zh").lower()
    _CURRENT = code if code in LANGUAGES else "zh"
    _clear_cache()


def language_display_name(code: str) -> str:
    return LANGUAGES.get(code, code)


def catalog_for(code: str) -> Dict[str, str]:
    """Return the JSON catalog for a language (empty for English)."""
    if code == "en":
        return {}
    return dict(_load_catalog(code))


def translate_for(text: str, code: str) -> str:
    """Translate without changing the process-wide current language."""
    if not text or code == "en":
        return text
    catalog = _load_catalog(code)
    return catalog.get(text, text)


def _catalog() -> Dict[str, str]:
    if _CURRENT == "en":
        return {}
    return _load_catalog(_CURRENT)


def _lookup(text: str) -> Optional[str]:
    catalog = _catalog()
    return catalog.get(text)


def _format_template(template: str, values: Iterable[str]) -> str:
    values_iter = iter(values)
    pieces: List[str] = []
    try:
        parsed = string.Formatter().parse(template)
    except ValueError:
        return template
    for literal, field_name, _format_spec, _conversion in parsed:
        pieces.append(literal)
        if field_name is not None:
            try:
                pieces.append(next(values_iter))
            except StopIteration:
                pieces.append("")
    return "".join(pieces)


_TEMPLATE_CACHE: List[Tuple[str, re.Pattern, str]] = []
_PREFIX_CACHE: List[Tuple[str, str]] = []
_CACHE_LANG: Optional[str] = None


def _clear_cache() -> None:
    global _CACHE_LANG
    _TEMPLATE_CACHE.clear()
    _PREFIX_CACHE.clear()
    _CACHE_LANG = None


def _build_cache() -> None:
    global _CACHE_LANG
    if _CACHE_LANG == _CURRENT:
        return
    _TEMPLATE_CACHE.clear()
    _PREFIX_CACHE.clear()
    for source, translated in _catalog().items():
        if "{" in source:
            try:
                parsed = list(string.Formatter().parse(source))
            except ValueError:
                continue
            pattern_parts: List[str] = ["^"]
            for literal, field_name, _spec, _conversion in parsed:
                pattern_parts.append(re.escape(literal))
                if field_name is not None:
                    pattern_parts.append("(.*?)")
            pattern_parts.append("$")
            try:
                regex = re.compile("".join(pattern_parts), re.DOTALL)
            except re.error:
                continue
            _TEMPLATE_CACHE.append((source, regex, translated))
        elif source.endswith(("：", ":", "： ", ": ", " ", "…")):
            _PREFIX_CACHE.append((source, translated))
    _TEMPLATE_CACHE.sort(key=lambda item: len(item[0]), reverse=True)
    _PREFIX_CACHE.sort(key=lambda item: len(item[0]), reverse=True)
    _CACHE_LANG = _CURRENT


def translate_dynamic(text: str) -> str:
    if not text or _CURRENT == "en":
        return text
    _build_cache()
    direct = _lookup(text)
    if direct is not None:
        return direct
    if text.startswith("⚠ "):
        return "⚠ " + translate_dynamic(text[2:])
    for _source, regex, translated in _TEMPLATE_CACHE:
        match = regex.match(text)
        if match:
            return _format_template(translated, match.groups())
    for source, translated in _PREFIX_CACHE:
        if text.startswith(source):
            return translated + text[len(source) :]
    return text


def t(text: str, *args: Any, **kwargs: Any) -> str:
    translated = translate_dynamic(text)
    if args or kwargs:
        try:
            return translated.format(*args, **kwargs)
        except (KeyError, IndexError, ValueError):
            return translated
    return translated


def localize_widget_tree(widget: tk.Misc) -> None:
    if _CURRENT == "en":
        return
    _localize(widget)


def _localize(widget: tk.Misc) -> None:
    try:
        if isinstance(widget, tk.Menu):
            _localize_menu(widget)
        elif isinstance(widget, ttk.Notebook):
            for tab_id in widget.tabs():
                try:
                    text = widget.tab(tab_id, "text")
                    translated = translate_dynamic(str(text))
                    if translated != text:
                        widget.tab(tab_id, text=translated)
                except tk.TclError:
                    pass
        elif isinstance(widget, ttk.Treeview):
            for column in widget["columns"]:
                try:
                    text = widget.heading(column, "text")
                    translated = translate_dynamic(str(text))
                    if translated != text:
                        widget.heading(column, text=translated)
                except tk.TclError:
                    pass
        elif isinstance(widget, (tk.Toplevel, tk.Tk)):
            try:
                title = widget.title()
                translated = translate_dynamic(title)
                if translated != title:
                    widget.title(translated)
            except tk.TclError:
                pass
    except tk.TclError:
        pass

    if not isinstance(
        widget,
        (tk.Text, tk.Entry, ttk.Entry, ttk.Combobox, ttk.Spinbox, tk.Listbox),
    ):
        try:
            keys = widget.keys()
        except (tk.TclError, AttributeError):
            keys = []
        if "text" in keys:
            try:
                text = widget.cget("text")
                translated = translate_dynamic(str(text))
                if translated != text:
                    widget.configure(text=translated)
            except tk.TclError:
                pass
        if "textvariable" in keys and not isinstance(widget, ttk.Treeview):
            try:
                var_name = widget.cget("textvariable")
                if var_name:
                    value = widget.getvar(var_name)
                    if value is not None:
                        translated = translate_dynamic(str(value))
                        if translated != str(value):
                            widget.setvar(var_name, translated)
            except tk.TclError:
                pass

    try:
        for child in widget.winfo_children():
            _localize(child)
    except tk.TclError:
        pass


def _localize_menu(menu: tk.Menu) -> None:
    try:
        end = menu.index("end")
    except tk.TclError:
        return
    if end is None:
        return
    for index in range(end + 1):
        try:
            label = menu.entrycget(index, "label")
        except tk.TclError:
            continue
        translated = translate_dynamic(str(label))
        if translated != label:
            try:
                menu.entryconfigure(index, label=translated)
            except tk.TclError:
                pass


def localize_menu(menu: tk.Menu) -> None:
    if _CURRENT != "en":
        _localize_menu(menu)


def install_messagebox_translation() -> None:
    """Translate standard message-box titles/messages without touching callers."""
    if getattr(messagebox, "_pixi_i18n_installed", False):
        return
    originals = {
        "showinfo": messagebox.showinfo,
        "showwarning": messagebox.showwarning,
        "showerror": messagebox.showerror,
        "askyesno": messagebox.askyesno,
        "askyesnocancel": messagebox.askyesnocancel,
        "askokcancel": messagebox.askokcancel,
        "askquestion": messagebox.askquestion,
    }

    def wrap(original):
        def wrapped(title=None, message=None, *args, **kwargs):
            if title is not None:
                title = translate_dynamic(str(title))
            if message is not None:
                message = translate_dynamic(str(message))
            return original(title, message, *args, **kwargs)

        return wrapped

    for name, original in originals.items():
        setattr(messagebox, name, wrap(original))
    messagebox._pixi_i18n_installed = True  # type: ignore[attr-defined]


def missing_translation_keys(code: str) -> List[str]:
    """Return English source keys absent from the requested catalog."""
    if code == "en":
        return []
    return sorted(set(_load_catalog("zh")) - set(_load_catalog(code)))


def untranslated_static_texts(root: tk.Misc) -> List[str]:
    """Development helper: list visible CJK strings in the English UI."""
    if _CURRENT != "en":
        return []
    found: List[str] = []

    def visit(widget: tk.Misc) -> None:
        if isinstance(widget, tk.Menu):
            try:
                end = widget.index("end")
            except tk.TclError:
                end = None
            if end is not None:
                for index in range(end + 1):
                    try:
                        label = str(widget.entrycget(index, "label"))
                    except tk.TclError:
                        continue
                    if _has_cjk(label):
                        found.append(label)
        elif isinstance(widget, ttk.Notebook):
            for tab_id in widget.tabs():
                try:
                    label = str(widget.tab(tab_id, "text"))
                    if _has_cjk(label):
                        found.append(label)
                except tk.TclError:
                    pass
        elif isinstance(widget, ttk.Treeview):
            for column in widget["columns"]:
                try:
                    label = str(widget.heading(column, "text"))
                    if _has_cjk(label):
                        found.append(label)
                except tk.TclError:
                    pass
        elif isinstance(widget, (tk.Toplevel, tk.Tk)):
            try:
                title = widget.title()
                if _has_cjk(title):
                    found.append(title)
            except tk.TclError:
                pass

        if not isinstance(
            widget,
            (tk.Text, tk.Entry, ttk.Entry, ttk.Combobox, ttk.Spinbox, tk.Listbox),
        ):
            try:
                keys = widget.keys()
            except (tk.TclError, AttributeError):
                keys = []
            if "text" in keys:
                try:
                    text = str(widget.cget("text"))
                    if _has_cjk(text):
                        found.append(text)
                except tk.TclError:
                    pass
            if "textvariable" in keys:
                try:
                    var_name = widget.cget("textvariable")
                    if var_name:
                        value = widget.getvar(var_name)
                        if value is not None and _has_cjk(str(value)):
                            found.append(str(value))
                except tk.TclError:
                    pass
        for child in widget.winfo_children():
            visit(child)

    visit(root)
    return sorted(set(found))


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)
