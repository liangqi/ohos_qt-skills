"""Qt source tree operations: clone, inspect (SV1), upstream evolution check.

Python replacement of clone-qt-src.sh. The Qt 5 harmony branches are
super-repositories (tqtc-qt5) where qtbase / qtohosextras are submodules.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Dict, List, Optional

from . import envcheck
from .state import ForgeState

# Branch layout of the harmony ports (see ENV.md "source acquisition").
COMMERCIAL_REPO = "https://codereview.qt-project.org/qt/tqtc-qt5"
OPENSOURCE_REPO = "https://gitcode.com/ohos-qt/qt-harmonyos-src"

BRANCHES = {
    "5.12": "tqtc/harmonyos-5.12.12",
    "5.15": "tqtc/harmonyos-5.15.16",
}

# The GitCode opensource mirror does NOT carry the tqtc/* branch names.
# Its plain snapshots (`main` / `5.12.12`) additionally carry Windows CRLF
# line endings and lost executable bits (initial import), which break POSIX
# configure (QOH037). The `build/macos-arm64-*` branches are the POSIX
# build branches (LF endings + build-enabling warning-suppression patches)
# that produced the official prebuilt SDKs - the correct default for
# macOS/Linux source builds even though they are named "macos".
OPENSOURCE_BRANCHES = {
    "5.12": "build/macos-arm64-qt5.12.12",
}

# Directories whose changes matter most for the OHOS port (upstream report).
WATCH_DIRS = [
    "qtbase/src/plugins/platforms/ohos",
    "qtbase/src/harmonyos",
    "qtohosextras",
]


def clone(method: str, version: str, dest: Path,
          user: str = "", password: str = "", branch: str = "",
          timeout: float = 7200.0) -> Dict:
    """Clone a Qt harmony branch + submodules. method: commercial|opensource.

    opensource defaults to the GitCode mirror's POSIX build branch
    (OPENSOURCE_BRANCHES); override with `branch` at your own risk - the
    plain `main`/`5.12.12` snapshots are CRLF + non-exec and fail on
    macOS/Linux (QOH037)."""
    if version not in BRANCHES:
        raise ValueError("unsupported version %r (valid: %s)"
                         % (version, ", ".join(BRANCHES)))
    if method == "opensource":
        branch = branch or OPENSOURCE_BRANCHES.get(version) or BRANCHES[version]
    else:
        branch = branch or BRANCHES[version]
    if method == "commercial":
        repo = COMMERCIAL_REPO
        if user and password:
            # credentials stay in-memory for this command only
            repo = "https://%s:%s@%s" % (user, password, repo.split("://", 1)[1])
    elif method == "opensource":
        repo = OPENSOURCE_REPO
    else:
        raise ValueError("method must be commercial or opensource")

    dest.parent.mkdir(parents=True, exist_ok=True)
    res = {"steps": [], "dest": str(dest)}
    import subprocess
    for label, args in (
            ("clone", ["git", "clone", "--branch", branch, "--single-branch",
                       repo, str(dest)]),
            ("submodules", ["git", "submodule", "update", "--init",
                            "--recursive"]),
    ):
        cwd = dest if label == "submodules" else dest.parent
        proc = subprocess.run(args, cwd=str(cwd), timeout=timeout,
                              capture_output=True, text=True, errors="replace")
        res["steps"].append({"step": label, "rc": proc.returncode,
                             "tail": (proc.stderr or proc.stdout)[-2000:]})
        if proc.returncode != 0:
            res["ok"] = False
            return res
    # strip credentials from the remote URL (kb-init safety note)
    if method == "commercial":
        subprocess.run(["git", "remote", "set-url", "origin",
                        COMMERCIAL_REPO], cwd=str(dest),
                       capture_output=True, text=True)
    res["ok"] = bool((dest / "qtbase").is_dir())
    if not res["ok"]:
        return res

    # ---- POSIX post-clone fixups (opensource mirror quirks, QOH037) ----
    if os.name != "nt":
        crlf = _crlf_check(dest / "qtbase" / "configure")
        res["steps"].append({"step": "crlf_check", "rc": 0 if not crlf else 1,
                             "tail": ("qtbase/configure uses CRLF line "
                                      "endings - `sh configure` will fail "
                                      "(bad interpreter: /bin/sh^M). Re-clone "
                                      "with the default POSIX build branch "
                                      "(OPENSOURCE_BRANCHES)."
                                      if crlf else "LF ok")})
        if crlf:
            res["ok"] = False
            return res
        fixed = _restore_exec_bits(dest)
        res["steps"].append({"step": "exec_bits", "rc": 0,
                             "tail": ("restored +x on %d shebang scripts"
                                      % fixed) if fixed else "already ok"})
    return res


def _crlf_check(script: Path) -> bool:
    """True if the file carries CRLF line endings (Windows snapshots)."""
    try:
        with script.open("rb") as fh:
            return b"\r\n" in fh.read(4096)
    except OSError:
        return False


def _restore_exec_bits(dest: Path) -> int:
    """The opensource mirror's initial import stored every file as 100644,
    so `sh qtbase/configure` dies with 'Permission denied' (QOH037).
    Restore +x on all shebang scripts and record it as a git commit so the
    working tree stays clean for the SV1 unregistered-changes gate."""
    import subprocess
    ls = subprocess.run(["git", "ls-files"], cwd=str(dest),
                        capture_output=True, text=True, errors="replace")
    fixed: List[str] = []
    for rel in ls.stdout.splitlines():
        path = dest / rel
        try:
            with path.open("rb") as fh:
                shebang = fh.read(2) == b"#!"
            if shebang and not os.access(path, os.X_OK):
                path.chmod(path.stat().st_mode | 0o111)
                fixed.append(rel)
        except OSError:
            continue
    if not fixed:
        return 0
    for i in range(0, len(fixed), 200):          # dodge ARG_MAX
        batch = fixed[i:i + 200]
        subprocess.run(["git", "update-index", "--chmod=+x", "--"] + batch,
                       cwd=str(dest), capture_output=True, text=True)
    # -c identity guards: fresh machines without user.name/email would
    # otherwise fail the commit silently and leave a dirty tree for SV1
    subprocess.run(["git", "-c", "user.name=qt-sdk-forge",
                    "-c", "user.email=qt-sdk-forge@localhost",
                    "commit", "-q", "-m",
                    "fix: restore executable bits lost in initial import "
                    "(shebang scripts) [auto: qt-sdk-forge src-clone]"],
                   cwd=str(dest), capture_output=True, text=True)
    return len(fixed)


def inspect(src: Path) -> Dict:
    """SV1: branch / commit / submodule state / dirty files of the tree."""
    info: Dict = {"src": str(src), "valid": (src / "qtbase").is_dir()}
    if not info["valid"]:
        return info

    def git(*args, cwd):
        return envcheck.run_git(list(args), cwd=cwd)

    # super-repo + qtbase submodule each report their own HEAD
    out = git("rev-parse", "--abbrev-ref", "HEAD", cwd=src).stdout.strip()
    info["branch"] = out or None
    info["commit"] = git("rev-parse", "HEAD", cwd=src).stdout.strip() or None

    qtbase = src / "qtbase"
    info["qtbase_commit"] = git("rev-parse", "HEAD",
                                cwd=qtbase).stdout.strip() or None

    sub = git("submodule", "status", "--recursive", cwd=src).stdout
    uninit = [l.split()[1] for l in sub.splitlines()
              if l.startswith("-")]          # "-<sha> <path>" = not initialised
    info["uninitialised_submodules"] = uninit

    dirty = git("status", "--porcelain", cwd=qtbase).stdout.splitlines()
    info["qtbase_dirty"] = sorted(
        _parse_status_line(l) for l in dirty if l.strip())
    return info


def _parse_status_line(line: str) -> str:
    # "XY <path>" -> path (rename entries: "R  old -> new" keep new)
    path = line[3:].strip()
    return path.split(" -> ")[-1]


def upstream_check(src: Path, applied_patch_files: List[str],
                   st: Optional[ForgeState] = None,
                   timeout: float = 900.0) -> Dict:
    """Fetch upstream, list new commits, overlap them with the patch stack.

    Returns facts only; the LLM (per SKILL.md §7) reads the report and
    classifies changes into capability / fix / breaking / conflict.
    """
    info = {"src": str(src), "watch_dirs": WATCH_DIRS}
    if not (src / "qtbase").is_dir():
        info["error"] = "invalid source tree"
        return info

    branch = envcheck.run_git(
        ["rev-parse", "--abbrev-ref", "HEAD"], src).stdout.strip()
    info["branch"] = branch

    runner = st.run_cmd if st else _no_state_runner()
    fetch = runner(["git", "fetch", "--quiet", "origin"], "git-fetch",
                   timeout=timeout, cwd=src)
    info["fetch"] = {"status": fetch.status, "rc": fetch.exit_code}
    if fetch.status != "PASS":
        return info

    log = envcheck.run_git(
        ["log", "--oneline", "--no-decorate", "-50",
         "HEAD..origin/%s" % branch], src).stdout.strip()
    info["new_commits"] = [l for l in log.splitlines() if l.strip()]

    # per-commit file overlap with locally applied patches
    overlap: Dict[str, List[str]] = {}
    patch_files = set(applied_patch_files)
    for line in info["new_commits"]:
        sha = line.split(maxsplit=1)[0]
        files_out = envcheck.run_git(
            ["diff-tree", "--no-commit-id", "--name-only", "-r", sha],
            src).stdout.split()
        hit = sorted(patch_files & set(files_out))
        if hit:
            overlap[line] = hit
    info["patch_overlap"] = overlap

    watch_hits = []
    for line in info["new_commits"]:
        sha = line.split(maxsplit=1)[0]
        files_out = envcheck.run_git(
            ["diff-tree", "--no-commit-id", "--name-only", "-r", sha],
            src).stdout.split()
        if any(f.startswith(w) or w in f for w in WATCH_DIRS
               for f in files_out):
            watch_hits.append(line)
    info["watch_dir_commits"] = watch_hits
    return info


class _NoStateRunner:
    """Fallback when no ForgeState exists: plain subprocess run."""

    def run_cmd(self, args, label, timeout=600.0, cwd=None, **kw):
        import subprocess
        from .state import CommandResult
        result = CommandResult(command=" ".join(str(a) for a in args),
                               label=label, timeout=timeout,
                               start_time=time.strftime("%Y-%m-%d %H:%M:%S"))
        try:
            proc = subprocess.run([str(a) for a in args], cwd=str(cwd),
                                  capture_output=True, text=True,
                                  errors="replace", timeout=timeout)
            result.exit_code = proc.returncode
            result.status = "PASS" if proc.returncode == 0 else "FAIL"
            result.stdout_tail = (proc.stdout or "")[-2000:]
            result.stderr_tail = (proc.stderr or "")[-2000:]
        except Exception as exc:                          # noqa: BLE001
            result.status = "FAIL"
            result.stderr_tail = str(exc)
        return result


def _no_state_runner():
    return _NoStateRunner()
