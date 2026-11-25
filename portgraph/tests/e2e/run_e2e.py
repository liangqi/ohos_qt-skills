#!/usr/bin/env python3
"""portgraph E2E dependency reconciliation harness (real GitHub projects x README dependency descriptions).

For each real Qt project in corpus.json:
  clone (reuse existing clone) -> private DB copy (isolated from the main DB, parallelizable) -> scan
  -> analyze -> fetch-deps --dry-run -> extract dependency oracle from README/INSTALL
  -> reconcile direct deps (depth-1) -> auto-attribute differences (evidence via build-file grep)
  -> human-readable report (.report.md) + agent-readable report (.report.json)

Usage:
    python tests/e2e/run_e2e.py list
    python tests/e2e/run_e2e.py run --project corpus_a [--fresh-db] [--skip-scan] [--no-clone]
    python tests/e2e/run_e2e.py run --all

Outputs:
    tests/e2e/reports/<app>.report.md     human-readable dependency analysis report
    tests/e2e/reports/<app>.report.json   agent-readable structured report
    tests/e2e/oracle/<app>.json           dependency oracle (auto-extracted on first run;
                                          set reviewed=true after agent review/correction)
    tests/e2e/overrides/<app>.json        attribution correction rules (take effect on rerun after agent edits)
    workspace/e2e/db/<app>.sqlite         private DB copy (gitignored area)

Difference attribution classes (by_design=true is expected behavior, not counted as a bug):
    matched / matched-optional      oracle and portgraph agree
    missed-dep           ★ bug candidate  declared in README and referenced by build files, not detected by portgraph
    resolution-gap       ★ bug candidate  scan produced a pkg-unknown ghost node, while the DB actually
                                    has a known HarmonyOS package for the same library under another name (real resolution gap)
    false-positive       ★ bug candidate  detected by portgraph but not referenced by build files
    readme-stale                    declared in README but not referenced by build files (README out of date)
    readme-omitted                  referenced by build files but not listed in README (portgraph correct)
    qt-granularity                  Qt/KF module granularity folded (README only says "Qt")
    build-only                      build tool (fetch-deps does not collect build deps)
    optional-not-built              optional dependency, not in the default build
    vendored                        declared in README but a .gitmodules bundled submodule
                                    (compiled with the project, not fetched as an external package)
    unknown-ok                      ghost node with no similarly named known package: a real external dep
                                    with no HarmonyOS package; need_port is the correct conclusion
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from port_graph import (DB_PATH, WORKSPACE, cloner, db, deps_fetch,  # noqa: E402
                        engine, kb_seed, project_scanner, qt_scanner)


def _rel(p) -> str:
    """Path relative to the portgraph root: baseline reports never record local absolute paths (portable,
    no machine info leaked; reports are tool regression assets and store only relative locations)."""
    try:
        return str(Path(p).resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(p)

E2E_DIR = Path(__file__).resolve().parent
ORACLE_DIR = E2E_DIR / "oracle"
OVERRIDES_DIR = E2E_DIR / "overrides"
REPORTS_DIR = E2E_DIR / "reports"
CORPUS_FILE = E2E_DIR / "corpus.json"
E2E_DB_DIR = WORKSPACE / "e2e" / "db"
DRYRUN_OUT = WORKSPACE / "e2e" / "ohos-libs-dryrun"

BUG_CLASSES = {"missed-dep", "resolution-gap", "false-positive"}
BY_DESIGN_CLASSES = {"matched", "matched-optional", "readme-stale",
                     "readme-omitted", "qt-granularity", "build-only",
                     "optional-not-built", "unknown-ok", "vendored",
                     "unclassified"}

# ---------------------------------------------------------------- Constant tables

# Hint words for README dependency section headings (lowercase substring match; Chinese hints match Chinese READMEs)
SECTION_HINTS = ("dependenc", "requirement", "依赖", "prerequisite",
                 "third-party", "third party", "third‑party", "libraries",
                 "构建所需", "需要安装")

# Build tools/test frameworks (not needed on the target; outside fetch-deps scope)
BUILD_TOOLS = {
    "cmake", "ninja", "ninja-build", "make", "gmake", "gcc", "g++", "clang",
    "clang++", "llvm", "lld", "python", "python3", "python2", "perl", "ruby",
    "node", "nodejs", "git", "subversion", "svn", "pkg-config", "pkgconf",
    "autoconf", "automake", "libtool", "m4", "nasm", "yasm", "patch", "flex",
    "bison", "gperf", "extra-cmake-modules", "ecm", "doxygen", "graphviz",
    "sphinx", "meson", "qt-tools", "qtbase-dev", "lrelease", "moc",
    "gettext", "po4a", "appstream", "desktop-file-utils", "shared-mime-info",
    "gtest", "googletest", "gmock", "catch2", "catch", "libunity", "mock",
}

# README-side name alias -> canonical name (complements kb_seed.ALIASES, opposite direction)
README_ALIASES = {
    "qt": "qt", "qt5": "qt", "qt6": "qt", "qtbase": "qt", "qt-base": "qt",
    "qt5-base": "qt", "qt6-base": "qt", "qt-framework": "qt",
    "kf5": "kf", "kf6": "kf", "kf": "kf", "kde-frameworks": "kf",
    "kde-framework": "kf",
    "libssl": "openssl", "libcrypto": "openssl", "openssl-dev": "openssl",
    "libssl-dev": "openssl", "openssl-3": "openssl",
    "boost-libs": "boost", "boost-libraries": "boost", "libboost": "boost",
    "boost-dev": "boost",
    "zlib1g": "zlib", "zlib1g-dev": "zlib", "zlib-dev": "zlib",
    "libz": "zlib",
    "libtorrent": "libtorrent-rasterbar",
    "taglib-dev": "taglib", "libtag": "taglib",
    "libbotan": "botan", "botan-2": "botan", "botan-3": "botan",
    "libsodium-dev": "libsodium", "libgcrypt": "libgcrypt",
    "libxkb": "libxkbcommon", "xkbcommon": "libxkbcommon",
    "qt5-webengine": "qt", "qt6-webengine": "qt",
    "qt5-quickcontrols2": "qt", "qt6-quickcontrols2": "qt",
    # Same library, different name (confirmed in e2e corpus_a review): nayuki QR-Code-generator
    # = cmd-pkgs libqrcodegen (same version lineage, 1.8.0)
    "qr-code-generator": "libqrcodegen",
}

_VERSION_TOK_RE = re.compile(r"^[\d<>=~^]|^v?\d+(\.\d+)*\+?$")
_STOP_WORDS = {"and", "or", "with", "higher", "later", "newer", "above",
               "greater", "以上", "及以上", "or", "newer.", "later."}  # Chinese: "or higher"


# ---------------------------------------------------------------- Utilities

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_corpus() -> List[Dict]:
    data = json.loads(CORPUS_FILE.read_text(encoding="utf-8"))
    return data["projects"]


def fresh_db_copy(dst: Path) -> None:
    """Copy the main DB into a project-private DB using the sqlite3 backup API (WAL-safe)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    src = sqlite3.connect(str(DB_PATH))
    out = sqlite3.connect(str(dst))
    with out:
        src.backup(out)
    src.close()
    out.close()


