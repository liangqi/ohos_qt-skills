# qt-sdk-forge — Qt OHOS SDK building · patches · version management

The engineering plane for the local Qt for HarmonyOS SDK: **the single entry point for every Qt SDK build (whatever the version, whatever the platform)
and for producing temporary test versions**. Other agents provide change proposals; this agent turns them into
traceable, verifiable, switchable SDK versions.

```
Other agents (problem analysis/fault KB) ──change-proposal ticket──▶ qt-sdk-forge ──SDK version──▶ app developers
                                              │
                     ┌────────────────────────┤
                     ▼                        ▼
          upstream tqtc/harmonyos-* branches   knowledge feedback into faults/
          (evolution tracking, patch retirement)  (version verification records, review progress)
```

## Features

| Responsibility | Description |
|----------------|-------------|
| **Building** | Full (configure→build→install) and incremental install; parameterized variants: Qt 5.12/5.15 × release/debug × gl/gles; runs natively on Windows/macOS/Linux/HarmonyOS |
| **Patch management** | Accepts external change-proposal tickets (proposals), reviewing them before applying; a registry provides traceability (refs link to faults/QOH/QTBUG); full lifecycle: apply/revert/export/supersede |
| **Version release** | Version numbers `<qtver>+p<N>.<yyyymmdd>` (p = patch generation; the version itself is the traceability); a manifest (patch set + SHA256 + snapshot of key .so files); `use` switches versions and syncs ENV.local.md |
| **Evolution tracking** | `upstream-check`: report on new upstream commits (annotated against watch directories) + patch overlap comparison (superseded candidates) + linkage with faults review |

**Core discipline (machine-enforced)**: change proposals without refs are rejected on import; diagnostic patches are barred from
release versions (allowed with `--type test`); before release, the qtbase working tree must match the patch-stack registry
exactly; success is judged solely by the SV0-SV8 gate results — the LLM does the reasoning, the tools provide the facts.

## Obtaining versions and licensing

**Source available only with a commercial license**: Qt **5.15.16** (the main HarmonyOS line, commercial channel only)
and Qt **5.12.12** (the commercial branch, latest snapshot). Both come from
`https://codereview.qt-project.org/qt/tqtc-qt5` (branches `tqtc/harmonyos-5.15.16`
/ `tqtc/harmonyos-5.12.12`); you first need to generate HTTP Credentials on codereview.

**Open-source versions available to users without a commercial license** (the public GitCode repository
`https://gitcode.com/ohos-qt/qt-harmonyos-src`, no credentials needed):
- Qt **5.12.12 source** (the open-source snapshot `qt-harmonyos-src-5.12.12-20260625`)
- Qt **5.12.12 prebuilt SDK** (releases page: Windows/macOS × Desktop GL/GLES,
  HarmonyOS × GLES)
- ⚠️ 5.15 has **no open-source release** — without a license, if you need 5.15 there's no way to get it through open-source channels

| Target | License requirement | Can the agent fetch it automatically? | Command/method |
|--------|---------------------|---------------------------------------|----------------|
| 5.15.16 source | **Commercial required** | ✅ | `src-clone --method commercial --version 5.15 --user --pass` |
| 5.12.12 source | None (open source works) | ✅ | `src-clone --method opensource --version 5.12` |
| 5.12.12 prebuilt SDK | None | ✅ | Download from releases (`skills/kb-init/scripts/download-qt-sdk.sh`) |
| 6.12 prebuilt kit | None (Qt account) | ❌ **The user must install it manually** | See the onboarding flow below |

**Qt 6.12 can't be downloaded automatically by the agent**: the official online installer requires logging into a Qt account and interactively
ticking the **HarmonyOS** target, which the agent can't do on the user's behalf. When a 6.12 request comes in, the agent must
explicitly tell the user to onboard it manually. The flow:

1. The user downloads the online installer from the Qt website and logs into their Qt account
2. Choose a custom installation and tick the **HarmonyOS** target (once installed, the kit path looks like
   `C:\Qt\Qt6.12-beta3\6.12.0\harmonyos_arm64_v8a`; also note the host toolchain, e.g. `mingw_64`)
3. Once the user has finished installing, the agent registers it: `config set sdk_root <kit path>`, then `use` switches
   ENV.local.md (`QT6_OHOS_SDK` / `QT6_HOST_SDK`)

## Quick start

```bash
# 0) Prerequisite: the knowledge base's ENV.local.md is ready (if not, run skills/kb-init first)
python tools/qt-sdk-run.py init     # create workspace/qt-sdk/.qtsdk and bridge the paths

# 1) Point it at things (on Windows use Windows paths; /mnt/c/... are WSL paths)
python tools/qt-sdk-run.py config set qt_src <Qt source root>
python tools/qt-sdk-run.py config set ohos_sdk_native <OHOS SDK native>

# 2) Build a version (platform-independent; for obtaining the source see references/build-matrix.md §1)
python tools/qt-sdk-run.py configure --qt 5.15 --render gl --build-type release
python tools/qt-sdk-run.py build && python tools/qt-sdk-run.py install
python tools/qt-sdk-run.py verify          # SV0-SV8 gates
python tools/qt-sdk-run.py release --note "first 5.15.16"
python tools/qt-sdk-run.py use <version>   # sync ENV.local.md
```

