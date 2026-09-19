"""Qt 工程扫描：复用 vendored 的 qt_scanner，新增平台接口检测与图节点生成。

产物：
- app:<name> 节点（普通属性）
- uses-module 边 -> qtmod:*（Qt 模块）
- runtime 边 -> 已入库包节点 / pkg-unknown:* 幽灵节点（第三方库）
- node_interfaces 记录（平台接口使用 + 证据）
"""

from __future__ import annotations

import re
import warnings
from bisect import bisect_right
from pathlib import Path
from typing import Dict, List, Optional

from . import db, kb_seed
from . import qt_scanner

# 平台接口检测规则: iface_id -> (正则)
# 注意：只检测实际的 API 调用/头文件包含，不检测平台宏引用（Q_OS_WIN/_WIN32 等）
# 因为平台宏引用本身就是条件编译守卫，由宏栈追踪处理
PLATFORM_API_RULES: List[Dict] = [
    {"iface": "iface:win32",
     "re": re.compile(r"#\s*include\s*<\s*(windows|shellapi|shlobj|winuser|"
                      r"wingdi|winbase|winsock2|commctrl|commdlg)\.h\s*>|"
                      r"\b(CreateWindow|SendMessage|PostMessage|GetMessage|"
                      r"LoadLibrary|GetProcAddress|CreateFile|ReadFile|WriteFile|"
                      r"VirtualAlloc|HeapAlloc|RegOpenKey|RegQueryValue|CoCreateInstance|"
                      r"IDispatch|IUnknown|HWND|HDC|HINSTANCE)\b")},
    {"iface": "iface:x11",
     "re": re.compile(r"#\s*include\s*<\s*(X11|xcb|Xlib)\b")},
    {"iface": "iface:wayland",
     "re": re.compile(r"#\s*include\s*<\s*wayland-client")},
    {"iface": "iface:dbus",
     "re": re.compile(r"#\s*include\s*<\s*dbus/|\bQDBusConnection\b|"
                       r"#\s*include\s*<\s*QtDBus")},
    {"iface": "iface:alsa",
     "re": re.compile(r"#\s*include\s*<\s*alsa/|\bsnd_")},
    {"iface": "iface:pulseaudio",
     "re": re.compile(r"#\s*include\s*<\s*pulse/|\bpa_simple|\bpa_mainloop")},
    {"iface": "iface:coreaudio",
     "re": re.compile(r"#\s*include\s*<\s*(CoreAudio|AudioToolbox|"
                      r"CoreAudioTypes|CoreMIDI)\b|\bAudioUnit\b|\bMIDIPortRef\b")},
    {"iface": "iface:cocoa",
     "re": re.compile(r"#\s*(include|import)\s*<\s*(Cocoa|AppKit|Foundation|IOKit)/"
                      r"|\bNS(Window|View|Application|Responder|Object)\b|"
                      r"@interface\b|@implementation\b|^\s*@\w+\b")},
    {"iface": "iface:systemd",
     "re": re.compile(r"#\s*include\s*<\s*systemd/|"
                      r"\b(sd_listen_fds|sd_notify|sd_notifyf|sd_watchdog|"
                      r"sd_booted|sd_journal_)\b")},
    {"iface": "iface:dylib",
     "re": re.compile(r"\bdlopen\s*\(|\bLoadLibrary[AW]?\s*\(|"
                      r"\bdlsym\s*\(|\bdlclose\s*\(")},
    {"iface": "iface:gpu-desktop-gl",
     "re": re.compile(r"#\s*include\s*<\s*GL/gl\.h|\bglBegin\s*\(|\bglClear\s*\(")
     },
    {"iface": "iface:fork-exec",
     "re": re.compile(r"\bfork\s*\(\s*\)")},
]

# 平台宏分类（用于宏栈追踪）
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
# 功能宏（由 CMake/qmake 注入）保守视为"可能在鸿蒙编译"
FEATURE_MACROS = {
    "HAVE_X11", "USE_DBUS", "USE_PULSEAUDIO", "USE_ALSA", "USE_COREAUDIO",
    "HAVE_DBUS", "HAVE_ALSA", "HAVE_PULSEAUDIO", "HAVE_SYSTEMD",
    "USE_OPENGL", "HAVE_OPENGL", "PLATFORM_LINUX", "PLATFORM_OHOS",
}

