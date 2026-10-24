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

from .util import strip_ansi


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
    process: subprocess.Popen
    started: float
    refresh: bool = False
    command_line: str = ""
    cancelled: bool = False
    extra: dict = field(default_factory=dict)

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
            process = subprocess.Popen(
                command,
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
        except OSError as exc:
            raise RuntimeError("无法启动命令：{}".format(exc)) from exc

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

    def _reader(self, job: Job) -> None:
        stream = job.process.stdout
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
                returncode = job.process.wait()
            except OSError:
                returncode = -1
            elapsed = job.elapsed
            with self._lock:
                self.jobs.pop(job.job_id, None)
            self.events.put(
                JobEvent(
                    kind="done",
                    job=job,
                    returncode=returncode,
                    elapsed=elapsed,
                )
            )

    def cancel(self, job_id: int) -> bool:
        with self._lock:
            job = self.jobs.get(job_id)
        if job is None:
            return False
        job.cancelled = True
        if os.name == "nt":
            try:
                subprocess.run(
                    [
                        "taskkill",
                        "/PID",
                        str(job.process.pid),
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
            job.process.terminate()
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


def open_terminal(
    args: Sequence[str],
    cwd: Optional[Path] = None,
    title: str = "Pixi",
) -> subprocess.Popen:
    """Open a new PowerShell window running *args*.

    Interactive tasks (Jupyter, shells) are much more usable in a real
    terminal, so they are intentionally not captured by the GUI job manager.
    """

    if os.name == "nt":
        command = terminal_command_line(args, title=title)
        return subprocess.Popen(
            ["powershell.exe", "-NoExit", "-Command", command],
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
