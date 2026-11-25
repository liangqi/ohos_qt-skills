# corpus-d Dependency Reconciliation Report (portgraph E2E)

> Generated: 2026-09-19T15:12:49Z | Corpus: corpus.json#corpus-d | Build system: cmake | Source files: 710
> Oracle: INSTALL (review: reviewed, 7 entries; origin: Written by hand: the dependency list is in the INSTALL file at the repository root (no extension; corpus oracle_files was misconfigured as INSTALL.md; and it is a plain-text numbered list, not markdown headings, so the automatic extractor cannot parse it). Reviewed entry by entry against the original INSTALL text.)

## 1. Summary

| Metric | Value |
|---|---|
| Portability verdict | **blocked** (blocked 4 / unknown 1 / platform-excluded 0) |
| Detection recall | 100% (5/5 README runtime deps) |
| Detection precision | 100% |
| Bug candidates | **0** (none) |
| Dependency closure | 19 items (cmd_only 1, need_port 1, provided 8, target 1, would_download 8) |

**Agent review notes**:

- Second-round review (worker3-deps-test, baseline f98a2e7): the root causes of both first-round resolution-gaps (libtorrentrasterbar / systemd) were confirmed and fixed. 1) The libtorrentrasterbar ghost node = find_package(LibtorrentRasterbar) (CheckPackages.cmake:6, flattened CamelCase name) and pkg_check_modules(libtorrent-rasterbar) (same file L9, hyphenated name), the same library under different names, were not merged -- fix: project_scanner._link_third_party groups and merges by separator-stripped key + kb_seed.build_dashless_index fallback resolution (flattened CamelCase name -> known hyphenated package name, key length >= 6 to avoid collisions). libtorrent-rasterbar is indeed not in hb-core/cmd-pkgs (cmd-pkgs only has the different library libtorrent-rakshasa, whose dashless key differs, so no false mapping); keeping a single pkg-unknown:libtorrent-rasterbar ghost node is the correct conclusion (need_port); its version constraint >= 2.0.10 cannot be statically resolved because of the CMake macro argument ${version} (residual item).
- 2) The systemd ghost node = find_package(Systemd) (dist/unix/CMakeLists.txt:3) is guarded by if (SYSTEMD), while SYSTEMD is declared via feature_option_dependent(... OFF "NOT GUI" OFF) and defaults to OFF (GUI defaults to ON), and that find_package only probes the service-file install directory (no linking) -- fix: qt_scanner gained CMake option-guard analysis (collecting option/feature_option[_dependent]/cmake_dependent_option defaults + line-by-line if-stack tracking + Find<Name>.cmake modules inheriting the caller's guard); declarations inside a guard get optional edges; optional edges do not enter the runtime closure/portability analysis/fetch-deps. Underlying root cause: the dist directory was excluded by EXCLUDE_DIRS, losing the guard context (corpus-d's add_subdirectory(dist) is a real build subdirectory); that exclusion has been removed.
- The harness evidence-gathering defect left over from the previous round is fixed: name_variants appends a stripped variant for node names containing @version (openssl@3), so a failed grep for find_package(OpenSSL) no longer causes a false-positive verdict.
- Oracle notes (carried over from the first round): the dependency list is in the INSTALL file at the repository root (a plain-text numbered list; corpus oracle_files was once misconfigured as INSTALL.md); this oracle was written by hand by an agent, checked entry by entry against the original INSTALL text (7 entries: 5 runtime + 1 build + 1 optional), and has been reviewed.

## 2. Portability Verdict (analyze)

| Blocker kind | Node | Reason |
|---|---|---|
| unsupported-interface | app:corpus-d | uses platform interface macOS Cocoa/AppKit unsupported on HarmonyOS (os-api) macOS-only UI/system framework; HarmonyOS alternative interfaces in the same catego |
| unsupported-interface | app:corpus-d | uses platform interface D-Bus IPC unsupported on HarmonyOS (ipc) HarmonyOS has no D-Bus (the Qt D-Bus module is out of scope); switch to system services/IPC; Ha |
| unsupported-interface | app:corpus-d | uses platform interface Win32 API unsupported on HarmonyOS (os-api) Windows-only system interface; HarmonyOS alternative interfaces in the same category: dlopen |
| unsupported-module | qtmod:dbus | Qt for HarmonyOS module support table: unsupported - HarmonyOS has no D-Bus |

1 unconfirmed items:
- [unknown-package] pkg-unknown:libtorrent-rasterbar: no HarmonyOS prebuilt artifact, must be cross-compiled and ported yourself; not in the Harmonybrew/cmd-pkgs known list

## 3. Difference Attribution Details (oracle x portgraph direct deps)

| Class | README side | portgraph side | Type/depth | Evidence/notes |
|---|---|---|---|---|
| Optional, not enabled | python | — | optional | optional dependency, not enabled in the default build |
| Build tool | cmake | — | build | build tool; fetch-deps does not collect build edges |
| Granularity folded | — | Qt D-Bus | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt Network | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt SQL | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt SVG | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt Test | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt Widgets | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt XML | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Matched | boost | boost | package d1 |  |
| Matched | libtorrent-rasterbar | libtorrent-rasterbar | package d1 | matched a ghost node: real external dependency with no known HarmonyOS package (fetch-deps reports need_port/needs a source port; detection correct) |
| Matched | openssl | openssl@3 | package d1 |  |
| Matched | qt | Qt Core | qt-module d1 |  |
| Matched | zlib | zlib | package d1 |  |

Class counts: Build tool×1, Matched×5, Optional, not enabled×1, Granularity folded×7

## 4. Dependency Closure Overview (fetch-deps --dry-run)

- Closure total 19 items: cmd_only 1, need_port 1, provided 8, target 1, would_download 8
- Bottle directly downloadable: boost, openssl@3, zlib, icu4c@78, xz, zstd, zlib-ng-compat, lz4
- Command-only fetch (cmd_only): ca-certificates
- Needs own port (need_port): libtorrent-rasterbar
  - libtorrent-rasterbar: ?

## 5. Full Direct Dependency List (portgraph depth-1)

| Node | Type | Edge | port_status | Depth |
|---|---|---|---|---|
| boost | package | runtime | ported | 1 |
| libtorrent-rasterbar | package | runtime | unknown | 1 |
| openssl@3 | package | runtime | ported | 1 |
| zlib | package | runtime | ported | 1 |
| Qt Core | qt-module | uses-module | ported | 1 |
| Qt D-Bus | qt-module | uses-module | blocked | 1 |
| Qt Network | qt-module | uses-module | ported | 1 |
| Qt SQL | qt-module | uses-module | ported | 1 |
| Qt SVG | qt-module | uses-module | ported | 1 |
| Qt Test | qt-module | uses-module | ported | 1 |
| Qt Widgets | qt-module | uses-module | ported | 1 |
| Qt XML | qt-module | uses-module | ported | 1 |

## 6. Methodology

- Comparison scope: portgraph direct deps (depth-1 edges) vs deps declared in README/INSTALL; the closure is only an artifact overview.
- Attribution evidence: for unmatched items, automatically grep the cloned repo's build files (find_package/pkg_check_modules/target_link_libraries/vcpkg, etc.).
- ★ classes (missed-dep / resolution-gap / false-positive) are bug candidates requiring manual confirmation; the rest are expected differences.
- Agent-readable report: `tests/e2e/reports/corpus-d.report.json`
