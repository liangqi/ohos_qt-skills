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

编码：中文 Windows 的默认代码页是 GBK，子进程输出里的 UTF-8 字节会让
`subprocess` 的读取线程抛 `UnicodeDecodeError`（栈在 `_readerthread`，
看起来完全不像编码问题）。这里统一三件事，缺一不可：
  ① 本进程 stdio 强制 UTF-8；
  ② 传给子进程的环境里带 `PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8`；
  ③ 子进程输出按 UTF-8 解码并 `errors="replace"`（历史日志里的坏字节不该让门禁崩）。
"""

from __future__ import annotations

import os
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
    "tools/ohos-platform-audit.py",
    "portgraph/portgraph.py",
]


def _force_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass


def _child_env() -> dict:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.setdefault("PYTHONLEGACYWINDOWSSTDIO", "0")
    return env


def run(title: str, argv: list[str]) -> bool:
    print(f"== {title} ==")
    try:
        code = subprocess.call([PY] + argv, cwd=ROOT, env=_child_env())
    except OSError as exc:                     # 解释器/脚本缺失
        print(f"  无法执行：{exc}")
        return False
    print()
    return code == 0


def main() -> int:
    _force_utf8_stdio()
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
            proc = subprocess.run([PY, rel, "--help"], cwd=ROOT, env=_child_env(),
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            code = proc.returncode
            if code != 0:
                tail = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
                print(f"  FAIL {rel}（exit {code}）")
                if tail:
                    print("       " + tail.splitlines()[-1][:160])
        except OSError as exc:
            code = -1
            print(f"  FAIL {rel}（{exc}）")
        if code != 0:
            smoke_ok = False
    if smoke_ok:
        print(f"  {len(CLI_SMOKE)} 个 CLI 全部 exit 0")
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
