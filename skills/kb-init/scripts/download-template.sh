#!/bin/bash
# download-template.sh — download the HarmonyOS project template archive templates-0625.zip
#
# When to use: when you have no Qt source tree (only a prebuilt SDK, or building on a HarmonyOS PC),
# download the template archive separately from the GitCode releases page.
#
# Download page: https://gitcode.com/ohos-qt/qt-harmonyos-src/releases
# Archive name: templates-0625.zip
#
# Usage:
#   bash download-template.sh --dest=<directory> [--url=<custom download URL>]
#
# Exit codes: 0=success, 1=bad arguments, 2=download failed

set -uo pipefail

DEST=""
CUSTOM_URL=""

for arg in "$@"; do
  case "$arg" in
    --dest=*) DEST="${arg#*=}" ;;
    --url=*)  CUSTOM_URL="${arg#*=}" ;;
    *) echo "Unknown argument: $arg"; exit 1 ;;
  esac
done

if [ -z "$DEST" ]; then
  echo "ERROR: --dest=<directory> is required"
  echo "Usage: bash download-template.sh --dest=<directory> [--url=<download URL>]"
  exit 1
fi

RELEASES_URL="https://gitcode.com/ohos-qt/qt-harmonyos-src/releases"
ARCHIVE_NAME="templates-0625.zip"

echo "--- HarmonyOS project template download ---"
echo "  Target: $DEST"
echo "  Archive: $ARCHIVE_NAME"
echo ""

if [ -d "$DEST/entry" ] && [ -f "$DEST/build-profile.json5" ]; then
  echo "STATUS=already-exists"
  echo "Template directory already exists: $DEST"
  echo "OHOS_TEMPLATE_SRC=$DEST"
  exit 0
fi

mkdir -p "$DEST"

DOWNLOAD_URL=""
if [ -n "$CUSTOM_URL" ]; then
  DOWNLOAD_URL="$CUSTOM_URL"
else
  API_URL="https://gitcode.com/api/v5/repos/ohos-qt/qt-harmonyos-src/releases"
  echo "Querying the releases API: $API_URL"
  ASSET_URL=$(curl -fsSL "$API_URL" 2>/dev/null | \
    grep -o "\"browser_download_url\":\"[^\"]*${ARCHIVE_NAME}\"" | \
    head -1 | \
    sed 's/"browser_download_url":"//;s/"$//')

  if [ -n "$ASSET_URL" ]; then
    DOWNLOAD_URL="$ASSET_URL"
  else
    echo "STATUS=need-manual"
    echo ""
    echo "Could not determine the download link automatically. Please do it manually:"
    echo "  1. Go to $RELEASES_URL"
    echo "  2. Find $ARCHIVE_NAME and download it"
    echo "  3. Pass the downloaded file path to this script:"
    echo "     bash download-template.sh --dest=$DEST --url=file:///path/to/$ARCHIVE_NAME"
    echo ""
    echo "Or extract it manually into: $DEST"
    exit 2
  fi
fi

echo "Downloading: $DOWNLOAD_URL"
TMPFILE=$(mktemp)
if curl -fSL --progress-bar -o "$TMPFILE" "$DOWNLOAD_URL"; then
  echo "Download complete"
else
  echo "ERROR: download failed: $DOWNLOAD_URL"
  rm -f "$TMPFILE"
  echo ""
  echo "Please download it manually:"
  echo "  1. Go to $RELEASES_URL"
  echo "  2. Download $ARCHIVE_NAME"
  echo "  3. Run: bash download-template.sh --dest=$DEST --url=file:///path/to/$ARCHIVE_NAME"
  exit 2
fi

echo "Extracting..."
case "$(basename "$DOWNLOAD_URL")" in
  *.zip)
    unzip -q -o "$TMPFILE" -d "$DEST" ;;
  *.tar.gz|*.tgz)
    tar xzf "$TMPFILE" -C "$DEST" ;;
  *)
    unzip -q -o "$TMPFILE" -d "$DEST" 2>/dev/null || tar xzf "$TMPFILE" -C "$DEST" ;;
esac
rm -f "$TMPFILE"

if [ -d "$DEST/entry" ] && [ -f "$DEST/build-profile.json5" ]; then
  echo "Extraction complete: $DEST"
  echo ""
  echo "STATUS=installed"
  echo "OHOS_TEMPLATE_SRC=$DEST"
  echo ""
  echo "Template directory structure:"
  echo "  $DEST/"
  ls -1 "$DEST" | sed 's/^/  ├── /'
else
  NESTED=$(find "$DEST" -maxdepth 2 -name "build-profile.json5" -exec dirname {} \; | head -1)
  if [ -n "$NESTED" ] && [ "$NESTED" != "$DEST" ]; then
    echo "The template is in a subdirectory; moving it..."
    mv "$NESTED"/* "$DEST"/ 2>/dev/null
    mv "$NESTED"/.* "$DEST"/ 2>/dev/null
    rmdir "$NESTED" 2>/dev/null
    echo "STATUS=installed"
    echo "OHOS_TEMPLATE_SRC=$DEST"
  else
    echo "WARN: extraction finished but the expected directory structure was not found"
    echo "Please check: $DEST"
    echo "STATUS=extracted-unverified"
  fi
fi
