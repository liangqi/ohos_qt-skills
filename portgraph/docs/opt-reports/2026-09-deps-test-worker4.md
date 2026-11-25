# portgraph dependency analysis: out-of-corpus generalization test and performance validation report

> Branch `worker4-deps-test` (baseline f98a2e7, all 44 unit tests passing)
> Test date: 2026-09-19 | Workspace: `portgraph/`
> Bottom line: **the generalization test exposed 9 kinds of problems on 3 real projects outside the corpus; all root causes were fixed with 12 new regression unit tests (44→56, all passing); the full gen-a deps run went from 12.4s → 3.1s (4.0x); the e2e baseline corpus regression shows no real degradation**. Commits: `c04060a` (fixes), `d6a2877` (e2e regression refresh).

---

## 1. Test setup

### Data sources (ingest all)

| Source | Scale | Notes |
|---|---|---|
| Harmonybrew hb-core | 4758 formulas (all ported), 9395 dependency edges | Manual sparse clone (`workspace/hb-core`; a baseline leftover: `ingest harmonybrew` lacks automatic fetching, still outstanding) |
| cmd-pkgs | 1248 packages | Cloned automatically |
| KB Qt modules | 63 | — |
| Total | **6069 nodes / 9395 edges** | `python portgraph.py ingest all` |

### Out-of-corpus projects (outside the e2e corpora corpus-a/corpus-b/corpus-c/corpus-d)

| Project | Build system | Source files | Why chosen |
|---|---|---|---|
| gen-f | cmake+qmake | 751 | Dual build systems; `src/libraries/` vendored layout mixed with submodules |
| gen-e | cmake | 1185 | Component-style GStreamer/GLib/GIO dependencies; rich CI install lists |
| gen-a | cmake+qmake | 22769 (35MB of text) | Custom CMake macros (kis_add_library); the most dependency variant names; performance stress-test sample |

Manual reference sources: each project's CMakeLists/Find module text, `.gitmodules`, CI workflows, README/INSTALL, plus spot checks of hb/cmd-pkgs artifact tarball contents (`tar tzf` to check .pc/.so ownership, measured on glib/gstreamer/openexr).

---

## 2. Generalization findings: which problems recur across projects

### Recurring across projects (hit in ≥2 projects)

| # | Problem | Projects | Root cause | Fix |
|---|------|---------|------|------|
| 1 | **hb formula version extraction failed → direct bottle links missing** | Global (419/4758 formulas, boost/antlr/ant/aom/action-validator…; the Boost artifact for gen-e/gen-a showed `brew install boost`) | `_URL_VER_RE` only recognized "version immediately followed by an extension", not suffix segments like `-bin`/`-b2-nodocs`, `.crate`, an uppercase `V1.30` prefix, a letter suffix like `2.4j`, or the version as its own path segment | Extended regex + path-segment fallback; 227 versions recovered (0 regressions), direct links spot-checked with HTTP 200 |
| 2 | **Resolution semantics split between scan time and report time** | gen-e (libsparsehash: fetch-deps reported need_port while the deps report had an artifact), gen-a (gstreamer-1.0/fftw3 ghosts) | `project_scanner` only did "exact name + PKG_ALIASES", without lib-prefix stripping/version-suffix stripping; `deps_report._resolve` had the full ladder | Extracted a shared `kb_seed.resolve_pkg_name` (alias first → original name → lib-prefix variants → version suffix → build-form suffix), used by both |
| 3 | **Different names of the same library not merged → duplicate entries/duplicate downloads** | gen-a (fftw 24 entries, webp 7, lcms 7, jpeg 6), gen-e (sqlite3+sqlite double artifact download), gen-f (botan-2/botan-3/Botan3, three entries) | PKG_ALIASES lacked component/variant names; aliases didn't apply to candidates after lib-prefix stripping; cmd-pkgs `sqlite3` and hb `sqlite` are cross-source different libraries with the same name | Extended the alias table (all verified against tarball contents: glib components, the 3 core gstreamer modules, 12 fftw variants, the webp/openjpeg/openexr/gsl/lcms2 families, etc.) + the ladder expands aliases for candidates + alias-first eliminates the sqlite3/sqlite double artifact + find_package name alias rewriting (KDcrawQt6→kdcraw) + ghost nodes use the canonical name |
| 4 | **In-project targets treated as external dependencies (false need_port)** | gen-a (45 internal gen-a* targets + junk names WIN32_DEBUG_POSTFIX/d), gen-f (fakevim: `set(bin fakevim)` + `add_library(${bin})`, indirect via a variable) | `_ADD_TARGET_RE` didn't recognize macro wrappers (`add_library(${ARGS})` inside `macro(kis_add_library)`) or `${VAR}` target names; CMake variable names/single-character values in find_library argument lists were taken as library names | Macro-wrapper detection (the first argument of a call to a macro/function whose body contains add_library counts as a target) + `${VAR}` resolved through the set() table + find_library filters all-uppercase underscore tokens and single-character tokens |
| 5 | **CI list parsing noise** | gen-e (the `-y` of `apt install -y` truncated into a package name `y`) | The token regex required the first character to be alphanumeric, so the leading `-` was dropped and `startswith("-")` never took effect | The token regex includes the leading `-`, then filters uniformly; the skip set gains upgrade/dist-upgrade |
| 6 | **Test frameworks/compiler runtime libraries falsely reported as need_port** | gen-f (gtest_main, gcov) | The raw link-name path didn't check TEST_FRAMEWORKS; atomic/gcov/intl weren't in the system library list | Section 6b hooks into TEST_FRAMEWORKS → test role; OHOS_SYSTEM_LIBS gains atomic/gcov/intl (keys normalized to lowercase) |

