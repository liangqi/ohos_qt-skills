---
name: qt-sdk-forge
description: |
  Local Qt for HarmonyOS SDK engineering plane: builds Qt source (full/incremental), applies and tracks patches,
  manages, releases and maintains local SDK versions, and tracks upstream evolution to update the knowledge base.
  Via the unified CLI tools/qt-sdk-run.py (Python, native on Windows/macOS/Linux) it turns
  SDK engineering knowledge into an executable, resumable, traceable, verifiable closed loop:
  change-proposal import → patch review/apply → build + install → SV0-SV8 gates → version release → ENV sync →
  upstream tracking → patch retirement → knowledge feedback.
  Triggered when the user says "build / rebuild Qt", "patch Qt / apply this change proposal",
  "release an SDK version / a temporary test version", "switch / roll back the SDK version",
  "check upstream for updates (when a build check is needed)", or "maintain the local Qt SDK".
  All Qt SDK builds (any version) and temporary test versions are produced by this agent.
  Triggers (incl. Chinese): 编译 Qt, 重编 Qt, 打补丁, 出 SDK 版本, 临时测试版本, 切换 SDK, 回滚 SDK, 上游演进.
---

# qt-sdk-forge: Qt OHOS SDK building · patches · version management

> Design principle (consistent with the knowledge base): **the LLM does the reasoning, the tools provide the facts.**
> The agent must not declare an SDK usable because "make didn't report errors" — success is judged solely by the SV gate results.
> Likewise, "the patch is applied" doesn't mean "the patch is understood" — every imported change proposal must be reviewed before it's applied.

## Role and boundaries

- This skill is the **execution plane on the SDK engineer's side**. `qt-app-porting` (application migration) explicitly doesn't rebuild the Qt
  framework — that's exactly this skill's job: source + patches → a traceable local SDK version.
- **Responsibility entry point (the only one)**: every request to "build the Qt SDK (5.12/5.15 from source, 6.12 prebuilt registration)" or
  "produce a temporary test version for a change" is routed to this skill and executed by `tools/qt-sdk-run.py`.
- Upstream input: change proposals from other agents / humans (framework fixes, diagnostic logging, upstream backports).
- Downstream output: multiple local SDK versions (5.12 / 5.15 × debug/release × gl/gles variants),
  version manifests, knowledge base evolution updates.
- This skill **doesn't do** application migration or problem diagnosis (that's `framework-issue-analysis`'s job) —
  but it receives the output of both (change proposals / fix-verification requests) and feeds back results.

## When to trigger

- The user asks to build / rebuild Qt (full or incremental install), whatever the version
- The user provides a change proposal / patch file and asks to apply it to the Qt source and release a version (including temporary test versions)
- The user asks to view, switch, roll back, or release local SDK versions
- The user asks to check upstream evolution or to verify "whether the new version fixes some problem" (when a rebuild is needed to verify)
- Periodic maintenance tasks (upstream tracking, patch-stack re-review, faults review linkage)

## Prerequisites

1. `ENV.local.md` exists (if not, run `skills/kb-init` first)
2. On first use, run `python tools/qt-sdk-run.py init` (creates the `workspace/qt-sdk/.qtsdk/`
   state and automatically bridges the path variables from ENV.local.md)
3. Required knowledge pages:
   - `semantic/qt-harmonyos-build.md` (configure arguments, the skip list, the three incremental-build pitfalls)
   - `procedural/framework-issue-analysis.md` §4.3-4.5 (iron rules for generating and cleaning up patches)
   - As needed: `procedural/framework-fix-verification.md` (fix verification),
     `problems/_lookup.md` (check build errors here first), `faults/_registry.md` (root causes linked to patches)
4. **Platform/version/source-acquisition questions** (which platform to build on, which version to build, where the source comes from,
   what to do without a license, whether to use a prebuilt): first check this skill's
   `references/build-matrix.md` — the version × channel decision table, the platform × toolchain matrix,
   the CLI argument vs. configure difference table, and the per-platform manual equivalent commands for when the CLI isn't available are all on that page
