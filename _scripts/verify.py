#!/usr/bin/env python3
"""ohos-qt-skills repository self-check (contract / structure / knowledge pages / hygiene).

Usage:
    python3 _scripts/verify.py            # full check
    python3 _scripts/verify.py --quiet    # print problems only
    python3 _scripts/verify.py --json      # machine-readable output

Exit code: 0 = PASS (WARN allowed) | 1 = FAIL (has ERROR)

Design principles: zero third-party dependencies (pure standard library), runs identically on
Windows / macOS / Linux; checks only "facts a machine can decide" (existence / consistency /
parseability), no subjective quality scoring.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- result collection

ERRORS: list[str] = []
WARNS: list[str] = []
INFOS: list[str] = []


def error(code: str, msg: str) -> None:
    ERRORS.append(f"[{code}] {msg}")


def warn(code: str, msg: str) -> None:
    WARNS.append(f"[{code}] {msg}")


def info(msg: str) -> None:
    INFOS.append(msg)


# ---------------------------------------------------------------- helpers

SKIP_DIRS = {".git", "node_modules", "__pycache__", "dist", "build", "outputs", ".venv"}
ARTIFACT_DIRS = {".cxx", ".hvigor", ".idea", ".gradle", ".deveco"}
TEXT_EXTS = {
    ".md", ".py", ".sh", ".json", ".json5", ".yaml", ".yml", ".toml", ".txt",
    ".ets", ".ts", ".cpp", ".h", ".hpp", ".cmake", ".cfg", ".ini", ".prf", ".pro",
}
MAX_SCAN_BYTES = 2 * 1024 * 1024
# Common placeholder user names don't count as leaks (used in doc examples)
PLACEHOLDER_USERS = {"you", "yourname", "username", "currentuser", "user", "example", "me"}
LOCAL_PATH_RE = re.compile(r"/Users/([A-Za-z0-9._-]+)/")
WIN_PATH_RE = re.compile(r"[A-Za-z]:\\\\?[Uu]sers\\\\?([A-Za-z0-9._-]+)")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return ""


def frontmatter(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    return text[4:end] if end != -1 else None


def fm_field(fm: str, key: str) -> str | None:
    m = re.search(rf"^{re.escape(key)}:[ \t]*(.*)$", fm, re.M)
    return m.group(1).strip() if m else None


_GIT_VISIBLE: set[str] | None = None
_GIT_PROBED = False
INCLUDE_IGNORED = False


def _git_visible_files() -> set[str] | None:
    """The set of files in this repo that git tracks or does not ignore; None outside git.

    The hygiene check must only look at "what would be committed": the Qt build tree in the local
    `workspace/` and the local absolute paths in `ENV.local.md` are gitignored; scanning them
    produces hundreds of entries of noise unrelated to the commit that drown the real errors
    (134 entries measured on a Windows machine).
    """
    global _GIT_VISIBLE, _GIT_PROBED
    if _GIT_PROBED:
        return _GIT_VISIBLE
    _GIT_PROBED = True
    try:
        proc = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError:
        _GIT_VISIBLE = None
        return None
    if proc.returncode != 0:
        _GIT_VISIBLE = None
        return None
    raw = proc.stdout.decode("utf-8", errors="replace")
    _GIT_VISIBLE = {item for item in raw.split("\0") if item}
    return _GIT_VISIBLE


def walk_files(root: Path):
    visible = None if INCLUDE_IGNORED else _git_visible_files()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            path = Path(dirpath) / name
            if visible is not None:
                try:
                    rel = path.relative_to(root).as_posix()
                except ValueError:
                    rel = path.as_posix()
                if rel not in visible:
                    continue
            yield path


# ---------------------------------------------------------------- contract checks

CONTRACT_KEYS = [
    "schema_version", "id", "kind", "entrypoint", "map", "verify",
    "tooling_contract_version", "default_audience",
]


def load_contract() -> dict:
    path = ROOT / "kb.yaml"
    if not path.exists():
        error("C1", "missing repository contract kb.yaml")
        return {}
    contract: dict = {}
    current_list: str | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith("  - ") and current_list:
            contract.setdefault(current_list, []).append(raw[4:].strip())
            continue
        m = re.match(r"^([A-Za-z0-9_]+):[ \t]*(.*)$", raw)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        if value:
            contract[key] = value
            current_list = None
        else:
            current_list = key
            contract.setdefault(key, [])
    for key in CONTRACT_KEYS:
        if not contract.get(key):
            error("C1", f"kb.yaml is missing required key {key}")
    return contract


def check_paths(contract: dict) -> None:
    for rel in contract.get("required_paths", []):
        if not (ROOT / rel).exists():
            error("C2", f"path required by the contract does not exist: {rel}")
    for rel in contract.get("optional_paths", []):
        if not (ROOT / rel).exists():
            info(f"optional path missing (not a failure): {rel}")
    entry = contract.get("entrypoint")
    if entry and not (ROOT / entry).exists():
        error("C2", f"entry file does not exist: {entry}")
    idx = contract.get("map")
    if idx and not (ROOT / idx).exists():
        error("C2", f"knowledge map does not exist: {idx}")


def check_entrypoints() -> None:
    agents = ROOT / "AGENTS.md"
    claude = ROOT / "CLAUDE.md"
    if not agents.exists():
        error("C3", "missing AGENTS.md")
        return
    if not claude.exists():
        warn("C3", "missing CLAUDE.md (Claude Code users must copy AGENTS.md by hand)")
        return
    if agents.read_text(encoding="utf-8") != claude.read_text(encoding="utf-8"):
        error("C3", "AGENTS.md and CLAUDE.md differ (CLAUDE.md should be a copy of AGENTS.md)")


# ---------------------------------------------------------------- knowledge page checks

# Required fields per domain (keeps each domain's existing schema differences; converging gradually)
DOMAIN_RULES = {
    "semantic": ["id", "type", "summary", "status", "audience"],
    "procedural": ["id", "type", "summary", "status", "audience"],
    "episodic": ["id", "type", "summary", "status", "audience"],
    "problems": ["id", "type", "summary", "status", "audience"],
    "ohos-common-kb-public": ["id", "summary", "status", "audience"],
}

PAGE_GLOBS = [
    ("semantic", "semantic/*.md"),
    ("procedural", "procedural/*.md"),
    ("episodic", "episodic/postmortems/*.md"),
    ("problems", "problems/*.md"),
    ("ohos-common-kb-public", "ohos-common-kb-public/*/*.md"),
]


def collect_pages() -> tuple[list[tuple[str, Path, str]], dict[str, str]]:
    pages: list[tuple[str, Path, str]] = []
    ids: dict[str, str] = {}
    for domain, pattern in PAGE_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            if path.name.startswith("_"):
                continue
            text = read_text(path)
            fm = frontmatter(text)
            rel = str(path.relative_to(ROOT))
            if fm is None:
                error("C4", f"{rel} is missing frontmatter")
                continue
            pages.append((domain, path, fm))
            for field in DOMAIN_RULES.get(domain, ["id", "summary", "status", "audience"]):
                if not fm_field(fm, field):
                    error("C4", f"{rel} is missing frontmatter field {field}")
            pid = fm_field(fm, "id")
            if pid:
                if pid in ids:
                    error("C5", f"duplicate id: {pid} ({ids[pid]} and {rel})")
                ids[pid] = rel
            audience = fm_field(fm, "audience")
            if audience and audience != "public":
                error("C6", f"{rel} has audience={audience} (the public repo only allows public)")
    return pages, ids


def head_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True, timeout=15)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def tracked_files() -> list[str]:
    """Checked-in file list: prefer git ls-files (authoritative), otherwise fall back to walking the filesystem."""
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                             capture_output=True, text=True, timeout=30)
        if out.returncode == 0 and out.stdout:
            return [x for x in out.stdout.split("\0") if x]
    except (OSError, subprocess.SubprocessError):
        pass
    return sorted(str(p.relative_to(ROOT)) for p in walk_files(ROOT))


def content_tree_sha256() -> str:
    """sha256 over sorted("<relpath>\\0<sha256(file)>\\n"), excluding the manifest itself."""
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


def count_tests() -> int:
    def count(*rels: str) -> int:
        total = 0
        for rel in rels:
            try:
                tree = ast.parse(read_text(ROOT / rel))
            except SyntaxError:
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


def _yaml_value(raw: str) -> str:
    """Get a scalar value: strip the trailing comment and quotes (no splitting inside quotes)."""
    v = raw.strip()
    if v[:1] in ('"', "'"):
        quote = v[0]
        end = v.find(quote, 1)
        return v[1:end] if end != -1 else v.strip(quote)
    idx = v.find(" #")
    return (v[:idx] if idx != -1 else v).strip()


def _yaml_scalars(text: str) -> dict:
    """Only reads top-level `key: value` and one-level-indented `  key: value`; enough for the manifest."""
    flat: dict = {}
    section = ""
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = re.match(r"^  ([A-Za-z0-9_]+):[ \t]*(.*)$", raw)
        if m and section:
            flat[f"{section}.{m.group(1)}"] = _yaml_value(m.group(2))
            continue
        m = re.match(r"^([A-Za-z0-9_]+):[ \t]*(.*)$", raw)
        if m:
            value = _yaml_value(m.group(2))
            if value:
                flat[m.group(1)] = value
                section = ""
            else:
                section = m.group(1)
    return flat


def check_manifest(pages: list[tuple[str, Path, str]]) -> None:
    """The fields of the release manifest (RELEASE-MANIFEST.yaml) must match the actual repository.

    In the trunk-candidate stage only structural facts are checked (page counts / skills / test
    counts / enum values); once status=released, the content tree digest and root_commit must
    match too -- otherwise "reconcilable" is just words.
    """
    path = ROOT / "RELEASE-MANIFEST.yaml"
    if not path.exists():
        warn("M1", "missing RELEASE-MANIFEST.yaml (release manifest; should be permanent from trunk on)")
        return
    fm = _yaml_scalars(read_text(path))

    version = fm.get("release_version", "")
    if not re.match(r"^v\d+\.\d+\.\d+$", version):
        error("M1", f"release_version has an invalid format: {version!r} (should look like v3.0.0)")
    status = fm.get("status", "")
    if status not in ("trunk-candidate", "released", "retired"):
        error("M1", f"status has an invalid value: {status!r} (trunk-candidate / released / retired)")

    common = sum(1 for d, _, _ in pages if d == "ohos-common-kb-public")
    qt_side = len(pages) - common
    for key, actual in (("common_pages_count", common), ("qt_pages_count", qt_side)):
        claimed = fm.get(key, "")
        if not claimed.isdigit():
            error("M1", f"{key} missing or not an integer: {claimed!r}")
        elif int(claimed) != actual:
            error("M1", f"{key}={claimed}, actual {actual} (update the manifest when the page count changes)")

    skills = re.findall(r'"([^"]+)"', fm.get("skills", ""))
    actual_skills = sorted(p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md"))
    if sorted(skills) != actual_skills:
        error("M1", f"skills list does not match the skills/ directory: manifest {sorted(skills)}, actual {actual_skills}")

    claimed_tests = fm.get("validation.unittests", "")
    actual_tests = count_tests()
    if not claimed_tests.isdigit():
        error("M1", f"validation.unittests missing or not an integer: {claimed_tests!r}")
    elif int(claimed_tests) != actual_tests:
        error("M1", f"validation.unittests={claimed_tests}, actual {actual_tests}")

    digest = fm.get("content_tree_sha256", "")
    if not re.match(r"^[0-9a-f]{64}$", digest):
        error("M1", "content_tree_sha256 missing or not 64 lowercase hex digits")
        return
    actual_digest = content_tree_sha256()
    if status == "released":
        root_commit = fm.get("root_commit", "")
        if not re.match(r"^[0-9a-f]{40}$", root_commit):
            error("M1", "status=released but root_commit is not backfilled (40-character SHA)")
            return
        # Only enforce digest consistency when on the release commit; normal commits after the release are not errors (the tree has moved on)
        if head_commit() == root_commit and digest != actual_digest:
            error("M1", "on the release commit, content_tree_sha256 does not match the tree"
                        " (the manifest was changed or the commit was tampered with)")
        elif head_commit() != root_commit:
            info("release %s was archived at %s…; the current tree is after it" % (version[:12], root_commit[:12]))
    elif digest != actual_digest:
        info("the release manifest is a %s snapshot (%s…) that differs from the current tree -- at release time run "
             "_scripts/gen-manifest.py to refresh it" % (version, digest[:12]))


def _strip_inline_code(line: str) -> str:
    """Replace inline code spans with blanks so example syntax isn't taken as a real link."""
    return re.sub(r"`[^`]*`", lambda m: " " * len(m.group(0)), line)


