"""Qt 工程预扫描（vendored，独立于 qt_ohos 包）。

识别构建系统（qmake/CMake）、Qt 模块与版本、源文件清单、语言统计、
第三方包声明（find_package / pkg_check_modules / Conan / vcpkg 清单）。
供 project_scanner 消费。

综合依赖分析增强（deps report 消费）：
- find_package 完整参数（最低版本 / REQUIRED / COMPONENTS / OPTIONAL_COMPONENTS）
- 主机构建工具链（cmake 最低版本 / C++ 标准 / find_program / COMMAND 工具引用）
- 运行时动态加载（dlopen / QLibrary / QPluginLoader 字面量）
- qmake LIBS 链接库、.gitmodules 自带依赖、vendored 目录
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
# 构建输出目录（build / build-Debug / build.123 / build2）：排除以免扫到生成物；
# 注意 buildscripts / buildtools 是源码目录（muse、musescore 的依赖清单
# ExtDepsManifest.cmake / SetupQt6.cmake 都在其中），不能按 build 前缀排除
# （e2e musescore 复核确认的前缀误排除 bug）。
_BUILD_DIR_RE = re.compile(r"^build(?:[-._].+|\d+)?$")
MAX_FILE_BYTES = 2 * 1024 * 1024

_PRO_QT_RE = re.compile(r"^\s*QT\s*([+\-]?=)\s*(.*)$", re.M)
# 兼容 find_package(Qt6 ${VER} CONFIG REQUIRED COMPONENTS Core Gui ...) 形式
_CMAKE_FINDPKG_QT_RE = re.compile(r"find_package\s*\(\s*Qt(\d)\b([^)]*)\)", re.I)
_CMAKE_FINDPKG_KF_RE = re.compile(r"find_package\s*\(\s*KF(\d)\b([^)]*)\)", re.I)
_KF_LINK_RE = re.compile(r"KF\d::(\w+)")
# 子目标/别名 -> 归一化组件名
_KF_ALIAS = {"configcore": "config", "configgui": "config",
             "kiocore": "kio", "kiowidgets": "kio", "kiofilewidgets": "kio",
             "i18nqml": "i18n", "bookmarkswidgets": "bookmarks"}
_COMPONENTS_RE = re.compile(r"\bCOMPONENTS\s+([^)]*)", re.I)
_CMAKE_KW = {"REQUIRED", "CONFIG", "QUIET", "MODULE", "COMPONENTS",
             "OPTIONAL_COMPONENTS"}
# 任意 find_package(<Name> ...) —— 捕获第三方包名（Qt/KF 已单独处理）
_FINDPKG_ANY_RE = re.compile(r"find_package\s*\(\s*([A-Za-z0-9_]+)", re.I)
# pkg_check_modules(<PREFIX> [REQUIRED] <module> [<module> ...])
_PKGCHECK_RE = re.compile(r"pkg_check_modules\s*\(\s*\w+\s+([^)]*)\)", re.I)
_PKGCONF_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]*")
_INCLUDE_QT_RE = re.compile(r"#\s*include\s*<\s*(Qt([A-Za-z0-9]+|))\s*/")
# Conan / vcpkg 清单（版本可为精确号或范围串，如 [>=1.2 <2]，含空格）
_CONAN_TXT_REQ_RE = re.compile(r"^\s*([A-Za-z0-9_.+-]+)(?:/(.+?))?\s*$")
_CONAN_PY_REQ_RE = re.compile(r'"([A-Za-z0-9_.+-]+)/([^"]*)"')
_VCPKG_JSON_DEPS = ("dependencies",)

# ---- 综合依赖分析增强 ----
# cmake_minimum_required(VERSION 3.16[...])
_CMAKE_MIN_RE = re.compile(
    r"cmake_minimum_required\s*\(\s*VERSION\s+([0-9][\d.]*)", re.I)
# set(CMAKE_CXX_STANDARD 17) / target 属性 CXX_STANDARD 17
_CXX_STD_RE = re.compile(r"\bCMAKE_CXX_STANDARD\s+(\d+)")
_CXX_STD_PROP_RE = re.compile(r"\bCXX_STANDARD\s+(\d+)")
# qmake: CONFIG += c++17 / -std=c++17
_QMAKE_CXX_RE = re.compile(
    r"CONFIG\s*\+=\s*[^\n]*?\bc\+\+(\d{2})\b|-std=c\+\+(\d{2})")
# find_package 完整参数串（[^)]* 跨行）
_FINDPKG_FULL_RE = re.compile(
    r"find_package\s*\(\s*([A-Za-z0-9_.-]+)\s*([^)]*)\)", re.I)
_FINDPROG_RE = re.compile(r"find_program\s*\(([^)]*)\)", re.I)
_COMMAND_TOKEN_RE = re.compile(r"\bCOMMAND\s+([^\s)]+)")
# 运行时动态加载（字面量；兼容 QLibrary lib("x") 声明形式）
_DLOPEN_RE = re.compile(r'\bdlopen\s*\(\s*"([^"]+)"')
_QLIBRARY_RE = re.compile(r'\bQLibrary(?:\s+\w+)?\s*\(\s*"([^"]+)"')
_QPLUGINLOADER_RE = re.compile(
    r'\bQPluginLoader(?:\s+\w+)?\s*\(\s*"([^"]+)"')
# qmake LIBS += -lfoo
_QMAKE_LIBS_RE = re.compile(r"^\s*LIBS\s*\+=\s*(.+)$", re.M)
_QMAKE_LINK_FLAG_RE = re.compile(r"(?:^|\s)-l([A-Za-z0-9_.+-]+)")
# 测试设施
_ENABLE_TESTING_RE = re.compile(r"\benable_testing\s*\(")
_ADD_TEST_RE = re.compile(r"\badd_test\s*\(")
# find_package 参数关键字
_FP_KW = {"REQUIRED", "CONFIG", "QUIET", "MODULE", "COMPONENTS",
          "OPTIONAL_COMPONENTS", "EXACT", "NO_MODULE", "NO_POLICY_SCOPE",
          "GLOBAL", "BYPASS_PROVIDER", "REGISTRY_VIEW", "CMAKE_FIND_ROOT_PATH"}

# 已知主机构建工具名（构建机运行，不部署到设备）。
# 命中以下集合或命中特征后缀（*-config/*-scanner 等）的
# COMMAND/find_program token 记为构建工具。
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

# vendored 源码目录名（项目内自带、随项目一起编译的依赖）
VENDORED_DIR_NAMES = ("3rdparty", "thirdparty", "third_party", "third-party",
                      "external", "extern", "ext", "vendor", "deps", "dep",
                      "subprojects", "dependencies")

# ---- 依赖声明全形式检测（deps report 第二轮增强）----
# target_link_libraries(<tgt> [PRIVATE|...] <item>...)：item 可为导入目标
# （Foo::Bar）、裸库名（z/ssl/qtermwidget6）、-lfoo、"-framework X"、路径
_TARGET_LINK_RE = re.compile(r"target_link_libraries\s*\(([^)]*)\)", re.I | re.S)
_ADD_TARGET_RE = re.compile(
    r"\b(?:qt\d+_)?add_(?:library|executable)\s*\(\s*([A-Za-z0-9_.:-]+)")
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
_MESON_VER_RE = re.compile(r"version:\s*'([^']+)'")
_MESON_OPT_RE = re.compile(r"required:\s*false")
_MESON_MODS_RE = re.compile(r"modules:\s*\[([^\]]*)\]")
_MESON_FINDLIB_RE = re.compile(r"\bcc\s*\.\s*find_library\s*\(\s*'([^']+)'")
_MESON_PROJECT_RE = re.compile(r"project\s*\(([^)]*)\)", re.S)
_MESON_MIN_RE = re.compile(r"meson_version:\s*'>=\s*([\d.]+)'")
_MESON_STD_RE = re.compile(r"cpp_std\s*=\s*'?gnu?\+\+(\d+)")
_MESON_SUBPROJECT_RE = re.compile(r"\bsubproject\s*\(\s*'([^']+)'")
# autotools：PKG_CHECK_MODULES([VAR],[foo >= 1.2]) / AC_CHECK_LIB / AC_SEARCH_LIBS
_PKGCHK_MOD_RE = re.compile(r"PKG_CHECK_MODULES\s*\(\s*\[?\w+\]?\s*,\s*\[([^\]]*)\]", re.S)
_AC_CHECK_LIB_RE = re.compile(r"AC_CHECK_LIB\s*\(\s*\[?([A-Za-z0-9_.+-]+)")
_AC_SEARCH_LIBS_RE = re.compile(r"AC_SEARCH_LIBS\s*\(\s*\[?\w+\]?\s*,\s*\[([^\]]*)\]")
# CI / 安装脚本：apt(-get) install / brew install / pacman -S <pkgs>
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
        # ---- 综合依赖分析增强 ----
        "find_package_details": [],   # find_package 完整参数（含版本/REQUIRED/组件）
        "toolchain": {},              # cmake/meson 最低版本 / C++ 标准 / 构建工具引用
        "dynamic_loads": [],          # dlopen/QLibrary/QPluginLoader 字面量
        "qmake_libs": [],             # LIBS += -lfoo
        "qmake_pkgconfig": [],        # PKGCONFIG += foo
        "git_submodules": [],         # .gitmodules 条目（自带依赖 + 锁定提交）
        "vendored_dirs": [],          # 3rdparty/ 等自带源码目录
        # ---- 依赖声明全形式检测（第二轮增强）----
        "raw_libs": [],               # 裸链接名（target_link_libraries/find_library/
                                      #   cc.find_library/AC_CHECK_LIB）
        "macos_frameworks": [],       # -framework X
        "fetched_deps": [],           # FetchContent/ExternalProject/CPM 配置期拉取
        "manifest_deps": [],          # 依赖清单函数（require_dep 等）声明的依赖
        "meson_deps": [],             # meson dependency('name', version: ...)
        "meson": {},                  # {version_min, cxx_standard, subprojects}
        "autotools_deps": [],         # PKG_CHECK_MODULES([V],[pkg >= x])
        "env_installs": [],           # CI/脚本 apt/brew/pacman install 的环境依赖
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
    # 项目自带 .cmake 模块（cmake/Modules 等）与 CMakeLists 一起参与依赖
    # 提取——find_package 常集中在被 include() 的 .cmake 里（如 qBittorrent
    # 的 CheckPackages.cmake）
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

    # 第三方包：CMake find_package/pkg_check_modules + Conan/vcpkg 清单
    info["cmake_packages"] = _detect_cmake_packages(root, info["cmake_files"])
    info["pkg_manifests"] = _detect_pkg_manifests(root)

    # 综合依赖分析增强（deps report 消费）
    info["find_package_details"] = _detect_find_package_details(root, info)
    info["toolchain"] = _detect_toolchain(root, info)
    info["dynamic_loads"] = _detect_dynamic_loads(root, info)
    info["qmake_libs"] = _detect_qmake_libs(root, info)
    info["qmake_pkgconfig"] = _detect_qmake_pkgconfig(root, info)
    info["git_submodules"] = _detect_gitmodules(root)
    info["vendored_dirs"] = _detect_vendored_dirs(root)

    # 依赖声明全形式检测（第二轮增强）
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
    # _walk 跳过 . 开头目录，CI 文件（.github/.ci/顶层 *.sh）需显式收集
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


# Qt 组件列表变量：set(<var> Core Gui ...) / list(APPEND <var> X ...)，
# 供 find_package(Qt6 ... COMPONENTS ${var}) 展开（muse 框架 SetupQt6.cmake 形式）
_SET_LISTVAR_RE = re.compile(r"\bset\s*\(\s*(\w+)\s+(.*?)\)", re.S)
_LIST_APPEND_RE = re.compile(r"\blist\s*\(\s*APPEND\s+(\w+)\s+([^)]*)\)", re.S)
_LISTVAR_TOKEN_KW = {"CACHE", "PATH", "STRING", "BOOL", "FILEPATH", "INTERNAL",
                     "FORCE", "ON", "OFF", "REQUIRED"}


def _listvar_tokens(body: str) -> List[str]:
    """set/list(APPEND) 值域里的组件名 token（标识符，剔除关键字/${var}/字面量）。"""
    out = []
    for tok in body.split():
        tok = tok.strip('"\'')
        if (not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", tok)
                or tok.upper() in _LISTVAR_TOKEN_KW):
            continue
        out.append(tok)
    return out


def _collect_list_vars(root: Path, cmake_files: List[str]) -> Dict[str, str]:
    """累积 set(<var> ...) / list(APPEND <var> ...) 的标识符列表值。

    只保留纯标识符 token（Core/Gui/...），版本号/路径/${var}/CACHE 关键字
    全部剔除，因此不会与 _collect_cmake_vars 的字面量变量冲突。
    同一文件内 set() 重置、list(APPEND) 追加；跨文件取并集（同名变量
    在不同作用域各自定义时，并集与扫描顺序无关，避免 sandbox 等
    非主构建目录的声明因目录遍历顺序而遮蔽主声明）。
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
            for comp in re.split(r"\s+", comps):
                comp = comp.strip()
                if comp and comp.isalpha() and comp.upper() not in _CMAKE_KW:
                    modules.add(comp.lower())
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
    if modules and qt_version is None:
        qt_version = "5"  # HarmonyOS Qt currently ships 5.12 / 5.15
    return modules, qt_version, frameworks, kf_components


