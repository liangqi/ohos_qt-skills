---
name: qt-app-porting
description: |
  Automated migration of Qt applications to HarmonyOS. Through the unified CLI tools/qt-ohos-run.py, it turns the knowledge base's
  migration knowledge into an executable, resumable, verifiable, and distillable engineering closed loop:
  scan → risk report → migration plan → tracked automatic changes → build → package → install →
  launch → crash check → verification gates (G0-G12) → report → knowledge distillation.
  Triggered when the user says "migrate/port this Qt project to HarmonyOS", "auto-migrate",
  "run the migration", "verify the migration result", or "analyze this build/runtime log".
  Triggers (incl. Chinese): 鸿蒙化, 迁移, 移植, 自动迁移, 跑一遍迁移, 验证迁移结果, 分析日志.
---

# qt-app-porting: automated migration of Qt applications to HarmonyOS

> Design principle (consistent with the knowledge base): **the LLM does the reasoning, the tools provide the facts.**
> The agent must not declare a migration successful because "it looks like it compiled" — success is judged solely by
> the gate results (G0-G12) of `qt-ohos-run verify`.

## When to trigger

- The user gives a Qt project directory and asks to migrate / port it / port it to HarmonyOS

- The user asks to verify an already-migrated project ("what makes you say the migration succeeded?")

- The user gives a build / runtime log and asks to locate the error (this can also go through \[E] Build troubleshooting; this skill provides machine matching)

## Workflow (the agent executes these in order)

### Step 0 Environment detection (G0 prerequisite)

Confirm the knowledge base environment is usable (`ENV.local.md` exists; if not, run `skills/kb-init` first).

### Step 1 Initialize + pre-scan

```bash
python tools/qt-ohos-run.py scan <project-dir>
```

Produces `.qt-ohos/scan.json`: build system, Qt version/modules, source inventory, third-party dependencies, and the
**Qt HarmonyOS Porting Risk Report** (hits from the machine rules in knowledge/rules/R\*.yaml).

Read the Critical/High risks to the user, and load the knowledge pages named in each finding's `kb` field.
If a hit is in a non-HarmonyOS platform file (`*_win.cpp`/`*_mac.mm`/a directory containing `xcb`) or inside
a conditional block such as `#ifdef Q_OS_WIN`, it's lowered one level and tagged with `scope` — that code isn't even
compiled in a HarmonyOS build.

Classify third-party dependencies before touching anything:

```bash
python portgraph/portgraph.py deps <app>          # each entry comes with file:line evidence
python portgraph/portgraph.py fetch-deps <app>    # pull the ones that have bottles into ohos-libs/
python tools/qt-ohos-run.py pkgconfig --relocate  # rewrite build-machine paths in .pc files to local ones
python tools/qt-ohos-run.py pkgconfig --write-shim  # for hosts without pkg-config
```

Unresolved dependencies are split into "not in the knowledge base" (a real gap) and "name didn't match" (cases like `ada`→`ada-url`;
the entry comes with a hint about similar packages); the project's own subdirectories are never treated as third-party libraries.

### Step 2 Generate the migration plan

```bash
python tools/qt-ohos-run.py plan
```

Produces `.qt-ohos/migration-plan.json`: three kinds of steps, auto / assisted / manual.
**Manual steps must be executed by the agent one by one**; each one comes with knowledge base references (refs).

### Step 3 Tracked automatic changes

```bash
python tools/qt-ohos-run.py patch
```

Only allowlisted fixes are applied (e.g. the qmake `:!ohos` scope, B9; `CMAKE_AUTORCC`, B10).
Pure CMake projects / projects without qrc often have none that apply; in that case it prints a **candidate list**
(file:line + why + how to change it) for a human or the agent to judge — it won't stay silent just because
"it's not confident enough to change things automatically".
Every change is tracked: `.qt-ohos/changes.json` + `originals/` (revertible) +
`patches/000x-*.patch` (can be committed and reviewed).

⚠️ **Don't blindly widen platform guards**: on the HarmonyOS branch, `Q_OS_LINUX` **is already defined**
(Qt 6.12+ defines `Q_OS_HARMONY` and derives `Q_OS_LINUX` from it; the Qt 5.15 kit additionally has
`Q_OS_OHOS`), so `#ifdef Q_OS_LINUX` branches get compiled on HarmonyOS. Such locations can only be reviewed manually;
see G3 and the macro-order notes in `semantic/qt-harmonyos-golden-rules.md`.

### Step 4 Configure the build environment and run it

Check first, then configure — **don't** skip doctor and go straight to `build`; if the Qt6 prebuilt kit is missing any single piece,
the failure will be impossible to diagnose:

```bash
python tools/qt-ohos-run.py doctor     # cmake/make/Qt kit/OHOS native SDK/hvigor/JDK/hdc/device
```

The Qt 6 prebuilt kit and the Qt 5.15 suite are two completely different build recipes: Qt6 requires
`qt_host_sdk` (the host kit) + `ohos_sdk_native`; `build` automatically passes
`CMAKE_TOOLCHAIN_FILE=<kit>/lib/cmake/Qt6/qt.toolchain.cmake`,
`QT_CHAINLOAD_TOOLCHAIN_FILE=<native>/build/cmake/ohos.toolchain.cmake`, and
`QT_HOST_PATH`; `package` goes through `_make_hap` / `harmonydeployqt6` by itself,
so you no longer need to write the packaging commands by hand. For the full recipe and the five hvigor environment variables, see
`procedural/qt6-ohos-windows-cli-deploy.md`.

```bash
python tools/qt-ohos-run.py config set qt_sdk_prefix  <kit>/harmonyos_arm64_v8a
python tools/qt-ohos-run.py config set qt_host_sdk    <kit>/mingw_64          # required for Qt6
python tools/qt-ohos-run.py config set ohos_sdk_native <sdk>/native          # required for Qt6
python tools/qt-ohos-run.py config set deveco_path    <DevEco Studio install dir> # hvigor/JDK/SDK are derived from it
python tools/qt-ohos-run.py config set bundle_name    com.example.app         # G8 log filtering
python tools/qt-ohos-run.py config set compatible_sdk "5.0.0(12)"             # aligned with build-profile
python tools/qt-ohos-run.py build      # G3: cross-configuration + cmake --build
python tools/qt-ohos-run.py package    # G5: automatic _make_hap / harmonydeployqt6 + HAP dependency-closure check
python tools/qt-ohos-run.py sign       # optional: devecocli generates signing materials and writes build-profile
python tools/qt-ohos-run.py install    # G6 hdc install (paths converted to the native local form automatically)
python tools/qt-ohos-run.py launch     # G7 aa start (the ability is read from mainElement in module.json5)
python tools/qt-ohos-run.py smoke      # G8 crash-window check
python tools/qt-ohos-run.py smoke-interact   # G10 machine evidence: screenshot → click → screenshot again and compare
```

Every step has a timeout, an exit code, and evidence in `.qt-ohos/logs/`; **TIMEOUT is never PASS**.

Keys of `.qt-ohos/env.json` (all settable with `config set`; defaults in the last column):

