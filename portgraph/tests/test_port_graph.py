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
            # 7z 扩展名 + 连字符补丁号版本（imagemagick 7.1.2-31 实证，
            # 修复前退化为尾部 "31.7z" → bottle URL 404）
            "https://github.com/ImageMagick/ImageMagick/releases/download/7.1.2-31/ImageMagick-7.1.2-31.7z": "7.1.2-31",
            "https://github.com/ImageMagick/ImageMagick6/releases/download/6.9.13-56/ImageMagick-6.9.13-56.7z": "6.9.13-56",
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


# ------------------------------------------------- e2e qbittorrent 复盘修复

class TestCmakeOptionGuard(unittest.TestCase):
    """OFF 默认 CMake 选项守卫内的 find_package/pkg_check_modules 标 optional。

    取证样本：qBittorrent dist/unix/CMakeLists.txt 的 if (SYSTEMD)
    （SYSTEMD 由 feature_option_dependent 声明且默认 OFF）。同时覆盖
    dist/ 目录不再被排除（add_subdirectory(dist) 是真实构建子目录）。
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
        # dist/ 内的 CMakeLists 不应再被排除
        (root / "dist" / "unix" / "CMakeLists.txt").write_text(
            self.DIST_CMAKE, encoding="utf-8")
        # Find 模块文件：find_package(Systemd) optional → 整个模块继承
        (root / "cmake" / "Modules" / "FindSystemd.cmake").write_text(
            self.FIND_MODULE_CMAKE, encoding="utf-8")
        # macro 体内的声明：调用点生效，不标 optional
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
            # SYSTEMD 默认 OFF → find_package(Systemd) optional
            self.assertIn("systemd", cp["find_package_optional"])
            self.assertNotIn("systemd", cp["find_package"])
            # Find<systemd>.cmake 模块继承 optional（pkg_check_modules）
            self.assertIn("systemd", cp["pkg_check_modules_optional"])
            self.assertNotIn("systemd", cp["pkg_check_modules"])
            # pkg_modules 条目带 optional 标志
            pm = {d["name"]: d for d in cp["pkg_modules"]}
            self.assertTrue(pm["systemd"].get("optional"))
            # 默认 ON 的选项（DBUS/WEBUI）与无条件声明 → 必需
            self.assertIn("boost", cp["find_package"])
            self.assertNotIn("boost", cp["find_package_optional"])
            self.assertNotIn("dbus", cp["find_package"])
            # STACKTRACE 默认 OFF → optional
            self.assertIn("libunwindstacktrace",
                          cp["find_package_optional"])
            # macro 体内的声明不标 optional（调用点上下文未知）
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
    """optional 边不进入 runtime 闭包与可移植性分析（e2e systemd 误报修复）。"""

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
            # 可移植性分析不沿 optional 边递归（不产生 unknown）
            analysis = engine.analyze(conn, scan["app_id"])
            self.assertEqual(
                [u["node"] for u in analysis["unknowns"]], [])
            # fetch-deps 闭包不含 optional 依赖
            closure = deps_fetch.dependency_closure(conn, scan["app_id"])
            ids = [n["id"] for n in closure]
            self.assertNotIn("pkg-unknown:systemd", ids)
            self.assertIn("hb:zlib", ids)
            # 扫描摘要区分 optional / unknown
            self.assertEqual(scan["deps_unknown"], [])
            self.assertEqual([d["hint"] for d in scan["deps_optional"]],
                             ["systemd"])
            conn.close()


class TestDashlessSameLibMerge(unittest.TestCase):
    """同库异名归并：find_package CamelCase 压平名与 pkg-config 连字符名
    不产生重复幽灵节点；包库有对应包时能兑底解析（e2e libtorrentrasterbar
    幽灵节点修复）。"""

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
            # 只产生一个 libtorrent 幽灵节点（boost 无包源，另算一个），
            # 代表名为 pkg-config 连字符口径
            self.assertEqual(
                [d["node"] for d in scan["deps_unknown"]
                if "torrent" in d["node"]],
                ["pkg-unknown:libtorrent-rasterbar"])
            lt = next(d for d in scan["deps_unknown"]
                      if d["node"] == "pkg-unknown:libtorrent-rasterbar")
            self.assertEqual(lt["merged_from"], ["libtorrentrasterbar"])
            edges = [e for e in db.out_edges(conn, scan["app_id"])
                     if e["dst"].startswith("pkg-unknown:")]
            self.assertEqual(len(edges), 2)   # boost + 合并后的 libtorrent
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
            # 压平名兑底解析到连字符包名 → 无 libtorrent 幽灵节点
            self.assertEqual(
                [d for d in scan["deps_unknown"]
                 if "torrent" in d["node"]], [])
            linked = {d["hint"]: d for d in scan["deps_linked"]}
            self.assertEqual(linked["libtorrent-rasterbar"]["node"],
                             "hb:libtorrent-rasterbar")
            conn.close()

    def test_dashless_alias_for_collapsed_only_name(self):
        """仅有 find_package 压平名时，兑底解析到连字符包名并标注 alias。"""
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
        """短名（<6 字符）不走兑底匹配，避免碰撞误映射。"""
        node = kb_seed.resolve_package_dashless(None, "zlib")
        self.assertIsNone(node)

    def test_dashless_index_excludes_ghost_nodes(self):
        """pkg-unknown 幽灵节点不入索引：避免上一次扫描的幽灵
        被下一次扫描当作已知包解析（deps CLI 写主库后复现）。"""
        conn = db.connect(":memory:")
        db.init_db(conn)
        db.upsert_node(conn, "pkg-unknown:libtorrent-rasterbar", "package",
                       "libtorrent-rasterbar", "scan", "unknown")
        node = kb_seed.resolve_package_dashless(conn, "libtorrentrasterbar")
        self.assertIsNone(node)
        conn.close()


class TestE2ENameVariants(unittest.TestCase):
    """e2e harness 取证变体：含 @version 的节点名（openssl@3）需追加剥离
    变体，否则 grep 不到 find_package(OpenSSL) 原始声明（误判 false-positive）。"""

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
        # oracle 侧不变：仅节点侧追加剥离变体
        self.assertIn("openssl", e2e.name_variants("OpenSSL >= 3.0"))


if __name__ == "__main__":
    unittest.main()


# =====================================================================
# e2e tdesktop（tier C）deps-test 轮新增：external_* 导入目标链接解析、
# 构建工具过滤、vendored 子模块抑制、win32 系统库防误连、harness 取证
# =====================================================================

def _load_e2e_harness():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "run_e2e", PROJECT_ROOT / "tests" / "e2e" / "run_e2e.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestExternalTargetLinks(unittest.TestCase):
    """target_link_libraries 的 ns::external_<name> 导入目标解析
    （tdesktop 全部三方库走这条路，find_package 位于 cmake_helpers）。"""

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
  PkgConfig::TDESKTOP_UDEV
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
            # external_ 前缀剥除 + ext_target 高置信标记
            for n in ("zlib", "openal", "webrtc"):
                self.assertIn(n, raw, "missing %s" % n)
                self.assertTrue(raw[n].get("ext_target"))
                self.assertIn("external-target",
                              " ".join(raw[n]["hows"]))
            # 非 external_ 的命名空间目标 / Qt / PkgConfig / 项目内目标跳过
            for n in ("lib_base", "qt5::core", "qt_static_plugins",
                      "external_foo", "foo", "pkgconfig"):
                self.assertNotIn(n, raw)
            # 裸名仍走原通道
            self.assertIn("z", raw)
            self.assertFalse(raw["z"].get("ext_target"))

    def test_graph_links_and_ghosts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._project(Path(tmp))
            # vendored 子模块：external_cmark_gfm 对应 .gitmodules 条目
            (root / ".gitmodules").write_text(
                '[submodule "ThirdParty/cmark-gfm"]\n'
                "\tpath = Telegram/ThirdParty/cmark-gfm\n"
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
            # 已知包连边（openal 经 PKG_ALIASES → openal-soft）
            self.assertEqual(linked["zlib"]["node"], "hb:zlib")
            self.assertEqual(linked["openal"]["node"], "cmdpkgs:openal-soft")
            self.assertEqual(linked["openal"]["alias"], "openal-soft")
            self.assertEqual(linked["openal"]["via"], "external-target")
            unknown = {d["hint"] for d in scan["deps_unknown"]}
            # 未解析的 external_ 声明 → 幽灵节点（高置信）
            self.assertIn("webrtc", unknown)
            # vendored 子模块命中 → 不建幽灵（随项目编译）
            self.assertNotIn("cmark_gfm", unknown)


class TestBuildToolFindpkgFilter(unittest.TestCase):
    """find_package(Python3) 等构建工具不建运行时边（此前产生
    pkg-unknown:python3 幽灵，e2e 报假 resolution-gap）。"""

    def test_python3_not_runtime_edge(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "codegen"
            root.mkdir()
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.16)\nproject(Gen)\n"
                "find_package(Python3 REQUIRED)\n"
                "pkg_check_modules(UDEV REQUIRED IMPORTED_TARGET libudev)\n",
                encoding="utf-8")
            conn = db.connect(":memory:")
            db.init_db(conn)
            kb_seed.seed_interfaces(conn)
            scan = project_scanner.scan_project(conn, root)
            hints = {d["hint"] for d in scan["deps_unknown"]}
            self.assertNotIn("python3", hints)
            edges = {e["dst"] for e in db.out_edges(conn, scan["app_id"])}
            self.assertNotIn("pkg-unknown:python3", edges)
            # 真实运行时依赖（pkg-config 名）仍建幽灵
            self.assertIn("libudev", hints)
            self.assertIn("pkg-unknown:libudev", edges)
            conn.close()


class TestWin32LibNoFalseEdge(unittest.TestCase):
    """win32 系统库名（bcrypt/hid/...）不因同名 Unix 库误连边。"""

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


class TestPkgAliasesTdesktop(unittest.TestCase):
    """e2e tdesktop 复核确认的别名缺口（external_* 裸名 → 鸿蒙包）。"""

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
            self.assertIsNotNone(node, "%s 未解析" % name)
            self.assertEqual(node["id"], want)
        conn.close()


class TestE2eHarnessDepsTest(unittest.TestCase):
    """harness（run_e2e）取证与归类修正：
    词界环视、分隔符折叠、幽灵判定（resolution-gap vs unknown-ok）、
    vendored 子模块归类。"""

    @classmethod
    def setUpClass(cls):
        cls.h = _load_e2e_harness()

    def test_grep_boundary_matches_prefixed_target(self):
        # \b 词界匹配不到 external_xxhash / lib_zlib；环视边界可以
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "CMakeLists.txt").write_text(
                "target_link_libraries(Telegram PRIVATE "
                "desktop-app::external_xxhash lib_zlib)\n",
                encoding="utf-8")
            ev = self.h.grep_dep_refs(repo, self.h.name_variants("xxHash"))
            self.assertGreaterEqual(ev["strong"], 1)
            ev2 = self.h.grep_dep_refs(repo, ["zlib"])
            self.assertGreaterEqual(ev2["strong"], 1)
            # 词界保护不能误伤：zlib 不得命中 zlibng 之类连写
            (repo / "CMakeLists.txt").write_text(
                "target_link_libraries(x PRIVATE zlibng)\n", encoding="utf-8")
            ev3 = self.h.grep_dep_refs(repo, ["zlib"])
            self.assertEqual(ev3["strong"], 0)

    def test_grep_multiline_tll(self):
        # tll 每个链接项独占一行：逐行匹配会漏证据，需全文匹配
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "CMakeLists.txt").write_text(
                "target_link_libraries(Telegram\nPRIVATE\n"
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
        # 形近包存在（openal ⊂ openal-soft，分量交集）→ 真解析缺口
        hit = self.h.ghost_plausible_package(conn, "openal")
        self.assertIsNotNone(hit)
        self.assertEqual(hit["id"], "hb:openal-soft")
        # lib 前缀折叠后相等 → 真解析缺口
        hit2 = self.h.ghost_plausible_package(conn, "xkbcommon")
        self.assertIsNotNone(hit2)
        # 无形近包（udev ⊄ uudeview：无分隔分量交集）→ 幽灵为正确检出
        self.assertIsNone(self.h.ghost_plausible_package(conn, "libudev"))
        self.assertIsNone(self.h.ghost_plausible_package(conn, "webrtc"))
        conn.close()

    def test_vendored_submodule_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".gitmodules").write_text(
                '[submodule "ThirdParty/GSL"]\n'
                "\tpath = Telegram/ThirdParty/GSL\n"
                "\turl = https://github.com/Microsoft/GSL.git\n"
                '[submodule "ThirdParty/xxHash"]\n'
                "\tpath = Telegram/ThirdParty/xxHash\n"
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
        # nayuki QR-Code-generator = cmd-pkgs libqrcodegen（版本同源 1.8.0）
        self.assertEqual(self.h.canon_of("QR Code generator"),
                         "libqrcodegen")


class TestPkgConfigVersionSuffixResolve(unittest.TestCase):
    """pkg-config 版本后缀名（lilv-0/glib-2.0）在图侧也解析到包
    （此前仅 deps_report._resolve 支持，图侧产生幽灵节点，
    e2e musescore 复核确认）。"""

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
        # lib 前缀近似也统一到 resolve_package
        self.assertEqual(kb_seed.resolve_package(conn, "xkbcommon")["id"],
                         "hb:libxkbcommon")
        # 无形近包仍返回 None（保持幽灵行为）
        self.assertIsNone(kb_seed.resolve_package(conn, "suil-0"))
        conn.close()

class TestBuildscriptsDirNotExcluded(unittest.TestCase):
    """build* 前缀误排除修复：buildscripts/buildtools 是源码目录必须扫描，
    build/build-Debug 等构建输出目录仍排除（e2e musescore 根因）。"""

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
            self.assertNotIn("out", fp)       # build/ 与 build-Debug/ 排除


class TestVendoredCmakeSkip(unittest.TestCase):
    """vendored/依赖引擎目录内的 CMake 声明与注释行不算应用依赖
    （e2e musescore：thirdparty/fluidsynth、KDDockWidgets/python、
    muse_deps/recipes 污染 depth-1；注释行 find_package 误匹配）。"""

    def _project(self, tmp: Path):
        root = tmp / "vend"
        # 内嵌三方自己的 find_package（不应计入）
        p = root / "framework/audio/thirdparty/fluidsynth/CMakeLists.txt"
        p.parent.mkdir(parents=True)
        p.write_text(
            "find_package(GLib2 REQUIRED)\n"
            "find_package(Lash)\n"
            "# Exported targets for cmake: find_package(FluidSynth)\n",
            encoding="utf-8")
        # 依赖引擎子模块 recipes 的系统模式回退（不应计入）
        p = root / "muse_deps/recipes/lv2sdk/meta.cmake"
        p.parent.mkdir(parents=True)
        p.write_text(
            "pkg_check_modules(lv2sdk_system REQUIRED IMPORTED_TARGET "
            "lilv-0 suil-0 lv2)\n", encoding="utf-8")
        # 内嵌三方的 include 也不算 hint 证据
        p = root / "thirdparty/kdw/util.h"
        p.parent.mkdir(parents=True)
        p.write_text("#include <uuid/uuid.h>\n", encoding="utf-8")
        # 应用自身声明（应计入）
        (root / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.16)\nproject(Vend)\n"
            "find_package(Jack REQUIRED)\n"
            "# find_package(Commented)\n"
            "find_package(Git REQUIRED)\n",   # VCS 构建工具应跳过
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


class TestRequireDepManifest(unittest.TestCase):
    """依赖清单函数检测（muse_deps 引擎）：require_dep/require_source_dep/
    require_tool → link/vendored/tool 三种角色；条件块标注。"""

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
if (MUSE_MODULE_AUDIO_PIPEWIRE)
    require_dep(pipewire)
endif()
"""

    def _project(self, tmp: Path):
        root = tmp / "mdep"
        # 引擎定义在依赖子模块（vendored 路径）：定义可用，但其中调用不扫
        p = root / "muse_deps/buildtools/manifest.cmake"
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
            # 条件块标注：不求值，只标注
            self.assertTrue(md["pipewire"]["conditional"])
            self.assertIn("MUSE_MODULE_AUDIO_PIPEWIRE",
                          md["pipewire"]["condition"])
            # STATIC 等模式参数不是依赖名；引擎内部调用不扫
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
            # require_dep → runtime 边（已解析包）
            self.assertEqual(edges.get("hb:zlib"), "runtime")
            # require_source_dep → vendored 边（幽灵节点 + vendored 描述）
            self.assertEqual(edges.get("pkg-unknown:kddockwidgets"),
                             "vendored")
            # require_tool 不连边
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
            # 条件块声明的 required=False
            by_name = {d["name"]: d for d in report["link_deps"]}
            self.assertFalse(by_name["pipewire"]["required"])


