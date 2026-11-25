# portgraph — portability topology graph for porting Qt applications to HarmonyOS

Analyzes whether a Qt application can run fully on HarmonyOS: it scans the app's dependencies (Qt modules,
KDE Frameworks components, third-party libraries) and platform interface usage (Win32/Cocoa/X11/ALSA…),
builds a SQLite dependency graph, recursively derives a portability verdict, and visualizes it as a web graph.

**Standalone project**: no dependency on an external knowledge base. The Qt module support matrix is vendored in `data/`,
and the project pre-scanner is vendored in `port_graph/qt_scanner.py`.

> Need to explain this module to someone? Start with **[OVERVIEW.md](OVERVIEW.md)** (one page:
> the problem it solves + architecture diagram), then come back here for CLI details.

---

## Architecture

```
Data source ingest            Scanning                Analysis/presentation
─────────────────         ──────────────          ─────────────────
Harmonybrew formulae ─┐                          ┌─ CLI (analyze/summary)
  (4741 formulae)      ├─► SQLite graph data      ├─ REST API (FastAPI)
cmd-pkgs README       ─┤   nodes / edges /        └─ Web graph (G6)
  (1248 prebuilt pkgs) │   interfaces                  horizontal hierarchical layout
Qt module support ──────┤        ▲
  matrix (data/*.md)    │        │ recursive verdict engine
                       ─┘        │ (portable/blocked/uncertain)
                   project_scanner ◄── app project scan
                   (CMake/qmake + source macro-guard analysis)
```

### Portability verdict model

An app node is judged **portable** if and only if:
1. All of its platform interfaces are supported on HarmonyOS (or excluded by conditional compilation for non-HarmonyOS platforms);
2. All of its dependencies are recursively portable.

| Verdict | Meaning |
|---|---|
| `portable` | All dependencies and interfaces are ready; it can be ported to HarmonyOS directly |
| `blocked` | There is a hard blocker: an unsupported platform interface / an unsupported Qt module / a blocked dependency |
| `uncertain` | No hard blocker, but there are unknown dependencies/interfaces (such as packages without a bottle) |

**Node boundary** (what counts as one "project" node): the smallest "independently portable unit", the unit you would port,
package and link independently. app = project repository; package = Harmonybrew/cmd-pkgs recipe;
qt-module = Qt module; framework = KDE Frameworks component (e.g. kio, judged recursively per component rather than
blocked as a whole). Platform interfaces (ALSA/X11…) are node attributes, not nodes.

**Platform-interface guard analysis**: for every platform API hit in the source, a macro stack tracker
(`#ifdef`/`#ifndef`/`#if defined()` AND/OR nesting, `#else`/`#elif`) decides whether that code
is compiled on HarmonyOS:
- `unconditional` / `ohos-active`: compiled → a hard blocker if unsupported
- `platform-excluded`: wrapped in a non-HarmonyOS macro guard → not blocking; the equivalent HarmonyOS replacement interface is attached
- `platform-file-excluded`: in a platform-specific file (macos/win/… paths) → not blocking

Each blocking interface has a **risk level** (by the share of hits that get compiled): high ≥80%, medium 30~80%, low <30%.

---

## Quick start

### Dependencies

- Python 3.10+ (the standard library is enough for ingest/scan/analyze)
- Web service: `pip install fastapi uvicorn`
- Graph front end: AntV G6 (loaded from a CDN, nothing to install)

### Initialize the data

```bash
# 1) Sparse checkout of the Harmonybrew formula repository (needed the first time)
git clone --filter=blob:none --sparse https://atomgit.com/Harmonybrew/homebrew-core.git workspace/hb-core
cd workspace/hb-core && git sparse-checkout set Formula && cd ../..

# 2) Load data into the database
python portgraph.py ingest harmonybrew   # 4741 formulae → package nodes + direct bottle links
python portgraph.py ingest cmdpkgs       # 1248 prebuilt packages (repository cloned automatically)
python portgraph.py ingest kb            # Qt module matrix + interface whitelist
# Or all at once: python portgraph.py ingest all
```

### Analyze a Qt application

```bash
# Clone and scan (background task; see the web UI)
python portgraph.py clone https://github.com/<org>/<your-Qt-app>

# Or scan an existing local project
python portgraph.py scan workspace/<app>

# Portability analysis (blockers, risk levels, dependency artifact list)
python portgraph.py analyze <app> --summary
```

Example output (fictional sample, sample-app):

```
verdict: blocked
blockers: 2
  [unsupported-interface] app:sample-app: uses a platform interface not supported on HarmonyOS
      macOS Cocoa/AppKit … [evidence: 212 file-level exclusions / 4 unconditional …]
dependency artifact list: 8 dependencies (3 with HarmonyOS artifacts / 5 provided by the framework / 0 need porting)
  [has artifact] ffmpeg v9.0.1 (runtime) ported
      HarmonyOS artifact: https://harmonybrew.atomgit.com/bottles/ffmpeg-9.0.1.arm64_ohos.bottle.1.tar.gz
      source download: https://ffmpeg.org/releases/ffmpeg-9.0.1.tar.xz
```

