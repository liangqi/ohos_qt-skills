"""Background clone+scan jobs: run asynchronously with queryable progress; the frontend can refresh or run them in the background at any time.

Job state lives in an in-process dict (_JOBS), advanced by a daemon thread:
  clone(8%) -> scan(45%) -> done(100%) / error.
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Dict, Optional

from . import cloner, db, project_scanner

_JOBS: Dict[str, Dict] = {}
_LOCK = threading.Lock()


def start_clone_job(url: str, name: Optional[str] = None) -> str:
    """Create and start a clone+scan job; return job_id."""
    job_id = uuid.uuid4().hex[:8]
    with _LOCK:
        _JOBS[job_id] = {
            "id": job_id, "url": url, "status": "running",
            "stage": "clone", "percent": 5,
            "message": "Cloning repository...", "result": None, "error": None,
            "created": time.time(),
        }
    t = threading.Thread(target=_run, args=(job_id, url, name), daemon=True)
    t.start()
    return job_id


def get_job(job_id: str) -> Optional[Dict]:
    with _LOCK:
        j = _JOBS.get(job_id)
        return dict(j) if j else None


def list_jobs() -> list:
    with _LOCK:
        return [dict(j) for j in _JOBS.values()]


def _set(job_id: str, **kw) -> None:
    with _LOCK:
        if job_id in _JOBS:
            _JOBS[job_id].update(kw)


def _run(job_id: str, url: str, name: Optional[str]) -> None:
    try:
        _set(job_id, stage="clone", percent=8,
             message="Running shallow clone (slow for large repositories)...")
        info = cloner.clone_repo(url, name)
        if not info.get("cloned"):
            _set(job_id, message="Directory already exists, reusing the local copy...")
        _set(job_id, stage="scan", percent=45,
             message="Clone finished, scanning source files and dependencies...")
        conn = db.connect()
        db.init_db(conn)
        try:
            scan = project_scanner.scan_project(conn, info["path"])
        finally:
            conn.close()
        _set(job_id, stage="done", status="done", percent=100,
             message="Done: %s (%d source files)" % (
                 scan.get("app_id"), scan.get("sources", 0)),
             result={"clone": info, "scan": scan})
    except Exception as exc:  # noqa: BLE001
        _set(job_id, stage="error", status="error", percent=100,
             message="Failed: %s" % exc, error=str(exc))
