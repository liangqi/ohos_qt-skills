#!/usr/bin/env python3
"""Repository gate -- pure standard library, cross-platform (runs on Windows without bash).

    python _scripts/ci.py            # run every gate; the exit code is the verdict
    bash _scripts/ci.sh              # same as above (thin shell wrapper that forwards here)

The four gates are exactly the same as `ci.sh`:
  1. Repository self-check (contract/structure/references/index/release manifest/hygiene, 10 categories)
  2. Fault base source of truth <-> derived artifacts
  3. Test cases (consistency + engine + scan)
  4. CLI smoke test (every CLI's --help must exit 0)

The release manifest does not take part in the verdict: on an ordinary commit it is necessarily a
"stale snapshot"; at release time reconcile it separately with
`python _scripts/gen-manifest.py --check --strict`.

Encoding: the default code page on Chinese-locale Windows is GBK, and UTF-8 bytes in a child
process's output make `subprocess`'s reader thread raise `UnicodeDecodeError` (the stack is in
`_readerthread`, and it looks nothing like an encoding problem). Three things are unified here,
and all three are required:
  (1) this process's stdio is forced to UTF-8;
  (2) the environment passed to child processes carries `PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8`;
  (3) child output is decoded as UTF-8 with `errors="replace"` (bad bytes in historical logs
      should not crash the gate).
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
    except OSError as exc:                     # interpreter/script missing
        print(f"  cannot execute: {exc}")
        return False
    print()
    return code == 0


def main() -> int:
    _force_utf8_stdio()
    results: list[tuple[str, bool]] = []
    results.append(("1/4 repository self-check (contract/structure/references/index/release manifest/hygiene)",
                    run("1/4 repository self-check (contract/structure/references/index/release manifest/hygiene, 10 categories)",
                        ["_scripts/verify.py"])))
    results.append(("2/4 fault base source of truth <-> derived artifacts",
                    run("2/4 fault base source of truth <-> derived artifacts", ["tools/faults-build.py", "check"])))
    results.append(("3/4 test cases (consistency + engine + scan)",
                    run("3/4 test cases (consistency + engine + scan)",
                        ["-m", "unittest", "discover", "-s", "tests"])))

    print("== 4/4 CLI smoke test (--help all exit 0) ==")
    smoke_ok = True
    for rel in CLI_SMOKE:
        try:
            proc = subprocess.run([PY, rel, "--help"], cwd=ROOT, env=_child_env(),
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            code = proc.returncode
            if code != 0:
                tail = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
                print(f"  FAIL {rel} (exit {code})")
                if tail:
                    print("       " + tail.splitlines()[-1][:160])
        except OSError as exc:
            code = -1
            print(f"  FAIL {rel} ({exc})")
        if code != 0:
            smoke_ok = False
    if smoke_ok:
        print(f"  all {len(CLI_SMOKE)} CLIs exit 0")
    print()
    results.append(("4/4 CLI smoke test", smoke_ok))

    failed = [name for name, ok in results if not ok]
    if failed:
        print("CI: FAILED -- " + "; ".join(failed))
        return 1
    print("CI: all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
