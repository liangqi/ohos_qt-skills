---
id: procedural-fetch-ohos-third-party-lib
type: procedural
domain: workflow
tags: [qt, harmonyos, third-party, harmonybrew, bottle]
created: 2026-07-07
updated: 2026-07-07
status: active
audience: public
refs: [procedural-qt-app-harmonyos-migration, semantic-qt-harmonyos-third-party-libs]
summary: >
  One-command download of arm64-OpenHarmony prebuilt bottles (.so) from Harmonybrew, with checksum verification and extraction,
  so you can link them into a Qt HarmonyOS project without cross-compiling. Covers recursive dependencies, qmake/CMake link snippets, and version-resolution pitfalls.
---

# Getting prebuilt arm64-OpenHarmony third-party libraries from Harmonybrew

> Use `fetch-ohos-bottle.sh` to download Harmonybrew's community-built arm64-OpenHarmony bottles (`.so`) in one command: it verifies the sha256, extracts them, and recursively pulls runtime dependencies, so you can link them into a Qt HarmonyOS project without cross-compiling. In the HarmonyOS porting workflow, use it instead of cross-compiling from source whenever a library already has a bottle.

---

## When to use this

- Your application depends on a C/C++ third-party library for which Harmonybrew already provides an `arm64_ohos` prebuilt bottle.
- You want to skip OHOS NDK cross-compilation and get a linkable arm64-OpenHarmony `.so` + headers + CMake config directly.
- You're pulling dependencies in bulk in a CI pipeline and want to avoid each pipeline cross-compiling its own.
- You want the `lib/cmake/<pkg>Config.cmake` bundled in the bottle so you can integrate via `find_package`.

> Not applicable when Harmonybrew has no bottle for the library — fall back to cross-compiling from source, [[qt-harmonyos-third-party-libs]] §2.

---

## Prerequisites

| Tool | Purpose | Notes |
|------|---------|-------|
| bash | Running the script | Git Bash / WSL / CI all work (the script uses `set -euo pipefail`, so it fails fast) |
| git | Cloning/pulling the formula repository | AtomGit's raw `.rb` files and REST API are blocked by CloudWAF (HTTP 418), and the Harmonybrew formula JSON returns 404 NoSuchKey — **only the git protocol works**, so the script uses `git clone --sparse` to fetch just the `Formula/` tree |
| curl | Downloading bottles + HEAD probing | `-sIL` to probe, `-fL` to download |
| tar | Extracting `.tar.gz` | Bundled with Git Bash |
| sha256sum or shasum | Verifying the sha256 | Git Bash bundles `shasum -a 256`; the script falls back automatically |

No curl of raw `.rb` files or the JSON API is needed — raw/REST are blocked with 418 and the formula JSON 404s, so the script goes entirely through git.

---

## Quick start

```bash
# Fetch abseil and its runtime dependencies, extracting into ${DELIVERABLES_ROOT}/ohos-libs
bash _scripts/fetch-ohos-bottle.sh -f abseil -o ${DELIVERABLES_ROOT}/ohos-libs
```

Expected output (`${DELIVERABLES_ROOT}/ohos-libs` is the absolute path `-o` resolves to; progress/info lines go to stderr, while the ✅ summary and link snippets go to stdout):

```
✅ abseil 20260526.0
   lib/     ${DELIVERABLES_ROOT}/ohos-libs/abseil/20260526.0/lib
   include/ ${DELIVERABLES_ROOT}/ohos-libs/abseil/20260526.0/include
   cmake/   ${DELIVERABLES_ROOT}/ohos-libs/abseil/20260526.0/lib/cmake

# qmake (.pro) — linking abseil
LIBS += -L${DELIVERABLES_ROOT}/ohos-libs/abseil/20260526.0/lib \
        -labsl_base -labsl_city -labsl_clock -labsl_hash -labsl_raw_hash_set -labsl_status -labsl_strings -labsl_throw_delegate

# CMake — abseil provides abslConfig.cmake
cmake -S . -B build_ohos \
  -DCMAKE_TOOLCHAIN_FILE=$NATIVE_OHOS_SDK/build/cmake/ohos.toolchain.cmake \
  -DOHOS_ARCH=arm64-v8a \
  -DCMAKE_PREFIX_PATH=${DELIVERABLES_ROOT}/ohos-libs/abseil/20260526.0 \
  -DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=BOTH
```

