"""Project pre-scan: build system, Qt modules, sources, binaries.

Step 1-2 of the migration pipeline (project identification + Qt capability
scan). Output is stored to .qt-ohos/scan.json by the CLI.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

SOURCE_EXTS = {".c", ".cc", ".cpp", ".cxx", ".c++", ".h", ".hh", ".hpp", ".hxx",
               ".m", ".mm", ".qml", ".qrc", ".ui", ".pro", ".pri"}
TEXT_SCAN_EXTS = {".c", ".cc", ".cpp", ".cxx", ".c++", ".h", ".hh", ".hpp",
                  ".hxx", ".m", ".mm", ".qml"}
BINARY_EXTS = {".so", ".a", ".dll", ".dylib", ".lib", ".dll.a"}
EXCLUDE_DIRS = {".git", ".hg", ".svn", ".qt-ohos", "node_modules", "__pycache__",
                ".idea", ".vs", ".vscode", ".gradle", "out", "dist"}
EXCLUDE_DIR_PREFIXES = ("build",)
MAX_FILE_BYTES = 2 * 1024 * 1024

_PRO_QT_RE = re.compile(r"^\s*QT\s*([+\-]?=)\s*(.*)$", re.M)
# Handles find_package(Qt6 ...) / find_package(Qt${QT_VERSION_MAJOR} COMPONENTS ...)
# In the latter the version is a variable: no literal, but the component list is still usable
_CMAKE_FINDPKG_QT_RE = re.compile(r"find_package\s*\(\s*Qt((?:\d|\$\{[^}]+\}))?([^)]*)\)", re.I)

# --- Qt major version detection (ordered by evidence strength; first match wins) ---
_QT_FINDPKG_LITERAL_RE = re.compile(r"find_package\s*\(\s*Qt([56])\b", re.I)
_QT_TARGET_RE = re.compile(r"\bQt([56])::[A-Za-z]")
_QT_NAMES_RE = re.compile(r"find_package\s*\(\s*QT\s+NAMES\s+Qt([56])", re.I)
# Only assignment forms count (set(QT_VERSION_MAJOR 6) / QT_VERSION_MAJOR=6).
# Conditionals like `if (QT_VERSION_MAJOR LESS 6)` only say "still supports Qt5"; not a verdict.
_QT_MAJOR_VAR_RE = re.compile(r"""QT_VERSION_MAJOR\s*(?:=|:=)?\s*["']?([56])\b""")
_QT6_CMD_RE = re.compile(
    r"\b(qt_standard_project_setup|qt_add_executable|qt_add_resources"
    r"|qt_add_qml_module|qt_add_translations|qt6_add_resources)\b")
_QT5_CMD_RE = re.compile(
    r"\b(qt5_use_modules|qt5_wrap_cpp|qt5_add_resources|qt5_add_translation)\b")
_QT_PRO_MAJOR_RE = re.compile(
    r"QT_MAJOR_VERSION\s*\+?=[^\n]*?([56])|greaterThan\s*\(\s*QT_MAJOR_VERSION\s*,\s*([56])")
_CMAKE_FINDPKG_KF_RE = re.compile(r"find_package\s*\(\s*KF(\d)\b([^)]*)\)", re.I)
_KF_LINK_RE = re.compile(r"KF\d::(\w+)")
# sub-targets/aliases -> normalized component name
_KF_ALIAS = {"configcore": "config", "configgui": "config",
             "kiocore": "kio", "kiowidgets": "kio", "kiofilewidgets": "kio",
             "i18nqml": "i18n", "bookmarkswidgets": "bookmarks"}
_COMPONENTS_RE = re.compile(r"\bCOMPONENTS\s+([^)]*)", re.I)
_CMAKE_KW = {"REQUIRED", "CONFIG", "QUIET", "MODULE", "COMPONENTS",
             "OPTIONAL_COMPONENTS"}
