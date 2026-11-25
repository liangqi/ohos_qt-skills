"""Qt project pre-scan (vendored, independent of the qt_ohos package).

Detects the build system (qmake/CMake), Qt modules and version, source file list, language statistics,
and third-party package declarations (find_package / pkg_check_modules / Conan / vcpkg manifests).
Consumed by project_scanner.

Comprehensive dependency analysis enhancements (consumed by the deps report):
- Full find_package arguments (minimum version / REQUIRED / COMPONENTS / OPTIONAL_COMPONENTS)
- Host build toolchain (cmake minimum version / C++ standard / find_program / COMMAND tool references)
- Runtime dynamic loading (dlopen / QLibrary / QPluginLoader literals)
- qmake LIBS link libraries, .gitmodules bundled dependencies, vendored directories
"""

from __future__ import annotations

import json
import re
import warnings
from pathlib import Path
from typing import Dict, List, Optional

SOURCE_EXTS = {".c", ".cc", ".cpp", ".cxx", ".c++", ".h", ".hh", ".hpp", ".hxx",
               ".m", ".mm", ".qml", ".qrc", ".ui", ".pro", ".pri"}
TEXT_SCAN_EXTS = {".c", ".cc", ".cpp", ".cxx", ".c++", ".h", ".hh", ".hpp",
                  ".hxx", ".m", ".mm", ".qml"}
BINARY_EXTS = {".so", ".a", ".dll", ".dylib", ".lib", ".dll.a"}
# Excluded directories: only those that are definitely not source (VCS/IDE caches/build outputs).
# Note: dist is not excluded -- in C++/CMake projects it is often a source-controlled packaging/install subdirectory
# (e.g. corpus_d's add_subdirectory(dist), which contains real dependency declarations and
# option guards; an e2e postmortem once missed the if(SYSTEMD) guard context by excluding dist).
EXCLUDE_DIRS = {".git", ".hg", ".svn", ".qt-ohos", "node_modules", "__pycache__",
                ".idea", ".vs", ".vscode", ".gradle", "out"}
# dist is not in the exclusion list: in C++ projects dist is usually a source-controlled packaging/install directory (corpus_d's
# dist/unix/CMakeLists.txt is a real build subdirectory, confirmed by e2e review)
# Build output directories (build / build-Debug / build.123 / build2): excluded to avoid scanning generated files;
# note buildscripts / buildtools are source directories (the dependency manifests of corpus_b_core and corpus_b,
# ExtDepsManifest.cmake / SetupQt6.cmake, live there) and must not be excluded by the build prefix
# (prefix over-exclusion bug confirmed by e2e corpus_b review).
_BUILD_DIR_RE = re.compile(r"^build(?:[-._].+|\d+)?$")
MAX_FILE_BYTES = 2 * 1024 * 1024

_PRO_QT_RE = re.compile(r"^\s*QT\s*([+\-]?=)\s*(.*)$", re.M)
# Also handles the find_package(Qt6 ${VER} CONFIG REQUIRED COMPONENTS Core Gui ...) form
_CMAKE_FINDPKG_QT_RE = re.compile(r"find_package\s*\(\s*Qt(\d)\b([^)]*)\)", re.I)
_CMAKE_FINDPKG_KF_RE = re.compile(r"find_package\s*\(\s*KF(\d)\b([^)]*)\)", re.I)
_KF_LINK_RE = re.compile(r"KF\d::(\w+)")
# Sub-target/alias -> normalized component name
_KF_ALIAS = {"configcore": "config", "configgui": "config",
             "kiocore": "kio", "kiowidgets": "kio", "kiofilewidgets": "kio",
             "i18nqml": "i18n", "bookmarkswidgets": "bookmarks"}
_COMPONENTS_RE = re.compile(r"\bCOMPONENTS\s+([^)]*)", re.I)
_CMAKE_KW = {"REQUIRED", "CONFIG", "QUIET", "MODULE", "COMPONENTS",
             "OPTIONAL_COMPONENTS", "EXACT", "NO_MODULE", "NO_POLICY_SCOPE"}


def _orphan_components(rest: str) -> List[str]:
    """Trailing component names without a COMPONENTS keyword (CMake semantics: bare names after
    the version/keywords are components).

    gen_c evidence: find_package(Qt6 ${V} CONFIG REQUIRED\n Core ...)
    and find_package(KF6 ${V} REQUIRED\n Bookmarks ...) -- valid but with no
    COMPONENTS keyword; the old parser missed them all (Qt modules were only hit by the include heuristic).
    Tokens after OPTIONAL_COMPONENTS are optional components and are not collected (conservatively not judged required).
    """
    out: List[str] = []
    seen_kw = False
    seen_comp = False   # component region: all following bare names are components (Config has the same form as CONFIG)
    for tok in rest.split():
        t = tok.strip('"')
        if not t:
            continue
        up = t.upper()
        if not seen_comp:
            if "${" in t:
                seen_kw = True
                continue
            if re.fullmatch(r"\d+(\.\d+)*", t):
                seen_kw = True
                continue
            if up == "OPTIONAL_COMPONENTS":
                break
            if up in _CMAKE_KW:
                seen_kw = True
                continue
        if seen_kw and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", t):
            out.append(t)
            seen_comp = True
    return out
# Any find_package(<Name> ...) -- captures third-party package names (Qt/KF handled separately)
_FINDPKG_ANY_RE = re.compile(r"find_package\s*\(\s*([A-Za-z0-9_]+)", re.I)
# pkg_check_modules(<PREFIX> [REQUIRED] <module> [<module> ...])
_PKGCHECK_RE = re.compile(r"pkg_check_modules\s*\(\s*\w+\s+([^)]*)\)", re.I)
_PKGCONF_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]*")
_INCLUDE_QT_RE = re.compile(r"#\s*include\s*<\s*(Qt([A-Za-z0-9]+|))\s*/")
# Conan / vcpkg manifests (version may be exact or a range string such as [>=1.2 <2], with spaces)
_CONAN_TXT_REQ_RE = re.compile(r"^\s*([A-Za-z0-9_.+-]+)(?:/(.+?))?\s*$")
_CONAN_PY_REQ_RE = re.compile(r'"([A-Za-z0-9_.+-]+)/([^"]*)"')
_VCPKG_JSON_DEPS = ("dependencies",)

# ---- Comprehensive dependency analysis enhancements ----
# cmake_minimum_required(VERSION 3.16[...])
_CMAKE_MIN_RE = re.compile(
    r"cmake_minimum_required\s*\(\s*VERSION\s+([0-9][\d.]*)", re.I)
# set(CMAKE_CXX_STANDARD 17) / target property CXX_STANDARD 17
_CXX_STD_RE = re.compile(r"\bCMAKE_CXX_STANDARD\s+(\d+)")
_CXX_STD_PROP_RE = re.compile(r"\bCXX_STANDARD\s+(\d+)")
# qmake: CONFIG += c++17 / -std=c++17
_QMAKE_CXX_RE = re.compile(
    r"CONFIG\s*\+=\s*[^\n]*?\bc\+\+(\d{2})\b|-std=c\+\+(\d{2})")
# Full find_package argument string ([^)]* spans lines)
_FINDPKG_FULL_RE = re.compile(
    r"find_package\s*\(\s*([A-Za-z0-9_.-]+)\s*([^)]*)\)", re.I)
_FINDPROG_RE = re.compile(r"find_program\s*\(([^)]*)\)", re.I)
_COMMAND_TOKEN_RE = re.compile(r"\bCOMMAND\s+([^\s)]+)")
# Runtime dynamic loading (literals; also handles the QLibrary lib("x") declaration form)
_DLOPEN_RE = re.compile(r'\bdlopen\s*\(\s*"([^"]+)"')
_QLIBRARY_RE = re.compile(r'\bQLibrary(?:\s+\w+)?\s*\(\s*"([^"]+)"')
_QPLUGINLOADER_RE = re.compile(
    r'\bQPluginLoader(?:\s+\w+)?\s*\(\s*"([^"]+)"')
# qmake LIBS += -lfoo
_QMAKE_LIBS_RE = re.compile(r"^\s*LIBS\s*\+=\s*(.+)$", re.M)
_QMAKE_LINK_FLAG_RE = re.compile(r"(?:^|\s)-l([A-Za-z0-9_.+-]+)")
# Test infrastructure
_ENABLE_TESTING_RE = re.compile(r"\benable_testing\s*\(")
_ADD_TEST_RE = re.compile(r"\badd_test\s*\(")
# find_package argument keywords
_FP_KW = {"REQUIRED", "CONFIG", "QUIET", "MODULE", "COMPONENTS",
          "OPTIONAL_COMPONENTS", "EXACT", "NO_MODULE", "NO_POLICY_SCOPE",
          "GLOBAL", "BYPASS_PROVIDER", "REGISTRY_VIEW", "CMAKE_FIND_ROOT_PATH"}

# Known host build tool names (run on the build machine, not deployed to the device).
# COMMAND/find_program tokens that hit this set or match a characteristic suffix
# (*-config/*-scanner etc.) are recorded as build tools.
KNOWN_HOST_TOOLS = {
    "cmake", "ninja", "make", "gmake", "mingw32-make", "ninja-build",
    "pkg-config", "pkgconf", "protoc", "grpc_cpp_plugin", "flex", "bison",
    "gperf", "re2c", "ragel", "yasm", "nasm", "python", "python2", "python3",
    "perl", "ruby", "tclsh", "bash", "sh", "doxygen", "dot", "msgfmt",
    "msgmerge", "xgettext", "git", "svn", "hg", "autoconf", "automake",
    "libtoolize", "autoreconf", "autoheader", "aclocal", "ccache", "sccache",
    "clang", "clang++", "gcc", "g++", "cc", "c++", "ld", "ar", "strip",
    "objcopy", "windres", "lupdate", "lrelease", "lconvert", "qmake",
    "qtpaths", "moc", "uic", "rcc", "wayland-scanner", "gdbus-codegen",
    "glib-genmarshal", "glib-mkenums", "lrelease-pro", "lupdate-pro",
}
_HOST_TOOL_SUFFIXES = ("-config", "-scanner", "-codegen", "-genmarshal",
                       "-mkenums", "-probe", "-desktop-file-utils")

# vendored source directory names (dependencies bundled in the project and compiled with it)
VENDORED_DIR_NAMES = ("3rdparty", "thirdparty", "third_party", "third-party",
                      "external", "extern", "ext", "vendor", "deps", "dep",
                      "subprojects", "dependencies")

# ---- Detection of all dependency declaration forms (deps report second-round enhancement) ----
# target_link_libraries(<tgt> [PRIVATE|...] <item>...): item can be an imported target
# (Foo::Bar), a bare library name (z/ssl/qtermwidget6), -lfoo, "-framework X", or a path
_TARGET_LINK_RE = re.compile(r"target_link_libraries\s*\(([^)]*)\)", re.I | re.S)
_ADD_TARGET_RE = re.compile(
    r"\b(?:qt\d+_)?add_(?:library|executable)\s*\(\s*([A-Za-z0-9_.:-]+)")
# macro/function name definitions (wrappers that call add_library in their body, e.g. gen_a's
# kis_add_library(gen_aui SHARED ...): its first argument is the target name)
_MACRO_DEF_RE = re.compile(
    r"\b(?:macro|function)\s*\(\s*([A-Za-z0-9_.:-]+)", re.I)
_END_BLOCK_RE = re.compile(r"^\s*end(?:macro|function)\b", re.I | re.M)
_TLL_KEYWORDS = {"PRIVATE", "PUBLIC", "INTERFACE", "DEBUG", "OPTIMIZE",
                 "RELEASE", "GENERAL", "OPTIONAL", "LINK_PUBLIC",
                 "LINK_PRIVATE", "LINK_INTERFACE_LIBRARIES"}
_FRAMEWORK_RE = re.compile(r"-framework\s+([A-Za-z]\w*)")
_LFLAG_RE = re.compile(r"(?:^|\s)-l([A-Za-z0-9_.+-]+)")
# find_library(<VAR> [NAMES] name... [PATHS ...])
_FINDLIB_RE = re.compile(r"find_library\s*\(([^)]*)\)", re.I)
_FINDLIB_KW = {"NAMES", "PATHS", "HINTS", "PATH_SUFFIXES", "DOC", "REQUIRED",
               "NAMES_PER_DIR", "NO_CACHE", "VALIDATOR", "CMAKE_FIND_ROOT_PATH",
               "NO_DEFAULT_PATH", "ONLY_CMAKE_FIND_ROOT_PATH"}
# FetchContent_Declare / ExternalProject_Add / CPMAddPackage
_FETCHED_DECLARE_RE = re.compile(
    r"\b(FetchContent_Declare|ExternalProject_Add|CPMAddPackage)\s*"
    r"\(\s*([A-Za-z0-9_.:-]+|GITHUB_REPOSITORY)([^)]*)\)", re.S)
