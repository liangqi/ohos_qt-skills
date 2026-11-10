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

from qt_ohos import (error_engine, knowledge, rule_engine, scanner, state,  # noqa: E402
                     verifier, yaml_lite)
from qt_ohos.patch import ChangeTracker  # noqa: E402
from qt_ohos import state as state_mod  # noqa: E402
from qt_ohos import builder as builder_mod  # noqa: E402

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
        self.assertGreaterEqual(len(files), 19)
        for path in files:
            data = yaml_lite.parse(path.read_text(encoding="utf-8"))
            self.assertTrue(str(data["id"]).startswith("R"), path.name)
            self.assertIn(data["severity"], ("critical", "high", "medium", "low"))
            self.assertIsInstance(data["match"], dict)

    def test_parse_error_files(self):
        err_dir = REPO_ROOT / "knowledge" / "errors"
        files = list(err_dir.glob("QOH*.yaml"))
        self.assertGreaterEqual(len(files), 43)
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


class TestRuleGuard(unittest.TestCase):
    """R019：平台分发头只写一个 OHOS 宏时必须报，双宏必须不报。"""

    def _scan(self, tmp: Path):
        (tmp / "src" / "platform").mkdir(parents=True)
        (tmp / "src" / "platform" / "platform_good.h").write_text(
            "#elif defined Q_OS_OHOS || defined Q_OS_HARMONY\n", encoding="utf-8")
        (tmp / "src" / "platform" / "platform_bad.h").write_text(
            "#elif defined Q_OS_OHOS\n#include \"platform/linux/x.h\"\n",
            encoding="utf-8")
        info = {"sources": [], "pro_files": [], "cmake_files": []}
        risk = rule_engine.RuleEngine(REPO_ROOT).scan(info, tmp)
        return [f for f in risk["findings"] if f["rule"] == "R019"]

    def test_flags_single_macro_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            hits = self._scan(Path(tmp))
            files = {f["file"] for f in hits}
            self.assertEqual(len(files), 1, hits)
            self.assertTrue(next(iter(files)).endswith("platform_bad.h"))
            self.assertIn("missing", hits[0]["snippet"])


class TestCmakeArgs(unittest.TestCase):
    """config set cmake_args "-G Ninja ..." 是字符串，必须能当参数列表用。"""

    def test_string_form_is_split(self):
        self.assertEqual(builder_mod._cmake_args("-G Ninja -DFOO=1"),
                         ["-G", "Ninja", "-DFOO=1"])

    def test_list_form_passes_through(self):
        self.assertEqual(builder_mod._cmake_args(["-G", "Ninja"]), ["-G", "Ninja"])

    def test_empty_is_empty(self):
        self.assertEqual(builder_mod._cmake_args(None), [])
        self.assertEqual(builder_mod._cmake_args(""), [])

    def test_configure_build_accepts_string_args(self):
        """端到端：字符串 cmake_args 不能再把 G3 直接炸掉。"""
        calls = []

        def fake_run(cmd, label=None, timeout=None, **kw):
            calls.append(list(cmd) if isinstance(cmd, (list, tuple)) else cmd)
            return state_mod.CommandResult(
                command=str(cmd), label=label or "", status="PASS", stdout="",
                stderr="", exit_code=0, start_time="t")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.16)\nproject(p LANGUAGES CXX)\n",
                encoding="utf-8")
            st = state_mod.init_state(root)
            st.write_json("env.json", {"qt_sdk_prefix": "/tmp/fake-qt",
                                       "cmake_args": "-G Ninja"})
            st.run_cmd = fake_run
            result = builder_mod.configure_and_build(st, timeout=5)
            self.assertEqual(result.status, "PASS")
            self.assertIn("-G", calls[0])
            self.assertIn("Ninja", calls[0])


