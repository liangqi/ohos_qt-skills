---
name: ohos-qt-skills
description: |
  Entry point of the Qt → HarmonyOS porting repo: makes "can it be ported, how, did it succeed" decidable.
  Use when porting a Qt/C++ app to HarmonyOS/OpenHarmony; assessing feasibility of a Qt app or its
  dependencies; downloading HarmonyOS arm64 prebuilts (bottles); troubleshooting build/packaging/signing/
  deploy/runtime issues (dlopen, crash, white screen); checking Qt API/module/platform-limit support;
  judging Qt defect vs HarmonyOS limitation vs app misuse; building a local Qt OHOS SDK;
  or capturing lessons into the KB.
  Core: three-state feasibility verdict, dependency roles + closure download; resumable
  migration pipeline (scan → plan → tracked changes → build → HAP → install → G0-G13 gates);
  knowledge (iron rules, QOH patterns, pitfalls, S→C→W→T fault graph); SDK plane (SV0-SV8).
  Triggers: porting, HarmonyOS, Qt OHOS, QtOhosExtras, third-party deps, cross-compile, bottle, HAP, hvigor,
  devecocli, hdc, dlopen, white screen, crash, build error, QOH, 鸿蒙化, 移植 Qt, 三方依赖, 交叉编译, 白屏, 闪退, 构建报错.
metadata:
  author: OpenHarmony PC Developer · ohos_qt-skills maintainers
  category: software-development
  version: 2.3.0
---

# ohos-qt-skills: engineering entry point for porting Qt applications to HarmonyOS

This skill is the repository's main entry point; the other 5 sub-skills each own one section of the pipeline (see §G).
**All commands below are run from the repository root**; path variables that appear in knowledge pages (`QT5_15_OHOS_SDK`,
`OHOS_SDK_NATIVE`, etc.) all come from `ENV.local.md`; don't hard-code local paths in your answers.

There is only one criterion: **the LLM does the reasoning, the tools supply the facts.** Whether a migration succeeded is judged only by the
G0–G13 gates of `qt-ohos-run.py verify` (SV0–SV8 on the SDK side); "it builds", "it's installed", `TIMEOUT`, and "didn't crash within 3 seconds of launch"
are none of them PASS.

Two things in the knowledge layer are worth scanning first on every task: the **golden iron rules** (known pitfalls; go through them before changing code) and the
**QOH error patterns** (machine-matched by `analyze-log`; a hit comes with the root cause and knowledge page references).

## Trigger scenarios

- **Migrating / porting** a Qt project to HarmonyOS (assessing or executing)
- Analyzing a Qt project's **third-party dependencies**, or downloading HarmonyOS arm64 **cross-compiled artifacts / bottles**
- Troubleshooting Qt HarmonyOS **build / packaging / signing / deployment / runtime errors**
- Looking up support for Qt **APIs / modules / platform limitations** on HarmonyOS
- Checking whether a problem **is fixed / whose it is / how to work around it** (fault graph)
- Building, patching, and maintaining a local **Qt OHOS SDK**

---

## Prerequisites

On first use, or when `ENV.local.md` doesn't exist, first run `skills/kb-init/SKILL.md` to initialize the environment
(detection of DevEco Studio / HarmonyOS SDK / Qt OHOS SDK / toolchain, installation guidance, path configuration, validation).
Path variables in knowledge pages (such as `QT5_15_OHOS_SDK`, `OHOS_SDK_NATIVE`) are all defined in `ENV.local.md`.

Pure lookup tasks (reading knowledge pages, checking API support) need neither initialization nor a local toolchain.

## Instructions

1. **First decide which path the task belongs to.** Read the routing table in `_index/_task-routing.md` (16 task types A–S);
   don't just dive in from memory. Pure lookup tasks don't need a local toolchain; if you'll touch build/install/signing, first confirm
   `ENV.local.md` and tool availability per §Prerequisites.

2. **For any "migrate/port/port to HarmonyOS/feasibility assessment" request, step 0 must be the feasibility assessment** (§A). Run
   `portgraph analyze` to get the three-state verdict `portable` / `blocked` / `uncertain`, then run `deps` to see
   dependency roles and version ranges, and `fetch-deps --dry-run` to preview the closure when needed. **With ≥3 third-party dependencies, do not
   judge feasibility one by one by hand**; always go by the closure output.

3. **Present the conclusion in terms the user can decide on.** `blocked` must name the specific blockers and the guard evidence (only an unconditional
   `ohos-active` hit on a core path counts as a hard blocker; optional branches can be let through); `uncertain` must **list item by item**
   the gaps that "have no bottle and need cross-compiling from source"; don't just say vaguely "there are risks".

