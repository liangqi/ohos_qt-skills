# TEST-REPORT — portgraph dependency analysis: real-project testing and optimization (corpus-d, tier B)

> Branch: `worker3-deps-test` | Baseline: `f98a2e7` (all 44 unit tests passing) | This round's commit: `d8f32c3` (all 53 unit tests passing)
> Date: 2026-09-19 | Workspace: `~/harmony-workspace/worker3` (fresh workspace)
> Corpus: `portgraph/tests/e2e/corpus.json#corpus-d` (e2e tier B, README/INSTALL have a dependency section)

## 1. Executive summary

Ran the portgraph dependency-analysis e2e reconciliation on the real project **corpus-d** (shallow clone of upstream master).
The first round on the baseline code produced **2 resolution-gap bug candidates** (`libtorrentrasterbar` and `systemd`
ghost nodes). After locating root causes one by one from build-file evidence, fixed **3 root causes + 1 harness evidence defect**,
each with new unit tests (44→53, all passing). **bug_candidates 2→0, recall/precision stay at 100%**,
with no change to any e2e reconciliation semantics (zero changes to the oracle / classification logic / metric formulas).

## 2. Before/after metrics (corpus-d e2e)

| Metric | Baseline f98a2e7 | After fix d8f32c3 | Change |
|---|---|---|---|
| Detection recall (README runtime dependencies) | 100% (5/5) | 100% (5/5) | Unchanged |
| Detection precision | 100% | 100% | Unchanged |
| **Bug candidates** | **2** (resolution-gap×2) | **0** | **-2** |
| Portability unknowns | 3 | 1 | -2 |
| Total dependency closure | 21 | 19 | -2 |
| need_port (needs porting yourself) | 3 (libtorrentrasterbar / libtorrent-rasterbar / systemd) | 1 (libtorrent-rasterbar) | -2 (dedup + optional dependency leaves the closure) |
| d1 ghost nodes | 3 | 1 | -2 |
| verdict | blocked (4 blockers: Cocoa/D-Bus/Win32 interfaces + Qt D-Bus module) | blocked (same) | Unchanged (real blockers) |

Corpus regression (to ensure the fixes don't break other projects):

| Project | Result |
|---|---|
| corpus-c (B, reviewed oracle) | **No regression**: metrics/closure/direct dependencies identical to the committed baseline (the diff is only timestamps and repo_path) |
| corpus-b (C, reviewed oracle) | The metric change (recall 50%→25%) **comes entirely from the upstream build-system migration** (the fresh clone has been refactored to a corpus-b-deps/FetchContent manifest, with far fewer find_package declarations). A/B check: the baseline code scanning the same fresh clone gives the same results as the fixed code (qt_modules=3, 4~5 direct dependencies); and the new mechanism correctly judges `pkg_check_modules(mnxdom)` (guarded by `option(CB_USE_SYSTEM_MNXDOM ... OFF)`) as optional — validating the option-guard analysis on a second real project |

## 3. Fix list (root cause → fix → evidence → test)

### 3.1 Different names of the same library not merged → libtorrentrasterbar ghost node (resolution-gap #1)

- **Evidence**: `cmake/Modules/CheckPackages.cmake` L6 `find_package(LibtorrentRasterbar QUIET ...)` (CamelCase flattened name → `libtorrentrasterbar`) and L9 `pkg_check_modules(... "libtorrent-rasterbar>=...")` (hyphenated name) refer to the same library; the scan produced two `pkg-unknown` ghost nodes, and the closure counted need_port twice.
- **Fix**:
  - `project_scanner._link_third_party`: groups and merges by a separator-stripped key (`kb_seed._dashless_key`); the group's representative name = one that resolves to a known package > one with separators (pkg-config/hb naming) > the first; `merged_from` records the merged names.
  - `kb_seed.build_dashless_index` / `resolve_package_dashless`: fallback when resolution fails — the flattened name matches a known hyphenated package name (only hb:/cmdpkgs: sources included, key length ≥6 to avoid collisions, **pkg-unknown ghosts excluded** to avoid a self-fulfilling loop where "a ghost from the previous scan is treated as a known package by the next scan"; this problem was found and fixed during self-testing).
  - Verified no wrong mapping: cmd-pkgs' `libtorrent-rakshasa` (a different library used by rTorrent) has a different dashless key, so it won't mismatch.
- **Test**: `TestDashlessSameLibMerge` (4 cases: merges into a single ghost when unresolvable, fallback resolution when the package database has the package, alias=dashless when only the flattened name exists, short names/ghosts not indexed).

### 3.2 systemd wrongly entered the runtime dependencies (resolution-gap #2)

- **Evidence**: `dist/unix/CMakeLists.txt` L3 `find_package(Systemd)` sits inside `if (SYSTEMD)`; root `CMakeLists.txt` L39 `feature_option_dependent(SYSTEMD ... OFF "NOT GUI" OFF)` — SYSTEMD defaults to OFF (GUI defaults to ON), and that find_package only probes the service-file install directory (no linking).
- **Fix**:
  - `qt_scanner` gains CMake option-guard analysis: collects the defaults of `option` / `feature_option` / `feature_option_dependent` / `cmake_dependent_option` (merged across files) → tracks an if stack line by line → `find_package`/`pkg_check_modules` inside a **positive** guard (not negated with NOT) of an option defaulting to OFF are marked optional; `Find<Name>.cmake` module files inherit the guard at the `find_package(Name)` call site (the module only runs when called); `else`/`elseif` branches and function/macro bodies are conservatively not evaluated; when a package has both required and optional declaration sites, it is treated as required.
  - `project_scanner`: names on the optional list get an **optional edge** (a new edge type) and don't enter the runtime closure / portability analysis / fetch-deps / the d1 semantics of e2e reconciliation (all consumers filter on `("runtime","uses-module")`, so they're excluded automatically); the scan summary gains `deps_optional`.
  - `deps_report`: optional-guarded entries get `required=false` + the note "the default build doesn't include this dependency".