# any find_package(<Name> ...) -- captures third-party package names (Qt/KF handled separately)
_FINDPKG_ANY_RE = re.compile(r"find_package\s*\(\s*([A-Za-z0-9_]+)", re.I)
# pkg_check_modules(<PREFIX> [REQUIRED] <module> [<module> ...])
_PKGCHECK_RE = re.compile(r"pkg_check_modules\s*\(\s*\w+\s+([^)]*)\)", re.I)
_PKGCONF_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]*")
_INCLUDE_QT_RE = re.compile(r"#\s*include\s*<\s*(Qt([A-Za-z0-9]+|))\s*/")
# Conan / vcpkg manifests
_CONAN_TXT_REQ_RE = re.compile(r"^\s*([A-Za-z0-9_.+-]+(?:/[A-Za-z0-9_.+-]+)?)\s*$")
_CONAN_PY_REQ_RE = re.compile(r'"([A-Za-z0-9_.+-]+/[A-Za-z0-9_.+-]+)"')
_VCPKG_JSON_DEPS = ("dependencies",)

# known third-party hints: name -> (include regexes, link/find names)
THIRD_PARTY_HINTS = {
    "openssl":  (r"#\s*include\s*<\s*openssl/", ("ssl", "crypto", "OpenSSL")),
    "zlib":     (r"#\s*include\s*<\s*zlib\.h", ("z", "ZLIB")),
    "libpng":   (r"#\s*include\s*<\s*png\.h", ("png", "PNG")),
    "libjpeg":  (r"#\s*include\s*<\s*(jpeglib\.h|turbojpeg\.h)", ("jpeg", "JPEG")),
    "sqlite":   (r"#\s*include\s*<\s*sqlite3\.h", ("sqlite3", "SQLite3")),
    "ffmpeg":   (r"#\s*include\s*<\s*(libavcodec|libavformat|libavutil)/",
                 ("avcodec", "avformat", "avutil", "FFMPEG")),
    "curl":     (r"#\s*include\s*<\s*curl/curl\.h", ("curl", "CURL")),
    "boost":    (r"#\s*include\s*<\s*boost/", ("Boost",)),
    "icu":      (r"#\s*include\s*<\s*unicode/", ("icu", "ICU")),
    "freetype": (r"#\s*include\s*<\s*(ft2build\.h|freetype2/)", ("freetype",)),
    "harfbuzz": (r"#\s*include\s*<\s*hb\.h", ("harfbuzz",)),
    "protobuf": (r"#\s*include\s*<\s*google/protobuf/", ("protobuf", "Protobuf")),
    "spdlog":   (r"#\s*include\s*<\s*spdlog/", ("spdlog",)),
    "libuuid":  (r"#\s*include\s*<\s*uuid/uuid\.h", ("uuid",)),
    "glm":      (r"#\s*include\s*<\s*glm/", ("glm",)),
    "opencv":   (r"#\s*include\s*<\s*opencv2/", ("opencv", "OpenCV")),
}


def scan_project(project_root) -> Dict:
    root = Path(project_root).resolve()
    info: Dict = {
        "name": root.name,
        "root": str(root),
        "build_system": "unknown",
        "pro_files": [],
        "cmake_files": [],
        "qrc_files": [],
        "ui_files": [],
        "qt_version_hint": None,
        "qt_modules": [],
        "frameworks": [],
        "kf_components": [],
        "cmake_packages": {"find_package": [], "pkg_check_modules": []},
        "pkg_manifests": {"conan": [], "vcpkg": []},
        "sources": [],
        "language_stats": {},
        "binary_artifacts": [],
        "third_party_hints": [],
        "warnings": [],
    }

    pro_files, cmake_files = [], []
    sources: List[Dict] = []
    binaries: List[str] = []
    lang_stats: Dict[str, int] = {}

    for path in _walk(root):
        rel = path.relative_to(root).as_posix()
        ext = path.suffix.lower()
        if ext == ".pro" or ext == ".pri":
            pro_files.append(rel)
        elif path.name.lower() in ("cmakelists.txt",) or ext == ".cmake":
            cmake_files.append(rel)
        elif ext == ".qrc":
            info["qrc_files"].append(rel)
        elif ext == ".ui":
            info["ui_files"].append(rel)
        elif ext in BINARY_EXTS:
            binaries.append(rel)
        if ext in SOURCE_EXTS and ext not in (".pro", ".pri"):
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            sources.append({"path": rel, "ext": ext, "size": size})
            lang_stats[ext] = lang_stats.get(ext, 0) + 1

    info["pro_files"] = pro_files
    # Keep .cmake: Qt's find_package often lives in a submodule's *.cmake (e.g. cmake/external/qt/package.cmake)
    info["cmake_files"] = cmake_files
    info["sources"] = sources
    info["binary_artifacts"] = binaries
    info["language_stats"] = lang_stats

    if pro_files and cmake_files:
        info["build_system"] = "cmake+qmake"
    elif pro_files:
        info["build_system"] = "qmake"
    elif cmake_files:
        info["build_system"] = "cmake"

    modules, qt_version, frameworks, kf_components = _detect_qt(root, info)
    info["qt_modules"] = sorted(modules)
    info["qt_version_hint"] = qt_version
    info["frameworks"] = sorted(frameworks)
    info["kf_components"] = sorted(kf_components)

    info["third_party_hints"] = _detect_third_party(root, sources)

    # third-party packages: CMake find_package/pkg_check_modules + Conan/vcpkg manifests
    info["cmake_packages"] = _detect_cmake_packages(root, info["cmake_files"])
    info["pkg_manifests"] = _detect_pkg_manifests(root)

    if len(sources) > 4000:
        info["warnings"].append(
            "large project (%d source files); scan may take a while" % len(sources))
    return info