**Produce a temporary test version for a change** (another agent's change proposal → SDK):

```bash
python tools/qt-sdk-run.py forge <proposal-dir> --qt 5.15 --release --type test
```

## Command quick reference

| Area | Commands |
|------|----------|
| Environment | `init` · `env` (SV0 detection) · `config set/get/show` · `src-clone --method commercial\|opensource --version 5.12\|5.15` |
| Modules | `modules --qt <ver>` (static: built by default/can be enabled/unsupported on the platform) · `modules --configured` (the modules actually in the active variant) · `configure --with a,b` (enable modules skipped by default) · `configure --skip a,b` (add more skips) |
| Patches | `patch-import <dir>` · `patch-apply/revert <id>` · `patch-list` · `patch-export <id> --dest` · `patch-mark <id> <status>` |
| Building | `configure --qt --render gl\|gles\|gles3 --build-type [--skip] [--with]` · `build` · `install` (all accept `--qt` to switch the variant slot) |
| Verification | `verify` (SV0-SV8) · `smoke-mark --result pass\|fail` |
| Versions | `release [--type release\|test]` · `release-list` · `use <ver>` · `diff <v1> <v2>` |
| Evolution | `upstream-check` |
| Flow | `forge <dir> [--release]` · `status` · `resume --run` |

Exit codes: `0` PASS / `1` FAIL / `2` budget exhausted / `3` PARTIAL (usable at build level).
Task budget: `QT_SDK_TASK_BUDGET_SEC`, `QT_SDK_TASK_DEADLINE`.
Multiple variants: build contexts are stored in multiple slots keyed by `<qt>-<render>-<build_type>`, listed by `status`
(`*` = active); to maintain both the 5.12 and 5.15 source trees at once, use `QT_SDK_HOME`/`--home` to open
separate homes.

## Change-proposal tickets (the input protocol for other agents)

```
<proposal-dir>/
├── proposal.yaml   # id / source / type(diagnostic|fix|backport) / motivation /
│                   # refs (required; links to faults/C-xxxx, QOHxxx, QTBUG) / base / retire_when
├── patches/0001-*.patch   # unified diff, relative to the qtbase submodule root
└── notes.md        # the originating agent's reasoning
```

Import means machine validation: missing refs are rejected, the patch must be a valid diff, and `git apply --check`
runs first to prevent conflicts. Patch state machine: `imported → applied → built → released → superseded/reverted`.

## Verification gates SV0-SV8

| Gate | Criterion |
|------|-----------|
| SV0 | Environment ready (source tree / OHOS SDK native / MinGW+Perl / cmake) |
| SV1 | Source state known: qtbase working-tree changes = the patch-stack registry |
| SV2/SV3 | configure / make exit code 0 (TIMEOUT ≠ PASS) |
| SV4 | install propagation: the mtime of key .so files (libqohos, etc.) is later than the install start |
| SV5 | SDK completeness: qmake / lib / include / mkspecs |
| SV6 | Traceability consistent: manifest patch set = git diff, version number p<N> = patch count |
| SV7 | Smoke test (optional): `smoke-mark` or hand over to qt-app-porting |
| SV8 | Release archived: manifest + ENV.local.md switched |

Only `PASS` lets you declare the version usable; `PARTIAL` (SV7 SKIP) can only be reported as "usable at build level".

## State directory

```
workspace/qt-sdk/.qtsdk/     # overridable with QT_SDK_HOME / --home; write gate: file lock + atomic replace
├── state.json   env.json    # state machine / local configuration
├── registry.yaml            # patch registry
├── patches/  inbox/         # patch library / external tickets
├── builds/  releases/  logs/  # build evidence / version manifests / full logs
```

Concurrency contract: the lock prevents file corruption but not lost updates from read-modify-write — **one forge process per home at a time**.

## Documentation index

| Document | Contents |
|----------|----------|
| [SKILL.md](SKILL.md) | Agent operating manual: workflow Steps 0-6, periodic evolution maintenance, discipline and boundaries |
| [references/build-matrix.md](references/build-matrix.md) | Platform × version × source-acquisition decision table (commercial/open-source channels, the credentials flow, per-platform toolchains, configure differences, equivalent manual commands) |
| `semantic/qt-harmonyos-build.md` | Build knowledge page (the verbatim configure, the skip list, the three incremental-build pitfalls) |
| `procedural/framework-issue-analysis.md` | Iron rules for generating and cleaning up patches (§4.3-4.5) |
| `skills/kb-init/` | Environment initialization (DevEco installation, system dependencies, ENV.local.md generation) |

## Boundaries

- Doesn't do application migration (the domain of `qt-app-porting`) or problem diagnosis (the domain of `framework-issue-analysis`)
- Qt 6.12 is an official prebuilt; **the installer must be run manually by the user** (the agent can't download it on their behalf); this agent only registers/switches/tracks it; `configure --qt 6.12` is rejected outright
- One home corresponds to one Qt source tree (a single `qt_src` value + a shared patch stack); use multiple homes for multiple trees
