"""port_graph self-tests: formula/README parsers + portability inference engine.

How to run (from the portgraph project root):

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import io
import re
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from port_graph import (cmdpkgs, db, deps_fetch, deps_report, engine,  # noqa: E402
                        harmonybrew, kb_seed, project_scanner, qt_scanner)

CURL_RB = PROJECT_ROOT / "workspace" / "hb-core" / "Formula" / "c" / "curl.rb"


class TestFormulaParser(unittest.TestCase):

    def test_curl_formula(self):
        if not CURL_RB.exists():
            self.skipTest("hb-core sparse checkout not present")
        info = harmonybrew.parse_formula(CURL_RB)
        self.assertEqual(info["name"], "curl")
        # Upstream formulas can evolve at any time (8.21.0 -> 8.22.0 -> ...),
        # so only check the version format, not a specific version
        self.assertRegex(info["version"], r"^8\.\d+(\.\d+)?(_\d+)?$")
        self.assertTrue(info["ohos_bottle"])
        self.assertTrue(info["keg_only_macos"])
        deps = {d[0]: (d[1], d[2]) for d in info["deps"]}
        self.assertIn("brotli", deps)
        self.assertEqual(deps["brotli"][0], ["runtime"])
        self.assertIn("openssl@3", deps)
        # Dependencies inside a head do block are ignored
        self.assertNotIn("autoconf", deps)
        # Platform conditional blocks
        self.assertEqual(deps["zlib-ng-compat"][1], "linux")
        self.assertEqual(deps["libidn2"][1], "linux+macos-old")
        self.assertEqual(deps["pkgconf"][0], ["build", "test"])
        ufm = [u[0] for u in info["uses_from_macos"]]
        self.assertIn("krb5", ufm)
        self.assertIn("openldap", ufm)

    def test_formula_without_ohos_bottle(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "foo.rb"
            f.write_text(
                'class Foo < Formula\n'
                '  desc "demo"\n'
                '  url "https://example.com/foo-1.2.3.tar.gz"\n'
                '  depends_on "bar"\n'
                '  bottle do\n'
                '    sha256 cellar: :any, arm64_sonoma: "abc"\n'
                '  end\n'
                'end\n', encoding="utf-8")
            info = harmonybrew.parse_formula(f)
            self.assertFalse(info["ohos_bottle"])
            self.assertEqual(info["version"], "1.2.3")
            self.assertEqual([d[0] for d in info["deps"]], ["bar"])


class TestCmdpkgsParser(unittest.TestCase):

    def test_readme_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            readme = Path(tmp) / "README.md"
            # Fixture intentionally in Chinese: mirrors the external cmd-pkgs README format
            readme.write_text(
                "# t\n\n## 语言运行时列表\n"
                "|软件|版本|安装命令|\n|---|---|---|\n"
                "|node|24.0.0|curl x \\| sh|\n\n"
                "## 命令行&&三方库列表\n"
                "|软件|版本|安装命令|\n|-----|----|----|\n"
                "|openssl|1.1.1w|curl y|\n"
                "|openssl|3.0.1|curl z|\n"
                "\n其他文本行结束表格。\n", encoding="utf-8")
            entries = cmdpkgs.parse_readme(readme)
            names = {e["name"]: e["version"] for e in entries}
            self.assertEqual(names["node"], "24.0.0")
            # For multiple versions with the same name, take the last one
            self.assertEqual(names["openssl"], "3.0.1")
            self.assertEqual(len(entries), 2)


class TestKbSeed(unittest.TestCase):

    def test_normalize_module(self):
        self.assertEqual(kb_seed.normalize_module("Qt Core"), "core")
        self.assertEqual(kb_seed.normalize_module("Qt Quick Controls"),
                         "quickcontrols")
        self.assertEqual(kb_seed.normalize_module("Qt D-Bus"), "dbus")
        self.assertEqual(kb_seed.normalize_module("Qt 3D"), "3d")

    def test_seed_from_real_page(self):
        if not kb_seed.MODULES_PAGE.exists():
            self.skipTest("modules page missing")
        conn = db.connect(":memory:")
        db.init_db(conn)
        r = kb_seed.ingest(conn)
        self.assertGreaterEqual(r["qt_modules"], 40)
        self.assertIn("Qt WebEngine (all submodules)", r["blocked_modules"])
        core = db.get_node(conn, "qtmod:core")
        self.assertEqual(core["port_status"], "ported")
        we = db.get_node(conn, "qtmod:webengine")
        self.assertEqual(we["port_status"], "blocked")
        self.assertEqual(core["cluster_id"], "cluster:qt")
        conn.close()


def _build_graph(conn):
    """Small graph: app dependency chain + Qt modules + interfaces."""
    db.init_db(conn)
    kb_seed.seed_interfaces(conn)
    db.upsert_cluster(conn, "cluster:qt", "Qt", "framework")
    db.upsert_node(conn, "app:demo", "app", "demo", "scan", "unknown")
    db.upsert_node(conn, "hb:pkga", "package", "pkga", "harmonybrew", "ported")
    db.upsert_node(conn, "hb:pkgb", "package", "pkgb", "harmonybrew", "ported")
    db.upsert_node(conn, "hb:pkgu", "package", "pkgu", "harmonybrew", "unknown")
    db.upsert_node(conn, "qtmod:core", "qt-module", "Qt Core", "kb-seed",
                   "ported", cluster_id="cluster:qt")
    db.upsert_node(conn, "qtmod:webengine", "qt-module", "Qt WebEngine",
                   "kb-seed", "blocked", cluster_id="cluster:qt")


class TestEngine(unittest.TestCase):

    def _conn(self):
        conn = db.connect(":memory:")
        _build_graph(conn)
        return conn

    def test_portable_chain(self):
        conn = self._conn()
        db.upsert_edge(conn, "app:demo", "hb:pkga", "runtime")
        db.upsert_edge(conn, "hb:pkga", "hb:pkgb", "runtime")
        db.upsert_edge(conn, "app:demo", "qtmod:core", "uses-module")
        r = engine.analyze(conn, "app:demo")
        self.assertEqual(r["verdict"], "portable")
        self.assertEqual(r["blockers"], [])
        conn.close()

    def test_blocked_module(self):
        conn = self._conn()
        db.upsert_edge(conn, "app:demo", "qtmod:webengine", "uses-module")
        r = engine.analyze(conn, "app:demo")
        self.assertEqual(r["verdict"], "blocked")
        kinds = {b["kind"] for b in r["blockers"]}
        self.assertIn("unsupported-module", kinds)
        paths = [b["path"] for b in r["blockers"]
                 if b["node"] == "qtmod:webengine"]
        self.assertIn(["app:demo", "qtmod:webengine"], paths)
        conn.close()

    def test_unknown_dependency_uncertain(self):
        conn = self._conn()
        db.upsert_edge(conn, "app:demo", "hb:pkgu", "runtime")
        r = engine.analyze(conn, "app:demo")
        self.assertEqual(r["verdict"], "uncertain")
        self.assertTrue(any(u["kind"] == "unknown-package"
                            for u in r["unknowns"]))
        conn.close()

    def test_unsupported_interface_blocks(self):
        conn = self._conn()
        db.add_node_interface(conn, "app:demo", "iface:dbus",
                              evidence="QDBusConnection @ main.cpp")
        r = engine.analyze(conn, "app:demo")
        self.assertEqual(r["verdict"], "blocked")
        self.assertTrue(any(b["kind"] == "unsupported-interface"
                            for b in r["blockers"]))
        conn.close()

    def test_dependency_cycle_terminates(self):
        conn = self._conn()
        db.upsert_edge(conn, "app:demo", "hb:pkga", "runtime")
        db.upsert_edge(conn, "hb:pkga", "hb:pkgb", "runtime")
        db.upsert_edge(conn, "hb:pkgb", "hb:pkga", "runtime")
        r = engine.analyze(conn, "app:demo")
        self.assertEqual(r["verdict"], "portable")
        conn.close()

    def test_macos_only_dep_skipped(self):
        conn = self._conn()
        db.upsert_node(conn, "hb:macdep", "package", "macdep", "harmonybrew",
                       "blocked")
        db.upsert_edge(conn, "app:demo", "hb:macdep", "runtime",
                       platform_cond="macos")
        r = engine.analyze(conn, "app:demo")
        # macOS conditional dependencies are not needed on HarmonyOS and must not block
        self.assertEqual(r["verdict"], "portable")
        conn.close()

    def test_build_deps_not_considered(self):
        conn = self._conn()
        db.upsert_node(conn, "hb:tool", "package", "tool", "harmonybrew",
                       "blocked")
        db.upsert_edge(conn, "app:demo", "hb:tool", "build")
        r = engine.analyze(conn, "app:demo")
        self.assertEqual(r["verdict"], "portable")
        conn.close()


class TestMacroStack(unittest.TestCase):
    """Macro stack tracking: #ifdef/#if defined/#else/#endif guard state."""

    def test_platform_macro_excludes(self):
        # Code wrapped in Q_OS_WIN is not compiled on HarmonyOS
        code = (
            "#ifdef Q_OS_WIN\n"
            "  QDBusConnection c;\n"
            "#endif\n"
        )
        g = project_scanner._macro_stack_status(code)
        # QDBusConnection is on line 2 and should be excluded by the platform guard
        self.assertIn(2, g)
        self.assertEqual(g[2], "platform-excluded")

    def test_else_branch_switches(self):
        code = (
            "#ifdef Q_OS_WIN\n"
            "  // win code\n"
            "#else\n"
            "  // ohos/linux code\n"
            "#endif\n"
        )
        g = project_scanner._macro_stack_status(code)
        self.assertEqual(g[2], "platform-excluded")  # #ifdef branch
        # The #else branch compiles on HarmonyOS (Q_OS_WIN false -> NOT Q_OS_WIN true)
        self.assertEqual(g[4], "ohos-active")

    def test_nested_macros(self):
        code = (
            "#ifdef Q_OS_LINUX\n"
            "  #ifdef Q_OS_WIN\n"
            "    win inside linux\n"
            "  #endif\n"
            "  linux only\n"
            "#endif\n"
        )
        g = project_scanner._macro_stack_status(code)
        # Q_OS_LINUX is active on HarmonyOS (HarmonyOS implies Linux), so the outer block is not excluded
        # Only the inner Q_OS_WIN is excluded
        self.assertEqual(g[3], "platform-excluded")  # win inside linux
        self.assertEqual(g[5], "ohos-active")        # linux only

    def test_ohos_macro_active(self):
        code = (
            "#ifdef Q_OS_OHOS\n"
            "  ohos specific\n"
            "#endif\n"
        )
        g = project_scanner._macro_stack_status(code)
        self.assertEqual(g[2], "ohos-active")

    def test_if_defined_form(self):
        code = (
            "#if defined(_WIN32) || defined(_WIN64)\n"
            "  win code\n"
            "#endif\n"
        )
        g = project_scanner._macro_stack_status(code)
        self.assertEqual(g[2], "platform-excluded")

    def test_or_with_ohos_macro_compiles(self):
        """defined(Q_OS_WIN) || defined(Q_OS_OHOS) compiles on HarmonyOS."""
        code = (
            "#if defined(Q_OS_WIN) || defined(Q_OS_OHOS)\n"
            "  compiles on ohos\n"
            "#endif\n"
        )
        g = project_scanner._macro_stack_status(code)
        self.assertEqual(g[2], "ohos-active")

    def test_and_with_win_macro_excluded(self):
        """defined(Q_OS_LINUX) && defined(Q_OS_WIN) does not compile on HarmonyOS."""
        code = (
            "#if defined(Q_OS_LINUX) && defined(Q_OS_WIN)\n"
            "  not on ohos\n"
            "#endif\n"
        )
        g = project_scanner._macro_stack_status(code)
        self.assertEqual(g[2], "platform-excluded")

    def test_ifndef_win_compiles_on_ohos(self):
        """#ifndef Q_OS_WIN is true on HarmonyOS (Q_OS_WIN undefined)."""
        code = (
            "#ifndef Q_OS_WIN\n"
            "  non-win code\n"
            "#endif\n"
        )
        g = project_scanner._macro_stack_status(code)
        self.assertEqual(g[2], "ohos-active")


class TestFilePlatformExclusion(unittest.TestCase):
    """File-level platform isolation: path contains a platform keyword -> platform-file-excluded."""

    def test_macos_path_excluded(self):
        self.assertEqual(
            project_scanner._file_platform_excluded(
                "src/platform/macos/foo.mm"),
            "macos")
        self.assertEqual(
            project_scanner._file_platform_excluded(
                "src/framework/mac/util.mm"),
            "macos")

    def test_windows_path_excluded(self):
        self.assertEqual(
            project_scanner._file_platform_excluded(
                "src/platform/windows/foo.cpp"),
            "windows")
        self.assertEqual(
            project_scanner._file_platform_excluded(
                "src/ui/win/helper.cpp"),
            "windows")

    def test_filename_suffix_excluded(self):
        # Desktop projects often name platform implementations xxx_win.cpp / xxx.mm rather than putting them under platform/win
        self.assertEqual(
            project_scanner._file_platform_excluded("src/core/app_win.cpp"),
            "windows")
        self.assertEqual(
            project_scanner._file_platform_excluded("src/ui/view.mm"),
            "macos")
        self.assertEqual(
            project_scanner._file_platform_excluded("src/core/window_win.h"),
            "windows")

    def test_generic_suffix_not_excluded(self):
        # Names like darwin_helper.cpp / windowsless.cpp must not be caught by mistake
        self.assertIsNone(project_scanner._file_platform_excluded(
            "src/core/darwin_helper.cpp"))
        self.assertIsNone(project_scanner._file_platform_excluded(
            "src/core/win.cpp"))

    def test_linux_path_not_excluded(self):
        # Generic Linux code compiles on HarmonyOS and must not be excluded
        self.assertIsNone(project_scanner._file_platform_excluded(
            "src/platform/linux/foo.cpp"))

    def test_generic_path_not_excluded(self):
        self.assertIsNone(project_scanner._file_platform_excluded(
            "src/core/main.cpp"))


class TestWin32ApiPrecision(unittest.TestCase):
    """Function-like symbols must carry call parentheses: engine::SendMessage{ is a member with the same name, not the Win32 API."""

    def _win32(self):
        for rule in project_scanner.PLATFORM_API_RULES:
            if rule["iface"] == "iface:win32":
                return rule["re"]
        raise AssertionError("iface:win32 rule missing")

    def test_member_like_identifier_not_matched(self):
        self.assertIsNone(self._win32().search("engine::SendMessage{"))
        self.assertIsNone(self._win32().search("auto msg = SendMessage;"))

    def test_real_calls_matched(self):
        self.assertIsNotNone(self._win32().search("SendMessage(hwnd, WM_CLOSE, 0, 0);"))
        self.assertIsNotNone(self._win32().search("HWND h = nullptr;"))
        self.assertIsNotNone(self._win32().search("#include <windows.h>"))


