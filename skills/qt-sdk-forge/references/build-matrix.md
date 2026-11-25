# Build matrix: platform × version × source acquisition

> The loadable reference layer of qt-sdk-forge. When handling a "build version X on platform Y" request, the agent decides using this page,
> then executes via the SKILL.md workflow.
> Deep environment initialization (DevEco installation, system dependencies, ENV.local.md generation) belongs to
> `skills/kb-init/`; this page focuses on the **source → SDK** acquisition and build path.

---

## 1. Version × acquisition channel decision table

Ask two questions first: **do you need to modify the Qt source?** (yes → build from source; no → prebuilt)
**Do you have a commercial license?** (yes → commercial; no → only the 5.12 open-source/prebuilt release and the Qt6 installer)

| Target | Acquisition | Channel and coordinates | CLI command |
|--------|-------------|-------------------------|-------------|
| Qt 5.15.16 (recommended source line) | Build from source | **Commercial only**: `https://codereview.qt-project.org/qt/tqtc-qt5`, branch `tqtc/harmonyos-5.15.16` | `src-clone --method commercial --version 5.15 --dest <dir> --user <U> --pass <P>` |
| Qt 5.12.12 (LTS maintenance line) | Build from source | Commercial: same repository, branch `tqtc/harmonyos-5.12.12`; **open source**: `https://gitcode.com/ohos-qt/qt-harmonyos-src`, POSIX build branch `build/macos-arm64-qt5.12.12` (LF + build-enabling patches, the default on macOS/Linux; the `main`/`5.12.12` snapshots have CRLF + lost executable bits and are only usable on Windows, see QOH037) | `src-clone --method commercial\|opensource --version 5.12 --dest <dir>` |
| Qt 5.12.12 (framework unchanged) | Prebuilt SDK | `https://gitcode.com/ohos-qt/qt-harmonyos-src/releases` (Windows/macOS × GL/GLES, HarmonyOS × GLES) | Download and extract manually, or `bash skills/kb-init/scripts/download-qt-sdk.sh --platform=<os> --dest <dir>` |
| Qt 6.12 | Official prebuilt installer | The Qt online installer; choose a custom installation and tick the **HarmonyOS** target; the kit path looks like `C:\Qt\Qt6.12-beta3\6.12.0\harmonyos_arm64_v8a` | ❌ **The agent can't download it automatically**: the installer requires logging into a Qt account and interactive operation, so you must **tell the user to install it manually**; once done, register it with `config set sdk_root` |

**Capability differences between versions**: 5.12/5.15 are complete kits (QtOhosExtras, QPA); the 6.12 prebuilt includes the
libqohos QPA and HarmonyExtras, but **lacks WebEngine/DBus/Pdf/Script**
(see `semantic/qt-harmonyos-qt6-status.md`).

### Commercial credentials flow (prerequisite for src-clone --method commercial)

1. Open https://codereview.qt-project.org in a browser and log into your Qt account
2. Settings → HTTP Credentials → GENERATE NEW PASSWORD
3. Note the username/password and pass them to `src-clone --user --pass` (kept only in memory; once the clone finishes,
   the CLI automatically restores the remote URL to its credential-free form)

### Acquisition essentials (common to all source lines)

- The source is about **3GB** and cloning takes a while; disk budget: 3GB source + 5GB build output + 2GB SDK, **reserve >= 15GB**
- **Submodules must be initialized**: `git submodule update --init --recursive` — QtOhosExtras
  is in a submodule (`src-clone` already includes this step; SV1 checks it)
- A full build takes **30-60 minutes** (depending on CPU cores)

---

## 2. Platform × toolchain prerequisites

Required on all platforms: the **OHOS SDK native** (bundled with DevEco Studio:
`<DEVECO>/sdk/default/openharmony/native`, which must contain `llvm/bin/` and `sysroot/`)
+ git + cmake. The CLI's `env` subcommand checks each of these.

