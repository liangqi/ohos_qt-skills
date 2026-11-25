# TEST-REPORT: portgraph dependency analysis × corpus-a (e2e corpus tier C), measurements and optimization

> Branch `worker1-deps-test` (baseline f98a2e7, all 44 unit tests passing) | workspace `~/harmony-workspace/worker1`
> Under test: `portgraph deps` / `fetch-deps` / the e2e reconciliation harness (`portgraph/tests/e2e/run_e2e.py`)
> Corpus: corpus-a (corpus-a, tier C, real project, shallow clone of HEAD on 2026-09-19) + full-corpus regression (corpus-c / corpus-b / corpus-d)
> Constraints observed: the e2e reconciliation semantics were not changed (the recall/precision formulas, oracle files, and BUG_CLASSES definitions were left untouched); every fix located its root cause from build-file evidence, never with the aim of "padding the metrics".

---

## 1. Before/after metrics

### 1.1 corpus-a (this round's target project)

| Metric | Pre-fix baseline¹ | After fix | Change |
|---|---|---|---|
| Detection recall | 24% (4/17) | **53% (9/17)** | +29pp |
| Detection precision² | 80% | 60% | −20pp (see note) |
| Bug candidates | 9 (missed-dep 7 + resolution-gap 2) | **2 (missed-dep 2, both residual blind spots)** | −7 |
| False positives | 0 | 0 | — |
| Direct dependencies (depth-1, non-Qt modules) | 6 (4 packages + 2 ghosts) | 19 (12 packages + 7 ghosts) | Wider detection coverage |
| deps report link classification | 10 items | 26 items | +16 |
| fetch-deps closure | 38 (need_port 2) | 61 (need_port 7) | More complete |

¹ The pre-fix baseline is this round's rerun on a **fresh clone** (corpus-a HEAD had moved on: added lib_fido2/fido2 support, Python3 mesh codegen, etc.): recall 24% / precision 80% / bug 9. The old report committed in the previous round (recall 24% / precision 100% / bug 7) was based on an earlier clone and main-database DB, so it is not directly comparable.

² Precision semantics (existing formula, unchanged): `matched / (matched + readme-omitted + false-positive)`. The drop is not due to false positives (false-positive stays at 0) but because **6 newly detected real dependencies are not listed in the README** (boost, cmark-gfm, glib, libfido2, libiconv, minizip, all with target_link_libraries evidence, classified readme-omitted = portgraph correct) and entered the denominator. In other words, the precision drop is a by-product of the semantics when "detection coverage widens and all new hits are real", not a quality regression.

### 1.2 Full-corpus regression (all 4 projects rerun, updated report baselines committed)

| Project | Old baseline³ | New baseline | Notes |
|---|---|---|---|
| corpus-a | 24% / 100% / 7 | **53% / 60% / 2** | See above |
| corpus-c | 100% / 23% / 0 | 100% / 23% / 0 | Per-class counts identical, zero regressions |
| corpus-b | 50% / 46% / 11 | **38% / 27% / 0** | bug 11→0; the recall change is mainly due to the upstream corpus-b-deps refactor (§3.2), not a code regression from this round |
| corpus-d | 80% / 100% / 1 | **100% / 100% / 0** | libtorrent-rasterbar miss fixed (unified version-suffix/lib-prefix resolution) |

³ Old baselines are taken from the report files committed in the previous round (old clone + old main-database DB state).

Unit tests: 44 → **56, all passing** (12 new; every fix has a corresponding test).

---

## 2. Fix list (root cause → fix → test)

### 2.1 Tool side (port_graph)

