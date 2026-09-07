#!/usr/bin/env bash
# kb-promote-drafts.sh — Post-merge draft promotion.
# Moves status:draft files from drafts/ to their formal directories,
# assigns final ids, regenerates indexes, and commits.
#
# Called by: kb-bot.py (post-merge), or manually by an editor.
# Usage: bash _scripts/kb-promote-drafts.sh [--dry-run] [--no-commit]
#
# Exit: 0 = success (or nothing to promote), 1 = error

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DRY_RUN=false
NO_COMMIT=false

for arg in "$@"; do
  case "$arg" in
    --dry-run)   DRY_RUN=true ;;
    --no-commit) NO_COMMIT=true ;;
    *)           printf 'Unknown option: %s\n' "$arg" >&2; exit 1 ;;
  esac
done

# --- Helpers ---

extract_fm_field() {
  local file="$1" field="$2"
  awk -v field="$field" '
    BEGIN { in_fm=0 }
    /^---[[:space:]]*$/ { in_fm++; next }
    in_fm == 1 && $0 ~ "^"field":" {
      sub("^"field":[[:space:]]*", "")
      gsub(/^["'\'']|["'\'']$/, "")
      print
      exit
    }
    in_fm >= 2 { exit }
  ' "$file"
}

set_fm_field() {
  local file="$1" field="$2" value="$3"
  local tmp
  tmp="$(mktemp)"
  awk -v field="$field" -v value="$value" '
    BEGIN { in_fm=0; done=0 }
    /^---[[:space:]]*$/ { in_fm++; print; next }
    in_fm == 1 && !done && $0 ~ "^"field":" {
      print field ": " value
      done=1
      next
    }
    { print }
  ' "$file" > "$tmp"
  mv "$tmp" "$file"
}

replace_fm_id() {
  local file="$1" new_id="$2"
  set_fm_field "$file" "id" "$new_id"
}

# --- Determine target directory from type ---
target_dir_for_type() {
  case "$1" in
    semantic)   echo "semantic" ;;
    procedural) echo "procedural" ;;
    episodic)   echo "episodic/postmortems" ;;
    problem)    echo "problems" ;;
    preference) echo "preference" ;;
    *)          echo "" ;;
  esac
}

# --- Main ---

shopt -s nullglob
DRAFTS=("$REPO_ROOT"/drafts/E*-*.md)

if [ ${#DRAFTS[@]} -eq 0 ]; then
  echo "No drafts to promote."
  exit 0
fi

PROMOTED=0
ERRORS=0
TIMESTAMP="$(date +%Y-%m-%d)"

for draft in "${DRAFTS[@]}"; do
  filename="$(basename "$draft")"
  status="$(extract_fm_field "$draft" "status")"

  # Only promote status:draft
  if [ "$status" != "draft" ]; then
    continue
  fi

  type="$(extract_fm_field "$draft" "type")"
  old_id="$(extract_fm_field "$draft" "id")"

  # Derive final slug: strip E{N}- prefix from filename
  final_slug="$(echo "$filename" | sed 's/^E[0-9]*-//; s/\.md$//')"

  # Derive final id: strip e{N}- prefix from id
  final_id="$(echo "$old_id" | sed 's/^e[0-9]*-//')"

  # Determine target
  target_dir="$(target_dir_for_type "$type")"
  if [ -z "$target_dir" ]; then
    printf 'ERROR: %s has unknown type "%s", cannot promote\n' "$filename" "$type" >&2
    ERRORS=$((ERRORS + 1))
    continue
  fi

  target_path="$REPO_ROOT/$target_dir/$final_id.md"

  # Check collision
  if [ -f "$target_path" ]; then
    printf 'ERROR: target %s already exists, skipping %s\n' "$target_dir/$final_id.md" "$filename" >&2
    ERRORS=$((ERRORS + 1))
    continue
  fi

  if [ "$DRY_RUN" = true ]; then
    printf '[DRY-RUN] %s -> %s/%s.md (id: %s)\n' "$filename" "$target_dir" "$final_id" "$final_id"
    PROMOTED=$((PROMOTED + 1))
    continue
  fi

  # Ensure target directory exists
  mkdir -p "$REPO_ROOT/$target_dir"

  # Update frontmatter: status -> active, id -> final_id
  set_fm_field "$draft" "status" "active"
  replace_fm_id "$draft" "$final_id"

  # Move file
  mv "$draft" "$target_path"

  # Write tombstone
  cat > "$REPO_ROOT/drafts/_promoted/$filename.promoted" <<EOF
original_file: drafts/$filename
promoted_to: $target_dir/$final_id.md
original_id: $old_id
final_id: $final_id
type: $type
promoted_at: $TIMESTAMP
EOF

  printf 'PROMOTED: %s -> %s/%s.md\n' "$filename" "$target_dir" "$final_id"
  PROMOTED=$((PROMOTED + 1))
done

if [ "$DRY_RUN" = true ]; then
  printf '\n[DRY-RUN] Would promote %d draft(s), %d error(s)\n' "$PROMOTED" "$ERRORS"
  exit 0
fi

if [ "$PROMOTED" -gt 0 ]; then
  # Regenerate indexes
  echo "Regenerating indexes..."
  bash "$REPO_ROOT/_scripts/kb-regen-indexes.sh"

  if [ "$NO_COMMIT" = false ]; then
    # Commit the promotion
    cd "$REPO_ROOT"
    git add drafts/ "$REPO_ROOT"/semantic/ "$REPO_ROOT"/procedural/ \
            "$REPO_ROOT"/episodic/ "$REPO_ROOT"/problems/ "$REPO_ROOT"/preference/ \
            "$REPO_ROOT"/_index/ 2>/dev/null || true
    git commit -m "ci(promote): $PROMOTED draft(s) promoted to formal directories"
    echo "Committed promotion."
  fi
fi

printf '\nDone: %d promoted, %d errors\n' "$PROMOTED" "$ERRORS"
[ "$ERRORS" -gt 0 ] && exit 1
exit 0