class TestDepsFetch(unittest.TestCase):
    """fetch-deps: dependency closure + artifact classification (fully offline, dry-run / local extraction)."""

    def _conn(self):
        conn = db.connect(":memory:")
        db.init_db(conn)
        db.upsert_node(conn, "app:demo", "app", "demo", "scan", "blocked")
        db.upsert_node(conn, "hb:pkga", "package", "pkga", "harmonybrew",
                       "ported", version="1.0",
                       links={"artifact_url": "https://harmonybrew.atomgit.com"
                              "/bottles/pkga-1.0.arm64_ohos.bottle.tar.gz",
                              "artifact_cmd": "brew install pkga"})
        db.upsert_node(conn, "hb:pkgb", "package", "pkgb", "harmonybrew",
                       "ported", version="2.0",
                       links={"artifact_url": "https://gitcode.com/x/y"
                              "/releases/download/pkgs/pkgb-2.0-ohos-aarch64.tar.gz"})
        db.upsert_node(conn, "hb:pkgc", "package", "pkgc", "harmonybrew",
                       "ported", links={"artifact_cmd": "brew install pkgc"})
        db.upsert_node(conn, "hb:pkgd", "package", "pkgd", "harmonybrew",
                       "unknown",
                       links={"source_url": "https://example.com/pkgd-1.tar.gz"})
        db.upsert_node(conn, "hb:zeta", "package", "zeta", "harmonybrew",
                       "unknown")
        db.upsert_node(conn, "cmdpkgs:zeta", "package", "zeta", "cmdpkgs",
                       "ported", version="3.3",
                       links={"artifact_url": "https://gitcode.com/x/y"
                              "/releases/download/pkgs/zeta-3.3-ohos-aarch64.tar.gz"})
        db.upsert_node(conn, "qtmod:core", "qt-module", "Qt Core", "kb-seed",
                       "ported")
        db.upsert_node(conn, "hb:toolx", "package", "toolx", "harmonybrew",
                       "ported")
        db.upsert_node(conn, "hb:pkgx", "package", "pkgx", "harmonybrew",
                       "ported")
        db.upsert_edge(conn, "app:demo", "hb:pkga", "runtime")
        db.upsert_edge(conn, "hb:pkga", "hb:pkgb", "runtime")
        db.upsert_edge(conn, "app:demo", "hb:pkgc", "runtime")
        db.upsert_edge(conn, "app:demo", "hb:pkgd", "runtime")
        db.upsert_edge(conn, "app:demo", "hb:zeta", "runtime")
        db.upsert_edge(conn, "app:demo", "cmdpkgs:zeta", "runtime")
        db.upsert_edge(conn, "app:demo", "qtmod:core", "uses-module")
        db.upsert_edge(conn, "app:demo", "hb:toolx", "build")
        db.upsert_edge(conn, "app:demo", "hb:pkgx", "runtime",
                       platform_cond="macos")
        return conn

    def test_closure_rules(self):
        conn = self._conn()
        ids = {n["id"] for n in deps_fetch.dependency_closure(
            conn, "app:demo")}
        self.assertIn("hb:pkgb", ids)       # runtime deps of a ported package are still expanded
        self.assertIn("qtmod:core", ids)    # provided nodes are in the closure
        self.assertNotIn("hb:toolx", ids)   # build edges create no target-side artifact needs
        self.assertNotIn("hb:pkgx", ids)    # macos conditional dependency skipped
        conn.close()

    def test_dry_run_classification(self):
        conn = self._conn()
        db.upsert_node(conn, "pkg-unknown:gtest", "package", "gtest",
                       "scan", "unknown")
        db.upsert_edge(conn, "app:demo", "pkg-unknown:gtest", "runtime")
        with tempfile.TemporaryDirectory() as tmp:
            m = deps_fetch.fetch_app_deps(conn, "app:demo", Path(tmp),
                                          dry_run=True)
            by_id = {e["id"]: e for e in m["deps"]}
            # Test frameworks no longer falsely reported as need_port (must port yourself)
            self.assertEqual(by_id["pkg-unknown:gtest"]["status"], "test")
            self.assertEqual(by_id["pkg-unknown:gtest"]["role"], "test")
            self.assertEqual(m["summary"].get("test"), 1)
            self.assertEqual(by_id["app:demo"]["status"], "target")
            self.assertEqual(by_id["qtmod:core"]["status"], "provided")
            self.assertEqual(by_id["hb:pkga"]["status"], "would_download")
            self.assertEqual(by_id["hb:pkgb"]["status"], "would_download")
            self.assertEqual(by_id["hb:pkgc"]["status"], "cmd_only")
            self.assertEqual(by_id["hb:pkgd"]["status"], "need_port")
            self.assertEqual(by_id["hb:pkgd"]["source_url"],
                             "https://example.com/pkgd-1.tar.gz")
            # Cross-source fill-in: hb:zeta has no direct link, the direct link of same-named cmdpkgs:zeta fills in
            self.assertEqual(by_id["hb:zeta"]["status"], "would_download")
            self.assertEqual(by_id["cmdpkgs:zeta"]["status"], "covered")
            self.assertNotIn("manifest_path", m)
            self.assertEqual(sorted(Path(tmp).iterdir()), [])  # dry-run writes nothing to disk
            self.assertIn("would_download", m["summary"])
            self.assertTrue(m["toolchain"]["cmake_prefix_path"])
        conn.close()

    def test_extract_replaces_readonly_leftover(self):
        """Read-only partial leftovers from a previous failure: re-extraction should replace them wholesale, not raise PermissionError."""
        import os
        import stat as stat_mod
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            tar_path = tmp / "pkg.tar.gz"
            with tarfile.open(tar_path, "w:gz") as tar:
                ti = tarfile.TarInfo("lib/libz.so.1.3")
                ti.size = 1
                tar.addfile(ti, io.BytesIO(b"Z"))
            target = tmp / "out" / "zeta" / "3.3"
            stale = target / "lib" / "stale.so"
            stale.parent.mkdir(parents=True)
            stale.write_bytes(b"old")
            os.chmod(stale, stat_mod.S_IREAD)   # brew read-only leftover
            deps_fetch._extract_tarball(tar_path, target)
            self.assertFalse(stale.exists())
            self.assertTrue((target / "lib" / "libz.so.1.3").is_file())

    def test_extract_flat_tarball(self):
        """cmd-pkgs flat layout: links land as copies (NTFS); root location and library list are correct."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            tar_path = tmp / "pkg.tar.gz"
            with tarfile.open(tar_path, "w:gz") as tar:
                ti = tarfile.TarInfo("lib/libz.so.1.3")
                ti.size = 1
                tar.addfile(ti, io.BytesIO(b"Z"))
                for lname in ("lib/libz.so.1", "lib/libz.so"):
                    link = tarfile.TarInfo(lname)
                    link.type = tarfile.SYMTYPE
                    link.linkname = "libz.so.1.3"
                    tar.addfile(link)
                ti2 = tarfile.TarInfo("include/zlib.h")
                ti2.size = 1
                tar.addfile(ti2, io.BytesIO(b"h"))
            target = tmp / "out" / "zeta" / "3.3"
            fixed = deps_fetch._extract_tarball(tar_path, target)
            self.assertEqual(fixed, ["lib/libz.so.1", "lib/libz.so"])
            self.assertTrue((target / "lib" / "libz.so.1").is_file())
            root = deps_fetch._locate_root(target)
            self.assertEqual(root, target)
            self.assertEqual(deps_fetch._list_libs(root), ["z"])
        self.assertEqual(
            deps_fetch._ver_from_url(
                "https://gitcode.com/x/releases/download/pkgs/"
                "zeta-3.3-ohos-aarch64.tar.gz"),
            "3.3")


class TestDepsReport(unittest.TestCase):
    """Comprehensive dependency analysis: role classification / version ranges / toolchain / dynamic loading / vendored."""

    CMAKE = """
cmake_minimum_required(VERSION 3.16)
project(Foo VERSION 1.2.3)
set(CMAKE_CXX_STANDARD 17)
find_package(Qt5 5.15 REQUIRED COMPONENTS Core Widgets
                                 OPTIONAL_COMPONENTS Network)
find_package(ZLIB 1.2 REQUIRED)
find_package(OpenSSL)
find_package(GTest)
find_package(ECM)
find_program(PYTHON3_EXECUTABLE python3)
execute_process(COMMAND protoc --version)
pkg_check_modules(FF REQUIRED "libavcodec >= 58")
enable_testing()
add_test(NAME t1 COMMAND foo)
"""

    PRO = """
QT += core gui widgets
CONFIG += c++17
LIBS += -L/some/path -lbaz -lm
"""

    MAIN_CPP = """
#include <zlib.h>
#include <QtWidgets>
int main() {
    dlopen("libfoo.so", 2);
    QLibrary lib("barplugin");
    return 0;
}
"""

    def _project(self, tmp: Path):
        root = tmp / "foo"
        (root / "src").mkdir(parents=True)
        (root / "3rdparty" / "quux").mkdir(parents=True)
        (root / "CMakeLists.txt").write_text(self.CMAKE.strip() + "\n",
                                             encoding="utf-8")
        (root / "src" / "main.cpp").write_text(self.MAIN_CPP,
                                               encoding="utf-8")
        (root / "foo.pro").write_text(self.PRO, encoding="utf-8")
        (root / "conanfile.txt").write_text(
            "[requires]\nzlib/[>=1.2 <2]\n", encoding="utf-8")
        (root / ".gitmodules").write_text(
            '[submodule "dep/spdlog"]\n'
            "\tpath = dep/spdlog\n"
            "\turl = https://github.com/gabime/spdlog.git\n",
            encoding="utf-8")
        return root

    def _conn(self):
        conn = db.connect(":memory:")
        db.init_db(conn)
        kb_seed.seed_interfaces(conn)
        db.upsert_node(conn, "hb:zlib", "package", "zlib", "harmonybrew",
                       "ported", version="1.3.2",
                       links={"artifact_url": "https://harmonybrew.atomgit.com"
                              "/bottles/zlib-1.3.2.arm64_ohos.bottle.tar.gz"})
        db.upsert_node(conn, "hb:zstd", "package", "zstd", "harmonybrew",
                       "ported", version="1.5.7",
                       links={"artifact_url": "https://harmonybrew.atomgit.com"
                              "/bottles/zstd-1.5.7.arm64_ohos.bottle.tar.gz"})
        db.upsert_node(conn, "hb:openssl@3", "package", "openssl@3",
                       "harmonybrew", "ported", version="3.6.4")
        db.upsert_node(conn, "qtmod:core", "qt-module", "Qt Core", "kb-seed",
                       "ported")
        db.upsert_edge(conn, "hb:zlib", "hb:zstd", "runtime")
        return conn

    def test_find_package_parse(self):
        fp = {"name": "Qt5", "name_lower": "qt5", "version": "5.15",
              "required": True, "exact": False,
              "components": ["Core", "Widgets"],
              "optional_components": ["Network"], "file": "CMakeLists.txt",
              "line": 4}
        got = qt_scanner._parse_findpkg_args(
            "Qt5", " 5.15 REQUIRED COMPONENTS Core Widgets\n"
            " OPTIONAL_COMPONENTS Network", "CMakeLists.txt", 4)
        self.assertEqual(got, fp)

    def test_report_classification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            conn = self._conn()
            report = deps_report.analyze_dependencies(conn, root)
            # ---- link classification and version ranges
            link = {d["name"].lower(): d for d in report["link_deps"]}
            self.assertIn("zlib", link)
            self.assertEqual(link["zlib"]["min_version"], "1.2")
            self.assertTrue(link["zlib"]["required"])
            self.assertEqual(link["zlib"]["version_range"], "[>=1.2 <2]")
            self.assertEqual(link["zlib"]["version_check"], "satisfied")
            self.assertEqual(link["zlib"]["resolved_node"], "hb:zlib")
            self.assertEqual(link["zlib"]["available_version"], "1.3.2")
            # OpenSSL without REQUIRED -> optional
            self.assertIn("openssl", link)
            self.assertFalse(link["openssl"]["required"])
            # pkg_check_modules version constraint (libavcodec merged into ffmpeg via alias)
            self.assertIn("ffmpeg", link)
            self.assertEqual(link["ffmpeg"]["version_req"], ">= 58")
            # qmake LIBS
            self.assertIn("baz", link)
            self.assertIn("m", link)
            self.assertEqual(link["m"]["kind"], "system-lib")
            # ---- toolchain
            t = report["toolchain"]
            self.assertEqual(t["cmake_min"], "3.16")
            self.assertEqual(t["cxx_standard"], 17)
            tools = {x["tool"] for x in t["tools"]}
            self.assertIn("python3", tools)   # find_program
            self.assertIn("protoc", tools)    # COMMAND
            self.assertTrue(t["has_testing"])
            # ---- test dependencies
            self.assertTrue(any(d["name"] == "GTest"
                                for d in report["test_deps"]))
            # ---- runtime transitive closure (zlib -> zstd)
            rt = {d["name"]: d for d in report["runtime_deps"]}
            self.assertIn("zstd", rt)
            self.assertEqual(rt["zstd"]["needed_by"], ["zlib"])
            self.assertEqual(rt["zstd"]["version"], "1.5.7")
            # ---- dynamic loading
            dl = {d["name"]: d for d in report["dynamic_loads"]}
            self.assertIn("libfoo.so", dl)
            self.assertIn("barplugin", dl)
            # ---- vendored
            vendored = {d["name"] for d in report["vendored"]}
            self.assertIn("dep/spdlog", vendored)
            self.assertIn("3rdparty", vendored)
            # ---- Qt
            q = report["qt"]
            self.assertEqual(q["major"], "5")
            self.assertEqual(q["min_version"], "5.15")
            self.assertEqual(q["check"], "satisfied")
            mods = {m["module"]: m for m in q["modules"]}
            self.assertEqual(mods["core"]["status"], "ported")
            self.assertFalse(mods["network"]["required"])  # OPTIONAL_COMPONENTS
            # ---- ECM classified as a build tool rather than link
            self.assertNotIn("ecm", link)
            self.assertTrue(any(
                bt.get("tool") == "ecm" or "ecm" in (bt.get("how") or [])
                for bt in report["toolchain"]["tools"]))
            conn.close()

    def test_version_conflict_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.16)\n"
                "project(Foo)\n"
                "find_package(ZLIB 9.9 REQUIRED)\n", encoding="utf-8")
            conn = self._conn()
            report = deps_report.analyze_dependencies(conn, root)
            link = {d["name"].lower(): d for d in report["link_deps"]}
            self.assertEqual(link["zlib"]["version_check"], "conflict")
            self.assertTrue(any("zlib" in w["msg"].lower()
                                for w in report["warnings"]))
            conn.close()

    def test_alias_version_scheme_not_false_conflict(self):
        """A version constraint after alias merging (libavcodec >= 58 -> ffmpeg) is in terms of
        the library's major version, not comparable to the package version: should be unknown, not a spurious conflict."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.16)\n"
                "project(Foo)\n"
                'pkg_check_modules(FF REQUIRED "libavcodec >= 58")\n',
                encoding="utf-8")
            conn = self._conn()
            db.upsert_node(conn, "hb:ffmpeg", "package", "ffmpeg",
                           "harmonybrew", "ported", version="9.0.2")
            report = deps_report.analyze_dependencies(conn, root)
            link = {d["name"].lower(): d for d in report["link_deps"]}
            self.assertIn("ffmpeg", link)
            self.assertEqual(link["ffmpeg"]["version_req"], ">= 58")
            self.assertEqual(link["ffmpeg"]["version_check"], "unknown")
            # No version-conflict warning; instead an info entry explains the version scales are not comparable
            self.assertFalse(any(
                w["level"] == "warn" and "version conflict" in w["msg"]
                for w in report["warnings"]))
            self.assertTrue(any(
                w["level"] == "info" and "libavcodec" in w["msg"]
                for w in report["warnings"]))
            conn.close()

    def test_cross_source_same_lib_merged(self):
        """The same library under different names across sources (hb:qrencode / cmdpkgs:libqrencode) is merged into a single
        link entry; no more multiple contradictory entries for the same library."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.16)\n"
                "project(Foo)\n"
                "find_package(QREncode REQUIRED)\n"
                "find_package(libqrencode REQUIRED)\n", encoding="utf-8")
            conn = self._conn()
            db.upsert_node(conn, "hb:qrencode", "package", "qrencode",
                           "harmonybrew", "ported", version="4.1.1",
                           links={"artifact_url": "https://x/qrencode.bottle.tar.gz"})
            db.upsert_node(conn, "cmdpkgs:libqrencode", "package", "libqrencode",
                           "cmdpkgs", "ported", version="4.1.1",
                           links={"artifact_url": "https://x/libqrencode.tar.gz"})
            report = deps_report.analyze_dependencies(conn, root)
            names = [d["name"].lower() for d in report["link_deps"]]
            self.assertEqual(names.count("libqrencode") + names.count("qrencode"),
                             1)
            entry = next(d for d in report["link_deps"]
                         if d["name"].lower() in ("libqrencode", "qrencode"))
            self.assertTrue((entry.get("artifact") or {}).get("ready"))
            # Evidence from both declarations is kept
            self.assertEqual(len(entry["evidence"]), 2)
            conn.close()

    def test_no_conn_still_classifies(self):
        """Without a DB (conn=None), a pure scan still produces role classification; only the artifacts are empty."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            report = deps_report.analyze_dependencies(None, root)
            link = {d["name"].lower(): d for d in report["link_deps"]}
            self.assertIn("zlib", link)
            self.assertEqual(link["zlib"]["version_check"], "unknown")
            self.assertEqual(report["counts"]["test"], 1)
            self.assertTrue(report["counts"]["vendored"] >= 2)

    def test_build_tools_count_matches_display(self):
        """build_tools count matches the text report: tools list + fixed CMake/C++/compiler
        lines (fixes double counting when tools already contains build_tools entries)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            conn = self._conn()
            report = deps_report.analyze_dependencies(conn, root)
            t = report["toolchain"]
            expected = len(t["tools"]) + (1 if t["cmake_min"] else 0) \
                + (1 if t["cxx_standard"] else 0) + 1
            self.assertEqual(report["counts"]["build_tools"], expected)
            conn.close()

    def test_libav_version_not_false_conflict(self):
        """libavcodec >= 58 is a library major version (~ffmpeg 4.x), a different scale from ffmpeg release
        versions: must not be falsely reported as conflict; record unknown with an explanation."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            conn = self._conn()
            db.upsert_node(conn, "hb:ffmpeg", "package", "ffmpeg",
                           "harmonybrew", "ported", version="7.1")
            report = deps_report.analyze_dependencies(conn, root)
            link = {d["name"].lower(): d for d in report["link_deps"]}
            self.assertEqual(link["ffmpeg"]["version_req"], ">= 58")
            # Merged implementation: adopts worker1's generic version_req_from approach
            # (replacing worker2's original libav-major-specific marker)
            self.assertEqual(link["ffmpeg"]["version_req_from"],
                             "libavcodec")
            self.assertEqual(link["ffmpeg"]["version_check"], "unknown")
            self.assertFalse(any(w["msg"].startswith("ffmpeg version conflict")
                                 for w in report["warnings"]))
            conn.close()

    def test_runtime_closure_cache_shared(self):
        """With the shared graph cache, closure results and dedup rules are unchanged: when two link deps point to the same
        transitive dependency, needed_by merges both sides, and cyclic graphs do not loop forever."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            conn = self._conn()
            # zlib -> zstd -> zlib (cycle) + openssl -> zstd (shared transitive dependency)
            db.upsert_edge(conn, "hb:zstd", "hb:zlib", "runtime")
            db.upsert_edge(conn, "hb:openssl@3", "hb:zstd", "runtime")
            report = deps_report.analyze_dependencies(conn, root)
            rt = {d["name"].lower(): d for d in report["runtime_deps"]}
            self.assertIn("zstd", rt)
            self.assertIn("zlib", set(rt["zstd"]["needed_by"]))
            conn.close()

    def test_manifest_roles(self):
        """fetch-deps manifest: depth determines role (link/runtime/provided)."""
        conn = self._conn()
        db.upsert_node(conn, "app:demo", "app", "demo", "scan", "unknown")
        db.upsert_edge(conn, "app:demo", "hb:zlib", "runtime")
        db.upsert_edge(conn, "app:demo", "qtmod:core", "uses-module")
        with tempfile.TemporaryDirectory() as tmp:
            m = deps_fetch.fetch_app_deps(conn, "app:demo", Path(tmp),
                                          dry_run=True)
            roles = {e["name"]: e.get("role") for e in m["deps"]}
            self.assertEqual(roles["zlib"], "link")        # depth 1
            self.assertEqual(roles["zstd"], "runtime")     # depth 2 transitive
            self.assertEqual(roles["Qt Core"], "provided")
            self.assertEqual(m["roles"].get("link"), 1)
            self.assertEqual(m["roles"].get("runtime"), 1)
        conn.close()

    def test_fetch_cross_source_dedup(self):
        """Cross-source dedup of the same library under different names (normalized name: lib prefix removed): download only once."""
        conn = self._conn()
        db.upsert_node(conn, "app:demo", "app", "demo", "scan", "unknown")
        db.upsert_node(conn, "hb:qrencode", "package", "qrencode",
                       "harmonybrew", "ported", version="4.1.1",
                       links={"artifact_url": "https://x/qrencode.bottle.tar.gz"})
        db.upsert_node(conn, "cmdpkgs:libqrencode", "package", "libqrencode",
                       "cmdpkgs", "ported", version="4.1.1",
                       links={"artifact_url": "https://x/libqrencode.tar.gz"})
        # Ghost node xkbcommon and libxkbcommon are the same library under different names: the artifact should fill in instead of need_port
        db.upsert_node(conn, "pkg-unknown:xkbcommon", "package", "xkbcommon",
                       "scan", "unknown")
        db.upsert_node(conn, "hb:libxkbcommon", "package", "libxkbcommon",
                       "harmonybrew", "ported", version="1.13.2",
                       links={"artifact_url": "https://x/libxkbcommon.tar.gz"})
        for dst in ("hb:qrencode", "cmdpkgs:libqrencode",
                    "pkg-unknown:xkbcommon", "hb:libxkbcommon"):
            db.upsert_edge(conn, "app:demo", dst, "runtime")
        with tempfile.TemporaryDirectory() as tmp:
            m = deps_fetch.fetch_app_deps(conn, "app:demo", Path(tmp),
                                          dry_run=True)
            by_id = {e["id"]: e for e in m["deps"]}
            self.assertEqual(by_id["hb:qrencode"]["status"], "would_download")
            self.assertEqual(by_id["cmdpkgs:libqrencode"]["status"], "covered")
            self.assertEqual(by_id["pkg-unknown:xkbcommon"]["status"],
                             "would_download")
            self.assertEqual(by_id["hb:libxkbcommon"]["status"], "covered")
            self.assertEqual(m["summary"].get("would_download"), 2)
        conn.close()

    def test_fetch_special_classification(self):
        """CMake built-ins (OpenMP) / test frameworks (GTest) no longer shown as "must port yourself"."""
        conn = self._conn()
        db.upsert_node(conn, "app:demo", "app", "demo", "scan", "unknown")
        for ghost in ("openmp", "gtest"):
            db.upsert_node(conn, "pkg-unknown:%s" % ghost, "package", ghost,
                           "scan", "unknown")
            db.upsert_edge(conn, "app:demo", "pkg-unknown:%s" % ghost,
                           "runtime")
        with tempfile.TemporaryDirectory() as tmp:
            m = deps_fetch.fetch_app_deps(conn, "app:demo", Path(tmp),
                                          dry_run=True)
            by_name = {e["name"]: e for e in m["deps"]}
            # OpenMP: compiler feature, provided with the NDK, not in need_port
            self.assertEqual(by_name["openmp"]["status"], "provided")
            self.assertEqual(by_name["openmp"]["role"], "build-tool")
            # GTest: role=test, explicitly not in the release package
            self.assertEqual(by_name["gtest"]["role"], "test")
            self.assertIn("not part of the release package", by_name["gtest"].get("note", ""))
        conn.close()


class TestScanAliasResolution(unittest.TestCase):
    """Scan-time alias resolution: pkg-config library names resolve directly to HarmonyOS packages, no ghost nodes."""

    def _project(self, tmp: Path):
        root = tmp / "aliasproj"
        root.mkdir(parents=True)
        (root / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.16)\n"
            "project(AliasProj)\n"
            'pkg_check_modules(FF REQUIRED "libavcodec >= 58")\n',
            encoding="utf-8")
        return root

    def test_libavcodec_resolves_to_ffmpeg(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            db.upsert_node(conn, "hb:ffmpeg", "package", "ffmpeg",
                           "harmonybrew", "ported", version="9.0.2")
            scan = project_scanner.scan_project(conn, root)
            self.assertEqual(scan["deps_linked"],
                             [{"hint": "libavcodec", "node": "hb:ffmpeg",
                               "status": "ported", "alias": "ffmpeg"}])
            self.assertEqual(scan["deps_unknown"], [])
            edges = {e["dst"] for e in db.out_edges(conn, scan["app_id"])}
            self.assertIn("hb:ffmpeg", edges)
            self.assertNotIn("pkg-unknown:libavcodec", edges)
            conn.close()


class TestDepsFullForms(unittest.TestCase):
    """Second-round enhancements: bare tll names / find_library / -framework / FetchContent /
    qmake PKGCONFIG / meson / autotools / CI script installs."""

    CMAKE = """