abseil has no runtime dependencies, so recursion isn't triggered. ffmpeg (with 14 dependencies) recursively pulls zlib/openssl@3 and others.

---

## Where this fits in the workflow

This step comes after **phase one §1.1 feasibility assessment** in [[qt-app-harmonyos-migration]]:

- When assessing third-party dependencies, first check whether Harmonybrew has an `arm64_ohos` bottle.
- **If there's a bottle** → use this script to fetch the `.so` + headers + CMake config in one command, skip cross-compilation, and go straight to §6 build system adaptation.
- **If there isn't** → follow [[qt-harmonyos-third-party-libs]] §2 to cross-compile from source with the OHOS NDK.

In other words, this script is the automated implementation of the "integrating prebuilt .so files" strategy (row 3 of [[qt-harmonyos-third-party-libs]] §1's strategy table), with the Harmonybrew community repository as the source.

---

## How dependency resolution behaves

By default the script **recursively pulls runtime dependencies**, recursing by the formula's real name (such as `icu4c@78`, `zlib-ng-compat`, `pkgconf`), with a visited set for deduplication.

| Where depends_on appears | Handling |
|--------------------------|----------|
| At class-body top level (a bare `depends_on "x"`) | ✅ Included (runtime) |
| Inside an `on_linux do` / `on_arm64_ohos do` block | ✅ Included (OHOS is linux-based) |
| Inside an `on_macos do` block | ❌ Stripped |
| Inside a `head do` block | ❌ Stripped (head-only build dependencies) |
| Inside a `resource "..." do` block | ❌ Stripped |
| With `=> :build`, `=> :test`, or `=> [:build, :test]` | ❌ Excluded (not runtime) |
| The same package appearing both as `:build` and bare (such as glib's gettext) | ✅ The runtime list keeps the bare instance once |

Other behavior:
- `--no-deps` disables recursion and fetches only the named formula (use it only when you're sure the dependencies are already in place).
- `uses_from_macos "bzip2"` (in boost/pcre2) is **not** a `depends_on` and isn't fetched automatically — the script prints `ℹ️ Note: <formula> has uses_from_macos dependencies…`; fetch them manually if a library turns out to be missing at runtime.
- Trailing `#` comments (such as ffmpeg's `depends_on "libvmaf" # dependent: ab-av1`) are stripped before the name is extracted.
- Recursion reuses the cache: an already-downloaded bottle isn't re-downloaded (unless you pass `--force`).

---

## Supported libraries

> The 16 formulae below were confirmed to have `arm64_ohos` bottles (probed 2026-07-07). Versions are resolved dynamically by the script from the formula; "resolved dynamically" means derived from the `url` field. Not every formula has a bottle; the bare names (openssl / icu4c / pkg-config) don't exist — use the `@` variants or `pkgconf`.

| Library | Version | arm64_ohos | Notes |
|---------|---------|:----------:|-------|
| abseil | 20260526.0 | ✓ | sha256 `3a1ec15d…b46e` verified; no runtime dependencies |
| openssl@3 | 3.6.3 | ✓ | An `@` variant; bare `openssl` doesn't exist, and the URL tries `@` first, then `%40` |
| zlib | 1.3.2 | ✓ | |
| ffmpeg | 8.1.2 | ✓ | 14 runtime dependencies, fetched recursively |
| libpng | Resolved dynamically | ✓ | The `lib` prefix → `Formula/lib/` (not `Formula/l/`) |
| freetype | Resolved dynamically | ✓ | |
| harfbuzz | Resolved dynamically | ✓ | |
| protobuf | 35.1 | ✓ | The url has a `v` prefix (`v35.1` → `35.1`) |
| jsoncpp | Resolved dynamically | ✓ | |
| boost | 1.90.0_1 | ✓ | A top-level `revision 1` → the filename `<ver>_1` |
| sqlite | 3.53.0 | ✓ | An explicit `version "3.53.0"` (the only explicit version) |
| curl | 8.21.0 | ✓ | `rebuild 1` inside `bottle do` → `.bottle.1.tar.gz` |
| libxml2 | Resolved dynamically | ✓ | The `lib` prefix |
| pcre2 | 10.47_1 | ✓ | A top-level `revision 1` → `_1` |
| glib | Resolved dynamically | ✓ | gettext appears both as `:build` and bare; the runtime list deduplicates to one entry |
| fontconfig | 2.17.1 | ✓ | The url is `2.17.1.orig` → the regex stops at `.orig` → `2.17.1` |

Missing bare names and their replacements: `openssl` → use `openssl@3`; `icu4c` → use `icu4c@78`; `pkg-config` → use `pkgconf` (the script substitutes this automatically).

---

## Linking into Qt

The script generates the qmake `-l` list dynamically in its summary (by scanning `lib/lib*.so` and stripping the `lib` prefix and `.so[.N]` suffix) plus a CMake snippet (only when `lib/cmake/<pkg>/<pkg>Config.cmake` exists). Below is abseil's actual output, where `${DELIVERABLES_ROOT}/ohos-libs` stands for the absolute path `-o` resolved to:

```makefile
# qmake (.pro) — linking abseil
LIBS += -L${DELIVERABLES_ROOT}/ohos-libs/abseil/20260526.0/lib \
        -labsl_base -labsl_city -labsl_clock -labsl_hash -labsl_raw_hash_set -labsl_status -labsl_strings -labsl_throw_delegate
```

```cmake
# CMake — abseil provides abslConfig.cmake
cmake -S . -B build_ohos \
  -DCMAKE_TOOLCHAIN_FILE=$NATIVE_OHOS_SDK/build/cmake/ohos.toolchain.cmake \
  -DOHOS_ARCH=arm64-v8a \
  -DCMAKE_PREFIX_PATH=${DELIVERABLES_ROOT}/ohos-libs/abseil/20260526.0 \
  -DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=BOTH
```

Key points:
- The `-L` path = `<out-dir>/<formula>/<version>/lib` (the `lib/` subdirectory after extraction).
- The `-l` list is generated dynamically from `lib/lib*.so`; different libraries have different `.so` sets, so just copy the script's output.
- `CMAKE_PREFIX_PATH` points at `<out-dir>/<formula>/<version>` (which contains `lib/`, `include/`, and `lib/cmake/`), and `find_package` locates things from there.
- You **must** pass `-DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=BOTH`, or `find_package` won't find the dependencies when cross-compiling (the iron rule in [[qt-harmonyos-third-party-libs]] §4.1 and [[qt-harmonyos-project-structure]] §4.2).
- Once you have the `.so`, deploy it into `entry/libs/arm64-v8a/` for it to work on the device ([[qt-harmonyos-third-party-libs]] §3).

---

## Notes and pitfalls

- **A single hyphen**: the bottle URL is `<formula>-<version>.arm64_ohos.bottle[.rebuild].tar.gz` (**one** hyphen between the name and the version), not Homebrew's default double hyphen. The script builds it that way — don't change it by hand.
- **Not every formula has a bottle**: if the script finds no `arm64_ohos:` line in the formula, it errors out and points you at the source-build fallback. Without a bottle, follow [[qt-harmonyos-third-party-libs]] §2.
- **arm64-only / can't run on Windows**: these `.so` files use the arm64-OpenHarmony ABI, so on Windows you **can link against them but not run them**; running requires deploying the `.so` to a HarmonyOS device (`entry/libs/arm64-v8a/`).
- **Runtime dependencies must be fetched too**: recursion is on by default (`--no-deps` is only for when you're sure the dependencies are in place). Missing a dependency → `dlopen` fails on the device.
- **The sha256 must be verified**: the script reads the sha256 from the formula's `bottle do` block and enforces it; on a mismatch it deletes the cache and errors out. Don't bypass it.
- **`.so` symlinks on Windows**: inside a bottle, `libfoo.so` is usually a symlink to `libfoo.so.N`, which Windows NTFS can't create (tar reports `Cannot create Symlink` and exits non-zero). The script judges extraction success by whether the target directory was created (ignoring tar's exit code) and automatically recreates the missing `.so` link names by **copying**, so `-lfoo` can be found by the OHOS cross-linker. The symlink warnings during extraction can be ignored.
- **CloudWAF → you must git clone**: AtomGit's raw `.rb` files and the atomgit.com REST API are blocked with 418, and the Harmonybrew formula JSON returns 404 NoSuchKey (not 418). The script reads formulae via `git clone --sparse` and can't `curl` the raw files. `git clone` is occasionally blocked too — just retry.

---

## Troubleshooting

| Symptom | What to check |
|---------|---------------|
| `formula 'X' doesn't exist. Available @ variants: …` | The bare name is missing — use `-f openssl@3` / `-f icu4c@78` / `-f pkgconf` (the script substitutes `pkgconf` for `pkg-config` automatically) |
| `bottle 404: <url>` | Wrong version — check `revision`/`rebuild`: pass `-v <ver>` explicitly, or look at the formula `.rb`'s top-level `revision N` and the `rebuild N` inside `bottle do` |
| `formula 'X' has no arm64_ohos bottle` | There's no prebuilt package for this library; cross-compile from source per [[qt-harmonyos-third-party-libs]] §2 |
| `sha256 mismatch` | The cache is corrupt — re-download with `--force`; if it still doesn't match, the formula updated its bottle, so `git pull` the formula repository (`~/.cache/harmonybrew-core`) |
| `git clone failed` | CloudWAF blocks intermittently — retry; or delete `~/.cache/harmonybrew-core` and retry; or point at a fresh clone with `--formula-repo <path>`; with no network at all, formulae can't be read |
| `no sha256sum/shasum` | Windows Git Bash bundles `shasum`; or use WSL |
| A version-derivation warning plus a bottle 404 | The url-derived version got truncated at a `.`/`-` (fontconfig's `.orig` / boost's `-b2`) — pass the correct version explicitly with `-v` |

---

## Checklist

- [ ] The formula name is correct (including `@` variants and the `lib` prefix; replace the bare openssl/icu4c/pkg-config with variants or pkgconf)
- [ ] The HEAD probe of the bottle returns 200
- [ ] The sha256 verification passes (enforced by the script)
- [ ] Runtime dependency recursion completed (or `--no-deps` was used with the dependencies confirmed in place)
- [ ] The `.so` has been deployed into `entry/libs/arm64-v8a/` (see [[qt-harmonyos-third-party-libs]] §3)
- [ ] qmake's `LIBS +=` or CMake's `CMAKE_PREFIX_PATH` + `CMAKE_FIND_ROOT_PATH_MODE_PACKAGE=BOTH` is configured

---

## Supply chain

| Dimension | Details |
|-----------|---------|
| **Upstream source** | The Harmonybrew community repository (atomgit.com/Harmonybrew/homebrew-core) |
| **Upstream input** | The formula `.rb` (version/sha256/dependency metadata) + the bottle `.tar.gz` (prebuilt arm64-OpenHarmony `.so` files) |
| **Downstream recipients** | Qt HarmonyOS porting projects (application migration) / CI pipelines |
| **Deliverables** | `<out-dir>/<formula>/<version>/{lib,include,lib/cmake}` + the qmake/CMake link snippets |
| **Deliverable path** | `${DELIVERABLES_ROOT}/ohos-libs/` (see `ENV.md`) |
| **Routing rules** | No bottle → fall back to cross-compiling from source ([[qt-harmonyos-third-party-libs]] §2) |

---

## Related context

- [[qt-app-harmonyos-migration]] — The HarmonyOS migration workflow (this script is used after phase one §1.1)
- [[qt-harmonyos-third-party-libs]] — The guide to porting third-party libraries (§2 for cross-compiling from source when there's no bottle; §3 for `.so` deployment rules; §4 for CMake integration)
- [[qt-harmonyos-platform-limits]] — `.so` deployment / dlopen restrictions (dlopen rejects writable paths)

---

## References

- The Harmonybrew formula repository: `https://atomgit.com/Harmonybrew/homebrew-core.git` (git clone; default branch `main`; files at `Formula/<first-letter>/<name>.rb`)
- The bottle download domain: `https://harmonybrew.atomgit.com/bottles/<formula>-<version>.arm64_ohos.bottle.tar.gz`
- The Harmonybrew mirror-deploy documentation (`HOMEBREW_BOTTLE_DOMAIN` mirror configuration)
- [Qt for HarmonyOS (Qt Wiki)](https://wiki.qt.io/Qt_for_HarmonyOS) — The overall architecture