4. **To actually migrate, go through the execution layer** (§B): `scan → plan → patch → config → build → package →
   install → launch → smoke → verify`. Each step persists state in the target project's `.qt-ohos/`;
   after an interruption resume with `status` / `resume`; **don't rely on conversation memory to keep track of progress**.

5. **Only make allowlisted automatic modifications.** All automatic changes go into `.qt-ohos/changes.json` and the patches directory,
   so they can be rolled back and reviewed; do not blindly widen `Q_OS_LINUX` guards (on HarmonyOS `Q_OS_OHOS` implies `Q_OS_LINUX`),
   and do not comment out functional code to get the build to pass. Changes that need human judgment go into the assisted/manual sections of the migration plan.

6. **Machine-match errors first, then read knowledge pages** (§B). Run
   `python tools/qt-ohos-run.py analyze-log <log>`; a matching QOH pattern brings out the root cause and
   knowledge page references; follow them into `problems/`, or first scan the golden iron rules in
   `semantic/qt-harmonyos-golden-rules.md`. Before building a large C++ project, run `cpp20-gap-scan` first instead of hitting errors round after round.

7. **To decide "whose problem this is", check the fault graph; don't guess** (§D). Check the symptom index in `faults/_registry.md` or
   `faults/_graph.yaml`: C pages state the classification (defect, will be fixed / limitation, platform limitation → alternative),
   the responsible domain, workarounds, and the open ticket status. Filing an upstream ticket requires a demo or log + stack level evidence.

8. **If a tool is unavailable, stop and report; don't pretend to succeed** (§F-7). Before build/install/signing/log collection, verify that
   `devecocli`, `hdc`, and the Qt kit are available; `devecocli` lookup order: `DEVECO_CLI` in `ENV.local.md`
   → PATH → npm global → bundled with DevEco (**it isn't necessarily installed with DevEco Studio**). If it's missing, output the install
   command and stop; do not continue with guessed paths.

9. **Switch to the SDK plane when you need to rebuild or patch Qt**: `tools/qt-sdk-run.py`
   (`patch-import` → `patch-apply` → `build` → `install` → `verify` → `release`).
   Patches must be traceable (the manifest records source and applicable versions); temporary test versions go through `release --temp`;
   don't edit the SDK directory by hand.

10. **Wrap up with a machine verdict** (§E). `verify` exit codes: `0` PASS / `3` PARTIAL (build chain passed, device side not done) / `1` FAIL — in scripts don't treat any non-zero as a crash. On delivery give `verify`'s gate results (PASS/PARTIAL/FAIL +
    numbers of the failed items), not "should be fine now"; for a partial pass, list the gates that didn't pass and why.

11. **Knowledge capture is part of the process, not optional.** New pitfalls go into `faults/_drafts/` first (with a reproduction demo or
    log + stack), then get merged through the editor-in-chief gate in `skills/kb-iterator/SKILL.md`; after changing `faults/_data/`
    or a C page you must run `python tools/faults-build.py build` to rebuild the derived artifacts, with zero ERRORs from `check`,
    and use `review` to scan for due and not-closed items.

12. **After changing the repository, run its own tests first**: `python -m unittest discover -s tests` (consistency/engine/scan)
    and `python tools/faults-build.py check`. Numbers in the docs are constrained by the consistency tests; when counts change, update
    `README.md`, `SKILL.md`, `AGENTS.md`, and the index pages under `_index/` in sync.

---

## A. Feasibility assessment and dependency closure (portgraph, mandatory step 0)

```bash
# First use: build the graph data (automatically fetches the Harmonybrew 4741 formulae + cmd-pkgs 1248
# prebuilt package data sources; one-time, needs a network connection)
python portgraph/portgraph.py ingest all

python portgraph/portgraph.py scan <local project path>         # or clone <git-url>
python portgraph/portgraph.py analyze <app> --summary     # portability verdict
python portgraph/portgraph.py deps <app or path>            # dependency role analysis (see §C)
python portgraph/portgraph.py fetch-deps <app> --dry-run  # dependency closure preview
```

Verdicts:

- `portable` — can be ported to HarmonyOS directly (no hard blockers; dependencies have prebuilt artifacts or can be cross-compiled with the project);
- `blocked` — there are hard blockers: unsupported platform APIs / Qt modules / required dependencies;
- `uncertain` — there are unknown dependencies, i.e. gaps that need cross-compiling from source.

**Discipline**:

- With ≥3 third-party dependencies, **do not** judge feasibility one by one by hand; go by the closure analysis output;
- `unknowns` (dependencies without a bottle) must be **reported to the user explicitly, item by item** — this is the list of gaps for cross-compiling from source;
- a blocked verdict requires examining the blockers' guard evidence (only an unconditional `ohos-active` hit on a core path counts as a hard blocker;
  optional branches can be let through).

