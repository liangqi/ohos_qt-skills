# portgraph dependency analysis (deps / fetch-deps) optimization report

- Branch: `worker2-deps-opt` (commit `8d4f446`)
- Scope: `portgraph/portgraph.py`, `portgraph/port_graph/deps_report.py`,
  `portgraph/port_graph/deps_fetch.py`, `portgraph/tests/test_port_graph.py`,
  `portgraph/docs/{deps-report,fetch-deps}.md`
- Validation baseline: `python -m unittest discover -s tests` (35 → 38 cases, all passing;
  1 skip is the environment skip for a missing hb-core sparse checkout); sample project + real DB
  (1248 cmdpkgs packages, collected online with `ingest all`) running `deps` and
  `fetch-deps` end to end (dry-run / real download / idempotent rerun).

---

## 1. Current state (before optimization)

| Command | Design intent | Observed behavior |
|---|---|---|
| `deps <path\|app>` | Full dependency picture: five roles + multi-source version constraints + how to obtain artifacts | Functionally complete; but the runtime closure does O(D×(V+E)) repeated database queries, the text report's counts/grouping are misleading, libav versions use the wrong scale, and the path error is misleading |
| `fetch-deps <app>` | One-step retrieval of HarmonyOS artifacts for an app's dependency closure (direct bottle download + manifest) | Download/verification/atomic placement/idempotence are robust; but test frameworks are falsely reported as need_port |

## 2. Change list (4 improvements)

### 1. Performance: a shared graph cache for the deps report (`deps_report.py`)

- **Problem**: `analyze_dependencies` ran a separate `_runtime_closure` BFS for **each**
  link dependency, and every node went through `db.get_node`/`db.out_edges` database queries.
  A synthetic stress test (200 find_package × a 500-node deep-chain graph) measured **241,000 SQL
  queries, 1.85s**, and the profile showed `_runtime_closure` taking 89% of the time. Real-world cases
  (deep closures after the full hb ingestion) scale up linearly.
- **Change**: added `_GraphCache` (a two-level dict cache of nodes/out-edges); `_runtime_closure`
  gains a `cache` parameter so all closure BFS runs within an analysis share one cache; `_resolve` gains a resolution
  result cache (including None misses), and dynamic_loads / env_deps reuse the same cache.
- **Effect**: the same stress test takes **0.16s (about 11.6x)**, with link=200 / runtime=499 output
  identical to before; cyclic graphs and shared transitive dependencies (needed_by multi-source merging) behave the same
  (covered by new unit tests).

### 2. Accuracy: libav* version constraints no longer falsely report conflict (`deps_report.py`)

