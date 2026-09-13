#!/bin/bash
# compile-qt-sdk.sh — build the Qt OHOS SDK from source
#
# Usage: bash skills/kb-init/scripts/compile-qt-sdk.sh \
#         --src=<Qt source directory> \
#         --dest=<SDK output directory> \
#         --render=<gl|gles> \
#         --build-type=<release|debug> \
#         --ohos-sdk-native=<OHOS SDK native path>
# Output: QT_OHOS_SDK=<SDK path>
# Exit codes: 0=success, 1=failure

set -uo pipefail

SRC=""
DEST=""
RENDER="gl"
BUILD_TYPE="release"
OHOS_SDK_NATIVE=""

for arg in "$@"; do
  case "$arg" in
    --src=*) SRC="${arg#*=}";;
    --dest=*) DEST="${arg#*=}";;
    --render=*) RENDER="${arg#*=}";;
    --build-type=*) BUILD_TYPE="${arg#*=}";;
    --ohos-sdk-native=*) OHOS_SDK_NATIVE="${arg#*=}";;
    *) echo "Unknown option: $arg" >&2; exit 2;;
  esac
done

if [ -z "$SRC" ] || [ -z "$DEST" ] || [ -z "$OHOS_SDK_NATIVE" ]; then
  echo "Usage: bash compile-qt-sdk.sh --src=<source> --dest=<output> --render=<gl|gles> --build-type=<release|debug> --ohos-sdk-native=<path>"
  exit 2
fi

# Detect the OS
OS="unknown"
case "$(uname -s)" in
  Darwin*) OS="macos";;
  Linux*)  OS="linux";;
  MINGW*|MSYS*|CYGWIN*) OS="windows";;
esac

echo "--- Qt OHOS SDK build ---"
echo "  Source: $SRC"
echo "  Output: $DEST"
echo "  Rendering: $RENDER"
echo "  Build type: $BUILD_TYPE"
echo "  Platform: $OS"
echo "  OHOS SDK: $OHOS_SDK_NATIVE"
echo ""

# Check the source
if [ ! -d "$SRC/qtbase" ]; then
  echo "FAIL: invalid Qt source directory (no qtbase/): $SRC"
  exit 1
fi

# Check the build tools
if [ "$OS" = "windows" ]; then
  if ! command -v mingw32-make &>/dev/null; then
    echo "FAIL: mingw32-make is not installed"
    echo "  Install MinGW: https://www.mingw-w64.org/"
    exit 1
  fi
  if ! command -v perl &>/dev/null; then
    echo "FAIL: perl is not installed"
    echo "  Install Strawberry Perl: https://strawberryperl.com/"
    exit 1
  fi
  if ! command -v powershell.exe &>/dev/null && ! command -v pwsh &>/dev/null; then
    echo "FAIL: PowerShell not found"
    echo "  Building Qt on Windows must be done from PowerShell"
    exit 1
  fi
fi

if ! command -v cmake &>/dev/null; then
  echo "FAIL: cmake is not installed"
  echo "  macOS: brew install cmake"
  echo "  Windows: https://cmake.org/download/"
  echo "  Linux: sudo apt install cmake"
  exit 1
fi

# Check the OHOS SDK
if [ ! -d "$OHOS_SDK_NATIVE/llvm/bin" ]; then
  echo "FAIL: invalid OHOS SDK native path (no llvm/bin/): $OHOS_SDK_NATIVE"
  exit 1
fi

# Determine the Qt version (inferred from the source directory name)
QT_VERSION="5.12"
echo "$SRC" | grep -q "5.15" && QT_VERSION="5.15"

# SDK output directory name
SDK_DIR_NAME="Qt${QT_VERSION}.12-arm64-v8a"
[ "$QT_VERSION" = "5.15" ] && SDK_DIR_NAME="Qt5.15.16-arm64-v8a"
[ "$RENDER" = "gles" ] && SDK_DIR_NAME="${SDK_DIR_NAME}-gles"
[ "$BUILD_TYPE" = "debug" ] && SDK_DIR_NAME="${SDK_DIR_NAME}-debug"