cmake_minimum_required(VERSION 3.16)
project(Full)
add_library(internal STATIC src/x.cpp)
add_executable(fullapp src/main.cpp)
find_library(KEYUTILS_LIBRARIES NAMES keyutils REQUIRED)
target_link_libraries(fullapp PRIVATE internal z ssl Qt5::Core
  ${BOTAN_LIBRARIES} -lpthread
  "-framework Foundation -framework AppKit"
  Wtsapi32.lib
)
FetchContent_Declare(qhotkey
  GIT_REPOSITORY https://github.com/Skycoder42/QHotkey.git
  GIT_TAG v1.1.0
)
function(search_dependency pkg)
  # internally looks up indirectly via pkg_check_modules/find_library
endfunction()
set(TOXCORE_MINIMUM_VERSION "0.2.20")
search_dependency(TOXCORE PACKAGE libtoxcore LIBRARY toxcore
  MINIMUM_VERSION ${TOXCORE_MINIMUM_VERSION})
"""

    MESON = """
project('m', 'cpp', meson_version: '>= 0.53',
        default_options: ['cpp_std=gnu++17'])
glib_dep = dependency('glib-2.0', version: '>= 2.36', required: true)
opt_dep = dependency('gtk+-3.0', required: false)
m_dep = cc.find_library('m')
qt_dep = dependency('qt5', modules: ['Core', 'Widgets'])
"""

    CONFIGURE_AC = """
PKG_CHECK_MODULES([FOO], [zlib >= 1.2 libcurl])
AC_CHECK_LIB([m], [sqrt])
"""

    def _project(self, tmp: Path):
        root = tmp / "full"
        (root / "src").mkdir(parents=True)
        (root / ".github" / "workflows").mkdir(parents=True)
        (root / "CMakeLists.txt").write_text(self.CMAKE, encoding="utf-8")
        (root / "app.pro").write_text(
            "QT += core\nPKGCONFIG += libqrencode\n", encoding="utf-8")
        (root / "meson.build").write_text(self.MESON, encoding="utf-8")
        (root / "configure.ac").write_text(self.CONFIGURE_AC,
                                           encoding="utf-8")
        (root / ".github" / "workflows" / "ci.yml").write_text(
            "run: sudo apt install cmake libkeyutils-dev zlib1g-dev\n",
            encoding="utf-8")
        return root

    def test_scanner_extractions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            info = qt_scanner.scan_project(root)
            raw = {e["name"].lower(): e for e in info["raw_libs"]}
            # bare tll names / find_library / -l / .lib normalization
            for n in ("z", "ssl", "keyutils", "pthread", "wtsapi32"):
                self.assertIn(n, raw, "raw_libs missing %s" % n)
            self.assertNotIn("internal", raw)      # in-project targets excluded
            self.assertNotIn("qt5::core", raw)     # imported targets excluded
            self.assertNotIn("botan_libraries", raw)
            # find_library goes into raw_libs
            self.assertIn("find_library", raw["keyutils"]["hows"])
            # macOS frameworks
            fw = {f["name"] for f in info["macos_frameworks"]}
            self.assertEqual(fw, {"Foundation", "AppKit"})
            # FetchContent: name/URL/pinned tag
            self.assertEqual(len(info["fetched_deps"]), 1)
            fd = info["fetched_deps"][0]
            self.assertEqual(fd["name"], "qhotkey")
            self.assertEqual(fd["how"], "FetchContent")
            self.assertEqual(fd["tag"], "v1.1.0")
            # Custom wrapper function: PACKAGE name + set() variable version resolution (quoted)
            self.assertEqual(len(info["wrapper_deps"]), 1)
            wdp = info["wrapper_deps"][0]
            self.assertEqual(wdp["name"], "libtoxcore")
            self.assertEqual(wdp["wrapper"], "search_dependency")
            self.assertEqual(wdp["library"], "toxcore")
            self.assertEqual(wdp["version"], "0.2.20")
            # qmake PKGCONFIG
            self.assertEqual([p["name"] for p in info["qmake_pkgconfig"]],
                             ["libqrencode"])
            # meson: version requirement / optional / built-in qt modules / cc.find_library
            md = {d["name"]: d for d in info["meson_deps"]}
            self.assertEqual(md["glib-2.0"]["version"], ">= 2.36")
            self.assertFalse(md["gtk+-3.0"]["required"])
            self.assertEqual(info["meson"]["version_min"], "0.53")
            self.assertEqual(info["meson"]["cxx_standard"], 17)
            self.assertIn("core", info["qt_modules"])
            self.assertIn("widgets", info["qt_modules"])
            self.assertIn("m", raw)              # cc.find_library merged into raw_libs
            # autotools: PKG_CHECK_MODULES version constraints
            ad = {d["name"]: d for d in info["autotools_deps"]}
            self.assertEqual(ad["zlib"]["version_req"], ">= 1.2")
            self.assertIn("libcurl", ad)
            # CI script installs
            env = {e["name"] for e in info["env_installs"]}
            self.assertEqual(env, {"cmake", "libkeyutils-dev",
                                   "zlib1g-dev"})

    def test_report_full_forms(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            db.upsert_node(conn, "hb:glib", "package", "glib", "harmonybrew",
                           "ported", version="2.84.4")
            report = deps_report.analyze_dependencies(conn, root)
            link = {d["name"].lower(): d for d in report["link_deps"]}
            # meson version constraint + check (2.84.4 >= 2.36)
            self.assertEqual(link["glib-2.0"]["version_req"], ">= 2.36")
            self.assertEqual(link["glib-2.0"]["version_check"], "satisfied")
            # macOS frameworks -> platform-iface
            self.assertEqual(link["foundation"]["kind"], "platform-iface")
            # .lib → win32-system-lib
            self.assertEqual(link["wtsapi32"]["kind"], "win32-system-lib")
            # -pthread / z / ssl -> system libraries
            self.assertEqual(link["z"]["kind"], "system-lib")
            self.assertEqual(link["pthread"]["kind"], "system-lib")
            # FetchContent -> vendored (with pinned tag)
            vend = {v["name"]: v for v in report["vendored"]}
            self.assertEqual(vend["qhotkey"]["tag"], "v1.1.0")
            # Custom wrapper function declaration -> link (version constraint resolved via set() variable)
            self.assertEqual(link["libtoxcore"]["version_req"], ">= 0.2.20")
            # autotools version constraint
            self.assertEqual(link["zlib"]["version_req"], ">= 1.2")
            # env list
            names = {e["name"] for e in report["env_deps"]}
            self.assertIn("libkeyutils-dev", names)
            # toolchain: minimum meson version
            tools = {t["tool"] for t in report["toolchain"]["tools"]}
            self.assertIn("meson", tools)
            self.assertEqual(report["toolchain"]["cxx_standard"], 17)
            conn.close()


class TestDbNameLookup(unittest.TestCase):
    """Case-insensitive lookup in find_node_by_name (regression: lower(name)=lower(?)
    cannot use an index -> full table scan hotspot in deps reports on large DBs; 2026-09 integration rollback
    performance fix: COLLATE NOCASE + functional index, semantically equivalent, folds ASCII only)"""

    def _conn(self):
        conn = db.connect(":memory:")
        db.init_db(conn)
        db.upsert_node(conn, "hb:boost", "package", "Boost", "harmonybrew", "ported", version="1.92.0")
        db.upsert_node(conn, "hb:zlib", "package", "zlib", "harmonybrew", "ported", version="1.3.1")
        return conn

    def test_case_insensitive_lookup(self):
        conn = self._conn()
        for probe in ("boost", "BOOST", "Boost", "bOoSt"):
            node = db.find_node_by_name(conn, probe)
            self.assertIsNotNone(node, probe)
            self.assertEqual(node["id"], "hb:boost")
        conn.close()

    def test_exact_match_still_works(self):
        conn = self._conn()
        self.assertEqual(db.find_node_by_name(conn, "zlib")["version"], "1.3.1")
        self.assertIsNone(db.find_node_by_name(conn, "no-such-pkg"))
        conn.close()

    def test_nocase_index_created_and_used(self):
        conn = self._conn()
        indexes = {r["name"] for r in
                   conn.execute("PRAGMA index_list(nodes)").fetchall()}
        self.assertIn("idx_nodes_name_nocase", indexes)
        plan = conn.execute(
            "EXPLAIN QUERY PLAN "
            "SELECT * FROM nodes WHERE name='boost' COLLATE NOCASE LIMIT 1"
        ).fetchall()
        self.assertIn("idx_nodes_name_nocase", plan[0]["detail"])
        conn.close()


class TestGeneralizationFixes(unittest.TestCase):
    """Regression tests for problems exposed by out-of-corpus generalization tests (gen_f/gen_e/gen_a, 2026-09):
    URL version extraction / macro-wrapped targets / find_library keywords / env -y /
    shared resolution ladder / in-tree detection / test role for raw link names."""

    # ---- 0) table gaps exposed by the gen_d generalization round (2026-09 worker2-deps-regress)
    def test_gen_d_regress_classifications(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "lm"
            (root / "src").mkdir(parents=True)
            (root / "CMakeLists.txt").write_text("""
cmake_minimum_required(VERSION 3.16)
project(LmRegress)
find_package(PackageHandleStandardArgs)
find_package(PythonInterp)
find_package(Perl)
find_package(OpenGL)
find_package(OggVorbis)
pkg_check_modules(PULSE libpulse)
find_package(CxxTest)
add_library(app STATIC src/x.cpp)
target_link_libraries(app PRIVATE cxxtest)
""", encoding="utf-8")
            (root / "src" / "x.cpp").write_text("", encoding="utf-8")
            info = qt_scanner.scan_project(root)
            fp = set(info["cmake_packages"]["find_package"])
            # CMake utility modules / OpenGL system capability: not in the package list
            for n in ("packagehandlestandardargs", "opengl"):
                self.assertNotIn(n, fp, n)
            # Host interpreters stay in the list (build-tool on the report side, no edge on the graph side)
            for n in ("perl", "pythoninterp"):
                self.assertIn(n, fp, n)
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            db.upsert_node(conn, "hb:libvorbis", "package", "libvorbis",
                           "harmonybrew", "ported")
            # Graph side: host interpreters / CMake modules / opengl create no runtime edges and no ghosts
            scan = project_scanner.scan_project(conn, root)
            hints = [d["hint"] for d in scan["deps_linked"]] + \
                [d["hint"] for d in scan["deps_unknown"]]
            for n in ("perl", "pythoninterp", "packagehandlestandardargs",
                      "opengl"):
                self.assertNotIn(n, hints, n)
            report = deps_report.analyze_dependencies(conn, root)
            link = {d["name"].lower(): d for d in report["link_deps"]}
            # Composite module name oggvorbis merged into libvorbis via alias
            self.assertIn("libvorbis", link)
            self.assertNotIn("oggvorbis", link)
            # libpulse -> platform interface (PulseAudio has no HarmonyOS service)
            self.assertEqual(link["libpulse"]["kind"], "platform-iface")
            # cxxtest -> test framework, not in link and needs no porting
            self.assertNotIn("cxxtest", link)
            self.assertIn("cxxtest",
                          {t["name"] for t in report["test_deps"]})
            tools = {t["tool"] for t in report["toolchain"]["tools"]}
            # Host interpreters classified as build-tool (if they enter the report by another path)
            self.assertIn("perl", tools)
            conn.close()

    # ---- 0b) libgen_g generalization round: binding-generator toolchain + combined stripping of lib prefix + version suffix
    def test_gen_g_bindings_and_ladder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "os"
            (root / "bindings").mkdir(parents=True)
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.16)\nproject(OsB)\n"
                "add_subdirectory(bindings)\n", encoding="utf-8")
            (root / "bindings" / "CMakeLists.txt").write_text(
                "find_package(SWIG 3.0 REQUIRED)\n"
                "find_package(Java REQUIRED)\n"
                "find_package(JNI REQUIRED)\n"
                "find_package(Ruby)\n"
                "find_package(PythonLibs 3)\n"
                "pkg_check_modules(PC_PIPEWIRE libpipewire-0.3)\n",
                encoding="utf-8")
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            db.upsert_node(conn, "hb:ruby", "package", "ruby", "harmonybrew",
                           "ported")
            db.upsert_node(conn, "hb:pipewire", "package", "pipewire",
                           "harmonybrew", "ported")
            # Graph side: binding tools create no runtime edges (ruby no longer linked to hb:ruby)
            scan = project_scanner.scan_project(conn, root)
            hints = [d["hint"] for d in scan["deps_linked"]] + \
                [d["hint"] for d in scan["deps_unknown"]]
            for n in ("swig", "ruby", "java", "jni", "pythonlibs"):
                self.assertNotIn(n, hints, n)
            # libpipewire-0.3 resolves to hb:pipewire (see 0c), no ghost
            self.assertEqual(scan["deps_unknown"], [])
            # Report side: binding tools classified as build-tools
            report = deps_report.analyze_dependencies(conn, root)
            tools = {t["tool"] for t in report["toolchain"]["tools"]}
            for n in ("swig", "ruby", "java", "jni", "pythonlibs"):
                self.assertIn(n, tools, n)
            link = {d["name"].lower() for d in report["link_deps"]}
            self.assertNotIn("swig", link)
            conn.close()

    # ---- 0e) gen_d second round: platform-interface library names / versioned library name merging
    def test_gen_d_iface_libnames_and_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "lm2"
            root.mkdir()
            (root / "CMakeLists.txt").write_text("""