def norm_name(s: str) -> str:
    """Normalize a dependency name: lowercase, strip markdown decoration, drop version tokens, unify separators."""
    s = s.strip().lower()
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = s.replace("`", "").replace("**", "").replace("*", "")
    toks = []
    for t in s.split():
        tl = t.strip("()[]{}:;,.")
        if not tl:
            continue
        if _VERSION_TOK_RE.match(tl):
            break
        if tl in _STOP_WORDS:
            break
        toks.append(tl)
        if len(toks) >= 4:
            break
    s = " ".join(toks)
    s = re.sub(r"[^a-z0-9@+]+", "-", s).strip("-")
    return s


def canon_of(s: str) -> str:
    """Further folding: alias table + @variant stripping."""
    n = norm_name(s)
    n = README_ALIASES.get(n, n)
    if "@" in n and not n.startswith("openssl@"):
        n = n.split("@", 1)[0]
    return n


def pg_canon(node: Dict) -> str:
    """portgraph dependency node -> canonical name (qt-module folds to qt, KF folds to kf).

    Separator normalization matches the oracle-side norm_name (_ / space -> -): otherwise
    json_schema_validator (require_dep underscore name) would never match the
    oracle's json-schema-validator; only symmetric normalization makes them comparable."""
    if node["kind"] == "qt-module":
        return "qt"
    if node["kind"] == "framework":
        return "kf"
    name = (node["name"] or "").lower()
    if "@" in name and not name.startswith("openssl@"):
        name = name.split("@", 1)[0]
    name = re.sub(r"[^a-z0-9@+]+", "-", name).strip("-")
    return name or node["id"].split(":", 1)[-1].lower()


def names_match(oracle_name: str, pg_name: str, pg_node: Dict) -> bool:
    """Match oracle name <-> portgraph node name (exact -> alias -> kb_seed.ALIASES -> containment)."""
    oc = canon_of(oracle_name)
    pc = pg_canon(pg_node)
    if not oc or not pc:
        return False
    if oc == pc:
        return True
    # kb_seed.ALIASES: openssl → [openssl@3, openssl]
    for cand in kb_seed.ALIASES.get(oc, []):
        if cand == pc or cand == (pg_node["name"] or "").lower():
            return True
    if len(oc) >= 5 and len(pc) >= 5 and (oc in pc or pc in oc):
        return True
    return False


def _fold_pkg_name(n: str) -> str:
    """Fold a package name: lowercase, drop @variant, drop lib prefix, normalize separators."""
    n = (n or "").lower().strip()
    at = n.find("@")
    if at > 0:
        n = n[:at]
    if n.startswith("lib") and len(n) > 3:
        n = n[3:]
    return n.replace("_", "-").strip("-")


def ghost_plausible_package(conn, ghost_name: str) -> Optional[Dict]:
    """Whether a ghost node name has a known HarmonyOS package it "should have resolved to".

    Criteria (any hit means it exists):
    - the target package that kb_seed.PKG_ALIASES points to exists in the DB
    - an ingested hb/cmd-pkgs package name is equal after folding, or one is a substring of the other and they share a full separator component
      (openal ⊂ openal-soft; udev ⊄ uudeview -- no shared component)
    Returns {id, name} or None. None -> the ghost is a correct detection (unknown-ok).
    """
    raw = (ghost_name or "").strip()
    g = _fold_pkg_name(raw)
    if not g or len(g) < 3:
        return None
    alias = kb_seed.PKG_ALIASES.get(raw.lower())
    if isinstance(alias, str):
        node = kb_seed.resolve_package(conn, alias)
        if node:
            return {"id": node["id"], "name": node["name"]}
    g_parts = set(p for p in g.split("-") if p)
    try:
        rows = conn.execute(
            "SELECT id, name FROM nodes WHERE kind='package' "
            "AND (id LIKE 'hb:%' OR id LIKE 'cmdpkgs:%')").fetchall()
    except sqlite3.Error:
        return None
    for r in rows:
        p = _fold_pkg_name(r["name"] or "")
        if not p:
            continue
        if p == g:
            return {"id": r["id"], "name": r["name"]}
        p_parts = set(x for x in p.split("-") if x)
        if (g in p or p in g) and (g_parts & p_parts):
            return {"id": r["id"], "name": r["name"]}
    return None


