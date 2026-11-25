# DEPS-OPT-REPORT — portgraph dependency analysis (deps / fetch-deps) optimization report

> Branch: `worker1-deps-opt` (single commit `0501a99`)
> Scope: `portgraph/port_graph/{deps_report,deps_fetch,kb_seed,project_scanner}.py`,
> `portgraph/portgraph.py`, `portgraph/tests/`, `portgraph/docs/`
> Validation environment: Python 3.10, main database with 4758 Harmonybrew formulas + 1248 cmd-pkgs ingested;
> real corpus corpus-c (884 source files, e2e corpus tier B); synthetic sample project deps-sample.

---

## 1. Current state and how problems were located

### Toolchain status

- `deps <path|app>`: `qt_scanner` scan of 19 signal types → `deps_report.analyze_dependencies`
  five-role classification (link/build-tool/runtime/test/vendored/provided/env) + multi-source version constraint checks
  + hb/cmd-pkgs artifact resolution → text/JSON report
- `fetch-deps <app>`: `deps_fetch.dependency_closure` (BFS over runtime/uses-module edges) →
  per-node classified download (bottle sha256 verification / cmd-pkgs tar.gz) → manifest (role/status/toolchain)
- Scan ingestion (`project_scanner.scan_project`) connects names from find_package/pkg_check_modules etc.
  to package nodes by edges; unresolved ones become `pkg-unknown:*` ghost nodes

### Locating problems

Ran the complete chain: `ingest all` (hb-core sparse clone, 4758 formulas) → synthetic sample project
`deps`/`fetch-deps` → real project corpus-c `deps`/`fetch-deps --dry-run` → e2e reconciliation
harness (`tests/e2e/run_e2e.py run --project corpus-c`), collecting evidence from five angles: accuracy, dedup consistency,
classification semantics, output readability, and CLI usability.

---

## 2. Change list (4 improvements)

### 1. Fixing version-check semantics: eliminating false conflicts from cross-name aliases (accuracy ★)