def _detect_third_party(root: Path, sources: List[Dict]) -> List[Dict]:
    found: Dict[str, List[str]] = {}
    for src in sources:
        if src["ext"] not in TEXT_SCAN_EXTS:
            continue
        if _is_vendored_path(src["path"]):
            continue  # vendored 三方自己的 include 不算应用依赖证据
        text = _read_text(root / src["path"])
        for name, (pattern, _libs) in THIRD_PARTY_HINTS.items():
            if name in found and len(found[name]) >= 3:
                continue
            if re.search(pattern, text):
                found.setdefault(name, []).append(src["path"])
    return [{"name": name, "evidence": files[:5]} for name, files in
            sorted(found.items())]


# CMake 构建模块/工具链，非运行时依赖，find_package 命中时跳过。
# 与 deps_report.CUILD_TOOL_FINDPKG / CMAKE_BUILTIN_PACKAGES 对齐（避免
# 循环导入在两处维护：图侧跳过 + 报告侧归入 build-tool/system-lib 分类）
_FINDPKG_SKIP = {"ecm", "pkgconfig", "pkgconf", "threads", "sharedmimeinfo",
                 "doxygen", "gettext", "intltool", "i18n", "imported_target",
                 "findpackagehandlestandardargs", "selectlibrary",
                 "pkg_check_modules",
                 # CMake 内置模块（编译器特性 / musl libc 内置）
                 "openmp", "iconv", "dl",
                 # 主机构建工具 / VCS（find_package(Git) 是取版本，非链接 git）
                 "git", "subversion", "mercurial", "ccache", "sccache",
                 "cmake", "ninja", "python", "python3", "flex", "bison",
                 "gperf", "linguisttools"}  # noqa: keep explicit