- **Tests**: `TestCmakeOptionGuard` (2 cases: OFF/ON defaults, if guard, Find-module inheritance, no evaluation inside macro bodies, find_package_details with an optional flag), `TestOptionalEdgeExcludedFromClosure` (optional-edge semantics: not in analyze unknowns / not in the closure / distinguished in the summary).

### 3.3 Underlying root cause: the dist directory was excluded, losing the guard context

- **Evidence**: `qt_scanner.EXCLUDE_DIRS` contained `dist`, so `dist/unix/CMakeLists.txt` (a real build subdirectory via corpus-d's `add_subdirectory(dist)`) was not scanned — in the first round the if-guard context of systemd was completely invisible.
- **Fix**: removed `dist` from `EXCLUDE_DIRS` (in C++/CMake projects dist is mostly a source-controlled packaging/install directory, not a build artifact; the JS ecosystem meaning doesn't apply to this tool's domain), with a comment recording the rationale.
- **Test**: the `TestCmakeOptionGuard` fixture is placed in `dist/unix/CMakeLists.txt`, which also covers this regression.

### 3.4 e2e harness evidence defect: @version node names couldn't be grepped (a leftover suggestion from the previous round)

- **Evidence**: `name_variants` didn't generate an `@3`-stripped variant for `openssl@3`, so it couldn't grep `find_package(OpenSSL)` (CheckPackages.cmake:47) and would misjudge a false positive (worked around by oracle review in the first round, fixed properly this round).
- **Fix**: `tests/e2e/run_e2e.py name_variants` appends stripped variants for node names/node ids containing `@` (only affects evidence grep, not the reconciliation classification semantics).
- **Test**: `TestE2ENameVariants`.

## 4. Residual items (not bugs this round, recorded)

1. **libtorrent-rasterbar is not in hb-core / cmd-pkgs** (a data-source gap, not a resolution defect): keeping a single `pkg-unknown:libtorrent-rasterbar` ghost node / need_port=1 is the **correct conclusion** (the INSTALL text itself warns against installing the different rakshasa library). The real fix is to submit a libtorrent-rasterbar formula to Harmonybrew (upstream https://github.com/arvidn/libtorrent).
2. **The libtorrent version constraint can't be resolved statically**: the `${version}` in `pkg_check_modules(... "libtorrent-rasterbar>=${version}")` is a CMake macro parameter (`macro(find_libtorrent version)`), which the `set()` variable table can't substitute → the deps report lacks `>= 2.0.10`. Possible improvement: backfill from literal macro-argument call sites (like `find_libtorrent(2.0)`); low payoff, not done for now.
3. **corpus-b corpus drift**: upstream master has migrated its build system (corpus-b-deps/FetchContent manifest), and the old oracle (18 entries) only reaches 25% recall on the fresh clone. The oracle needs rebuilding for the new layout (left alone this round to avoid accidentally changing the reconciliation semantics; the A/B check proved it isn't a code regression).
4. **The generic ⚠ hint for "matched to a ghost node"** is kept: the harness can't distinguish "a real data-source gap" from "a resolution gap"; the manual review explanation is given in the notes of `tests/e2e/overrides/corpus-d.json` (libtorrent-rasterbar is the former).
5. **Displaying optional edges**: currently visible among out-edges in the API node detail (type=optional), but the web graph/CLI summary has no dedicated grouping yet (a future enhancement).
6. **Theoretical collision risk of the dashless fallback**: two different libraries with the same key after stripping separators would mismatch; narrowed with "known package sources only + key length ≥6 + hb/ported take priority on key conflicts", and no real collision was found (validated on the corpus-d/corpus-b/corpus-c corpora).

## 5. Environment and reproduction

```bash
cd ~/harmony-workspace/worker3/portgraph
git clone --filter=blob:none --sparse https://atomgit.com/Harmonybrew/homebrew-core.git workspace/hb-core
(cd workspace/hb-core && git sparse-checkout set Formula)
python portgraph.py ingest all          # hb 4758 formulas + cmd-pkgs 1248
python -m unittest discover -s tests    # 53 tests OK
python tests/e2e/run_e2e.py run --project corpus-d --fresh-db
# → recall=100% precision=100% bug_candidates=0 closure=19 need_port=1
```

Files changed: `port_graph/qt_scanner.py` (option guards + optional marking + removal of the dist exclusion),
`port_graph/project_scanner.py` (same-library merging + optional edges), `port_graph/kb_seed.py`
(dashless index/resolution), `port_graph/deps_report.py` (optional semantics),
`tests/e2e/run_e2e.py` (name_variants @ stripping), `tests/test_port_graph.py` (+9 tests),
`tests/e2e/overrides/corpus-d.json` (review notes updated),
`tests/e2e/reports/*.report.{md,json}` (new corpus-d baseline + corpus-c/corpus-b reruns),
`docs/deps-report.md` (semantics documentation).