5. **Linux support status**: ✅ verified in practice (Ubuntu 22.04 x86_64, 2026-09-19,
   Qt 5.12.12 GLES release → SV0-SV6/SV8 PASS). All Linux adaptations are built into the CLI:
   - `src-clone --method opensource` checks out the POSIX build branch by default and automatically restores
     executable bits (QOH037); CRLF snapshots are rejected
   - The OHOS SDK is obtained from the public OpenHarmony mirror (no Huawei account login needed) and requires
     apiVersion >= 23; see `references/build-matrix.md` §2.1 (QOH041)
   - configure includes `-no-dbus` (QOH039) and dirty-build-directory fingerprint protection (QOH040)
   - The `python` alias is provided automatically by `.qtsdk/pyshim` (QOH038); SV0 checks
     `python3` / `python_alias`
   - On low-memory machines (<= 8GB), limit parallelism with `config set jobs <N>`

## State Plane

State directory: `workspace/qt-sdk/.qtsdk/` (overridable with `--home` or `QT_SDK_HOME`)

```
workspace/qt-sdk/
├── .qtsdk/
│   ├── state.json        # build context: source path/branch/commit/variant/phase checkpoint
│   ├── env.json          # managed by config set (qt_src/build_root/sdk_root/jobs...)
│   ├── patches/          # patch library (P0001-*.patch, git diff format)
│   ├── registry.yaml     # patch registry (see below)
│   ├── inbox/            # ★ external change-proposal tickets (the input interface for other agents)
│   │   └── <proposal-id>/
│   │       ├── proposal.yaml
│   │       ├── patches/0001-*.patch
│   │       └── notes.md
│   ├── builds/           # each build: logs + config.summary snapshot
│   ├── releases/         # release manifests: manifest-<ver>.yaml + RELEASES.md index
│   └── logs/             # full command logs (state.json only keeps the tail as evidence)
└── sdk/                  # SDK output root (directory names follow the existing convention)
```

### Patch registry registry.yaml (one entry per patch)

| Field | Description |
|-------|-------------|
| `id` | Incrementing number, `P0001` |
| `type` | `diagnostic` (diagnostic logging) / `fix` (framework fix) / `backport` (upstream backport) |
| `status` | `imported → applied → built → released → superseded / reverted` |
| `origin` | Originating ticket `proposal-id`, or `manual` |
| `refs` | Linked `faults/C-xxxx` / `QOHxxx` / `problems/` pages / `QTBUG-xxxxx` |
| `base_commit` | The qtbase commit at application time (traceability) |
| `files` | List of files involved |
| `upstream` | Whether it's been submitted upstream, ticket number, status |
| `retire_when` | Retirement condition (usually the release of the upstream fix_version) |

### External change-proposal tickets (proposal.yaml, the input protocol for other agents)

```yaml
id: prop-20260915-001
source: framework-issue-analysis        # or faults-C0002 / human
type: fix                               # diagnostic | fix | backport
motivation: Fix the input method focus-switch race
refs: [faults/C-0003, QTBUG-xxxxx]      # linked knowledge pages and tracking tickets
base: tqtc/harmonyos-5.15.16@962aa625   # base branch and commit
retire_when: Re-review after upstream 5.15.17 is released
expected_verification:                   # expected verification method (corresponds to SV7)
  demo: <reproduction demo path>
  steps: Regress following the C-0003 reproduction steps
```

> **Discipline**: `patch-import` rejects proposals without `refs` outright (machine-enforced) — untraceable
> patches are debt for future version management. When the agent receives a proposal without refs, it first fills in the links (ask the originating
> agent or check `faults/_registry.md`) and then imports it.

## Workflow (the agent executes these in order)

### Step 0 Environment detection (SV0)

```bash
python tools/qt-sdk-run.py env
```

Checks: a valid Qt source tree (`qtbase/` + `qtohosextras/`), `OHOS_SDK_NATIVE` (containing
`llvm/bin/`), on Windows MinGW (`mingw32-make`) + Strawberry Perl, and cmake.
Fix any FAIL first (see the troubleshooting section of `skills/kb-init/references/qt-compile-guide.md`).
If a path is wrong, correct it with `config set` (note that on Windows you must use Windows paths;
`/mnt/c/...` are WSL paths):

