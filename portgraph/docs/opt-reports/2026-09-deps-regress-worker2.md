# REGRESS-REPORT: portgraph dependency analysis "regression + generalization" two-phase test report

> Date: 2026-09-19 | Branch: `worker2-deps-regress` (baseline `416ef8d` → 6 commits this round)
> Workspace: `~/harmony-workspace/worker2/portgraph/`
> Bottom line first: **Phase 1 regression passed on the first try (e2e corpus-b report byte-identical to the baseline, recall=100%/precision=95%/bug=0, every category count of the 89-item closure identical); Phase 2 generalization on two high-star out-of-corpus projects, gen-d + gen-g/libgen-g, exposed 4 classes of tool bugs (all fixed at the root cause with 6 new unit tests, 87→93 all passing), and additionally characterized 2 data-source gaps and 10+ project-specific conventions/observations; after all fixes, the reports for the four e2e corpus projects stay byte-identical (no cross-project regression)**.

---

## Phase 1: corpus-b regression (first-pass analysis correctness check)

### 1.1 Test setup and procedure

- Code: `worker2-deps-regress` @ `416ef8d` (with all integration fixes) + this round's fixes
- Corpus clone: `workspace/corpus-b` @ master `2b540fe` (corpus-b-core `8c2f77a` / corpus-b-deps `6525edb`, same source as the baseline report)
- Procedure (strictly fresh, no manual touch-up of oracle/overrides):
  1. `rm portgraph.db && portgraph.py ingest all --offline` (hb-core 4758 formulas / cmdpkgs 1248 packages gate=PASS / kb 63 Qt modules)
  2. `portgraph.py scan workspace/corpus-b`
  3. `portgraph.py deps corpus-b --json`
  4. `portgraph.py fetch-deps corpus-b --dry-run --json`
  5. `tests/e2e/run_e2e.py run --project corpus-b --fresh-db` (the oracle is the corpus-b-deps engine-rewrite version, reviewed=true, 25 entries)

### 1.2 First-pass analysis correctness check results (item by item)

