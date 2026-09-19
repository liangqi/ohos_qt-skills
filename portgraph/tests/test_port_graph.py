"""port_graph 自测：formula/README 解析器 + 可移植性推导引擎。

运行方式（portgraph 项目根目录）:

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
        # 上游 formula 随时会演进（8.21.0 -> 8.22.0 -> …），
        # 只验证版本号形态，不锁具体版本
        self.assertRegex(info["version"], r"^8\.\d+(\.\d+)?(_\d+)?$")
        self.assertTrue(info["ohos_bottle"])
        self.assertTrue(info["keg_only_macos"])
        deps = {d[0]: (d[1], d[2]) for d in info["deps"]}
        self.assertIn("brotli", deps)
        self.assertEqual(deps["brotli"][0], ["runtime"])
        self.assertIn("openssl@3", deps)
        # head do 块内依赖被忽略
        self.assertNotIn("autoconf", deps)
        # 平台条件块
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
            # 同名多版本取最后出现
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
        self.assertIn("Qt WebEngine (全子模块)", r["blocked_modules"])
        core = db.get_node(conn, "qtmod:core")
        self.assertEqual(core["port_status"], "ported")
        we = db.get_node(conn, "qtmod:webengine")
        self.assertEqual(we["port_status"], "blocked")
        self.assertEqual(core["cluster_id"], "cluster:qt")
        conn.close()


def _build_graph(conn):
    """小图：app 依赖链 + Qt 模块 + 接口。"""
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
        # macOS 条件依赖在鸿蒙上不需要，不应阻塞
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
    """宏栈追踪：#ifdef/#if defined/#else/#endif 守卫状态判断。"""

    def test_platform_macro_excludes(self):
        # Q_OS_WIN 包裹的代码在鸿蒙上不编译
        code = (
            "#ifdef Q_OS_WIN\n"
            "  QDBusConnection c;\n"
            "#endif\n"
        )
        g = project_scanner._macro_stack_status(code)
        # QDBusConnection 在第 2 行，应被 platform 守卫排除
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
        self.assertEqual(g[2], "platform-excluded")  # #ifdef 分支
        # #else 分支在鸿蒙会编译（Q_OS_WIN 为假 → NOT Q_OS_WIN 为真）
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
        # Q_OS_LINUX 在鸿蒙上是 active（鸿蒙隐含 Linux），所以外层不算排除
        # 内层 Q_OS_WIN 才是排除
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
        """defined(Q_OS_WIN) || defined(Q_OS_OHOS) 在鸿蒙会编译。"""
        code = (
            "#if defined(Q_OS_WIN) || defined(Q_OS_OHOS)\n"
            "  compiles on ohos\n"
            "#endif\n"
        )
        g = project_scanner._macro_stack_status(code)
        self.assertEqual(g[2], "ohos-active")

    def test_and_with_win_macro_excluded(self):
        """defined(Q_OS_LINUX) && defined(Q_OS_WIN) 在鸿蒙不编译。"""
        code = (
            "#if defined(Q_OS_LINUX) && defined(Q_OS_WIN)\n"
            "  not on ohos\n"
            "#endif\n"
        )
        g = project_scanner._macro_stack_status(code)
        self.assertEqual(g[2], "platform-excluded")

    def test_ifndef_win_compiles_on_ohos(self):
        """#ifndef Q_OS_WIN 在鸿蒙为真（Q_OS_WIN 未定义）。"""
        code = (
            "#ifndef Q_OS_WIN\n"
            "  non-win code\n"
            "#endif\n"
        )
        g = project_scanner._macro_stack_status(code)
        self.assertEqual(g[2], "ohos-active")


class TestFilePlatformExclusion(unittest.TestCase):
    """文件级平台隔离：路径含平台关键词 → platform-file-excluded。"""

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

    def test_linux_path_not_excluded(self):
        # Linux 通用代码鸿蒙会编译，不应排除
        self.assertIsNone(project_scanner._file_platform_excluded(
            "src/platform/linux/foo.cpp"))

    def test_generic_path_not_excluded(self):
        self.assertIsNone(project_scanner._file_platform_excluded(
            "src/core/main.cpp"))


