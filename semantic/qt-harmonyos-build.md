---
id: semantic-qt-harmonyos-build
type: semantic
domain: tech
tags: [qt, harmonyos, build, configure, cmake, deveco, mingw, perl]
created: 2026-06-02
updated: 2026-07-03
status: active
audience: public
refs: [semantic-qt-harmonyos-overview]
summary: >
  The Qt for HarmonyOS build guide: setting up the macOS/Windows build environment, configure options,
  Qt Creator kit configuration, DevEco Studio integration, OpenSSL/OpenGL configuration, and the Qt 5.15 skip list.
---

# The Qt for HarmonyOS build guide

## Prerequisites

### macOS (Sonoma 14.0+)
- git ≥ 2.39.3
- python ≥ 3.12.0
- DevEco Studio (which bundles the SDK)

### Windows
- **MinGW toolchain**: `llvm-mingw-20230919-ucrt-x86_64.zip` is recommended (extract it to, say, `D:\`)
- **Perl**: [Strawberry Perl](https://strawberryperl.com/)
- **DevEco Studio** + the HarmonyOS SDK
- Add MinGW and Perl to PATH, and set `MINGW_ROOT` and `PERL_ROOT`

## Environment variables

```bash
# macOS
export NATIVE_OHOS_SDK=/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/native

# Windows (cmd)
SET NATIVE_OHOS_SDK=<LOCAL_PATH>
SET OHOS_SDK_SYSROOT=%NATIVE_OHOS_SDK%\sysroot
SET LLVM_INSTALL_DIR=%NATIVE_OHOS_SDK%\llvm
SET QT5_ROOT_DIR=<LOCAL_PATH>
```

## The configure command

### macOS (arm64-v8a)

```bash
#!/bin/sh
ARCH="arm64-v8a"
QT5_ROOT_DIR=<PATH_TO>/tqtc-qt5
QT5_BUILD_DIR="$QT5_ROOT_DIR/build_${ARCH}"

mkdir "$QT5_BUILD_DIR"
cd "$QT5_BUILD_DIR"

../configure \
 -v \
 -xplatform ohos-clang \
 -prefix /data/storage/el1/bundle/libs/arm64 \
 -extprefix ${NATIVE_OHOS_SDK}/opt/Qt/5.12.12/ohos-${ARCH}-clang/ \
 -opensource -confirm-license -release \
 -no-use-gold-linker -no-gcc-sysroot \
 -ohos-arch ${ARCH} \
 -skip qt3d -skip qtactiveqt -skip qtandroidextras -skip qtcanvas3d \
 -skip qtconnectivity -skip qtdatavis3d -skip qtdoc -skip qtdocgallery \
 -skip qtfeedback -skip qtgamepad -skip qtgraphicaleffects -skip qtlocation \
 -skip qtmacextras -skip qtnetworkauth -skip qtpim -skip qtpurchasing \
 -skip qtqa -skip qtremoteobjects -skip qtrepotools -skip qtscript \
 -skip qtscxml -skip qtsensors -skip qtserialbus -skip qtserialport \
 -skip qtspeech -skip qtsystems -skip qttools -skip qttranslations \
 -skip qtvirtualkeyboard -skip qtwayland -skip qtwebchannel \
 -skip qtwebengine -skip qtwebglplugin -skip qtwebsockets \
 -skip qtwebview -skip qtwinextras -skip qtx11extras -skip doc \
 -no-dbus -c++std c++14 \
 -nomake examples -nomake tests

make -j16
make install
```

### Windows (arm64-v8a)

```bat
REM Skip modules
SET QT_SKIPS=-skip qt3d -skip qtactiveqt -skip qtandroidextras -skip qtcanvas3d -skip qtconnectivity -skip qtdatavis3d -skip qtdoc -skip qtdocgallery -skip qtfeedback -skip qtgamepad -skip qtgraphicaleffects -skip qtlocation -skip qtmacextras -skip qtnetworkauth -skip qtpim -skip qtpurchasing -skip qtqa -skip qtremoteobjects -skip qtrepotools -skip qtscript -skip qtscxml -skip qtsensors -skip qtserialbus -skip qtserialport -skip qtspeech -skip qtsystems -skip qttools -skip qttranslations -skip qtvirtualkeyboard -skip qtwayland -skip qtwebchannel -skip qtwebengine -skip qtwebglplugin -skip qtwebsockets -skip qtwebview -skip qtwinextras -skip qtx11extras -no-dbus -skip doc

REM Configure
call ..\tqtc-qt5\configure.bat -v -xplatform ohos-clang ^
 -device-option CROSS_COMPILE=%LLVM_INSTALL_DIR%\bin ^
 -prefix /data/storage/el1/bundle/libs/arm64 ^
 -extprefix c:\Qt\qt-5.12.12-ohos ^
 -opensource -confirm-license -debug ^
 -no-use-gold-linker %QT_SKIPS% ^
 -nomake tests -nomake examples ^
 -no-gcc-sysroot -c++std c++14 -ohos-arch arm64-v8a
```

### The Qt 5.15.16 skip list (leaner)

```
-skip doc -skip qtactiveqt -skip qtandroidextras -skip qtcanvas3d
-skip qtdoc -skip qtfeedback -skip qtgamepad -skip qtlocation
-skip qtmacextras -skip qtnetworkauth -skip qtpim -skip qtpurchasing
-skip qtqa -skip qtremoteobjects -skip qtrepotools -skip qtscript
-skip qtsystems -skip qttools -skip qtwayland -skip qtwebchannel
-skip qtwebengine -skip qtwebglplugin -skip qtwinextras -skip qtx11extras
-skip qtopcua -skip qtknx -skip qtconnectivity -skip coap
```

## OpenSSL configuration

If you need OpenSSL support, append this to configure:
```
-openssl-runtime -I"${QT_SOURCE_DIR_OPENSSL}" -ssl
```
Header source: [gitee.com/openharmony/third_party_openssl](https://gitee.com/openharmony/third_party_openssl/tree/master/include/)

## OpenGL configuration

- **Before this commit** (qtbase c5de1b3d): you must specify `-opengles3` explicitly
- **After this commit**:
  - Auto-detect: `./configure` with no such option
  - Force desktop OpenGL: `-opengl desktop`
  - Force OpenGL ES: `-opengl es2 -opengles3`

**Fixing a failed desktop OpenGL build**:
1. Make sure the SDK and device version are ≥ API 20
2. Download `libGLv4.so` from [gitee.com/inkuu/opengl](https://gitee.com/inkuu/opengl/tree/mesa_headers_all)
3. Copy it into the SDK at `sysroot/usr/lib/aarch64-linux-ohos/`, replacing the existing file
4. Rebuild
5. Set the `NEED_OPENGL` environment variable in `app.json5`

## Qt Creator kit configuration

### 1. Add the Qt version
Preferences → Kits → Qt Versions → Add → select the `qmake` your build produced

### 2. Configure the compiler
Compilers → Add → Custom → C:
- **Name**: OHOS Clang
- **Compiler path**: `<SDK>/native/llvm/bin/clang`
- **ABI**: `arm - linux - generic - elf - 64bit`

Do the same for C++, selecting `clang++` and naming it `OHOS Clang++`

### 3. Create the kit
Kits → Add → select the Qt version and compilers you configured above

### 4. Set the environment variable
Preferences → Environment → System → Change:
```
NATIVE_OHOS_SDK=<SDK path>/native
```

## Incremental Qt5 source builds and install

> After adding a diagnostic patch or logging, you need to rebuild Qt and install it into the SDK before your demo will link against the modified libqohos.so.
> For the initial full configure and build, see §The configure command above; this section focuses on **incremental builds + install** (the high-frequency operation when investigating framework problems).

### Windows (the primary environment)

Run this from **PowerShell or cmd**; from bash/git-bash, add `SHELL=cmd.exe` to override it — `mingw32-make` calls `/usr/bin/sh` by default, which treats backslash paths (`C:\...`) as escapes and swallows them, whereas `SHELL=cmd.exe` forces cmd.exe as the shell and works from bash, PowerShell, and cmd alike:

```powershell
# Take the build directory from ENV.md (QT5_12_BUILD; for 5.15 use ${QT_BUILD_ROOT}/build_5.15.16_arm64-v8a)
cd ${QT5_12_BUILD}
mingw32-make.exe SHELL=cmd.exe -j64 install
```

The `install` target propagates the build outputs (including the modified `libqohos.so` and the Qt5 module `.so` files) into the installed SDK (`QT5_12_OHOS_SDK`; the real value is in ENV.md). Rebuild your demo afterwards and it will link against the libqohos.so containing your logging/changes.

### macOS

```bash
cd <QT_BUILD_DIR>   # e.g. tqtc-qt5/build_arm64-v8a
make -j16 install
```

### The full chain (patch → logging takes effect)

```
Edit the source in the qtbase working tree (adding qOhosPrintfWarning, etc.)
  → mingw32-make install (PowerShell)
    → libqohos.so is updated in the SDK
      → rebuild the demo with hvigorw assembleHap
        → lib<app>.so links in the new libqohos.so
          → deploy to the device → capture logs with hilog
```

## Common pitfalls

| Symptom | Root cause | Fix |
|---------|------------|-----|
| You changed the source but hilog shows no new logs | You ran `make` without `install`, so libqohos.so in the SDK wasn't updated | The `install` target is mandatory |
| mingw32-make reports path errors in bash/git-bash | mingw32-make calls `/usr/bin/sh`, which swallows backslash paths | Add the `SHELL=cmd.exe` argument, or switch to PowerShell/cmd |
| The demo still links the old libqohos.so | You didn't rebuild the demo after install | Re-run `hvigorw assembleHap` after install |
| `mingw32-make: command not found` | MINGW_ROOT isn't on PATH | Add ENV.md's `MINGW_ROOT` to PATH |

> For the full process of building the Qt source with added logging to investigate framework problems, see phase two of the framework issue analysis methodology.

## References

- [Building Qt for HarmonyOS](https://wiki.qt.io/Building_Qt_for_HarmonyOS)
