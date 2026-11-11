"""Knowledge-base consistency self-tests for ohos_qt-skills (v2.3.0).

覆盖引擎测试（test_qt_ohos.py）与 portgraph 测试（portgraph/tests/）之外的
"知识库自一致性"层——把 README / SKILL.md / AGENTS.md / 索引页中的声称与
仓库实际状态绑定（keep numbers real，数字漂移在提交前被拦截）：

  L1 Skill 清单规范   根级与子级 SKILL.md frontmatter（name/description 长度）、
                      AGENTS 技能表登记完整性
  L2 文档计数一致性   QOH / R 规则 / 铁律 / 任务路由 / API 映射 / problems /
                      faults 图规模 / 测试用例数——文档声称 == 实际值
  L3 交叉引用完整性   QOH refs → problems 页；README/SKILL.md/AGENTS.md/
                      _task-routing 中的路径引用可解析；README 链接与锚点
  L4 CLI 契约         三个 CLI 的子命令集合（增删子命令须显式更新本测试）
  L5 集成门禁         faults-build check（真源 ↔ 派生物，ERROR 必须为 0）

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
    # utf-8-sig：容忍个别文件带 BOM（如 knowledge/*/index.yaml）
    return (REPO_ROOT / rel).read_text(encoding="utf-8-sig")


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def claim(text: str, pattern: str, origin: str) -> int:
    """从文档中提取数字声称；找不到即失败（防止措辞改动后静默失去守护）。"""
    m = re.search(pattern, text)
    if not m:
        raise AssertionError(f"{origin} 中找不到声称模式 {pattern!r}（措辞变了请同步更新测试）")
    return int(m.group(1))


def claims(text: str, pattern: str, origin: str):
    """返回文档中全部匹配的数字（同一声称散落多处时，每一处都要对）。"""
    found = [int(m) for m in re.findall(pattern, text)]
    if not found:
        raise AssertionError(f"{origin} 中找不到声称模式 {pattern!r}（措辞变了请同步更新测试）")
    return found


def count_tests(*paths: str) -> int:
    """按 AST 统计 Test* 类里的 test_ 方法数。

    不能用 grep 数 "def test_ "：本文件里就有匹配该字面量的正则字符串，
    会被误数成用例。AST 只认真实的函数定义。
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
# L1 Skill 清单规范
# --------------------------------------------------------------------------