def check_relative_links() -> None:
    """Markdown relative .md links must point to existing files (C10).

    C7 only checks `[[wikilink]]`; relative links like `](path.md)` were never checked, and in
    practice there was already one root-relative link (which necessarily breaks when resolved
    from a subdirectory) that neither the renderer nor Obsidian could open.
    """
    for path in walk_files(ROOT):
        if path.suffix != ".md":
            continue
        rel = path.relative_to(ROOT).as_posix()
        in_fence = False
        for line in read_text(path).splitlines():
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            # A `](x.md)` inside inline code is an example, not a link
            for match in re.finditer(r"\]\(([^)\s#]+\.md)(?:#[^)]*)?\)",
                                     _strip_inline_code(line)):
                target = match.group(1)
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                if not (path.parent / target).exists():
                    error("C10", f"relative link points to a nonexistent file: {rel} -> {target}")


INDEX_ENTRY_FILES = (
    "_index/_map.md", "_index/_tags.md", "_index/_task-routing.md",
    "_index/_dashboard.md", "problems/_lookup.md",
    "ohos-common-kb-public/_index.md",
)


def check_page_reachability(pages: list) -> None:
    """Every knowledge page must appear in at least one index (C11).

    Of 132 pages only 45 were once in `_map`; the rest relied on full-repo search. A page that is
    written but can't be found by following the map is invisible to an Agent. The index entry
    can be _map/_tags/_task-routing/_lookup/the embedded library index.
    """
    texts = []
    for rel in INDEX_ENTRY_FILES:
        path = ROOT / rel
        if path.exists():
            texts.append(read_text(path))
    orphan = []
    for dirname, path, _aud in pages:
        if path.name.startswith("_"):
            continue
        if not any(path.name in text for text in texts):
            orphan.append(path.relative_to(ROOT).as_posix())
    for rel in orphan:
        error("C11", f"page is not in any index (an Agent following the map can't see it): {rel}")