cmake_minimum_required(VERSION 3.16)
project(Lm2)
find_library(ASOUND asound)
find_library(PULSE pulse)
find_library(FS1 fluidsynth-1)
add_library(p STATIC a.c)
target_link_libraries(p PRIVATE ${ASOUND} ${PULSE} ${FS1} sfftw)
""", encoding="utf-8")
            (root / "a.c").write_text("", encoding="utf-8")
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            db.upsert_node(conn, "cmdpkgs:fftw", "package", "fftw",
                           "cmdpkgs", "ported", version="3.3.10")
            report = deps_report.analyze_dependencies(conn, root)
            link = {d["name"].lower(): d for d in report["link_deps"]}
            # ALSA / PulseAudio library name forms -> platform-iface
            self.assertEqual(link["asound"]["kind"], "platform-iface")
            self.assertEqual(link["pulse"]["kind"], "platform-iface")
            # fluidsynth-1 / sfftw merged into the base name
            self.assertNotIn("fluidsynth-1", link)
            self.assertNotIn("sfftw", link)
            self.assertIn("fftw", link)
            self.assertEqual(link["fftw"]["available_version"], "3.3.10")
            conn.close()

    # ---- 0c) graph-side resolution check (hint keeps the original name; the node should hit hb:pipewire)
    def test_gen_g_ladder_node_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "os2"
            root.mkdir()
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.16)\nproject(OsC)\n"
                "pkg_check_modules(PC_PIPEWIRE libpipewire-0.3)\n",
                encoding="utf-8")
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            db.upsert_node(conn, "hb:pipewire", "package", "pipewire",
                           "harmonybrew", "ported")
            scan = project_scanner.scan_project(conn, root)
            linked = {d["hint"]: d["node"] for d in scan["deps_linked"]}
            self.assertEqual(linked.get("libpipewire-0.3"), "hb:pipewire")
            self.assertEqual(scan["deps_unknown"], [])
            conn.close()

    # ---- 0d) libgen_g second round: win32 gap libraries + OpenCV target name merging
    def test_gen_g_win32_and_target_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "os3"
            root.mkdir()
            (root / "CMakeLists.txt").write_text("""
cmake_minimum_required(VERSION 3.16)
project(OsD)
add_library(osd STATIC a.c)
if(WIN32)
    target_link_libraries(osd PUBLIC imagehlp dbghelp ole32)
endif()
if(ENABLE_OPENCV)
    target_link_libraries(osd PUBLIC opencv_core opencv_dnn)
endif()
pkg_check_modules(BABL babl-0.1)
""", encoding="utf-8")
            (root / "a.c").write_text("", encoding="utf-8")
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            db.upsert_node(conn, "cmdpkgs:opencv", "package", "opencv",
                           "cmdpkgs", "ported")
            report = deps_report.analyze_dependencies(conn, root)
            link = {d["name"].lower(): d for d in report["link_deps"]}
            # win32 system libraries
            for n in ("imagehlp", "dbghelp"):
                self.assertEqual(link[n]["kind"], "win32-system-lib", n)
            # OpenCV imported target names merged into opencv (no longer 5 separate ghosts)
            self.assertIn("opencv", link)
            for n in ("opencv_core", "opencv_dnn"):
                self.assertNotIn(n, link, n)
            # babl-0.1 version suffix stripped to babl (the same ghost)
            conn.close()

    # ---- 1) harmonybrew URL version extraction (root cause of 419 formulas without a version)
    def test_url_version_extraction(self):
        cases = {
            # Name suffix segments after the version such as -b2-nodocs / -bin / -complete (boost/ant/antlr)
            "https://github.com/boostorg/boost/releases/download/boost-1.92.0/boost-1.92.0-b2-nodocs.tar.xz": "1.92.0",
            "https://www.apache.org/dyn/closer.lua?path=ant/binaries/apache-ant-1.10.18-bin.tar.xz": "1.10.18",
            "https://www.antlr.org/download/antlr-4.13.2-complete.jar": "4.13.2",
            # Rust crate extension
            "https://static.crates.io/crates/action-validator/action-validator-0.9.0.crate": "0.9.0",
            # Uppercase V prefix / letter suffix without digits
            "https://github.com/CycoPH/atasm/archive/refs/tags/V1.30.tar.gz": "1.30",
            "https://loop-aes.sourceforge.net/aespipe/aespipe-v2.4j.tar.bz2": "2.4j",
            "https://www.harding.motd.ca/autossh/autossh-1.4g.tgz": "1.4g",
            # 7z extension + hyphenated patch-number version (confirmed with imagemagick 7.1.2-31;
            # before the fix it degraded to the trailing "31.7z" -> bottle URL 404)
            "https://github.com/ImageMagick/ImageMagick/releases/download/7.1.2-31/ImageMagick-7.1.2-31.7z": "7.1.2-31",
            "https://github.com/ImageMagick/ImageMagick6/releases/download/6.9.13-56/ImageMagick-6.9.13-56.7z": "6.9.13-56",
            # Regression: existing forms unchanged
            "https://www.zlib.net/zlib-1.3.1.tar.gz": "1.3.1",
            "https://github.com/i/indi/archive/refs/tags/v2.0.9.tar.gz": "2.0.9",
            "https://ftp.gnu.org/gnu/gzip/gzip-1.14.tar.xz": "1.14",
            # Version as a standalone path segment (fallback rule)
            "https://chiselapp.com/user/moinejf/repository/abcm2ps/tarball/v8.14.18/download.tar.gz": "8.14.18",
        }
        for url, want in cases.items():
            m = harmonybrew._URL_VER_RE.search(url)
            got = m.group(1) if m else None
            if not got:
                m2 = harmonybrew._URL_VER_SEG_RE.search(url)
                got = m2.group(1) if m2 else None
            self.assertEqual(got, want, "version of %s" % url)

    # ---- 2) macro-wrapped add_library (confirmed with gen_a kis_add_library)
    def test_macro_wrapped_add_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "p"
            root.mkdir()
            (root / "CMakeLists.txt").write_text("""
cmake_minimum_required(VERSION 3.16)
project(MacroWrap)
macro(kis_add_library)
    add_library(${REAL_UNPARSED_ARGUMENTS})
endmacro()
kis_add_library(gen_aui SHARED src/x.cpp)
add_executable(app src/main.cpp)
target_link_libraries(app PRIVATE gen_aui zlib)
""", encoding="utf-8")
            (root / "src").mkdir()
            (root / "src" / "x.cpp").write_text("", encoding="utf-8")
            (root / "src" / "main.cpp").write_text("", encoding="utf-8")
            info = qt_scanner.scan_project(root)
            raw = {e["name"].lower() for e in info["raw_libs"]}
            self.assertNotIn("gen_aui", raw)   # in-project target defined by a macro
            self.assertIn("zlib", raw)

    # ---- 2b) add_library indirected through a set() variable (confirmed with fakevim)
    def test_var_indirect_add_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "p"
            root.mkdir()
            (root / "CMakeLists.txt").write_text("""
cmake_minimum_required(VERSION 3.16)
project(VarIndirect)
set(bin fakevim)
add_library(${bin} STATIC fakevim.cpp)
add_executable(app main.cpp)
target_link_libraries(app PRIVATE ${bin} libgit2)
""", encoding="utf-8")
            (root / "fakevim.cpp").write_text("", encoding="utf-8")
            (root / "main.cpp").write_text("", encoding="utf-8")
            info = qt_scanner.scan_project(root)
            raw = {e["name"].lower() for e in info["raw_libs"]}
            self.assertNotIn("fakevim", raw)
            self.assertIn("libgit2", raw)

    # ---- 3) CMake variable names / single-character junk in find_library argument lists
    def test_find_library_skips_keyword_junk(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "p"
            root.mkdir()
            (root / "CMakeLists.txt").write_text("""
cmake_minimum_required(VERSION 3.16)
project(FindJunk)
find_library(QUAZIP_LIBRARIES WIN32_DEBUG_POSTFIX d
    NAMES quazip5 quazip HINTS /usr/lib)
""", encoding="utf-8")
            info = qt_scanner.scan_project(root)
            raw = {e["name"].lower() for e in info["raw_libs"]}
            self.assertNotIn("win32_debug_postfix", raw)
            self.assertNotIn("d", raw)
            self.assertIn("quazip5", raw)
            self.assertIn("quazip", raw)

    # ---- 4) option tokens of apt install -y in CI scripts are not listed
    def test_env_install_dash_y(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "p"
            (root / ".github" / "workflows").mkdir(parents=True)
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.16)\nproject(EnvY)\n",
                encoding="utf-8")
            (root / ".github" / "workflows" / "ci.yml").write_text(
                "run: apt install -y libtag-dev\n"
                "run: apt upgrade -y\n", encoding="utf-8")
            info = qt_scanner.scan_project(root)
            env = {e["name"] for e in info["env_installs"]}
            self.assertEqual(env, {"libtag-dev"})

    # ---- 5) shared resolution ladder (scan time and report time use the same rules)
    def test_resolve_pkg_ladder(self):
        conn = db.connect(":memory:")
        db.init_db(conn)
        kb_seed.seed_interfaces(conn)
        for nid, name in (("hb:sqlite", "sqlite"), ("hb:fftw", "fftw"),
                          ("hb:glib", "glib"), ("cmdpkgs:gstreamer", "gstreamer"),
                          ("hb:jpeg-turbo", "jpeg-turbo")):
            db.upsert_node(conn, nid, "package", name, "harmonybrew",
                           "ported", version="1.0")
        # Same library, different names (hb package-name aliases take precedence, eliminating the sqlite3/sqlite double artifact)
        self.assertEqual(kb_seed.resolve_pkg_name(conn, "sqlite3")["id"],
                         "hb:sqlite")
        # lib prefix stripping + variant suffix (libfftw3f_omp -> fftw)
        self.assertEqual(kb_seed.resolve_pkg_name(conn, "libfftw3f_omp")["id"],
                         "hb:fftw")
        # pkg-config component names (gio-2.0 -> glib; gstreamer-base -> gstreamer)
        self.assertEqual(kb_seed.resolve_pkg_name(conn, "gio-2.0")["id"],
                         "hb:glib")
        self.assertEqual(kb_seed.resolve_pkg_name(conn, "gstreamer-base-1.0")["id"],
                         "cmdpkgs:gstreamer")
        # build-form suffix (jpeg-static -> jpeg-turbo)
        self.assertEqual(kb_seed.resolve_pkg_name(conn, "jpeg-static")["id"],
                         "hb:jpeg-turbo")
        # No match returns None
        self.assertIsNone(kb_seed.resolve_pkg_name(conn, "no-such-pkg"))
        conn.close()

    # ---- 5b) scan-time ghost nodes use the alias canonical name (botan3/botan-3 merged)
    def test_scan_ghost_canonical_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "p"
            root.mkdir()
            (root / "CMakeLists.txt").write_text(
                'pkg_check_modules(B REQUIRED botan-3)\n'
                'find_package(Botan3 REQUIRED)\n', encoding="utf-8")
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            scan = project_scanner.scan_project(conn, root)
            unknown = {u["hint"] for u in scan["deps_unknown"]}
            self.assertEqual(unknown, {"botan-3"})   # both declarations map to the same ghost
            conn.close()

    # ---- 6) in-tree detection: unresolved names that hit a bundled source directory in the project
    def test_in_tree_dir_classification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "p"
            lib = root / "src" / "libraries" / "fakevim"
            lib.mkdir(parents=True)
            for i in range(4):
                (lib / ("f%d.cpp" % i)).write_text("", encoding="utf-8")
            (lib / "CMakeLists.txt").write_text(
                "project(fakevim)\n", encoding="utf-8")
            # The dependency-collection parent directory needs >= 5 library subdirectories
            for k in ("qtcsv", "qhotkey", "md4c", "botan", "sonnet"):
                d = root / "src" / "libraries" / k
                d.mkdir(parents=True)
                (d / "CMakeLists.txt").write_text("", encoding="utf-8")
                (d / "x.cpp").write_text("", encoding="utf-8")
            (root / "CMakeLists.txt").write_text(
                "find_package(fakevim REQUIRED)\n"
                "find_package(Lager REQUIRED)\n", encoding="utf-8")
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            report = deps_report.analyze_dependencies(conn, root)
            link = {d["name"].lower(): d for d in report["link_deps"]}
            self.assertEqual(link["fakevim"]["kind"], "in-tree")
            self.assertTrue(link["fakevim"]["artifact"]["ready"])
            # Unresolved names without a same-named source directory are still need_port gaps
            self.assertEqual(link["lager"]["kind"], "package")
            self.assertFalse((link["lager"].get("artifact") or {}).get("ready"))
            conn.close()

    # ---- 6b) in-tree does not wrongly take in the project's own code directories (confirmed with gen_a lager/lcms)
    def test_in_tree_rejects_project_code_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "p"
            d = root / "libs" / "flake" / "text" / "lager"
            d.mkdir(parents=True)
            (d / "CMakeLists.txt").write_text("", encoding="utf-8")
            (d / "CssLength.cpp").write_text("", encoding="utf-8")
            # Glue directory (no build files)
            g = root / "plugins" / "jpeg" / "3rdparty" / "lcms"
            g.mkdir(parents=True)
            (g / "iccjpeg.c").write_text("", encoding="utf-8")
            (g / "iccjpeg.h").write_text("", encoding="utf-8")
            (root / "CMakeLists.txt").write_text(
                "find_package(Lager REQUIRED)\n", encoding="utf-8")
            from port_graph.deps_report import (_in_tree_dir_index,
                                                _match_in_tree_dir)
            idx = _in_tree_dir_index(root)
            self.assertIsNone(_match_in_tree_dir(idx, "lager"))
            self.assertIsNone(_match_in_tree_dir(idx, "lcms"))

    # ---- 6e) git submodule link dependencies (confirmed with corpus_a kcoreaddons/microtex):
    #          with a shallow clone and no init, submodule directories are empty and invisible to the in-tree index,
    #          but .gitmodules declares them -> unresolved names go to in-tree, no false
    #          "no artifact -> must build from source"; same-named deps resolved to an artifact get an extra
    #          "submodule can be built with the project" note (confirmed with cmark-gfm/xxhash)
    def test_submodule_link_classification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "p"
            root.mkdir()
            (root / ".gitmodules").write_text(
                '[submodule "corpus_a/ThirdParty/kcoreaddons"]\n'
                "\tpath = corpus_a/ThirdParty/kcoreaddons\n"
                "\turl = https://github.com/KDE/kcoreaddons.git\n"
                '[submodule "corpus_a/ThirdParty/xxHash"]\n'
                "\tpath = corpus_a/ThirdParty/xxHash\n"
                "\turl = https://github.com/Cyan4973/xxHash.git\n",
                encoding="utf-8")
            (root / "CMakeLists.txt").write_text(
                "add_executable(app main.cpp)\n"
                "target_link_libraries(app PRIVATE\n"
                "  desktop-app::external_kcoreaddons\n"
                "  desktop-app::external_xxhash)\n", encoding="utf-8")
            (root / "main.cpp").write_text("int main(){}\n", encoding="utf-8")
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            db.upsert_node(conn, "hb:xxhash", "package", "xxhash",
                           "harmonybrew", "ported", version="0.8.3",
                           links={"artifact_url": "http://x/xxhash.tar.gz"})
            report = deps_report.analyze_dependencies(conn, root)
            link = {d["name"].lower(): d for d in report["link_deps"]}
            # Unresolved + submodule declaration -> in-tree (source ships with the repo)
            self.assertEqual(link["kcoreaddons"]["kind"], "in-tree")
            self.assertTrue(link["kcoreaddons"]["artifact"]["ready"])
            self.assertIn("git submodule",
                          link["kcoreaddons"]["artifact"]["source"])
            # Resolved to an artifact + submodule declaration -> artifact usable, but the submodule alternative is noted
            self.assertEqual(link["xxhash"]["kind"], "package")
            self.assertTrue(link["xxhash"]["artifact"]["ready"])
            self.assertIn("submodule", link["xxhash"]["ohos_note"])
            conn.close()

    # ---- 6f) CPMAddPackage(NAME <name> ...) name extraction (confirmed with gen_i:
    #          the literal NAME was once taken as a package name, putting a junk entry
    #          "NAME" in the vendored section; the real names ads/QSimpleUpdater should be extracted)
    def test_cpm_name_keyword(self):
        from port_graph.qt_scanner import _detect_fetched_deps
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "thirdparty").mkdir()
            (root / "thirdparty" / "CMakeLists.txt").write_text(
                "CPMAddPackage(\n"
                "    NAME ads\n"
                "    GITHUB_REPOSITORY githubuser0xFFFF/Qt-Advanced-Docking-System\n"
                "    GIT_TAG 5.0.0)\n"
                "CPMAddPackage(\n"
                "    NAME QSimpleUpdater\n"
                "    GITHUB_REPOSITORY alex-spataru/QSimpleUpdater\n"
                "    GIT_TAG c5c136c)\n"
                "FetchContent_Declare(foo GIT_REPOSITORY https://x/foo.git)\n",
                encoding="utf-8")
            out = _detect_fetched_deps(root, ["thirdparty/CMakeLists.txt"])
            names = {d["name"] for d in out}
            self.assertIn("ads", names)
            self.assertIn("QSimpleUpdater", names)
            self.assertIn("foo", names)
            self.assertNotIn("NAME", names)

    # ---- 6g) packages pulled by CPM/FetchContent: link name hits (including loose folding,
    #          qtadvanceddocking-qt6 == last URL segment of ads) -> in-tree,
    #          no more false need_port (confirmed with gen_i)
    def test_fetched_dep_link_classification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "p"
            root.mkdir()
            (root / "thirdparty").mkdir()
            (root / "thirdparty" / "CMakeLists.txt").write_text(
                "CPMAddPackage(\n"
                "    NAME ads\n"
                "    GITHUB_REPOSITORY githubuser0xFFFF/Qt-Advanced-Docking-System\n"
                "    GIT_TAG 5.0.0)\n"
                "CPMAddPackage(\n"
                "    NAME editorconfig_core_qt\n"
                "    GITHUB_REPOSITORY editorconfig/editorconfig-core-qt\n"
                "    GIT_TAG ab62f05)\n", encoding="utf-8")
            (root / "CMakeLists.txt").write_text(
                "add_executable(app main.cpp)\n"
                "target_link_libraries(app PRIVATE\n"
                "  qtadvanceddocking-qt6\n"
                "  editorconfig-core-qt)\n", encoding="utf-8")
            (root / "main.cpp").write_text("int main(){}\n", encoding="utf-8")
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            report = deps_report.analyze_dependencies(conn, root)
            link = {d["name"].lower(): d for d in report["link_deps"]}
            for nm in ("qtadvanceddocking-qt6", "editorconfig-core-qt"):
                self.assertEqual(link[nm]["kind"], "in-tree", nm)
                self.assertTrue(link[nm]["artifact"]["ready"], nm)
            conn.close()

    # ---- 6h) find_package(<own project name>) self-reference (confirmed with gen_j: was once wrongly
    #          resolved to an unrelated same-named package cmdpkgs:gen_j): the root project() name is skipped;
    #          project(fakevim) in a vendored subdirectory does not affect the host's declarations
    def test_find_package_self_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "p"
            root.mkdir()
            (root / "CMakeLists.txt").write_text(
                "project(gen_j)\n"
                "find_package(gen_j REQUIRED)\n"
                "find_package(OpenSSL REQUIRED)\n", encoding="utf-8")
            lib = root / "src" / "libraries" / "fakevim"
            lib.mkdir(parents=True)
            (lib / "CMakeLists.txt").write_text(
                "project(fakevim)\nadd_library(fakevim f.cpp)\n",
                encoding="utf-8")
            (root / "src" / "CMakeLists.txt").write_text(
                "find_package(fakevim REQUIRED)\n", encoding="utf-8")
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            report = deps_report.analyze_dependencies(conn, root)
            names = {d["name"].lower() for d in report["link_deps"]}
            self.assertNotIn("gen_j", names)     # self-reference not included
            self.assertIn("openssl", names)         # normal external package kept
            conn.close()

    # ---- 6i) meson internal dependencies and subprojects (confirmed with gen_j/rizin):
    #          targets defined by override_dependency (rz_core) and
    #          bundled subprojects under subprojects/ (zydis) -> in-tree;
    #          external dependencies (pcre2) stay as package
    def test_meson_internal_dep_classification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "p"
            librz = root / "librz" / "core"
            librz.mkdir(parents=True)
            (librz / "meson.build").write_text(
                "rz_core_dep = declare_dependency(...\n"
                "meson.override_dependency('rz_core', rz_core_dep)\n",
                encoding="utf-8")
            sp = root / "subprojects" / "zydis"
            sp.mkdir(parents=True)
            (sp / "meson.build").write_text(
                "project('zydis')\n", encoding="utf-8")
            (root / "meson.build").write_text(
                "project('rizin', 'cpp')\n"
                "rz_core_dep = dependency('rz_core')\n"
                "zydis_dep = dependency('zydis')\n"
                "pcre2_dep = dependency('libpcre2-@0@')\n",
                encoding="utf-8")
            from port_graph import qt_scanner
            info = qt_scanner.scan_project(root)
            md = {d["name"]: d for d in info["meson_deps"]}
            self.assertTrue(md["rz_core"].get("internal"))
            self.assertTrue(md["zydis"].get("internal"))
            self.assertIn("libpcre2", md)      # @0@ placeholder stripped
            self.assertNotIn("libpcre2-@0@", md)
            self.assertFalse(md["libpcre2"].get("internal"))
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            report = deps_report.analyze_dependencies(conn, root, info)
            link = {d["name"].lower(): d for d in report["link_deps"]}
            self.assertEqual(link["rz_core"]["kind"], "in-tree")
            self.assertEqual(link["zydis"]["kind"], "in-tree")
            conn.close()

    # ---- 7) bare link name hitting a test framework -> test role
    def test_raw_lib_test_framework(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "p"
            root.mkdir()
            (root / "CMakeLists.txt").write_text("""