# 文件级平台隔离：路径中含这些关键词的文件，整个文件是该平台专属的，
# CMake 层面不会在鸿蒙编译 → 文件内接口视为 platform-file-excluded
# （注意：linux 路径不在此列，因为鸿蒙会编译 Linux 通用代码）
NON_OHOS_PLATFORM_PATH_HINTS = (
    ("macos", ("platform/macos", "platform/osx", "platform/apple",
               "platform/darwin", "/macos/", "/osx/", "/apple/",
               "/mac/", "/darwin/")),
    ("windows", ("platform/windows", "platform/win", "/windows/", "/win32/",
                 "/winrt/", "/win/")),
    ("android", ("platform/android", "/android/")),
    ("ios", ("platform/ios", "/ios/")),
)


def _file_platform_excluded(file_rel: str) -> Optional[str]:
    """根据文件路径判断是否为非鸿蒙平台专属文件。"""
    rel = file_rel.lower().replace("\\", "/")
    for plat, hints in NON_OHOS_PLATFORM_PATH_HINTS:
        for hint in hints:
            if hint in rel:
                return plat
    return None

_IFDEF_RE = re.compile(r"#\s*ifdef\s+(\w+)")
_IFNDEF_RE = re.compile(r"#\s*ifndef\s+(\w+)")
_IF_DEFINED_RE = re.compile(r"#\s*if\s+(.+)$")
_DEFINED_RE = re.compile(r"defined\s*\(\s*(\w+)\s*\)|defined\s+(\w+)")
_ELSE_RE = re.compile(r"#\s*else\b")
_ELIF_RE = re.compile(r"#\s*elif\s+(.+)$")
_ENDIF_RE = re.compile(r"#\s*endif\b")


def _extract_defined_macros(expr: str) -> List[str]:
    """从 #if 表达式中提取 defined(X) 宏名。"""
    return [m[0] or m[1] for m in _DEFINED_RE.findall(expr)]


def _macro_compiles_on_ohos(macro: str) -> bool:
    """单个宏在鸿蒙构建时是否为真（保守估计）。

    - 鸿蒙/通用宏 → True（确定为真或保守视为真）
    - 非鸿蒙平台宏 → False（确定为假）
    - 未知宏 → True（保守，可能由构建系统注入）
    """
    if macro in NON_OHOS_PLATFORM_MACROS:
        return False
    return True  # ohos/general/feature/unknown 都保守视为真


def _expr_compiles_on_ohos(expr: str) -> Optional[bool]:
    """对 #if/#elif 表达式做粗略求值，判断在鸿蒙是否为真。

    仅处理 defined(X) 与 && / || / ! 的组合；无法解析时返回 None（保守视为真）。
    """
    # 提取所有 defined(X) → 布尔值
    def repl(m):
        name = m.group(1) or m.group(2)
        return "1" if _macro_compiles_on_ohos(name) else "0"
    simplified = _DEFINED_RE.sub(repl, expr)
    # 也处理裸宏名（如 #if Q_OS_WIN）——保守视为宏名即条件
    for tok in re.findall(r"\b[A-Z_]\w*\b", simplified):
        if tok in ("1", "0", "defined", "true", "false"):
            continue
        simplified = simplified.replace(tok,
            "1" if _macro_compiles_on_ohos(tok) else "0")
    try:
        # 用 Python 求值（&& → and, || → or, ! → not）
        py = simplified.replace("&&", " and ").replace("||", " or ")
        py = re.sub(r"!(?=[01(])", " not ", py)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return bool(eval(py, {"__builtins__": {}}, {}))
    except Exception:
        return None