# ---------------------------------------------------------------- Oracle extraction

def _parse_oracle_dep(raw: str) -> Optional[Dict]:
    """One README dependency text -> {name, type, raw}; returns None if unparseable."""
    s = raw.strip()
    if not s or len(s) > 120:
        return None
    s_disp = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)   # keep original text for display
    low = s.lower()
    typ = "runtime"
    # Chinese keywords match Chinese READMEs ("optional", "build", "compile")
    if ("optional" in low or "可选" in low or "if available" in low
            or "not required" in low):
        typ = "optional"
    if (("(build" in low and ")" in low) or "build only" in low
            or "构建" in low or "编译" in low or "compile" in low
            or "toolchain" in low):
        typ = "build"
    name = norm_name(s)
    if not name or len(name) > 60:
        return None
    if canon_of(name) in BUILD_TOOLS or name in BUILD_TOOLS:
        typ = "build"
    if typ == "runtime" and name in BUILD_TOOLS:
        typ = "build"
    # Drop multi-word prose lines (many tokens and ending with a period)
    if s.endswith(".") and len(s.split()) > 6:
        return None
    return {"name": name, "display": s_disp.strip(), "type": typ, "raw": s}


def extract_oracle_from_doc(text: str) -> List[Dict]:
    """Extract dependency section entries (bullets/numbered/table rows) from README/INSTALL text."""
    lines = text.splitlines()
    deps: List[Dict] = []
    seen = set()
    level = None
    in_sec = False
    for ln in lines:
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            lvl, title = len(m.group(1)), m.group(2).lower()
            if any(h in title for h in SECTION_HINTS):
                in_sec, level = True, lvl
                continue
            if in_sec and lvl <= (level or 9):
                in_sec = False
            continue
        if not in_sec:
            continue
        item = None
        mb = re.match(r"^\s*[-*+•]\s+(.+)$", ln)
        mn = re.match(r"^\s*\d+[.)]\s+(.+)$", ln)
        mt = re.match(r"^\s*\|(.+)\|\s*$", ln)
        if mb:
            item = mb.group(1)
        elif mn:
            item = mn.group(1)
        elif mt:
            cells = [c.strip() for c in mt.group(1).split("|")]
            if all(re.match(r"^[-: ]*$", c) for c in cells if c):
                continue
            item = next((c for c in cells if c), None)
        if not item:
            continue
        d = _parse_oracle_dep(item)
        if d and d["name"] not in seen:
            seen.add(d["name"])
            deps.append(d)
    return deps


def load_oracle(proj: Dict, repo_path: Path) -> Dict:
    """Load the oracle: a manually reviewed file takes priority; otherwise auto-extract and write it (reviewed=false)."""
    app = proj["name"]
    of = ORACLE_DIR / ("%s.json" % app)
    if of.exists():
        data = json.loads(of.read_text(encoding="utf-8"))
        data.setdefault("app", app)
        data.setdefault("reviewed", False)
        return data
    extracted: List[Dict] = []
    source = None
    for fname in proj.get("oracle_files", ["README.md"]):
        f = repo_path / fname
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        got = extract_oracle_from_doc(text)
        if got:
            source, extracted = fname, got
            break
    data = {"app": app, "source": source,
            "source_note": "auto-extracted (heuristic), pending agent review" if source
            else "no dependency section found, to be written manually by an agent",
            "reviewed": False, "deps": extracted}
    ORACLE_DIR.mkdir(parents=True, exist_ok=True)
    of.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                  encoding="utf-8")
    return data


# ---------------------------------------------------------------- Build-file evidence

BUILD_FILE_NAMES = {"CMakeLists.txt", "meson.build", "vcpkg.json",
                    "conanfile.py", "conanfile.txt", "configure.ac"}
BUILD_FILE_SUFFIXES = (".cmake", ".pro", ".pri", ".prf")
LOOSE_ONLY_NAMES = {"vcpkg.json", "conanfile.py", "conanfile.txt"}
LOOSE_ONLY_SUFFIXES = (".pro", ".pri")
SKIP_DIRS = {".git", "node_modules"}


def _collect_build_files(repo: Path, max_files: int = 4000) -> List[Path]:
    out: List[Path] = []
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            if (fn in BUILD_FILE_NAMES or fn.endswith(BUILD_FILE_SUFFIXES)
                    or fn.endswith(".cmake")):
                out.append(Path(root) / fn)
                if len(out) >= max_files:
                    return out
    return out


def _word_guard(e: str) -> str:
    """Word-boundary guard: anything other than alphanumerics counts as a boundary (including _:.-@ separators).

    \b cannot match underscore/colon-joined forms such as external_openal / lib_zlib /
    ns::openal (e2e corpus_a review: external_*-prefixed target names were once missed),
    so lookaround assertions implement separator-sensitive boundaries.
    """
    return r"(?<![A-Za-z0-9])" + e + r"(?![A-Za-z0-9])"


