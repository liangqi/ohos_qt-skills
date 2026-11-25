"""Qt project scanning: reuses the vendored qt_scanner, adding platform interface detection and graph node generation.

Outputs:
- app:<name> node (plain attributes)
- uses-module edges -> qtmod:* (Qt modules)
- runtime edges -> ingested package nodes / pkg-unknown:* phantom nodes (third-party libraries)
- optional edges -> dependencies not in the default build (declared inside CMake options that default to OFF;
  not part of the runtime closure/portability analysis, only for the presentation layer and manual review)
- node_interfaces records (platform interface usage + evidence)
"""

from __future__ import annotations

import re
import warnings
from bisect import bisect_right
from pathlib import Path
from typing import Dict, List, Optional

from . import db, kb_seed
from . import qt_scanner
# The macro stack mechanism moved into qt_scanner (qt_scanner's dynamic_loads detection also needs
# per-line platform guard filtering); re-exported here to keep module-level names compatible with existing tests
from .qt_scanner import (  # noqa: F401
    NON_OHOS_PLATFORM_MACROS, OHOS_OR_GENERAL_MACROS, FEATURE_MACROS,
    _extract_defined_macros, _macro_compiles_on_ohos,
    _expr_compiles_on_ohos, _guard_status, _macro_stack_status,
)

# Platform interface detection rules: iface_id -> (regex)
# Note: only actual API calls/header includes are detected, not platform macro references (Q_OS_WIN/_WIN32, etc.),
# because platform macro references are themselves conditional-compilation guards, handled by macro stack tracking
PLATFORM_API_RULES: List[Dict] = [
    {"iface": "iface:win32",
     # Function-like symbols must carry call parentheses: same-named members/plain identifiers such as `engine::SendMessage{`
     # were once counted as Win32 API calls (observed false positive). Type names (HWND/HDC...) still match bare.
     "re": re.compile(r"#\s*include\s*<\s*(windows|shellapi|shlobj|winuser|"
                      r"wingdi|winbase|winsock2|commctrl|commdlg)\.h\s*>|"
                      r"\b(CreateWindow|SendMessage|PostMessage|GetMessage|"
                      r"LoadLibrary|GetProcAddress|CreateFile|ReadFile|WriteFile|"
                      r"VirtualAlloc|HeapAlloc|RegOpenKey|RegQueryValue|"
                      r"CoCreateInstance)\s*\(|"
                      r"\b(IDispatch|IUnknown|HWND|HDC|HINSTANCE)\b"),
     "pre": ("windows.h", "shellapi", "shlobj", "winuser", "wingdi",
             "winbase", "winsock2", "commctrl", "commdlg", "CreateWindow",
             "SendMessage", "PostMessage", "GetMessage", "LoadLibrary",
             "GetProcAddress", "CreateFile", "ReadFile", "WriteFile",
             "VirtualAlloc", "HeapAlloc", "RegOpenKey", "RegQueryValue",
             "CoCreateInstance", "IDispatch", "IUnknown", "HWND", "HDC",
             "HINSTANCE")},
    {"iface": "iface:x11",
     "re": re.compile(r"#\s*include\s*<\s*(X11|xcb|Xlib)\b"),
     "pre": ("X11", "xcb", "Xlib")},
    {"iface": "iface:wayland",
     "re": re.compile(r"#\s*include\s*<\s*wayland-client"),
     "pre": ("wayland-client",)},
    {"iface": "iface:dbus",
     "re": re.compile(r"#\s*include\s*<\s*dbus/|\bQDBusConnection\b|"
                       r"#\s*include\s*<\s*QtDBus"),
     "pre": ("dbus/", "QDBusConnection", "QtDBus")},
    {"iface": "iface:alsa",
     # Only real ALSA API prefixes: a bare snd_ matches any variable name
     # (seen in gen_j/rizin: the variable name snd_last_ch in a generated scanner.c
     # once caused the whole app to be misjudged as blocked)
     "re": re.compile(r"#\s*include\s*<\s*alsa/|\bsnd_(pcm|ctl|mixer|seq|"
                       r"rawmidi|card|config|lib|hwdep|timer|input|output|"
                       r"error)[_\w]*"),
     "pre": ("alsa/", "snd_pcm", "snd_ctl", "snd_mixer", "snd_seq",
             "snd_rawmidi", "snd_card", "snd_config", "snd_lib",
             "snd_hwdep", "snd_timer", "snd_input", "snd_output",
             "snd_error")},
    {"iface": "iface:pulseaudio",
     "re": re.compile(r"#\s*include\s*<\s*pulse/|\bpa_simple|\bpa_mainloop"),
     "pre": ("pulse/", "pa_simple", "pa_mainloop")},
    {"iface": "iface:coreaudio",
     "re": re.compile(r"#\s*include\s*<\s*(CoreAudio|AudioToolbox|"
                      r"CoreAudioTypes|CoreMIDI)\b|\bAudioUnit\b|\bMIDIPortRef\b"),
     "pre": ("CoreAudio", "AudioToolbox", "CoreMIDI", "AudioUnit",
             "MIDIPortRef")},
    {"iface": "iface:cocoa",
     "re": re.compile(r"#\s*(include|import)\s*<\s*(Cocoa|AppKit|Foundation|IOKit)/"
                      r"|\bNS(Window|View|Application|Responder|Object)\b|"
                      r"@interface\b|@implementation\b|^\s*@\w+\b"),
     # "@" alone as an anchor: covers the ^\s*@\w+ branch (start of text); better a wasted run than a miss
     "pre": ("Cocoa", "AppKit", "Foundation", "IOKit", "NSWindow", "NSView",
             "NSApplication", "NSResponder", "NSObject", "@")},
    {"iface": "iface:systemd",
     "re": re.compile(r"#\s*include\s*<\s*systemd/|"
                      r"\b(sd_listen_fds|sd_notify|sd_notifyf|sd_watchdog|"
                      r"sd_booted|sd_journal_)\b"),
     "pre": ("systemd/", "sd_listen", "sd_notify", "sd_watchdog",
             "sd_booted", "sd_journal_")},
    {"iface": "iface:dylib",
     "re": re.compile(r"\bdlopen\s*\(|\bLoadLibrary[AW]?\s*\(|"
                      r"\bdlsym\s*\(|\bdlclose\s*\("),
     "pre": ("dlopen", "dlsym", "dlclose", "LoadLibrary")},
    {"iface": "iface:gpu-desktop-gl",
     "re": re.compile(r"#\s*include\s*<\s*GL/gl\.h|\bglBegin\s*\(|\bglClear\s*\(")
     ,
     "pre": ("GL/gl.h", "glBegin", "glClear")},
    {"iface": "iface:fork-exec",
     "re": re.compile(r"\bfork\s*\(\s*\)"),
     "pre": ("fork",)},
]