See `portgraph/README.md`, `portgraph/docs/deps-report.md`, and `portgraph/docs/fetch-deps.md` for details.

**Large repository retrieval resilience**: on a weak network `clone` of a large pack is easily cut off (`curl 56` early EOF) — if 2-3 retries
still fail, switch to a **resumable codeload tarball download** (GitHub: `https://codeload.github.com/<owner>/<repo>/tar.gz/refs/heads/<branch>`,
or `.../tar.gz/<tag|sha>`), unpack it into the portgraph workspace, and `scan` it in as usual.

## B. Full migration pipeline commands

```bash
python tools/qt-ohos-run.py doctor            # environment check (cmake / Qt kit / SDK / hvigor / JDK / hdc / device)
python tools/qt-ohos-run.py scan <project dir>   # pre-scan + risk report from 19 rules
python tools/qt-ohos-run.py plan              # migration plan (auto/assisted/manual)
python tools/qt-ohos-run.py patch             # allowlisted automatic fixes (tracked)
python tools/qt-ohos-run.py config set qt_sdk_prefix <Qt OHOS SDK path>
python tools/qt-ohos-run.py build             # G3 build
python tools/qt-ohos-run.py build --record-only --artifacts "build-ohos/*.so" \
                                              # external cross-compilation already succeeded: only register the result, don't rerun
python tools/qt-ohos-run.py package           # G5 package the HAP (Qt6 automatically uses _make_hap / harmonydeployqt6 + DT_NEEDED closure check)
python tools/qt-ohos-run.py sign              # devecocli generates signing material; without devecocli, prints the six-item checklist
python tools/qt-ohos-run.py install           # G6 hdc install on device (POSIX paths automatically converted to native local form)
python tools/qt-ohos-run.py launch            # G7 launch (ability taken from mainElement in module.json5)
python tools/qt-ohos-run.py smoke             # G8 crash-window check (SKIP if install/launch didn't pass; never judged PASS)
python tools/qt-ohos-run.py smoke-interact    # G10 machine evidence: screenshot → click → screenshot again; humans still keep the verdict
python tools/qt-ohos-run.py verify            # G0-G13 gates (the only success criterion)
python tools/qt-ohos-run.py libcheck <lib> --level built|probed --evidence "..."
                                              # library-level progress: built = compiles and links, probed = works on the device
python tools/qt-ohos-run.py mark-risk --rule R003 --evidence "changed in a.cpp:120"
                                              # G2 only accepts "handled" markers that carry evidence
python tools/qt-ohos-run.py package --record-only --hap entry/build/.../app.hap
                                              # external packaging: only register the HAP
```

**Platform-layer porting pre-check** (run it first when porting layer by layer; it catches things much earlier than link-time errors):

```bash
python tools/ohos-platform-audit.py <app>/SourceFiles/platform
#   header-dispatch files must name both Q_OS_OHOS and Q_OS_HARMONY (or use the compiler macro __OHOS__);
#   a non-zero exit code blocks
python tools/ohos-platform-audit.py <platform-dir> --undefined link.log
#   lists the symbols in the link log that "no ohos/ implementation ever mentions"
```

One-shot mode: `migrate <project dir>` (chains everything automatically, pausing with guidance at shell-project generation that needs a human;
templates are in `templates/qt-ohos-app/`); to resume across sessions: `status` / `resume --run`.

**C++20 gap pre-check (before building a large C++ project)**: OHOS clang15/libc++15 lacks several C++20 features,
and hitting errors round after round at compile time is expensive. Scan first, then build:

```bash
python tools/cpp20-gap-scan.py scan <src>          # 8-rule gap report
python tools/cpp20-gap-scan.py fix <src> --apply   # automatic fixes for mechanical items
```

(The rules are aligned with `problems/build-clang15-libcpp15-cpp20-gaps.md`.)

**Machine diagnosis immediately on build failure** (QOH error patterns; a matching entry comes with the root cause, diagnosis steps, and knowledge page references):

```bash
python tools/qt-ohos-run.py analyze-log <log file>
```