def grep_dep_refs(repo: Path, name_variants: List[str],
                  max_hits: int = 5) -> Dict:
    """Search the cloned repo's build files for dependency references; return strong/weak evidence.

    Strong evidence: find_package/pkg_check_modules/find_library/target_link_libraries
    Weak evidence: bare-name occurrences in vcpkg/conan/qmake files
    """
    variants = []
    for v in name_variants:
        if v and len(v) >= 3 and v not in variants:
            variants.append(v)
    if not variants:
        return {"strong": 0, "weak": 0, "hits": []}
    strict, loose = [], []
    for v in variants:
        e = re.escape(v)
        b = _word_guard(e)
        strict.append(re.compile(r"(?i)find_package\s*\(\s*%s" % b))
        strict.append(re.compile(r"(?i)pkg_check_modules\s*\([^)]*%s" % b))
        strict.append(re.compile(r"(?i)find_library\s*\([^)]*%s" % b))
        strict.append(re.compile(r"(?is)target_link_libraries\s*\([^)]*?%s"
                                 % b))
        loose.append(re.compile(r"(?i)%s" % b))
    hits: List[Dict] = []
    n_strong = n_weak = 0
    try:
        files = _collect_build_files(repo)
    except OSError:
        files = []
    for f in files:
        is_loose_only = (f.name in LOOSE_ONLY_NAMES
                         or f.name.endswith(LOOSE_ONLY_SUFFIXES))
        try:
            if f.stat().st_size > 2_000_000:
                continue
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(f.relative_to(repo)).replace("\\", "/")
        # Strong evidence: full-text match (CMake commands often span lines -- corpus_a's
        # target_link_libraries puts each link item on its own line; per-line matching would miss evidence)
        for pat in strict:
            for m in pat.finditer(text):
                n_strong += 1
                line_no = text.count("\n", 0, m.end()) + 1
                if len(hits) < max_hits:
                    snippet = text[m.start():m.end()]
                    snippet = snippet[snippet.rfind("\n") + 1:][:120]
                    hits.append({"file": rel, "line": line_no,
                                 "strong": True, "text": snippet})
        if is_loose_only:
            for i, line in enumerate(text.splitlines(), 1):
                if any(p.search(line) for p in loose):
                    n_weak += 1
                    if len(hits) < max_hits and not any(
                            h["file"] == rel and h["line"] == i
                            for h in hits):
                        hits.append({"file": rel, "line": i, "strong": False,
                                     "text": line.strip()[:120]})
    return {"strong": n_strong, "weak": n_weak, "hits": hits}


def name_variants(disp_or_name: str, node: Optional[Dict] = None) -> List[str]:
    """Oracle raw name / pg node name -> list of grep variants."""
    out = []
    raw = (disp_or_name or "").strip()
    if raw:
        out.append(raw)
        out.append(raw.lower())
    n = norm_name(raw) if raw else ""
    if n:
        out.append(n)
        out.append(n.replace("-", ""))
    if node is not None:
        nm = (node["name"] or "").strip()
        if nm:
            out.append(nm)
            out.append(nm.lower())
        # When the node name has @version (openssl@3), add the stripped variant: otherwise grep cannot find
        # raw declarations like find_package(OpenSSL) (confirmed in e2e corpus_d retrospective)
        if "@" in nm:
            out.append(nm.split("@", 1)[0])
        nid = node["id"]
        if ":" in nid:
            tail = nid.split(":", 1)[1]
            out.append(tail)
            if "@" in tail:
                out.append(tail.split("@", 1)[0])
        # Reverse aliases: build files use the alias form (find_package(X11) /
        # pkg_check_modules(xkbcommon)), while the scan already merged it into the target package node
        # (libx11 / libxkbcommon) -- add the original alias names to the grep variants too
        node_nm = (node["name"] or "").lower()
        for alias_key, alias_target in kb_seed.PKG_ALIASES.items():
            if alias_target.lower() == node_nm:
                out.append(alias_key)
    return list(dict.fromkeys(v for v in out if v and len(v) >= 3))


