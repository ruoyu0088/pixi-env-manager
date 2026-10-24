"""Small helpers shared by the UI and the command layer."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List


_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text or "")


def split_user_args(text: str) -> List[str]:
    """Split a Windows command-line fragment into arguments.

    This deliberately preserves backslashes (important for Windows paths) and
    removes quotes anywhere in a token, so ``--foo="hello world"`` becomes a
    single argument.  It handles the common quoting cases without pretending to
    be a full shell parser.
    """

    text = (text or "").strip()
    if not text:
        return []
    args: List[str] = []
    buffer: List[str] = []
    quote = ""
    index = 0
    while index < len(text):
        character = text[index]
        if quote:
            if character == "\\" and index + 1 < len(text) and text[index + 1] == quote:
                buffer.append(quote)
                index += 2
                continue
            if character == quote:
                quote = ""
            else:
                buffer.append(character)
            index += 1
            continue
        if character in "\"'":
            quote = character
            index += 1
            continue
        if character in " \t":
            if buffer:
                args.append("".join(buffer))
                buffer = []
            index += 1
            continue
        buffer.append(character)
        index += 1
    if buffer:
        args.append("".join(buffer))
    return args


def shorten_path(path: str, limit: int = 52) -> str:
    if not path:
        return ""
    text = str(Path(path))
    if len(text) <= limit:
        return text
    parts = Path(text).parts
    if len(parts) >= 4:
        compact = os.path.join(parts[0], "…", *parts[-2:])
        if len(compact) <= limit + 4:
            return compact
    return text[: max(1, limit // 2 - 1)] + "…" + text[-max(1, limit // 2 - 1) :]


def format_size(value: int) -> str:
    try:
        size = int(value)
    except (TypeError, ValueError):
        return ""
    if size <= 0:
        return ""
    units = ("B", "KB", "MB", "GB")
    amount = float(size)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            if unit == "B":
                return "{:.0f} {}".format(amount, unit)
            return "{:.1f} {}".format(amount, unit)
        amount /= 1024
    return ""


def truncate_text(text: str, limit: int = 60) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)] + "…"