**Wrap-up actions**: `finish` produces the report; for new problems use `draft "<title>"` to capture a draft, and after verification
`promote QOHxxx` to make it official; `recipes <project>` searches for similar past migration cases (ranked by similarity in `episodic/`).

## C. Dependency role analysis and prebuilt artifact download

### Dependency role analysis (deps)

```bash
python portgraph/portgraph.py deps <app or path> [--json]
```

Answers "what does this project actually depend on" by role; each dependency comes with `file:line` evidence and a version range check
(satisfied / conflict):

| Role | Meaning | Handling |
|------|---------|----------|
| link | Needs build artifacts (headers + libs) | Must have HarmonyOS cross-compiled artifacts |
| build-tool | Build-machine tool (cmake/protoc…) | Not deployed to the device |
| runtime | Transitive-closure .so + dlopen | If missing on the device it won't start; no sign at build time |
| test | Used only for tests | Can be skipped |
| vendored | Source shipped with the project | Cross-compiled along with the project |
| env | Environment dependency declared in CI scripts | Weak dependency |

(There are also provided = supplied by a Qt module, and optional = guarded by an option that defaults to OFF.)

### Downloading HarmonyOS prebuilt artifacts (fetch / fetch-deps)

```bash
# One or more packages (arm64-ohos bottles, with include/ + lib/ + cmake config)
python portgraph/portgraph.py fetch "zlib,jsoncpp,openssl@3"

# One-step download of the app-level dependency closure (recommended; preview with --dry-run first)
python portgraph/portgraph.py fetch-deps <app> --dry-run
python portgraph/portgraph.py fetch-deps <app>            # download + manifest
```

`fetch-deps` does all of this automatically: look up direct links in the database → download → sha256 check → unpack into `workspace/ohos-libs/`
→ recreate `.so` symlinks on Windows/NTFS → output CMake/qmake integration snippets. Each manifest item carries a status
decision table (downloaded / already_local / covered / provided / cmd_only / need_port / test /
failed); only `need_port` / `failed` need to be handed to a human for cross-compiling from source.

### Key points for cross-compilation integration

- **CMake**: `-DCMAKE_PREFIX_PATH=<bottle path> -DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=BOTH` (iron rule)
- **qmake**: `LIBS += -L<bottle>/lib -lfoo` (the `-l` list comes from the fetch output)
- On Windows a `.so` can only be linked, not run; it must be deployed to `entry/libs/arm64-v8a/` to go onto a device
- Runtime dependencies must be pulled in fully and recursively (fetch-deps handles this); anything missed fails at `dlopen` on the device

## D. Knowledge lookup entry points

| What you want to do | Entry point |
|---------------------|-------------|
| Task routing (look here first when a request arrives) | `_index/_task-routing.md` |
| Scan the iron rules to avoid known pitfalls | `semantic/qt-harmonyos-golden-rules.md` |
| Hit an error (step one) | `problems/_lookup.md` (or `analyze-log` machine matching) |
| Is a problem fixed / whose is it / how to work around it | `faults/_registry.md` §symptom index |
| API replacement | `semantic/qt-harmonyos-api-mapping.md` + `qt-harmonyos-code-patterns.md` |
| Module support status | `semantic/qt-harmonyos-modules.md` |
| Platform limitations | `semantic/qt-harmonyos-platform-limits.md` |
| The whole knowledge picture | `_index/_map.md` (one-sentence summary per page) |

The fixed loading chain: `_task-routing → golden-rules → _map → read pages as needed → follow refs deeper`.

## E. Success criteria

| Scenario | The only criterion | Common misjudgment |
|----------|--------------------|--------------------|
| Application migration | G0–G8 of `qt-ohos-run.py verify` all pass (PASS) | "It builds", "it's installed" |
| Partially done | `PARTIAL`: build/packaging passed but the device side isn't verified; list the failed gates item by item | Reported as PASS |
| SDK build | SV0–SV8 of `qt-sdk-run.py verify` all pass | "install finished" |
| Fault classification | The C page has `evidence_type` (demo / log + stack / statically decidable) + a closed loop with no gaps | Guessing the root cause from symptoms |
| Knowledge base health | Consistency tests all green + zero ERRORs from `faults-build check` | The pages open |

**TIMEOUT is never PASS.** A `FAIL` must report the failure + remaining problems (QOH numbers).

## F. Discipline red lines

1. **Success is decided only by tools**: application migration by `verify` (G0–G13), SDK builds by SV0–SV8;
   TIMEOUT is never PASS.
