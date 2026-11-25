"""Comprehensive dependency analysis (deps report): a full dependency picture of a Qt project.

Answers "what does this project actually depend on", by role:

  link       Dependencies whose build artifacts the project expects to obtain (target-side
             headers + .so/.a; must exist when compiling/linking the app; if missing,
             cross-compilation fails)
  build-tool Compiler/build tool dependencies (run on the build machine: cmake version,
             C++ standard, code generators protoc/flex/bison...; not deployed to the device)
  runtime    Runtime dependencies (device-side .so: transitive closure of link deps +
             dlopen/QLibrary dynamic loading; not part of the build, but the app won't run without them)
  test       Test-only dependencies (not shipped in the release package)
  vendored   Source bundled in the project (.gitmodules / 3rdparty directories, built with the project)

Each dependency carries:
  - Version requirement (find_package minimum version / pkg-config, meson, autotools
    constraint / conan range)
  - Requirement level (REQUIRED / optional)
  - How to obtain the HarmonyOS artifact (hb bottle / cmd-pkgs / provided by Qt SDK /
    shipped with the system / needs source porting) and version requirement check
    (satisfied / conflict)

Usage:

    python portgraph.py deps <project path|scanned app name> [--json]

Relation to existing commands: analyze answers "can it be ported"; fetch-deps answers
"how to get the artifacts"; deps answers "what is the full dependency picture, what role
does each play, and are version requirements met".
"""

from __future__ import annotations

import os
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from . import db, engine, kb_seed, project_scanner, qt_scanner
from .kb_seed import PKG_ALIASES as LIB_NAME_ALIASES
from .qt_scanner import BUILD_TOOL_FINDPKG, WIN32_SYSTEM_LIBS

# Libraries shipped with OHOS (NDK sysroot / system image): linking needs no bundled artifact
# (KB: semantic/qt-harmonyos-third-party-libs §linking system libraries directly)
OHOS_SYSTEM_LIBS = {
    "zlib": "libz ships with OHOS system/NDK, use -lz directly; a bottle also works",
    "z": "libz ships with OHOS system/NDK",
    "openssl": "libssl/libcrypto ship with OHOS (building Qt needs extra header path configuration)",
    "ssl": "libssl ships with OHOS",
    "crypto": "libcrypto ships with OHOS",
    "icu": "ICU ships with OHOS (dependency of Qt time zone/text backends)",
    "pthread": "pthread built into musl libc",
    "dl": "dlopen built into musl libc",
    "m": "musl libc math library",
    "rt": "musl libc",
    "atomic": "compiler runtime libatomic (ships with OHOS NDK clang)",
    "gcov": "GCC coverage runtime (clang uses --coverage; usually only for test/coverage builds)",
    "stdc++": "OHOS NDK libc++",
    "c++": "OHOS NDK libc++",
    "c++_shared": "OHOS NDK libc++_shared (provided with the SDK)",
    "log": "OHOS NDK hilog (libhilog_ndk.z.so)",
    "EGL": "OHOS system EGL (libEGL_ndk.z.so)",
    "GLESv3": "OHOS system OpenGL ES (libGLESv3_ndk.z.so)",
    "GLESv2": "OHOS system OpenGL ES",
    "intl": "gettext/libintl built into musl libc",
}
# Keys normalized to lowercase: bare link names are matched via .lower() (GLESv3/glesv3 etc.)
OHOS_SYSTEM_LIBS = {k.lower(): v for k, v in OHOS_SYSTEM_LIBS.items()}

# Windows system libraries (qmake win32 blocks / MSVC linking): not applicable to HarmonyOS
# (the code is usually wrapped in platform guards); annotated rather than treated as a
# "needs source build" gap.
# The table itself lives in qt_scanner (project_scanner also filters win32 system library
# names with it at scan time, so same-named Unix libraries (e.g. bcrypt) don't get wrong edges)

# -l link name -> common package name alignment (hb package naming): see kb_seed.PKG_ALIASES
# (deps_report and project_scanner share the same table, so deps resolves names
#   the same way as fetch-deps/analyze)

# The pkg-config version of the libav* family is the library major version (libavcodec 58 ~=
# ffmpeg 4.x), a different scale from ffmpeg release versions: once merged into ffmpeg under
# another name, that constraint cannot be compared directly -- handled uniformly by the
# version_req_from mechanism (worker1 approach)

# CMake built-in modules: not third-party packages, classified by meaning (kind + note)
CMAKE_BUILTIN_PACKAGES = {
    "threads": {"kind": "system-lib",
                "note": "CMake built-in Threads module: pthread (built into musl libc)"},
    "openmp": {"kind": "build-tool",
               "note": "compiler feature: OHOS NDK clang supports -fopenmp (libomp ships with the SDK)"},
    "iconv": {"kind": "system-lib", "note": "iconv built into musl libc"},
    "dl": {"kind": "system-lib", "note": "dlopen built into musl libc"},
    "opengl": {"kind": "system-lib",
               "note": "OHOS provides OpenGL ES (libEGL_ndk / libGLESv3_ndk); "
                      "desktop OpenGL calls must be adapted to GLES 3 (verified on gen_d/gen_p)"},
    "packagehandlestandardargs": {
        "kind": "build-tool",
        "note": "CMake built-in module (find_package_handle_standard_args), not a dependency "
                "(verified on gen_d FindFFTW.cmake; it was once listed under the wrong name "
                "findpackagehandlestandardargs, leaving phantom leftovers)"},
}

# Platform-interface-bound packages: a find_package/link hit means the app talks directly to
# that platform stack, which HarmonyOS lacks (whether it is actually compiled is decided by
# analyze's macro-guard/CMake-condition evidence)
INTERFACE_BOUND_PACKAGES = {
    "x11": "X11 display interface: HarmonyOS does not support direct use; check whether the code "
           "can be cut via build options/conditional compilation; hb's libx11 bottle is only for "
           "transitive dependency chains",
    "xext": "X11 extension: HarmonyOS does not support direct use",
    "xcb": "XCB: HarmonyOS does not support direct use",
    "alsa": "ALSA audio: unavailable on HarmonyOS, switch to HarmonyOS AudioRenderer",
    "asound": "ALSA client library name (-lasound / find_library): unavailable on HarmonyOS, "
            "switch to HarmonyOS AudioRenderer/AudioCapturer (verified on gen_d FindAlsa)",
    "pulseaudio": "PulseAudio: HarmonyOS has no such service",
    "libpulse": "PulseAudio client library (pkg-config name libpulse): HarmonyOS has no such service, "
              "switch to HarmonyOS AudioRenderer/AudioCapturer (verified on gen_d)",
    "pulse": "PulseAudio client library name (find_library pulse / -lpulse): HarmonyOS has no such "
           "service (verified on gen_d FindPulseAudio)",
    "dbus": "D-Bus IPC: HarmonyOS has no D-Bus (Qt D-Bus module is Out of scope)",
    "cocoa": "macOS Cocoa: not applicable to HarmonyOS",
    "appkit": "macOS AppKit: not applicable to HarmonyOS",
    "coreaudio": "macOS CoreAudio: unavailable on HarmonyOS",
    "wayland": "Direct Wayland use: the HarmonyOS window model is not the Wayland protocol",
    "systemd": "systemd: HarmonyOS has no systemd",
    "udev": "udev (device management from the systemd family): HarmonyOS has no udev, device enumeration "
            "must use HarmonyOS APIs (hb has a libudev with a matching name, but it is not a portable third-party library)",
    "libudev": "pkg-config name of udev (libudev): HarmonyOS has no udev, treat as a platform interface",
    "network": "macOS Network framework (bare link name form): usually inside an APPLE "
              "platform block, not applicable to HarmonyOS",
    "foundation": "macOS Foundation framework: not applicable to HarmonyOS (APPLE platform block)",
    "security": "macOS Security framework: not applicable to HarmonyOS (APPLE platform block)",
    "coreservices": "macOS CoreServices framework: not applicable to HarmonyOS (APPLE platform block)",
    "corefoundation": "macOS CoreFoundation framework: not applicable to HarmonyOS (APPLE platform block)",
    # macOS frameworks pulled in via find_library bare names (verified on corpus_b_core:
    # AudioToolbox/CoreMIDI are find_library'd inside an OS_IS_MAC block; when missing from
    # this table they were reported as ordinary packages "needing source cross-compilation")
    "audiotoolbox": "macOS AudioToolbox framework: unavailable on HarmonyOS, switch to HarmonyOS"
                  " AudioRenderer/AudioCapturer (pulled in inside an APPLE platform block)",
    "coremidi": "macOS CoreMIDI framework: not applicable to HarmonyOS (pulled in inside an APPLE platform block; "
              "MIDI must switch to the HarmonyOS MIDI capability)",
    "carbon": "macOS Carbon legacy framework: not applicable to HarmonyOS (pulled in inside an APPLE platform block)",
}