# File-level platform isolation: files whose paths contain these keywords are entirely platform-specific,
# and are not compiled for HarmonyOS at the CMake level -> interfaces in them count as platform-file-excluded
# (note: linux paths are not listed, because HarmonyOS compiles generic Linux code)
NON_OHOS_PLATFORM_PATH_HINTS = (
    ("macos", ("platform/macos", "platform/osx", "platform/apple",
               "platform/darwin", "/macos/", "/osx/", "/apple/",
               "/mac/", "/darwin/")),
    ("windows", ("platform/windows", "platform/win", "/windows/", "/win32/",
                 "/winrt/", "/win/")),
    ("android", ("platform/android", "/android/")),
    ("ios", ("platform/ios", "/ios/")),
)


# File name suffixes also express platform ownership: desktop projects often use `xxx_win.cpp` / `xxx_mac.mm`
# instead of a platform/win directory. Looking only at directories misses a whole class of files.
NON_OHOS_FILE_SUFFIX = (
    ("macos", (".mm", "_macos.cpp", "_macos.mm", "_osx.cpp", "_osx.mm",
               "_darwin.cpp", "_darwin.mm", "_cocoa.mm")),
    ("windows", ("_win.cpp", "_win32.cpp", "_windows.cpp", "_winrt.cpp",
                 "_win.h", "_win32.h")),
)