# vendored / 依赖清单目录的路径段：其内的 CMake 声明属于内嵌三方代码自己
# 或依赖引擎的构建逻辑，不是应用自身的直接依赖（e2e musescore 复核确认：
# thirdparty/fluidsynth、KDDockWidgets/python 与 muse_deps/recipes 的
# find_package/pkg_check_modules 污染 depth-1 清单）。
# 注：不含 "ext"（过短，误伤正常目录名）；"*_deps" 后缀匹配依赖引擎子模块
# （muse_deps 等 recipes 集合）。
_VENDORED_PATH_SEGS = frozenset({
    "thirdparty", "3rdparty", "third_party", "third-party",
    "vendor", "vendors", "vendored", "external", "extern",
    "deps", "dep", "dependencies", "subprojects",
})


def _is_vendored_path(rel: str) -> bool:
    """相对路径是否位于 vendored 三方/依赖引擎目录内（依赖提取时跳过）。"""
    for seg in rel.lower().replace("\\", "/").split("/")[:-1]:
        if seg in _VENDORED_PATH_SEGS or seg.endswith("_deps"):
            return True
    return False


# pkg_check_modules 专属关键字（IMPORTED_TARGET/GLOBAL 等），非模块名
_PKGCHECK_KW = {"IMPORTED_TARGET", "GLOBAL", "STATIC", "SHARED", "MODULE",
                "OPTIONAL", "SKIP_CMAKE_DIRS", "WITHOUT_CMAKE_PACKAGE"}