class TestFetchVendoredRole(unittest.TestCase):
    """fetch-deps：vendored 边（require_source_dep）→ status/role=vendored，
    不下载、不下钻其传递依赖。"""

    def test_vendored_not_need_port(self):
        conn = db.connect(":memory:")
        db.init_db(conn)
        kb_seed.seed_interfaces(conn)
        db.upsert_node(conn, "app:x", "app", "x", "scan", "unknown")
        db.upsert_node(conn, "hb:vend1", "package", "vend1",
                       "harmonybrew", "ported")
        db.upsert_node(conn, "pkg-unknown:vend2", "package", "vend2",
                       "scan", "unknown")
        # vend2 自身的 runtime 依赖（闭包不应包含）
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
        self.assertNotIn("vend2child", by_name)   # vendored 不下钻
        self.assertEqual(manifest["summary"].get("vendored"), 2)
        conn.close()


class TestQtComponentsListVar(unittest.TestCase):
    """set(<var> Core Gui ...) + list(APPEND) + find_package(Qt6 COMPONENTS
    ${var}) 的组件展开（muse SetupQt6.cmake 形式）；同名变量跨文件并集，
    与目录遍历顺序无关。"""

    def _project(self, tmp: Path):
        root = tmp / "qtcomp"
        root.mkdir(parents=True)
        (root / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.16)\nproject(QtComp)\n"
            "set(qt_components\n    Core\n    Gui\n    Widgets\n)\n"
            "list(APPEND qt_components Network)\n"
            "find_package(Qt6 6.8 REQUIRED COMPONENTS ${qt_components})\n",
            encoding="utf-8")
        # sandbox 等旁支目录的同名变量：并集去重，不遮蔽主声明
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