def _file_platform_excluded(file_rel: str) -> Optional[str]:
    """Decide from the file path whether this is a file specific to a non-HarmonyOS platform."""
    rel = file_rel.lower().replace("\\", "/")
    for plat, hints in NON_OHOS_PLATFORM_PATH_HINTS:
        for hint in hints:
            if hint in rel:
                return plat
    # Suffixes like `_win.cpp`: only the file name is checked, to avoid collateral hits beyond `darwin_helper.cpp`
    # (darwin is a path hint for mac); `_osx`/`_macos` are also covered by the path hints.
    name = rel.rsplit("/", 1)[-1]
    for plat, suffixes in NON_OHOS_FILE_SUFFIX:
        for suffix in suffixes:
            if name.endswith(suffix):
                return plat
    return None

_PROJECT_VER_RE = re.compile(
    r"project\s*\([^)]*VERSION\s+([0-9.]+)", re.I | re.S)


def normalize_app_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _detect_platform_interfaces(root: Path, scan_info: Dict) -> List[Dict]:
    """Scan sources and return [{iface, hits: [{file, line, guard}], guard_distribution}].

    guard values:
      - unconditional:       no guard, compiled on HarmonyOS
      - ohos-active:         HarmonyOS/generic guard, compiled on HarmonyOS
      - platform-excluded:   wrapped in a non-HarmonyOS platform macro guard, not compiled on HarmonyOS
      - platform-file-excluded: the file itself is specific to a non-HarmonyOS platform, not compiled by CMake

    The overall guard of an interface = its most "dangerous" hit:
      - any unconditional/ohos-active hit -> overall ohos-active
      - otherwise all hits are platform-excluded/platform-file-excluded -> platform-excluded
    """
    hits: Dict[str, Dict] = {}
    for src in scan_info["sources"]:
        if src["ext"] not in qt_scanner.TEXT_SCAN_EXTS:
            continue
        path = root / src["path"]
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # Run the interface rules first: with no hits, skip per-line macro stack tracking (most files have no platform API
        # calls; previously the full per-line regex pass over every source file took 3/4 of total scan time)
        file_matches: List = []
        for rule in PLATFORM_API_RULES:
            # Literal anchors first: no anchor means no match (every regex branch contains these required substrings);
            # measured on 35MB of source: regex scan 7s -> <1s after anchor filtering
            if not any(a in text for a in rule.get("pre", ())):
                continue
            for m in rule["re"].finditer(text):
                file_matches.append((rule, m))
        if not file_matches:
            continue
        file_plat = _file_platform_excluded(src["path"])
        guard_by_line = _macro_stack_status(text)
        lines = text.splitlines()
        # Precompute newline offsets and locate line numbers by binary search (O(n log n) instead of O(n*m))
        nl_offsets = [i for i, ch in enumerate(text) if ch == "\n"]
        for rule, m in file_matches:
                # line number = number of preceding newlines + 1
                line_no = bisect_right(nl_offsets, m.start()) + 1
                # File-level platform isolation takes precedence over line-level guards
                if file_plat:
                    guard = "platform-file-excluded"
                else:
                    guard = guard_by_line.get(line_no, "ohos-active")
                h = hits.setdefault(
                    rule["iface"],
                    {"iface": rule["iface"], "hits": [],
                     "guard_counts": {"unconditional": 0, "ohos-active": 0,
                                      "platform-excluded": 0,
                                      "platform-file-excluded": 0}})
                if len(h["hits"]) < 5:
                    h["hits"].append({"file": src["path"], "line": line_no,
                                      "guard": guard,
                                      "snippet": lines[line_no - 1].strip()[:80]})
                h["guard_counts"][guard] = h["guard_counts"].get(guard, 0) + 1

    result = []
    for h in hits.values():
        gc = h["guard_counts"]
        if gc.get("unconditional", 0) > 0 or gc.get("ohos-active", 0) > 0:
            overall = "ohos-active"
        else:
            overall = "platform-excluded"
        result.append({"iface": h["iface"], "hits": h["hits"],
                       "guard": overall, "guard_counts": gc})
    return result


