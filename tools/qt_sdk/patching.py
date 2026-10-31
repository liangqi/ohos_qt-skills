"""Patch registry + lifecycle: import -> apply -> built -> released, with
revert / export / supersede transitions.

External change proposals (the interface other agents use to request SDK
versions) live in <home>/.qtsdk/inbox/<proposal-id>/ :

    proposal.yaml   id / source / type / motivation / refs / base / ...
    patches/*.patch unified diffs relative to the qtbase submodule root
    notes.md        free-form reasoning from the source agent

Patch files are copied into .qtsdk/patches/P<nnnn>-<name>.patch and tracked
in .qtsdk/registry.yaml. All git operations run inside <src>/qtbase.

Patch types (see SKILL.md):
    diagnostic  [OHOS] logging for issue triage - banned from releases
    fix         framework fix destined for upstream
    backport    upstream fix applied locally ahead of a release
"""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from . import envcheck, yaml_lite
from .locking import atomic_write, file_lock
from .state import ForgeState

REGISTRY_NAME = "registry.yaml"
PATCH_TYPES = ("diagnostic", "fix", "backport")
PATCH_STATUSES = ("imported", "applied", "built", "released",
                  "superseded", "reverted")

_DIFF_FILE_RE = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)


# ---------------------------------------------------------------- registry

def registry_path(st: ForgeState) -> Path:
    return st.state_dir / REGISTRY_NAME


def load_registry(st: ForgeState) -> Dict:
    path = registry_path(st)
    if not path.exists():
        return {"patches": []}
    data = yaml_lite.parse(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict) or "patches" not in data:
        return {"patches": []}
    return data


def save_registry(st: ForgeState, data: Dict) -> None:
    path = registry_path(st)
    path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(path):
        atomic_write(path, yaml_lite.dump(data))


def _next_id(data: Dict) -> str:
    numbers = []
    for entry in data.get("patches", []):
        m = re.match(r"P(\d+)", str(entry.get("id", "")))
        if m:
            numbers.append(int(m.group(1)))
    return "P%04d" % (max(numbers, default=0) + 1)


def _patch_files(patch_text: str) -> List[str]:
    return _DIFF_FILE_RE.findall(patch_text)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def entries(st: ForgeState) -> List[Dict]:
    return load_registry(st).get("patches", [])


def by_id(st: ForgeState, patch_id: str) -> Optional[Dict]:
    for entry in entries(st):
        if str(entry.get("id")) == patch_id:
            return entry
    return None


def patch_file_of(st: ForgeState, entry: Dict) -> Optional[Path]:
    name = entry.get("file")
    if not name:
        return None
    path = st.state_dir / "patches" / name
    return path if path.exists() else None


# ---------------------------------------------------------------- import

def import_proposal(st: ForgeState, proposal_dir: Path) -> Dict:
    """Import an external change proposal: review + register + copy patches.

    Enforces the SKILL.md review rules that a tool can decide:
    - proposal.yaml must exist and carry refs (traceability gate)
    - patch files must exist and parse (contain '+++ b/' hunks)
    - type must be one of PATCH_TYPES
    """
    proposal_dir = Path(proposal_dir).resolve()
    meta_file = proposal_dir / "proposal.yaml"
    if not meta_file.is_file():
        return {"ok": False, "error": "proposal.yaml not found in %s"
                % proposal_dir}

    meta = yaml_lite.parse(meta_file.read_text(encoding="utf-8")) or {}
    ptype = str(meta.get("type", "")).lower()
    if ptype not in PATCH_TYPES:
        return {"ok": False,
                "error": "proposal type %r invalid (valid: %s)"
                % (meta.get("type"), ", ".join(PATCH_TYPES))}

    refs = meta.get("refs") or []
    if isinstance(refs, str):
        refs = [refs]
    if not refs:
        return {"ok": False,
                "error": "proposal has no refs - refuse to import "
                         "untraceable changes (SKILL.md discipline)"}

    patch_files = sorted((proposal_dir / "patches").glob("*.patch")) \
        if (proposal_dir / "patches").is_dir() else []
    if not patch_files:
        return {"ok": False, "error": "no *.patch files in proposal patches/"}

    texts = {p.name: p.read_text(encoding="utf-8", errors="replace")
             for p in patch_files}
    files: List[str] = []
    for name, text in texts.items():
        if "+++ b/" not in text:
            return {"ok": False,
                    "error": "%s does not look like a unified diff "
                             "(no '+++ b/' hunks)" % name}
        files.extend(_patch_files(text))

    data = load_registry(st)
    entry_id = _next_id(data)
    patch_store = st.state_dir / "patches"
    patch_store.mkdir(parents=True, exist_ok=True)

    copied: List[str] = []
    for src in patch_files:
        target = "%s-%s" % (entry_id, src.stem)
        shutil.copy2(src, patch_store / target)
        copied.append(target)

    entry = {
        "id": entry_id,
        "type": ptype,
        "status": "imported",
        "origin": str(meta.get("id") or proposal_dir.name),
        "source": str(meta.get("source", "")),
        "motivation": str(meta.get("motivation", "")),
        "refs": refs,
        "files": sorted(set(files)),
        "file": copied[0] if len(copied) == 1 else None,
        "files_multiple": copied if len(copied) > 1 else None,
        "sha256": {name: _sha256(patch_store / name) for name in copied},
        "base": str(meta.get("base", "")),
        "base_commit": None,
        "imported": _timestamp(),
        "upstream": None,
        "retire_when": str(meta.get("retire_when", "")),
        "note": "",
    }
    data["patches"].append(entry)
    save_registry(st, data)
    st.section("patches_imported")   # touch state for observability
    st.save()

    return {"ok": True, "id": entry_id, "entry": entry,
            "review_hints": _review_hints(entry)}


