"""TOML manifest editor with line numbers and a small built-in highlighter."""

from __future__ import annotations

import locale
import os
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Dict, Optional

from .. import i18n
from ..models import WorkspaceData
from ..toml_highlight import tokenize

try:  # Python 3.11+
    import tomllib
except ImportError:  # pragma: no cover - fallback for older interpreters
    tomllib = None  # type: ignore[assignment]


class EditorTab(ttk.Frame):
    def __init__(self, master, app, colors: Dict[str, str]):
        super().__init__(master, padding=(14, 12))
        self.app = app
        self.colors = colors
        self.path: Optional[Path] = None
        self.workspace: Optional[WorkspaceData] = None
        self._original_text = ""
        self._newline = "\n"
        self._bom = False
        self._saved_mtime: Optional[float] = None
        self._dirty = False
        self._loading = False
        self._highlight_job: Optional[str] = None
        self._validate_job: Optional[str] = None
        self._find_visible = False
        self._syntax_ok: Optional[bool] = None

        header = ttk.Frame(self)
        header.pack(fill="x")
        ttk.Label(header, text="Manifest Editor", style="Title.TLabel").pack(side="left")
        self.path_var = tk.StringVar(value="No file open")
        path_label = ttk.Label(
            header, textvariable=self.path_var, style="Muted.TLabel"
        )
        path_label.pack(side="left", padx=(10, 0), pady=(6, 0))

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(10, 6))
        self.save_button = ttk.Button(
            toolbar, text="Save  Ctrl+S", style="Accent.TButton", command=self.save
        )
        self.save_button.pack(side="left")
        self.reload_button = ttk.Button(
            toolbar, text="Reload", command=self.reload_file
        )
        self.reload_button.pack(side="left", padx=(6, 0))
        self.find_button = ttk.Button(
            toolbar, text="Find  Ctrl+F", command=self.toggle_find
        )
        self.find_button.pack(side="left", padx=(6, 0))
        ttk.Button(
            toolbar, text="Open Folder", command=self._open_folder
        ).pack(side="right")
        ttk.Button(
            toolbar, text="Copy Path", command=self._copy_path
        ).pack(side="right", padx=(0, 6))

        self.find_bar = ttk.Frame(self)
        ttk.Label(self.find_bar, text="Find", style="Muted.TLabel").pack(
            side="left", padx=(0, 5)
        )
        self.find_var = tk.StringVar()
        self.find_entry = ttk.Entry(self.find_bar, textvariable=self.find_var, width=30)
        self.find_entry.pack(side="left")
        self.find_entry.bind("<Return>", lambda _event: self.find_next(False))
        self.find_entry.bind("<Escape>", lambda _event: self.toggle_find(False))
        ttk.Button(
            self.find_bar, text="Next", style="Small.TButton", command=lambda: self.find_next(False)
        ).pack(side="left", padx=(5, 0))
        ttk.Button(
            self.find_bar, text="Previous", style="Small.TButton", command=lambda: self.find_next(True)
        ).pack(side="left", padx=(4, 0))
        ttk.Button(
            self.find_bar, text="Close", style="Small.TButton", command=lambda: self.toggle_find(False)
        ).pack(side="left", padx=(4, 0))

        editor_frame = ttk.Frame(self)
        editor_frame.pack(fill="both", expand=True, pady=(0, 0))
        editor_frame.rowconfigure(0, weight=1)
        editor_frame.columnconfigure(1, weight=1)

        self.gutter = tk.Text(
            editor_frame,
            width=5,
            padx=4,
            pady=6,
            takefocus=0,
            borderwidth=0,
            highlightthickness=0,
            wrap="none",
            state="disabled",
            cursor="arrow",
        )
        self.gutter.grid(row=0, column=0, sticky="ns")
        self.text = tk.Text(
            editor_frame,
            wrap="none",
            undo=True,
            maxundo=-1,
            autoseparators=True,
            padx=10,
            pady=6,
            borderwidth=0,
            highlightthickness=0,
            font=self.app.theme.fonts.mono,
        )
        self.text.grid(row=0, column=1, sticky="nsew")
        self.y_scroll = ttk.Scrollbar(
            editor_frame, orient="vertical", command=self.text.yview
        )
        self.y_scroll.grid(row=0, column=2, sticky="ns")
        self.x_scroll = ttk.Scrollbar(
            editor_frame, orient="horizontal", command=self.text.xview
        )
        self.x_scroll.grid(row=1, column=1, sticky="ew")
        self.text.configure(
            yscrollcommand=self._on_text_yscroll,
            xscrollcommand=self.x_scroll.set,
        )
        self.gutter.bind("<MouseWheel>", self._gutter_wheel)

        status = ttk.Frame(self)
        status.pack(side="bottom", fill="x", pady=(5, 0), before=editor_frame)
        self.pos_var = tk.StringVar(value="Ln 1, Col 1")
        self.mode_var = tk.StringVar(value="UTF-8  ·  LF")
        self.syntax_var = tk.StringVar(value="")
        self.dirty_var = tk.StringVar(value="No file open")
        ttk.Label(status, textvariable=self.pos_var, style="Muted.TLabel").pack(
            side="left"
        )
        ttk.Label(status, textvariable=self.mode_var, style="Muted.TLabel").pack(
            side="left", padx=(16, 0)
        )
        self.syntax_label = ttk.Label(
            status, textvariable=self.syntax_var, style="Muted.TLabel"
        )
        self.syntax_label.pack(side="left", padx=(16, 0))
        self.dirty_label = ttk.Label(
            status, textvariable=self.dirty_var, style="Muted.TLabel"
        )
        self.dirty_label.pack(side="right")

        self.text.bind("<<Modified>>", self._on_modified)
        self.text.bind("<KeyRelease>", self._on_cursor, add="+")
        self.text.bind("<ButtonRelease-1>", self._on_cursor, add="+")
        self.text.bind("<Control-s>", lambda _event: (self.save(), "break")[1])
        self.text.bind("<Control-f>", lambda _event: (self.toggle_find(), "break")[1])
        self.text.bind("<Control-r>", lambda _event: (self.reload_file(), "break")[1])
        self.text.bind("<Tab>", self._insert_tab)
        self.text.bind("<Shift-Tab>", self._unindent)
        self.text.bind("<Button-3>", self._editor_menu)
        self.bind("<Control-s>", lambda _event: (self.save(), "break")[1])

        self.apply_theme(colors)
        self._set_enabled(False)

    # ------------------------------------------------------------------
    def apply_theme(self, colors: Dict[str, str]) -> None:
        self.colors = colors
        self.text.configure(
            background=colors["panel"],
            foreground=colors["text"],
            insertbackground=colors["text"],
            selectbackground=colors["selected"],
            selectforeground=colors["selected_text"],
            font=self.app.theme.fonts.mono,
        )
        self.gutter.configure(
            background=colors["panel_alt"],
            foreground=colors["muted"],
            font=self.app.theme.fonts.mono_small,
            selectbackground=colors["panel_alt"],
            selectforeground=colors["muted"],
        )
        tags = {
            "comment": dict(foreground=colors["comment"], font=self.app.theme.fonts.mono),
            "table": dict(
                foreground=colors["table"],
                font=self.app.theme.fonts.mono_bold,
            ),
            "key": dict(foreground=colors["key"]),
            "operator": dict(foreground=colors["muted"]),
            "string": dict(foreground=colors["string"]),
            "number": dict(foreground=colors["number"]),
            "boolean": dict(foreground=colors["boolean"]),
            "date": dict(foreground=colors["date"]),
            "punct": dict(foreground=colors["muted"]),
            "current_line": dict(background=colors["current_line"]),
            "search": dict(
                background=colors["warning_bg"],
                foreground=colors["warning"],
            ),
        }
        for name, options in tags.items():
            self.text.tag_configure(name, **options)
        self.text.tag_raise("current_line")
        self.text.tag_raise("search")
        if self._dirty:
            self.dirty_label.configure(foreground=colors["warning"])
        self._update_status()

    def _set_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for button in (self.save_button, self.reload_button, self.find_button):
            button.configure(state=state)
        self.text.configure(state=state)
        if enabled:
            self.text.configure(background=self.colors["panel"])
        else:
            self.text.configure(background=self.colors["panel_alt"])

    # ------------------------------------------------------------------
    def set_workspace(self, workspace: Optional[WorkspaceData]) -> None:
        self.workspace = workspace
        if workspace is None:
            self.path = None
            self._set_enabled(False)
            self.text.configure(state="normal")
            self.text.delete("1.0", "end")
            self.gutter.configure(state="normal")
            self.gutter.delete("1.0", "end")
            self.gutter.configure(state="disabled")
            self.path_var.set("No file open")
            self.dirty_var.set("No file open")
            self._set_enabled(False)
            return
        if self.path and self.path.resolve() == workspace.manifest.resolve():
            self._set_enabled(True)
            return
        self.load_file(workspace.manifest)

    def load_file(self, path: Path, force: bool = False) -> bool:
        if self._dirty and not force:
            if not self.maybe_save():
                return False
        try:
            raw = path.read_bytes()
        except OSError as exc:
            messagebox.showerror("Read failed", "Could not read:\n{}\n\n{}".format(path, exc), parent=self)
            return False
        self._bom = raw.startswith(b"\xef\xbb\xbf")
        try:
            text = raw.decode("utf-8-sig" if self._bom else "utf-8")
        except UnicodeDecodeError:
            try:
                text = raw.decode(locale.getpreferredencoding(False))
            except UnicodeDecodeError:
                text = raw.decode("utf-8", "replace")
        self._newline = "\r\n" if "\r\n" in text else "\n"
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        self._loading = True
        try:
            self.path = path
            self._original_text = normalized
            self.text.configure(state="normal")
            self.text.delete("1.0", "end")
            self.text.insert("1.0", normalized)
            self.text.edit_modified(False)
            self.text.edit_reset()
            self.text.mark_set("insert", "1.0")
            self.text.see("1.0")
            self._dirty = False
            self._saved_mtime = self._safe_mtime(path)
            self.path_var.set(str(path))
            self.dirty_var.set("Saved")
            self.dirty_label.configure(foreground=self.colors["muted"])
            self.mode_var.set(
                "UTF-8{}  ·  {}".format(
                    " BOM" if self._bom else "",
                    "CRLF" if self._newline == "\r\n" else "LF",
                )
            )
            self._syntax_ok = None
            self.syntax_var.set("")
            self.text.edit_modified(False)
            self._set_enabled(True)
        finally:
            self._loading = False
        self._update_line_numbers()
        self._highlight()
        self._update_status()
        self._schedule_validation()
        self.text.focus_set()
        return True

    def _safe_mtime(self, path: Path) -> Optional[float]:
        try:
            return path.stat().st_mtime
        except OSError:
            return None

    # ------------------------------------------------------------------
    def _on_text_yscroll(self, first: str, last: str) -> None:
        self.y_scroll.set(first, last)
        try:
            self.gutter.yview_moveto(first)
        except tk.TclError:
            pass

    def _gutter_wheel(self, event) -> str:
        delta = int(-1 * (event.delta / 120)) if event.delta else 0
        if delta:
            self.text.yview_scroll(delta, "units")
        return "break"

    def _on_modified(self, _event=None) -> None:
        if self._loading:
            return
        if not self.text.edit_modified():
            return
        self.text.edit_modified(False)
        self._dirty = True
        self.dirty_var.set("Unsaved")
        self.dirty_label.configure(foreground=self.colors["warning"])
        self._update_line_numbers()
        self._schedule_highlight()
        self._update_status()
        self._schedule_validation()

    def _schedule_highlight(self) -> None:
        if self._highlight_job:
            try:
                self.after_cancel(self._highlight_job)
            except tk.TclError:
                pass
        self._highlight_job = self.after(90, self._highlight)

    def _highlight(self) -> None:
        self._highlight_job = None
        if not self.path:
            return
        content = self.text.get("1.0", "end-1c")
        for tag in (
            "comment",
            "table",
            "key",
            "operator",
            "string",
            "number",
            "boolean",
            "date",
            "punct",
        ):
            self.text.tag_remove(tag, "1.0", "end")
        for token in tokenize(content):
            if token.end <= token.start:
                continue
            start = "1.0 + {} chars".format(token.start)
            end = "1.0 + {} chars".format(token.end)
            self.text.tag_add(token.kind, start, end)
        self._update_current_line()

    def _update_current_line(self) -> None:
        self.text.tag_remove("current_line", "1.0", "end")
        try:
            line = self.text.index("insert").split(".")[0]
            self.text.tag_add("current_line", "{}.0".format(line), "{}.end".format(line))
        except tk.TclError:
            pass

    def _update_line_numbers(self) -> None:
        try:
            line_count = int(self.text.index("end-1c").split(".")[0])
        except (tk.TclError, ValueError):
            line_count = 1
        self.gutter.configure(state="normal")
        self.gutter.delete("1.0", "end")
        numbers = "\n".join(str(number) for number in range(1, line_count + 1))
        self.gutter.insert("1.0", numbers)
        width = max(4, len(str(line_count)) + 2)
        self.gutter.configure(width=width, state="disabled")

    def _on_cursor(self, _event=None) -> None:
        try:
            line, column = self.text.index("insert").split(".")
            self.pos_var.set("Ln {}, Col {}".format(line, column))
        except (tk.TclError, ValueError):
            pass
        self._update_current_line()

    def _insert_tab(self, _event=None) -> str:
        self.text.insert("insert", "    ")
        return "break"

    def _unindent(self, _event=None) -> str:
        try:
            line_start = self.text.index("insert linestart")
            prefix = self.text.get(line_start, "insert")
            remove = min(4, len(prefix) - len(prefix.lstrip(" ")))
            if remove:
                self.text.delete("insert-{}c".format(remove), "insert")
        except tk.TclError:
            pass
        return "break"

    # ------------------------------------------------------------------
    def toggle_find(self, show: Optional[bool] = None) -> None:
        if show is None:
            show = not self._find_visible
        self._find_visible = show
        if show:
            self.find_bar.pack(fill="x", pady=(0, 6), before=self.text.master)
            self.find_entry.focus_set()
            self.find_entry.select_range(0, "end")
        else:
            self.find_bar.pack_forget()
            self.text.tag_remove("search", "1.0", "end")
            self.text.focus_set()

    def find_next(self, backwards: bool = False) -> None:
        needle = self.find_var.get().strip()
        if not needle:
            return
        self.text.tag_remove("search", "1.0", "end")
        start = self.text.index("insert")
        if backwards:
            found = self.text.search(
                needle, start, stopindex="1.0", backwards=True, nocase=True
            )
            if not found:
                found = self.text.search(
                    needle, "end", stopindex="1.0", backwards=True, nocase=True
                )
        else:
            found = self.text.search(
                needle, "insert+1c", stopindex="end", nocase=True
            )
            if not found:
                found = self.text.search(needle, "1.0", stopindex="end", nocase=True)
        if found:
            end = "{}+{}c".format(found, len(needle))
            self.text.tag_add("search", found, end)
            self.text.mark_set("insert", end)
            self.text.see(found)
            self.text.focus_set()
        else:
            self.bell()

    def _editor_menu(self, event) -> None:
        menu = tk.Menu(self, tearoff=0)
        self.app.theme.style_menu(menu)
        menu.add_command(label="Undo", command=self.text.edit_undo)
        menu.add_command(label="Redo", command=self.text.edit_redo)
        menu.add_separator()
        menu.add_command(label="Cut", command=lambda: self.text.event_generate("<<Cut>>"))
        menu.add_command(label="Copy", command=lambda: self.text.event_generate("<<Copy>>"))
        menu.add_command(label="Paste", command=lambda: self.text.event_generate("<<Paste>>"))
        menu.add_separator()
        menu.add_command(label="Select All", command=self._select_all)
        i18n.localize_menu(menu)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _select_all(self) -> None:
        self.text.tag_add("sel", "1.0", "end-1c")
        self.text.mark_set("insert", "1.0")

    # ------------------------------------------------------------------
    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def maybe_save(self) -> bool:
        if not self._dirty:
            return True
        answer = messagebox.askyesnocancel(
            "Unsaved changes",
            "{} has unsaved changes.\n\nSave first?".format(
                self.path.name if self.path else "Manifest file"
            ),
            parent=self,
            default=messagebox.YES,
        )
        if answer is None:
            return False
        if answer:
            return self.save()
        return True

    def save(self) -> bool:
        if not self.path:
            return False
        content = self.text.get("1.0", "end-1c")
        error = self._validate_content(content)
        if error:
            if not messagebox.askyesno(
                "TOML syntax error",
                "The file has a syntax error:\n\n{}\n\nSave anyway?".format(error),
                parent=self,
            ):
                return False
        # Do not silently overwrite a file changed by another editor.
        current_mtime = self._safe_mtime(self.path)
        if (
            self._saved_mtime is not None
            and current_mtime is not None
            and current_mtime != self._saved_mtime
            and content != self._original_text
        ):
            if not messagebox.askyesno(
                "File changed",
                "The file was changed by another program.\nOverwrite anyway?",
                parent=self,
            ):
                return False
        raw_text = content.replace("\n", self._newline)
        try:
            data = raw_text.encode("utf-8-sig" if self._bom else "utf-8")
            temp_path = self.path.with_name(
                ".{}.{}.tmp".format(self.path.name, os.getpid())
            )
            temp_path.write_bytes(data)
            os.replace(temp_path, self.path)
        except OSError as exc:
            messagebox.showerror("Save failed", "Could not save file:\n{}".format(exc), parent=self)
            return False
        finally:
            try:
                if "temp_path" in locals() and temp_path.exists():
                    temp_path.unlink()
            except OSError:
                pass
        self._original_text = content
        self._saved_mtime = self._safe_mtime(self.path)
        self._dirty = False
        self.text.edit_modified(False)
        self.dirty_var.set("Saved " + time.strftime("%H:%M:%S"))
        self.dirty_label.configure(foreground=self.colors["success"])
        self._syntax_ok = not bool(error)
        self._update_status()
        if self.workspace and not error:
            self.app.on_manifest_saved(self.path)
        elif error:
            self.dirty_var.set("Saved (syntax error)")
            self.dirty_label.configure(foreground=self.colors["danger"])
        return True

    def reload_file(self) -> None:
        if not self.path:
            return
        if self._dirty:
            if not messagebox.askyesno(
                "Reload",
                "Reloading will discard unsaved changes. Continue?",
                parent=self,
            ):
                return
        self._dirty = False
        self.load_file(self.path, force=True)

    def reload_if_clean(self) -> None:
        """Reload when a command or another editor changed the manifest."""
        if not self.path or self._dirty or self._loading:
            return
        current = self._safe_mtime(self.path)
        if current is None:
            return
        if self._saved_mtime is None or current != self._saved_mtime:
            self.load_file(self.path, force=True)

    def _validate_content(self, content: str) -> str:
        if tomllib is None:
            return ""
        try:
            tomllib.loads(content)
            return ""
        except Exception as exc:
            text = str(exc)
            return text.splitlines()[0][:500] if text else "TOML parse failed"

    def _schedule_validation(self) -> None:
        if self._validate_job:
            try:
                self.after_cancel(self._validate_job)
            except tk.TclError:
                pass
        self._validate_job = self.after(500, self._validate_live)

    def _validate_live(self) -> None:
        self._validate_job = None
        if not self.path:
            return
        content = self.text.get("1.0", "end-1c")
        error = self._validate_content(content)
        self._syntax_ok = not bool(error)
        if error:
            self.syntax_var.set("Syntax error")
            self.syntax_label.configure(foreground=self.colors["danger"])
        else:
            self.syntax_var.set("TOML syntax OK")
            self.syntax_label.configure(foreground=self.colors["success"])

    def _update_status(self) -> None:
        self.pos_var.set(self.pos_var.get() or "Ln 1, Col 1")
        if self._syntax_ok is False:
            self.syntax_var.set("Syntax error")
            self.syntax_label.configure(foreground=self.colors["danger"])
        elif self._syntax_ok is True:
            self.syntax_var.set("TOML syntax OK")
            self.syntax_label.configure(foreground=self.colors["success"])

    def _open_folder(self) -> None:
        if self.path:
            self.app.open_path(str(self.path.parent))

    def _copy_path(self) -> None:
        if self.path:
            self.clipboard_clear()
            self.clipboard_append(str(self.path))