### Specific to a single project

| # | Problem | Project | Root cause | Fix |
|---|------|------|------|------|
| 7 | **Vendored source directories reported as need_port** | gen-f (`src/libraries/` layout: fakevim/botan/litehtml/gumbo source is in the repo yet reported as "no artifact → build from source") | `_detect_vendored_dirs` only recognized directory names like 3rdparty/external and only one level deep | New in-tree judgment: an unresolved name matching an in-project source directory (vendored path segment / dependency-collection parent directory with ≥5 library subdirectories / README features, a triple threshold) → kind=in-tree; **counterexample check**: gen-a `libs/flake/text/lager` (the project's own code) and `3rdparty/lcms` (iccjpeg glue, no build files) are not wrongly included |
| 8 | **Ghost nodes created at scan time for build tools/platform interfaces** | corpus-a/corpus-d/corpus-b (pkg-unknown:python3 and :systemd entered need_port) | The scan phase didn't know the BUILD_TOOL_FINDPKG/INTERFACE_BOUND_PACKAGES classifications | `_link_third_party` skips both lists (imported inside the function to avoid circular dependencies) |
| 9 | **Bare macOS framework link names/case matching** | gen-a (Foundation/Security reported as a package GAP via find_library; GLESv3 didn't match the mixed-case key because of `.lower()`) | Inconsistent key case in OHOS_SYSTEM_LIBS; INTERFACE_BOUND_PACKAGES lacked Foundation/Security, etc. | Keys normalized to lowercase; added foundation/security/coreservices/corefoundation |

### Judged "correct behavior" after manual verification (not fixed)

- gen-a gstreamer-app/audio/pbutils/tag `need_port`: the cmd-pkgs gstreamer tarball was measured to contain only base/controller/net/check, and the plugins-base components genuinely have no HarmonyOS artifact — **deliberately no alias added**; the need_port verdict is correct.
- gen-e getopt (inside an if(WIN32) block)/Sparkle (if(APPLE)): the lack of structured platform-block parsing is a known limitation (same origin as worker2 leftover #2); the entries are readable and don't mislead the agent's decisions.
- Mlt7/qca2/Poppler/PyQt5/6/KSeExpr/Lager/Immer/Zug/libunibreak/QUAZIP (gen-a), libchromaprint/libgpod/libpulse/KDSingleApplication-qt (gen-e), botan (corpus-c, already reviewed in e2e): hb/cmd-pkgs genuinely have no corresponding package, so need_port is correct.

---

## 3. Fix list and verification

| Fix | Files | Verification |
|------|------|------|
| URL version extraction | `port_graph/harmonybrew.py` | 11 URL-shape unit tests; full re-ingest diff: 227 gained / 0 lost / 0 changed; boost-1.92.0_1 / antlr-4.13.2_1 / action-validator-0.9.0 direct links HTTP 200 |
| Macro wrapper + variable target recognition | `port_graph/qt_scanner.py` | gen-a internal targets 45→0; fakevim excluded; 2 unit tests |
| find_library junk tokens | Same as above | WIN32_DEBUG_POSTFIX/d gone, quazip kept; unit test |
| env -y | Same as above | `y` gone from the gen-e env list; unit test |
| Shared resolution ladder | `port_graph/kb_seed.py` (new `resolve_pkg_name`), `deps_report.py`, `project_scanner.py` | Unit tests for libfftw3f_omp→fftw, gio-2.0→glib, jpeg-static→jpeg-turbo, etc.; gen-a link 177→65 |
| PKG_ALIASES extension | `port_graph/kb_seed.py` | All verified against tarball/bottle contents (glib/gstreamer/openexr tar spot checks) |
| in-tree judgment | `port_graph/deps_report.py` | 6 gen-f items moved to in-tree; gen-a lager/lcms counterexamples not wrongly included; 2 unit tests |
| test/system-lib/platform-iface classification | Same as above | gtest_main→test; atomic/gcov/intl→system-lib; Foundation/Security→platform-iface; unit test |
| Skipping build-tool/interface names at scan time | `port_graph/project_scanner.py` | corpus-a python3 and corpus-d/corpus-b systemd ghosts eliminated |
| Docs | `docs/deps-report.md` | Updated descriptions of the resolution ladder and performance semantics |

**Unit tests: 44 → 56, all passing** (`python tests/test_port_graph.py`, 12 new cases in `TestGeneralizationFixes`).

### Effect of the fixes (manual before/after comparison)

| Project | link entries | fetch-deps closure | need_port |
|------|----------|----------------|-----------|
| gen-f | 17 (incl. 8 false positives) → **16** (in-tree 6 / test 1 / system-lib 2 reclassified) | 28 → **47** (real dependencies such as the aspell/hunspell artifacts enter the closure as resolution fills in) | 6 → **4** (botan family unified) |
| gen-e | 40 → **36** (gio/gobject/gio-unix merged into glib, fftw3→fftw with an artifact, gstreamer-base merged into gstreamer) | 52 → **55** | 21 → **11** |
| gen-a | **177 → 65 (-63%)** (45 internal targets + 24 fftw variants + webp/lcms/jpeg families merged) | 143 → **112** | 38 → **16** (14 of the remaining 16 are real gaps) |

Spot checks of version-check verdicts: gen-e TagLib `>= 2.0` (find_package) and `>= 1.12` (multi-source merge) against hb 2.3.2 = satisfied ✓; sqlite `>= 3.9` after alias merging is marked unknown + a scale warning (library major version vs package version numbering) ✓, as designed.

---

## 4. Performance benchmarks

### Full deps run (scan + ingest + report, with `--json`)

| Project | Baseline | After fix | Speedup |
|------|------|--------|------|
| gen-a (largest closure, 35MB of source) | **12.4s** | **3.05s** | **4.1x** |
| gen-e | 1.7s | 0.63s | 2.7x |
| gen-f | 2.6s | 0.81s | 3.2x |

### fetch-deps closure (--dry-run)

gen-a 112-item closure **0.06s**, gen-e 55 items 0.05s, gen-f 47 items 0.05s — the closure BFS is not a bottleneck.

### Confirming the _GraphCache effect (measured on gen-a)

- node queries: 384 calls / 64 misses → **83% hit rate**; out_edges 261 / 93 misses;
- the `analyze_dependencies` phase takes only **0.13s** (0.129s with the cache disabled as a control, identical output) — **the cache works but analyze is no longer a bottleneck** (gen-a's link closures overlap little; the 11.6x scenario in worker2's synthetic stress test is a highly repetitive deep chain, for which the cache is still key).

### Remaining hotspots (breakdown of the 3.05s, cProfile)

1. `_detect_platform_interfaces` ≈1.9s: the literal-anchor `any(a in text …)` scan itself (29 anchors for the win32 rule) + reading 6293 files. Possible follow-ups: merge anchors into a single-pass scan, or bucket by first character.
2. `qt_scanner.scan_project` ≈1.7s: third_party (0.39s)/wrapper_deps (0.34s)/dynamic_loads each read all source files independently (29064 read_text calls) — a **shared read cache** could save roughly another 1/3 of the IO.
3. DB writes and pathlib overhead ≈0.3s.

### Performance fix details

- `_detect_platform_interfaces` 10.7s → 1.9s: ① files with no interface-rule hit skip the line-by-line macro-stack tracking (`_macro_stack_status` calls 6293→23); ② 12 platform rules gain literal-anchor prefiltering — every regex branch contains a required substring, so no anchor means no match, **semantics unchanged (full gen-a comparison: 54 hits, 0 misses)**.
- `_detect_dynamic_loads` 1.4s → 0.1s: substring prefiltering for dlopen/QLibrary/QPluginLoader.

---

## 5. e2e baseline corpus regression (4 projects, rerun after the fixes)

| Project | recall | precision | bug candidates | Attribution of change |
|------|--------|-----------|----------|----------|
| corpus-a | 24% | 100%→80% | 7→**8** | python3 ghost eliminated (-1); libfido2 is an upstream-added webauthn submodule (readme-omitted, correctly detected by portgraph, README not updated); libudev genuinely has no HarmonyOS package (need_port correct); the 7 missed-deps are known from the baseline (desktop-app::external_* targets whose submodule is missing) |
| corpus-b | 50%→25% | 46%→**100%** | 11→**1** | **All 10 resolution-gap ghosts resolved** (alsa/sndfile/tinyxml/brotlidec/dbus1/glib2/iconv/intl/ogg/png → real packages); the recall drop is due to an **upstream refactor**: in the fresh clone, the third-party freetype/fluidsynth trees embedded in `src/framework/` were deleted (corpus drift, not a regression), and the oracle's old dependencies became readme-stale |
| corpus-c | 100% | 23%→25% | **0** | Metrics stable; the precision gain comes from eliminating surplus ghosts |
| corpus-d | 80% | 100% | 1→**2** | systemd ghost eliminated; after the LibtorrentRasterbar ghost name was normalized, the harness classification changed — libtorrent genuinely has no HarmonyOS package, so the need_port verdict is unchanged (residual note below) |

**Conclusion: no real accuracy degradation; every metric change is attributable to (a) ghost elimination or (b) upstream corpus drift.**

---

## 6. Residual items (not fixed, for later)

1. **The hb-core data source lacks automatic fetching** (a baseline leftover): `ingest harmonybrew` silently returns `files: 0` when `workspace/hb-core` is missing. Recommend mirroring cmdpkgs' automatic sparse clone (set up manually this time; the 4758 formulas are in place).
2. **Debug-suffix variants from find_library** (cblasd/gsld/gslcblasd/vpxmd, 4 in gen-a): stripping a `-d` suffix would break real library names (e.g. `libd`), so no general rule was added.
3. **No structured platform-block parsing** (find_package/getopt/Sparkle inside if(WIN32)/if(APPLE)) — name-level classification already covers the main cases; block-level judgment needs CMake semantic analysis, and its cost/benefit is still to be evaluated (same origin as worker2 leftover #2).
4. **qt_scanner detectors read files repeatedly** (29064 read_text calls): a shared read cache is expected to save another ~1s but involves changing several function signatures; not touched this time.
5. **LibtorrentRasterbar ghost-name matching in the e2e harness**: after ghost-name normalization (libtorrent-rasterbar vs libtorrentrasterbar), the harness reports both missed-dep + resolution-gap; recommend normalized matching of pkg-unknown names on the harness side.
6. **include contamination from embedded third-party code** (corpus-a util-linux/openssl, known from the baseline): the #include heuristic inside vendored directories counts the host's libraries into the app's depth-1; this round's in-tree index could be used to exclude includes under vendored paths — left for later.
7. The corpus-b e2e oracle needs to be re-reviewed and finalized for the new upstream structure (src/framework deleted).

---

## 7. Reproduction commands

```bash
cd portgraph
python portgraph.py ingest all                     # hb-core needs a manual sparse clone first (see residual #1)
python tests/test_port_graph.py                    # 56 tests OK
python portgraph.py deps workspace/<gen-f|gen-e|gen-a> --json
python portgraph.py fetch-deps <app> --dry-run
python tests/e2e/run_e2e.py run --all              # corpus regression
# performance
/usr/bin/time -f "%es" python portgraph.py deps workspace/gen-a --json > /dev/null
```
