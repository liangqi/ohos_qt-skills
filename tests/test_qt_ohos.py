"""Engine self-tests for the qt-ohos execution plane.

Run from the repository root:

    python -m unittest discover -s tests -v
"""

from __future__ import annotations
import json
import pathlib
import shutil
import argparse
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from qt_ohos import (assessor, error_engine, knowledge, rule_engine,  # noqa: E402
                     scanner, state, verifier, yaml_lite)
from qt_ohos.patch import ChangeTracker  # noqa: E402
from qt_ohos import state as state_mod  # noqa: E402
from qt_ohos import builder as builder_mod  # noqa: E402

SAMPLE_QPA_LOG = """
E Qt      : dlopen failed: library "libqohos.so" not found
F Qt      : Cannot load Qt platform plugin "qohos"
F Qt      : This application failed to start because it could not find or load the Qt platform plugin "qohos"
"""


def write_elf(path: Path, needed=(), machine: int = 183,
              e_type: int = 3) -> Path:
    """Write a synthetic ELF64 image with DT_NEEDED.

    Enough for `qt_ohos.elf` and the G4/G5 content checks (header identity +
    dynamic segment); not a loadable library.
    """
    import struct
    strtab = b""
    offsets = []
    for name in needed:
        offsets.append(len(strtab))
        strtab += name.encode() + b"\x00"
    ehsize, phentsize, phnum = 64, 56, 2
    phoff = ehsize
    dyn_off = phoff + phentsize * phnum
    dyn = b"".join(struct.pack("<qQ", 1, off) for off in offsets)
    str_off = dyn_off + 16 * (len(offsets) + 3)
    dyn += struct.pack("<qQ", 5, str_off)
    dyn += struct.pack("<qQ", 10, len(strtab))
    dyn += struct.pack("<qQ", 0, 0)
    total = str_off + len(strtab)
    ident = b"\x7fELF" + bytes([2, 1, 1, 0]) + bytes(8)
    header = ident + struct.pack("<HHIQQQIHHHHHH", e_type, machine, 1, 0,
                                 phoff, 0, 0, ehsize, phentsize, phnum,
                                 64, 0, 0)
    phdrs = struct.pack("<IIQQQQQQ", 1, 5, 0, 0, 0, total, total, 8)
    phdrs += struct.pack("<IIQQQQQQ", 2, 6, dyn_off, dyn_off, dyn_off,
                         16 * (len(offsets) + 2), 16 * (len(offsets) + 2), 8)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + phdrs + dyn + strtab)
    return path