add_executable(app main.cpp)
target_link_libraries(app PRIVATE gtest_main libgit2)
""", encoding="utf-8")
            (root / "main.cpp").write_text("", encoding="utf-8")
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            report = deps_report.analyze_dependencies(conn, root)
            tests = {t["name"] for t in report["test_deps"]}
            links = {d["name"] for d in report["link_deps"]}
            self.assertIn("gtest_main", tests)
            self.assertNotIn("gtest_main", links)
            self.assertIn("libgit2", links)
            conn.close()

    # ---- 8) compiler runtime libraries -> system-lib (atomic/gcov)
    def test_compiler_runtime_system_lib(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "p"
            root.mkdir()
            (root / "CMakeLists.txt").write_text("""
add_executable(app main.cpp)
target_link_libraries(app PRIVATE atomic)
""", encoding="utf-8")
            (root / "app.pro").write_text("LIBS += -lgcov\n",
                                          encoding="utf-8")
            (root / "main.cpp").write_text("", encoding="utf-8")
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            report = deps_report.analyze_dependencies(conn, root)
            link = {d["name"].lower(): d for d in report["link_deps"]}
            self.assertEqual(link["atomic"]["kind"], "system-lib")
            self.assertEqual(link["gcov"]["kind"], "system-lib")
            # System libraries produce no need_port warning
            warn = [w for w in report["warnings"]
                    if "atomic" in w["msg"] or "gcov" in w["msg"]]
            self.assertEqual(warn, [])
            conn.close()

    # ---- 9) find_package names merged via alias (KDcrawQt6/kdcraw unified)
    def test_find_package_alias_rename(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "p"
            root.mkdir()
            (root / "CMakeLists.txt").write_text(
                "find_package(KDcrawQt6 REQUIRED)\n"
                "pkg_check_modules(KD REQUIRED kdcraw)\n",
                encoding="utf-8")
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            report = deps_report.analyze_dependencies(conn, root)
            names = [d["name"] for d in report["link_deps"]]
            self.assertEqual(names.count("kdcraw"), 1)
            self.assertNotIn("KDcrawQt6", names)
            conn.close()


class TestCLICompact(unittest.TestCase):
    """Trailing --compact: `portgraph.py <cmd> --compact` should work the same as the leading form."""

    def test_compact_after_subcommand(self):
        import subprocess
        r = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "portgraph.py"),
             "stats", "--compact"],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.strip())


# ------------------------------------------------- e2e corpus_d post-mortem fixes

class TestCmakeOptionGuard(unittest.TestCase):
    """find_package/pkg_check_modules inside CMake option guards that default to OFF are marked optional.

    Evidence sample: if (SYSTEMD) in corpus_d dist/unix/CMakeLists.txt
    (SYSTEMD is declared via feature_option_dependent and defaults to OFF). Also covers
    the dist/ directory no longer being excluded (add_subdirectory(dist) is a real build subdirectory).
    """

    ROOT_CMAKE = """cmake_minimum_required(VERSION 3.16)
project(GuardProj)
feature_option(GUI "Build GUI" ON)
feature_option_dependent(SYSTEMD "Install systemd unit" OFF "NOT GUI" OFF)
option(WEBUI "Enable WebUI" ON)
option(STACKTRACE "Stacktrace" OFF)
if (CMAKE_SYSTEM_NAME STREQUAL "Linux")
    feature_option_dependent(DBUS "D-Bus" ON "GUI" OFF)
endif()
"""

    DIST_CMAKE = """if (SYSTEMD)
    if (NOT SYSTEMD_DIR)
        find_package(Systemd)
    endif()
endif()
if (DBUS)
    find_package(Qt6 6.6 REQUIRED COMPONENTS DBus)
endif()
if (STACKTRACE)
    find_package(LibunwindStacktrace QUIET)
endif()
find_package(Boost 1.76 REQUIRED)
"""

    FIND_MODULE_CMAKE = """
find_package(PkgConfig QUIET)
if (NOT GUARDPROJ_FOUND)
    pkg_check_modules(GUARDPROJ "systemd")
endif()
"""

    MACRO_CMAKE = """
macro(find_lib version)
    find_package(LibtorrentRasterbar QUIET ${version})
endmacro()
find_lib(2.0)
"""

    def _project(self, tmp: Path):
        root = tmp / "guardproj"
        (root / "dist" / "unix").mkdir(parents=True)
        (root / "cmake" / "Modules").mkdir(parents=True)
        (root / "CMakeLists.txt").write_text(self.ROOT_CMAKE,
                                              encoding="utf-8")
        # CMakeLists inside dist/ must no longer be excluded
        (root / "dist" / "unix" / "CMakeLists.txt").write_text(
            self.DIST_CMAKE, encoding="utf-8")
        # Find module file: find_package(Systemd) optional -> the whole module inherits it
        (root / "cmake" / "Modules" / "FindSystemd.cmake").write_text(
            self.FIND_MODULE_CMAKE, encoding="utf-8")
        # Declarations inside a macro body: take effect at the call site, not marked optional
        (root / "cmake" / "Modules" / "CheckPackages.cmake").write_text(
            self.MACRO_CMAKE, encoding="utf-8")
        return root

    def _packages(self, tmp: Path):
        root = self._project(tmp)
        info = qt_scanner.scan_project(root)
        return info["cmake_packages"], info

    def test_optional_flagging(self):
        with tempfile.TemporaryDirectory() as tmp:
            cp, info = self._packages(Path(tmp))
            # SYSTEMD defaults to OFF -> find_package(Systemd) optional
            self.assertIn("systemd", cp["find_package_optional"])
            self.assertNotIn("systemd", cp["find_package"])
            # Find<systemd>.cmake module inherits optional (pkg_check_modules)
            self.assertIn("systemd", cp["pkg_check_modules_optional"])
            self.assertNotIn("systemd", cp["pkg_check_modules"])
            # pkg_modules entries carry the optional flag
            pm = {d["name"]: d for d in cp["pkg_modules"]}
            self.assertTrue(pm["systemd"].get("optional"))
            # Options defaulting to ON (DBUS/WEBUI) and unconditional declarations -> required
            self.assertIn("boost", cp["find_package"])
            self.assertNotIn("boost", cp["find_package_optional"])
            self.assertNotIn("dbus", cp["find_package"])
            # STACKTRACE defaults to OFF -> optional
            self.assertIn("libunwindstacktrace",
                          cp["find_package_optional"])
            # Declarations inside a macro body are not marked optional (call-site context unknown)
            self.assertIn("libtorrentrasterbar", cp["find_package"])
            self.assertNotIn("libtorrentrasterbar",
                             cp["find_package_optional"])

    def test_find_package_details_optional(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            info = qt_scanner.scan_project(root)
            details = {(d["name"], d["file"].endswith("unix/CMakeLists.txt"))
                       : d for d in info["find_package_details"]}
            systemd = next(d for (n, _), d in details.items()
                           if n == "Systemd")
            self.assertTrue(systemd.get("optional"))
            boost = next(d for (n, _), d in details.items()
                         if n == "Boost")
            self.assertFalse(boost.get("optional", False))


class TestOptionalEdgeExcludedFromClosure(unittest.TestCase):
    """optional edges do not enter the runtime closure or portability analysis (fix for the e2e systemd false positive)."""

    def test_optional_edge_semantics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "optproj"
            root.mkdir()
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.16)\n"
                "project(OptProj)\n"
                'option(SYSTEMD "Install unit" OFF)\n'
                "if (SYSTEMD)\n"
                "    find_package(Systemd)\n"
                "endif()\n"
                "find_package(ZLIB 1.2 REQUIRED)\n",
                encoding="utf-8")
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            db.upsert_node(conn, "hb:zlib", "package", "zlib",
                           "harmonybrew", "ported", version="1.3.1")
            scan = project_scanner.scan_project(conn, root)
            edges = {e["type"]: e["dst"]
                     for e in db.out_edges(conn, scan["app_id"])}
            self.assertEqual(edges.get("optional"),
                             "pkg-unknown:systemd")
            self.assertEqual(edges.get("runtime"), "hb:zlib")
            # Portability analysis does not recurse along optional edges (no unknown produced)
            analysis = engine.analyze(conn, scan["app_id"])
            self.assertEqual(
                [u["node"] for u in analysis["unknowns"]], [])
            # The fetch-deps closure does not include optional dependencies
            closure = deps_fetch.dependency_closure(conn, scan["app_id"])
            ids = [n["id"] for n in closure]
            self.assertNotIn("pkg-unknown:systemd", ids)
            self.assertIn("hb:zlib", ids)
            # The scan summary distinguishes optional / unknown
            self.assertEqual(scan["deps_unknown"], [])
            self.assertEqual([d["hint"] for d in scan["deps_optional"]],
                             ["systemd"])
            conn.close()


class TestDashlessSameLibMerge(unittest.TestCase):
    """Merging the same library under different names: the flattened CamelCase find_package name and the hyphenated pkg-config name
    do not create duplicate ghost nodes; when the package DB has the matching package, fallback resolution works (fix for the e2e libtorrentrasterbar
    ghost node)."""

    CMAKE = """cmake_minimum_required(VERSION 3.16)
project(DashlessProj)
find_package(LibtorrentRasterbar 2.0 REQUIRED)
pkg_check_modules(LT IMPORTED_TARGET "libtorrent-rasterbar>=2.0.10")
find_package(Boost REQUIRED)
"""

    def _project(self, tmp: Path):
        root = tmp / "dashless"
        root.mkdir()
        (root / "CMakeLists.txt").write_text(self.CMAKE, encoding="utf-8")
        return root

    def test_ghost_merge_when_unresolvable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            scan = project_scanner.scan_project(conn, root)
            # Only one libtorrent ghost node is produced (boost has no package source and counts separately),
            # with the hyphenated pkg-config form as the representative name
            self.assertEqual(
                [d["node"] for d in scan["deps_unknown"]
                if "torrent" in d["node"]],
                ["pkg-unknown:libtorrent-rasterbar"])
            lt = next(d for d in scan["deps_unknown"]
                      if d["node"] == "pkg-unknown:libtorrent-rasterbar")
            self.assertEqual(lt["merged_from"], ["libtorrentrasterbar"])
            edges = [e for e in db.out_edges(conn, scan["app_id"])
                     if e["dst"].startswith("pkg-unknown:")]
            self.assertEqual(len(edges), 2)   # boost + the merged libtorrent
            conn.close()

    def test_dashless_resolve_when_package_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            db.upsert_node(conn, "hb:libtorrent-rasterbar", "package",
                           "libtorrent-rasterbar", "harmonybrew",
                           "ported", version="2.0.10")
            scan = project_scanner.scan_project(conn, root)
            # The flattened name falls back to the hyphenated package name -> no libtorrent ghost node
            self.assertEqual(
                [d for d in scan["deps_unknown"]
                 if "torrent" in d["node"]], [])
            linked = {d["hint"]: d for d in scan["deps_linked"]}
            self.assertEqual(linked["libtorrent-rasterbar"]["node"],
                             "hb:libtorrent-rasterbar")
            conn.close()

    def test_dashless_alias_for_collapsed_only_name(self):
        """With only the flattened find_package name, fallback resolves to the hyphenated package name and annotates alias."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "dashless2"
            root.mkdir()
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.16)\n"
                "project(Dashless2)\n"
                "find_package(LibtorrentRasterbar 2.0 REQUIRED)\n",
                encoding="utf-8")
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            db.upsert_node(conn, "hb:libtorrent-rasterbar", "package",
                           "libtorrent-rasterbar", "harmonybrew",
                           "ported", version="2.0.10")
            scan = project_scanner.scan_project(conn, root)
            self.assertEqual(scan["deps_unknown"], [])
            self.assertEqual(
                [(d["hint"], d["node"], d.get("alias"))
                 for d in scan["deps_linked"]],
                [("libtorrentrasterbar", "hb:libtorrent-rasterbar",
                  "dashless")])
            conn.close()

    def test_dashless_resolve_no_short_name_collision(self):
        """Short names (< 6 characters) skip fallback matching to avoid collisions and false mappings."""
        node = kb_seed.resolve_package_dashless(None, "zlib")
        self.assertIsNone(node)

    def test_dashless_index_excludes_ghost_nodes(self):
        """pkg-unknown ghost nodes are not indexed: otherwise ghosts from a previous scan
        would be resolved as known packages by the next scan (reproduced after the deps CLI wrote to the main DB)."""
        conn = db.connect(":memory:")
        db.init_db(conn)
        db.upsert_node(conn, "pkg-unknown:libtorrent-rasterbar", "package",
                       "libtorrent-rasterbar", "scan", "unknown")
        node = kb_seed.resolve_package_dashless(conn, "libtorrentrasterbar")
        self.assertIsNone(node)
        conn.close()