_FETCH_URL_RE = re.compile(r"(?:GIT_REPOSITORY|GITHUB_REPOSITORY|URL)\s+(\S+)")
_FETCH_TAG_RE = re.compile(r"(?:GIT_TAG|GIT_VERSION|VERSION|URL_HASH)\s+(\S+)")
_FETCHED_HOW = {"FetchContent_Declare": "FetchContent",
                "ExternalProject_Add": "ExternalProject",
                "CPMAddPackage": "CPM"}
# qmake: PKGCONFIG += foo
_QMAKE_PKGCONFIG_RE = re.compile(r"^\s*PKGCONFIG\s*\+=\s*(.+)$", re.M)
# meson: dependency('name'[, version: '>=x'[, required: false[, modules: [...]]]])
_MESON_DEP_RE = re.compile(r"dependency\s*\(\s*'([^']+)'([^)]*)\)", re.S)
# Dependencies defined inside a meson project (override_dependency): not external packages
_MESON_OVERRIDE_RE = re.compile(
    r"meson\s*\.\s*override_dependency\s*\(\s*'([^']+)'")
_MESON_VER_RE = re.compile(r"version:\s*'([^']+)'")
_MESON_OPT_RE = re.compile(r"required:\s*false")
_MESON_MODS_RE = re.compile(r"modules:\s*\[([^\]]*)\]")
_MESON_FINDLIB_RE = re.compile(r"\bcc\s*\.\s*find_library\s*\(\s*'([^']+)'")
_MESON_PROJECT_RE = re.compile(r"project\s*\(([^)]*)\)", re.S)
_MESON_MIN_RE = re.compile(r"meson_version:\s*'>=\s*([\d.]+)'")
_MESON_STD_RE = re.compile(r"cpp_std\s*=\s*'?gnu?\+\+(\d+)")
_MESON_SUBPROJECT_RE = re.compile(r"\bsubproject\s*\(\s*'([^']+)'")
# autotools: PKG_CHECK_MODULES([VAR],[foo >= 1.2]) / AC_CHECK_LIB / AC_SEARCH_LIBS
_PKGCHK_MOD_RE = re.compile(r"PKG_CHECK_MODULES\s*\(\s*\[?\w+\]?\s*,\s*\[([^\]]*)\]", re.S)
_AC_CHECK_LIB_RE = re.compile(r"AC_CHECK_LIB\s*\(\s*\[?([A-Za-z0-9_.+-]+)")
_AC_SEARCH_LIBS_RE = re.compile(r"AC_SEARCH_LIBS\s*\(\s*\[?\w+\]?\s*,\s*\[([^\]]*)\]")
# CI / install scripts: apt(-get) install / brew install / pacman -S <pkgs>
_CI_INSTALL_RE = re.compile(
    r"(?:apt(?:-get)?\s+(?:-\S+\s+)*install|brew\s+install|pacman\s+(?:-\S+\s+)*-S)"
    r"[\s\\]+(.+?)(?=$|\n(?:[^\s\\]|\\\s)|\|\||&&)", re.S)

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
        # ---- Comprehensive dependency analysis enhancements ----
        "find_package_details": [],   # full find_package arguments (including version/REQUIRED/components)
        "toolchain": {},              # cmake/meson minimum version / C++ standard / build tool references
        "dynamic_loads": [],          # dlopen/QLibrary/QPluginLoader literals
        "qmake_libs": [],             # LIBS += -lfoo
        "qmake_pkgconfig": [],        # PKGCONFIG += foo
        "git_submodules": [],         # .gitmodules entries (bundled dependencies + pinned commits)
        "vendored_dirs": [],          # bundled source directories such as 3rdparty/
        # Project-owned targets/directories (folds): a dependency name hitting these means it is
        # something this project builds itself, not an external package (tdesktop's auto_updates/crash_reports etc.)
        "first_party": {"targets": [], "dirs": {}, "projects": []},
        # ---- Detection of all dependency declaration forms (second-round enhancement) ----
        "raw_libs": [],               # bare link names (target_link_libraries/find_library/
                                      #   cc.find_library/AC_CHECK_LIB)
        "macos_frameworks": [],       # -framework X
        "fetched_deps": [],           # configure-time fetches via FetchContent/ExternalProject/CPM
        "manifest_deps": [],          # dependencies declared by dependency-manifest functions (require_dep etc.)
        "meson_deps": [],             # meson dependency('name', version: ...)
        "meson": {},                  # {version_min, cxx_standard, subprojects}
        "autotools_deps": [],         # PKG_CHECK_MODULES([V],[pkg >= x])
        "env_installs": [],           # environment dependencies from CI/script apt/brew/pacman install
    }

    pro_files, cmake_files = [], []
    meson_files: List[str] = []
    autotools_files: List[str] = []
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
        elif path.name == "meson.build":
            meson_files.append(rel)
        elif path.name in ("configure.ac", "configure.in"):
            autotools_files.append(rel)
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
    # Project-bundled .cmake modules (cmake/Modules etc.) take part in dependency extraction together
    # with CMakeLists -- find_package calls are often concentrated in include()d .cmake files (e.g. corpus_d's
    # CheckPackages.cmake)
    info["cmake_files"] = cmake_files
    # project()'s own name (for project_scanner's self-reference filtering)
    info["cmake_project_names"] = sorted(
        _cmake_project_names(root, cmake_files))
    info["sources"] = sources
    info["binary_artifacts"] = binaries
    info["language_stats"] = lang_stats

    if pro_files and cmake_files:
        info["build_system"] = "cmake+qmake"
    elif pro_files:
        info["build_system"] = "qmake"
    elif cmake_files:
        info["build_system"] = "cmake"
    elif meson_files:
        info["build_system"] = "meson"
    elif autotools_files:
        info["build_system"] = "autotools"

    modules, qt_version, frameworks, kf_components = _detect_qt(root, info)
    info["qt_modules"] = sorted(modules)
    info["qt_version_hint"] = qt_version
    info["frameworks"] = sorted(frameworks)
    info["kf_components"] = sorted(kf_components)

    info["third_party_hints"] = _detect_third_party(root, sources)

    # Third-party packages: CMake find_package/pkg_check_modules + Conan/vcpkg manifests
    info["cmake_packages"] = _detect_cmake_packages(root, info["cmake_files"])
    info["pkg_manifests"] = _detect_pkg_manifests(root)

    # Comprehensive dependency analysis enhancements (consumed by the deps report)
    info["find_package_details"] = _detect_find_package_details(root, info)
    info["toolchain"] = _detect_toolchain(root, info)
    info["dynamic_loads"] = _detect_dynamic_loads(root, info)
    info["qmake_libs"] = _detect_qmake_libs(root, info)
    info["qmake_pkgconfig"] = _detect_qmake_pkgconfig(root, info)
    info["git_submodules"] = _detect_gitmodules(root)
    info["vendored_dirs"] = _detect_vendored_dirs(root)
    info["first_party"] = _detect_first_party(root, info["cmake_files"],
                                              info["pro_files"])

    # Detection of all dependency declaration forms (second-round enhancement)
    raw_libs, frameworks_m = _detect_cmake_raw_links(root, info["cmake_files"])
    info["raw_libs"] = raw_libs
    info["macos_frameworks"] = frameworks_m
    info["fetched_deps"] = _detect_fetched_deps(root, info["cmake_files"])
    _cmake_vart = _collect_cmake_vars(root, info["cmake_files"])
    info["wrapper_deps"] = _detect_wrapper_deps(root, info["cmake_files"],
                                                _cmake_vart)
    info["manifest_deps"] = _detect_manifest_deps(root, info["cmake_files"])
    if meson_files:
        _absorb_meson(root, info, meson_files)
    if autotools_files:
        _absorb_autotools(root, info, autotools_files)
    # _walk skips directories starting with '.', so CI files (.github/.ci/top-level *.sh) must be collected explicitly
    info["env_installs"] = _detect_env_installs(root, _collect_ci_files(root))

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
                if name in EXCLUDE_DIRS or name.startswith("."):
                    continue
                if _BUILD_DIR_RE.match(name):
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


# Qt component list variables: set(<var> Core Gui ...) / list(APPEND <var> X ...),
# for expanding find_package(Qt6 ... COMPONENTS ${var}) (the form used by the corpus_b_core framework's SetupQt6.cmake)
_SET_LISTVAR_RE = re.compile(r"\bset\s*\(\s*(\w+)\s+(.*?)\)", re.S)
_LIST_APPEND_RE = re.compile(r"\blist\s*\(\s*APPEND\s+(\w+)\s+([^)]*)\)", re.S)
_LISTVAR_TOKEN_KW = {"CACHE", "PATH", "STRING", "BOOL", "FILEPATH", "INTERNAL",
                     "FORCE", "ON", "OFF", "REQUIRED"}


def _listvar_tokens(body: str) -> List[str]:
    """Component-name tokens in a set/list(APPEND) value list (identifiers; keywords/${var}/literals removed)."""
    out = []
    for tok in body.split():
        tok = tok.strip('"\'')
        if (not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", tok)
                or tok.upper() in _LISTVAR_TOKEN_KW):
            continue
        out.append(tok)
    return out


def _collect_list_vars(root: Path, cmake_files: List[str]) -> Dict[str, str]:
    """Accumulate identifier list values of set(<var> ...) / list(APPEND <var> ...).

    Only pure identifier tokens (Core/Gui/...) are kept; version numbers/paths/${var}/the CACHE keyword
    are all removed, so this cannot conflict with the literal variables of _collect_cmake_vars.
    Within one file set() resets and list(APPEND) appends; across files the union is taken (when a
    variable of the same name is defined in different scopes, the union is independent of scan order, which keeps
    declarations in non-main build directories such as sandbox from shadowing the main declaration through directory traversal order).
    """
    union: Dict[str, List[str]] = {}
    for rel in cmake_files:
        text = _read_text(root / rel)
        local: Dict[str, List[str]] = {}
        for m in _SET_LISTVAR_RE.finditer(text):
            toks = _listvar_tokens(m.group(2) or "")
            if toks:
                local[m.group(1)] = list(toks)
        for m in _LIST_APPEND_RE.finditer(text):
            toks = _listvar_tokens(m.group(2) or "")
            if toks:
                local[m.group(1)] = local.get(m.group(1), []) + toks
        for var, toks in local.items():
            merged = union.setdefault(var, [])
            for t in toks:
                if t not in merged:
                    merged.append(t)
    return {var: " ".join(toks) for var, toks in union.items()}


def _detect_qt(root: Path, info: Dict):
    modules = set()
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

    frameworks = set()
    kf_components = set()
    list_vars = _collect_list_vars(root, info["cmake_files"])
    for rel in info["cmake_files"]:
        text = _read_text(root / rel)
        for match in _CMAKE_FINDPKG_QT_RE.finditer(text):
            qt_version = qt_version or match.group(1)
            rest = _subst_vars(match.group(2) or "", list_vars)
            cm = _COMPONENTS_RE.search(rest)
            comps = cm.group(1) if cm else ""
            for comp in re.split(r"\s+", comps) + _orphan_components(rest):
                comp = comp.strip()
                if comp and comp.isalpha() and comp.upper() not in _CMAKE_KW:
                    modules.add(comp.lower())
        for match in _CMAKE_FINDPKG_KF_RE.finditer(text):
            frameworks.add("KF%s" % match.group(1))
            rest = match.group(2) or ""
            cm = _COMPONENTS_RE.search(rest)
            # the segment captured by _COMPONENTS_RE may include following keywords, so filter with _CMAKE_KW;
            # orphan tokens are guaranteed by the region state machine not to be keywords, so don't filter (otherwise
            # the KF component Config, same form as CONFIG, would be dropped -- gen_c evidence)
            kw_filtered = [c for c in re.split(r"\s+", cm.group(1))
                           if c and c.isalpha()
                           and c.upper() not in _CMAKE_KW] if cm else []
            kf_tokens = kw_filtered + _orphan_components(rest)
            for comp in kf_tokens:
                comp = comp.strip()
                if comp and comp.isalpha():
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
    if modules and qt_version is None:
        qt_version = "5"  # HarmonyOS Qt currently ships 5.12 / 5.15
    return modules, qt_version, frameworks, kf_components


def _detect_third_party(root: Path, sources: List[Dict]) -> List[Dict]:
    found: Dict[str, List[str]] = {}
    for src in sources:
        if src["ext"] not in TEXT_SCAN_EXTS:
            continue
        if _is_vendored_path(src["path"]):
            continue  # includes inside vendored third-party code don't count as application dependency evidence
        text = _read_text(root / src["path"])
        for name, (pattern, _libs) in THIRD_PARTY_HINTS.items():
            if name in found and len(found[name]) >= 3:
                continue
            if re.search(pattern, text):
                found.setdefault(name, []).append(src["path"])
    return [{"name": name, "evidence": files[:5]} for name, files in
            sorted(found.items())]