# Host-side build tools hit by find_package (formerly silently dropped by _FINDPKG_SKIP, now
# classified as build-tool so no information is lost). The table itself lives in qt_scanner
# (project_scanner also filters runtime edges with it; project_scanner must not depend back on deps_report)

# Test frameworks (find_package/QT module name hit -> test category)
TEST_FRAMEWORKS = {
    "gtest", "googletest", "catch2", "catch", "doctest", "qtest", "qttest",
    "testlib", "cppunit", "boosttest", "unittest++", "gtest_main", "qttest",
    "gmock", "gmock_main",
    "cxxtest",
}

# Build tools that ship with Qt (provided by the Qt SDK, nothing to prepare separately)
QT_TOOL_NAMES = {"moc", "uic", "rcc", "lupdate", "lrelease", "lconvert",
                 "qmake", "qtpaths", "lrelease-pro", "lupdate-pro"}

# Qt for HarmonyOS available versions (KB validation baseline: 5.12.12 / 5.15.16 / 6.12 prebuilt)
QT_OHOS_AVAILABLE = {"5": ("5.12", "5.15"), "6": ("6.12",)}

RECURSE_TYPES = ("runtime",)
SKIP_PLATFORM_CONDS = ("macos",)
PROVIDED_KINDS = ("qt-module", "platform-api")


# ---------------------------------------------------------------- version comparison

def _ver_key(v) -> tuple:
    if not v:
        return ()
    parts = re.findall(r"\d+", str(v))
    return tuple(int(p) for p in parts)


def _check_min(min_ver: Optional[str], available: Optional[str]) -> str:
    """find_package minimum version vs available version."""
    if min_ver is None:
        return "any" if available else "unknown"
    if not available:
        return "unknown"
    return ("satisfied" if _ver_key(available) >= _ver_key(min_ver)
            else "conflict")


def _check_req(version_req: Optional[str], available: Optional[str]) -> str:
    """pkg-config/conan constraint with operator (">= 2.50") vs available version."""
    if not version_req:
        return _check_min(None, available)
    m = re.match(r"(>=|<=|==|=|<|>|!=)\s*([\w.]+)", version_req)
    if not m:
        return "unknown"
    if not available:
        return "unknown"
    op, want = m.group(1), _ver_key(m.group(2))
    have = _ver_key(available)
    if not want or not have:
        return "unknown"
    ok = {">=": have >= want, "<=": have <= want, "<": have < want,
          ">": have > want, "==": have == want, "=": have == want,
          "!=": have != want}.get(op)
    if ok is None:
        return "unknown"
    return "satisfied" if ok else "conflict"


# ---------------------------------------------------------------- artifact resolution

def _resolve(conn, name: str, cache: Optional[Dict] = None) -> Optional[Dict]:
    """Package name (find_package/pkg-config/include hint) -> package node in the DB.

    Delegates to kb_seed.resolve_pkg_name's shared resolution ladder (alias first -> original
    name -> lib-prefix variants -> strip pkg-config version suffix), consistent with scan time
    (project_scanner) -- this removes the split where scan time created a phantom node while
    report time could resolve the name (verified on libsparsehash/gio-2.0).
    cache: resolution cache for a single analysis (includes None misses; the graph does not
    change during an analysis).
    """
    if conn is None:
        return None
    return kb_seed.resolve_pkg_name(conn, name, cache)


def _artifact_of(node: Optional[Dict]) -> Optional[Dict]:
    if node is None:
        return None
    art = engine.artifact_info(node)
    if art["ready"]:
        src = art["artifact_url"] or art["artifact_cmd"] or art["artifact_local"]
    elif art["provided"]:
        src = "provided"
    else:
        src = None
    return {"ready": art["ready"], "provided": art["provided"],
            "source": src,
            "source_url": art.get("source_url"),
            "repo_url": art.get("repo_url")}


def _in_tree_dir_index(root: Path) -> Dict[str, str]:
    """Index of source directories bundled in the project: directory name (lowercase) -> relative path.

    Used to decide whether an unresolved bare link name/find_package name is actually source
    bundled in the project (verified on gen_f's src/libraries/fakevim, botan, litehtml: the
    report falsely flagged need_port while the source is in the repo and built with the project).

    Only collects directories that "look like third-party libraries", to avoid misjudging the
    project's own code directories (gen_a's libs/flake/text/lager, the iccjpeg glue in
    plugins/impex/jpeg/3rdparty/lcms) as in-tree:
      - the directory contains a build file (CMakeLists/Makefile.am/.pri/.pro) (glue
        directories without build files, such as iccjpeg, are excluded by this)
      - and one of: the path contains a vendored directory segment (3rdparty/external/...),
        the parent directory is a dependency collection (>=5 subdirectories each with build
        files, e.g. src/libraries), or the directory contains README/LICENSE/COPYING
        (a trait of upstream source packages)
    """
    vendored_names = set(qt_scanner.VENDORED_DIR_NAMES)
    lib_dirs: Dict[str, list] = {}      # dirpath -> (basename, relpath, nfiles)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in (".git", "node_modules", "build",
                                    "build_ohos")]
        d = Path(dirpath)
        base = d.name.lower()
        if not base or len(base) < 3 or base in lib_dirs:
            continue
        has_build = any(f in filenames for f in
                        ("CMakeLists.txt", "Makefile.am")) or any(
            f.rsplit(".", 1)[-1] in ("pri", "pro") for f in filenames)
        if not has_build:
            continue
        lib_dirs[dirpath] = [base, d.relative_to(root).as_posix(), 0,
                             filenames]
    # "Dependency collection" test for the parent: the parent name is a library container
    # (libraries/libs) and >=5 subdirectories each look like library directories. The
    # container-name whitelist avoids mistaking feature-grouping directories for dependency
    # collections -- gen_b's generators/ (poppler/epub/markdown/...) holds format generator
    # plugin code, not bundled library source (it was verified to be misjudged as in-tree,
    # hiding the real need_port of poppler/epub); gen_f's src/libraries is a real
    # collection of bundled libraries.
    _LIB_CONTAINER_NAMES = {"libraries", "libs"}
    children: Dict[str, int] = {}
    for dirpath in lib_dirs:
        parent = str(Path(dirpath).parent)
        children[parent] = children.get(parent, 0) + 1
    out: Dict[str, str] = {}
    for dirpath, (base, rel, _n, filenames) in lib_dirs.items():
        parts = Path(rel).parts[:-1]
        parent_path = Path(dirpath).parent
        parent = str(parent_path)
        parent_is_collection = (
            children.get(parent, 0) >= 5
            and parent_path.name.lower() in _LIB_CONTAINER_NAMES)
        has_readme = any(f.upper().startswith(("README", "LICENSE", "COPYING"))
                         for f in filenames)
        # README/LICENSE alone is not enough: the README of gen_b generators/epub describes
        # "a backend based on the external libepub" (pointing to svn to fetch the library),
        # not a bundled source package -- it only serves as supporting evidence inside a
        # library-container parent (bundled libraries in a container below collection size,
        # e.g. only 2 real libraries under libraries/, each with its upstream README).
        if (vendored_names.intersection(parts) or parent_is_collection
                or (has_readme
                    and parent_path.name.lower() in _LIB_CONTAINER_NAMES)):
            out.setdefault(base, rel)
    return out


def _loose_folds(n: str) -> set:
    """Loose fold candidates for a dependency name: lowercase, drop non-alphanumerics, drop
    the lib prefix, drop trailing qt5/qt6/system variant tokens.

    editorconfig_core_qt == editorconfig-core-qt;
    Qt-Advanced-Docking-System == qtadvanceddocking-qt6 (CPM name ads
    vs link target name qtadvanceddocking-qt6, verified on gen_i)."""
    toks = [t for t in re.split(r"[-_./]+", (n or "").lower()) if t]
    while toks and toks[-1] in ("qt5", "qt6", "system"):
        toks = toks[:-1]
    out = set()
    if toks:
        f = "".join(toks)
        out.add(f)
        if f.startswith("lib") and len(f) > 3:
            out.add(f[3:])
    return {f for f in out if len(f) >= 3}