SDK_OUTPUT="$DEST/$SDK_DIR_NAME"
BUILD_DIR="$DEST/build-$SDK_DIR_NAME"

echo "  SDK output: $SDK_OUTPUT"
echo "  Build directory: $BUILD_DIR"
echo ""

# Create the directories
mkdir -p "$BUILD_DIR"
mkdir -p "$SDK_OUTPUT"

# Set the cross-compilation environment variables
export NATIVE_OHOS_SDK="$OHOS_SDK_NATIVE"
export OHOS_SDK_SYSROOT="$OHOS_SDK_NATIVE/sysroot"
export LLVM_INSTALL_DIR="$OHOS_SDK_NATIVE/llvm"

echo "Environment variables set:"
echo "  NATIVE_OHOS_SDK=$NATIVE_OHOS_SDK"
echo "  OHOS_SDK_SYSROOT=$OHOS_SDK_SYSROOT"
echo "  LLVM_INSTALL_DIR=$LLVM_INSTALL_DIR"
echo ""

# Build the configure arguments
CONFIGURE_ARGS=""
[ "$BUILD_TYPE" = "debug" ] && CONFIGURE_ARGS="$CONFIGURE_ARGS -debug" || CONFIGURE_ARGS="$CONFIGURE_ARGS -release"
[ "$RENDER" = "gles" ] && CONFIGURE_ARGS="$CONFIGURE_ARGS -opengl es2" || CONFIGURE_ARGS="$CONFIGURE_ARGS -opengl desktop"

echo "=== Starting the build ==="
echo "  This may take 30-60 minutes; please be patient..."
echo ""

if [ "$OS" = "windows" ]; then
  # Windows: the build must run in PowerShell
  echo "On Windows, the build must be run from PowerShell."
  echo "Open PowerShell and run the following commands:"
  echo ""
  echo "  cd $SRC"
  echo "  \$env:NATIVE_OHOS_SDK = \"$OHOS_SDK_NATIVE\""
  echo "  \$env:OHOS_SDK_SYSROOT = \"\$env:NATIVE_OHOS_SDK/sysroot\""
  echo "  \$env:LLVM_INSTALL_DIR = \"\$env:NATIVE_OHOS_SDK/llvm\""
  echo "  configure.bat -xplatform ohos-clang $CONFIGURE_ARGS -prefix $SDK_OUTPUT"
  echo "  mingw32-make -j8"
  echo "  mingw32-make install"
  echo ""
  echo "Once the build finishes, the SDK will be at: $SDK_OUTPUT"
  echo ""
  echo "QT_OHOS_SDK=$SDK_OUTPUT"
  echo ""
  echo "Note: this script cannot run the Windows build automatically from Git Bash."
  echo "Run the commands above manually in PowerShell, then run verify-env.sh again to validate."
  exit 0
fi

# macOS / Linux: we can build directly
cd "$SRC"

echo "Step 1/3: configure..."
./configure -xplatform ohos-clang $CONFIGURE_ARGS \
  -prefix "$SDK_OUTPUT" \
  -nomake examples -nomake tests \
  -skip qtwebengine 2>&1 | tail -20

rc=$?
if [ $rc -ne 0 ]; then
  echo ""
  echo "FAIL: configure failed (exit $rc)"
  echo "  Check the error messages above"
  exit 1
fi

echo ""
echo "Step 2/3: make (this may take 30-60 minutes)..."
make -j$(sysctl -n hw.ncpu 2>/dev/null || nproc 2>/dev/null || echo 4) 2>&1 | tail -5

rc=$?
if [ $rc -ne 0 ]; then
  echo ""
  echo "FAIL: make failed (exit $rc)"
  echo "  Check the error messages above"
  exit 1
fi

echo ""
echo "Step 3/3: make install..."
make install 2>&1 | tail -5

rc=$?
if [ $rc -ne 0 ]; then
  echo ""
  echo "FAIL: make install failed (exit $rc)"
  exit 1
fi

echo ""
echo "=== Build complete ==="
echo "QT_OHOS_SDK=$SDK_OUTPUT"
echo ""
echo "The SDK has been installed to: $SDK_OUTPUT"
