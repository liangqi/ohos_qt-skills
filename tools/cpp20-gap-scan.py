#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cpp20-gap-scan.py — pre-flight check and mechanical fixes for C++20 gaps in OHOS NDK clang15/libc++15.

Background
----------
The OHOS NDK's clang 15 / libc++ 15 lack a number of C++20 language and library features (see
``problems/build-clang15-libcpp15-cpp20-gaps.md``). Full builds of large projects hit these gaps
over and over, and every "build -> error -> locate -> fix" round is expensive (tens of minutes to
hours per project). This tool moves that work earlier: **statically scan for known gap patterns
before building**, and automatically fix the mechanically fixable ones.

Usage
-----
    python tools/cpp20-gap-scan.py scan <src_dir> [--json]
        Scan and report; exit 1 if gaps are found (CI-friendly), exit 0 if none.
    python tools/cpp20-gap-scan.py fix <src_dir> [--apply]
        Automatically fix the mechanically fixable items (GAP-02); dry-run by default, --apply writes to disk.

Rule table (matches the sections of the problems page)
------------------------------------------------------
GAP-01  lambda capturing a structured binding (P1091, §1)   review
GAP-02  make_unique_for_overwrite (missing in libc++15)     auto-fix
GAP-03  std::stop_token / jthread (libc++ 19+ only)         review (needs shim)
GAP-04  std::atomic_ref (libc++ 19 only)                    review (needs polyfill)
GAP-05  std::ranges:: algorithms (partial in libc++ 15)     review
GAP-06  defaulted operator<=> with shared_ptr (§7)          review
GAP-07  init-capture-only lambda (§1 family, this capture)  review
GAP-08  pthread_setaffinity_np (missing in musl)            review (guard macro)

The following gaps **can only be found at compile time** and are not covered by this tool
(see the corresponding sections of the problems page):
P0634 omitted typename (§3), P0960 parenthesized aggregate initialization (§2),
allocator_traits::construct_at instantiation failure, variant __best_match (§8).