| Key | Purpose | Default |
|---|---|---|
| `qt_sdk_prefix` | Qt for OHOS SDK prefix (Qt5 uses `-DCMAKE_PREFIX_PATH`; Qt6 discovers the toolchain from it) | — |
| `qt_host_sdk` | Qt6 host kit (`mingw_64`), turned into `QT_HOST_PATH`; without it configure FAILs outright | — |
| `ohos_sdk_native` | OHOS native SDK, turned into `OHOS_SDK_NATIVE` + `-DOHOS_ARCH` | — |
| `generator` / `make_program` | Generator (Windows defaults to `MinGW Makefiles`; **Ninja spins idle in the sandbox**) | Derived per platform |
| `build_cwd` | Parent directory of the build directory (set it when the CMake project is in a subdirectory) | Project root |
| `build_command` | A whole custom build command (if given, the built-in branches aren't used) | — |
| `cmake` / `build_dir` / `cmake_args` | Tunables for the cmake branch; `cmake_args` is a single command-line string that G3 splits by shell rules | `cmake` / `build-ohos` / empty |
| `package_target` | Packaging target name (default `<target>_make_hap`) | Automatic |
| `harmonyos_build` / `package_dir` | Packaging output location (Qt6 default `<build_dir>/harmonyos-build`) | Auto-detected |
| `package_command` | Custom packaging command (an escape hatch; if given, neither built-in path is used) | Built-in |
| `hvigor` / `java_home` / `deveco_sdk_home` / `hvigor_home` / `npm_cache` | The five hvigor settings; the first three default to values derived from `deveco_path`, the last two default to writable directories under `.qt-ohos/` | Automatic |
| `hap_glob` | HAP artifact pattern; `-signed` is preferred | `**/build/**/*.hap` |
| `hap_allowed_libs` | soname prefixes allowed to be left out of the package (by default, everything outside the system-library allowlist must go into the HAP) | Empty |
| `bundle_name` | **G8 filters logs by it**; if unset, the whole device buffer is captured and G8 can reach at most PARTIAL | Empty |
| `ability_name` | The ability to launch; defaults to `mainElement` from `module.json5` (`QAbility` for Qt6) | Automatic |
| `process_name` | G8's second filter term (HarmonyOS process names are often the last segment of the bundle, which is the default) | Last bundle segment |
| `compatible_sdk` | Compared with `compatibleSdkVersion` in `build-profile.json5`; aligned automatically before packaging, and mismatches are stopped | The SDK's actual value |
| `crash_wait_sec` | Seconds to watch for crashes after launch | 8 |
| `hdc` / `devecocli` | Tool paths (give absolute paths when they aren't on PATH) | PATH lookup |
When the build fails, analyze the log immediately:

```bash
python tools/qt-ohos-run.py analyze-log <log-file>
```

The error pattern engine (knowledge/errors/QOH\*.yaml) reports the matching QOH entries, root causes,
diagnosis steps, and the corresponding knowledge pages; the agent follows `refs` to read the pages, fixes the problem, and reruns the corresponding step.

### Step 5 Verification gates (the only success criterion)

```bash
python tools/qt-ohos-run.py verify
```

Prints the G0-G12 gate table. Decision rules:

- `Result: PASS` → only when G0-G8 all pass can you report the migration as successful

- `Result: PARTIAL` → built/packaged successfully but device-side verification isn't complete; **you can only report partial completion**

- `Result: FAIL` → report the failure + the remaining problems (QOH numbers)

### Step 6 Report + knowledge feedback

```bash
python tools/qt-ohos-run.py finish
python tools/qt-ohos-run.py draft "<new problem title>"   # when you hit a new problem
python tools/qt-ohos-run.py promote QOHxxx         # promote a draft once it's verified
```

**Success criterion**: if the migration ends without producing any reusable knowledge, proactively prompt the user to contribute a draft.
The next migration can use `qt-ohos-run recipes <project>` to search similar historical cases
(episodic/, ranked by similarity).

## One-shot mode

```bash
python tools/qt-ohos-run.py migrate <project-dir>
```

Automatically chains the automatable parts of Steps 1-4; when it reaches a `project_generation` step that needs a human
(creating the HarmonyOS shell project; for templates see `templates/qt-ohos-app/` and the template built into the Qt source,
`qtbase/src/harmonyos/templates`), it pauses and gives guidance. To resume across sessions:

```bash
python tools/qt-ohos-run.py status          # see which phase it stopped at
python tools/qt-ohos-run.py resume --run    # continue from the checkpoint
```

Task budget (keeps long tasks from running away): `QT_OHOS_TASK_BUDGET_SEC`,
`QT_OHOS_TASK_DEADLINE` (HH:MM); when exceeded, a checkpoint is written automatically and it exits with code 2.

## Relationship with the rest of the knowledge base

| Layer              | Carrier                                                    |
| ------------------ | ---------------------------------------------------------- |
| Task Router        | `_index/_task-routing.md` (route code \[P])                 |
| Knowledge Plane    | `semantic/` `procedural/` `episodic/` `problems/`          |
| Execution Plane    | `tools/qt-ohos-run.py` + `tools/qt_ohos/`                  |
| State Plane        | `.qt-ohos/` inside the target project (state/manifest/changes/evidence) |
| Verification Plane | `verify` gates G0-G12                                      |
| Learning Plane     | `knowledge/rules/` `knowledge/errors/` `knowledge/drafts/` |

## Multi-agent interface and human-in-the-loop

The communication contract is in `_index/_agent-mesh.md` (the single source of truth; this section is only a summary; the agent name is app-porter).

- Inbound: `task-order` (dispatcher), `assessment` + `deps-manifest` (port-assessor),
  `sdk-release` (sdk-forge, consumed via `config set qt_sdk_prefix`)
- Outbound: `task-report` (dispatcher), leads on suspected framework problems handed to framework-analyst,
  `kb-draft` (`draft` / `promote`)
- All handoffs go through ho-\*.yaml envelopes + appends to flow.jsonl; nothing without refs is accepted

Human-in-the-loop points: signing certificates and passwords (H2, never written to disk); non-allowlisted changes — especially `Q_OS_LINUX` guards
(on HarmonyOS `Q_OS_OHOS` implies `Q_OS_LINUX`) — are only patched after manual review (H3); whether to move to the problem chain when verify=FAIL and
no known error pattern matched (H1); one-shot mode pausing at `project_generation` with guidance (H2).
For the full list and level definitions, see `_agent-mesh.md` §5.

## Boundaries

- This skill doesn't rebuild the Qt framework itself (that's the domain of `semantic/qt-harmonyos-build.md`)

- Third-party library builds can hook into the external `build_in_harmonyos` (set the `OHC_RUN` environment variable);
  this knowledge base only detects the dependencies and gives guidance via `semantic/qt-harmonyos-third-party-libs.md`

<br />
