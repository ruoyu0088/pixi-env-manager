"""Entry point for the Pixi environment manager."""

from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime
from pathlib import Path


def _crash_log_path() -> Path:
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) / "PixiEnvManager" if appdata else Path.home() / ".pixi-env-manager"
    return base / "crash.log"


def _parse_option(argv: list[str], name: str, default: str) -> str:
    if name not in argv:
        return default
    index = argv.index(name)
    if index + 1 >= len(argv):
        return default
    return argv[index + 1]


def _usage() -> None:
    print("Pixi Environment Manager")
    print("")
    print("  start.bat                         Start the Tk desktop UI")
    print("  start.bat --web                   Start the Web UI on 127.0.0.1:8010")
    print("  start.bat --web --host 0.0.0.0 --port 8010")
    print("  start.bat --web --set-password    Set the Web UI password")
    print("  start.bat --web --open            Open the browser after starting")
    print("")


def _run_web(argv: list[str]) -> int:
    port_text = _parse_option(argv, "--port", "8010")
    try:
        port = int(port_text)
    except ValueError:
        print("Invalid port: {}".format(port_text), file=sys.stderr)
        return 2
    if not 1 <= port <= 65535:
        print("Port must be between 1 and 65535.", file=sys.stderr)
        return 2
    host = _parse_option(argv, "--host", "127.0.0.1").strip() or "127.0.0.1"
    from app.web.server import run_server

    return run_server(
        host=host,
        port=port,
        open_browser="--open" in argv,
    )


def main() -> None:
    argv = sys.argv[1:]
    if "--help" in argv or "-h" in argv:
        _usage()
        return
    if "--set-password" in argv:
        from app.web.auth import set_password_interactive

        raise SystemExit(set_password_interactive())
    if "--web" in argv:
        raise SystemExit(_run_web(argv))

    from app.ui.main_window import main as run_gui

    run_gui()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
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

            message = "The program failed to start."
            if path:
                message += "\n\nError log:\n{}".format(path)
            message += "\n\n" + details[-1500:]
            tkinter.messagebox.showerror("Pixi Environment Manager", message)
        except Exception:
            pass
        raise