class TestMusescoreAliasResolution(unittest.TestCase):
    """e2e musescore 确认的别名缺口：CMake 模块名/依赖清单名 → hb 包名，
    扫描期解析不产生幽灵节点。"""

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
    """clone 复用时应补拉 submodule（musescore 依赖清单在 muse_deps/muse
    submodule 内，不初始化则扫描不到）；无 submodule/失败时静默降级。"""

    def test_reused_clone_inits_submodules_silently(self):
        from port_graph import cloner
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "subproj"
            root.mkdir()
            # 伪造已有克隆：.git 目录 + .gitmodules（内容指向不存在的子模块）
            (root / ".git").mkdir()
            (root / "CMakeLists.txt").write_text(
                "project(Sub)\n", encoding="utf-8")
            (root / ".gitmodules").write_text(
                '[submodule "muse_deps"]\n'
                '\tpath = muse_deps\n'
                '\turl = https://example.invalid/muse_deps.git\n',
                encoding="utf-8")
            orig_ws = cloner.WORKSPACE
            cloner.WORKSPACE = Path(tmp)   # 克隆目标指到临时 workspace
            try:
                info = cloner.clone_repo("https://github.com/x/subproj",
                                         name="subproj")
            finally:
                cloner.WORKSPACE = orig_ws
            # 目录已存在 → 复用，且 submodule init 失败（无效 URL）不抛异常
            self.assertFalse(info["cloned"])
            self.assertEqual(info["path"], str(root))

    def test_no_gitmodules_noop(self):
        from port_graph import cloner
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "plain"
            root.mkdir()
            (root / ".git").mkdir()
            # 无 .gitmodules → 直接返回，不执行 git 命令
            cloner._init_submodules(root, 10)
            self.assertTrue((root / ".git").is_dir())