### Comprehensive dependency analysis (role classification + version ranges)

```bash
# Accepts a path or an already-scanned app name; --json prints a machine-readable report
python portgraph.py deps <app>
```

Answers "what exactly does this project depend on" by role (see docs/deps-report.md for details):

| Role | Meaning | Examples |
|---|---|---|
| link | Dependencies whose built artifacts the project expects to obtain (target-side headers+libs) | `find_package(ZLIB 1.2 REQUIRED)`, bare names in `target_link_libraries`, `find_library`, meson `dependency()`, autotools `PKG_CHECK_MODULES` |
| build-tool | Compiler/build-tool dependencies (run on the build machine, not deployed) | cmake≥3.16 / C++17 / protoc / ECM / meson≥0.53 |
| runtime | Runtime dependencies (device-side .so: transitive closure + dlopen/QLibrary) | ffmpeg's 14 transitive dependencies |
| test | Test-only, not shipped | GTest / Catch2 |
| vendored | Source bundled with the project (.gitmodules / 3rdparty/ / FetchContent) | dep/spdlog, qtColorWidgets (pinned by GIT_TAG) |
| env | Environment list installed by CI/scripts (a cross-checking source) | `apt install libkeyutils-dev` |

Each dependency carries its version range (find_package minimum version / pkg-config·meson·autotools·wrapper-function
constraints / conan ranges), how to obtain the HarmonyOS artifact, and a version-requirement check (satisfied / conflict).
See docs/deps-report.md for the coverage map of the 19 kinds of declaration signals.

### Getting cross-compilation dependencies (on non-HarmonyOS platforms)

`brew install` only runs on HarmonyOS devices; on other platforms, use `fetch` to download
arm64-OpenHarmony prebuilt bottles directly (with include/ + lib/ + cmake config):

```bash
# One or more packages
python portgraph.py fetch "zlib,jsoncpp,openssl@3"

# Or get all dependency artifacts for a whole app in one go (agent tool; see docs/fetch-deps.md)
python portgraph.py fetch-deps sample-app --dry-run   # preview the classified list
python portgraph.py fetch-deps sample-app            # download + manifest
```

Done automatically: look up the direct link in the database → download → verify sha256 → unpack into `workspace/ohos-libs/`
→ on Windows/NTFS, recreate `.so` symlinks as copies → print CMake/qmake integration snippets.

**Direct bottle link rule** (verified in practice):

```
https://harmonybrew.atomgit.com/bottles/<name>-<version>[_<revision>].arm64_ohos.bottle[.<rebuild>].tar.gz
```

