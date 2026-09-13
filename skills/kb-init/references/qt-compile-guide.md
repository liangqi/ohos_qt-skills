# Guide to building Qt from source

This document explains in detail how to build the Qt for HarmonyOS SDK from source; it applies to users with a Qt commercial license.

## Prerequisites

Building the Qt source requires these tools:

| Tool | Purpose | How to install |
|------|---------|----------------|
| **cmake** | Build system | macOS: `brew install cmake`<br>Windows: https://cmake.org/download/<br>Linux: `sudo apt install cmake` |
| **clang/llvm** | Cross-compiler | Installed with the OHOS SDK (bundled with DevEco Studio) |
| **MinGW** | Windows compiler | Windows only: https://www.mingw-w64.org/ |
| **Strawberry Perl** | Qt build scripts | Windows only: https://strawberryperl.com/ |
| **PowerShell** | Windows build environment | Ships with Windows |

## Build process overview

```
1. Prepare the source (clone + submodules)
2. Configure the cross-compilation environment (set environment variables)
3. Run configure (generates the Makefiles)
4. Build (make/mingw32-make)
5. Install (make install)
```

## Detailed steps

### Step 1: prepare the source

```bash
# Clone the source (using your Qt credentials)
git clone --branch tqtc/harmonyos-5.12.12 --single-branch \
  https://<username>:<password>@codereview.qt-project.org/qt/tqtc-qt5 \
  workspace/qt-src/qt5.12

cd workspace/qt-src/qt5.12

# Initialize the submodules (required — QtOhosExtras lives in a submodule)
git submodule update --init --recursive
```

**Verify**: check that the `qtbase/` and `qtohosextras/` directories exist.

### Step 2: configure the environment variables

**macOS / Linux**:
```bash
export NATIVE_OHOS_SDK="/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/native"
export OHOS_SDK_SYSROOT="$NATIVE_OHOS_SDK/sysroot"
export LLVM_INSTALL_DIR="$NATIVE_OHOS_SDK/llvm"
```

**Windows (PowerShell)**:
```powershell
$env:NATIVE_OHOS_SDK = "C:\Program Files\Huawei\DevEco Studio\sdk\default\openharmony\native"
$env:OHOS_SDK_SYSROOT = "$env:NATIVE_OHOS_SDK\sysroot"
$env:LLVM_INSTALL_DIR = "$env:NATIVE_OHOS_SDK\llvm"
```

**Verify**:
```bash
ls $NATIVE_OHOS_SDK/llvm/bin/clang    # macOS/Linux
dir $env:NATIVE_OHOS_SDK\llvm\bin\clang.exe  # Windows PowerShell
```

### Step 3: run configure

Change into the source directory and run the configure script:

**macOS / Linux**:
```bash
cd workspace/qt-src/qt5.12

./configure -xplatform ohos-clang \
  -release \
  -opengl desktop \
  -prefix "$(pwd)/../qt-sdk/Qt5.12.12-arm64-v8a" \
  -nomake examples \
  -nomake tests \
  -skip qtwebengine
```

**Windows (PowerShell)**:
```powershell
cd workspace\qt-src\qt5.12

configure.bat -xplatform ohos-clang `
  -release `
  -opengl desktop `
  -prefix "$(Get-Location)\..\qt-sdk\Qt5.12.12-arm64-v8a" `
  -nomake examples `
  -nomake tests `
  -skip qtwebengine
```

#### configure options explained

| Option | Description | Possible values |
|--------|-------------|-----------------|
| `-xplatform` | Cross-compilation platform | `ohos-clang` (fixed) |
| `-release` | Build type | `-release` (optimized) or `-debug` (debug build) |
| `-opengl` | Rendering backend | `desktop` (Desktop GL) or `es2` (GLES) |
| `-prefix` | SDK installation path | Any directory |
| `-nomake examples` | Skip building the examples | Recommended; speeds up the build |
| `-nomake tests` | Skip building the tests | Recommended; speeds up the build |
| `-skip qtwebengine` | Skip WebEngine | Recommended; HarmonyOS doesn't support it |

