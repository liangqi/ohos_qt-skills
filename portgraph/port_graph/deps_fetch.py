"""One-shot fetch of HarmonyOS artifacts for an app's dependencies (agent tool, see docs/fetch-deps.md).

    python portgraph.py fetch-deps <app> [--out DIR] [--force] [--dry-run] [--json]

Dependency closure scope: recurse along runtime / uses-module edges (consistent with the
portability decision engine), skipping conditional deps with platform_cond=macos. Key difference
from the decision engine: packages already ported to HarmonyOS (ported) are still descended into
for their runtime deps -- bottles do not bundle their deps, so linking/running on the target still
needs the artifacts of those deps (.so / headers / pkg-config).

build/test deps are host build tools (cmake/nasm etc. run on the build machine); they are not
target-side artifact requirements and are not downloaded.

Node classification (status in the manifest):
  downloaded    downloaded and extracted successfully in this run
  already_local ready locally (artifact_local or out/<name>/<version>/ already exists)
  covered       artifact of a same-named package already fetched via another data-source node (hb:/cmdpkgs: dedup)
  provided      Qt module / platform API, provided by the Qt SDK / HarmonyOS framework itself
  vendored      bundled source dependency (require_source_dep), built with the project, not downloaded
  cmd_only      no direct link but a fetch command exists (mostly formulas missing a version, so no bottle URL can be built)
  need_port     no artifact; must be cross-compiled yourself (source link attached)
  failed        download failed (404 / network error / sha256 mismatch)
  target        the app node itself
"""

from __future__ import annotations

import json
import re
import tarfile
import shutil
from collections import Counter, deque
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

from . import db, deps_report, engine, harmonybrew

RECURSE_TYPES = ("runtime", "uses-module")
VENDORED_TYPES = ("vendored",)
SKIP_PLATFORM_CONDS = ("macos",)
PROVIDED_KINDS = ("qt-module", "platform-api")

# tail of a cmd-pkgs artifact URL: .../<name>-<version>-ohos-aarch64.tar.gz
_URL_VER_RE = re.compile(r"-(.+?)-ohos-aarch64\.tar\.gz$")


def dependency_closure(conn, app_id: str) -> List[Dict]:
    """BFS-collect the app's dependency closure (including the app itself); returns nodes in discovery order.

    Each node gets _depth (hops from the app): 1 = declared directly by the app (link semantics),
    >=2 = transitive dependency (runtime semantics).
    provided nodes (Qt modules) are not expanded -- their deps ship with the Qt SDK.
    vendored edges directly from the app (require_source_dep, bundled source deps) are added to the
    closure (with _via="vendored") but not descended into -- the bundled source is cross-compiled
    with the project, and its own deps are carried by the project source/build scripts.
    """
    result: List[Dict] = []
    visited = {app_id: 0}
    queue: deque = deque([(app_id, 0, None)])
    while queue:
        nid, depth, via = queue.popleft()
        node = db.get_node(conn, nid)
        if node is None:
            continue
        node["_depth"] = depth
        if via:
            node["_via"] = via
        result.append(node)
        if node["kind"] in PROVIDED_KINDS:
            continue
        for e in db.out_edges(conn, nid, RECURSE_TYPES + VENDORED_TYPES):
            if e.get("platform_cond") in SKIP_PLATFORM_CONDS:
                continue
            is_vendored = e["type"] in VENDORED_TYPES
            if is_vendored and depth != 0:
                continue  # only collect vendored deps directly from the app
            if e["dst"] not in visited:
                visited[e["dst"]] = depth + 1
                if is_vendored:
                    # not enqueued: vendored deps are not descended into
                    vnode = db.get_node(conn, e["dst"])
                    if vnode is None:
                        continue
                    vnode["_depth"] = depth + 1
                    vnode["_via"] = "vendored"
                    result.append(vnode)
                else:
                    queue.append((e["dst"], depth + 1, None))
    return result


def _ver_from_url(url: str) -> Optional[str]:
    m = _URL_VER_RE.search(url)
    return m.group(1) if m else None


def _list_libs(installed: Path) -> List[str]:
    lib_dir = installed / "lib"
    if not lib_dir.is_dir():
        return []
    return sorted(p.stem[3:] for p in lib_dir.glob("lib*.so"))


def _hints(installed: Path, libs: List[str]) -> Dict:
    return {
        "cmake": (
            "cmake -S . -B build_ohos \\\n"
            "  -DCMAKE_TOOLCHAIN_FILE=$NATIVE_OHOS_SDK/build/cmake/ohos.toolchain.cmake \\\n"
            "  -DOHOS_ARCH=arm64-v8a \\\n"
            "  -DCMAKE_PREFIX_PATH=%s \\\n"
            "  -DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=BOTH" % installed),
        "qmake": ("LIBS += -L%s/lib %s" % (
            installed, " ".join("-l%s" % l for l in libs))),
        "deploy": "deploy the .so files to entry/libs/arm64-v8a/ before they can run on the device",
    }