def _vendored_declarations(info: Dict) -> Dict[str, tuple]:
    """Index of bundled-source declarations: loose fold name -> (label, detail).

    Covers four kinds of "built with the project" declarations:
    - git submodules (.gitmodules; in an uninitialized shallow clone the directory is empty
      and invisible to _in_tree_dir_index) -- verified on corpus_a kcoreaddons/microtex
    - CPM/FetchContent/ExternalProject configure-time fetches (fetched_deps; either the name
      or the last URL segment can match) -- verified on gen_i ads/QSimpleUpdater
    - meson bundled subprojects (subprojects/ directory and .wrap) and project-internal
      override_dependency targets -- verified on gen_j/rizin's zydis/rz_*
    """
    out: Dict[str, tuple] = {}

    def add(nm: str, label: str, detail: str) -> None:
        for f in _loose_folds(nm):
            if f not in out:
                out[f] = (label, detail)

    for gm in info.get("git_submodules") or []:
        cands = [gm.get("name") or "", gm.get("path") or ""]
        url_last = ((gm.get("url") or "").rstrip("/").rsplit("/", 1)[-1])
        if url_last.endswith(".git"):
            url_last = url_last[:-4]
        cands.append(url_last)
        path = gm.get("path") or gm.get("name") or ""
        for c in cands:
            add(c, "git submodule", path)
    for fd in info.get("fetched_deps") or []:
        nm = fd.get("name") or ""
        how = fd.get("how") or "FetchContent"
        add(nm, how, nm)
        url = fd.get("url") or ""
        last = url.rstrip("/").rsplit("/", 1)[-1]
        if last.endswith(".git"):
            last = last[:-4]
        if last:
            add(last, how, nm)
    meson = info.get("meson") or {}
    for nm in meson.get("internal_deps") or []:
        add(nm, "meson subproject/internal target", nm)
    for nm in meson.get("subprojects") or []:
        add(nm, "meson subproject", nm)
    return out


def _match_in_tree_dir(index: Dict[str, str], name: str) -> Optional[str]:
    """Unresolved library name -> same-named source directory in the project (version suffix stripped/aliases applied)."""
    cands = [name.lower()]
    canon = LIB_NAME_ALIASES.get(name.lower())
    if canon:
        cands.append(canon.lower())
    for c in list(cands):
        stripped = re.sub(r"-\d+(\.\d+)*$", "", c)
        if stripped != c:
            cands.append(stripped)
    for c in cands:
        hit = index.get(c)
        if hit:
            return hit
    return None


class _GraphCache:
    """Graph query cache (nodes / out-edges) within a single analysis.

    The deps report runs one runtime-closure BFS per link dependency, so the same node is
    queried repeatedly (200 deps x a deep graph measured 240k SQL queries). The graph does
    not change during an analysis, so a shared cache brings total queries back to O(V+E).
    """

    def __init__(self, conn):
        self.conn = conn
        self._nodes: Dict = {}
        self._edges: Dict = {}

    def node(self, node_id: str) -> Optional[Dict]:
        if node_id not in self._nodes:
            self._nodes[node_id] = db.get_node(self.conn, node_id)
        return self._nodes[node_id]

    def out_edges(self, node_id: str, etypes) -> List[Dict]:
        key = (node_id, etypes)
        if key not in self._edges:
            self._edges[key] = db.out_edges(self.conn, node_id, etypes)
        return self._edges[key]


def _runtime_closure(conn, node_id: str,
                     cache: Optional[_GraphCache] = None) -> List[Dict]:
    """Transitive runtime dependencies of a package node (BFS; skips provided and macos conditions).

    Consistent with deps_fetch.dependency_closure: bottles don't bundle their dependencies, so
    target-side linking/running still needs the .so files they depend on.
    cache: node/out-edge cache shared across dependencies (see _GraphCache).
    """
    from collections import deque
    if cache is None:
        cache = _GraphCache(conn)
    out: List[Dict] = []
    visited = {node_id}
    queue = deque([node_id])
    while queue:
        nid = queue.popleft()
        if nid != node_id:
            node = cache.node(nid)
            if node:
                out.append(node)
        for e in cache.out_edges(nid, RECURSE_TYPES):
            if e.get("platform_cond") in SKIP_PLATFORM_CONDS:
                continue
            if e["dst"] not in visited:
                visited.add(e["dst"])
                nd = cache.node(e["dst"])
                if nd is None or nd["kind"] in PROVIDED_KINDS:
                    continue
                queue.append(e["dst"])
    return out


def _version_check(entry: Dict) -> str:
    """Whether multi-source version constraints (conan range / pkg constraint / find_package
    minimum version) are met: when several exist, take the worst result (any conflict is a conflict).

    When version_req_from is present, version_req comes from another library name (alias
    merge, e.g. libavcodec >= 58 -> ffmpeg) and constrains the library major version rather
    than the package version; the scales are not comparable -> treated as unknown (no false conflict).
    """
    avail = entry.get("available_version")
    cross = bool(entry.get("version_req_from"))
    checks = []
    if entry.get("version_range"):
        checks.append(_check_req(_range_to_req(entry["version_range"]), avail))
    if entry.get("version_req"):
        checks.append("unknown" if cross
                      else _check_req(entry["version_req"], avail))
    if entry.get("min_version"):
        checks.append(_check_min(entry["min_version"], avail))
    if "conflict" in checks:
        return "conflict"
    if "satisfied" in checks:
        return "satisfied"
    if checks:
        return checks[0]
    return "any" if avail else "unknown"


# ---------------------------------------------------------------- main analysis

def _merge_link_entries(base: Dict, entry: Dict) -> None:
    """Merge entry (same library under another name) into base (called in phase 7b).

    - REQUIRED wins; version info takes the first explicit value seen (consistent with _DepBook)
    - a more specific kind overrides (system-lib/platform-iface/framework over package)
    - when base has no artifact but entry does (cross-source hb/cmdpkgs complement), adopt
      entry's resolution result
    """
    base["required"] = base["required"] or entry["required"]
    for f in ("min_version", "version_req", "version_range"):
        base[f] = base.get(f) or entry.get(f)
    if not base.get("version_req") and entry.get("version_req") \
            and entry.get("version_req_from"):
        base["version_req_from"] = entry["version_req_from"]
    if entry["kind"] not in ("package", base["kind"]):
        # a more specific kind overrides (system-lib/platform-iface/framework win)
        if base["kind"] == "package":
            base["kind"] = entry["kind"]
    if entry.get("ohos_note") and not base.get("ohos_note"):
        base["ohos_note"] = entry["ohos_note"]
    base["evidence"] = (base.get("evidence", [])
                        + [e for e in entry.get("evidence", [])
                           if e not in base.get("evidence", [])])
    base_art = base.get("artifact") or {}
    ent_art = entry.get("artifact") or {}
    if ent_art.get("ready") and not base_art.get("ready"):
        # base has no artifact while entry resolved to a node with one (e.g. the vcpkg name
        # did not resolve but the find_package name resolved to a bottle): adopt entry's result
        for f in ("resolved_node", "port_status", "available_version",
                  "artifact"):
            if entry.get(f) is not None:
                base[f] = entry[f]


class _DepBook:
    """Merges multi-source evidence for same-named dependencies (find_package/pkg/conan/include/qmake)."""

    def __init__(self):
        self.by_name: Dict[str, Dict] = {}

    def add(self, name: str, kind: str = "package", required: bool = True,
            min_version: str = None, version_req: str = None,
            version_range: str = None, components: List[str] = None,
            evidence: str = None) -> Dict:
        key = name.lower()
        entry = self.by_name.get(key)
        if entry is None:
            entry = {"name": name, "kind": kind, "required": required,
                     "min_version": min_version, "version_req": version_req,
                     "version_range": version_range,
                     "components": components or [], "evidence": []}
            self.by_name[key] = entry
        else:
            # REQUIRED wins over optional; version info takes the first explicit value seen
            if required:
                entry["required"] = True
            entry["min_version"] = entry["min_version"] or min_version
            entry["version_req"] = entry["version_req"] or version_req
            entry["version_range"] = entry["version_range"] or version_range
            if components:
                for c in components:
                    if c not in entry["components"]:
                        entry["components"].append(c)
        if evidence and evidence not in entry["evidence"]:
            entry["evidence"].append(evidence)
        return entry

    def values(self) -> List[Dict]:
        return sorted(self.by_name.values(), key=lambda d: d["name"].lower())