#### Common configure errors

**Error 1**: `Cannot find feature spec_post.prf`
- **Cause**: the submodules weren't initialized
- **Fix**: `git submodule update --init --recursive`

**Error 2**: `clang not found`
- **Cause**: the environment variables aren't set
- **Fix**: check that `$LLVM_INSTALL_DIR/bin/clang` exists

**Error 3**: `sysroot not found`
- **Cause**: the OHOS SDK path is wrong
- **Fix**: check that `$OHOS_SDK_SYSROOT` points at the right directory

### Step 4: build

**macOS / Linux**:
```bash
make -j$(sysctl -n hw.ncpu 2>/dev/null || nproc 2>/dev/null || echo 4)
```

**Windows (PowerShell)**:
```powershell
mingw32-make -j8
```

> ⚠️ **On Windows you must build from PowerShell** — you cannot run mingw32-make in Git Bash.

Build time: 30–60 minutes (depending on your CPU core count).

#### Common build errors

**Error 1**: `undefined reference to xxx`
- **Cause**: a missing link library
- **Fix**: check the configure output and confirm all dependency libraries were found

**Error 2**: `mingw32-make: *** [xxx] Error 2`
- **Cause**: an error mid-build
- **Fix**: read the specific error above it; it's usually a source or environment problem

**Error 3**: `fatal error: xxx.h: No such file or directory`
- **Cause**: a wrong header path
- **Fix**: check that the OHOS SDK sysroot is complete

### Step 5: install

**macOS / Linux**:
```bash
make install
```

**Windows (PowerShell)**:
```powershell
mingw32-make install
```

Once installation finishes, the SDK appears in the directory given by `-prefix`.

**Verify**:
```bash
ls workspace/qt-sdk/Qt5.12.12-arm64-v8a/
# You should see: bin/ include/ lib/ mkspecs/ plugins/ qml/
```

## Using the SDK you built

After the build, add the SDK path to `ENV.local.md`:

```markdown
| `QT5_12_OHOS_SDK` | `/Users/you/dev/qt-sdk/Qt5.12.12-arm64-v8a` |
```

Then use it in your Qt project:

```cmake
set(CMAKE_PREFIX_PATH "/Users/you/dev/qt-sdk/Qt5.12.12-arm64-v8a")
```

## Troubleshooting

### Problem: the build is very slow

- **Fix**: increase parallelism with `-j16` or `-j32` (depending on your CPU core count)
- **Optimization**: use `-nomake examples -nomake tests -skip qtwebengine`

### Problem: not enough disk space

- The Qt source is about 3 GB, the build outputs about 5 GB, and the SDK about 2 GB
- **Fix**: make sure you have at least 15 GB free

### Problem: submodule initialization fails

- **Cause**: a network problem or wrong credentials
- **Fix**:
  ```bash
  git submodule sync
  git submodule update --init --recursive
  ```

### Problem: some modules can't be found after configure

- **Cause**: some Qt modules depend on system libraries
- **Fix**: use `-skip` to skip the modules you don't need, for example:
  ```bash
  -skip qtwebengine -skip qtwayland -skip qtlocation
  ```

### Problem: path errors when building on Windows

- **Cause**: running mingw32-make in Git Bash
- **Fix**: you must build from PowerShell

## Automating the build

The `compile-qt-sdk.sh` script automates the process above:

```bash
bash skills/kb-init/scripts/compile-qt-sdk.sh \
  --src=workspace/qt-src/qt5.12 \
  --dest=workspace/qt-sdk \
  --render=gl \
  --build-type=release \
  --ohos-sdk-native=/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/native
```

The script runs configure → make → make install automatically.

**Note**: on Windows the script can't run the build itself (it must run in PowerShell), so it prints the PowerShell commands for you to run manually.