def _detect_cmake_packages(root: Path, cmake_files: List[str]) -> Dict:
    """从 CMake 中提取第三方包：find_package(*) 和 pkg_check_modules。

    Qt/KF 已由 _detect_qt 专门处理，这里只返回其它包。
    返回 {find_package: [names...], pkg_check_modules: [modules...],
          pkg_modules: [{name, version_req}...]}（含版本约束）。
    """
    findpkgs = set()
    pkgmods = set()
    pkg_details: Dict[str, Dict] = {}
    vart = _collect_cmake_vars(root, cmake_files)
    skip_prefixes = ("qt", "kf")
    for rel in cmake_files:
        if _is_vendored_path(rel):
            continue
        text = _strip_cmake_comments(_read_text(root / rel))
        for m in _FINDPKG_ANY_RE.finditer(text):
            name = m.group(1).lower()
            if (name.startswith(skip_prefixes) or name in _CMAKE_KW
                    or name in _FINDPKG_SKIP
                    or name.replace(".", "").isdigit()):
                continue
            findpkgs.add(name)
        for m in _PKGCHECK_RE.finditer(text):
            # pkg-config spec 可带版本约束："glib-2.0 >= 2.50" / glib-2.0>=2.50
            # 替换 set() 变量；无法解析的 ${宏参} 整体剔除，避免混入包名
            specs = _subst_vars(m.group(1), vart).replace("\\\n", " ")
            specs = re.sub(r"\$\{\w+\}", " ", specs)
            _absorb_pkg_spec(specs, pkg_details)
            for tok in _PKGCONF_NAME_RE.findall(specs):
                tok = tok.lower()
                if (tok.upper() in _CMAKE_KW or tok in _FINDPKG_SKIP
                        or tok.upper() in _PKGCHECK_KW
                        or tok.startswith(("qt", "kf"))
                        or tok.replace(".", "").isdigit()):
                    continue
                pkgmods.add(tok)
                pkg_details.setdefault(tok, {"name": tok, "version_req": None})
    # 带约束的 spec 覆盖裸名（保留版本要求）
    pkgmods.update(pkg_details.keys())
    return {"find_package": sorted(findpkgs),
            "pkg_check_modules": sorted(pkgmods),
            "pkg_modules": sorted(pkg_details.values(),
                                  key=lambda d: d["name"])}