# CMake build modules/toolchains, not runtime dependencies; skipped when find_package hits them.
# Aligned with deps_report.CUILD_TOOL_FINDPKG / CMAKE_BUILTIN_PACKAGES (maintained in two places to avoid
# circular imports: skipped on the graph side + classified as build-tool/system-lib on the report side)
_FINDPKG_SKIP = {"ecm", "pkgconfig", "pkgconf", "threads", "sharedmimeinfo",
                 "doxygen", "gettext", "intltool", "i18n", "imported_target",
                 "packagehandlestandardargs", "selectlibrary",
                 "pkg_check_modules",
                 # CMake built-in modules (compiler features / musl libc built-ins)
                 "openmp", "iconv", "dl",
                 # OpenGL: HarmonyOS uses OpenGL ES (EGL/GLESv3_ndk system capability,
                 # not a CMake built-in but equally not an external package; CMAKE_BUILTIN category on the report side)
                 "opengl",
                 # Host build tools / VCS (find_package(Git) fetches the version, it doesn't link git)
                 "git", "subversion", "mercurial", "ccache", "sccache",
                 "cmake", "ninja", "python", "python3", "flex", "bison",
                 "gperf", "linguisttools"}  # noqa: keep explicit


# Path segments of vendored / dependency-manifest directories: CMake declarations inside them belong to embedded third-party code's own
# or the dependency engine's build logic, not the application's own direct dependencies (confirmed by e2e corpus_b review:
# find_package/pkg_check_modules in thirdparty/fluidsynth, KDDockWidgets/python and corpus_b_deps/recipes
# polluted the depth-1 list).
# Note: "ext" is not included (too short, hits normal directory names); the "*_deps" suffix matches dependency-engine submodules
# (recipe collections such as corpus_b_deps).
_VENDORED_PATH_SEGS = frozenset({
    "thirdparty", "3rdparty", "third_party", "third-party",
    "vendor", "vendors", "vendored", "external", "extern",
    "deps", "dep", "dependencies", "subprojects",
})


def _is_vendored_path(rel: str) -> bool:
    """Whether a relative path lies inside a vendored third-party/dependency-engine directory (skipped during dependency extraction)."""
    for seg in rel.lower().replace("\\", "/").split("/")[:-1]:
        if seg in _VENDORED_PATH_SEGS or seg.endswith("_deps"):
            return True
    return False


# Wrapper CMake file signature: defines an add_library(external_<X> ...) imported target
# (cmake_helpers / desktop-app convention; all of corpus_a's third-party libraries go this way).
# Such files are not vendored source but the declaration layer of the application's external dependencies: the
# find_package / pkg_check_modules inside them are the application's own dependencies (example:
# cmake/external/openal/CMakeLists.txt defines external_openal and
# find_package(OpenAL REQUIRED)). After submodule initialization external_X becomes
# an in-project target; if wrapper files were skipped as well, real dependencies would be hidden by the two rules combined
# (corpus_a postmortem: openal/ada/rnnoise were missed).
_WRAPPER_TARGET_RE = re.compile(
    r"add_library\s*\(\s*external_[A-Za-z0-9_.:-]+", re.I)


def _is_wrapper_cmake(root: Path, rel: str, text: str) -> bool:
    """Wrapper declaration file under a vendored path (not vendored source, not skipped)."""
    return bool(_WRAPPER_TARGET_RE.search(text))

# Windows system libraries (qmake win32 blocks / MSVC linking): not applicable to HarmonyOS (the code is usually
# wrapped in platform guards). project_scanner filters win32 link names with this at scan time (preventing
# same-named Unix libraries from getting wrong edges, e.g. bcrypt -> OpenBSD bcrypt); deps_report annotates them rather than
# treating them as "needs building from source" gaps
WIN32_SYSTEM_LIBS = {
    "user32", "kernel32", "gdi32", "shell32", "ole32", "oleaut32", "uuid",
    "advapi32", "ws2_32", "mswsock", "winmm", "dsound", "ddraw", "dxgi",
    "d3d9", "d3d11", "dwmapi", "shlwapi", "comctl32", "comdlg32",
    "imm32", "wininet", "winhttp", "crypt32", "secur32", "netapi32",
    "psapi", "version", "iphlfapi", "powrprof", "setupapi", "strmiids",
    "avifil32", "mfplat", "mfuuid", "strmbase", "strmbasd", "wtsapi32",
    "windowsapp", "delayimp", "opengl32", "glu32", "wintrust", "shcore",
    "winscard", "bcrypt", "hid", "winusb", "cfgmgr32",
    # corpus_b_core evidence: the 4 gaps from target_link_libraries inside an OS_IS_WIN block
    # (winmm/ole32/shell32/wintrust etc. from the same block are already in the table)
    "mmdevapi", "msi", "taskschd", "userenv",
    # libgen_g evidence: exception handling/DirectShow in a WIN32 block (ole32/strmiids
    # /uuid from the same block are already in the table)
    "dbghelp", "imagehlp",
}

# find_package names that are build tools/interpreters (host side, not application runtime dependencies).
# project_scanner uses this to filter runtime edges (deps_report consumes it too, keeping both sides consistent).
BUILD_TOOL_FINDPKG = {
    "ecm": "extra-cmake-modules (KDE CMake modules, host side)",
    "pkgconfig": "pkg-config (host side)",
    "pkgconf": "pkgconf (host-side pkg-config compatible)",
    "gettext": "gettext toolchain (msgfmt/xgettext, host side)",
    "intltool": "intltool (host side)",
    "doxygen": "Doxygen documentation generator (host side)",
    "sharedmimeinfo": "update-mime-database (host side)",
    "cmake": "CMake",
    "ninja": "Ninja build tool",
    "python3": "Python 3",
    "python": "Python",
    "pythoninterp": "Python interpreter (CMake FindPythonInterp, host side)",
    "pythonlibs": "Python headers/libraries (CMake FindPythonLibs, binding generation, host side)",
    "perl": "Perl interpreter (host side, test/code generation scripts)",
    "swig": "SWIG binding generator (host side, libgen_g bindings evidence)",
    "ruby": "Ruby interpreter (binding generation/scripts, host side)",
    "java": "JDK (CMake FindJava, binding generation, host side)",
    "jni": "JNI headers (CMake FindJNI, binding compilation, host side)",
    "flex": "flex lexer generator",
    "bison": "bison parser generator",
    "gperf": "gperf perfect hash generator",
    "git": "git",
    "ccache": "ccache compiler cache",
    "sccache": "sccache compiler cache",
    "linguisttools": "Qt Linguist tools (lupdate/lrelease, shipped with the Qt SDK)",
    "lxqt2-build-tools": "LXQt CMake build modules (host side, similar to ECM)",
    "lxqt-build-tools": "LXQt CMake build modules (host side, similar to ECM)",
}


# pkg_check_modules-specific keywords (IMPORTED_TARGET/GLOBAL etc.), not module names
_PKGCHECK_KW = {"IMPORTED_TARGET", "GLOBAL", "STATIC", "SHARED", "MODULE",
                "OPTIONAL", "SKIP_CMAKE_DIRS", "WITHOUT_CMAKE_PACKAGE"}


# ------------------------------------------------------ CMake option guard analysis
#
# Background (e2e corpus_d postmortem): find_package(Systemd) sits
# inside `if (SYSTEMD)`, and SYSTEMD is declared by feature_option_dependent(... OFF ...)
# with a default of OFF -- that dependency is not part of the default build and should not be recorded as a runtime dependency.
# Approach: collect the defaults of option/feature_option[_dependent]/cmake_dependent_option;
# track the if stack line by line; find_package/pkg_check_modules inside a bare guard (not modified by NOT) of an
# OFF-by-default option are marked optional. Detections inside a Find<Name>.cmake module
# file inherit the optional guard of find_package(Name) (the module only runs when
# called, so the guard context is at the call site).

# option(NAME "doc" [ON|OFF]) -- CMake defaults to OFF when no default is given
_OPTION_RE = re.compile(
    r'^\s*option\s*\(\s*(\w+)\s+"(?:[^"\\]|\\.)*"\s*([A-Za-z0-9_${}.]+)?',
    re.M)
# feature_option(NAME "doc" <default>)
_FEATURE_OPTION_RE = re.compile(
    r'^\s*feature_option\s*\(\s*(\w+)\s+"(?:[^"\\]|\\.)*"\s*'
    r'([A-Za-z0-9_${}.]+)',
    re.M)
# feature_option_dependent(NAME "doc" <default> "COND" <fallback>) /
# cmake_dependent_option (same form): the first non-string argument is the default
_DEPENDENT_OPTION_RE = re.compile(
    r'^\s*(?:feature_option_dependent|cmake_dependent_option)\s*\('
    r'\s*(\w+)\s+"(?:[^"\\]|\\.)*"\s*([A-Za-z0-9_${}.]+)',
    re.M)

_CMAKE_IF_RE = re.compile(r'^\s*if\s*\((.*)\)\s*$', re.I)
_CMAKE_ELSEIF_RE = re.compile(r'^\s*elseif\s*\((.*)\)\s*$', re.I)
_CMAKE_ELSE_RE = re.compile(r'^\s*else\s*\(\s*\)\s*$', re.I)
_CMAKE_ENDIF_RE = re.compile(r'^\s*endif\s*\(\s*\)\s*$', re.I)
_CMAKE_FUNC_RE = re.compile(r'^\s*(?:function|macro)\s*\(', re.I)
_CMAKE_ENDFUNC_RE = re.compile(r'^\s*end(?:function|macro)\b', re.I)
# Tokens modified by NOT in a condition: `NOT X` means entered when X is false, not a positive guard
_NOT_TOKEN_RE = re.compile(r'(?i)\bNOT\s+(\w+)')

# Platform-condition if frames: other-platform tokens (not applicable to HarmonyOS) and OHOS-compatible tokens.
# Declarations inside such a frame are only built on those platforms; the default HarmonyOS build excludes them -> required=False.
# When both kinds of token are present, don't judge it excluded (UNIX AND NOT APPLE is an OHOS-active block);
# tokens modified by NOT don't count (NOT WIN32 is an OHOS-active block).
_OTHER_PLATFORM_TOKENS = frozenset({
    "APPLE", "DARWIN", "COCOA", "IOS", "TVOS", "WATCHOS",
    "WIN32", "WINDOWS", "MSVC", "MINGW", "MSYS", "CYGWIN",
    "FREEBSD", "OPENBSD", "NETBSD", "HAIKU", "SOLARIS", "ANDROID",
})
_OHOS_ACTIVE_TOKENS = frozenset({"UNIX", "LINUX", "POSIX", "OHOS",
                                  "HARMONY"})


def _frame_platform_excluded(cond: str) -> Optional[str]:
    """Whether an if condition is specific to other platforms (not applicable to HarmonyOS). Returns the condition string or None.

    Evidence: gen_c if(HAIKU) tll network, if(SYSTEM_NAME MATCHES
    "FreeBSD") tll util, gen_b mobile if(ANDROID) tll -lsoftokn3,
    corpus_c FindQREncode if(WIN32 AND NOT MINGW) find_library(qrencoded).
    """
    stripped = _NOT_TOKEN_RE.sub(" ", cond)
    toks = {t.upper() for t in re.findall(r"\w+", stripped)}
    if not (toks & _OTHER_PLATFORM_TOKENS):
        return None
    if toks & _OHOS_ACTIVE_TOKENS:
        return None
    return cond.strip()


def _cmake_platform_line_map(text: str) -> Dict[int, Optional[str]]:
    """Track the CMake if stack line by line, returning {line number: condition string of the innermost excluding frame, or None}.

    Same structure as _cmake_optional_line_map: else/elseif are conservatively not judged excluded;
    function/macro bodies are not judged (call-site context is unreliable).
    """
    result: Dict[int, Optional[str]] = {}
    stack: List[Optional[str]] = []
    func_depth = 0
    for lineno, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        m = _CMAKE_IF_RE.match(s)
        if m:
            stack.append(_frame_platform_excluded(m.group(1)))
        elif _CMAKE_ELSEIF_RE.match(s) and stack:
            # an elseif branch's condition can be evaluated directly (if(Darwin) ... elseif(Windows):
            # both branches are specific to other platforms; corpus_d src/base evidence);
            # only a bare else (the complement, including OHOS) is conservatively not judged
            em = _CMAKE_ELSEIF_RE.match(s)
            stack[-1] = _frame_platform_excluded(em.group(1))
        elif _CMAKE_ELSE_RE.match(s) and stack:
            stack[-1] = None
        elif _CMAKE_ENDIF_RE.match(s) and stack:
            stack.pop()
        elif _CMAKE_FUNC_RE.match(s):
            func_depth += 1
        elif _CMAKE_ENDFUNC_RE.match(s) and func_depth:
            func_depth -= 1
        cur = None
        if func_depth == 0:
            for fr in stack:
                if fr:
                    cur = fr
                    break
        result[lineno] = cur
    return result


