"""Cross-platform advisory file lock + atomic write.

Concurrency model (documented boundary of qt-sdk-forge):

- `file_lock` serialises *writers* of one file (state.json / registry.yaml /
  RELEASES.md) across processes on the same forge home.
- `atomic_write` (tmp file + os.replace) makes each write all-or-nothing, so
  concurrent *readers* never observe a torn file.
- Read-modify-write sequences (e.g. load_registry -> apply -> save_registry)
  are NOT covered by a single lock span; the documented contract is one
  forge process per home at a time. The lock prevents file corruption, not
  lost updates between parallel agents.

Windows: msvcrt.locking on a sidecar "<path>.lock" file.
POSIX:   fcntl.flock on the same sidecar file.
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path

try:
    import msvcrt

    def _lock_fd(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)

    def _unlock_fd(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)

except ImportError:                                   # POSIX
    import fcntl

    def _lock_fd(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock_fd(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)


class LockTimeout(RuntimeError):
    """Raised when a lock cannot be acquired within the timeout."""


@contextmanager
def file_lock(path, timeout: float = 10.0):
    """Advisory exclusive lock on `<path>.lock` for the duration of the
    `with` block. The lock file itself is not the protected content."""
    lock_path = Path(str(path) + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
    try:
        deadline = time.time() + timeout
        while True:
            try:
                _lock_fd(fd)
                break
            except OSError:
                if time.time() >= deadline:
                    raise LockTimeout(
                        "could not lock %s within %.1fs (another forge "
                        "process writing?)" % (lock_path, timeout))
                time.sleep(0.1)
        try:
            yield
        finally:
            _unlock_fd(fd)
    finally:
        os.close(fd)


def atomic_write(path, text: str) -> None:
    """Write text all-or-nothing: tmp file + os.replace.

    os.replace is atomic on POSIX and on Windows (since py3.3) even when
    the target exists, so readers see either the old or the new content.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    os.replace(tmp, path)