- **A single hyphen** between name and version (not Homebrew's double hyphen)
- A top-level formula `revision N` → version suffix `_N` (e.g. pcre2-10.47_1)
- `rebuild N` inside the `bottle do` block → `.bottle.N.tar.gz` (e.g. curl-8.21.0)
- `@` variants are kept as-is (openssl@3-3.6.4); the bare names openssl/icu4c must use a variant

Key points for cross-compilation integration:
- CMake: `-DCMAKE_PREFIX_PATH=<bottle-path> -DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=BOTH` (iron rule)
- qmake: `LIBS += -L<bottle>/lib -lfoo` (the -l list is printed by fetch)
- On Windows `.so` files can only be linked, not run; they must be deployed to `entry/libs/arm64-v8a/` to get onto the device
- Runtime dependencies must be fetched recursively in full (e.g. ffmpeg's 14); missing one makes dlopen fail on the device

### Start the web service

```bash
python portgraph.py serve              # http://127.0.0.1:8000
python portgraph.py serve --port 8080
```

Features: app selection, knowledge graph (horizontal hierarchical / force-directed / circular layouts; Qt modules aggregated and expandable),
a blocker panel (filter by risk level), a node-detail drawer (platform-interface evidence, dependencies,
HarmonyOS artifact and source links), and adding analysis targets (background clone + scan; the progress bar can be minimized / refreshed any time).

---

## CLI reference

| Command | Description |
|---|---|
| `ingest <source>` | Load data: `harmonybrew` / `cmdpkgs` / `kb` / `all`; `--offline` skips pulling |
| `clone <url> [--name N]` | Shallow clone + scan into the database |
| `scan <project>` | Scan a local Qt project |
| `analyze <app> [--summary]` | Portability analysis; `--summary` gives a human-readable summary |
| `deps <path\|app> [--json]` | Comprehensive dependency analysis: link/build-tool/runtime/test/vendored classification + version ranges + artifact sources ([docs](docs/deps-report.md)) |
| `fetch <pkg,...> [--out D] [--force]` | Download bottles as cross-compilation dependencies |
| `fetch-deps <app> [--out D] [--force] [--dry-run] [--json]` | Download HarmonyOS artifacts for all of an app's dependencies in one go + manifest ([docs](docs/fetch-deps.md)) |
| `stats` | Data statistics |
| `export [out]` | Export the whole graph as JSON |
| `serve [--port P] [--host H]` | Start the web service |

Global: `--compact` prints compact JSON.

## REST API

| Endpoint | Description |
|---|---|
| `GET /api/apps` | App list |
| `GET /api/graph?root={app_id}` | Topology graph data (expanded smartly by portability: nodes already ported to HarmonyOS aren't drilled into, unported ones are expanded recursively) |
| `GET /api/analysis/{app_id}` | Portability analysis (verdict/blockers/unknowns/risk) |
| `GET /api/node/{node_id}` | Node details (including artifact link info) |
| `POST /api/scan` | Scan a local path `{path}` |
| `POST /api/clone` | Create a background clone + scan job `{url}` → `job_id` |
| `GET /api/job/{id}` | Job progress (percent/stage/message) |
| `GET /api/jobs` | Job list |
| `POST /api/ingest` | Trigger an ingest `{source}` |

## Directory layout

```
portgraph/
├── README.md               This document
├── docs/
│   ├── fetch-deps.md       One-step dependency artifact fetching (agent tool docs)
│   └── deps-report.md      Comprehensive dependency analysis: role classification + version ranges (agent tool docs)
├── portgraph.py            CLI entry point
├── port_graph/             Python package
│   ├── __init__.py         Path constants (PROJECT_ROOT/workspace/…)
│   ├── db.py               SQLite schema (nodes/edges/interfaces + link columns)
│   ├── harmonybrew.py      Formula parsing + direct bottle link construction/downloader
│   ├── cmdpkgs.py          cmd-pkgs README parsing + direct artifact links
│   ├── kb_seed.py          Qt module matrix (parsed from data/) + interface whitelist + KF component dependencies
│   ├── qt_scanner.py       Project pre-scan (vendored; find_package details/toolchain/dynamic loading)
│   ├── project_scanner.py  Project scan into the database (platform-interface macro-guard analysis/KF recursion/third-party alignment)
│   ├── engine.py           Recursive portability verdicts + artifact_info
│   ├── deps_report.py      deps: comprehensive dependency analysis (role classification/version ranges/transitive closure)
│   ├── deps_fetch.py       fetch-deps: one-step fetching of an app's dependency-closure artifacts
│   ├── cloner.py           git shallow clone
│   ├── jobs.py             Background jobs (progress bar)
│   └── api.py              FastAPI endpoints + front-end hosting
├── web/                    Front end (G6 knowledge graph)
├── data/                   Vendored knowledge data (Qt module HarmonyOS support matrix)
├── tests/                  Unit tests
└── workspace/              Runtime data (gitignored)
    ├── portgraph.db        SQLite graph data
    ├── hb-core/            Harmonybrew formula repository (data source)
    ├── cmd-pkgs/           cmd-pkgs repository (data source)
    ├── ohos-libs/          HarmonyOS prebuilt artifacts downloaded by fetch
    └── <app>/              App projects from clone/scan
```

## Data sources

| Source | Scale | Provides |
|---|---|---|
| [Harmonybrew](https://atomgit.com/Harmonybrew/homebrew-core) | 4741 formulae | Dependency graph, direct bottle links, source/homepage links |
| [cmd-pkgs](https://gitcode.com/OpenHarmonyPCDeveloper/cmd-pkgs) | 1248 packages | Direct links to HarmonyOS aarch64 prebuilt artifacts |
| Qt module HarmonyOS support matrix (vendored) | 50 modules | 36 supported / 14 unsupported |
| Interface whitelist (hand-curated) | 22 interfaces | Support status of POSIX/socket/GLES/pthread… (including 3 native HarmonyOS replacements) |
| KDE Frameworks component dependency table | 30 components | Recursive KF→Qt/KF/interface expansion |

## Tests

```bash
cd portgraph
python -m unittest discover -s tests -v    # 119 tests: parsers/engine/guards/closure/extraction/all forms of dependency declarations
```

## Known limitations

- Platform-interface detection is regex matching; API names in comments (e.g. `// DestroyWindow(...)`) and
  same-named custom functions can produce false positives and inflate the risk level (planned: strip comments + constrain to call forms)
- Formulae whose hb node lacks a version number (412 of them, urls without a version form) have no direct bottle link
  and fall back to cross-compiling from source
- When cmd-pkgs and harmonybrew packages of the same name fill in each other's links across sources, versioned links are only filled in when the versions match
