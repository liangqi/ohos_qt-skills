"""Source tracking + patch solidification.

Keeps the original of every modified file (for rollback and diffing),
records every change in changes.json, and can solidify all changes into
unified patch files:

    patches/0001-<category>.patch

This answers: "what did we actually change for HarmonyOS?"
"""

from __future__ import annotations

import difflib
import json
import re
import time
from pathlib import Path
from typing import Dict, List

CHANGES_FILE = "changes.json"


class ChangeTracker:
    def __init__(self, state):
        self.state = state
        self.state_dir = state.state_dir
        self.originals_dir = self.state_dir / "originals"
        self.patches_dir = self.state_dir / "patches"
        self.changes_file = self.state_dir / CHANGES_FILE

    # ------------------------------------------------------------ tracking
    def _load(self) -> List[Dict]:
        if self.changes_file.exists():
            return json.loads(self.changes_file.read_text(encoding="utf-8"))
        return []

    def _save(self, changes: List[Dict]) -> None:
        self.changes_file.write_text(
            json.dumps(changes, ensure_ascii=False, indent=2), encoding="utf-8")

    def track(self, rel_path: str, original: str, modified: str,
              source: str, description: str) -> Dict:
        """Record a change; stores the first original copy for rollback."""
        orig_copy = self.originals_dir / rel_path
        if not orig_copy.exists():
            orig_copy.parent.mkdir(parents=True, exist_ok=True)
            orig_copy.write_text(original, encoding="utf-8")

        hunk_count = sum(1 for line in difflib.unified_diff(
            original.splitlines(), modified.splitlines())
            if line.startswith("@@"))
        entry = {
            "file": rel_path,
            "source": source,           # rule id / fix id / manual
            "description": description,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "added_lines": _count_diff(original, modified, "+"),
            "removed_lines": _count_diff(original, modified, "-"),
            "hunks": hunk_count,
        }
        changes = self._load()
        changes.append(entry)
        self._save(changes)
        return entry

    def all_changes(self) -> List[Dict]:
        return self._load()

    # ------------------------------------------------------------ output
    def generate_patches(self) -> List[str]:
        """Group changes by source category and write unified patches."""
        self.patches_dir.mkdir(parents=True, exist_ok=True)
        groups: Dict[str, List[str]] = {}
        for change in self._load():
            category = _slug(change.get("source", "misc"))
            rel = change["file"]
            orig_path = self.originals_dir / rel
            work_path = self.state.project_root / rel
            if not orig_path.exists() or not work_path.exists():
                continue
            original = orig_path.read_text(encoding="utf-8", errors="replace")
            modified = work_path.read_text(encoding="utf-8", errors="replace")
            diff = "".join(difflib.unified_diff(
                original.splitlines(keepends=True),
                modified.splitlines(keepends=True),
                fromfile="a/%s" % rel, tofile="b/%s" % rel))
            if diff:
                groups.setdefault(category, []).append(diff)

        written = []
        for idx, (category, diffs) in enumerate(sorted(groups.items()), 1):
            patch_path = self.patches_dir / ("%04d-%s.patch" % (idx, category))
            patch_path.write_text("".join(diffs), encoding="utf-8")
            written.append(patch_path.relative_to(self.state_dir).as_posix())
        return written

    def rollback(self) -> List[str]:
        restored = []
        for change in self._load():
            rel = change["file"]
            orig_path = self.originals_dir / rel
            work_path = self.state.project_root / rel
            if orig_path.exists() and work_path.exists():
                work_path.write_text(orig_path.read_text(encoding="utf-8"),
                                     encoding="utf-8")
                restored.append(rel)
        return restored


def _count_diff(original: str, modified: str, sign: str) -> int:
    count = 0
    for line in difflib.unified_diff(original.splitlines(), modified.splitlines()):
        if line.startswith(sign) and not line.startswith(sign * 3):
            count += 1
    return count


def _slug(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", str(text)).strip("-").lower()
    return text[:32] or "misc"
