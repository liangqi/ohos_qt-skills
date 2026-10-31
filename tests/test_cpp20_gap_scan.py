# -*- coding: utf-8 -*-
"""cpp20-gap-scan 单元测试。"""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "cpp20_gap_scan", Path(__file__).resolve().parent.parent / "tools" / "cpp20-gap-scan.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class TestScan(unittest.TestCase):
    def _scan(self, code: str):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "t.cpp"
            f.write_text(code, encoding="utf-8")
            return {(rid, ln) for rid, ln, _ in MOD.scan_file(f)}

    def test_gap02_make_unique_for_overwrite(self):
        hits = self._scan(
            "auto buf = std::make_unique_for_overwrite<std::uint8_t[]>(size);\n")
        self.assertIn(("GAP-02", 1), hits)

    def test_gap02_fix_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "t.cpp"
            f.write_text(
                "auto a = std::make_unique_for_overwrite<char[]>(n);\n"
                "auto b = std::make_unique_for_overwrite<Foo>();\n",
                encoding="utf-8")
            new, n = MOD.MUFO_RE.subn(MOD._mugo_repl, f.read_text(encoding="utf-8"))
            self.assertEqual(n, 2)
            self.assertIn("std::unique_ptr<char[]>(new char[n])", new)
            self.assertIn("std::unique_ptr<Foo>(new Foo())", new)
            # 幂等：再扫无命中
            f.write_text(new, encoding="utf-8")
            self.assertNotIn("GAP-02", {r for r, _, _ in MOD.scan_file(f)})

    def test_gap01_structured_binding_capture(self):
        hits = self._scan(
            "auto [widget, animate] = CreateIcon();\n"
            "_anim = [animate] { widget->run(); };\n")
        self.assertIn(("GAP-01", 2), hits)
        # init-capture 安全，不报
        hits2 = self._scan(
            "auto [widget, animate] = CreateIcon();\n"
            "_anim = [h = animate] { h(); };\n")
        self.assertNotIn(("GAP-01", 2), hits2)

    def test_gap03_stop_token(self):
        hits = self._scan("#include <stop_token>\nstd::stop_token tok;\n")
        self.assertIn(("GAP-03", 2), hits)

    def test_gap04_atomic_ref(self):
        hits = self._scan("std::atomic_ref<int> r{x};\n")
        self.assertIn(("GAP-04", 1), hits)

    def test_gap05_ranges(self):
        hits = self._scan("if (std::ranges::any_of(v, p)) {}\n")
        self.assertIn(("GAP-05", 1), hits)

    def test_gap07_init_capture_only(self):
        hits = self._scan("auto f = [peer_ = peer] { _deliveryReportSent.remove(peer_); };\n")
        self.assertIn(("GAP-07", 1), hits)
        # [=, x=y] 与 [&] 不报
        hits2 = self._scan("auto g = [=, peer_ = peer] { use(peer_); };\n"
                           "auto h = [&] { x(); };\n")
        self.assertEqual([r for r, _, _ in hits2], [])

    def test_gap08_setaffinity(self):
        hits = self._scan("pthread_setaffinity_np(t, s, m);\n")
        self.assertIn(("GAP-08", 1), hits)

    def test_clean_file_no_hits(self):
        hits = self._scan("int main() { return 0; }\n")
        self.assertEqual(hits, set())


if __name__ == "__main__":
    unittest.main()
