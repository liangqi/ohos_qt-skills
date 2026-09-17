"""综合依赖分析（deps report）：一个 Qt 工程的依赖全景画像。

按角色回答"这个项目到底依赖什么"：

  link       项目期望获取到编译产物的依赖（目标侧 headers + .so/.a，
             编译/链接应用时必须存在；缺失则交叉编译失败）
  build-tool 编译器/构建工具依赖（构建机运行：cmake 版本、C++ 标准、
             代码生成器 protoc/flex/bison…；不部署到设备）
  runtime    运行时依赖（设备侧 .so：link 依赖的传递闭包 +
             dlopen/QLibrary 动态加载；不参与编译但缺了跑不起来）
  test       测试专用依赖（不进发行包）
  vendored   项目内自带源码（.gitmodules / 3rdparty 目录，随项目编译）

每个依赖附：
  - 版本范围（find_package 最低版本 / pkg-config 约束 / conan 范围）
  - 需求级别（REQUIRED / optional）
  - 鸿蒙产物可得性（hb bottle / cmd-pkgs / Qt SDK 提供 / 系统自带 /
    需源码移植）与版本满足性检查

用法：

    python portgraph.py deps <项目路径|已扫描应用名> [--json]

与既有命令的关系：analyze 回答"能不能移植"；fetch-deps 回答"产物怎么拿"；
deps 回答"依赖全景是什么、各自扮演什么角色、版本要求是否满足"。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

from . import db, engine, kb_seed, project_scanner, qt_scanner

# OHOS 系统自带库（NDK sysroot / 系统镜像）：链接无需自带产物
# （KB: semantic/qt-harmonyos-third-party-libs §系统库直链）
OHOS_SYSTEM_LIBS = {
    "zlib": "OHOS 系统/NDK 自带 libz，可直接 -lz；用 bottle 亦可",
    "z": "OHOS 系统/NDK 自带 libz",
    "openssl": "OHOS 系统自带 libssl/libcrypto（Qt 编译需额外配置头文件路径）",
    "ssl": "OHOS 系统自带 libssl",
    "crypto": "OHOS 系统自带 libcrypto",
    "icu": "OHOS 系统自带 ICU（Qt 时区/文本后端依赖）",
    "pthread": "musl libc 内置 pthread",
    "dl": "musl libc 内置 dlopen",
    "m": "musl libc 数学库",
    "rt": "musl libc",
    "stdc++": "OHOS NDK libc++",
    "c++": "OHOS NDK libc++",
    "c++_shared": "OHOS NDK libc++_shared（随 SDK 提供）",
    "log": "OHOS NDK hilog（libhilog_ndk.z.so）",
    "EGL": "OHOS 系统 EGL（libEGL_ndk.z.so）",
    "GLESv3": "OHOS 系统 OpenGL ES（libGLESv3_ndk.z.so）",
    "GLESv2": "OHOS 系统 OpenGL ES",
}

# Windows 系统库（qmake win32 块 / MSVC 链接）：鸿蒙不适用（代码通常被
# 平台守卫包裹），标注而非当作"需源码编译"的缺口
WIN32_SYSTEM_LIBS = {
    "user32", "kernel32", "gdi32", "shell32", "ole32", "oleaut32", "uuid",
    "advapi32", "ws2_32", "mswsock", "winmm", "dsound", "ddraw", "dxgi",
    "d3d9", "d3d11", "dwmapi", "shlwapi", "comctl32", "comdlg32",
    "imm32", "wininet", "winhttp", "crypt32", "secur32", "netapi32",
    "psapi", "version", "iphlpapi", "powrprof", "setupapi", "strmiids",
    "avifil32", "mfplat", "mfuuid", "strmbase", "strmbasd", "wtsapi32",
    "windowsapp", "delayimp", "opengl32", "glu32", "wintrust", "shcore",
}

# -l 链接名 → 常见包名对齐（hb 包名口径）
LIB_NAME_ALIASES = {
    "swscale": "ffmpeg", "avcodec": "ffmpeg", "avformat": "ffmpeg",
    "avutil": "ffmpeg", "swresample": "ffmpeg", "postproc": "ffmpeg",
    "ssl": "openssl", "crypto": "openssl",
    "sqlite3": "sqlite", "curl": "curl", "gcrypt": "libgcrypt",
    "tag": "taglib", "mtp": "libmtp", "usb-1.0": "libusb",
    "magic": "libmagic", "exif": "libexif", "discid": "libdiscid",
    "chromaprint": "chromaprint", "mp3lame": "lame",
}

# CMake 内置模块：非第三方包，按语义归类（kind + 说明）
CMAKE_BUILTIN_PACKAGES = {
    "threads": {"kind": "system-lib",
                "note": "CMake 内置 Threads 模块：pthread（musl libc 内置）"},
    "openmp": {"kind": "build-tool",
               "note": "编译器特性：OHOS NDK clang 支持 -fopenmp（libomp 随 SDK）"},
    "iconv": {"kind": "system-lib", "note": "musl libc 内置 iconv"},
    "dl": {"kind": "system-lib", "note": "musl libc 内置 dlopen"},
}

# 平台接口绑定包：find_package/链接命中说明应用直连该平台栈，
# 鸿蒙不可用（是否真的编译由 analyze 的宏守卫/CMake 条件证据判定）
INTERFACE_BOUND_PACKAGES = {
    "x11": "X11 显示接口：鸿蒙不支持直连；确认所在代码是否可通过构建选项"
           "/条件编译裁剪，hb 的 libx11 bottle 仅用于依赖链传递场景",
    "xext": "X11 扩展：鸿蒙不支持直连",
    "xcb": "XCB：鸿蒙不支持直连",
    "alsa": "ALSA 音频：鸿蒙不可用，需改鸿蒙 AudioRenderer",
    "pulseaudio": "PulseAudio：鸿蒙无此服务",
    "dbus": "D-Bus IPC：鸿蒙无 D-Bus（Qt D-Bus 模块 Out of scope）",
    "cocoa": "macOS Cocoa：鸿蒙不适用",
    "appkit": "macOS AppKit：鸿蒙不适用",
    "coreaudio": "macOS CoreAudio：鸿蒙不可用",
    "wayland": "Wayland 直连：鸿蒙窗口模型非 Wayland 协议",
    "systemd": "systemd：鸿蒙无 systemd",
}

# find_package 命中的主机侧构建工具（原 _FINDPKG_SKIP 静默丢弃，现归入
# build-tool 分类，不再丢失信息）
BUILD_TOOL_FINDPKG = {
    "ecm": "extra-cmake-modules（KDE CMake 模块，主机侧）",
    "pkgconfig": "pkg-config（主机侧）",
    "pkgconf": "pkgconf（主机侧 pkg-config 兼容）",
    "gettext": "gettext 工具链（msgfmt/xgettext，主机侧）",
    "intltool": "intltool（主机侧）",
    "doxygen": "Doxygen 文档生成器（主机侧）",
    "sharedmimeinfo": "update-mime-database（主机侧）",
    "cmake": "CMake",
    "ninja": "Ninja 构建器",
    "python3": "Python 3",
    "python": "Python",
    "flex": "flex 词法生成器",
    "bison": "bison 语法生成器",
    "gperf": "gperf 完美哈希生成器",
    "git": "git",
    "ccache": "ccache 编译缓存",
    "sccache": "sccache 编译缓存",
    "linguisttools": "Qt Linguist 工具（lupdate/lrelease，随 Qt SDK）",
    "lxqt2-build-tools": "LXQt CMake 构建模块（主机侧，类似 ECM）",
    "lxqt-build-tools": "LXQt CMake 构建模块（主机侧，类似 ECM）",
}

# 测试框架（find_package/QT 模块名命中 → test 分类）
TEST_FRAMEWORKS = {
    "gtest", "googletest", "catch2", "catch", "doctest", "qtest", "qttest",
    "testlib", "cppunit", "boosttest", "unittest++", "gtest_main", "qttest",
}

# Qt 自带的构建工具（由 Qt SDK 提供，无需单独准备）
QT_TOOL_NAMES = {"moc", "uic", "rcc", "lupdate", "lrelease", "lconvert",
                 "qmake", "qtpaths", "lrelease-pro", "lupdate-pro"}

# Qt for HarmonyOS 可用版本（KB 校验基准：5.12.12 / 5.15.16 / 6.12 预构建）
QT_OHOS_AVAILABLE = {"5": ("5.12", "5.15"), "6": ("6.12",)}

RECURSE_TYPES = ("runtime",)
SKIP_PLATFORM_CONDS = ("macos",)
PROVIDED_KINDS = ("qt-module", "platform-api")


# ---------------------------------------------------------------- 版本比较

def _ver_key(v) -> tuple:
    if not v:
        return ()
    parts = re.findall(r"\d+", str(v))
    return tuple(int(p) for p in parts)


def _check_min(min_ver: Optional[str], available: Optional[str]) -> str:
    """find_package 最低版本 vs 可用版本。"""
    if min_ver is None:
        return "any" if available else "unknown"
    if not available:
        return "unknown"
    return ("satisfied" if _ver_key(available) >= _ver_key(min_ver)
            else "conflict")


def _check_req(version_req: Optional[str], available: Optional[str]) -> str:
    """pkg-config/conan 带操作符约束（">= 2.50"）vs 可用版本。"""
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


# ---------------------------------------------------------------- 产物解析

def _resolve(conn, name: str) -> Optional[Dict]:
    """包名（find_package/pkg-config/include 线索）→ 已入库包节点。

    近似对齐依次尝试：原名 / 补 lib 前缀（xkbcommon→libxkbcommon）/
    去 lib 前缀 / 去 pkg-config 版本后缀（glib-2.0→glib）及其组合。
    """
    if conn is None:
        return None
    name = name.lower()
    stripped = re.sub(r"-\d+(\.\d+)*$", "", name)
    cands = [name]
    if not name.startswith("lib"):
        cands.append("lib" + name)
    if name.startswith("lib"):
        cands.append(name[3:])
    if stripped != name:
        cands.append(stripped)
        if not stripped.startswith("lib"):
            cands.append("lib" + stripped)
    for cand in cands:
        node = kb_seed.resolve_package(conn, cand)
        if node:
            return node
    return None


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


def _runtime_closure(conn, node_id: str) -> List[Dict]:
    """一个包节点的传递 runtime 依赖（BFS；跳过 provided 与 macos 条件）。

    与 deps_fetch.dependency_closure 口径一致：bottle 不捆绑依赖，
    目标侧链接/运行仍需其依赖的 .so。
    """
    out: List[Dict] = []
    visited = {node_id}
    queue = [node_id]
    while queue:
        nid = queue.pop(0)
        if nid != node_id:
            node = db.get_node(conn, nid)
            if node:
                out.append(node)
        for e in db.out_edges(conn, nid, RECURSE_TYPES):
            if e.get("platform_cond") in SKIP_PLATFORM_CONDS:
                continue
            if e["dst"] not in visited:
                visited.add(e["dst"])
                nd = db.get_node(conn, e["dst"])
                if nd is None or nd["kind"] in PROVIDED_KINDS:
                    continue
                queue.append(e["dst"])
    return out


def _version_check(entry: Dict) -> str:
    """多源约束（conan 范围 / pkg 约束 / find_package 最低版本）满足性：
    同时存在时取最差结果（任一冲突即冲突）。"""
    avail = entry.get("available_version")
    checks = []
    if entry.get("version_range"):
        checks.append(_check_req(_range_to_req(entry["version_range"]), avail))
    if entry.get("version_req"):
        checks.append(_check_req(entry["version_req"], avail))
    if entry.get("min_version"):
        checks.append(_check_min(entry["min_version"], avail))
    if "conflict" in checks:
        return "conflict"
    if "satisfied" in checks:
        return "satisfied"
    if checks:
        return checks[0]
    return "any" if avail else "unknown"


# ---------------------------------------------------------------- 主分析

class _DepBook:
    """同名依赖的多源证据合并（find_package/pkg/conan/include/qmake）。"""

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
            # REQUIRED 优先于 optional；版本信息取最先出现的明确值
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


def analyze_dependencies(conn, root, info: Dict = None) -> Dict:
    """生成综合依赖分析报告。conn 可为 None（纯扫描，无产物解析）。"""
    root = Path(root).resolve()
    info = info or qt_scanner.scan_project(root)
    version = project_scanner._detect_version(root)

    fp_details = info.get("find_package_details", [])
    pkg_manifests = info.get("pkg_manifests", {})
    cmake_packages = info.get("cmake_packages", {})

    # ---- Qt 版本要求（find_package(Qt5 5.15 ...) / .pro 启发）
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

    # ---- 分类桶
    link = _DepBook()
    test_deps: List[Dict] = []
    build_tools: List[Dict] = []
    warnings: List[Dict] = []

    # ---- 1) find_package 明细
    for fp in fp_details:
        name = fp["name_lower"]
        ev = "find_package(%s%s%s) %s:%d" % (
            fp["name"], " %s" % fp["version"] if fp["version"] else "",
            " REQUIRED" if fp["required"] else "", fp["file"], fp["line"])
        if name.startswith("qt") or name.startswith("kf"):
            continue  # Qt 模块/KF 组件单独处理
        if name in TEST_FRAMEWORKS:
            test_deps.append({"name": fp["name"], "source": ev,
                              "note": "测试框架，不进发行包"})
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
            e = link.add(fp["name"], kind="platform-iface",
                         required=fp["required"], evidence=ev)
            e["ohos_note"] = INTERFACE_BOUND_PACKAGES[name]
            continue
        entry = link.add(fp["name"], required=fp["required"],
                         min_version=fp["version"],
                         components=(fp["components"]
                                     + fp["optional_components"]) or None,
                         evidence=ev)
        if fp["exact"]:
            entry["version_req"] = "== %s" % fp["version"]

    # ---- 2) pkg_check_modules（含版本约束）
    for pm in cmake_packages.get("pkg_modules", []):
        ev = "pkg_check_modules(%s%s)" % (
            pm["name"], " %s" % pm["version_req"] if pm["version_req"] else "")
        if pm["name"] in TEST_FRAMEWORKS:
            test_deps.append({"name": pm["name"], "source": ev,
                              "note": "测试框架，不进发行包"})
            continue
        if pm["name"] in INTERFACE_BOUND_PACKAGES:
            e = link.add(pm["name"], kind="platform-iface", evidence=ev)
            e["ohos_note"] = INTERFACE_BOUND_PACKAGES[pm["name"]]
            continue
        link.add(pm["name"], version_req=pm["version_req"], evidence=ev)

    # ---- 3) Conan / vcpkg 清单（版本可为范围串）
    for c in pkg_manifests.get("conan", []):
        link.add(c["name"], version_range=c.get("version"),
                 evidence="conan: %s/%s" % (c["name"], c.get("version") or "*"))
    for v in pkg_manifests.get("vcpkg", []):
        link.add(v["name"], min_version=v.get("version"),
                 evidence="vcpkg.json: %s" % v["name"]
                 + (" (>= %s)" % v["version"] if v.get("version") else ""))

    # ---- 4) include 启发（源码直接 #include 三方头）
    for h in info.get("third_party_hints", []):
        link.add(h["name"], required=False,
                 evidence="include: %s" % h["evidence"][0]
                 if h.get("evidence") else "include")

    # ---- 5) qmake LIBS += -lfoo
    for ql in info.get("qmake_libs", []):
        n = ql["name"]
        if n in OHOS_SYSTEM_LIBS:
            ev = "qmake LIBS -l%s（%s）" % (n, OHOS_SYSTEM_LIBS[n])
            e = link.add(n, kind="system-lib", evidence=ev)
            e["ohos_note"] = OHOS_SYSTEM_LIBS[n]
        elif n in WIN32_SYSTEM_LIBS:
            e = link.add(n, kind="win32-system-lib", required=False,
                         evidence="qmake LIBS -l%s" % n)
            e["ohos_note"] = "Windows 系统库：通常位于 win32 平台块，鸿蒙不适用"
        else:
            aliased = LIB_NAME_ALIASES.get(n.lower())
            e = link.add(aliased or n,
                         evidence="qmake LIBS -l%s (%s)" % (
                             n, ql["evidence"][0] if ql.get("evidence") else "?"))
            if aliased:
                e.setdefault("ohos_note", "链接名 %s 归并为包 %s" % (n, aliased))

    # ---- 6) KDE Frameworks 组件（link，framework 类）
    for comp in info.get("kf_components", []):
        deps = kb_seed.KF_DEPS.get(comp)
        note = None
        if deps:
            note = "依赖 Qt 模块: %s" % ", ".join(deps.get("qt", []))
            if deps.get("ifaces"):
                note += "；绑定平台接口: %s" % ", ".join(deps["ifaces"])
        e = link.add(comp, kind="framework", evidence="find_package(KF* %s)" % comp)
        if note:
            e["ohos_note"] = "KDE Frameworks 组件，需源码交叉编译；" + note

    # ---- 6b) 裸链接名（target_link_libraries / find_library /
    #          cc.find_library / AC_CHECK_LIB）：不经 find_package 的直接链接
    for rl in info.get("raw_libs", []):
        n = rl["name"]
        ev = "%s (%s)" % ("+".join(rl.get("hows", [])),
                          rl["evidence"][0] if rl.get("evidence") else "?")
        if n.lower() in OHOS_SYSTEM_LIBS:
            e = link.add(n, kind="system-lib", evidence=ev)
            e["ohos_note"] = OHOS_SYSTEM_LIBS[n.lower()]
        elif n.lower() in WIN32_SYSTEM_LIBS:
            e = link.add(n, kind="win32-system-lib", required=False, evidence=ev)
            e["ohos_note"] = "Windows 系统库：通常位于 win32 平台块，鸿蒙不适用"
        elif n.lower() in INTERFACE_BOUND_PACKAGES:
            e = link.add(n, kind="platform-iface", evidence=ev)
            e["ohos_note"] = INTERFACE_BOUND_PACKAGES[n.lower()]
        else:
            aliased = LIB_NAME_ALIASES.get(n.lower())
            e = link.add(aliased or n, evidence=ev)
            e.setdefault("ohos_note",
                         "裸链接名（无 find_package/pkg-config 声明），"
                         "产物可得性以名称对齐结果为准")

    # ---- 6c) macOS 框架（-framework X）
    for fw in info.get("macos_frameworks", []):
        e = link.add(fw["name"], kind="platform-iface", required=False,
                     evidence="-framework %s (%s)" % (
                         fw["name"], fw["evidence"][0] if fw.get("evidence") else "?"))
        e["ohos_note"] = "macOS 框架：位于 APPLE 平台块，鸿蒙不适用"

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

    # ---- 6f) autotools PKG_CHECK_MODULES（含版本约束）
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

    # ---- 7) 解析产物 + 版本检查 + 传递 runtime
    runtime_book: Dict[str, Dict] = {}
    link_list = link.values()
    for entry in link_list:
        skip_resolve = entry["kind"] in ("system-lib", "win32-system-lib",
                                         "platform-iface")
        node = None if skip_resolve else _resolve(conn, entry["name"])
        entry["resolved_node"] = node["id"] if node else None
        entry["port_status"] = node["port_status"] if node else None
        entry["available_version"] = node["version"] if node else None
        entry["artifact"] = _artifact_of(node)
        if entry["kind"] == "system-lib":
            entry["artifact"] = entry["artifact"] or {
                "ready": True, "provided": True, "source": "ohos-system"}
        # 版本满足性（见 _version_check）
        entry["version_check"] = _version_check(entry)
        if conn is not None and node is not None and node["id"].startswith(("hb:", "cmdpkgs:")):
            for trans in _runtime_closure(conn, node["id"]):
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

    # ---- 7b) 同库异名合并（resolved_node 相同，如 xkbcommon/libxkbcommon）
    merged: Dict[str, Dict] = {}
    for entry in link_list:
        key = entry.get("resolved_node") or entry["name"].lower()
        base = merged.get(key)
        if base is None:
            merged[key] = entry
            continue
        base["required"] = base["required"] or entry["required"]
        for f in ("min_version", "version_req", "version_range"):
            base[f] = base.get(f) or entry.get(f)
        if entry["kind"] not in ("package", base["kind"]):
            # kind 更具体的覆盖（system-lib/platform-iface/framework 优先）
            if base["kind"] == "package":
                base["kind"] = entry["kind"]
        if entry.get("ohos_note") and not base.get("ohos_note"):
            base["ohos_note"] = entry["ohos_note"]
        base["evidence"] = (base.get("evidence", [])
                            + [e for e in entry.get("evidence", [])
                               if e not in base.get("evidence", [])])
        base["version_check"] = _version_check(base)
    link_list = sorted(merged.values(), key=lambda d: d["name"].lower())

    # ---- 8) dlopen/QLibrary/QPluginLoader 运行时动态加载
    dynamic_loads = []
    for dl in info.get("dynamic_loads", []):
        raw = dl["name"]
        cand = re.sub(r"^lib", "", re.sub(r"\.(so|dll|dylib).*$", "", raw))
        node = _resolve(conn, cand) or _resolve(conn, raw)
        dynamic_loads.append({
            "name": raw, "resolved_node": node["id"] if node else None,
            "artifact": _artifact_of(node),
            "how": dl["how"],
            "note": (None if node else
                     "运行时加载目标未匹配到已知包：若非 Qt 插件需确认来源"),
        })
        if node is None and not raw.startswith(("platform", "imageformats",
                                                "iconengines", "codecs",
                                                "styles", "sqldrivers")):
            warnings.append({
                "level": "warn",
                "msg": "动态加载 %s（%s）未匹配到已知包；Qt 自带插件"
                       "（platform/styles 等）随 Qt SDK 部署，其余需确认"
                       % (raw, dl["how"][0])})

    # ---- 9) Qt 模块（provided，随 Qt SDK）
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

    # ---- 10) 工具链
    toolchain_info = info.get("toolchain", {})
    meson_info = info.get("meson", {})
    tools = []
    for tool, hows in sorted(toolchain_info.get("tools", {}).items()):
        tools.append({"tool": tool, "how": hows[:3],
                      "provided_by": ("qt-sdk" if tool in QT_TOOL_NAMES
                                      else "host")})
    # find_package 命中的构建工具包（ecm/gettext/doxygen 等）并入工具链
    for bt in build_tools:
        tools.append({"tool": bt["tool"], "how": bt["how"],
                      "provided_by": bt["provided_by"],
                      "note": bt["note"]})
    cxx_std = toolchain_info.get("cxx_standard")
    if meson_info.get("cxx_standard"):
        cxx_std = max(cxx_std or 0, meson_info["cxx_standard"])
    if meson_info.get("version_min"):
        tools.append({"tool": "meson", "how": [">= %s（meson_version）"
                                               % meson_info["version_min"]],
                      "provided_by": "host"})
    toolchain = {
        "cmake_min": toolchain_info.get("cmake_min"),
        "cxx_standard": cxx_std,
        "compiler": "OHOS NDK clang（HarmonyOS SDK 自带）",
        "cxx_note": (
            "OHOS NDK clang 支持 C++17；C++20 特性覆盖需按 SDK 版本确认"
            if cxx_std and cxx_std >= 20 else
            ("C++%d：OHOS NDK clang 支持" % cxx_std if cxx_std else None)),
        "tools": tools,
        "has_testing": toolchain_info.get("has_testing", False),
        "note": "构建工具只需在构建机可用（Windows/Linux/macOS 均可），"
                "不部署到设备；Qt 工具（moc/uic/rcc）随 Qt SDK 自动调用",
    }

    # ---- 11) vendored（submodule / vendored 目录 / FetchContent 等配置期拉取）
    vendored = [{"name": gm.get("name") or gm.get("path"),
                 "path": gm.get("path"), "url": gm.get("url"),
                 "note": "submodule：随项目编译，锁定提交在仓库内"}
                for gm in info.get("git_submodules", [])]
    vendored.extend({"name": d, "path": d, "url": None,
                     "note": "vendored 目录：随项目一起编译"}
                    for d in info.get("vendored_dirs", []))
    vendored.extend({"name": fd["name"], "path": None, "url": fd.get("url"),
                     "tag": fd.get("tag"),
                     "note": "%s：configure 阶段拉取源码随项目编译%s" % (
                         fd["how"],
                         "，锁定 %s" % fd["tag"] if fd.get("tag") else "")}
                    for fd in info.get("fetched_deps", []))
    vendored.extend({"name": sp, "path": "subprojects/%s" % sp, "url": None,
                     "note": "meson subproject：随项目一起编译"}
                    for sp in meson_info.get("subprojects", []))

    # ---- 11b) 环境依赖（CI / 安装脚本 apt/brew/pacman install 清单）
    env_deps = []
    for env in info.get("env_installs", []):
        raw_name = env["name"]
        # 发行版包名 → 库名近似（libfoo-dev → foo）
        cand = re.sub(r"-dev$", "", raw_name)
        if cand.startswith("lib") and len(cand) > 3:
            cand = cand[3:]
        node = _resolve(conn, cand) or _resolve(conn, raw_name)
        env_deps.append({
            "name": raw_name, "resolved_node": node["id"] if node else None,
            "available_version": node["version"] if node else None,
            "evidence": env.get("evidence", [])[:2]})

    # ---- 12) Qt 版本满足性
    qt_check = None
    if qt_major:
        avail = QT_OHOS_AVAILABLE.get(str(qt_major))
        if avail:
            best = max(avail, key=_ver_key)
            qt_check = _check_min(qt_min, best)
        else:
            qt_check = "unknown"

    # ---- 13) 汇总与警告
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
                "msg": "%s 版本冲突：要求 %s，鸿蒙产物为 %s"
                       % (entry["name"], " 且 ".join(wants),
                          entry.get("available_version") or "?")})
        elif entry["kind"] == "platform-iface":
            if entry["required"]:
                warnings.append({
                    "level": "warn",
                    "msg": "%s 直连平台栈：%s"
                           % (entry["name"],
                              entry.get("ohos_note") or "鸿蒙不支持")})
        elif not (entry.get("artifact") or {}).get("ready") and entry["required"]:
            warnings.append({
                "level": "warn" if entry["kind"] == "package" else "info",
                "msg": "%s 无鸿蒙预编译产物（required=%s）：需源码交叉编译%s"
                       % (entry["name"], entry["required"],
                          "，源码: %s" % (entry["artifact"] or {}).get("repo_url")
                          if (entry["artifact"] or {}).get("repo_url") else "")})
    if info.get("build_system") == "qmake":
        warnings.append({
            "level": "info",
            "msg": "qmake 工程交叉编译需自定义 mkspec（参考 KB: QScintilla 案例）"})
    if qt_check == "conflict":
        warnings.append({
            "level": "warn",
            "msg": "Qt 版本要求 %s 高于 Qt for HarmonyOS 可用版本（%s）"
                   % (qt_min, "/".join(QT_OHOS_AVAILABLE.get(str(qt_major), ())))})

    # ---- 13b) 环境清单交叉核对：CI 安装但构建文件未声明的库名（潜在漏检）
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
                "msg": "CI 脚本安装了 %s 但构建文件未声明：可能经变量引用/自"
                       "定义 Find 模块引入（补查），或仅为构建机工具"
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
            "note": "Qt 模块由 Qt for HarmonyOS SDK 提供，"
                    "harmonydeployqt 负责部署",
        },
        "toolchain": toolchain,
        "link_deps": link_list,
        "runtime_deps": list(runtime_book.values()),
        "dynamic_loads": dynamic_loads,
        "test_deps": test_deps,
        "vendored": vendored,
        "env_deps": env_deps,
        "counts": {
            "link": len(link_list),
            "runtime": len(runtime_book),
            "dynamic_loads": len(dynamic_loads),
            "build_tools": len(build_tools) + len(tools),
            "test": len(test_deps),
            "vendored": len(vendored),
            "env": len(env_deps),
            "qt_modules": len(qt_modules),
        },
        "warnings": warnings,
    }
    return report


def _range_to_req(range_str: Optional[str]) -> Optional[str]:
    """conan 范围串 '[>=1.2 <2]' → 取第一个 '>=x' 约束（近似检查）。"""
    if not range_str:
        return None
    m = re.search(r">=\s*([\w.]+)", range_str)
    return ">= %s" % m.group(1) if m else None


# ---------------------------------------------------------------- 渲染

def render_text(report: Dict) -> str:
    """人读摘要。"""
    p = report["project"]
    q = report["qt"]
    t = report["toolchain"]
    lines: List[str] = []
    lines.append("=== 依赖分析: %s%s ===" % (
        p["name"], " v%s" % p["version"] if p["version"] else ""))
    lines.append("构建系统: %s | 源文件 %d 个" % (p["build_system"], p["sources"]))
    if q.get("major"):
        check = {"satisfied": "✓ 满足", "conflict": "✗ 冲突",
                 "unknown": "? 未知"}.get(q.get("check"), "")
        lines.append("Qt: %s%s | 鸿蒙可用: %s %s" % (
            q["major"], " (>= %s)" % q["min_version"] if q.get("min_version") else "",
            "/".join(q.get("available_on_ohos") or ["?"]), check))
    blocked_qt = [m["module"] for m in q["modules"] if m["status"] == "blocked"]
    if blocked_qt:
        lines.append("Qt 阻塞模块: %s" % ", ".join(blocked_qt))

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
            return "系统自带"
        if e.get("kind") == "win32-system-lib":
            return "Windows 系统库（鸿蒙不适用）"
        if e.get("kind") == "platform-iface":
            return "平台接口（鸿蒙不支持直连）"
        if a.get("ready"):
            return "产物: %s" % a.get("source")
        if a.get("provided"):
            return "框架提供"
        return "无产物 → 需源码编译"

    lines.append("")
    lines.append("── 编译产物依赖 (link) %d 个：目标侧 headers+libs，"
                 "交叉编译/链接时必须存在 ──" % len(report["link_deps"]))
    for e in report["link_deps"]:
        req = "" if e["required"] else " [optional]"
        vc = {"satisfied": " ✓", "conflict": " ✗版本冲突",
              "unknown": ""}.get(e.get("version_check"), "")
        lines.append("  • %s %s%s%s (%s)"
                     % (e["name"], _ver(e), req, vc, e["kind"]))
        lines.append("      %s" % _art(e))
        if e.get("available_version"):
            lines.append("      鸿蒙版本: %s%s" % (
                e["available_version"],
                "" if e.get("version_check") != "conflict" else "（低于要求）"))
        if e.get("evidence"):
            lines.append("      证据: %s" % e["evidence"][0])
        if e.get("ohos_note"):
            lines.append("      注: %s" % e["ohos_note"])

    lines.append("")
    lines.append("── 编译器/工具链依赖 (build-tool) %d 个：构建机运行，"
                 "不部署到设备 ──" % report["counts"]["build_tools"])
    if t.get("cmake_min"):
        lines.append("  • CMake >= %s（cmake_minimum_required）" % t["cmake_min"])
    if t.get("cxx_standard"):
        lines.append("  • C++%d（%s）" % (t["cxx_standard"], t["cxx_note"] or ""))
    lines.append("  • 编译器: %s" % t["compiler"])
    for tool in t.get("tools", []):
        lines.append("  • %s（%s）" % (tool["tool"],
                                      "Qt SDK 提供" if tool["provided_by"] == "qt-sdk"
                                      else "构建机准备: " + tool["how"][0]))

    rt = report["runtime_deps"]
    lines.append("")
    lines.append("── 运行时依赖 (runtime) %d 个：设备侧 .so，"
                 "部署到 entry/libs/arm64-v8a/ ──" % len(rt))
    for e in rt[:40]:
        a = e.get("artifact") or {}
        src = ("产物: %s" % a["source"] if a.get("ready")
               else "无产物 → 需随其来源一起源码编译")
        lines.append("  • %s v%s — %s（传递自 %s）"
                     % (e["name"], e.get("version") or "?", src,
                        ", ".join(e.get("needed_by", [])[:3])))
    if len(rt) > 40:
        lines.append("  … 另有 %d 个传递依赖" % (len(rt) - 40))
    for dl in report["dynamic_loads"]:
        lines.append("  • [动态加载] %s（%s）%s" % (
            dl["name"], dl["how"][0],
            "→ " + (dl["artifact"].get("source") or "未匹配到已知包")
            if dl.get("artifact") else ""))

    if report["test_deps"]:
        lines.append("")
        lines.append("── 测试依赖 (test) %d 个：不进发行包 ──"
                     % len(report["test_deps"]))
        for e in report["test_deps"]:
            lines.append("  • %s — %s" % (e["name"], e["source"]))

    if report["vendored"]:
        lines.append("")
        lines.append("── 自带源码 (vendored) %d 个：随项目编译，"
                     "无需外部产物 ──" % len(report["vendored"]))
        for e in report["vendored"]:
            lines.append("  • %s (%s)%s" % (e["name"], e["note"],
                                            " %s" % e["url"] if e.get("url") else ""))

    env = report.get("env_deps", [])
    if env:
        lines.append("")
        lines.append("── 环境依赖 (env, CI/脚本安装) %d 个：构建机环境清单，"
                     "交叉核对信源 ──" % len(env))
        for e in env[:25]:
            res = ("→ %s v%s" % (e["resolved_node"], e["available_version"])
                   if e.get("resolved_node") else "（未匹配到已知包）")
            lines.append("  • %s %s" % (e["name"], res))
        if len(env) > 25:
            lines.append("  … 另有 %d 个" % (len(env) - 25))

    if report["warnings"]:
        lines.append("")
        lines.append("── 警告/提示 %d 条 ──" % len(report["warnings"]))
        for w in report["warnings"]:
            lines.append("  %s %s" % ("[!]" if w["level"] == "warn" else "[i]",
                                      w["msg"]))
    return "\n".join(lines)