class TestDepsFetch(unittest.TestCase):
    """fetch-deps：依赖闭包 + 产物分类（全部离线，dry-run / 本地解压）。"""

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
        self.assertIn("hb:pkgb", ids)       # ported 包的 runtime 依赖仍展开
        self.assertIn("qtmod:core", ids)    # provided 节点在闭包内
        self.assertNotIn("hb:toolx", ids)   # build 边不产生目标侧产物需求
        self.assertNotIn("hb:pkgx", ids)    # macos 条件依赖跳过
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
            # 测试框架不再误报 need_port（需自行移植）
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
            # 跨源互补：hb:zeta 无直链，同名 cmdpkgs:zeta 的直链补位
            self.assertEqual(by_id["hb:zeta"]["status"], "would_download")
            self.assertEqual(by_id["cmdpkgs:zeta"]["status"], "covered")
            self.assertNotIn("manifest_path", m)
            self.assertEqual(sorted(Path(tmp).iterdir()), [])  # dry-run 不写盘
            self.assertIn("would_download", m["summary"])
            self.assertTrue(m["toolchain"]["cmake_prefix_path"])
        conn.close()

    def test_extract_replaces_readonly_leftover(self):
        """上次失败留下的只读半成品：重新提取应整体替换而非 PermissionError。"""
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
            os.chmod(stale, stat_mod.S_IREAD)   # brew 只读残留
            deps_fetch._extract_tarball(tar_path, target)
            self.assertFalse(stale.exists())
            self.assertTrue((target / "lib" / "libz.so.1.3").is_file())

    def test_extract_flat_tarball(self):
        """cmd-pkgs 扁平结构：链接以拷贝落地（NTFS），根定位与库列表正确。"""
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
    """综合依赖分析：角色分类 / 版本范围 / 工具链 / 动态加载 / vendored。"""

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
            # ---- link 分类与版本范围
            link = {d["name"].lower(): d for d in report["link_deps"]}
            self.assertIn("zlib", link)
            self.assertEqual(link["zlib"]["min_version"], "1.2")
            self.assertTrue(link["zlib"]["required"])
            self.assertEqual(link["zlib"]["version_range"], "[>=1.2 <2]")
            self.assertEqual(link["zlib"]["version_check"], "satisfied")
            self.assertEqual(link["zlib"]["resolved_node"], "hb:zlib")
            self.assertEqual(link["zlib"]["available_version"], "1.3.2")
            # OpenSSL 无 REQUIRED → optional
            self.assertIn("openssl", link)
            self.assertFalse(link["openssl"]["required"])
            # pkg_check_modules 版本约束（libavcodec 按别名归并为 ffmpeg）
            self.assertIn("ffmpeg", link)
            self.assertEqual(link["ffmpeg"]["version_req"], ">= 58")
            # qmake LIBS
            self.assertIn("baz", link)
            self.assertIn("m", link)
            self.assertEqual(link["m"]["kind"], "system-lib")
            # ---- 工具链
            t = report["toolchain"]
            self.assertEqual(t["cmake_min"], "3.16")
            self.assertEqual(t["cxx_standard"], 17)
            tools = {x["tool"] for x in t["tools"]}
            self.assertIn("python3", tools)   # find_program
            self.assertIn("protoc", tools)    # COMMAND
            self.assertTrue(t["has_testing"])
            # ---- 测试依赖
            self.assertTrue(any(d["name"] == "GTest"
                                for d in report["test_deps"]))
            # ---- 运行时传递闭包（zlib → zstd）
            rt = {d["name"]: d for d in report["runtime_deps"]}
            self.assertIn("zstd", rt)
            self.assertEqual(rt["zstd"]["needed_by"], ["zlib"])
            self.assertEqual(rt["zstd"]["version"], "1.5.7")
            # ---- 动态加载
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
            # ---- ECM 归入构建工具而非 link
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
        """别名归并后的版本约束（libavcodec >= 58 → ffmpeg）是库主版本
        口径，与包版本不可比：应判 unknown 而非虚假 conflict。"""
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
            # 不产生版本冲突警告，改以 info 说明版本口径不可比
            self.assertFalse(any(
                w["level"] == "warn" and "版本冲突" in w["msg"]
                for w in report["warnings"]))
            self.assertTrue(any(
                w["level"] == "info" and "libavcodec" in w["msg"]
                for w in report["warnings"]))
            conn.close()

    def test_cross_source_same_lib_merged(self):
        """同一库跨源异名（hb:qrencode / cmdpkgs:libqrencode）合并为单条
        link 条目，不再出现同库多条矛盾条目。"""
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
            # 两个声明的证据都保留
            self.assertEqual(len(entry["evidence"]), 2)
            conn.close()

    def test_build_tools_count_matches_display(self):
        """counts.build_tools 与渲染展示项一致（工具数 + CMake/C++/编译器）。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            conn = self._conn()
            report = deps_report.analyze_dependencies(conn, root)
            t = report["toolchain"]
            expected = (len(t["tools"]) + (1 if t["cmake_min"] else 0)
                        + (1 if t["cxx_standard"] else 0) + 1)
            self.assertEqual(report["counts"]["build_tools"], expected)
            conn.close()

    def test_no_conn_still_classifies(self):
        """无 DB（conn=None）时纯扫描仍产出角色分类，只是产物为空。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            report = deps_report.analyze_dependencies(None, root)
            link = {d["name"].lower(): d for d in report["link_deps"]}
            self.assertIn("zlib", link)
            self.assertEqual(link["zlib"]["version_check"], "unknown")
            self.assertEqual(report["counts"]["test"], 1)
            self.assertTrue(report["counts"]["vendored"] >= 2)

    def test_build_tools_count_matches_display(self):
        """build_tools 计数与文本报告展示一致：tools 列表 + CMake/C++/编译器
        固定行（修复 tools 已含 build_tools 条目的重复计数）。"""
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
        """libavcodec >= 58 是库主版本号（≈ffmpeg 4.x），与 ffmpeg 发布
        版本不同量纲：不得误报 conflict，应记 unknown 并附说明。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            conn = self._conn()
            db.upsert_node(conn, "hb:ffmpeg", "package", "ffmpeg",
                           "harmonybrew", "ported", version="7.1")
            report = deps_report.analyze_dependencies(conn, root)
            link = {d["name"].lower(): d for d in report["link_deps"]}
            self.assertEqual(link["ffmpeg"]["version_req"], ">= 58")
            # 合并实现：采用 worker1 的通用 version_req_from 口径
            # （替换原 worker2 的 libav-major 专用标记）
            self.assertEqual(link["ffmpeg"]["version_req_from"],
                             "libavcodec")
            self.assertEqual(link["ffmpeg"]["version_check"], "unknown")
            self.assertFalse(any(w["msg"].startswith("ffmpeg 版本冲突")
                                 for w in report["warnings"]))
            conn.close()

    def test_runtime_closure_cache_shared(self):
        """共享图缓存下闭包结果与去重口径不变：两个 link 依赖指向同一传递
        依赖时 needed_by 合并双方，环图不死循环。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            conn = self._conn()
            # zlib → zstd → zlib（环）+ openssl → zstd（共享传递依赖）
            db.upsert_edge(conn, "hb:zstd", "hb:zlib", "runtime")
            db.upsert_edge(conn, "hb:openssl@3", "hb:zstd", "runtime")
            report = deps_report.analyze_dependencies(conn, root)
            rt = {d["name"].lower(): d for d in report["runtime_deps"]}
            self.assertIn("zstd", rt)
            self.assertIn("zlib", set(rt["zstd"]["needed_by"]))
            conn.close()

    def test_manifest_roles(self):
        """fetch-deps manifest：depth 决定 role（link/runtime/provided）。"""
        conn = self._conn()
        db.upsert_node(conn, "app:demo", "app", "demo", "scan", "unknown")
        db.upsert_edge(conn, "app:demo", "hb:zlib", "runtime")
        db.upsert_edge(conn, "app:demo", "qtmod:core", "uses-module")
        with tempfile.TemporaryDirectory() as tmp:
            m = deps_fetch.fetch_app_deps(conn, "app:demo", Path(tmp),
                                          dry_run=True)
            roles = {e["name"]: e.get("role") for e in m["deps"]}
            self.assertEqual(roles["zlib"], "link")        # depth 1
            self.assertEqual(roles["zstd"], "runtime")     # depth 2 传递
            self.assertEqual(roles["Qt Core"], "provided")
            self.assertEqual(m["roles"].get("link"), 1)
            self.assertEqual(m["roles"].get("runtime"), 1)
        conn.close()

    def test_fetch_cross_source_dedup(self):
        """同库异名跨源去重（规范化名：去 lib 前缀）：只下载一次。"""
        conn = self._conn()
        db.upsert_node(conn, "app:demo", "app", "demo", "scan", "unknown")
        db.upsert_node(conn, "hb:qrencode", "package", "qrencode",
                       "harmonybrew", "ported", version="4.1.1",
                       links={"artifact_url": "https://x/qrencode.bottle.tar.gz"})
        db.upsert_node(conn, "cmdpkgs:libqrencode", "package", "libqrencode",
                       "cmdpkgs", "ported", version="4.1.1",
                       links={"artifact_url": "https://x/libqrencode.tar.gz"})
        # 幽灵节点 xkbcommon 与 libxkbcommon 同库异名：产物应补位而非 need_port
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
        """CMake 内置（OpenMP）/测试框架（GTest）不再显示为“需自行移植”。"""
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
            # OpenMP：编译器特性，随 NDK 提供，不进 need_port
            self.assertEqual(by_name["openmp"]["status"], "provided")
            self.assertEqual(by_name["openmp"]["role"], "build-tool")
            # GTest：role=test，明确不进发行包
            self.assertEqual(by_name["gtest"]["role"], "test")
            self.assertIn("不进发行包", by_name["gtest"].get("note", ""))
        conn.close()