class TestGateHonesty(unittest.TestCase):
    """门禁只能"证有不证无"：没有证据一律 NOT_RUN/SKIP/PARTIAL，绝不 PASS。"""

    def _gates(self, runtime=None, build=None, scan=None):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        root = Path(tmp)
        st = state_mod.init_state(root)
        if runtime is not None:
            st.write_json("runtime.json", runtime)
        if build is not None:
            st.write_json("build.json", build)
        if scan is not None:
            st.write_json("scan.json", scan)
        gates, _overall = verifier.evaluate(st)
        return gates

    def test_g2_not_run_without_risk_scan(self):
        gates = self._gates()
        self.assertEqual(gates["G2"]["status"], "NOT_RUN")

    def test_g2_pass_only_after_scan(self):
        gates = self._gates(scan={"risk": {"findings": [
            {"rule": "R001", "severity": "high"}]}})
        self.assertEqual(gates["G2"]["status"], "PASS")
        self.assertIn("1 findings", gates["G2"]["detail"])

    def test_g5_fails_when_package_says_pass_without_hap(self):
        gates = self._gates(build={"package": {"status": "PASS"}, "hap": None})
        self.assertEqual(gates["G5"]["status"], "FAIL")

    def test_g8_partial_when_log_not_bundle_filtered(self):
        runtime = {
            "install": {"status": "PASS"}, "launch": {"status": "PASS"},
            "crash_check": {"status": "PASS", "bundle_filtered": False},
            "crash_markers_found": [],
        }
        gates = self._gates(runtime=runtime)
        self.assertEqual(gates["G8"]["status"], "PARTIAL")
        self.assertIn("bundle_name", gates["G8"]["detail"])

    def test_g8_pass_when_bundle_filtered(self):
        runtime = {
            "install": {"status": "PASS"}, "launch": {"status": "PASS"},
            "crash_check": {"status": "PASS", "bundle_filtered": True},
            "crash_markers_found": [],
        }
        gates = self._gates(runtime=runtime)
        self.assertEqual(gates["G8"]["status"], "PASS")


def _load_platform_audit():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "ohos_platform_audit_probe",
        REPO_ROOT / "tools" / "ohos-platform-audit.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestPlatformAuditClassify(unittest.TestCase):
    """只写一个宏的文件必须被判成"头分发且缺宏"，不能落到源分发里静默放行。"""

    def _audit(self, files: dict):
        audit_mod = _load_platform_audit()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, body in files.items():
                (root / name).write_text(body, encoding="utf-8")
            return audit_mod.audit(root)

    def test_single_macro_is_flagged_not_skipped(self):
        report = self._audit({"platform_tray.h": (
            "#pragma once\n"
            "#ifdef Q_OS_OHOS\n#include \"ohos/tray_ohos.h\"\n"
            "#else\n#include \"linux/tray_linux.h\"\n#endif\n")})
        self.assertEqual(report["source_dispatch"], [])
        self.assertEqual(report["missing_both_macros"], ["platform_tray.h"])

    def test_both_macros_is_ok(self):
        report = self._audit({"platform_audio.h": (
            "#pragma once\n"
            "#if defined(Q_OS_OHOS) || defined(Q_OS_HARMONY)\n"
            "#include \"ohos/audio_ohos.h\"\n#else\n#endif\n")})
        self.assertEqual(report["header_dispatch"][0]["ok"], True)
        self.assertEqual(report["missing_both_macros"], [])

    def test_linux_include_without_ohos_branch_warns(self):
        report = self._audit({"platform_notify.h": (
            "#pragma once\n#if defined(Q_OS_WIN)\n#include \"win/n.h\"\n"
            "#else\n#include \"platform/linux/n.h\"\n#endif\n")})
        self.assertEqual(report["no_ohos_branch"], ["platform_notify.h"])
        self.assertEqual(report["missing_both_macros"], [])

    def test_plain_header_is_source_dispatch(self):
        report = self._audit({"platform_tray.h": (
            "#pragma once\nstruct Tray;\nvoid init_tray();\n")})
        self.assertEqual(report["source_dispatch"], ["platform_tray.h"])
        self.assertEqual(report["missing_both_macros"], [])


class TestVersionedSoSibling(unittest.TestCase):
    """版本化 .so 旁边有同名 .so 时，soname 已满足，不该报错。"""

    def test_sibling_plain_so_silences_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            libs = root / "entry" / "libs" / "arm64-v8a"
            libs.mkdir(parents=True)
            (libs / "libfoo.so.1").write_text("x", encoding="utf-8")
            (libs / "libfoo.so").write_text("x", encoding="utf-8")
            st = state_mod.init_state(root)
            st.write_json("env.json", {})
            errors, _warns = builder_mod.preflight_package(st)
            self.assertEqual(errors, [])


