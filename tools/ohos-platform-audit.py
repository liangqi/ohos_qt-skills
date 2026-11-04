#!/usr/bin/env python3
"""平台层移植审计 —— 回答"这个应用的平台抽象还缺什么"。

    python tools/ohos-platform-audit.py <app>/SourceFiles/platform
    python tools/ohos-platform-audit.py <app>/SourceFiles/platform --json
    python tools/ohos-platform-audit.py <dir> --undefined undef.txt

为什么需要它：桌面应用的平台层有**两种分发机制**，只盯一种最多覆盖一半。

  1. **头文件分发**：`platform_*.h` 末尾是一串 `#ifdef` 链，链尾 `#else` 落到
     Linux 实现。只写 `Q_OS_OHOS` 的守卫在 Qt 6.x kit 上**永不成立**
     （6.x 只定义 `Q_OS_HARMONY`），于是静默拿到 D-Bus/X11 实现。
  2. **源文件分发**：`platform_*.h` 里根本没有 `#ifdef`，构建过程按路径挑 `.cpp`。
     这类头一个字都不用改，只要 `ohos/xxx_ohos.cpp` 被构建选中就生效。

退出码：0 = 每个头分发文件都同时接受两个 OHOS 宏；1 = 有文件只认一个宏；
2 = 用法/路径错误。`--undefined` 模式下，0 = 未发现"完全没人实现"的符号。

实现约束：纯标准库、无第三方依赖、Windows/macOS/Linux 一致。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HEADER_PREFIX = "platform_"
OHOS_MACROS = ("Q_OS_OHOS", "Q_OS_HARMONY")
# 头分发判定：链里出现 Linux 头路径，或出现至少两个 Q_OS_* 分支
LINUX_ROUTE_RE = re.compile(r"platform/linux/")
OS_BRANCH_RE = re.compile(r"#\s*(?:el)?if(?:def)?\s+.*Q_OS_[A-Z]+")
UNDEF_RE = re.compile(r"undefined (?:symbol|reference)[: ]+[`'\"]?([A-Za-z_][\w:~<>]*)")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    except OSError:
        return ""


def classify(text: str) -> str:
    """header = 靠 #ifdef 链选头；source = 靠构建按路径选 .cpp。"""
    if LINUX_ROUTE_RE.search(text):
        return "header"
    if len(set(OS_BRANCH_RE.findall(text))) >= 2:
        return "header"
    return "source"


def audit(root: Path, strict: bool = False) -> dict:
    headers = sorted(p for p in root.glob(HEADER_PREFIX + "*.h") if p.is_file())
    header_dispatch, source_dispatch, missing = [], [], []
    for path in headers:
        text = read_text(path)
        kind = classify(text)
        has_all = all(macro in text for macro in OHOS_MACROS)
        if kind == "header":
            header_dispatch.append({"file": path.name, "ok": has_all,
                                    "macros": [m for m in OHOS_MACROS if m in text]})
            if not has_all:
                missing.append(path.name)
        else:
            source_dispatch.append(path.name)

    ohos_dir = root / "ohos"
    ohos_files = sorted(p.name for p in ohos_dir.iterdir() if p.is_file()) \
        if ohos_dir.is_dir() else []

    # 源分发文件：头里没有分支可改，实现必须由构建按路径选中，所以要断言
    # `ohos/` 下真有对应实现（按去掉 platform_ 前缀的核心名匹配）。
    unimplemented = []
    if strict:
        blob = "\n".join(ohos_files).lower()
        for name in source_dispatch:
            core = name[len(HEADER_PREFIX):-len(".h")].lower()
            if core and core not in blob:
                unimplemented.append(name)

    return {
        "root": str(root),
        "header_dispatch": header_dispatch,
        "source_dispatch": source_dispatch,
        "missing_both_macros": missing,
        "ohos_implementations": ohos_files,
        "ohos_dir_exists": ohos_dir.is_dir(),
        "source_dispatch_unimplemented": unimplemented,
    }


