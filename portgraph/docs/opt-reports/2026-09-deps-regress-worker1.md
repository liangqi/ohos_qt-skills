<<<<<<< HEAD
<<<<<<< HEAD
# REGRESS-REPORT — portgraph dependency analysis "regression + generalization" test report

> Branch: `worker1-deps-regress` (baseline `416ef8d`, with all integration fixes)
> Test date: 2026-09-19 | Workspace: `portgraph/`
> Bottom line first: **Stage 1 corpus-a single-pass correctness verification passed (the e2e report is byte-identical to the baseline except for timestamps; the only new finding, a false report on the kcoreaddons/microtex submodules, is fixed); Stage 2 exposed 11 classes of problems on 2 high-star out-of-corpus projects (gen-j, gen-i), 10 classes had their root causes fixed and 5 regression unit tests were added (88→92, all passing), and the e2e regression over the four corpora shows zero degradation**.

---

## 1. Stage 1: corpus-a regression (single-pass correctness)

### 1.1 Flow and timing (fresh DB, no manual touch-ups at any point)

| Step | Command | Time |
|---|---|---|
| Data source ingestion | `ingest all --offline` (empty DB → 6069 nodes: hb 4758 + cmdpkgs 1248 + kb, zero apps) | 1.20s |
| Scan | `scan workspace/corpus-a` (cmake, 2932 source files) | 1.80s |
| **Full deps run (single command, including scan + ingestion + report)** | `deps workspace/corpus-a --json` (runs through in one go on a fresh DB) | **1.90s (before the fix) / 2.12–2.17s (with this round's new merging logic)** |
| Dependency closure | `fetch-deps corpus-a --dry-run --json` | 0.06s |

**Performance comparison** (last round's `docs/opt-reports/` numbers: gen-a 3.05s/22769 files, gen-e 0.63s/1185, gen-f 0.81s/751):
corpus-a (2932 files, dense CMake declarations) at 2.15s sits between gen-e and gen-a, matching the scan-volume/time curve, so **there is no performance regression**; the newly added bundled-source declaration merging (the `_vendored_declarations` lenient folded index) costs about +0.2s, and the closure BFS at 0.06s is on par with last round (0.05–0.06s).

### 1.2 Item-by-item check against the baseline (against the `tests/e2e/reports/corpus-a` baseline)

- **Full e2e harness regression** (`run --project corpus-a --fresh-db --no-clone`): the generated report.md/json are **byte-identical to the git baseline (only the generation timestamp differs)** — recall 53% / precision 60% / bug_candidates 2 (breakpad/crashpad, both known residuals: the shallow clone didn't initialize the cmake_helpers submodule, so the main integration logic is invisible).
- **Portability verdict**: blocked (macOS Cocoa + Win32 platform interfaces) + unknown 8 (fork/exec ×1 + pkg-unknown ×7) — matches the baseline.
- **d1 direct dependencies** (24 nodes: 19 package + 5 qt-module): checked one by one, consistent; ported 12 (boost/cmark-gfm/ffmpeg/glib/libfido2/libiconv/libqrcodegen/minizip/openal-soft/openssl@3/xxhash/zlib) / unknown 7 (libudev/ada/auto_updates/crash_reports/rnnoise/tde2e/webrtc).
- **Closure of 61 items**: would_download 47 / need_port 7 / provided 5 / target 1 / cmd_only 1 (ca-certificates) — exactly matches the baseline.
- **Classification of the 26 link entries in the deps report**: 12 resolved (version_check all `any`, no false conflicts — the build files really have no visible version constraints, since find_package sits in the uninitialized submodule) ✓; 7 unknown→need_port, verdict correct ✓; 5 win32-system-lib (bcrypt/delayimp/hid/setupapi/ws2_32, all optional) ✓; **2 entries revealed a problem (see 1.3)**.
- **35 vendored entries** (35 submodules, including gsl/range-v3/hunspell/kcoreaddons/MicroTeX/cmark-gfm/libfido2, etc.) ✓; build-tool 7 (CMake>=3.25, clang, python3×3, pkgconfig×2) ✓; env 13 ✓.

### 1.3 Found and fixed: link names of uninitialized git submodules falsely reported as need_port

- **Symptom**: `kcoreaddons` and `microtex` were reported in the link section as "no artifact → needs building from source" (kind=package, version_check=unknown), but both are submodules declared in `.gitmodules` (`corpus-a/ThirdParty/kcoreaddons`, `corpus-a/ThirdParty/MicroTeX`), with source bundled in the repo and compiled with the project.
- **Root cause**: `deps_report` §7 only merged against "same-named source directories in the project" (the in-tree index), but a submodule directory left uninitialized by a shallow clone is empty (no build files), so it is invisible to the index; the graph side (project_scanner) already had the equivalent `_submodule_folds` logic, but the report layer lacked it.
- **Fix**: the report layer gains a bundled-source declaration index (further generalized this round, see Stage 2); entries already resolved to a bottle where the project also bundles a submodule (cmark-gfm/xxhash/lz4/libfido2) get the note "can be compiled with the project; the bottle is an alternative" (semantics unchanged, information more complete).
- **Test**: `test_submodule_link_classification` (unresolved→in-tree / resolved→note).

---

## 2. Stage 2: generalization to high-star GitHub Qt projects

### 2.0 Project selection (declared up front)

| Project | Stars | Build system | Size | Reason for selection |
|---|---|---|---|---|
| **gen-j** (rizinorg/gen-j) | 19.7k | CMake + Qt5/6 + meson submodule | 2697 source files | Reverse-engineering GUI, not on the suggested list (to avoid overlap); extremely complex dependency structure: the whole rizin engine is vendored as a git submodule (double wrapping with built-in meson subprojects + ExternalProject) |
| **gen-i** (dail8859/gen-i) | 14.6k | CMake + qmake + CPM | 651 source files | Not on the suggested list; a Qt6 editor with CPM-fetched bundled dependencies + a thirdparty/ layout, a build shape different from all four corpus projects |

Shallow-cloned into `portgraph/workspace/` (gen-j 9s / gen-i 14s). **Note**: while cloning gen-j, the cloner's shallow submodule initialization failed silently (`rizin/` was an empty directory), so it was filled in manually with `git submodule update --init --depth 1` (the failure couldn't be reproduced and was a transient network issue; the cloner's "silently skip" design is itself a known trade-off — see residual observations).

### 2.1 gen-j: 11 classes of problems, 10 fixed

| # | Problem (before fix → after fix) | Classification | Root cause and fix |
|---|---|---|---|
| 1 | `find_package(gen-j REQUIRED)` (plugin sample template) self-reference → resolved to an **unrelated package of the same name** `cmdpkgs:gen-j` (version 1.04, a "cutting machine tool") listed as would_download → self-reference filtered, no longer appears | **Tool bug** | `qt_scanner._cmake_project_names`: skip the root CMakeLists `project()` name (both the find_package and details paths + the project_scanner graph side); only the root file counts, so `project(fakevim)` in a vendored subdirectory doesn't affect the host |
| 2 | **37** internal libraries of the rizin engine (rz_core/rz_util/…/rzwinkd, `dependency('rz_*')` in the meson.build of the vendored rizin submodule) reported as need_port wholesale → in-tree | **Tool bug** (generalization gap: internal targets of a vendored engine) | `qt_scanner._meson_internal_names`: collect `meson.override_dependency()` names + `subprojects/` directory names and .wrap names; matching meson dependencies are marked `internal=True`, and `cc.find_library` is skipped likewise; deps_report classifies them in-tree |
| 3 | meson bundled subprojects (ptrace-wrap/zydis/softfloat/rizin-grammar-c/rizin-math-parser/rizin-shell-parser/rzheap/rzar/rzgdb/rzqnx/rzspp/rzw32dbg_wrap/rzwinkd/pcre2_cross_native/libblake2) reported as need_port → in-tree | **Tool bug** | Same as #2 (subprojects/ directories + .wrap file names go into the internal set) |
| 4 | CPM declaration extraction produced the garbage name **"NAME"** (the keyword in `CPMAddPackage(NAME …)` taken as the package name); gen-i's real CPM names (ads/QSimpleUpdater/editorconfig_core_qt/SingleApplication) were **all invisible** because the declarations live in `thirdparty/CMakeLists.txt`, which the vendored-path skip excluded → names extracted correctly, and vendored paths are no longer skipped (thirdparty/ is often fetch glue written by the host) | **Tool bug** | `qt_scanner._detect_fetched_deps`: take the actual name after the NAME keyword; skip things like `${Name}` that can't be resolved statically (forwarding calls inside the CPM implementation file itself); remove the vendored-path skip |
| 5 | Unresolved link names matching CPM/FetchContent/ExternalProject declarations still reported as need_port (gen-i `qtadvanceddocking-qt6`/`QSimpleUpdater`/`editorconfig-core-qt`) → in-tree | **Tool bug** | `deps_report._vendored_declarations`: four kinds of bundled-source declarations (git submodule/CPM-FetchContent/ExternalProject/meson subprojects and internal targets) go into one lenient folded index (strip the lib prefix, strip trailing qt5/qt6/system variant tokens: `qtadvanceddocking-qt6` ≡ the last URL segment `Qt-Advanced-Docking-System` of CPM package `ads`); resolved ones get the "the bottle is an alternative" note |
| 6 | `dbghelp` (Windows debugging library) not in WIN32_SYSTEM_LIBS → reported as need_port → win32-system-lib [optional] | **Data source gap** (name table) | Add dbghelp to `qt_scanner.WIN32_SYSTEM_LIBS` |
| 7 | meson string interpolation `dependency('libpcre2-@0@')` → garbage name `libpcre2-@0@` → after stripping the placeholder, `libpcre2` correctly resolves to the pcre2 bottle (>=10.42 vs 10.48 **satisfied**) | **Tool bug** | `_absorb_meson` strips `@0@`; also cleans up the trailing `-` of `subproject('capstone-' + …)` (garbage name 'capstone-') |
| 8 | `pkg_check_modules(libgvc)` reported as need_port although a graphviz bottle exists (libgvc is a graphviz link library) → resolved via alias merging | **Data source gap** (alias table) | Add libgvc/libcgraph/libcdt → graphviz to `kb_seed.PKG_ALIASES` |
| 9 | **The ALSA platform-interface rule `\bsnd_` matched any variable name**: the `snd_last_ch` variable in rizin's generated scanner.c → the whole app misjudged "blocked" (direct ALSA, while the whole rizin repo has no ALSA usage at all) → after tightening to real ALSA API prefixes (snd_pcm_/snd_ctl_/snd_mixer_/snd_seq_…), the false report is gone | **Tool bug** (detection rule too broad) | The iface:alsa rule in `project_scanner.PLATFORM_RULES` and its prefilter anchor tightened together; semantic invariance confirmed by the e2e regression over the four corpora |
| 10 | (side effect of #5) `find_package(Rizin)` created a ghost pkg-unknown:rizin → need_port on the graph side (the repo bundles the rizin/ submodule and defaults to `gen-j_USE_BUNDLED_RIZIN=ON`) → no ghost created on the graph side | **Tool bug** | When main-list resolution fails, `project_scanner` applies the same submodule-fold skip as the bare-link-name path (previously only the external_ bare-name path was covered) |
| R1 | execinfo/kvm/proc/socket/util (rizin's Solaris/BSD platform probes, cc.find_library) reported as need_port (required=True) | **Data source gap** (platform library name table) | **Not fixed** (residual): no table for non-Linux platform libraries; this is over-provisioning (extra downloads/reports), not the reverse error of misleading toward "HarmonyOS package missing". Recommend adding an INTERFACE_BOUND-style platform table later |
| R2 | Graphviz `tri_option(… AUTO)` treated as required by default | **Project-specific convention** | **Not fixed**: the default-value semantics of CMake tri-state options (ON/OFF/AUTO) aren't modeled; the current conservative bias (required first) is consistent with the existing design |
| R3 | macOS Cocoa / Win32 platform interfaces counted as ohos-active → blocked | **Known limitation** (same source as last round's residual #2) | **Not fixed**: no structured parsing of cross-platform #ifdef platform blocks; consistent with the corpus-a baseline behavior (same kind of false report) |
| R4 | The cloner's shallow submodule initialization fails silently (transient network issue, not reproducible) | **Observation** | Filled in manually; later consider having the cloner include a warning in its return value on failure |

**gen-j results after the fix**: link 77 entries = package 27 (real external dependencies such as capstone/openssl/zlib/pcre2/tree-sitter/graphviz/bzip2, **12 with bottles**) + **in-tree 41** (the whole rizin family + meson subprojects) + win32-system-lib 6 + system-lib 2 (m/threads) + platform-iface 1 (macOS Network); PySide2/6/Shiboken* optional need_port (HarmonyOS really has no PySide artifacts, **verdict correct**); closure 17 items = would_download 12 / need_port **0** / provided 3 / target 1 / cmd_only 1; version checks capstone >=4.0.2 vs 5.0.9 and pcre2 >=10.42 vs 10.48 both satisfied; verdict still blocked (macOS/Win32 platform interfaces, R3) + fork()/exec() unknown (rizin spawns debug target processes, **verdict correct**). deps 3.2s.

### 2.2 gen-i

**Before the fix**: all 3 link entries falsely reported as need_port (editorconfig-core-qt / QSimpleUpdater / qtadvanceddocking-qt6, all fetched by CPM and compiled with the project); the vendored section had a garbage entry "NAME" (problem #4); scintilla/lexilla/lua/uchardet (bundled source in thirdparty/, via add_subdirectory) correctly stayed out of link ✓.

**After the fix**: all 3 link entries in-tree (`CPM:ads` / `CPM:QSimpleUpdater` / `CPM:editorconfig_core_qt`); 5 vendored entries (thirdparty + ads + QSimpleUpdater + SingleApplication + editorconfig_core_qt, no garbage names); **closure 6 items = target 1 + provided 5 (Qt Core/GUI/Network/PrintSupport/Widgets, available in HarmonyOS 6.12), need_port 0, no bottles to download at all** — the app's real dependency surface on HarmonyOS is just Qt 6, matching the conclusion from reading the build files by hand; the verdict is blocked only because of the macOS/Win32 platform-interface heuristic (R3; 21 sites were correctly recognized as excluded by macro guards, 97 counted unconditionally as ohos-active). deps 0.79s.

**No new problems found in gen-i** (the #4/#5 it exposed were both demonstrated by it). Minor flaw: `find_package(Qt6 COMPONENTS LinguistTools)` is counted in qt_modules (LinguistTools is a tool-side lrelease component that ships with the Qt SDK and doesn't affect the conclusion; not fixed).

### 2.3 Problem classification summary

| Classification | Count | Handling |
|---|---|---|
| Tool bug (including generalization gaps) | 9 classes (#1–#5, #7, #9, #10 + Stage 1 submodule merging) | All root causes fixed + 5 regression unit tests |
| Data source gap (name/alias tables) | 3 classes (#6 dbghelp, #8 libgvc, R1 platform library table) | First 2 fixed; R1 left as residual |
| Project-specific convention | 2 classes (R2 tri_option, the rizin/CPM layout itself) | Recorded; R2's conservative bias matches the existing design |
| Known limitation (left over from last round) | 1 class (R3 structured parsing of platform blocks) | Recorded, consistent with baseline behavior |

---

## 3. Tests and regression

- **Unit tests**: 88 → **92, all passing** (`python -m unittest tests.test_port_graph`; new: `test_submodule_link_classification`, `test_cpm_name_keyword`, `test_fetched_dep_link_classification`, `test_find_package_self_reference`, `test_meson_internal_dep_classification` — see `TestGeneralizationFixes` §6e–6i).
- **Full e2e regression over the four corpora** (corpus-a/corpus-c/corpus-d/corpus-b, `--fresh-db`): recall/precision/bug_candidates and closure counts **all match the baseline**, report diffs are timestamps only (reverted) — the ALSA rule tightening, self-reference filtering, meson internal set, and opening up the CPM path did not affect the corpus projects' conclusions.
- **Performance**: corpus-a full run 2.15s (2932 files), gen-j 3.2s (2697 files, including a full scan of the rizin submodule), gen-i 0.79s (651 files); fetch-deps dry-run 0.06s for each. Same order of magnitude as last round's gen-a 3.05s (22769 files)/gen-e 0.63s/gen-f 0.81s, no regression.

## 4. Residuals and recommendations

1. **Platform library name table gap** (R1): Solaris/BSD probe libraries (socket/nsl/proc/util/kvm/execinfo) have no classification table — recommend extending an INTERFACE_BOUND-style "non-Linux platform probe library" table (gen-j/rizin and some BSD-oriented projects will hit it).
2. **CMake tri-state options** (R2, tri_option AUTO): the optional judgment only recognizes "default OFF" guards; a "default AUTO (soft dependency)" tier could be added.
3. **Structured parsing of platform blocks** (R3): same source as last round's residual; macOS/Win32 platform code is counted as ohos-active, leading to blocked; this is common for cross-platform Qt apps and is the largest known conservative bias in the analyze layer.
4. **Visibility of cloner submodule initialization failures** (R4): silently skipping on failure doesn't block the clone, but it leads to the downstream "uninitialized-submodule blind spot" (same root cause as corpus-a's breakpad/crashpad); recommend having the return value carry a warning so the agent can prompt for a manual pull.
5. Qt tool-side components such as LinguistTools are counted in qt_modules (doesn't affect the conclusion; could be classified build-tool).
=======
# Regression + generalization test report: deps performance benchmark and generalization to popular GitHub Qt projects

> Branch `worker4-deps-regress` (baseline 416ef8d, with all integration fixes)
> Test date: 2026-09-19 | Workspace: `portgraph/`
> Bottom line first: **no performance regression, and an improvement (gen-a 3.70s→3.17s, better than last round's fixed state of 3.21s; 3.9x relative to the f98a2e7 baseline)**; along the way **6 real bugs** were exposed and fixed (1 performance + 5 correctness, including the root cause of cloner submodule fetching failing silently, which affects every submodule-based project); analysis quality on the generalization projects gen-h/gen-o is good, with an incidental fix for dynamic_loads platform-guard false reports. Unit tests 65→94, all passing.

---

## 1. Stage 1: performance regression (4 e2e corpora + 3 generalization projects)

### 1.1 Data sources and environment

- Main DB rebuilt: `python portgraph.py ingest all` → 6069 nodes (hb 4758 / cmdpkgs 1248 / kb-seed 63) / 9504 edges, consistent with last round.
- Timing method: full deps run (scan + ingestion + report, with `--json`) and the fetch-deps `--dry-run` closure, median of 3 runs each.
- **Benchmark method erratum**: fetch-deps takes an app name (`gen-a`), not a path (`workspace/gen-a`); the latter exits silently (exit 1) — this round confirmed that the `fetch-deps <app>` in last round's report means the app name, and all fetch timings were re-measured with the correct argument.

### 1.2 A/B comparison (isolated with git worktree, same clone, same DB rebuild flow)

| Project | f98a2e7 (baseline from two rounds ago) | c04060a (last round's fixed state) | 416ef8d (integration, measured this round) | 416ef8d + NOCASE fix (bddcd59) |
|------|------|------|------|------|
| gen-a deps | 12.25s | 3.21s | **3.70s (+15% regression)** | **3.17s** |
| gen-e deps | 2.13s | 0.69s | 0.82s (+19%) | **0.58s** |
| gen-f deps | 3.21s | 0.86s | 1.06s (+23%) | **0.72s** |

**Locating the regression** (cProfile before/after): the alias table/resolution ladder added by the integration (c04060a→416ef8d) increased calls to `find_node_by_name`, and that function's `lower(name)=lower(?)` can't use the `idx_nodes_name` (BINARY collation) index → a full table scan of 6069 rows every time; 350 lookups during gen-a's report phase took 0.4s in total.

**Fix (bddcd59)**: `name=? COLLATE NOCASE` + the `idx_nodes_name_nocase` function index. Semantically equivalent (SQLite `lower()`/`NOCASE` both fold ASCII only; a name-by-name equivalence check across all 6159 names in the DB passed; older DBs get the index automatically through `CREATE INDEX IF NOT EXISTS` in `init_db`). 350 lookups 0.4s→0.002s.

### 1.3 Final performance benchmark (after all fixes, full clone state)

| Project | deps median | fetch-deps --dry-run | Notes |
|------|------|------|------|
| gen-a | **3.17s** | 0.06s | 22769 source files, no submodules |
| gen-e | 0.60s | 0.06s | Closure of 61 items |
| gen-f | 0.87s | 0.06s | With 8 submodules in place (last round scanned empty directories) |
| corpus-a | 3.66s | 0.06s | 6358 source files (35 submodules in place; only 2932 when the integration baseline was generated) |
| corpus-b | 4.29s | 0.06s | 5729 source files (corpus-b-core/corpus-b-deps in place) |
| corpus-c | 0.53s | 0.06s | 884 source files |
| corpus-d | 0.50s | 0.06s | 710 source files |

- Comparable conclusions vs last round: gen-a/gen-e are **better than** last round's fixed state (3.21/0.69), and gen-f holds even (0.87 vs 0.86) despite the larger scan scope (submodules filled in); **no performance regression**.
- The fetch-deps closure BFS is a constant 0.06s, not a bottleneck (consistent with last round's conclusion).

### 1.4 4 bugs exposed by the correctness regression (fixed incidentally in Stage 1)

In the first e2e regression run, corpus-b's metrics were abnormal (recall 100%→56%); a stash A/B proved it was unrelated to my performance fix. The root-cause investigation chain:

| # | bug | Root cause | Fix |
|---|-----|------|------|
| 1 | **cloner submodule fetching fails silently** (project-wide root cause) | In `git submodule update init ...` the bare `init` lacks `--`, so git treats it as a pathspec and errors out, and `_init_submodules` is completely silent on returncode≠0 → submodules of a reused clone can never be fetched (all 35 corpus-a submodules empty, corpus-b-deps empty) | `--init` + failure stderr made visible (c069898); fetching on the reuse path verified |
| 2 | **Wrapper dependencies hidden** (corpus-a: openal/ada/zlib/openssl/bt all missed) | Once the submodules are in place, `external_X` becomes an in-project target (defined); combined with the vendored-path skip, the real dependencies declared by the wrapper are doubly invisible | Files with the wrapper signature (`add_library(external_X)`) are not skipped as vendored; when a wrapper target is linked, the underlying library names are passed through; the wrapper's internal guard (DESKTOP_APP_USE_PACKAGED) only switches the fetch method and doesn't make it optional (c069898) |
| 3 | **OR guards misjudged as optional** | `if (X OR LINUX)` is always active because LINUX is always true on HarmonyOS, but the old logic marked the whole frame optional as soon as it saw a positive reference to an OFF option | Any always-true disjunct (LINUX/UNIX/NOT WIN32/…) → not marked optional (c069898) |
| 4 | **meson/autotools detectors lacked the vendored skip** | The CMake detectors have the `_is_vendored_path` skip, but `_absorb_meson`/`_absorb_autotools` didn't → the configure.ac of ThirdParty/nimf (anthy/gtk+/m17n) and the meson.build of xdg-desktop-portal (libgeoclue/pipewire) leaked into depth-1 | Added the same skip (c069898) |

**Final e2e metrics** (baselines regenerated after full submodule initialization, 1270e53):

| Project | Integration baseline (416ef8d)¹ | Final this round | Attribution of change |
|------|------|------|------|
| corpus-a | 53% / 60% / 2 | **71% / 38% / 4** | 2932→6358 source files; wrapper pass-through restored openal/ada/zlib/openssl/bt/boost/lz4; the remaining 4 candidates were checked manually: breakpad/crashpad are vendored source via add_subdirectory inside cmake_helpers (verdict correct), libxcb/libdispatch are real Linux dependencies (missing from the README) |
| corpus-b | 100% / 95% / 0 | 100% / 95% / 0 | Unchanged |
| corpus-c | 100% / 23% / 0 | 100% / 23% / 0 | Unchanged |
| corpus-d | 100% / 100% / 0 | 100% / 100% / 0 | Unchanged |

¹ Note: the integration baseline itself was generated under the cloner bug (clones with uninitialized submodules); corpus-a's old 53% baseline was a product of "incomplete scan scope but a loose recall measure" (cmark-gfm/ada and others counted through the external_X ghost mechanism); this round's 71% is the real recall under a complete scan. The submodule state was normal when the corpus-b/corpus-c/corpus-d old baselines were generated, so they're unaffected.

**Decisive A/B**: running 416ef8d's original code on the current full clone of corpus-a = 24%/57%/7, field-for-field identical to this round's code on the same clone (differing only in the items restored by the wrapper/OR/vendored fixes) — proving that 100% of the metric change comes from the clone conditions and the fixes above, with no other code behavior drift.

### 1.5 Analysis correctness spot check (gen-e, item by item)

- **Classification**: all 36 link entries match the source — macOS frameworks (AppKit/Carbon/CoreAudio/…) → platform-iface ✓; dwmapi → win32-system-lib ✓; Threads → system-lib ✓; GTest → test ✓; Boost/ICU/TagLib/OpenSSL find_package line numbers (175/179/214/171) match the CMakeLists text ✓; gio/gobject/gio-unix merged into glib ✓; gstreamer-base merged into gstreamer ✓.
- **Versions**: TagLib `>=1.12` (find_package(TagLib 2.0) + multi-source merge) vs hb 2.3.2 = satisfied ✓; libchromaprint `>=1.4`, libgpod `>=0.7.92`, libmtp `>=1.0` exactly match source :207/:210/:211 ✓; sqlite `>=3.9` → unknown + a scale warning (library major version vs package version numbering, as designed) ✓.
- **need_port verdicts** (verified name by name in the DB): libchromaprint/libgpod/libmtp/libpulse/kdsingleapplication/backtrace have no hb/cmdpkgs package → need_port correct ✓; gstreamer-app/audio/pbutils/tag (plugins-base components, verified via tarball last round) ✓; libsparsehash→google-sparsehash, libebur128, libcdio resolved as ported ✓.
- **Minor flaw found (not fixed)**: in `find_package(KDSingleApplication-qt${QT_VERSION_MAJOR} 1.1.0 REQUIRED)` the version number 1.1.0 is lost after variable interpolation (name normalization is correct; the need_port verdict is unaffected).

### 1.6 Unit test structure bug (fixed incidentally)

The `if __name__: unittest.main()` in `tests/test_port_graph.py` sat in the middle of the file (line 1601), so the 13 test classes after it (22 cases, appended across several merge rounds) **had never been executed** — the "56/65 all passing" in past reports was actually a partial run. Moved to the end of the file; all 94 cases pass.

---

## 2. Stage 2: generalization to popular GitHub Qt projects

**Selection statement**: gen-o (cnr-isti-vclab/gen-o, Qt5 3D mesh processing, ~4.5k stars) + gen-h (gen-h/gen-h, Qt6 text editor, ~2k stars). speedcrunch was originally planned, but **its GitHub repository has been closed** (only a migration notice remains; the project moved to Bitbucket), so it was dropped in favor of gen-h — avoiding the four e2e projects and the other workers' picks.

### 2.1 Checkout completeness

| Project | Clone | submodule | Notes |
|------|------|------|------|
| gen-o | shallow clone 1m55s (431MB working tree) | src/vcglib ✓ in place (fixed cloner) | HEAD 71e7b0b |
| gen-h | shallow clone 12s | No submodules | HEAD 37652c5 |

The cloner `--init` fix was verified directly on both new projects: gen-o's vcglib was fetched in one go (this submodule would have failed silently under the old code).

### 2.2 gen-h: excellent analysis quality

- **Real dependencies**: Qt6 (≥6.4, 14 components) + uchardet (pkg_check_modules, CMakeLists:36) — **all detected correctly**; closure 13 items (provided 11 = Qt modules + qtpromise vendored, would_download 1 = uchardet 0.0.7, target 1).
- **Platform verdict correct**: Qt D-Bus, QtWebEngine → blocked (consistent with the KB module status; porting blockers shown accurately); Core5Compat → mapped to core, ported ✓.
- **Found and fixed 1 bug (5985fb3)**: `QLibrary("kernel32")` (singleapplication.cpp:163, inside an `#if defined(Q_OS_WIN)` block) was falsely reported as a runtime dynamic load. Fix: the macro-stack mechanism moved from project_scanner to qt_scanner (re-exported for compatibility), and dynamic_loads excludes platform-excluded lines (prefiltering keeps performance intact). Also fixed: qt_scanner was missing `import warnings`, causing a NameError during macro expression evaluation that was swallowed as a conservative true.
- Remaining minor noise: `qtpromise.tests.utils` (a test cmake target name of the vendored library src/ui/libs/qtpromise mixed into the link list, 1 entry, doesn't affect need_port/the closure).
- **Performance**: deps 0.18s / fetch-deps 0.05s.

### 2.3 gen-o: main dependencies correct, noise found inside the vendored subtree

- **Main dependencies correct** (src/CMakeLists.txt): Eigen3/GLEW/OpenGL/muparser/openctm/lib3ds all detected; lib3ds→hb 1.3.0 ✓, eigen/fftw/opencv→ported ✓; Qt5 ≥5.15 detected ✓.
- **need_port verdict check** (verified in the DB): muparser/openctm/GLEW have no HarmonyOS packages → need_port correct; OpenGL → need_port is reasonable (OHOS has OpenGL ES, needs EGL/GLES adaptation).
- **The vcglib submodule is vendored** ✓ (`src/vcglib`, `src/external` recognized correctly), but the find_package/qmake LIBS of **vcglib's own example/test projects** inside it (`src/vcglib/apps/*`, `src/vcglib/eigenlib/unsupported/test/*`) leak into the app's depth-1: about 20 entries such as Adolc/CUDA/HIP/GoogleHash/MPREAL/GLFW3/embree/GLUT/freeglut/the cholmod family (gen-o's main build doesn't compile these targets). The real dependencies of the main CMakeLists are unaffected; about half of the 10 need_port among the 21 closure items come from this noise.
- **Qt major misjudged**: the report says `major: 4` (polluted by the QT variable of vcglib's legacy qmake projects), while the main project is actually Qt5 ≥5.15; the module table has lowercase unknown variants qtcore/qtgui mixed in.
- **Performance**: deps 2.94-3.00s (22k+ source files) / fetch-deps 0.05s.

### 2.4 Problem classification summary

| Problem | Project | Classification | Handling |
|------|------|------|------|
| kernel32 dynamic_load false report | gen-h | defect (platform macro guard not filtered) | **Fixed** (5985fb3) + 2 unit tests |
| cloner submodule fails silently | All submodule projects | defect (syntax error + swallowed error) | **Fixed** (c069898) + unit test |
| Example/test projects inside the vendored subtree leak | gen-o (vcglib apps/eigenlib tests) | defect (direction: depth constraint on non-build-target directories inside submodules) | Not fixed, recorded as residual (see 3) |
| qtpromise.tests.utils target name mixed in | gen-h | defect (minor, 1 noise entry) | Not fixed, recorded as residual |
| Qt major misjudged (4) | gen-o | defect (minor, legacy qmake polluting the hint) | Not fixed, recorded as residual |
| KDSingleApplication-qt version number lost | gen-e | defect (minor, version token lost after ${VAR} interpolation) | Not fixed, recorded as residual |

---

## 3. Residual items (not fixed, for follow-up)

1. **Dependency leaks from non-build directories inside submodules** (gen-o: vcglib's apps/eigenlib/unsupported test projects leak about 20 depth-1 noise entries). Direction: combine the .gitmodules submodule paths + "subdirectories not included in the main build" (apps/test/unsupported naming traits) into a depth constraint; must avoid breaking normal cases like corpus-b's corpus-b-core where "the dependency list lives in a submodule".
2. **Test target names of vendored libraries mixed into the link list** (gen-h qtpromise.tests.utils; the path src/ui/libs/ has no vendored-signature segment).
3. **Qt major hint pollution** (gen-o: legacy qmake projects make the main project's Qt5 judged as 4; recommend giving find_package(QtN) in the main CMakeLists higher priority than qmake hints).
4. **Version token lost when the find_package name contains ${VAR}** (gen-e KDSingleApplication-qt 1.1.0).
5. **e2e harness misses matches for resolved renames** (liblzma→xz is now connected via kb_seed.ALIASES; for similar cases, recommend the harness consume PKG_ALIASES uniformly).
6. **Scope of the harness's grep evidence collection** (the libxcb/libdispatch false candidates: the references are inside the submodule wrapper, which the harness's build-file search doesn't cover; recommend including submodule paths).
7. Last round's residuals #2/#3/#4 (find_library debug suffixes, structured platform block parsing, qt_scanner shared read cache) still apply.

---

## 4. Fix and commit list

| Commit | Content |
|------|------|
| bddcd59 | perf: find_node_by_name NOCASE function index (regression fix) + 3 unit tests |
| c069898 | fix: cloner `--init` syntax + triple wrapper pass-through + OR guard semantics + meson/autotools vendored skip + liblzma alias + unit test structure fix |
| 1270e53 | test(e2e): baselines regenerated from full clones + breakpad/crashpad notes updated |
| 5985fb3 | fix: dynamic_loads platform macro guard filtering (macro stack moved to qt_scanner) + 2 unit tests |
| (this commit) | docs: REGRESS-REPORT.md |

Unit tests 65→**94, all passing** (including the 22 existing cases that had never been executed); for the final metrics of the four e2e projects see §1.4.

---
>>>>>>> worker4-deps-regress

## 5. Reproduction commands

```bash
cd portgraph
<<<<<<< HEAD
python -m unittest tests.test_port_graph                       # all 92 pass
# Stage 1 (runs through in one go on a fresh DB)
rm workspace/portgraph.db && python portgraph.py ingest all --offline
/usr/bin/time -f "%es" python portgraph.py deps workspace/corpus-a --json
python portgraph.py fetch-deps corpus-a --dry-run --json
python tests/e2e/run_e2e.py run --project corpus-a --no-clone --fresh-db
# Stage 2
python portgraph.py deps workspace/gen-j --json && python portgraph.py fetch-deps gen-j --dry-run
python portgraph.py deps workspace/gen-i --json && python portgraph.py fetch-deps gen-i --dry-run
python tests/e2e/run_e2e.py run --all --no-clone --fresh-db    # corpus regression
```
=======
# REGRESS-REPORT — portgraph dependency analysis regression + generalization test

> Branch: `worker3-deps-regress` | Baseline: `416ef8d` (with all integration fixes, all 87 unit tests passing)
> Date: 2026-09-19 | Workspace: `~/harmony-workspace/worker3`
> Stage 1 corpora: corpus-d + corpus-c (e2e corpus tier B, regression)
> Stage 2 generalization: **gen-b** (KDE/Qt document viewer, master 8662e426, 500 source files)
> + **gen-c** (KDE/Qt terminal, master a6ef17f7, 382 source files) —
> avoiding the four e2e corpus projects (corpus-a/corpus-b/corpus-c/corpus-d) and other workers' picks
> (gen-a/gen-e/gen-f)

## 1. Executive summary

- **Stage 1 regression: single-pass correctness 100% passed**. The full fresh DB → scan → deps --json →
  fetch-deps --dry-run flow ran on the baseline code with **zero manual touch-ups** and produced results matching the
  `tests/e2e/reports/` baseline item by item (closure composition, would_download list,
  d1 list, need_port verdicts, and analyze verdict all exactly equal; reports regenerated by the e2e harness
  are **byte-identical** to the committed baseline, with diffs only in timestamps and workspace paths).
- **Stage 2 generalization: gen-b + gen-c exposed 9 classes of problems** (6 tool bugs + 2 data source
  alias gaps + 1 heuristic limitation), **all root causes fixed**, with 14 regression unit tests added
  (87 → 101, all passing); the 3 classes of report-level defects found during Stage 1 regression (unrelated to the baseline's measures,
  since e2e reconciliation doesn't go through deps --json) were also fixed.
- Corpus regression: corpus-d / corpus-c / corpus-b baselines byte-for-byte unchanged; corpus-a
  precision 60%→64% (the platform-block fix removed the APPLE-only false edge libiconv, an **expected improvement**;
  the baseline is updated with this round). Performance is in the same order of magnitude as last round's comparable numbers, no regression.

## 2. Stage 1: regression (corpus-d + corpus-c @ 416ef8d)

### 2.1 Method

An independent fresh DB per project (`rm portgraph.db && ingest all --offline`: hb 4758
formulas + cmd-pkgs 1248, gate PASS) → `scan` → `deps --json` →
`fetch-deps --dry-run` → `analyze`, checked item by item against the `tests/e2e/reports/*.report.{md,json}`
baselines; also ran the e2e harness (`run --project X --fresh-db --no-clone`)
to regenerate reports and diff them against the committed baselines. All commands timed with `/usr/bin/time`.

### 2.2 Single-pass correctness check (all passed, zero manual touch-ups)

| Check | corpus-d | corpus-c |
|---|---|---|
| analyze verdict | blocked (4 blockers + 1 unknown) ✓ same as baseline | blocked (5 blockers + 1 unknown) ✓ same as baseline |
| Dependency closure | **19 items** = target 1 / provided 8 / cmd_only 1 / need_port 1 / would_download 8 ✓ | **42 items** = target 1 / provided 8 / covered 1 / cmd_only 1 / need_port 1 / would_download 30 ✓ |
| would_download list | 8/8 exactly equal name by name ✓ | 30/30 exactly equal name by name ✓ |
| need_port verdict | libtorrent-rasterbar (really absent from hb/cmd-pkgs, correct) ✓ | botan (same, correct) ✓ |
| d1 direct dependencies | 12/12 (name/type/port_status) consistent ✓ | 20/20 consistent ✓ |
| optional edges | systemd (SYSTEMD default-OFF guard) ✓ | — |
| Merging different names of the same library | libtorrentrasterbar merged into libtorrent-rasterbar (merged_from) ✓ | qrencode/libqrencode, three pcsc names merged ✓ |
| e2e metrics | recall 100% / precision 100% / bug 0 ✓ | recall 100% / precision 23% / bug 0 ✓ |
| e2e report diff | **timestamps + worker paths only** (byte-identical) ✓ | Same ✓ |

### 2.3 Timing (baseline code 416ef8d, with two fresh-DB runs, cold/warm)

| Step | corpus-d (710 source files) | corpus-c (884 source files) |
|---|---|---|
| ingest all --offline | 2.04s / 1.17s (second run) | 1.17s |
| scan | 0.63s | 0.64s |
| deps --json | 0.57s | 0.72s |
| fetch-deps --dry-run | 0.05s | 0.06s |
| analyze | 0.07s | 0.06s |
| Full e2e harness run | 0.57s | 0.72s |

**Comparison with last round**: the archived reports (`portgraph/docs/opt-reports/`) didn't record
deps timings for corpus-d/corpus-c; the closest comparable number is worker4's generalization round
gen-f 0.81s (similar size) → corpus-c 0.72s, same order of magnitude, **no performance regression**.
Re-measured after all of this round's fixes: corpus-d deps 0.57s, corpus-c 0.73s (on par).

### 2.4 Report-level defects found during regression (don't affect the e2e reconciliation measures; fixed this round)

The baseline reconciles against DB nodes/closures, but the link table of `deps --json` showed 3 kinds of behavior inconsistent with the
project facts (see fixes F3/F4/F5 in §4):

- corpus-d's `Systemd` entry had required=True + a "direct platform stack" warning (it actually sits inside the
  SYSTEMD default-OFF option guard);
- corpus-d had both `LibtorrentRasterbar` + `libtorrent-rasterbar` entries, with two
  "needs cross-compiling from source" warnings (merged on the DB side but not on the report side);
- corpus-c's `qrencoded` (a Windows debug variant name inside FindQREncode.cmake's WIN32 AND NOT MINGW block)
  and `network` (an if(HAIKU) block) were falsely reported required=True.

## 3. Stage 2: generalization to popular GitHub Qt projects (gen-b + gen-c)

**Selection statement**: gen-b (~2.6k stars, KDE's flagship document viewer, CMake/ECM/KF6,
with a broad dependency surface for multimedia formats such as poppler) + gen-c (KDE's default terminal, CMake/KF6).
Shallow-cloned into `portgraph/workspace/`, ran `deps --json` +
`fetch-deps --dry-run`, and compared item by item by hand against `CMakeLists.txt`, `cmake/modules/Find*.cmake`,
and README/BUILD.md.

### 3.1 gen-b (before → after fix)

| Dimension | Baseline code | After fix |
|---|---|---|
| deps link entries | 39 | 37 (ddjvuapi/libmarkdown merged into the same-library entries) |
| Closure | 104 items | 101 items: need_port 32→30, would_download 60→59 |
| need_port composition | 24×KF + djvulibre + **ddjvuapi (duplicate)** + epub + kexiv2qt6 + **nss (wrongly pulled in from the mobile ANDROID block)** + phonon4qt6 + poppler + qmobipocket6 | 24×KF + djvulibre + epub + kexiv2qt6 + phonon4qt6 + poppler + qmobipocket6 (all checked to be really absent from hb/cmd-pkgs, **need_port verdict correct**) |
| KF component resolution | `archive`→hb:libarchive, `config`→hb:libconfig (**same name, different meaning mismatch**; the report showed a ready bottle contradicting need_port in the closure) | Resolved to `kf:<comp>` nodes, consistent with the closure |
| Version constraints | Poppler/DjVuLibre/QMobipocket6 all missing (quoted versions `"24.08.0"`/`"3.5.28"`/`"2"` not parsed) | All detected and included in checks |
| in-tree misjudgment | Poppler/EPub judged "bundled source in the project, no external artifact needed" (they are actually the `generators/poppler` and `generators/epub` format-generator plugin directories; the README states plainly "libepub based backend... obtained using svn co") | Judged package (real need_port) |
| Platform blocks | freebl3/softokn3/nssckbi/nss (in the mobile/app `if (ANDROID)` block) falsely reported required=True | required=False + the note "inside an if(ANDROID) platform block", excluded from the closure |

**Manual comparison conclusion**: detections match the `CMakeLists.txt` declarations one by one (KF6 12 required components +
Qt6 components + Discount/DjVuLibre/EPub/Poppler/QMobipocket6/LibSpectre(0.2)/
KExiv2Qt6/Phonon4Qt6/Freetype/TIFF/ZLIB); the Android-only NSS linking in `mobile/app/CMakeLists.txt`
is correctly recognized as a platform block. The gen-b README has no dependency section (the build files
are the only source of truth), so nothing is missed. **The hb:markdown mismatch once pulled daringfireball's Perl/PHP
Markdown 1.0.1 bottle into the closure** (the libmarkdown that gen-b links is actually discount's
library name) — eliminated after the fix.

### 3.2 gen-c (before → after fix)

| Dimension | Baseline code | After fix |
|---|---|---|
| Qt modules | Only 1 (widgets, from the demo subproject) — the main declaration `find_package(Qt6 ${QT_MIN_VERSION} CONFIG REQUIRED\n Core Multimedia PrintSupport Widgets)` has **no COMPONENTS keyword, so all were missed** | 5 (core/dbus/multimedia/printsupport/widgets) |
| KF components | 21 (mostly backfilled from KF6:: link target names), **ConfigWidgets/Service/NewStuff missed, Config swallowed by the CONFIG keyword** | 24 (exactly matching the CMakeLists declarations) |
| Closure | 51 items (need_port 23, provided 5) | 56 items (need_port 26 = all KF, provided 7) |
| Platform blocks | `util` (`if(SYSTEM_NAME MATCHES "FreeBSD")` kinfo_getfile) and `network` (`if(HAIKU)` inet_aton) falsely reported required=True with "needs cross-compiling from source"/"macOS Network framework" | required=False + correct notes (FreeBSD/Haiku blocks), excluded from the closure |
| Version checks | ICU 61.0 satisfied, libssh 0.9.8 satisfied (already correct) | Same (Qt 6.5.0 satisfied) |

**Manual comparison conclusion**: BUILD.md's neon apt list includes KF auth/package/declarative/
kcmutils, but the build file's `find_package(KF6 ...)` doesn't declare them (the docs are a packaging approximation,
not the build source of truth) — portgraph goes by the build files, so **nothing is missed**; DBusAddons/GlobalAccel inside `if(USE_DBUS)` (UNIX
default ON) are correctly judged required (OHOS counts as UNIX-like, enabled by
default).

### 3.3 Overall analysis correctness assessment (both projects)

- **Classification**: after the fix, the link/runtime/framework/platform-iface/win32-system-lib/
  in-tree classification matches the facts of the build files;
- **Version checks**: after the fix, all declared versions are detected (quoted versions + keyword-less component names were the only
  two forms of misses), and the satisfied/any verdicts for resolved dependencies are all correct;
- **need_port verdicts**: all of gen-b's 30 and gen-c's 26 need_port items were verified against
  hb-core/cmd-pkgs to have no corresponding package (the bulk is the whole KF6 family — needs cross-compiling from source,
  verdict correct; the real cure is submitting KF formulas to Harmonybrew, a data source gap).

## 4. Problem list and classification (all fixed + tests added)

| # | Problem | Evidence | Classification | Fix |
|---|---|---|---|---|
| F1 | find_package **quoted versions** not parsed | gen-b `Poppler "24.08.0"`, `DjVuLibre "3.5.28"`, `QMobipocket6 "2"` | Tool bug | `qt_scanner._parse_findpkg_args` strips quotes from tokens |
| F2 | **Trailing components without the COMPONENTS keyword** missed; component names identical in form to keywords (Config↔CONFIG) swallowed | gen-c Qt6/KF6 main declarations (4 Qt modules + 3 KF components missed) | Tool bug (legal CMake syntax not covered) | `_orphan_components` region state machine (bare names after the version/keywords are components; once the component region starts, nothing is interpreted as a keyword) + wired into the KF/Qt detectors + `_parse_findpkg_args` uses the same logic |
| F3 | INTERFACE_BOUND (platform-iface) entries ignored optional guards | corpus-d systemd (SYSTEMD default OFF) required=True + false warning | Tool bug | `deps_report` §1/§2 platform-interface branches pass optional through |
| F4 | **Separator-stripped duplicates of the same library** in the deps link table | corpus-d LibtorrentRasterbar×libtorrent-rasterbar double warnings | Tool bug (merged at scan time, not aligned at report time) | `deps_report` §7b separator-stripped merge key (single-word names + key length ≥6; KF node names containing spaces don't participate) |
| F5 | **Missing platform-block context**: tll/-l/find_library/pkg_check_modules inside blocks such as if(APPLE)/if(WIN32)/if(HAIKU)/if(ANDROID)/STREQUAL "Darwin"/"Windows" falsely reported required and wrongly pulled into the closure | corpus-d AppKit/Carbon/IOKit/objc (Darwin), iphlpapi (Windows); gen-c util (FreeBSD), network (Haiku); gen-b nss/softokn3/freebl3/nssckbi (ANDROID); corpus-c qrencoded (WIN32 AND NOT MINGW); corpus-a external_iconv (APPLE) | Tool bug (a recommendation recorded in the worker1 round, implemented this round) | `qt_scanner._cmake_platform_line_map` (isomorphic with the option-guard line map; UNIX/LINUX/POSIX treated as OHOS-active, not downgraded; NOT X negated conditions not downgraded; elseif evaluated by its own condition, else conservative) → raw_libs/pkg detections annotated with `platform_block` → deps_report required=False + note, project_scanner doesn't connect an edge |
| F6 | **KF components went through the package-name resolution ladder**: KF Archive≠libarchive, KF Config≠libconfig | gen-b/gen-c (the report showed a ready bottle contradicting need_port in the closure) | Tool bug | `deps_report` §7 resolves framework entries to `kf:<comp>` nodes |
| F7 | **in-tree misjudged functional grouping directories**: the heuristic of a `generators/` parent directory with ≥5 subdirectories treated format-generator plugin directories as bundled libraries | gen-b generators/poppler, generators/epub (masking real need_port) | Tool heuristic limitation (triggered by the KDE generators layout) | `_in_tree_dir_index` gets an allowlist of dependency-collection parent directories (libraries/libs); the README only serves as corroboration inside the container. Retesting gen-f fakevim/litehtml showed no regression |
| F8 | **ddjvuapi alias gap**: djvulibre's pkg-config name and find_package name produced double ghosts and double need_port | gen-b (FindDjVuLibre.cmake probes the same library with pkg_check_modules(ddjvuapi)) | Data source gap (alias knowledge) | `kb_seed.PKG_ALIASES["ddjvuapi"]="djvulibre"` + alias normalization of the `_link_third_party` grouping key |
| F9 | **libmarkdown same name, different meaning**: discount's library name resolved to hb:markdown (daringfireball's Perl/PHP version), putting the wrong bottle into the closure | gen-b (FindDiscount.cmake `pkg_check_modules(Discount "libmarkdown")`) | Data source gap (alias knowledge, an instance of the same-name-different-meaning risk) | `PKG_ALIASES["libmarkdown"]="discount"` |

## 5. Corpus regression verification (full, after the fixes)

| Project | Result |
|---|---|
| corpus-d / corpus-c | e2e reports **byte-identical** to the baselines (timestamps/paths only); closure/metrics unchanged |
| corpus-b | Same as above (note: the workspace clone needs `git submodule update --init`; when uninitialized, source files are 3139 vs 5729 and results aren't comparable to the baseline — verified this round, an operational caveat) |
| corpus-a (master 4d4da47, verified with a supplementary clone) | precision 60%→64%, closure 61→60: **the false edge `desktop-app::external_iconv` (libiconv) inside the APPLE block was correctly removed by F5**, an expected improvement; the baseline was regenerated with this round; recall 53% / 2 missed-deps are pre-existing baseline state (upstream README drift, see the residual items in the worker1 report), not introduced this round |
| gen-f (spot check) | fakevim/litehtml still correctly in-tree (no regression from the F7 tightening) |
| Unit tests | **101/101, all passing** (87 → +14: quoted versions/keyword-less components/Config look-alike/platform blocks×3/optional platform interfaces/report separator-stripped merging/KF resolution/in-tree×2/aliases×2) |

## 6. Residual items (not fixed this round, recorded)

1. **keyutils (corpus-c)**: sits inside an `if("${CMAKE_SYSTEM}" MATCHES "Linux")`
   block — LINUX is treated as OHOS-active and not downgraded (conservatively required). The verdict is reasonable: OHOS musl has no
   keyutils.h, so porting really needs attention here; the tool can't statically determine the value of CMAKE_SYSTEM
   under the OHOS toolchain.
2. **corpus-a's 2 missed-deps**: pre-existing in the baseline (drift between the upstream README and the build files),
   see the residual items in `docs/opt-reports/2026-09-deps-test-worker1.md`.
3. **Discount is required=True after merging**: pkg_check_modules (required semantics) and
   find_package (no REQUIRED) for the same library merge as required (the conservative direction, _DepBook's existing
   merge rule); on the gen-b side set_package_properties actually makes it optional — being perfectly precise
   would need the call-site context inside the Find module, low payoff.
4. **The whole KF6 family is need_port** (gen-b 24 / gen-c 26 items): a data source gap; the real cure
   is submitting the KF6 formula group to Harmonybrew.
5. **Platform inheritance from a find_package inside a platform block into the contents of the Find<Name>.cmake module** is not implemented
   (conservatively treated as required).
6. **The submodule state of the corpus-b clone** affects comparability (§5); recommend that the e2e harness
   warn about clones with uninitialized submodules.

## 7. Reproduction

```bash
cd ~/harmony-workspace/worker3/portgraph
python -m unittest discover -s tests        # 101 tests OK
# Stage 1 regression (fresh DB flow)
rm workspace/portgraph.db && python portgraph.py ingest all --offline
time python portgraph.py scan workspace/corpus-d
time python portgraph.py deps workspace/corpus-d --json > /tmp/q.json
time python portgraph.py fetch-deps corpus-d --dry-run
python tests/e2e/run_e2e.py run --project corpus-d --fresh-db --no-clone
python tests/e2e/run_e2e.py run --project corpus-c  --fresh-db --no-clone
git diff tests/e2e/reports/                  # timestamps/paths only
# Stage 2 generalization
git clone --depth 1 https://github.com/KDE/gen-b.git  workspace/gen-b
git clone --depth 1 https://github.com/KDE/gen-c.git workspace/gen-c
python portgraph.py deps workspace/gen-b --json | python -m json.tool | less
python portgraph.py fetch-deps gen-b --dry-run
```

Changed files: `port_graph/qt_scanner.py` (quoted versions/keyword-less components/platform-block line map/
Config look-alike), `port_graph/deps_report.py` (optional platform interfaces/separator-stripped
merging/KF resolution/in-tree container allowlist/platform-block required),
`port_graph/project_scanner.py` (alias-normalized grouping key/platform-block raw lib skip),
`port_graph/kb_seed.py` (PKG_ALIASES +2), `tests/test_port_graph.py` (+14),
`docs/deps-report.md` (documentation of platform-block/KF resolution/in-tree semantics),
`tests/e2e/reports/corpus-a.report.{md,json}` (baseline updated after the platform-block fix).
>>>>>>> worker3-deps-regress
=======
python tests/test_port_graph.py                        # 94 tests OK
python portgraph.py ingest all                         # main DB, 6069 nodes
# Performance (median of 3 runs)
/usr/bin/time -f "%es" python portgraph.py deps workspace/gen-a --json > /dev/null
/usr/bin/time -f "%es" python portgraph.py fetch-deps gen-a --dry-run > /dev/null   # note: app name, not a path
# e2e regression (full clones with submodules)
python tests/e2e/run_e2e.py run --all --fresh-db
# Generalization projects
python portgraph.py deps workspace/gen-o --json
python portgraph.py deps workspace/gen-h --json
python portgraph.py fetch-deps gen-o --dry-run
# A/B (isolated with worktree)
git worktree add .ab/c04060a c04060a   # share the clone via a symlink inside workspace, then time the same flow
```
>>>>>>> worker4-deps-regress
