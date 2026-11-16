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

import base64
import json
import locale
import os
import shlex
import shutil
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

    def invalidate_scan_stages(self) -> List[str]:
        """配置变更后让扫描类阶段失效，返回被撤销的阶段名。

        扫描结论是 env.json 的函数（qt_version / bundle_name / sdk 路径都会
        改变判定），配置一改就得重算；否则用户必须记得加 `--force`，
        而"忘了加"的后果是拿着旧结论继续往下走。
        """
        scan_stages = ("env_check", "project_scan", "qt_scan", "risk_scan",
                       "dependency_scan")
        completed: List[str] = self.data.setdefault("completed", [])
        dropped = [stage for stage in scan_stages if stage in completed]
        for stage in dropped:
            completed.remove(stage)
        if dropped:
            self.save()
        return dropped

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
                cwd=None, expect_rc: int = 0,
                extra_env: Optional[Dict[str, str]] = None) -> CommandResult:
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
            child_env = None
            if extra_env:
                child_env = dict(os.environ)
                child_env.update({k: str(v) for k, v in extra_env.items()
                                  if v is not None})
            proc = subprocess.run(
                argv, cwd=str(cwd or self.project_root),
                capture_output=True, timeout=timeout, env=child_env,
                shell=isinstance(args, str) and os.name == "nt")
            result.exit_code = proc.returncode
            # 不要 text=True：它按 locale（中文 Windows = cp936）解码 UTF-8 的
            # 子进程输出，日志里就是乱码。统一 utf-8 优先、locale 兜底。
            result.stdout = _clip(_decode_output(proc.stdout))
            result.stderr = _clip(_decode_output(proc.stderr))
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

    def hdc_pull(self, remote: str, local, timeout: float = 120.0,
                 hdc: str = "hdc"):
        """Pull a device file, and verify it actually landed.

        `hdc file recv` returns 0 while creating nothing (sandboxed paths,
        permission errors on the device side) — a pure return-code check then
        reports "取了截图" with an empty file. So: recv, stat, and fall back to
        `shell base64`, which returns the bytes on stdout.

        Returns (ok, channel, detail).
        """
        target = Path(local)
        target.parent.mkdir(parents=True, exist_ok=True)
        name = Path(remote).name
        first = self.run_cmd([hdc, "file", "recv", remote, str(target)],
                             "hdc-pull:%s" % name, timeout=timeout)
        if first.status == "PASS" and target.is_file() and target.stat().st_size:
            return True, "file-recv", str(target)
        second = self.run_cmd([hdc, "shell", "base64 %s" % remote],
                              "hdc-pull-b64:%s" % name, timeout=timeout)
        if second.status == "PASS" and second.stdout.strip():
            try:
                payload = base64.b64decode("".join(second.stdout.split()))
            except Exception as exc:                 # noqa: BLE001
                return False, "", "base64 解码失败：%s" % exc
            if payload:
                target.write_bytes(payload)
                return True, "shell-base64", str(target)
        return False, "", ("hdc file recv 未落文件（rc=%s），base64 兜底也失败"
                           % first.exit_code)

    def skip_cmd(self, label: str, reason: str) -> CommandResult:
        result = CommandResult(command="", label=label, status="SKIP",
                               stderr=reason, start_time=_now())
        self.data.setdefault("commands", []).append(result.to_dict())
        self.save()
        return result

    def fail_cmd(self, label: str, reason: str) -> CommandResult:
        """记录一条"没跑但确实不合格"的命令（与 SKIP 的"没测"区分开）。"""
        result = CommandResult(command="", label=label, status="FAIL",
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
        """读状态文件。损坏时告警并按缺省处理，不让整条命令崩在 traceback 上。

        中断的运行会留下半截 json（build.json / scan.json）。此前这种情况
        每个子命令都直接抛 JSONDecodeError；现在按"没有这条证据"处理（门禁
        因此只会更保守），并把重建方法打出来。
        """
        path = self.state_dir / name
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            print("[qt-ohos-run] WARNING: %s 解析失败（%s），按缺失处理；"
                  "需要重建就删除该文件后重跑对应步骤"
                  % (path.name, str(exc)[:80]))
            return default


def load_state(project_root) -> MigrationState:
    root = Path(project_root)
    state_file = root / STATE_DIR_NAME / "state.json"
    if state_file.exists():
        try:
            json.loads(state_file.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise SystemExit(
                "[qt-ohos-run] %s 已损坏（%s）。\n"
                "  恢复方式：备份并删除 %s 后重新 `init` + `scan`（.qt-ohos/logs 与 "
                "patches 不会丢）" % (state_file, str(exc)[:80], state_file))
    return MigrationState(root)


def init_state(project_root) -> MigrationState:
    return MigrationState(Path(project_root), create=True)


# ----------------------------------------------------------------- utils

def native_path(value, base=None) -> str:
    """Absolute, host-native path string.

    Windows `hdc` / `hvigor` 不认 POSIX 风格的相对路径：`hdc install -r
    build/x.hap` 拼出来的却是 `<当前目录>/C:/<用户>/.../build/x.hap`，
    设备侧报 `no such file or directory`。统一在这里转成宿主的绝对路径
    （Windows 上 os.path.abspath 会给出反斜杠形式）。
    """
    path = Path(str(value))
    if not path.is_absolute():
        path = Path(base or os.getcwd()) / path
    return os.path.abspath(os.path.expanduser(str(path)))


def find_hdc() -> str:
    """hdc 在 DevEco/CLI 的 toolchains 里，不一定在 PATH 上。"""
    found = shutil.which("hdc") or shutil.which("hdc.exe")
    return found or "hdc"


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


def _decode_output(data) -> str:
    """子进程输出解码：UTF-8 优先，失败退回 locale（cp936 等），最后 replace。"""
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    candidates = ["utf-8"]
    try:
        preferred = locale.getpreferredencoding(False)
    except Exception:                      # pragma: no cover - 平台缺 locale
        preferred = ""
    for encoding in (preferred, "gb18030", "cp1252"):
        if encoding and encoding.lower() not in ("utf-8", "utf8") \
                and encoding not in candidates:
            candidates.append(encoding)
    for encoding in candidates:
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")


def _bytes_to_str(data) -> str:
    if data is None:
        return ""
    if isinstance(data, bytes):
        return _decode_output(data)
    return str(data)
