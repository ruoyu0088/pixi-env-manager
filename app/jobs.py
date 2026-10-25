"""Background command execution with streamed output and process-tree stop."""

from __future__ import annotations

import os
import queue
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .util import split_user_args, strip_ansi


CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)


def child_env() -> Dict[str, str]:
    env = os.environ.copy()
    env["PIXI_NO_PROGRESS"] = "true"
    env["PIXI_COLOR"] = "never"
    env["NO_COLOR"] = "1"
    env["CLICOLOR"] = "0"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    return env


@dataclass
class Job:
    job_id: int
    title: str
    args: List[str]
    cwd: Optional[str]
    process: Optional[subprocess.Popen]
    started: float
    refresh: bool = False
    command_line: str = ""
    cancelled: bool = False
    extra: dict = field(default_factory=dict)
    commands: List[List[str]] = field(default_factory=list)

    @property
    def elapsed(self) -> float:
        return max(0.0, time.time() - self.started)


@dataclass
class JobEvent:
    kind: str
    job: Job
    text: str = ""
    returncode: Optional[int] = None
    elapsed: float = 0.0


class JobManager:
    """Run any number of independent jobs and stream their events."""

    def __init__(self) -> None:
        self.events: "queue.Queue[JobEvent]" = queue.Queue()
        self.jobs: Dict[int, Job] = {}
        self._lock = threading.Lock()
        self._counter = 0

    @property
    def busy(self) -> bool:
        with self._lock:
            return bool(self.jobs)

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self.jobs)

    def jobs_snapshot(self) -> List[Job]:
        with self._lock:
            return list(self.jobs.values())

    def get(self, job_id: int) -> Optional[Job]:
        with self._lock:
            return self.jobs.get(job_id)

    def has_mutating(self, exclude: Optional[int] = None) -> bool:
        with self._lock:
            return any(
                job.extra.get("mutating") and job.job_id != exclude
                for job in self.jobs.values()
            )

    def start(
        self,
        title: str,
        args: Sequence[str],
        cwd: Optional[Path] = None,
        refresh: bool = False,
        extra: Optional[dict] = None,
    ) -> Job:
        with self._lock:
            self._counter += 1
            job_id = self._counter

        command = [str(item) for item in args]
        try:
            process = self._spawn(command, cwd)
        except OSError as exc:
            raise RuntimeError("Failed to start command: {}".format(exc)) from exc

        job = Job(
            job_id=job_id,
            title=title,
            args=command,
            cwd=str(cwd) if cwd else None,
            process=process,
            started=time.time(),
            refresh=refresh,
            command_line=subprocess.list2cmdline(command),
            extra=dict(extra or {}),
        )
        with self._lock:
            self.jobs[job_id] = job
        threading.Thread(target=self._reader, args=(job,), daemon=True).start()
        return job

    def start_sequence(
        self,
        title: str,
        commands: Sequence[Sequence[str]],
        cwd: Optional[Path] = None,
        refresh: bool = False,
        extra: Optional[dict] = None,
        stop_on_error: bool = True,
    ) -> Job:
        normalized = [
            [str(item) for item in command] for command in commands if command
        ]
        if not normalized:
            raise RuntimeError("Command sequence is empty.")
        with self._lock:
            self._counter += 1
            job_id = self._counter
            job = Job(
                job_id=job_id,
                title=title,
                args=[],
                cwd=str(cwd) if cwd else None,
                process=None,
                started=time.time(),
                refresh=refresh,
                command_line=" ; ".join(
                    subprocess.list2cmdline(command) for command in normalized
                ),
                extra={
                    **dict(extra or {}),
                    "sequence": True,
                    "steps": len(normalized),
                },
                commands=normalized,
            )
            self.jobs[job_id] = job
        threading.Thread(
            target=self._sequence_reader,
            args=(job, cwd, stop_on_error),
            daemon=True,
        ).start()
        return job

    def _spawn(
        self, command: Sequence[str], cwd: Optional[Path]
    ) -> subprocess.Popen:
        return subprocess.Popen(
            [str(item) for item in command],
            cwd=str(cwd) if cwd else None,
            env=child_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
        )

    def _stream_process(self, job: Job, process: subprocess.Popen) -> int:
        stream = process.stdout
        try:
            if stream is not None:
                for line in iter(stream.readline, ""):
                    self.events.put(
                        JobEvent(kind="line", job=job, text=strip_ansi(line.rstrip("\r\n")))
                    )
        finally:
            try:
                if stream is not None:
                    stream.close()
            except OSError:
                pass
        try:
            return process.wait()
        except OSError:
            return -1

    def _finish(self, job: Job, returncode: int) -> None:
        elapsed = job.elapsed
        with self._lock:
            job.process = None
            self.jobs.pop(job.job_id, None)
        self.events.put(
            JobEvent(
                kind="done",
                job=job,
                returncode=returncode,
                elapsed=elapsed,
            )
        )

    def _reader(self, job: Job) -> None:
        returncode = 0
        if job.process is not None:
            returncode = self._stream_process(job, job.process)
        self._finish(job, returncode)

    def _sequence_reader(
        self,
        job: Job,
        cwd: Optional[Path],
        stop_on_error: bool,
    ) -> None:
        final_returncode = 0
        for index, command in enumerate(job.commands, start=1):
            if job.cancelled:
                final_returncode = -1
                break
            self.events.put(
                JobEvent(
                    kind="line",
                    job=job,
                    text="[{} / {}] $ {}".format(
                        index,
                        len(job.commands),
                        subprocess.list2cmdline(command),
                    ),
                )
            )
            try:
                process = self._spawn(command, cwd)
            except OSError as exc:
                self.events.put(
                    JobEvent(
                        kind="line",
                        job=job,
                        text="Failed to start command: {}".format(exc),
                    )
                )
                final_returncode = 1
                break
            with self._lock:
                job.process = process
            if job.cancelled:
                self._terminate(process)
            returncode = self._stream_process(job, process)
            with self._lock:
                job.process = None
            if job.cancelled:
                final_returncode = -1
                break
            if returncode != 0:
                final_returncode = returncode
                if stop_on_error:
                    break
            else:
                final_returncode = 0
        if job.cancelled and final_returncode == 0:
            final_returncode = -1
        self._finish(job, final_returncode)

    def _terminate(self, process: subprocess.Popen) -> None:
        try:
            process.terminate()
        except OSError:
            pass

    def cancel(self, job_id: int) -> bool:
        with self._lock:
            job = self.jobs.get(job_id)
        if job is None:
            return False
        job.cancelled = True
        with self._lock:
            process = job.process
        if process is None:
            return True
        if os.name == "nt":
            try:
                subprocess.run(
                    [
                        "taskkill",
                        "/PID",
                        str(process.pid),
                        "/T",
                        "/F",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=CREATE_NO_WINDOW,
                    timeout=10,
                )
                return True
            except (OSError, subprocess.SubprocessError):
                pass
        try:
            process.terminate()
            return True
        except OSError:
            return False

    def cancel_all(self) -> int:
        count = 0
        for job in self.jobs_snapshot():
            if self.cancel(job.job_id):
                count += 1
        return count

    def drain(self) -> List[JobEvent]:
        events: List[JobEvent] = []
        while True:
            try:
                events.append(self.events.get_nowait())
            except queue.Empty:
                break
        return events


def _ps_quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def terminal_command_line(args: Sequence[str], title: str = "Pixi") -> str:
    command = "& " + " ".join(_ps_quote(item) for item in args)
    prefix = "$Host.UI.RawUI.WindowTitle = {}; ".format(_ps_quote(title))
    return prefix + command


def cmd_command_line(args: Sequence[str], title: str = "Pixi") -> str:
    return subprocess.list2cmdline([str(item) for item in args])


def _terminal_kind(executable: str) -> str:
    name = Path(executable).name.lower()
    if name in ("powershell.exe", "powershell", "pwsh.exe", "pwsh"):
        return "powershell"
    if name in ("cmd.exe", "cmd"):
        return "cmd"
    if name in ("wt.exe", "wt", "windowsterminal.exe"):
        return "wt"
    return "custom"


def build_terminal_argv(
    args: Sequence[str],
    cwd: Optional[Path] = None,
    title: str = "Pixi",
    terminal: str = "",
) -> List[str]:
    """Build the command line for the configured terminal.

    An empty setting keeps the previous PowerShell behavior.  The setting may
    be a simple executable (``cmd.exe``, ``wt.exe``, ``pwsh.exe``), that
    executable with arguments, or a small template using ``{command}``,
    ``{cmd}``, ``{cwd}`` and ``{title}``.
    """

    cwd_text = str(cwd or Path.cwd())
    powershell_command = terminal_command_line(args, title=title)
    cmd_command = cmd_command_line(args, title=title)
    spec = (terminal or "").strip()
    if spec and " " in spec and Path(spec).is_file():
        tokens = [spec]
    else:
        tokens = split_user_args(spec) if spec else ["powershell.exe"]
    if not tokens:
        tokens = ["powershell.exe"]

    has_template = any(
        placeholder in token
        for token in tokens
        for placeholder in ("{command}", "{cmd}", "{cwd}", "{title}")
    )
    if has_template:
        return [
            token.replace("{command}", powershell_command)
            .replace("{cmd}", cmd_command)
            .replace("{cwd}", cwd_text)
            .replace("{title}", title)
            for token in tokens
        ]

    kind = _terminal_kind(tokens[0])
    if kind == "cmd":
        return tokens + ["/K", cmd_command]
    if kind == "wt":
        return tokens + [
            "-d",
            cwd_text,
            "powershell.exe",
            "-NoExit",
            "-Command",
            powershell_command,
        ]
    # PowerShell-compatible terminals and custom executables.
    return tokens + ["-NoExit", "-Command", powershell_command]


def open_terminal(
    args: Sequence[str],
    cwd: Optional[Path] = None,
    title: str = "Pixi",
    terminal: str = "",
) -> subprocess.Popen:
    """Open a new terminal window running *args*.

    Interactive tasks (Jupyter, shells) are much more usable in a real
    terminal, so they are intentionally not captured by the GUI job manager.
    """

    if os.name == "nt":
        command = build_terminal_argv(
            args, cwd=cwd, title=title, terminal=terminal
        )
        return subprocess.Popen(
            command,
            cwd=str(cwd) if cwd else None,
            env=child_env(),
            creationflags=CREATE_NEW_CONSOLE,
        )
    # Best effort for non-Windows development environments.
    return subprocess.Popen(
        [str(item) for item in args],
        cwd=str(cwd) if cwd else None,
        env=child_env(),
        start_new_session=True,
    )