```bash
python tools/qt-sdk-run.py config set qt_src <Qt source root>
python tools/qt-sdk-run.py config set ohos_sdk_native <OHOS SDK native>
```

Fetching the source when it's missing (commercial credentials are kept only in memory, never written to disk, and are removed from the remote automatically after cloning;
**for channel selection — version availability, license requirements, prebuilt options — see the
`references/build-matrix.md` §1 decision table**):

```bash
python tools/qt-sdk-run.py src-clone --method commercial --version 5.15 \
  --dest workspace/qt-src/qt5.15 --user <QT_USER> --pass <QT_PASS>
# without a license: --method opensource (the open-source GitCode mirror)
```

### Step 1 Inventory the source and the patch stack (SV1)

```bash
python tools/qt-sdk-run.py status
```

- `verify`'s SV1 machine-checks that **the qtbase working-tree changes = the union of files of the patches registered in registry**;
  any unregistered change is a FAIL; `status` shows the health of the patch stack
- Submodule integrity (QtOhosExtras is in a submodule) is checked by SV1; if it isn't initialized, it reports
  a `git submodule update --init --recursive` hint

### Step 2 Import a change proposal (the external agent interface)

```bash
python tools/qt-sdk-run.py patch-import <proposal-dir>
```

The agent must **understand before importing** (review checklist; the machine-enforced items are built into import):

1. Read the `refs` in proposal.yaml and load the linked knowledge pages (faults C pages / problems pages),
   confirming that the proposal matches the root-cause classification
2. Patch file scope: import only parses the `+++ b/` file list; **the agent must manually verify that the patch
   only contains files relevant to the proposal** (framework-issue-analysis §4.5 iron rule — exclude tracing
   logs for other bugs and experimental code); hunks out of scope must be split out by the originator
3. Conflict detection is guaranteed up front by `patch-apply`'s `git apply --check`

```bash
python tools/qt-sdk-run.py patch-apply P0001     # apply + move the status to applied
python tools/qt-sdk-run.py patch-list            # patch-stack overview
python tools/qt-sdk-run.py patch-revert P0001    # roll back
python tools/qt-sdk-run.py patch-export P0001 --dest <dir>   # export for upstream submission
python tools/qt-sdk-run.py patch-mark P0001 superseded       # fixed upstream; retire it
```

> **Don't blindly widen platform guards**: on HarmonyOS `Q_OS_OHOS` implies `Q_OS_LINUX`,
> so `#ifdef Q_OS_LINUX` branches already get compiled — when reviewing, confirm manually following the macro-order notes in `semantic/qt-harmonyos-api.md`.

### Step 3 Build (full or incremental)

**Full** (new source tree / switching variants; the configure arguments and skip lists follow
`semantic/qt-harmonyos-build.md` and are built into building.py, with separate lists for 5.12 and 5.15.16):

```bash
python tools/qt-sdk-run.py configure --qt 5.15 --render gl --build-type release
python tools/qt-sdk-run.py build        # default timeout 4h, override with --timeout
python tools/qt-sdk-run.py install
```

**Selecting and querying modules** (the default skip list is built in per version and can be adjusted):

```bash
python tools/qt-sdk-run.py modules --qt 5.15          # query: built by default / can be enabled with --with / unsupported on the platform
python tools/qt-sdk-run.py modules --configured       # query: modules actually installed in the active variant's SDK
python tools/qt-sdk-run.py configure --qt 5.15 --with qtconnectivity   # remove from the default skip list (enable)
python tools/qt-sdk-run.py configure --qt 5.15 --skip qtcharts         # add a skip
```

- `--render` supports `gl | gles | gles3` (gles3 = `-opengl es2 -opengles3`, requires
  qtbase c5de1b3d+; with `gl`, a sysroot libGLv4.so pre-check runs automatically, and if it's missing you get a warning and
  replacement guidance, without blocking)
