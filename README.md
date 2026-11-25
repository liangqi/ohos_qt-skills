<div align="center">

# ohos_qt-skills

**A Qt → HarmonyOS porting engineering repo: knowledge · machine rules · executable pipeline**

Assess → migrate → build → install on device → verify → capture knowledge; every step has a machine-decidable result.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Qt](https://img.shields.io/badge/Qt-5.12%20%7C%205.15%20%7C%206.12-green.svg)](#capability-spec)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](#get-started-in-30-seconds)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](#quality-assurance)
[![Pages](https://img.shields.io/badge/knowledge%20pages-135-orange.svg)](_index/_map.md)

**Version v3.0.0** | [Changelog](CHANGELOG.md) | [Contributing guide](CONTRIBUTING.md) | [Task routing](_index/_task-routing.md)

</div>

> The three things porting a Qt application to HarmonyOS needs live in the same tree: **facts** (knowledge pages), **criteria** (machine rules and error patterns),
> and **actions** (executable CLIs and gates). Humans and agents follow the same path to move an application onto HarmonyOS,
> and the result of each step is decided by tools, not by "looks fine to me".
>
> Design principle: **the LLM does the reasoning, the tools supply the facts**. Building successfully doesn't mean the migration succeeded,
> and `TIMEOUT` is never `PASS`.
> 
> Join the project: you're invited to become a developer of the AtomGit ohos_qt-skills project. Invitation link: https://gitcode.com/invite/link/7a8aa925435647dbbf55

---

## What problem this repository solves

Getting a Qt/C++ desktop application to run on HarmonyOS is hard in these places:

| Scenario | Usual approach | This repository's approach |
|----------|----------------|----------------------------|
| Not knowing whether it can be ported | Leaf through the wiki module by module, try building | `portgraph analyze` gives a three-state verdict (portable / blocked / uncertain) + classification of blocking root causes |
| Builds after porting, but a white screen/crash on the device | Stare at logs and guess | Gates G0–G13 judge item by item; a missing .so closure, signing, or deployment gaps all get pointed out |
| Hitting the same error again and again | Dig through chat history | 44 QOH error patterns machine-matched + 59 real-world pitfall pages + a fault graph that locates "whose problem it is, whether it's fixed, how to work around it" |
| Days lost downloading/cross-compiling third-party dependencies | Find bottles and build by hand | `portgraph deps` / `fetch-deps` produce dependency role classification and a closure list |
| Breaks as soon as someone else takes over | Word of mouth | Persisted state machine (`.qt-ohos/`) + task ledger + knowledge capture protocol |

In one sentence: **turn "got it to run once" into "runs repeatably, can be taken over by someone else, can be accepted by a machine"**.

---

## Architecture: four layers in one, with a closed feedback loop

```
┌───────────────────────────────────────────────────────────────┐
│  Entry       SKILL.md · AGENTS.md · README.md · SETUP.md      │
│              → where humans come in: positioning, features,   │
│                getting started, agent contract                │
├───────────────────────────────────────────────────────────────┤
│  Knowledge   semantic/ procedural/ episodic/ problems/        │
│              ohos-common-kb-public/                           │
│              → source of truth for humans: facts, workflows,  │
│                retrospectives, error fixes, platform knowledge│
├───────────────────────────────────────────────────────────────┤
│  Machine     knowledge/errors(44 QOH) · rules(19 R)           │
│              knowledge/adaptation · faults/(fault graph)      │
│              → indexes for tools: matchable patterns distilled│
│                from the knowledge layer                       │
├───────────────────────────────────────────────────────────────┤
│  Execution   tools/qt-ohos-run.py · qt-sdk-run.py             │
│              faults-build.py · kb-verify-qt.py · portgraph/   │
│              templates/qt-ohos-app/                           │
│              → the part that does the work and gives PASS/FAIL│
└───────────────────────────────────────────────────────────────┘
   ↑ gate results, working recipes, newly hit pitfalls ——— flow back and get captured ↓
```

Four hard constraints:

- **The knowledge layer is the single source of truth humans read**; the machine layer is only its **projection** and doesn't create a separate set of facts — so the two always agree;
- **Conclusions of the execution layer must be reproducible**: gate decisions are based on file existence, binary symbols, and log patterns, not on what the model says about itself;
- **Feeding back is mandatory**: new problems land as drafts first and enter the source of truth only after the editor-in-chief gate; every entry written must be checkable by the fact re-review tools.

---

## Core capabilities

| Capability | Entry point | Status |
|------------|-------------|--------|
| 🔍 Feasibility assessment | `portgraph/portgraph.py analyze / deps / fetch-deps` | Can ingest 4741 Harmonybrew formulae + 1248 cmd-pkg index entries (network needed the first time) and produces a three-state verdict |
| 🚚 Automated migration pipeline | `tools/qt-ohos-run.py` (29 subcommands) | scan (19 pre-scan rules produce a risk report) → plan → tracked modifications → build → package → install on device → launch → smoke → gates, with checkpoint/resume; external cross-compilation can register its result with `build --record-only` |
| 🚦 Success verdict | `qt-ohos-run.py verify` (G0–G13) | Gate-level PASS / PARTIAL / FAIL; `TIMEOUT` doesn't count as passing |
| 🧠 Log diagnosis | `qt-ohos-run.py analyze-log` | 44 QOH error patterns auto-matched; a hit gives knowledge page references |
| 🧱 Platform-layer audit | `tools/ohos-platform-audit.py` | Distinguishes two kinds of dispatch, in-header `#ifdef` vs. build-time per-path `.cpp` selection; asserts that header dispatch names both OHOS macros; `--undefined` infers missing implementations from link logs |
| 🧰 Qt SDK engineering plane | `tools/qt-sdk-run.py` (24 subcommands) | Build / incremental install / patch provenance / SV0–SV8 release gates / upstream evolution tracking |
| 🗺️ Fault tracking | `faults/` + `tools/faults-build.py` | S→C→W→T fault graph (17/18/15/11): classification, responsible domain, workarounds, open tickets, closed-loop gaps |
| 📚 Knowledge foundation | `semantic/` `procedural/` `problems/` | 135 pages (Qt side 108 + embedded platform 27), 38 iron rules, 13 API mapping categories, 59 real-world pitfalls |
| 🏗️ Project template | `templates/qt-ohos-app/` | A clean 71-file HarmonyOS shell project (replacing the historical dirty template that carried build artifacts) |
| ✅ Self-check tests | `tests/` | engine self-tests 120 cases + consistency 27 cases + C++20 scan 9 cases |

---

## Get started in 30 seconds

### Just want to look things up (zero dependencies)

```bash
git clone https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills.git
cd ohos_qt-skills
cat _index/_task-routing.md     # what you're doing → which pages to read
cat _index/_map.md              # one-sentence summary per page
```

No Python needed, nothing to install. Open it directly as an Obsidian vault to see the reference graph.
To pin a version: `git clone --branch vX.Y.Z <repository URL>` (tags correspond one-to-one with `CHANGELOG.md`).

### Step 0: feasibility assessment (build the graph data first the first time)

When you take over an unfamiliar project, deciding "can it be ported" first saves days compared with changing code right away:

```bash
python portgraph/portgraph.py ingest all            # first time: fetch the Harmonybrew + cmd-pkgs data sources and build the graph
python portgraph/portgraph.py scan <your Qt project path>  # or clone <git-url>
python portgraph/portgraph.py analyze <app> --summary     # three-state verdict
python portgraph/portgraph.py deps <app>                  # dependency role analysis (each with file:line evidence)
python portgraph/portgraph.py fetch-deps <app> --dry-run  # dependency closure preview
python portgraph/portgraph.py fetch-deps <app>            # pull bottles into ohos-libs/
python tools/qt-ohos-run.py pkgconfig --relocate          # rewrite build-machine paths in .pc files to local ones
python tools/qt-ohos-run.py pkgconfig --write-shim        # generate a pkg-config stand-in (common on Windows)
```

The verdict is one of `portable` / `blocked` / `uncertain`: `blocked` names the specific blockers,
and `uncertain` lists the gaps that "need cross-compiling from source" — that list is what scheduling should be based on.

Unresolved dependencies come in two kinds; don't confuse them: **not in the knowledge base** (a real gap; schedule a port) and
**names don't match** (the project says `ada`, the database calls it `ada-url`; the project says `pango-1.0`, the database calls it `pango`).
Entries of the latter kind carry a hint like `; the knowledge base has a similar package …`; rename according to the hint first, then decide. The project's own
subdirectories (things like `auto_updates`/`crash_reports`, whose source files are built along with the project) are not treated as
third-party libraries.

### Want an agent to do the work

Open this repository in an agent that supports `SKILL.md` / `AGENTS.md` (Claude Code / Codex / Cursor, etc.) and just state what you need:

- "Port this Qt project to HarmonyOS" → goes through `qt-app-porting` (the execution pipeline)
- "What's wrong with this pile of build logs" → goes through `analyze-log` + `problems/`
- "Build me a Qt 5.15 HarmonyOS SDK" → goes through `qt-sdk-forge`
- "Is this problem actually a Qt bug or a HarmonyOS limitation" → goes through the fault graph `faults/`

The agent's loading order, execution discipline, and prohibitions are in [AGENTS.md](AGENTS.md). For environment dependencies and first-time setup, see [SETUP.md](SETUP.md).

### Want to run the tools locally yourself

Drive a complete migration (each step leaves state under the target project's `.qt-ohos/`; after an interruption you can `resume`):

```bash
python tools/qt-ohos-run.py doctor            # environment check: cmake / Qt kit / SDK / hvigor / hdc / device
python tools/qt-ohos-run.py scan <project dir>   # pre-scan + risk report from 19 rules
python tools/qt-ohos-run.py plan              # migration plan (auto / assisted / manual)
python tools/qt-ohos-run.py patch             # allowlisted automatic fixes (tracked)
python tools/qt-ohos-run.py build             # G3 build
python tools/qt-ohos-run.py package           # G5 package the HAP (Qt6 automatically uses _make_hap / harmonydeployqt6 + dependency closure check)
python tools/qt-ohos-run.py sign              # optional: devecocli generates signing material and writes build-profile
python tools/qt-ohos-run.py install           # G6 hdc install on device (paths automatically converted to native local form)
python tools/qt-ohos-run.py launch            # G7 launch (ability read from mainElement in module.json5)
python tools/qt-ohos-run.py smoke             # G8 crash-window check (skipped if install/launch didn't pass; never judged PASS)
python tools/qt-ohos-run.py smoke-interact    # G10 machine evidence: screenshot → click → screenshot again and compare; humans keep the verdict
python tools/qt-ohos-run.py verify            # G0-G13 gates — the only success criterion (exit 0/3/1)
```

To do it all in one go, use one-shot mode `python tools/qt-ohos-run.py migrate <project>` (chains the whole flow automatically,
and stops with guidance when shell-project generation needs a human decision); to resume across sessions, use `status` / `resume --run`.

Quick self-checks and environment-related tools:

```bash
python _scripts/ci.py                      # run all four gates at once (contract + fault library + tests + CLI smoke)
python tools/faults-build.py check         # fault library source of truth ↔ derived artifact consistency
python tools/cpp20-gap-scan.py scan <src>  # scan for C++20 gaps before building a large project
python tools/kb-verify-qt.py               # fact re-review of knowledge pages (needs ENV.local.md pointing at a local SDK)
python -m unittest discover -s tests -v    # full test suite
```

Use `--help` to look up any subcommand: `python tools/qt-ohos-run.py --help`, `python tools/qt-sdk-run.py --help`.

The tool layer **uses only the Python standard library** (3.10+) and runs on Windows / macOS / Linux; the `serve` subcommand of `portgraph`
additionally needs FastAPI (optional).

---

## Skills at a glance

Each directory under `skills/` is an independent Agent Skill. The boundaries are drawn by "who may write the source of truth", not by an arbitrary split of features:

| Skill | Role | Write permission |
|-------|------|------------------|
| [`kb-init`](skills/kb-init/SKILL.md) | Environment initialization: detect DevEco / OHOS SDK / Qt source, install missing dependencies, generate `ENV.local.md` | Writes only the local `ENV.local.md` |
| [`qt-app-porting`](skills/qt-app-porting/SKILL.md) | Main application migration pipeline (calls `qt-ohos-run.py`), produces reports and knowledge drafts | Writes only the target project + `.qt-ohos/` + drafts |
| [`qt-sdk-forge`](skills/qt-sdk-forge/SKILL.md) | Qt SDK build, patch application and provenance, local multi-version releases (SV0–SV8) | Writes only the local SDK directory |
| [`task-dispatcher`](skills/task-dispatcher/SKILL.md) | Task ledger / handover envelopes / flow log for multi-agent collaboration | Writes only the task ledger |
| [`kb-iterator`](skills/kb-iterator/SKILL.md) | **The single write gateway to the source of truth**: merge drafts, promote, regenerate indexes, re-review facts, distill retrospectives | The only one that may write the knowledge source of truth |
| [`qt-community-to-official`](skills/qt-community-to-official/SKILL.md) | Community edition (QtOhExtras) → official edition (QtOhosExtras) code migration, patch generation, build fixes, signed HAP | Writes only the target project |

Plus one repository tool that isn't under `skills/`: `portgraph` (the feasibility graph), step 0 of any porting task.

---

## CLI tools

| Tool | Subcommands | What it does |
|------|-------------|--------------|
| `tools/qt-ohos-run.py` | 29 | `scan` `plan` `patch` `build` `package` `install` `launch` `smoke` `smoke-interact` `verify` `analyze-log` `assess` `migrate` `finish` `status` `resume` `rollback` `mark-gate` `mark-ui` `mark-risk` `libcheck` `pkgconfig` `doctor` `sign` `draft` `promote` `recipes` `config` `init` |
| `tools/qt-sdk-run.py` | 24 | `init` `env` `config` `src-clone` `status` `patch-import` `patch-apply` `patch-list` `patch-revert` `patch-export` `patch-mark` `configure` `build` `install` `verify` `smoke-mark` `release` `release-list` `modules` `use` `diff` `upstream-check` `forge` `resume` |
| `tools/faults-build.py` | 4 | `build` `check` `review` `all`: source of truth → derived artifacts, closed-loop gap check |
| `tools/ohos-platform-audit.py` | — | Platform-layer audit: classification of the two kinds of dispatch + dual OHOS macro assertion; `--undefined` infers missing implementations |
| `tools/kb-verify-qt.py` | — | Fact re-review of knowledge pages (versions, symbols, paths) |
| `tools/cpp20-gap-scan.py` | — | Scan for C++20 gaps in the HarmonyOS toolchain |
| `portgraph/portgraph.py` | 10 | `ingest` `clone` `scan` `analyze` `deps` `stats` `fetch` `fetch-deps` `export` `serve` |

`qt-sdk-run.py forge <proposal-dir>` packages a change proposal into a traceable patch proposal (with a manifest),
which `patch-import` / `patch-apply` then land in the source tree — so "who changed which line of Qt, and why" can always be looked up.

Gate verdicts have only three levels: `PASS` (G0–G8 all pass), `PARTIAL` (build/link passed, packaging and device side not done),
and `FAIL`; `verify` exits with `0` / `3` / `1`. Neither `TIMEOUT` nor `SKIP`/`NOT_RUN` counts as passing.

`STALE` is a marker, not a fourth level: a record (G6 install / G7 launch / G8 crash window) is bound to
"which HAP's sha256, which device"; after repackaging or switching devices, those records are marked `STALE` and counted as `FAIL` in the verdict —
reusing an old PASS after the package changed is the easiest kind of "pass" to fool yourself with.

Gates look at content, not at whether files exist: G4 reads each artifact and asserts `ELF64 / AArch64 / DYN` (the wrong architecture
doesn't count as "it built"), G5 unpacks the HAP and checks the `DT_NEEDED` closure of `libs/<abi>/*.so` (missing a single
`libssl.so.3` reports "dependency closure broken"), G2 requires every critical risk to carry evidence, and G8 without `bundle_name` configured
can be at most PARTIAL. G13 goes one level further: it subtracts "exported by the package ∪
exported by the sysroot" from the strong undefined symbols of every `.so` in the HAP; what remains are the symbols that can make the process SIGSEGV directly in `find_sym2` when `dlopen` runs on the board.
Without a sysroot G13 only SKIPs and never fails just because it can't see; by default it reports PARTIAL as `advisory`,
and only `config set undefined_gate strict` makes it FAIL.

---

## Find pages by scenario

| What I want to do | Read these first |
|-------------------|------------------|
| Port a Qt application to HarmonyOS | The "Step 0" assessment above → `procedural/qt-app-harmonyos-migration.md` + `semantic/qt-harmonyos-porting-workflow.md` |
| Look up an API replacement | `semantic/qt-harmonyos-api-mapping.md` + `semantic/qt-harmonyos-code-patterns.md` |
| Check whether a Qt module supports HarmonyOS | `semantic/qt-harmonyos-modules.md` |
| Look up a HarmonyOS platform limitation | `semantic/qt-harmonyos-platform-limits.md` |
| Build failure / packaging / can't deploy | First `analyze-log` → `problems/_lookup.md` + `semantic/qt-harmonyos-build-run-workflow.md` |
| Window / dialog / lifecycle anomalies | `semantic/qt-harmonyos-window-model.md` + `semantic/qt-harmonyos-lifecycle.md` |
| How to use QtOhosExtras | `semantic/qt-ohos-extras.md` + `semantic/qt-ohos-extras-examples.md` |
| Decide who owns a problem (Qt defect / HarmonyOS limitation / application issue) | `faults/_registry.md` §symptom index |
| Third-party libraries / cross-compilation | `semantic/qt-harmonyos-third-party-libs.md` + `portgraph deps` / `fetch-deps` |
| Qt6 adaptation status | `semantic/qt-harmonyos-qt6-status.md` |
| Write a demo / validation project | `procedural/demo-generation.md` + `templates/qt-ohos-app/` |
| Qt + CEF applications | `procedural/qt-cef-ohos-dev-guide.md` |
| Read through the whole picture | `_index/_map.md` (one-sentence summary per page) |
| DevEco toolchain / MCP capability boundaries | `ohos-common-kb-public/procedural/deveco-cli-usage-rules.md` + `ohos-common-kb-public/semantic/deveco-mcp-capabilities.md` |

**How to use the fault library**: S is the application-level symptom, C is the root cause, and every C is **classified** — `defect` (Qt/HarmonyOS really
has a defect that will be fixed; needs an open ticket and a workaround) or `limitation` (a platform limitation; give an alternative rather than waiting for a fix);
W is the workaround, T the upstream tracking ticket. New problems go into `faults/_drafts/` first, through draft → editor-in-chief gate → promote
to official, so guesses never go straight into the source of truth.

## Key points for cross-compilation and dependency integration

- **CMake**: `-DCMAKE_PREFIX_PATH=<bottle path> -DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=BOTH`
- **qmake**: `LIBS += -L<bottle>/lib -lfoo` (the `-l` list comes from the `fetch` output)
- On Windows a `.so` **can only be linked, not run**; it must be deployed to `entry/libs/arm64-v8a/` to go onto a device
- Runtime dependencies must be pulled in fully and recursively (`fetch-deps` handles this); anything missed fails at `dlopen` on the device, with no sign at build time

## Directory structure

```
ohos_qt-skills/
├── SKILL.md                    # Agent Skill entry point (frontmatter + Instructions)
├── AGENTS.md                   # Agent behavioral contract (Claude Code can use a local copy)
├── README.md  SETUP.md  SECURITY.md  CHANGELOG.md  CONTRIBUTING.md
├── ENV.md                      # List of environment variable names (real values go in ENV.local.md, not checked in)
├── _index/                     # Index: _map map / _tags tags / _dashboard dashboard / _task-routing routing
├── semantic/                   # Semantic knowledge (26 pages): module status, API mapping, platform limitations, window/lifecycle
├── procedural/                 # Procedural knowledge (15 pages): migration, troubleshooting, build, releases, demo generation
├── episodic/                   # Episodic knowledge (8 pages, postmortems/): retrospectives from real projects
├── problems/                   # Error knowledge base (56 pages): real build/deployment/runtime errors and solutions
├── ohos-common-kb-public/      # Embedded general HarmonyOS platform knowledge (27 pages, ArkTS/ArkUI/NAPI/Stage)
├── knowledge/                  # Machine layer: errors(QOH) / rules(R) / adaptation
├── faults/                     # Fault graph: _data source of truth + C pages + derived _graph/_registry
├── tools/                      # Execution layer: CLIs + qt_ohos / qt_sdk engine packages
├── templates/qt-ohos-app/      # Clean HarmonyOS shell project template (71 files)
├── portgraph/                  # Portability graph subproject (CLI + package + web graph + self-tests)
├── tests/                      # Repository consistency / engine / scanner self-tests
└── skills/                     # 6 Agent Skills
```

---

## Quality assurance

In this repository "numbers written in the docs" are **testable assertions**, guarded by `tests/test_kb_consistency.py`: it binds
the claims in README, `SKILL.md`, `AGENTS.md`, and the index pages to the actual state of the repository:

| Level | Means | What it catches |
|-------|-------|-----------------|
| Numbers | Consistency cases (27) | Page count, QOH, rule count, iron rules, task routes, API mappings, fault graph scale, test count not matching reality |
| References | Same as above (path and anchor checks) | Pages/sections referenced in the docs don't exist |
| Manifest | Same as above (Skill manifest conventions) | Invalid frontmatter in root/child `SKILL.md`, a skill missing from `AGENTS.md` |
| Contract | Same as above (CLI contract) | The subcommand sets of the seven CLIs changed silently |
| Closed loop | `tools/faults-build.py check` | Fault library source of truth and derived artifacts inconsistent, chains not closed |
| Engine | `tests/test_qt_ohos.py` | Behavioral regressions in the state machine, gates, error matching |
| Graph | `portgraph/tests/` | Portability verdicts, dependency classification, bottle resolution |

Derived views are generated by scripts and checked by gates: for `_index/_dashboard.md` (page count/active count/problems/fault scale) run
`python _scripts/gen-dashboard.py`; for `faults/_graph.yaml` and `_registry.md` run
`python tools/faults-build.py build` — hand-edited numbers get caught by `verify`.

Current status: all tests green (engine 120 + consistency 27 + scan 9 = 156 cases, plus 131 graph unit tests), `faults-build check` has zero ERRORs.
One command runs all four gates: `python _scripts/ci.py` (also works on Windows without bash).

---

## Capability spec

Look things up by "what you want to do"; 16 task types in total:

| Code | Task type | Starting point |
|------|-----------|----------------|
| A | Application porting (full flow) | `_index/_task-routing.md` → migration workflow |
| B | API replacement lookup | 13 API mapping categories + code patterns |
| C | Module support lookup | Module adaptation status matrix |
| D | Platform limitation lookup | Platform limitations page + iron rules |
| E | Build troubleshooting | Build/run workflow + `problems/_lookup.md` |
| F | Window/dialog behavior | Window model + iron rules |
| G | Lifecycle | Lifecycle page (closeEvent/continuation/sharing) |
| H | QtOhosExtras APIs | 145+ QtOhosExtras extension APIs |
| L | Qt6 status | Qt6 adaptation status and gaps |
| M | Third-party libraries/dependencies | Third-party libraries page + `portgraph deps` |
| N | Toolchain | devecocli / hvigor / hdc usage and boundaries |
| P | Automated migration (execution layer) | `qt-ohos-run.py` |
| Q | Demo generation | Sample project generation flow |
| R | Fault tracking | Fault graph S→C→W→T |
| S | SDK engineering | `qt-sdk-run.py` |

---

## Known limitations

- **Platforms**: end-to-end testing is mainly on Windows + DevEco Studio; toolchain paths for macOS/Linux are covered, but the real-device install flow is less validated there.
- **CI**: there is no hosted CI; gates rely on local execution and maintainer review.
- **portgraph**: data comes from external indexes (Harmonybrew / cmd-pkgs); the first `ingest` needs a network connection; offline it can only read the already-checked-in `portgraph/data`.
- **Knowledge freshness**: both Qt and HarmonyOS keep moving; "done/fixed" on a page is governed by the `updated` and `last_confirmed` fields, and content past its review period is flagged by `faults-build review`.
- **Embedded platform knowledge**: `ohos-common-kb-public/` is trimmed from an upstream platform knowledge base; if it conflicts with the official documentation, the official documentation wins.
- **Limits of the feasibility verdict**: `portgraph`'s platform API detection is regex matching — API names in comments (such as `// DestroyWindow(...)`)
  can still produce false positives, so hard-blocker verdicts need a human to review the guard evidence. Function-like symbols now require call parentheses, and `*_win.cpp`/`*.mm`
  are excluded by file name, so the false-positive surface is smaller than in early versions.
- **Cross-compiling third-party libraries from source is not built into this repository**: it can hook up to an external `build_in_harmonyos` toolchain (set the `OHC_RUN`
  environment variable); this repository handles dependency detection, direct bottle download, and integration guidance.

---

## Design philosophy

1. **A single source of truth**: each thing is written only once; the machine layer is a projection, not a copy; `kb-iterator` is the only write entry point, preventing several people from each writing their own version.
2. **Decidable conclusions**: whatever can be written as an assertion isn't written as advice — gates judge by files, symbols, and log patterns, not by what the model says about itself.
3. **Failures leave a trail**: every automatic modification goes into `.qt-ohos/changes.json` + the patch directory; interrupted runs can resume, and everything can be reviewed afterward.
4. **Knowledge must be refutable**: every fault carries an evidence type (demo / log+stack / statically decidable); pure hearsay isn't accepted.
5. **Numbers must be real**: counts in the docs are guarded by tests; changing the docs without changing the facts turns the tests red.

---

## Environment variables and multi-tool compatibility

Knowledge pages don't hard-code local paths; they refer to them by variable name: `QT5_15_OHOS_SDK`, `QT5_15_SRC`, `OHOS_SDK_NATIVE`,
`DEVECO_CLI`, `HDC`, and so on. The variable list is in [ENV.md](ENV.md); real values go in `ENV.local.md` (gitignored,
not checked in), generated interactively by `kb-init`.

| Tool | How to hook it up |
|------|-------------------|
| Claude Code | Copy [AGENTS.md](AGENTS.md) to a local `CLAUDE.md` and it's loaded automatically |
| Codex | Reads `AGENTS.md` directly |
| Cursor / Windsurf | Reference `_index/_map.md` in `.cursorrules` / `.windsurfrules` |
| Obsidian | Open it directly as a vault and look at the reference graph |

## Versions and releases

- Version numbers follow [SemVer](https://semver.org/): **MAJOR** for breaking changes (deleting/moving pages/directory reshuffles that break links), **MINOR** for additions (new pages/new CLI subcommands/new skills), **PATCH** for corrections.
- Each release's [RELEASE-MANIFEST.yaml](RELEASE-MANIFEST.yaml) records the source SHA, page counts, and
  `content_tree_sha256` (content tree digest), so it can be reproduced and reconciled.

**Ways to obtain the Qt source** (pick one according to your license and network conditions):

- Commercial license: `git clone https://codereview.qt-project.org/qt/tqtc-qt5` (branches such as `tqtc/harmonyos-5.15.16`)
- Open-source mirror: `ohos-qt/qt-harmonyos-src` (some snapshots lose the executable bit and have CRLF; `src-clone` handles this automatically)
- Prebuilt SDK: take it directly from the upstream releases, or build locally with `qt-sdk-run.py` (SV0–SV8 gates)

---

## FAQ

**On what basis do we say "the migration succeeded"?**
Only G0–G12 of `python tools/qt-ohos-run.py verify` count: it passes only when G0–G8 all pass; `PARTIAL` means build/link
passed but packaging and the device side aren't done yet (an intermediate result, not a deliverable state); neither `TIMEOUT` nor `SKIP`/`NOT_RUN` counts as passing.
Building successfully ≠ successful migration.

**Can my application be ported?**
Run the portgraph trio first: `analyze` (portable / blocked / uncertain), `deps` (dependency roles and versions),
`fetch-deps --dry-run` (which have HarmonyOS prebuilt bottles, which need cross-compiling from source). When there are ≥3 third-party dependencies,
**don't judge them one by one by hand**; go by the closure output.

**Do I have to buy a Qt commercial license?**
It depends on which route you take: Qt 6.12 with the prebuilt HarmonyOS components from the official online installer, and Qt 5.12 from the open-source mirror, need no commercial license;
the Qt 5.15 source line (`tqtc-qt5`) needs a commercial license. The three channels are in the previous section.

**Is Qt WebEngine supported?**
No. On HarmonyOS, use CEF for OpenHarmony as the replacement; API mappings and migration steps are in
[qt-cef-ohos-dev-guide.md](procedural/qt-cef-ohos-dev-guide.md). If you only need to display web pages, you can start with Qt WebView's native bridge.

---

## Contributing

Content corrections, additional errors, migration retrospectives, fault intelligence, and tool improvements are all welcome; see the [contributing guide](CONTRIBUTING.md).
Issue templates are in `.gitcode/ISSUE_TEMPLATE/`. Only pages with `audience: public` are accepted; frontmatter must include
`id` / `type` / `summary` / `status`; cross-references use `refs` or wikilinks, with no broken links.
License: MIT (see [LICENSE](LICENSE)).