def _resolve_qtmod(conn, key: str, _cache: Optional[Dict] = None) -> Optional[Dict]:
    """Scanned module name -> qtmod node (supports prefix matching, e.g. webenginewidgets->webengine).

    _cache reuses the loaded Qt module list within one scan, avoiding repeated full table scans.
    """
    node = db.get_node(conn, "qtmod:%s" % key)
    if node:
        return node
    if _cache is None or "qtmods" not in _cache:
        rows = conn.execute(
            "SELECT * FROM nodes WHERE kind='qt-module'").fetchall()
        qtmods = [(r["id"][len("qtmod:"):], dict(r)) for r in rows]
        if _cache is not None:
            _cache["qtmods"] = qtmods
    else:
        qtmods = _cache["qtmods"]
    cands = []
    for rkey, rdict in qtmods:
        if key.startswith(rkey) or rkey.startswith(key):
            cands.append((min(len(key), len(rkey)), rdict))
    if cands:
        cands.sort(key=lambda t: -t[0])
        return cands[0][1]
    return None


_SET_VER_PART_RE = re.compile(r'VERSION_(MAJOR|MINOR|PATCH)\s+"?(\d+)"?')


def _detect_version(root: Path) -> Optional[str]:
    for cmake in ("CMakeLists.txt", "version.cmake"):
        p = root / cmake
        if not p.exists():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = _PROJECT_VER_RE.search(text)
        if m:
            return m.group(1)
        parts = {}
        for pm in _SET_VER_PART_RE.finditer(text):
            parts.setdefault(pm.group(1), pm.group(2))
        if "MAJOR" in parts:
            return ".".join(parts[k] for k in ("MAJOR", "MINOR", "PATCH")
                            if k in parts)
    return None


def _link_kf_components(conn, app_id: str, components: List[str]) -> None:
    """Build KDE Frameworks components as framework subproject nodes and connect edges, for recursive analysis by the engine.

    app -> kf:component (runtime); kf:component -> qtmod:* (uses-module) /
    kf:subcomponent (runtime); platform interfaces of kf:component are written to node_interfaces.
    Sub-framework dependencies between components are expanded by BFS, avoiding a blanket blocked verdict.
    """
    seen = set()
    queue = [(app_id, c) for c in components]
    while queue:
        parent_id, comp = queue.pop(0)
        kf_id = "kf:%s" % comp
        db.upsert_edge(conn, parent_id, kf_id, "runtime")
        if comp in seen:
            continue
        seen.add(comp)
        db.upsert_node(
            conn, kf_id, "framework", "KF %s" % comp, "scan", "unknown",
            description="KDE Frameworks component (subproject, analyzed recursively)",
            port_evidence="decided recursively from its Qt modules/platform interfaces/sub-framework dependencies")
        deps = kb_seed.KF_DEPS.get(comp, {"qt": ["core"], "kf": [], "ifaces": []})
        for q in deps.get("qt", []):
            if db.get_node(conn, "qtmod:%s" % q):
                db.upsert_edge(conn, kf_id, "qtmod:%s" % q, "uses-module")
        for ifc in deps.get("ifaces", []):
            db.add_node_interface(conn, kf_id, ifc)
        for k2 in deps.get("kf", []):
            queue.append((kf_id, k2))


def _fold_dep_name(n: str) -> str:
    """Fold a dependency name: lowercase, drop non-alphanumerics (normalizes separator/case differences)."""
    return re.sub(r"[^a-z0-9]+", "", (n or "").lower())


def _submodule_folds(git_submodules: List[Dict]) -> set:
    """Set of folded git submodule names (name / last path segment / last url segment): used to recognize vendored dependencies."""
    folds = set()
    for gm in git_submodules or []:
        cands = [gm.get("name") or ""]
        path = gm.get("path") or ""
        cands.append(path.rsplit("/", 1)[-1])
        url = (gm.get("url") or "").rstrip("/")
        last = url.rsplit("/", 1)[-1]
        if last.endswith(".git"):
            last = last[:-4]
        cands.append(last)
        for c in cands:
            f = _fold_dep_name(c)
            if len(f) >= 3:
                folds.add(f)
    return folds