def vendored_submodule_match(repo_path: Path,
                             oracle_names: List[str]) -> Optional[Dict]:
    """Whether an oracle dependency name (both name and display are tried) is a .gitmodules bundled submodule
    (vendored, compiled with the project).

    Match: folded name (separators/case removed) equals the submodule name / last path segment / last url segment,
    or one is a substring of the other (>=5 chars). Returns {path, url} or None.
    """
    try:
        submodules = qt_scanner._detect_gitmodules(repo_path)
    except OSError:
        return None
    if not submodules:
        return None

    def fold(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", (s or "").lower())

    wants = []
    for nm in oracle_names:
        w = fold(canon_of(nm))
        if w and len(w) >= 3 and w not in wants:
            wants.append(w)
    if not wants:
        return None
    for gm in submodules:
        url = (gm.get("url") or "").rstrip("/")
        url_last = url.rsplit("/", 1)[-1]
        if url_last.endswith(".git"):
            url_last = url_last[:-4]
        cands = [gm.get("name") or "",
                 (gm.get("path") or "").rsplit("/", 1)[-1],
                 url_last]
        for c in cands:
            f = fold(c)
            if not f or len(f) < 3:
                continue
            for want in wants:
                if f == want or (len(want) >= 5 and
                                 (want in f or f in want)):
                    return {"path": gm.get("path"), "url": gm.get("url")}
    return None


# ---------------------------------------------------------------- Main flow

def bfs_depths(conn, app_id: str) -> Dict[str, int]:
    depths = {app_id: 0}
    queue = [app_id]
    while queue:
        nid = queue.pop(0)
        for e in db.out_edges(conn, nid, ("runtime", "uses-module")):
            if e.get("platform_cond") in ("macos",):
                continue
            if e["dst"] not in depths:
                depths[e["dst"]] = depths[nid] + 1
                queue.append(e["dst"])
    return depths


def run_project(proj: Dict, args) -> Dict:
    app_key = proj["name"]
    print("[e2e] ==== %s (tier %s) ====" % (app_key, proj.get("tier", "?")))

    # 1. clone (reuse existing clone)
    if args.no_clone:
        repo_path = WORKSPACE / app_key
    else:
        info = cloner.clone_repo(proj["url"], app_key)
        repo_path = Path(info["path"])
        print("[e2e] clone: %s (%s)" % (
            repo_path, "existing, reused" if not info["cloned"] else "freshly cloned"))

    # 2. private DB copy
    db_file = E2E_DB_DIR / ("%s.sqlite" % app_key)
    if args.fresh_db or not db_file.exists():
        fresh_db_copy(db_file)
        print("[e2e] private DB: %s (freshly copied from main DB)" % db_file.name)
    conn = db.connect(db_file)

    try:
        # 3. scan
        if args.skip_scan:
            row = conn.execute(
                "SELECT id FROM nodes WHERE kind='app' AND id LIKE ?",
                ("app:%" + app_key.lower() + "%",)).fetchone()
            if not row:
                print("[e2e] --skip-scan but private DB has no such app; falling back to scan")
                args.skip_scan = False
            else:
                app_id = row["id"]
                scan = {"app_id": app_id, "name": app_key,
                        "build_system": "?", "sources": "?"}
        if not args.skip_scan:
            print("[e2e] scanning %s ..." % repo_path.name)
            scan = project_scanner.scan_project(conn, repo_path)
            app_id = scan["app_id"]
            print("[e2e] scan: app_id=%s build=%s sources=%s "
                  "qt_modules=%d deps_linked=%d deps_unknown=%d" % (
                      app_id, scan["build_system"], scan["sources"],
                      len(scan["modules_linked"]), len(scan["deps_linked"]),
                      len(scan["deps_unknown"])))

        # 4. analyze
        analysis = engine.analyze(conn, app_id)
        print("[e2e] analyze: verdict=%s blockers=%d unknowns=%d" % (
            analysis["verdict"], len(analysis["blockers"]),
            len(analysis["unknowns"])))

        # 5. fetch-deps dry-run (no download, no disk writes)
        manifest = deps_fetch.fetch_app_deps(conn, app_id, DRYRUN_OUT,
                                             dry_run=True)
        print("[e2e] fetch-deps(dry-run): closure=%d %s" % (
            manifest["closure_size"],
            " ".join("%s=%d" % kv for kv in sorted(
                manifest["summary"].items()))))

        # 6. direct deps + closure depth
        depths = bfs_depths(conn, app_id)
        direct = []
        for e in db.out_edges(conn, app_id, ("runtime", "uses-module")):
            if e.get("platform_cond") in ("macos",):
                continue
            nd = db.get_node(conn, e["dst"])
            if nd is None:
                continue
            direct.append({"id": nd["id"], "name": nd["name"],
                           "kind": nd["kind"], "edge": e["type"],
                           "port_status": nd["port_status"],
                           "depth": depths.get(e["dst"], -1)})
        direct.sort(key=lambda d: (d["kind"], d["name"].lower()))

        # 7. oracle
        oracle = load_oracle(proj, repo_path)
        print("[e2e] oracle: source=%s reviewed=%s deps=%d" % (
            oracle.get("source"), oracle.get("reviewed"),
            len(oracle.get("deps", []))))

        # 8. reconcile + attribute
        diffs, matched_pg_ids = reconcile(conn, oracle, direct, repo_path,
                                          manifest, app_id)

        # 9. overrides
        notes = []
        ov_file = OVERRIDES_DIR / ("%s.json" % app_key)
        if ov_file.exists():
            ov = json.loads(ov_file.read_text(encoding="utf-8"))
            notes = apply_overrides(diffs, ov)

        # 10. metrics
        metrics = compute_metrics(oracle, diffs)

        # 11. reports
        result = assemble_result(proj, app_id, scan, analysis, manifest,
                                 direct, oracle, diffs, metrics, notes,
                                 repo_path)
        write_reports(result, diffs)
        print("[e2e] %s metrics: recall=%s precision=%s bug_candidates=%d" % (
            app_key, metrics["recall"], metrics["precision"],
            metrics["bug_candidates"]))
        for d in diffs:
            if d["class"] in BUG_CLASSES:
                note = d.get("agent_note") or (
                    d["evidence"]["note"] if d.get("evidence") else "")
                print("      ★ [%s] %s ← %s" % (
                    d["class"], d.get("oracle_name") or d.get("pg_name"),
                    note))
        print("[e2e] reports: %s / %s" % (
            REPORTS_DIR / ("%s.report.md" % app_key),
            REPORTS_DIR / ("%s.report.json" % app_key)))
        return result
    finally:
        conn.close()


def reconcile(conn, oracle: Dict, direct: List[Dict], repo_path: Path,
              manifest: Dict, app_id: str) -> tuple:
    """Reconciliation core: oracle x direct deps -> list of attributed differences + set of matched pg node ids."""
    diffs: List[Dict] = []
    matched_pg_ids: set = set()
    odeps = oracle.get("deps", [])

    # --- pass 1: oracle entries ---
    for o in odeps:
        odisp = o.get("display") or o.get("name")
        hit = next((d for d in direct
                    if d["id"] not in matched_pg_ids
                    and names_match(odisp, d["name"], d)), None)
        if hit:
            matched_pg_ids.add(hit["id"])
            cls = ("matched-optional" if o.get("type") == "optional"
                   else "matched")
            ev = None
            if hit["id"].startswith("pkg-unknown:"):
                cand = ghost_plausible_package(conn, hit["name"])
                ev = ({"note": "⚠ matched a ghost node: the DB has a similarly named known package %s (%s) "
                       "-> name resolution gap, needs review" % (cand["name"], cand["id"])}
                      if cand else
                      {"note": "matched a ghost node: real external dependency with no known HarmonyOS package "
                       "(fetch-deps reports need_port/needs a source port; detection correct)"})
            diffs.append({"class": cls, "side": "oracle", "by_design": True,
                          "oracle_name": o.get("name"),
                          "oracle_type": o.get("type"),
                          "pg_id": hit["id"], "pg_name": hit["name"],
                          "pg_kind": hit["kind"], "pg_status": hit["port_status"],
                          "depth": hit["depth"], "evidence": ev,
                          "agent_note": None})
            continue
        if o.get("type") == "build":
            diffs.append({"class": "build-only", "side": "oracle",
                          "by_design": True, "oracle_name": o.get("name"),
                          "oracle_type": "build", "pg_id": None,
                          "pg_name": None, "pg_kind": None, "pg_status": None,
                          "depth": None,
                          "evidence": {"note": "build tool; fetch-deps does not collect build edges"},
                          "agent_note": None})
            continue
        if o.get("type") == "optional":
            diffs.append({"class": "optional-not-built", "side": "oracle",
                          "by_design": True, "oracle_name": o.get("name"),
                          "oracle_type": "optional", "pg_id": None,
                          "pg_name": None, "pg_kind": None, "pg_status": None,
                          "depth": None,
                          "evidence": {"note": "optional dependency, not enabled in the default build"},
                          "agent_note": None})
            continue
        # runtime and unmatched -> gather evidence: is it a vendored submodule (compiled with the project,
        # not fetched as an external package)? otherwise, do build files reference it?
        vend = vendored_submodule_match(
            repo_path, [odisp, o.get("name") or ""])
        if vend:
            diffs.append({"class": "vendored", "side": "oracle",
                          "by_design": True, "oracle_name": o.get("name"),
                          "oracle_type": "runtime", "pg_id": None,
                          "pg_name": None, "pg_kind": None,
                          "pg_status": None, "depth": None,
                          "evidence": {"note": " .gitmodules bundled submodule"
                            " (%s -> %s): compiled together with the project source, not fetched/detected"
                            " as an external package" % (vend["path"], vend["url"])},
                          "agent_note": None})
            continue
        ev = grep_dep_refs(repo_path, name_variants(odisp))
        if ev["strong"] or ev["weak"]:
            cls, note = "missed-dep", (
                "declared in README and referenced by build files (strong=%d weak=%d), "
                "not detected by portgraph -> scanner miss candidate"
                % (ev["strong"], ev["weak"]))
        else:
            cls, note = "readme-stale", (
                "declared in README but no build-file reference -> README likely out of date/typo")
        diffs.append({"class": cls, "side": "oracle",
                      "by_design": cls not in BUG_CLASSES,
                      "oracle_name": o.get("name"), "oracle_type": "runtime",
                      "pg_id": None, "pg_name": None, "pg_kind": None,
                      "pg_status": None, "depth": None,
                      "evidence": {"note": note, "grep": ev["hits"]},
                      "agent_note": None})

    # --- pass 2: portgraph direct deps ---
    for d in direct:
        if d["id"] in matched_pg_ids:
            continue
        base = {"class": "", "side": "pg", "by_design": True,
                "oracle_name": None, "oracle_type": None,
                "pg_id": d["id"], "pg_name": d["name"], "pg_kind": d["kind"],
                "pg_status": d["port_status"], "depth": d["depth"],
                "evidence": None, "agent_note": None}
        if d["kind"] == "qt-module":
            base["class"] = "qt-granularity"
            base["evidence"] = {"note": "Qt module granularity: README usually just says 'Qt'"}
            diffs.append(base)
            continue
        if d["kind"] == "framework":
            base["class"] = "qt-granularity"
            base["evidence"] = {"note": "KDE Frameworks component granularity: "
                              "README usually just says 'KDE Frameworks'"}
            diffs.append(base)
            continue
        if d["id"].startswith("pkg-unknown:"):
            cand = ghost_plausible_package(conn, d["name"])
            if cand:
                base["class"] = "resolution-gap"
                base["by_design"] = False
                base["evidence"] = {"note": "pkg-unknown ghost node: "
                                  "the DB has a known HarmonyOS package for the same library under another name, %s (%s) -> "
                                  "name resolution gap (ALIASES missing an entry)"
                                  % (cand["name"], cand["id"])}
            else:
                base["class"] = "unknown-ok"
                base["evidence"] = {"note": "no known HarmonyOS package matched: real external "
                                  "dependency; the ghost node is a correct detection "
                                  "(fetch-deps reports need_port/needs a source port)"}
            diffs.append(base)
            continue
        ev = grep_dep_refs(repo_path, name_variants(None, d))
        if ev["strong"] or ev["weak"]:
            base["class"] = "readme-omitted"
            base["evidence"] = {"note": "referenced by build files but not listed in README -> "
                                "README incomplete (portgraph correct)",
                                "grep": ev["hits"]}
        else:
            base["class"] = "false-positive"
            base["by_design"] = False
            base["evidence"] = {"note": "detected by portgraph but no build-file reference -> "
                                "scanner false-positive candidate (include heuristic/name coincidence)",
                                "grep": ev["hits"]}
        diffs.append(base)
    return diffs, matched_pg_ids


def apply_overrides(diffs: List[Dict], ov: Dict) -> List[str]:
    for rule in ov.get("reclassify", []):
        for d in diffs:
            if rule.get("dep") is not None:
                if d.get("pg_id") != rule["dep"] and (
                        (d.get("pg_name") or "").lower() != rule["dep"].lower()):
                    continue
            if rule.get("oracle") is not None:
                if (d.get("oracle_name") or "").lower() != rule["oracle"].lower():
                    continue
            if rule.get("from") and d["class"] != rule["from"]:
                continue
            d["class"] = rule["to"]
            d["by_design"] = rule["to"] not in BUG_CLASSES
            d["agent_note"] = rule.get("reason", "")
    return ov.get("notes", [])


def compute_metrics(oracle: Dict, diffs: List[Dict]) -> Dict:
    odeps = oracle.get("deps", [])
    o_runtime = [d for d in odeps if d.get("type") == "runtime"]
    o_optional = [d for d in odeps if d.get("type") == "optional"]
    matched = [d for d in diffs if d["class"] == "matched"]
    matched_opt = [d for d in diffs if d["class"] == "matched-optional"]
    pg_eff = [d for d in diffs if d["side"] == "pg"
              and d["class"] in ("readme-omitted", "false-positive")] + \
             [d for d in diffs if d["side"] == "oracle"
              and d["class"] in ("matched", "matched-optional")]
    pg_match = [d for d in diffs if d["class"] in ("matched",
                                                   "matched-optional")]
    bug = [d for d in diffs if d["class"] in BUG_CLASSES]
    recall = ("%.0f%%" % (100.0 * len(matched) / len(o_runtime))
              if o_runtime else "n/a")
    precision = ("%.0f%%" % (100.0 * len(pg_match) / len(pg_eff))
                 if pg_eff else "n/a")
    return {
        "oracle_runtime": len(o_runtime), "oracle_optional": len(o_optional),
        "matched": len(matched), "matched_optional": len(matched_opt),
        "recall": recall, "precision": precision,
        "bug_candidates": len(bug),
        "bug_by_class": {c: sum(1 for d in bug if d["class"] == c)
                         for c in sorted(BUG_CLASSES)},
        "class_counts": {c: sum(1 for d in diffs if d["class"] == c)
                         for c in sorted({d["class"] for d in diffs})},
    }


# ---------------------------------------------------------------- Reports

def assemble_result(proj, app_id, scan, analysis, manifest, direct, oracle,
                    diffs, metrics, notes, repo_path) -> Dict:
    return {
        "schema": "portgraph-e2e-report/1",
        "app": {"key": proj["name"], "app_id": app_id,
                "name": scan.get("name"), "url": proj["url"],
                "tier": proj.get("tier"),
                "build_system": scan.get("build_system"),
                "sources": scan.get("sources"),
                "repo_path": _rel(repo_path)},
        "generated_at": now_iso(),
        "verdict": analysis["verdict"],
        "blockers": [{"kind": b["kind"], "node": b["node"],
                      "reason": b["reason"]} for b in analysis["blockers"]],
        "unknowns": [{"kind": u["kind"], "node": u["node"],
                      "reason": u["reason"]} for u in analysis["unknowns"]],
        "platform_excluded": analysis.get("platform_excluded", []),
        "closure": {
            "size": manifest["closure_size"],
            "summary": manifest["summary"],
            "need_port": [{"id": e["id"], "name": e["name"],
                           "version": e.get("version"),
                           "source_url": e.get("source_url"),
                           "repo_url": e.get("repo_url")}
                          for e in manifest["deps"]
                          if e["status"] == "need_port"],
            "cmd_only": [{"id": e["id"], "name": e["name"],
                          "artifact_cmd": e.get("artifact_cmd")}
                         for e in manifest["deps"]
                         if e["status"] == "cmd_only"],
            "would_download": [e["name"] for e in manifest["deps"]
                               if e["status"] == "would_download"],
        },
        "direct_deps": direct,
        "oracle": oracle,
        "diffs": diffs,
        "metrics": metrics,
        "agent_notes": notes,
    }


_CLASS_LABEL = {
    "matched": "Matched", "matched-optional": "Matched (optional)",
    "missed-dep": "★Missed", "resolution-gap": "★Resolution gap",
    "false-positive": "★False positive", "readme-stale": "README stale",
    "readme-omitted": "README omitted", "qt-granularity": "Granularity folded",
    "build-only": "Build tool", "optional-not-built": "Optional, not enabled",
    "unknown-ok": "Unknown pkg (OK)", "vendored": "Bundled submodule",
    "unclassified": "Unclassified",
}


def _md_escape(s) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def write_md_report(r: Dict, path: Path) -> None:
    m = r["metrics"]
    lines: List[str] = []
    a = lines.append
    a("# %s Dependency Reconciliation Report (portgraph E2E)" % r["app"]["name"])
    a("")
    a("> Generated: %s | Corpus: corpus.json#%s | Build system: %s | Source files: %s"
      % (r["generated_at"], r["app"]["key"], r["app"]["build_system"],
         r["app"]["sources"]))
    a("> Oracle: %s (review: %s, %d entries; origin: %s)" % (
        r["oracle"].get("source") or "none",
        "reviewed" if r["oracle"].get("reviewed") else "**not reviewed**",
        len(r["oracle"].get("deps", [])),
        r["oracle"].get("source_note", "")))
    a("")
    a("## 1. Summary")
    a("")
    a("| Metric | Value |")
    a("|---|---|")
    a("| Portability verdict | **%s** (blocked %d / unknown %d / platform-excluded %d) |" % (
        r["verdict"], len(r["blockers"]), len(r["unknowns"]),
        len(r["platform_excluded"])))
    a("| Detection recall | %s (%d/%d README runtime deps) |" % (
        m["recall"], m["matched"], m["oracle_runtime"]))
    a("| Detection precision | %s |" % m["precision"])
    a("| Bug candidates | **%d** (%s) |" % (
        m["bug_candidates"],
        ", ".join("%s=%d" % kv for kv in m["bug_by_class"].items()
                  if kv[1]) or "none"))
    a("| Dependency closure | %d items (%s) |" % (
        r["closure"]["size"],
        ", ".join("%s %d" % kv for kv in
                  sorted(r["closure"]["summary"].items()))))
    a("")
    if r["agent_notes"]:
        a("**Agent review notes**:")
        a("")
        for n in r["agent_notes"]:
            a("- %s" % n)
        a("")
    a("## 2. Portability Verdict (analyze)")
    a("")
    if r["blockers"]:
        a("| Blocker kind | Node | Reason |")
        a("|---|---|---|")
        for b in r["blockers"][:30]:
            a("| %s | %s | %s |" % (_md_escape(b["kind"]),
                                    _md_escape(b["node"]),
                                    _md_escape(b["reason"])[:160]))
    else:
        a("(no hard blockers)")
    if r["unknowns"]:
        a("")
        a("%d unconfirmed items:" % len(r["unknowns"]))
        for u in r["unknowns"][:15]:
            a("- [%s] %s: %s" % (u["kind"], u["node"], u["reason"][:120]))
    a("")
    a("## 3. Difference Attribution Details (oracle x portgraph direct deps)")
    a("")
    a("| Class | README side | portgraph side | Type/depth | Evidence/notes |")
    a("|---|---|---|---|---|")
    order = ["missed-dep", "resolution-gap", "false-positive",
             "readme-stale", "readme-omitted", "optional-not-built",
             "build-only", "qt-granularity", "matched", "matched-optional"]
    def sort_key(d):
        c = d["class"]
        return order.index(c) if c in order else len(order)
    for d in sorted(r["diffs"], key=sort_key):
        note = d["evidence"]["note"] if d.get("evidence") else ""
        if d.get("agent_note"):
            note = "%s [agent: %s]" % (note, d["agent_note"])
        a("| %s | %s | %s | %s%s | %s |" % (
            _CLASS_LABEL.get(d["class"], d["class"]),
            _md_escape(d.get("oracle_name") or "—"),
            _md_escape(d.get("pg_name") or "—"),
            d.get("pg_kind") or d.get("oracle_type") or "",
            " d%d" % d["depth"] if d.get("depth") else "",
            _md_escape(note)[:200]))
    a("")
    a("Class counts: %s" % ", ".join(
        "%s×%d" % (_CLASS_LABEL.get(c, c), n)
        for c, n in m["class_counts"].items()))
    a("")
    a("## 4. Dependency Closure Overview (fetch-deps --dry-run)")
    a("")
    c = r["closure"]
    a("- Closure total %d items: %s" % (
        c["size"], ", ".join("%s %d" % kv
                             for kv in sorted(c["summary"].items()))))
    if c["would_download"]:
        a("- Bottle directly downloadable: %s" % ", ".join(c["would_download"][:40]))
    if c["cmd_only"]:
        a("- Command-only fetch (cmd_only): %s" % ", ".join(
            e["name"] for e in c["cmd_only"][:20]))
    if c["need_port"]:
        a("- Needs own port (need_port): %s" % ", ".join(
            e["name"] for e in c["need_port"][:20]))
        for e in c["need_port"][:10]:
            src = e.get("source_url") or e.get("repo_url") or "?"
            a("  - %s: %s" % (e["name"], src))
    a("")
    a("## 5. Full Direct Dependency List (portgraph depth-1)")
    a("")
    a("| Node | Type | Edge | port_status | Depth |")
    a("|---|---|---|---|---|")
    for d in r["direct_deps"]:
        a("| %s | %s | %s | %s | %s |" % (
            _md_escape(d["name"]), d["kind"], d["edge"],
            d["port_status"], d["depth"]))
    a("")
    a("## 6. Methodology")
    a("")
    a("- Comparison scope: portgraph direct deps (depth-1 edges) vs deps declared in README/INSTALL; "
      "the closure is only an artifact overview.")
    a("- Attribution evidence: for unmatched items, automatically grep the cloned repo's build files "
      "(find_package/pkg_check_modules/target_link_libraries/vcpkg, etc.).")
    a("- ★ classes (missed-dep / resolution-gap / false-positive) are bug candidates "
      "requiring manual confirmation; the rest are expected differences.")
    a("- Agent-readable report: `%s`" % (
        _rel(REPORTS_DIR / ("%s.report.json" % r["app"]["key"]))))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_reports(result: Dict, diffs: List[Dict]) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    key = result["app"]["key"]
    write_md_report(result, REPORTS_DIR / ("%s.report.md" % key))
    (REPORTS_DIR / ("%s.report.json" % key)).write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- CLI

def main() -> None:
    ap = argparse.ArgumentParser(
        prog="run_e2e.py",
        description="portgraph E2E dependency reconciliation harness (real projects x README)")
    sub = ap.add_subparsers(dest="cmd")
    p_run = sub.add_parser("run", help="run reconciliation for one/all corpus projects")
    p_run.add_argument("--project", help="project name in the corpus")
    p_run.add_argument("--all", action="store_true", help="run all, sequentially")
    p_run.add_argument("--fresh-db", action="store_true",
                       help="force re-copy of the private DB from the main DB")
    p_run.add_argument("--skip-scan", action="store_true",
                       help="skip rescanning (when the private DB already has the app)")
    p_run.add_argument("--no-clone", action="store_true",
                       help="do not call clone (directory must already exist)")
    sub.add_parser("list", help="list corpus projects")
    args = ap.parse_args()

    if args.cmd == "list" or not args.cmd:
        for p in load_corpus():
            print("%-12s tier %-2s %s  oracle: %s" % (
                p["name"], p.get("tier", "?"), p["url"],
                ",".join(p.get("oracle_files", []))))
        return

    corpus = load_corpus()
    if args.all:
        for p in corpus:
            run_project(p, args)
        return
    if not args.project:
        ap.error("need --project <name> or --all (see list for available projects)")
    proj = next((p for p in corpus if p["name"] == args.project), None)
    if proj is None:
        ap.error("no such project in corpus: %s (see list for available ones)" % args.project)
    run_project(proj, args)


if __name__ == "__main__":
    main()