class TestE2ENameVariants(unittest.TestCase):
    """e2e harness evidence variants: node names containing @version (openssl@3) need an extra stripped
    variant, otherwise grep cannot find the original find_package(OpenSSL) declaration (false-positive verdict)."""

    def _load_e2e(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "run_e2e", PROJECT_ROOT / "tests" / "e2e" / "run_e2e.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_at_version_stripped(self):
        e2e = self._load_e2e()
        node = {"name": "openssl@3", "id": "hb:openssl@3"}
        variants = e2e.name_variants(None, node)
        self.assertIn("openssl@3", variants)
        self.assertIn("openssl", variants)
        # The oracle side is unchanged: only the node side gets the stripped variant
        self.assertIn("openssl", e2e.name_variants("OpenSSL >= 3.0"))




# =====================================================================
# Added in the e2e corpus_a (tier C) deps-test round: external_* imported target link resolution,
# build tool filtering, vendored submodule suppression, win32 system library false-link prevention, harness evidence
# =====================================================================

def _load_e2e_harness():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "run_e2e", PROJECT_ROOT / "tests" / "e2e" / "run_e2e.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestExternalTargetLinks(unittest.TestCase):
    """Resolution of ns::external_<name> imported targets in target_link_libraries
    (all of corpus_a's third-party libraries take this path; find_package lives in cmake_helpers)."""

    CMAKE = """
cmake_minimum_required(VERSION 3.16)
project(Ext)
add_library(app STATIC src/main.cpp)
add_library(external_foo STATIC src/foo.cpp)
target_link_libraries(app PRIVATE
  desktop-app::external_zlib
  desktop-app::external_openal
  desktop-app::external_webrtc
  desktop-app::lib_base
  desktop-app::external_qt_static_plugins
  Qt5::Core
  PkgConfig::CORPUS_A_UDEV
  external_foo
  z
)
"""

    def _project(self, tmp: Path):
        root = tmp / "extproj"
        (root / "src").mkdir(parents=True)
        (root / "CMakeLists.txt").write_text(self.CMAKE, encoding="utf-8")
        return root

    def test_external_targets_extracted(self):
        with tempfile.TemporaryDirectory() as tmp:
            info = qt_scanner.scan_project(self._project(Path(tmp)))
            raw = {e["name"].lower(): e for e in info["raw_libs"]}
            # external_ prefix stripped + high-confidence ext_target marker
            for n in ("zlib", "openal", "webrtc"):
                self.assertIn(n, raw, "missing %s" % n)
                self.assertTrue(raw[n].get("ext_target"))
                self.assertIn("external-target",
                              " ".join(raw[n]["hows"]))
            # Non-external_ namespaced targets / Qt / PkgConfig / in-project targets skipped
            for n in ("lib_base", "qt5::core", "qt_static_plugins",
                      "external_foo", "foo", "pkgconfig"):
                self.assertNotIn(n, raw)
            # Bare names still take the original path
            self.assertIn("z", raw)
            self.assertFalse(raw["z"].get("ext_target"))

    def test_graph_links_and_ghosts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            # vendored submodule: external_cmark_gfm corresponds to a .gitmodules entry
            (root / ".gitmodules").write_text(
                '[submodule "ThirdParty/cmark-gfm"]\n'
                "\tpath = corpus_a/ThirdParty/cmark-gfm\n"
                "\turl = https://github.com/github/cmark-gfm.git\n",
                encoding="utf-8")
            (root / "CMakeLists.txt").write_text(
                self.CMAKE.replace(
                    "desktop-app::external_webrtc",
                    "desktop-app::external_webrtc\n"
                    "  desktop-app::external_cmark_gfm"),
                encoding="utf-8")
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            db.upsert_node(conn, "hb:zlib", "package", "zlib", "harmonybrew",
                           "ported")
            db.upsert_node(conn, "cmdpkgs:openal-soft", "package",
                           "openal-soft", "cmdpkgs", "ported")
            db.upsert_node(conn, "cmdpkgs:bcrypt", "package", "bcrypt",
                           "cmdpkgs", "ported")
            scan = project_scanner.scan_project(conn, root)
            linked = {d["hint"]: d for d in scan["deps_linked"]}
            # Known package gets an edge (openal via PKG_ALIASES -> openal-soft)
            self.assertEqual(linked["zlib"]["node"], "hb:zlib")
            self.assertEqual(linked["openal"]["node"], "cmdpkgs:openal-soft")
            self.assertEqual(linked["openal"]["alias"], "openal-soft")
            self.assertEqual(linked["openal"]["via"], "external-target")
            unknown = {d["hint"] for d in scan["deps_unknown"]}
            # Unresolved external_ declaration -> ghost node (high confidence)
            self.assertIn("webrtc", unknown)
            # vendored submodule hit -> no ghost (built with the project)
            self.assertNotIn("cmark_gfm", unknown)


class TestBuildToolFindpkgFilter(unittest.TestCase):
    """Build tools such as find_package(Python3) get no runtime edge (this previously created
    a pkg-unknown:python3 ghost and the e2e reported a false resolution-gap)."""

    def test_python3_not_runtime_edge(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "codegen"
            root.mkdir()
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.16)\nproject(Gen)\n"
                "find_package(Python3 REQUIRED)\n"
                "pkg_check_modules(UDEV REQUIRED IMPORTED_TARGET libudev)\n"
                # Fully portable third-party library: a control for "real runtime dependencies still get ghosts"
                "pkg_check_modules(CURL REQUIRED IMPORTED_TARGET libcurl)\n",
                encoding="utf-8")
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            scan = project_scanner.scan_project(conn, root)
            hints = {d["hint"] for d in scan["deps_unknown"]}
            self.assertNotIn("python3", hints)
            edges = {e["dst"] for e in db.out_edges(conn, scan["app_id"])}
            self.assertNotIn("pkg-unknown:python3", edges)
            # udev is a platform interface (systemd family, HarmonyOS has no udev) -> no ghost;
            # the name matches hb, but "has a bottle" does not mean "should be ported"
            self.assertNotIn("libudev", hints)
            self.assertNotIn("pkg-unknown:libudev", edges)
            # Real runtime dependencies (pkg-config names) still get ghosts
            self.assertIn("libcurl", hints)
            self.assertIn("pkg-unknown:libcurl", edges)
            conn.close()


class TestWin32LibNoFalseEdge(unittest.TestCase):
    """win32 system library names (bcrypt/hid/...) are not falsely linked to same-named Unix libraries."""

    def test_bcrypt_win32_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "w32"
            root.mkdir()
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.16)\nproject(W32)\n"
                "add_library(f2 STATIC f2.c)\n"
                "target_link_libraries(f2 PRIVATE bcrypt hid ws2_32)\n",
                encoding="utf-8")
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            db.upsert_node(conn, "cmdpkgs:bcrypt", "package", "bcrypt",
                           "cmdpkgs", "ported")
            scan = project_scanner.scan_project(conn, root)
            hints = [d["hint"] for d in scan["deps_linked"]] + \
                [d["hint"] for d in scan["deps_unknown"]]
            self.assertNotIn("bcrypt", hints)
            self.assertNotIn("hid", hints)
            conn.close()


class Testcorpus_bRegressTables(unittest.TestCase):
    """Table gaps exposed by the corpus_b regression round (2026-09 worker2-deps-regress):
    gmock test framework / 4 win32 system library gaps / bare macOS framework names in find_library
    (before the fix all were reported as ordinary packages: "no HarmonyOS prebuilt artifact, needs source cross-compilation")."""

    CMAKE = """
cmake_minimum_required(VERSION 3.16)
project(RegressTables)
add_library(drv STATIC src/x.cpp)
if (OS_IS_WIN)
    target_link_libraries(drv PRIVATE winmm mmdevapi msi taskschd userenv)
endif()
if (OS_IS_MAC)
    find_library(AUDIOTOOLBOX_LIB AudioToolbox)
    find_library(CARBON_LIB Carbon)
    find_library(COREMIDI_LIB CoreMIDI)
    target_link_libraries(drv PRIVATE ${AUDIOTOOLBOX_LIB} ${CARBON_LIB})
endif()
add_executable(t1 src/t1.cpp)
target_link_libraries(t1 PRIVATE drv gmock)
"""

    def test_table_classifications(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "rt"
            (root / "src").mkdir(parents=True)
            (root / "CMakeLists.txt").write_text(self.CMAKE,
                                                 encoding="utf-8")
            (root / "src" / "x.cpp").write_text("", encoding="utf-8")
            (root / "src" / "t1.cpp").write_text("", encoding="utf-8")
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            report = deps_report.analyze_dependencies(conn, root)
            link = {d["name"].lower(): d for d in report["link_deps"]}
            # gmock -> test classification, not in link and no "needs source cross-compilation" report
            self.assertNotIn("gmock", link)
            self.assertIn("gmock", {t["name"] for t in report["test_deps"]})
            # win32 system libraries -> win32-system-lib
            for n in ("mmdevapi", "msi", "taskschd", "userenv"):
                self.assertEqual(link[n]["kind"], "win32-system-lib", n)
            # Bare macOS framework name in find_library -> platform-iface + ohos_note
            for n in ("audiotoolbox", "carbon", "coremidi"):
                self.assertEqual(link[n]["kind"], "platform-iface", n)
                self.assertTrue(link[n].get("ohos_note"), n)
            # The misleading "needs source cross-compilation" warning no longer appears
            for w in report["warnings"]:
                self.assertNotIn("needs source cross-compilation",
                                 "{} {}".format(w.get("msg", ""), w))
            # Graph side: bare win32 names create no ghosts / false edges
            scan = project_scanner.scan_project(conn, root)
            hints = [d["hint"] for d in scan["deps_linked"]] + \
                [d["hint"] for d in scan["deps_unknown"]]
            for n in ("mmdevapi", "msi", "taskschd", "userenv"):
                self.assertNotIn(n, hints)
            conn.close()


class TestPkgAliasescorpus_a(unittest.TestCase):
    """Alias gaps confirmed by the e2e corpus_a review (bare external_* names -> HarmonyOS packages)."""

    def test_aliases_resolve(self):
        conn = db.connect(":memory:")
        db.init_db(conn)
        kb_seed.seed_interfaces(conn)
        db.upsert_node(conn, "cmdpkgs:openal-soft", "package", "openal-soft",
                       "cmdpkgs", "ported")
        db.upsert_node(conn, "hb:libiconv", "package", "libiconv",
                       "harmonybrew", "ported")
        db.upsert_node(conn, "hb:boost", "package", "boost", "harmonybrew",
                       "ported")
        db.upsert_node(conn, "hb:cmark-gfm", "package", "cmark-gfm",
                       "harmonybrew", "ported")
        db.upsert_node(conn, "cmdpkgs:libqrcodegen", "package", "libqrcodegen",
                       "cmdpkgs", "ported")
        for name, want in (("openal", "cmdpkgs:openal-soft"),
                           ("iconv", "hb:libiconv"),
                           ("boost_regex", "hb:boost"),
                           ("cmark_gfm", "hb:cmark-gfm"),
                           ("qr_code_generator", "cmdpkgs:libqrcodegen")):
            alias = kb_seed.PKG_ALIASES[name]
            node = kb_seed.resolve_package(conn, alias)
            self.assertIsNotNone(node, "%s not resolved" % name)
            self.assertEqual(node["id"], want)
        conn.close()


class TestE2eHarnessDepsTest(unittest.TestCase):
    """harness (run_e2e) evidence and classification fixes:
    word-boundary lookarounds, separator folding, ghost verdict (resolution-gap vs unknown-ok),
    vendored submodule classification."""

    @classmethod
    def setUpClass(cls):
        cls.h = _load_e2e_harness()

    def test_grep_boundary_matches_prefixed_target(self):
        # \b word boundaries cannot match external_xxhash / lib_zlib; lookaround boundaries can
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "CMakeLists.txt").write_text(
                "target_link_libraries(corpus_a PRIVATE "
                "desktop-app::external_xxhash lib_zlib)\n",
                encoding="utf-8")
            ev = self.h.grep_dep_refs(repo, self.h.name_variants("xxHash"))
            self.assertGreaterEqual(ev["strong"], 1)
            ev2 = self.h.grep_dep_refs(repo, ["zlib"])
            self.assertGreaterEqual(ev2["strong"], 1)
            # Word-boundary protection must not misfire: zlib must not hit concatenations like zlibng
            (repo / "CMakeLists.txt").write_text(
                "target_link_libraries(x PRIVATE zlibng)\n", encoding="utf-8")
            ev3 = self.h.grep_dep_refs(repo, ["zlib"])
            self.assertEqual(ev3["strong"], 0)

    def test_grep_multiline_tll(self):
        # Each tll link item is on its own line: line-by-line matching misses evidence, so match the full text
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "CMakeLists.txt").write_text(
                "target_link_libraries(corpus_a\nPRIVATE\n"
                "    desktop-app::external_boost_regex\n"
                "    desktop-app::external_minizip\n)\n",
                encoding="utf-8")
            ev = self.h.grep_dep_refs(repo, ["boost"])
            self.assertGreaterEqual(ev["strong"], 1)
            self.assertEqual(ev["hits"][0]["line"], 3)

    def test_names_match_underscore_folding(self):
        node = {"kind": "package", "name": "crash_reports", "id":
                "pkg-unknown:crash-reports"}
        self.assertTrue(self.h.names_match("Crash reports", "crash_reports",
                                           node))

    def test_ghost_plausible_package(self):
        conn = db.connect(":memory:")
        db.init_db(conn)
        db.upsert_node(conn, "hb:openal-soft", "package", "openal-soft",
                       "harmonybrew", "ported")
        db.upsert_node(conn, "hb:uudeview", "package", "uudeview",
                       "harmonybrew", "ported")
        db.upsert_node(conn, "hb:libxkbcommon", "package", "libxkbcommon",
                       "harmonybrew", "ported")
        # A similar-looking package exists (openal within openal-soft, component intersection) -> real resolution gap
        hit = self.h.ghost_plausible_package(conn, "openal")
        self.assertIsNotNone(hit)
        self.assertEqual(hit["id"], "hb:openal-soft")
        # Equal after lib prefix folding -> real resolution gap
        hit2 = self.h.ghost_plausible_package(conn, "xkbcommon")
        self.assertIsNotNone(hit2)
        # No similar-looking package (udev vs uudeview: no separator-component intersection) -> the ghost is a correct detection
        self.assertIsNone(self.h.ghost_plausible_package(conn, "libudev"))
        self.assertIsNone(self.h.ghost_plausible_package(conn, "webrtc"))
        conn.close()

    def test_vendored_submodule_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".gitmodules").write_text(
                '[submodule "ThirdParty/GSL"]\n'
                "\tpath = corpus_a/ThirdParty/GSL\n"
                "\turl = https://github.com/Microsoft/GSL.git\n"
                '[submodule "ThirdParty/xxHash"]\n'
                "\tpath = corpus_a/ThirdParty/xxHash\n"
                "\turl = https://github.com/Cyan4973/xxHash.git\n",
                encoding="utf-8")
            m1 = self.h.vendored_submodule_match(
                repo, ["Guideline Support Library", "gsl"])
            self.assertIsNotNone(m1)
            self.assertEqual(m1["url"],
                             "https://github.com/Microsoft/GSL.git")
            m2 = self.h.vendored_submodule_match(repo, ["xxHash"])
            self.assertIsNotNone(m2)
            self.assertIsNone(
                self.h.vendored_submodule_match(repo, ["OpenSSL"]))
            self.assertIsNone(
                self.h.vendored_submodule_match(repo, ["opus"]))

    def test_readme_alias_qr_code_generator(self):
        # nayuki QR-Code-generator = cmd-pkgs libqrcodegen (same version lineage, 1.8.0)
        self.assertEqual(self.h.canon_of("QR Code generator"),
                         "libqrcodegen")


class TestPkgConfigVersionSuffixResolve(unittest.TestCase):
    """pkg-config names with version suffixes (lilv-0/glib-2.0) also resolve to packages on the graph side
    (previously only deps_report._resolve supported this, and the graph side created ghost nodes;
    confirmed by the e2e corpus_b review)."""

    def test_version_suffix_stripped(self):
        conn = db.connect(":memory:")
        db.init_db(conn)
        kb_seed.seed_interfaces(conn)
        db.upsert_node(conn, "hb:lilv", "package", "lilv", "harmonybrew",
                       "ported")
        db.upsert_node(conn, "hb:glib", "package", "glib", "harmonybrew",
                       "ported")
        db.upsert_node(conn, "hb:libxkbcommon", "package", "libxkbcommon",
                       "harmonybrew", "ported")
        self.assertEqual(kb_seed.resolve_package(conn, "lilv-0")["id"],
                         "hb:lilv")
        self.assertEqual(kb_seed.resolve_package(conn, "glib-2.0")["id"],
                         "hb:glib")
        # lib-prefix approximations are also unified into resolve_package
        self.assertEqual(kb_seed.resolve_package(conn, "xkbcommon")["id"],
                         "hb:libxkbcommon")
        # No similar-looking package still returns None (keeps the ghost behavior)
        self.assertIsNone(kb_seed.resolve_package(conn, "suil-0"))
        conn.close()

class TestBuildscriptsDirNotExcluded(unittest.TestCase):
    """Fix for wrongful exclusion by the build* prefix: buildscripts/buildtools are source directories and must be scanned,
    while build output directories such as build/build-Debug are still excluded (e2e corpus_b root cause)."""

    def _project(self, tmp: Path):
        root = tmp / "bs"
        for rel in ("buildscripts/cmake/Setup.cmake", "buildtools/x.cmake",
                    "build/out.cmake", "build-Debug/out.cmake"):
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            name = rel.split("/")[-1].replace("out.cmake", "Out").replace(
                ".cmake", "").replace("Setup", "SetupDep")
            p.write_text("find_package(%s REQUIRED)\n" % name,
                         encoding="utf-8")
        (root / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.16)\nproject(BS)\n",
            encoding="utf-8")
        return root

    def test_buildscripts_scanned_build_output_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            info = qt_scanner.scan_project(root)
            fp = set(info["cmake_packages"]["find_package"])
            self.assertIn("setupdep", fp)     # buildscripts/cmake/Setup.cmake
            self.assertIn("x", fp)            # buildtools/x.cmake
            self.assertNotIn("out", fp)       # build/ and build-Debug/ excluded


class TestVendoredCmakeSkip(unittest.TestCase):
    """CMake declarations inside vendored/dependency-engine directories and comment lines do not count as application dependencies
    (e2e corpus_b: thirdparty/fluidsynth, KDDockWidgets/python,
    corpus_b_deps/recipes polluting depth-1; find_package false matches on comment lines)."""

    def _project(self, tmp: Path):
        root = tmp / "vend"
        # The embedded third-party code's own find_package (must not count)
        p = root / "framework/audio/thirdparty/fluidsynth/CMakeLists.txt"
        p.parent.mkdir(parents=True)
        p.write_text(
            "find_package(GLib2 REQUIRED)\n"
            "find_package(Lash)\n"
            "# Exported targets for cmake: find_package(FluidSynth)\n",
            encoding="utf-8")
        # System-mode fallback in the dependency-engine submodule's recipes (must not count)
        p = root / "corpus_b_deps/recipes/lv2sdk/meta.cmake"
        p.parent.mkdir(parents=True)
        p.write_text(
            "pkg_check_modules(lv2sdk_system REQUIRED IMPORTED_TARGET "
            "lilv-0 suil-0 lv2)\n", encoding="utf-8")
        # Includes inside embedded third-party code are not hint evidence either
        p = root / "thirdparty/kdw/util.h"
        p.parent.mkdir(parents=True)
        p.write_text("#include <uuid/uuid.h>\n", encoding="utf-8")
        # The application's own declarations (must count)
        (root / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.16)\nproject(Vend)\n"
            "find_package(Jack REQUIRED)\n"
            "# find_package(Commented)\n"
            "find_package(Git REQUIRED)\n",   # VCS build tool should be skipped
            encoding="utf-8")
        return root

    def test_vendored_and_comments_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            info = qt_scanner.scan_project(root)
            fp = info["cmake_packages"]["find_package"]
            self.assertEqual(fp, ["jack"])
            self.assertEqual(info["cmake_packages"]["pkg_check_modules"], [])
            hints = {h["name"] for h in info["third_party_hints"]}
            self.assertNotIn("libuuid", hints)


