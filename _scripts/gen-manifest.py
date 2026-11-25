#!/usr/bin/env python3
"""Refresh the computable fields of RELEASE-MANIFEST.yaml (zero third-party dependencies).

Why it exists: the manifest says "reproducible and reconcilable", but the content tree digest,
page counts, and test counts used to be filled in by hand and went stale as soon as code changed.
This script recomputes them and writes them back in place; run it once in the release flow
(before tagging).

Usage:
    python3 _scripts/gen-manifest.py            # refresh hash/counts/time, leave status unchanged
    python3 _scripts/gen-manifest.py --check    # compare only, don't modify the file; exit 1 on mismatch
    python3 _scripts/gen-manifest.py --release  # set status=released and backfill root_commit

Exit code: 0 = consistent/refreshed; 1 = --check found a mismatch or the environment is unsuitable.
"""

from __future__ import annotations

import argparse
import ast
import datetime
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "RELEASE-MANIFEST.yaml"

PAGE_GLOBS = [
    ("semantic", "semantic/*.md"),
    ("procedural", "procedural/*.md"),
    ("episodic", "episodic/postmortems/*.md"),
    ("problems", "problems/*.md"),
    ("ohos-common-kb-public", "ohos-common-kb-public/*/*.md"),
]


def tracked_files() -> list[str]:
    """Checked-in file list = tracked + untracked-but-not-ignored.

    Looking only at `--cached` has a hidden consequence: newly written pages are not in the list
    until `git add`, so the refreshed content_tree_sha256 **silently misses those files** -- the
    page count is right (it walks the filesystem) but the digest is wrong, and "reconcilable"
    relies precisely on the digest.
    """
    out = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        print("gen-manifest: git is required (the checked-in file list is taken from git ls-files)")
        sys.exit(1)
    return [x for x in out.stdout.split("\0") if x]


def content_tree_sha256() -> str:
    h = hashlib.sha256()
    for rel in sorted(tracked_files()):
        if rel == "RELEASE-MANIFEST.yaml":
            continue
        path = ROOT / rel
        if not path.is_file():
            continue
        h.update(rel.encode("utf-8") + b"\0")
        h.update(hashlib.sha256(path.read_bytes()).hexdigest().encode() + b"\n")
    return h.hexdigest()


def page_counts() -> tuple[int, int, str]:
    counts: dict[str, int] = {}
    for domain, pattern in PAGE_GLOBS:
        counts[domain] = sum(
            1 for p in sorted(ROOT.glob(pattern)) if not p.name.startswith("_"))
    common = counts.get("ohos-common-kb-public", 0)
    qt_side = sum(v for k, v in counts.items() if k != "ohos-common-kb-public")
    detail = " + ".join(f"{k} {v}" for k, v in counts.items()
                        if k != "ohos-common-kb-public")
    return common, qt_side, detail


def test_count() -> int:
    def count(*rels: str) -> int:
        total = 0
        for rel in rels:
            try:
                tree = ast.parse((ROOT / rel).read_text(encoding="utf-8-sig"))
            except (OSError, SyntaxError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                    total += sum(1 for item in node.body
                                 if isinstance(item, ast.FunctionDef)
                                 and item.name.startswith("test_"))
        return total
    return (count("tests/test_qt_ohos.py", "tests/test_kb_consistency.py",
                  "tests/test_cpp20_gap_scan.py")
            + count("portgraph/tests/test_port_graph.py",
                    "portgraph/tests/test_prefetch.py"))


def current_commit() -> str:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True, timeout=30)
    return out.stdout.strip() if out.returncode == 0 else ""


def set_scalar(text: str, key: str, value: str, indent: str = "",
               comment: str | None = None) -> str:
    """Change one `key: value` line. comment=None keeps the original trailing comment; otherwise it is replaced with the given comment."""
    pattern = re.compile(rf"^({re.escape(indent)}{re.escape(key)}:[ \t]*)([^\n#]*?)([ \t]*#[^\n]*)?$",
                         re.M)
    m = pattern.search(text)
    if not m:
        print(f"gen-manifest: field {key} not found in the manifest")
        sys.exit(1)
    tail = ("             # " + comment) if comment is not None else (m.group(3) or "")
    return text[:m.start()] + m.group(1) + value + tail + text[m.end():]


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh the computable fields of the release manifest")
    parser.add_argument("--check", action="store_true", help="compare only, don't write the file")
    parser.add_argument("--strict", action="store_true",
                        help="with --check: a content tree digest mismatch also counts as failure (use on release commits)")
    parser.add_argument("--release", action="store_true",
                        help="set status=released and backfill root_commit/released_at")
    args = parser.parse_args()

    original = MANIFEST.read_text(encoding="utf-8")
    text = original

    common, qt_side, detail = page_counts()
    digest = content_tree_sha256()
    tests = test_count()
    now = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()

    text = set_scalar(text, "content_tree_sha256", digest)
    text = set_scalar(text, "built_at", f'"{now}"')
    text = set_scalar(text, "common_pages_count", str(common))
    text = set_scalar(text, "qt_pages_count", str(qt_side),
                      comment=f"{detail} (excluding _index/_lookup)")
    text = set_scalar(text, "unittests", str(tests),
                      indent="  ")
    if args.release:
        commit = current_commit()
        text = set_scalar(text, "root_commit", f'"{commit}"')
        text = set_scalar(text, "status", "released")
        text = set_scalar(text, "released_at", f'"{now[:10]}"')

    if args.check:
        # Counts (pages/test cases/skills) must match; the content tree digest is only required to
        # match on release commits, otherwise every ordinary commit turns red and soon nobody looks at the "check".
        counts_changed = [ln for ln in text.splitlines()
                          if ln not in original.splitlines() and ln.strip()
                          and not ln.split(":")[0] in ("content_tree_sha256", "built_at")]
        hash_changed = ("content_tree_sha256: " + digest) not in original
        if counts_changed:
            print("gen-manifest: counts don't match reality (run _scripts/gen-manifest.py to refresh)")
            for line in counts_changed:
                print("  → " + line.strip())
            return 1
        if hash_changed:
            if args.strict:
                print("gen-manifest: content tree digest mismatch in strict mode -- the manifest must be refreshed on a release commit")
                return 1
            print(f"gen-manifest: counts consistent ({common + qt_side} pages / {tests} cases); "
                  f"the manifest is an old snapshot ({digest[:12]}…); refresh it with gen-manifest.py before release")
            return 0
        print(f"gen-manifest: consistent ({common + qt_side} pages / {tests} cases / {digest[:12]}…)")
        return 0

    MANIFEST.write_text(text, encoding="utf-8")
    print(f"gen-manifest: refreshed (Qt {qt_side} + platform {common} = {qt_side + common} pages, "
          f"{tests} cases, {digest[:12]}…)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
