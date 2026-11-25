# -*- coding: utf-8 -*-
"""Unit tests for parallel prefetch (prefetch_bottles) and download cache hits (_download skip).

file:// bottles, no real network dependency. Background: a full-flow test in a clean environment measured
serial downloads at 57KB/s on a weak network, sinking fetch-deps (90-minute timeout); with parallel prefetch the same workload takes about 8 minutes.
"""
import hashlib
import tarfile
import tempfile
import unittest
from pathlib import Path

from port_graph import db, harmonybrew
from tests.test_port_graph import _build_graph


def _mk_bottle_tar(tmp: Path, pkg: str, ver: str):
    root = tmp / ("src-" + pkg)
    (root / pkg / ver / "lib").mkdir(parents=True, exist_ok=True)
    so = root / pkg / ver / "lib" / ("lib%s.so" % pkg)
    so.write_bytes(("payload-" + pkg).encode())
    tar = tmp / ("%s-%s.tar.gz" % (pkg, ver))
    with tarfile.open(tar, "w:gz") as tf:
        tf.add(root / pkg, arcname=pkg)
    sha = hashlib.sha256(tar.read_bytes()).hexdigest()
    return tar, sha


def _conn_with_pkg(tmp: Path, pkg: str, ver: str, url: str, sha: str):
    conn = db.connect(":memory:")
    _build_graph(conn)
    db.upsert_node(conn, "hb:%s" % pkg, "package", pkg, "harmonybrew",
                   "ported", version=ver,
                   links={"artifact_url": url, "bottle_sha256": sha})
    return conn


class TestPrefetchBottles(unittest.TestCase):

    def test_prefetch_parallel_and_cache_hit(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            t1, s1 = _mk_bottle_tar(tmp, "pkga", "1.0")
            t2, s2 = _mk_bottle_tar(tmp, "pkgb", "2.0")
            conn = _conn_with_pkg(tmp, "pkga", "1.0", t1.as_uri(), s1)
            db.upsert_node(conn, "hb:pkgb", "package", "pkgb", "harmonybrew",
                           "ported", version="2.0",
                           links={"artifact_url": t2.as_uri(),
                                  "bottle_sha256": s2})
            out = tmp / "ohos-libs"
            r = harmonybrew.prefetch_bottles(conn, ["pkga", "pkgb"], out,
                                             jobs=2)
            self.assertEqual(r["planned"], 2)
            self.assertEqual(r["downloaded_or_cached"], 2, r["failed"])
            self.assertEqual(r["failed"], [])
            c1 = out / ".cache" / t1.name
            self.assertTrue(c1.exists())
            mtime = c1.stat().st_mtime_ns
            r2 = harmonybrew.prefetch_bottles(conn, ["pkga", "pkgb"], out,
                                              jobs=2)
            self.assertEqual(r2["downloaded_or_cached"], 2)
            # Cache hit: no re-download (mtime unchanged)
            self.assertEqual(c1.stat().st_mtime_ns, mtime)
            conn.close()

    def test_prefetch_installed_skip(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            t1, s1 = _mk_bottle_tar(tmp, "pkga", "1.0")
            conn = _conn_with_pkg(tmp, "pkga", "1.0", t1.as_uri(), s1)
            out = tmp / "ohos-libs"
            (out / "pkga" / "1.0" / "lib").mkdir(parents=True)
            r = harmonybrew.prefetch_bottles(conn, ["pkga"], out, jobs=2)
            self.assertEqual(r["skipped_installed"], 1)
            self.assertEqual(r["planned"], 0)
            conn.close()

    def test_prefetch_bad_sha_failed(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            t1, _ = _mk_bottle_tar(tmp, "pkga", "1.0")
            conn = _conn_with_pkg(tmp, "pkga", "1.0", t1.as_uri(),
                                  "dead" * 16)
            out = tmp / "ohos-libs"
            r = harmonybrew.prefetch_bottles(conn, ["pkga"], out, jobs=2)
            self.assertEqual(len(r["failed"]), 1)
            self.assertEqual(r["failed"][0]["name"], "pkga")
            # The bad file was deleted; no polluted cache left behind
            self.assertFalse((out / ".cache" / t1.name).exists())
            conn.close()

    def test_download_no_sha_trusts_existing(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            f = tmp / "no_sha.bin"
            f.write_bytes(b"x")
            mtime = f.stat().st_mtime_ns
            harmonybrew._download(tmp.as_uri() + "/no_sha.bin", f, None)
            # No sha metadata: trust it if it exists, no re-download
            self.assertEqual(f.stat().st_mtime_ns, mtime)


if __name__ == "__main__":
    unittest.main()