2. **Do not blindly widen `Q_OS_LINUX` guards**: on HarmonyOS `Q_OS_OHOS` implies `Q_OS_LINUX`,
   so `#ifdef Q_OS_LINUX` branches already compile on HarmonyOS — such changes require human review
   (see `semantic/qt-harmonyos-api.md`).
3. **Every automatic modification is tracked**: `.qt-ohos/changes.json` + `patches/` in the target project,
   rollback-able and reviewable; untracked manual edits are forbidden.
4. **Knowledge feeds back**: new problems go through `draft` → `promote`; after changing the fault library's source of truth you must run
   `python tools/faults-build.py build` to rebuild derived artifacts; merging drafts goes through the editor-in-chief gate (reproduction demo must be run +
   human verification).
5. **Dependency decisions aren't made by hand**: feasibility with ≥3 third-party libraries goes by the portgraph closure analysis output (§A).
6. **Evidence standard**: classifying a problem as Qt-framework-side requires a reproduction demo or debug log + stack (pure hearsay/guesses are not accepted);
   defects filed upstream require demo/logs level evidence; Qt-side reproduction logic is concentrated in a single `main.cpp` with numbered reproduction steps.
7. **Tool availability pre-check**: before starting any build/install/signing/log collection work, locate and verify the toolchain
   (`devecocli --version`, `hdc version`, Qt kit existence). `devecocli` lookup order:
   `DEVECO_CLI` in `ENV.local.md` → PATH → npm global → bundled with DevEco (see
   `ohos-common-kb-public/procedural/deveco-cli-usage-rules.md` §Tool availability pre-check).
   If resolution fails, immediately tell the user what's missing and the install command; do not continue with guessed paths.
8. **End-of-turn discipline (operational level)**: in non-interactive CLI sessions (`opencode run` / `claude -p`, etc.)
   **end of turn = session exit, and no mechanism will wake you up**.
   - **Do not "delegate to background agents and then wrap up waiting"** — once the main turn exits, child processes lose their coordinator, finish their own work, and
     disband on the spot (the cause of death in two rounds of testing).
   - Long tasks (cloning/building/sub-agents) must **wait synchronously for completion within the current turn**, or be run sequentially yourself;
     if you really need parallelism, only blocking waits within the session are allowed (shell foreground, `Wait-Process`).
   - Before the pipeline reaches the `verify` terminal state or an explicit human confirmation point, do not output a summary and stop; if you really must abort,
     persist state to `.qt-ohos/` and state how to resume.
9. **Don't write local absolute paths or credentials**: knowledge pages use only the variable names from `ENV.local.md`.

## G. Sub-skills

| Skill | Purpose |
|-------|---------|
| `skills/kb-init/SKILL.md` | Environment initialization (detect dependencies, installation guidance, generate `ENV.local.md`) |
| `skills/qt-app-porting/SKILL.md` | Automated migration details (workflow / gate semantics / human touchpoints) |
| `skills/qt-sdk-forge/SKILL.md` | Qt SDK build, patch application, and version management (SV0–SV8 gates) |
| `skills/task-dispatcher/SKILL.md` | Multi-agent collaboration dispatch (task ledger / handover envelopes / flow log) |
| `skills/kb-iterator/SKILL.md` | Knowledge base iteration (draft merge gate / index regeneration / fact checking) |

The multi-agent collaboration contract (interface cards / handover envelopes / human touchpoint levels) is in `_index/_agent-mesh.md`.

## H. Version baseline

- Document version: v2.3.0 (change history in [CHANGELOG.md](CHANGELOG.md))
- Qt framework validation baseline: Qt 5.15.16 (tqtc/harmonyos-5.15.16) / Qt 5.12.12
  (tqtc/harmonyos-5.12.12); see the final table of [AGENTS.md](AGENTS.md)
- Environment variable list: `ENV.md`; real values go in `ENV.local.md` (not checked in)

## I. Reference entry points

- Repository overview, architecture, and capabilities: [README.md](README.md)
- Environment dependencies and first-time setup: [SETUP.md](SETUP.md)
- Agent behavioral contract and execution discipline: [AGENTS.md](AGENTS.md)
- Task routing (15 types): [_index/_task-routing.md](_index/_task-routing.md)
- Knowledge map: [_index/_map.md](_index/_map.md) | Dashboard: [_index/_dashboard.md](_index/_dashboard.md)
- Error quick reference: `problems/_lookup.md` | Fault registry: `faults/_registry.md`
- Feasibility graph: `portgraph/README.md`
