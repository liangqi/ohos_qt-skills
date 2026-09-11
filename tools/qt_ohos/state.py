"""Migration state machine with checkpoint/resume, command evidence and
task budgets.

All persistent state lives in <project>/.qt-ohos/ :

    state.json          main state machine (stage / completed / next / gates)
    env.json            local environment configuration
    scan.json           project scan + risk report
    migration-plan.json generated migration plan
    changes.json        source tracking (every tracked edit)
    build.json          build/package evidence
    runtime.json        install/launch/smoke evidence
    report.md           final migration report
    logs/               command logs (evidence)
    originals/          pre-patch file copies (rollback / diff)
    patches/            generated unified patches

Design rules (borrowed from build_in_harmonyos):
- every command result is recorded as evidence; TIMEOUT is never PASS
- success is decided by tools (gates), not by the LLM
- on budget exhaustion the state carries checkpoint info for `resume`
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

STATE_DIR_NAME = ".qt-ohos"

# Ordered migration stages (checkpoint granularity).
STAGES = [
    "env_check",
    "project_scan",
    "qt_scan",
    "risk_scan",
    "dependency_scan",
    "assess",
    "plan",
    "project_generation",
    "source_patch",
    "compile",
    "package",
    "install",
    "launch",
    "smoke",
    "report",
    "knowledge",
]


class BudgetExhausted(RuntimeError):
    """Raised when the task budget / deadline is exceeded."""


@dataclass
class CommandResult:
    command: str
    start_time: str = ""
    duration: float = 0.0
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    timeout: Optional[float] = None
    status: str = "NOT_RUN"      # PASS / FAIL / TIMEOUT / SKIP / NOT_RUN
    evidence: str = ""            # relative path of the log inside .qt-ohos
    label: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class MigrationState:
    """State machine persisted in <project>/.qt-ohos/state.json."""

    def __init__(self, project_root: Path, create: bool = False):
        self.project_root = Path(project_root).resolve()
        self.state_dir = self.project_root / STATE_DIR_NAME
        self.state_file = self.state_dir / "state.json"
        self.data: Dict = {}
        if self.state_file.exists():
            self.data = json.loads(self.state_file.read_text(encoding="utf-8"))
        elif create:
            self.data = {
                "project": self.project_root.name,
                "created": _now(),
                "stage": None,
                "completed": [],
                "current": {"stage": None, "error": None},
                "next": {"action": "scan"},
                "qt": {"version": None},
                "ohos": {"api": None},
                "gates": {},
                "commands": [],
                "budget": {"exhausted": False, "checkpoint_steps": []},
            }
            self.save()
        else:
            raise FileNotFoundError(
                "no migration state found at %s (run `qt-ohos-run init` first)"
                % self.state_file)

    # ------------------------------------------------------------ basics
    @property
    def project(self) -> str:
        return self.data.get("project", self.project_root.name)

    def save(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.data["updated"] = _now()
        self.state_file.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ------------------------------------------------------------ stages
    def begin_stage(self, stage: str) -> None:
        _check_stage(stage)
        self.data["stage"] = stage
        self.data["current"] = {"stage": stage, "error": None}
        self.save()

    def complete_stage(self, stage: str, next_action: Optional[str] = None) -> None:
        _check_stage(stage)
        completed: List[str] = self.data.setdefault("completed", [])
        if stage not in completed:
            completed.append(stage)
        self.data["current"] = {"stage": stage, "error": None}
        if next_action:
            self.data["next"] = {"action": next_action}
        self.save()

    def fail_stage(self, stage: str, error: str, next_action: Optional[str] = None) -> None:
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
        """Enforce QT_OHOS_TASK_BUDGET_SEC / QT_OHOS_TASK_DEADLINE.

        Raises BudgetExhausted and records a checkpoint so that `resume`
        can continue from the completed steps.
        """
        budget = self.data.setdefault("budget", {})
        started = budget.get("session_start")
        if started is None:
            budget["session_start"] = time.time()
            started = budget["session_start"]

        limit = os.environ.get("QT_OHOS_TASK_BUDGET_SEC")
        deadline = os.environ.get("QT_OHOS_TASK_DEADLINE")
        exhausted = False
        reason = ""
        if limit:
            try:
                if time.time() - float(started) > float(limit):
                    exhausted = True
                    reason = "QT_OHOS_TASK_BUDGET_SEC=%s exceeded" % limit
            except ValueError:
                pass
        if not exhausted and deadline:
            try:
                hh, mm = deadline.split(":")
                now = time.localtime()
                if (now.tm_hour, now.tm_min) > (int(hh), int(mm)):
                    exhausted = True
                    reason = "past QT_OHOS_TASK_DEADLINE=%s" % deadline
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
                "`qt-ohos-run resume`" % reason)

    def reset_budget_session(self) -> None:
        budget = self.data.setdefault("budget", {})
        budget["session_start"] = time.time()
        budget["exhausted"] = False
        self.save()

    # ------------------------------------------------------------ commands
    def run_cmd(self, args, label: str, timeout: float = 600.0,
                cwd=None, expect_rc: int = 0) -> CommandResult:
        """Run a command, record it as evidence. TIMEOUT is never PASS."""
        if isinstance(args, str):
            # Windows: shell=True expects a single command string; splitting it
            # breaks paths with spaces (PROC5). POSIX: shlex split, no shell.
            if os.name == "nt":
                argv = args
            else:
                argv = shlex.split(args)
            command_repr = args
        else:
            argv = list(args)
            command_repr = " ".join(str(a) for a in argv)

        result = CommandResult(command=command_repr, label=label, timeout=timeout,
                               start_time=_now())
        log_name = "logs/%s-%s.log" % (time.strftime("%Y%m%d-%H%M%S"), _slug(label))
        log_path = self.state_dir / log_name
        log_path.parent.mkdir(parents=True, exist_ok=True)

        start = time.time()
        try:
            proc = subprocess.run(
                argv, cwd=str(cwd or self.project_root),
                capture_output=True, text=True, timeout=timeout,
                errors="replace", shell=isinstance(args, str) and os.name == "nt")
            result.exit_code = proc.returncode
            result.stdout = _clip(proc.stdout)
            result.stderr = _clip(proc.stderr)
            result.status = "PASS" if proc.returncode == expect_rc else "FAIL"
        except subprocess.TimeoutExpired as exc:
            result.stdout = _clip(_bytes_to_str(exc.stdout))
            result.stderr = _clip(_bytes_to_str(exc.stderr))
            result.status = "TIMEOUT"
        except FileNotFoundError as exc:
            result.stderr = str(exc)
            result.status = "FAIL"
            result.exit_code = -1
        result.duration = round(time.time() - start, 2)

        log_path.write_text(
            "$ %s\n# status=%s exit_code=%s duration=%.2fs timeout=%s\n"
            "--- stdout ---\n%s\n--- stderr ---\n%s\n" % (
                command_repr, result.status, result.exit_code, result.duration,
                timeout, result.stdout, result.stderr),
            encoding="utf-8")
        result.evidence = log_name
        self.data.setdefault("commands", []).append(result.to_dict())
        self.save()
        return result

    def skip_cmd(self, label: str, reason: str) -> CommandResult:
        result = CommandResult(command="", label=label, status="SKIP",
                               stderr=reason, start_time=_now())
        self.data.setdefault("commands", []).append(result.to_dict())
        self.save()
        return result

    # ------------------------------------------------------------ helpers
    def section(self, name: str) -> Dict:
        return self.data.setdefault(name, {})

    def write_json(self, name: str, payload) -> Path:
        path = self.state_dir / name
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        return path

    def read_json(self, name: str, default=None):
        path = self.state_dir / name
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))


def load_state(project_root) -> MigrationState:
    return MigrationState(Path(project_root))


def init_state(project_root) -> MigrationState:
    return MigrationState(Path(project_root), create=True)


# ----------------------------------------------------------------- utils

def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _check_stage(stage: str) -> None:
    if stage not in STAGES:
        raise ValueError("unknown stage %r (valid: %s)" % (stage, ", ".join(STAGES)))


def _slug(text: str) -> str:
    keep = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in text.strip())
    return keep.strip("-")[:48] or "cmd"


def _clip(text: str, limit: int = 20000) -> str:
    if text is None:
        return ""
    if len(text) > limit:
        return text[:limit] + "\n... [truncated %d chars]" % (len(text) - limit)
    return text


def _bytes_to_str(data) -> str:
    if data is None:
        return ""
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    return str(data)
