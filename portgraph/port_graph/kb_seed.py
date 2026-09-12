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