# ---------------------------------------------------------------- internal

def _walk(root: Path):
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir())
        except (PermissionError, OSError):
            continue
        for entry in entries:
            name = entry.name
            if entry.is_dir():
                if name in EXCLUDE_DIRS or name.startswith(EXCLUDE_DIR_PREFIXES + (".",)):
                    continue
                stack.append(entry)
            elif entry.is_file():
                try:
                    if entry.stat().st_size > MAX_FILE_BYTES:
                        continue
                except OSError:
                    continue
                yield entry


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def detect_qt_major(texts: List[str]) -> tuple:
    """Determine the Qt major version from build file text. Returns (major
    version string or None, evidence description).

    Evidence strength: find_package(Qt6 literal > Qt6:: targets > NAMES Qt6 >
    QT_VERSION_MAJOR assignment > Qt6-only CMake commands. If none decides it,
    return None -- don't guess.
    """
    joined = "\n".join(texts)
    checks = [
        (_QT_FINDPKG_LITERAL_RE, "find_package(Qt{})"),
        (_QT_TARGET_RE, "Qt{}:: link target"),
        (_QT_NAMES_RE, "find_package(QT NAMES Qt{})"),
        (_QT_MAJOR_VAR_RE, "QT_VERSION_MAJOR={}"),
    ]
    for rx, label in checks:
        match = rx.search(joined)
        if match:
            value = match.group(1)
            return value, label.format(value)
    if _QT6_CMD_RE.search(joined):
        return "6", "Qt6-only CMake command"
    if _QT5_CMD_RE.search(joined):
        return "5", "Qt5-only CMake command"
    match = _QT_PRO_MAJOR_RE.search(joined)
    if match:
        major = match.group(1) or match.group(2)
        return major, "qmake QT_MAJOR_VERSION={}".format(major)
    return None, ""


def _optional_component_names(rest: str) -> set:
    """Component names in an `OPTIONAL_COMPONENTS a b c` clause (missing ones
    are not blockers).

    Semantic boundary: everything after `OPTIONAL_COMPONENTS` up to the next
    uppercase keyword is optional; `QUIET` only affects the error wording, not
    whether a component is required.
    """
    match = re.search(r"\bOPTIONAL_COMPONENTS\b(.*?)(?:\b(?:%s)\b|$)"
                      % "|".join(sorted(_CMAKE_KW - {"OPTIONAL_COMPONENTS"})),
                      rest, re.I | re.S)
    if not match:
        return set()
    return {c.lower() for c in re.split(r"\s+", match.group(1)) if c.isalpha()}