def _env_json_qt_version(root: Path):
    """Read qt_version from `.qt-ohos/env.json` (explicitly set by the user, takes precedence over inference)."""
    path = Path(root) / ".qt-ohos" / "env.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = data.get("qt_version")
    if value in (None, ""):
        return None
    value = str(value).strip()
    return value[0] if value and value[0] in "56" else None


def analyze_dependencies(conn, root, info: Dict = None) -> Dict:
    """Generate the comprehensive dependency analysis report. conn may be None (scan only, no artifact resolution)."""
    root = Path(root).resolve()
    info = info or qt_scanner.scan_project(root)
    version = project_scanner._detect_version(root)

    fp_details = info.get("find_package_details", [])
    pkg_manifests = info.get("pkg_manifests", {})
    cmake_packages = info.get("cmake_packages", {})

    # ---- Qt version requirement (find_package(Qt5 5.15 ...) declaration / inferred from .pro files)
    qt_min = None
    qt_optional_modules = set()
    for fp in fp_details:
        if re.fullmatch(r"qt\d", fp["name_lower"]):
            if fp["version"]:
                qt_min = fp["version"] if qt_min is None else max(
                    qt_min, fp["version"], key=_ver_key)
            for c in fp.get("optional_components") or []:
                qt_optional_modules.add(c.lower())
    qt_major = info.get("qt_version_hint")

    # ---- category buckets
    link = _DepBook()
    test_deps: List[Dict] = []
    build_tools: List[Dict] = []
    warnings: List[Dict] = []

    qt_override = _env_json_qt_version(root)
    if qt_override:
        # `.qt-ohos/env.json` is a fact the user explicitly corrected (`qt-ohos-run config set
        # qt_version 6`); it is more authoritative than build-file inference, otherwise "changed
        # the config but deps still prints Qt: 5" would make people think the config had no effect.
        qt_major = qt_override
        warnings.append({
            "level": "info",
            "msg": "Qt major version taken from .qt-ohos/env.json (qt_version=%s)" % qt_override,
        })

    # ---- 1) find_package details
    for fp in fp_details:
        name = fp["name_lower"]
        ev = "find_package(%s%s%s) %s:%d" % (
            fp["name"], " %s" % fp["version"] if fp["version"] else "",
            " REQUIRED" if fp["required"] else "", fp["file"], fp["line"])
        if name.startswith("qt") or name.startswith("kf"):
            continue  # Qt modules/KF components handled separately
        if name in TEST_FRAMEWORKS:
            test_deps.append({"name": fp["name"], "source": ev,
                              "note": "test framework, not shipped in the release package"})
            continue
        if name in CMAKE_BUILTIN_PACKAGES:
            spec = CMAKE_BUILTIN_PACKAGES[name]
            if spec["kind"] == "build-tool":
                build_tools.append({"tool": name, "how": [ev],
                                    "note": spec["note"],
                                    "provided_by": "host"})
            else:
                e = link.add(fp["name"], kind=spec["kind"],
                             required=fp["required"], evidence=ev)
                e["ohos_note"] = spec["note"]
            continue
        if name in BUILD_TOOL_FINDPKG:
            build_tools.append({"tool": name, "how": [ev],
                                "note": BUILD_TOOL_FINDPKG[name],
                                "provided_by": "qt-sdk"
                                if name == "linguisttools" else "host"})
            continue
        if name in INTERFACE_BOUND_PACKAGES:
            plat = fp.get("platform")
            e = link.add(fp["name"], kind="platform-iface",
                         required=(fp["required"] and not fp.get("optional")
                                   and not plat),
                         evidence=ev)
            e["ohos_note"] = INTERFACE_BOUND_PACKAGES[name]
            if fp.get("optional"):
                e["note"] = ("CMake option guard (default OFF): "
                              "the default build does not include this dependency")
            elif plat:
                e["note"] = ("inside an if(%s) platform block: built only on that platform, "
                              "not included in the HarmonyOS build" % plat)
            continue
        # Merge the same library under different names: rewrite the find_package name via the
        # alias table (KDcrawQt6->kdcraw, QuaZip-Qt->quazip) so that, without a package source,
        # it merges with pkg-config/bare-link declarations into one entry
        aliased = LIB_NAME_ALIASES.get(name)
        entry = link.add(aliased or fp["name"],
                         required=(fp["required"] and not fp.get("optional")
                                   and not fp.get("platform")),
                         min_version=fp["version"],
                         components=(fp["components"]
                                     + fp["optional_components"]) or None,
                         evidence=ev)
        if fp.get("optional"):
            entry["note"] = ("CMake option guard (default OFF): "
                              "the default build does not include this dependency")
        elif fp.get("platform"):
            entry["note"] = ("inside an if(%s) platform block: built only on that platform, "
                              "not included in the HarmonyOS build" % fp["platform"])
        if aliased:
            entry.setdefault("ohos_note",
                             "find_package name %s merged into package %s"
                             % (fp["name"], aliased))
        if fp["exact"]:
            entry["version_req"] = "== %s" % fp["version"]

    # ---- 2) pkg_check_modules (with version constraints)
    for pm in cmake_packages.get("pkg_modules", []):
        ev = "pkg_check_modules(%s%s)" % (
            pm["name"], " %s" % pm["version_req"] if pm["version_req"] else "")
        if pm["name"] in TEST_FRAMEWORKS:
            test_deps.append({"name": pm["name"], "source": ev,
                              "note": "test framework, not shipped in the release package"})
            continue
        if pm["name"] in INTERFACE_BOUND_PACKAGES:
            e = link.add(pm["name"], kind="platform-iface",
                         required=(not pm.get("optional")
                                   and not pm.get("platform")), evidence=ev)
            e["ohos_note"] = INTERFACE_BOUND_PACKAGES[pm["name"]]
            if pm.get("optional"):
                e["note"] = ("CMake option guard (default OFF): "
                              "the default build does not include this dependency")
            elif pm.get("platform"):
                e["note"] = ("inside an if(%s) platform block: built only on that platform, "
                              "not included in the HarmonyOS build" % pm["platform"])
            continue
        # Same library declared twice (pkg-config name vs find_package name): merge by alias.
        # The version constraint is attached under the merged original name (version_req_from):
        # libavcodec's ">= 58" is a library major version, not directly comparable with the
        # ffmpeg package version.
        aliased = LIB_NAME_ALIASES.get(pm["name"], pm["name"])
        e = link.add(aliased, version_req=pm["version_req"], evidence=ev,
                     required=(not pm.get("optional")
                               and not pm.get("platform")))
        if pm.get("optional"):
            e["note"] = "CMake option guard (default OFF): the default build does not include this dependency"
        elif pm.get("platform"):
            e["note"] = ("inside an if(%s) platform block: built only on that platform, "
                          "not included in the HarmonyOS build" % pm["platform"])
        if pm["version_req"] and aliased != pm["name"]:
            e["version_req_from"] = pm["name"]

    # ---- 3) Conan / vcpkg manifests (version may be a range string)
    for c in pkg_manifests.get("conan", []):
        link.add(c["name"], version_range=c.get("version"),
                 evidence="conan: %s/%s" % (c["name"], c.get("version") or "*"))
    for v in pkg_manifests.get("vcpkg", []):
        link.add(v["name"], min_version=v.get("version"),
                 evidence="vcpkg.json: %s" % v["name"]
                 + (" (>= %s)" % v["version"] if v.get("version") else ""))

    # ---- 4) Source directly #includes third-party headers (16 kinds incl. zlib/openssl/boost;
    #          a source of implicit dependencies when build files don't declare them)
    for h in info.get("third_party_hints", []):
        link.add(h["name"], required=False,
                 evidence="include: %s" % h["evidence"][0]
                 if h.get("evidence") else "include")

    # ---- 5) qmake LIBS += -lfoo
    for ql in info.get("qmake_libs", []):
        n = ql["name"]
        if n in OHOS_SYSTEM_LIBS:
            ev = "qmake LIBS -l%s (%s)" % (n, OHOS_SYSTEM_LIBS[n])
            e = link.add(n, kind="system-lib", evidence=ev)
            e["ohos_note"] = OHOS_SYSTEM_LIBS[n]
        elif n in WIN32_SYSTEM_LIBS:
            e = link.add(n, kind="win32-system-lib", required=False,
                         evidence="qmake LIBS -l%s" % n)
            e["ohos_note"] = "Windows system library: usually inside a win32 platform block, not applicable to HarmonyOS"
        else:
            aliased = LIB_NAME_ALIASES.get(n.lower())
            e = link.add(aliased or n,
                         evidence="qmake LIBS -l%s (%s)" % (
                             n, ql["evidence"][0] if ql.get("evidence") else "?"))
            if aliased:
                e.setdefault("ohos_note", "link name %s merged into package %s" % (n, aliased))

    # ---- 6) KDE Frameworks components (link, framework kind)
    for comp in info.get("kf_components", []):
        deps = kb_seed.KF_DEPS.get(comp)
        note = None
        if deps:
            note = "depends on Qt modules: %s" % ", ".join(deps.get("qt", []))
            if deps.get("ifaces"):
                note += "; bound platform interfaces: %s" % ", ".join(deps["ifaces"])
        e = link.add(comp, kind="framework", evidence="find_package(KF* %s)" % comp)
        if note:
            e["ohos_note"] = "KDE Frameworks component, needs source cross-compilation; " + note

    # ---- 6b) Bare link names (target_link_libraries / find_library /
    #          cc.find_library / AC_CHECK_LIB): direct linking without find_package
    for rl in info.get("raw_libs", []):
        n = rl["name"]
        ev = "%s (%s)" % ("+".join(rl.get("hows", [])),
                          rl["evidence"][0] if rl.get("evidence") else "?")
        plat = rl.get("platform_block")
        if n.lower() in TEST_FRAMEWORKS:
            # A bare target_link_libraries name hits a test framework (e.g. gen_f's
            # gtest_main): classify as test rather than a need_port link
            test_deps.append({"name": n, "source": ev,
                              "note": "test framework, not shipped in the release package"})
            continue
        if n.lower() in OHOS_SYSTEM_LIBS:
            e = link.add(n, kind="system-lib",
                         required=not plat, evidence=ev)
            e["ohos_note"] = OHOS_SYSTEM_LIBS[n.lower()]
        elif n.lower() in WIN32_SYSTEM_LIBS:
            e = link.add(n, kind="win32-system-lib", required=False, evidence=ev)
            e["ohos_note"] = "Windows system library: usually inside a win32 platform block, not applicable to HarmonyOS"
        elif n.lower() in INTERFACE_BOUND_PACKAGES:
            existed = (n.lower() in link.by_name)
            e = link.add(n, kind="platform-iface", required=not plat,
                         evidence=ev)
            e["ohos_note"] = INTERFACE_BOUND_PACKAGES[n.lower()]
            if plat and not existed:
                e["note"] = ("inside an if(%s) platform block: built only on that platform, "
                              "not included in the HarmonyOS build" % plat)
        else:
            aliased = LIB_NAME_ALIASES.get(n.lower())
            existed = ((aliased or n).lower() in link.by_name)
            e = link.add(aliased or n, required=not plat, evidence=ev)
            if rl.get("ext_target"):
                e.setdefault(
                    "ohos_note",
                    "external_* imported target link (the find_package declaration lives in an "
                    "external build module/uninitialized submodule, e.g. cmake_helpers); "
                    "how to obtain the artifact depends on the name match result")
            else:
                e.setdefault("ohos_note",
                             "bare link name (not declared via find_package/pkg-config); "
                             "how to obtain the artifact depends on the name match result")
            if plat and not existed:
                # Annotate only when this entry was created by a bare link declaration inside a
                # platform block; for existing entries (required find_package declarations etc.)
                # the required semantics are protected by the merge rules (REQUIRED wins and is
                # not downgraded here)
                e["note"] = ("inside an if(%s) platform block: built only on that platform, "
                              "not included in the HarmonyOS build" % plat)

    # ---- 6c) macOS frameworks (-framework X)
    for fw in info.get("macos_frameworks", []):
        e = link.add(fw["name"], kind="platform-iface", required=False,
                     evidence="-framework %s (%s)" % (
                         fw["name"], fw["evidence"][0] if fw.get("evidence") else "?"))
        e["ohos_note"] = "macOS framework: inside an APPLE platform block, not applicable to HarmonyOS"

    # ---- 6d) qmake PKGCONFIG +=
    for pc in info.get("qmake_pkgconfig", []):
        link.add(pc["name"],
                 evidence="qmake PKGCONFIG += %s (%s)" % (
                     pc["name"], pc["evidence"][0] if pc.get("evidence") else "?"))

    # ---- 6e) meson dependency('name', version: ...)
    for md in info.get("meson_deps", []):
        n = md["name"]
        if n.lower() in CMAKE_BUILTIN_PACKAGES:
            spec = CMAKE_BUILTIN_PACKAGES[n.lower()]
            e = link.add(n, kind=spec["kind"],
                         required=md.get("required", True),
                         evidence="meson dependency('%s') %s" % (
                             n, md["evidence"][0] if md.get("evidence") else ""))
            e["ohos_note"] = spec["note"]
            continue
        if n.lower() in INTERFACE_BOUND_PACKAGES:
            e = link.add(n, kind="platform-iface", required=md.get("required", True),
                         evidence="meson dependency('%s') %s" % (
                             n, md["evidence"][0] if md.get("evidence") else ""))
            e["ohos_note"] = INTERFACE_BOUND_PACKAGES[n.lower()]
        else:
            link.add(n, required=md.get("required", True),
                     version_req=md.get("version"),
                     evidence="meson dependency('%s'%s) %s" % (
                         n, " %s" % md["version"] if md.get("version") else "",
                         md["evidence"][0] if md.get("evidence") else ""))

    # ---- 6f) autotools PKG_CHECK_MODULES (with version constraints)
    for ad in info.get("autotools_deps", []):
        n = ad["name"]
        if n.lower() in INTERFACE_BOUND_PACKAGES:
            e = link.add(n, kind="platform-iface",
                         evidence="PKG_CHECK_MODULES %s" % n)
            e["ohos_note"] = INTERFACE_BOUND_PACKAGES[n.lower()]
        else:
            link.add(n, version_req=ad.get("version_req"),
                     evidence="PKG_CHECK_MODULES(%s%s) %s" % (
                         n, " %s" % ad["version_req"] if ad.get("version_req") else "",
                         ad["evidence"][0] if ad.get("evidence") else ""))

    # ---- 6g) Custom wrapper function declarations (e.g. gen_n search_dependency's
    #          PACKAGE <pkg-config name> [LIBRARY x] [MINIMUM_VERSION v])
    for wd in info.get("wrapper_deps", []):
        n = wd["name"]
        ev = "%s(PACKAGE %s%s%s)" % (
            wd.get("wrapper", "wrapper"), n,
            " %s" % wd["version"] if wd.get("version") else "",
            " %s" % wd["evidence"][0] if wd.get("evidence") else "")
        if n.lower() in INTERFACE_BOUND_PACKAGES:
            e = link.add(n, kind="platform-iface", evidence=ev)
            e["ohos_note"] = INTERFACE_BOUND_PACKAGES[n.lower()]
            continue
        aliased = LIB_NAME_ALIASES.get(n.lower())
        e = link.add(aliased or n,
                     version_req=(">= %s" % wd["version"]) if wd.get("version")
                     else None,
                     evidence=ev)
        if aliased:
            e.setdefault("ohos_note", "wrapper declaration %s merged into package %s" % (n, aliased))

    # ---- 6h) Dependency manifest functions (corpus_b_deps engine etc.): require_dep /
    #          require_source_dep / require_tool. link -> regular link dependency;
    #          source -> vendored; tool -> toolchain
    manifest_vendored: List[Dict] = []
    for md in info.get("manifest_deps", []):
        n = md["name"]
        ev = "require_dep-style manifest declaration %s (%s)" % (
            n, md["evidence"][0] if md.get("evidence") else "?")
        if md.get("conditional"):
            ev += " [conditional block if(%s), not necessarily enabled in the default build]" % (md.get("condition") or "?")
        if md["mode"] == "tool":
            build_tools.append({"tool": n, "how": [ev],
                                "note": "host build tool declared in the dependency manifest"
                                        " (require_tool); just install it on the build machine",
                                "provided_by": "host"})
        elif md["mode"] == "source":
            manifest_vendored.append({"name": n, "path": None, "url": None,
                                      "note": "require_source_dep: source bundled, "
                                              "built together with the project"})
        else:
            e = link.add(n, required=not md.get("conditional"), evidence=ev)
            if md.get("conditional"):
                e.setdefault("ohos_note",
                             "declared inside conditional block if(%s), not necessarily enabled in the default build"
                             % (md.get("condition") or "?"))

    # ---- 7) resolve artifacts + version check + transitive runtime
    runtime_book: Dict[str, Dict] = {}
    graph_cache = _GraphCache(conn) if conn is not None else None
    resolve_cache: Dict[str, Optional[Dict]] = {}
    in_tree_index: Optional[Dict[str, str]] = None   # built lazily
    vendored_decls = _vendored_declarations(info)
    # The project's own targets/directories (CMake targets, subdirectories with build files,
    # the project() name): when unresolved they are "things this project builds", not "the
    # knowledge base is missing this third-party library".
    # first_party fold names keep hyphens (auto-updates), while _loose_folds() strips all
    # separators (autoupdates); both sides must be folded to "alphanumerics only" to compare
    first_party_folds = {
        re.sub(r"[^a-z0-9]", "", f): f
        for f in (qt_scanner.first_party_folds(info) if info else set())}
    fp_declared: List[Dict] = []
    link_list = link.values()
    for entry in link_list:
        skip_resolve = entry["kind"] in ("system-lib", "win32-system-lib",
                                         "platform-iface")
        if entry["kind"] == "framework":
            # KF components must not go through the package name resolution ladder: component
            # names collide with unrelated C libraries (KF Archive != libarchive, KF Config !=
            # libconfig; verified on gen_b/gen_c, which once showed a ready bottle contradicting
            # a need_port closure). Resolve to the kf:<comp> node created at scan time
            # (port_status=unknown -> needs source cross-compilation, consistent with the
            # fetch-deps closure).
            node = (db.get_node(conn, "kf:%s" % entry["name"].lower())
                    if conn is not None else None)
        else:
            node = None if skip_resolve else _resolve(conn, entry["name"],
                                                      resolve_cache)
        entry["resolved_node"] = node["id"] if node else None
        entry["_resolved_name"] = node["name"] if node else None
        entry["port_status"] = node["port_status"] if node else None
        entry["available_version"] = node["version"] if node else None
        entry["artifact"] = _artifact_of(node)
        # Unresolved but a same-named source directory exists in the project: bundled source
        # built with the project, not an external need_port gap (verified on fakevim/litehtml/botan)
        if (node is None and entry["kind"] == "package" and root
                and Path(root).is_dir()):
            if in_tree_index is None:
                in_tree_index = _in_tree_dir_index(Path(root))
            hit = _match_in_tree_dir(in_tree_index, entry["name"])
            if hit:
                entry["kind"] = "in-tree"
                entry["artifact"] = {"ready": True, "provided": True,
                                     "source": "in-tree:%s" % hit}
                entry["ohos_note"] = ("source directory bundled in the project (%s): built "
                                      "with the project, no external artifact needed" % hit)
        # Unresolved but matches a bundled-source declaration (git submodule / CPM-FetchContent
        # / meson subproject or internal target): the source comes with the project, not an
        # external need_port gap (verified on corpus_a kcoreaddons, gen_i QSimpleUpdater,
        # gen_j rz_*/zydis)
        if node is None and entry["kind"] == "package" and vendored_decls:
            hit = next((vendored_decls[f]
                        for f in _loose_folds(entry["name"])
                        if f in vendored_decls), None)
            if hit:
                label, detail = hit
                entry["kind"] = "in-tree"
                entry["artifact"] = {"ready": True, "provided": True,
                                     "source": "%s:%s" % (label, detail)}
                entry["ohos_note"] = (
                    "%s (%s): source built with the project, no external artifact needed" % (label, detail))
        # Resolved to a HarmonyOS artifact, but the project also bundles the library source: the bottle is an alternative
        if (node is not None and entry["kind"] == "package"
                and vendored_decls):
            hit = next((vendored_decls[f]
                        for f in _loose_folds(entry["name"])
                        if f in vendored_decls), None)
            if hit:
                label, detail = hit
                entry["ohos_note"] = ((entry.get("ohos_note") or "")
                                      + "; the project bundles this library's source (%s %s), "
                                        "it can be built with the project, the bottle is an alternative"
                                        % (label, detail)).lstrip("; ")
        # Unresolved but matches the project's own target/subdirectory: built with the project, not need_port
        if node is None and entry["kind"] == "package" and first_party_folds:
            hit_key = next((f for f in _loose_folds(entry["name"])
                            if f in first_party_folds), None)
            hit = first_party_folds[hit_key] if hit_key else None
            if hit:
                entry["kind"] = "in-tree"
                entry["artifact"] = {"ready": True, "provided": True,
                                     "source": "first-party:%s" % hit}
                entry["ohos_note"] = (
                    "the project's own target/directory (%s): built by this project's CMake, "
                    "no external artifact needed" % hit)
                fp_declared.append({"name": entry["name"], "fold": hit})
        if entry["kind"] == "system-lib":
            entry["artifact"] = entry["artifact"] or {
                "ready": True, "provided": True, "source": "ohos-system"}
        # version requirement check (see _version_check)
        entry["version_check"] = _version_check(entry)
        if conn is not None and node is not None and node["id"].startswith(("hb:", "cmdpkgs:")):
            for trans in _runtime_closure(conn, node["id"], graph_cache):
                r = runtime_book.get(trans["name"].lower())
                if r is None:
                    r = {"name": trans["name"], "kind": trans["kind"],
                         "version": trans.get("version"),
                         "port_status": trans.get("port_status"),
                         "artifact": _artifact_of(trans),
                         "needed_by": []}
                    runtime_book[trans["name"].lower()] = r
                if entry["name"].lower() not in r["needed_by"]:
                    r["needed_by"].append(entry["name"].lower())

    # ---- 7b) Merge the same library under different names: first by resolved_node (e.g.
    #          xkbcommon/libxkbcommon), then by the normalized name of the resolved node (lib
    #          prefix/@variant stripped, e.g. hb:qrencode and cmdpkgs:libqrencode are both
    #          qrencode), so one library doesn't show up as several contradictory entries)
    def _canon_pkg_name(n: str) -> str:
        n = (n or "").lower()
        if n.startswith("lib"):
            n = n[3:]
        at = n.find("@")
        return n[:at] if at > 0 else n

    def _dashless_merge_key(name: str) -> Optional[str]:
        """Separator-free merge key (libtorrent-rasterbar -> libtorrentrasterbar).

        Only for single-word names without whitespace (KF node names with whitespace such as
        "KF archive" are excluded, otherwise all KF components would wrongly merge under one key)
        and key length >= 6 (consistent with kb_seed.resolve_package_dashless's collision
        guard); when the name itself has no separators the key is name.lower() and no extra
        key is needed (the plain key of a flattened-name entry naturally collides with the
        separator-free key of a hyphenated entry -> merge).
        """
        if not re.fullmatch(r"[A-Za-z0-9@+_.-]+", name or ""):
            return None
        key = kb_seed._dashless_key(name)
        if len(key) < 6 or key == name.lower():
            return None
        return key

    by_key: Dict[str, Dict] = {}
    for entry in link_list:
        keys = []
        if entry.get("resolved_node"):
            keys.append(entry["resolved_node"])
            if entry.get("_resolved_name"):
                keys.append(_canon_pkg_name(entry["_resolved_name"]))
        else:
            keys.append(entry["name"].lower())
        # Same library under different names (flattened vs hyphenated) merges via the
        # separator-free key -- aligned with the grouping strategy of scan-time
        # project_scanner._link_third_party, so the deps table doesn't double-count one
        # unresolved library (two "needs source cross-compilation" warnings)
        dk = _dashless_merge_key(entry["name"])
        if dk:
            keys.append(dk)
        for key in keys:
            base = by_key.get(key)
            if base is not None and base is not entry:
                _merge_link_entries(base, entry)
                break
        else:
            for key in keys:
                by_key[key] = entry
            continue
    merged_ids = set()
    for base in by_key.values():
        merged_ids.add(id(base))
    link_list = sorted((e for e in link_list if id(e) in merged_ids),
                       key=lambda d: d["name"].lower())
    for entry in link_list:
        entry.pop("_resolved_name", None)
        # merging may have changed version fields, recompute the check
        entry["version_check"] = _version_check(entry)

    # ---- 8) dlopen/QLibrary/QPluginLoader runtime dynamic loading
    dynamic_loads = []
    for dl in info.get("dynamic_loads", []):
        raw = dl["name"]
        cand = re.sub(r"^lib", "", re.sub(r"\.(so|dll|dylib).*$", "", raw))
        node = (_resolve(conn, cand, resolve_cache)
                or _resolve(conn, raw, resolve_cache))
        dynamic_loads.append({
            "name": raw, "resolved_node": node["id"] if node else None,
            "artifact": _artifact_of(node),
            "how": dl["how"],
            "note": (None if node else
                     "runtime load target did not match a known package: if it is not a Qt plugin, confirm its origin"),
        })
        if node is None and not raw.startswith(("platform", "imageformats",
                                                "iconengines", "codecs",
                                                "styles", "sqldrivers")):
            warnings.append({
                "level": "warn",
                "msg": "dynamic load %s (%s) did not match a known package; Qt's own plugins"
                       " (platform/styles etc.) are deployed with the Qt SDK, others need confirmation"
                       % (raw, dl["how"][0])})

    # ---- 9) Qt modules (provided, with the Qt SDK)
    qt_modules = []
    resolve_cache: Dict = {}
    for mod in info.get("qt_modules", []):
        node = (project_scanner._resolve_qtmod(conn, mod, _cache=resolve_cache)
                if conn is not None else None)
        qt_modules.append({
            "module": mod, "node": node["id"] if node else None,
            "status": node["port_status"] if node else "unknown",
            "required": mod not in qt_optional_modules,
        })

    # ---- 10) toolchain
    toolchain_info = info.get("toolchain", {})
    meson_info = info.get("meson", {})
    tools = []
    for tool, hows in sorted(toolchain_info.get("tools", {}).items()):
        tools.append({"tool": tool, "how": hows[:3],
                      "provided_by": ("qt-sdk" if tool in QT_TOOL_NAMES
                                      else "host")})
    # build tool packages hit by find_package (ecm/gettext/doxygen etc.) are merged into the toolchain
    for bt in build_tools:
        tools.append({"tool": bt["tool"], "how": bt["how"],
                      "provided_by": bt["provided_by"],
                      "note": bt["note"]})
    cxx_std = toolchain_info.get("cxx_standard")
    if meson_info.get("cxx_standard"):
        cxx_std = max(cxx_std or 0, meson_info["cxx_standard"])
    if meson_info.get("version_min"):
        tools.append({"tool": "meson", "how": [">= %s (meson_version)"
                                               % meson_info["version_min"]],
                      "provided_by": "host"})
    toolchain = {
        "cmake_min": toolchain_info.get("cmake_min"),
        "cxx_standard": cxx_std,
        "compiler": "OHOS NDK clang (ships with the HarmonyOS SDK)",
        "cxx_note": (
            "OHOS NDK clang supports C++17; C++20 feature coverage must be confirmed per SDK version"
            if cxx_std and cxx_std >= 20 else
            ("C++%d: supported by OHOS NDK clang" % cxx_std if cxx_std else None)),
        "tools": tools,
        "has_testing": toolchain_info.get("has_testing", False),
        "note": "build tools only need to be available on the build machine (Windows/Linux/macOS all work), "
                "not deployed to the device; Qt tools (moc/uic/rcc) are invoked automatically with the Qt SDK",
    }

    # ---- 11) vendored (submodule / vendored directory / FetchContent and other configure-time fetches)
    vendored = [{"name": gm.get("name") or gm.get("path"),
                 "path": gm.get("path"), "url": gm.get("url"),
                 "note": "submodule: built with the project, commit pinned in the repo"}
                for gm in info.get("git_submodules", [])]
    vendored.extend({"name": d, "path": d, "url": None,
                     "note": "vendored directory: built together with the project"}
                    for d in info.get("vendored_dirs", []))
    vendored.extend({"name": fd["name"], "path": None, "url": fd.get("url"),
                     "tag": fd.get("tag"),
                     "note": "%s: source fetched at configure time and built with the project%s" % (
                         fd["how"],
                         ", pinned to %s" % fd["tag"] if fd.get("tag") else "")}
                    for fd in info.get("fetched_deps", []))
    vendored.extend({"name": sp, "path": "subprojects/%s" % sp, "url": None,
                     "note": "meson subproject: built together with the project"}
                    for sp in meson_info.get("subprojects", []))
    # bundled-source dependencies declared via require_source_dep (merged after dedup)
    vendored_names = {v["name"].lower() for v in vendored}
    vendored.extend(v for v in manifest_vendored
                    if v["name"].lower() not in vendored_names)

    # ---- 11b) environment dependencies (CI / install script apt/brew/pacman install lists)
    env_deps = []
    for env in info.get("env_installs", []):
        raw_name = env["name"]
        # distro package name -> approximate library name (libfoo-dev -> foo)
        cand = re.sub(r"-dev$", "", raw_name)
        if cand.startswith("lib") and len(cand) > 3:
            cand = cand[3:]
        node = (_resolve(conn, cand, resolve_cache)
                or _resolve(conn, raw_name, resolve_cache))
        env_deps.append({
            "name": raw_name, "resolved_node": node["id"] if node else None,
            "available_version": node["version"] if node else None,
            "evidence": env.get("evidence", [])[:2]})

    # ---- 12) Qt version check
    qt_check = None
    if qt_major:
        avail = QT_OHOS_AVAILABLE.get(str(qt_major))
        if avail:
            best = max(avail, key=_ver_key)
            qt_check = _check_min(qt_min, best)
        else:
            qt_check = "unknown"

    # ---- 13) summary and warnings
    for entry in link_list:
        if entry.get("version_req_from"):
            warnings.append({
                "level": "info",
                "msg": "the version constraint %s of %s comes from the library version of %s (alias merge), "
                       "not directly comparable with the %s package version (%s); needs manual confirmation"
                       % (entry.get("version_req"), entry["name"],
                          entry["version_req_from"], entry["name"],
                          entry.get("available_version") or "?")})
    for entry in link_list:
        if entry["kind"] in ("system-lib", "win32-system-lib"):
            continue
        if entry.get("version_check") == "conflict":
            wants = []
            if entry.get("version_range"):
                wants.append("[%s]" % entry["version_range"])
            if entry.get("version_req"):
                wants.append(entry["version_req"])
            if entry.get("min_version"):
                wants.append(">= %s" % entry["min_version"])
            warnings.append({
                "level": "warn",
                "msg": "%s version conflict: requires %s, HarmonyOS artifact is %s"
                       % (entry["name"], " and ".join(wants),
                          entry.get("available_version") or "?")})
        elif entry["kind"] == "platform-iface":
            if entry["required"]:
                warnings.append({
                    "level": "warn",
                    "msg": "%s talks directly to a platform stack: %s"
                           % (entry["name"],
                              entry.get("ohos_note") or "not supported on HarmonyOS")})
        elif not (entry.get("artifact") or {}).get("ready") and entry["required"]:
            warnings.append({
                "level": "warn" if entry["kind"] == "package" else "info",
                "msg": "%s has no HarmonyOS prebuilt artifact (required=%s): needs source cross-compilation%s"
                       % (entry["name"], entry["required"],
                          ", source: %s" % (entry["artifact"] or {}).get("repo_url")
                          if (entry["artifact"] or {}).get("repo_url") else "")})
    if info.get("build_system") == "qmake":
        warnings.append({
            "level": "info",
            "msg": "cross-compiling a qmake project needs a custom mkspec (see KB: the QScintilla case)"})
    if qt_check == "conflict":
        warnings.append({
            "level": "warn",
            "msg": "Qt version requirement %s is higher than the Qt for HarmonyOS available versions (%s)"
                   % (qt_min, "/".join(QT_OHOS_AVAILABLE.get(str(qt_major), ())))})

    # ---- 13b) cross-check environment lists: library names installed by CI but not declared in build files (potential misses)
    link_names = {e["name"].lower() for e in link_list}
    link_names.update(m["module"] for m in qt_modules)
    for ed in env_deps:
        cand = re.sub(r"-dev$", "", ed["name"].lower())
        if cand.startswith("lib") and len(cand) > 3:
            cand = cand[3:]
        if (ed["resolved_node"] is None and cand
                and cand not in link_names
                and not cand.startswith(("qt", "kf", "lxqt", "build-essential"))
                and cand not in {"meson", "ninja", "cmake", "git", "g++",
                                 "gcc", "pkg-config", "gettext", "ccache",
                                 "create-dmg", "flatpak", "flatpak-builder",
                                 "fakeroot", "devscripts", "debhelper",
                                 "asciidoctor", "python3"}):
            warnings.append({
                "level": "info",
                "msg": "CI script installs %s but build files don't declare it: it may come in via a variable "
                       "reference/custom Find module (check further), or be a build-machine tool only"
                       % ed["name"]})

    report = {
        "project": {
            "name": info["name"], "root": str(root),
            "build_system": info["build_system"], "version": version,
            "sources": len(info["sources"]),
        },
        "qt": {
            "major": qt_major, "min_version": qt_min,
            "check": qt_check,
            "available_on_ohos": list(QT_OHOS_AVAILABLE.get(str(qt_major), []))
            if qt_major else [],
            "modules": qt_modules,
            "kf_components": info.get("kf_components", []),
            "note": "Qt modules are provided by the Qt for HarmonyOS SDK, "
                    "harmonydeployqt handles deployment",
        },
        "toolchain": toolchain,
        "link_deps": link_list,
        "runtime_deps": list(runtime_book.values()),
        "dynamic_loads": dynamic_loads,
        "test_deps": test_deps,
        "vendored": vendored,
        "first_party": fp_declared,
        "env_deps": env_deps,
        "counts": {
            "link": len(link_list),
            "runtime": len(runtime_book),
            "dynamic_loads": len(dynamic_loads),
            # Consistent with the text report: the tools list + three fixed rows for CMake
            # minimum version/C++ standard/compiler (previously counted as
            # len(build_tools)+len(tools), but tools already contains the build_tools entries,
            # so it double-counted and missed the fixed rows)
            "build_tools": (len(toolchain["tools"])
                            + (1 if toolchain["cmake_min"] else 0)
                            + (1 if toolchain["cxx_standard"] else 0)
                            + 1),
            "test": len(test_deps),
            "vendored": len(vendored),
            "env": len(env_deps),
            "qt_modules": len(qt_modules),
        },
        "warnings": warnings,
    }
    return report


