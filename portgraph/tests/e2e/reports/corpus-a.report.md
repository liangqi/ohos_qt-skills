# corpus-a Dependency Reconciliation Report (portgraph E2E)

> Generated: 2026-09-19T15:12:59Z | Corpus: corpus.json#corpus-a | Build system: cmake+qmake | Source files: 6358
> Oracle: README.md (review: reviewed, 20 entries; origin: README §Third-party manually reviewed entry by entry: stripped license-suffix noise; GYP/Ninja/CMake changed to build type; Open Sans/Vazirmatn fonts and Emoji alpha codes are data assets (not link dependencies) and were removed)

## 1. Summary

| Metric | Value |
|---|---|
| Portability verdict | **blocked** (blocked 7 / unknown 19 / platform-excluded 2) |
| Detection recall | 71% (12/17 README runtime deps) |
| Detection precision | 40% |
| Bug candidates | **3** (false-positive=1, missed-dep=2) |
| Dependency closure | 112 items (cmd_only 2, covered 1, need_port 21, provided 9, target 1, would_download 78) |

**Agent review notes**:

- Fixed in this round (corpus-a deps-test): the scanner now parses ns::external_<name> imported target names in target_link_libraries (prefix stripped -> raw_libs ext_target) and adds edges/creates ghosts, so openal/xxhash/webrtc/ada/qr-code-generator and similar no longer need manual reclassification
- gsl/range-v3/hunspell and similar are bundled .gitmodules submodules (vendored, built with the project); the harness now classifies them as vendored automatically based on .gitmodules evidence
- Root cause of the remaining breakpad/crashpad gap: the shallow clone did not initialize submodules (cmake/ is cmake_helpers), so the find_package/breakpad-cp selection logic inside it is invisible; a complete fix needs 'clone --recurse-submodules' or degraded handling of the missing paths hinted by .gitmodules, see the residual items in TEST-REPORT
- lzma-sdk/liblzma/opus: the main repo's build files indeed have no reference (liblzma/opus come in via cmake_helpers' external prebuilt Libraries directory or the tg_owt stack); the readme-stale classification matches the facts within the current scan scope

## 2. Portability Verdict (analyze)

| Blocker kind | Node | Reason |
|---|---|---|
| unsupported-interface | app:corpus-a | uses platform interface macOS Cocoa/AppKit unsupported on HarmonyOS (os-api) macOS-only UI/system framework; HarmonyOS alternative interfaces in the same catego |
| unsupported-interface | app:corpus-a | uses platform interface D-Bus IPC unsupported on HarmonyOS (ipc) HarmonyOS has no D-Bus (the Qt D-Bus module is out of scope); switch to system services/IPC; Ha |
| unsupported-interface | app:corpus-a | uses platform interface systemd unsupported on HarmonyOS (os-api) HarmonyOS has no systemd service management; HarmonyOS alternative interfaces in the same cate |
| unsupported-interface | app:corpus-a | uses platform interface Win32 API unsupported on HarmonyOS (os-api) Windows-only system interface; HarmonyOS alternative interfaces in the same category: dlopen |
| unsupported-interface | app:corpus-a | uses platform interface Direct X11/Xlib unsupported on HarmonyOS (display) HarmonyOS has no X11 display server; Qt apps should go through QPA, code using X11 di |
| unsupported-module | qtmod:dbus | Qt for HarmonyOS module support table: unsupported - HarmonyOS has no D-Bus |
| unsupported-module | qtmod:waylandcompositor | Qt for HarmonyOS module support table: unsupported - Linux/Wayland compositor framework; the HarmonyOS window model is not Wayland |

