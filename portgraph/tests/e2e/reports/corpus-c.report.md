# corpus-c Dependency Reconciliation Report (portgraph E2E)

> Generated: 2026-09-19T15:13:09Z | Corpus: corpus.json#corpus-c | Build system: cmake | Source files: 884
> Oracle: INSTALL.md (review: reviewed, 7 entries; origin: Finalized after agent review: removed the leftover prose link set-up-build-environment; asciidoctor reclassified as build per the original text (build tools must exist within your PATH + KPXC_FEATURE_DOCS); this version of INSTALL.md declares only three libraries, qt/botan/zlib, with no libgcrypt/argon2/libsodium/ykpers; vcpkg/xvfb-run are tools/test helpers mentioned in prose and are not in the oracle)

## 1. Summary

| Metric | Value |
|---|---|
| Portability verdict | **blocked** (blocked 5 / unknown 1 / platform-excluded 0) |
| Detection recall | 100% (3/3 README runtime deps) |
| Detection precision | 23% |
| Bug candidates | **0** (none) |
| Dependency closure | 42 items (cmd_only 1, covered 1, need_port 1, provided 8, target 1, would_download 30) |

**Agent review notes**:

- Oracle review: removed the leftover prose link set-up-build-environment; asciidoctor reclassified as build per the original text (documentation build tool); this version of INSTALL.md declares only three runtime libraries, qt/botan/zlib, with no libgcrypt/argon2/libsodium/ykpers; vcpkg/xvfb-run are tools/test helpers mentioned in prose and are not in the oracle
- Final verdict on the 4 resolution-gaps: the three alias gaps xkbcommon/x11/pcsc were added to kb_seed.PKG_ALIASES (xkbcommon->libxkbcommon, x11->libx11, pcsc->pcsc-lite, libpcsclite->pcsc-lite), so the scan now resolves straight to the real package nodes and no longer creates ghosts; openmp is a CMake built-in compiler feature, reclassified as unknown-ok (fetch-deps also marks it provided under the built-in category); the ghost node matched by botan was checked and indeed has no HarmonyOS package, so the need_port verdict is correct
- Recall going from 60% to 100% comes entirely from correcting the oracle denominator (build tools/leftover links had been wrongly counted as runtime); portgraph's detections did not change; precision staying at 27% reflects how minimal INSTALL.md's dependency declarations are (all 8 items missing from the README were confirmed by grep evidence to be real build references; portgraph is correct)

## 2. Portability Verdict (analyze)

| Blocker kind | Node | Reason |
|---|---|---|
| unsupported-interface | app:corpus-c | uses platform interface macOS Cocoa/AppKit unsupported on HarmonyOS (os-api) macOS-only UI/system framework; HarmonyOS alternative interfaces in the same catego |
| unsupported-interface | app:corpus-c | uses platform interface D-Bus IPC unsupported on HarmonyOS (ipc) HarmonyOS has no D-Bus (the Qt D-Bus module is out of scope); switch to system services/IPC; Ha |
| unsupported-interface | app:corpus-c | uses platform interface Win32 API unsupported on HarmonyOS (os-api) Windows-only system interface; HarmonyOS alternative interfaces in the same category: dlopen |
| unsupported-interface | app:corpus-c | uses platform interface Direct X11/Xlib unsupported on HarmonyOS (display) HarmonyOS has no X11 display server; Qt apps should go through QPA, code using X11 di |
| unsupported-module | qtmod:dbus | Qt for HarmonyOS module support table: unsupported - HarmonyOS has no D-Bus |

1 unconfirmed items:
- [unknown-package] pkg-unknown:botan: no HarmonyOS prebuilt artifact, must be cross-compiled and ported yourself; not in the Harmonybrew/cmd-pkgs known list

## 3. Difference Attribution Details (oracle x portgraph direct deps)

