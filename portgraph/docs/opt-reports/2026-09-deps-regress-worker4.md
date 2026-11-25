# Regression + generalization test report: deps performance benchmark and generalization on popular GitHub Qt projects

> Branch `worker4-deps-regress` (baseline 416ef8d, includes all integration fixes)
> Test date: 2026-09-19 | Workspace: `portgraph/`
> Conclusion first: **no performance regression, and an improvement (gen-a 3.70s→3.17s, better than the previous round's fixed state of 3.21s; 3.9x relative to the f98a2e7 baseline)**; the process exposed and fixed **6 real bugs** (1 performance + 5 correctness, including the root cause of silently failing submodule fetches in the cloner, which affected every submodule-based project); analysis quality on the generalization projects gen-h/gen-o is good, with an incidental fix for false dynamic_loads reports inside platform guards. Unit tests 65→94, all passing.

---

## 1. Phase 1: performance regression (4 e2e corpora + 3 generalization projects)

### 1.1 Data sources and environment

- Main database rebuild: `python portgraph.py ingest all` → 6069 nodes (hb 4758 / cmdpkgs 1248 / kb-seed 63) / 9504 edges, consistent with the previous round.
- Timing method: full deps flow (scan + ingestion + report, with `--json`) and the fetch-deps `--dry-run` closure, median of 3 runs each.
- **Benchmark method erratum**: fetch-deps takes an app name (`gen-a`), not a path (`workspace/gen-a`); the latter exits silently (exit 1) — this round confirmed that the previous round's `fetch-deps <app>` means the app name, and all fetch timings were re-measured with the correct argument.

### 1.2 A/B comparison (git worktree isolation, same clone, same DB rebuild flow)

| Project | f98a2e7 (baseline two rounds ago) | c04060a (previous round's fixed state) | 416ef8d (integration, measured this round) | 416ef8d + NOCASE fix (bddcd59) |
|------|------|------|------|------|
| gen-a deps | 12.25s | 3.21s | **3.70s (+15% regression)** | **3.17s** |
| gen-e deps | 2.13s | 0.69s | 0.82s (+19%) | **0.58s** |
| gen-f deps | 3.21s | 0.86s | 1.06s (+23%) | **0.72s** |

**Locating the regression** (cProfile before/after): the alias table/resolution ladder added by the integration (c04060a→416ef8d) increased calls to `find_node_by_name`, and that function's `lower(name)=lower(?)` can't use the `idx_nodes_name` (BINARY collation) index → a full scan of 6069 rows every time; 350 lookups during gen-a's report phase took 0.4s in total.

**Fix (bddcd59)**: `name=? COLLATE NOCASE` + an `idx_nodes_name_nocase` function index. Semantically equivalent (SQLite `lower()`/`NOCASE` both fold ASCII only; an equivalence check over all 6159 names in the database passed; old databases get the index automatically through `init_db`'s `CREATE INDEX IF NOT EXISTS`). 350 lookups 0.4s→0.002s.

### 1.3 Final performance benchmark (after all fixes, fully cloned)

| Project | deps median | fetch-deps --dry-run | Notes |
|------|------|------|------|
| gen-a | **3.17s** | 0.06s | 22769 source files, no submodules |
| gen-e | 0.60s | 0.06s | closure of 61 items |
| gen-f | 0.87s | 0.06s | with 8 submodules in place (the previous round scanned empty directories) |
| corpus-a | 3.66s | 0.06s | 6358 source files (35 submodules in place; only 2932 when the integration baseline was generated) |
| corpus-b | 4.29s | 0.06s | 5729 source files (corpus-b-core/corpus-b-deps in place) |
| corpus-c | 0.53s | 0.06s | 884 source files |
| corpus-d | 0.50s | 0.06s | 710 source files |

- Comparison with the previous round: gen-a/gen-e are **better than** the previous round's fixed state (3.21/0.69), and gen-f stays flat (0.87 vs 0.86) even with a larger scan scope (submodules filled in); **no performance regression**.
- The fetch-deps closure BFS is a constant 0.06s, not a bottleneck (consistent with the previous round's conclusion).

### 1.4 4 bugs exposed during the correctness regression (fixed along the way in phase 1)

The first e2e regression run showed anomalous corpus-b metrics (recall 100%→56%); a stash A/B proved it unrelated to my performance fix, and the root-cause investigation went as follows:

| # | bug | Root cause | Fix |
|---|-----|------|------|
| 1 | **Silently failing submodule fetch in the cloner** (project-wide root cause) | In `git submodule update init ...` the bare `init` lacks `--`, so git treats it as a pathspec and errors out, and `_init_submodules` was completely silent on returncode≠0 → submodules of reused clones never got fetched (all 35 corpus-a submodules empty, corpus-b-deps empty) | `--init` + failure stderr made visible (c069898); fetching verified on the reuse path |
| 2 | **Wrapper dependencies hidden** (corpus-a: openal/ada/zlib/openssl/bt all missed) | Once submodules are in place, `external_X` becomes an in-project target (defined), and combined with the vendored-path skip, the real dependencies declared by the wrapper become doubly invisible | Files with a wrapper signature (`add_library(external_X)`) are not skipped as vendored; when a wrapper target is linked, the underlying library name is passed through; guards inside the wrapper (DESKTOP_APP_USE_PACKAGED) only switch the acquisition method and don't apply optional (c069898) |
| 3 | **OR guards misjudged as optional** | `if (X OR LINUX)` is always active because LINUX is always true on HarmonyOS, but the old logic marked the whole frame optional as soon as it saw a positive reference to an OFF option | Any always-true disjunct (LINUX/UNIX/NOT WIN32/…) → not marked optional (c069898) |
| 4 | **meson/autotools detectors lacked the vendored skip** | The CMake detectors have the `_is_vendored_path` skip, but `_absorb_meson`/`_absorb_autotools` didn't → ThirdParty/nimf's configure.ac (anthy/gtk+/m17n) and xdg-desktop-portal's meson.build (libgeoclue/pipewire) leaked into depth-1 | Added the same skip (c069898) |

**Final e2e metrics** (baselines regenerated after full submodule initialization, 1270e53):

| Project | Integration baseline (416ef8d)¹ | Final this round | Attribution of change |
|------|------|------|------|
| corpus-a | 53% / 60% / 2 | **71% / 38% / 4** | 2932→6358 source files; wrapper passthrough restores openal/ada/zlib/openssl/bt/boost/lz4; the remaining 4 candidates were manually verified: breakpad/crashpad are vendored source via add_subdirectory inside cmake_helpers (verdict correct), libxcb/libdispatch are real Linux dependencies (missing from the README) |
| corpus-b | 100% / 95% / 0 | 100% / 95% / 0 | Unchanged |
| corpus-c | 100% / 23% / 0 | 100% / 23% / 0 | Unchanged |
| corpus-d | 100% / 100% / 0 | 100% / 100% / 0 | Unchanged |

¹ Note: the integration baseline itself was generated under the cloner bug (clones with uninitialized submodules); corpus-a's old 53% baseline was an artifact of "incomplete scan scope but overly lenient recall semantics" (cmark-gfm/ada etc. were counted through the external_X ghost mechanism); this round's 71% is the real recall under a complete scan. The corpus-b/corpus-c/corpus-d old baselines were generated with normal submodule state, so they're unaffected.

**Decisive A/B**: the original 416ef8d code on the current full clone gives corpus-a = 24%/57%/7, matching this round's code on the same clone field by field (differing only in the items restored by the wrapper/OR/vendored fixes) — proving the metric change comes 100% from clone conditions and the above fixes, with no other code behavior drift.

### 1.5 Analysis correctness spot check (gen-e, item by item)

- **Classification**: all 36 link entries match the source — macOS frameworks (AppKit/Carbon/CoreAudio/…) → platform-iface ✓; dwmapi → win32-system-lib ✓; Threads → system-lib ✓; GTest → test ✓; Boost/ICU/TagLib/OpenSSL find_package line numbers (175/179/214/171) match the CMakeLists text ✓; gio/gobject/gio-unix merged into glib ✓; gstreamer-base merged into gstreamer ✓.
- **Versions**: TagLib `>=1.12` (find_package(TagLib 2.0) + multi-source merge) vs hb 2.3.2 = satisfied ✓; libchromaprint `>=1.4`, libgpod `>=0.7.92`, libmtp `>=1.0` exactly match source :207/:210/:211 ✓; sqlite `>=3.9` → unknown + scale warning (library major version vs package version numbering, as designed) ✓.
- **need_port verdicts** (verified name by name in the DB): libchromaprint/libgpod/libmtp/libpulse/kdsingleapplication/backtrace have no hb/cmdpkgs package → need_port correct ✓; gstreamer-app/audio/pbutils/tag (plugins-base components, verified via tarball last round) ✓; libsparsehash→google-sparsehash, libebur128, libcdio resolved as ported ✓.
- **Minor flaw found (not fixed)**: in `find_package(KDSingleApplication-qt${QT_VERSION_MAJOR} 1.1.0 REQUIRED)` the version number 1.1.0 is lost after variable interpolation (name normalization is correct; the need_port verdict is unaffected).

### 1.6 Unit test structure bug (fixed along the way)

The `if __name__: unittest.main()` in `tests/test_port_graph.py` sat in the middle of the file (line 1601), so the 13 test classes after it (22 cases, appended across several merges) **had never been executed** — the "56/65 all passing" in historical reports was actually a partial run. It has been moved to the end of the file; all 94 cases pass.

---

## 2. Phase 2: generalization on popular GitHub Qt projects

**Selection statement**: gen-o (cnr-isti-vclab/gen-o, Qt5 3D mesh processing, ~4.5k stars) + gen-h (gen-h/gen-h, Qt6 text editor, ~2k stars). The original pick was speedcrunch, but **its GitHub repository has been closed** (only a migration notice remains; the project moved to Bitbucket), so it was dropped in favor of gen-h — avoiding the four e2e projects and other workers' picks.

### 2.1 Checkout completeness

| Project | Clone | submodule | Notes |
|------|------|------|------|
| gen-o | shallow clone 1m55s (431MB working tree) | src/vcglib ✓ in place (fixed cloner) | HEAD 71e7b0b |
| gen-h | shallow clone 12s | no submodules | HEAD 37652c5 |

The cloner `--init` fix was verified directly on both new projects: gen-o's vcglib was fetched in one go (that submodule would have failed silently under the old code).

### 2.2 gen-h: excellent analysis quality

- **Real dependencies**: Qt6 (≥6.4, 14 components) + uchardet (pkg_check_modules, CMakeLists:36) — **all correctly detected**; closure of 13 items (provided 11 = Qt modules + qtpromise vendored, would_download 1 = uchardet 0.0.7, target 1).
- **Platform verdicts correct**: Qt D-Bus, QtWebEngine → blocked (consistent with the KB module status; porting blockers presented faithfully); Core5Compat → mapped to core, ported ✓.
- **Found and fixed 1 bug (5985fb3)**: `QLibrary("kernel32")` (singleapplication.cpp:163, inside an `#if defined(Q_OS_WIN)` block) was falsely reported as a runtime dynamic load. Fix: the macro-stack mechanism moved from project_scanner to qt_scanner (re-exported for compatibility), and dynamic_loads excludes platform-excluded lines (prefiltering keeps performance intact). Incidental fix: qt_scanner was missing `import warnings`, so a NameError during macro expression evaluation was swallowed as a conservative true.
- Remaining minor noise: `qtpromise.tests.utils` (a test cmake target name of the vendored library src/ui/libs/qtpromise mixed into the link list; 1 entry, doesn't affect need_port/closure).
- **Performance**: deps 0.18s / fetch-deps 0.05s.

### 2.3 gen-o: main dependencies correct, noise found inside the vendored subtree

- **Main dependencies correct** (src/CMakeLists.txt): Eigen3/GLEW/OpenGL/muparser/openctm/lib3ds all detected; lib3ds→hb 1.3.0 ✓, eigen/fftw/opencv→ported ✓; Qt5 ≥5.15 detected ✓.
- **need_port verdict verification** (DB-verified): muparser/openctm/GLEW have no HarmonyOS package → need_port correct; OpenGL → need_port reasonable (OHOS uses OpenGL ES, needs EGL/GLES adaptation).
- **The vcglib submodule is vendored** ✓ (`src/vcglib` and `src/external` correctly identified), but the find_package/qmake LIBS of **vcglib's own example/test projects** inside it (`src/vcglib/apps/*`, `src/vcglib/eigenlib/unsupported/test/*`) leak into the app's depth-1: about 20 entries such as Adolc/CUDA/HIP/GoogleHash/MPREAL/GLFW3/embree/GLUT/freeglut/the cholmod family (gen-o's main build doesn't compile these targets). The real dependencies of the main CMakeLists are unaffected; about half of the 10 need_port among the 21 closure items stem from this noise.
- **Qt major misjudged**: the report says `major: 4` (polluted by the QT variable of vcglib's legacy qmake projects), while the main project is actually Qt5 ≥5.15; lowercase unknown qtcore/qtgui variants are mixed into the module table.
- **Performance**: deps 2.94-3.00s (22k+ source files) / fetch-deps 0.05s.

### 2.4 Problem classification summary

| Problem | Project | Classification | Disposition |
|------|------|------|------|
| kernel32 dynamic_load false report | gen-h | defect (platform macro guard not filtered) | **Fixed** (5985fb3) + 2 unit tests |
| Silent cloner submodule failure | all submodule projects | defect (syntax error + swallowed error) | **Fixed** (c069898) + unit test |
| Leakage from example/test projects inside the vendored subtree | gen-o (vcglib apps/eigenlib tests) | defect (direction: depth constraints on non-build-target directories inside submodules) | Not fixed, recorded as residual (see §3) |
| qtpromise.tests.utils target name mixed in | gen-h | defect (minor, 1 noise entry) | Not fixed, recorded as residual |
| Qt major misjudged (4) | gen-o | defect (minor, legacy qmake pollutes the hint) | Not fixed, recorded as residual |
| KDSingleApplication-qt version number lost | gen-e | defect (minor, version token lost after ${VAR} interpolation) | Not fixed, recorded as residual |

---

## 3. Residual items (not fixed, for follow-up)

1. **Dependency leakage from non-build directories inside submodules** (gen-o: vcglib's apps/eigenlib/unsupported test projects leak about 20 depth-1 noise entries). Direction: combine .gitmodules submodule paths + "subdirectories not included in the main build" (apps/test/unsupported naming traits) into a depth constraint; must avoid breaking normal cases like corpus-b's corpus-b-core where "the dependency manifest lives in a submodule".
2. **Test target names of vendored libraries mixed into the link list** (gen-h qtpromise.tests.utils; the path src/ui/libs/ has no vendored-characteristic segment).
3. **Qt major hint pollution** (gen-o: legacy qmake projects make the Qt5 main project be judged as 4; recommend giving the main CMakeLists find_package(QtN) priority over qmake hints).
4. **Version token lost when the find_package name contains ${VAR}** (gen-e KDSingleApplication-qt 1.1.0).
5. **e2e harness missed matches for resolved renames** (liblzma→xz is already connected via kb_seed.ALIASES; for similar cases, recommend the harness consume PKG_ALIASES uniformly).
6. **Scope of harness grep evidence** (libxcb/libdispatch false candidates: the references are inside submodule wrappers, which the harness's build-file search doesn't cover; recommend including submodule paths).
7. Previous-round residuals #2/#3/#4 (find_library debug suffixes, structured platform-block parsing, shared read cache in qt_scanner) still apply.

---

## 4. Fixes and commit list

| Commit | Content |
|------|------|
| bddcd59 | perf: find_node_by_name NOCASE function index (regression fix) + 3 unit tests |
| c069898 | fix: cloner `--init` syntax + triple wrapper passthrough + OR guard semantics + meson/autotools vendored skip + liblzma alias + unit test structure fix |
| 1270e53 | test(e2e): baselines regenerated from full clones + breakpad/crashpad note update |
| 5985fb3 | fix: dynamic_loads platform macro guard filtering (macro stack moved to qt_scanner) + 2 unit tests |
| (this commit) | docs: REGRESS-REPORT.md |

Unit tests 65→**94, all passing** (including 22 existing cases that had never been executed); final metrics for the four e2e projects are in §1.4.

---

## 5. Reproduction commands

```bash
cd portgraph
python tests/test_port_graph.py                        # 94 tests OK
python portgraph.py ingest all                         # main database: 6069 nodes
# Performance (median of 3 runs)
/usr/bin/time -f "%es" python portgraph.py deps workspace/gen-a --json > /dev/null
/usr/bin/time -f "%es" python portgraph.py fetch-deps gen-a --dry-run > /dev/null   # note: app name, not a path
# e2e regression (full clones with submodules)
python tests/e2e/run_e2e.py run --all --fresh-db
# Generalization projects
python portgraph.py deps workspace/gen-o --json
python portgraph.py deps workspace/gen-h --json
python portgraph.py fetch-deps gen-o --dry-run
# A/B (worktree isolation)
git worktree add .ab/c04060a c04060a   # inside workspace, share the clones via symlinks, then time with the same flow
```
