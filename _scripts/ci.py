#!/usr/bin/env python3
"""仓库门禁 —— 纯标准库、跨平台（Windows 没有 bash 也能跑）。

    python _scripts/ci.py            # 跑全部门禁，退出码即结论
    bash _scripts/ci.sh              # 同上（薄壳，转发到这里）

四条门禁与 `ci.sh` 完全一致：
  1. 仓库自检（契约/结构/引用/索引/发版清单/卫生，10 类）
  2. 故障库真源 ↔ 派生物
  3. 用例（一致性 + 引擎 + 扫描）
  4. CLI 冒烟（每个 CLI 的 --help 必须 exit 0）

发版清单不参与判定：普通提交上它必然是"旧快照"，发版时另用
`python _scripts/gen-manifest.py --check --strict` 对账。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable or "python"

CLI_SMOKE = [
    "tools/qt-ohos-run.py",
    "tools/qt-sdk-run.py",
    "tools/faults-build.py",
    "tools/cpp20-gap-scan.py",
    "tools/kb-cef-graft.py",
    "portgraph/portgraph.py",
]


def run(title: str, argv: list[str]) -> bool:
    print(f"== {title} ==")
    try:
        code = subprocess.call([PY] + argv, cwd=ROOT)
    except OSError as exc:                     # 解释器/脚本缺失
        print(f"  无法执行：{exc}")
        return False
    print()
    return code == 0


def main() -> int:
    results: list[tuple[str, bool]] = []
    results.append(("1/4 仓库自检（契约/结构/引用/索引/发版清单/卫生）",
                    run("1/4 仓库自检（契约/结构/引用/索引/发版清单/卫生，10 类）",
                        ["_scripts/verify.py"])))
    results.append(("2/4 故障库真源 ↔ 派生物",
                    run("2/4 故障库真源 ↔ 派生物", ["tools/faults-build.py", "check"])))
    results.append(("3/4 用例（一致性 + 引擎 + 扫描）",
                    run("3/4 用例（一致性 + 引擎 + 扫描）",
                        ["-m", "unittest", "discover", "-s", "tests"])))

    print("== 4/4 CLI 冒烟（--help 全部 exit 0） ==")
    smoke_ok = True
    for rel in CLI_SMOKE:
        try:
            code = subprocess.call([PY, rel, "--help"], cwd=ROOT,
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
        except OSError:
            code = -1
        if code != 0:
            smoke_ok = False
            print(f"  FAIL {rel}（exit {code}）")
    if smoke_ok:
        print("  6 个 CLI 全部 exit 0")
    print()
    results.append(("4/4 CLI 冒烟", smoke_ok))

    failed = [name for name, ok in results if not ok]
    if failed:
        print("CI: 失败 —— " + "；".join(failed))
        return 1
    print("CI: 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