| Class | README side | portgraph side | Type/depth | Evidence/notes |
|---|---|---|---|---|
| README omitted | — | libqrencode | package d1 | referenced by build files but not listed in README -> README incomplete (portgraph correct) |
| README omitted | — | libusb | package d1 | referenced by build files but not listed in README -> README incomplete (portgraph correct) |
| README omitted | — | libx11 | package d1 | referenced by build files but not listed in README -> README incomplete (portgraph correct) |
| README omitted | — | libxi | package d1 | referenced by build files but not listed in README -> README incomplete (portgraph correct) |
| README omitted | — | libxkbcommon | package d1 | referenced by build files but not listed in README -> README incomplete (portgraph correct) |
| README omitted | — | libxtst | package d1 | referenced by build files but not listed in README -> README incomplete (portgraph correct) |
| README omitted | — | minizip | package d1 | referenced by build files but not listed in README -> README incomplete (portgraph correct) |
| README omitted | — | pcsc-lite | package d1 | referenced by build files but not listed in README -> README incomplete (portgraph correct) |
| README omitted | — | qrencode | package d1 | referenced by build files but not listed in README -> README incomplete (portgraph correct) |
| README omitted | — | readline | package d1 | referenced by build files but not listed in README -> README incomplete (portgraph correct) |
| Build tool | cmake | — | build | build tool; fetch-deps does not collect build edges |
| Build tool | make | — | build | build tool; fetch-deps does not collect build edges |
| Build tool | g++ | — | build | build tool; fetch-deps does not collect build edges |
| Build tool | asciidoctor | — | build | build tool; fetch-deps does not collect build edges |
| Granularity folded | — | Qt Core | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt D-Bus | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt GUI | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt Network | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt SVG | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt Test | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt Widgets | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Matched | qt | Qt Concurrent | qt-module d1 |  |
| Matched | botan | botan | package d1 | matched a ghost node: real external dependency with no known HarmonyOS package (fetch-deps reports need_port/needs a source port; detection correct) [agent: Review ⚠ note: neither the hb-core Formula  |
| Matched | zlib | zlib | package d1 |  |

Class counts: Build tool×4, Matched×3, Granularity folded×7, README omitted×10

## 4. Dependency Closure Overview (fetch-deps --dry-run)

- Closure total 42 items: cmd_only 1, covered 1, need_port 1, provided 8, target 1, would_download 30
- Bottle directly downloadable: minizip, pcsc-lite, qrencode, readline, libx11, zlib, libxkbcommon, libusb, libxi, libxtst, zlib-ng-compat, libpng, libxcb, xorgproto, xkeyboard-config, libxext, libxfixes, python@3.14, libxau, libxdmcp, mpdecimal, openssl@3, sqlite, xz, zstd, gettext, util-linux, musl-compat, lz4, libunistring
- Command-only fetch (cmd_only): ca-certificates
- Needs own port (need_port): botan
  - botan: ?

## 5. Full Direct Dependency List (portgraph depth-1)

| Node | Type | Edge | port_status | Depth |
|---|---|---|---|---|
| botan | package | runtime | unknown | 1 |
| libqrencode | package | runtime | ported | 1 |
| libusb | package | runtime | ported | 1 |
| libx11 | package | runtime | ported | 1 |
| libxi | package | runtime | ported | 1 |
| libxkbcommon | package | runtime | ported | 1 |
| libxtst | package | runtime | ported | 1 |
| minizip | package | runtime | ported | 1 |
| pcsc-lite | package | runtime | ported | 1 |
| qrencode | package | runtime | ported | 1 |
| readline | package | runtime | ported | 1 |
| zlib | package | runtime | ported | 1 |
| Qt Concurrent | qt-module | uses-module | ported | 1 |
| Qt Core | qt-module | uses-module | ported | 1 |
| Qt D-Bus | qt-module | uses-module | blocked | 1 |
| Qt GUI | qt-module | uses-module | ported | 1 |
| Qt Network | qt-module | uses-module | ported | 1 |
| Qt SVG | qt-module | uses-module | ported | 1 |
| Qt Test | qt-module | uses-module | ported | 1 |
| Qt Widgets | qt-module | uses-module | ported | 1 |

## 6. Methodology

- Comparison scope: portgraph direct deps (depth-1 edges) vs deps declared in README/INSTALL; the closure is only an artifact overview.
- Attribution evidence: for unmatched items, automatically grep the cloned repo's build files (find_package/pkg_check_modules/target_link_libraries/vcpkg, etc.).
- ★ classes (missed-dep / resolution-gap / false-positive) are bug candidates requiring manual confirmation; the rest are expected differences.
- Agent-readable report: `tests/e2e/reports/corpus-c.report.json`
