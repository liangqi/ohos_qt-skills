# TEST-REPORT: portgraph dependency analysis × real project corpus-b (e2e corpus tier C)

> Date: 2026-09-19 | Branch: `worker2-deps-test` (baseline f98a2e7 → 4 commits this round)
> Corpus: `portgraph/tests/e2e/corpus.json#corpus-b`, clone of master **2b540fe** (2026-09-18)
> Tool code: `portgraph/port_graph/` (qt_scanner / project_scanner / deps_report / deps_fetch / kb_seed / cloner)
> Unit tests: **54/54 passing** (baseline 44 + 10 new); the e2e reconciliation semantics (difference classes and metric definitions) were not changed.

---

## 0. Important background: upstream dependency model change

corpus-b master has migrated from "CI setup.sh apt list + `CB_COMPILE_USE_SYSTEM_*` system-library switches" (the 4.x era,
which the old oracle was compiled from) to **the corpus-b-deps custom dependency engine**:

- Dependency-manifest declarations: `require_dep(<name> [STATIC|SYSTEM|REBUILD])` / `require_source_dep(<name>)`
  (bundled source) / `require_tool(<name>)` (host build tool), located in
  `buildscripts/cmake/DependencyManifest.cmake` (application) and `corpus-b-core/buildscripts/cmake/ExtDepsManifest.cmake`
  (the corpus-b-core framework submodule), resolved by the `corpus-b-deps` submodule (recipes + prebuilt.lock);
- Qt components: `set(qt_components ...)` + `list(APPEND ...)` + `find_package(Qt6 6.8 REQUIRED
  COMPONENTS ${qt_components})` (variable form);
- The old oracle's pulseaudio / openssl / tinyxml / ffmpeg no longer exist on master.

So besides fixing portgraph, this round **rewrote
`tests/e2e/oracle/corpus-b.json`** following the e2e design flow (the oracle is reviewed and corrected by the agent), based on the manifest files in the repo + the `CorpusBOptions.cmake` defaults to determine
optionality. To present the contribution of the "code fixes" alone honestly, the metric comparison also gives
measurements of **old code × new oracle** (rerun with the f98a2e7 code checked out).

Also note: the first e2e run happened with submodules uninitialized (corpus-b-core/ and corpus-b-deps/ were empty directories), so the scan results
were badly distorted (deps_linked=1). The cloner was fixed to initialize submodules automatically (see §2.7), ensuring reproducibility.

---

## 1. Before/after metrics

### 1.1 Main comparison (same oracle: the new oracle rewritten this round)

| Metric | Pre-fix code (f98a2e7) × new oracle | After fix (HEAD) | Change |
|---|---|---|---|
| Detection recall (oracle runtime dependencies) | **38%** (6/16) | **100%** (16/16) | +62pp |
| Detection precision | **53%** | **100%** | +47pp |
| Total bug candidates | **22** (missed-dep 4 / resolution-gap 17 / false-positive 1) | **0** | −22 |
| depth-1 ghost nodes (pkg-unknown) | 24 | 5 (all genuinely without a bottle) | −19 |
| vendored dependencies correctly separated | 0 (all mixed into need_port) | 10 (status/role=vendored) | — |
| fetch-deps closure need_port | 22 | 5 | −17 |
| Closure overview | 41 items (would_download 10, no vendored class) | 84 items (would_download 49 / vendored 10 / cmd_only 3 / provided 16) | The transitive closure is more complete after the hb-core data source was filled in |

### 1.2 Reference: state at the start of the session (old code × old oracle, i.e. the previous round's baseline report)

recall 50% / precision 36% / bug candidates 10 (all resolution-gap; agent review found 10 alias gaps +
13 unknown-ok). These numbers depend on an outdated oracle and are only a historical reference; the structural problems they exposed
(contamination from embedded thirdparty code, false matches on comment lines, missing .cmake scanning) were all traced to their root causes and fixed this round.

### 1.3 Why the remaining bug candidates = 0 is genuine

The 5 ghost nodes (mnxdom / msdfgen / opusenc / pipewire / json_schema_validator) were each checked against
hb-core (4758 formulas, filled in by ingest this round) and cmd-pkgs (1248 packages) and confirmed to **genuinely have no bottle**, so portgraph's
need_port / unknown verdict is correct, not a resolution gap — this is written into `overrides/corpus-b.json` as the agent's
final verdict. 14 of the matched items resolve to real bottles (alsa-lib, libogg, libvorbis, libsndfile,
nlohmann-json, flac, opus, lame, fdk-aac, freetype, harfbuzz, libpng, zlib, jack).