def _range_to_req(range_str: Optional[str]) -> Optional[str]:
    """conan range string '[>=1.2 <2]' -> take the first '>=x' constraint (approximate check)."""
    if not range_str:
        return None
    m = re.search(r">=\s*([\w.]+)", range_str)
    return ">= %s" % m.group(1) if m else None


# ---------------------------------------------------------------- rendering

def render_text(report: Dict) -> str:
    """Human-readable summary."""
    p = report["project"]
    q = report["qt"]
    t = report["toolchain"]
    lines: List[str] = []
    lines.append("=== Dependency analysis: %s%s ===" % (
        p["name"], " v%s" % p["version"] if p["version"] else ""))
    lines.append("Build system: %s | %d source files" % (p["build_system"], p["sources"]))
    if q.get("major"):
        check = {"satisfied": "✓ satisfied", "conflict": "✗ conflict",
                 "unknown": "? unknown"}.get(q.get("check"), "")
        lines.append("Qt: %s%s | available on HarmonyOS: %s %s" % (
            q["major"], " (>= %s)" % q["min_version"] if q.get("min_version") else "",
            "/".join(q.get("available_on_ohos") or ["?"]), check))
    blocked_qt = [m["module"] for m in q["modules"] if m["status"] == "blocked"]
    if blocked_qt:
        lines.append("Blocked Qt modules: %s" % ", ".join(blocked_qt))

    def _ver(e):
        parts = []
        if e.get("min_version"):
            parts.append(">= %s" % e["min_version"])
        if e.get("version_req"):
            parts.append(e["version_req"])
        if e.get("version_range"):
            parts.append("[%s]" % e["version_range"])
        return " ".join(parts)

    def _art(e):
        a = e.get("artifact") or {}
        if e.get("kind") == "system-lib":
            return "ships with the system"
        if e.get("kind") == "win32-system-lib":
            return "Windows system library (not applicable to HarmonyOS)"
        if e.get("kind") == "platform-iface":
            return "platform interface (HarmonyOS does not support direct use)"
        if a.get("ready"):
            return "artifact: %s" % a.get("source")
        if a.get("provided"):
            return "provided by the framework"
        return "no artifact -> needs source build"

    # group ordering: real external packages first, then framework/system libraries/platform interfaces
    _kind_rank = {"package": 0, "framework": 1, "system-lib": 2,
                  "win32-system-lib": 3, "platform-iface": 4,
                  "in-tree": 5}
    lines.append("")
    lines.append("── Build artifact dependencies (link): %d, target-side headers+libs, "
                 "must exist when cross-compiling/linking ──" % len(report["link_deps"]))
    for e in sorted(report["link_deps"],
                    key=lambda d: (_kind_rank.get(d.get("kind"), 0),
                                   d["name"].lower())):
        req = "" if e["required"] else " [optional]"
        vc = {"satisfied": " ✓", "conflict": " ✗ version conflict",
              "unknown": ""}.get(e.get("version_check"), "")
        lines.append("  • %s %s%s%s (%s)"
                     % (e["name"], _ver(e), req, vc, e["kind"]))
        lines.append("      %s" % _art(e))
        if e.get("available_version"):
            lines.append("      HarmonyOS version: %s%s" % (
                e["available_version"],
                "" if e.get("version_check") != "conflict" else " (below requirement)"))
        if e.get("evidence"):
            lines.append("      evidence: %s" % e["evidence"][0])
        if e.get("ohos_note"):
            lines.append("      note: %s" % e["ohos_note"])

    lines.append("")
    lines.append("── Compiler/toolchain dependencies (build-tool): %d, run on the build machine, "
                 "not deployed to the device ──" % report["counts"]["build_tools"])
    if t.get("cmake_min"):
        lines.append("  • CMake >= %s (cmake_minimum_required)" % t["cmake_min"])
    if t.get("cxx_standard"):
        lines.append("  • C++%d (%s)" % (t["cxx_standard"], t["cxx_note"] or ""))
    lines.append("  • compiler: %s" % t["compiler"])
    for tool in t.get("tools", []):
        lines.append("  • %s (%s)" % (tool["tool"],
                                      "provided by Qt SDK" if tool["provided_by"] == "qt-sdk"
                                      else "prepare on build machine: " + tool["how"][0]))

    rt = report["runtime_deps"]
    lines.append("")
    lines.append("── Runtime dependencies (runtime): %d, device-side .so, "
                 "deployed to entry/libs/arm64-v8a/ ──" % len(rt))
    for e in rt[:40]:
        a = e.get("artifact") or {}
        src = ("artifact: %s" % a["source"] if a.get("ready")
               else "no artifact -> needs source build along with its origin")
        lines.append("  • %s v%s — %s (transitive from %s)"
                     % (e["name"], e.get("version") or "?", src,
                        ", ".join(e.get("needed_by", [])[:3])))
    if len(rt) > 40:
        lines.append("  … %d more transitive dependencies" % (len(rt) - 40))
    for dl in report["dynamic_loads"]:
        lines.append("  • [dynamic load] %s (%s)%s" % (
            dl["name"], dl["how"][0],
            " -> " + (dl["artifact"].get("source") or "no known package matched")
            if dl.get("artifact") else ""))

    if report["test_deps"]:
        lines.append("")
        lines.append("── Test dependencies (test): %d, not shipped in the release package ──"
                     % len(report["test_deps"]))
        for e in report["test_deps"]:
            lines.append("  • %s — %s" % (e["name"], e["source"]))

    if report["vendored"]:
        lines.append("")
        lines.append("── Bundled source (vendored): %d, built with the project, "
                     "no external artifact needed ──" % len(report["vendored"]))
        for e in report["vendored"]:
            lines.append("  • %s (%s)%s" % (e["name"], e["note"],
                                            " %s" % e["url"] if e.get("url") else ""))

    env = report.get("env_deps", [])
    if env:
        lines.append("")
        lines.append("── Environment dependencies (env, installed by CI/scripts): %d, build-machine "
                     "environment list, a cross-check source ──" % len(env))
        for e in env[:25]:
            res = ("→ %s v%s" % (e["resolved_node"], e["available_version"])
                   if e.get("resolved_node") else "(no known package matched)")
            lines.append("  • %s %s" % (e["name"], res))
        if len(env) > 25:
            lines.append("  … %d more" % (len(env) - 25))

    if report["warnings"]:
        lines.append("")
        lines.append("── Warnings/notes: %d ──" % len(report["warnings"]))
        for w in report["warnings"]:
            lines.append("  %s %s" % ("[!]" if w["level"] == "warn" else "[i]",
                                      w["msg"]))
    return "\n".join(lines)