class TestWrapperCmakePassthrough(unittest.TestCase):
    """Wrapper declaration files under vendored paths (add_library(external_X))
    are not vendored sources: the find_package / pkg_check_modules in them are the application's
    own dependencies and should pass through (corpus_a post-mortem: after submodule init, external_X
    became an in-project target, and together with the vendored skip it hid openal/ada/rnnoise entirely)."""

    def _project(self, tmp: Path):
        root = tmp / "wrap"
        # cmake_helpers-style wrapper: defines external_openal + find_package
        p = root / "cmake/external/openal/CMakeLists.txt"
        p.parent.mkdir(parents=True)
        p.write_text(
            "add_library(external_openal INTERFACE IMPORTED GLOBAL)\n"
            "add_library(desktop-app::external_openal ALIAS external_openal)\n"
            "if (DESKTOP_APP_USE_PACKAGED)\n"
            "    find_package(OpenAL REQUIRED CONFIG)\n"
            "endif()\n",
            encoding="utf-8")
        # pkg_check_modules variant of the wrapper (rnnoise)
        p = root / "cmake/external/rnnoise/CMakeLists.txt"
        p.parent.mkdir(parents=True)
        p.write_text(
            "add_library(external_rnnoise INTERFACE IMPORTED GLOBAL)\n"
            "find_package(PkgConfig REQUIRED)\n"
            "pkg_check_modules(RNNOISE IMPORTED_TARGET rnnoise)\n",
            encoding="utf-8")
        # Counterexample 1: a real vendored source tree (no external_ target definition) -> still skipped
        p = root / "thirdparty/fluidsynth/CMakeLists.txt"
        p.parent.mkdir(parents=True)
        p.write_text(
            "find_package(GLib2 REQUIRED)\n"
            "target_link_libraries(fluidsynth PRIVATE glib-2.0)\n",
            encoding="utf-8")
        # The application's own declarations: link the wrapper target (the wrapper is defined under a vendored path;
        # external_X is not skipped because of an in-tree definition; the underlying library name passes through)
        (root / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.16)\nproject(Wrap)\n"
            "add_subdirectory(cmake/external/openal)\n"
            "target_link_libraries(app PRIVATE desktop-app::external_openal)\n",
            encoding="utf-8")
        return root

    def test_wrapper_findpkg_and_pkgconf_passthrough(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            info = qt_scanner.scan_project(root)
            fp = info["cmake_packages"]["find_package"]
            # The wrapper's find_package passes through; PkgConfig itself is a host tool and is skipped
            self.assertIn("openal", fp)
            self.assertNotIn("pkgconfig", fp)
            # The real vendored source tree is still skipped
            self.assertNotIn("glib2", fp)
            # The wrapper's pkg_check_modules passes through
            pm = info["cmake_packages"]["pkg_check_modules"]
            self.assertIn("rnnoise", pm)
            self.assertNotIn("lilv-0", pm)
            # When an external_X target defined by a wrapper is linked, it is not skipped because of an in-tree definition:
            # the underlying library name passes through via external-target evidence (root cause from the ada/zlib/openal post-mortem)
            raw = {x["name"]: x for x in info["raw_libs"]}
            self.assertIn("openal", raw)
            self.assertTrue(any("external-target" in h
                                for h in raw["openal"]["hows"]))
            # Counterexample: targets defined inside a real vendored source tree (not an external_ wrapper)
            # are still in-project targets and do not enter raw_libs
            self.assertNotIn("fluidsynth", raw)


class TestDynamicLoadPlatformGuard(unittest.TestCase):
    """QLibrary/dlopen loads inside non-HarmonyOS platform guards (#if defined(Q_OS_WIN))
    are not compiled and not counted in dynamic_loads (gen_h post-mortem: kernel32 false positive)."""

    def test_win_guarded_qlibrary_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "app"
            (root / "src").mkdir(parents=True)
            (root / "src" / "main.cpp").write_text(
                "#if defined(Q_OS_WIN)\n"
                "    QLibrary lib(\"kernel32\");\n"
                "#endif\n"
                "void init() { QLibrary l(\" genuine_plugin \"); }\n",
                encoding="utf-8")
            info = qt_scanner.scan_project(root)
            names = [d["name"] for d in info["dynamic_loads"]]
            self.assertNotIn("kernel32", names)
            self.assertIn("genuine_plugin", names)

    def test_unconditional_load_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "app"
            (root / "src").mkdir(parents=True)
            (root / "src" / "main.cpp").write_text(
                "void init() { QLibrary l(\"plainlib\"); }\n",
                encoding="utf-8")
            info = qt_scanner.scan_project(root)
            self.assertEqual([d["name"] for d in info["dynamic_loads"]],
                             ["plainlib"])


class TestRequireDepManifest(unittest.TestCase):
    """Dependency manifest function detection (corpus_b_deps engine): require_dep/require_source_dep/
    require_tool -> three roles link/vendored/tool; conditional block annotation."""

    ENGINE = """
function(require_dep name)
  # resolve prebuilt / system / source
endfunction()
function(require_source_dep name)
endfunction()
function(require_tool name)
endfunction()
"""
    MANIFEST = """
require_dep(zlib)
require_dep(freetype STATIC)
require_source_dep(kddockwidgets)
require_tool(crashpad_handler)
if (CB_MODULE_AUDIO_PIPEWIRE)
    require_dep(pipewire)
endif()
"""

    def _project(self, tmp: Path):
        root = tmp / "mdep"
        # The engine is defined in the dependency submodule (vendored path): the definitions are usable, but calls inside it are not scanned
        p = root / "corpus_b_deps/buildtools/manifest.cmake"
        p.parent.mkdir(parents=True)
        p.write_text(self.ENGINE +
                     "require_dep(internal_only_in_engine)\n",
                     encoding="utf-8")
        p = root / "buildscripts/cmake/ExtDepsManifest.cmake"
        p.parent.mkdir(parents=True)
        p.write_text(self.MANIFEST, encoding="utf-8")
        (root / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.16)\nproject(MDep)\n",
            encoding="utf-8")
        return root

    def test_manifest_deps_extracted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            info = qt_scanner.scan_project(root)
            md = {d["name"]: d for d in info["manifest_deps"]}
            self.assertEqual(md["zlib"]["mode"], "link")
            self.assertFalse(md["zlib"]["conditional"])
            self.assertEqual(md["freetype"]["mode"], "link")
            self.assertEqual(md["kddockwidgets"]["mode"], "source")
            self.assertEqual(md["crashpad_handler"]["mode"], "tool")
            # Conditional block annotation: not evaluated, only annotated
            self.assertTrue(md["pipewire"]["conditional"])
            self.assertIn("CB_MODULE_AUDIO_PIPEWIRE",
                          md["pipewire"]["condition"])
            # Mode arguments such as STATIC are not dependency names; calls inside the engine are not scanned
            self.assertNotIn("static", md)
            self.assertNotIn("internal_only_in_engine", md)

    def test_manifest_graph_edges(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            db.upsert_node(conn, "hb:zlib", "package", "zlib",
                           "harmonybrew", "ported")
            scan = project_scanner.scan_project(conn, root)
            edges = {e["dst"]: e["type"]
                     for e in db.out_edges(conn, scan["app_id"])}
            # require_dep -> runtime edge (resolved package)
            self.assertEqual(edges.get("hb:zlib"), "runtime")
            # require_source_dep -> vendored edge (ghost node + vendored description)
            self.assertEqual(edges.get("pkg-unknown:kddockwidgets"),
                             "vendored")
            # require_tool gets no edge
            self.assertNotIn("pkg-unknown:crashpad-handler", edges)
            self.assertEqual([v["hint"] for v in scan["deps_vendored"]],
                             ["kddockwidgets"])
            conn.close()

    def test_manifest_report_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            report = deps_report.analyze_dependencies(None, root)
            link = {d["name"] for d in report["link_deps"]}
            self.assertIn("zlib", link)
            self.assertIn("freetype", link)
            vend = {v["name"] for v in report["vendored"]}
            self.assertIn("kddockwidgets", vend)
            tools = {t["tool"] for t in report["toolchain"]["tools"]}
            self.assertIn("crashpad_handler", tools)
            # Declarations in conditional blocks have required=False
            by_name = {d["name"]: d for d in report["link_deps"]}
            self.assertFalse(by_name["pipewire"]["required"])


class TestFetchVendoredRole(unittest.TestCase):
    """fetch-deps: vendored edges (require_source_dep) -> status/role=vendored,
    not downloaded, and their transitive dependencies are not descended into."""

    def test_vendored_not_need_port(self):
        conn = db.connect(":memory:")
        db.init_db(conn)
        kb_seed.seed_interfaces(conn)
        db.upsert_node(conn, "app:x", "app", "x", "scan", "unknown")
        db.upsert_node(conn, "hb:vend1", "package", "vend1",
                       "harmonybrew", "ported")
        db.upsert_node(conn, "pkg-unknown:vend2", "package", "vend2",
                       "scan", "unknown")
        # vend2's own runtime dependency (the closure must not include it)
        db.upsert_node(conn, "pkg-unknown:vend2child", "package",
                       "vend2child", "scan", "unknown")
        db.upsert_edge(conn, "app:x", "hb:vend1", "vendored")
        db.upsert_edge(conn, "app:x", "pkg-unknown:vend2", "vendored")
        db.upsert_edge(conn, "pkg-unknown:vend2",
                       "pkg-unknown:vend2child", "runtime")
        manifest = deps_fetch.fetch_app_deps(
            conn, "app:x", Path(tempfile.gettempdir()) / "x-out",
            dry_run=True)
        by_name = {e["name"]: e for e in manifest["deps"]}
        self.assertEqual(by_name["vend1"]["status"], "vendored")
        self.assertEqual(by_name["vend1"]["role"], "vendored")
        self.assertEqual(by_name["vend2"]["status"], "vendored")
        self.assertNotIn("vend2child", by_name)   # vendored is not descended into
        self.assertEqual(manifest["summary"].get("vendored"), 2)
        conn.close()


class TestQtComponentsListVar(unittest.TestCase):
    """set(<var> Core Gui ...) + list(APPEND) + find_package(Qt6 COMPONENTS
    ${var}) component expansion (the corpus_b_core SetupQt6.cmake form); same-named variables are unioned across files,
    independent of directory traversal order."""

    def _project(self, tmp: Path):
        root = tmp / "qtcomp"
        root.mkdir(parents=True)
        (root / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.16)\nproject(QtComp)\n"
            "set(qt_components\n    Core\n    Gui\n    Widgets\n)\n"
            "list(APPEND qt_components Network)\n"
            "find_package(Qt6 6.8 REQUIRED COMPONENTS ${qt_components})\n",
            encoding="utf-8")
        # Same-named variables in side directories such as sandbox: unioned and deduplicated, not shadowing the main declaration
        p = root / "sandbox/web_sandbox/CMakeLists.txt"
        p.parent.mkdir(parents=True)
        p.write_text(
            "set(qt_components Core Gui Quick Qml Widgets)\n"
            "list(APPEND qt_components Svg)\n", encoding="utf-8")
        return root

    def test_components_from_list_var(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            info = qt_scanner.scan_project(root)
            for m in ("core", "gui", "widgets", "network", "quick",
                      "qml", "svg"):
                self.assertIn(m, info["qt_modules"], "missing %s" % m)
            self.assertEqual(info["qt_version_hint"], "6")


class Testcorpus_bAliasResolution(unittest.TestCase):
    """Alias gaps confirmed by e2e corpus_b: CMake module names/dependency manifest names -> hb package names,
    so scan-time resolution creates no ghost nodes."""

    def _project(self, tmp: Path):
        root = tmp / "msalias"
        root.mkdir(parents=True)
        (root / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.16)\nproject(MSAlias)\n"
            "find_package(ALSA REQUIRED)\n"
            "find_package(SndFile REQUIRED)\n"
            "find_package(PNG REQUIRED)\n"
            "find_package(DBus1)\n"
            "find_package(GLib2 REQUIRED)\n"
            "find_package(TinyXml REQUIRED)\n",
            encoding="utf-8")
        return root

    def test_aliases_resolve(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            for nid, name in [("cmdpkgs:alsa-lib", "alsa-lib"),
                              ("hb:libsndfile", "libsndfile"),
                              ("cmdpkgs:libpng", "libpng"),
                              ("cmdpkgs:dbus", "dbus"),
                              ("cmdpkgs:glib", "glib"),
                              ("cmdpkgs:tinyxml2", "tinyxml2")]:
                db.upsert_node(conn, nid, "package", name, "test", "ported")
            scan = project_scanner.scan_project(conn, root)
            linked = {d["hint"]: d["node"] for d in scan["deps_linked"]}
            self.assertEqual(linked["alsa"], "cmdpkgs:alsa-lib")
            self.assertEqual(linked["sndfile"], "hb:libsndfile")
            self.assertEqual(linked["png"], "cmdpkgs:libpng")
            self.assertEqual(linked["dbus1"], "cmdpkgs:dbus")
            self.assertEqual(linked["glib2"], "cmdpkgs:glib")
            self.assertEqual(linked["tinyxml"], "cmdpkgs:tinyxml2")
            self.assertEqual(scan["deps_unknown"], [])
            conn.close()


class TestClonerSubmodules(unittest.TestCase):
    """When reusing a clone, submodules should be pulled in too (corpus_b's dependency manifests live in the corpus_b_deps/corpus_b_core
    submodules and cannot be scanned without init); degrade silently when there are no submodules or init fails."""

    def test_reused_clone_inits_submodules_silently(self):
        from port_graph import cloner
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "subproj"
            root.mkdir()
            # Fake an existing clone: .git directory + .gitmodules (pointing to a nonexistent submodule)
            (root / ".git").mkdir()
            (root / "CMakeLists.txt").write_text(
                "project(Sub)\n", encoding="utf-8")
            (root / ".gitmodules").write_text(
                '[submodule "corpus_b_deps"]\n'
                '\tpath = corpus_b_deps\n'
                '\turl = https://example.invalid/corpus_b_deps.git\n',
                encoding="utf-8")
            orig_ws = cloner.WORKSPACE
            cloner.WORKSPACE = Path(tmp)   # point the clone target at a temporary workspace
            try:
                info = cloner.clone_repo("https://github.com/x/subproj",
                                         name="subproj")
            finally:
                cloner.WORKSPACE = orig_ws
            # Directory already exists -> reuse it, and a failed submodule init (invalid URL) does not raise
            self.assertFalse(info["cloned"])
            self.assertEqual(info["path"], str(root))

    def test_no_gitmodules_noop(self):
        from port_graph import cloner
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "plain"
            root.mkdir()
            (root / ".git").mkdir()
            # No .gitmodules -> return directly without running git commands
            cloner._init_submodules(root, 10)
            self.assertTrue((root / ".git").is_dir())


class TestQuotedVersionAndOrphanComponents(unittest.TestCase):
    """Generalization regressions (confirmed with gen_b/gen_c):

    - find_package with a quoted version: find_package(Poppler "24.08.0" COMPONENTS Qt6)
    - trailing components without the COMPONENTS keyword: find_package(Qt6 ${V} CONFIG REQUIRED
        \\n Core Multimedia ...) (valid CMake syntax; gen_c missed all of them)
    - component names identical to keywords: the KF component Config must not be dropped as the CONFIG keyword
    """

    def _project(self, tmp: Path, cmake: str):
        root = Path(tmp) / "p"
        root.mkdir()
        (root / "CMakeLists.txt").write_text(cmake, encoding="utf-8")
        return root

    def test_quoted_version_parsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(tmp, (
                "cmake_minimum_required(VERSION 3.16)\n"
                "project(QuotedVer)\n"
                'find_package(Poppler "24.08.0" COMPONENTS Qt6)\n'))
            info = qt_scanner.scan_project(root)
            fp = next(d for d in info["find_package_details"]
                      if d["name"] == "Poppler")
            self.assertEqual(fp["version"], "24.08.0")
            self.assertEqual(fp["components"], ["Qt6"])

    def test_components_without_keyword(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(tmp, (
                "cmake_minimum_required(VERSION 3.16)\n"
                "project(OrphanComps)\n"
                "set(QT_MIN_VERSION 6.5.0)\n"
                "find_package(Qt6 ${QT_MIN_VERSION} CONFIG REQUIRED\n"
                "    Core\n"
                "    Multimedia\n"
                "    PrintSupport\n"
                "    Widgets\n"
                ")\n"))
            info = qt_scanner.scan_project(root)
            for mod in ("core", "multimedia", "printsupport", "widgets"):
                self.assertIn(mod, info["qt_modules"], mod)
            fp = next(d for d in info["find_package_details"]
                      if d["name"] == "Qt6")
            self.assertEqual(sorted(fp["components"]),
                             ["Core", "Multimedia", "PrintSupport",
                              "Widgets"])

    def test_kf_config_component_not_swallowed(self):
        """The KF component name Config has the same form as the CONFIG keyword: once the component section starts, words are no longer
        interpreted as keywords (gen_c find_package(KF6 ${V} REQUIRED Bookmarks
        Config ConfigWidgets ...) used to drop Config)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(tmp, (
                "cmake_minimum_required(VERSION 3.16)\n"
                "project(KfConfig)\n"
                "set(KF6_DEP_VERSION 6.6.0)\n"
                "find_package(KF6 ${KF6_DEP_VERSION} REQUIRED\n"
                "    Bookmarks\n"
                "    Config\n"
                "    ConfigWidgets\n"
                ")\n"))
            info = qt_scanner.scan_project(root)
            for comp in ("bookmarks", "config", "configwidgets"):
                self.assertIn(comp, info["kf_components"], comp)
            fp = next(d for d in info["find_package_details"]
                      if d["name"] == "KF6")
            self.assertIn("Config", fp["components"])

    def test_optional_components_still_optional(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(tmp, (
                "cmake_minimum_required(VERSION 3.16)\n"
                "project(OptComps)\n"
                "find_package(Qt5 5.15 REQUIRED COMPONENTS Core Widgets "
                "OPTIONAL_COMPONENTS Network)\n"))
            info = qt_scanner.scan_project(root)
            fp = next(d for d in info["find_package_details"]
                      if d["name"] == "Qt5")
            self.assertEqual(fp["components"], ["Core", "Widgets"])
            self.assertEqual(fp["optional_components"], ["Network"])


class TestPlatformBlockContext(unittest.TestCase):
    """Link/probe declarations inside if blocks for other platforms: required=False + note,
    no DB runtime edge (gen_c if(HAIKU) network, if(FreeBSD) util,
    corpus_d if(Darwin)/elseif(Windows), gen_b mobile if(ANDROID),
    corpus_c FindQREncode if(WIN32 AND NOT MINGW) confirmed)."""

    CMAKE = """cmake_minimum_required(VERSION 3.16)
project(PlatBlocks)
find_package(ZLIB REQUIRED)
if (CMAKE_SYSTEM_NAME STREQUAL "Darwin")
    find_library(AppKit_LIBRARY AppKit)
    target_link_libraries(app PRIVATE ${AppKit_LIBRARY} objc)
elseif (CMAKE_SYSTEM_NAME STREQUAL "Windows")
    target_link_libraries(app PRIVATE iphlpapi)
endif()
if(HAIKU)
    target_link_libraries(app PRIVATE network)
endif()
if("${CMAKE_SYSTEM_NAME}" MATCHES "FreeBSD")
    target_link_libraries(app PRIVATE util)
endif()
if (ANDROID)
    pkg_check_modules(NSS "nss")
    target_link_libraries(app2 PRIVATE -lsoftokn3)
endif()
if(UNIX AND NOT APPLE)
    target_link_libraries(app PRIVATE usb-1.0)
endif()
if(NOT WIN32)
    target_link_libraries(app PRIVATE keyutils)
endif()
"""

    def _project(self, tmp: Path):
        root = Path(tmp) / "plat"
        root.mkdir()
        (root / "CMakeLists.txt").write_text(self.CMAKE, encoding="utf-8")
        return root

    def test_raw_links_platform_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            info = qt_scanner.scan_project(root)
            raw = {r["name"].lower(): r for r in info["raw_libs"]}
            for n in ("appkit", "objc", "iphlpapi", "network", "util",
                      "softokn3"):
                self.assertTrue(raw[n].get("platform_block"),
                                "%s should have a platform-block marker" % n)
            # OHOS-active blocks (UNIX AND NOT APPLE / NOT WIN32) are not judged excluded
            self.assertFalse(raw["usb-1.0"].get("platform_block"))
            self.assertFalse(raw["keyutils"].get("platform_block"))

    def test_report_required_flags_and_edges(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            db.upsert_node(conn, "hb:libusb", "package", "libusb",
                           "harmonybrew", "ported", version="1.0.30")
            scan = project_scanner.scan_project(conn, root)
            report = deps_report.analyze_dependencies(conn, root, info=None)
            link = {d["name"].lower(): d for d in report["link_deps"]}
            for n in ("appkit", "objc", "iphlpapi", "network", "util",
                      "softokn3", "nss"):
                self.assertFalse(link[n]["required"],
                                 "%s should be required=False" % n)
                self.assertIn("platform block", link[n].get("note") or "")
            # OHOS-active blocks stay required
            self.assertTrue(link["keyutils"]["required"])
            # usb-1.0 merged into libusb via the alias table (same library, different names)
            self.assertTrue(link["libusb"]["required"])
            # DB: declarations inside platform blocks get no runtime edge (eliminates nss/systemd-style ghosts)
            dsts = {e["dst"] for e in db.out_edges(conn, scan["app_id"])}
            self.assertNotIn("pkg-unknown:nss", dsts)
            self.assertNotIn("pkg-unknown:network", dsts)
            self.assertNotIn("pkg-unknown:util", dsts)
            # Resolvable declarations inside UNIX AND NOT APPLE get edges as usual
            self.assertIn("hb:libusb", dsts)
            conn.close()

    def test_unguarded_declaration_wins(self):
        """A library with both platform-block declarations and non-platform-block declarations -> required (cross-platform library)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "mixed"
            root.mkdir()
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.16)\n"
                "project(Mixed)\n"
                "if(APPLE)\n"
                "    target_link_libraries(app PRIVATE foo)\n"
                "endif()\n"
                "target_link_libraries(app PRIVATE foo)\n",
                encoding="utf-8")
            info = qt_scanner.scan_project(root)
            raw = {r["name"].lower(): r for r in info["raw_libs"]}
            self.assertFalse(raw["foo"].get("platform_block"))
            conn = db.connect(":memory:")
            db.init_db(conn)
            report = deps_report.analyze_dependencies(conn, root, info=info)
            link = {d["name"].lower(): d for d in report["link_deps"]}
            self.assertTrue(link["foo"]["required"])
            conn.close()