19 unconfirmed items:
- [unknown-interface] app:corpus-a: HarmonyOS support for platform interface fork()/exec() process model is unconfirmed (guard=ohos-active)
- [unknown-package] pkg-unknown:ada: no HarmonyOS prebuilt artifact, must be cross-compiled and ported yourself; not in the Harmonybrew/cmd-pkgs known list
- [unknown-package] pkg-unknown:microsoft: no HarmonyOS prebuilt artifact, must be cross-compiled and ported yourself; not in the Harmonybrew/cmd-pkgs known list
- [unknown-package] pkg-unknown:range: no HarmonyOS prebuilt artifact, must be cross-compiled and ported yourself; not in the Harmonybrew/cmd-pkgs known list
- [unknown-package] pkg-unknown:tde2e: no HarmonyOS prebuilt artifact, must be cross-compiled and ported yourself; not in the Harmonybrew/cmd-pkgs known list
- [unknown-package] pkg-unknown:tg-owt: no HarmonyOS prebuilt artifact, must be cross-compiled and ported yourself; not in the Harmonybrew/cmd-pkgs known list
- [unknown-package] pkg-unknown:tl: no HarmonyOS prebuilt artifact, must be cross-compiled and ported yourself; not in the Harmonybrew/cmd-pkgs known list
- [unknown-package] pkg-unknown:breakpad-client: no HarmonyOS prebuilt artifact, must be cross-compiled and ported yourself; not in the Harmonybrew/cmd-pkgs known list
- [unknown-package] pkg-unknown:giomm-2-68: no HarmonyOS prebuilt artifact, must be cross-compiled and ported yourself; not in the Harmonybrew/cmd-pkgs known list
- [unknown-package] pkg-unknown:libudev: no HarmonyOS prebuilt artifact, must be cross-compiled and ported yourself; not in the Harmonybrew/cmd-pkgs known list
- [unknown-package] pkg-unknown:pangocairo: no HarmonyOS prebuilt artifact, must be cross-compiled and ported yourself; not in the Harmonybrew/cmd-pkgs known list
- [unknown-package] pkg-unknown:pangoft2: no HarmonyOS prebuilt artifact, must be cross-compiled and ported yourself; not in the Harmonybrew/cmd-pkgs known list
- [unknown-package] pkg-unknown:rnnoise: no HarmonyOS prebuilt artifact, must be cross-compiled and ported yourself; not in the Harmonybrew/cmd-pkgs known list
- [unknown-package] pkg-unknown:auto-updates: no HarmonyOS prebuilt artifact, must be cross-compiled and ported yourself; not in the Harmonybrew/cmd-pkgs known list
- [unknown-package] pkg-unknown:crash-reports: no HarmonyOS prebuilt artifact, must be cross-compiled and ported yourself; not in the Harmonybrew/cmd-pkgs known list

## 3. Difference Attribution Details (oracle x portgraph direct deps)

