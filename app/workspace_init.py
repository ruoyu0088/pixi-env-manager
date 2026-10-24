"""Helpers for creating a new Pixi workspace from the GUI."""

from __future__ import annotations

import platform
import sys
from pathlib import Path
from typing import Iterable, List, Sequence


COMMON_PLATFORMS = ("win-64", "linux-64", "osx-64", "osx-arm64")


def default_platform() -> str:
    if sys.platform.startswith("win"):
        return "win-64"
    if sys.platform == "darwin":
        return "osx-arm64" if platform.machine().lower() in ("arm64", "aarch64") else "osx-64"
    return "linux-64"


def normalize_channels(values: Sequence[str]) -> List[str]:
    result: List[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
    return result


def build_init_args(
    path: Path,
    channels: Iterable[str],
    platforms: Iterable[str],
) -> List[str]:
    target = Path(path).expanduser()
    args = ["init", str(target), "--format", "pixi"]
    for channel in normalize_channels(list(channels)):
        args += ["--channel", channel]
    for target_platform in normalize_channels(list(platforms)):
        args += ["--platform", target_platform]
    return args


def workspace_name(path: Path) -> str:
    return Path(path).expanduser().name