def _detect_qt(root: Path, info: Dict):
    modules = set()
    required: Dict[str, bool] = {}
    qt_version = None

    for rel in info["pro_files"]:
        text = _read_text(root / rel)
        for match in _PRO_QT_RE.finditer(text):
            op, names = match.group(1), match.group(2)
            names = names.replace("\\", " ").split()
            for name in names:
                name = name.strip()
                if not name:
                    continue
                if op.startswith("-"):
                    modules.discard(name.lower())
                else:
                    modules.add(name.lower())
                    required[name.lower()] = True

    frameworks = set()
    kf_components = set()
    cmake_texts = []
    for rel in info["cmake_files"]:
        text = _read_text(root / rel)
        cmake_texts.append(text)
        for match in _CMAKE_FINDPKG_QT_RE.finditer(text):
            qt_version = qt_version or match.group(1)
            rest = match.group(2) or ""
            cm = _COMPONENTS_RE.search(rest)
            comps = cm.group(1) if cm else ""
            optional = _optional_component_names(rest)
            for comp in re.split(r"\s+", comps):
                comp = comp.strip()
                if comp and comp.isalpha() and comp.upper() not in _CMAKE_KW:
                    name = comp.lower()
                    modules.add(name)
                    # Components listed under COMPONENTS are hard dependencies
                    # (configure fails without them); OPTIONAL_COMPONENTS are soft
                    # dependencies. REQUIRED / QUIET only change the error wording,
                    # not whether things can proceed when one is missing.
                    required[name] = bool(required.get(name)) or (
                        name not in optional)
        for match in _CMAKE_FINDPKG_KF_RE.finditer(text):
            frameworks.add("KF%s" % match.group(1))
            rest = match.group(2) or ""
            cm = _COMPONENTS_RE.search(rest)
            if cm:
                for comp in re.split(r"\s+", cm.group(1)):
                    comp = comp.strip()
                    if comp and comp.isalpha() and comp.upper() not in _CMAKE_KW:
                        kf_components.add(_KF_ALIAS.get(comp.lower(), comp.lower()))
        for match in _KF_LINK_RE.finditer(text):
            name = match.group(1).lower()
            kf_components.add(_KF_ALIAS.get(name, name))

    # include-based heuristic (also captures modules missed by build files)
    for src in info["sources"]:
        if src["ext"] not in TEXT_SCAN_EXTS:
            continue
        text = _read_text(root / src["path"])
        for match in _INCLUDE_QT_RE.finditer(text):
            whole, mod = match.group(1), match.group(2)
            if mod:
                modules.add(mod.lower())
            elif whole == "Qt":
                modules.add("core")

    modules.discard("")
    # components wrapped in `if(TARGET Qt6::X)` / `if(Qt6X_FOUND)`: the project already tolerates their absence
    for text in cmake_texts:
        for name in list(required):
            if not required[name]:
                continue
            guarded = re.search(
                r"if\s*\(\s*(?:TARGET\s+)?Qt\d?::?%s\b|if\s*\([^)]*%s_FOUND"
                % (re.escape(name), re.escape(name)), text, re.I)
            if guarded:
                required[name] = False
    info["qt_module_required"] = {k: bool(required.get(k)) for k in sorted(modules)}
    if qt_version and not qt_version.isdigit():
        qt_version = None   # find_package(Qt${...}) yields no literal version

    # with no literal version in the build files, infer from evidence (Qt6 projects were once misjudged as Qt5)
    evidence = ""
    for rel in info["pro_files"]:
        cmake_texts.append(_read_text(root / rel))
    if qt_version is None:
        qt_version, evidence = detect_qt_major(cmake_texts)
    else:
        evidence = "find_package(Qt%s)" % qt_version
    info["qt_version_evidence"] = evidence
    if qt_version is None and modules:
        info["warnings"].append(
            "Could not determine the Qt major version from the build files (Qt5 and "
            "Qt6 differ in module matrix and CMake wiring); fetch submodules "
            "recursively, or set it with `config set qt_version 5|6`, then scan again")
    return modules, qt_version, frameworks, kf_components


def _detect_third_party(root: Path, sources: List[Dict]) -> List[Dict]:
    found: Dict[str, List[str]] = {}
    for src in sources:
        if src["ext"] not in TEXT_SCAN_EXTS:
            continue
        text = _read_text(root / src["path"])
        for name, (pattern, _libs) in THIRD_PARTY_HINTS.items():
            if name in found and len(found[name]) >= 3:
                continue
            if re.search(pattern, text):
                found.setdefault(name, []).append(src["path"])
    return [{"name": name, "evidence": files[:5]} for name, files in
            sorted(found.items())]