def check_dashboard_generated() -> None:
    """`_index/_dashboard.md` must match the generator output (C9).

    The dashboard's page count, per-domain active counts, number of problems entries, and fault
    graph size are derived facts; writing them by hand inevitably drifts (a header of 15 with
    14 pages in the table was observed). Numbers may only be updated via `_scripts/gen-dashboard.py`.
    """
    import importlib.util
    gen = ROOT / "_scripts" / "gen-dashboard.py"
    dash = ROOT / "_index" / "_dashboard.md"
    if not gen.exists() or not dash.exists():
        warn("C9", "missing _scripts/gen-dashboard.py or _index/_dashboard.md")
        return
    try:
        spec = importlib.util.spec_from_file_location("kb_gen_dashboard", gen)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        generated = module.render()
    except Exception as exc:                       # pragma: no cover - a broken generator must be visible
        warn("C9", f"gen-dashboard.py failed to run: {exc}")
        return
    strip = lambda text: re.sub(r"^updated: .*$", "", text, count=1, flags=re.M)  # noqa: E731
    if strip(generated) != strip(read_text(dash)):
        error("C9", "_index/_dashboard.md does not match the generator output"
                    " (run python _scripts/gen-dashboard.py; don't edit the numbers by hand)")


def check_wikilinks(ids: dict[str, str]) -> None:
    # Only look at tracked files: third-party docs in `workspace/`, `.hvigor-home/`, `node_modules/`
    # (such as minimatch's `[[Prototype]]`) are not this repo's content; scanning them only creates
    # noise and forces users to delete build caches to get the gate green.
    files = [p for p in walk_files(ROOT) if p.suffix == ".md"]
    names = {p.stem for p in files}
    broken: dict[str, int] = {}
    for path in files:
        in_fence = False
        for line in read_text(path).splitlines():
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for m in re.finditer(r"\[\[([^\]\|]+)(?:\|[^\]]*)?\]\]", line):
                target = m.group(1).split("#")[0].strip()
                if not target:
                    continue
                base = Path(target).stem
                if base in names or target in ids:
                    continue
                broken[target] = broken.get(target, 0) + 1
    for target, count in sorted(broken.items(), key=lambda kv: -kv[1]):
        error("C7", f"wikilink cannot be resolved: [[{target}]] ({count} occurrences)")