| # | Root cause (build-file evidence) | Fix | Test |
|---|---|---|---|
| T1 | **`target_link_libraries` skipped all `::` imported targets** (old qt_scanner logic `or "::" in t: continue`). corpus-a links every third-party library as `desktop-app::external_zlib/external_openal/external_webrtc/...`, and the real find_package calls live in the uninitialized `cmake/` (cmake_helpers) submodule — the scanner was nearly blind to this kind of project, and openssl/zlib/ffmpeg were only caught by luck through the include heuristic | Parse `ns::external_<name>`: strip the `external_` prefix, add to raw_libs and mark `ext_target=True` (high-confidence external declaration); `PkgConfig::` (already covered by pkg_check_modules), `Qt*::`/`kf` prefixes, and targets defined by in-project add_library are still excluded | `TestExternalTargetLinks` (2) |
| T2 | **find_package(Python3) created a runtime edge** → ghost `pkg-unknown:python3` (corpus-a cmake/generate_models.cmake:22 bakes meshes at build time; deps_report had long classified it build-tool, so the graph side was inconsistent) | Moved the `BUILD_TOOL_FINDPKG` table into qt_scanner; project_scanner filters it, shared by both sides | `TestBuildToolFindpkgFilter` |
| T3 | **Win32 system libraries got false edges**: `bcrypt` in the Windows section of lib_fido2.cmake hit cmdpkgs:bcrypt (the OpenBSD password-hashing library, unrelated) | Moved the `WIN32_SYSTEM_LIBS` table into qt_scanner and extended it (bcrypt/hid/winusb/cfgmgr32); project_scanner filters at scan time | `TestWin32LibNoFalseEdge` |
| T4 | **Alias gaps** (external_* bare names → HarmonyOS packages): openal→cmdpkgs:openal-soft (OpenAL Soft, kcat), iconv→hb:libiconv, boost_regex→hb:boost, cmark_gfm→hb:cmark-gfm (separator difference), qr_code_generator→cmdpkgs:libqrcodegen (nayuki QR-Code-generator; the cmd-pkgs 1.8.0 version series has the same origin, verified) | Added 5 entries to kb_seed.PKG_ALIASES (each verified against the identity of the DB package node) | `TestPkgAliasescorpus-a` |
| T5 | **pkg-config version-suffixed names weren't resolved on the graph side**: corpus-b corpus-b-deps `pkg_check_modules(... lilv-0 suil-0 zix-0 lv2)`; hb:lilv/hb:zix exist but the graph side produced ghosts (deps_report._resolve had long supported this approximation, so the two sides were inconsistent) | kb_seed.resolve_package gains add-lib-prefix/strip-lib-prefix/version-suffix-stripping approximations (aligned with deps_report._resolve) | `TestPkgConfigVersionSuffixResolve` |
| T6 | No distinction between vendored submodules (declared in .gitmodules, compiled with the project) and external packages: external_cmark_gfm resolves to a package, but external_microtex/external_kcoreaddons produced misleading need_port ghosts | project_scanner: when an external_target is unresolved, first check the folded .gitmodules names (name/last path segment/last URL segment); a vendored hit creates no ghost | `TestExternalTargetLinks.test_graph_links_and_ghosts` |

### 2.2 Harness side (run_e2e.py, evidence/attribution accuracy, reconciliation semantics unchanged)

| # | Root cause | Fix | Test |
|---|---|---|---|
| H1 | **Evidence grep matched line by line**: in corpus-a each target_link_libraries link item sits on its own line, so line-by-line matching missed all evidence from multi-line statements (which once caused boost/glib/minizip/cmark-gfm to be misjudged as false positives) | Strong evidence now uses a whole-file finditer + line-number backtracking | `test_grep_multiline_tll` |
| H2 | **`\b` word boundaries don't match underscore-joined names**: in `external_xxhash`/`lib_zlib`, xxhash/zlib are surrounded by `_` (a word character), so `\b` doesn't hold — the previous round misjudged zlib as a false positive because of this (recorded in the agent notes) | Word boundaries via lookaround assertions (anything non-alphanumeric counts as a boundary), verified not to over-match (zlib ⊄ zlibng) | `test_grep_boundary_matches_prefixed_target` |
| H3 | **Every ghost node was reported as resolution-gap (bug candidate)**: libudev (HarmonyOS has no udev; the HDF driver framework replaces it), webrtc/ada/rnnoise and other real external dependencies with genuinely no corresponding package in the database — the ghost is a **correct detection** (fetch-deps correctly reports need_port), not a bug | New `ghost_plausible_package()`: resolution-gap is reported only when the database has a similar known package (alias hit / equal folded names / substring sharing a full separator-delimited component, udev⊄uudeview), otherwise unknown-ok (that class was reserved in BY_DESIGN_CLASSES and is enabled for the first time this round) | `test_ghost_plausible_package` |
| H4 | **Oracle-side vendored items had no evidence-based classification**: gsl/range-v3/hunspell are .gitmodules submodules (corpus-a/ThirdParty/GSL, etc.), and classifying them as readme-stale distorts the meaning | `vendored_submodule_match()`: classify as vendored based on .gitmodules evidence (new by-design class) | `test_vendored_submodule_match` |
| H5 | Separator differences in name matching: `crash_reports` vs `crash-reports` didn't match | pg_canon folds `_`→`-`; README_ALIASES gains qr-code-generator→libqrcodegen | `test_names_match_underscore_folding`, etc. |