_PKG_SPEC_VER_RE = re.compile(
    r"([A-Za-z0-9][A-Za-z0-9._+-]*)\s*(>=|<=|==|=|<|>|!=)\s*([0-9][\w.]*)")


def _absorb_pkg_spec(spec: str, out: Dict[str, Dict]) -> None:
    """吸收一条 pkg-config spec（可含版本约束）到 out。"""
    m = _PKG_SPEC_VER_RE.search(spec)
    if not m:
        return
    name = m.group(1).lower()
    out[name] = {"name": name,
                 "version_req": "%s %s" % (m.group(2), m.group(3))}


def _detect_pkg_manifests(root: Path) -> Dict:
    """解析 Conan / vcpkg 清单，获取精确的包名+版本+传递依赖。

    返回 {conan: [{name, version?}], vcpkg: [names]}。
    """
    conan = []
    vcpkg = []
    # conanfile.txt [requires] 段
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
    # conanfile.py requires 列表
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
    # conan.lock 精确版本
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


# ------------------------------------------------ 综合依赖分析增强


def _looks_like_host_tool(tok: str) -> bool:
    """token 是否为已知主机构建工具名（或命中特征后缀）。"""
    t = tok.strip("\"'")
    if not t or t != t.strip() or "$" in t:
        return False
    if t in KNOWN_HOST_TOOLS:
        return True
    return t.endswith(_HOST_TOOL_SUFFIXES) or t.startswith("glib-")


def _parse_findpkg_args(name: str, rest: str, rel: str,
                        line: int) -> Dict:
    """解析 find_package(<Name> [ver] [REQUIRED] [COMPONENTS ...]
    [OPTIONAL_COMPONENTS ...]) 参数。"""
    tokens = rest.replace("\\\n", " ").split()
    version = None
    required = False
    exact = False
    components: List[str] = []
    optional_components: List[str] = []
    mode = None
    for tok in tokens:
        up = tok.strip('"').upper()
        if up == "COMPONENTS":
            mode = "c"
            continue
        if up == "OPTIONAL_COMPONENTS":
            mode = "o"
            continue
        if up in _FP_KW:
            if up == "REQUIRED":
                required = True
            elif up == "EXACT":
                exact = True
            mode = None
            continue
        if version is None and re.fullmatch(r"\d+(\.\d+)*", tok):
            version = tok
            continue
        if "${" in tok or "$ENV" in tok:
            mode = None
            continue
        if mode == "c":
            components.append(tok)
        elif mode == "o":
            optional_components.append(tok)
    return {"name": name, "name_lower": name.lower(), "version": version,
            "required": required, "exact": exact,
            "components": components, "optional_components": optional_components,
            "file": rel, "line": line}


# 自定义依赖包装函数：function/macro(...pkg_check_modules(${pkg} ${arg_PACKAGE})...)
# 形式的间接声明，调用处 search_dependency(NAME PACKAGE <pkg名> ...) 提取
_FUNC_DEF_RE = re.compile(r"^\s*(?:function|macro)\s*\(\s*(\w+)", re.M)
_WRAP_PACKAGE_RE = re.compile(r"\bPACKAGE\s+\"?([A-Za-z0-9_.+-]+)\"?")
_WRAP_LIBRARY_RE = re.compile(r"\bLIBRARY\s+\"?([A-Za-z0-9_.+-]+)\"?")
_WRAP_MINVER_RE = re.compile(r"MINIMUM_VERSION\s+(?:\$\{(\w+)\}|\"?([\w.]+)\"?)")
_WRAP_FRAMEWORK_RE = re.compile(r"\bFRAMEWORK\s+\"?([A-Za-z0-9_]+)\"?")