Note: the scan is heuristic (no semantic analysis); GAP-01/06/07 produce a few false positives.
Review hits manually using the patterns in the problems page. Auto-fix only covers items whose
semantic equivalence is clear-cut.
"""
import argparse
import json
import re
import sys
from pathlib import Path

SOURCE_EXTS = {".h", ".hpp", ".hh", ".hxx", ".cc", ".cpp", ".cxx", ".c", ".ipp", ".tpp"}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".qt-ohos", "out", "build"}

# ---------------------------------------------------------------- rule definitions

# GAP-02: make_unique_for_overwrite (the only auto-fix item)
MUFO_RE = re.compile(
    r"(?<![\w:.])(?:std::)?make_unique_for_overwrite<\s*(?P<type>[^<>]+?)\s*>\s*"
    r"\(\s*(?P<args>[^()]*)\s*\)"
)

# GAP-01: structured binding declarations (auto [a, b] = / const auto &[k, v] :)
BINDING_RE = re.compile(r"\bauto\s*(&|\&&)?\s*\[(?P<names>[^\]]+)\]\s*[=:]")
# lambda capture list (followed by ( { < ~, which marks a lambda rather than an array subscript)
LAMBDA_RE = re.compile(r"\[(?P<caps>[^\[\]]*)\]\s*[\(\{<~]")

# GAP-03: stop_token / jthread
STOPTOKEN_RE = re.compile(r"\bstd::(stop_token|stop_source|stop_callback|jthread)\b|#include\s*<stop_token>")

# GAP-04: atomic_ref
ATOMICREF_RE = re.compile(r"\bstd::atomic_ref\s*<")

# GAP-05: std::ranges:: algorithms (common set)
RANGES_RE = re.compile(r"\bstd::ranges::(?P<algo>[a-zA-Z_]\w*)")
RANGES_KNOWN = {
    "any_of", "all_of", "none_of", "find", "find_if", "find_if_not",
    "count", "count_if", "sort", "stable_sort", "copy", "copy_if",
    "transform", "remove", "remove_if", "unique", "reverse", "rotate",
    "min_element", "max_element", "min", "max", "clamp", "equal",
    "lexicographical_compare", "fill", "generate", "for_each",
    "includes", "set_intersection", "set_union",
    "begin", "end", "size", "data", "empty",  # these have std:: equivalents
}

# GAP-08: missing in musl
SETAFFINITY_RE = re.compile(r"\bpthread_setaffinity_np\s*\(")

RULES = [
    ("GAP-01", "P1091", "report",
     "lambda capturing a structured binding (clang 16+ only): copy via init-capture or into a plain local first (§1)"),
    ("GAP-02", "make_unique_for_overwrite", "auto",
     "libc++15 has no make_unique_for_overwrite: for arrays use std::unique_ptr<T[]>(new T[n]) (auto-fixable)"),
    ("GAP-03", "stop_token/jthread", "report",
     "libc++ 19+ only: write your own shim (mutex+condvar, §4)"),
    ("GAP-04", "atomic_ref", "report",
     "libc++ 19 only: __atomic_* pass-through polyfill (§5)"),
    ("GAP-05", "std::ranges", "report",
     "First try adding -D_LIBCPP_ENABLE_EXPERIMENTAL (verified to unlock all libc++15 ranges algorithms and <format>; "
     "jthread/clock_cast/expected/source_location are still missing); otherwise switch to std::X(iter...) or bundle range-v3 (§6/§9)"),
    ("GAP-06", "operator<=> shared_ptr", "report",
     "P1614 not implemented: a defaulted <=> with shared_ptr members is implicitly deleted; write explicit operator==/< (§7)"),
    ("GAP-07", "init-capture this", "report",
     "an init-capture-only lambda that uses this/members in its body needs = added ([=, name = val]) - same family as §1"),
    ("GAP-08", "pthread_setaffinity_np", "report",
     "musl lacks this function: guard with #if defined(__GLIBC__)"),
]


# ---------------------------------------------------------------- scan implementation

def iter_sources(root: Path):
    if root.is_file():
        yield root
        return
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in SOURCE_EXTS:
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        yield p


def _binding_names(text):
    names = set()
    for m in BINDING_RE.finditer(text):
        for part in m.group("names").split(","):
            part = part.strip()
            # strip any leftover qualifiers (normally a plain identifier)
            ident = re.match(r"[A-Za-z_]\w*$", part)
            if ident:
                names.add(part)
    return names


def _lambda_captures_uses(caps: str, names) -> bool:
    """A bare binding name appears in the capture list (by-value and by-reference capture both trigger P1091; init-capture is safe)."""
    for seg in caps.split(","):
        seg = seg.strip()
        if not seg:
            continue
        if seg in names:            # bare name: by-value capture
            return True
        if seg.startswith("&") and seg[1:].strip() in names:
            return True             # &name: by-reference capture
        # name = expr is an init-capture, safe
    return False


def _lambda_body(text: str, cap_start: int) -> str:
    """Starting at the capture list `[`, return the lambda body text (up to the matching `}` or a statement boundary)."""
    depth = 0
    i = cap_start
    n = len(text)
    # find the closing ] of the capture list
    while i < n:
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
            if depth == 0:
                i += 1
                break
        i += 1
    # look ahead for the lambda body `{` (past the parameter list/specifiers), at most 200 chars
    brace = text.find("{", i, min(n, i + 200))
    if brace < 0:
        return ""
    depth, j = 0, brace
    while j < n:
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[brace:j + 1]
        j += 1
    return ""


# proxy signals for "implicit this" in a lambda body: the this keyword / member identifiers prefixed with _ or m_
THIS_USE_RE = re.compile(r"\bthis\b|\b_[A-Za-z]\w*\b|\bm_[A-Za-z]\w*\b")


def scan_file(path: Path):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    hits = []
    lines = text.splitlines()

    def lineno(pos):
        return text.count("\n", 0, pos) + 1

    # GAP-01: structured binding captured by a lambda (heuristic)
    bnames = _binding_names(text)
    if bnames:
        for m in LAMBDA_RE.finditer(text):
            if _lambda_captures_uses(m.group("caps"), bnames):
                hits.append(("GAP-01", lineno(m.start()), m.group(0)[:60]))

    # GAP-02: make_unique_for_overwrite
    for m in MUFO_RE.finditer(text):
        hits.append(("GAP-02", lineno(m.start()), m.group(0)[:80]))

    # GAP-03: stop_token family
    for m in STOPTOKEN_RE.finditer(text):
        hits.append(("GAP-03", lineno(m.start()), m.group(0)[:60]))

    # GAP-04: atomic_ref
    for m in ATOMICREF_RE.finditer(text):
        hits.append(("GAP-04", lineno(m.start()), m.group(0)[:60]))

    # GAP-05: std::ranges algorithms
    for m in RANGES_RE.finditer(text):
        if m.group("algo") in RANGES_KNOWN:
            hits.append(("GAP-05", lineno(m.start()), m.group(0)[:60]))

    # GAP-06: operator<=> and shared_ptr in the same file (coarse, once per file)
    if "operator<=>" in text and "std::shared_ptr" in text:
        ln = next((i + 1 for i, l in enumerate(lines) if "operator<=>" in l), 1)
        hits.append(("GAP-06", ln, "operator<=> + shared_ptr in the same file (file-level review)"))

    # GAP-07: init-capture-only lambda whose body uses this / members prefixed with _ or m_ (implicit this)
    for m in LAMBDA_RE.finditer(text):
        caps = m.group("caps").strip()
        if not caps or "&" in caps or re.match(r"^=", caps) or "this" in caps:
            continue
        segs = [s.strip() for s in caps.split(",") if s.strip()]
        if segs and all(re.match(r"^[A-Za-z_]\w*\s*=", s) for s in segs):
            body = _lambda_body(text, m.start())
            if body and THIS_USE_RE.search(body):
                hits.append(("GAP-07", lineno(m.start()), m.group(0)[:60]))

    # GAP-08: pthread_setaffinity_np
    for m in SETAFFINITY_RE.finditer(text):
        hits.append(("GAP-08", lineno(m.start()), m.group(0)[:60]))

    # dedupe (same line, same rule, same snippet reported once)
    seen, uniq = set(), []
    for rid, ln, frag in hits:
        key = (rid, ln)
        if key not in seen:
            seen.add(key)
            uniq.append((rid, ln, frag))
    return uniq


def cmd_scan(root: Path, as_json=False):
    all_hits = []
    for p in iter_sources(root):
        for rid, ln, frag in scan_file(p):
            all_hits.append({"rule": rid, "file": str(p), "line": ln, "fragment": frag})
    rule_meta = {r[0]: {"category": r[1], "mode": r[2], "advice": r[3]} for r in RULES}
    if as_json:
        print(json.dumps({"hits": all_hits, "rules": rule_meta}, ensure_ascii=False, indent=1))
    else:
        auto_n = sum(1 for h in all_hits if h["rule"] == "GAP-02")
        by_rule = {}
        for h in all_hits:
            by_rule[h["rule"]] = by_rule.get(h["rule"], 0) + 1
        for h in sorted(all_hits, key=lambda x: (x["file"], x["line"])):
            meta = rule_meta[h["rule"]]
            print(f"{h['rule']}  {h['file']}:{h['line']}")
            print(f"       {meta['advice']}")
            print(f"       -> {h['fragment']}")
        print(f"\nSummary: {len(all_hits)} hit(s) (auto-fixable {auto_n} / need review {len(all_hits) - auto_n})"
              f"  across {len({h['file'] for h in all_hits})} file(s)")
        for rid in sorted(by_rule):
            meta = rule_meta[rid]
            print(f"  {rid}: {by_rule[rid]} hit(s)  ({meta['category']})")
        if all_hits:
            print("Mechanical fix: python tools/cpp20-gap-scan.py fix <dir> --apply")
    return 1 if all_hits else 0


def _mugo_repl(m):
    typ, args = m.group("type").strip(), m.group("args").strip()
    if typ.endswith("[]"):
        elem = typ[:-2].strip()
        return f"std::unique_ptr<{typ}>(new {elem}[{args}])"
    call = f"({args})" if args else "()"
    return f"std::unique_ptr<{typ}>(new {typ}{call})"


def cmd_fix(root: Path, apply=False):
    total, files = 0, []
    for p in iter_sources(root):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        new, n = MUFO_RE.subn(_mugo_repl, text)
        if n:
            total += n
            files.append((p, n))
            rel = p
            if apply:
                p.write_text(new, encoding="utf-8", newline="\n")
            preview = MUFO_RE.search(text)
            print(f"{'FIXED' if apply else 'DRY-RUN'}  {rel}  ({n} fix(es))")
            print(f"        e.g.: {preview.group(0)[:70] if preview else ''}")
    mode = "written to disk" if apply else "(dry-run; add --apply to write to disk)"
    print(f"\nFixed {total} occurrence(s) {mode}; GAP-01/03/04/05/06/07/08 need manual review (see the problems page)")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Pre-flight check and mechanical fixes for C++20 gaps in OHOS clang15/libc++15")
    ap.add_argument("mode", choices=["scan", "fix"], help="scan=report only (exit 1 for CI) / fix=mechanical fix")
    ap.add_argument("dir", help="source directory (recursive; .git/out/build etc. are skipped automatically)")
    ap.add_argument("--json", action="store_true", help="JSON output for scan")
    ap.add_argument("--apply", action="store_true", help="make fix actually write to disk (dry-run by default)")
    args = ap.parse_args()
    root = Path(args.dir)
    if not root.exists():
        print(f"Directory does not exist: {root}", file=sys.stderr)
        return 2
    if args.mode == "scan":
        return cmd_scan(root, args.json)
    return cmd_fix(root, args.apply)


if __name__ == "__main__":
    sys.exit(main())
