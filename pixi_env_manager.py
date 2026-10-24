"""Entry point for the Pixi environment manager."""

from __future__ import annotations

import os
import traceback
from datetime import datetime
from pathlib import Path


def _crash_log_path() -> Path:
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) / "PixiEnvManager" if appdata else Path.home() / ".pixi-env-manager"
    return base / "crash.log"


def main() -> None:
    from app.ui.main_window import main as run_gui

    run_gui()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        details = traceback.format_exc()
        try:
            path = _crash_log_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write("\n===== {} =====\n".format(datetime.now().isoformat()))
                handle.write(details)
                handle.write("\n")
        except OSError:
            path = None
        try:
            import tkinter.messagebox

            message = "程序启动失败。"
            if path:
                message += "\n\n错误日志：\n{}".format(path)
            message += "\n\n" + details[-1500:]
            tkinter.messagebox.showerror("Pixi 环境管理器", message)
        except Exception:
            pass
        raise