- A custom module set is part of the configure fingerprint: a change in the module set automatically triggers cleaning the dirty build directory and reconfiguring
  (QOH040 protection), so no .pri files from old modules are left behind

**Incremental + install** (the everyday case: rebuild after patching; reuses the variant context from the last configure directly):

```bash
python tools/qt-sdk-run.py build
python tools/qt-sdk-run.py install
```

**Parallel maintenance of multiple variants** (build contexts are stored in multiple slots per variant: one slot per
`<qt>-<render>-<build_type>`; the `active` pointer decides what build/install/verify/release act on):

```bash
python tools/qt-sdk-run.py status                          # list all variant slots (* = active)
python tools/qt-sdk-run.py build --qt 5.12 --render gles --build-type debug
python tools/qt-sdk-run.py verify --qt 5.15                 # switch back to 5.15 and verify again
```

> Switching to a variant that hasn't been configured is rejected, listing the available slots; old single-slot state is migrated to multiple slots automatically.
> Note: one home still corresponds to **one Qt source tree** (a single `qt_src` value + a shared patch stack) —
> to maintain both the 5.12 and 5.15 trees at once, open two forge homes with `QT_SDK_HOME` / `--home`.

> The Windows build gap is closed: the CLI spawns `mingw32-make.exe SHELL=cmd.exe` directly,
> which is safe under any host shell (bash swallows backslash paths — one of the knowledge base's three pitfalls;
> SHELL=cmd.exe forces recipes to be executed by cmd.exe).
> The path environment (NATIVE_OHOS_SDK / OHOS_SDK_SYSROOT / LLVM_INSTALL_DIR, and
> MINGW_ROOT / PERL_ROOT on PATH) is injected automatically by the CLI.

The three pitfalls are built in (violating one makes the gate FAIL):
1. **build without install** → SV4 checks that the mtime of key .so files (libqohos, etc.) is later than
   the install start time; the build subcommand prints an explicit reminder when it finishes
2. **running mingw32-make directly under bash/git-bash** → the CLI avoids it with SHELL=cmd.exe
3. **demo not rebuilt after install** → the demo must be rebuilt before the SV7 smoke test (the CLI reminds you)

Each step's log, exit code, and config.summary snapshot are stored in `.qtsdk/builds/`; **TIMEOUT is never
PASS**. When a build fails, run error matching first, then read the pages and fix:

```bash
python tools/qt-ohos-run.py analyze-log <log>     # reuses the 36 QOH patterns
```

### Step 4 Verification gates (the only success criterion)

```bash
python tools/qt-sdk-run.py verify
```

| Gate | Criterion |
|------|-----------|
| SV0 | Environment ready (source tree / OHOS SDK native / MinGW+Perl / cmake) |
| SV1 | Source state known: branch + commit + submodules registered, qtbase working-tree changes = the patch-stack registry |
| SV2 | configure exit code 0, config.summary snapshot written to disk |
| SV3 | make exit code 0 (TIMEOUT ≠ PASS) |
| SV4 | install propagation: key .so files exist and their mtime is later than the install start |
| SV5 | SDK completeness: bin/qmake, lib/, include/, mkspecs/ |
| SV6 | Traceability consistent: manifest patch set = the actual git diff, version number p<N> = patch count |
| SV7 | Smoke test (optional): registered manually with `smoke-mark`, or run `qt-app-porting`'s build/smoke with the new SDK |
| SV8 | Release archived: manifest written to disk + ENV.local.md switched |

```bash
python tools/qt-sdk-run.py smoke-mark --result pass --note "C-0003 demo regression passed"
```

- `Result: PASS` (SV0-SV6 + SV8, SV7 registered) → only then can you declare the version usable
- `Result: PARTIAL` (SV7 SKIP) → built and installed successfully but not smoke-tested; **you can only report "usable at build level"** (exit code 3)
- `Result: FAIL` → report the failure + the remaining problems (gate items; build errors go through analyze-log)

### Step 5 Release a version