class TestSdkVersionCompare(unittest.TestCase):
    """build-profile.json5 两种写法（"5.0.5(17)" 字符串 / 12 纯 API 号）都要能比。"""

    def test_normalized_forms(self):
        same = builder_mod._sdk_equal
        self.assertTrue(same("5.0.5(17)", "5.0.5（17）"))
        self.assertTrue(same("5.0.5(17)", "17"))
        self.assertTrue(same(17, "17"))
        self.assertFalse(same("5.0.5(17)", "5.0.5(12)"))
        self.assertFalse(same("12", "17"))

    def test_numeric_build_profile_is_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "build-profile.json5").write_text(
                '{\n  "app": {\n    "products": [{"compatibleSdkVersion": 17}]\n'
                '  }\n}', encoding="utf-8")
            st = state_mod.init_state(root)
            st.write_json("env.json", {"compatible_sdk": "5.0.5(17)"})
            errors, _warns = builder_mod.preflight_package(st)
            self.assertEqual(errors, [])
            st.write_json("env.json", {"compatible_sdk": "5.0.5(12)"})
            errors, _warns = builder_mod.preflight_package(st)
            self.assertTrue(any("compatibleSdkVersion" in e for e in errors))


class TestManifestHashCoversUntracked(unittest.TestCase):
    """未 git add 的新文件也必须进摘要，否则发版清单会静默漏页。"""

    def test_untracked_file_changes_digest(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "gen_manifest_probe", REPO_ROOT / "_scripts" / "gen-manifest.py")
        gm = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gm)
        before = gm.content_tree_sha256()
        probe = REPO_ROOT / "problems" / "zz-manifest-probe.md"
        probe.write_text("# probe\n", encoding="utf-8")
        try:
            after = gm.content_tree_sha256()
        finally:
            probe.unlink()
        self.assertNotEqual(before, after)


class TestPackagePreflight(unittest.TestCase):
    """打包前必须拦下版本化 .so 与 compatibleSdkVersion 不一致（都是装机才炸的错）。"""

    def test_blocks_versioned_so_and_sdk_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            libs = root / "entry" / "libs" / "arm64-v8a"
            libs.mkdir(parents=True)
            (libs / "libfoo.so.1").write_text("x", encoding="utf-8")
            (libs / "libbar.so").write_text("x", encoding="utf-8")
            (root / "build-profile.json5").write_text(
                '{"app":{"products":[{"compatibleSdkVersion":"5.0.0(12)"}]}}',
                encoding="utf-8")
            st = state_mod.init_state(root)
            st.write_json("env.json", {"compatible_sdk": "5.0.5(17)"})
            errors, _warns = builder_mod.preflight_package(st)
            joined = "\n".join(errors)
            self.assertIn("libfoo.so.1", joined)
            self.assertIn("compatibleSdkVersion", joined)
            self.assertNotIn("libbar.so", joined)

    def test_clean_tree_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            libs = root / "entry" / "libs" / "arm64-v8a"
            libs.mkdir(parents=True)
            (libs / "libok.so").write_text("x", encoding="utf-8")
            st = state_mod.init_state(root)
            st.write_json("env.json", {})
            errors, _warns = builder_mod.preflight_package(st)
            self.assertEqual(errors, [])


class TestG8Propagation(unittest.TestCase):
    """install/launch 没过时 G8 必须 SKIP —— 旧实现会拿全设备 hilog 灌出 PASS。"""

    def test_g8_skip_without_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            st = state_mod.init_state(project)
            st.write_json("runtime.json", {
                "install": {"status": "FAIL", "stderr": "install failed"},
                "launch": {"status": "NOT_RUN"},
                "crash_check": {"status": "PASS", "stderr": "no markers"},
            })
            gates, _overall = verifier.evaluate(st)
            self.assertEqual(gates["G8"]["status"], "SKIP")
            self.assertIn("not applicable", gates["G8"]["detail"])


