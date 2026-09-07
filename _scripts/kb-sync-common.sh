#!/usr/bin/env bash
# kb-sync-common.sh — Vendor-bump ohos-common-kb-public/ from upstream.
# Fetches the latest public subset from su-meiyan/ohos-common-kb,
# diffs against vendored copy, and opens a PR if changed.
#
# Usage: bash _scripts/kb-sync-common.sh [--dry-run]
# Called by: kb-bot.py (nightly), or manually by an editor.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR_DIR="$REPO_ROOT/ohos-common-kb-public"
UPSTREAM_URL="https://gitcode.com/su-meiyan/ohos-common-kb.git"
DRY_RUN=false

[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

echo "=== kb-sync-common.sh ==="
echo "  Vendor dir: $VENDOR_DIR"
echo "  Upstream: $UPSTREAM_URL"

# Clone upstream to temp dir
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "  Fetching upstream..."
git clone --depth=1 "$UPSTREAM_URL" "$TMP_DIR/ohos-common-kb" 2>/dev/null

UPSTREAM_SHA="$(git -C "$TMP_DIR/ohos-common-kb" rev-parse HEAD)"
echo "  Upstream SHA: $UPSTREAM_SHA"

# Filter public pages (audience: public or no audience field)
SRC_DIR="$TMP_DIR/ohos-common-kb"
OUT_DIR="$TMP_DIR/filtered"
mkdir -p "$OUT_DIR"

# Copy all .md files that are audience:public or have no audience field
find "$SRC_DIR" -name "*.md" -not -path "*/.git/*" -not -path "*/_scripts/*" | while read -r f; do
  rel="${f#$SRC_DIR/}"
  # Check audience field
  aud="$(awk '/^---/{fm++;next} fm==1 && /^audience:/{sub(/^audience:[[:space:]]*/,"");print;exit}' "$f" 2>/dev/null || echo "")"
  if [ -z "$aud" ] || [ "$aud" = "public" ]; then
    mkdir -p "$OUT_DIR/$(dirname "$rel")"
    cp "$f" "$OUT_DIR/$rel"
  fi
done

# Diff against current vendor
if [ ! -d "$VENDOR_DIR" ]; then
  echo "  Vendor dir does not exist yet, creating..."
  CHANGED=true
else
  # Compare
  DIFF_OUT="$(diff -rq "$VENDOR_DIR" "$OUT_DIR" 2>/dev/null || true)"
  if [ -z "$DIFF_OUT" ]; then
    echo "  No changes detected. Vendor is up to date."
    exit 0
  fi
  CHANGED=true
  echo "  Changes detected:"
  echo "$DIFF_OUT" | head -20
fi

if [ "$DRY_RUN" = true ]; then
  echo "  [DRY-RUN] Would update vendor and open PR."
  exit 0
fi

# Update vendor directory
echo "  Updating vendor..."
rm -rf "$VENDOR_DIR"
cp -r "$OUT_DIR" "$VENDOR_DIR"

# Commit and create branch
cd "$REPO_ROOT"
BRANCH="bot/sync-common-$(date +%Y%m%d)"
git checkout -b "$BRANCH" 2>/dev/null || git checkout "$BRANCH"
git add ohos-common-kb-public/
git commit -m "chore(sync): bump ohos-common-kb-public to ${UPSTREAM_SHA:0:8}"

echo ""
echo "  Committed on branch: $BRANCH"
echo "  Push and create PR manually, or let kb-bot.py handle it."
echo "  git push origin $BRANCH"
