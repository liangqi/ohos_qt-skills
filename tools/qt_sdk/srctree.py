"""Qt source tree operations: clone, inspect (SV1), upstream evolution check.

Python replacement of clone-qt-src.sh. The Qt 5 harmony branches are
super-repositories (tqtc-qt5) where qtbase / qtohosextras are submodules.
"""

from __future__ import annotations

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

# Directories whose changes matter most for the OHOS port (upstream report).
WATCH_DIRS = [
    "qtbase/src/plugins/platforms/ohos",
    "qtbase/src/harmonyos",
    "qtohosextras",
]


def clone(method: str, version: str, dest: Path,
          user: str = "", password: str = "",
          timeout: float = 7200.0) -> Dict:
    """Clone a Qt harmony branch + submodules. method: commercial|opensource."""
    if version not in BRANCHES:
        raise ValueError("unsupported version %r (valid: %s)"
                         % (version, ", ".join(BRANCHES)))
    branch = BRANCHES[version]
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
    return res


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
        "rev-parse", "--abbrev-ref", "HEAD", cwd=src).stdout.strip()
    info["branch"] = branch

    runner = st.run_cmd if st else _no_state_runner()
    fetch = runner(["git", "fetch", "--quiet", "origin"], "git-fetch",
                   timeout=timeout, cwd=src)
    info["fetch"] = {"status": fetch.status, "rc": fetch.exit_code}
    if fetch.status != "PASS":
        return info

    log = envcheck.run_git(
        "log", "--oneline", "--no-decorate", "-50",
        "HEAD..origin/%s" % branch, cwd=src).stdout.strip()
    info["new_commits"] = [l for l in log.splitlines() if l.strip()]

    # per-commit file overlap with locally applied patches
    overlap: Dict[str, List[str]] = {}
    patch_files = set(applied_patch_files)
    for line in info["new_commits"]:
        sha = line.split(maxsplit=1)[0]
        files_out = envcheck.run_git(
            "diff-tree", "--no-commit-id", "--name-only", "-r", sha,
            cwd=src).stdout.split()
        hit = sorted(patch_files & set(files_out))
        if hit:
            overlap[line] = hit
    info["patch_overlap"] = overlap

    watch_hits = []
    for line in info["new_commits"]:
        sha = line.split(maxsplit=1)[0]
        files_out = envcheck.run_git(
            "diff-tree", "--no-commit-id", "--name-only", "-r", sha,
            cwd=src).stdout.split()
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