class TestPipelineShortCircuit(unittest.TestCase):
    """编译没过就别继续调 hvigor/hdc：连带失败会把"没测"混进报告。"""

    def test_device_chain_stops_after_compile(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.16)\n"
                "project(p LANGUAGES CXX)\n"
                "find_package(Qt6 COMPONENTS Core REQUIRED)\n", encoding="utf-8")
            (project / "main.cpp").write_text("int main(){}\n", encoding="utf-8")
            tool = REPO_ROOT / "tools" / "qt-ohos-run.py"
            proc = subprocess.run(
                [sys.executable, tool, "--project", project, "migrate",
                 "--no-verify"],
                capture_output=True, text=True, timeout=180)
            out = proc.stdout + proc.stderr
            self.assertIn("上游 compile 未通过", out)
            for stage in ("package", "install", "launch", "smoke"):
                self.assertIn("%s: SKIP" % stage, out)


class TestScanIdempotenceHint(unittest.TestCase):
    """第二次 scan 不重扫时必须说话，否则"改了代码再扫"看起来像扫过了。"""

    def test_second_scan_explains_it_skipped(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.16)\n"
                "project(p LANGUAGES CXX)\n"
                "find_package(Qt6 COMPONENTS Core REQUIRED)\n", encoding="utf-8")
            (project / "main.cpp").write_text("int main(){}\n", encoding="utf-8")
            tool = REPO_ROOT / "tools" / "qt-ohos-run.py"
            cmd = [sys.executable, tool, "--project", project, "scan"]
            first = subprocess.run(cmd, capture_output=True, text=True)
            second = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertIn("未重扫", second.stdout)
            self.assertIn("--force", second.stdout)


class TestCrashLogScope(unittest.TestCase):
    """日志过滤词只有 bundle 全名时，只写进程名的行会被丢掉 —— 结果是"没证据"。
    过滤词同时含 bundle 与进程名（缺省 bundle 末段）。"""

    def _run(self, log_text, env_extra):
        calls = []

        def fake_run_cmd(cmd, label=None, timeout=None, **kw):
            calls.append(cmd)
            return state_mod.CommandResult(
                command=" ".join(cmd), label=label or "", status="PASS",
                stdout=log_text, stderr="", exit_code=0, start_time="t")

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            st = state_mod.init_state(project)
            st.write_json("env.json", dict({"hdc": "hdc",
                                            "crash_wait_sec": 1}, **env_extra))
            st.write_json("runtime.json", {"install": {"status": "PASS"},
                                          "launch": {"status": "PASS"}})
            st.run_cmd = fake_run_cmd            # 不碰真设备
            result = builder_mod.crash_check(st, timeout=5)
            return result, st.read_json("runtime.json")

    def test_process_name_only_log_is_kept(self):
        log = "11-04 I A00000/telegramdesktop/td: starting\n"
        result, runtime = self._run(log, {"bundle_name": "org.telegram.desktop"})
        self.assertEqual(result.status, "PASS")
        self.assertTrue(runtime["crash_check"]["bundle_filtered"])
        self.assertIn("filtered by", result.stderr)

    def test_bundle_segment_fallback_keeps_log(self):
        # 进程名与 bundle 不共享"末段"，但共享一个 >=4 字符的段 → 放宽后应命中
        log = "11-04 I A00000/telegram/x: starting\n"
        result, _runtime = self._run(log, {"bundle_name": "org.telegram.desktop"})
        self.assertEqual(result.status, "PASS")
        self.assertIn("telegram", result.stderr)

    def test_no_matching_line_is_not_run(self):
        log = "11-04 I A00000/otherapp/x: unrelated\n"
        result, _runtime = self._run(log, {"bundle_name": "org.telegram.desktop",
                                           "process_name": "zzz"})
        self.assertEqual(result.status, "NOT_RUN")

    def test_crash_marker_in_scoped_line_fails(self):
        log = "11-04 E A00000/telegramdesktop/td: cppcrash happened\n"
        result, _runtime = self._run(log, {"bundle_name": "org.telegram.desktop"})
        self.assertEqual(result.status, "FAIL")


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
            # 草稿必须落在被跟踪的 faults/_drafts/（top-level drafts/ 是 gitignore 的）
            self.assertEqual(path.parent.name, "_drafts")
            self.assertEqual(path.parent.parent.name, "faults")
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
