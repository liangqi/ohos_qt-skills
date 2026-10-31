"""Version release / manifest / ENV switch.

Version scheme (SKILL.md):  <qtver>+p<N>.<yyyymmdd>
    N = number of locally applied patches (patch generation) - the version
    number itself encodes traceability; SV6 enforces manifest == git diff.

Release types:
    release  diagnostic patches are rejected unless --allow-diagnostic
    test     temporary build to validate one change (any patch types)
"""

from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

from . import building, envcheck, patching, yaml_lite
from .locking import file_lock
from .state import ForgeState

RELEASES_DIR = "releases"
RELEASES_INDEX = "RELEASES.md"

ENV_SDK_VAR = {"5.12": "QT5_12_OHOS_SDK",
               "5.15": "QT5_15_OHOS_SDK",
               "6.12": "QT6_OHOS_SDK"}

_ENV_ROW_TMPL = "| `%s` | `%s` |"


def version_of(qt_version: str, patch_count: int,
               date: Optional[str] = None) -> str:
    return "%s+p%d.%s" % (qt_version, patch_count,
                          date or time.strftime("%Y%m%d"))


def parse_version(ver: str) -> Dict:
    # NOTE: release() appends a same-day sequence suffix ".N" when a version
    # is cut twice on one day (e.g. 5.15+p1.20261009.2); accept it here so a
    # legitimate same-day second cut does not fail its own SV6 gate.
    m = re.match(r"^(\d+\.\d+)\+p(\d+)\.(\d{8})(?:\.(\d+))?$", ver.strip())
    if not m:
        raise ValueError("bad version %r (expected <qtver>+p<N>.<yyyymmdd>[.N])"
                         % ver)
    return {"qt": m.group(1), "patches": int(m.group(2)),
            "date": m.group(3)}


# ---------------------------------------------------------------- release

def release(st: ForgeState, note: str = "", release_type: str = "release",
            allow_diagnostic: bool = False,
            smoke: Optional[Dict] = None) -> Dict:
    """Cut a version: manifest + SHA256 chain + RELEASES.md entry.

    Gates enforced here (SV6 pre-check, tool-decided facts):
    - applied patch set == version patch generation
    - diagnostic patches blocked in `release` type builds
    """
    try:
        ctx = building.build_ctx(st)
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)}
    qt_version = ctx.get("qt_version")
    sdk_dir = Path(ctx.get("sdk_dir") or "")
    if not qt_version or not sdk_dir.is_dir():
        return {"ok": False,
                "error": "no installed SDK context - run install first"}

    applied = patching.applied_entries(st)
    for entry in applied:
        if (entry.get("type") == "diagnostic" and release_type == "release"
                and not allow_diagnostic):
            return {"ok": False,
                    "error": "patch %s (%s) is diagnostic; test-only. "
                             "Revert it, or use --type test / "
                             "--allow-diagnostic"
                             % (entry["id"], entry.get("motivation", ""))}

    # manifest must reflect the real git diff of qtbase (SV6 basis)
    src = Path(st.env().get("qt_src") or "")
    qtbase = src / "qtbase" if src else None
    dirty = []
    if qtbase and qtbase.is_dir():
        out = envcheck.run_git(["status", "--porcelain"], qtbase).stdout
        dirty = sorted(l[3:].strip().split(" -> ")[-1]
                       for l in out.splitlines() if l.strip())
    registered = patching.applied_files(st)
    unregistered = [f for f in dirty if f not in registered]
    if unregistered:
        return {"ok": False,
                "error": "unregistered working-tree changes in qtbase: %s - "
                         "register them (patch-import) or revert before "
                         "releasing" % unregistered[:10]}

    ver = version_of(qt_version, len(applied))
    existing = _manifest_path(st, ver)
    if existing.exists():
        # same-day second cut: bump a sequence suffix
        seq = 2
        while _manifest_path(st, "%s.%d" % (ver, seq)).exists():
            seq += 1
        ver = "%s.%d" % (ver, seq)

    manifest = {
        "version": ver,
        "type": release_type,
        "qt_version": qt_version,
        "render": ctx.get("render"),
        "build_type": ctx.get("build_type"),
        "sdk_dir": str(sdk_dir),
        "build_dir": ctx.get("build_dir"),
        "base_commit": patching.applied_entries(st) and
        patching.applied_entries(st)[0].get("base_commit") or
        (envcheck.run_git(["rev-parse", "HEAD"], qtbase).stdout.strip()
         if qtbase and qtbase.is_dir() else None),
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "note": note,
        "patches": [{
            "id": e["id"], "type": e.get("type"),
            "status": e.get("status"), "origin": e.get("origin"),
            "refs": e.get("refs"), "files": e.get("files"),
            "sha256": e.get("sha256"),
        } for e in applied],
        "key_libs": _key_lib_snapshot(sdk_dir),
        "smoke": smoke,
    }

    path = _manifest_path(st, ver)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml_lite.dump(manifest), encoding="utf-8")
    _append_index(st, manifest)
    for entry in applied:
        patching.mark_status(st, entry["id"], "released")
    st.section("release").update({"version": ver, "manifest": str(path)})
    st.complete_stage("release", next_action="env_sync")
    return {"ok": True, "version": ver, "manifest": str(path),
            "patches": [e["id"] for e in applied]}


