"""Engine self-tests for the qt-ohos execution plane.

Run from the repository root:

    python -m unittest discover -s tests -v
"""

from __future__ import annotations
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from qt_ohos import error_engine, knowledge, rule_engine, scanner, state, yaml_lite  # noqa: E402
from qt_ohos.patch import ChangeTracker  # noqa: E402

SAMPLE_QPA_LOG = """
E Qt      : dlopen failed: library "libqohos.so" not found
F Qt      : Cannot load Qt platform plugin "qohos"
F Qt      : This application failed to start because it could not find or load the Qt platform plugin "qohos"
"""


def make_project(root: Path) -> Path:
    """Create a small synthetic Qt project with known risk markers."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "app.pro").write_text(
        "QT += core gui widgets dbus\n"
        "unix:!android:!macx {\n"
        "    SOURCES += unixstuff.cpp\n"
        "}\n", encoding="utf-8")
    (root / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.16)\n"
        "project(sample)\n"
        "set(CMAKE_AUTOMOC ON)\n"
        "find_package(Qt5 COMPONENTS Widgets)\n", encoding="utf-8")
    src = root / "src"
    src.mkdir()
    (src / "main.cpp").write_text(
        "#include <QtDBus/QDBusConnection>\n"
        "#include <openssl/ssl.h>\n"
        "int main() {\n"
        "    pid_t pid = fork();\n"
        "    QSystemTrayIcon tray;\n"
        "    return 0;\n"
        "}\n", encoding="utf-8")
    return root


class TestYamlLite(unittest.TestCase):
    def test_parse_rule_files(self):
        rules_dir = REPO_ROOT / "knowledge" / "rules"
        files = list(rules_dir.glob("R*.yaml"))
        self.assertGreaterEqual(len(files), 18)
        for path in files:
            data = yaml_lite.parse(path.read_text(encoding="utf-8"))
            self.assertTrue(str(data["id"]).startswith("R"), path.name)
            self.assertIn(data["severity"], ("critical", "high", "medium", "low"))
            self.assertIsInstance(data["match"], dict)

    def test_parse_error_files(self):
        err_dir = REPO_ROOT / "knowledge" / "errors"
        files = list(err_dir.glob("QOH*.yaml"))
        self.assertEqual(len(files), 42)
        for path in files:
            data = yaml_lite.parse(path.read_text(encoding="utf-8"))
            self.assertTrue(str(data["id"]).startswith("QOH"), path.name)
            self.assertIsInstance(data["patterns"], list)
            self.assertGreater(len(data["patterns"]), 0)

    def test_roundtrip(self):
        obj = {"id": "T1", "list": ["a", "b"], "nested": {"x": 1},
               "flag": True, "empty": []}
        text = yaml_lite.dump(obj)
        back = yaml_lite.parse(text)
        self.assertEqual(back["id"], "T1")
        self.assertEqual(back["list"], ["a", "b"])
        self.assertEqual(back["nested"]["x"], 1)
        self.assertEqual(back["flag"], True)


class TestScannerAndRules(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = make_project(Path(self.tmp.name) / "sample")

    def tearDown(self):
        self.tmp.cleanup()

    def test_scan_detects_build_and_modules(self):
        info = scanner.scan_project(self.project)
        self.assertEqual(info["build_system"], "cmake+qmake")
        for mod in ("core", "gui", "widgets", "dbus"):
            self.assertIn(mod, info["qt_modules"])
        self.assertTrue(any(h["name"] == "openssl"
                            for h in info["third_party_hints"]))

    def test_rule_engine_finds_critical_risks(self):
        info = scanner.scan_project(self.project)
        engine = rule_engine.RuleEngine(REPO_ROOT)
        risk = engine.scan(info, self.project)
        hit_rules = {f["rule"] for f in risk["findings"]}
        self.assertIn("R001", hit_rules)   # dbus
        self.assertIn("R006", hit_rules)   # fork()
        self.assertIn("R012", hit_rules)   # system tray
        self.assertIn("R015", hit_rules)   # unix scope without !ohos
        self.assertGreaterEqual(risk["summary"].get("critical", 0), 2)


class TestQtVersionDetection(unittest.TestCase):
    """Qt 主版本识别：真实工程（tdesktop）的 Qt 配置落在子模块 .cmake 里，
    曾因只认 find_package(Qt6 字面量而把 Qt6 工程当成 Qt5 评估。"""

    def test_literal_find_package(self):
        self.assertEqual(scanner.detect_qt_major(["find_package(Qt6 COMPONENTS Core)"])[0], "6")
        self.assertEqual(scanner.detect_qt_major(["find_package(Qt5 REQUIRED)"])[0], "5")

    def test_link_targets_and_names(self):
        self.assertEqual(scanner.detect_qt_major(["target_link_libraries(x Qt6::Widgets)"])[0], "6")
        self.assertEqual(scanner.detect_qt_major(
            ["find_package(QT NAMES Qt6 COMPONENTS Core QUIET)"])[0], "6")

    def test_qt6_only_cmake_commands(self):
        self.assertEqual(scanner.detect_qt_major(["qt_standard_project_setup()"])[0], "6")
        self.assertEqual(scanner.detect_qt_major(["qt5_wrap_cpp(SRCS a.h)"])[0], "5")
        # 条件分支只说明"还兼容 Qt5"，不能当成工程主版本
        self.assertIsNone(scanner.detect_qt_major(
            ["if (QT_VERSION_MAJOR LESS 6)\n  use_qt5()\nendif()"])[0])
        self.assertEqual(scanner.detect_qt_major(["set(QT_VERSION_MAJOR 6)"])[0], "6")

    def test_variable_form_yields_no_version(self):
        # find_package(Qt${QT_VERSION_MAJOR} ...) 取不到字面量：不猜
        major, _ = scanner.detect_qt_major(
            ["find_package(Qt${QT_VERSION_MAJOR} COMPONENTS Core Gui REQUIRED)"])
        self.assertIsNone(major)

    def test_cmake_files_beyond_cmakelists_are_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "p"
            (root / "cmake" / "external" / "qt").mkdir(parents=True)
            (root / "CMakeLists.txt").write_text(
                "project(p)\nadd_subdirectory(cmake)\n", encoding="utf-8")
            (root / "cmake" / "external" / "qt" / "package.cmake").write_text(
                "find_package(QT NAMES Qt6 COMPONENTS Core QUIET)\n"
                "find_package(Qt${QT_VERSION_MAJOR} COMPONENTS Core Gui Widgets REQUIRED)\n",
                encoding="utf-8")
            info = scanner.scan_project(root)
            self.assertIn("cmake/external/qt/package.cmake", info["cmake_files"])
            self.assertEqual(info["qt_version_hint"], "6", info)
            self.assertIn("widgets", info["qt_modules"])

    def test_unknown_version_warns_instead_of_assuming_qt5(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "p"
            (root / "src").mkdir(parents=True)
            (root / "CMakeLists.txt").write_text(
                "project(p)\nadd_executable(p main.cpp)\n", encoding="utf-8")
            (root / "src" / "main.cpp").write_text(
                "#include <QtWidgets/QApplication>\nint main(){}\n", encoding="utf-8")
            info = scanner.scan_project(root)
            self.assertIsNone(info["qt_version_hint"])
            self.assertTrue(any("未能从构建文件判定 Qt 主版本" in w
                                for w in info["warnings"]))


class TestErrorEngine(unittest.TestCase):
    def test_qpa_log_matches_qoh001(self):
        engine = error_engine.ErrorEngine(REPO_ROOT)
        hits = engine.analyze(SAMPLE_QPA_LOG, stage_hint="launch")
        self.assertTrue(hits)
        self.assertEqual(hits[0]["id"], "QOH001")
        self.assertGreater(hits[0]["score"], 0.5)
        self.assertIn("problems/runtime-fail-qpa-plugin-not-found.md",
                      hits[0]["refs"]["problems"])

    def test_spawn_java_matches_qoh015(self):
        engine = error_engine.ErrorEngine(REPO_ROOT)
        hits = engine.analyze("ERROR: spawn java ENOENT at PackageHap step")
        self.assertTrue(any(h["id"] == "QOH015" for h in hits))


class TestStateAndPatches(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = make_project(Path(self.tmp.name) / "sample")

    def tearDown(self):
        self.tmp.cleanup()

    def test_state_lifecycle_and_command_evidence(self):
        st = state.init_state(self.project)
        st.begin_stage("env_check")
        st.complete_stage("env_check", next_action="scan")
        self.assertIn("env_check", st.data["completed"])

        result = st.run_cmd([sys.executable, "-c", "print('ok')"], label="probe")
        self.assertEqual(result.status, "PASS")
        self.assertTrue((st.state_dir / result.evidence).exists())

        # TIMEOUT must never be PASS
        result = st.run_cmd([sys.executable, "-c", "import time; time.sleep(5)"],
                            label="slow", timeout=1)
        self.assertEqual(result.status, "TIMEOUT")

        # reload from disk
        st2 = state.load_state(self.project)
        self.assertIn("env_check", st2.data["completed"])

    def test_change_tracker_and_patches(self):
        st = state.init_state(self.project)
        tracker = ChangeTracker(st)
        pro = self.project / "app.pro"
        original = pro.read_text(encoding="utf-8")
        modified = original.replace("unix:!android:!macx",
                                    "unix:!android:!macx:!ohos")
        pro.write_text(modified, encoding="utf-8")
        tracker.track("app.pro", original, modified, "fix-b9-unix-scope",
                      "append :!ohos (B9)")
        patches = tracker.generate_patches()
        self.assertEqual(len(patches), 1)
        patch_text = (st.state_dir / patches[0]).read_text(encoding="utf-8")
        self.assertIn(":!ohos", patch_text)

        changes = json.loads((st.state_dir / "changes.json").read_text(
            encoding="utf-8"))
        self.assertEqual(changes[0]["source"], "fix-b9-unix-scope")

        # rollback restores the original
        tracker.rollback()
        self.assertEqual(pro.read_text(encoding="utf-8"), original)


class TestKnowledge(unittest.TestCase):
    def test_draft_and_promote_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            kb = Path(tmp)
            (kb / "knowledge" / "errors").mkdir(parents=True)
            (kb / "knowledge" / "errors" / "index.yaml").write_text(
                "version: 1\nentry_count: 36\n", encoding="utf-8")
            path = knowledge.create_draft(kb, "Test problem",
                                          summary="s", symptom="sym",
                                          log="error: boom")
            self.assertTrue(path.exists())
            self.assertEqual(path.parent.name, "drafts")   # D2: top-level drafts/
            draft_id = path.stem
            page = knowledge.promote_draft(kb, draft_id)
            # dual output: problems/ page (truth) + knowledge/errors/ yaml
            self.assertTrue(page.exists())
            self.assertEqual(page.parent.name, "problems")
            page_text = page.read_text(encoding="utf-8")
            self.assertIn("id: problem-runtime-fail-test-problem", page_text)
            self.assertIn("status: open", page_text)
            self.assertIn("error: boom", page_text)
            entry = yaml_lite.parse(
                (kb / "knowledge" / "errors" / ("%s.yaml" % draft_id))
                .read_text(encoding="utf-8"))
            self.assertEqual(entry["id"], draft_id)
            self.assertEqual(entry["refs"]["problems"],
                             ["problems/%s" % page.stem + ".md"])
            # index count bumped automatically
            index_text = (kb / "knowledge" / "errors" / "index.yaml") \
                .read_text(encoding="utf-8")
            self.assertIn("entry_count: 37", index_text)
            # draft marked promoted
            self.assertIn("status: promoted",
                          path.read_text(encoding="utf-8"))


class TestAssessor(unittest.TestCase):
    def _scan(self, modules, qt_hint="6"):
        return {"qt_modules": modules, "qt_version_hint": qt_hint,
                "build_system": "cmake", "sources": [],
                "third_party_hints": [], "cmake_packages": {"find_package": []},
                "pkg_manifests": {"conan": [], "vcpkg": []},
                "frameworks": [], "kf_components": []}

    def test_empty_project_is_not_portable(self):
        """空目录/指错路径：没有任何 Qt 特征时不许给 portable。"""
        from qt_ohos import assessor
        with tempfile.TemporaryDirectory() as tmp:
            kb = Path(tmp)
            adapt = Path(__file__).resolve().parent.parent / "knowledge" \
                / "adaptation"
            if not (adapt / "modules.yaml").is_file():
                self.skipTest("adaptation matrix not available")
            shutil.copytree(adapt, kb / "knowledge" / "adaptation")
            empty = assessor.evaluate(kb, {
                "qt_modules": [], "qt_version_hint": None,
                "build_system": "unknown", "sources": [],
                "third_party_hints": [], "cmake_packages": {"find_package": []},
                "pkg_manifests": {"conan": [], "vcpkg": []},
                "frameworks": [], "kf_components": []})
            self.assertEqual(empty["verdict"], "uncertain")
            self.assertTrue(any("未识别到 Qt 工程特征" in h
                                for h in empty["hints"]))
            self.assertIn("未识别到 Qt 工程特征", assessor.render(empty))

    def test_verdicts_against_matrix(self):
        from qt_ohos import assessor
        with tempfile.TemporaryDirectory() as tmp:
            kb = Path(tmp)
            adapt = Path(__file__).resolve().parent.parent / "knowledge" \
                / "adaptation"
            if not (adapt / "modules.yaml").is_file():
                self.skipTest("adaptation matrix not available")
            shutil.copytree(adapt, kb / "knowledge" / "adaptation")
            blocked = assessor.evaluate(kb, self._scan(
                ["core", "gui", "webenginewidgets"]))
            self.assertEqual(blocked["verdict"], "blocked")
            self.assertEqual(blocked["blockers"][0]["code"],
                             "MODULE-OUT-OF-SCOPE")
            uncertain = assessor.evaluate(kb, self._scan(
                ["core", "multimedia"], qt_hint="5"))
            self.assertEqual(uncertain["verdict"], "uncertain")
            portable = assessor.evaluate(kb, self._scan(["core", "widgets"]))
            self.assertEqual(portable["verdict"], "portable")
            self.assertTrue(portable["checklist_hits"])
            # KDE framework stack special case
            kde = assessor.evaluate(kb, self._scan(
                ["core", "widgets"],
                qt_hint="6") | {"frameworks": ["KF6"], "kf_components":
                                ["config", "i18n", "kio", "widgets", "core"]})
            self.assertEqual(kde["verdict"], "blocked")
            self.assertTrue(kde["kde_stack"])


class TestCliSmoke(unittest.TestCase):
    def test_scan_and_verify_on_synthetic_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp) / "sample")
            cli = str(TOOLS_DIR / "qt-ohos-run.py")
            proc = subprocess.run(
                [sys.executable, cli, "--project", str(project), "scan",
                 str(project)], capture_output=True, text=True, timeout=120)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("Risk Report", proc.stdout)
            scan_file = project / ".qt-ohos" / "scan.json"
            self.assertTrue(scan_file.exists())

            proc = subprocess.run(
                [sys.executable, cli, "--project", str(project), "verify"],
                capture_output=True, text=True, timeout=60)
            self.assertIn("Result:", proc.stdout)

            proc = subprocess.run(
                [sys.executable, cli, "--project", str(project), "status"],
                capture_output=True, text=True, timeout=60)
            self.assertEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
