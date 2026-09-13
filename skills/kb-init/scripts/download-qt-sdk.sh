#!/bin/bash
# download-qt-sdk.sh — download the prebuilt Qt OHOS SDK
#
# Usage: bash skills/kb-init/scripts/download-qt-sdk.sh --platform=<macos|windows|linux> --dest=<directory>
# Output: downloads and extracts the SDK, then prints QT5_12_OHOS_SDK=<path>
# Exit codes: 0=success, 1=failure

set -uo pipefail

PLATFORM=""
DEST=""

for arg in "$@"; do
  case "$arg" in
    --platform=*) PLATFORM="${arg#*=}";;
    --dest=*) DEST="${arg#*=}";;
    *) echo "Unknown option: $arg" >&2; exit 2;;
  esac
done

if [ -z "$PLATFORM" ] || [ -z "$DEST" ]; then
  echo "Usage: bash download-qt-sdk.sh --platform=<macos|windows|linux> --dest=<directory>"
  exit 2
fi

RELEASES_URL="https://gitcode.com/ohos-qt/qt-harmonyos-src/releases"

echo "--- Qt OHOS SDK download ---"
echo "  Platform: $PLATFORM"
echo "  Target: $DEST"
echo ""

# Create the target directory
mkdir -p "$DEST"

# GitCode releases page URL
echo "Querying available SDK versions..."
echo ""

# Determine the keyword based on the platform
case "$PLATFORM" in
  macos)   KEYWORD="macos";;
  windows) KEYWORD="windows";;
  linux)   KEYWORD="linux";;
  *) echo "Unsupported platform: $PLATFORM"; exit 1;;
esac

# Try to get release information through the GitCode API
API_URL="https://gitcode.com/api/v5/repos/ohos-qt/qt-harmonyos-src/releases?per_page=10"
RELEASES_JSON=""
if command -v curl &>/dev/null; then
  RELEASES_JSON=$(curl -sL "$API_URL" 2>/dev/null || true)
elif command -v wget &>/dev/null; then
  RELEASES_JSON=$(wget -qO- "$API_URL" 2>/dev/null || true)
fi

# Parse the release assets
if [ -n "$RELEASES_JSON" ] && echo "$RELEASES_JSON" | grep -q "browser_download_url"; then
  echo "Found the following available SDK packages:"
  echo ""

  # Extract all download URLs and names
  DOWNLOAD_URLS=$(echo "$RELEASES_JSON" | grep -o '"browser_download_url":"[^"]*"' | sed 's/"browser_download_url":"//;s/"$//')
  ASSET_NAMES=$(echo "$RELEASES_JSON" | grep -o '"name":"[^"]*"' | sed 's/"name":"//;s/"$//')

  # List them and match the platform
  MATCHED_URL=""
  MATCHED_NAME=""
  INDEX=0
  while IFS= read -r url; do
    name=$(echo "$ASSET_NAMES" | sed -n "$((INDEX + 1))p")
    # Check whether it matches the platform
    if echo "$url" | grep -qi "$KEYWORD"; then
      echo "  [$INDEX] $name"
      echo "      $url"
      if [ -z "$MATCHED_URL" ]; then
        MATCHED_URL="$url"
        MATCHED_NAME="$name"
      fi
    fi
    INDEX=$((INDEX + 1))
  done <<< "$DOWNLOAD_URLS"

  if [ -z "$MATCHED_URL" ]; then
    echo ""
    echo "No SDK package matching the $PLATFORM platform was found."
    echo "Please download it manually from $RELEASES_URL."
    exit 1
  fi

  echo ""
  echo "About to download: $MATCHED_NAME"
  echo "Download URL: $MATCHED_URL"
  echo ""
else
  echo "Could not retrieve release information through the API."
  echo "Please download the SDK for your platform manually from $RELEASES_URL."
  echo ""
  echo "After downloading, extract the SDK into: $DEST"
  echo "Then run the initialization skill again."
  exit 1
fi

# Download
DOWNLOAD_FILE="$DEST/$MATCHED_NAME"
echo "Downloading..."
if command -v curl &>/dev/null; then
  curl -L -o "$DOWNLOAD_FILE" "$MATCHED_URL"
elif command -v wget &>/dev/null; then
  wget -O "$DOWNLOAD_FILE" "$MATCHED_URL"
fi

if [ ! -f "$DOWNLOAD_FILE" ]; then
  echo "Download failed. Please download it manually: $MATCHED_URL"
  exit 1
fi

echo "Download complete: $DOWNLOAD_FILE"
echo ""

# Extract
echo "Extracting..."
case "$MATCHED_NAME" in
  *.zip)
    unzip -q -o "$DOWNLOAD_FILE" -d "$DEST"
    ;;
  *.tar.gz|*.tgz)
    tar xzf "$DOWNLOAD_FILE" -C "$DEST"
    ;;
  *.tar.xz)
    tar xJf "$DOWNLOAD_FILE" -C "$DEST"
    ;;
  *.7z)
    if command -v 7z &>/dev/null; then
      7z x "$DOWNLOAD_FILE" -o"$DEST" -y >/dev/null
    else
      echo "7z is required to extract .7z files. Please install p7zip or extract manually."
      exit 1
    fi
    ;;
  *)
    echo "Unknown archive format: $MATCHED_NAME"
    echo "Please extract it manually into: $DEST"
    exit 1
    ;;
esac

echo "Extraction complete."
echo ""

# Locate the extracted SDK directory
SDK_PATH=""
for d in "$DEST"/Qt5.12* "$DEST"/qt5.12* "$DEST"/Qt5.15* "$DEST"/qt5.15*; do
  if [ -d "$d" ]; then
    SDK_PATH="$d"
    break
  fi
done

# If no standard directory name was found, take the first extracted subdirectory
if [ -z "$SDK_PATH" ]; then
  SDK_PATH=$(find "$DEST" -mindepth 1 -maxdepth 1 -type d | head -1)
fi

if [ -n "$SDK_PATH" ]; then
  echo "QT5_12_OHOS_SDK=$SDK_PATH"
  echo ""
  echo "SDK is ready: $SDK_PATH"
else
  echo "Could not locate the extracted SDK directory. Please check: $DEST"
  exit 1
fi
