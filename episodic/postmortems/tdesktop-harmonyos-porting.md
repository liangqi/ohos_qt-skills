---
id: episodic-projects-tdesktop-harmonyos-porting
type: episodic
domain: project
tags: [tdesktop, telegram, qt6, harmonyos, portgraph, cross-compile, hap, signing, ime]
created: 2026-09-12
updated: 2026-09-12
status: active
audience: public
refs: [problem-build-qt612-qos-harmony-macro, problem-build-clang15-libcpp15-cpp20-gaps, problem-runtime-hap-missing-so-closure, problem-build-qt612-ohos-plugin-rebuild, problem-runtime-ohos-ime-reset-detach, semantic-qt-harmonyos-build]
summary: >
  A full HarmonyOS port of Telegram Desktop (tdesktop v7.0.2) with no features cut: portgraph fetch-deps resolved every dependency with
  59 bottles + 9 source builds; adapted 2088 targets (the Q_OS_HARMONY macro / the not_ohos
  set / clang15 C++20 gaps); harmonydeployqt + signing injection + hvigor packaging into a 550MB HAP;
  DT_NEEDED closure analysis fixed the die-at-startup crash; a rebuild-and-deploy chain for the Qt 6.12 platform plugin + an IME reset fix.
  Zero crashes in a 60s smoke test after installing. Reusable: a five-stage pipeline + 6 tool-script patterns.
---

# Full HarmonyOS port of tdesktop (Telegram Desktop) — lessons learned

## Project overview

| Field | Details |
|-------|---------|
| Timeframe | 2026-09-10 ~ 2026-09-12 |
| Tech stack | tdesktop v7.0.2 (7002007) + Qt 6.12-beta3 harmonyos_arm64_v8a kit + OHOS NDK clang15/libc++15 (API 23) |
| Goal | No features cut; runs without crashing on a HarmonyOS PC (HUAWEI MateBook Pro) |
| Scale | 2088 build targets → 55 .so files → 550MB signed HAP |
| Status | ✅ Installed and running, zero crashes in a 60s hilog smoke test; IME reset bug fixed and regression-tested |

## Overall pipeline (reusable skeleton)

```
portgraph fetch-deps (dependency closure)     ← stage 1
  → ninja out-ohos (source adaptation build)  ← stage 2
  → harmonydeployqt --no-build                ← stage 3
  → signing injection + hvigorw assembleHap   ← stage 3
  → hdc install -r + hilog smoke              ← stage 4
  → rebuild and replace the platform plugin (optional) ← stage 5
```

Each stage is independently re-entrant; a failure in one stage doesn't roll back the others.

## Stage 1: resolving dependencies (driven by portgraph)

```bash
python portgraph.py fetch-deps tdesktop --dry-run   # look at the closure and the gaps first
python portgraph.py fetch-deps tdesktop             # outputs land in workspace/ohos-libs/ (a cross-application cache)
python portgraph.py fetch-deps tdesktop --json      # get CMAKE_PREFIX_PATH and other integration parameters from the manifest
```

- **59 dependencies hit a bottle directly** (Harmonybrew/cmd-pkgs prebuilt outputs), with integration parameters read from the manifest.
- **9 without a bottle were built from source**, with two special techniques:
  - **aom**: the official source has no bottle → build from source using the GitHub `m-ab-s` mirror;
  - **dav1d**: only a static library → convert static to shared: `clang -shared -Wl,--whole-archive libdav1d.a -o libdav1d.so.7 ...`.
- **Bottle symlink corruption on Windows/NTFS**: shows up as 0-byte files or inaccessible reparse
  points (EACCES) → delete the corrupt links and copy in the real versioned files (202 fixed this time).
- Feature coverage check conclusion (nothing cut): rlottie (→tlottie), tg_owt+webrtc, tgcalls, cld3,
  libprisma, icu, and libwebp are all available in the package.

## Stage 2: source adaptation (2088 targets)

Three main kinds of adaptation; the first two each became a standalone problem page:

1. **Platform macro and source-set exclusion**: the Qt 6.12 kit's macro is `Q_OS_HARMONY` (not 5.15's `Q_OS_OHOS`);
   if `nice_target_sources`' ohos branch mistakenly marks `not_linux`, it silently turns the ohos implementations into
   HEADER_FILE_ONLY → see
   [build-qt612-qos-harmony-macro](../../problems/build-qt612-qos-harmony-macro.md).
2. **8 kinds of C++20 gaps in clang15/libc++15** (capturing structured bindings/P0960/P0634/stop_token/
   atomic_ref/ranges/shared_ptr `<=>`/variant construction) → see
   [build-clang15-libcpp15-cpp20-gaps](../../problems/build-clang15-libcpp15-cpp20-gaps.md).
3. **Miscellaneous adaptations** (small in scope but required):

| Location | Change |
|----------|--------|
| `update_checker.cpp` | 6 platform guards |
| `platform_*.h` dispatch headers | Macros changed to `HARMONY \|\| OHOS` for dual compatibility |
| `specific_ohos.h` | **Check before changing**: an `inline` function doesn't emit a symbol in a TU that doesn't reference it in the first place (`llvm-nm specific_ohos.cpp.o` shows only `T psAppDataPath()` / `T psCleanup()`); when referenced, it shows up as `W` (weak) in the caller's TU. **Only** remove `inline` when the link reports undefined and `llvm-nm` shows the symbol as weak/missing |
| `tray_ohos / webauthn_ohos / file_utilities_ohos` | New implementations / removed outer duplicate definitions. **The tray isn't an optional class**: `Platform::Tray _tray` is a member variable of the tray manager, constructed unconditionally, and `TrayIconSupported()` only blocks the icon, not construction; you must provide a complete no-op public surface (14 methods + `HasMonochromeSetting()`), and deleting the class blows up at link time |
| `base_power_save_blocker_ohos` | QPointer signature adaptation |
| `lib_ui` | Added 3 files under `ui/platform/ohos/` |
| `delayed_activation.cpp` | Excluded the XCB path |
| Several TooManyCooks headers | Compatible rewrites for typename/atomic_ref/constructors |

**Lesson**: multiple changes to the same file must be edited **serially**: parallel SearchReplace on the same file overwrites each other
(race overwrites happened 3 times this time: sync.hpp / spawn_many.hpp / settings_notifications.cpp).

## Stage 3: packaging and deployment (the make_hap.py three-step pattern)

```
① harmonydeployqt --input <deployment-settings.json> --output <proj> --no-build
② inject signingConfigs into build-profile.json5 (keeping the content from the previous session)
③ hvigorw assembleHap --mode module -p product=default -p buildMode=debug --no-daemon
```

- Signing materials: a Huawei Cloud debug certificate (certpath/keyAlias/storeFile + **an encrypted password blob**).
  The bundle name must match the profile binding; hvigor's encrypted password blob can be reused directly from a previous project's
  build-profile.json5, with no need to regenerate it.
- Environment requirements: `DEVECO_SDK_HOME=<sdk>`; prepend node + DevEco's jbr/bin to PATH.
- Three hvigor pitfalls: ① command not found → you must pass the full path of `hvigorw.bat`; ② missing
  DEVECO_SDK_HOME → BuildNativeWithCmake skips in 1ms with no output; ③ `spawn java ENOENT` →
  jbr/bin isn't on PATH.

## Stage 4: runtime verification and troubleshooting "dies at startup"

- **60s hilog smoke**: after installing and launching, capture 60 seconds of logs; zero crashes passes the gate.
- **Dies at startup (64ms, exit 254)**: jscrash `TypeError: handleAbilityStageOnCreate of
  undefined` = transitive .so dependencies of libqohos.so are missing → use `llvm-readobj --needed-libs`
  to compute a DT_NEEDED **BFS closure** from libqohos.so + libTelegram.so, and compare against the system .so files and the deployment directory
  to find the gaps → fill in libdav1d.so.7 / libaom.so.3 / libbz2.so.1.0 / libz.so → see
  [runtime-hap-missing-so-closure](../../problems/runtime-hap-missing-so-closure.md).