def _resolve_pkg_node(conn, name: str) -> tuple:
    """Package name -> (node, alias): if the direct name fails, retry via kb_seed.PKG_ALIASES.

    Avoids pkg-unknown phantom nodes for the same library under a different name (fetch-deps would falsely report need_port
    while the bottle the alias points to actually exists).
    """
    node = kb_seed.resolve_package(conn, name)
    alias_used = None
    if node is None:
        aliases = kb_seed.PKG_ALIASES.get(name.lower())
        if isinstance(aliases, str):
            aliases = [aliases]
        for alias in aliases or []:
            node = kb_seed.resolve_package(conn, alias.lower())
            if node:
                alias_used = alias
                break
    return node, alias_used


def _link_third_party(conn, app_id: str, info: Dict) -> Dict:
    """Connect third-party packages found by CMake find_package/pkg_check_modules + Conan/vcpkg manifests + dependency-list
    functions (require_dep, etc.) to known package nodes; unmatched ones are recorded as
    unknown package nodes. require_source_dep (bundled source) -> vendored edge;
    require_tool (host build tool) gets no edge.

    Enhancements from three rounds of real-world testing (driven by e2e corpus_a/corpus_b/corpus_d reviews):
    - build tools/interpreters hit by find_package (python3, etc.) get no runtime edge -
      those are build-time dependencies, classified as build-tool on the deps_report side;
    - ns::external_<name> imported target names in target_link_libraries (after stripping the prefix
      they are in raw_libs with ext_target=True): connected if resolvable; if unresolvable and not
      a vendored submodule, a phantom node is created (high-confidence declaration, e.g. all of corpus_a's third-party libs);
    - merging same-library aliases: find_package CamelCase flattened names (LibtorrentRasterbar ->
      libtorrentrasterbar) and pkg-config hyphenated names (libtorrent-rasterbar) are grouped by
      separator-stripped key, with one representative name per group, avoiding duplicate phantom nodes/downloads;
    - declarations inside CMake options that default to OFF (not in the default build) get optional edges
      and are not part of the runtime closure/portability analysis.

    Returns {linked: [...], unknown: [...], optional: [...], vendored: [...]}.
    """
    # Build tool/platform interface names get neither a package node nor a phantom (python3/ecm/gettext are
    # host-side tools, systemd/alsa are platform interfaces, covered by the analyze/deps classification;
    # previously a pkg-unknown:python3 phantom was counted by fetch-deps as need_port)
    from . import deps_report as _dr      # imported inside the function to avoid a circular import
    _skip = (_dr.BUILD_TOOL_FINDPKG.keys() | _dr.INTERFACE_BOUND_PACKAGES.keys()
             | _dr.QT_TOOL_NAMES)
    cp = info.get("cmake_packages", {})
    # find_package build tools (python3/cmake/...) are not app runtime dependencies
    names: List[str] = [n for n in cp.get("find_package", [])
                        if n not in qt_scanner.BUILD_TOOL_FINDPKG]
    names.extend(n for n in cp.get("find_package_optional", [])
                 if n not in qt_scanner.BUILD_TOOL_FINDPKG)
    names.extend(cp.get("pkg_check_modules", []))
    names.extend(cp.get("pkg_check_modules_optional", []))
    pm = info.get("pkg_manifests", {})
    for c in pm.get("conan", []):
        names.append(c["name"])
    for v in pm.get("vcpkg", []):        # a vcpkg entry may be a str or {name, version}
        names.append(v["name"] if isinstance(v, dict) else v)
    # Merge third-party libraries found via source #include (deduplicated, order preserved)
    for h in info.get("third_party_hints", []):
        if h["name"] not in names:
            names.append(h["name"])
    # Dependency-list functions (require_dep): resolved on an equal footing with find_package
    manifest = info.get("manifest_deps", [])
    for md in manifest:
        if md["mode"] == "link" and md["name"] not in names:
            names.append(md["name"])
    # project() self-references (e.g. find_package(gen_j) in the gen_j plugin sample):
    # not an external dependency; avoid resolving to an unrelated same-named package (seen with cmdpkgs:gen_j)
    self_names = {n.lower() for n in info.get("cmake_project_names", [])}
    if self_names:
        names = [n for n in names if n.lower() not in self_names]

    # optional list: packages whose every declaration is inside an OFF-by-default option guard
    # (the scanner layer already gives required precedence: any required declaration keeps it off the optional list)
    # Project-owned names (CMake targets / directories with build files / subproject names): if unresolved,
    # they are things this repository builds, not "'a third-party library missing from the knowledge base'"
    fp_folds = qt_scanner.first_party_folds(info)
    first_party: List[Dict] = []

    optional_names = set(cp.get("find_package_optional", []))
    optional_names.update(cp.get("pkg_check_modules_optional", []))
    optional_names.update(spec["name"] for spec in
                          cp.get("pkg_modules", []) if spec.get("optional"))

    def _resolve(name: str, dashless_index: Dict[str, str]):
        # Shares the resolution ladder with deps_report._resolve (alias first -> original name -> lib
        # prefix variants -> version suffix stripped): scanning no longer creates pkg-unknown phantom nodes
        # for lack of lib-prefix stripping (seen with libsparsehash/gstreamer-1.0)
        node = kb_seed.resolve_pkg_name(conn, name)
        alias_used = None
        canon = kb_seed.PKG_ALIASES.get(name.lower())
        if node is not None:
            # Mark resolutions merged via the alias table (libavcodec -> ffmpeg)
            if canon and canon.lower() == (node.get("name") or "").lower():
                alias_used = canon
        else:
            # Fallback: separator-stripped matching (CamelCase flattened name -> hyphenated package name)
            node = kb_seed.resolve_package_dashless(conn, name, dashless_index)
            if node:
                alias_used = "dashless"
        return node, alias_used

    def _emit(name: str, node, alias_used=None, via=None, merged=None,
              edge_type="runtime"):
        """Write a resolution result to the graph: when node is None, create a phantom node (using the alias table's canonical name,
        so same-library aliases botan3/botan-3 merge into one phantom instead of a double need_port)."""
        if node is None and fp_folds:
            fold = qt_scanner._fold_name(name)
            if fold in fp_folds:
                # Subdirectories/targets bundled with the project (tdesktop's external_auto_updates
                # and the like): the source is compiled with the project, so neither a node nor a phantom
                first_party.append({"hint": name, "fold": fold})
                return
        if node is not None:
            target_id = node["id"]
            status = node["port_status"]
        else:
            # Phantom nodes use the alias table's canonical name (same-library aliases botan3/botan-3 merge into
            # one phantom instead of a double need_port)
            canon = kb_seed.PKG_ALIASES.get(name.lower())
            if canon and canon.lower() != name.lower():
                name = canon
            target_id = "pkg-unknown:%s" % normalize_app_name(name)
            status = "unknown"
            db.upsert_node(
                conn, target_id, "package", name, "scan", "unknown",
                description="third-party library found by scanning, not matched to a known package source",
                port_evidence="not in the Harmonybrew/cmd-pkgs known list")
        db.upsert_edge(conn, app_id, target_id, edge_type)
        item = {"hint": name, "node": target_id, "status": status}
        if alias_used:
            item["alias"] = alias_used
        if via:
            item["via"] = via
        if merged:
            item["merged_from"] = merged
        if edge_type == "optional":
            item["optional"] = True
            optional.append(item)
        elif node is not None:
            linked.append(item)
        else:
            unknown.append(item)

    linked, unknown, optional = [], [], []
    seen = set()
    # Folded git submodule names (computed early: shared by the main list and bare link names) -
    # find_package(Rizin) while the repo bundles a rizin/ submodule (bundled build by default):
    # no phantom, the source comes with the project (seen with gen_j)
    submodule_folds = _submodule_folds(info.get("git_submodules", []))

    # ---- Main list: group same-library aliases (group representative = one that resolves to a known package >
    #      one with separators (pkg-config/hb naming convention) > the first seen).
    #      The group key is the separator-stripped key after alias normalization: ddjvuapi->djvulibre,
    #      usb-1.0->libusb and similar aliases join the same group via the alias table, no longer producing duplicate
    #      unknown entries (seen with gen_b's double djvulibre phantom)
    dashless_index = kb_seed.build_dashless_index(conn)
    groups: Dict[str, List[str]] = {}
    order: List[str] = []
    for name in names:
        canon = kb_seed.PKG_ALIASES.get(name.lower()) or name
        key = kb_seed._dashless_key(canon)
        if key not in groups:
            groups[key] = []
            order.append(key)
        if name not in groups[key]:
            groups[key].append(name)
        seen.add(name.lower())

    for key in order:
        members = groups[key]
        dashed = [n for n in members if re.search(r"[-_.]", n)]
        rep, rep_node, rep_alias = None, None, None
        for cand in dashed + [m for m in members if m not in dashed]:
            node, alias = _resolve(cand, dashless_index)
            if node:
                rep, rep_node, rep_alias = cand, node, alias
                break
        if rep is None:
            rep = dashed[0] if dashed else members[0]
        merged = [m for m in members if m != rep]
        # Any required member -> required (conservative: when optional and required declarations coexist, treat as required)
        edge_type = ("runtime" if any(m not in optional_names
                                      for m in members) else "optional")
        # Build tool/platform interface names (python3/ecm/systemd) with no resolvable artifact
        # get neither a node nor a phantom (covered by the analyze/deps classification); resolvable ones
        # (e.g. alsa -> cmdpkgs:alsa-lib) are connected normally; phantoms of optional declarations keep
        # their optional edge (not in the closure, information only)
        if (rep_node is None and edge_type == "runtime"
                and rep.lower() in _skip):
            continue
        # Unresolved and the name folds to a git submodule (bundled and compiled with the project by default): no phantom
        if rep_node is None and _fold_dep_name(rep) in submodule_folds:
            continue
        _emit(rep, rep_node, rep_alias, merged=merged, edge_type=edge_type)

    # ---- Bare link names (including ns::external_<name> imported targets, marked
    #      ext_target after prefix stripping): connected if resolvable; high-confidence external-target declarations
    #      get a phantom node when unresolved and not a vendored submodule
    for rl in info.get("raw_libs", []):
        name = rl["name"]
        # Bare link declarations inside other platforms' if blocks (gen_c if(HAIKU) network, gen_b
        # mobile if(ANDROID) -lsoftokn3, etc.): not in the default HarmonyOS build, no edge
        if rl.get("platform_block"):
            continue
        if name.lower() in seen:
            continue
        # Same-library aliases: entries for the same library by flattened name/alias were skipped during main-list grouping
        canon = kb_seed.PKG_ALIASES.get(name.lower()) or name
        if kb_seed._dashless_key(canon) in groups:
            continue
        seen.add(name.lower())
        # Windows system libraries (usually in win32 platform blocks): skipped, to prevent wrongly connecting same-named Unix
        # libraries (bcrypt -> OpenBSD bcrypt)
        if name.lower() in qt_scanner.WIN32_SYSTEM_LIBS:
            continue
        node, alias_used = _resolve(name, dashless_index)
        if node:
            _emit(name, node, alias_used,
                  via="external-target" if rl.get("ext_target") else None)
        elif rl.get("ext_target"):
            # vendored submodules (declared in .gitmodules, compiled with the project) get no phantom:
            # the dependency is self-contained in the project source, not an external package to fetch/port
            if _fold_dep_name(name) in submodule_folds:
                continue
            if len(name) >= 3:
                _emit(name, None)

    # require_source_dep: bundled source dependency -> vendored edge (compiled with the project,
    # fetch-deps marks role=vendored, not counted as need_port)
    vendored = []
    for md in manifest:
        if md["mode"] != "source":
            continue
        name = md["name"]
        node, alias_used = _resolve(name, dashless_index)
        if node:
            vid = node["id"]
            status = node["port_status"]
        else:
            vid = "pkg-unknown:%s" % normalize_app_name(name)
            status = "unknown"
            db.upsert_node(
                conn, vid, "package", name, "scan", "unknown",
                description="bundled source dependency declared in the dependency list (require_source_dep), "
                            "compiled with the project source",
                port_evidence="not in the Harmonybrew/cmd-pkgs known list (vendored, "
                              "no external artifact needed)")
        db.upsert_edge(conn, app_id, vid, "vendored")
        item = {"hint": name, "node": vid, "status": status,
                "evidence": md["evidence"][:1]}
        if alias_used:
            item["alias"] = alias_used
        vendored.append(item)
    return {"linked": linked, "unknown": unknown, "optional": optional,
            "vendored": vendored, "first_party": first_party}