def _detect_wrapper_deps(root: Path, cmake_files: List[str],
                         vart: Dict[str, str]) -> List[Dict]:
    """项目自定义包装函数（如 qTox 的 search_dependency）里的依赖声明。

    识别条件：函数名由项目 function()/macro() 定义，且调用参数中带
    PACKAGE <pkg-config 名> / LIBRARY <库名> / MINIMUM_VERSION <版本> /
    FRAMEWORK <macOS 框架> 关键字。返回包装出的依赖清单。
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
            continue  # 依赖引擎/内嵌三方目录内的调用不是应用依赖
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


# 依赖清单函数名（muse_deps 引擎等）：require_dep(name [STATIC|SYSTEM|REBUILD]) /
# require_source_dep(name)（源码自带）/ require_tool(name)（主机构建工具）。
# 要求函数在项目扫描到的 CMake 中有 function()/macro() 定义（避免同名普通
# 调用误匹配），首个参数为依赖名。
_MANIFEST_FN_RE = re.compile(
    r"(?i)^(?:require|add|use|need)[_-]?"
    r"(?:source[_-]?)?(?:dep|deps|dependency|dependencies|tool|package)s?$")
_MANIFEST_ARG_KW = {"STATIC", "SYSTEM", "REBUILD", "REQUIRED", "OPTIONAL",
                    "ON", "OFF"}


def _detect_manifest_deps(root: Path, cmake_files: List[str]) -> List[Dict]:
    """自定义依赖清单函数的调用（如 muse_deps 引擎的 require_dep）。

    返回 [{name, mode(link|source|tool), conditional, condition,
           evidence: [file:line]}]。函数定义可位于依赖引擎子模块
    （vendored 路径），但只扫描应用侧文件里的调用。
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
        # 轻量 if/endif 追踪：记录调用是否位于条件块内（不求值，仅标注）。
        # events: [(pos, cond)]，cond 为 if 条件文本，endif 为 None
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
                # 调用点之前重建 if 栈，取栈顶为所在条件
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
    """收集 set(<var> <字面量>) 定义的简单变量（版本号等），供
    find_package(${var}) 的版本解析做近似替换（忽略 CMake 作用域）。"""
    vart: Dict[str, str] = {}
    for rel in cmake_files:
        for m in re.finditer(r"^\s*set\s*\(\s*(\w+)\s+\"?([\w.]+)\"?\s*\)",
                             _read_text(root / rel), re.M):
            vart.setdefault(m.group(1), m.group(2))
    return vart


def _subst_vars(text: str, vart: Dict[str, str]) -> str:
    """把 ${var} 替换为 set() 表中的字面量值；未知变量原样保留。"""
    return re.sub(r"\$\{(\w+)\}",
                  lambda m: vart.get(m.group(1), m.group(0)), text)


def _detect_find_package_details(root: Path, info: Dict) -> List[Dict]:
    """提取全部 find_package 调用的完整参数（跨行），含 Qt/KF 调用。"""
    vart = _collect_cmake_vars(root, info["cmake_files"])
    out: List[Dict] = []
    for rel in info["cmake_files"]:
        if _is_vendored_path(rel):
            continue
        text = _strip_cmake_comments(_read_text(root / rel))
        for m in _FINDPKG_FULL_RE.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            out.append(_parse_findpkg_args(m.group(1),
                                           _subst_vars(m.group(2) or "", vart),
                                           rel, line))
    return out