- **Problem**: after `pkg_check_modules(FF REQUIRED "libavcodec >= 58")` was merged into the ffmpeg entry via
  `LIB_NAME_ALIASES`, `>= 58` was compared directly against the ffmpeg release version
  (e.g. cmdpkgs' 8.1.1) → a false `version_check=conflict` +
  "ffmpeg version conflict: requires >= 58, HarmonyOS artifact is 7.1" warning. In fact 58 is the
  **libavcodec library major version** (58 ≈ ffmpeg 4.x), and 8.1.1 fully satisfies it.
  ffmpeg is a frequent dependency of media Qt apps, and a false conflict misleads the agent into evaluating
  "downgrade/build from source".
- **Change**: added a `LIBAV_LIB_NAMES` set; when pkg_check_modules is merged and the source name
  (lib prefix stripped) belongs to the libav family, the entry is tagged `version_req_scope=libav-major`
  with an ohos_note explaining the scale difference; `_version_check` records `unknown` for such constraints
  instead of comparing. **Version constraints from other sources (find_package minimum version, conan ranges)
  are still checked normally**.
- **Effect**: in `deps` text/JSON, ffmpeg shows `version_check=unknown` +
  the scale explanation, with no more false conflict warning; `version_req` is kept verbatim (`>= 58`).

### 3. Accuracy: fetch-deps no longer falsely reports test frameworks as need_port (`deps_fetch.py` + `portgraph.py`)

- **Problem**: the scanner also creates a runtime edge for `find_package(GTest)`, so in the fetch-deps
  closure gtest (a pkg-unknown ghost node) was classified `need_port`, printing
  "gtest needs porting yourself (source: ?)" — test frameworks don't go into the release package, so this
  misleads the agent (the deps report itself classifies it as test, so the two commands disagreed).
- **Change**: `deps_fetch` adds a `TEST_FRAMEWORKS` set; matches in the closure get
  `status=test` / `role=test` + an explanation ("test framework, not in the release package; only handle it if you need to run tests on a HarmonyOS
  device"). CLI progress output and summary ordering support the `test` status accordingly;
  the `docs/fetch-deps.md` status table gains a `test` row.
- **Effect**: fetch-deps on the demo project goes from "need_port 2" (gtest+x11) to
  "need_port 1 (x11) / test 1 (gtest)"; e2e reconciliation is unaffected (e2e reconciles using
  `out_edges` direct dependencies and doesn't look at the manifest status).

### 4. Readability / error handling (`deps_report.py` + `portgraph.py`)

- **build_tools count fix**: formerly `counts["build_tools"] =
  len(build_tools) + len(tools)` — but step 10 had already merged the build_tools entries into
  tools, **double-counting** them; and the three fixed display rows CMake minimum version / C++ standard / compiler
  weren't counted (the demo project showed "build-tool 0" yet listed 3 rows). Now it matches
  the text display: `len(tools) + CMake?1 + C++?1 + compiler 1`.
- **Grouping link dependencies**: the text report sorts `link_deps` grouped by kind
  (package → framework → system-lib → win32-system-lib →
  platform-iface), so the "real external packages" that need handling come first and system libraries/platform interfaces last.
  The order of `link_deps` in JSON is unchanged (sorted by name).
- **deps path error**: passing a nonexistent path (`/no/such/dir`) or a file used to report
  "app not found: /no/such/dir (run scan first)" — although the user clearly passed a path.
  Now path-like input (exists / contains a separator / starts with `.`) reports "project path doesn't exist or is not a
  directory… (to analyze an already-scanned app, pass the app name)"; plain app names still follow the original logic.

### New tests (`tests/test_port_graph.py`, 35 → 38 cases)

| Case | Coverage |
|---|---|
| `test_libav_version_not_false_conflict` | libav-major tag / unknown check / no conflict warning |
| `test_build_tools_count_matches_display` | Count matches tools + fixed rows (no double counting) |
| `test_runtime_closure_cache_shared` | Closure semantics with the shared cache: needed_by multi-source merging, no infinite loop on cyclic graphs |
| `test_dry_run_classification` (extended) | fetch-deps outputs status/role=test for gtest |

## 3. Before/after comparison

| Dimension | Before | After |
|---|---|---|
| deps synthetic stress test (200 deps × 500-node deep chain) | 1.85s (241,000 SQL queries) | **0.16s (~11.6x)**, identical output |
| ffmpeg (libavcodec >= 58 vs 8.1.1) | `conflict` + false conflict warning | `unknown` + scale explanation |
| fetch-deps on GTest | `need_port` ("needs porting yourself, source: ?") | `test` ("not in the release package, skipped") |
| demo project build-tool count | "0" (actually showing 3 rows) | "3", matching the display |
| link list presentation | Names interleaved (X11 sandwiched between packages) | Grouped by kind, external packages first |
| `deps /no/such/dir` | "app not found… run scan first" (misleading) | "path doesn't exist or is not a directory…" |

## 4. Remaining issues and recommendations

1. **No automatic retrieval of the hb-core data source**: `ingest harmonybrew` silently returns `files: 0`
   when `workspace/hb-core` is missing (no clone, no warning),
   so this test environment had only the single cmdpkgs source. Recommendation: mirror cmdpkgs' automatic clone +
   sparse checkout, or explicitly warn "data source directory missing" in the output.
2. **Merging different libraries with the same name can still mismatch** (known limitation): `_resolve`'s lib prefix/suffix
   rules can't handle same-name-different-meaning cases like MPC (multi-precision library vs music player), so artifact URLs still need
   manual checking before relying on them. Consider adding a
   `match=approx` tag in the deps report for entries "matched only via fuzzy rules".
3. **Dynamic loading only recognizes literals**: `QLibrary(name + ".so")` is statically invisible, so misses
   are a design limitation; recommend counting `QLibrary(` occurrences per project in warnings as a
   hint (currently only matched literals are reported).
4. **analyze semantics for test frameworks**: this round only fixed fetch-deps' presentation;
   `engine.analyze` still counts pkg-unknown:gtest among the unknowns (possibly pulling the
   verdict to uncertain). A more thorough fix would be for project_scanner to create `test` edges rather than `runtime` edges for test
   frameworks, but that changes analyze/e2e behavior, so recommend evaluating it
   separately.
5. **deps rescans everything every time**: when `cmd_deps` is given a path it rescans + re-ingests every time
   (idempotent but repetitive). A scan result cache (fingerprinted by mtime/file count) would benefit repeated calls on large
   projects.
6. **The e2e harness is not part of CI**: `tests/e2e` needs real clones of four large projects
   and wasn't run in this environment; recommend documenting its network/disk prerequisites, or periodically
   running `run_e2e.py run --all` as a regression gate in an environment with network access.

---

*Report generated by the optimization task on the worker2-deps-opt branch; all changes were committed with commit `8d4f446`
and touch only the `~/harmony-workspace/worker2` directory.*