def check_index_consistency(pages: list[tuple[str, Path, str]]) -> None:
    dash = ROOT / "_index/_dashboard.md"
    if not dash.exists():
        warn("C8", "missing _index/_dashboard.md")
        return
    fm = frontmatter(read_text(dash)) or ""
    claimed = fm_field(fm, "total_pages")
    if not claimed:
        return
    try:
        claimed_n = int(claimed)
    except ValueError:
        warn("C8", f"total_pages in _dashboard.md is not an integer: {claimed}")
        return
    # Same scope as _dashboard: count only semantic/procedural/episodic/preference;
    # problems and the embedded common-KB are counted separately (see problems/_lookup and the manifest).
    scoped = [p for p in pages if p[0] in ("semantic", "procedural", "episodic")]
    archived = sum(1 for _, _, page_fm in scoped
                   if (fm_field(page_fm, "status") or "") == "archived")
    actual = len(scoped) - archived
    if claimed_n != actual:
        warn("C8", f"_dashboard.md claims {claimed_n} active pages, actual {actual} ({archived} archived)")


# ---------------------------------------------------------------- hygiene checks

def check_hygiene() -> None:
    artifacts: dict[str, int] = {}
    leaks: list[str] = []
    if not INCLUDE_IGNORED and _git_visible_files() is None:
        # Without git there is no basis for "which files would be committed": noise is then
        # inevitable and must be stated, otherwise users would think these H2s are real leaks.
        warn("H1", "git not detected (or not inside a work tree): the hygiene check cannot skip gitignored"
                   " local files, so H2 noise is expected; reproduce explicitly with --include-ignored")
    for path in walk_files(ROOT):
        rel = path.relative_to(ROOT)
        parts = set(rel.parts[:-1])
        if path.name == ".DS_Store" or path.suffix == ".pyc" or path.name == "__pycache__":
            key = path.name if path.name != "__pycache__" else "__pycache__"
            artifacts[key] = artifacts.get(key, 0) + 1
            continue
        hit = parts & ARTIFACT_DIRS
        if hit:
            key = "/".join(sorted(hit))
            artifacts[key] = artifacts.get(key, 0) + 1
            continue
        if path.suffix.lower() not in TEXT_EXTS:
            continue
        try:
            if path.stat().st_size > MAX_SCAN_BYTES:
                continue
        except OSError:
            continue
        text = read_text(path)
        if not text:
            continue
        hit = None
        for m in LOCAL_PATH_RE.finditer(text):
            if m.group(1).lower() not in PLACEHOLDER_USERS:
                hit = m.group(0)
                break
        if hit is None:
            for m in WIN_PATH_RE.finditer(text):
                if m.group(1).lower() not in PLACEHOLDER_USERS:
                    hit = m.group(0)
                    break
        if hit:
            leaks.append(f"{rel}: {hit}")
    for key, count in sorted(artifacts.items()):
        warn("H1", f"build/system artifact directory {key} exists in the committed tree ({count} files)")
    for leak in leaks:
        error("H2", f"file contains a local absolute path: {leak}")