def _detect_toolchain(root: Path, info: Dict) -> Dict:
    """主机构建工具链要求：cmake 最低版本 / C++ 标准 / 工具引用 / 测试设施。

    工具引用来源：find_program 参数 + execute_process/add_custom_command
    的 COMMAND 首 token（仅记已知工具名或命中特征后缀的工具，避免噪音）。
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
                # 第一个纯大写 token 是接收变量名，跳过
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
    """版本号 → 可比较元组（'1.2.3b' → (1,2,3)）。"""
    if not v:
        return ()
    parts = re.findall(r"\d+", str(v))
    return tuple(int(p) for p in parts)


def _detect_dynamic_loads(root: Path, info: Dict) -> List[Dict]:
    """源码中的运行时动态加载目标（仅字符串字面量，变量拼接无法静态确定）。"""
    targets: Dict[str, List[str]] = {}
    for src in info["sources"]:
        if src["ext"] not in TEXT_SCAN_EXTS:
            continue
        text = _read_text(root / src["path"])
        for rx, how in ((_DLOPEN_RE, "dlopen"), (_QLIBRARY_RE, "QLibrary"),
                        (_QPLUGINLOADER_RE, "QPluginLoader")):
            for m in rx.finditer(text):
                t = m.group(1).strip()
                if not t or "$" in t or "://" in t or t.startswith("/"):
                    continue
                targets.setdefault(t, []).append("%s (%s)" % (src["path"], how))
    return [{"name": t, "how": hows[:3]} for t, hows in sorted(targets.items())]


def _detect_qmake_libs(root: Path, info: Dict) -> List[Dict]:
    """qmake LIBS += -lfoo 的目标侧链接库。"""
    libs: Dict[str, List[str]] = {}
    for rel in info["pro_files"]:
        for m in _QMAKE_LIBS_RE.finditer(_read_text(root / rel)):
            for lm in _QMAKE_LINK_FLAG_RE.finditer(m.group(1)):
                libs.setdefault(lm.group(1), []).append(rel)
    return [{"name": n, "evidence": ev[:3]} for n, ev in sorted(libs.items())]


def _detect_gitmodules(root: Path) -> List[Dict]:
    """.gitmodules：vendored 依赖（submodule 锁定到具体提交）。"""
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
    """3rdparty/ 等自带源码目录（根目录与一级子目录范围内识别）。"""
    out = set()
    bases = [root] + [p for p in root.iterdir()
                      if p.is_dir() and not p.name.startswith(".")]
    for base in bases:
        for name in VENDORED_DIR_NAMES:
            d = base / name
            if not d.is_dir():
                continue
            # 至少含一个子目录或构建文件，才算 vendored 依赖集合
            if any(s.is_dir() for s in d.iterdir()) or (d / "CMakeLists.txt").is_file():
                out.add(d.relative_to(root).as_posix())
    return sorted(out)


# ------------------------------------------------ 依赖声明全形式检测（第二轮）


def _norm_lib_name(name: str) -> str:
    """裸链接名归一：去掉 .lib/.so/.a/.dylib 等文件后缀。"""
    return re.sub(r"\.(lib|so|a|dylib)(\.\d+)*$", "", name)


def _add_raw_lib(out: Dict[str, Dict], name: str, how: str, rel: str) -> None:
    n = _norm_lib_name(name).strip('"\'')
    if not n or not re.fullmatch(r"[A-Za-z0-9_.+-]+", n):
        return
    e = out.setdefault(n.lower(), {"name": n, "hows": [], "evidence": []})
    if how not in e["hows"]:
        e["hows"].append(how)
    if rel not in e["evidence"] and len(e["evidence"]) < 3:
        e["evidence"].append(rel)


def _detect_qmake_pkgconfig(root: Path, info: Dict) -> List[Dict]:
    """qmake: CONFIG += link_pkgconfig + PKGCONFIG += foo 的 pkg-config 依赖。"""
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
    """去掉 # 行注释（多行调用参数里的注释文字会污染裸名提取）。"""
    return _CMT_RE.sub(" ", text)


def _detect_cmake_raw_links(root: Path, cmake_files: List[str]):
    """CMake 中不经 find_package 声明的直接链接：

    - target_link_libraries 裸名（排除项目内 add_library/add_executable 目标、
      导入目标 Foo::Bar、${VAR}/生成器表达式、关键字与链接 flag）
    - -lfoo 链接 flag（含引号内的多 flag 串）
    - "-framework X"（macOS 框架）
    - find_library(VAR [NAMES] name...) 的库名候选
    返回 (raw_libs, macos_frameworks)。
    """
    raw: Dict[str, Dict] = {}
    frameworks: Dict[str, List[str]] = {}
    texts: Dict[str, str] = {}
    defined = set()
    for rel in cmake_files:
        if _is_vendored_path(rel):
            continue  # vendored 三方自己的链接声明不算应用依赖
        text = _strip_cmake_comments(_read_text(root / rel))
        texts[rel] = text
        for m in _ADD_TARGET_RE.finditer(text):
            defined.add(m.group(1).lower())
    for rel, text in texts.items():
        for m in _TARGET_LINK_RE.finditer(text):
            args = _strip_cmake_comments(m.group(1))
            args = args.replace("\\\n", " ").replace('"', " ")
            for fw in _FRAMEWORK_RE.finditer(args):
                frameworks.setdefault(fw.group(1), []).append(rel)
            # 框架段不参与裸名/链接 flag 提取
            args = _FRAMEWORK_RE.sub(" ", args)
            body = args.split(None, 1)
            if len(body) < 2:
                continue
            for lm in _LFLAG_RE.finditer(args):
                _add_raw_lib(raw, lm.group(1), "target_link_libraries -l", rel)
            for tok in body[1].split():
                t = tok.strip()
                if (not t or t.startswith("$") or "::" in t
                        or "/" in t or "\\" in t
                        or t.upper() in _TLL_KEYWORDS or t.startswith("-")):
                    continue
                _add_raw_lib(raw, t, "target_link_libraries", rel)
        for m in _FINDLIB_RE.finditer(text):
            toks = _strip_cmake_comments(m.group(1)).replace("\\\n", " ").split()
            # 首参数是接收结果的变量名，无条件跳过；NAMES 后是库名候选，
            # PATHS/HINTS/PATH_SUFFIXES/DOC 后是路径/描述（跳过）
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
                _add_raw_lib(raw, t, "find_library", rel)
    for name in defined:      # 项目内目标不算外部依赖
        raw.pop(name, None)
    fw_list = [{"name": k, "evidence": v[:3]} for k, v in sorted(frameworks.items())]
    return (sorted(raw.values(), key=lambda d: d["name"]),
            fw_list)