def _locate_root(target: Path) -> Path:
    """Locate the install root: flat packages (cmd-pkgs, lib/include directly under target) use target;
    packages with a top-level directory use the single subdirectory containing lib/include/bin."""
    if any((target / d).is_dir() for d in ("lib", "include", "bin")):
        return target
    cands = [c for c in sorted(target.iterdir()) if c.is_dir() and
             any((c / d).is_dir() for d in ("lib", "include", "bin"))]
    return cands[0] if cands else target


def _extract_tarball(tar_path: Path, target: Path) -> List[str]:
    """Extract a generic HarmonyOS artifact tar.gz into target; returns the list of .so links recreated.

    Extract into staging first, then move into place atomically: a failure midway (disk/lock errors
    other than network) leaves no half-done result, so a rerun never mistakes a broken artifact for a
    ready one. NTFS cannot create symlinks: relative links inside the package are replaced by copies
    of their targets so that -lfoo can be resolved by the cross linker.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(target.name + ".staging")
    if staging.exists():
        harmonybrew._rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)
    fixed: List[str] = []
    try:
        with tarfile.open(tar_path, "r:gz") as tar:
            pending = []
            for m in tar.getmembers():
                if m.isdir():
                    (staging / m.name).mkdir(parents=True, exist_ok=True)
                elif m.isreg():
                    harmonybrew._extract_with_retry(tar, m, staging)
                elif m.issym():
                    pending.append(m)
            for m in pending:
                link_path = staging / m.name
                src = None
                if not m.linkname.startswith("/"):
                    src = (link_path.parent / m.linkname).resolve()
                if src and src.is_file() and not link_path.exists():
                    shutil.copy2(src, link_path)
                    fixed.append(m.name)
    except Exception:
        harmonybrew._rmtree(staging)
        raise
    if target.exists():       # overwrite the old artifact (may contain brew read-only files)
        harmonybrew._rmtree(target)
    staging.rename(target)
    return fixed


def _fetch_generic(node: Dict, out_dir: Path, force: bool) -> Dict:
    """Download a HarmonyOS artifact from a non-bottle domain (cmd-pkgs tar.gz etc.) and extract it to
    out/<name>/<version>/. No sha256 in the DB (the cmd-pkgs source provides no digest)."""
    url = node["artifact_url"]
    name = node["name"]
    version = node.get("version") or _ver_from_url(url) or "unknown"
    target = out_dir / name / version
    if target.exists() and any(target.iterdir()) and not force:
        return {"status": "already_local", "artifact_url": url,
                "installed": str(target)}
    cache = out_dir / ".cache"
    cache.mkdir(exist_ok=True)
    tar_path = cache / url.rsplit("/", 1)[-1]
    harmonybrew._download(url, tar_path, node.get("bottle_sha256"))
    fixed = _extract_tarball(tar_path, target)
    tar_path.unlink(missing_ok=True)
    installed = _locate_root(target)
    libs = _list_libs(installed)
    return {"status": "downloaded", "artifact_url": url,
            "sha256": "verified" if node.get("bottle_sha256") else "n/a",
            "installed": str(installed), "libs": libs,
            "symlinks_fixed": fixed[:10], "hints": _hints(installed, libs)}


def _fetch_one(conn, node: Dict, out_dir: Path, force: bool) -> Dict:
    """Dispatch the download by artifact URL domain: the bottle domain goes through fetch_bottle
    (sha256 verified), everything else through generic tar.gz extraction. Never raises on failure;
    returns a failed entry instead."""
    url = node["artifact_url"]
    try:
        if url.startswith(harmonybrew.BOTTLE_DOMAIN):
            r = harmonybrew.fetch_bottle(conn, node["name"], out_dir,
                                         force=force)
            # the skip path (already exists) has no sha256/libs/hints keys, so use .get
            return {"status": "already_local" if r.get("skipped")
                    else "downloaded",
                    "artifact_url": r["bottle_url"],
                    "sha256": r.get("sha256"),
                    "installed": r["installed"],
                    "libs": r.get("libs"), "hints": r.get("hints")}
        return _fetch_generic(node, out_dir, force)
    except Exception as exc:
        return {"status": "failed", "artifact_url": url, "error": str(exc)}


def _mark_local(conn, name: str, installed: str) -> None:
    """Write the ready artifact path back to same-named nodes (hb:/cmdpkgs:) for the Web detail view.

    An existing value pointing to a real path is kept; one pointing to a stale directory (e.g. an old
    absolute path from before the project was moved) is overwritten with the new path.
    """
    for nid in ("hb:%s" % name, "cmdpkgs:%s" % name):
        node = db.get_node(conn, nid)
        if node is None:
            continue
        old = node.get("artifact_local")
        if old and Path(old).is_dir():
            continue
        conn.execute("UPDATE nodes SET artifact_local=? WHERE id=?",
                     (installed, nid))
    conn.commit()


def _norm_key(name: str) -> str:
    """Dedup key for same-named packages: lowercase + strip the lib prefix (hb:qrencode and
    cmdpkgs:libqrencode are both qrencode; the xkbcommon ghost node shares a key with libxkbcommon)."""
    n = (name or "").lower()
    if n.startswith("lib") and len(n) > 5:
        n = n[3:]
    return n


def _classify_special(entry: Dict, name_lower: str, node: Dict,
                      depth: int) -> None:
    """Classify deps that are not target-side artifact requirements (aligned with the deps report scope).

    - CMake built-ins/compiler features (Threads/OpenMP/iconv/dl) -> status=provided,
      shipped with the OHOS NDK/SDK; no longer shown as "must port yourself (source: ?)"
    - Test frameworks (GTest/Catch2/...) -> role=test, not part of the release package
      (status still follows artifact availability; would_download info is kept when a bottle exists)
    - Host build-tool packages (ghost nodes for find_package build tools such as ECM with no artifact)
      -> role=build-tool, just install on the build machine; ones with a real artifact (e.g. gettext,
      which is also a runtime library) are not reclassified, to avoid breaking transitive-dep cases
    """
    spec = deps_report.CMAKE_BUILTIN_PACKAGES.get(name_lower)
    if spec:
        entry["status"] = "provided"
        entry["role"] = ("build-tool" if spec["kind"] == "build-tool"
                         else "provided")
        entry["note"] = "Not an external artifact dependency: " + spec["note"]
        return
    if name_lower in deps_report.TEST_FRAMEWORKS:
        entry["role"] = "test"
        entry["note"] = ("Test framework, not part of the release package; "
                         "only handle it if tests must run on a HarmonyOS device")
        # ghost nodes without an artifact are marked test directly (no HarmonyOS artifact needed;
        # previously misreported as need_port); when a bottle exists, status follows artifact
        # availability (download info kept)
        if not (node and (node.get("artifact_url")
                          or node.get("artifact_cmd"))):
            entry["status"] = "test"
        return
    if (depth == 1 and name_lower in deps_report.BUILD_TOOL_FINDPKG
            and not (node.get("artifact_url") or node.get("artifact_cmd"))):
        entry["role"] = "build-tool"
        entry["note"] = ("Host build tool (%s): install it on the build machine; "
                         "not deployed to the device"
                         % deps_report.BUILD_TOOL_FINDPKG[name_lower])


def fetch_app_deps(conn, app_id: str, out_dir: Path,
                   force: bool = False, dry_run: bool = False,
                   progress: Optional[Callable[[Dict], None]] = None,
                   jobs: int = 8) -> Dict:
    """Download every obtainable HarmonyOS artifact in the app's dependency closure; returns the manifest.

    dry_run=True only classifies, without downloading or writing to disk; progress is a callback
    invoked after each node; with jobs>1, tars from the bottle domain are prefetched in parallel first
    (measured on a weak network: serial at 57KB/s timed out after 90 minutes vs 8 minutes in parallel),
    then each package is extracted and installed (extraction stays serial to avoid Windows antivirus
    file-lock races).
    """
    app = db.get_node(conn, app_id)
    if app is None:
        raise ValueError("app node not found: %s" % app_id)
    out_dir = Path(out_dir)
    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    nodes = dependency_closure(conn, app_id)

    # Pre-scan: a same-named package counts as downloadable if any of its nodes has a direct artifact
    # link (hb/cmdpkgs cross-fill; the dedup key is the normalized name, so the same library under
    # different names, like qrencode/libqrencode, is not downloaded twice)
    downloadable = {}
    for n in nodes:
        if n.get("artifact_url"):
            downloadable.setdefault(_norm_key(n["name"]), n)

    # Parallel prefetch: all pending bottle-domain packages pull their tars into .cache in one batch
    # (cache hits are skipped automatically); fetch_bottle in the main loop then hits the cache and
    # goes straight to extraction
    if not dry_run and jobs > 1 and downloadable:
        hb_names = [n["name"] for n in downloadable.values()
                    if n.get("artifact_url", "").startswith(
                        harmonybrew.BOTTLE_DOMAIN)]
        if hb_names:
            if progress:
                print("[prefetch] prefetching %d bottles in parallel (jobs=%d)..."
                      % (len(hb_names), jobs))
            r = harmonybrew.prefetch_bottles(conn, hb_names, out_dir,
                                             force=force, jobs=jobs)
            if progress:
                print("[prefetch] ready %d / skipped (installed) %d / failed %d"
                      % (r["downloaded_or_cached"], r["skipped_installed"],
                         len(r["failed"])))
                for f in r["failed"]:
                    print("[prefetch]   %s: %s" % (f["name"], f["error"]))

    entries: List[Dict] = []
    installed_by_name: Dict[str, str] = {}
    for node in nodes:
        name = node["name"]
        depth = node.get("_depth", 0)
        art = engine.artifact_info(node)
        entry = {"id": node["id"], "name": name, "kind": node["kind"],
                 "version": node.get("version"),
                 "port_status": node.get("port_status")}
        if node["id"] == app_id:
            entry["status"] = "target"
            entry["role"] = "target"
        elif node.get("_via") == "vendored":
            entry["status"] = "vendored"
            entry["role"] = "vendored"
            entry["note"] = ("Bundled source dependency (require_source_dep): "
                             "cross-compiled with the project source; no external HarmonyOS artifact needed")
        elif node["kind"] in PROVIDED_KINDS:
            entry["status"] = "provided"
            entry["role"] = "provided"
            entry["note"] = "Provided by the Qt SDK / HarmonyOS framework; deployed with Qt for HarmonyOS"
        else:
            # depth 1 = declared directly by the app (link: headers+libs take part in compiling/linking)
            # depth >=2 = transitive dependency (runtime: not bundled in the bottle; the device still needs its .so)
            entry["role"] = "link" if depth == 1 else "runtime"
            key = _norm_key(name)
            # semantic classification of built-in modules/test frameworks/build tools (may set status directly)
            _classify_special(entry, name.lower(), node, depth)
            if not entry.get("status"):
                if key in installed_by_name:
                    entry["status"] = "covered"
                    entry["installed"] = installed_by_name[key]
                elif key in downloadable:
                    src = downloadable[key]
                    entry["version"] = src.get("version") or entry["version"]
                    if dry_run:
                        entry["status"] = "would_download"
                        entry["artifact_url"] = src["artifact_url"]
                        # pre-fill the target path so same-named nodes are correctly marked covered in dry-run too
                        installed_by_name[key] = str(
                            out_dir / src["name"] / (src.get("version") or "unknown"))
                    else:
                        entry.update(_fetch_one(conn, src, out_dir, force))
                        if entry.get("installed"):
                            installed_by_name[key] = entry["installed"]
                            if entry["status"] in ("downloaded", "already_local"):
                                _mark_local(conn, name, entry["installed"])
                elif art.get("artifact_local") and Path(art["artifact_local"]).is_dir():
                    entry["status"] = "already_local"
                    entry["installed"] = art["artifact_local"]
                    installed_by_name[key] = art["artifact_local"]
                elif art.get("artifact_cmd"):
                    entry["status"] = "cmd_only"
                    entry["artifact_cmd"] = art["artifact_cmd"]
                    entry["note"] = ("No direct link (could not resolve the formula version): "
                                     "run this command on a HarmonyOS device, or add the version to build the bottle URL")
                else:
                    entry["status"] = "need_port"
                    entry["source_url"] = art.get("source_url")
                    entry["repo_url"] = art.get("repo_url")
                    entry["homepage"] = art.get("homepage")
        entries.append(entry)
        if progress:
            progress(entry)

    installed_dirs = sorted({e["installed"] for e in entries
                             if e.get("installed")})
    manifest = {
        "app": {"id": app_id, "name": app["name"]},
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "out_dir": str(out_dir),
        "closure_size": len(nodes),
        "summary": dict(Counter(e["status"] for e in entries)),
        "roles": dict(Counter(e.get("role", "?") for e in entries)),
        "deps": entries,
        "toolchain": {
            "cmake_prefix_path": ";".join(installed_dirs),
            "cmake": (
                "cmake -S . -B build_ohos \\\n"
                "  -DCMAKE_TOOLCHAIN_FILE=$NATIVE_OHOS_SDK/build/cmake/ohos.toolchain.cmake \\\n"
                "  -DOHOS_ARCH=arm64-v8a \\\n"
                "  -DCMAKE_PREFIX_PATH=%s \\\n"
                "  -DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=BOTH"
                % ";".join(installed_dirs)),
            "note": "NATIVE_OHOS_SDK is the local HarmonyOS SDK native path; "
                    "all .so files must be deployed to entry/libs/arm64-v8a/ to run on the device",
        },
    }
    if not dry_run:
        slug = re.sub(r"[^\w.-]+", "_", app["name"]) or app_id
        mpath = out_dir / ("manifest-%s.json" % slug)
        mpath.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1),
            encoding="utf-8")
        manifest["manifest_path"] = str(mpath)
    return manifest