class TestOptionalPlatformIface(unittest.TestCase):
    """INTERFACE_BOUND_PACKAGES (platform-iface) entries follow optional guards:
    corpus_d systemd (find_package(Systemd) inside a feature_option_dependent block
    defaulting to OFF) used to be falsely reported as required=True + a "talks directly to the platform stack" warning."""

    def test_optional_systemd_not_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "optiface"
            root.mkdir()
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.16)\n"
                "project(OptIface)\n"
                "feature_option_dependent(SYSTEMD \"install systemd stuff\" "
                "OFF \"NOT GUI\" OFF)\n"
                "add_subdirectory(dist)\n",
                encoding="utf-8")
            dist = root / "dist"
            dist.mkdir()
            (dist / "CMakeLists.txt").write_text(
                "if (SYSTEMD)\n"
                "    find_package(Systemd)\n"
                "endif()\n",
                encoding="utf-8")
            conn = db.connect(":memory:")
            db.init_db(conn)
            report = deps_report.analyze_dependencies(conn, root)
            link = {d["name"].lower(): d for d in report["link_deps"]}
            self.assertFalse(link["systemd"]["required"])
            self.assertIn("option guard", link["systemd"].get("note") or "")
            warns = [w["msg"] for w in report["warnings"]
                     if "Systemd" in w["msg"]]
            self.assertEqual(warns, [])
            conn.close()


class TestDashlessMergeInDepsReport(unittest.TestCase):
    """Separator-stripped merge in the deps report link table: unresolved flattened/hyphenated names of the same library
    are not double counted (corpus_d LibtorrentRasterbar + libtorrent-rasterbar
    used to produce two "needs source cross-compilation" warnings)."""

    def test_single_entry_single_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "dashrep"
            root.mkdir()
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.16)\n"
                "project(DashRep)\n"
                "find_package(LibtorrentRasterbar 2.0 REQUIRED)\n"
                "pkg_check_modules(LT IMPORTED_TARGET "
                "\"libtorrent-rasterbar>=2.0.10\")\n",
                encoding="utf-8")
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            report = deps_report.analyze_dependencies(conn, root)
            entries = [d for d in report["link_deps"]
                       if "torrent" in d["name"].lower()]
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["name"], "libtorrent-rasterbar")
            warns = [w["msg"] for w in report["warnings"]
                     if "torrent" in w["msg"].lower()]
            self.assertEqual(len(warns), 1)
            conn.close()


class TestKfFrameworkResolution(unittest.TestCase):
    """KF component entries resolve to kf:<comp> nodes rather than via the package-name ladder: KF Archive !=
    libarchive, KF Config != libconfig (gen_b/gen_c used to show a ready
    bottle by mistake, contradicting the closure's need_port)."""

    def test_framework_resolves_to_kf_node(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "kfproj"
            root.mkdir()
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.16)\n"
                "project(KFProj)\n"
                "find_package(KF6 6.6 REQUIRED COMPONENTS Archive Config)\n"
                "find_package(Qt6 6.6 REQUIRED COMPONENTS Core Widgets)\n",
                encoding="utf-8")
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            # Unrelated same-named C libraries (libarchive/libconfig) exist in the DB
            db.upsert_node(conn, "hb:libarchive", "package", "libarchive",
                           "harmonybrew", "ported", version="3.8.9")
            db.upsert_node(conn, "hb:libconfig", "package", "libconfig",
                           "harmonybrew", "ported", version="1.8.2")
            project_scanner.scan_project(conn, root)
            report = deps_report.analyze_dependencies(conn, root)
            link = {d["name"].lower(): d for d in report["link_deps"]}
            self.assertEqual(link["archive"]["resolved_node"], "kf:archive")
            self.assertEqual(link["config"]["resolved_node"], "kf:config")
            self.assertFalse((link["archive"].get("artifact") or {})
                             .get("ready"))
            conn.close()


class TestInTreeGeneratorDirs(unittest.TestCase):
    """in-tree detection does not wrongly take in functional grouping directories (gen_b generators/poppler,
    generators/epub are format generator plugin code, not bundled library sources); bundled libraries inside library containers
    (libraries/libs) are matched as usual (confirmed with gen_f fakevim)."""

    def test_generators_not_in_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "gen"
            root.mkdir()
            (root / "CMakeLists.txt").write_text(
                "find_package(Poppler REQUIRED)\n"
                "find_package(EPub REQUIRED)\n"
                "add_subdirectory(generators)\n",
                encoding="utf-8")
            gens = root / "generators"
            for name in ("poppler", "epub", "djvu", "tiff", "xps", "txt"):
                d = gens / name
                d.mkdir(parents=True)
                (d / "CMakeLists.txt").write_text(
                    "gen_b_add_generator(gen_bGenerator_%s x.cpp)\n" % name,
                    encoding="utf-8")
                (d / "x.cpp").write_text("", encoding="utf-8")
            # The README of generators/epub explains it is "a backend based on the external libepub"
            (gens / "epub" / "README").write_text(
                "This is a libepub based backend\n", encoding="utf-8")
            from port_graph.deps_report import (_in_tree_dir_index,
                                                _match_in_tree_dir)
            idx = _in_tree_dir_index(root)
            self.assertIsNone(_match_in_tree_dir(idx, "Poppler"))
            self.assertIsNone(_match_in_tree_dir(idx, "EPub"))

    def test_libraries_container_with_readme_still_in_tree(self):
        """A library container with only a few bundled libraries (fewer than 5) is still judged in-tree when backed by a README."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "libs2"
            root.mkdir()
            lib = root / "src" / "libraries" / "fakevim"
            lib.mkdir(parents=True)
            (lib / "fakevim.cpp").write_text("", encoding="utf-8")
            (lib / "CMakeLists.txt").write_text(
                "project(fakevim)\n", encoding="utf-8")
            (lib / "README.md").write_text(
                "# FakeVim\nlibrary to emulate Vim\n",
                encoding="utf-8")
            (root / "CMakeLists.txt").write_text(
                "find_package(fakevim REQUIRED)\n", encoding="utf-8")
            from port_graph.deps_report import (_in_tree_dir_index,
                                                _match_in_tree_dir)
            idx = _in_tree_dir_index(root)
            self.assertEqual(_match_in_tree_dir(idx, "fakevim"),
                             "src/libraries/fakevim")


class TestFirstPartyDepsReport(unittest.TestCase):
    """The project's own targets must not count as "the knowledge base lacks this package".

    There are two folding schemes (first_party keeps hyphens, `auto-updates`; `_loose_folds`
    removes all separators, `autoupdates`); both sides must line up, otherwise the deps report still
    reports the project's own subdirectories as "needs source cross-compilation".
    """

    def test_wrapper_target_is_in_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "app"
            (root / "compat" / "auto_updates").mkdir(parents=True)
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.16)\n"
                "project(probe CXX)\n"
                "find_package(auto_updates REQUIRED)\n"
                "add_subdirectory(compat/auto_updates)\n",
                encoding="utf-8")
            (root / "compat" / "auto_updates" / "CMakeLists.txt").write_text(
                "add_library(external_auto_updates STATIC auto_updates.cpp)\n",
                encoding="utf-8")
            (root / "compat" / "auto_updates" / "auto_updates.cpp").write_text(
                "int f() { return 1; }\n", encoding="utf-8")
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            info = qt_scanner.scan_project(root)
            project_scanner.scan_project(conn, root, info=info)
            report = deps_report.analyze_dependencies(conn, root, info=info)
            entries = {e["name"]: e for e in report["link_deps"]}
            self.assertIn("auto_updates", entries)
            entry = entries["auto_updates"]
            self.assertEqual(entry["kind"], "in-tree")
            self.assertTrue(entry["artifact"]["provided"])
            self.assertIn("auto-updates", entry["ohos_note"])
            self.assertEqual([p["name"] for p in report["first_party"]],
                             ["auto_updates"])
            self.assertFalse([w for w in report["warnings"]
                              if "auto_updates" in w["msg"]])

    def test_external_wrapper_without_sources_stays_unknown(self):
        """Uninitialized submodules (no source in the directory) must not be treated as built with the project."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "app2"
            (root / "cmake" / "external" / "webrtc").mkdir(parents=True)
            (root / "CMakeLists.txt").write_text(
                "project(probe2 CXX)\n"
                "add_subdirectory(cmake/external/webrtc)\n",
                encoding="utf-8")
            (root / "cmake" / "external" / "webrtc" / "CMakeLists.txt"
             ).write_text("add_library(external_webrtc STATIC)\n",
                          encoding="utf-8")
            info = qt_scanner.scan_project(root)
            folds = qt_scanner.first_party_folds(info)
            self.assertNotIn("webrtc", folds)
            self.assertIn("external-webrtc", folds)


class TestPkgAliasesgen_b(unittest.TestCase):
    """Alias gaps confirmed by gen_b generalization: ddjvuapi->djvulibre (same-library pkg-config
    name, eliminating double ghosts), libmarkdown->discount (hb markdown is daringfireball's
    Perl/PHP version; the same-name-different-thing confusion once downloaded the wrong bottle)."""

    def test_ddjvuapi_merges_into_djvulibre_ghost(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "djvu"
            root.mkdir()
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.16)\n"
                "project(DjVu)\n"
                "find_package(DjVuLibre \"3.5.28\")\n"
                "pkg_check_modules(PC_DJVULIBRE ddjvuapi)\n",
                encoding="utf-8")
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            scan = project_scanner.scan_project(conn, root)
            ghosts = [d["node"] for d in scan["deps_unknown"]]
            self.assertEqual(ghosts, ["pkg-unknown:djvulibre"])
            lt = scan["deps_unknown"][0]
            self.assertEqual(lt.get("merged_from"), ["ddjvuapi"])
            conn.close()

    def test_libmarkdown_resolves_to_discount(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "md"
            root.mkdir()
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.16)\n"
                "project(Md)\n"
                "find_package(Discount)\n"
                "pkg_check_modules(Discount IMPORTED_TARGET \"libmarkdown\")\n",
                encoding="utf-8")
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            db.upsert_node(conn, "hb:discount", "package", "discount",
                           "harmonybrew", "ported", version="3.0.2.0")
            # Same-name trap package: daringfireball Markdown (not a C library)
            db.upsert_node(conn, "hb:markdown", "package", "markdown",
                           "harmonybrew", "ported", version="1.0.1")
            scan = project_scanner.scan_project(conn, root)
            self.assertEqual(scan["deps_unknown"], [])
            # Discount (find_package name) and libmarkdown (pkg-config name)
            # are the same library, merged into a single entry that resolves to hb:discount
            self.assertEqual(
                [(d["hint"], d["node"], d.get("merged_from"))
                 for d in scan["deps_linked"]],
                [("discount", "hb:discount", ["libmarkdown"])])
            conn.close()

    def test_init_cmd_uses_dash_init_flag(self):
        """Regression: a bare init in `git submodule update init ...` is taken by git as a pathspec;
        it errors, but the old version silently swallowed it -> the submodules of a reused clone were never pulled
        (corpus_b scan scope missing, large-scale missed detections in deps). Must use --init."""
        from port_graph import cloner
        captured = {}

        class FakeResult:
            returncode = 0
            stderr = ""

        def fake_run(cmd, **kw):
            captured["cmd"] = cmd
            return FakeResult()

        orig_run = cloner.subprocess.run
        cloner.subprocess.run = fake_run
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "proj"
                root.mkdir()
                (root / ".git").mkdir()
                (root / ".gitmodules").write_text(
                    '[submodule "x"]\n\tpath = x\n\turl = https://e.invalid/x.git\n',
                    encoding="utf-8")
                cloner._init_submodules(root, 10)
        finally:
            cloner.subprocess.run = orig_run
        cmd = captured["cmd"]
        self.assertIn("--init", cmd)
        # A bare init (without --) must no longer appear in the command
        self.assertNotIn("init", [c for c in cmd if not c.startswith("-")])


if __name__ == "__main__":
    unittest.main()


class TestFetchBytesRangeFallback(unittest.TestCase):
    """D-08: gitcode releases return 401 for direct requests without Range; only with Range do they return 206."""

    def _server(self, first_status=401, honor_range=True):
        import http.server
        import threading

        payload = b"bottle-bytes-" * 200

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                rng = self.headers.get("Range")
                if rng is None and first_status:
                    self.send_response(first_status)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                start = 0
                if rng and honor_range:
                    start = int(rng.split("=")[1].split("-")[0])
                    body = payload[start:]
                    self.send_response(206)
                    self.send_header("Content-Range", "bytes %d-%d/%d" % (
                        start, len(payload) - 1, len(payload)))
                else:
                    body = payload
                    self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return srv, payload

    def test_retries_with_range_after_401(self):
        from port_graph import harmonybrew
        srv, payload = self._server()
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "a.tar.gz"
            harmonybrew._fetch_bytes(
                "http://127.0.0.1:%d/f" % srv.server_address[1], dest, 10)
            self.assertEqual(dest.read_bytes(), payload)

    def test_server_ignoring_range_does_not_duplicate(self):
        from port_graph import harmonybrew
        srv, payload = self._server(first_status=401, honor_range=False)
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "a.tar.gz"
            harmonybrew._fetch_bytes(
                "http://127.0.0.1:%d/f" % srv.server_address[1], dest, 10)
            # The first 401 wrote no file; the second 200 is a full download -> there must not be two copies of the content
            self.assertEqual(dest.read_bytes(), payload)
