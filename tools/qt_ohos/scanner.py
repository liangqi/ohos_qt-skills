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
# 兼容 find_package(Qt6 ...) / find_package(Qt${QT_VERSION_MAJOR} COMPONENTS ...)
# 后者版本号是变量，取不到字面量但组件列表仍是可用的
_CMAKE_FINDPKG_QT_RE = re.compile(r"find_package\s*\(\s*Qt((?:\d|\$\{[^}]+\}))?([^)]*)\)", re.I)

# --- Qt 主版本识别（按证据强度排序，先命中者胜） ---
_QT_FINDPKG_LITERAL_RE = re.compile(r"find_package\s*\(\s*Qt([56])\b", re.I)
_QT_TARGET_RE = re.compile(r"\bQt([56])::[A-Za-z]")
_QT_NAMES_RE = re.compile(r"find_package\s*\(\s*QT\s+NAMES\s+Qt([56])", re.I)
# 只认赋值形态（set(QT_VERSION_MAJOR 6) / QT_VERSION_MAJOR=6）。
# `if (QT_VERSION_MAJOR LESS 6)` 这类条件分支只说明"还支持 Qt5"，不能当结论。
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
# Conan / vcpkg 清单
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
    # 保留 .cmake：Qt 的 find_package 常写在子模块的 *.cmake 里（如 cmake/external/qt/package.cmake）
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

    # 第三方包：CMake find_package/pkg_check_modules + Conan/vcpkg 清单
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
    """从构建文件文本判定 Qt 主版本。返回 (主版本字符串或 None, 证据说明)。

    证据强度：find_package(Qt6 字面量 > Qt6:: 目标 > NAMES Qt6 > QT_VERSION_MAJOR 赋值
    > Qt6-only CMake 命令。都判不出就返回 None —— 不猜。
    """
    joined = "\n".join(texts)
    checks = [
        (_QT_FINDPKG_LITERAL_RE, "find_package(Qt{})"),
        (_QT_TARGET_RE, "Qt{}:: 链接目标"),
        (_QT_NAMES_RE, "find_package(QT NAMES Qt{})"),
        (_QT_MAJOR_VAR_RE, "QT_VERSION_MAJOR={}"),
    ]
    for rx, label in checks:
        match = rx.search(joined)
        if match:
            value = match.group(1)
            return value, label.format(value)
    if _QT6_CMD_RE.search(joined):
        return "6", "Qt6-only CMake 命令"
    if _QT5_CMD_RE.search(joined):
        return "5", "Qt5-only CMake 命令"
    match = _QT_PRO_MAJOR_RE.search(joined)
    if match:
        major = match.group(1) or match.group(2)
        return major, "qmake QT_MAJOR_VERSION={}".format(major)
    return None, ""


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
    cmake_texts = []
    for rel in info["cmake_files"]:
        text = _read_text(root / rel)
        cmake_texts.append(text)
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
    if qt_version and not qt_version.isdigit():
        qt_version = None   # find_package(Qt${...}) 取不到字面量版本

    # 构建文件里没有字面量版本时，用证据推断（Qt6 工程曾被误判为 Qt5）
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
            "未能从构建文件判定 Qt 主版本（Qt5 与 Qt6 的模块矩阵、CMake 接线都不同）；"
            "递归拉取子模块，或用 `config set qt_version 5|6` 指定后再 scan")
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
    返回 {find_package: [names...], pkg_check_modules: [modules...]}。
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
                        ref = m.group(1)
                        parts = ref.split("/")
                        conan.append({"name": parts[0],
                                      "version": parts[1] if len(parts) > 1 else None})
    # conanfile.py requires 列表
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
    return {"conan": conan, "vcpkg": sorted(set(vcpkg))}