def _guard_status(active_macros: List[str]) -> str:
    """根据活动宏判断接口命中行的编译守卫状态（遗留兼容接口）。

    注意：#if 表达式可能是 AND/OR 混合，无法精确求值。
    新代码应使用帧级 compiles_on_ohos 追踪，此函数仅保留用于简单场景。
    """
    if not active_macros:
        return "unconditional"
    if all(m in NON_OHOS_PLATFORM_MACROS for m in active_macros):
        return "platform-excluded"
    return "ohos-active"


def _macro_stack_status(text: str) -> Dict[int, str]:
    """逐行宏栈追踪，返回 {line_no: guard_status}。

    每个栈帧记录 (compiles_on_ohos: Optional[bool])。
    行的编译状态 = 所有帧 compiles_on_ohos 的 AND：
      - 任意帧为 False → platform-excluded（确定不编译）
      - 所有帧为 True → ohos-active（确定编译）
      - 含 None（无法判断）→ ohos-active（保守）
      - 无帧 → unconditional
    """
    result: Dict[int, str] = {}
    # 栈元素: compiles_on_ohos (True/False/None)
    stack: List[Optional[bool]] = []

    def current_guard() -> str:
        if not stack:
            return "unconditional"
        if any(f is False for f in stack):
            return "platform-excluded"
        return "ohos-active"

    for lineno, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        m = _IFDEF_RE.match(s)
        if m:
            stack.append(_macro_compiles_on_ohos(m.group(1)))
            result[lineno] = current_guard()
            continue
        m = _IFNDEF_RE.match(s)
        if m:
            # ifndef MACRO: 在鸿蒙编译当且仅当 MACRO 在鸿蒙为假
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

_PROJECT_VER_RE = re.compile(
    r"project\s*\([^)]*VERSION\s+([0-9.]+)", re.I | re.S)