def symcheck(root: Path, undefined_file: Path) -> dict:
    """从链接期 undefined symbol 清单反推"哪些平台符号还没人实现"。

    判据故意保守：符号名（去掉参数与限定后）在 `ohos/` 任何实现文件里
    出现过即视为"有人管"，否则列为疑似缺失。它不替代链接器，
    只把"一两百条 undefined 里哪些属于平台层"这件事自动收敛。
    """
    text = read_text(undefined_file)
    symbols = sorted(set(UNDEF_RE.findall(text)))
    ohos_dir = root / "ohos"
    blob = "\n".join(read_text(p) for p in ohos_dir.iterdir()
                     if p.is_file()) if ohos_dir.is_dir() else ""
    platform_level = []
    for sym in symbols:
        base = sym.split("(")[0].split("::")[-1].strip()
        if not base:
            continue
        if base in blob:
            continue
        platform_level.append(sym)
    return {
        "undefined_total": len(symbols),
        "platform_level_missing": platform_level,
        "ohos_dir": str(ohos_dir),
    }


def render(report: dict) -> str:
    lines = []
    hd = report["header_dispatch"]
    lines.append("header dispatch (%d), all must name %s:" %
                 (len(hd), " and ".join(OHOS_MACROS)))
    for item in hd:
        lines.append("  %-42s %s" % (item["file"],
                                     "OK" if item["ok"] else "MISSING"))
    lines.append("")
    lines.append("source dispatch (%d), no #ifdef chain by design:" %
                 len(report["source_dispatch"]))
    for name in report["source_dispatch"]:
        lines.append("  %s" % name)
    lines.append("")
    if report["ohos_dir_exists"]:
        lines.append("ohos/ implementations (%d):" %
                     len(report["ohos_implementations"]))
    else:
        lines.append("ohos/ directory does not exist")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="平台层移植审计：头分发/源分发分类 + 双 OHOS 宏断言")
    parser.add_argument("platform_dir", help="应用的平台目录（如 SourceFiles/platform）")
    parser.add_argument("--json", action="store_true", help="机读输出")
    parser.add_argument("--undefined", metavar="FILE",
                        help="链接日志文件：反推仍缺实现的平台符号")
    parser.add_argument("--strict", action="store_true",
                        help="源分发文件也必须在 ohos/ 下有对应实现，否则判失败")
    args = parser.parse_args()

    root = Path(args.platform_dir)
    if not root.is_dir():
        print("not a directory: %s" % root, file=sys.stderr)
        return 2

    report = audit(root, strict=args.strict)
    exit_code = 1 if (report["missing_both_macros"]
                      or report["source_dispatch_unimplemented"]) else 0

    undef_report = None
    if args.undefined:
        undef_file = Path(args.undefined)
        if not undef_file.is_file():
            print("not a file: %s" % undef_file, file=sys.stderr)
            return 2
        undef_report = symcheck(root, undef_file)
        report["undefined"] = undef_report
        if undef_report["platform_level_missing"]:
            exit_code = 1

    if args.strict and not report["ohos_dir_exists"]:
        report["source_dispatch_unimplemented"] = list(report["source_dispatch"])
        exit_code = 1

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render(report))
        if undef_report is not None:
            lines = report["header_dispatch"]
            print("")
            print("undefined symbols: %d total, %d with no ohos/ implementation"
                  % (undef_report["undefined_total"],
                     len(undef_report["platform_level_missing"])))
            for sym in undef_report["platform_level_missing"][:40]:
                print("  missing: %s" % sym)
        print("")
        if report["source_dispatch_unimplemented"]:
            print("FAIL: %d source-dispatch header(s) have no ohos/ implementation:"
                  % len(report["source_dispatch_unimplemented"]))
            for name in report["source_dispatch_unimplemented"]:
                print("  %s" % name)
        if report["missing_both_macros"]:
            print("FAIL: %d header(s) do not accept both OHOS macros:"
                  % len(report["missing_both_macros"]))
            for name in report["missing_both_macros"]:
                print("  %s" % name)
        else:
            print("PASS: every header-dispatch platform file accepts both OHOS macros")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
