#!/usr/bin/env bash
# kb-release.sh — SemVer release for ohos_qt-skills canonical trunk.
# Generates CHANGELOG entry, updates RELEASE-MANIFEST.yaml, creates git tag.
#
# Usage:
#   bash _scripts/kb-release.sh --auto          # auto-detect bump level
#   bash _scripts/kb-release.sh --bump minor    # explicit bump
#   bash _scripts/kb-release.sh --version v3.1.0  # explicit version
#   bash _scripts/kb-release.sh --dry-run --auto  # preview only
#
# Called by: kb-bot.py (post-merge auto-release), or manually by an editor.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STATE_FILE="$REPO_ROOT/_scripts/RELEASE-STATE"
MANIFEST="$REPO_ROOT/RELEASE-MANIFEST.yaml"
CHANGELOG="$REPO_ROOT/CHANGELOG.md"

DRY_RUN=false
BUMP=""
VERSION=""
NOTES=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)  DRY_RUN=true; shift ;;
    --auto)     BUMP="auto"; shift ;;
    --bump)     BUMP="$2"; shift 2 ;;
    --version)  VERSION="$2"; shift 2 ;;
    --notes)    NOTES="$2"; shift 2 ;;
    *)          printf 'Unknown option: %s\n' "$1" >&2; exit 1 ;;
  esac
done

# --- Read current version ---
if [ -f "$STATE_FILE" ]; then
  CURRENT_VERSION="$(awk -F= '$1=="version"{print $2}' "$STATE_FILE")"
else
  CURRENT_VERSION="v3.0.0"
fi

# Parse semver
parse_version() {
  local v="${1#v}"
  MAJOR="$(echo "$v" | cut -d. -f1)"
  MINOR="$(echo "$v" | cut -d. -f2)"
  PATCH="$(echo "$v" | cut -d. -f3)"
}

parse_version "$CURRENT_VERSION"

# --- Auto-detect bump level ---
if [ "$BUMP" = "auto" ]; then
  # Get last tag
  LAST_TAG="$(git -C "$REPO_ROOT" describe --tags --abbrev=0 2>/dev/null || echo "")"
  if [ -z "$LAST_TAG" ]; then
    BUMP="minor"
  else
    CHANGED="$(git -C "$REPO_ROOT" diff --name-only "$LAST_TAG"..HEAD 2>/dev/null || echo "")"
    if echo "$CHANGED" | grep -qE '^(kb\.yaml|_scripts/kb-gate|_scripts/verify|CLAUDE\.md|AGENTS\.md)'; then
      BUMP="major"
    elif echo "$CHANGED" | grep -qE '^(semantic|procedural|episodic|preference)/.*\.md$'; then
      BUMP="minor"
    else
      BUMP="patch"
    fi
  fi
fi

# --- Calculate new version ---
if [ -n "$VERSION" ]; then
  NEW_VERSION="${VERSION#v}"
else
  case "$BUMP" in
    major) NEW_VERSION="$((MAJOR + 1)).0.0" ;;
    minor) NEW_VERSION="$MAJOR.$((MINOR + 1)).0" ;;
    patch) NEW_VERSION="$MAJOR.$MINOR.$((PATCH + 1))" ;;
    *)     printf 'ERROR: invalid bump level: %s\n' "$BUMP" >&2; exit 1 ;;
  esac
fi

NEW_TAG="v$NEW_VERSION"
TODAY="$(date +%Y-%m-%d)"

printf 'Release: %s -> %s (%s)\n' "$CURRENT_VERSION" "$NEW_TAG" "${BUMP:-explicit}"

if [ "$DRY_RUN" = true ]; then
  printf '[DRY-RUN] Would release %s\n' "$NEW_TAG"
  exit 0
fi

# --- Generate CHANGELOG entry ---
LAST_TAG="$(git -C "$REPO_ROOT" describe --tags --abbrev=0 2>/dev/null || echo "")"
if [ -n "$LAST_TAG" ]; then
  COMMIT_LOG="$(git -C "$REPO_ROOT" log --oneline "$LAST_TAG"..HEAD --no-merges 2>/dev/null | head -30)"
else
  COMMIT_LOG="$(git -C "$REPO_ROOT" log --oneline -10 --no-merges 2>/dev/null)"
fi

CHANGELOG_ENTRY="## $NEW_TAG ($TODAY)

"
if [ -n "$NOTES" ]; then
  CHANGELOG_ENTRY+="**$NOTES**

"
fi
CHANGELOG_ENTRY+="### Changes

$COMMIT_LOG
"

# Prepend to CHANGELOG (after the header line)
if [ -f "$CHANGELOG" ]; then
  TMP_CL="$(mktemp)"
  head -1 "$CHANGELOG" > "$TMP_CL"
  echo "" >> "$TMP_CL"
  echo "$CHANGELOG_ENTRY" >> "$TMP_CL"
  tail -n +2 "$CHANGELOG" >> "$TMP_CL"
  mv "$TMP_CL" "$CHANGELOG"
else
  printf '# Changelog\n\n%s\n' "$CHANGELOG_ENTRY" > "$CHANGELOG"
fi

# --- Update RELEASE-MANIFEST.yaml ---
CONTENT_SHA="$(find "$REPO_ROOT" -type f \
  -not -path '*/.git/*' \
  -not -path '*/_scripts/*' \
  -not -name 'RELEASE-MANIFEST.yaml' \
  | sort | xargs sha256sum 2>/dev/null | sha256sum | cut -d' ' -f1)"

ROOT_COMMIT="$(git -C "$REPO_ROOT" rev-parse HEAD)"

# Count pages
QT_PAGES="$(find "$REPO_ROOT"/semantic "$REPO_ROOT"/procedural "$REPO_ROOT"/episodic "$REPO_ROOT"/preference "$REPO_ROOT"/problems -name '*.md' -not -name '_index.md' 2>/dev/null | wc -l)"
COMMON_PAGES="$(find "$REPO_ROOT"/ohos-common-kb-public -name '*.md' 2>/dev/null | wc -l)"

cat > "$MANIFEST" <<EOF
# RELEASE-MANIFEST.yaml - Qt for HarmonyOS KB (canonical trunk)
# Generated: $TODAY by kb-release.sh (builder v3, schema v1)

release_version: $NEW_TAG
released_at: "$TODAY"
target:
  id: ohos_qt-skills
  type: kb
  kb_id: ohos-qt-kb
  mode: canonical-trunk
root_commit: "$ROOT_COMMIT"
builder_version: 3
publication_schema_version: 1
content_tree_sha256: $CONTENT_SHA
embedded_dependencies:
  ohos-common-kb-public:
    content_tree_sha256: $(find "$REPO_ROOT/ohos-common-kb-public" -type f 2>/dev/null | sort | xargs sha256sum 2>/dev/null | sha256sum | cut -d' ' -f1)
skills: ["kb-init"]
page_counts:
  qt: $QT_PAGES
  common: $COMMON_PAGES
EOF

# --- Update RELEASE-STATE ---
cat > "$STATE_FILE" <<EOF
version=$NEW_VERSION
released_at=$TODAY
EOF

# --- Commit + tag ---
cd "$REPO_ROOT"
git add CHANGELOG.md RELEASE-MANIFEST.yaml _scripts/RELEASE-STATE
git commit -m "release $NEW_TAG @ $TODAY"
git tag "$NEW_TAG"

printf '\nReleased %s successfully.\n' "$NEW_TAG"
printf 'Push with: git push origin main --tags\n'