---

## 2. Fix list (root cause → fix → unit test, item by item)

| # | Root cause (build-file evidence) | Fix | Unit test |
|---|---|---|---|
| 1 | **`build*` prefix wrongly excluded** (the biggest source of misses): `_walk` treated `buildscripts/` and `buildtools/` as build output directories and excluded them, so corpus-b-core's `ExtDepsManifest.cmake` / `DependencyManifest.cmake` / `SetupQt6.cmake` / `FindJack.cmake` trees were never scanned | Switched to `_BUILD_DIR_RE` (output-directory shapes such as `build` / `build-Debug` / `build123`); `buildscripts` / `buildtools` are scanned normally | `TestBuildscriptsDirNotExcluded` |
| 2 | **Contamination from vendored / dependency-engine directories** (the main source of false positives): `find_package`/`pkg_check_modules` embedded in third-party code or the engine itself, in `corpus-b-core/framework/audio/thirdparty/fluidsynth/fluidsynth-2.3.3/CMakeLists.txt`, `.../dockwindow/thirdparty/KDDockWidgets/python/CMakeLists.txt`, and `corpus-b-deps/recipes/lv2sdk/meta.cmake` (glib2/dbus1/lash/midishare/oboe/openmp/opensles/pulseaudio/pyside/python3/shiboken/portaudio/readline/SDL2/curl/lv2/lilv-0/suil-0/zix-0…), were counted as the app's depth-1 dependencies | New `_is_vendored_path()` (path segments `thirdparty`/`3rdparty`/`third_party`/`vendor`/`external`/`extern`/`deps`/`dependencies`/`subprojects` + the `*_deps` suffix); find_package / pkg_check / find_package_details / raw_links / fetched_deps / wrapper / include hints are all filtered; function-definition collection is not filtered (the engine defines require_dep inside a vendored path) | `TestVendoredCmakeSkip` |
| 3 | **False matches on CMake comment lines**: `# Exported targets for cmake: find_package(FluidSynth)` at `fluidsynth-2.3.3/CMakeLists.txt:851` produced `pkg-unknown:fluidsynth` | `_detect_cmake_packages` / `_detect_find_package_details` / `_detect_cmake_raw_links` / `_detect_fetched_deps` all apply `_strip_cmake_comments` before matching | Same as above |
| 4 | **require_dep dependency-manifest functions not recognized at all** (the main source of misses): all `require_dep`/`require_source_dep`/`require_tool` calls of the corpus-b-deps engine (ogg/vorbis/flac/opus/libsndfile/zlib/freetype/harfbuzz/libpng/fdk-aac/lame/opusenc/pipewire/msdfgen/nlohmann_json/json_schema_validator + 10 bundled-source dependencies) were missed | New `_detect_manifest_deps()`: the function name matches `require*dep/tool/package` and has a `function/macro` definition in the scanned CMake; the first argument is the dependency name, and mode splits into link/source/tool; a lightweight if/endif stack marks conditional (without evaluating). Graph side: link → runtime edge, source → **vendored edge** (fetch-deps status/role=vendored, not downloaded or descended into), tool gets no edge; the deps report merges them into the link/vendored/toolchain sections | `TestRequireDepManifest` (3), `TestFetchVendoredRole` |
| 5 | **Qt component list variables not expanded**: `find_package(Qt6 6.8 REQUIRED COMPONENTS ${qt_components})` yielded 0 components, and qt_modules had only 7 (from the include heuristic); in addition, `_walk`'s LIFO order let the same-named `set(qt_components ...)` in `sandbox/web_sandbox` shadow the main declaration | `_collect_list_vars()`: accumulates `set()` (multi-line) / `list(APPEND)`, pure identifier tokens; **cross-file union** (independent of traversal order); `_detect_qt` substitutes `${var}` in Qt find_package arguments. qt_modules 7→19 (adding network/svg/xml/quickwidgets/shadertools/concurrent, etc.) | `TestQtComponentsListVar` |
| 6 | **Alias gaps** (located in the previous round, landed this round): alsa→alsa-lib, sndfile→libsndfile, tinyxml→tinyxml2, glib2→glib, dbus1→dbus, ogg→libogg, vorbis→libvorbis, png→libpng, brotlidec→brotli, intl→gettext, utfcpp→utf8cpp, nlohmann_json→nlohmann-json (target packages verified to exist in hb-core/cmd-pkgs); additionally `find_package(Git/OpenMP/iconv/dl, etc.)` is skipped as a build tool/CMake built-in module (aligned with deps_report BUILD_TOOL_FINDPKG / CMAKE_BUILTIN_PACKAGES) | Entries added to `PKG_ALIASES` + `kb_seed.ALIASES`; `_FINDPKG_SKIP` extended | `Testcorpus-bAliasResolution` |
| 7 | **e2e not reproducible**: `git clone --depth 1` doesn't initialize submodules, so corpus-b-deps/corpus-b-core were empty → all dependency manifests invisible | `cloner.clone_repo` shallowly initializes submodules on clone/reuse (`--depth 1 --recursive`, silently degrades on failure) | `TestClonerSubmodules` (2) |
| 8 | **Asymmetric separators in the e2e matcher**: the oracle side's `norm_name` normalizes `_` to `-`, `pg_canon` didn't → `json_schema_validator` (an underscored require_dep name) could never match | `pg_canon` applies the same separator normalization (a matching-symmetry fix; difference classes and metric definitions untouched) | Measured in e2e (this case is covered by this round's corpus; the harness has no unit-test framework) |

Incidental: `ingest all` filled in the hb-core data source (workspace/hb-core sparse clone, 4758 formulas ingested);
before that the main database had 0 hb nodes (all hb evidence in the old report came from the previous round's environment).

---

## 3. Residual items (not fixed this round, recorded)

1. **require_dep conditional blocks are not evaluated**: declarations that are off by default, such as msdfgen (`NOT CB_MODULE_DRAW_USE_QTTEXTDRAW`, not enabled by default),
   pipewire (`CB_MODULE_AUDIO_PIPEWIRE` default OFF), and asiosdk (Windows), still enter the
   closure → the fetch-deps overview is on the conservative side (the deps report already marks them conditional + required=False). Consider evaluating
   common conditions using the `option(... ON/OFF)` defaults in `CorpusBOptions.cmake`.
2. **raw_libs noise in the deps report**: corpus-b-core creates targets with custom functions such as `declare_module`
   (engraving/global/cb_audio_*, etc.), invisible to the `add_library` scan → internal target names end up in the link list,
   and a few coincidentally resolve to hb package names (e.g. `global` → hb:global). Target definition recognition could be extended
   (`add_library` wrapped in a `function`/custom declare functions).
3. **need_port ghost nodes have no source link** (`source_url: ?`): pkg-unknown nodes carry no repo info;
   it could be filled in from the source pins in corpus-b-deps `recipes/*/spec.cmake` (engine-specific; generality to be discussed).
4. **The `corpus-b-core` submodule is wrongly listed in the vendored section of the deps report**: `_detect_gitmodules` lists every submodule as
   vendored, but corpus-b-core is the application framework itself (not a third-party library). The semantic boundary is undecided (doesn't affect e2e reconciliation).
5. **Reports for the other corpus projects were not rerun**: the e2e reports for corpus-a/corpus-c/corpus-d are still products of the old scanner;
   this round's fixes (especially vendored skipping, buildscripts scanning, and comment stripping) are expected to change their depth-1 lists
   (corpus-a's `ThirdParty/` directory will likewise be skipped correctly), so a later `run --all` to refresh the baselines is recommended.
6. **iconv alias decision**: the previous round suggested iconv→libiconv, but in deps_report semantics iconv is built into musl libc
   (CMAKE_BUILTIN_PACKAGES system-lib), so this round skips it per the tool's own semantics rather than aliasing it; the suggestion was not adopted.

---

## 4. Commit log

| commit | Content |
|---|---|
| `fix(deps): 6 scan/resolution root-cause fixes driven by the corpus-b e2e review` | qt_scanner/project_scanner/deps_report/deps_fetch/kb_seed + 8 unit tests + docs |
| `test(e2e): corpus-b reconciliation baseline update (master 2b540fe) + cloner submodule initialization` | oracle/overrides rewrite, cloner, corpus, pg_canon, 2 unit tests, baseline report |
| `test(e2e): corpus-b report baseline (final, with timestamp)` | Final report after the before/after experiment |

Final verification: `python -m unittest tests.test_port_graph` → **54/54 OK**;
`python tests/e2e/run_e2e.py run --project corpus-b --fresh-db` →
recall=100% / precision=100% / bug_candidates=0 (report at
`portgraph/tests/e2e/reports/corpus-b.report.md`).