**Note on semantics** (why this doesn't count as "changing the reconciliation semantics"): the recall/precision formulas, the oracle file contents, and the BUG_CLASSES definitions (missed-dep/resolution-gap/false-positive) were not changed. The vendored/unknown-ok classes added this round only affect **difference attribution** (why a difference exists), not the comparison of "oracle runtime dependencies × portgraph direct dependencies" itself; vendored items stay in the recall denominator (conservative semantics, so improved classification doesn't inflate recall).

---

## 3. Residual items judged to be tool problems (not fixed, documented)

### 3.1 corpus-a breakpad / crashpad missed (missed-dep ×2, the only remaining bug candidates)

- **Evidence**: the main repo only references them in the macOS/macstore platform-guarded sections (CMakeLists.txt:2349 `find_program(CRASHPAD_HANDLER crashpad_handler)`, :2381 `target_link_frameworks(corpus-a PRIVATE Breakpad)`); the Linux-side integration goes entirely through `desktop-app::external_crash_reports` (:97), whose internal breakpad/crashpad either-or logic lives **inside the cmake/ submodule (desktop-app/cmake_helpers), which the shallow clone didn't initialize, so it is outside the scan scope**.
- **Verdict**: tool problem (uninitialized-submodule blind spot); kept as missed-dep + a manual note in overrides, not masked.
- **Possible follow-ups**: `--recurse-submodules` when cloning (cost: submodules like tg_owt/webrtc are huge); or downgraded annotation of missing paths based on .gitmodules hints ("declarations in this submodule are invisible"). Recorded in `docs/deps-report.md` §Known limitations.

### 3.2 corpus-b recall 50%→38% (not a code regression from this round; judged a tool-coverage problem)

- **Evidence**: the upstream corpus-b-deps submodule was refactored — the old commit exposed system dependencies via find_package/pkg_check_modules (alsa/jack/sndfile/tinyxml, etc.; the old report's 23 pg-side nodes came from these); the new commit (6525edb) switched to a custom `set(DEP_LIBS sndfile)` / `DEP_TARGET` DSL, invisible to a generic scanner.
- **Verdict**: tool-coverage problem (each project's custom wrapper convention; a generic tool can only cover PACKAGE/LIBRARY-keyword-style conventions). Bug candidates went from 11 → 0 (of the old 10 resolution-gaps, lilv-0/zix-0 were fixed by T5 and the rest disappeared with the upstream refactor; the old single false positive, util-linux, no longer appears).

### 3.3 corpus-a lzma-sdk / liblzma / opus classified readme-stale (same blind spot as 3.1)

- **Evidence**: the main repo's build files really contain no reference to them (grep is empty); liblzma/opus come in through cmake_helpers' external prebuilt Libraries directory or tg_owt (the WebRTC stack), so the granularity of the README declarations is naturally misaligned with the declarations visible in the main repo.
- **Verdict**: the same family of submodule/external-directory blind spots as 3.1; readme-stale is a factual description within the current scan scope (the overrides notes explain why), not a misclassification.

### 3.4 Corpus drift notice (not a tool problem)

The clone HEADs of corpus-a and corpus-b have both moved on (corpus-a added a fido2/WebAuthn stack and Python3 build-time codegen; corpus-b-deps was refactored), while the oracle (reviewed) still reflects the old HEAD. Every difference in this round was manually reviewed and classified one by one; before future e2e runs, it's recommended to check that the oracle matches the clone HEAD.

---

## 4. Deliverables

- Code fixes: `port_graph/qt_scanner.py`, `project_scanner.py`, `kb_seed.py`, `deps_report.py`
- Harness fixes: `tests/e2e/run_e2e.py`
- Unit tests: `tests/test_port_graph.py` 44→56, all passing (`python -m unittest tests.test_port_graph`)
- e2e baseline update: `tests/e2e/reports/{corpus-a,corpus-c,corpus-b,corpus-d}.report.{md,json}` (all 4 projects rerun, --fresh-db)
- overrides update: `tests/e2e/overrides/corpus-a.json` (removed 5 reclassifications that are now handled natively, kept the breakpad/crashpad residual notes)
- Docs: `docs/deps-report.md` (explanation of external_* imported-target resolution + the uninitialized-submodule blind spot as a known limitation)
- Commit: the `worker1-deps-test` branch (this report committed together with the code)