def write_elf_symbols(path: Path, undefined=(), exports=(), machine: int = 183,
                       e_type: int = 3) -> Path:
    """Synthesize an ELF64 with .dynsym: `undefined` are strong undefined symbols, `exports` are exported symbols.

    G13 (the unresolved-symbol gate) needs symbol-level facts; DT_NEEDED alone is not enough.
    """
    import struct

    dynstr = b"\x00"
    names = {}
    for name in list(undefined) + list(exports):
        if name not in names:
            names[name] = len(dynstr)
            dynstr += name.encode() + b"\x00"
    syms = [struct.pack("<IBBHQQ", 0, 0, 0, 0, 0, 0)]  # the null symbol must be at index 0
    for name in undefined:
        syms.append(struct.pack("<IBBHQQ", names[name], (1 << 4) | 2, 0, 0, 0, 0))
    for name in exports:
        syms.append(struct.pack("<IBBHQQ", names[name], (1 << 4) | 2, 0, 1,
                                0x100, 4))
    dynsym = b"".join(syms)
    shstr = b"\x00.dynsym\x00.dynstr\x00.shstrtab\x00"
    ehsize, phentsize, phnum = 64, 56, 1
    phoff = ehsize
    body_off = phoff + phentsize * phnum
    shstr_off = body_off
    dynstr_off = shstr_off + len(shstr)
    dynsym_off = dynstr_off + len(dynstr)
    shoff = body_off + len(shstr) + len(dynstr) + len(dynsym)
    total = shoff + 4 * 64
    ident = b"\x7fELF" + bytes([2, 1, 1, 0]) + bytes(8)
    header = ident + struct.pack("<HHIQQQIHHHHHH", e_type, machine, 1, 0,
                                 phoff, shoff, 0, ehsize, phentsize, phnum,
                                 64, 4, 3)
    phdrs = struct.pack("<IIQQQQQQ", 1, 5, 0, 0, 0, total, total, 8)

    def shdr(name, stype, offset, size, link=0, entsize=0, info=0):
        return struct.pack("<IIQQQQIIQQ", name, stype, 8, 0, offset, size,
                           link, info, 8, entsize)

    shdrs = b"".join([
        shdr(0, 0, 0, 0),
        shdr(1, 11, dynsym_off, len(dynsym), link=2, entsize=24, info=1),
        shdr(9, 3, dynstr_off, len(dynstr)),
        shdr(17, 3, shstr_off, len(shstr)),
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + phdrs + shstr + dynstr + dynsym + shdrs)
    return path


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
    """R019: a platform-dispatch header with only one OHOS macro must be reported; both macros must not be."""

    def _scan(self, tmp: Path):
        (tmp / "src" / "platform").mkdir(parents=True)
        (tmp / "src" / "platform" / "platform_good.h").write_text(
            "#elif defined Q_OS_OHOS || defined Q_OS_HARMONY\n", encoding="utf-8")
        (tmp / "src" / "platform" / "platform_bad.h").write_text(
            "#elif defined Q_OS_OHOS\n#include \"platform/linux/x.h\"\n",
            encoding="utf-8")
        # Only the Qt6 macro: correct on Qt6, the rule must not fire (`when` only
        # targets files that wrote Q_OS_OHOS, otherwise it would hit projects
        # that are already fixed)
        (tmp / "src" / "platform" / "platform_harmony_only.h").write_text(
            "#elif defined Q_OS_HARMONY\n#include \"ohos/x.h\"\n",
            encoding="utf-8")
        # the compiler macro exists in both generations, so that counts as complete too
        (tmp / "src" / "platform" / "platform_compiler_macro.h").write_text(
            "#if defined(Q_OS_OHOS) || defined(__OHOS__)\n", encoding="utf-8")
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

    def test_harmony_only_header_is_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = {f["file"] for f in self._scan(Path(tmp))}
            self.assertFalse(any(f.endswith("platform_harmony_only.h")
                                 for f in files), files)

    def test_compiler_macro_counts_as_version_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = {f["file"] for f in self._scan(Path(tmp))}
            self.assertFalse(any(f.endswith("platform_compiler_macro.h")
                                 for f in files), files)


class TestCmakeArgs(unittest.TestCase):
    """config set cmake_args "-G Ninja ..." is a string and must be usable as an argument list."""

    def test_string_form_is_split(self):
        self.assertEqual(builder_mod._cmake_args("-G Ninja -DFOO=1"),
                         ["-G", "Ninja", "-DFOO=1"])

    def test_list_form_passes_through(self):
        self.assertEqual(builder_mod._cmake_args(["-G", "Ninja"]), ["-G", "Ninja"])

    def test_empty_is_empty(self):
        self.assertEqual(builder_mod._cmake_args(None), [])
        self.assertEqual(builder_mod._cmake_args(""), [])

    def test_configure_build_accepts_string_args(self):
        """End to end: a string cmake_args must no longer blow up G3."""
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
    """Gates can only "prove presence, not absence": without evidence it is always NOT_RUN/SKIP/PARTIAL, never PASS."""

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


def _load_cli():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "qt_ohos_run_probe", REPO_ROOT / "tools" / "qt-ohos-run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_platform_audit():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "ohos_platform_audit_probe",
        REPO_ROOT / "tools" / "ohos-platform-audit.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestOverallVerdict(unittest.TestCase):
    """Three-level verdict: compile chain passes = PARTIAL (interim result), packaging fails = FAIL."""

    def _run(self, build, runtime=None):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        root = Path(tmp)
        st = state_mod.init_state(root)
        st.write_json("scan.json", {"risk": {"findings": []},
                                    "cmake_files": ["CMakeLists.txt"]})
        st.write_json("migration-plan.json", {"steps": []})
        st.write_json("build.json", build)
        if runtime:
            st.write_json("runtime.json", runtime)
        gates, overall = verifier.evaluate(st)
        return gates, overall

    def test_compiled_not_packaged_is_partial(self):
        gates, overall = self._run(
            {"compile": {"status": "PASS"}, "artifacts": []})
        self.assertEqual(gates["G3"]["status"], "PASS")
        self.assertEqual(gates["G5"]["status"], "NOT_RUN")
        self.assertEqual(overall, "PARTIAL")

    def test_package_failed_is_fail(self):
        _gates, overall = self._run(
            {"compile": {"status": "PASS"}, "artifacts": [],
             "package": {"status": "FAIL"}})
        self.assertEqual(overall, "FAIL")

    def test_compile_failed_is_fail(self):
        _gates, overall = self._run({"compile": {"status": "FAIL"}})
        self.assertEqual(overall, "FAIL")


class TestG4ArtifactExists(unittest.TestCase):
    """G4 must not just look at the path string in build.json: the artifact must actually be on disk."""

    def _gates(self, artifacts):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        root = Path(tmp)
        st = state_mod.init_state(root)
        st.write_json("build.json", {"compile": {"status": "PASS"},
                                     "artifacts": artifacts})
        gates, _overall = verifier.evaluate(st)
        return gates["G4"], root

    def test_missing_artifact_fails(self):
        gate, _root = self._gates(["build-ohos/nope.so"])
        self.assertEqual(gate["status"], "FAIL")
        self.assertIn("none exists on disk", gate["detail"])

    def test_existing_artifact_passes(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        root = Path(tmp)
        write_elf(root / "build-ohos" / "libok.so", ["libQt6Core.so.6", "libc.so"])
        st = state_mod.init_state(root)
        st.write_json("build.json", {"compile": {"status": "PASS"},
                                     "artifacts": ["build-ohos/libok.so"]})
        gates, _overall = verifier.evaluate(st)
        self.assertEqual(gates["G4"]["status"], "PASS")
        self.assertIn("on disk", gates["G4"]["detail"])
        self.assertIn("ELF64/aarch64/DYN", gates["G4"]["detail"])

    def test_partial_when_some_listed_but_missing(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        root = Path(tmp)
        write_elf(root / "build-ohos" / "libok.so", ["libc.so"])
        st = state_mod.init_state(root)
        st.write_json("build.json", {"compile": {"status": "PASS"}, "artifacts": [
            "build-ohos/libok.so", "build-ohos/gone.so"]})
        gates, _overall = verifier.evaluate(st)
        self.assertEqual(gates["G4"]["status"], "PARTIAL")


class TestG4ElfIdentity(unittest.TestCase):
    """\"File exists and is non-empty\" is not a criterion: a .so with the wrong architecture/type still fails dlopen on the device."""

    def _gate(self, files):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        root = Path(tmp)
        st = state_mod.init_state(root)
        artifacts = []
        for name, writer in files:
            writer(root / "build-ohos" / name)
            artifacts.append("build-ohos/" + name)
        st.write_json("build.json", {"compile": {"status": "PASS"},
                                     "artifacts": artifacts})
        gates, _overall = verifier.evaluate(st)
        return gates["G4"]

    def test_wrong_arch_fails(self):
        gate = self._gate([("libx.so", lambda p: write_elf(p, ["libc.so"],
                                                          machine=62))])
        self.assertEqual(gate["status"], "FAIL")
        self.assertIn("x86_64", gate["detail"])

    def test_non_elf_fails(self):
        def writer(path):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"not an elf")

        gate = self._gate([("libx.so", writer)])
        self.assertEqual(gate["status"], "FAIL")
        self.assertIn("not an ELF", gate["detail"])

    def test_static_archive_accepted(self):
        def writer(p):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"!<arch>\nsome object\n")
        gate = self._gate([("libstatic.a", writer)])
        self.assertEqual(gate["status"], "PASS")


class TestHapDeps(unittest.TestCase):
    """A HAP missing one DT_NEEDED library only blows up after install -- G5 must check the closure at packaging time."""

    def _gate(self, libs, env=None):
        import zipfile
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        root = Path(tmp)
        hap = root / "build" / "app.hap"
        hap.parent.mkdir(parents=True)
        with zipfile.ZipFile(hap, "w") as archive:
            for abi, name, data in libs:
                archive.writestr("libs/%s/%s" % (abi, name), data)
            archive.writestr("module.json", "{}")
        st = state_mod.init_state(root)
        if env:
            st.write_json("env.json", env)
        st.write_json("build.json", {"compile": {"status": "PASS"},
                                     "package": {"status": "PASS"},
                                     "hap": "build/app.hap", "artifacts": []})
        gates, _overall = verifier.evaluate(st)
        return gates["G5"], root

    def _elf_bytes(self, needed):
        import tempfile as _tf
        path = Path(_tf.mkdtemp()) / "x.so"
        write_elf(path, needed)
        data = path.read_bytes()
        shutil.rmtree(path.parent, True)
        return data

    def test_closed_closure_passes(self):
        gate, _root = self._gate([
            ("arm64-v8a", "libapp.so", self._elf_bytes(["libQt6Core.so.6",
                                                        "libc.so"])),
            ("arm64-v8a", "libQt6Core.so.6", self._elf_bytes(["libc.so"])),
        ])
        self.assertEqual(gate["status"], "PASS")
        self.assertIn("closure complete", gate["detail"])

    def test_missing_openssl_fails(self):
        gate, _root = self._gate([
            ("arm64-v8a", "libapp.so", self._elf_bytes(["libssl.so.3",
                                                        "libc.so"])),
        ])
        self.assertEqual(gate["status"], "FAIL")
        self.assertIn("libssl.so.3", gate["detail"])

    def test_unknown_lib_fails_by_default(self):
        gate, _root = self._gate([
            ("arm64-v8a", "libapp.so", self._elf_bytes(["libfoo.so.1"])),
        ])
        self.assertEqual(gate["status"], "FAIL")
        self.assertIn("libfoo.so.1", gate["detail"])

    def test_allowed_libs_env_respected(self):
        gate, _root = self._gate([
            ("arm64-v8a", "libapp.so", self._elf_bytes(["libfoo.so.1"])),
        ], env={"hap_allowed_libs": ["libfoo.so"]})
        self.assertEqual(gate["status"], "PASS")

    def test_wrong_abi_dir_fails(self):
        gate, _root = self._gate([
            ("armeabi-v7a", "libapp.so", self._elf_bytes(["libc.so"])),
        ])
        self.assertEqual(gate["status"], "FAIL")
        self.assertIn("armeabi-v7a", gate["detail"])

    def test_system_libs_are_not_reported(self):
        gate, _root = self._gate([
            ("arm64-v8a", "libapp.so", self._elf_bytes(["libc.so", "libm.so",
                                                        "libhilog.so"])),
        ])
        self.assertEqual(gate["status"], "PASS")


class TestG2EvidenceChain(unittest.TestCase):
    """mark-risk must carry evidence, otherwise 437 critical findings get cleared in one go and the gate becomes meaningless."""

    def _gates(self, state_mutator):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        root = Path(tmp)
        st = state_mod.init_state(root)
        st.write_json("scan.json", {"risk": {"findings": [
            {"rule": "R003", "severity": "critical", "file": "a.cpp", "line": 1}]}})
        state_mutator(st)
        gates, _overall = verifier.evaluate(st)
        return gates["G2"]

    def test_unresolved_critical_fails(self):
        gate = self._gates(lambda st: None)
        self.assertEqual(gate["status"], "FAIL")
        self.assertIn("unresolved", gate["detail"])

    def test_marked_without_evidence_fails(self):
        gate = self._gates(
            lambda st: st.__setattr__("data", dict(st.data, addressed_critical=["R003"])))
        self.assertEqual(gate["status"], "FAIL")
        self.assertIn("without evidence", gate["detail"])

    def test_marked_with_evidence_passes(self):
        def mark(st):
            verifier.mark_critical_addressed(
                st, ["R003"], evidence="a.cpp:12 isolated with #ifdef Q_OS_OHOS")
        gate = self._gates(mark)
        self.assertEqual(gate["status"], "PASS")
        self.assertIn("with evidence", gate["detail"])

    def test_evidence_survives_reload(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        root = Path(tmp)
        st = state_mod.init_state(root)
        verifier.mark_critical_addressed(st, ["R003"], evidence="changed in a.cpp")
        st2 = state_mod.load_state(root)
        rec = verifier.addressed_critical_records(st2)["R003"]
        self.assertEqual(rec["evidence"], "changed in a.cpp")
        self.assertTrue(rec["at"])


class TestCorruptState(unittest.TestCase):
    """Half-written json (left by an interrupted run) must not crash every subcommand with a traceback."""

    def test_corrupt_build_json_degrades_to_not_run(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        st = state_mod.init_state(tmp)
        (tmp / ".qt-ohos" / "build.json").write_text("{bad json", encoding="utf-8")
        gates, overall = verifier.evaluate(st)     # must not raise JSONDecodeError
        self.assertEqual(gates["G3"]["status"], "NOT_RUN")
        self.assertEqual(overall, "FAIL")

    def test_corrupt_state_json_explains_recovery(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        state_mod.init_state(tmp)
        (tmp / ".qt-ohos" / "state.json").write_text("{bad", encoding="utf-8")
        with self.assertRaises(SystemExit) as ctx:
            state_mod.load_state(tmp)
        self.assertIn("How to recover", str(ctx.exception))


class TestRuleScopeDowngrade(unittest.TestCase):
    """Hits in third-party/platform-specific directories are downgraded: code not compiled for OHOS must not block G2."""

    def test_third_party_downgraded(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "ThirdParty" / "dbus").mkdir(parents=True)
        (tmp / "ThirdParty" / "dbus" / "x.h").write_text(
            "#include <QtDBus/QDBusConnection>\n", encoding="utf-8")
        (tmp / "app.cpp").write_text(
            "#include <QtDBus/QDBusConnection>\n", encoding="utf-8")
        info = {"sources": [
            {"path": "ThirdParty/dbus/x.h", "ext": ".h"},
            {"path": "app.cpp", "ext": ".cpp"}], "pro_files": [], "cmake_files": []}
        risk = rule_engine.RuleEngine(REPO_ROOT).scan(info, tmp)
        by_file = {}
        for f in risk["findings"]:
            if f["rule"] == "R001":
                by_file.setdefault(f["file"], f)
        self.assertEqual(by_file["ThirdParty/dbus/x.h"]["severity"], "high")
        self.assertEqual(by_file["ThirdParty/dbus/x.h"]["scope"], "third-party")
        self.assertEqual(by_file["app.cpp"]["severity"], "critical")
        self.assertEqual(by_file["app.cpp"]["scope"], "")

    def test_vendor_is_not_downgraded(self):
        # vendor/ and external/ are often really compiled: no automatic downgrade, or real risks get missed
        self.assertEqual(rule_engine._path_scope("vendor/zlib/zlib.h"), "")
        self.assertEqual(rule_engine._path_scope("external/ffmpeg/lib.c"), "")
        self.assertEqual(rule_engine._path_scope("ThirdParty/x/y.h"), "third-party")

    def test_exclude_globs_skip_file(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "gen").mkdir()
        (tmp / "gen" / "y.h").write_text(
            "#include <QtDBus/QDBusConnection>\n", encoding="utf-8")
        # custom rule: source match + exclude
        rules_dir = tmp / "knowledge" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "R900.yaml").write_text(
            "id: R900\nname: probe\nseverity: high\nmatch:\n"
            "  source: ['QtDBus']\n  exclude: ['gen/**']\n", encoding="utf-8")
        info = {"sources": [{"path": "gen/y.h", "ext": ".h"}],
                "pro_files": [], "cmake_files": []}
        risk = rule_engine.RuleEngine(tmp).scan(info, tmp)
        self.assertEqual([f for f in risk["findings"] if f["rule"] == "R900"], [])


class TestPlatformAuditClassify(unittest.TestCase):
    """A file with only one macro must be classified as "header dispatch with a missing macro", not silently passed as source dispatch."""

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

    def test_compiler_macro_is_ok(self):
        report = self._audit({"platform_audio.h": (
            "#pragma once\n#if defined(__OHOS__)\n"
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
    """When a versioned .so has a same-named .so next to it, the soname is satisfied and must not be reported."""

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
    """Both build-profile.json5 forms ("5.0.5(17)" string / plain API number 12) must be comparable."""

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
    """New files that were not git-added must also go into the digest, otherwise the release manifest silently misses pages."""

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
    """Versioned .so files and a mismatched compatibleSdkVersion must be stopped before packaging (both are errors that only blow up at install)."""

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


class TestQt6ProjectLayout(unittest.TestCase):
    """Qt6's artifact location and ability name both differ from the Qt5 shell project, so the defaults cannot be reused."""

    def _state(self, root: Path):
        st = state_mod.init_state(root)
        st.write_json("env.json", {})
        return st

    def test_preflight_finds_qt6_layout(self):
        # Qt6: `_make_hap` generates the HAP project in <build_dir>/harmonyos-build/
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build = root / "build-ohos" / "harmonyos-build"
            libs = build / "entry" / "libs" / "arm64-v8a"
            libs.mkdir(parents=True)
            (libs / "libssl.so.3").write_text("x", encoding="utf-8")
            (build / "build-profile.json5").write_text(
                '{"app":{"products":[{"compatibleSdkVersion":"5.0.0(12)"}]}}',
                encoding="utf-8")
            st = self._state(root)
            st.write_json("env.json", {"compatible_sdk": "6.0.2(22)"})
            errors, _warns = builder_mod.preflight_package(st)
            joined = "\n".join(errors)
            self.assertIn("libssl.so.3", joined)
            self.assertIn("compatibleSdkVersion", joined)

    def test_align_sdk_rewrites_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # the app-level build-profile.json5 in the Qt6 deployment directory
            profile = root / "build-ohos" / "harmonyos-build" / "build-profile.json5"
            profile.parent.mkdir(parents=True)
            profile.write_text(
                '{"app":{"products":[{"compatibleSdkVersion":"6.1.0(23)",'
                '"runtimeOS":"HarmonyOS"}]}}', encoding="utf-8")
            st = self._state(root)
            env = {"compatible_sdk": "6.0.2(22)"}
            changes = builder_mod.align_sdk_profile(st, env)
            self.assertTrue(changes)
            self.assertIn("6.0.2(22)", profile.read_text(encoding="utf-8"))

    def test_detect_ability_reads_main_element(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entry = root / "entry" / "src" / "main"
            entry.mkdir(parents=True)
            (entry / "module.json5").write_text(
                """{
                  // comments and trailing commas are both valid json5
                  "module": {
                    "mainElement": "QAbility",
                    "abilities": [{"name": "QAbility"}, {"name": "BackupAbility"}],
                  }
                }""", encoding="utf-8")
            st = self._state(root)
            self.assertEqual(builder_mod.detect_ability(st, {}), "QAbility")

    def test_find_hap_prefers_signed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("app-unsigned.hap", "app-signed.hap"):
                target = root / "entry" / "build" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("x", encoding="utf-8")
            found = builder_mod.find_hap(root)
            self.assertTrue(found and found.endswith("app-signed.hap"), found)

    def test_native_path_is_absolute(self):
        p = state_mod.native_path("build/app.hap")
        self.assertTrue(Path(p).is_absolute(), p)
        self.assertNotIn("\n", p)


class TestG8Propagation(unittest.TestCase):
    """When install/launch did not pass, G8 must SKIP -- the old implementation filled in a PASS from device-wide hilog."""

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
    """If compilation failed, don't go on to call hvigor/hdc: cascading failures mix "not tested" into the report."""

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
            self.assertIn("upstream compile did not pass", out)
            for stage in ("package", "install", "launch", "smoke"):
                self.assertIn("%s: SKIP" % stage, out)


class TestScanIdempotenceHint(unittest.TestCase):
    """When a second scan does not rescan it must say so, otherwise "changed the code and scanned again" looks like it was scanned."""

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
            self.assertIn("not rescanned", second.stdout)
            self.assertIn("--force", second.stdout)


class TestCrashLogScope(unittest.TestCase):
    """If the log filter terms contain only the full bundle name, lines that only
    carry the process name are dropped -- resulting in "no evidence". The filter
    terms contain both the bundle and the process name (by default the last
    segment of the bundle)."""

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
            st.run_cmd = fake_run_cmd            # don't touch a real device
            result = builder_mod.crash_check(st, timeout=5)
            return result, st.read_json("runtime.json")

    def test_process_name_only_log_is_kept(self):
        log = "11-04 I A00000/telegramdesktop/td: starting\n"
        result, runtime = self._run(log, {"bundle_name": "org.telegram.desktop"})
        self.assertEqual(result.status, "PASS")
        self.assertTrue(runtime["crash_check"]["bundle_filtered"])
        self.assertIn("filtered by", result.stderr)

    def test_bundle_segment_fallback_keeps_log(self):
        # process name and bundle don't share the "last segment" but share a >=4-char segment -> should match after relaxing
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
    """Qt major version detection: a real project (tdesktop) keeps its Qt config
    in a submodule .cmake; recognizing only the find_package(Qt6 literal once
    caused a Qt6 project to be assessed as Qt5."""

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
        # a conditional only says "still compatible with Qt5"; it is not the project's major version
        self.assertIsNone(scanner.detect_qt_major(
            ["if (QT_VERSION_MAJOR LESS 6)\n  use_qt5()\nendif()"])[0])
        self.assertEqual(scanner.detect_qt_major(["set(QT_VERSION_MAJOR 6)"])[0], "6")

    def test_variable_form_yields_no_version(self):
        # find_package(Qt${QT_VERSION_MAJOR} ...) has no literal: don't guess
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
            self.assertTrue(any("Could not determine the Qt major version from the build files" in w
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


class TestRecordOnlyAndFlagOrder(unittest.TestCase):
    """External build/packaging results can be registered; --project works before or after the subcommand."""

    def _project(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.16)\nproject(p LANGUAGES CXX)\n"
            "find_package(Qt6 COMPONENTS Core REQUIRED)\n", encoding="utf-8")
        (tmp / "main.cpp").write_text("int main(){}\n", encoding="utf-8")
        return tmp

    def _cli(self, *argv, cwd=None):
        import subprocess
        return subprocess.run(
            [sys.executable, str(REPO_ROOT / "tools" / "qt-ohos-run.py"), *argv],
            capture_output=True, text=True, cwd=str(cwd) if cwd else None)

    def test_build_record_only_pass(self):
        project = self._project()
        (project / "build-ohos").mkdir()
        (project / "build-ohos" / "libx.so").write_bytes(b"\x7fELF")
        self._cli("--project", str(project), "init")
        proc = self._cli("--project", str(project), "build", "--record-only",
                         "--artifacts", "build-ohos/*.so")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("recorded external build", proc.stdout)
        build = state_mod.load_state(project).read_json("build.json")
        self.assertEqual(build["compile"]["status"], "PASS")
        self.assertEqual(build["mode"], "recorded")
        self.assertEqual(build["artifacts"], ["build-ohos/libx.so"])

    def test_build_record_only_without_artifact_fails(self):
        project = self._project()
        self._cli("--project", str(project), "init")
        proc = self._cli("--project", str(project), "build", "--record-only",
                         "--artifacts", "build-ohos/*.so")
        self.assertEqual(proc.returncode, 1)
        build = state_mod.load_state(project).read_json("build.json")
        self.assertEqual(build["compile"]["status"], "FAIL")

    def test_package_record_only(self):
        project = self._project()
        (project / "out").mkdir()
        (project / "out" / "app.hap").write_bytes(b"PK\x03\x04")
        self._cli("--project", str(project), "init")
        proc = self._cli("--project", str(project), "package", "--record-only",
                         "--hap", "out/app.hap")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        build = state_mod.load_state(project).read_json("build.json")
        self.assertEqual(build["hap"], "out/app.hap")

    def test_project_flag_after_subcommand_works(self):
        project = self._project()
        self._cli("--project", str(project), "init")
        proc = self._cli("verify", "--project", str(project))
        # without a configured environment verify returns 1 anyway; the point is it must not be 2 (usage error)
        self.assertNotEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("G0", proc.stdout)
        # the explanation line goes to stderr (must not pollute --json stdout)
        self.assertIn("given after the subcommand", proc.stderr)


class TestJsonContract(unittest.TestCase):
    """With `--json`, stdout must be directly parseable JSON (human output goes to stderr)."""

    def test_verify_json_is_pure(self):
        import json as _json
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.16)\n"
                "project(p LANGUAGES CXX)\n", encoding="utf-8")
            tool = REPO_ROOT / "tools" / "qt-ohos-run.py"
            subprocess.run([sys.executable, tool, "--project", project, "init"],
                           capture_output=True)
            proc = subprocess.run(
                [sys.executable, tool, "verify", "--json", "--project", project],
                capture_output=True, text=True)
            payload = _json.loads(proc.stdout)          # passes if it doesn't raise
            self.assertIn("overall", payload)
            self.assertIn("gates", payload)


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
            # drafts must land in the tracked faults/_drafts/ (top-level drafts/ is gitignored)
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
        """Empty directory / wrong path: with no Qt signal at all, portable must not be given."""
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
            self.assertTrue(any("No Qt project signal detected" in h
                                for h in empty["hints"]))
            self.assertIn("No Qt project signal detected", assessor.render(empty))

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


class TestScannerRequired(unittest.TestCase):
    """Optional Qt modules must not be judged as blockers (stress test F1 / Windows field test P1-1)."""

    def _scan(self, cmake_text):
        tmp = pathlib.Path(tempfile.mkdtemp())
        (tmp / "CMakeLists.txt").write_text(cmake_text, encoding="utf-8")
        (tmp / "main.cpp").write_text("#include <QApplication>\n",
                                      encoding="utf-8")
        return scanner.scan_project(tmp)

    def test_optional_components_not_required(self):
        info = self._scan(
            "cmake_minimum_required(VERSION 3.16)\n"
            "project(demo)\n"
            "find_package(Qt6 COMPONENTS Core Widgets "
            "OPTIONAL_COMPONENTS WebEngineWidgets)\n")
        required = info["qt_module_required"]
        self.assertTrue(required["core"])
        self.assertTrue(required["widgets"])
        self.assertFalse(required["webenginewidgets"])

    def test_component_guarded_by_target_check_is_not_required(self):
        """A QUIET + `if(TARGET ...)` module is a soft dependency (the real shape of stress test F1)."""
        info = self._scan(
            "find_package(Qt6 QUIET COMPONENTS Core WebEngineWidgets)\n"
            "if(TARGET Qt6::WebEngineWidgets)\n"
            "  target_link_libraries(app PRIVATE Qt6::WebEngineWidgets)\n"
            "endif()\n")
        self.assertTrue(info["qt_module_required"]["core"])
        self.assertFalse(info["qt_module_required"]["webenginewidgets"])

    def test_required_is_required(self):
        info = self._scan(
            "find_package(Qt6 REQUIRED COMPONENTS Core Charts)\n")
        self.assertTrue(info["qt_module_required"]["charts"])


class TestAssessorOptional(unittest.TestCase):
    def test_optional_out_of_scope_does_not_block(self):
        assessment = assessor.evaluate(
            REPO_ROOT,
            {"qt_modules": ["core", "widgets", "webenginewidgets"],
             "qt_module_required": {"core": True, "widgets": True,
                                    "webenginewidgets": False},
             "qt_version_hint": "6.8.3", "sources": [],
             "third_party_hints": []})
        codes = [b["code"] for b in assessment["blockers"]]
        self.assertNotIn("MODULE-OUT-OF-SCOPE", codes)
        self.assertEqual([m["module"] for m in assessment["optional_modules"]],
                         ["webenginewidgets"])
        self.assertNotEqual(assessment["verdict"], "blocked")
        self.assertIn("optional", assessment["summary"])

    def test_required_out_of_scope_still_blocks(self):
        assessment = assessor.evaluate(
            REPO_ROOT,
            {"qt_modules": ["core", "webenginewidgets"],
             "qt_module_required": {"core": True,
                                    "webenginewidgets": True},
             "qt_version_hint": "6.8.3", "sources": [],
             "third_party_hints": []})
        codes = [b["code"] for b in assessment["blockers"]]
        self.assertIn("MODULE-OUT-OF-SCOPE", codes)


class TestCrashEvidence(unittest.TestCase):
    """D-01: crash detection must look at three kinds of evidence, not just filter log lines by bundle."""

    def _run(self, hilog, pidof_out="", fault_before=None, fault_after=None,
             env_extra=None, artifacts=None):
        calls = {"ls": 0}

        def fake_run_cmd(cmd, label=None, timeout=None, **kw):
            joined = " ".join(cmd)
            if "faultlogger" in joined:
                calls["ls"] += 1
                names = fault_before if calls["ls"] == 1 else fault_after
                text = "\n".join(sorted(names or []))
                return state_mod.CommandResult(
                    command=joined, label=label or "", status="PASS",
                    stdout=text, stderr="", exit_code=0, start_time="t")
            if "pidof" in joined:
                return state_mod.CommandResult(
                    command=joined, label=label or "", status="PASS",
                    stdout=pidof_out, stderr="", exit_code=0, start_time="t")
            return state_mod.CommandResult(
                command=joined, label=label or "", status="PASS",
                stdout=hilog, stderr="", exit_code=0, start_time="t")

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            st = state_mod.init_state(project)
            st.write_json("env.json", dict({"hdc": "hdc", "crash_wait_sec": 1,
                                            "bundle_name": "org.qtproject.example.app"},
                                           **(env_extra or {})))
            st.write_json("runtime.json", {"install": {"status": "PASS"},
                                          "launch": {"status": "PASS"}})
            st.write_json("build.json", {"artifacts": artifacts or []})
            st.run_cmd = fake_run_cmd
            result = builder_mod.crash_check(st, timeout=5)
            return result, st.read_json("runtime.json")

    def test_system_crash_line_fails(self):
        # a real OHOS crash line: C02D11/processdump/DfxFaultLogger: #03 pc … libapp.so(main+5616)
        hilog = ("11-18 I C02D11/processdump/DfxFaultLogger: #03 pc 0000 "
                 "libapp.so(main+5616)\n")
        result, runtime = self._run(
            hilog, pidof_out="4242",
            artifacts=[{"path": "build-ohos/libapp.so"}])
        self.assertEqual(result.status, "FAIL")
        self.assertIn("system crash line", result.stderr)
        evidence = runtime["crash_check"]["crash_evidence"]
        self.assertEqual(evidence["system_crash_lines"], 1)
        self.assertEqual(evidence["system_crash_lines_ours"], 1)

    def test_faultlogger_new_file_fails(self):
        hilog = "11-18 I A00000/app/x: still running\n"
        result, _runtime = self._run(
            hilog, pidof_out="4242", fault_before=set(),
            fault_after={"cppcrash-org.qtproject.example.app-20020198-"
                         "20261118163801293.log"})
        self.assertEqual(result.status, "FAIL")
        self.assertIn("faultlogger", result.stderr)

    def test_pid_gone_fails(self):
        result, _runtime = self._run("11-18 I A00000/app/x: hello\n",
                                     pidof_out="")
        self.assertEqual(result.status, "FAIL")
        self.assertIn("pidof", result.stderr)

    def test_no_evidence_is_not_run(self):
        result, _runtime = self._run(
            "11-18 I A00000/otherapp/x: unrelated\n",
            pidof_out="error: device offline",
            env_extra={"bundle_name": "org.qtproject.example.fincept"})
        self.assertEqual(result.status, "NOT_RUN")


class TestHapAllowedLibs(unittest.TestCase):
    """D-02: an allowlist stored as a string gets expanded character by character, and "l" lets every lib* through."""

    def test_string_value_is_split(self):
        usable, rejected = verifier._hap_allowed_libs(
            {"hap_allowed_libs": "libssl.so.3,libcrypto.so.3"})
        self.assertEqual(usable, ["libssl.so.3", "libcrypto.so.3"])
        self.assertEqual(rejected, [])

    def test_single_char_prefix_is_rejected(self):
        usable, rejected = verifier._hap_allowed_libs({"hap_allowed_libs": "l"})
        self.assertEqual(usable, [])
        self.assertEqual(rejected, ["l"])

    def test_list_value_kept(self):
        usable, _rejected = verifier._hap_allowed_libs(
            {"hap_allowed_libs": ["libfoo.so", "l"]})
        self.assertEqual(usable, ["libfoo.so"])


class TestStaleRecords(unittest.TestCase):
    """D-03: records must be bound to "which HAP, which device"."""

    def test_record_of_other_hap_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            hap = project / "app.hap"
            hap.write_bytes(b"new-hap")
            st = state_mod.init_state(project)
            build_json = {"hap": "app.hap",
                          "hap_fingerprint": {"sha256": verifier.file_fingerprint(hap)["sha256"],
                                              "size": hap.stat().st_size,
                                              "mtime_ns": hap.stat().st_mtime_ns}}
            runtime = {"install": {"status": "PASS", "hap_sha256": "deadbeef"},
                       "launch": {"status": "PASS", "hap_sha256": "deadbeef"}}
            reasons = verifier.stale_reasons(st, build_json, runtime)
            self.assertTrue(any("another HAP" in r for r in reasons))

    def test_matching_record_is_not_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            hap = project / "app.hap"
            hap.write_bytes(b"same")
            sha = verifier.file_fingerprint(hap)["sha256"]
            st = state_mod.init_state(project)
            build_json = {"hap": "app.hap",
                          "hap_fingerprint": {"sha256": sha,
                                              "size": hap.stat().st_size,
                                              "mtime_ns": hap.stat().st_mtime_ns}}
            runtime = {"install": {"status": "PASS", "hap_sha256": sha}}
            self.assertEqual(verifier.stale_reasons(st, build_json, runtime), [])


class TestG13Loadable(unittest.TestCase):
    """D-05: unresolved symbols must be resolvable within the HAP, not just "it compiled"."""

    def _hap(self, project: Path, undefined, exports=()) -> Path:
        import zipfile
        lib = project / "libapp.so"
        write_elf_symbols(lib, undefined=undefined, exports=exports)
        hap = project / "app.hap"
        with zipfile.ZipFile(hap, "w") as archive:
            archive.write(lib, "libs/arm64-v8a/libapp.so")
        return hap

    def test_unresolved_symbol_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            hap = self._hap(Path(tmp), undefined=["__at_fini", "foo"])
            report = verifier._hap_symbol_report(hap, "arm64-v8a", [], set())
            self.assertEqual(report["unresolved"],
                             ["__at_fini (needed by libapp.so)",
                              "foo (needed by libapp.so)"])

    def test_packed_or_sysroot_exports_resolve(self):
        with tempfile.TemporaryDirectory() as tmp:
            hap = self._hap(Path(tmp), undefined=["foo"], exports=["bar"])
            report = verifier._hap_symbol_report(hap, "arm64-v8a", [], {"foo"})
            self.assertEqual(report["unresolved"], [])

    def test_allowed_prefix_resolves(self):
        with tempfile.TemporaryDirectory() as tmp:
            hap = self._hap(Path(tmp), undefined=["libva_tramp"])
            report = verifier._hap_symbol_report(
                hap, "arm64-v8a", ["libva"], set())
            self.assertEqual(report["unresolved"], [])

    def _evaluate(self, project: Path, env_extra=None, package="PASS"):
        st = state_mod.init_state(project)
        (project / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.16)\nproject(p)\n"
            "find_package(Qt6 COMPONENTS Core REQUIRED)\n", encoding="utf-8")
        st.write_json("env.json", dict({"qt_sdk_prefix": str(project),
                                        "cmake": "cmake"}, **(env_extra or {})))
        st.write_json("build.json", {"hap": "app.hap",
                                     "package": {"status": package},
                                     "compile": {"status": "PASS"}})
        gates, _overall = verifier.evaluate(st)
        return gates["G13"]

    def test_gate_skips_without_sysroot(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self._hap(project, undefined=["foo"])
            gate = self._evaluate(project)
            self.assertEqual(gate["status"], "SKIP")

    def test_gate_partial_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self._hap(project, undefined=["foo"])
            native = project / "native"
            (native / "sysroot" / "usr" / "lib" / "arm64-v8a").mkdir(parents=True)
            gate = self._evaluate(project, {"ohos_sdk_native": str(native)})
            self.assertEqual(gate["status"], "PARTIAL")
            self.assertIn("foo", gate["detail"])

    def test_gate_strict_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self._hap(project, undefined=["foo"])
            native = project / "native"
            (native / "sysroot" / "usr" / "lib" / "arm64-v8a").mkdir(parents=True)
            gate = self._evaluate(project, {"ohos_sdk_native": str(native),
                                            "undefined_gate": "strict"})
            self.assertEqual(gate["status"], "FAIL")


class TestProjectFlagInSubcommand(unittest.TestCase):
    """D-04: a subparser declaring its own --project overrides the global value."""

    def test_project_after_subcommand_survives(self):
        tool = REPO_ROOT / "tools" / "qt-ohos-run.py"
        for argv in (["--project", "/tmp/x", "libcheck", "core"],
                     ["libcheck", "core", "--project", "/tmp/x"]):
            proc = subprocess.run([sys.executable, str(tool)] + argv,
                                  capture_output=True, text=True, timeout=60)
            self.assertNotIn("no migration state in %s" % str(REPO_ROOT),
                             proc.stdout + proc.stderr,
                             "%s dropped --project: %s" % (argv, proc.stderr))


class TestDraftSummaryFile(unittest.TestCase):
    """D-19: long Chinese summaries get split into multiple arguments by PowerShell, so pass them via a file.

    The Chinese test summary below is intentional (non-ASCII round trip)."""

    def test_summary_file_is_read(self):
        cli = _load_cli()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            st = state_mod.init_state(project)
            summary_file = project / "summary.txt"
            summary_file.write_text("来自文件的摘要", encoding="utf-8")
            args = argparse.Namespace(project=str(project), title="t",
                                      summary=None,
                                      summary_file=str(summary_file),
                                      symptom=None, log=None, tag=None)
            created = {}
            original = cli.knowledge.create_draft

            def fake_create(kb_root, title, **kw):
                created.update(kw)
                return Path(tmp) / "QOH999.md"

            cli.knowledge.create_draft = fake_create
            try:
                cli.cmd_draft(args)
            finally:
                cli.knowledge.create_draft = original
            self.assertEqual(created.get("summary"), "来自文件的摘要")


class TestScanRound(unittest.TestCase):
    """D-20: two scan rounds must be distinguishable, and a config change must be visible."""

    def test_round_and_hash_are_recorded(self):
        tool = REPO_ROOT / "tools" / "qt-ohos-run.py"
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            make_project(project)
            for _ in range(2):
                proc = subprocess.run(
                    [sys.executable, str(tool), "--project", str(project),
                     "scan", "--force"],
                    capture_output=True, text=True, timeout=180)
                self.assertEqual(proc.returncode, 0, proc.stderr[-400:])
            info = json.loads((project / ".qt-ohos" / "scan.json")
                              .read_text(encoding="utf-8"))
            self.assertEqual(info["scan_round"], 2)
            self.assertEqual(len(info["scan_config_hash"]), 16)
            first = info["scan_config_hash"]
            proc = subprocess.run(
                [sys.executable, str(tool), "--project", str(project),
                 "config", "set", "qt_version", "6.6.0"],
                capture_output=True, text=True, timeout=180)
            self.assertEqual(proc.returncode, 0, proc.stderr[-400:])
            proc = subprocess.run(
                [sys.executable, str(tool), "--project", str(project),
                 "scan", "--force"],
                capture_output=True, text=True, timeout=180)
            self.assertEqual(proc.returncode, 0, proc.stderr[-400:])
            info = json.loads((project / ".qt-ohos" / "scan.json")
                              .read_text(encoding="utf-8"))
            self.assertEqual(info["scan_round"], 3)
            self.assertNotEqual(info["scan_config_hash"], first)


class TestPkgconfig(unittest.TestCase):
    """`.pc` relocation and shim: Windows hosts have no pkg-config, and HarmonyOS
    artifacts contain absolute build-machine paths (`prefix=/storage/Users/...`)."""

    PC = """\
prefix=/storage/Users/currentUser/.harmonybrew/Cellar/opus/1.6.1_1
exec_prefix=${prefix}
libdir=${prefix}/lib
includedir=${prefix}/include

Name: opus
Description: Opus IETF audio codec
Version: 1.6.1
Requires.private: vpx
Libs: -L${libdir} -lopus
Cflags: -I${includedir}/opus
"""

    def _tree(self, root: Path) -> Path:
        for pkg, ver in (("opus", "1.6.1"), ("libvpx", "1.17.0")):
            d = root / pkg / ver / "lib" / "pkgconfig"
            d.mkdir(parents=True)
            (root / pkg / ver / "lib").mkdir(exist_ok=True)
        (root / "opus" / "1.6.1" / "lib" / "pkgconfig" / "opus.pc") \
            .write_text(self.PC.replace(
                "/storage/Users/currentUser/.harmonybrew/Cellar/opus/1.6.1_1",
                "/storage/Users/currentUser/.harmonybrew/Cellar/opus/1.6.1_1"),
                encoding="utf-8")
        (root / "libvpx" / "1.17.0" / "lib" / "pkgconfig" / "vpx.pc") \
            .write_text(
                "prefix=/storage/Users/currentUser/.harmonybrew/Cellar/"
                "libvpx/1.17.0_2\nlibdir=${prefix}/lib\nincludedir="
                "${prefix}/include\n\nName: vpx\nVersion: 1.17.0\n"
                "Libs: -L/storage/Users/currentUser/.harmonybrew/Cellar/"
                "libvpx/1.17.0_2/lib -lvpx\nCflags: -I/storage/Users/"
                "currentUser/.harmonybrew/Cellar/libvpx/1.17.0_2/include\n",
                encoding="utf-8")
        return root

    def test_relocate_rewrites_build_machine_prefix(self):
        from qt_ohos import pkgconfig
        with tempfile.TemporaryDirectory() as tmp:
            root = self._tree(Path(tmp))
            out = pkgconfig.relocate_tree(root)
            self.assertEqual(out["scanned"], 2)
            text = (root / "opus" / "1.6.1" / "lib" / "pkgconfig" / "opus.pc") \
                .read_text(encoding="utf-8")
            self.assertIn(str(root / "opus" / "1.6.1"), text)
            self.assertNotIn("/storage/Users", text)
            # ${prefix}-derived entries must be kept verbatim, not concatenated twice
            self.assertIn("libdir=${prefix}/lib", text)
            self.assertIn("Name: opus", text)

    def test_relocate_is_idempotent(self):
        from qt_ohos import pkgconfig
        with tempfile.TemporaryDirectory() as tmp:
            root = self._tree(Path(tmp))
            pkgconfig.relocate_tree(root)
            again = pkgconfig.relocate_tree(root)
            self.assertEqual(again["changed"], [])

    def test_query_walks_requires_recursively(self):
        from qt_ohos import pkgconfig
        with tempfile.TemporaryDirectory() as tmp:
            root = self._tree(Path(tmp))
            pkgconfig.relocate_tree(root)
            res = pkgconfig.query(["opus"], root, want_cflags=True,
                                  want_libs=True, private=True)
            self.assertEqual(res["missing"], [])
            joined = " ".join(res["libs"])
            self.assertIn("-lopus", joined)
            self.assertIn(str(root / "libvpx" / "1.17.0" / "lib"), joined)
            self.assertTrue(all("/storage" not in c for c in res["cflags"]))

    def test_write_shim_creates_both_launchers(self):
        from qt_ohos import pkgconfig
        with tempfile.TemporaryDirectory() as tmp:
            out = pkgconfig.write_shim(Path(tmp) / "bin")
            names = sorted(Path(p).name for p in out["written"])
            self.assertEqual(names, ["pkg-config", "pkg-config.bat"])


class TestPkgconfigEnv(unittest.TestCase):
    """The generated pkg-config stand-in must actually be on the build environment's PATH.

    Writing the file without changing PATH means the project's
    `pkg_check_modules` still can't find packages -- nothing is fixed.
    """

    def test_shim_on_path_and_libdir(self):
        import types
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".qt-ohos" / "bin").mkdir(parents=True)
            (root / ".qt-ohos" / "bin" / "pkg-config.bat").write_text(
                "@echo off\n", encoding="utf-8")
            pc_dir = root / "ohos-libs" / "opus" / "1.6.1" / "lib" / "pkgconfig"
            pc_dir.mkdir(parents=True)
            (pc_dir / "opus.pc").write_text("Name: opus\n", encoding="utf-8")
            fake = types.SimpleNamespace(project_root=root,
                                         state_dir=root / ".qt-ohos")
            extra = builder_mod.pkgconfig_env(fake, {})
            self.assertTrue(extra["PATH"].startswith(
                str(root / ".qt-ohos" / "bin")))
            self.assertIn(str(pc_dir), extra["PKG_CONFIG_LIBDIR"])

    def test_no_shim_no_path_override(self):
        import types
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake = types.SimpleNamespace(project_root=root,
                                         state_dir=root / ".qt-ohos")
            extra = builder_mod.pkgconfig_env(fake, {})
            self.assertNotIn("PATH", extra)


class TestPkgAliases(unittest.TestCase):
    """D-07: of tdesktop's 8 unknowns, most are "name didn't match" rather than "not in the knowledge base"."""

    def test_report_alias_families(self):
        sys.path.insert(0, str(REPO_ROOT / "portgraph"))
        from port_graph import kb_seed
        for hint, expect in (("ada", "ada-url"),
                             ("libudev", "udev"), ("pango-1.0", "pango"),
                             ("pangomm-2.48", "pangomm"),
                             ("sigc++-2.0", "libsigc++")):
            self.assertEqual(kb_seed.PKG_ALIASES.get(hint), expect,
                             "%s should normalize to %s" % (hint, expect))


class TestFirstPartyDetection(unittest.TestCase):
    """D-07: the project's own subdirectories (auto_updates/crash_reports/tde2e/wallet_engine)
    are not third-party libraries and must not be called `pkg-unknown:*`. The
    criterion is whether the wrapper file declares dependencies."""

    def test_external_wrapper_without_deps_is_first_party(self):
        sys.path.insert(0, str(REPO_ROOT / "portgraph"))
        from port_graph import qt_scanner
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "auto_updates").mkdir()
            (root / "auto_updates" / "CMakeLists.txt").write_text(
                "add_library(external_auto_updates STATIC auto_updates.cpp)\n",
                encoding="utf-8")
            # only sources actually in the repo count as "built with the project"; an empty directory is an uninitialized submodule
            (root / "auto_updates" / "auto_updates.cpp").write_text(
                "int f() { return 1; }\n", encoding="utf-8")
            (root / "libs").mkdir()
            (root / "libs" / "CMakeLists.txt").write_text(
                "find_package(OpenAL REQUIRED)\n"
                "add_library(external_openal STATIC openal.cpp)\n",
                encoding="utf-8")
            info = qt_scanner._detect_first_party(
                root, ["auto_updates/CMakeLists.txt",
                       "libs/CMakeLists.txt"], [])
            folds = qt_scanner.first_party_folds({"first_party": info})
            self.assertIn("auto-updates", folds)
            self.assertNotIn("openal", folds)


class TestPlatformFileScope(unittest.TestCase):
    """D-11: _win.cpp/_mac.mm scattered across ordinary directories are not compiled for OHOS."""

    def test_suffix_and_token_matching(self):
        from qt_ohos import rule_engine as re_mod
        self.assertEqual(re_mod._path_scope("src/app/foo_win.cpp"),
                         "platform-excluded")
        self.assertEqual(re_mod._path_scope("src/bar_mac.mm"),
                         "platform-excluded")
        self.assertEqual(re_mod._path_scope("src/core_win32.cpp"),
                         "platform-excluded")
        for neutral in ("src/window.cpp", "src/machine.cpp", "src/Wine.cpp",
                        "src/main.cpp"):
            self.assertEqual(re_mod._path_scope(neutral), "", neutral)

    def test_guarded_ranges_excludes_non_ohos_branch(self):
        from qt_ohos import rule_engine as re_mod
        text = ("#include <x>\n"
                "#ifdef Q_OS_WIN\n"
                "int x = 1;\n"
                "#endif\n"
                "int y = 2;\n")
        ranges = re_mod._guarded_ranges(text)
        self.assertEqual(len(ranges), 1)
        self.assertIn(2, ranges[0])
        text2 = ("#if defined(Q_OS_LINUX)\n"
                 "int x = 1;\n"
                 "#endif\n")
        self.assertEqual(re_mod._guarded_ranges(text2), [])


class TestFixCandidates(unittest.TestCase):
    """D-12: pure CMake with no qrc: the auto-fix is empty, but a candidate list must be given."""

    def test_candidates_point_at_real_issues(self):
        from qt_ohos import migration
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.21)\n"
                "project(app CXX)\n"
                "find_package(Qt6 COMPONENTS Core Gui REQUIRED)\n"
                "add_executable(app main.cpp)\n"
                "find_package(X11 REQUIRED)\n"
                "set(CMAKE_CXX_STANDARD 20)\n",
                encoding="utf-8")
            cands = migration.fix_candidates(
                {"cmake_files": ["CMakeLists.txt"]}, root)
            ids = {c["id"] for c in cands}
            self.assertIn("cand-shared-lib", ids)
            self.assertIn("cand-xcb-dbus", ids)
            self.assertIn("cand-cxx20", ids)
            for cand in cands:
                self.assertTrue(cand["hits"])
                self.assertTrue(cand["why"])
                self.assertTrue(cand["fix"])
            # read-only: must not rewrite any file
            self.assertEqual(
                (root / "CMakeLists.txt").read_text(encoding="utf-8")
                .count("add_executable"), 1)


class TestPkgconfigCli(unittest.TestCase):
    """`pkgconfig` must pass through native pkg-config syntax (--cflags etc.),
    otherwise the only usage on Windows is assembling .pc paths by hand."""

    def test_passthrough_flags_reach_pkgconfig(self):
        tool = REPO_ROOT / "tools" / "qt-ohos-run.py"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pc = root / "opus" / "1.6.1" / "lib" / "pkgconfig"
            pc.mkdir(parents=True)
            (pc / "opus.pc").write_text(
                "prefix=%s\nlibdir=${prefix}/lib\nincludedir=${prefix}/include"
                "\n\nName: opus\nVersion: 1.6.1\nLibs: -L${libdir} -lopus\n"
                "Cflags: -I${includedir}\n" % (root / "opus" / "1.6.1"),
                encoding="utf-8")
            (root / "opus" / "1.6.1" / "lib").mkdir(exist_ok=True)
            proc = subprocess.run(
                [sys.executable, str(tool), "pkgconfig",
                 "--libdir", str(root), "--cflags", "--libs", "opus"],
                capture_output=True, text=True, timeout=120)
            self.assertEqual(proc.returncode, 0, proc.stderr[-400:])
            self.assertIn("-lopus", proc.stdout)
            self.assertIn("-I", proc.stdout)
            proc = subprocess.run(
                [sys.executable, str(tool), "pkgconfig",
                 "--libdir", str(root), "--relocate", "--dry-run"],
                capture_output=True, text=True, timeout=120)
            self.assertEqual(proc.returncode, 0, proc.stderr[-400:])
            self.assertIn("scanned 1 .pc", proc.stdout)


class TestSuggestPackages(unittest.TestCase):
    """D-07: distinguish "not in the knowledge base" from "name didn't match"."""

    def setUp(self):
        sys.path.insert(0, str(REPO_ROOT / "portgraph"))
        from port_graph import db, kb_seed
        self._db, self._seed = db, kb_seed
        self.conn = db.connect(":memory:")
        db.init_db(self.conn)
        kb_seed.seed_interfaces(self.conn)
        db.upsert_node(self.conn, "hb:ada-url", "package", "ada-url",
                       "harmonybrew", "ported")
        db.upsert_node(self.conn, "hb:pango", "package", "pango",
                       "harmonybrew", "unported")

    def tearDown(self):
        self.conn.close()

    def test_suggests_close_names_for_unknown_hint(self):
        hints = self._seed.suggest_packages(self.conn, "ada")
        self.assertIn("ada-url", hints)
        hints = self._seed.suggest_packages(self.conn, "pangoft2")
        self.assertIn("pango", hints)

    def test_no_suggestion_for_unrelated_name(self):
        self.assertEqual(self._seed.suggest_packages(self.conn, "zzzqqq"), [])
