"""Knowledge-base consistency self-tests for ohos_qt-skills (v2.3.0).

Covers the "knowledge base self-consistency" layer beyond the engine tests (test_qt_ohos.py)
and the portgraph tests (portgraph/tests/) -- it binds the claims in README / SKILL.md /
AGENTS.md / the index pages to the actual state of the repository (keep numbers real: number
drift is caught before commit):

  L1 Skill manifest rules      root and sub-level SKILL.md frontmatter (name/description length),
                               completeness of the AGENTS skill table
  L2 Documented count          QOH / R rules / iron rules / task routes / API mappings / problems /
     consistency               faults graph size / test case counts -- documented claim == actual value
  L3 Cross-reference           QOH refs -> problems pages; path references in README/SKILL.md/
     integrity                 AGENTS.md/_task-routing resolve; README links and anchors
  L4 CLI contract              the subcommand sets of the three CLIs (adding/removing a subcommand
                               must explicitly update this test)
  L5 Integration gate          faults-build check (source of truth <-> derived artifacts, ERROR must be 0)

Run from the repository root:

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

from qt_ohos import yaml_lite  # noqa: E402


def read(rel: str) -> str:
    # utf-8-sig: tolerate the odd file with a BOM (such as knowledge/*/index.yaml)
    return (REPO_ROOT / rel).read_text(encoding="utf-8-sig")


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def claim(text: str, pattern: str, origin: str) -> int:
    """Extract a numeric claim from a doc; fail if not found (so a wording change can't silently drop the guard)."""
    m = re.search(pattern, text)
    if not m:
        raise AssertionError(f"claim pattern {pattern!r} not found in {origin} (if the wording changed, update the test to match)")
    return int(m.group(1))


def claims(text: str, pattern: str, origin: str):
    """Return every matching number in a doc (when one claim is scattered over several places, each must be right)."""
    found = [int(m) for m in re.findall(pattern, text)]
    if not found:
        raise AssertionError(f"claim pattern {pattern!r} not found in {origin} (if the wording changed, update the test to match)")
    return found


def count_tests(*paths: str) -> int:
    """Count the test_ methods in Test* classes via the AST.

    Counting "def test_ " with grep doesn't work: this very file contains regex strings that
    match that literal and would be miscounted as test cases. The AST only sees real function
    definitions.
    """
    total = 0
    for rel in paths:
        tree = ast.parse(read(rel))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                total += sum(1 for item in node.body
                             if isinstance(item, ast.FunctionDef)
                             and item.name.startswith("test_"))
    return total


# --------------------------------------------------------------------------
# L1 Skill manifest rules
# --------------------------------------------------------------------------

def parse_frontmatter(text: str):
    """Parse `---`-fenced frontmatter and return (name, description).

    A file that doesn't start with frontmatter (such as a legacy *** fence) returns (None, None).
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, None
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return None, None
    name, desc_lines, in_desc = None, [], False
    for ln in lines[1:end]:
        m = re.match(r"name:\s*(\S+)", ln)
        if m:
            name, in_desc = m.group(1), False
            continue
        m = re.match(r"description:\s*(.*)", ln)
        if m:
            rest = m.group(1).strip()
            if rest and not rest.startswith(("|", ">")):
                desc_lines.append(rest.strip('"'))
                in_desc = False
            else:
                in_desc = True
            continue
        if in_desc:
            if ln.startswith((" ", "\t")):
                desc_lines.append(ln.strip())
            else:
                in_desc = False
    return name, " ".join(desc_lines)


class TestSkillManifest(unittest.TestCase):
    """The root SKILL.md and skills/*/SKILL.md must be valid Agent Skill manifests."""

    def test_root_skill_frontmatter(self):
        name, desc = parse_frontmatter(read("SKILL.md"))
        self.assertEqual(name, "ohos-qt-skills")
        self.assertRegex(name or "", r"^[a-z0-9-]{1,64}$")
        self.assertTrue(desc, "description must not be empty")
        self.assertLessEqual(len(desc), 1024, f"description is {len(desc)} characters, over the 1024 limit")

    def test_subskill_frontmatter(self):
        skills_dir = REPO_ROOT / "skills"
        dirs = sorted(d for d in skills_dir.iterdir() if d.is_dir())
        self.assertGreaterEqual(len(dirs), 5)
        for d in dirs:
            with self.subTest(skill=d.name):
                name, desc = parse_frontmatter(read(f"skills/{d.name}/SKILL.md"))
                self.assertIsNotNone(
                    name,
                    f"skills/{d.name}/SKILL.md frontmatter is invalid (must start with a --- fence)")
                self.assertEqual(name, d.name, "frontmatter name must match the directory name")
                self.assertRegex(name, r"^[a-z0-9-]{1,64}$")
                self.assertTrue(desc, "description must not be empty")
                self.assertLessEqual(len(desc), 1024)

    def test_agents_registers_all_skills(self):
        agents = read("AGENTS.md")
        for d in sorted((REPO_ROOT / "skills").iterdir()):
            if d.is_dir():
                self.assertIn(f"`{d.name}`", agents,
                              f"the AGENTS.md skill table does not register skills/{d.name}")
        self.assertIn("`portgraph`", agents, "AGENTS.md should register the portgraph repository tool")


# --------------------------------------------------------------------------
# L2 Documented count consistency (keep numbers real)
# --------------------------------------------------------------------------

def qoh_files():
    return sorted((REPO_ROOT / "knowledge" / "errors").glob("QOH*.yaml"))


def rule_files():
    return sorted((REPO_ROOT / "knowledge" / "rules").glob("R*.yaml"))


# episodic knowledge pages live in the postmortems/ subdirectory
PAGE_DIRS = {"semantic": "semantic", "procedural": "procedural",
             "episodic": "episodic/postmortems", "problems": "problems"}


def pages(domain: str):
    return [p for p in (REPO_ROOT / PAGE_DIRS[domain]).glob("*.md")
            if not p.name.startswith("_")]


class TestLinkAndReachabilityChecks(unittest.TestCase):
    """New gates: relative .md link existence (C10) and page index reachability (C11)."""

    def _verify(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "kb_verify_probe", REPO_ROOT / "_scripts" / "verify.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_broken_relative_link_detected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sub").mkdir()
            (root / "sub" / "a.md").write_text(
                "see [b](b.md) and [ok](../ok.md)\n", encoding="utf-8")
            (root / "ok.md").write_text("# ok\n", encoding="utf-8")
            mod = self._verify()
            mod.ROOT = root
            mod.INCLUDE_IGNORED = True
            mod.ERRORS.clear()
            mod.check_relative_links()
            joined = "\n".join(mod.ERRORS)
            self.assertIn("[C10]", joined)
            self.assertIn("b.md", joined)
            self.assertNotIn("ok.md", joined)

    def test_gitignored_markdown_does_not_break_wikilinks(self):
        # Third-party docs in build caches (minimatch's `[[Prototype]]`) are not this repo's content:
        # the old implementation rglob'ed the whole tree, forcing users to delete caches to get the gate green.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "cache" / "hvigor").mkdir(parents=True)
            (root / "cache" / "hvigor" / "vendor.md").write_text(
                "see [[Prototype]] and [[toString]]\n", encoding="utf-8")
            (root / "a.md").write_text("# a\n", encoding="utf-8")
            mod = self._verify()
            mod.ROOT = root
            mod.INCLUDE_IGNORED = False
            mod._GIT_PROBED = True
            mod._GIT_VISIBLE = {"a.md"}
            mod.ERRORS.clear()
            mod.check_wikilinks({})
            self.assertEqual(mod.ERRORS, [])
            # Reverse control: when ignored files are forcibly included they must be reported (otherwise the test itself verifies nothing)
            mod.INCLUDE_IGNORED = True
            mod.ERRORS.clear()
            mod.check_wikilinks({})
            self.assertIn("[C7]", "\n".join(mod.ERRORS))

    def test_inline_code_link_is_not_flagged(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.md").write_text(
                "syntax example: `](path.md)` is not a real link\n", encoding="utf-8")
            mod = self._verify()
            mod.ROOT = root
            mod.INCLUDE_IGNORED = True
            mod.ERRORS.clear()
            mod.check_relative_links()
            self.assertEqual(mod.ERRORS, [])

    def test_orphan_page_detected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "problems").mkdir()
            page = root / "problems" / "lonely.md"
            page.write_text("# x\n", encoding="utf-8")
            (root / "problems" / "_lookup.md").write_text("# other page\n", encoding="utf-8")
            mod = self._verify()
            mod.ROOT = root
            mod.ERRORS.clear()
            mod.check_page_reachability([("problems", page, "public")])
            self.assertTrue(any("[C11]" in e and "lonely.md" in e
                                for e in mod.ERRORS))

    def test_page_listed_in_index_passes(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "problems").mkdir()
            page = root / "problems" / "known.md"
            page.write_text("# x\n", encoding="utf-8")
            (root / "problems" / "_lookup.md").write_text(
                "- [known](known.md)\n", encoding="utf-8")
            mod = self._verify()
            mod.ROOT = root
            mod.ERRORS.clear()
            mod.check_page_reachability([("problems", page, "public")])
            self.assertEqual(mod.ERRORS, [])


class TestDocumentedCounts(unittest.TestCase):
    """Numeric claims in the docs must equal the actual repository values; update the docs when the actual values change."""

    @classmethod
    def setUpClass(cls):
        cls.readme = read("README.md")
        cls.skill = read("SKILL.md")
        cls.agents = normalized(read("AGENTS.md"))
        cls.routing = read("_index/_task-routing.md")
        cls.dashboard = read("_index/_dashboard.md")
        cls.testing = read("TESTING.md")

    def test_qoh_count(self):
        actual = len(qoh_files())
        index = yaml_lite.parse(read("knowledge/errors/index.yaml"))
        self.assertEqual(int(index["entry_count"]), actual,
                         "knowledge/errors/index.yaml entry_count does not match the file count")
        self.assertEqual(claim(self.readme, r"(\d+) QOH error patterns", "README"), actual)
        # Counts appear only in README / the manifest / the dashboard; guidance docs (SKILL/AGENTS/routing)
        # no longer state numbers, so a change in the facts doesn't need 5 hand edits (missed three times historically).
        for name, text in (("SKILL.md", self.skill), ("AGENTS.md", self.agents),
                           ("_task-routing", self.routing)):
            self.assertIsNone(re.search(r"\d+ (?:QOH|error patterns?)\b", text),
                              f"{name} should no longer state a QOH count; use wording without a number")

    def test_rule_count(self):
        actual = len(rule_files())
        index = yaml_lite.parse(read("knowledge/rules/index.yaml"))
        self.assertEqual(int(index["rule_count"]), actual)
        self.assertEqual(claim(self.readme, r"(\d+) pre-scan rules", "README"), actual)

    def test_golden_rules_total(self):
        golden = read("semantic/qt-harmonyos-golden-rules.md")
        total = sum(int(m) for m in
                    re.findall(r"^## .*\((\d+) rules?\)", golden, re.M))
        self.assertEqual(claim(self.readme, r"(\d+) iron rules", "README"), total)
        for name, text in (("SKILL.md", self.skill), ("_task-routing", self.routing)):
            self.assertIsNone(re.search(r"\d+ (?:golden|iron) rules?\b", text),
                              f"{name} should no longer state an iron rule count; use wording without a number")

    def test_routing_codes(self):
        codes = re.findall(r"^### \[([A-Z])\]", self.routing, re.M)
        self.assertEqual(len(codes), 16, f"the number of task routes changed: {codes}")
        self.assertEqual(set(codes), set("ABCDEFGHLMNOPQRS"))
        self.assertEqual(claim(self.readme, r"(\d+) task types", "README"), len(codes))

    def test_api_mapping_categories(self):
        n = len(re.findall(r"^## \d+", read("semantic/qt-harmonyos-api-mapping.md"), re.M))
        self.assertEqual(claim(self.readme, r"(\d+) API mapping categories", "README"), n)

    def test_problems_pages(self):
        actual = len(pages("problems"))
        self.assertEqual(claim(self.readme, r"(\d+) real-world pitfall", "README"), actual)
        self.assertEqual(
            claim(self.dashboard, r"problems \((\d+) entries\)", "_dashboard"), actual)

    def test_dashboard_domain_counts(self):
        """"Active" excludes archived: the scope must match verify's C8 check."""
        def active(domain):
            return [p for p in pages(domain)
                    if "status: archived" not in
                    read(p.relative_to(REPO_ROOT).as_posix())]

        for domain in ("semantic", "procedural", "episodic"):
            claimed = claim(self.dashboard, rf"{domain} \((\d+) active\)", "_dashboard")
            self.assertEqual(claimed, len(active(domain)),
                             f"_dashboard {domain} count is stale")
        total = sum(len(active(d)) for d in ("semantic", "procedural", "episodic"))
        self.assertEqual(
            claim(self.dashboard, r"Total active\*\* \| \*\*(\d+)", "_dashboard"), total)

    def test_dashboard_is_generated(self):
        """The dashboard is a derived view: it must match the generator output (numbers may not be edited by hand)."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "gen_dashboard_probe", REPO_ROOT / "_scripts" / "gen-dashboard.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        generated = re.sub(r"^updated: .*$", "", mod.render(), count=1, flags=re.M)
        current = re.sub(r"^updated: .*$", "", self.dashboard, count=1, flags=re.M)
        self.assertEqual(current, generated,
                         "_dashboard.md does not match the generator output: run python _scripts/gen-dashboard.py")

    def test_ohos_extras_api_claim(self):
        semantic = read("semantic/qt-ohos-extras.md")
        m = re.search(r"(\d+)\+", semantic)
        self.assertIsNotNone(m, "semantic/qt-ohos-extras.md is missing the N+ total API count claim")
        self.assertEqual(claim(self.readme, r"(\d+)\+ QtOhosExtras", "README"),
                         int(m.group(1)))

    def test_faults_graph_counts(self):
        registry = "\n".join(read("faults/_registry.md").splitlines()[:15])
        counts = {k: int(re.search(rf"{k}:\s*(\d+)", registry).group(1))
                  for k in ("symptoms", "causes", "workarounds", "tickets")}
        # README core capability row: "S→C→W→T fault graph (17/18/15/5)"
        m = re.search(r"fault graph \((\d+)/(\d+)/(\d+)/(\d+)\)", self.readme)
        self.assertIsNotNone(m, "README is missing the fault graph size claim")
        self.assertEqual(
            tuple(int(x) for x in m.groups()),
            (counts["symptoms"], counts["causes"],
             counts["workarounds"], counts["tickets"]))
        # _dashboard faults row
        m2 = re.search(
            r"\((\d+) records: (\d+) symptoms S \+ (\d+) root causes C \+ (\d+) workarounds W \+ (\d+) tracking tickets T\)",
            self.dashboard)
        self.assertIsNotNone(m2, "_dashboard is missing the fault statistics row")
        self.assertEqual(tuple(int(x) for x in m2.groups()[1:]),
                         (counts["symptoms"], counts["causes"],
                          counts["workarounds"], counts["tickets"]))

    def test_testcase_counts(self):
        """Count test cases for real via the AST and check every claim in README / TESTING.md.

        Lessons learned: counting "def test_" with grep once counted two literals in this file's
        regex strings as test cases (claimed 22, actually 20); portgraph counted only the graph
        file and missed the 4 in test_prefetch.py (claimed 119, actually 123).
        """
        engine = count_tests("tests/test_qt_ohos.py")
        consistency = count_tests("tests/test_kb_consistency.py")
        scanner = count_tests("tests/test_cpp20_gap_scan.py")
        graph = count_tests("portgraph/tests/test_port_graph.py",
                            "portgraph/tests/test_prefetch.py")
        expected = (engine, consistency, scanner)

        triple = re.compile(r"engine (\d+) \+ consistency (\d+) \+ (?:cpp20 )?scan (\d+)")
        for origin, text in (("README", self.readme), ("TESTING.md", self.testing)):
            found = triple.findall(text)
            self.assertTrue(found, f"{origin} is missing the \"engine N + consistency N + scan N\" test case claim")
            for got in found:
                self.assertEqual(tuple(int(x) for x in got), expected,
                                 f"{origin} claims {got}, actual {expected}")
            # Graph count: the two docs word it differently (N graph unit tests / N portgraph unit tests);
            # check it wherever it appears, without requiring each doc to state it (the triple above is the fallback for the total)
            for got in (int(x) for x in re.findall(r"(\d+) graph unit tests", text)):
                self.assertEqual(got, graph, f"{origin} claims {got} graph unit tests, actual {graph}")
            for got in (int(x) for x in re.findall(r"(\d+) portgraph unit tests", text)):
                self.assertEqual(got, graph, f"{origin} claims {got} portgraph unit tests, actual {graph}")

    def test_docs_counts_synced(self):
        """The derived numbers in README / TESTING must match `_scripts/sync-counts.py`.

        These numbers are re-projected by the script from the source of truth (page count, QOH,
        rules, iron rules, problems, test case count). Adding/removing test cases no longer needs
        three hand edits to the docs, but you **must** run sync-counts once, otherwise this goes red.
        """
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "sync_counts", REPO_ROOT / "_scripts" / "sync-counts.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        counts = module.compute()
        problems = []
        for path in sorted({rel for rel, _p, _b in module.RULES}):
            original = (REPO_ROOT / path).read_text(encoding="utf-8")
            updated = module.apply(original, path, counts, problems)
            self.assertEqual(updated, original,
                             f"the derived numbers in {path} are stale: run python _scripts/sync-counts.py")
        self.assertEqual(problems, [], "anchors for derived numbers are missing: " + "; ".join(problems))


# --------------------------------------------------------------------------
# L3 Cross-reference integrity
# --------------------------------------------------------------------------

KB_DIRS = ("semantic", "procedural", "problems", "faults", "_index", "skills")
KNOWN_PREFIXES = ("semantic/", "procedural/", "episodic/", "problems/", "faults/",
                  "_index/", "skills/", "tools/", "portgraph/", "templates/",
                  "tests/", "knowledge/", "ohos-common-kb-public/")
RUNTIME_PREFIXES = ("workspace/", ".qt-ohos", ".qtsdk", "ENV", "TODO.local",
                    "dist/", "build/", "outputs/", "entry/", "AppScope/", "qtbase/")


def _candidates(token: str):
    """Resolve a reference token into candidate repository paths.

    Knowledge page naming convention: most pages under semantic/ carry the `qt-harmonyos-` prefix,
    while docs like _task-routing often use a short form (`golden-rules.md` ->
    `semantic/qt-harmonyos-golden-rules.md`); both forms are candidates.
    """
    cands = [token]  # relative to the repository root (such as kb.yaml, ENV.md)
    if "/" in token:
        cands.append(token)
        if not Path(token).suffix:
            cands.append(token + ".md")
    else:
        # short-form prefix convention: full name = qt- prefix + short form (qt-harmonyos-xxx / qt-ohos-extras, etc.)
        for d in KB_DIRS:
            for pfx in ("", "qt-", "qt-harmonyos-", "qt-ohos-"):
                cands.append(f"{d}/{pfx}{token}")
                if not Path(token).suffix:
                    cands.append(f"{d}/{pfx}{token}.md")
    return cands


def missing_refs(text: str, origin: str):
    """Extract repository path references from inline code and return the list that can't be resolved.

    Only tokens that "look like knowledge paths" are positively matched (known directory prefix /
    .md|.yaml suffix / knowledge page naming prefixes like qt-), to avoid mistaking CLI subcommand
    names for paths.
    """
    problems = []
    for token in re.findall(r"`([^`\n]+)`", text):
        t = token.strip()
        if (not t or " " in t or "*" in t or "{" in t or "}" in t or "=" in t
                or t[0].isupper() or t.startswith(("<", "http", "$", "~", "-", "/", "."))):
            continue
        if any(t.startswith(p) for p in RUNTIME_PREFIXES):
            continue
        looks_like_ref = (
            any(t.startswith(p) for p in KNOWN_PREFIXES)
            or Path(t).suffix in (".md", ".yaml")
            or ("/" not in t and Path(t).suffix == ""
                and t.startswith(("qt-", "kb-", "qdrag")))
        )
        if not looks_like_ref:
            continue
        if not any((REPO_ROOT / c).exists() for c in _candidates(t)):
            problems.append(f"{origin}: `{t}` cannot be resolved to a path in the repository")
    return problems


class TestCrossReferences(unittest.TestCase):

    def test_qoh_refs_exist(self):
        for path in qoh_files():
            data = yaml_lite.parse(path.read_text(encoding="utf-8"))
            refs = data.get("refs") or {}
            for key in ("problems", "kb"):
                for ref in refs.get(key) or []:
                    self.assertTrue(
                        (REPO_ROOT / ref).exists(),
                        f"{path.name} refs.{key} points to a nonexistent page: {ref}")

    def test_doc_path_refs_resolve(self):
        problems = []
        for rel in ("README.md", "SKILL.md", "AGENTS.md", "_index/_task-routing.md"):
            problems.extend(missing_refs(read(rel), rel))
        self.assertEqual(problems, [], "\n".join(problems))

    def test_readme_links_and_anchors(self):
        text = read("README.md")
        for target in re.findall(r"\]\(([^)]+)\)", text):
            if target.startswith(("http", "#")):
                continue
            self.assertTrue((REPO_ROOT / target).exists(),
                            f"broken README link: {target}")
        heads = {h.strip().lower().replace(" ", "-")
                 for h in re.findall(r"^#+ (.+)$", text, re.M)}
        for anchor in re.findall(r"\]\(#([^)]+)\)", text):
            self.assertIn(anchor, heads, f"broken README anchor: #{anchor}")


# --------------------------------------------------------------------------
# L4 CLI contract (subcommand sets -- adding/removing commands must explicitly update this)
# --------------------------------------------------------------------------

QT_OHOS_RUN_CMDS = {
    "init", "scan", "plan", "patch", "build", "package", "install", "launch",
    "smoke", "verify", "analyze-log", "status", "resume", "migrate", "finish",
    "assess", "rollback", "mark-gate", "mark-ui", "mark-risk", "draft",
    "promote", "recipes", "config", "libcheck", "pkgconfig", "doctor", "sign",
    "smoke-interact",
}
QT_SDK_RUN_CMDS = {
    "init", "env", "config", "src-clone", "status", "patch-import",
    "patch-apply", "patch-list", "patch-revert", "patch-export", "patch-mark",
    "configure", "build", "install", "verify", "smoke-mark", "release",
    "release-list", "modules", "use", "diff", "upstream-check", "forge",
    "resume",
}
PORTGRAPH_CMDS = {
    "ingest", "clone", "scan", "analyze", "deps", "stats", "fetch",
    "fetch-deps", "export", "serve",
}


def cli_subcommands(script: str):
    env = {**os.environ, "COLUMNS": "300", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / script), "--help"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=120)
    m = re.search(r"\{([^}]+)\}", proc.stdout)
    if not m:
        raise AssertionError(f"{script} --help does not list subcommands:\n{proc.stdout[:500]}")
    return set(m.group(1).split(","))


class TestCliContract(unittest.TestCase):

    def test_qt_ohos_run_subcommands(self):
        self.assertEqual(cli_subcommands("tools/qt-ohos-run.py"),
                         QT_OHOS_RUN_CMDS)

    def test_qt_sdk_run_subcommands(self):
        self.assertEqual(cli_subcommands("tools/qt-sdk-run.py"),
                         QT_SDK_RUN_CMDS)

    def test_portgraph_subcommands(self):
        self.assertEqual(cli_subcommands("portgraph/portgraph.py"),
                         PORTGRAPH_CMDS)


# --------------------------------------------------------------------------
# L5 Integration gate
# --------------------------------------------------------------------------

class TestIntegrationGates(unittest.TestCase):

    def test_faults_build_check_zero_errors(self):
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "tools" / "faults-build.py"), "check"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=300)
        self.assertEqual(
            proc.returncode, 0,
            "faults-build check has ERRORs (source of truth and derived artifacts disagree):\n"
            + proc.stdout[-2000:])


if __name__ == "__main__":
    unittest.main()