def _collect_option_defaults(cmake_texts: List[str]) -> Dict[str, bool]:
    """Collect default values of CMake option declarations -> {option name: whether the default is true}.

    Merged across files (option definitions and if guards are often in different files); the first definition wins.
    Defaults containing non-literals such as ${VAR} are not recorded (cannot be determined).
    """
    out: Dict[str, bool] = {}
    for rx in (_OPTION_RE, _FEATURE_OPTION_RE, _DEPENDENT_OPTION_RE):
        for text in cmake_texts:
            for m in rx.finditer(text):
                name, val = m.group(1), (m.group(2) or "OFF").upper()
                if name in out:
                    continue
                if val in ("ON", "TRUE", "1"):
                    out[name] = True
                elif val in ("OFF", "FALSE", "0"):
                    out[name] = False
    return out


# Platform conditions that are always true for the HarmonyOS target (Q_OS_OHOS implies Q_OS_LINUX):
# if branches containing these disjuncts are necessarily active in OHOS builds and must not be marked optional
_PLATFORM_TRUE_DISJUNCTS = frozenset({
    "LINUX", "UNIX", "NOT WIN32", "NOT APPLE", "NOT MSVC", "NOT IOS",
    "NOT MACOS", "NOT WINDOWS",
})
_PLATFORM_TRUE_RE = re.compile(
    r"CMAKE_SYSTEM_NAME\s+(?:STREQUAL|MATCHES)\s+\"?Linux", re.I)


def _disjunct_always_true(d: str) -> bool:
    """Whether a single OR disjunct is always true for the HarmonyOS target."""
    d = d.strip().upper()
    if d in _PLATFORM_TRUE_DISJUNCTS:
        return True
    if _PLATFORM_TRUE_RE.search(d):
        return True
    # retry after stripping parentheses (the (NOT WIN32) form)
    inner = d.strip("() ").strip()
    return inner in _PLATFORM_TRUE_DISJUNCTS