def _key_lib_snapshot(sdk_dir: Path) -> List[Dict]:
    snap = []
    for lib in building.sdk_key_libs(sdk_dir):
        stat = lib.stat()
        snap.append({"path": str(lib.relative_to(sdk_dir)),
                     "size": stat.st_size,
                     "mtime": time.strftime("%Y-%m-%d %H:%M:%S",
                                            time.localtime(stat.st_mtime)),
                     "sha256": _sha256_file(lib)})
    return snap


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _manifest_path(st: ForgeState, ver: str) -> Path:
    return st.state_dir / RELEASES_DIR / ("manifest-%s.yaml" % ver)


def _append_index(st: ForgeState, manifest: Dict) -> None:
    index = st.state_dir / RELEASES_DIR / RELEASES_INDEX
    index.parent.mkdir(parents=True, exist_ok=True)
    row = "| %s | %s | %s | %s | %s | %s |\n" % (
        manifest["version"], manifest["type"], manifest["qt_version"],
        ",".join(p["id"] for p in manifest.get("patches", [])) or "-",
        manifest["sdk_dir"], (manifest.get("note") or "").replace("|", "/"))
    with file_lock(index):
        if not index.exists():
            index.write_text(
                "# SDK releases\n\n"
                "| version | type | qt | patches | sdk | note |\n"
                "|---------|------|----|---------|-----|------|\n",
                encoding="utf-8")
        with index.open("a", encoding="utf-8") as fh:
            fh.write(row)


# ---------------------------------------------------------------- listing

def list_releases(st: ForgeState) -> List[Dict]:
    out = []
    rdir = st.state_dir / RELEASES_DIR
    if not rdir.is_dir():
        return out
    for path in sorted(rdir.glob("manifest-*.yaml")):
        data = yaml_lite.parse(path.read_text(encoding="utf-8")) or {}
        data["_path"] = str(path)
        out.append(data)
    return sorted(out, key=lambda m: str(m.get("created", "")),
                  reverse=True)


def diff_versions(st: ForgeState, v1: str, v2: str) -> Dict:
    m1 = _find(st, v1)
    m2 = _find(st, v2)
    if not m1 or not m2:
        return {"ok": False, "error": "version not found"}
    p1 = {p["id"]: p for p in m1.get("patches", [])}
    p2 = {p["id"]: p for p in m2.get("patches", [])}
    return {
        "ok": True,
        "added_patches": [p2[k] for k in sorted(set(p2) - set(p1))],
        "removed_patches": [p1[k] for k in sorted(set(p1) - set(p2))],
        "same_patches": sorted(set(p1) & set(p2)),
        "meta_diff": {k: [m1.get(k), m2.get(k)]
                      for k in ("qt_version", "render", "build_type",
                                "base_commit")
                      if m1.get(k) != m2.get(k)},
    }


def _find(st: ForgeState, ver: str) -> Optional[Dict]:
    for manifest in list_releases(st):
        if manifest.get("version") == ver:
            return manifest
    return None


# ---------------------------------------------------------------- switch

def use(st: ForgeState, ver: str, env_local: Optional[Path] = None) -> Dict:
    """Point ENV.local.md at a released SDK (default pointer switch)."""
    manifest = _find(st, ver)
    if not manifest:
        return {"ok": False, "error": "unknown release %r (see release-list)"
                % ver}
    qt_version = str(manifest.get("qt_version"))
    var = ENV_SDK_VAR.get(qt_version)
    if not var:
        return {"ok": False,
                "error": "no ENV.local.md variable for Qt %s" % qt_version}
    sdk_dir = str(manifest.get("sdk_dir"))

    env_local = Path(env_local) if env_local else \
        (Path(__file__).resolve().parent.parent.parent / "ENV.local.md")
    if not env_local.is_file():
        return {"ok": False,
                "error": "ENV.local.md not found at %s - pass --env-local "
                         "<path>" % env_local}

    text = env_local.read_text(encoding="utf-8")
    new_row = _ENV_ROW_TMPL % (var, sdk_dir)
    pattern = re.compile(r"\|\s*`%s`\s*\|\s*`[^`]*`\s*\|" % var)
    if pattern.search(text):
        # lambda replacement: no re-escaping of backslashes in Windows paths
        text = pattern.sub(lambda m: new_row, text)
    else:
        text += "\n## SDK releases (qt-sdk-forge)\n\n%s\n" % new_row
    marker = "Current release: `%s`" % ver
    text = re.sub(r"<!-- qt-sdk-forge:current -->.*?<!-- end -->",
                  "<!-- qt-sdk-forge:current -->%s<!-- end -->" % marker, text)
    if marker not in text:
        text += "\n<!-- qt-sdk-forge:current -->%s<!-- end -->\n" % marker
    env_local.write_text(text, encoding="utf-8")

    st.section("env_sync").update({"version": ver, "env_var": var})
    st.complete_stage("env_sync")
    return {"ok": True, "version": ver, "env_var": var,
            "sdk_dir": sdk_dir, "env_local": str(env_local)}
