"""种子数据：Qt 模块鸿蒙支持矩阵 + 平台接口白名单 + 跨源名称对齐。

- Qt 模块：运行时解析 data/qt-harmonyos-modules.md 三张表（vendored 知识页）
- 平台接口白名单：人工策展
- 名称对齐：扫描线索名 -> harmonybrew/cmd-pkgs 包节点
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import DATA_DIR, db

MODULES_PAGE = DATA_DIR / "qt-harmonyos-modules.md"
QT_CLUSTER_ID = "cluster:qt"

# ------------------------------------------------------------- 接口白名单

# (id, name, category, ohos_status, note)
INTERFACE_SEEDS: List[Tuple[str, str, str, str, str]] = [
    ("iface:posix", "POSIX/musl C 库", "os-api", "supported",
     "OpenHarmony NDK 使用 musl libc，POSIX 基础接口覆盖面广"),
    ("iface:bsd-socket", "BSD socket / TCP-IP", "network", "supported",
     "鸿蒙网络栈支持标准 BSD socket API"),
    ("iface:opengl-es", "OpenGL ES / EGL", "graphics", "supported",
     "鸿蒙图形栈提供 EGL/GLES；桌面 OpenGL 需降级转换为 GLES"),
    ("iface:pthread", "pthread 多线程", "os-api", "supported",
     "musl 提供 pthread"),
    ("iface:dylib", "dlopen 动态加载", "os-api", "convertible",
     "鸿蒙支持 dlopen，但库路径/打包方式受限，需适配 HAP 内 native 目录"),
    ("iface:macos-system", "macOS 系统库绑定", "os-api", "convertible",
     "formula 依赖 macOS 系统自带库；鸿蒙上需改为显式打包依赖"),
    ("iface:glib-event", "glib 事件循环", "os-api", "convertible",
     "可用 Qt 事件循环替代或移植 glib 主循环"),
    ("iface:gnutls-api", "GnuTLS/GSS-API 系统绑定", "crypto", "convertible",
     "可改为显式依赖开源实现包"),
    ("iface:x11", "X11/Xlib 直连", "display", "unsupported",
     "鸿蒙无 X11 显示服务；Qt 应用应走 QPA，直连 X11 代码不可移植"),
    ("iface:wayland", "Wayland 直连", "display", "unsupported",
     "鸿蒙窗口模型非 Wayland 协议；直连代码不可移植"),
    ("iface:dbus", "D-Bus IPC", "ipc", "unsupported",
     "鸿蒙无 D-Bus（Qt D-Bus 模块 Out of scope）；需改用系统服务/IPC"),
    ("iface:alsa", "ALSA 直连", "audio", "unsupported",
     "鸿蒙音频走 AudioRenderer/AudioCapturer，ALSA 不可用"),
    ("iface:pulseaudio", "PulseAudio 直连", "audio", "unsupported",
     "鸿蒙无 PulseAudio 服务"),
    ("iface:coreaudio", "macOS CoreAudio", "audio", "unsupported",
     "macOS 专属音频框架"),
    ("iface:win32", "Win32 API", "os-api", "unsupported",
     "Windows 专属系统接口"),
    ("iface:cocoa", "macOS Cocoa/AppKit", "os-api", "unsupported",
     "macOS 专属 UI/系统框架"),
    ("iface:systemd", "systemd", "os-api", "unsupported",
     "鸿蒙无 systemd 服务管理"),
    ("iface:fork-exec", "fork()/exec() 进程模型", "os-api", "unknown",
     "musl 提供 fork，但鸿蒙应用沙箱对子进程有约束，需按场景评估"),
    ("iface:gpu-desktop-gl", "桌面 OpenGL(3.x+/兼容上下文)", "graphics", "convertible",
     "需转换为 OpenGL ES 或经 Qt RHI/ANGLE 类方案"),
    # ---- 鸿蒙原生接口（作为不支持接口的替代选项）----
    ("iface:ohos-audio", "鸿蒙 AudioRenderer/AudioCapturer", "audio", "supported",
     "鸿蒙原生音频 API，替代 ALSA/PulseAudio/CoreAudio"),
    ("iface:ohos-window", "鸿蒙 WindowStage/XComponent", "display", "supported",
     "鸿蒙窗口模型，替代 X11/Wayland 直连"),
    ("iface:ohos-ipc", "鸿蒙 IPC/系统服务能力", "ipc", "supported",
     "鸿蒙原生 IPC 机制，替代 D-Bus"),
]

# ------------------------------------------------------------- KF 组件依赖
# KDE Frameworks 组件 -> {qt: Qt模块, kf: 依赖的其他KF组件, ifaces: 平台接口}
# 用于把 KF 组件作为子项目递归分析，而非整体判 blocked。
KF_DEPS: Dict[str, Dict] = {
    "coreaddons": {"qt": ["core"], "kf": [], "ifaces": []},
    "i18n": {"qt": ["core", "gui"], "kf": ["coreaddons"], "ifaces": []},
    "config": {"qt": ["core"], "kf": ["coreaddons"], "ifaces": []},
    "configwidgets": {"qt": ["core", "gui", "widgets"],
                      "kf": ["config", "coreaddons", "i18n", "widgetsaddons",
                             "guiaddons"], "ifaces": []},
    "guiaddons": {"qt": ["core", "gui"], "kf": [], "ifaces": []},
    "widgetsaddons": {"qt": ["core", "gui", "widgets"],
                      "kf": ["coreaddons"], "ifaces": []},
    "itemviews": {"qt": ["core", "gui", "widgets"], "kf": [], "ifaces": []},
    "textwidgets": {"qt": ["core", "gui", "widgets"],
                    "kf": ["iconthemes"], "ifaces": []},
    "iconthemes": {"qt": ["core", "gui"], "kf": ["guiaddons"], "ifaces": []},
    "xmlgui": {"qt": ["core", "gui", "widgets"],
               "kf": ["config", "coreaddons", "i18n", "iconthemes",
                      "widgetsaddons", "itemviews", "textwidgets"],
               "ifaces": []},
    "completion": {"qt": ["core", "gui", "widgets"],
                   "kf": ["config", "coreaddons", "i18n", "widgetsaddons"],
                   "ifaces": []},
    "archive": {"qt": ["core"], "kf": [], "ifaces": []},
    "crash": {"qt": ["core"], "kf": ["coreaddons"], "ifaces": []},
    "jobwidgets": {"qt": ["core", "gui", "widgets"],
                   "kf": ["coreaddons"], "ifaces": []},
    "kio": {"qt": ["core", "gui", "widgets", "network"],
            "kf": ["coreaddons", "config", "i18n", "jobwidgets",
                   "widgetsaddons"], "ifaces": ["iface:dbus"]},
    "colorscheme": {"qt": ["core", "gui"], "kf": ["guiaddons", "config"],
                    "ifaces": []},
    "windowsystem": {"qt": ["core", "gui"], "kf": [],
                     "ifaces": ["iface:x11", "iface:win32"]},
    "dbusaddons": {"qt": ["core", "dbus"], "kf": [], "ifaces": ["iface:dbus"]},
    "dnssd": {"qt": ["core", "network"], "kf": [], "ifaces": ["iface:dbus"]},
    "notifications": {"qt": ["core", "gui", "widgets"],
                      "kf": ["config", "coreaddons", "i18n", "widgetsaddons"],
                      "ifaces": ["iface:dbus"]},
    "notifyconfig": {"qt": ["core", "gui", "widgets"],
                     "kf": ["notifications", "config"], "ifaces": []},
    "bookmarks": {"qt": ["core"], "kf": ["kio", "coreaddons"], "ifaces": []},
    "kcmutils": {"qt": ["core", "gui", "widgets"],
                 "kf": ["coreaddons", "i18n", "config", "service"],
                 "ifaces": []},
    "service": {"qt": ["core"], "kf": ["coreaddons", "config"], "ifaces": []},
    "doctools": {"qt": ["core"], "kf": [], "ifaces": []},
    "statusnotifieritem": {"qt": ["core", "gui", "dbus"], "kf": [],
                           "ifaces": ["iface:dbus"]},
    "screen": {"qt": ["core", "gui"], "kf": ["windowsystem"],
               "ifaces": ["iface:x11"]},
}

# ------------------------------------------------------------- Qt 模块

_ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|(.*)$")


def normalize_module(name: str) -> str:
    """'Qt Quick Controls' -> 'quickcontrols'；'Qt WebEngine (全子模块)' -> 'webengine'。"""
    n = re.sub(r"[（(].*?[)）]", "", name.strip())
    if n.lower().startswith("qt "):
        n = n[3:]
    elif n.lower().startswith("qt") and len(n) > 2 and n[2].isupper():
        n = n[2:]
    return re.sub(r"[\s\-_]+", "", n).lower()


def _parse_module_tables(text: str) -> List[Dict]:
    """解析知识页中的三类模块表。"""
    modules: List[Dict] = []
    section = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("## "):
            if "Essentials" in s:
                section = "essentials"
            elif "Out of scope" in s or "不在范围内" in s:
                section = "oos"
            elif "已完成" in s or "Add-Ons" in s:
                section = "addons"
            else:
                section = None
            continue
        if section is None or not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 2 or set(cells[0]) <= {"-", ":", " "}:
            continue
        if cells[0] in ("模块", "我想确认..."):
            continue
        name = cells[0]
        if section == "oos":
            modules.append({"name": name, "status": "blocked",
                            "note": cells[1] if len(cells) > 1 else ""})
        else:
            c512 = cells[1] if len(cells) > 1 else ""
            c515 = cells[2] if len(cells) > 2 else ""
            note = cells[3] if len(cells) > 3 else ""
            ok512, ok515 = "✅" in c512, "✅" in c515
            if ok512 and ok515:
                status = "ported"
            elif ok512 or ok515:
                status = "ported"
                note = ("部分支持：" + ("仅5.12" if ok512 else "仅5.15")
                        + ("；" + note if note else ""))
            else:
                status = "blocked"
            modules.append({"name": name, "status": status, "note": note})
    return modules


def seed_qt_modules(conn) -> List[Dict]:
    text = MODULES_PAGE.read_text(encoding="utf-8")
    modules = _parse_module_tables(text)
    db.upsert_cluster(conn, QT_CLUSTER_ID, "Qt", "framework")
    for m in modules:
        key = normalize_module(m["name"])
        evidence = ("Qt for HarmonyOS 模块适配表: " +
                    ("不支持 - " + m["note"] if m["status"] == "blocked"
                     else "已完成" + ("（" + m["note"] + "）" if m["note"] else "")))
        db.upsert_node(conn, "qtmod:%s" % key, "qt-module", m["name"],
                       "kb-seed", m["status"], port_evidence=evidence,
                       cluster_id=QT_CLUSTER_ID)
    return modules


def seed_interfaces(conn) -> None:
    for seed in INTERFACE_SEEDS:
        db.upsert_interface(conn, *seed)


# ------------------------------------------------------------- 名称对齐

# 扫描线索名 -> 候选包名（按优先级）
ALIASES: Dict[str, List[str]] = {
    "openssl": ["openssl@3", "openssl"],
    "libjpeg": ["jpeg-turbo", "libjpeg-turbo"],
    "icu": ["icu4c", "icu"],
    "libuuid": ["util-linux", "libuuid", "uuid"],
    "freetype": ["freetype"],
    "harfbuzz": ["harfbuzz"],
    "ffmpeg": ["ffmpeg"],
    "sqlite": ["sqlite"],
    "zlib": ["zlib"],
    "libpng": ["libpng"],
    "curl": ["curl"],
    "boost": ["boost"],
    "protobuf": ["protobuf"],
    "spdlog": ["spdlog"],
    "glm": ["glm"],
    "opencv": ["opencv"],
}


# 库名/pkg-config 名 → 鸿蒙包名对齐（hb 包名口径）。
# deps_report 用于同库双声明合并；project_scanner 用于扫描期解析（消除
# libavcodec→ffmpeg 这类幽灵节点），两处共享同一张表。
PKG_ALIASES: Dict[str, str] = {
    "swscale": "ffmpeg", "avcodec": "ffmpeg", "avformat": "ffmpeg",
    "avutil": "ffmpeg", "swresample": "ffmpeg", "postproc": "ffmpeg",
    "libswscale": "ffmpeg", "libavcodec": "ffmpeg", "libavformat": "ffmpeg",
    "libavutil": "ffmpeg", "libavdevice": "ffmpeg",
    "ssl": "openssl", "crypto": "openssl",
    "sqlite3": "sqlite", "curl": "curl", "gcrypt": "libgcrypt",
    "tag": "taglib", "mtp": "libmtp", "usb-1.0": "libusb",
    "magic": "libmagic", "exif": "libexif", "discid": "libdiscid",
    "chromaprint": "chromaprint", "mp3lame": "lame",
    # pkg-config 模块名无 lib 前缀 → hb 包名（e2e keepassxc 复核确认的缺口）
    "xkbcommon": "libxkbcommon", "x11": "libx11",
    # PC/SC 智能卡栈：find_package(PCSC)/pkg-config libpcsclite/find_library
    # pcsclite → pcsc-lite
    "pcsc": "pcsc-lite", "libpcsclite": "pcsc-lite",
    "pcsclite": "pcsc-lite",
    # pkg-config 名 → CMake find_package 名（同库双声明合并）
    "libtorrent-rasterbar": "LibtorrentRasterbar",
    # ── 语料外泛化测试补充（QOwnNotes/strawberry/krita 实证，2026-09）──
    # glib 家族 pkg-config 模块（libgio/gobject/gthread/gmodule 随 glib
    # 包发布，cmd-pkgs glib 2.88.0 与 hb glib bottle 内均实测含对应 .pc）
    "gio-2.0": "glib", "gio-unix-2.0": "glib", "gobject-2.0": "glib",
    "gthread-2.0": "glib", "gmodule-2.0": "glib",
    "gmodule-no-export-2.0": "glib",
    # gstreamer 核心模块（cmd-pkgs gstreamer tarball 实测含
    # libgst{base,controller,net,check}-1.0.so 与对应 .pc；
    # gstreamer-app/audio/pbutils/tag 属 gst-plugins-base，不在包内，
    # 不加别名以兑底 need_port 定性）
    "gstreamer-base-1.0": "gstreamer", "gstreamer-net-1.0": "gstreamer",
    "gstreamer-controller-1.0": "gstreamer",
    # fftw 精度/线程变体（同名包内，cmdpkgs:fftw 3.3.10）
    "fftw3": "fftw", "fftw3f": "fftw", "fftw3l": "fftw", "fftw3q": "fftw",
    "fftw3_omp": "fftw", "fftw3f_omp": "fftw", "fftw3l_omp": "fftw",
    "fftw3q_omp": "fftw", "fftw3_threads": "fftw",
    "fftw3f_threads": "fftw", "fftw3l_threads": "fftw",
    "fftw3q_threads": "fftw",
    # libav* 遗漏项（libavfilter 缺失致 krita 误报 need_port）
    "libavfilter": "ffmpeg", "libswresample": "ffmpeg",
    "libpostproc": "ffmpeg",
    # 各库常见变体名（hb/cmd-pkgs 包名口径）
    "gif": "giflib",                       # krita find_package(GIF)
    "jpegxl": "libjxl", "libjxl_threads": "libjxl",  # cmdpkgs:libjxl
    "turbojpeg": "jpeg-turbo", "libturbojpeg": "jpeg-turbo",
    "turbojpeg-static": "jpeg-turbo", "jpeg-static": "jpeg-turbo",
    "webpdecoder": "webp", "webpdemux": "webp", "webpmux": "webp",
    "sharpyuv": "webp", "libsharpyuv": "webp",
    "libopenjp2": "openjpeg", "openjp2": "openjpeg",
    "openjpip": "openjpeg", "openjpip_server": "openjpeg",
    "libopenjpip": "openjpeg", "libopenjpip_server": "openjpeg",
    "harfbuzz-icu": "harfbuzz",
    "eigen3": "eigen",                      # krita find_package(Eigen3)
    "botan3": "botan-3",                    # QOwnNotes find_package(Botan3)
    # OpenEXR 3.x 组件（hb openexr bottle 实测含 libIex/IlmThread/
    # OpenEXR/Core/Util；Half 在 3.x 归 imath）
    "iex": "openexr", "iexmath": "openexr", "ilmimf": "openexr",
    "ilmimfutil": "openexr", "ilmthread": "openexr",
    "openexrcore": "openexr", "openexrutil": "openexr",
    "half": "imath",
    # gsl 的 cblas 组件（hb/cmd-pkgs gsl 同包发布）
    "gslcblas": "gsl", "cblas": "gsl",
    "jpeg": "jpeg-turbo",                   # hb 包名为 jpeg-turbo
    # lcms2（hb 包名 little-cms2 / cmd-pkgs 名 lcms2）
    "lcms-2": "lcms2", "lcms2": "lcms2",
    "lcms-2_fast_float": "lcms2", "lcms2_fast_float": "lcms2",
    # Ogg（libogg 包）
    "ogg": "libogg",
    # 同库异名归并（无包源时幽灵节点用规范名，避免双份 need_port）
    "quazip-qt": "quazip", "kdcrawqt6": "kdcraw",
}


def resolve_package(conn, hint_name: str) -> Optional[Dict]:
    """第三方库线索 -> 已入库的包节点（hb 优先，ported 优先）。"""
    candidates = ALIASES.get(hint_name.lower(), [hint_name])
    best: Optional[Dict] = None
    for cand in candidates:
        for prefix in ("hb:", "cmdpkgs:"):
            node = db.get_node(conn, prefix + cand.lower())
            if node is None and prefix == "cmdpkgs:":
                node = db.find_node_by_name(conn, cand)
                if node and not node["id"].startswith("cmdpkgs:"):
                    node = None
            if node:
                if best is None or (node["port_status"] == "ported" and
                                    best["port_status"] != "ported"):
                    best = node
                break
        if best and best["port_status"] == "ported":
            break
    return best


def resolve_pkg_name(conn, name: str,
                      cache: Optional[Dict] = None) -> Optional[Dict]:
    """库线索名（find_package/pkg-config/裸链接）→ 已入库包节点。

    deps_report 与 project_scanner 的共享解析口径，依次尝试：
      1. 别名表 PKG_ALIASES（hb 包名口径，如 sqlite3→sqlite、
         libavfilter→ffmpeg；优先于原名，使同库异名归并到同一节点，
         避免 sqlite3/sqlite 双产物重复下载）
      2. 原名 / 补 lib 前缀（xkbcommon→libxkbcommon）/ 去 lib 前缀
      3. 去 pkg-config 版本后缀（glib-2.0→glib）及其组合
    扫描期与报告期共用，消除 fetch-deps 幽灵节点而 deps 报告能解析
    的口径分裂（libsparsehash/gio-2.0 实证）。
    cache: 单次分析内缓存（含 None 未命中；分析期间图不变）。
    """
    if conn is None:
        return None
    key = (name or "").lower()
    if not key:
        return None
    if cache is not None and key in cache:
        return cache[key]
    node = None
    alias = PKG_ALIASES.get(key)
    if alias and alias.lower() != key:
        node = resolve_package(conn, alias.lower())
    if node is None:
        stripped = re.sub(r"-\d+(\.\d+)*$", "", key)
        cands = [key]
        if not key.startswith("lib"):
            cands.append("lib" + key)
        if key.startswith("lib"):
            cands.append(key[3:])
        if stripped != key:
            cands.append(stripped)
            if not stripped.startswith("lib"):
                cands.append("lib" + stripped)
        # find_library NAMES 的构建形态后缀（libFLAC_static / jpeg-static
        # / libFLAC_dynamic）→ 基础名
        for base in list(cands):
            s2 = re.sub(r"[_-](static|dynamic|debug)$", "", base)
            if s2 != base and s2 not in cands:
                cands.append(s2)
        # 展开各候选的别名（libfftw3 → 去前缀 fftw3 → 别名 fftw；
        # libwebpmux → webpmux → webp）
        expanded: List[str] = []
        for cand in cands:
            expanded.append(cand)
            a = PKG_ALIASES.get(cand)
            if a and a.lower() not in expanded:
                expanded.append(a.lower())
        for cand in expanded:
            node = resolve_package(conn, cand)
            if node:
                break
    if cache is not None:
        cache[key] = node
    return node


def ingest(conn) -> Dict:
    db.init_db(conn)
    modules = seed_qt_modules(conn)
    seed_interfaces(conn)
    db.set_meta(conn, "ingest_kb_at", db.now())
    db.set_meta(conn, "qt_module_count", str(len(modules)))
    conn.commit()
    return {
        "qt_modules": len(modules),
        "blocked_modules": [m["name"] for m in modules if m["status"] == "blocked"],
        "interfaces": len(INTERFACE_SEEDS),
    }