```bash
python tools/qt-sdk-run.py release --note "Fix the C-0003 input method race"
# temporary test version (may include diagnostic patches):
python tools/qt-sdk-run.py release --type test --note "For verifying the C-0003 fix"
```

- Version number: `<qtver>+p<N>.<yyyymmdd>` (e.g. `5.15.16+p3.20260915`, p = the local patch generation;
  multiple releases on the same day automatically get a sequence suffix)
- Generates `releases/manifest-<ver>.yaml`: the patch set (id + SHA256), base commit,
  all variant parameters, the SDK directory, and a snapshot of key .so files (size/mtime/SHA256)
- **Discipline (machine-enforced)**: `diagnostic` patches are rejected under `--type release`;
  revert them first, or release with `--type test` / `--allow-diagnostic` instead
- Release pre-check: if qtbase has unregistered changes, the release is refused (SV1 traceability consistency)

### Step 6 Version switching and ENV sync

```bash
python tools/qt-sdk-run.py release-list          # version list (with patch-set summaries)
python tools/qt-sdk-run.py use 5.15.16+p3.20260915
python tools/qt-sdk-run.py diff <v1> <v2>        # differences in patch set/commit/parameters
```

`use` updates the corresponding variable in `ENV.local.md` (`QT5_15_OHOS_SDK` / `QT5_12_OHOS_SDK` /
`QT6_OHOS_SDK`) and writes the current release marker. Rollback = `use` an old version (the SDK directories stay put;
only the pointer switches).

## Periodic evolution maintenance (upstream tracking)

**Trigger**: the user says "check upstream / update version knowledge", or a periodic task (weekly recommended).

### 7.1 Upstream evolution check

```bash
python tools/qt-sdk-run.py upstream-check
```

- Fetches the upstream branches and produces a list of new commits + **watch-directory annotations**
  (`qtbase/src/plugins/platforms/ohos/`, `qtbase/src/harmonyos/`, `qtohosextras/`)
- **The agent must read and understand it** (not just list it): output an "evolution report" in four categories — "new capabilities / fixes / breaking changes / conflicts with local
  patches" — and store it at `.qtsdk/builds/upstream-<date>.md`

### 7.2 Patch-stack re-review (superseded detection)

- upstream-check automatically does a **file overlap comparison** (new upstream commits × local applied patches)
  and outputs the overlap list as superseded candidates
- The agent judges the candidates semantically (whether upstream has already fixed it) → if so, verify with the linked reproduction demo →
  `patch-mark <id> superseded` → revert the patch → release a new version without that patch
  (the new version's p generation decreases automatically; SV6 guarantees consistency)

### 7.3 faults review linkage (the knowledge base update closed loop)

```bash
python tools/faults-build.py review
```

- For T tracking tickets whose fix_version is due: use the new SDK + the C page's linked reproduction demo and go through
  `procedural/framework-fix-verification.md` to verify
- Record the result as the first row of the C page's "version verification record" (required by the knowledge base's evidence gate)
- After modifying `faults/_data/*.yaml` or a C page, you must run `python tools/faults-build.py build`
  to regenerate the derived artifacts, with ERRORs cleared to zero

### 7.4 Version baseline table update

When the upstream baseline changes (new branch / new commit / Qt6 status progresses):
- Update the "Qt framework versions (validation baseline)" table at the end of `AGENTS.md` + `CLAUDE.md`
- Update the validation baseline tables at the end of related pages (`semantic/qt-harmonyos-build.md`,
  `semantic/qt-harmonyos-qt6-status.md`, and others as affected)
- When there's new knowledge to contribute, go through `draft → promote` (aligned with `qt-app-porting`'s knowledge feedback)

## One-shot mode and resumption

```bash
# review → apply → build → install → gates → (with --release) release a version
python tools/qt-sdk-run.py forge <proposal-dir> --qt 5.15 --release --type test

python tools/qt-sdk-run.py status                 # which phase it stopped at
python tools/qt-sdk-run.py resume --run           # continue from the checkpoint
```