| Check dimension | Result | Details |
|---|---|---|
| e2e metrics | ✅ identical to baseline | recall=100% / precision=95% / bug_candidates=0 (same values as baseline §1) |
| Portability verdict | ✅ | verdict=blocked, 8 blockers (ALSA/CoreAudio/D-Bus/PulseAudio/systemd/Win32 interfaces + qtmod:dbus/x11extras) + 4 unknowns, matching baseline §2 item by item |
| Direct dependencies (depth-1) | ✅ | 34 items = 18 packages (14 resolved to bottles + 4 ghosts) + 16 qt-modules, list matching baseline §5 line by line |
| Dependency classification | ✅ | link 47 / runtime 51 / build_tools 22 / vendored 13 (10 require_source_dep + mnxdom FetchContent + corpus-b-core/corpus-b-deps submodules) / env 4 / qt_modules 21 |
| Optional/conditional dependencies | ✅ | jack/mnxdom (option guard, required=False + "default OFF" note), msdfgen/pipewire (conditional block + ohos_note) all annotated correctly |
| Version checks | ✅ no false conflicts | 0 version_req entries (the corpus-b-deps manifest carries no versions), Qt 6.8→satisfied, all any/unknown, no conflict |
| need_port verdicts | ✅ 4/4 correct | msdfgen/opusenc/pipewire/json_schema_validator — each rechecked against hb-core (4758) and cmd-pkgs (1248): no bottle exists, source pinned in corpus-b-deps/recipes (matches the baseline agent's final verdict) |
| fetch-deps closure | ✅ | 89 items: cmd_only 1 (ca-certificates) / need_port 4 / provided 16 / target 1 / vendored 10 / would_download 57, identical to baseline §4 |
| Report regeneration | ✅ **byte-identical** | diff against the `tests/e2e/reports/corpus-b` baseline only in `generated_at` and `repo_path` (baseline was generated in the worker1 workspace) |
| DB determinism | ✅ | fresh DB output vs the old main database differs in only 2 **improvements** (icu4c@78/fontconfig artifact version + bottle URL filled in; the old database was built by pre-integration code; classification counts unchanged) |

**Conclusion: first-pass analysis correctness PASS, with no manual touch-up.**

### 1.3 Timing and comparison with the previous round

| Step | This round (range over 3 runs) | Previous round's report (docs/opt-reports/2026-09-deps-test-worker4.md) |
|---|---|---|
| `ingest all --offline` (fresh DB) | 1.7s | — (no corpus-b timing last round) |
| `scan` (5729 source files + corpus-b-core/corpus-b-deps submodules) | 4.44–4.60s | — |
| `deps --json` (by app name, no rescan) | 4.43–4.52s | — |
| **deps end to end (scan + ingest + report --json)** | **8.9–9.1s** | gen-a 3.05s / gen-e 0.63s / gen-f 0.81s (same machine, different projects) |
| `fetch-deps --dry-run` (89-item closure) | 0.063–0.070s | gen-a 112 items 0.06s / gen-e 0.05s / gen-f 0.05s |
| e2e harness end to end (private DB+scan+analyze+fetch+reconciliation) | 4.65s | — |

Interpretation: corpus-b wasn't timed separately last round, so there's no same-project number to compare directly; compared with projects measured last round, corpus-b (5729 source files + about 6300 corpus-b-deps engine files, a larger CMake surface) at 9.0s is in the same order of magnitude as gen-a (6293 files, 3.05s), a reasonable scale-up for its scan size; **the fetch-deps closure BFS confirms last round's conclusion: not a bottleneck** (0.06–0.07s vs 0.05–0.06s). No sign of performance regression.

### 1.4 Tool bugs found and fixed in Phase 1 (2 items, commits `1f7cca5` / `ccf958e`)

1. **hb version extraction: `.7z` extension + hyphenated patch-number versions → garbage version + bottle URL 404**
   - Symptom: in the env_deps section of the corpus-b deps report, `imagemagick available_version=31.7z` (real version 7.1.2-31).
   - Root cause: `_URL_VER_RE`'s extension list lacked `7z` and its version group didn't allow a `-N` patch segment, so the trailing `31.7z` of `ImageMagick-7.1.2-31.7z` was taken as the version; `bottle_url()` then built `imagemagick-31.7z_1.arm64_ohos.bottle.tar.gz`.
   - Fix: version group `(?:_\d+)? → (?:[_-]\d+)?`, and `7z` added to the extension list.
   - Verification: re-parsing all 4758 formulas changed only 14 versions; each was checked against the bottle server with curl HEAD — **13 returned 200 OK** (including imagemagick/imagemagick@6, which were 404 before the fix); inxi's 404 is a data-source gap (see §3.2).
2. **Gaps in the deps classification tables: 7 names treated as ordinary packages with a misleading "needs cross-compiling from source" warning**
   - `gmock` (linked into the `${MODULE_TEST}` test target) → TEST_FRAMEWORKS;
   - `mmdevapi/msi/taskschd/userenv` (target_link_libraries inside corpus-b-core's `OS_IS_WIN` block; 8 sibling libraries in the same block were already in the table) → WIN32_SYSTEM_LIBS;
   - `AudioToolbox/Carbon/CoreMIDI` (find_library inside an `OS_IS_MAC` block) → INTERFACE_BOUND_PACKAGES (platform-iface + HarmonyOS alternative note).
   - Effect: corpus-b deps link 47→46, test 0→1, misleading warnings 9→2; the e2e baseline is unaffected (report byte-identical).

### 1.5 Phase 1 observations (not fixed, recorded following the baseline's conventions)

- `embind` (src/web/audioengine, a `Q_OS_WASM` wasm-only block) / `gcrashpad` (an internal target name of the crashpad source dependency in corpus-b-deps): project-specific conventions; such conditional blocks/target names can't be judged generically.
- The coincidental resolution `global → hb:global` (the GNU Global tagging system), need_port ghosts without source_url, and require_dep conditional blocks not being evaluated (msdfgen/pipewire on the conservative side): all residuals recorded last round, with the same behavior this round.

---

## Phase 2: generalization on high-star GitHub Qt projects

### 2.1 Project selection

| Project | Stars/clone | Reason for selection |
|---|---|---|
| **gen-d** | ~8.3k★ @ `70aecee` (+11 submodules shallow-initialized) | On the suggested list; a C++ Qt5(6) audio workstation, mixed CMake+pkg-config+vcpkg+autotools build, wide dependency surface (audio stack in the same domain as corpus-b but structured differently) |
| **gen-g/libgen-g** | `f20829f` | The C++ core of gen-g from the suggested list; Qt6+FFmpeg+JUCE+SWIG multi-language bindings |
| ~~calibre~~ | — | **Explicitly dropped**: a PyQt app, outside the C++/CMake scanning scope (see the gen-g-qt evidence in §2.4: the behavior is "gracefully empty", not a crash) |
| gen-g-qt | `047f4a2` | Used only as evidence of the PyQt scope boundary, not an analysis target |

The four e2e corpus projects (corpus-a/corpus-b/corpus-c/corpus-d) and the projects used last round (gen-a/gen-e/gen-f) were avoided.

### 2.2 gen-d (5273 source files, Qt 5.15/6.0, cmake+qmake)

**Manual reference baseline**: root CMakeLists.txt (WANT_* options + FIND_PACKAGE blocks), cmake/modules/Find*.cmake (22 in-house modules), vcpkg.json, .gitmodules (11 submodules), and the build files of submodules such as gen-p/calf/swh/veal/adplug/gme.

**Correctly detected (spot-checked)**: FFTW `>=3.0.0` (pkg_check; unknown after alias merging is by design), gtk+-2.0 `>=2.12.0` → hb:gtk+ 2.24.33 satisfied (hb does have a GTK2 formula), jack `>=0.77` → 1.9.22 ✓, Portaudio `>=19` → 19.7.0 ✓, X11/x11extras → platform-iface/blocked ✓, libjack dlopen → cmdpkgs:jack ✓, WANT_SDL(ON)→SDL2 required, WANT_JACK→optional ✓, gen-p submodule dependencies (fftw/boost/mxml/liblo) merged in correctly, 22 vendored items (submodules+ExternalProject+FetchContent pthreads4w all with pinning info).

**4 classes of tool bugs fixed (commits `2a64818` / `ddeb1d0`)**:

| # | Problem | Root cause → fix |
|---|---|---|
| 1 | `PackageHandleStandardArgs` ghost | Misspelled name `findpackagehandlestandardargs` in `_FINDPKG_SKIP` (with the Find prefix it never matches) → corrected + `CMAKE_BUILTIN_PACKAGES` classification on the consumer side |
| 2 | `Perl`/`PythonInterp` host interpreters treated as runtime dependencies (perl got an edge to hb:perl) | Added perl/pythoninterp to BUILD_TOOL_FINDPKG (filtered on the graph side + build-tool on the report side) |
| 3 | `CxxTest` test framework treated as a runtime link | Added cxxtest to TEST_FRAMEWORKS |
| 4 | `OggVorbis` composite module-name ghost | gen-d's FindOggVorbis is internally find_package(Ogg/Vorbis) (both real dependencies already detected separately) → PKG_ALIASES oggvorbis→libvorbis |
| 5 | `libpulse`/`asound`/`pulse` reported as need_port | PulseAudio/ALSA pkg-config names and library-name forms → added the three to INTERFACE_BOUND_PACKAGES (platform-iface + HarmonyOS AudioRenderer guidance) |
| 6 | `OpenGL` ghost | On OHOS this is the GLES/EGL system capability → _FINDPKG_SKIP + CMAKE_BUILTIN_PACKAGES (system-lib + adaptation note) |
| 7 | Versioned library names `fluidsynth-1/2/3`/`sfftw` not merged | veal FindFluidSynth's macOS dylib variants / swh's single-precision fftw → merged via PKG_ALIASES |
| 8 | `FluidSynth` falsely reported "no artifact" on the report side | The graph side resolved cmdpkgs:fluid-synth via the dashless fallback while the report-side ladder had no dashless step (split semantics) → explicit alias fluidsynth→fluid-synth (2.2.0 vs 2.4.6 = satisfied) |

**Effect**: link 79→70 / build_tools 22→26 / test 0→1 / closure 132→125 / **need_port 17→12** / misleading warnings 24→17. The remaining 12 need_port items were each verified to **have no bottle, so unknown-ok is correct**: carla-native-plugin, carla-standalone (Carla plugin host), fltk/ntk/ntk_images (zyn GUI), gig (libgig), oss, sndio (BSD audio), sdl (SDL1), suil-0, suilmodules, wine (WANT_VST).

**Observations (project-specific conventions/conservative by design, recorded but not fixed)**:
- `sdl3` comes from `cmake/apple/MacDeployQt.cmake` (pkg_check in a macOS packaging script) → false positive (has a bottle, only an extra download); there's no generic rule to recognize packaging/deploy scripts.
- `SDL` (v1) comes from game-music-emu's `player/` (`add_subdirectory(... EXCLUDE_FROM_ALL)`, not built) → false positive; the scanner isn't aware of EXCLUDE_FROM_ALL.
- `FLTK` soft-optional (no REQUIRED/QUIET, failure only downgrades the Zyn GUI) → conservatively required=True; find_package semantics make this undecidable.
- `bash-completion` conflict=true (veal's vendored configure.ac requires >=2.0, hb has 1.3 — Homebrew's bash-completion is the 1.x line); bash-completion itself is a host-side completion package.
- Vendored display-name noise (the `src/3rdparty` parent directory name, the `doc/wiki` documentation submodule); the `suilmodules` in-house Find module name ghost.
- target_link/AC_CHECK_LIB noise inside the swh/veal vendored LADSPA plugins (blo/db/gverb/iir/mx/pitchscale/rms/lash/libbinio): **not skipping submodule paths is intentional** (the corpus-b-core counterexample: the framework submodule's ExtDepsManifest must be scanned); the semantic boundary is open for discussion.
- `qt.min_version=None`: the version in `find_package(Qt${QT_VERSION_MAJOR} ${gen-d_QT_MIN_VERSION} ...)` goes through a variable and isn't resolved (component variables are supported, version variables aren't) — a minor gap.

### 2.3 gen-g/libgen-g (316 source files, Qt6, cmake)

**Manual reference baseline**: root/src CMakeLists.txt (option defaults: ENABLE_MAGICK ON / ENABLE_OPENCV OFF / ENABLE_WAYLAND_CAPTURE ON), bindings/ (SWIG bindings for five languages), cmake/Modules/Find*.cmake, the external/godot-cpp submodule.

**Correctly detected**: Qt6 Core/Gui/Widgets required ✓, `FFmpeg REQUIRED` ✓, `Resvg`→hb:resvg ✓, `ImageMagick` (the 7.1.2-31 fixed in Phase 1 reproduces for real here) ✓, `OpenCV 4`→cmdpkgs 4.9.0 (ENABLE_OPENCV OFF → required=False, option guard correct) ✓, `Catch2 QUIET`→test classification ✓, `Protobuf 3` vs hb 12=satisfied ✓, godot-cpp vendored ✓, wayland-capture dlopen hint ✓.

**4 groups of tool bugs fixed (commit `f543d9f`)**:

| # | Problem | Root cause → fix |
|---|---|---|
| 1 | SWIG binding toolchain treated as runtime dependencies: `SWIG/Java/JNI/Ruby/PythonLibs` got runtime edges to hb:ruby/hb:swig, and java/jni/pythonlibs became need_port ghosts | The find_package calls in bindings/ are all for host-side binding generation → added swig/ruby/java/jni/pythonlibs to BUILD_TOOL_FINDPKG |
| 2 | The resolution ladder of `libpipewire-0.3` lacked the combined form | Needs stripping both the lib prefix and the version suffix (stripping either alone doesn't match) → resolve_pkg_name/resolve_package gain the combined stripped[3:] candidate (verified by a unit test constructing hb:pipewire) |
| 3 | `dbghelp`/`imagehlp` missing Win32 libraries | WIN32 block exception handling/DirectShow (ole32/strmiids/uuid in the same block were already in the table) → WIN32_SYSTEM_LIBS |
| 4 | 5 separate ghosts `opencv_core/video/highgui/dnn/tracking` | OpenCV 4 imported-target name literals (inside the ENABLE_OPENCV OFF block) → merged into opencv via PKG_ALIASES; `jsoncppd` (Findjsoncpp's debug variant) → jsoncpp |

**Effect**: link 30→19 / build_tools 11→18 / closure 74→68 / **need_port 7→4**. The remaining 4 items were each verified to **have no bottle, so unknown-ok is correct**: `babl` (color space conversion), `libpipewire-0.3`/`libspa-0.2` (Wayland screen capture, Linux-only, default ON), `gen-gaudio` (JUCE audio library, REQUIRED).

**Observations**: `Protobuf` required=True — it's in the `else()` branch inside the ENABLE_OPENCV block (evaluated only after OpenCV_FOUND), and the option guard conservatively not evaluating else/elseif is a **documented design**; `babl`/`babl-0.1` double entries (find_package and Findbabl's find_library, merged in the closure but not on the report side, cosmetic).

### 2.4 gen-g-qt (evidence for the PyQt scope boundary)

Scan result: `build=unknown / sources=20 / qt_modules=[] / deps_linked=[]` — **gracefully empty, no crash**. Confirmed: portgraph deps analysis targets C++/CMake/qmake projects; PyQt apps (gen-g-qt, and calibre likewise) are outside its scope and need a separate evaluation (Python-side dependencies + Qt runtime packaging). This is a **scope boundary**, not a defect.

---

## 3. Problem characterization summary

### 3.1 Tool bugs (all fixed + unit-tested, 5 commits)

| Category | Items | Impact |
|---|---|---|
| Data-source parsing (ingest) | imagemagick/imagemagick@6 versions `31.7z`/`56.7z` → bottle URL 404 | fetch-deps download failure |
| Classification table gaps | gmock/cxxtest (test), mmdevapi/msi/taskschd/userenv/dbghelp/imagehlp (win32), AudioToolbox/Carbon/CoreMIDI (macOS frameworks), asound/pulse/libpulse (audio platform interfaces), opengl (system GLES) | Misleading "needs cross-compiling from source" warnings / false need_port reports |
| Host tools misjudged | perl/pythoninterp/pythonlibs/swig/ruby/java/jni treated as runtime dependencies | Ghosts/useless downloads |
| Resolution ladder | PackageHandleStandardArgs misspelling, missing combined lib-prefix + version-suffix form, split semantics for fluidsynth on the report side, oggvorbis/fluidsynth-N/sfftw/opencv_*/jsoncppd not merged | Ghost nodes/duplicate entries |

### 3.2 Data-source gaps (data-side problems, not tool problems)

1. **inxi bottle not published**: the formula declares an arm64_ohos bottle (with sha256), but every single/double-hyphen variant on the bottle server returns 404 — the URL built after the version-extraction fix also returns 404.
2. **cmd-pkgs names contain versions**: `sdl12-compat-1.2.68` (the version is embedded in the package name) — `sdl` (SDL1) can't be aliased stably (it breaks on upgrade); the SDL1 detection stays unknown-ok.

### 3.3 Project-specific conventions / documented design (recorded but not fixed)

embind (wasm-only block), gcrashpad (corpus-b-deps internal target), sdl3 from MacDeployQt.cmake (packaging script), SDL from the gme player (EXCLUDE_FROM_ALL), FLTK/babl soft-optional find_package, Protobuf in a conservatively-handled else branch, swh/veal vendored LADSPA noise (not skipping submodules is required by the corpus-b-core counterexample), vendored display-name noise, bash-completion scale conflict (the data is true), Qt version via a set() variable, the global→hb:global coincidence (residual from last round), need_port ghosts without source_url (residual from last round).

---

## 4. Regression safety

- **The four e2e corpora**: corpus-a (53%/60%/2), corpus-b (100%/95%/0), corpus-c (100%/23%/0), corpus-d (100%/100%/0) — after all fixes landed, a full rerun **three times** produced reports **byte-identical** to the committed baselines (diff only in timestamps/repo_path), and closure counts were checked unchanged per project.
- **Unit tests**: 87 → **93 all passing** (6 new: Testcorpus-bRegressTables, test_gen-d_regress_classifications, test_gen-g_bindings_and_ladder, test_gen-g_ladder_node_resolution, test_gen-g_win32_and_target_merge, test_gen-d_iface_libnames_and_merge + extended URL version-extraction cases).
- **bottle URL authenticity**: each of the 14 formulas whose version changed was checked with HEAD (13×200 / 1×404 = data-source gap); imagemagick URL before/after the fix (404→200).

## 5. Commit list (worker2-deps-regress, baseline 416ef8d)

| commit | Content |
|---|---|
| `1f7cca5` | fix(ingest): fix URL extraction for 7z/hyphenated versions (imagemagick 31.7z→7.1.2-31) + verification across all formulas |
| `ccf958e` | fix(deps): 3 table gaps exposed by the corpus-b regression (gmock/win32 libraries/macOS frameworks) |
| `2a64818` | fix(deps): 5 classification/resolution gaps exposed by the gen-d generalization round |
| `f543d9f` | fix(deps): binding toolchain/win32 library/target-name merging gaps exposed by the libgen-g generalization round |
| `ddeb1d0` | fix(deps): gen-d deep-dive round — platform-interface library names/versioned library-name merging/fluidsynth split semantics |
| (this one) | docs: REGRESS-REPORT.md |
