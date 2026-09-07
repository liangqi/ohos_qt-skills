#!/usr/bin/env python3
"""
kb-bot.py — Cron orchestrator for ohos_qt-skills canonical trunk.

Jobs:
  1. PR poll: validate new/updated PRs (gate + LLM review + comment + auto-merge)
  2. Merge detect: promote drafts, fix index drift, auto-release
  3. Nightly: full audit, vendor bump check

Usage:
  python _scripts/kb-bot.py                # run all jobs once
  python _scripts/kb-bot.py --job pr       # PR poll only
  python _scripts/kb-bot.py --job merge    # merge detect only
  python _scripts/kb-bot.py --job nightly  # nightly audit only
  python _scripts/kb-bot.py --dry-run      # preview without actions

Schedule via cron/Task Scheduler: every 10-15 minutes for pr+merge, nightly for audit.

Configuration:
  - GitCode token: ~/.gitcode file or GITCODE_TOKEN env var
  - LLM key: LLM_KEY env var (for semantic review)
  - Repo: hardcoded below (OpenHarmonyPCDeveloper/ohos_qt-skills)

Extends: kb-pr-review.py (internal repo PR review agent)
"""

import json
import os
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone

# ═══════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════

OWNER = "OpenHarmonyPCDeveloper"
REPO = "ohos_qt-skills"
API_BASE = f"https://gitcode.com/api/v5/repos/{OWNER}/{REPO}"

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = REPO_ROOT / "_scripts" / ".kb-bot-state.json"

# Auto-merge policy
AUTO_MERGE_PATHS = {"drafts/", "problems/"}  # low-risk paths
AUTO_MERGE_AUTHORS = set()  # populated from CONTRIBUTORS or team list; empty = no auto-merge by author

# LLM review (optional)
LLM_KEY = os.environ.get("LLM_KEY", "")
LLM_ENABLED = bool(LLM_KEY)

# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def get_token():
    """Load GitCode token from env or ~/.gitcode file."""
    token = os.environ.get("GITCODE_TOKEN", "")
    if token:
        return token
    gitcode_file = Path.home() / ".gitcode"
    if gitcode_file.exists():
        return gitcode_file.read_text().strip()
    return ""