| Platform | Compiler | Platform-specific tools | Key notes |
|----------|----------|-------------------------|-----------|
| **Windows** (primary) | MinGW (recommended: `llvm-mingw-20230919-ucrt-x86_64`) | Strawberry Perl | Put `MINGW_ROOT` and `PERL_ROOT` on PATH. mingw32-make must be run with `SHELL=cmd.exe` — **the CLI already does this**, so it's safe under any host shell |
| **macOS** (Sonoma 14+) | Xcode/clang | git >= 2.39.3, python >= 3.12 | `make -j$(sysctl -n hw.ncpu)`; run configure as `sh <src>/configure` |
| **Linux** | OHOS SDK llvm | python3 (the CLI automatically shims a `python` alias, QOH038) + make | Same build flow as macOS (POSIX branch). **Verified in practice** (Ubuntu 22.04 x86_64): src-clone defaults to the POSIX build branch + automatically restores executable bits; configure includes `-no-dbus` (QOH039) + fingerprint protection that automatically cleans dirty build directories (QOH040); `python` is provided automatically by `.qtsdk/pyshim` |
| **HarmonyOS PC** (HarmonyOS PC/dev board/container) | OHOS SDK llvm | [HarmonyBrew](https://gitcode.com/Harmonybrew) (the HarmonyOS port of brew) | `zsh -c "$(curl -fsSL https://harmonybrew.atomgit.com/install.sh)"`, then `brew install git cmake`, etc. |

Platform adaptation is built into the CLI (`tools/qt_sdk/building.py`):
- Windows: `cmd.exe /c configure.bat` + `mingw32-make.exe SHELL=cmd.exe`, automatically injecting `NATIVE_OHOS_SDK`/`OHOS_SDK_SYSROOT`/`LLVM_INSTALL_DIR` and `-device-option CROSS_COMPILE=<llvm>/bin`
- POSIX (macOS/Linux/HarmonyOS): `sh configure` + `make`

### 2.1 Getting the OHOS SDK on Linux (public channel, no login required)

The DevEco **Command Line Tools** require logging into Huawei's website; on Linux you can instead use the native toolchain from the **official public OpenHarmony
mirror** (same origin and structure as the DevEco SDK; verified to work):

```bash
# Path pattern: https://repo.huaweicloud.com/openharmony/os/<version>/ohos-sdk-windows_linux-public.tar.gz
# Choosing a version: QOH041 — the Qt porting layer requires apiVersion >= 23 (i.e. >= 6.1);
#   5.0.3 (API 15) lacks symbols such as OH_ArkUI_PointerEvent_GetGlobalDisplayX, so qarkui won't compile
curl -L -o ohos-sdk.tar.gz \
  "https://repo.huaweicloud.com/openharmony/os/6.1-LTS/ohos-sdk-windows_linux-public.tar.gz"
tar xzf ohos-sdk.tar.gz ohos-sdk/linux/native-linux-x64-*.zip   # extract only native
unzip native-linux-x64-*.zip -d . && mv native/native native-sdk
python3 tools/qt-sdk-run.py config set ohos_sdk_native <absolute-path>/native-sdk
python3 tools/qt-sdk-run.py env      # SV0 verifies llvm/bin + sysroot
```

Tested baseline (2026-09-19, Ubuntu 22.04): OpenHarmony 6.1.0.35 (API 23, clang 15.0.4,
the same version as the official prebuilts) + this repository's POSIX build branch → SV0-SV6/SV8 all PASS.

**Low-memory machines** (<= 8GB RAM): `config set jobs <N>` (N ≈ cores × 2/3 recommended; in testing,
12 cores / 7.7GB was stable with `-j8`).

**After switching SDKs**: the CLI's fingerprint protection cleans the build directory automatically (QOH040); when working manually, be sure to delete
the `build-<variant>` directory first.

---

## 3. Build differences between versions (CLI arguments → configure mapping)

The CLI's `configure --qt <V> --render <R> --build-type <T>` has the following differences built in,
so the agent doesn't need to assemble configure arguments by hand; this section is for cross-checking when reviewing config.summary.

| Difference | Qt 5.12.12 | Qt 5.15.16 | Qt 6.12 |
|------------|-----------|-----------|---------|
| skip list | Full skip (33 entries; see `semantic/qt-harmonyos-build.md` §The configure command) | Lean skip (27 entries; same page, §The Qt 5.15.16 skip list) | N/A |
| `-c++std` | c++14 | c++14 | — |
| OpenGL | `--render gl` → `-opengl desktop` (the CLI automatically checks for sysroot libGLv4.so and, if missing, warns and points to the gitee.com/inkuu/opengl replacement); `--render gles` → `-opengl es2`; `--render gles3` → `-opengl es2 -opengles3` (explicit ES3, requires qtbase c5de1b3d+) | Same as left | — |
| OpenSSL (optional) | Append `-openssl-runtime -I<openssl headers> -ssl` to configure; the headers come from [openharmony/third_party_openssl](https://gitee.com/openharmony/third_party_openssl/tree/master/include/) | Same as left | — |
| Mitigating Desktop GL build failures | SDK/device >= API 20; take `libGLv4.so` from [inkuu/opengl](https://gitee.com/inkuu/opengl/tree/mesa_headers_all), replace the file of the same name under `sysroot/usr/lib/aarch64-linux-ohos/`, and rebuild; set `NEED_OPENGL` in app.json5 | Same as left | — |
| SDK output directory name | `Qt5.12.12-arm64-v8a[-gles|-debug]` | `Qt5.15.16-arm64-v8a[-gles|-debug]` | Kit directory name (decided by the installer) |
| Buildable with this CLI | ✅ | ✅ | ❌ (`configure --qt 6.12` is rejected outright; register/switch/track only) |

A variant combination is the key for the multi-slot scheme: `<qt>-<render>-<build_type>` (e.g. `5.15-gles-debug`);
each configured variant gets its own slot (see SKILL.md §Parallel maintenance of multiple variants).

---

## 4. Quick paths per platform (command equivalence table)

### 4.1 From zero to SDK (any platform)

```bash
# ① Get the source (pick a channel with the §1 decision table)
python tools/qt-sdk-run.py src-clone --method <m> --version <v> --dest <dir> [--user U --pass P]

# ② Initialize the forge state + point it at things
python tools/qt-sdk-run.py init
python tools/qt-sdk-run.py config set qt_src <source root>
python tools/qt-sdk-run.py config set ohos_sdk_native <OHOS SDK native>

# ③ Build (platform-independent; the CLI adapts internally to Windows/POSIX)
python tools/qt-sdk-run.py configure --qt <v> --render gl --build-type release
python tools/qt-sdk-run.py build          # default timeout 4h, override with --timeout
python tools/qt-sdk-run.py install

# ④ Gates + release + switch
python tools/qt-sdk-run.py verify
python tools/qt-sdk-run.py release --note "initial 5.15.16 build"
python tools/qt-sdk-run.py use <version>
```

### 4.2 No source, prebuilt only (fastest start)

```bash
# 5.12: download and extract from GitCode releases (or use the kb-init script)
bash skills/kb-init/scripts/download-qt-sdk.sh --platform=<macos|windows|linux> --dest <dir>
# 6.12: tick the HarmonyOS target in the Qt online installer

# Register it in forge version management (ENV sync goes through use)
python tools/qt-sdk-run.py config set sdk_root <extract/install directory>
```

### 4.3 Platform-specific manual commands (equivalents when the CLI isn't available)

**Windows** (must be PowerShell/cmd, or add `SHELL=cmd.exe`):

```powershell
$env:NATIVE_OHOS_SDK = "C:\...\openharmony\native"
$env:OHOS_SDK_SYSROOT = "$env:NATIVE_OHOS_SDK\sysroot"
$env:LLVM_INSTALL_DIR = "$env:NATIVE_OHOS_SDK\llvm"
cd <build_dir>
mingw32-make.exe SHELL=cmd.exe -j64 install    # incremental + install in one command
```

**macOS / Linux / HarmonyOS**:

```bash
export NATIVE_OHOS_SDK=/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/native
export OHOS_SDK_SYSROOT="$NATIVE_OHOS_SDK/sysroot"
export LLVM_INSTALL_DIR="$NATIVE_OHOS_SDK/llvm"
cd <build_dir>
make -j$(nproc 2>/dev/null || sysctl -n hw.ncpu) install
```

For the full verbatim configure arguments, see `semantic/qt-harmonyos-build.md` and
`skills/kb-init/references/qt-compile-guide.md` (including a table of common configure/build errors).

---

## 5. Entry points for build troubleshooting

1. A CLI step exits non-zero → first look at the tail of `.qtsdk/logs/<timestamp>-<step>.log` (state.json also holds the tail as evidence)
2. `python tools/qt-ohos-run.py analyze-log <log>` — machine matching against 42 QOH error patterns; follow the matched entry's `refs` to read the problems/ knowledge pages
3. Search `problems/_lookup.md` by error message
4. The three incremental-build pitfalls (build without install / running mingw32-make under bash / demo not rebuilt after install) are backstopped by the SV4/SV7 gates; the **fourth pitfall** (reusing a dirty build directory across configurations/SDK switches, QOH040) is backstopped by the CLI's configure fingerprint protection

Common pitfalls of Linux/macOS source builds (prevention is built in for all of them, and analyze-log can match them):

| QOH | Symptom | Built-in prevention |
|-----|---------|---------------------|
| QOH037 | `configure: Permission denied` / `bad interpreter ^M` / no tqtc branch in the open-source mirror | src-clone defaults to the POSIX build branch + automatically restores executable bits + rejects CRLF |
| QOH038 | `python: not found` (during the QtQml stage) | build_env automatically shims `.qtsdk/pyshim` |
| QOH039 | qdbusreply.h -Wdeprecated-copy blocked by -Werror | configure includes `-no-dbus` |
| QOH040 | Leftover ibus plugin build (unknown QDBusArgument) | A changed configure fingerprint automatically cleans the build directory |
| QOH041 | qarkui lacks OH_ArkUI_* symbols | See §2.1; the SDK needs apiVersion >= 23 |

---

## 6. Verified baseline

| Version | Branch | Commit | Date |
|---------|--------|--------|------|
| Qt 5.15.16 | tqtc/harmonyos-5.15.16 | 962aa625 | 2026-04-19 |
| Qt 5.12.12 | tqtc/harmonyos-5.12.12 | 613336de | 2026-05-25 |

> After upstream evolves, first run `python tools/qt-sdk-run.py upstream-check`; for the baseline table update process,
> see SKILL.md §7.4.