- **Application-layer logs**: tdesktop's log.txt is at
  `/data/app/el2/100/base/<bundle>/preferences/log.txt` (the same directory as tdata);
  pull it with `hdc file recv` and look at `RPC Error` to judge the MTP/network layer (telling client bugs from server behavior).
- Network: the device goes through a local SOCKS proxy (trojan-go 127.0.0.1:1080), using tdesktop's built-in proxy settings.

## Stage 5: rebuilding the Qt platform plugin (the libqohos.so replacement workflow)

The rebuild chain established while fixing the IME reset bug in the Qt 6.12-beta3 ohos plugin:
cmake + `BUILD_SUBMODULES=src/plugins/platforms` with five pitfalls in a row (qt-cmake refuses to build qtbase itself /
NODE_ADDON_API_ROOT / FIND_ROOT_PATH re-rooting / OHOS_NDK_ROOT / fontconfig feature
scope) → the output replaces the **kit's** plugins/platforms (harmonydeployqt deploys from the kit; editing
the deployment directory directly gets overwritten) → mind filling in SONAME differences → see
[build-qt612-ohos-plugin-rebuild](../../problems/build-qt612-ohos-plugin-rebuild.md).

## Stage 6: IME integration and classifying "Chinese search finds nothing"

- **Fix**: the original Detach/Attach implementation of `QOhosInputContext::reset()` collapsed the soft keyboard mid composition +
  commit polluted the text with pinyin letters → aligned with Android's behavior of only finalizing the preedit → see
  [runtime-ohos-ime-reset-detach](../../problems/runtime-ohos-ime-reset-detach.md).
- **The IMEPROBE probe method** (reusable): add `qOhosPrintfDebug` + code-point escaping at the plugin's IMF callback entries + the context's key paths,
  capture 60-90s of hilog, and directly prove whether the commit path is clean.
- **Classifying "Chinese search returns no results" (not a porting bug)**: three-way check (local conversation search / remote global search /
  comparison with the official client on the same account), conclusions:
  - Local CJK indexing works (searching for 「极」 hits conversations already joined);
  - the Telegram server simply doesn't index short Chinese words for **global** search (the official client can't find them either);
  - tdesktop's local index only has built-in **Russian** transliteration (`translitRusEng`), no pinyin; Latin queries hitting
    Chinese conversations rely on the conversation's Latin @username.

## Reusable outputs (local tool scripts; the patterns can be re-created)

| Script | Purpose |
|--------|---------|
| `build-tdesktop-ohos.ps1` | `ninja -C out-ohos -k 0` + Tee the complete log (errors not truncated) |
| `make_hap.py` | Three-step packaging: deploy → signing injection → hvigor (stage 3 of this page) |
| `check_closure.py` | DT_NEEDED BFS closure vs. system libraries/the deployment directory to find gaps (stage 4) |
| `build-libqohos.ps1` | Rebuild the platform plugin with cmake BUILD_SUBMODULES (stage 5) |
| `capture_ime.py` / `analyze_ime.py` | hilog IME capture and UTF-8 code-point analysis (stage 6) |

## Lessons and principles

1. **portgraph first**: look at the closure with `--dry-run` first; if a bottle solves it, don't build from source (the workload differs by two orders of magnitude).
2. **Compiling ≠ a successful migration**: the install + smoke gate is what counts; silent-exclusion bugs (HEADER_FILE_ONLY)
   produce zero errors at compile time, and the signal is a flood of symbol errors at link time.
3. **When find fails in a cross-compilation, suspect FIND_ROOT_PATH re-rooting first**, and bypass it by pre-filling cache variables.
4. **Troubleshoot the platform layer and the application layer separately**: use probe logs for Qt plugin bugs, the application's own logs for application bugs
   (tdesktop's log.txt), and comparison with the official client for network/server problems.
5. **PowerShell distorts Chinese matches in BOM-less UTF-8 logs**; always use Python for cross-encoding analysis.
