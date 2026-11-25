"""Repository cloning: shallow-clone GitHub and other git repositories into workspace/ for scanning.

- Only http(s) URLs are allowed (local tool; prevents arbitrary command injection)
- Defaults to --depth 1 to avoid the full history of large repositories
- If the target directory already exists (with .git), reuse it instead of cloning again
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional

from . import WORKSPACE

_NAME_RE = re.compile(r"[^a-z0-9]+")


def repo_name_from_url(url: str) -> str:
    """https://github.com/owner/Repo(.git) -> repo (normalized to lowercase with hyphens)."""
    u = url.strip().rstrip("/")
    if u.endswith(".git"):
        u = u[:-4]
    last = u.split("/")[-1] or "repo"
    return _NAME_RE.sub("-", last.lower()).strip("-") or "repo"


def validate_url(url: str) -> Optional[str]:
    """Return an error message; return None if valid."""
    if not url or not re.match(r"^https?://", url.strip()):
        return "only http(s) git URLs are supported"
    if any(ch in url for ch in (";", "&", "|", "`", "$", "\n")):
        return "URL contains invalid characters"
    return None


def clone_repo(url: str, name: Optional[str] = None,
               depth: int = 1, timeout: int = 900) -> Dict:
    """Shallow-clone into workspace/<name> and shallow-initialize submodules.

    Returns {path, cloned, reason?}. Reuses an existing clone (cloned=False).
    Raises RuntimeError on failure.

    Submodules are fetched shallowly (--depth 1): for projects such as corpus_b the dependency
    manifests/framework live in submodules (corpus_b_deps, corpus_b_core); without initializing
    them no dependency declarations are found (confirmed by the e2e corpus_b review). Existing
    clones with uninitialized submodules are also backfilled.
    """
    err = validate_url(url)
    if err:
        raise RuntimeError(err)
    name = name or repo_name_from_url(url)
    name = _NAME_RE.sub("-", name.lower()).strip("-") or "repo"
    target = WORKSPACE / name
    if (target / ".git").exists() or any(target.glob("*")):
        _init_submodules(target, timeout)
        return {"path": str(target), "name": name, "cloned": False,
                "reason": "directory already exists, reusing the local copy"}
    target.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["git", "clone", "--depth", str(depth), url.strip(), str(target)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError("git clone timed out (>%ds): %s" % (timeout, url))
    if r.returncode != 0:
        tail = (r.stderr or "").strip().replace("\n", " ")[-400:]
        raise RuntimeError("git clone failed: %s" % (tail or "unknown error"))
    _init_submodules(target, timeout)
    return {"path": str(target), "name": name, "cloned": True}


def _init_submodules(target: Path, timeout: int) -> None:
    """Shallow-initialize submodules (skipped when there are none; warns on failure without blocking the clone)."""
    if not (target / ".gitmodules").is_file():
        return
    # --init must carry the -- prefix: a bare init is treated by git as a pathspec (regression:
    # the old bare init meant submodules of reused clones were never fetched,
    # so corpus_b lost scan coverage and deps were widely missed, silently with no error)
    cmd = ["git", "-C", str(target), "submodule", "update", "--init",
           "--depth", "1", "--recursive"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=max(timeout, 1800))
    except (subprocess.TimeoutExpired, OSError) as e:
        # Degrade when the network is restricted / submodule tooling is unavailable: scan only the main repo (visible warning)
        print("[cloner] submodule initialization degraded (%s): %s" % (type(e).__name__, e),
              file=sys.stderr)
        return
    if r.returncode != 0:
        tail = (r.stderr or "").strip().replace("\n", " ")[-300:]
        print("[cloner] submodule initialization failed (degrading to scanning only the main repo): %s" % (tail or "unknown"),
              file=sys.stderr)