def _split_top_level_or(cond: str) -> List[str]:
    """Split a condition on top-level OR outside parentheses (complex nesting mixed with AND is not handled;
    if it can't be split, the whole string is returned, falling back to the old behavior)."""
    parts, depth, cur, i = [], 0, "", 0
    up = cond.upper()
    while i < len(cond):
        c = cond[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif depth == 0 and up[i:i + 3] == " OR":
            nxt = cond[i:i + 4]
            if nxt[-1] in (" ", "\t") or i + 3 == len(cond):
                parts.append(cur)
                cur = ""
                i += 3
                while i < len(cond) and cond[i] in " \t":
                    i += 1
                continue
        cur += c
        i += 1
    parts.append(cur)
    return parts if len(parts) > 1 else [cond]


def _frame_positively_guarded(cond: str, off_options: Dict[str, bool]) -> bool:
    """Whether an if condition contains a bare positive reference (not modified by NOT) to an OFF-by-default option.

    `if (SYSTEMD)` -> True (SYSTEMD defaults to OFF);
    `if (NOT SYSTEMD)` / `if (DBUS)` (defaults to ON) -> False.
    OR disjunction semantics (corpus_a postmortem): `if (X OR LINUX)` is necessarily active on HarmonyOS
    because LINUX is always true, so it must not be marked optional -- only mark optional when all disjuncts are
    positive references to OFF options (or an OFF option is present and there is no always-true disjunct).
    """
    if not off_options:
        return False
    disjuncts = _split_top_level_or(cond)
    guarded = False
    for d in disjuncts:
        if _disjunct_always_true(d):
            return False
        stripped = _NOT_TOKEN_RE.sub(" ", d)
        for tok in re.findall(r"\w+", stripped):
            if off_options.get(tok) is False:
                guarded = True
    return guarded


def _cmake_optional_line_map(text: str,
                             off_options: Dict[str, bool]) -> Dict[int, bool]:
    """Track the CMake if stack line by line, returning {line number: whether inside an OFF-by-default option guard}.

    - any active if frame positively guarding an OFF-by-default option -> code in the frame is not in the default build;
    - else/elseif branches are conservatively treated as unguarded (they may contain fallback logic);
    - declarations inside function/macro bodies take effect at the call site, guard context unreliable -> not marked.
    """
    result: Dict[int, bool] = {}
    stack: List[bool] = []   # per frame: whether it is a positive guard on an OFF option
    func_depth = 0
    for lineno, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if _CMAKE_IF_RE.match(s):
            stack.append(_frame_positively_guarded(
                _CMAKE_IF_RE.match(s).group(1), off_options))
        elif _CMAKE_ELSEIF_RE.match(s) and stack:
            stack[-1] = False   # conservative: else/elseif branches are not judged as guards
        elif _CMAKE_ELSE_RE.match(s) and stack:
            stack[-1] = False
        elif _CMAKE_ENDIF_RE.match(s) and stack:
            stack.pop()
        elif _CMAKE_FUNC_RE.match(s):
            func_depth += 1
        elif _CMAKE_ENDFUNC_RE.match(s) and func_depth:
            func_depth -= 1
        result[lineno] = (func_depth == 0 and any(stack))
    return result


def _cmake_guard_context(root: Path,
                         cmake_files: List[str]) -> Dict[str, Dict[int, bool]]:
    """Build a {file: {line number: optional guard}} context (option defaults merged across files)."""
    texts = {rel: _read_text(root / rel) for rel in cmake_files}
    option_defaults = _collect_option_defaults(list(texts.values()))
    off_options = {k: v for k, v in option_defaults.items() if v is False}
    return {rel: _cmake_optional_line_map(text, off_options)
            for rel, text in texts.items()}


def _find_module_optional_files(cmake_files: List[str],
                                optional_names: set) -> set:
    """Find<Name>.cmake module files (when find_package of Name is under an optional guard,
    the whole module inherits optional -- pkg_check_modules inside the module only runs when called)."""
    if not optional_names:
        return set()
    wanted = {"find%s.cmake" % n for n in optional_names}
    return {rel for rel in cmake_files
            if Path(rel).name.lower() in wanted}


def _cmake_project_names(root: Path, cmake_files: List[str]) -> set:
    """project() name of the root CMakeLists.txt (lowercase):
    find_package(<own project name>) is a self-reference (e.g. the gen_j plugin sample's
    find_package(gen_j REQUIRED)), not an external dependency (it was once mis-resolved to
    an unrelated package of the same name, cmdpkgs:gen_j).

    Only the root CMakeLists.txt is collected: in vendored subdirectories,
    project(fakevim) (the gen_f src/libraries layout) declares the subproject's
    own name, and its existence doesn't make the host's find_package(fakevim) a self-reference.
    """
    names = set()
    rx = re.compile(r"\bproject\s*\(\s*([A-Za-z][A-Za-z0-9_-]*)")
    for rel in cmake_files:
        if Path(rel).parts[:-1] or Path(rel).name != "CMakeLists.txt":
            continue          # root CMakeLists.txt only
        for m in rx.finditer(_read_text(root / rel)):
            names.add(m.group(1).lower())
    return names


def _detect_cmake_packages(root: Path, cmake_files: List[str]) -> Dict:
    """Extract third-party packages from CMake: find_package(*) and pkg_check_modules.

    Qt/KF are handled separately by _detect_qt; only other packages are returned here.
    Returns {find_package: [required names...], find_package_optional: [optional names...],
          pkg_check_modules: [required names...], pkg_check_modules_optional: [...],
          pkg_modules: [{name, version_req, optional?}...]} (with version constraints).

    optional = the declaration site is inside an if guard of an OFF-by-default CMake option (not in the default build).
    When a package has both optional and required declaration sites, required wins (conservative).
    """
    findpkgs, pkgmods = set(), set()
    findpkgs_opt, pkgmods_opt = set(), set()
    findpkgs_plat, pkgmods_plat = set(), set()
    pkg_details: Dict[str, Dict] = {}
    vart = _collect_cmake_vars(root, cmake_files)
    guards = _cmake_guard_context(root, cmake_files)
    skip_prefixes = ("qt", "kf")
    # project()'s own name: find_package(<project name>) is a self-reference, skip it
    self_names = _cmake_project_names(root, cmake_files)

    def _line_of(text: str, pos: int) -> int:
        return text.count("\n", 0, pos) + 1

    # pass 1: find_package (collected first, for Find<Name>.cmake module inheritance)
    for rel in cmake_files:
        text = _strip_cmake_comments(_read_text(root / rel))
        text = _strip_cmake_comments(_read_text(root / rel))
        if _is_vendored_path(rel):
            if not _is_wrapper_cmake(root, rel, text):
                continue
            # wrapper file: external_X is linked unconditionally by the application; internal guards
            # (DESKTOP_APP_USE_PACKAGED etc.) only switch how it is obtained (find_package
            # vs. prebuilt path), not whether it is used -> no optional guard applied
            gmap = {}
        else:
            gmap = guards.get(rel, {})
        pmap = _cmake_platform_line_map(text)
        for m in _FINDPKG_ANY_RE.finditer(text):
            name = m.group(1).lower()
            if (name.startswith(skip_prefixes) or name in _CMAKE_KW
                    or name in _FINDPKG_SKIP
                    or name in self_names
                    or name.replace(".", "").isdigit()):
                continue
            if gmap.get(_line_of(text, m.start())):
                findpkgs_opt.add(name)
            elif pmap.get(_line_of(text, m.start())):
                findpkgs_plat.add(name)
            else:
                findpkgs.add(name)

    # Find<Name>.cmake module files: all detections inside inherit the optional guard
    opt_files = _find_module_optional_files(
        cmake_files, findpkgs_opt - findpkgs)

    # pass 2: pkg_check_modules
    for rel in cmake_files:
        text = _strip_cmake_comments(_read_text(root / rel))
        text = _strip_cmake_comments(_read_text(root / rel))
        if _is_vendored_path(rel):
            if not _is_wrapper_cmake(root, rel, text):
                continue
            gmap = {}   # wrapper: same as pass 1, no optional guard applied
        else:
            gmap = guards.get(rel, {})
        pmap = _cmake_platform_line_map(text)
        file_opt = (rel in opt_files) and not _is_vendored_path(rel)
        for m in _PKGCHECK_RE.finditer(text):
            line_opt = file_opt or gmap.get(_line_of(text, m.start()))
            line_plat = pmap.get(_line_of(text, m.start()))
            # a pkg-config spec may carry a version constraint: "glib-2.0 >= 2.50" / glib-2.0>=2.50
            # substitute set() variables; unresolvable ${macro args} are removed entirely so they don't leak into package names
            specs = _subst_vars(m.group(1), vart).replace("\\\n", " ")
            specs = re.sub(r"\$\{\w+\}", " ", specs)
            _absorb_pkg_spec(specs, pkg_details, optional=line_opt,
                             platform=line_plat)
            for tok in _PKGCONF_NAME_RE.findall(specs):
                tok = tok.lower()
                if (tok.upper() in _CMAKE_KW or tok in _FINDPKG_SKIP
                        or tok.upper() in _PKGCHECK_KW
                        or tok.startswith(("qt", "kf"))
                        or tok.replace(".", "").isdigit()):
                    continue
                if line_opt:
                    pkgmods_opt.add(tok)
                    pkg_details.setdefault(
                        tok, {"name": tok, "version_req": None,
                              "optional": True})
                elif line_plat:
                    pkgmods_plat.add(tok)
                    pkg_details.setdefault(
                        tok, {"name": tok, "version_req": None,
                              "platform": line_plat})
                else:
                    pkgmods.add(tok)
                    pkg_details.setdefault(tok, {"name": tok,
                                                 "version_req": None})

    # required wins: when optional/platform and required declaration sites coexist for a package, treat it as required
    findpkgs_opt -= findpkgs
    pkgmods_opt -= pkgmods
    findpkgs_plat -= findpkgs
    pkgmods_plat -= pkgmods
    for name in pkgmods:
        d = pkg_details.get(name)
        if d:
            d.pop("optional", None)
            d.pop("platform", None)
    # a spec with constraints overrides the bare name (keeps the version requirement; specs inside platform blocks
    # go to pkgmods_plat, not the required list)
    pkgmods.update(k for k, d in pkg_details.items()
                   if not d.get("optional") and not d.get("platform"))
    pkgmods_opt.update(k for k, d in pkg_details.items()
                       if d.get("optional"))
    pkgmods_plat.update(k for k, d in pkg_details.items()
                        if d.get("platform") and not d.get("optional")
                        and k not in pkgmods)
    pkgmods_plat -= pkgmods
    return {"find_package": sorted(findpkgs),
            "find_package_optional": sorted(findpkgs_opt),
            "find_package_platform": sorted(findpkgs_plat),
            "pkg_check_modules": sorted(pkgmods),
            "pkg_check_modules_optional": sorted(pkgmods_opt),
            "pkg_check_modules_platform": sorted(pkgmods_plat),
            "pkg_modules": sorted(pkg_details.values(),
                                  key=lambda d: d["name"])}


_PKG_SPEC_VER_RE = re.compile(
    r"([A-Za-z0-9][A-Za-z0-9._+-]*)\s*(>=|<=|==|=|<|>|!=)\s*([0-9][\w.]*)")


def _absorb_pkg_spec(spec: str, out: Dict[str, Dict],
                     optional: bool = False,
                     platform: Optional[str] = None) -> None:
    """Absorb one pkg-config spec (possibly with a version constraint) into out."""
    m = _PKG_SPEC_VER_RE.search(spec)
    if not m:
        return
    name = m.group(1).lower()
    out[name] = {"name": name,
                 "version_req": "%s %s" % (m.group(2), m.group(3))}
    if optional:
        out[name]["optional"] = True
    elif platform:
        out[name]["platform"] = platform


def _detect_pkg_manifests(root: Path) -> Dict:
    """Parse Conan / vcpkg manifests to get exact package names + versions + transitive dependencies.

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
                        conan.append({"name": m.group(1),
                                      "version": m.group(2)})
    # conanfile.py requires list
    for rel in ("conanfile.py",):
        p = root / rel
        if p.is_file():
            for m in _CONAN_PY_REQ_RE.finditer(
                    p.read_text(encoding="utf-8", errors="replace")):
                conan.append({"name": m.group(1),
                              "version": m.group(2)})
    # vcpkg.json dependencies
    for rel in ("vcpkg.json",):
        p = root / rel
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
                for dep in data.get("dependencies", []):
                    if isinstance(dep, str):
                        vcpkg.append({"name": dep})
                    elif isinstance(dep, dict) and "name" in dep:
                        ver = (dep.get("version>=") or dep.get("version==")
                               or dep.get("version"))
                        vcpkg.append({"name": dep["name"], "version": ver})
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
    return {"conan": conan,
            "vcpkg": sorted(vcpkg, key=lambda d: d["name"])}


# ------------------------------------------------ Comprehensive dependency analysis enhancements


def _looks_like_host_tool(tok: str) -> bool:
    """Whether a token is a known host build tool name (or matches a characteristic suffix)."""
    t = tok.strip("\"'")
    if not t or t != t.strip() or "$" in t:
        return False
    if t in KNOWN_HOST_TOOLS:
        return True
    return t.endswith(_HOST_TOOL_SUFFIXES) or t.startswith("glib-")


def _parse_findpkg_args(name: str, rest: str, rel: str,
                        line: int) -> Dict:
    """Parse find_package(<Name> [ver] [REQUIRED] [COMPONENTS ...]
    [OPTIONAL_COMPONENTS ...]) arguments."""
    tokens = rest.replace("\\\n", " ").split()
    version = None
    required = False
    exact = False
    components: List[str] = []
    optional_components: List[str] = []
    mode = None
    seen_kw = False    # past the version/keyword position (bare names after it are components)
    seen_comp = False  # component collection has started: all following bare names are components, no longer
                        # interpreted as keywords (the KF component name Config has the same form as CONFIG, gen_c evidence)
    for tok in tokens:
        tok2 = tok.strip('"')
        up = tok2.upper()
        if up == "COMPONENTS":
            mode = "c"
            seen_kw = True
            continue
        if up == "OPTIONAL_COMPONENTS":
            mode = "o"
            seen_kw = True
            continue
        if not seen_comp and up in _FP_KW:
            if up == "REQUIRED":
                required = True
            elif up == "EXACT":
                exact = True
            mode = None
            seen_kw = True
            continue
        if version is None and re.fullmatch(r"\d+(\.\d+)*", tok2):
            # the version may be quoted: find_package(Poppler "24.08.0" ...) (gen_b)
            version = tok2
            seen_kw = True
            continue
        if "${" in tok or "$ENV" in tok:
            mode = None
            seen_kw = True
            continue
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", tok2):
            continue
        if mode == "o":
            optional_components.append(tok2)
        elif seen_kw or mode == "c":
            # CMake semantics: bare names after the version/keywords are components, no COMPONENTS
            # keyword needed (gen_c: find_package(Qt6 ${V} CONFIG REQUIRED\n Core ...))
            components.append(tok2)
            mode = "c"
            seen_comp = True
    return {"name": name, "name_lower": name.lower(), "version": version,
            "required": required, "exact": exact,
            "components": components, "optional_components": optional_components,
            "file": rel, "line": line}


# Custom dependency wrapper functions: indirect declarations of the form function/macro(...pkg_check_modules(${pkg} ${arg_PACKAGE})...),
# extracted from call sites search_dependency(NAME PACKAGE <pkg name> ...)
_FUNC_DEF_RE = re.compile(r"^\s*(?:function|macro)\s*\(\s*(\w+)", re.M)
_WRAP_PACKAGE_RE = re.compile(r"\bPACKAGE\s+\"?([A-Za-z0-9_.+-]+)\"?")
_WRAP_LIBRARY_RE = re.compile(r"\bLIBRARY\s+\"?([A-Za-z0-9_.+-]+)\"?")
_WRAP_MINVER_RE = re.compile(r"MINIMUM_VERSION\s+(?:\$\{(\w+)\}|\"?([\w.]+)\"?)")
_WRAP_FRAMEWORK_RE = re.compile(r"\bFRAMEWORK\s+\"?([A-Za-z0-9_]+)\"?")


def _detect_wrapper_deps(root: Path, cmake_files: List[str],
                         vart: Dict[str, str]) -> List[Dict]:
    """Dependency declarations in project-defined wrapper functions (e.g. gen_n's search_dependency).

    Recognition: the function name is defined by a project function()/macro(), and the call arguments carry
    PACKAGE <pkg-config name> / LIBRARY <library name> / MINIMUM_VERSION <version> /
    FRAMEWORK <macOS framework> keywords. Returns the wrapped dependency list.
    """
    texts = {rel: _read_text(root / rel) for rel in cmake_files}
    funcs: set = set()
    for text in texts.values():
        for m in _FUNC_DEF_RE.finditer(text):
            funcs.add(m.group(1))
    if not funcs:
        return []
    out: List[Dict] = []
    seen: set = set()
    for rel, text in texts.items():
        if _is_vendored_path(rel):
            continue  # calls inside dependency-engine/embedded third-party directories are not application dependencies
        for fn in sorted(funcs):
            for cm in re.finditer(r"\b%s\s*\(([^)]*)\)" % re.escape(fn), text):
                args = _strip_cmake_comments(cm.group(1))
                pm = _WRAP_PACKAGE_RE.search(args)
                if not pm:
                    continue
                name = pm.group(1)
                key = name.lower()
                if key in seen:
                    continue
                seen.add(key)
                vm = _WRAP_MINVER_RE.search(args)
                version = None
                if vm:
                    version = (vart.get(vm.group(1)) if vm.group(1)
                               else vm.group(2))
                lm = _WRAP_LIBRARY_RE.search(args)
                fm = _WRAP_FRAMEWORK_RE.search(args)
                out.append({
                    "name": name, "wrapper": fn,
                    "library": lm.group(1) if lm else None,
                    "framework": fm.group(1) if fm else None,
                    "version": version, "evidence": [rel]})
    return out


# Dependency-manifest function names (the corpus_b_deps engine etc.): require_dep(name [STATIC|SYSTEM|REBUILD]) /
# require_source_dep(name) (bundled source) / require_tool(name) (host build tool).
# The function must have a function()/macro() definition in the project's scanned CMake (to avoid matching
# ordinary calls of the same name); the first argument is the dependency name.
_MANIFEST_FN_RE = re.compile(
    r"(?i)^(?:require|add|use|need)[_-]?"
    r"(?:source[_-]?)?(?:dep|deps|dependency|dependencies|tool|package)s?$")
_MANIFEST_ARG_KW = {"STATIC", "SYSTEM", "REBUILD", "REQUIRED", "OPTIONAL",
                    "ON", "OFF"}


def _detect_manifest_deps(root: Path, cmake_files: List[str]) -> List[Dict]:
    """Calls of custom dependency-manifest functions (e.g. the corpus_b_deps engine's require_dep).

    Returns [{name, mode(link|source|tool), conditional, condition,
           evidence: [file:line]}]. The function definition may live in a dependency-engine submodule
    (vendored path), but only calls in application-side files are scanned.
    """
    texts = {rel: _read_text(root / rel) for rel in cmake_files}
    funcs = {m.group(1) for text in texts.values()
             for m in _FUNC_DEF_RE.finditer(text)
             if _MANIFEST_FN_RE.match(m.group(1))}
    if not funcs:
        return []
    out: List[Dict] = []
    seen: set = set()
    for rel, raw in texts.items():
        if _is_vendored_path(rel):
            continue
        text = _strip_cmake_comments(raw)
        # lightweight if/endif tracking: records whether a call is inside a conditional block (not evaluated, annotation only).
        # events: [(pos, cond)], cond is the if condition text, None for endif
        events = [(m.start(), m.group(1)) for m in re.finditer(
            r"(?im)^\s*(?:if\s*\((.*?)\)|endif\b)", text)]
        for fn in sorted(funcs, key=len, reverse=True):
            for cm in re.finditer(
                    r"\b%s\s*\(\s*([A-Za-z0-9_][A-Za-z0-9_.+-]*)"
                    % re.escape(fn), text):
                name = cm.group(1)
                if name.upper() in _MANIFEST_ARG_KW or name.startswith("$"):
                    continue
                fnl = fn.lower()
                mode = ("tool" if "tool" in fnl
                        else "source" if "source" in fnl else "link")
                key = (mode, name.lower())
                if key in seen:
                    continue
                seen.add(key)
                # rebuild the if stack before the call site; the top of the stack is the enclosing condition
                stack: List[str] = []
                for pos, cond in events:
                    if pos >= cm.start():
                        break
                    if cond is None:
                        if stack:
                            stack.pop()
                    else:
                        stack.append(cond.strip())
                cond = stack[-1] if stack else None
                line = text.count("\n", 0, cm.start()) + 1
                out.append({"name": name, "mode": mode,
                            "conditional": cond is not None,
                            "condition": cond,
                            "evidence": ["%s:%d" % (rel, line)]})
    return out


def _collect_cmake_vars(root: Path, cmake_files: List[str]) -> Dict[str, str]:
    """Collect simple variables defined by set(<var> <literal>) (version numbers etc.), used for
    approximate substitution when resolving the version of find_package(${var}) (CMake scope is ignored)."""
    vart: Dict[str, str] = {}
    for rel in cmake_files:
        for m in re.finditer(r"^\s*set\s*\(\s*(\w+)\s+\"?([\w.]+)\"?\s*\)",
                             _read_text(root / rel), re.M):
            vart.setdefault(m.group(1), m.group(2))
    return vart


def _subst_vars(text: str, vart: Dict[str, str]) -> str:
    """Replace ${var} with the literal value from the set() table; unknown variables are left as is."""
    return re.sub(r"\$\{(\w+)\}",
                  lambda m: vart.get(m.group(1), m.group(0)), text)


def _detect_find_package_details(root: Path, info: Dict) -> List[Dict]:
    """Extract the full arguments of all find_package calls (across lines), including Qt/KF calls.

    Attaches an optional flag (declarations inside an OFF-by-default option guard, not in the default build).
    """
    vart = _collect_cmake_vars(root, info["cmake_files"])
    guards = _cmake_guard_context(root, info["cmake_files"])
    self_names = _cmake_project_names(root, info["cmake_files"])
    out: List[Dict] = []
    for rel in info["cmake_files"]:
        if _is_vendored_path(rel):
            continue
        text = _strip_cmake_comments(_read_text(root / rel))
        gmap = guards.get(rel, {})
        pmap = _cmake_platform_line_map(text)
        for m in _FINDPKG_FULL_RE.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            detail = _parse_findpkg_args(m.group(1),
                                         _subst_vars(m.group(2) or "", vart),
                                         rel, line)
            if detail["name"].lower() in self_names:
                continue    # project() self-reference (e.g. the gen_j plugin sample)
            if gmap.get(line):
                detail["optional"] = True
            elif pmap.get(line):
                detail["platform"] = pmap.get(line)
            out.append(detail)
    return out


def _detect_toolchain(root: Path, info: Dict) -> Dict:
    """Host build toolchain requirements: cmake minimum version / C++ standard / tool references / test infrastructure.

    Tool reference sources: find_program arguments + the first COMMAND token of execute_process/add_custom_command
    (only known tool names or tools matching a characteristic suffix are recorded, to avoid noise).
    """
    tools: Dict[str, List[str]] = {}

    def add(tool: str, how: str) -> None:
        tools.setdefault(tool, [])
        if how not in tools[tool]:
            tools[tool].append(how)

    cmake_min = None
    cxx_std = None
    has_testing = False
    for rel in info["cmake_files"]:
        text = _read_text(root / rel)
        m = _CMAKE_MIN_RE.search(text)
        if m:
            v = m.group(1).rstrip(".")
            if cmake_min is None or _ver_key(v) > _ver_key(cmake_min):
                cmake_min = v
        for rx in (_CXX_STD_RE, _CXX_STD_PROP_RE):
            m = rx.search(text)
            if m:
                v = int(m.group(1))
                if cxx_std is None or v > cxx_std:
                    cxx_std = v
        if _ENABLE_TESTING_RE.search(text) or _ADD_TEST_RE.search(text):
            has_testing = True
        for pm in _FINDPROG_RE.finditer(text):
            for tok in pm.group(1).split():
                t = tok.strip('"')
                if not t or "$" in t or t.upper() in _FP_KW:
                    continue
                # the first all-uppercase token is the receiving variable name, skip it
                if t == t.upper():
                    continue
                if _looks_like_host_tool(t):
                    add(t, "%s: find_program" % rel)
        for cm in _COMMAND_TOKEN_RE.finditer(text):
            t = cm.group(1).strip('"')
            if "$" in t:
                continue
            if _looks_like_host_tool(t):
                add(t, "%s: COMMAND" % rel)
    for rel in info["pro_files"]:
        text = _read_text(root / rel)
        for m in _QMAKE_CXX_RE.finditer(text):
            v = int(m.group(1) or m.group(2))
            if cxx_std is None or v > cxx_std:
                cxx_std = v
    return {"cmake_min": cmake_min, "cxx_standard": cxx_std,
            "tools": tools, "has_testing": has_testing}


def _ver_key(v):
    """Version string -> comparable tuple ('1.2.3b' -> (1,2,3))."""
    if not v:
        return ()
    parts = re.findall(r"\d+", str(v))
    return tuple(int(p) for p in parts)


# Platform macro classification (for macro stack tracking)
NON_OHOS_PLATFORM_MACROS = {
    "_WIN32", "WIN32", "_WIN64", "Q_OS_WIN", "Q_OS_WIN32", "Q_OS_WINRT",
    "__APPLE__", "Q_OS_MAC", "Q_OS_MACOS", "Q_OS_MACX", "Q_OS_DARWIN",
    "__MACH__", "Q_OS_AIX", "Q_OS_SOLARIS", "Q_OS_BSD", "Q_OS_FREEBSD",
    "Q_OS_ANDROID", "Q_OS_IOS", "Q_OS_TVOS", "Q_OS_WATCHOS",
    "Q_OS_QNX", "Q_OS_VXWORKS", "Q_OS_INTEGRITY",
}
OHOS_OR_GENERAL_MACROS = {
    "Q_OS_LINUX", "__linux__", "linux", "Q_OS_UNIX", "Q_OS_OHOS",
    "Q_OS_POSIX", "_POSIX_SOURCE", "__USE_POSIX",
}
# Feature macros (injected by CMake/qmake) are conservatively treated as "may compile on HarmonyOS"
FEATURE_MACROS = {
    "HAVE_X11", "USE_DBUS", "USE_PULSEAUDIO", "USE_ALSA", "USE_COREAUDIO",
    "HAVE_DBUS", "HAVE_ALSA", "HAVE_PULSEAUDIO", "HAVE_SYSTEMD",
    "USE_OPENGL", "HAVE_OPENGL", "PLATFORM_LINUX", "PLATFORM_OHOS",
}

_IFDEF_RE = re.compile(r"#\s*ifdef\s+(\w+)")
_IFNDEF_RE = re.compile(r"#\s*ifndef\s+(\w+)")
_IF_DEFINED_RE = re.compile(r"#\s*if\s+(.+)$")
_DEFINED_RE = re.compile(r"defined\s*\(\s*(\w+)\s*\)|defined\s+(\w+)")
_ELSE_RE = re.compile(r"#\s*else\b")
_ELIF_RE = re.compile(r"#\s*elif\s+(.+)$")
_ENDIF_RE = re.compile(r"#\s*endif\b")


def _extract_defined_macros(expr: str) -> List[str]:
    """Extract defined(X) macro names from an #if expression."""
    return [m[0] or m[1] for m in _DEFINED_RE.findall(expr)]


def _macro_compiles_on_ohos(macro: str) -> bool:
    """Whether a single macro is true in a HarmonyOS build (conservative estimate).

    - HarmonyOS/generic macros -> True (definitely true or conservatively treated as true)
    - non-HarmonyOS platform macros -> False (definitely false)
    - unknown macros -> True (conservative, may be injected by the build system)
    """
    if macro in NON_OHOS_PLATFORM_MACROS:
        return False
    return True  # ohos/general/feature/unknown are all conservatively treated as true


def _expr_compiles_on_ohos(expr: str) -> Optional[bool]:
    """Roughly evaluate an #if/#elif expression to decide whether it is true on HarmonyOS.

    Only combinations of defined(X) with && / || / ! are handled; returns None when unparsable (conservatively treated as true).
    """
    # extract all defined(X) -> boolean values
    def repl(m):
        name = m.group(1) or m.group(2)
        return "1" if _macro_compiles_on_ohos(name) else "0"
    simplified = _DEFINED_RE.sub(repl, expr)
    # also handle bare macro names (e.g. #if Q_OS_WIN) -- conservatively treat the macro name as the condition
    for tok in re.findall(r"\b[A-Z_]\w*\b", simplified):
        if tok in ("1", "0", "defined", "true", "false"):
            continue
        simplified = simplified.replace(tok,
            "1" if _macro_compiles_on_ohos(tok) else "0")
    try:
        # evaluate with Python (&& -> and, || -> or, ! -> not)
        py = simplified.replace("&&", " and ").replace("||", " or ")
        py = re.sub(r"!(?=[01(])", " not ", py)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return bool(eval(py, {"__builtins__": {}}, {}))
    except Exception:
        return None


def _guard_status(active_macros: List[str]) -> str:
    """Determine the compile-guard status of an interface hit line from active macros (legacy compatibility interface).

    Note: #if expressions may mix AND/OR and cannot be evaluated precisely.
    New code should use frame-level compiles_on_ohos tracking; this function is kept only for simple cases.
    """
    if not active_macros:
        return "unconditional"
    if all(m in NON_OHOS_PLATFORM_MACROS for m in active_macros):
        return "platform-excluded"
    return "ohos-active"


def _macro_stack_status(text: str) -> Dict[int, str]:
    """Line-by-line macro stack tracking, returning {line_no: guard_status}.

    Each stack frame records (compiles_on_ohos: Optional[bool]).
    A line's compile status = AND of all frames' compiles_on_ohos:
      - any frame False -> platform-excluded (definitely not compiled)
      - all frames True -> ohos-active (definitely compiled)
      - contains None (undeterminable) -> ohos-active (conservative)
      - no frames -> unconditional
    """
    result: Dict[int, str] = {}
    # stack element: compiles_on_ohos (True/False/None)
    stack: List[Optional[bool]] = []

    def current_guard() -> str:
        if not stack:
            return "unconditional"
        if any(f is False for f in stack):
            return "platform-excluded"
        return "ohos-active"

    for lineno, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        # fast path: the vast majority of lines are not preprocessor directives and don't affect the macro stack
        if not s.startswith("#"):
            result[lineno] = current_guard()
            continue
        m = _IFDEF_RE.match(s)
        if m:
            stack.append(_macro_compiles_on_ohos(m.group(1)))
            result[lineno] = current_guard()
            continue
        m = _IFNDEF_RE.match(s)
        if m:
            # ifndef MACRO: compiles on HarmonyOS iff MACRO is false on HarmonyOS
            val = _macro_compiles_on_ohos(m.group(1))
            stack.append(None if val is None else (not val))
            result[lineno] = current_guard()
            continue
        m = _IF_DEFINED_RE.match(s)
        if m:
            stack.append(_expr_compiles_on_ohos(m.group(1)))
            result[lineno] = current_guard()
            continue
        if _ELSE_RE.match(s) and stack:
            val = stack[-1]
            stack[-1] = None if val is None else (not val)
            result[lineno] = current_guard()
            continue
        m = _ELIF_RE.match(s)
        if m and stack:
            stack[-1] = _expr_compiles_on_ohos(m.group(1))
            result[lineno] = current_guard()
            continue
        if _ENDIF_RE.match(s) and stack:
            stack.pop()
            result[lineno] = current_guard()
            continue
        result[lineno] = current_guard()
    return result



def _detect_dynamic_loads(root: Path, info: Dict) -> List[Dict]:
    """Runtime dynamic-load targets in source (string literals only; variable concatenation can't be determined statically).

    Loads inside non-HarmonyOS platform guards (#if defined(Q_OS_WIN) etc.) are not compiled
    and are not counted (gen_h postmortem: QLibrary("kernel32") in singleapplication.cpp
    inside a Q_OS_WIN block was falsely reported as a runtime dynamic load).
    """
    targets: Dict[str, List[str]] = {}
    # substring prefilter: run the regex only if at least one of the three target API names appears (measured on large repos at
    # 1/3 of total scan time; most files contain no dynamic loading); macro stack tracking likewise only runs on
    # the rare files that hit the prefilter, so no performance cost
    prefilter = ("dlopen", "QLibrary", "QPluginLoader")
    for src in info["sources"]:
        if src["ext"] not in TEXT_SCAN_EXTS:
            continue
        text = _read_text(root / src["path"])
        if not any(k in text for k in prefilter):
            continue
        guard = _macro_stack_status(text)
        for rx, how in ((_DLOPEN_RE, "dlopen"), (_QLIBRARY_RE, "QLibrary"),
                        (_QPLUGINLOADER_RE, "QPluginLoader")):
            for m in rx.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                if guard.get(line) == "platform-excluded":
                    continue
                t = m.group(1).strip()
                if not t or "$" in t or "://" in t or t.startswith("/"):
                    continue
                targets.setdefault(t, []).append("%s (%s)" % (src["path"], how))
    return [{"name": t, "how": hows[:3]} for t, hows in sorted(targets.items())]


def _detect_qmake_libs(root: Path, info: Dict) -> List[Dict]:
    """Target-side link libraries from qmake LIBS += -lfoo."""
    libs: Dict[str, List[str]] = {}
    for rel in info["pro_files"]:
        for m in _QMAKE_LIBS_RE.finditer(_read_text(root / rel)):
            for lm in _QMAKE_LINK_FLAG_RE.finditer(m.group(1)):
                libs.setdefault(lm.group(1), []).append(rel)
    return [{"name": n, "evidence": ev[:3]} for n, ev in sorted(libs.items())]


def _detect_gitmodules(root: Path) -> List[Dict]:
    """.gitmodules: vendored dependencies (submodules pinned to specific commits)."""
    p = root / ".gitmodules"
    if not p.is_file():
        return []
    mods: List[Dict] = []
    cur: Dict = {}

    def flush():
        if cur.get("path") or cur.get("url"):
            mods.append(cur)

    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if s.startswith("[submodule"):
            flush()
            nm = re.search(r'"(.*)"', s)
            cur = {"name": nm.group(1) if nm else ""}
        elif "=" in s and cur:
            k, v = (x.strip() for x in s.split("=", 1))
            cur[k] = v
    flush()
    return mods


def _detect_vendored_dirs(root: Path) -> List[str]:
    """Bundled source directories such as 3rdparty/ (recognized within the root and first-level subdirectories)."""
    out = set()
    bases = [root] + [p for p in root.iterdir()
                      if p.is_dir() and not p.name.startswith(".")]
    for base in bases:
        for name in VENDORED_DIR_NAMES:
            d = base / name
            if not d.is_dir():
                continue
            # must contain at least one subdirectory or build file to count as a vendored dependency collection
            if any(s.is_dir() for s in d.iterdir()) or (d / "CMakeLists.txt").is_file():
                out.add(d.relative_to(root).as_posix())
    return sorted(out)


def _fold_name(name: str) -> str:
    """Folding rule for target/directory/dependency names: lowercase + non-alphanumerics folded to `-`."""
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")


def _detect_first_party(root: Path, cmake_files: List[str],
                        pro_files: List[str]) -> Dict:
    """Names the project produces itself: CMake targets, directories containing build files, subproject names.

    When these names appear in `target_link_libraries` (`external_<x>` imported targets,
    targets generated by wrapper macros) they are **things this repository compiles**, not external dependencies. Without this
    check, tdesktop's `external_auto_updates` / `external_crash_reports` /
    `external_tde2e` / `external_wallet_engine` would be treated as third-party libraries, producing
    `pkg-unknown:*` ghost nodes, and `fetch-deps` would then report "needs porting yourself".

    `external_<x>` is the naming convention of the external wrapper layer; real external libraries (openal/ada/rnnoise)
    go this way too: the distinction is **whether the wrapper file contains dependency declarations** (find_package /
    pkg_check_modules / find_library). No declarations = purely in-project implementation.
    """
    targets: set = set()
    dirs: Dict[str, str] = {}
    projects: set = set()
    texts: Dict[str, str] = {}
    for rel in cmake_files:
        try:
            text = _strip_cmake_comments(_read_text(root / rel))
        except OSError:
            continue
        texts[rel] = text
        parts = Path(rel).parts[:-1]
        if parts:
            dirs.setdefault(_fold_name(parts[-1]), "/".join(parts))
        for m in re.finditer(r"\bproject\s*\(\s*([A-Za-z][A-Za-z0-9_-]*)", text):
            projects.add(_fold_name(m.group(1)))
        declares_dep = bool(
            re.search(r"\bfind_package\s*\(", text, re.I)
            or re.search(r"\bpkg_check_modules\s*\(", text, re.I)
            or re.search(r"\bfind_library\s*\(", text, re.I)
            or re.search(r"\bpkg_search_module\s*\(", text, re.I))
        has_sources = _dir_has_sources(root, Path(rel).parent)
        for m in _ADD_TARGET_RE.finditer(text):
            tgt = m.group(1).lower()
            if tgt.startswith("${"):
                continue
            targets.add(_fold_name(tgt))
            if (tgt.startswith("external_") and not declares_dep
                    and has_sources):
                # the wrapper layer only exists to define targets uniformly, has no external dependency declarations inside,
                # and the source is in the repository -- only when all three conditions hold is it an in-project implementation.
                # without has_sources: uninitialized submodules (tdesktop's webrtc/
                # ada/rnnoise) would be misjudged as "compiled with the project", hiding real gaps instead.
                targets.add(_fold_name(tgt[len("external_"):]))
    for rel in pro_files:
        parts = Path(rel).parts[:-1]
        if parts:
            dirs.setdefault(_fold_name(parts[-1]), "/".join(parts))
    dirs.pop("", None)
    dirs.pop("-", None)
    return {"targets": sorted(targets),
            "dirs": dict(sorted(dirs.items())),
            "projects": sorted(projects)}


_SRC_SUFFIXES = (".c", ".cc", ".cpp", ".cxx", ".m", ".mm", ".s", ".S")


def _dir_has_sources(root: Path, rel_dir: Path, depth: int = 2) -> bool:
    """Whether this directory (or up to depth levels below) contains source files.

    Used to distinguish "a wrapper target really backed by source" from "a wrapper target pointing at an uninitialized submodule".
    """
    base = root / rel_dir
    if not base.is_dir():
        return False
    stack = [(base, 0)]
    while stack:
        current, level = stack.pop()
        try:
            entries = sorted(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_file() and entry.suffix in _SRC_SUFFIXES:
                return True
            if entry.is_dir() and level < depth and not entry.name.startswith("."):
                stack.append((entry, level + 1))
    return False


def first_party_folds(info: Dict) -> set:
    """scan_info -> folded set of project-owned names (a dependency name hitting it is not an external package).

    Only **target names** and `project()` names are collected, not directory names: same-named directories are common
    (`cmake/external/ada/` holds the wrapper for an external library), and folding by directory would hide real dependencies
    as project-owned code (observed: `find_package(ada)` was swallowed by the directory
    name of `external_ada`).
    """
    fp = info.get("first_party") or {}
    folds = set(fp.get("targets") or [])
    folds.update(fp.get("projects") or [])
    return {f for f in folds if f}


# ------------------------------------------------ Detection of all dependency declaration forms (second round)


def _norm_lib_name(name: str) -> str:
    """Normalize bare link names: strip file suffixes such as .lib/.so/.a/.dylib."""
    return re.sub(r"\.(lib|so|a|dylib)(\.\d+)*$", "", name)


def _add_raw_lib(out: Dict[str, Dict], name: str, how: str, rel: str,
                 ext_target: bool = False,
                 platform: Optional[str] = None) -> None:
    n = _norm_lib_name(name).strip('"\'')
    if not n or not re.fullmatch(r"[A-Za-z0-9_.+-]+", n):
        return
    e = out.setdefault(n.lower(), {"name": n, "hows": [], "evidence": []})
    if ext_target:
        # the name comes from a ns::external_<name> imported target (e.g. desktop-app::external_zlib):
        # the real find_package lives in an external build module (cmake_helpers etc.),
        # and the link name is the only visible declaration -- mark it as a high-confidence external dependency
        e["ext_target"] = True
    # platform block context: only mark when all declaration sites are inside other-platform if blocks;
    # any declaration site outside a platform block clears it (cross-platform library is required)
    if platform:
        if not e.get("unguarded"):
            e["platform_block"] = platform
    else:
        e["unguarded"] = True
        e.pop("platform_block", None)
    if how not in e["hows"]:
        e["hows"].append(how)
    if rel not in e["evidence"] and len(e["evidence"]) < 3:
        e["evidence"].append(rel)


def _detect_qmake_pkgconfig(root: Path, info: Dict) -> List[Dict]:
    """qmake: pkg-config dependencies from CONFIG += link_pkgconfig + PKGCONFIG += foo."""
    out: List[Dict] = []
    seen = set()
    for rel in info["pro_files"]:
        for m in _QMAKE_PKGCONFIG_RE.finditer(_read_text(root / rel)):
            for tok in _PKGCONF_NAME_RE.findall(m.group(1)):
                if tok.lower() not in seen:
                    seen.add(tok.lower())
                    out.append({"name": tok, "evidence": [rel]})
    return out


_CMT_RE = re.compile(r"#[^\n]*")


def _strip_cmake_comments(text: str) -> str:
    """Strip # line comments (comment text inside multi-line call arguments pollutes bare-name extraction)."""
    return _CMT_RE.sub(" ", text)


def _detect_cmake_raw_links(root: Path, cmake_files: List[str]):
    """Direct links in CMake not declared through find_package:

    - bare names in target_link_libraries (excluding in-project add_library/add_executable targets,
      imported targets Foo::Bar, ${VAR}/generator expressions, keywords and link flags)
    - -lfoo link flags (including multi-flag strings inside quotes)
    - "-framework X" (macOS frameworks)
    - library name candidates of find_library(VAR [NAMES] name...)
    Returns (raw_libs, macos_frameworks).
    """
    raw: Dict[str, Dict] = {}
    frameworks: Dict[str, List[str]] = {}
    texts: Dict[str, str] = {}
    all_texts: Dict[str, str] = {}   # includes vendored: for target definition collection
    defined = set()
    lib_macros = set()      # macro/function names that call add_library in their body
    for rel in cmake_files:
        text = _strip_cmake_comments(_read_text(root / rel))
        all_texts[rel] = text
        if _is_vendored_path(rel):
            # link declarations (target_link_libraries etc.) are not collected: vendored third-party
            # code's own links don't count as application dependencies; but its target definitions still take part in collection (see below)
            continue
        texts[rel] = text
        # wrapper detection: add_library( inside a macro/function definition block =>
        # calling <wrapper>(<target> ...) also defines an in-project target
        for dm in _MACRO_DEF_RE.finditer(text):
            body = text[dm.end():]
            em = _END_BLOCK_RE.search(body)
            if em and "add_library(" in body[:em.start()]:
                lib_macros.add(dm.group(1).lower())
    # set(<var> <literal>) variable table: resolves the target name of add_library(${VAR} ...)
    vart: Dict[str, str] = {}
    for text in all_texts.values():
        for m in re.finditer(
                r"^\s*set\s*\(\s*(\w+)\s+\"?([\w.]+)\"?\s*\)",
                text, re.M):
            vart.setdefault(m.group(1), m.group(2))
    # target definition collection (including vendored files): inside vendored source,
    # add_library(fluidsynth) defines an in-project target, and the application-side
    # target_link_libraries(fluidsynth) links the internal target rather than an external package
    wrapper_defined = set()   # external_* targets defined in wrapper files
    for rel, text in all_texts.items():
        is_wrapper = (_is_vendored_path(rel)
                      and _WRAPPER_TARGET_RE.search(text))
        for m in _ADD_TARGET_RE.finditer(text):
            tgt = m.group(1)
            if tgt.startswith("${"):
                # add_library(${VAR} ...): resolve the target name via the set(VAR x) variable table
                tgt = vart.get(tgt[2:-1].strip(), "")
            if tgt:
                defined.add(tgt.lower())
                if is_wrapper and tgt.lower().startswith("external_"):
                    wrapper_defined.add(tgt.lower())
        if lib_macros:
            for mw in lib_macros:
                for m in re.finditer(
                        r"\b%s\s*\(\s*([A-Za-z0-9_.:-]+)" % re.escape(mw),
                        text, re.I):
                    defined.add(m.group(1).lower())
    for rel, text in texts.items():
        pmap = _cmake_platform_line_map(text)
        for m in _TARGET_LINK_RE.finditer(text):
            args = _strip_cmake_comments(m.group(1))
            args = args.replace("\\\n", " ").replace('"', " ")
            line = text.count("\n", 0, m.start()) + 1
            plat = pmap.get(line)
            for fw in _FRAMEWORK_RE.finditer(args):
                frameworks.setdefault(fw.group(1), []).append(rel)
            # framework segments don't take part in bare-name/link-flag extraction
            args = _FRAMEWORK_RE.sub(" ", args)
            body = args.split(None, 1)
            if len(body) < 2:
                continue
            for lm in _LFLAG_RE.finditer(args):
                _add_raw_lib(raw, lm.group(1), "target_link_libraries -l", rel,
                             platform=plat)
            for tok in body[1].split():
                t = tok.strip()
                if not t or t.startswith("$") or t.upper() in _TLL_KEYWORDS \
                        or t.startswith("-"):
                    continue
                if "::" in t:
                    # imported target ns::name: the external_ prefix is a common convention of external
                    # wrapper layers such as cmake_helpers -- the name with the prefix stripped is a high-confidence external library
                    # declaration (all of corpus_a's third-party libraries go this way; find_package is not visible).
                    # PkgConfig::X is already covered by pkg_check_modules; Qt6::/in-project
                    # lib_* targets are not external package declarations, skip.
                    ns, _, tgt = t.partition("::")
                    tgt = tgt.strip('"')
                    tl = tgt.lower()
                    if (ns.lower() == "pkgconfig"
                            or not re.fullmatch(r"[A-Za-z0-9_.+-]+", tgt)
                            or not tl.startswith("external_")
                            or (tl in defined and tl not in wrapper_defined)
                            or (tgt.lower() in defined
                                and tl not in wrapper_defined)
                            or tl[len("external_"):].startswith(("qt", "kf"))):
                        continue
                    base = tgt[len("external_"):]
                    _add_raw_lib(raw, base,
                                 "target_link_libraries external-target", rel,
                                 ext_target=True, platform=plat)
                    continue
                if ("/" in t or "\\" in t):
                    continue
                _add_raw_lib(raw, t, "target_link_libraries", rel,
                             platform=plat)
        for m in _FINDLIB_RE.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            plat = pmap.get(line)
            toks = _strip_cmake_comments(m.group(1)).replace("\\\n", " ").split()
            # the first argument is the result variable name, always skipped; library name candidates follow NAMES,
            # paths/descriptions follow PATHS/HINTS/PATH_SUFFIXES/DOC (skipped)
            skip_value_kw = {"PATHS", "HINTS", "PATH_SUFFIXES", "DOC",
                             "VALIDATOR"}
            in_skip = False
            for i, tok in enumerate(toks):
                if i == 0:
                    continue
                t = tok.strip('"')
                up = t.upper()
                if up in _FINDLIB_KW or up == "NAMES":
                    in_skip = up in skip_value_kw
                    continue
                if in_skip or "$" in t:
                    continue
                if re.search(r"_(LIBRARY|LIBRARIES|LIB|LIBS)$", t):
                    continue
                # all-uppercase + underscore tokens are CMake variables/keywords (e.g. WIN32_DEBUG_POSTFIX that
                # slipped into the argument list in gen_a's FindQUAZIP.cmake), not
                # library name candidates; single-character tokens (such as the value d after the keyword above)
                # are also almost never library names on disk
                if re.fullmatch(r"[A-Z][A-Z0-9_]*_+[A-Z0-9_]*", t) or len(t) == 1:
                    continue
                _add_raw_lib(raw, t, "find_library", rel, platform=plat)
    for name in defined:      # in-project targets are not external dependencies
        raw.pop(name, None)
    fw_list = [{"name": k, "evidence": v[:3]} for k, v in sorted(frameworks.items())]
    return (sorted(raw.values(), key=lambda d: d["name"]),
            fw_list)


def _detect_fetched_deps(root: Path, cmake_files: List[str]) -> List[Dict]:
    """FetchContent_Declare / ExternalProject_Add / CPMAddPackage:
    Source dependencies fetched at configure time (GIT_REPOSITORY/URL + GIT_TAG/VERSION).

    vendored paths are not skipped: thirdparty/CMakeLists.txt is often the host's own
    fetch glue (gen_i evidence: all CPM declarations are in thirdparty/; skipping them lost
    the bundled declarations of ads/QSimpleUpdater etc., so link names could not be merged as in-tree).
    """
    out: List[Dict] = []
    seen = set()
    for rel in cmake_files:
        text = _strip_cmake_comments(_read_text(root / rel))
        for m in _FETCHED_DECLARE_RE.finditer(text):
            cmd, name, args = m.group(1), m.group(2), m.group(3)
            um = _FETCH_URL_RE.search(args)
            tm = _FETCH_TAG_RE.search(args)
            url = um.group(1).strip('",') if um else None
            if name in ("GITHUB_REPOSITORY", "GIT_REPOSITORY", "URL"):
                name = url.split("/")[-1] if url else name
            elif name == "NAME":
                # CPMAddPackage(NAME <name> ...): the first token is the keyword NAME,
                # the actual package name follows it (gen_i evidence: the literal NAME was once taken as the package name)
                nm = re.match(r"\s*\"?([A-Za-z0-9_.:+-]+)", args)
                if not nm or nm.group(1).startswith("$"):
                    # CPMAddPackage(NAME ${Name}) inside the CPM implementation file:
                    # cannot be resolved statically, skip (once produced the garbage entry "NAME")
                    continue
                name = nm.group(1)
            name = name.strip('",')
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append({"name": name, "how": _FETCHED_HOW[cmd], "url": url,
                        "tag": tm.group(1).strip('",') if tm else None,
                        "file": rel})
    return out


def _meson_internal_names(root: Path, meson_files: List[str]) -> set:
    """Set of dependency names defined/bundled inside a meson project (folding rule: lowercase, strip non-alpha-
    numerics, strip the lib prefix):

    - meson.override_dependency('name', ...) -- dependencies defined by the project's own library()
      (rizin's rz_core/rz_util etc.; gen_j evidence: once falsely reported en masse as
      need_port, actually compiled with the project via the vendored rizin submodule)
    - directory names and .wrap file names under <meson project root>/subprojects/ -- meson
      bundled subprojects (zydis/softfloat/ptrace-wrap etc.)
    """
    internal: Dict[str, str] = {}

    def fold(n: str) -> str:
        f = re.sub(r"[^a-z0-9]+", "", (n or "").lower())
        if f.startswith("lib") and len(f) > 3:
            f = f[3:]
        return f

    for rel in meson_files:
        text = _read_text(root / rel)
        for m in _MESON_OVERRIDE_RE.finditer(text):
            internal.setdefault(fold(m.group(1)), m.group(1))
    # subprojects directory (./subprojects/ of the meson project root)
    roots = set()
    for rel in meson_files:
        parts = Path(rel).parts
        if "subprojects" in parts:
            # a subproject's own meson.build: take the directory name after subprojects/
            i = parts.index("subprojects")
            if i + 1 < len(parts) and parts[i + 1] != "packagefiles":
                internal.setdefault(fold(parts[i + 1]), parts[i + 1])
            roots.add(str(Path(*parts[:i])))
        else:
            roots.add(str(Path(*parts[:-1])))
    for r in roots:
        sp = root / r / "subprojects"
        if not sp.is_dir():
            continue
        try:
            entries = list(sp.iterdir())
        except OSError:
            continue
        for e in entries:
            nm = e.name[:-5] if e.name.endswith(".wrap") else e.name
            if nm and nm != "packagefiles":
                internal.setdefault(fold(nm), nm)
    return set(internal)


def _absorb_meson(root: Path, info: Dict, meson_files: List[str]) -> None:
    """meson.build: dependency('name', version:) / cc.find_library /
    meson_version / cpp_std / subproject() / qt5|qt6 modules.

    Results are merged into info (meson_deps / meson / raw_libs / qt_modules).
    Internal dependencies (defined by override_dependency / bundled in subprojects) are marked internal=True,
    so deps_report files them as in-tree rather than need_port (gen_j/rizin evidence).
    """
    meson_info: Dict = {"version_min": None, "cxx_standard": None,
                        "subprojects": [], "internal_deps": []}
    deps: Dict[str, Dict] = {}
    internal = _meson_internal_names(root, meson_files)

    def _fold(n: str) -> str:
        f = re.sub(r"[^a-z0-9]+", "", (n or "").lower())
        if f.startswith("lib") and len(f) > 3:
            f = f[3:]
        return f

    for rel in meson_files:
        text = _read_text(root / rel)
        # meson declarations inside a vendored third-party subtree don't count as application dependencies (same rule as the CMake
        # detector; corpus_a postmortem: libgeoclue/pipewire of ThirdParty/xdg-desktop-portal
        # leaked into the application's depth-1)
        vendored = _is_vendored_path(rel)
        if not meson_info["version_min"]:
            pm = _MESON_PROJECT_RE.search(text)
            if pm:
                vm = _MESON_MIN_RE.search(pm.group(1))
                if vm:
                    meson_info["version_min"] = vm.group(1)
                sm = _MESON_STD_RE.search(pm.group(1))
                if sm:
                    meson_info["cxx_standard"] = int(sm.group(1))
        for sp in _MESON_SUBPROJECT_RE.finditer(text):
            sp_name = sp.group(1).rstrip("-_+.")
            if sp_name and sp_name not in meson_info["subprojects"]:
                meson_info["subprojects"].append(sp_name)
        for m in _MESON_DEP_RE.finditer(text):
            if vendored:
                continue
            name, args = m.group(1), m.group(2)
            # meson string interpolation ('libpcre2-@0@'): strip placeholders, otherwise
            # garbage names such as "libpcre2-@0@" end up in the report (rizin/meson.build evidence)
            name = name.replace("@0@", "").rstrip("-_.")
            if not name:
                continue
            if name in ("qt5", "qt6"):
                info["qt_version_hint"] = info.get("qt_version_hint") or name[2]
                mm = _MESON_MODS_RE.search(args)
                if mm:
                    for mod in re.findall(r"'(\w+)'", mm.group(1)):
                        if mod.lower() not in info["qt_modules"]:
                            info["qt_modules"].append(mod.lower())
                continue
            e = deps.setdefault(name, {"name": name, "version": None,
                                       "required": True, "evidence": [rel]})
            vm = _MESON_VER_RE.search(args)
            if vm and not e["version"]:
                e["version"] = vm.group(1)
            if _MESON_OPT_RE.search(args):
                e["required"] = False
            if _fold(name) in internal:
                e["internal"] = True
        for fl in _MESON_FINDLIB_RE.finditer(text):
            if vendored:
                continue    # a vendored third-party subtree's own declarations don't count as application dependencies
            if _fold(fl.group(1)) in internal:
                continue    # in-project library (defined by override_dependency)
            _merge_raw_lib(info["raw_libs"], fl.group(1),
                           "cc.find_library", rel)
    meson_info["internal_deps"] = sorted(internal)
    info["meson"] = meson_info
    info["meson_deps"] = sorted(deps.values(), key=lambda d: d["name"])


def _merge_raw_lib(raw_libs: List[Dict], name: str, how: str, rel: str) -> None:
    """Merge bare library names into info["raw_libs"] (deduplicated by lowercase name)."""
    n = _norm_lib_name(name).strip('"\'')
    if not n or not re.fullmatch(r"[A-Za-z0-9_.+-]+", n):
        return
    for e in raw_libs:
        if e["name"].lower() == n.lower():
            if how not in e["hows"]:
                e["hows"].append(how)
            if rel not in e["evidence"] and len(e["evidence"]) < 3:
                e["evidence"].append(rel)
            return
    raw_libs.append({"name": n, "hows": [how], "evidence": [rel]})


def _absorb_autotools(root: Path, info: Dict,
                      autotools_files: List[str]) -> None:
    """configure.ac: PKG_CHECK_MODULES (with version constraints) /
    AC_CHECK_LIB / AC_SEARCH_LIBS (bare library names)."""
    deps: Dict[str, Dict] = {}
    for rel in autotools_files:
        text = _read_text(root / rel)
        # a vendored third-party subtree's own configure.ac doesn't count as an application dependency (same rule as the CMake
        # detector; corpus_a postmortem: anthy/gtk+/m17n of ThirdParty/nimf
        # leaked into the application's depth-1)
        if _is_vendored_path(rel):
            continue
        for m in _PKGCHK_MOD_RE.finditer(text):
            # module lists are separated by commas or whitespace; a single spec can be "name" or
            # "name >= ver"
            for chunk in re.split(r",\s*", m.group(1)):
                for sm in re.finditer(
                        r"([A-Za-z0-9_.+-]+)"
                        r"(?:\s*(>=|<=|==|=|<|>)\s*([\w.]+))?", chunk):
                    nm, op, ver = sm.group(1), sm.group(2), sm.group(3)
                    e = deps.setdefault(
                        nm.lower(), {"name": nm, "version_req": None,
                                     "evidence": [rel]})
                    if op and ver and not e["version_req"]:
                        e["version_req"] = "%s %s" % (op, ver)
        for m in _AC_CHECK_LIB_RE.finditer(text):
            _merge_raw_lib(info["raw_libs"], m.group(1), "AC_CHECK_LIB", rel)
        for m in _AC_SEARCH_LIBS_RE.finditer(text):
            for lib in re.split(r"[\s,]+", m.group(1)):
                if lib and re.fullmatch(r"[A-Za-z0-9_.+-]+", lib):
                    _merge_raw_lib(info["raw_libs"], lib, "AC_SEARCH_LIBS", rel)
    info["autotools_deps"] = sorted(deps.values(), key=lambda d: d["name"])


def _collect_ci_files(root: Path) -> List[str]:
    """CI / install script files: .github/, .ci/ recursively + top-level *.sh.

    _walk skips directories starting with '.', so they are collected explicitly here.
    """
    out: List[str] = []
    for base in (root / ".github", root / ".ci"):
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if p.is_file() and p.suffix.lower() in (".yml", ".yaml", ".sh"):
                out.append(p.relative_to(root).as_posix())
    for p in root.glob("*.sh"):
        out.append(p.relative_to(root).as_posix())
    return out


def _detect_env_installs(root: Path, ci_files: List[str]) -> List[Dict]:
    """Environment dependencies declared by CI / install scripts (package name lists of apt/brew/pacman install).

    This is the build machine's environment list (a mix of build tools and link libraries), used as a
    cross-check source for build-file analysis; distro package names (libfoo-dev) must be mapped back to library names.
    """
    out: Dict[str, Dict] = {}
    # tokens with a leading '-' are captured too (the -y of apt install -y must not be truncated at its first character
    # and misread as the package name y, gen_e CI evidence)
    tok_re = re.compile(r"-?[A-Za-z0-9][A-Za-z0-9_.@+-]*")
    skip = {"sudo", "update", "install", "install-recommends", "upgrade",
            "dist-upgrade"}
    for rel in ci_files:
        text = _read_text(root / rel).replace("\\\n", " ")
        for m in re.finditer(r"(?:apt(?:-get)?|brew|pacman)\b[^\n]*", text):
            seg = m.group(0)
            pm = re.search(r"(?:\binstall\b|\s-S)\s+(.*)", seg)
            if not pm:
                continue
            tail = re.split(r"\|\||&&", pm.group(1))[0]
            for tok in tok_re.findall(tail):
                t = tok.lower()
                if tok.startswith("-") or t in skip:
                    continue
                e = out.setdefault(t, {"name": tok.split("=")[0],
                                       "evidence": []})
                if rel not in e["evidence"] and len(e["evidence"]) < 3:
                    e["evidence"].append(rel)
        if len(out) > 60:
            break
    return sorted(out.values(), key=lambda d: d["name"])