class TestScanAliasResolution(unittest.TestCase):
    """扫描期别名解析：pkg-config 库名直接解析到鸿蒙包，不产生幽灵节点。"""

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
    """第二轮增强：tll 裸名 / find_library / -framework / FetchContent /
    qmake PKGCONFIG / meson / autotools / CI 脚本安装。"""

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
  # 内部用 pkg_check_modules/find_library 间接查找
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
            # tll 裸名 / find_library / -l / .lib 归一
            for n in ("z", "ssl", "keyutils", "pthread", "wtsapi32"):
                self.assertIn(n, raw, "raw_libs missing %s" % n)
            self.assertNotIn("internal", raw)      # 项目内目标排除
            self.assertNotIn("qt5::core", raw)     # 导入目标排除
            self.assertNotIn("botan_libraries", raw)
            # find_library 归入 raw_libs
            self.assertIn("find_library", raw["keyutils"]["hows"])
            # macOS 框架
            fw = {f["name"] for f in info["macos_frameworks"]}
            self.assertEqual(fw, {"Foundation", "AppKit"})
            # FetchContent：名称/URL/锁定 tag
            self.assertEqual(len(info["fetched_deps"]), 1)
            fd = info["fetched_deps"][0]
            self.assertEqual(fd["name"], "qhotkey")
            self.assertEqual(fd["how"], "FetchContent")
            self.assertEqual(fd["tag"], "v1.1.0")
            # 自定义包装函数：PACKAGE 名 + set() 变量版本解析（带引号）
            self.assertEqual(len(info["wrapper_deps"]), 1)
            wdp = info["wrapper_deps"][0]
            self.assertEqual(wdp["name"], "libtoxcore")
            self.assertEqual(wdp["wrapper"], "search_dependency")
            self.assertEqual(wdp["library"], "toxcore")
            self.assertEqual(wdp["version"], "0.2.20")
            # qmake PKGCONFIG
            self.assertEqual([p["name"] for p in info["qmake_pkgconfig"]],
                             ["libqrencode"])
            # meson：版本要求 / optional / 内置 qt 模块 / cc.find_library
            md = {d["name"]: d for d in info["meson_deps"]}
            self.assertEqual(md["glib-2.0"]["version"], ">= 2.36")
            self.assertFalse(md["gtk+-3.0"]["required"])
            self.assertEqual(info["meson"]["version_min"], "0.53")
            self.assertEqual(info["meson"]["cxx_standard"], 17)
            self.assertIn("core", info["qt_modules"])
            self.assertIn("widgets", info["qt_modules"])
            self.assertIn("m", raw)              # cc.find_library 并入 raw_libs
            # autotools：PKG_CHECK_MODULES 版本约束
            ad = {d["name"]: d for d in info["autotools_deps"]}
            self.assertEqual(ad["zlib"]["version_req"], ">= 1.2")
            self.assertIn("libcurl", ad)
            # CI 脚本安装
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
            # meson 版本约束 + 校验（2.84.4 >= 2.36）
            self.assertEqual(link["glib-2.0"]["version_req"], ">= 2.36")
            self.assertEqual(link["glib-2.0"]["version_check"], "satisfied")
            # macOS 框架 → platform-iface
            self.assertEqual(link["foundation"]["kind"], "platform-iface")
            # .lib → win32-system-lib
            self.assertEqual(link["wtsapi32"]["kind"], "win32-system-lib")
            # -pthread / z / ssl → 系统库
            self.assertEqual(link["z"]["kind"], "system-lib")
            self.assertEqual(link["pthread"]["kind"], "system-lib")
            # FetchContent → vendored（含锁定 tag）
            vend = {v["name"]: v for v in report["vendored"]}
            self.assertEqual(vend["qhotkey"]["tag"], "v1.1.0")
            # 自定义包装函数声明 → link（版本约束经 set() 变量解析）
            self.assertEqual(link["libtoxcore"]["version_req"], ">= 0.2.20")
            # autotools 版本约束
            self.assertEqual(link["zlib"]["version_req"], ">= 1.2")
            # env 清单
            names = {e["name"] for e in report["env_deps"]}
            self.assertIn("libkeyutils-dev", names)
            # 工具链：meson 最低版本
            tools = {t["tool"] for t in report["toolchain"]["tools"]}
            self.assertIn("meson", tools)
            self.assertEqual(report["toolchain"]["cxx_standard"], 17)
            conn.close()