def scan_project(conn, project_root, info: Dict = None) -> Dict:
    """Scan a Qt project and write it to the graph. Returns a summary.

    info: a qt_scanner.scan_project result may be passed in for reuse (avoids rescanning large repositories).
    """
    root = Path(project_root).resolve()
    info = info or qt_scanner.scan_project(root)
    db.init_db(conn)

    app_id = "app:%s" % normalize_app_name(info["name"])
    version = _detect_version(root)
    # Record the project root path: commands such as deps / fetch-deps trace back to the source location by app name
    db.set_meta(conn, "root_%s" % app_id, str(root))
    db.upsert_node(
        conn, app_id, "app", info["name"], "scan", "unknown",
        version=version,
        description="Qt %s app, build system %s, %d source files" % (
            info.get("qt_version_hint") or "?", info["build_system"],
            len(info["sources"])),
        port_evidence="scanned, pending portability analysis")

    # Clear old outgoing edges and interface records (rescans are idempotent)
    conn.execute("DELETE FROM edges WHERE src=?", (app_id,))
    conn.execute("DELETE FROM node_interfaces WHERE node_id=?", (app_id,))

    # Qt module edges
    modules_linked, modules_without_kb_node = [], []
    resolve_cache: Dict = {}
    for mod in info["qt_modules"]:
        node = _resolve_qtmod(conn, mod, _cache=resolve_cache)
        if node:
            db.upsert_edge(conn, app_id, node["id"], "uses-module")
            modules_linked.append({"module": mod, "node": node["id"],
                                   "status": node["port_status"]})
        else:
            modules_without_kb_node.append(mod)

    # Third-party dependency edges (find_package/pkg_check_modules/Conan/vcpkg/include/
    # require_dep; require_source_dep -> vendored edge)
    tp = _link_third_party(conn, app_id, info)
    deps_linked, deps_unknown = tp["linked"], tp["unknown"]
    deps_optional = tp.get("optional", [])

    # KDE Frameworks components -> analyzed recursively as subproject nodes (no longer a blanket blocked verdict)
    _link_kf_components(conn, app_id, info.get("kf_components", []))

    # Platform interface usage
    ifaces = _detect_platform_interfaces(root, info)
    for h in ifaces:
        gc = h["guard_counts"]
        guard_label = {
            "unconditional": "compiled unconditionally",
            "ohos-active": "HarmonyOS/generic guard (compiled)",
            "platform-excluded": "wrapped in a non-HarmonyOS platform guard (not compiled)",
        }[h["guard"]]
        hit_desc = "; ".join(
            "%s:%d[%s] %s" % (hit["file"], hit["line"], hit["guard"],
                               hit["snippet"])
            for hit in h["hits"][:3])
        excluded_total = (gc.get("platform-excluded", 0)
                          + gc.get("platform-file-excluded", 0))
        evidence = (
            "[%s] guard=%s "
            "(%d unconditional / %d OHOS-compilable / %d macro-guard excluded / %d file-level excluded)"
            " | %s" % (
                guard_label, h["guard"],
                gc.get("unconditional", 0), gc.get("ohos-active", 0),
                gc.get("platform-excluded", 0),
                gc.get("platform-file-excluded", 0), hit_desc))
        db.add_node_interface(conn, app_id, h["iface"], evidence=evidence)

    db.set_meta(conn, "scan_%s_at" % app_id, db.now())
    conn.commit()
    return {
        "app_id": app_id, "name": info["name"], "version": version,
        "build_system": info["build_system"],
        "qt_version_hint": info.get("qt_version_hint"),
        "sources": len(info["sources"]),
        "modules_linked": modules_linked,
        # Honest naming: this lists "modules with no node in the knowledge base", not "modules missing from the project".
        # The old name modules_missing read as "missing dependency", leading to misjudging the project as broken.
        "modules_without_kb_node": modules_without_kb_node,
        "deps_linked": deps_linked, "deps_unknown": deps_unknown,
        "deps_vendored": tp["vendored"],
        "deps_first_party": tp.get("first_party", []),
        "deps_optional": deps_optional,
        "interfaces": ifaces,
    }
