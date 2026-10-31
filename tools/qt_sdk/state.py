"""Forge state machine: .qtsdk/ persistence, command evidence, task budget.

All persistent state lives in <KB_ROOT>/workspace/qt-sdk/.qtsdk/ (override
with the QT_SDK_HOME environment variable):

    state.json     stage machine (checkpoint granularity) + gates + commands
    env.json       local configuration (source/build/SDK paths, jobs)
    registry.yaml  patch registry (see patching.py)
    patches/       patch files (P0001-*.patch, unified diff)
    inbox/         external change proposals from other agents
    builds/        per-build evidence: logs + config.summary snapshots
    releases/      manifest-<ver>.yaml + RELEASES.md index
    logs/          raw command logs (full output; state.json keeps tails)

Unlike qt_ohos.state.run_cmd (capture_output + clip, which loses the *tail*
of huge compile logs where the errors live), run_cmd here streams output to
the log file and keeps the last N bytes for the in-state evidence.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional

from .locking import atomic_write, file_lock

KB_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_DIR_NAME = ".qtsdk"
DEFAULT_HOME = KB_ROOT / "workspace" / "qt-sdk"

# Ordered forge stages (checkpoint granularity).
STAGES = [
    "env_check",
    "src_verify",
    "patch_review",
    "patch_apply",
    "configure",
    "build",
    "install",
    "verify",
    "release",
    "env_sync",
]

TAIL_BYTES = 8000          # tail kept in state.json evidence
LOG_HEAD_BYTES = 4000      # head kept as well (configure summaries etc.)


class BudgetExhausted(RuntimeError):
    """Raised when QT_SDK_TASK_BUDGET_SEC / QT_SDK_TASK_DEADLINE is exceeded."""


@dataclass
class CommandResult:
    command: str
    label: str = ""
    start_time: str = ""
    duration: float = 0.0
    exit_code: Optional[int] = None
    stdout_tail: str = ""
    stderr_tail: str = ""
    timeout: Optional[float] = None
    status: str = "NOT_RUN"   # PASS / FAIL / TIMEOUT / SKIP / NOT_RUN
    evidence: str = ""        # relative log path inside .qtsdk
    log_lines: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _slug(text: str) -> str:
    keep = "".join(ch if ch.isalnum() or ch in "-_" else "-"
                   for ch in text.strip())
    return keep.strip("-")[:48] or "cmd"


class ForgeState:
    """State machine persisted in <home>/.qtsdk/state.json."""

    def __init__(self, home: Optional[Path] = None, create: bool = False):
        env_home = os.environ.get("QT_SDK_HOME")
        self.home = Path(home or env_home or DEFAULT_HOME).resolve()
        self.state_dir = self.home / STATE_DIR_NAME
        self.state_file = self.state_dir / "state.json"
        self.data: Dict = {}
        if self.state_file.exists():
            self.data = json.loads(
                self.state_file.read_text(encoding="utf-8"))
        elif create:
            self.data = {
                "created": _now(),
                "stage": None,
                "completed": [],
                "current": {"stage": None, "error": None},
                "next": {"action": "env"},
                "qt": {"version": None, "render": None, "build_type": None},
                "src": {"path": None, "branch": None, "commit": None},
                "gates": {},
                "commands": [],
                "budget": {"exhausted": False, "checkpoint_steps": []},
            }
            self.save()
        else:
            raise FileNotFoundError(
                "no forge state at %s (run `qt-sdk-run init` first)"
                % self.state_file)

    # ------------------------------------------------------------ basics
    def save(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.data["updated"] = _now()
        with file_lock(self.state_file):
            atomic_write(self.state_file,
                         json.dumps(self.data, ensure_ascii=False, indent=2))

    # ------------------------------------------------------------ stages
    def begin_stage(self, stage: str) -> None:
        _check_stage(stage)
        self.data["stage"] = stage
        self.data["current"] = {"stage": stage, "error": None}
        self.save()

    def complete_stage(self, stage: str,
                       next_action: Optional[str] = None) -> None:
        _check_stage(stage)
        completed: List[str] = self.data.setdefault("completed", [])
        if stage not in completed:
            completed.append(stage)
        self.data["current"] = {"stage": stage, "error": None}
        if next_action:
            self.data["next"] = {"action": next_action}
        self.save()

    def fail_stage(self, stage: str, error: str,
                   next_action: Optional[str] = None) -> None:
        _check_stage(stage)
        self.data["current"] = {"stage": stage, "error": error}
        if next_action:
            self.data["next"] = {"action": next_action}
        self.save()

    def remaining_stages(self) -> List[str]:
        completed = set(self.data.get("completed", []))
        return [s for s in STAGES if s not in completed]

    def next_stage(self) -> Optional[str]:
        remaining = self.remaining_stages()
        return remaining[0] if remaining else None

    # ------------------------------------------------------------ budget
    def check_budget(self) -> None:
        budget = self.data.setdefault("budget", {})
        started = budget.get("session_start")
        if started is None:
            budget["session_start"] = time.time()
            started = budget["session_start"]
        limit = os.environ.get("QT_SDK_TASK_BUDGET_SEC")
        deadline = os.environ.get("QT_SDK_TASK_DEADLINE")
        exhausted, reason = False, ""
        if limit:
            try:
                if time.time() - float(started) > float(limit):
                    exhausted = True
                    reason = "QT_SDK_TASK_BUDGET_SEC=%s exceeded" % limit
            except ValueError:
                pass
        if not exhausted and deadline:
            try:
                hh, mm = deadline.split(":")
                now = time.localtime()
                if (now.tm_hour, now.tm_min) > (int(hh), int(mm)):
                    exhausted = True
                    reason = "past QT_SDK_TASK_DEADLINE=%s" % deadline
            except ValueError:
                pass
        if exhausted:
            budget["exhausted"] = True
            budget["reason"] = reason
            budget["checkpoint_steps"] = list(self.data.get("completed", []))
            self.data["next"] = {"action": "resume"}
            self.save()
            raise BudgetExhausted(
                "budget exhausted (%s); checkpoint saved, continue with "
                "`qt-sdk-run resume`" % reason)

    def reset_budget_session(self) -> None:
        budget = self.data.setdefault("budget", {})
        budget["session_start"] = time.time()
        budget["exhausted"] = False
        self.save()

    # ------------------------------------------------------------ commands
    def run_cmd(self, args, label: str, timeout: float = 600.0,
                cwd=None, extra_env: Optional[Dict[str, str]] = None,
                expect_rc: int = 0) -> CommandResult:
        """Run a command; stream full output to a log file, keep tail as
        in-state evidence. TIMEOUT is never PASS."""
        argv = list(args) if not isinstance(args, str) else args
        command_repr = argv if isinstance(argv, str) else \
            subprocess.list2cmdline([str(a) for a in argv])
        result = CommandResult(command=command_repr, label=label,
                               timeout=timeout, start_time=_now())
        log_name = "logs/%s-%s.log" % (
            time.strftime("%Y%m%d-%H%M%S"), _slug(label))
        log_path = self.state_dir / log_name
        log_path.parent.mkdir(parents=True, exist_ok=True)

        env = dict(os.environ)
        if extra_env:
            env.update({k: str(v) for k, v in extra_env.items()})

        start = time.time()
        lines = 0
        try:
            with log_path.open("w", encoding="utf-8", errors="replace") as log:
                log.write("$ %s\n# timeout=%s\n" % (command_repr, timeout))
                proc = subprocess.Popen(
                    argv if isinstance(argv, str) else [str(a) for a in argv],
                    cwd=str(cwd) if cwd else None, env=env,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, errors="replace",
                    shell=isinstance(argv, str))
                assert proc.stdout is not None
                for line in proc.stdout:
                    lines += 1
                    log.write(line)
                rc = proc.wait(timeout=max(1.0, timeout - (time.time() - start)))
                result.exit_code = rc
                result.status = "PASS" if rc == expect_rc else "FAIL"
        except subprocess.TimeoutExpired:
            proc.kill()
            result.status = "TIMEOUT"
        except FileNotFoundError as exc:
            result.stderr_tail = str(exc)
            result.status = "FAIL"
            result.exit_code = -1
        result.duration = round(time.time() - start, 2)
        result.log_lines = lines

        text = _safe_read(log_path)
        result.stdout_tail = _tail(text, TAIL_BYTES)
        result.evidence = log_name
        with log_path.open("a", encoding="utf-8") as log:
            log.write("\n# status=%s exit_code=%s duration=%.2fs lines=%d\n"
                      % (result.status, result.exit_code,
                         result.duration, lines))
        self.data.setdefault("commands", []).append(result.to_dict())
        # keep state.json bounded: last 200 commands
        self.data["commands"] = self.data["commands"][-200:]
        self.save()
        return result

    def record(self, result: CommandResult) -> None:
        self.data.setdefault("commands", []).append(result.to_dict())
        self.save()

    def skip_cmd(self, label: str, reason: str) -> CommandResult:
        result = CommandResult(command="", label=label, status="SKIP",
                               stderr_tail=reason, start_time=_now())
        self.data.setdefault("commands", []).append(result.to_dict())
        self.save()
        return result

    # ------------------------------------------------------------ helpers
    def section(self, name: str) -> Dict:
        return self.data.setdefault(name, {})

    @property
    def env_file(self) -> Path:
        return self.state_dir / "env.json"

    def env(self) -> Dict:
        if self.env_file.exists():
            return json.loads(self.env_file.read_text(encoding="utf-8"))
        return {}

    def env_set(self, key: str, value) -> None:
        cfg = self.env()
        cfg[key] = value
        self.env_file.parent.mkdir(parents=True, exist_ok=True)
        with file_lock(self.env_file):
            atomic_write(self.env_file, json.dumps(
                cfg, ensure_ascii=False, indent=2))

    def write_json(self, name: str, payload) -> Path:
        path = self.state_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2))
        return path

    def read_json(self, name: str, default=None):
        path = self.state_dir / name
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))


def load_state(home: Optional[Path] = None) -> ForgeState:
    return ForgeState(home)


def init_state(home: Optional[Path] = None) -> ForgeState:
    return ForgeState(home, create=True)


# ----------------------------------------------------------------- utils

def _check_stage(stage: str) -> None:
    if stage not in STAGES:
        raise ValueError("unknown stage %r (valid: %s)"
                         % (stage, ", ".join(STAGES)))


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _tail(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return "... [truncated]\n" + text[-limit:]