class TestGeneralizationFixes(unittest.TestCase):
    """语料外泛化测试（QOwnNotes/strawberry/krita，2026-09）暴露问题的
    回归测试：URL 版本提取 / 宏包装目标 / find_library 关键字 / env -y /
    共享解析阶梯 / in-tree 判定 / raw 链接名的 test 角色。"""

    # ---- 1) harmonybrew URL 版本提取（419 个 formula 无版本的根因）
    def test_url_version_extraction(self):
        cases = {
            # 版本后带 -b2-nodocs / -bin / -complete 等名称后缀段（boost/ant/antlr）
            "https://github.com/boostorg/boost/releases/download/boost-1.92.0/boost-1.92.0-b2-nodocs.tar.xz": "1.92.0",
            "https://www.apache.org/dyn/closer.lua?path=ant/binaries/apache-ant-1.10.18-bin.tar.xz": "1.10.18",
            "https://www.antlr.org/download/antlr-4.13.2-complete.jar": "4.13.2",
            # Rust crate 扩展名
            "https://static.crates.io/crates/action-validator/action-validator-0.9.0.crate": "0.9.0",
            # 大写 V 前缀 / 字母尾缀无数字
            "https://github.com/CycoPH/atasm/archive/refs/tags/V1.30.tar.gz": "1.30",
            "https://loop-aes.sourceforge.net/aespipe/aespipe-v2.4j.tar.bz2": "2.4j",
            "https://www.harding.motd.ca/autossh/autossh-1.4g.tgz": "1.4g",
            # 回归：原有形态不变
            "https://www.zlib.net/zlib-1.3.1.tar.gz": "1.3.1",
            "https://github.com/i/indi/archive/refs/tags/v2.0.9.tar.gz": "2.0.9",
            "https://ftp.gnu.org/gnu/gzip/gzip-1.14.tar.xz": "1.14",
            # 版本是独立路径段（兑底规则）
            "https://chiselapp.com/user/moinejf/repository/abcm2ps/tarball/v8.14.18/download.tar.gz": "8.14.18",
        }
        for url, want in cases.items():
            m = harmonybrew._URL_VER_RE.search(url)
            got = m.group(1) if m else None
            if not got:
                m2 = harmonybrew._URL_VER_SEG_RE.search(url)
                got = m2.group(1) if m2 else None
            self.assertEqual(got, want, "version of %s" % url)

    # ---- 2) 宏包装的 add_library（krita kis_add_library 实证）
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
kis_add_library(kritaui SHARED src/x.cpp)
add_executable(app src/main.cpp)
target_link_libraries(app PRIVATE kritaui zlib)
""", encoding="utf-8")
            (root / "src").mkdir()
            (root / "src" / "x.cpp").write_text("", encoding="utf-8")
            (root / "src" / "main.cpp").write_text("", encoding="utf-8")
            info = qt_scanner.scan_project(root)
            raw = {e["name"].lower() for e in info["raw_libs"]}
            self.assertNotIn("kritaui", raw)   # 宏定义的项目内目标
            self.assertIn("zlib", raw)

    # ---- 2b) set() 变量间接的 add_library（fakevim 实证）
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

    # ---- 3) find_library 参数列表里的 CMake 变量名/单字符垃圾
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

    # ---- 4) CI 脚本 apt install -y 的选项 token 不入清单
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

    # ---- 5) 共享解析阶梯（扫描期与报告期口径一致）
    def test_resolve_pkg_ladder(self):
        conn = db.connect(":memory:")
        db.init_db(conn)
        kb_seed.seed_interfaces(conn)
        for nid, name in (("hb:sqlite", "sqlite"), ("hb:fftw", "fftw"),
                          ("hb:glib", "glib"), ("cmdpkgs:gstreamer", "gstreamer"),
                          ("hb:jpeg-turbo", "jpeg-turbo")):
            db.upsert_node(conn, nid, "package", name, "harmonybrew",
                           "ported", version="1.0")
        # 同库异名（hb 包名口径别名优先，消除 sqlite3/sqlite 双产物）
        self.assertEqual(kb_seed.resolve_pkg_name(conn, "sqlite3")["id"],
                         "hb:sqlite")
        # lib 前缀剥离 + 变体后缀（libfftw3f_omp → fftw）
        self.assertEqual(kb_seed.resolve_pkg_name(conn, "libfftw3f_omp")["id"],
                         "hb:fftw")
        # pkg-config 组件名（gio-2.0 → glib；gstreamer-base → gstreamer）
        self.assertEqual(kb_seed.resolve_pkg_name(conn, "gio-2.0")["id"],
                         "hb:glib")
        self.assertEqual(kb_seed.resolve_pkg_name(conn, "gstreamer-base-1.0")["id"],
                         "cmdpkgs:gstreamer")
        # 构建形态后缀（jpeg-static → jpeg-turbo）
        self.assertEqual(kb_seed.resolve_pkg_name(conn, "jpeg-static")["id"],
                         "hb:jpeg-turbo")
        # 未命中返回 None
        self.assertIsNone(kb_seed.resolve_pkg_name(conn, "no-such-pkg"))
        conn.close()

    # ---- 5b) 扫描期幽灵节点用别名规范名（botan3/botan-3 归并）
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
            self.assertEqual(unknown, {"botan-3"})   # 两条声明同一幽灵
            conn.close()

    # ---- 6) in-tree 判定：未解析名命中项目内自带源码目录
    def test_in_tree_dir_classification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "p"
            lib = root / "src" / "libraries" / "fakevim"
            lib.mkdir(parents=True)
            for i in range(4):
                (lib / ("f%d.cpp" % i)).write_text("", encoding="utf-8")
            (lib / "CMakeLists.txt").write_text(
                "project(fakevim)\n", encoding="utf-8")
            # 依赖集合父目录需要 ≥5 个库子目录
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
            # 无同名源码目录的未解析名仍是 need_port 缺口
            self.assertEqual(link["lager"]["kind"], "package")
            self.assertFalse((link["lager"].get("artifact") or {}).get("ready"))
            conn.close()

    # ---- 6b) in-tree 不误收项目自身代码目录（krita lager/lcms 实证）
    def test_in_tree_rejects_project_code_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "p"
            d = root / "libs" / "flake" / "text" / "lager"
            d.mkdir(parents=True)
            (d / "CMakeLists.txt").write_text("", encoding="utf-8")
            (d / "CssLength.cpp").write_text("", encoding="utf-8")
            # 胶水目录（无构建文件）
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

    # ---- 7) 裸链接名命中测试框架 → test 角色
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

    # ---- 8) 编译器运行时库 → system-lib（atomic/gcov）
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
            # 系统库不产生 need_port 警告
            warn = [w for w in report["warnings"]
                    if "atomic" in w["msg"] or "gcov" in w["msg"]]
            self.assertEqual(warn, [])
            conn.close()

    # ---- 9) find_package 名经别名归并（KDcrawQt6/kdcraw 合一）
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
    """--compact 后置：`portgraph.py <cmd> --compact` 应与前置等效可用。"""

    def test_compact_after_subcommand(self):
        import subprocess
        r = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "portgraph.py"),
             "stats", "--compact"],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.strip())


if __name__ == "__main__":
    unittest.main()