# CMake build modules/toolchain, not runtime dependencies; skip on find_package matches
_FINDPKG_SKIP = {"ecm", "pkgconfig", "threads", "sharedmimeinfo",
                 "doxygen", "gettext", "i18n", "imported_target",
                 "findpackagehandlestandardargs", "selectlibrary",
                 "pkg_check_modules"}  # noqa: keep explicit


def _detect_cmake_packages(root: Path, cmake_files: List[str]) -> Dict:
    """Extract third-party packages from CMake: find_package(*) and pkg_check_modules.

    Qt/KF are handled by _detect_qt; only other packages are returned here.
    Returns {find_package: [names...], pkg_check_modules: [modules...]}.
    """
    findpkgs = set()
    pkgmods = set()
    skip_prefixes = ("qt", "kf")
    for rel in cmake_files:
        text = _read_text(root / rel)
        for m in _FINDPKG_ANY_RE.finditer(text):
            name = m.group(1).lower()
            if (name.startswith(skip_prefixes) or name in _CMAKE_KW
                    or name in _FINDPKG_SKIP
                    or name.replace(".", "").isdigit()):
                continue
            findpkgs.add(name)
        for m in _PKGCHECK_RE.finditer(text):
            for tok in _PKGCONF_NAME_RE.findall(m.group(1)):
                tok = tok.lower()
                if (tok.upper() in _CMAKE_KW or tok in _FINDPKG_SKIP
                        or tok.startswith(("qt", "kf"))
                        or tok.replace(".", "").isdigit()):
                    continue
                pkgmods.add(tok)
    return {"find_package": sorted(findpkgs),
            "pkg_check_modules": sorted(pkgmods)}


def _detect_pkg_manifests(root: Path) -> Dict:
    """Parse Conan / vcpkg manifests for exact package names + versions +
    transitive dependencies.

    Returns {conan: [{name, version?}], vcpkg: [names]}.
    """
    conan = []
    vcpkg = []
    # conanfile.txt [requires] section
    for rel in ("conanfile.txt",):
        p = root / rel
        if p.is_file():
            in_requires = False
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                s = line.strip()
                if s.startswith("["):
                    in_requires = s.lower().startswith("[requires]")
                    continue
                if in_requires and s and not s.startswith("#"):
                    m = _CONAN_TXT_REQ_RE.match(s)
                    if m:
                        ref = m.group(1)
                        parts = ref.split("/")
                        conan.append({"name": parts[0],
                                      "version": parts[1] if len(parts) > 1 else None})
    # conanfile.py requires list
    for rel in ("conanfile.py",):
        p = root / rel
        if p.is_file():
            for m in _CONAN_PY_REQ_RE.finditer(
                    p.read_text(encoding="utf-8", errors="replace")):
                ref = m.group(1)
                parts = ref.split("/")
                conan.append({"name": parts[0],
                              "version": parts[1] if len(parts) > 1 else None})
    # vcpkg.json dependencies
    for rel in ("vcpkg.json",):
        p = root / rel
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
                for dep in data.get("dependencies", []):
                    if isinstance(dep, str):
                        vcpkg.append(dep)
                    elif isinstance(dep, dict) and "name" in dep:
                        vcpkg.append(dep["name"])
            except json.JSONDecodeError:
                pass
    # conan.lock exact versions
    conan_lock = root / "conan.lock"
    if conan_lock.is_file():
        try:
            lock = json.loads(conan_lock.read_text(encoding="utf-8", errors="replace"))
            seen = {c["name"] for c in conan}
            for ref in lock.get("requires", []):
                if isinstance(ref, str) and "/" in ref:
                    name, ver = ref.split("/", 1)
                    if name not in seen:
                        conan.append({"name": name, "version": ver})
                        seen.add(name)
        except (json.JSONDecodeError, AttributeError):
            pass
    return {"conan": conan, "vcpkg": sorted(set(vcpkg))}