Task budget: `QT_SDK_TASK_BUDGET_SEC`, `QT_SDK_TASK_DEADLINE` (when exceeded, a checkpoint is written
and it exits with code 2, aligned with qt-app-porting's runaway-prevention design).

**Exit codes**: 0 = PASS, 1 = FAIL, 2 = budget exhausted, 3 = PARTIAL (usable at build level).

**Concurrency contract**: writes to state.json / env.json / registry.yaml / RELEASES.md go through
a file lock (`<file>.lock`) + atomic replace (tmp + os.replace), so concurrent processes won't corrupt
files; but read-modify-write sequences (such as applying a patch) aren't held under a lock across steps — **run only one
forge process per home at a time**; if you need parallelism, use separate homes.

## Relationship with the rest of the knowledge base

| Layer | Carrier |
|-------|---------|
| Task Router | `_index/_task-routing.md` (route code [S]) |
| Knowledge Plane | `semantic/qt-harmonyos-build`, `procedural/framework-issue-analysis`, `procedural/framework-fix-verification`, `problems/`, `faults/` |
| Execution Plane | `tools/qt-sdk-run.py` + `tools/qt_sdk/` (state / envcheck / srctree / patching / building / releasing / verify) |
| State Plane | `workspace/qt-sdk/.qtsdk/` (state/registry/inbox/builds/releases) |
| Verification Plane | SV0-SV8 gates |
| Learning Plane | `knowledge/drafts/` (draft/promote), faults C page version verification records, the version baseline table |

**Upstream collaborating agents**: `framework-issue-analysis` (produces change-proposal tickets into the inbox),
faults library maintenance (C page fix suggestions → tickets); **downstream collaborating agents**: `qt-app-porting`
(consumes SDK versions for application migration and smoke tests; `qt_sdk_prefix` points at this plane's output),
`kb-init` (the ENV.local.md sync party). For the full interface cards and the handoff envelope contract, see `_index/_agent-mesh.md`.

## Human-in-the-loop points (HITL)

Level definitions: H1 blocking decision / H2 manual execution / H3 review and confirmation (for the general red lines and the table across all agents, see
`_index/_agent-mesh.md` §5).

| Level | Trigger condition | Behavior |
|-------|-------------------|----------|
| H2 | The Qt 6.12 prebuilt installer requires an interactive install with login; the agent doesn't download it on the user's behalf | Tell the user to install it manually, then register it with `config set sdk_root` |
| H2 | Credentials for cloning the commercial source | Provided verbally by the user; kept only in memory, never written to disk |
| H1 | Official release (`--type release`; switching the ENV pointer affects everything downstream) | Wait for user confirmation |
| H1 | Handling a diagnostic patch rejected by the release gate (revert / release a test version instead) | Wait for the user's ruling |
| H1 | Retiring a patch after the superseded re-review passes + releasing a new version without it | Wait for user confirmation |
| H2 | Manual verification results for the SV7 smoke test (what `smoke-mark` registers is a human conclusion) | Ask a human to run it and register the result |
| H1 | Submitting a patch upstream (this skill doesn't do it on anyone's behalf) | After `patch-export`, hand it to a human to submit |

## Boundaries

- Doesn't do application migration (the domain of `qt-app-porting`)
- Doesn't do problem diagnosis or root-cause analysis (the domain of `framework-issue-analysis`) — this skill only consumes its conclusions
- Doesn't submit patches upstream on the user's behalf (preparing the submission package goes through framework-issue-analysis phase four;
  `patch-export` only exports already-cleaned-up patches)
- The official Qt 6.12 prebuilt kit doesn't need building — **the installer requires an interactive install with a Qt account login, and the agent
  can't download it on the user's behalf**: when a 6.12 request comes in, the agent must tell the user to install it manually and explain the onboarding flow
  (tick the HarmonyOS target in the installer → register with `config set sdk_root <kit path>` →
  switch with `use`; see README §Obtaining versions and licensing for details). For 6.12 this skill only does "version registration
  + ENV sync + upstream status tracking" (`semantic/qt-harmonyos-qt6-status.md`);
  configure rejects 6.12 outright (only 5.12 / 5.15 are source-buildable)
