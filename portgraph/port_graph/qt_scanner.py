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
EXCLUDE_DIR_PREFIXES = ("build",)
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
# 命中以下集合或匹配启发式后缀的 COMMAND/find_program token 记为构建工具。
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
        "toolchain": {},              # cmake 最低版本 / C++ 标准 / 构建工具引用
        "dynamic_loads": [],          # dlopen/QLibrary/QPluginLoader 字面量
        "qmake_libs": [],             # LIBS += -lfoo
        "git_submodules": [],         # .gitmodules 条目（自带依赖 + 锁定提交）
        "vendored_dirs": [],          # 3rdparty/ 等自带源码目录
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
    info["cmake_files"] = [c for c in cmake_files
                           if Path(c).name.lower() == "cmakelists.txt"]
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

    # 第三方包：CMake find_package/pkg_check_modules + Conan/vcpkg 清单
    info["cmake_packages"] = _detect_cmake_packages(root, info["cmake_files"])
    info["pkg_manifests"] = _detect_pkg_manifests(root)

    # 综合依赖分析增强（deps report 消费）
    info["find_package_details"] = _detect_find_package_details(root, info)
    info["toolchain"] = _detect_toolchain(root, info)
    info["dynamic_loads"] = _detect_dynamic_loads(root, info)
    info["qmake_libs"] = _detect_qmake_libs(root, info)
    info["git_submodules"] = _detect_gitmodules(root)
    info["vendored_dirs"] = _detect_vendored_dirs(root)

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
    for rel in info["cmake_files"]:
        text = _read_text(root / rel)
        for match in _CMAKE_FINDPKG_QT_RE.finditer(text):
            qt_version = qt_version or match.group(1)
            rest = match.group(2) or ""
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
        text = _read_text(root / src["path"])
        for name, (pattern, _libs) in THIRD_PARTY_HINTS.items():
            if name in found and len(found[name]) >= 3:
                continue
            if re.search(pattern, text):
                found.setdefault(name, []).append(src["path"])
    return [{"name": name, "evidence": files[:5]} for name, files in
            sorted(found.items())]


# CMake 构建模块/工具链，非运行时依赖，find_package 命中时跳过
_FINDPKG_SKIP = {"ecm", "pkgconfig", "threads", "sharedmimeinfo",
                 "doxygen", "gettext", "i18n", "imported_target",
                 "findpackagehandlestandardargs", "selectlibrary",
                 "pkg_check_modules"}  # noqa: keep explicit


def _detect_cmake_packages(root: Path, cmake_files: List[str]) -> Dict:
    """从 CMake 中提取第三方包：find_package(*) 和 pkg_check_modules。

    Qt/KF 已由 _detect_qt 专门处理，这里只返回其它包。
    返回 {find_package: [names...], pkg_check_modules: [modules...],
          pkg_modules: [{name, version_req}...]}（含版本约束）。
    """
    findpkgs = set()
    pkgmods = set()
    pkg_details: Dict[str, Dict] = {}
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
            # pkg-config spec 可带版本约束："glib-2.0 >= 2.50" / glib-2.0>=2.50
            specs = m.group(1).replace("\\\n", " ")
            _absorb_pkg_spec(specs, pkg_details)
            for tok in _PKGCONF_NAME_RE.findall(specs):
                tok = tok.lower()
                if (tok.upper() in _CMAKE_KW or tok in _FINDPKG_SKIP
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
    """token 是否为已知主机构建工具名（或命中启发式后缀）。"""
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


def _detect_find_package_details(root: Path, info: Dict) -> List[Dict]:
    """提取全部 find_package 调用的完整参数（跨行），含 Qt/KF 调用。"""
    out: List[Dict] = []
    for rel in info["cmake_files"]:
        text = _read_text(root / rel)
        for m in _FINDPKG_FULL_RE.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            out.append(_parse_findpkg_args(m.group(1), m.group(2) or "",
                                           rel, line))
    return out


def _detect_toolchain(root: Path, info: Dict) -> Dict:
    """主机构建工具链要求：cmake 最低版本 / C++ 标准 / 工具引用 / 测试设施。

    工具引用来源：find_program 参数 + execute_process/add_custom_command
    的 COMMAND 首 token（仅记已知工具名或命中启发式后缀，避免噪音）。
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
