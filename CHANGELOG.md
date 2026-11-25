# Changelog

> Release history of the external knowledge base (developer edition). Version numbers follow [Semantic Versioning](https://semver.org/).
> The versioned object = the whole external repository bundle (the public Qt subset + the embedded ohos-common-kb + the kb-init skill + the root documents).
>
> - **MAJOR** — breaking: deleting/relocating a page users depend on, changing `audience` from public to internal, directory reshuffles that break old links, or an iron rule / API mapping being disproven and reversed
> - **MINOR** — content additions: a new page/section/API mapping entry/task type, or a newly embedded KB or skill
> - **PATCH** — content corrections: typos and wording fixes, updated error solutions, Qt reference version bumps
>
> Release process: tag `vX.Y.Z` on `trunk`, and cut a `release/vX.Y.Z` archive from that tag (see CONTRIBUTING.md).
> Each release's `RELEASE-MANIFEST.yaml` records page counts + `content_tree_sha256`, so it is reproducible.

---

## v3.0.0-rc13 — 2026-11-18

Fixes six things from the dependency layer (batch D) of the same review list: recognition coverage, download robustness, `.pc`
relocation, knowledge gaps, rule scope, and fix candidates. The core is separating "not in the knowledge base" from "names don't
match", and separating "third-party library" from "the project's own subdirectory".

### Recognition coverage (D-07)

- The `portgraph` alias table now covers `ada→ada-url`, `libudev→udev`, and same-library-different-name cases such as `pango`/`pangomm`/
  `glibmm`/`giomm`/`sigc++`/`range-v3`/`protobuf-lite`;
  `webrtc→tg_owt` is **not** normalized (that's tdesktop's proprietary naming; other projects using Google
  WebRTC would be misled), it only goes through the similar-name hint.
- Unresolved dependencies gain a "similar package" hint: `suggest_packages()` scores names in
  hb/cmdpkgs, the report says "the knowledge base has a similar package X; the name may just not match", and `unknowns` entries carry
  `name_hints`.
- The project's own names (CMake targets, directories containing build files, the `project()` name) are no longer treated as
  third-party libraries: an `external_<x>` wrapper file with **no** dependency declaration = an in-project implementation
  (tdesktop's `auto_updates`/`crash_reports`/`tde2e`/`wallet_engine`);
  the `deps` report marks it `kind=in-tree` and explains "built by this project's CMake".
- `udev`/`libudev` are classified as platform interfaces (systemd family): HarmonyOS has no udev, and a name match
  in hb doesn't mean it should be ported.

### Download robustness (D-08)

- `fetch` exit codes are three-state: all succeeded 0 / partial failure 2 / all failed 1, and it prints
  `N/M succeeded, K failed: …`; no more "partial failure, silently 0".
- `_fetch_bytes`: plain GET first; on 401/403/405 or a dropped connection it retries with `Range` resumption;
  when the server ignores Range and returns 200 it falls back to a truncating write (otherwise the file would be concatenated twice).

### pkg-config (D-09)

- New `tools/qt_ohos/pkgconfig.py` (pure Python): parses `.pc` (`${var}` expansion,
  recursive `Requires`/`Requires.private`), rewrites absolute build-machine paths to local ones
  (`prefix=/storage/<remote user>/.harmonybrew/Cellar/opus/1.6.1_1` → the local package root, idempotent),
  and generates `pkg-config` / `pkg-config.bat` stand-ins.
- New subcommand `pkgconfig`: `--relocate [DIR]` / `--dry-run` / `--write-shim [BIN]`
  / `--libdir` / `--list` / `--print-path`; other arguments are passed through with pkg-config semantics.
- `doctor` adds a pkg-config probe (a shim also counts as passing).
- Build environment integration: `build` prepends `.qt-ohos/bin` to `PATH` for both the configure and compile steps,
  and sets `PKG_CONFIG_LIBDIR` (without a shim `PATH` is left alone, to avoid pollution).

### Rule scope (D-11)

- Platform-specific **suffixes/tokens** also take part in downgrading: `foo_win.cpp`, `bar_mac.mm`,
  `xcb_window.cpp`, `core_win32.cpp` (previously only directories matched).
- Conditional-compilation block recognition: hits inside non-HarmonyOS branches such as `#ifdef Q_OS_WIN` are downgraded one level and marked
  `platform-guarded`; `#else`/`#elif` branches count again; conditions containing `Q_OS_LINUX`/`__OHOS__`
  are not excluded (both hold on HarmonyOS).

### Fix candidates (D-12)

- When no automatic fix is applicable, a **candidate list** is output: `cand-shared-lib` (the application must be SHARED),
  `cand-no-undefined`, `cand-xcb-dbus`, `cand-qt-host-tools`, `cand-rcc-write`,
  `cand-cxx20`, each with the rule number, why, how to change it, criterion, and `file:line` location;
  written to `fix_candidates` in `.qt-ohos/state.json`; the scan is read-only and doesn't modify files.

### Knowledge layer (D-10)

- New `problems/build-qt6-app-must-be-shared.md`: QAbility does `dlsym("main")` after `dlopen`,
  so the application target must be SHARED; backends that reference application-layer classes can only stay OBJECT.
- New `problems/build-qt6-no-undefined-symbols.md`: the toolchain forces
  `-Wl,--no-undefined` and `--allow-shlib-undefined` has no effect; unresolved symbols +
  GNU-hash-only objects → musl `find_sym2` SIGSEGV, with the criterion and three kinds of fix.
- New `problems/build-qt6-host-codegen-and-pango.md`: `QT_HOST_PATH` for cross-compilation,
  host `rcc` silently not writing files, pango's long dependency chain, and
  `DESKTOP_APP_USE_PANGO=OFF`.
- `problems/_lookup.md` indexes the three pages (problems 56→59); `_map`/dashboard synced.

### Tests and counts

- New regressions: `.pc` relocation/idempotency/recursive query/shim, alias families, own-directory recognition,
  file-level and block-level scope, read-only candidate list, `pkgconfig` pass-through, similar-package hint,
  two Range fallback cases. Test cases 142→154 (engine 118 + consistency 27 + scan 9),
  portgraph 127→129.

## v3.0.0-rc12 — 2026-11-18

Fixes four things from the review list of the second round of Windows testing (tdesktop 7.4.4 + Qt 6.12 kit + HAD-W32):
crash detection could miss crashes, the HAP allowlist could let half the system through, old records could pass as new results, and ELF reading could truncate.
The core of this round isn't adding features but making sure the tools **cannot** give a PASS when "it has already crashed".

- **P0 crash verdict (D-01)** `crash_check` now uses three mutually independent pieces of evidence: `pidof` at the end of the window,
  the before/after difference of the faultlogger directory over the window (file names carry timestamps; `ls` output isn't parsed), and the union of crash lines
  (this application's lines ∪ `processdump`/`DfxFaultLogger` system lines, the latter only those that mention this application).
  The old implementation filtered logs only by bundle, but OHOS system crash lines don't carry the bundle, so they were dropped wholesale → judged PASS.
- **P0 allowlist (D-02)** `hap_allowed_libs` went from being expanded character by character from a string (`"l"` let every `lib*` through) to
  unified normalization in three places: split at the verifier entry, stored as a list by `config set`, and prefixes shorter than 4 characters rejected with a hint.
- **P0 ELF parsing (D-06)** the strtab boundary now uses `DT_STRSZ`, the defensive cap goes from 1 MB → 256 MB, and on truncation
  `ElfInfo.truncated=True`. The old implementation truncated the strtab of big libraries with 320k dynsym entries, and `_cstr` read out of bounds and assembled
  garbage NEEDED entries (`libQt6Core.so Qt_6.12 C:/Users/…`), making G5 report 38 false missing libraries.
- **P0 unresolved symbols (D-05): new G13**: subtract "exported by the package ∪
  exported by the sysroot ∪ `undefined_allow` prefixes" from the strong undefined symbols of every `.so` in the HAP; what remains are the symbols that can make the process SIGSEGV in
  the `find_sym2` phase when `dlopen` runs on the board. Without `ohos_sdk_native`/sysroot it only SKIPs (never fails because it can't see),
  by default it reports PARTIAL as `advisory`, and only `config set undefined_gate strict` makes it FAIL.
- **P1 record fingerprints (D-03)** `install`/`launch` records store the HAP sha256 and device serial number, and packaging records
  `hap_fingerprint`; mismatches are marked `STALE` and counted as FAIL (not a fourth level). `verify`'s Result line states
  the verdict scope G0–G8; G9–G13 are supplementary evidence (D-13).
- **P1 CLI**: the `libcheck` subparser no longer overwrites the global `--project` with its default (D-04); `config set` supports
  list keys; `scan` records `scan_round`/`scan_config_hash`, and `status`/`verify` warn about stale scans (D-17/D-20);
  `draft --summary-file` (D-19); `doctor` looks for `mingw32-make` in the kit's `bin/` and checks the sysroot (D-16).
- **P1** G4's "unresolved DT_NEEDED" no longer warns about Qt libraries already in the HAP (D-14); `gen-dashboard.py`
  also reuses the body date when content hasn't changed, so the working tree no longer gets dirty the next day (along the way it fixes the bug where `\1` followed directly by a digit was treated as
  an octal escape, writing the title as `P26-11-16`).
- Test cases 124 → 142 (seven new regression groups: three crash evidences, allowlist normalization, record fingerprints, G13, scan rounds, `--project` propagation,
  `draft --summary-file`).

## v3.0.0-rc11 — 2026-11-16

Fixes the execution layer per the defect list from Windows testing (FinceptTerminal + Qt 6.12 prebuilt kit + SDK 6.0.2 CLI):
the criteria were right all along; what was wrong was "zero knowledge of the Qt6 prebuilt kit" — build only ran bare cmake, package was just a shell,
and the defaults for install/launch were still Qt5's.

- **P0** `build` understands the Qt6 kit: when it finds `lib/cmake/Qt6/qt.toolchain.cmake` it automatically assembles
  `CMAKE_TOOLCHAIN_FILE` / `QT_HOST_PATH` / `QT_CHAINLOAD_TOOLCHAIN_FILE` /
  `OHOS_SDK_NATIVE` / `OHOS_ARCH`, and the default generator on Windows becomes `MinGW Makefiles`; a missing
  `qt_host_sdk` / `ohos_sdk_native` FAILs immediately with the env key to fix (instead of producing a pile of CMake errors about Qt not being found)
- **P0** `package` has the two Qt6 paths built in: `cmake --build --target <app>_make_hap`, or
  `harmonydeployqt6 --input <deployment-settings> --output <harmonyos-build> --hvigor <abs>`;
  `No hvigor path specified` in the output (that warning returns 0) or hvigor/npm/EPERM diagnostics are judged FAIL
- **P0** SDK version alignment: before packaging, `compatibleSdkVersion` in `<harmonyos-build>/build-profile.json5`
  is set to the real value from `DEVECO_SDK_HOME` (the Qt6 template hardcodes `6.1.0(23)`,
  and a lower-version SDK fails right away with `00303082`), and `runtimeOS` is checked; preflight previously only scanned the Qt5-layout
  `root/entry/libs`, now it probes `package_dir` → `<build_dir>/harmonyos-build` → the root in turn
- **P0** `install` converts paths to native local form (Windows hdc given a relative `C:/…` string reports
  `Error opening file`); when the cached hap path goes stale it searches again, preferring `-signed.hap`
- **P0** `launch` reads the ability from `module.mainElement` in `module.json5` (the Qt6 template uses
  `QAbility`; the old default `EntryAbility` can never start), and FAILs printing the detected abilities if it can't read it
- **P0** G5 no longer just checks whether the HAP exists: it unpacks `libs/<abi>/*.so` and checks the `DT_NEEDED` closure;
  missing a single `libssl.so.3` reports "dependency closure broken" (imported SHARED libraries don't get into the HAP automatically;
  you have to write `QT_HARMONYOS_EXTRA_LIBS`); the allowlist goes through `hap_allowed_libs`
- **P0** new `tools/qt_ohos/elf.py` (pure Python ELF reading): G4 goes from "counting files" to asserting each one is
  `ELF64 / AArch64 / DYN`; `.a` is recognized by the `!<arch>` magic, and the wrong architecture is judged FAIL
- **MINOR** new subcommands `doctor` (environment check, runs even without `.qt-ohos/`), `sign`
  (devecocli generates signing material and checks references in `build-profile.json5`), and `smoke-interact`
  (screenshot → click → screenshot again and compare + process alive, producing `runtime["smoke_interact"]` evidence;
  G10 is still PARTIAL, the authority for the human verdict is not delegated)
- **MINOR** `assess` distinguishes required/optional modules: `OPTIONAL_COMPONENTS` and `if(TARGET Qt6::X)` guards downgrade,
  optional modules only go into `optional_modules` and don't count as blockers; `plan` is reordered to "environment self-check → SDK/hvigor/signing →
  shell project", skipping modules the kit already ships and optional ones
- **MINOR** portgraph's `modules_missing` is renamed `modules_without_kb_node` (it means "the KB has no node",
  not "the project is missing a dependency")
- **MINOR** new `_scripts/sync-counts.py`: derived numbers in README / TESTING are synced from the source of truth;
  `--check` goes into CI, and hand edits or missed edits both turn it red; `gen-dashboard.py` no longer refreshes the date stamp when content hasn't changed
  (a clean tree is no longer guaranteed red the next day)
- **FIX** a Chinese-locale Windows console crashed with `UnicodeEncodeError` on `•` → `main()` sets UTF-8 stdio uniformly
- **FIX** C7 no longer scans gitignored third-party docs (square brackets resembling
  wikilinks in the minimatch docs in the hvigor cache were treated as broken links)
- **MINOR** knowledge layer synced with testing: Qt 6.12+/6.13.0-dev only defines `Q_OS_HARMONY` (not `Q_OS_OHOS`);
  `qt6-status` / the full-flow page change their wording, and `R019` and `ohos-platform-audit` recognize `__OHOS__`;
  `problems/runtime-hap-missing-so-closure` adds the `QT_HARMONYOS_EXTRA_LIBS` variant;
  `_task-routing` adds the route [O] Qt6 end-to-end build and deployment; the Qt6 assertions in `verify-env.sh` are refined from
  "directory exists" to `libqohos.so` / `qt.toolchain.cmake` / `harmonydeployqt6`
- **MINOR** test cases 100 → 124 (Qt6 layout 5, HAP closure 6, G4 ELF 3, optional modules 5, guard 2)

---

## v3.0.0-rc10 — 2026-11-11

Wrap-up: the last hand-written derived numbers (`_index/_dashboard.md`) are now generated by a script and covered by the gates.

- **FIX** `_index/_dashboard.md` had always been hand-written: the header said "procedural (15 active)" while the table listed only 14 pages, and
  `total_pages` 48 didn't match the real 49. New `_scripts/gen-dashboard.py` re-projects it from page frontmatter,
  `problems/`, and `faults/_registry.md`; archived pages get their own section (previously they simply disappeared from the list,
  i.e. dropped out of every index)
- **MINOR** one more gate: `verify` C9 compares the dashboard with the generator output; hand-edited numbers are an ERROR;
  the AGENTS contract adds "derived views must not be edited by hand"
- **MINOR** check codes deduplicated: relative link check → C10, index reachability → C11 (C8/C9 were already taken by
  the dashboard and index consistency checks); TESTING synced
- **MINOR** test cases 99 → 100 (coverage of dashboard generation consistency and archived pages still being in the index)

---

## v3.0.0-rc9 — 2026-11-11

The externally readable layer is replaced with a polished narrative structure (using `matrix-release`'s README as the skeleton), and capabilities and facts
added on trunk are backfilled. One entry point for outsiders (README), one entry point for agents (AGENTS + `_index/`).

- **MINOR** README rewritten: keeps matrix-release's 19-section narrative (problem → architecture → capabilities → getting started →
  scenarios → directories → quality → spec → limitations → philosophy → environment → releases → contributing), adds trunk's own
  "FAQ", and removes the internal "Branch model"
- **MINOR** new capabilities backfilled: `tools/ohos-platform-audit.py` (audit of the two kinds of platform-layer dispatch), `libcheck`
  (library-level built/probed), `build/package --record-only` (registering external builds), `verify`'s three-level
  verdict and exit codes 0/3/1, the seven CLI contracts, and `qt-community-to-official` added to Skills
- **FIX** outdated facts in the skeleton corrected in one go: knowledge pages 120→132, QOH 42→44, R 18→19, problems
  47→56, iron rules 35→38, subcommands 24→25, fault graph 5→11 tracking tickets, test cases 119→99+127
- **MINOR** known limitations now mention the narrowed portgraph false-positive surface (function-like symbols require call parentheses, and
  platform-specific files are excluded by file name)

---

## v3.0.0-rc8 — 2026-11-11

A round of content review following the minimal plan "only add indexes, consolidate fact blocks" (read-only mapping first, then changes). Mapping conclusion:
comparing all 132 pages pairwise, **0 page-level duplicate pairs**; duplication occurs in fact blocks copied into multiple files.

- **MINOR** new `ohos-common-kb-public/_index.md`: index entry point for the 27 pages of the embedded platform KB.
  Previously 23 pages weren't in any index, and 15 of them weren't even reachable by links; they could only be found by searching the whole KB
- **MINOR** `_index/_map.md` completed: adds `knowledge-sedimentation` and two retrospectives
  (`qt-opensource-apps-harmonyos-survey`, `tdesktop-harmonyos-porting`),
  the problems section now points to `_lookup` as its single entry point, and an entry point for the embedded KB is added; `total_pages` corrected to the actual 52 entries
- **FIX** `_index/_agent-mesh.md` in `skills/kb-iterator/SKILL.md` was written root-relative,
  which is always broken when resolved from that directory → changed to `../../_index/_agent-mesh.md`
- **FIX** `problems/_lookup.md` was missing `runtime-icons-missing-libqico.md` (the index didn't keep up when it was merged)
- **MINOR** two new gates: C8 relative `.md` links must exist (previously only wikilinks were checked);
  C9 every knowledge page must be in at least one index (otherwise agents navigating by the map can't see it)
- **MINOR** count consolidation: numbers like `38 iron rules`/`44 QOH`/`56 real-world pitfalls` used to be scattered across
  SKILL, AGENTS, CLAUDE, `_task-routing`, and README, five places to edit by hand on every fact change
  (CI went red three times over this during this session). Now numbers live only in README + `RELEASE-MANIFEST.yaml`;
  guidance docs use wording without numbers, and the consistency tests become reverse guards
- **MINOR** test cases 95 → 99 (C8 missing links/inline code, C9 orphan pages/index hits)

---

## v3.0.0-rc6 — 2026-11-11

10 issues reported back after a real cross-compilation port on another machine: the first 4 concern gate criteria,
the rest scan evidence collection and CLI interaction. After checking each one, 8 were real (1 had a skewed diagnosis, 2 had already been fixed earlier).

- **FIX** the `PARTIAL` verdict existed in name only: the old condition required G5 ∈ (PASS, PARTIAL), but G5 never
  produces PARTIAL, so "build + link all passed, packaging not done yet" was always judged FAIL — every migration that only got as far as
  the build stage read as a failure. Now `G3 PASS and G4 PASS and G5 not failed` → PARTIAL, with an extra line after the result
  explaining "intermediate result, not deliverable"; a real G5 failure is still FAIL
- **FIX** G4 only looked at the artifact path strings in `build.json` and didn't check the disk: hand-written or stale paths could also pass.
  Now each one is stat'ed: all present → PASS, some missing → PARTIAL, all missing → FAIL
- **FIX** G2's "handled" had no evidence chain: a single `mark-risk --rule R001` could clear 437 critical
  risks, with no way to tell "really isolated" from "marked away". Now `--evidence` is required, and the record is stored in
  `state.json` (rule → evidence/note/at); legacy plain id lists are treated as "no evidence" and judged FAIL
- **FIX** the scan counted code HarmonyOS doesn't compile as critical: hits in `ThirdParty/` (such as tdesktop's
  fcitx5-qt DBus headers) and platform-specific directories (platform/win, windows/, macos/)
  are now automatically downgraded one level and marked with `scope`; rules can use `exclude` to exclude paths, and `scope: keep` turns off downgrading
- **FIX** portgraph platform evidence: file-level exclusion previously only recognized `platform/win/**`, missing `*_win.cpp`
  and `*.mm`; the win32 rule treated same-named members like `engine::SendMessage{` as API calls. Now
  platform-specific files are recognized by file name suffix, and function-like symbols require call parentheses
- **FIX** no way to register external build results: after a custom `build_ohos_k.py` cross-compiled successfully, `build`
  would only rerun it itself, forcing a hand-written `build.json` to get G3/G4 to reflect the real state (i.e. bypassing the tool with
  no evidence). New `build --record-only --artifacts <glob>` and `package --record-only --hap`
- **FIX** garbled subprocess output: `text=True` decoded UTF-8 output using the locale (Chinese Windows = cp936).
  Now it reads bytes and decodes UTF-8 first, with locale/gb18030 as the fallback
- **MINOR** `--project` written after the subcommand used to be treated as an unknown argument (or silently ignored); now both orders
  are equivalent, and a line of explanation is printed when it comes after
- **MINOR** G0's `cmake not on PATH` now comes with an executable fix (`config set cmake <absolute path>`
  or `build_command`)
- **FIX** (second-round self-review) `--json` stdout wasn't pure JSON: the human-readable gate table/risk report/argument
  notes all went to stdout, so `json.load` on the machine side failed outright. With `--json`, human output now goes to stderr
- **MINOR** exit codes used to be only 0/1; once PARTIAL became reachable it needed its own meaning: `0` PASS / `3` PARTIAL /
  `1` FAIL, documented in `verify --help`, TESTING, and SKILL
- **FIX** (second-round self-review) a corrupted state file crashed the whole command with `JSONDecodeError`: interrupted runs leave behind
  half-written `build.json`/`scan.json`, and previously every subcommand just threw a stack trace. Now it's treated as "this evidence doesn't exist"
  with a warning (the gates only get more conservative), and if `state.json` is corrupted, rebuild steps are given
- **FIX** (second-round self-review) scope downgrading also counted `vendor/`, `external/`, and `contrib/` as third-party —
  those directories are often really compiled in other projects (AOSP's `external/` is), and automatic downgrading would miss
  real risks that blow up. The list is narrowed to `ThirdParty/`, `third_party/`, `3rdparty/`; to exclude other directories, declare them
  explicitly with `match.exclude`
- **MINOR** `files`/`guard` hits also go through scope judgment, with consistent semantics
- **MINOR** test cases 75 → 94 (three-level verdict, G4 artifacts, G2 evidence, scope downgrading, registered builds,
  argument position, corrupted state), portgraph 123 → 127 (suffix exclusion, win32 precision)

---

## v3.0.0-rc5 — 2026-11-04

Lands the handoff list from real-device testing of telegramdesktop (`tdesktop-trunk-handoff-20261104`) into trunk item by item:
first fix the tool criteria that "would read untested as passed", then add the knowledge this disproved/confirmed.

- **FIX** `_scripts/ci.py` crashed on Chinese-locale Windows: subprocess output decoded as GBK threw
  `UnicodeDecodeError` on UTF-8 bytes (the stack landed in `subprocess._readerthread`, looking nothing like an encoding problem). Now three places change together:
  this process's stdio forced to UTF-8, the subprocess environment carrying `PYTHONUTF8=1`/`PYTHONIOENCODING=utf-8`, and output decoded with
  `errors="replace"`
- **FIX** the G8 crash gate could give a false PASS (the most serious one): the old implementation just ran a device-wide `hilog` and judged PASS,
  so when install/launch failed it amounted to "it didn't run, so it didn't crash". Now `crash_check` first looks at the upstream
  install/launch status, and anything other than PASS goes straight to SKIP with the reason stated; logs are filtered by `bundle_name`,
  and if not a single line belongs to this application after filtering it's judged NOT_RUN (empty evidence ≠ no crash); `smoke` distinguishes "not tested (exit 2)"
  from "crashed (exit 1)"
- **FIX** the hygiene check only looks at files that would be committed: the gitignored local `workspace/` build tree and
  `ENV.local.md` had produced 134 H2 noise entries (drowning out real errors). Now it filters by `git ls-files`,
  keeping an `--include-ignored` escape hatch
- **FIX** `draft` used to write into the gitignored `drafts/`, so knowledge captured following the documented process could never reach trunk;
  it now writes `faults/_drafts/` (a tracked directory), with docs and tests synced
- **FIX** configuration changes no longer depend on someone remembering `--force`: `config set` automatically invalidates env_check/project_scan/
  qt_scan/risk_scan/dependency_scan
- **FIX** `portgraph deps` didn't honor `config set qt_version`: it now reads `.qt-ohos/env.json` first,
  so Qt 6 projects are no longer printed as `Qt: 5`
- **FIX** three overly broad `analyze-log` patterns caused misdiagnoses: `QOH020`'s `No such file or directory`
  (missing nmake taken as missing libuuid), `QOH023`'s `undefined symbol`, and `QOH019`'s
  `file not found` are all narrowed to patterns with context; `QOH001` adds `Unknown platform type`
- **MINOR** new `tools/ohos-platform-audit.py`: classifies the two kinds of platform-layer dispatch (in-header `#ifdef` / build-time per-path
  `.cpp` selection) + asserts that header-dispatch files name both `Q_OS_OHOS` and `Q_OS_HARMONY`;
  `--undefined link.log` infers platform symbols still missing an implementation (symcheck)
- **MINOR** new `qt-ohos-run libcheck <lib> --level built|probed`: a library-level intermediate gate;
  `probed` must carry device evidence; the G4 details show "n built / m probed", so intermediate porting results are no longer swallowed by a whole-package failure
- **MINOR** pre-packaging checks: versioned `.so` files in `entry/libs/*/` (the loader can't find them by soname),
  non-`.so` files, and `compatibleSdkVersion` in `build-profile.json5` disagreeing with `env.json`'s
  `compatible_sdk` are all caught before packaging
- **MINOR** machine layer: new `QOH043` (single-macro platform guard, dead code on a Qt 6 kit), `QOH044`
  (host compiler without `--target` making `Q_OS_WIN` take effect, so "it builds" is false evidence), and `R019`
  (`guard` matcher: files matching the glob must contain both OHOS macros); the rule engine supports
  `match.guard`; `QOH042 → QOH043/044`, `R018 → R019`
- **MINOR** knowledge layer expanded: iron rules §6 grows from 2 to 5 rules (dual-macro guard, two kinds of dispatch, `-DQ_OS_OHOS`
  is a false fix) and adds "4 failure points of the platform model's else-means-Linux"; `porting-workflow` adds
  "prerequisite checklist for out-of-tree consumption of the app layer" (5 prerequisites + 2 traps); `third-party-libs` adds the local signing chain;
  `modules` adds measured platform macros for Qt 6.12+/6.13.0-dev
- **MINOR** corrected two overstatements in retrospectives: the `inline` in `specific_ohos.h` doesn't "have to be removed"
  (unreferenced TUs don't emit the symbol anyway; check with `llvm-nm` first, then change); the tray is a member variable, and
  `TrayIconSupported()` can't prevent construction, so it must get a complete no-op surface
- **MINOR** 8 new problems pages (platform dual macro, two kinds of dispatch, out-of-tree app-layer prerequisites, CMake `-include`
  deduplication, same-name header self-reference, appspawn `/proc/self/exe`, the tray must exist, local signing chain);
  knowledge pages 124 → 132, QOH 42 → 44, R 18 → 19, problems 48 → 56, iron rules 35 → 38
- **FIX** adversarial review caught three more false PASSes of the same kind: `G2` printed "no critical
  risks detected" and judged PASS when no risk scan had run at all (reading empty evidence as passing), now NOT_RUN; `G5` still judged PASS when the packaging command claimed PASS but
  no `.hap` could be found, now FAIL; `G8` without `bundle_name` configured captured the device-wide buffer,
  where other processes' crashes could mix in or mask its own, so such evidence can be at most PARTIAL
- **FIX** `gen-manifest.py` took the file list only from `git ls-files --cached`: newly written pages weren't in the digest before `git add`,
  so **the page count was right but the digest was missing pages** — and "reconcilable" rests entirely on the digest. Now `--cached
  --others --exclude-standard`
- **FIX** the help for `ohos-platform-audit.py --strict` said "source-dispatch files must have an ohos/ counterpart",
  but it actually only checked whether an `ohos/` directory existed; now it asserts for each source-dispatch header that its core name can be found in `ohos/`, exiting 1 if missing
- **FIX** when the pre-packaging check blocked, the record was written as SKIP ("not tested"), contradicting `build.json`'s FAIL;
  new `state.fail_cmd()`, meaning "tested and failed"
- **FIX** a versioned `.so` was still flagged when a same-named `libfoo.so` already existed next to it (the soname is actually satisfied) → allowed
- **FIX** the `migrate` chain collapsed smoke's "not tested" and "crashed" into exit code 1, inconsistent with the `smoke` subcommand's
  0/1/2 → not tested goes to 2
- **FIX** `faults-build review` kept listing drafts that remain after promote as "pending review" (after the move to `faults/_drafts/`
  such files keep accumulating) → skip `status: promoted`
- **FIX** (second review round, only exposed by running a synthetic project the way a real device would) `ohos-platform-audit.py`'s dispatch verdict
  required "at least two different Q_OS_ macros" to count as header dispatch, so **files with only one macro — exactly the kind it was meant to catch —
  were judged source dispatch with an overall PASS**; the tool had effectively been idling for a round. The criterion becomes "Q_OS_ conditional compilation
  appears, or a platform-subdirectory implementation is included, means header dispatch", and `no_ohos_branch` is added (there is a chain but OHOS isn't mentioned at all;
  suggests adding a branch rather than a macro); 4 classification regressions added
- **FIX** `crash_check` filtered logs only by the full bundle name: Qt application logs often only contain the process name,
  so "not a single line belongs to this application after filtering" → misjudged as NOT_RUN. Now it matches on both bundle + `process_name`
  (defaulting to the last segment of the bundle), and if there's still no hit it loosens once by each bundle segment before judging not tested
- **FIX** `analyze-log` had zero hits and gave no direction for `undefined symbol` logs: it now points to
  `ohos-platform-audit --undefined` (symbol names vary endlessly; they shouldn't be stuffed into fixed patterns in the first place)
- **FIX** the migration chain lacked short-circuiting: after a compile failure it kept calling hvigor → hdc → aa start, producing a string of
  knock-on failures, with "not tested" and "tested and failed" mixed together in the report. Now when upstream compile/package hasn't passed,
  later device stages are recorded as SKIP (`upstream:compile`) and no longer invoked, so a single command in the repository shows
  which step is really stuck
- **FIX** the pre-packaging check only recognized the string form `"compatibleSdkVersion": "5.0.5(17)"`: new projects
  write the plain API number `"compatibleSdkVersion": 17`, the regex didn't match → the consistency check silently didn't run.
  Both forms are now read and normalized when compared (full-width parentheses, `5.0.5(17)` vs `17`)
- **FIX** `scan` **exited silently** when all stages were complete: changing code and running `scan` again looked like a rescan,
  but not a single stage actually ran. Now it says explicitly "not rescanned this time (last run time)" and offers
  the two entry points `--force` / `config set`
- **MINOR** `G10` details note `manual record`, so when reading a report you can tell "tested by machine" from "declared by a human";
  rule hits give line numbers (previously `file:0`)
- **MINOR** the keys of `.qt-ohos/env.json` used to be scattered only in code (`bundle_name`, `compatible_sdk`,
  `hap_glob`, `crash_wait_sec`, etc.); `skills/qt-app-porting/SKILL.md` adds a complete key table
- **MINOR** test cases 48 → 70 (guard matching, G8 SKIP propagation, pre-packaging checks, 8 gate-honesty cases,
  digest covering untracked files, 4 platform dispatch classification cases, 3 crash filter cases, scan idempotency hint, 2 SDK version comparison cases), CLI smoke 6 → 7

---

## v3.0.0-rc3 — 2026-11-02

Adversarial review before real-device testing (running the full flow against a real Qt6 project such as telegramdesktop as a target) fixed 6 kinds of problems that would mislead judgment.

- **FIX** Qt major version detection: it previously only recognized the literal `find_package(Qt6`, while real projects often put the Qt configuration in a submodule `*.cmake` (tdesktop's is in `cmake/external/qt/package.cmake`). When the old logic "found modules but no version" it **simply assumed Qt5**, so Qt6 projects were assessed against the 5.15 module matrix and `assess` gave the wrong target version. Now it detects by strength of evidence (`find_package(Qt6` > `Qt6::` targets > `find_package(QT NAMES Qt6)` > `QT_VERSION_MAJOR` > Qt6-only CMake commands), and when it can't tell it **no longer guesses**: `scan` shows `qt: undetermined` with a warning, `assess` explicitly states "assessed assuming 5.15", and you can correct it with `config set qt_version 6`
- **FIX** `.cmake` files are included in detection: previously only `CMakeLists.txt` was scanned, so `find_package(Qt...)` in submodules (Qt's official wizard, desktop-app cmake_helpers, and the like) was all missed
- **FIX** CLI arguments unified: `init`/`scan`/`migrate`/`assess`/`recipes` previously only took positional arguments, and `--project <dir> init` errored out (while TESTING documented exactly that form). Now both forms are equivalent; `recipes` was more subtle — in `--project X recipes` the positional argument's default overwrote `--project` with `None`, silently returning "no similar cases found"
- **FIX** state directories created by mistake: `init`/`scan`/`migrate`/`assess` without a project directory now exit with an explicit error (code 2) instead of creating `.qt-ohos/` in the current directory by default
- **FIX** similar-case scoring normalized: the old formula didn't divide by the number of project features, so a single `cmake` could reach 1.00, putting clearly unrelated retrospectives first (tdesktop was once "matched" to Coin3D at 1.00). Now normalized to 0..1, with a `match:` basis line in the output
- **MINOR** new `_scripts/ci.py`: a pure-Python implementation of the four gates, so one command runs them all even on Windows without bash; `_scripts/ci.sh` becomes a thin wrapper. Gate commands in AGENTS/CONTRIBUTING/TESTING/README synced to `python _scripts/ci.py`
- **MINOR** `TESTING.md` adds a Windows pre-check (`core.longpaths`, recursive clone of submodules, paths with spaces/Chinese characters) and a tdesktop measured baseline table (6920 files / 3298 sources / 12.3-second scan / UNCERTAIN verdict / the main effort is cross-compiling third-party libraries such as ffmpeg and 161 places of win32-specific code)
- **MINOR** branch content re-review filled gaps (re-examined after the question "has all the knowledge from other branches made it into trunk"): `sync/sync-2026-09-11`
  is 66 commits newer than `main`; previously only the ancestry was registered via `-s ours`, without a file-by-file content comparison, missing 2 files —
  added `episodic/postmortems/tdesktop-harmonyos-porting.md` (full HarmonyOS port retrospective of tdesktop v7.0.2:
  59 bottles + 9 built from source, 2088 targets adapted, 550MB HAP, IME reset fix) and
  `problems/runtime-icons-missing-libqico.md` (.ico icons not shown: missing `imageformats/libqico.so`;
  when retrieved, that page's frontmatter lacked the closing `---`, now fixed); knowledge pages 122 → 124
- **MINOR** restored three doc sections lost in rewrites: `SKILL.md` "Prerequisites" (previously `§Prerequisites` was a dangling anchor),
  `CONTRIBUTING.md` "Feedback process" (Issue template table + `SECURITY.md` entry point), and `README.md` "FAQ"
  (success criterion / how to judge portability / whether a commercial license is needed / CEF as the WebEngine replacement) and "What to install locally"
- **MINOR** `LINEAGE.md` records the re-review conclusions: the two old pages from `sync/*` were already merged into the embedded common KB, `main`'s 139 template
  build artifacts, and `release/v2.1.0`'s copy of the old `skills/skills/` layout, each with the reason for not merging and where the capability lives
- **MINOR** doc corrections: the draft entry point in `_templates/draft.md` changed to trunk's `faults/_drafts/` + notes on the three kinds of entry point; `team/CONTRIBUTORS.md` no longer points to the no-longer-existing `_scripts/kb-init.py`; test count 41→48 (engine 12→19)

---

## v3.0.0 — 2026-10-31

The first `trunk` mainline release: formed by merging `main` (v2.2.1 content baseline) + `bitfun-release` (execution layer / machine layer / fault graph / templates),
and completed with the repository contract, gates, and branch model. **The old branches `main` and `bitfun-release` are frozen.**

- **BREAKING** repository positioning changed: from "Qt porting reference knowledge base" to "Qt → HarmonyOS porting engineering repo" (knowledge layer + machine layer + execution layer + governance layer). README / SKILL.md / AGENTS.md all rewritten; README organized as architecture-capabilities-getting started-skills-CLI-directories-branches-quality-spec-limitations-philosophy-releases; root `SKILL.md` changed to the standard Agent Skill form (frontmatter `name/description/metadata` + `## Instructions` in 12 steps)
- **BREAKING** branch model changed to three tiers: `trunk` (mainline/stable, only accepts merges from development branches) / `dev/<topic>` (development, accepts PRs) / `release/vX.Y.Z` (archive); `CONTRIBUTING.md` rewritten, making clear that "this repository has changed from a read-only derived view to a mainline development repo, and the upstream rebuild pipeline must be disabled to avoid overwriting merged work"
- **NEW** repository contract and self-check gates: `kb.yaml` (schema v1: entry points/map/self-check commands/required paths per layer/optional paths) + `_scripts/verify.sh` + `_scripts/verify.py` (zero dependencies, 9 kinds of check: contract completeness, required paths, AGENTS==CLAUDE, required frontmatter fields on content pages, unique ids, audience public only, resolvable wikilinks, dashboard counts, hygiene of artifact directories and local absolute paths)
- **FIX** 5 kinds of structural defects detected by the gates and fixed after the merge: ① the frontmatter of 3 pages had been mangled by a formatter into `***` fences + escaped square brackets (normalized comparison confirmed bitfun's substantive changes to those 3 pages were 0 and introduced a `<URL）→>` broken link; reverted to the main version); ② `semantic/qt-harmonyos-blocking-taxonomy.md` lacked `audience`; ③ `problems/runtime-harmonydeployqt-deploy-gaps.md` lacked `id/type/domain/status/severity/audience`; ④ 3 real personal paths `/Users/<name>/` → `<YOUR_HOME>` (verify exempts placeholders such as `you`/`currentUser`); ⑤ the frontmatter `name` in `skills/qt-community-to-official/SKILL.md` didn't match the directory name (`-cn` suffix)
- **FIX** restored two pieces of silently deleted content: `CLAUDE.md` (now enforced by verify to be verbatim identical to AGENTS.md, so Claude Code users don't have to copy it by hand) and `episodic/postmortems/qt-opensource-apps-harmonyos-survey.md` (a survey of 229 applications, the only ecosystem data, sanitized with `<INTERNAL_OUTPUT>` placeholders)
- **PATCH** consistency test fixes: `_candidates` adds repository-root-relative candidates (root files such as `kb.yaml` and `ENV.md` previously couldn't be resolved); `_dashboard` counts aligned with the restored page set (episodic 6→7, total 46→47)
- **MINOR** the following are the execution-layer/machine-layer/tracking-layer capabilities merged in from bitfun-release in this round (the unreleased content of the former v2.3.0)

- **MINOR** new execution layer (Execution Plane): the unified `tools/qt-ohos-run.py` CLI + the `tools/qt_ohos/` engine (pure standard library), turning migration knowledge into an executable, resumable, verifiable, knowledge-capturing engineering closed loop
  - `scan`: project recognition + Qt capability scan + third-party dependency scan + risk report from the 18 machine rules in `knowledge/rules/`
  - `analyze-log`: automatic diagnosis with the 41 QOH error patterns in `knowledge/errors/` (one-to-one with `problems/`; 36 existing + 5 captured from building from source on Linux, see below)
  - State machine + checkpoint/resume: `.qt-ohos/` in the target project (state/scan/plan/changes/logs/patches)
  - Verification Gate G0-G12 (`verify`): success is decided by tools; TIMEOUT is never PASS
  - Source tracking: allowlisted automatic fixes (B9 `:!ohos` scope, B10 AUTORCC) + patches persisted/rollback-able
  - Knowledge distillation: `draft` / `promote`; `recipes` searches episodic for similar migration cases
  - Task budget: `QT_OHOS_TASK_BUDGET_SEC` / `QT_OHOS_TASK_DEADLINE`
- **MINOR** new `skills/qt-app-porting/` skill + task routing code [P]; `templates/qt-ohos-app/` CMake glue template (embedding iron rules B1/B2/B10)
- **MINOR** new `tests/` (engine self-tests: YAML parsing, rule matching, error matching, state machine, CLI smoke)
- **MINOR** new fault library `faults/` (four-entity graph model: symptom S × root cause C × workaround W × tracking ticket T) — source of truth `faults/_data/*.yaml` (S/W/T records + causes/targets/tracks edges) + `C-*.md` root-cause pages (frontmatter + depends_on edges); `tools/faults-build.py` implements automatic evolution (`build` rebuilds the derived artifacts `_graph.yaml` machine-readable full graph + `_registry.md` registry table; `check` consistency gate: IDs/enums/edges/dates/refs/limitation evidence; `review` scans for due re-reviews + status progression lint); root-cause classification: defect (will be fixed) vs limitation (platform limitation → alternative), W includes verification and retirement conditions, T carries QTBUG/Huawei ticket numbers and fix_version; seeded with 8 root causes (5 defect + 2 limitation + 1 undetermined) + 7 symptoms + 6 workarounds + 4 tracking tickets (migrated from existing problems/episodic/semantic knowledge); task routing adds [R] fault tracking
- **MINOR** the fault library adds a collaborative submission and merge flow: `faults/_drafts/` (`_template.md` contributor submission checklist — verbatim symptom/environment trio/reproduction demo, required for defects, an official documentation link instead for limitations/duplicate-check statement) + a six-step editor-in-chief merge gate (duplicate check → **reproduction demo must be run**, not merged if not reproduced → human verification of evidence chain/classification/layer attribution/facts/sanitization → reproduction trail recorded in the C page's verification record → promote split merge → build gate); draft state machine draft/in-review/returned/rejected; the `review` subcommand lists drafts pending review
- **MINOR** the fault library adds an evidence standard for confirming problems and principles for writing reproduction demos: C pages must have `evidence_type` (demo reproduction project / logs debug log + stack / both / source file:line, only for statically decidable items / docs, limitation only), machine-enforced by `check` — a defect may not be classified on docs alone, a Qt-framework-side defect with only source gets a WARN (add dynamic evidence before filing upstream), and **defect/undetermined items with an open upstream ticket (qt-bug/ohos-issue/partner) must have demo/logs/both** (aligned with the HARD reproducibility gate of `qt-bug-report-generation`); seven principles for writing reproduction demos (minimal/self-contained and buildable/deterministic/comparative/pure root cause/carries diagnostic output/version trail) and a no-demo degraded path (logs + stack + the trio describing the capture environment); **hard requirement for Qt-framework-side demos: the reproduction logic is concentrated in a single main.cpp (the ohos project is only a glue shell) + reproduction steps numbered down to the operation level (no steps = not done)**
- **MINOR** the fault library adds a **disposition classification** derived view (automatically computed by `faults-build.py` from nature×responsible, not in the source of truth): must adapt for HarmonyOS (limitation) / Qt problem (defect + qt side) / system problem (defect + ohos side) / application usage problem (responsible=app, with the accompanying relaxation that allows thin C pages) / third-party library problem / pending classification; the registry adds §by disposition, and `_graph.yaml` adds a disposition field
- **MINOR** fault library **historical problem import batch 1** (10 problems, analyzed by 3 parallel sub-agents + reviewed and merged by the editor-in-chief): QDialog blockedByModal (C-0009 + patch), @ohos.deviceInfo bare-eval template crash (C-0010), mainthread Q_ASSERT (C-0011, undetermined), dlopen writable path (C-0012 + QTBUG-146624), sandbox read-only write crash (C-0013), cross-screen flicker (C-0014), hvigor CLI/IDE packaging divergence (C-0015, undetermined), QFileDialog wrongly added guard (C-0016, first application usage problem), curl Chinese mojibake (C-0017), ZINK RGBA8 mipmap black textures (C-0018, first third-party library problem); graph scale S 7→17 / C 8→18 / W 6→15 / T 4→5, refs backfilled in 14 source pages
- **MINOR** the fault library adds **chain completeness (closed-loop rules)**: a defect's (external responsibility) "workaround" must have both an adopted workaround (W adopted) and an open tracking ticket (T) — missing either means not closed (missing-ticket/missing-workaround/both-missing; `faults-build.py` derives `chain_state`/`gaps`); limitations and application issues must have an adopted workaround; **gaps propagate upward** (an S's claim of resolution is constrained by the causes aggregate: S=resolved while the chain has gaps → ERROR, S=mitigated with no adopted W → ERROR, C=workaround not closed → WARN); `_registry.md` adds §not-closed list (grouped by missing ticket/missing workaround/both missing) + a closed-loop column in the symptom index + a "chain closed" statistics row, `_graph.yaml` S/C nodes gain chain_state/gaps, and `review` adds a "not closed (to complete)" section; data fix: W-0004 targets extended to C-0005 + C-0006 (switching build combinations works around both root causes at once)
- **MINOR** qt-sdk-forge **full Linux pipeline support + measured verification** (Ubuntu 22.04 x86_64: Qt 5.12.12 GLES release + OpenHarmony SDK 6.1.0.35 → SV0-SV6/SV8 PASS, 2026-09-19). Captured from one complete Linux build in practice; all five pitfalls turned into machine-level prevention (caught before the error happens):
  - **QOH037 source snapshot defects**: the initial import of the GitCode open-source mirror lost all executable bits (620 shebang scripts), the `main`/`5.12.12` snapshots have CRLF, and there are no `tqtc/*` commercial branch names — `src-clone --method opensource` now checks out the POSIX build branch `build/macos-arm64-qt5.12.12` by default (new `OPENSOURCE_BRANCHES` mapping + `--branch` override), automatically restores executable bits after cloning and persists them with a git commit, and rejects CRLF trees outright
  - **QOH038 missing python alias**: qtdeclarative calls `python` while Linux only has `python3` — `build_env()` automatically creates `.qtsdk/pyshim/python` (without polluting the host); SV0 adds `python3`/`python_alias` checks
  - **QOH039 QtDBus fails to build**: clang 15's `-Wdeprecated-copy` × the mkspec's `-Werror`; and the HarmonyOS runtime has no DBus (QOH002) — the CLI's configure builds in `-no-dbus` (aligned with the official prebuilt and the semantic page)
  - **QOH040 dirty build directory (the fourth incremental pitfall)**: after changing configuration/switching SDK, a leftover `qt_lib_dbus.pri` makes `qtHaveModule(dbus)` falsely true and the ibus plugin gets built as usual — configure adds fingerprint protection (configure arguments + OHOS SDK version fingerprint), automatically cleaning the build directory on change
  - **QOH041 SDK API too old**: the qarkui QPA takes ArkUI NDK symbol addresses at compile time and needs apiVersion ≥ 23 (OpenHarmony ≥ 6.1; the official build uses API 24) — `build-matrix.md` adds §2.1 "Obtaining the OHOS SDK on Linux": the URL pattern of the OpenHarmony public mirror, a version selection table, unpack-and-register steps, and low-memory jobs advice
  - Accompanying: 5 new `problems/` pages (sources of fact), `knowledge/errors/` 36→41 entries, `_lookup.md` rebuilt, kb-init `qt-src-acquisition.md` corrects the open-source branch notes (same root cause as QOH037)
- **PATCH** qt-sdk-forge CLI fixes: the `env` subcommand now honors `config set qt_src/ohos_sdk_native` (it used to read only ENV.local.md, so the configuration was apparently ineffective); the `building.py` configure failure path crashed with `key` unassigned; 7 wrong `run_git()` call signatures (releasing/srctree/patching; `release`/`upstream-check` always crashed); `-no-dbus` added to the built-in configure arguments
- **MINOR** new multi-agent collaboration protocol `_index/_agent-mesh.md` (single source of truth): the knowledge base is split into interface cards for 7 core + 2 optional agents (trigger/CLI/gates/state plane/inbound and outbound deliverables; port-assessor / framework-analyst / test-verifier are defined by their interface cards); new **Task Ledger plane** (`workspace/tasks/`, gitignored) — `task.yaml` task ledger + `flow.jsonl` flow log (seven kinds of fixed write points: task-created / handoff-in·out / gate / anomaly / budget-exhausted / human-required / draft-produced / task-closed; append-only, each entry with refs) + `ho-*.yaml` handover envelopes (generalizing the qt-sdk-forge inbox protocol, 8 types); three task chains (porting / problem / evolution); **three-level classification of human touchpoints** (H1 blocking decision / H2 human execution / H3 review and confirmation), specified per agent + 5 general red lines (credentials·accounts·payments·external submissions always human; publishing·deletion·ENV switching need confirmation; gate semantics must not be upgraded; no classification without evidence; human-required must leave a trail); the concurrency contract reuses `.qtsdk/` file locks + atomic replacement. Accompanying new `skills/task-dispatcher/` (dispatch hub: file → route → monitor → close and hand over) and `skills/kb-iterator/` (engineering iteration editor-in-chief: merge gate / index regeneration / kb-verify fact checking / flow.jsonl retrospective distillation / evolution re-review — the single write gateway to the source of truth); the qt-app-porting and qt-sdk-forge SKILL.md files add an "Interfaces and human touchpoints" section; registered in the AGENTS skills table and hooked into _task-routing
- **PATCH** release branch trimming (bitfun-release): `CLAUDE.md` removed from version control (`AGENTS.md` with the same content stays as the checked-in source of truth and can be copied locally; the multi-tool tables in README/AGENTS corrected accordingly); the `HANDOVER.md` handover document and internal working drafts are not checked in (.gitignore prevents regression); internal dispatch platform IDs in `_agent-mesh.md` §8 sanitized (protocol and orchestration semantics kept)
- **MINOR** new root-level `SKILL.md`: the main entry point that turns the knowledge base into a skill — the frontmatter trigger words cover scenarios such as "port to HarmonyOS/port Qt/third-party dependency analysis/build errors" (loaded automatically when porting a Qt application to HarmonyOS), and the body fixes the main workflow (Step 0 portgraph feasibility assessment and dependency closure → qt-ohos-run pipeline → G0-G12 gates), third-party dependency analysis and download (deps role classification + one-step fetch/fetch-deps bottle retrieval), knowledge lookup entry points, and discipline red lines
- **PATCH** README fully rewritten and aligned with the actual knowledge base (multi-way consistency checks): task routes 13→15 types (adding [S] SDK engineering), QOH error patterns 36→41, API mappings 12→13 categories, directory tree adds knowledge/tools/portgraph/templates/tests/.gitcode and 5 skills, Skills table completed (SKILL.md main entry + qt-sdk-forge/task-dispatcher/kb-iterator + the portgraph repository tool), references to `_scripts/kb-dev-edition.sh` that no longer work externally removed; structure reworked per open-source best practices (badge row + core capabilities table + 30-second start + AI integration matrix + collapsed CLI subcommand list + FAQ + known limitations + version v2.3.0)
- **MINOR** new knowledge base consistency self-test `tests/test_kb_consistency.py` (20 cases, pure standard library, run together with the engine tests by `python -m unittest discover -s tests -v`): **L1** Skill manifest conventions (frontmatter name/description of the root + 5 child SKILL.md files, completeness of the AGENTS skills table); **L2** documented count consistency — documented claims == actual values (QOH 41 / R rules 18 / iron rules 35 / task routes 15 / API mappings 13 / problems 46 / faults graph 17-18-15-5 / test case count), so number drift is caught before commit (keep numbers real); **L3** cross-reference integrity (QOH refs → problems pages, resolution of inline paths in README/SKILL/AGENTS/_task-routing — supporting the `qt-`/`qt-harmonyos-`/`qt-ohos-` shorthand prefix convention, README relative links and anchors); **L4** CLI contract (subcommand sets of qt-ohos-run 24 / qt-sdk-run 24 / portgraph 10; adding or removing commands requires explicitly updating the test); **L5** faults-build check integration gate (exit 0 = zero ERRORs)
- **PATCH** the consistency tests, as soon as they landed, fixed a batch of same-origin outdated items and convention defects: AGENTS.md (36→41 QOH, removed the dead `_scripts/kb-dev-edition.sh` reference, H1 title CLAUDE.md→AGENTS.md); _task-routing.md ([H] ~36→145+ APIs, "33 iron rules"→35, B1-B11→B1-B12, W1-W5→W1-W6, "36 error patterns"→41, decision tree adds the [P] automated migration entry); portgraph/README.md (interface allowlist 19→22, unit tests 35→119); _dashboard.md (semantic 24→26 adding the blocking-taxonomy/dev-guide pages, problems 41→46, total active 47→48); skills/qt-app-porting/SKILL.md frontmatter normalized (`***`/long-dash fences→`---`, description body indented), long-dash closing fences in kb-iterator and task-dispatcher→`---`; the portgraph tests drop 1 dead case shadowed by a same-named one (test_build_tools_count_matches_display, 120 defined→119 actually run); README [N] route adds the ohos-common-kb-public/ prefix to deveco-mcp-capabilities, unit test count 120→119
- **PATCH** application names sanitized from the knowledge base (content policy: the knowledge base doesn't carry HarmonyOS porting information about specific applications, to keep agents from anchoring on specific cases and taking shortcuts): deleted 2 episodic application retrospective pages (a full port retrospective of an IM client, the 229-application survey page), keeping the distilled general lessons — "multiple changes to the same file must be serialized" goes into the pitfalls section of qt-app-harmonyos-migration, bottle-gap mirror sources/static-to-shared tricks into third-party-libs §3.4, statistics on the three big blocking modules (D-Bus/QtMultimedia/QtWebEngine) into the modules quick lookup; empirical references in the routing/protocol/procedural layers changed to "a large application"-style wording with internal collaboration process details removed; evidential mentions in problems/semantic generalized (batch build lists, reference implementations, etc.); portgraph doc examples switched to a fictional sample-app (the real URLs in the e2e corpus.json test infrastructure are exempt; third-party library names such as SARibbon/Coin3D kept as knowledge per the [M] route); the title of fault source-of-truth W-0008 sanitized accordingly and derived artifacts rebuilt (build OK / check 0 ERROR). Count knock-on: episodic 8→6, total active 48→46. Note: older commits on the remote still contain application names; public history was not rewritten
- **FIX** devecocli tool availability pre-check (empirical evidence from clean-environment testing: the agent couldn't locate devecocli in one go). Root cause: three docs said three different things, none of them true — kb-init claimed "DevEco Studio ships it at `<DEVECO>/tools/devecocli`" (doesn't exist in practice), usage-rules said to install `@deveco-test/deveco-cli` (a test channel), deveco-install said to install `deveco-cli` (the bare package name doesn't exist on npm); the actual source is the npm package `@deveco/deveco-cli` (binary `devecocli`, available on PATH). Fixes: ① deveco-cli-usage-rules adds a "tool availability pre-check (must do before starting work)" — a four-level lookup order (ENV.local.md `DEVECO_CLI` → PATH → npm global → DevEco bundled) + `--version` verification + stop-and-report on failure discipline; ② detect-env.sh lookup priority changed to PATH → npm global → bundled fallback, adds `DEVECO_CLI_VERSION` output, and OSS detection changed to probing the npm package; ③ generate-env-local.sh adds a `--deveco-cli` argument that writes the `DEVECO_CLI` variable; ④ package and binary names corrected throughout install-deveco-cli.sh / install-deps-harmonyos.sh (`npm i -g @deveco/deveco-cli`); ⑤ the kb-init SKILL check section and troubleshooting table rewritten (commands for both shells); ⑥ env-variables/deveco-install add the `DEVECO_CLI` variable and a "common misconceptions" table; ⑦ the root SKILL.md discipline red lines and AGENTS.md execution discipline add a "tool availability pre-check" item. Along the way: NeoHtop/open-pencil application names in usage-rules generalized (filling a gap in the sanitization policy)
- **NEW** `tools/cpp20-gap-scan.py` — **pre-build check and mechanical fixing** of C++20 gaps in OHOS clang15/libc++15 (driven by clean-environment testing: a full build of a large project takes tens of minutes per round, so iterating "hit error → locate → fix" round by round is expensive; a pre-check finds all hits at once). 8 rules aligned with problems/build-clang15-libcpp15-cpp20-gaps.md: GAP-01 lambda capture of structured bindings (P1091) / GAP-02 make_unique_for_overwrite (the only automatically fixed item, idempotent) / GAP-03 stop_token·jthread / GAP-04 atomic_ref / GAP-05 std::ranges / GAP-06 defaulted `<=>` containing shared_ptr / GAP-07 pure init-capture lambdas / GAP-08 pthread_setaffinity_np; P0634·P0960·construct_at·variant best_match can only be found at compile time, and the docs note they're out of scan scope. scan mode is CI-friendly (exit 1 on gaps, supports --json); fix defaults to dry-run. Integration: item 8 of the stage-zero pre-check in the migration workflow + the pre-build step in SKILL.md Step 1 + a "pre-check tool" section on the problems page; the problems page's "other pitfalls of the same kind" adds 2 new gaps found in practice (make_unique_for_overwrite, init-capture + this). 9 unit tests (tests/test_cpp20_gap_scan.py)
- **NEW** QOH042 (harmonydeployqt device-side deployment gaps, 5 kinds of systemic problem) — source: an agent's self-captured draft from clean-environment full-flow HarmonyOS porting tests (merged after human verification, application traces generalized): ① non-Qt dependencies of the QPA plugin (the fontconfig chain) aren't deployed (copyPlatformPlugin only recognizes the libQt6* prefix); ② bottle .so files without a SONAME produce absolute-path DT_NEEDED entries, and readElfDependencies truncates the whole dependency list at the drive-letter `:`; ③ libz.so.1 is skipped by Android convention but isn't in the HarmonyOS application linker namespace; ④ device system libraries live in non-standard paths chipset-sdk-sp/ndk/platformsdk; ⑤ bottles lack unversioned file names. With a readelf closure check method, a 5-item pre-deployment checklist + the hvigor environment trio (DEVECO_SDK_HOME/JAVA_HOME/backslash PATH). New problems/runtime-harmonydeployqt-deploy-gaps.md (the deployment-side sister page of runtime-hap-missing-so-closure on the runtime side) + knowledge/errors/QOH042.yaml + a _lookup index row; count knock-on 41→42 (index.yaml/README/SKILL/AGENTS/_task-routing/build-matrix). In this round of testing this class of deployment gap took about 1/4 of the total time (the longest single step 3h); with it in QOH, analyze-log reaches it directly by machine
- **FIX (test-driven)** end-of-turn discipline (SKILL.md discipline red line #7 + AGENTS.md execution discipline) — cause of death measured in the second round of clean-environment full-flow testing: in a non-interactive CLI session the main agent output an "in progress" summary and ended the turn (end of turn = session exit); 3 detached child processes finished their own stubs and disbanded on the spot, nobody took over the build stage, and the pipeline broke. New discipline: do not wrap up before reaching the verify terminal state or a human confirmation point; background tasks must be waited on until complete; if you really must abort, persist state to .qt-ohos/ and state how to resume
- **NEW (test-driven)** libc++15 experimental switch `-D_LIBCPP_ENABLE_EXPERIMENTAL` (problems/build-clang15-libcpp15-cpp20-gaps.md §9 + cpp20-gap-scan GAP-05 suggests it first) — measured: by default 16 ranges algorithms are missing; with the switch all are available and <format> is unlocked too, saving per-algorithm rewrites; jthread/expected/source_location/clock_cast are still missing and handled per the original sections
- **NEW (test-driven)** large repository retrieval resilience (SKILL.md Step 0) — when cloning a large pack gets cut off on a weak network (curl 56 early EOF) and retries still fail, switch to a resumable codeload tarball download (github.com/<owner>/<repo>/tar.gz/refs/heads/<branch>), unpack it into the portgraph workspace, and scan as usual
- **FIX (test-driven)** end-of-turn discipline upgraded to the operational level (SKILL.md red line #7 + AGENTS.md) — the third round of testing died after 42 minutes from the same pattern (even with the disciplined KB it still "delegated to 3 background agents and then wrapped up"); a plain "do not wrap up" wording isn't enough to correct model behavior, so it's upgraded to an operational prohibition: **do not "delegate to background agents and then wrap up waiting"** (in this environment that pattern = task interruption); long tasks must wait synchronously within the turn or run sequentially yourself, and if parallelism is really needed only blocking waits within the session are allowed; and it stresses "no mechanism will wake you up"
- **PERF (test-driven)** parallel downloads in portgraph `fetch-deps` — cause of death measured in the fourth round of testing: serial downloads at 57KB/s on a weak network dragged down the whole flow (a 90-minute timeout on a single step + 30 minutes for the final manifest; the agent was forced to write its own 4-batch parallel download script, getting 33 packages in 471 seconds). Fix: `prefetch_bottles` split out of `fetch_bottle` (ThreadPoolExecutor prefetches tars into .cache in parallel, 8 threads by default, cache hits/already-installed skipped automatically, a single package failure doesn't block); `_download` skips on cache hit (no re-download when the sha matches, naturally supporting reruns that only fill gaps); extraction stays serial (avoiding race conditions with Windows antivirus file locks). The CLI adds `--jobs` (default 8, 0/1 turns it off). 4 unit tests (tests/test_prefetch.py: parallel + cache-hit mtime check / skip already installed / bad sha failure cleanup / no sha trusts the existing file)
- **PATCH** implementation files of the devecocli pre-check fix landed (completing the scripts and docs for FIX ①-⑥ two entries up) + new `.gitattributes` forcing `*.sh text eol=lf` — a Windows checkout turning shell scripts into CRLF makes `bash detect-env.sh` fail with a syntax error, which was the root cause of the pre-check script "changed but won't run"; checking them in uniformly as LF fixes it once and for all
- **PATCH** `parse_version` in `tools/qt_sdk/releasing.py` accepts the `.N` suffix for a second package on the same day (such as `5.15+p1.20261009.2`) — cutting a second version on the same day is a legitimate operation that `release()` itself supports, yet it couldn't pass its own SV6 version gate
- **NEW (trunk governance)** the release manifest is machine-computable and reconcilable: new `_scripts/gen-manifest.py` (recomputes `content_tree_sha256` = sha256 over sorted `<relpath>\0<sha256>`, Qt/platform page counts, test case count, and `built_at`, writing them back in place; `--check` compares, `--check --strict` is for before tagging, `--release` sets released and backfills `root_commit`); `verify.py` adds the M1 check (the 10th kind): version/status enums, page counts, skills list, and test case count must equal reality, and the digest is only enforced when standing on `root_commit`. Previously the 162 test cases and 5 warnings in the manifest were stale hand-filled values
- **NEW (trunk governance)** `_scripts/ci.sh`: one command runs all four gates (verify / faults check / full test suite / `--help` smoke of the 5 CLIs); the exit code is the verdict, for direct use by pipelines or pre-push
- **FIX** the project path of `qt-ohos-run.py scan` became an optional positional argument and gave up the `--project` dest — previously `--project <dir> scan` made argparse error out (exactly the form the docs used); `scan <dir>` and `--project <dir> scan` are now equivalent
- **FIX** the hint from `plan`/`patch` outside a project directory now gives the `--project <project>` usage directly (the old hint only said "run init first", contradicting the fact that the user had just run `scan ~/app`); `analyze-log` no longer requires project state (it was pure log analysis yet printed an init hint first)
- **FIX (test-driven)** test case counts changed from grep counting to actual AST counting and brought under doc guarding: `test_testcase_counts` originally used `grep -c 'def test_'`, counting two literals in its own regex strings as cases (claimed 22, actually 20), and portgraph also missed the 4 in `test_prefetch.py` (119, actually 123); now it counts `test_` methods under `Test*` classes and checks every claim in README and TESTING (12 + 20 + 9 = 41, plus 123 for the graph)
- **FIX (hygiene)** cleaned up 178 build artifacts mistakenly checked in under `skills/qt-community-to-official/templates/` (`.cxx` 62 / `oh_modules` 79 / `.idea`+`.deveco` 14 / `.hvigor` 9 / `.DS_Store` 14), and added 6 `.gitignore` rules to prevent recurrence; `verify`'s 5 H1 warnings drop to zero, template directory 2.9 MB → 500 KB
- **NEW (fault library closed-loop relaxation)** if a defect lacking a tracking ticket already has a scheduled placeholder ticket (`T.status=draft` + `planned_filing`), `faults-build check` reports INFO instead of WARN: the gap still counts as not closed (`chain_state` unchanged, still listed in the not-closed list of `_registry.md` and marked `T-xxxx (planned)`); it just separates "nobody's handling it" from "scheduled to be filed". This release creates T-0008…T-0013 for C-0001/0002/0005/0009/0010/0018 (planned 2026-11-30), and the tracker enum adds `upstream` (third-party upstream, such as Mesa)
- **MERGE (branch convergence)** three branches that hadn't been fully merged into `trunk` have converged, recorded item by item in the new `LINEAGE.md` (with re-review commands and a "deliberately not merged" list): `matrix-release`'s README/SKILL rewrite becomes the documentation base of `trunk` (the original `trunk` still had the 116-line slimmed-down SKILL and a README with "no longer is" wording — a style that had already been rejected); `lzh-add-qt-cef-graft-test`'s `tools/kb-cef-graft.py` + config sample merged, correcting the old claim in the CEF guide that "the grafting script isn't in this knowledge base" (the script is right there in `tools/`); `trunk-flip-v3` adds `team/` (CONTRIBUTORS, TEAM_ONBOARDING), `_templates/` (draft/knowledge-page/problem), `procedural/knowledge-sedimentation.md` (rewritten for this repository's mechanisms: drafts into `faults/_drafts/`, derived artifacts via `faults-build build`, end-of-work `ci.sh`), and `_scripts/pre-push` (leak gate hook)
- **NOT-MERGED (deliberately not merged)** `kb-gate.sh` (old schema, opposite to the required `audience: public`), `kb-release.sh`/`RELEASE-STATE` (superseded by `gen-manifest.py`), `kb-regen-indexes.sh` (old index layout), `kb-sediment.sh`/`kb-promote-drafts.sh`/`drafts/` (a second draft convention alongside `faults/_drafts/`), `kb-bot.py` (external bot environment), `kb-init.py` (taken over by `skills/kb-init`), `kb-sync-common.sh` (no sync source), the root `TEST-REPORT.md` (a one-off record). The originals are still on the frozen branches; reasons and current counterparts are in `LINEAGE.md` §2; `kb-regen-indexes.sh` and `kb-sync-common.sh` are marked as known gaps in this repository
- note: `content_tree_sha256` in `RELEASE-MANIFEST.yaml` is now generated by `_scripts/gen-manifest.py`; the release process is in `CONTRIBUTING.md` §Release process

## v2.2.1 — 2026-08-29

- fix(procedural+semantic): fix skills self-nesting and phantom skills in the manifest

- With a persisted/reused OUT (e.g. a second build into dist/dev-edition), `copy_skills` ran `cp -r src dst`, which copies src *into* the already-existing dst → producing a doubly nested skills/skills/. Changed to `rm -rf` + copying `/.` contents to prevent nesting.
- gen-release-manifest's skills enumeration blindly collected every subdirectory, registering the self-nested skills/ as a phantom skill (the manifest showed skills: ["kb-init","skills"]). Added a SKILL.md check plus a fallback that skips self-nested directories.
- PR #9 previously cleaned up the skills/skills/ artifact in the external repository by hand; this change hardens both layers at the source so it can't recur.

## v2.2.0 — 2026-08-27

- Qt5+CEF HarmonyOS development guide + issue templates (.gitcode/ISSUE_TEMPLATE/) + xsy-letos/xsy-pyqt migration experience + versioned release mechanism (kb-publish.py, a fixed script that releases from main)

## v2.1.0 — 2026-08-25

- Updated Qt 6.12 beta3 module status (QtHarmonyExtras is a standalone module again + corrected file permission interfaces); added OHOS migration and build experience from several Qt applications; scrubbed hard-coded Qt paths from public pages; added a versioned release mechanism (README "Capability spec" section + RELEASE-MANIFEST + CHANGELOG)

## v2.0.0 — 2026-08-19

- **MINOR** Embedded the public subset of `ohos-common-kb` (ArkTS/ArkUI/NAPI/Stage model/DevEco toolchain basics) into `ohos-common-kb-public/`
- **MINOR** Added the `skills/kb-init/` initialization skill: detect the environment → guide installation of missing dependencies → generate `ENV.local.md` → validate the environment
- **MINOR** Multi-channel Qt source acquisition (commercial license via `codereview.qt-project.org` / open-source mirror `ohos-qt/qt-harmonyos-src` / prebuilt SDK releases)
- **MINOR** Added the root documents `SETUP.md` / `CONTRIBUTING.md` / `SECURITY.md`
- **MINOR** `RELEASE-MANIFEST.yaml` records multi-source SHAs + `content_tree_sha256` + page counts (builder v2, schema v1)

> The history of the old 5-skill repository from before v2.0.0 lives under the `legacy/pre-rewrite-*` tags (snapshotted into the internal `raw/imports/ohos_qt-skills-legacy/` for future reference). v1.0.0 was never backfilled.