| Class | README side | portgraph side | Type/depth | Evidence/notes |
|---|---|---|---|---|
| ★Missed | breakpad | — | runtime | declared in README but no build-file reference -> README likely out of date/typo [agent: The main integration lives in the cmake/ (cmake_helpers) submodule: on Linux it is wrapped by external_crash_re |
| ★Missed | crashpad | — | runtime | declared in README but no build-file reference -> README likely out of date/typo [agent: The main integration lives in the cmake/ (cmake_helpers) submodule: on Linux it is wrapped by external_crash_re |
| ★False positive | — | libxcb | package d1 | detected by portgraph but no build-file reference -> scanner false-positive candidate (include heuristic/name coincidence) |
| README stale | lzma-sdk | — | runtime | declared in README but no build-file reference -> README likely out of date/typo |
| README stale | opus | — | runtime | declared in README but no build-file reference -> README likely out of date/typo |
| README omitted | — | boost | package d1 | referenced by build files but not listed in README -> README incomplete (portgraph correct) |
| README omitted | — | cmark-gfm | package d1 | referenced by build files but not listed in README -> README incomplete (portgraph correct) |
| README omitted | — | glib | package d1 | referenced by build files but not listed in README -> README incomplete (portgraph correct) |
| README omitted | — | glibmm | package d1 | referenced by build files but not listed in README -> README incomplete (portgraph correct) |
| README omitted | — | jpeg-turbo | package d1 | referenced by build files but not listed in README -> README incomplete (portgraph correct) |
| README omitted | — | libavif | package d1 | referenced by build files but not listed in README -> README incomplete (portgraph correct) |
| README omitted | — | libheif | package d1 | referenced by build files but not listed in README -> README incomplete (portgraph correct) |
| README omitted | — | libjxl | package d1 | referenced by build files but not listed in README -> README incomplete (portgraph correct) |
| README omitted | — | libvpx | package d1 | referenced by build files but not listed in README -> README incomplete (portgraph correct) |
| README omitted | — | libxkbcommon | package d1 | referenced by build files but not listed in README -> README incomplete (portgraph correct) |
| README omitted | — | lz4 | package d1 | referenced by build files but not listed in README -> README incomplete (portgraph correct) |
| README omitted | — | minizip | package d1 | referenced by build files but not listed in README -> README incomplete (portgraph correct) |
| README omitted | — | openh264 | package d1 | referenced by build files but not listed in README -> README incomplete (portgraph correct) |
| README omitted | — | opus | package d1 | referenced by build files but not listed in README -> README incomplete (portgraph correct) |
| README omitted | — | pango | package d1 | referenced by build files but not listed in README -> README incomplete (portgraph correct) |
| README omitted | — | protobuf | package d1 | referenced by build files but not listed in README -> README incomplete (portgraph correct) |
| README omitted | — | xxhash | package d1 | referenced by build files but not listed in README -> README incomplete (portgraph correct) |
| Build tool | gyp | — | build | build tool; fetch-deps does not collect build edges |
| Build tool | ninja | — | build | build tool; fetch-deps does not collect build edges |
| Build tool | cmake | — | build | build tool; fetch-deps does not collect build edges |
| Granularity folded | — | KF archive | framework d1 | KDE Frameworks component granularity: README usually just says 'KDE Frameworks' |
| Granularity folded | — | KF coreaddons | framework d1 | KDE Frameworks component granularity: README usually just says 'KDE Frameworks' |
| Granularity folded | — | KF desktoptojson | framework d1 | KDE Frameworks component granularity: README usually just says 'KDE Frameworks' |
| Granularity folded | — | Qt D-Bus | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt GUI | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt Network | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt Quick | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt Quick Widgets | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt SVG | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt Wayland Compositor | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt Widgets | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Matched | qt | Qt Core | qt-module d1 |  |
| Matched | openssl | openssl@3 | package d1 |  |
| Matched | webrtc | webrtc | package d1 | matched a ghost node: real external dependency with no known HarmonyOS package (fetch-deps reports need_port/needs a source port; detection correct) |
| Matched | zlib | zlib | package d1 |  |
| Matched | liblzma | xz | package d1 |  |
| Matched | openal | openal-soft | package d1 |  |
| Matched | ffmpeg | ffmpeg | package d1 |  |
| Matched | range-v3 | range | package d1 | ⚠ matched a ghost node: the DB has a similarly named known package range-v3 (hb:range-v3) -> name resolution gap, needs review |
| Matched | xxhash | libxxhash | package d1 |  |
| Matched | qr-code-generator | libqrcodegen | package d1 |  |
| Matched | hunspell | hunspell | package d1 |  |
| Matched | ada | ada | package d1 | matched a ghost node: real external dependency with no known HarmonyOS package (fetch-deps reports need_port/needs a source port; detection correct) |
| Bundled submodule | gsl | — | runtime |  .gitmodules bundled submodule (corpus-a/ThirdParty/GSL -> https://github.com/Microsoft/GSL.git): compiled together with the project source, not fetched/detected as an external package |
| Unknown pkg (OK) | — | auto_updates | package d1 | no known HarmonyOS package matched: real external dependency; the ghost node is a correct detection (fetch-deps reports need_port/needs a source port) |
| Unknown pkg (OK) | — | breakpad-client | package d1 | no known HarmonyOS package matched: real external dependency; the ghost node is a correct detection (fetch-deps reports need_port/needs a source port) |
| Unknown pkg (OK) | — | crash_reports | package d1 | no known HarmonyOS package matched: real external dependency; the ghost node is a correct detection (fetch-deps reports need_port/needs a source port) |
| Unknown pkg (OK) | — | giomm-2.68 | package d1 | no known HarmonyOS package matched: real external dependency; the ghost node is a correct detection (fetch-deps reports need_port/needs a source port) |
| Unknown pkg (OK) | — | libudev | package d1 | no known HarmonyOS package matched: real external dependency; the ghost node is a correct detection (fetch-deps reports need_port/needs a source port) |
| Unknown pkg (OK) | — | microsoft | package d1 | no known HarmonyOS package matched: real external dependency; the ghost node is a correct detection (fetch-deps reports need_port/needs a source port) |
| Unknown pkg (OK) | — | pangocairo | package d1 | no known HarmonyOS package matched: real external dependency; the ghost node is a correct detection (fetch-deps reports need_port/needs a source port) |
| Unknown pkg (OK) | — | pangoft2 | package d1 | no known HarmonyOS package matched: real external dependency; the ghost node is a correct detection (fetch-deps reports need_port/needs a source port) |
| Unknown pkg (OK) | — | ranges | package d1 | no known HarmonyOS package matched: real external dependency; the ghost node is a correct detection (fetch-deps reports need_port/needs a source port) |
| Unknown pkg (OK) | — | rnnoise | package d1 | no known HarmonyOS package matched: real external dependency; the ghost node is a correct detection (fetch-deps reports need_port/needs a source port) |
| Unknown pkg (OK) | — | tde2e | package d1 | no known HarmonyOS package matched: real external dependency; the ghost node is a correct detection (fetch-deps reports need_port/needs a source port) |
| Unknown pkg (OK) | — | tg_owt | package d1 | no known HarmonyOS package matched: real external dependency; the ghost node is a correct detection (fetch-deps reports need_port/needs a source port) |
| Unknown pkg (OK) | — | tl | package d1 | no known HarmonyOS package matched: real external dependency; the ghost node is a correct detection (fetch-deps reports need_port/needs a source port) |
| Unknown pkg (OK) | — | tlottie | package d1 | no known HarmonyOS package matched: real external dependency; the ghost node is a correct detection (fetch-deps reports need_port/needs a source port) |
| Unknown pkg (OK) | — | tmc | package d1 | no known HarmonyOS package matched: real external dependency; the ghost node is a correct detection (fetch-deps reports need_port/needs a source port) |

Class counts: Build tool×3, ★False positive×1, Matched×12, ★Missed×2, Granularity folded×11, README omitted×17, README stale×2, Unknown pkg (OK)×15, Bundled submodule×1

## 4. Dependency Closure Overview (fetch-deps --dry-run)

- Closure total 112 items: cmd_only 2, covered 1, need_port 21, provided 9, target 1, would_download 78
- Bottle directly downloadable: boost, jpeg-turbo, libavif, libheif, xz, lz4, minizip, openal-soft, openssl@3, opus, protobuf, xxhash, zlib, glib, glibmm, hunspell, ffmpeg, libjxl, openh264, libvpx, libxcb, libxkbcommon, cmark-gfm, pango, libqrcodegen, icu4c@78, zstd, zlib-ng-compat, dav1d, libpng, libde265, libtiff, webp, x265, abseil, bison, python-setuptools, pcre2, dbus, util-linux
- Command-only fetch (cmd_only): aom, ca-certificates
- Needs own port (need_port): ada, microsoft, range, tde2e, tg_owt, tl, breakpad-client, giomm-2.68, libudev, pangocairo, pangoft2, rnnoise, auto_updates, crash_reports, ranges, tlottie, tmc, webrtc, KF archive, KF coreaddons
  - ada: ?
  - microsoft: ?
  - range: ?
  - tde2e: ?
  - tg_owt: ?
  - tl: ?
  - breakpad-client: ?
  - giomm-2.68: ?
  - libudev: ?
  - pangocairo: ?

## 5. Full Direct Dependency List (portgraph depth-1)

| Node | Type | Edge | port_status | Depth |
|---|---|---|---|---|
| KF archive | framework | runtime | unknown | 1 |
| KF coreaddons | framework | runtime | unknown | 1 |
| KF desktoptojson | framework | runtime | unknown | 1 |
| ada | package | runtime | unknown | 1 |
| auto_updates | package | runtime | unknown | 1 |
| boost | package | runtime | ported | 1 |
| breakpad-client | package | runtime | unknown | 1 |
| cmark-gfm | package | runtime | ported | 1 |
| crash_reports | package | runtime | unknown | 1 |
| ffmpeg | package | runtime | ported | 1 |
| giomm-2.68 | package | runtime | unknown | 1 |
| glib | package | runtime | ported | 1 |
| glibmm | package | runtime | ported | 1 |
| hunspell | package | runtime | ported | 1 |
| jpeg-turbo | package | runtime | ported | 1 |
| libavif | package | runtime | ported | 1 |
| libheif | package | runtime | ported | 1 |
| libjxl | package | runtime | ported | 1 |
| libqrcodegen | package | runtime | ported | 1 |
| libudev | package | runtime | unknown | 1 |
| libvpx | package | runtime | ported | 1 |
| libxcb | package | runtime | ported | 1 |
| libxkbcommon | package | runtime | ported | 1 |
| libxxhash | package | runtime | ported | 1 |
| lz4 | package | runtime | ported | 1 |
| microsoft | package | runtime | unknown | 1 |
| minizip | package | runtime | ported | 1 |
| openal-soft | package | runtime | ported | 1 |
| openh264 | package | runtime | ported | 1 |
| openssl@3 | package | runtime | ported | 1 |
| opus | package | runtime | ported | 1 |
| pango | package | runtime | ported | 1 |
| pangocairo | package | runtime | unknown | 1 |
| pangoft2 | package | runtime | unknown | 1 |
| protobuf | package | runtime | ported | 1 |
| range | package | runtime | unknown | 1 |
| ranges | package | runtime | unknown | 1 |
| rnnoise | package | runtime | unknown | 1 |
| tde2e | package | runtime | unknown | 1 |
| tg_owt | package | runtime | unknown | 1 |
| tl | package | runtime | unknown | 1 |
| tlottie | package | runtime | unknown | 1 |
| tmc | package | runtime | unknown | 1 |
| webrtc | package | runtime | unknown | 1 |
| xxhash | package | runtime | ported | 1 |
| xz | package | runtime | ported | 1 |
| zlib | package | runtime | ported | 1 |
| Qt Core | qt-module | uses-module | ported | 1 |
| Qt D-Bus | qt-module | uses-module | blocked | 1 |
| Qt GUI | qt-module | uses-module | ported | 1 |
| Qt Network | qt-module | uses-module | ported | 1 |
| Qt Quick | qt-module | uses-module | ported | 1 |
| Qt Quick Widgets | qt-module | uses-module | ported | 1 |
| Qt SVG | qt-module | uses-module | ported | 1 |
| Qt Wayland Compositor | qt-module | uses-module | blocked | 1 |
| Qt Widgets | qt-module | uses-module | ported | 1 |

## 6. Methodology

- Comparison scope: portgraph direct deps (depth-1 edges) vs deps declared in README/INSTALL; the closure is only an artifact overview.
- Attribution evidence: for unmatched items, automatically grep the cloned repo's build files (find_package/pkg_check_modules/target_link_libraries/vcpkg, etc.).
- ★ classes (missed-dep / resolution-gap / false-positive) are bug candidates requiring manual confirmation; the rest are expected differences.
- Agent-readable report: `tests/e2e/reports/corpus-a.report.json`