def parse_frontmatter(text: str):
    """解析 `---` 围栏的 frontmatter，返回 (name, description)。

    非 frontmatter 起始（如历史遗留的 *** 围栏）返回 (None, None)。
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
    """根级 SKILL.md 与 skills/*/SKILL.md 必须是合法的 Agent Skill 清单。"""

    def test_root_skill_frontmatter(self):
        name, desc = parse_frontmatter(read("SKILL.md"))
        self.assertEqual(name, "ohos-qt-skills")
        self.assertRegex(name or "", r"^[a-z0-9-]{1,64}$")
        self.assertTrue(desc, "description 不能为空")
        self.assertLessEqual(len(desc), 1024, f"description {len(desc)} 字符超限 1024")

    def test_subskill_frontmatter(self):
        skills_dir = REPO_ROOT / "skills"
        dirs = sorted(d for d in skills_dir.iterdir() if d.is_dir())
        self.assertGreaterEqual(len(dirs), 5)
        for d in dirs:
            with self.subTest(skill=d.name):
                name, desc = parse_frontmatter(read(f"skills/{d.name}/SKILL.md"))
                self.assertIsNotNone(
                    name,
                    f"skills/{d.name}/SKILL.md frontmatter 非法（必须以 --- 围栏开头）")
                self.assertEqual(name, d.name, "frontmatter name 必须与目录名一致")
                self.assertRegex(name, r"^[a-z0-9-]{1,64}$")
                self.assertTrue(desc, "description 不能为空")
                self.assertLessEqual(len(desc), 1024)

    def test_agents_registers_all_skills(self):
        agents = read("AGENTS.md")
        for d in sorted((REPO_ROOT / "skills").iterdir()):
            if d.is_dir():
                self.assertIn(f"`{d.name}`", agents,
                              f"AGENTS.md 技能表未登记 skills/{d.name}")
        self.assertIn("`portgraph`", agents, "AGENTS.md 应登记 portgraph 仓库工具")


# --------------------------------------------------------------------------
# L2 文档计数一致性（keep numbers real）
# --------------------------------------------------------------------------

def qoh_files():
    return sorted((REPO_ROOT / "knowledge" / "errors").glob("QOH*.yaml"))


def rule_files():
    return sorted((REPO_ROOT / "knowledge" / "rules").glob("R*.yaml"))


# episodic 的知识页在 postmortems/ 子目录下
PAGE_DIRS = {"semantic": "semantic", "procedural": "procedural",
             "episodic": "episodic/postmortems", "problems": "problems"}


def pages(domain: str):
    return [p for p in (REPO_ROOT / PAGE_DIRS[domain]).glob("*.md")
            if not p.name.startswith("_")]


class TestLinkAndReachabilityChecks(unittest.TestCase):
    """新增门禁：相对 .md 链接存在性（C10）与页面索引可达性（C11）。"""

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
                "见 [b](b.md) 与 [ok](../ok.md)\n", encoding="utf-8")
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

    def test_inline_code_link_is_not_flagged(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.md").write_text(
                "写法示例：`](path.md)` 不是真链接\n", encoding="utf-8")
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
            (root / "problems" / "_lookup.md").write_text("# 其他页\n", encoding="utf-8")
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
    """文档中的数字声称必须等于仓库实际值；实际值变化时同步更新文档。"""

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
                         "knowledge/errors/index.yaml entry_count 与文件数不符")
        self.assertEqual(claim(self.readme, r"(\d+) 条 QOH", "README"), actual)
        # 计数只在 README / 清单 / 仪表盘出现；指导类文档（SKILL/AGENTS/路由）
        # 不再写数字，避免每次事实变化要手改 5 处（历史上漏改过三次）。
        for name, text in (("SKILL.md", self.skill), ("AGENTS.md", self.agents),
                           ("_task-routing", self.routing)):
            self.assertIsNone(re.search(r"\d+ 条 (?:QOH|错误模式)", text),
                              f"{name} 不应再写 QOH 计数，改用不含数字的表述")

    def test_rule_count(self):
        actual = len(rule_files())
        index = yaml_lite.parse(read("knowledge/rules/index.yaml"))
        self.assertEqual(int(index["rule_count"]), actual)
        self.assertEqual(claim(self.readme, r"(\d+) 条预扫描规则", "README"), actual)

    def test_golden_rules_total(self):
        golden = read("semantic/qt-harmonyos-golden-rules.md")
        total = sum(int(m) for m in
                    re.findall(r"^## .*（(\d+) 条）", golden, re.M))
        self.assertEqual(claim(self.readme, r"(\d+) 条铁律", "README"), total)
        for name, text in (("SKILL.md", self.skill), ("_task-routing", self.routing)):
            self.assertIsNone(re.search(r"\d+ 条 (?:黄金)?铁律", text),
                              f"{name} 不应再写铁律计数，改用不含数字的表述")

    def test_routing_codes(self):
        codes = re.findall(r"^### \[([A-Z])\]", self.routing, re.M)
        self.assertEqual(len(codes), 15, f"任务路由数变化：{codes}")
        self.assertEqual(set(codes), set("ABCDEFGHLMNPQRS"))
        self.assertEqual(claim(self.readme, r"(\d+) 类任务", "README"), len(codes))

    def test_api_mapping_categories(self):
        n = len(re.findall(r"^## \d+", read("semantic/qt-harmonyos-api-mapping.md"), re.M))
        self.assertEqual(claim(self.readme, r"(\d+) 类 API 映射", "README"), n)

    def test_problems_pages(self):
        actual = len(pages("problems"))
        self.assertEqual(claim(self.readme, r"(\d+) 个实战踩坑", "README"), actual)
        self.assertEqual(
            claim(self.dashboard, r"problems（(\d+) 条目）", "_dashboard"), actual)

    def test_dashboard_domain_counts(self):
        """「活跃」不含 archived：口径要与 verify 的 C8 检查一致。"""
        def active(domain):
            return [p for p in pages(domain)
                    if "status: archived" not in
                    read(p.relative_to(REPO_ROOT).as_posix())]

        for domain in ("semantic", "procedural", "episodic"):
            claimed = claim(self.dashboard, rf"{domain}（(\d+) 活跃）", "_dashboard")
            self.assertEqual(claimed, len(active(domain)),
                             f"_dashboard {domain} 计数过时")
        total = sum(len(active(d)) for d in ("semantic", "procedural", "episodic"))
        self.assertEqual(
            claim(self.dashboard, r"合计活跃\*\* \| \*\*(\d+)", "_dashboard"), total)

    def test_dashboard_is_generated(self):
        """仪表盘是派生视图：必须与生成器输出一致（数字不许手改）。"""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "gen_dashboard_probe", REPO_ROOT / "_scripts" / "gen-dashboard.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        generated = re.sub(r"^updated: .*$", "", mod.render(), count=1, flags=re.M)
        current = re.sub(r"^updated: .*$", "", self.dashboard, count=1, flags=re.M)
        self.assertEqual(current, generated,
                         "_dashboard.md 与生成器输出不一致：跑 python _scripts/gen-dashboard.py")

    def test_ohos_extras_api_claim(self):
        semantic = read("semantic/qt-ohos-extras.md")
        m = re.search(r"(\d+)\+", semantic)
        self.assertIsNotNone(m, "semantic/qt-ohos-extras.md 缺少 N+ API 总数声称")
        self.assertEqual(claim(self.readme, r"(\d+)\+ QtOhosExtras", "README"),
                         int(m.group(1)))

    def test_faults_graph_counts(self):
        registry = "\n".join(read("faults/_registry.md").splitlines()[:15])
        counts = {k: int(re.search(rf"{k}:\s*(\d+)", registry).group(1))
                  for k in ("symptoms", "causes", "workarounds", "tickets")}
        # README 核心能力行："S→C→W→T 故障图（17/18/15/5）"
        m = re.search(r"故障图（(\d+)/(\d+)/(\d+)/(\d+)）", self.readme)
        self.assertIsNotNone(m, "README 缺少故障图规模声称")
        self.assertEqual(
            tuple(int(x) for x in m.groups()),
            (counts["symptoms"], counts["causes"],
             counts["workarounds"], counts["tickets"]))
        # _dashboard 故障行
        m2 = re.search(
            r"（(\d+) 记录：(\d+) 症状 S \+ (\d+) 根因 C \+ (\d+) 方案 W \+ (\d+) 跟踪单 T）",
            self.dashboard)
        self.assertIsNotNone(m2, "_dashboard 缺少故障统计行")
        self.assertEqual(tuple(int(x) for x in m2.groups()[1:]),
                         (counts["symptoms"], counts["causes"],
                          counts["workarounds"], counts["tickets"]))

    def test_testcase_counts(self):
        """用例数按 AST 实计，并核对 README / TESTING.md 的每一处声称。

        历史教训：曾用 grep 数 "def test_"，把本文件正则字符串里的两处字面量
        算成用例（声称 22，实际 20）；portgraph 只数了图谱文件，漏掉
        test_prefetch.py 的 4 个（声称 119，实际 123）。
        """
        engine = count_tests("tests/test_qt_ohos.py")
        consistency = count_tests("tests/test_kb_consistency.py")
        scanner = count_tests("tests/test_cpp20_gap_scan.py")
        graph = count_tests("portgraph/tests/test_port_graph.py",
                            "portgraph/tests/test_prefetch.py")
        expected = (engine, consistency, scanner)

        triple = re.compile(r"引擎 (\d+) \+ 一致性 (\d+) \+ (?:cpp20 )?扫描 (\d+)")
        for origin, text in (("README", self.readme), ("TESTING.md", self.testing)):
            found = triple.findall(text)
            self.assertTrue(found, f"{origin} 里缺少「引擎 N + 一致性 N + 扫描 N」的用例声称")
            for got in found:
                self.assertEqual(tuple(int(x) for x in got), expected,
                                 f"{origin} 声称 {got}，实际 {expected}")
            # 图谱数：两份文档措辞不同（图谱 N 单测 / portgraph N 单测），
            # 出现即校验，不强求每份都写（总数由上面的三元组兜底）
            for got in (int(x) for x in re.findall(r"图谱 (\d+) 单测", text)):
                self.assertEqual(got, graph, f"{origin} 声称图谱 {got} 单测，实际 {graph}")
            for got in (int(x) for x in re.findall(r"portgraph (\d+) 单测", text)):
                self.assertEqual(got, graph, f"{origin} 声称 portgraph {got} 单测，实际 {graph}")


# --------------------------------------------------------------------------
# L3 交叉引用完整性
# --------------------------------------------------------------------------

KB_DIRS = ("semantic", "procedural", "problems", "faults", "_index", "skills")
KNOWN_PREFIXES = ("semantic/", "procedural/", "episodic/", "problems/", "faults/",
                  "_index/", "skills/", "tools/", "portgraph/", "templates/",
                  "tests/", "knowledge/", "ohos-common-kb-public/")
RUNTIME_PREFIXES = ("workspace/", ".qt-ohos", ".qtsdk", "ENV", "TODO.local",
                    "dist/", "build/", "outputs/", "entry/", "AppScope/", "qtbase/")


def _candidates(token: str):
    """把引用 token 解析为候选仓库路径。

    知识页命名约定：semantic/ 下大部分页带 `qt-harmonyos-` 前缀，而
    _task-routing 等文档常用简写（`golden-rules.md` →
    `semantic/qt-harmonyos-golden-rules.md`），两种形态都作为候选。
    """
    cands = [token]  # 仓库根相对（如 kb.yaml、ENV.md）
    if "/" in token:
        cands.append(token)
        if not Path(token).suffix:
            cands.append(token + ".md")
    else:
        # 简写前缀约定：全名 = qt- 前缀 + 简写（qt-harmonyos-xxx / qt-ohos-extras 等）
        for d in KB_DIRS:
            for pfx in ("", "qt-", "qt-harmonyos-", "qt-ohos-"):
                cands.append(f"{d}/{pfx}{token}")
                if not Path(token).suffix:
                    cands.append(f"{d}/{pfx}{token}.md")
    return cands


def missing_refs(text: str, origin: str):
    """提取行内代码中的仓库路径引用，返回无法解析的清单。

    只对"看起来像知识路径"的 token 做正向匹配（已知目录前缀 / .md|.yaml
    后缀 / qt- 等知识页命名前缀），避免把 CLI 子命令名误判为路径。
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
            problems.append(f"{origin}: `{t}` 无法解析到仓库内路径")
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
                        f"{path.name} refs.{key} 指向不存在的页：{ref}")

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
                            f"README 链接失效：{target}")
        heads = {h.strip().lower().replace(" ", "-")
                 for h in re.findall(r"^#+ (.+)$", text, re.M)}
        for anchor in re.findall(r"\]\(#([^)]+)\)", text):
            self.assertIn(anchor, heads, f"README 锚点失效：#{anchor}")


# --------------------------------------------------------------------------
# L4 CLI 契约（子命令集合——增删命令须显式更新此处）
# --------------------------------------------------------------------------

QT_OHOS_RUN_CMDS = {
    "init", "scan", "plan", "patch", "build", "package", "install", "launch",
    "smoke", "verify", "analyze-log", "status", "resume", "migrate", "finish",
    "assess", "rollback", "mark-gate", "mark-ui", "mark-risk", "draft",
    "promote", "recipes", "config", "libcheck",
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
        raise AssertionError(f"{script} --help 未列出子命令：\n{proc.stdout[:500]}")
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
# L5 集成门禁
# --------------------------------------------------------------------------

class TestIntegrationGates(unittest.TestCase):

    def test_faults_build_check_zero_errors(self):
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "tools" / "faults-build.py"), "check"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=300)
        self.assertEqual(
            proc.returncode, 0,
            "faults-build check 存在 ERROR（真源与派生物不一致）：\n"
            + proc.stdout[-2000:])


if __name__ == "__main__":
    unittest.main()
