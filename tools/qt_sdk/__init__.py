"""qt_sdk - execution plane for the qt-sdk-forge agent skill.

Python replacement for the bash scripts that used to cover the Qt OHOS SDK
lifecycle (detect-env / clone-qt-src / compile-qt-sdk, see
skills/kb-init/scripts/).  Unlike the bash versions this runs natively on
Windows, which is the primary build host (see semantic/qt-harmonyos-build.md
"Qt5 source incremental build & install").

Layers:
    state.py      .qtsdk/ state machine + command evidence + task budget
    envcheck.py   SV0 environment check + ENV.local.md bridge
    srctree.py    source tree inspection/clone + upstream evolution check
    patching.py   patch registry + import/apply/revert/export
    building.py   configure / build / install (variant parameterised)
    releasing.py  version release / manifest / ENV switch
    verify.py     SV0..SV8 gates (the only success criterion)

Design rules (inherited from tools/qt_ohos):
- LLM reasons, tools decide facts: success == gate result, never "looks fine"
- every command result is recorded as evidence; TIMEOUT is never PASS
- Windows: mingw32-make must run with SHELL=cmd.exe (bash eats backslashes)
"""

from __future__ import annotations

import sys
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent.parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from qt_ohos import yaml_lite  # noqa: E402  (shared, dependency-free)

__all__ = ["yaml_lite"]