def _detect_fetched_deps(root: Path, cmake_files: List[str]) -> List[Dict]:
    """FetchContent_Declare / ExternalProject_Add / CPMAddPackage：
    configure 阶段拉取的源码依赖（GIT_REPOSITORY/URL + GIT_TAG/VERSION）。"""
    out: List[Dict] = []
    seen = set()
    for rel in cmake_files:
        if _is_vendored_path(rel):
            continue
        text = _strip_cmake_comments(_read_text(root / rel))
        for m in _FETCHED_DECLARE_RE.finditer(text):
            cmd, name, args = m.group(1), m.group(2), m.group(3)
            um = _FETCH_URL_RE.search(args)
            tm = _FETCH_TAG_RE.search(args)
            url = um.group(1).strip('",') if um else None
            if name in ("GITHUB_REPOSITORY", "GIT_REPOSITORY", "URL"):
                name = url.split("/")[-1] if url else name
            name = name.strip('",')
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append({"name": name, "how": _FETCHED_HOW[cmd], "url": url,
                        "tag": tm.group(1).strip('",') if tm else None,
                        "file": rel})
    return out


def _absorb_meson(root: Path, info: Dict, meson_files: List[str]) -> None:
    """meson.build：dependency('name', version:) / cc.find_library /
    meson_version / cpp_std / subproject() / qt5|qt6 modules。

    结果合并进 info（meson_deps / meson / raw_libs / qt_modules）。
    """
    meson_info: Dict = {"version_min": None, "cxx_standard": None,
                        "subprojects": []}
    deps: Dict[str, Dict] = {}
    for rel in meson_files:
        text = _read_text(root / rel)
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
            if sp.group(1) not in meson_info["subprojects"]:
                meson_info["subprojects"].append(sp.group(1))
        for m in _MESON_DEP_RE.finditer(text):
            name, args = m.group(1), m.group(2)
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
        for fl in _MESON_FINDLIB_RE.finditer(text):
            _merge_raw_lib(info["raw_libs"], fl.group(1),
                           "cc.find_library", rel)
    info["meson"] = meson_info
    info["meson_deps"] = sorted(deps.values(), key=lambda d: d["name"])


def _merge_raw_lib(raw_libs: List[Dict], name: str, how: str, rel: str) -> None:
    """把裸库名合并进 info["raw_libs"]（按小写名去重）。"""
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
    """configure.ac：PKG_CHECK_MODULES（含版本约束）/
    AC_CHECK_LIB / AC_SEARCH_LIBS（裸库名）。"""
    deps: Dict[str, Dict] = {}
    for rel in autotools_files:
        text = _read_text(root / rel)
        for m in _PKGCHK_MOD_RE.finditer(text):
            # 模块列表以逗号或空白分隔；单个 spec 可为 "name" 或
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
    """CI / 安装脚本文件：.github/、.ci/ 递归 + 顶层 *.sh。

    _walk 跳过 . 开头目录，这里显式收集。
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
    """CI / 安装脚本声明的环境依赖（apt/brew/pacman install 的包名清单）。

    这是构建机环境清单（混合构建工具与链接库），作为构建文件分析的
    交叉核对信源；发行版包名（libfoo-dev）需映射回库名使用。
    """
    out: Dict[str, Dict] = {}
    tok_re = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.@+-]*")
    skip = {"sudo", "update", "install", "install-recommends"}
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