**Problem**: after `pkg_check_modules(FF REQUIRED "libavcodec >= 58")` was merged into ffmpeg via alias,
`_check_req` compared the library major version 58 numerically against the ffmpeg package version 9.0.2 → falsely reported
`✗version conflict` + `HarmonyOS version 9.0.2 (below requirement)`, nudging the agent toward "downgrade or build a newer version from source".
(libavcodec's pkg-config Version is a 61.x.x-style ABI version, a different numbering scheme from ffmpeg releases.)

**Change** (`deps_report.py`):
- When pkg_check_modules is merged via alias and carries a version constraint, the entry records `version_req_from` (the constraining library name)
- `_version_check`: when `version_req_from` is present, that constraint evaluates to `unknown` (incomparable numbering),
  producing no conflict; a new info-level warning explains "library version numbering vs package version, needs manual confirmation"
- The JSON report structure gains the `version_req_from` field accordingly (docs/deps-report.md updated)

### 2. Deduplicating different names of the same library: merging contradictory deps entries + duplicate fetch-deps downloads (dedup ★)

**Problem** (measured on corpus-c):
- In the deps report the qrencode library appeared **3 times** (`QREncode`→hb:qrencode with a bottle,
  `libqrencode`→cmdpkgs:libqrencode with a direct link, and a `qrencoded` ghost); the same library said "artifact available" in one entry
  and "no artifact" in another
- In fetch-deps, `qrencode` and `libqrencode` were **each downloaded once** (two install roots, two copies of the .so);
  the `xkbcommon` ghost showed "needs porting yourself" while the `libxkbcommon` bottle in the same closure downloaded normally —
  two contradictory conclusions for the same dependency

**Change**:
- `kb_seed.PKG_ALIASES` (new shared table, migrated and extended from the former deps_report.LIB_NAME_ALIASES):
  fills gaps confirmed by e2e review: `xkbcommon→libxkbcommon`, `x11→libx11`,
  `pcsc/libpcsclite/pcsclite→pcsc-lite`
- `project_scanner._link_third_party`: retries via the alias table when the direct name is unresolved (eliminates ghosts;
  name resolution is consistent across analyze/fetch-deps/deps)
- `deps_report._resolve`: likewise falls back to the shared alias table
- `deps_report` 7b merge upgrade: besides resolved_node, entries are merged by the resolved node's **normalized name**
  (strip lib prefix/@variant) — hb:qrencode and cmdpkgs:libqrencode merge into one entry,
  multi-source evidence is kept, and when the base has no artifact the resolution from the side with an artifact is used
- `deps_fetch`: the `downloadable`/`installed_by_name` dedup key is normalized (`_norm_key`,
  strips the lib prefix) — the same library is downloaded only once, and the other node is marked `covered`

### 3. fetch-deps classification semantics and output (classification/readability ★)

**Problem**: `openmp needs porting yourself (source: ?)`, `gtest needs porting yourself (source: ?)` —
OpenMP is a compiler feature (libomp ships with the NDK) and GTest is a test framework; neither should be steered toward "porting".

**Change** (`deps_fetch.py` adds `_classify_special`, aligned with the deps report's semantics):
- CMake built-ins (Threads/OpenMP/iconv/dl) → `status=provided` + note (ships with the NDK/SDK)
- Test frameworks (GTest/Catch2/…) → `role=test` + note (not in the release package; status still follows artifact
  availability, and download info is kept when a bottle exists)
- Host build-tool ghosts (ECM and other artifact-less nodes, depth=1) → `role=build-tool`; ones with real artifacts
  (e.g. gettext, which is also a runtime library) are not reclassified, to avoid breaking transitive-dependency cases
- For need_port with no source link, output changes to "not ingested, no source link: please confirm the dependency name is correct…"
  (previously `(source: ?)`); when a note exists it is shown first
- The manifest `roles` count gains `test`/`build-tool` (docs/fetch-deps.md updated)

### 4. CLI and report readability fixes (usability)

- **Trailing `--compact`**: the former global flag only accepted `portgraph.py --compact deps X`; writing it the way people
  naturally do, `deps X --json --compact`, made argparse error out. The flag is now added to every subcommand, so
  both positions work (subparsers don't overwrite namespace values already set by the main parser)
- **build-tools count fix**: the former `len(build_tools)+len(tools)` double-counted find_package build
  tools and left out the fixed items (CMake/C++/compiler) — the sample project showed "0" yet listed 3 items below.
  Now it matches the rendered items: `len(tools)+cmake+cxx+compiler`
- The `_resolve_app` miss hint now covers the "a path was passed" case; `network` (the bare link name of the macOS Network framework)
  is classified platform-iface; `winscard` is added to the Win32 system library set
- BFS queue `pop(0)` → `deque.popleft()` (O(n²)→O(n))

### Incidental fixes (test assets)

- The `test_curl_formula` version assertion `8.21.0` changed to a pattern match `^8\.\d+(\.\d+)?(_\d+)?$`:
  this case was previously skipped because hb-core wasn't local; once the data source was filled in this time, it exposed that the upstream formula had moved on to
  8.22.0 (pre-existing data drift unrelated to these changes)
- The e2e harness `name_variants` gains **reverse alias** variants: alias-merged node names (libx11/
  pcsc-lite) can be hit by grepping the build files (`find_package(X11)`/`PCSC`), otherwise they are misjudged as false positives
- `overrides/corpus-c.json`: the 3 "ALIASES pending" resolution-gap rules have landed; notes updated

---

## 3. Before/after comparison

### 3.1 Synthetic sample (deps-sample: CMake + Qt5 + zlib/openssl/sqlite/X11/libavcodec)

| Dimension | Before | After |
|---|---|---|
| ffmpeg version check | `✗version conflict`, `HarmonyOS version 9.0.2 (below requirement)` (misleading) | No conflict mark + info "version constraint >= 58 comes from libavcodec's library version numbering… needs manual confirmation" |
| fetch-deps libavcodec | `needs porting yourself (source: ?)` (ghost node, although a bottle exists) | Resolved to `ffmpeg v9.0.2 needs download`, correctly expanding ffmpeg's 24 transitive runtime dependencies |
| fetch-deps gtest | `needs porting yourself (source: ?)` | `test framework, not in the release package; only handle it if you need to run tests on a HarmonyOS device` |
| fetch-deps x11 | `needs porting yourself (source: ?)` | `needs porting yourself (not ingested, no source link: please confirm the dependency name is correct…)` |

### 3.2 Real project corpus-c (884 source files)

| Dimension | Before | After |
|---|---|---|
| deps link entries | 32, with three contradictory qrencode entries | 29, same libraries merged (QREncode/libqrencode→1 entry, PCSC/pcsclite→1 entry with an artifact) |
| build-tools count | Showed `0` with 3 items listed below (and double-counted) | `10` = 7 tools + CMake + C++17 + compiler, matching what is shown |
| fetch-deps closure | 43 items: need_port **6**, covered 0 | 40 items: need_port **1** (only botan, which review confirmed has no HarmonyOS package, so the verdict is correct), covered 1 |
| qrencode download | qrencode + libqrencode **downloaded twice** | Downloaded once, the other node covered |
| xkbcommon/x11 ghosts | `needs porting yourself` (contradicting the libxkbcommon/libx11 bottles) | Ghost nodes filled in by the same library's bottle (would_download), real nodes covered |
| openmp | `needs porting yourself (source: ?)` | provided (compiler feature shipping with the NDK) |
| e2e reconciliation | bug_candidates **4** (resolution-gap×4), deps_unknown 6 | bug_candidates **0**, deps_unknown 2 (openmp/botan both reviewed as correct unknowns); recall 100% |
| Trailing `--compact` | argparse error, exit 2 | Compact JSON output as expected |

### 3.3 Tests

- 35 → **42** cases, all passing (7 new: alias version semantics, cross-source same-library merging, normalized dedup,
  special classification, scan-time alias resolution, build-tools count, trailing CLI --compact)
- Real download chain verified: `fetch zlib` bottle download + sha256 verification + NTFS link backfill work correctly

---

## 4. Remaining issues and recommendations

1. **Bare `target_link_libraries` names inside platform blocks**: corpus-c's `network` (a tll inside a macOS
   DARWIN block) is now classified platform-iface, but its `required` flag is still true — qt_scanner
   is unaware of the platform-block context at the tll call site. Recommendation: have qt_scanner record the
   `if(APPLE)/if(WIN32)` block containing the tll, and have deps_report downgrade bare names inside platform blocks to optional.
2. **The `qrencoded` ghost**: a threaded-variant name probed by find_library in FindQREncode.cmake;
   needs library-level alias knowledge (qrencoded→qrencode). Recommendation: extend PKG_ALIASES as needed.
3. **Risk of find_package names and hb package names sharing a name with different meanings** (already stated in the docs): extending PKG_ALIASES
   slightly widens the mismatch surface (e.g. the multi-precision library MPC vs the player mpc), so artifact URLs should still be checked manually before relying on them;
   consider adding a "source evidence" field to the alias table for display in the report.
4. **fetch-deps computes the closure twice**: `cmd_fetch_deps` first computes the total, then
   `fetch_app_deps` recomputes it (<0.1s at the current scale, negligible); if closures grow significantly,
   `fetch_app_deps` could gain a `closure=` reuse parameter.
5. **Test strategy for hb-core version drift**: `test_curl_formula` now uses a pattern assertion; the remaining case
   that depends on a local sparse checkout (1) still skips in environments without the data source, as expected.
6. **The other e2e corpora** (corpus-a/corpus-b/corpus-d) were not rerun this round (large clones);
   recommend running `run_e2e.py run --all` in a later round with network access to verify the effect of the alias changes on
   eliminating resolution gaps in the other corpora.

---

## 5. Reproduction commands

```bash
cd portgraph
python -m unittest discover -s tests            # all 42 cases pass
python portgraph.py deps <project-path> --json       # comprehensive dependency analysis
python portgraph.py deps <project-path> --json --compact   # trailing --compact (new)
python portgraph.py fetch-deps <app> --dry-run   # dependency closure classification preview
python tests/e2e/run_e2e.py run --project corpus-c --no-clone --fresh-db
# → recall=100% precision=23% bug_candidates=0 (was 4)
```