def _review_hints(entry: Dict) -> List[str]:
    """LLM-facing reminders for the review step (SKILL.md Step 2)."""
    hints = []
    if entry["type"] == "diagnostic":
        hints.append("diagnostic patch: allowed in test builds only; "
                     "releases require --allow-diagnostic")
    hints.append("verify the patch only touches files listed in `files` "
                 "(framework-issue-analysis §4.5 cleanup rule)")
    hints.append("load knowledge pages referenced by refs before building")
    return hints


# ---------------------------------------------------------------- apply

def apply(st: ForgeState, patch_id: str) -> Dict:
    """git apply --check then git apply inside <src>/qtbase."""
    entry = by_id(st, patch_id)
    if not entry:
        return {"ok": False, "error": "unknown patch %s" % patch_id}
    if entry.get("status") in ("applied", "built", "released"):
        return {"ok": False,
                "error": "patch %s already %s" % (patch_id,
                                                  entry.get("status"))}

    src = _qt_src(st)
    if not src:
        return {"ok": False, "error": "qt_src not configured "
                                      "(`config set qt_src <path>`)"}
    patch = patch_file_of(st, entry)
    if patch is None and not entry.get("files_multiple"):
        return {"ok": False, "error": "patch file missing for %s" % patch_id}

    patches = ([patch_file_of(st, entry)] if patch else []) or \
        [st.state_dir / "patches" / n for n in entry.get("files_multiple", [])]

    for p in patches:
        check = st.run_cmd(["git", "apply", "--check", str(p)],
                           "patch-check-%s" % patch_id, cwd=src)
        if check.status != "PASS":
            return {"ok": False, "error": "git apply --check failed for %s "
                    "(conflict or already applied?); see %s"
                    % (p.name, check.evidence)}
        applied = st.run_cmd(["git", "apply", str(p)],
                             "patch-apply-%s" % patch_id, cwd=src)
        if applied.status != "PASS":
            return {"ok": False, "error": "git apply failed; see %s"
                    % applied.evidence}

    entry["status"] = "applied"
    entry["base_commit"] = envcheck.run_git(
        ["rev-parse", "HEAD"], src).stdout.strip()
    _update_entry(st, entry)
    return {"ok": True, "id": patch_id, "base_commit": entry["base_commit"]}


def revert(st: ForgeState, patch_id: str) -> Dict:
    """git apply -R inside <src>/qtbase; status -> reverted."""
    entry = by_id(st, patch_id)
    if not entry:
        return {"ok": False, "error": "unknown patch %s" % patch_id}
    if entry.get("status") not in ("applied", "built"):
        return {"ok": False, "error": "patch %s is not applied "
                                      "(status=%s)" % (patch_id,
                                                       entry.get("status"))}
    src = _qt_src(st)
    patch = patch_file_of(st, entry)
    patches = ([patch] if patch else []) or \
        [st.state_dir / "patches" / n for n in entry.get("files_multiple", [])]
    for p in patches:
        res = st.run_cmd(["git", "apply", "-R", str(p)],
                         "patch-revert-%s" % patch_id, cwd=src)
        if res.status != "PASS":
            return {"ok": False, "error": "git apply -R failed; see %s"
                    % res.evidence}
    entry["status"] = "reverted"
    _update_entry(st, entry)
    return {"ok": True, "id": patch_id}


def mark_status(st: ForgeState, patch_id: str, status: str) -> Dict:
    if status not in PATCH_STATUSES:
        return {"ok": False, "error": "invalid status %r" % status}
    entry = by_id(st, patch_id)
    if not entry:
        return {"ok": False, "error": "unknown patch %s" % patch_id}
    entry["status"] = status
    _update_entry(st, entry)
    return {"ok": True}


def export(st: ForgeState, patch_id: str, dest: Path) -> Dict:
    """Copy the stored (already cleaned upstream-style) patch to dest/."""
    entry = by_id(st, patch_id)
    if not entry:
        return {"ok": False, "error": "unknown patch %s" % patch_id}
    patch = patch_file_of(st, entry)
    patches = [patch] if patch else \
        [st.state_dir / "patches" / n for n in entry.get("files_multiple", [])]
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for p in patches:
        target = dest / p.name
        shutil.copy2(p, target)
        out.append(str(target))
    return {"ok": True, "exported": out}


def _update_entry(st: ForgeState, entry: Dict) -> None:
    data = load_registry(st)
    for i, item in enumerate(data.get("patches", [])):
        if str(item.get("id")) == str(entry["id"]):
            data["patches"][i] = entry
            break
    save_registry(st, data)


def _qt_src(st: ForgeState) -> Optional[Path]:
    src = st.env().get("qt_src") or ""
    path = Path(src) if src else None
    if path and (path / "qtbase").is_dir():
        return path / "qtbase"
    return None


def applied_entries(st: ForgeState) -> List[Dict]:
    return [e for e in entries(st)
            if e.get("status") in ("applied", "built", "released")]


def applied_files(st: ForgeState) -> List[str]:
    files: List[str] = []
    for entry in applied_entries(st):
        files.extend(entry.get("files", []))
    return sorted(set(files))


def _timestamp() -> str:
    import time
    return time.strftime("%Y-%m-%d %H:%M:%S")