# ---------------------------------------------------------------- main flow

def main() -> int:
    parser = argparse.ArgumentParser(description="ohos-qt-skills repository self-check")
    parser.add_argument("--quiet", action="store_true", help="print ERROR/WARN only")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--include-ignored", action="store_true",
                        help="also scan gitignored local files (by default only files that would be committed)")
    args = parser.parse_args()
    global INCLUDE_IGNORED
    INCLUDE_IGNORED = args.include_ignored

    contract = load_contract()
    check_paths(contract)
    check_entrypoints()
    pages, ids = collect_pages()
    check_wikilinks(ids)
    check_relative_links()
    check_page_reachability(pages)
    check_index_consistency(pages)
    check_dashboard_generated()
    check_manifest(pages)
    check_hygiene()

    ok = not ERRORS
    if args.json:
        print(json.dumps(
            {"ok": ok, "errors": ERRORS, "warnings": WARNS, "info": INFOS,
             "pages": len(pages)},
            ensure_ascii=False, indent=2))
    else:
        if not args.quiet:
            contract_id = contract.get("id", "?")
            print(f"ohos-qt-skills verify — contract {contract_id} v{contract.get('schema_version', '?')}"
                  f" (tooling v{contract.get('tooling_contract_version', '?')})")
            print(f"content pages: {len(pages)} | ids: {len(ids)}")
            for line in INFOS:
                print(f"  INFO  {line}")
        for line in WARNS:
            print(f"  WARN  {line}")
        for line in ERRORS:
            print(f"  ERROR {line}")
        print(f"RESULT: {'PASS' if ok else 'FAIL'}"
              f" ({len(ERRORS)} errors, {len(WARNS)} warnings)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