def normalize_app_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _detect_platform_interfaces(root: Path, scan_info: Dict) -> List[Dict]:
    """扫描源码，返回 [{iface, hits: [{file, line, guard}], guard_distribution}]。

    guard 取值:
      - unconditional:       无守卫，鸿蒙会编译
      - ohos-active:         含鸿蒙/通用守卫，鸿蒙会编译
      - platform-excluded:   被非鸿蒙平台宏守卫包裹，鸿蒙不编译
      - platform-file-excluded: 所在文件本身是非鸿蒙平台专属文件，CMake 不编译

    接口的整体 guard = 最"危险"的命中点：
      - 只要有一个 unconditional/ohos-active 命中 → 整体 ohos-active
      - 否则全部命中都是 platform-excluded/platform-file-excluded → platform-excluded
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
        file_plat = _file_platform_excluded(src["path"])
        guard_by_line = _macro_stack_status(text)
        lines = text.splitlines()
        # 预计算换行偏移，用二分查找定位行号（O(n log n) 替代 O(n*m)）
        nl_offsets = [i for i, ch in enumerate(text) if ch == "\n"]
        for rule in PLATFORM_API_RULES:
            for m in rule["re"].finditer(text):
                # 行号 = 前面换行符数量 + 1
                line_no = bisect_right(nl_offsets, m.start()) + 1
                # 文件级平台隔离优先于行级守卫
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
    """扫描出的模块名 -> qtmod 节点（支持 webenginewidgets->webengine 前缀匹配）。

    _cache 用于在同一次扫描中复用已加载的 Qt 模块列表，避免重复全表扫描。
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
    """把 KDE Frameworks 组件建成 framework 子项目节点并连边，供引擎递归分析。

    app -> kf:组件（runtime）；kf:组件 -> qtmod:*（uses-module）/
    kf:子组件（runtime）；kf:组件 的平台接口写入 node_interfaces。
    用 BFS 展开组件间的子框架依赖，避免整体判 blocked。
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
            description="KDE Frameworks 组件（子项目，递归分析）",
            port_evidence="按其 Qt 模块/平台接口/子框架依赖递归判定")
        deps = kb_seed.KF_DEPS.get(comp, {"qt": ["core"], "kf": [], "ifaces": []})
        for q in deps.get("qt", []):
            if db.get_node(conn, "qtmod:%s" % q):
                db.upsert_edge(conn, kf_id, "qtmod:%s" % q, "uses-module")
        for ifc in deps.get("ifaces", []):
            db.add_node_interface(conn, kf_id, ifc)
        for k2 in deps.get("kf", []):
            queue.append((kf_id, k2))


def _fold_dep_name(n: str) -> str:
    """依赖名折叠：小写、去非字母数字（分隔符/大小写差异归一）。"""
    return re.sub(r"[^a-z0-9]+", "", (n or "").lower())


def _submodule_folds(git_submodules: List[Dict]) -> set:
    """git 子模块名折叠集合（name/path 末段/url 末段）：用于识别 vendored 依赖。"""
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


def _link_third_party(conn, app_id: str, info: Dict) -> Dict:
    """把 CMake find_package/pkg_check_modules + Conan/vcpkg 清单发现的第三方包
    连边到已知包节点；未匹配的记为 unknown 包节点。

    另含两轮增强（e2e tdesktop tier C 复核驱动）：
    - find_package 命中的构建工具/解释器（python3 等）不建运行时边——
      那是构建期依赖，deps_report 侧归 build-tool 分类
    - target_link_libraries 的 ns::external_<name> 导入目标名（剥前缀后
      在 raw_libs 里，ext_target=True）：能解析则连边，不能解析且非
      vendored 子模块则建幽灵节点（高置信声明，如 tdesktop 的全部三方库）
    返回 {linked: [...], unknown: [...]}。
    """
    cp = info.get("cmake_packages", {})
    # find_package 构建工具（python3/cmake/...）不是应用运行时依赖
    names: List[str] = [n for n in cp.get("find_package", [])
                        if n not in qt_scanner.BUILD_TOOL_FINDPKG]
    names.extend(cp.get("pkg_check_modules", []))
    pm = info.get("pkg_manifests", {})
    for c in pm.get("conan", []):
        names.append(c["name"])
    for v in pm.get("vcpkg", []):        # vcpkg 条目可为 str 或 {name, version}
        names.append(v["name"] if isinstance(v, dict) else v)
    # 合并源码 #include 发现的第三方库（去重保序）
    for h in info.get("third_party_hints", []):
        if h["name"] not in names:
            names.append(h["name"])

    seen = set()
    linked, unknown = [], []

    def _resolve_one(name: str):
        node = kb_seed.resolve_package(conn, name)
        alias_used = None
        if node is None:
            # 直接名未解析时按别名表重试（libavcodec → ffmpeg 等），
            # 避免同库异名产生 pkg-unknown 幽灵节点（fetch-deps 会误报
            # need_port，而别名指向的 bottle 实际存在）
            aliases = kb_seed.PKG_ALIASES.get(name.lower())
            if isinstance(aliases, str):
                aliases = [aliases]
            for alias in aliases or []:
                node = kb_seed.resolve_package(conn, alias.lower())
                if node:
                    alias_used = alias
                    break
        return node, alias_used

    def _link(name: str, node, alias_used=None, via=None):
        db.upsert_edge(conn, app_id, node["id"], "runtime")
        item = {"hint": name, "node": node["id"],
                "status": node["port_status"]}
        if alias_used:
            item["alias"] = alias_used
        if via:
            item["via"] = via
        linked.append(item)

    def _ghost(name: str):
        ghost_id = "pkg-unknown:%s" % normalize_app_name(name)
        db.upsert_node(
            conn, ghost_id, "package", name, "scan", "unknown",
            description="扫描发现的第三方库，未匹配到已知包源",
            port_evidence="不在 Harmonybrew/cmd-pkgs 已知清单")
        db.upsert_edge(conn, app_id, ghost_id, "runtime")
        unknown.append({"hint": name, "node": ghost_id})

    for name in names:
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        node, alias_used = _resolve_one(name)
        if node:
            _link(name, node, alias_used)
        else:
            _ghost(name)

    # ---- 裸链接名（含 ns::external_<name> 导入目标，剥前缀后标记
    #      ext_target）：能解析则连边；external-target 高置信声明
    #      在未解析且非 vendored 子模块时建幽灵节点
    submodule_folds = _submodule_folds(info.get("git_submodules", []))
    for rl in info.get("raw_libs", []):
        name = rl["name"]
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        # Windows 系统库（通常位于 win32 平台块）：跳过，防止同名 Unix
        # 库误连边（bcrypt → OpenBSD bcrypt）
        if name.lower() in qt_scanner.WIN32_SYSTEM_LIBS:
            continue
        node, alias_used = _resolve_one(name)
        if node:
            _link(name, node, alias_used,
                  via="external-target" if rl.get("ext_target") else None)
        elif rl.get("ext_target"):
            # vendored 子模块（.gitmodules 声明，随项目编译）不建幽灵：
            # 依赖由项目源码自足，不是需获取/移植的外部包
            if _fold_dep_name(name) in submodule_folds:
                continue
            if len(name) >= 3:
                _ghost(name)
    return {"linked": linked, "unknown": unknown}


def scan_project(conn, project_root, info: Dict = None) -> Dict:
    """扫描 Qt 工程并写入图。返回摘要。

    info: 可传入 qt_scanner.scan_project 的结果复用（避免大仓库重复扫描）。
    """
    root = Path(project_root).resolve()
    info = info or qt_scanner.scan_project(root)
    db.init_db(conn)

    app_id = "app:%s" % normalize_app_name(info["name"])
    version = _detect_version(root)
    # 记录项目根路径：deps / fetch-deps 等命令按应用名回溯源码位置
    db.set_meta(conn, "root_%s" % app_id, str(root))
    db.upsert_node(
        conn, app_id, "app", info["name"], "scan", "unknown",
        version=version,
        description="Qt %s 应用，构建系统 %s，%d 个源文件" % (
            info.get("qt_version_hint") or "?", info["build_system"],
            len(info["sources"])),
        port_evidence="已扫描，待可移植性分析")

    # 清理旧的出边与接口记录（重扫幂等）
    conn.execute("DELETE FROM edges WHERE src=?", (app_id,))
    conn.execute("DELETE FROM node_interfaces WHERE node_id=?", (app_id,))

    # Qt 模块边
    modules_linked, modules_missing = [], []
    resolve_cache: Dict = {}
    for mod in info["qt_modules"]:
        node = _resolve_qtmod(conn, mod, _cache=resolve_cache)
        if node:
            db.upsert_edge(conn, app_id, node["id"], "uses-module")
            modules_linked.append({"module": mod, "node": node["id"],
                                   "status": node["port_status"]})
        else:
            modules_missing.append(mod)

    # 第三方库依赖边（find_package/pkg_check_modules/Conan/vcpkg/include）
    tp = _link_third_party(conn, app_id, info)
    deps_linked, deps_unknown = tp["linked"], tp["unknown"]

    # KDE Frameworks 组件 → 作为子项目节点递归分析（不再整体判 blocked）
    _link_kf_components(conn, app_id, info.get("kf_components", []))

    # 平台接口使用
    ifaces = _detect_platform_interfaces(root, info)
    for h in ifaces:
        gc = h["guard_counts"]
        guard_label = {
            "unconditional": "无条件编译",
            "ohos-active": "含鸿蒙/通用守卫（会编译）",
            "platform-excluded": "被非鸿蒙平台守卫包裹（不编译）",
        }[h["guard"]]
        hit_desc = "; ".join(
            "%s:%d[%s] %s" % (hit["file"], hit["line"], hit["guard"],
                               hit["snippet"])
            for hit in h["hits"][:3])
        excluded_total = (gc.get("platform-excluded", 0)
                          + gc.get("platform-file-excluded", 0))
        evidence = (
            "[%s] guard=%s "
            "(%d 处无条件 / %d 处鸿蒙可编译 / %d 处宏守卫排除 / %d 处文件级排除)"
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
        "modules_linked": modules_linked, "modules_missing": modules_missing,
        "deps_linked": deps_linked, "deps_unknown": deps_unknown,
        "interfaces": ifaces,
    }