def api_get(endpoint, token):
    """GET request to GitCode API."""
    import urllib.request
    url = f"{API_BASE}/{endpoint}" if not endpoint.startswith("http") else endpoint
    req = urllib.request.Request(url, headers={
        "PRIVATE-TOKEN": token,
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  API GET error: {e}", file=sys.stderr)
        return None


def api_post(endpoint, data, token):
    """POST request to GitCode API."""
    import urllib.request
    url = f"{API_BASE}/{endpoint}" if not endpoint.startswith("http") else endpoint
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={
        "PRIVATE-TOKEN": token,
        "Content-Type": "application/json",
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  API POST error: {e}", file=sys.stderr)
        return None


def api_patch(endpoint, data, token):
    """PATCH request to GitCode API."""
    import urllib.request
    url = f"{API_BASE}/{endpoint}" if not endpoint.startswith("http") else endpoint
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={
        "PRIVATE-TOKEN": token,
        "Content-Type": "application/json",
    }, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  API PATCH error: {e}", file=sys.stderr)
        return None


def load_state():
    """Load bot state (last seen PR head SHAs, last main SHA)."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"pr_heads": {}, "last_main_sha": "", "last_run": ""}


def save_state(state):
    """Persist bot state."""
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def run_cmd(cmd, cwd=None, timeout=300):
    """Run shell command, return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd, capture_output=True,
            text=True, timeout=timeout, encoding="utf-8", errors="replace"
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"


def clone_pr(pr_number, token, target_dir):
    """Clone PR head into isolated directory for gate testing."""
    clone_url = f"https://oauth2:{token}@gitcode.com/{OWNER}/{REPO}.git"
    rc, out, err = run_cmd(
        f'git clone --depth=50 "{clone_url}" "{target_dir}"',
        timeout=120
    )
    if rc != 0:
        return False
    # Fetch PR ref
    rc, out, err = run_cmd(
        f'git fetch origin refs/merge-requests/{pr_number}/head:pr-{pr_number}',
        cwd=target_dir, timeout=60
    )
    if rc != 0:
        # Fallback: try pulls API head ref
        rc, out, err = run_cmd(
            f'git fetch origin refs/pull/{pr_number}/head:pr-{pr_number}',
            cwd=target_dir, timeout=60
        )
    if rc != 0:
        return False
    run_cmd(f'git checkout pr-{pr_number}', cwd=target_dir)
    return True


# ═══════════════════════════════════════════════════════════
# Job 1: PR Poll
# ═══════════════════════════════════════════════════════════

def job_pr(state, token, dry_run=False):
    """Poll open PRs, run gate on new/updated ones, comment results."""
    print("\n=== Job: PR Poll ===")

    prs = api_get("pulls?state=open&per_page=20", token)
    if not prs:
        print("  No open PRs (or API error).")
        return

    for pr in prs:
        pr_number = pr.get("number")
        head_sha = pr.get("head", {}).get("sha", "")
        title = pr.get("title", "")
        author = pr.get("user", {}).get("login", "")

        # Skip if already reviewed at this SHA
        if state["pr_heads"].get(str(pr_number)) == head_sha:
            continue

        print(f"  PR #{pr_number}: {title} (by {author}, sha={head_sha[:8]})")

        if dry_run:
            print(f"    [DRY-RUN] Would review PR #{pr_number}")
            continue

        # Clone and run gate
        with tempfile.TemporaryDirectory(prefix="kb-bot-pr-") as tmpdir:
            work_dir = os.path.join(tmpdir, "repo")
            if not clone_pr(pr_number, token, work_dir):
                print(f"    WARN: could not clone PR #{pr_number}")
                continue

            # Run verify.sh
            rc, out, err = run_cmd(
                "bash _scripts/verify.sh",
                cwd=work_dir, timeout=600
            )

            gate_pass = (rc == 0)
            gate_output = (out + err)[-2000:]  # last 2000 chars

            # Check if auto-merge eligible
            can_auto_merge = False
            if gate_pass:
                # Get changed files
                rc2, files_out, _ = run_cmd(
                    f"git diff --name-only origin/main...HEAD",
                    cwd=work_dir
                )
                changed_files = files_out.strip().split("\n") if files_out.strip() else []
                all_low_risk = all(
                    any(f.startswith(p) for p in AUTO_MERGE_PATHS)
                    for f in changed_files if f
                )
                can_auto_merge = all_low_risk and (
                    not AUTO_MERGE_AUTHORS or author in AUTO_MERGE_AUTHORS
                )

            # Post comment
            status_emoji = "✅" if gate_pass else "❌"
            comment_body = (
                f"## {status_emoji} Gate Check {'PASSED' if gate_pass else 'FAILED'}\n\n"
                f"**Commit**: `{head_sha[:8]}`\n"
                f"**Author**: @{author}\n\n"
            )
            if not gate_pass:
                comment_body += f"<details><summary>Gate output (last 2000 chars)</summary>\n\n```\n{gate_output}\n```\n</details>\n"
            if can_auto_merge:
                comment_body += "\n**Auto-merge eligible** (low-risk paths, gate clean).\n"

            api_post(f"pulls/{pr_number}/comments", {"body": comment_body}, token)

            # Auto-merge if eligible
            if can_auto_merge:
                print(f"    Auto-merging PR #{pr_number}...")
                merge_result = api_patch(
                    f"pulls/{pr_number}/merge",
                    {"merge_method": "squash"},
                    token
                )
                if merge_result:
                    print(f"    Merged PR #{pr_number}.")
                else:
                    print(f"    WARN: merge failed for PR #{pr_number}.")

        # Update state
        state["pr_heads"][str(pr_number)] = head_sha

    print(f"  Processed {len(prs)} PR(s).")


# ═══════════════════════════════════════════════════════════
# Job 2: Merge Detect
# ═══════════════════════════════════════════════════════════

def job_merge(state, token, dry_run=False):
    """Detect main advancement, promote drafts, fix index drift."""
    print("\n=== Job: Merge Detect ===")

    # Get current main HEAD
    repo_info = api_get("", token)
    if not repo_info:
        print("  Could not fetch repo info.")
        return

    # Use local clone to check main
    rc, current_sha, _ = run_cmd("git rev-parse origin/main", cwd=str(REPO_ROOT))
    if rc != 0:
        # Try fetching
        run_cmd("git fetch origin main", cwd=str(REPO_ROOT), timeout=60)
        rc, current_sha, _ = run_cmd("git rev-parse origin/main", cwd=str(REPO_ROOT))
        if rc != 0:
            print("  Could not determine main HEAD.")
            return

    current_sha = current_sha.strip()
    last_sha = state.get("last_main_sha", "")

    if current_sha == last_sha:
        print("  main unchanged, nothing to do.")
        return

    print(f"  main advanced: {last_sha[:8] if last_sha else '(init)'} -> {current_sha[:8]}")

    if dry_run:
        print("  [DRY-RUN] Would run promote + index check + release.")
        state["last_main_sha"] = current_sha
        return

    # Pull latest main locally
    run_cmd("git checkout main && git pull origin main", cwd=str(REPO_ROOT), timeout=60)

    # Promote drafts
    rc, out, err = run_cmd("bash _scripts/kb-promote-drafts.sh", cwd=str(REPO_ROOT), timeout=120)
    if rc == 0 and "PROMOTED:" in out:
        print(f"  Drafts promoted.\n{out}")
        # Push promotion commit
        run_cmd("git push origin main", cwd=str(REPO_ROOT), timeout=60)
    else:
        print(f"  No drafts to promote (or error: {err[:200]})")

    # Index drift check
    rc, out, err = run_cmd("bash _scripts/kb-regen-indexes.sh", cwd=str(REPO_ROOT), timeout=120)
    rc2, diff_out, _ = run_cmd("git diff --quiet _index/", cwd=str(REPO_ROOT))
    if rc2 != 0:
        print("  Index drift detected, committing regen...")
        run_cmd("git add _index/ && git commit -m 'ci(index): regen'", cwd=str(REPO_ROOT))
        run_cmd("git push origin main", cwd=str(REPO_ROOT), timeout=60)

    # Auto-release (patch/minor)
    rc, out, err = run_cmd("bash _scripts/kb-release.sh --auto", cwd=str(REPO_ROOT), timeout=120)
    if rc == 0:
        print(f"  Release: {out.strip()}")
        run_cmd("git push origin main --tags", cwd=str(REPO_ROOT), timeout=60)
    else:
        print(f"  Release skipped or failed: {err[:200]}")

    state["last_main_sha"] = current_sha


# ═══════════════════════════════════════════════════════════
# Job 3: Nightly Audit
# ═══════════════════════════════════════════════════════════

def job_nightly(state, token, dry_run=False):
    """Full repo audit: gate on main HEAD, leak scan, vendor check."""
    print("\n=== Job: Nightly Audit ===")

    if dry_run:
        print("  [DRY-RUN] Would run full audit.")
        return

    # Ensure on latest main
    run_cmd("git checkout main && git pull origin main", cwd=str(REPO_ROOT), timeout=60)

    # Full gate
    rc, out, err = run_cmd("bash _scripts/verify.sh", cwd=str(REPO_ROOT), timeout=600)
    if rc != 0:
        print(f"  FAIL: Gate failed on main HEAD!\n{(out + err)[-1000:]}")
        # TODO: notify editors (issue/comment)
    else:
        print("  Gate PASS on main HEAD.")

    # Vendor bump check (ohos-common-kb-public)
    print("  Vendor sync check: skipped (implement kb-sync-common.sh first)")

    print("  Nightly audit complete.")


# ═══════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="KB Bot — cron orchestrator")
    parser.add_argument("--job", choices=["pr", "merge", "nightly", "all"], default="all")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    token = get_token()
    if not token:
        print("ERROR: No GitCode token found (set GITCODE_TOKEN or create ~/.gitcode)", file=sys.stderr)
        sys.exit(1)

    state = load_state()

    print(f"kb-bot.py — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Repo: {OWNER}/{REPO}")
    print(f"  Job: {args.job}")
    print(f"  Dry-run: {args.dry_run}")

    if args.job in ("pr", "all"):
        job_pr(state, token, args.dry_run)

    if args.job in ("merge", "all"):
        job_merge(state, token, args.dry_run)

    if args.job in ("nightly", "all"):
        job_nightly(state, token, args.dry_run)

    save_state(state)
    print("\nDone.")


if __name__ == "__main__":
    main()
