"""Harmonybrew homebrew-core formula parser (pure Python, regex + block-level state machine).

Extracts (see plan §4.1):
- Plain attributes: desc / homepage / url -> version
- Dependency edges: depends_on (including => :build/:test conditions and on_linux/on_macos platform blocks)
- Port status: an arm64_ohos: key inside the bottle do block => ported
- Platform interface binding: uses_from_macos / keg_only :provided_by_macos => iface:macos-system
- Direct bottle download (works on any platform, so non-HarmonyOS hosts can fetch deps for cross-compiling)
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import subprocess
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import HB_CORE, db

# Block context: once inside these blocks, the whole block is ignored
_IGNORE_BLOCKS = ("head", "test", "livecheck")
# do line: `<expr> do |args|`
_DO_RE = re.compile(r"^\s*(.+?)\s+do\b\s*(?:\|[^|]*\|)?\s*$")
_DEF_RE = re.compile(r"^\s*def\s+\w+")
_BLOCK_KW_RE = re.compile(r"^\s*(if|unless|case|begin|for)\b")
_END_RE = re.compile(r"^\s*end\b")
_DESC_RE = re.compile(r'^\s*desc\s+"((?:[^"\\]|\\.)*)"')
_HOMEPAGE_RE = re.compile(r'^\s*homepage\s+"([^"]+)"')
_URL_RE = re.compile(r'^\s*url\s+"([^"]+)"')
_VERSION_RE = re.compile(r'^\s*version\s+"([^"]+)"')
_DEPENDS_RE = re.compile(r'^\s*depends_on\s+(.+)$')
_USES_MACOS_RE = re.compile(r'^\s*uses_from_macos\s+(.+)$')
_KEG_ONLY_MACOS_RE = re.compile(r"^\s*keg_only\s+:provided_by_macos")
_OHOS_BOTTLE_RE = re.compile(r"arm64_ohos:\s*\"")
# head "https://github.com/x/y.git", branch: "..." -> source git repository
_HEAD_RE = re.compile(r'^\s*head\s+"([^"]+)"')
# arm64_ohos: "<sha256 digest>" -> HarmonyOS bottle artifact digest
_OHOS_BOTTLE_DIGEST_RE = re.compile(r'arm64_ohos:\s*"([0-9a-f]{64})"')
# top-level revision N -> version suffix _N (e.g. pcre2 10.47_1)
_REVISION_RE = re.compile(r"^\s*revision\s+(\d+)")
# rebuild N inside the bottle block -> file name .bottle.N.tar.gz (e.g. curl 8.21.0)
_REBUILD_RE = re.compile(r"^\s*rebuild\s+(\d+)")

# Harmonybrew public bottle download domain (downloadable directly on any platform; no brew/HarmonyOS device needed)
# Naming rule (verified in practice): <name>-<version>[_<revision>].arm64_ohos.bottle[.<rebuild>].tar.gz
# Note: a single hyphen between name and version, not Homebrew's default double hyphen
BOTTLE_DOMAIN = "https://harmonybrew.atomgit.com/bottles"

_STRING_ARG_RE = re.compile(r'^"([^"]+)"\s*(?:=>\s*(.+))?$')
# Extract the version from the url. Covers the forms seen in practice:
#   name-1.2.3.tar.gz / name_2.42.2_1.tar.xz / name-9.6p1.tgz   (separator -/_)
#   .../tags/20260817.0.tar.gz  .../tags/v1.0.2.tar.gz          (GitHub archive)
#   name-v1.5.6.tar.gz                                           (v prefix)
#   name-20260408.tar.gz                                         (date version, >=6 digits)
#   https://site/ack-v3.10.0                                     (no extension, URL ends there)
#   name-1.2.3-b2-nodocs.tar.xz / ant-1.10.18-bin.tar.xz         (name-suffix segments such
#     as -bin/-src after the version; seen with boost/antlr)
#   xxx-0.9.0.crate                                              (Rust crate)
#   ImageMagick-7.1.2-31.7z                                      (7z extension +
#     hyphenated patch-number version; seen with imagemagick/imagemagick@6; previously 7z was
#     not in the extension list and the regex took the trailing "31.7z" as the version -> bottle URL 404)
#   .../tarball/v8.14.18/download.tar.gz                         (the version is a separate
#     path segment and the file name has no version; seen with chiselapp; a fallback rule,
#     only tried when the file-name-anchored match fails)
_URL_VER_RE = re.compile(
    r"[-_/][vV]?(\d+(?:\.\d+)+(?:[a-zA-Z]\d*)?(?:[_-]\d+)?|\d{6,})"
    r"(?=(?:[-_.][A-Za-z][\w.]*)*\."
    r"(?:tar\.(?:gz|bz2|xz|lz)|t(?:gz|bz2|xz)|zip|tar|gz|bz2|xz|7z|jar|crate)"
    r"(?:[?#]|$)|$)")
# Fallback: the version is a whole path segment (v1.2.3/) and the file name has no version
_URL_VER_SEG_RE = re.compile(
    r"[-_/][vV]?(\d+(?:\.\d+)+(?:[a-zA-Z]\d*)?(?:[_-]\d+)?|\d{6,})/")

MACOS_SYSTEM_IFACE = (
    "iface:macos-system", "macOS system library binding", "os-api", "convertible",
    "The formula depends on libraries bundled with macOS; on HarmonyOS they must become explicitly packaged dependencies (mostly convertible open-source libraries)")


def bottle_url(name: str, version: Optional[str],
               revision: Optional[int] = None,
               rebuild: Optional[int] = None) -> Optional[str]:
    """Build the direct arm64-OpenHarmony bottle link; returns None when the version is missing.

    Rules verified in practice (HTTP 200):
      zlib    1.3.2            -> zlib-1.3.2.arm64_ohos.bottle.tar.gz
      curl    8.21.0 rebuild 1 -> curl-8.21.0.arm64_ohos.bottle.1.tar.gz
      pcre2   10.47  revision 1-> pcre2-10.47_1.arm64_ohos.bottle.tar.gz
      ffmpeg  9.0.1  rebuild 1 -> ffmpeg-9.0.1.arm64_ohos.bottle.1.tar.gz
      openssl@3 3.6.4          -> openssl@3-3.6.4.arm64_ohos.bottle.tar.gz
    """
    if not version:
        return None
    # Avoid duplication: a url-derived version may already carry the _N suffix (e.g. name-2.42.2_1.tar.xz)
    ver = version
    if revision and not version.endswith("_%d" % revision):
        ver = "%s_%d" % (version, revision)
    suffix = ".bottle.%d.tar.gz" % rebuild if rebuild else ".bottle.tar.gz"
    return "%s/%s-%s.arm64_ohos%s" % (BOTTLE_DOMAIN, name, ver, suffix)


def _parse_dep_arg(arg: str) -> Optional[Tuple[str, List[str]]]:
    """Parse a depends_on / uses_from_macos argument -> (package name, list of types)."""
    m = _STRING_ARG_RE.match(arg.strip())
    if not m:
        return None  # depends_on xcode:/macos:/arch: and other non-package deps
    name, arrow = m.group(1), (m.group(2) or "").strip()
    types: List[str] = ["runtime"]
    if arrow.startswith(":"):
        tag = arrow[1:].strip()
        types = [tag] if tag in ("build", "test") else ["runtime"]
    elif arrow.startswith("["):
        tags = re.findall(r":(\w+)", arrow)
        types = [t for t in tags if t in ("build", "test")] or ["runtime"]
    return name, types


def _platform_cond_of(stack: List[str]) -> Optional[str]:
    """Derive the platform condition from the block stack (HarmonyOS is in the Linux kernel family, so on_linux counts as a valid dependency)."""
    conds = []
    for ctx in stack:
        if ctx.startswith("on_linux"):
            conds.append("linux")
        elif ctx.startswith("on_macos"):
            conds.append("macos")
        elif ctx.startswith("on_system"):
            conds.append("linux+macos-old")
        elif ctx.startswith(("on_arm", "on_intel")):
            conds.append("arch")
    return "+".join(conds) if conds else None


def _unquote(s: str) -> str:
    return s.replace('\\"', '"').replace("\\\\", "\\")


def parse_formula(path: Path) -> Dict:
    """Parse a single formula file."""
    name = path.stem
    info: Dict = {
        "name": name, "desc": None, "homepage": None, "version": None,
        "url": None, "head_url": None, "deps": [], "uses_from_macos": [],
        "keg_only_macos": False, "ohos_bottle": False,
        "ohos_bottle_digest": None, "revision": None, "rebuild": None,
    }
    stack: List[str] = []       # block context stack
    ignored = 0                 # nesting depth inside ignored blocks
    in_bottle = False
    url_version: Optional[str] = None
    explicit_version: Optional[str] = None

    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if _END_RE.match(line):
            if stack:
                ctx = stack.pop()
                if ctx in _IGNORE_BLOCKS:
                    ignored -= 1
                elif ctx == "bottle":
                    in_bottle = False
            continue

        # block opening: `<expr> do |args|` / `def name` / leading if|unless|case|begin|for
        opened = None
        m = _DO_RE.match(line)
        if m:
            expr = m.group(1).strip()
            opened = expr.split()[0].split("(")[0] if expr.split() else "do"
        elif _DEF_RE.match(line):
            opened = "def"
        elif _BLOCK_KW_RE.match(line):
            opened = stripped.split()[0]

        if opened is not None:
            stack.append(opened)
            if opened in _IGNORE_BLOCKS:
                ignored += 1
            elif opened == "bottle":
                in_bottle = True
            continue

        if ignored > 0:
            continue

        # inside the bottle block: detect arm64_ohos, the artifact digest and the rebuild number
        if in_bottle:
            if _OHOS_BOTTLE_RE.search(line):
                info["ohos_bottle"] = True
            dm = _OHOS_BOTTLE_DIGEST_RE.search(line)
            if dm and info["ohos_bottle_digest"] is None:
                info["ohos_bottle_digest"] = dm.group(1)
            rm = _REBUILD_RE.match(line)
            if rm and info["rebuild"] is None:
                info["rebuild"] = int(rm.group(1))
            continue

        # scalar attributes
        m = _DESC_RE.match(line)
        if m and info["desc"] is None:
            info["desc"] = _unquote(m.group(1))
            continue
        m = _HOMEPAGE_RE.match(line)
        if m and info["homepage"] is None:
            info["homepage"] = m.group(1)
            continue
        m = _VERSION_RE.match(line)
        if m and explicit_version is None:
            explicit_version = m.group(1)
            continue
        m = _REVISION_RE.match(line)
        if m and info["revision"] is None:
            info["revision"] = int(m.group(1))
            continue
        m = _URL_RE.match(line)
        if m and info["url"] is None:
            info["url"] = m.group(1)
            if url_version is None:
                vm = _URL_VER_RE.search(m.group(1))
                if vm:
                    url_version = vm.group(1)
                elif url_version is None:
                    # fallback: the version as a separate path segment (.../tarball/v8.14.18/xx.tar.gz)
                    vm = _URL_VER_SEG_RE.search(m.group(1))
                    if vm:
                        url_version = vm.group(1)
            continue
        m = _HEAD_RE.match(line)
        if m and info["head_url"] is None:
            info["head_url"] = m.group(1)
            continue
        if _KEG_ONLY_MACOS_RE.match(line):
            info["keg_only_macos"] = True
            continue

        # dependencies (taking the enclosing platform block into account)
        cond = _platform_cond_of(stack)
        m = _DEPENDS_RE.match(line)
        if m:
            parsed = _parse_dep_arg(m.group(1))
            if parsed:
                info["deps"].append((parsed[0], parsed[1], cond))
            continue
        m = _USES_MACOS_RE.match(line)
        if m:
            parsed = _parse_dep_arg(m.group(1))
            if parsed:
                info["uses_from_macos"].append((parsed[0], parsed[1]))
            continue

    info["version"] = explicit_version or url_version
    return info


def iter_formula_files(formula_dir: Path = HB_CORE):
    return sorted(Path(formula_dir).glob("*/*.rb"))


# Harmonybrew formula main repo (sparse checkout of Formula/ only, to avoid pulling the full git history)
HB_REPO_URL = "https://atomgit.com/Harmonybrew/homebrew-core.git"


def ensure_core(repo_dir: Path = None) -> Path:
    """Clone or update Harmonybrew hb-core (blob:none shallow clone + sparse checkout of
    Formula/ only). Previously ingest silently returned 0 files when the directory was missing
    (a pitfall hit repeatedly across several test rounds); it now fetches automatically or fails explicitly."""
    dest = Path(repo_dir) if repo_dir else HB_CORE.parent
    if (dest / ".git").exists():
        subprocess.run(["git", "-C", str(dest), "pull", "--ff-only"],
                       capture_output=True, text=True, timeout=300)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(
            ["git", "clone", "--depth", "1", "--filter=blob:none",
             "--sparse", HB_REPO_URL, str(dest)],
            capture_output=True, text=True, timeout=1800)
        if r.returncode != 0:
            raise RuntimeError(
                "hb-core clone failed (%s): %s" % (HB_REPO_URL,
                                                 (r.stderr or "").strip()[:200]))
        subprocess.run(["git", "-C", str(dest), "sparse-checkout", "set",
                        "Formula"], capture_output=True, text=True,
                       timeout=300, check=True)
    return dest


def ingest(conn, formula_dir: Path = HB_CORE, limit: int = 0,
           pull: bool = False) -> Dict:
    """Parse all formulas and write them to the DB. Returns stats.

    With pull=True or a missing formula directory, hb-core is cloned/updated automatically (with
    --offline it only exits with an error when the directory is missing, instead of silently
    returning 0 files)."""
    db.init_db(conn)
    if pull or not Path(formula_dir).exists():
        try:
            ensure_core(Path(formula_dir).parent
                        if formula_dir != HB_CORE else None)
        except RuntimeError:
            if not iter_formula_files(formula_dir):
                raise   # directory still missing and no local data: fail explicitly
    files = iter_formula_files(formula_dir)
    if limit:
        files = files[:limit]

    parsed: List[Dict] = []
    errors: List[str] = []
    for f in files:
        try:
            parsed.append(parse_formula(f))
        except Exception as exc:  # a single-file failure does not block the rest
            errors.append("%s: %s" % (f.name, exc))

    names = {p["name"] for p in parsed}
    db.upsert_interface(conn, *MACOS_SYSTEM_IFACE)

    ported = 0
    for p in parsed:
        node_id = "hb:%s" % p["name"]
        status = "ported" if p["ohos_bottle"] else "unknown"
        if p["ohos_bottle"]:
            ported += 1
        if p["ohos_bottle"]:
            digest = p.get("ohos_bottle_digest")
            evidence = "arm64_ohos bottle (HarmonyOS prebuilt artifact released)"
            if digest:
                evidence += ", bottle sha256:%s..." % digest[:12]
            # the direct bottle link can be downloaded from any platform (including Windows), no brew/HarmonyOS device needed
            b_url = bottle_url(p["name"], p["version"],
                               p.get("revision"), p.get("rebuild"))
            if b_url:
                evidence += ", download: %s" % b_url
            artifact_cmd = "brew install %s" % p["name"]
        else:
            evidence = ("Harmonybrew formula exists, but there is no arm64_ohos bottle: "
                        "no HarmonyOS prebuilt artifact, must be cross-compiled yourself; "
                        "portability is decided recursively from its deps and platform interfaces")
            b_url = None
            artifact_cmd = None
        db.upsert_node(conn, node_id, "package", p["name"], "harmonybrew",
                       status, version=p["version"], description=p["desc"],
                       port_evidence=evidence,
                       links={"source_url": p["url"],
                              "repo_url": p.get("head_url"),
                              "homepage": p["homepage"],
                              "artifact_url": b_url,
                              "artifact_cmd": artifact_cmd,
                              "bottle_sha256": p.get("ohos_bottle_digest")})
        for dep_name, types, cond in p["deps"]:
            dst = "hb:%s" % dep_name
            for t in types:
                db.upsert_edge(conn, node_id, dst, t, platform_cond=cond)
        # uses_from_macos: interface binding + (if a same-named formula exists) a dependency edge
        for dep_name, types in p["uses_from_macos"]:
            db.add_node_interface(conn, node_id, MACOS_SYSTEM_IFACE[0],
                                  evidence="uses_from_macos %s" % dep_name)
            if dep_name in names:
                for t in types:
                    db.upsert_edge(conn, node_id, "hb:%s" % dep_name, t,
                                   platform_cond="macos")
        if p["keg_only_macos"]:
            db.add_node_interface(conn, node_id, MACOS_SYSTEM_IFACE[0],
                                  evidence="keg_only :provided_by_macos")

    db.set_meta(conn, "ingest_harmonybrew_at", db.now())
    db.set_meta(conn, "harmonybrew_formula_count", str(len(parsed)))
    db.set_meta(conn, "harmonybrew_ported_count", str(ported))
    conn.commit()
    return {
        "files": len(files), "parsed": len(parsed), "ported": ported,
        "errors": errors[:10], "error_count": len(errors),
        "edges_written": conn.execute(
            "SELECT COUNT(*) c FROM edges WHERE src LIKE 'hb:%'").fetchone()["c"],
    }


# ------------------------------------------------------------- bottle download
# Lets non-HarmonyOS hosts (Windows/Linux/macOS) fetch arm64-OpenHarmony deps
# for OHOS NDK cross-compiling, without brew or a HarmonyOS device.
# Flow: look up the direct link in the DB -> download -> verify sha256 -> extract -> recreate .so link names on NTFS.

_UA = {"User-Agent": "portgraph/1.0 (+bottle-fetch)"}


def _find_package(conn, name: str) -> Optional[Dict]:
    """Look up an hb package node by name/ID (supports variants like openssl@3 and fuzzy matching)."""
    for nid in (name if name.startswith("hb:") else "hb:%s" % name, name):
        node = db.get_node(conn, nid)
        if node:
            return node
    row = conn.execute(
        "SELECT id FROM nodes WHERE id LIKE 'hb:%' AND name=? LIMIT 1",
        (name,)).fetchone()
    if row:
        return db.get_node(conn, row["id"])
    # fuzzy prefix: pkg-config -> pkgconf etc.
    row = conn.execute(
        "SELECT id FROM nodes WHERE id LIKE 'hb:%' AND id LIKE ? LIMIT 1",
        ("hb:%" + name + "%",)).fetchone()
    return db.get_node(conn, row["id"]) if row else None


def _download(url: str, dest: Path, sha256: Optional[str],
              timeout: int = 300) -> None:
    """Download and verify sha256 (on mismatch, delete and raise).

    Cache hits are skipped: if dest exists and its sha256 matches (without a sha, non-empty counts
    as complete), it is not downloaded again -- this supports parallel prefetch followed by per-package
    extraction, and gives resume semantics (a rerun only fills in what is missing).
    """
    if dest.exists() and dest.stat().st_size > 0:
        if sha256:
            h = hashlib.sha256(dest.read_bytes()).hexdigest()
            if h == sha256:
                return
        else:
            return  # no sha metadata: trust the existing file; extraction failure is the fallback error
    _fetch_bytes(url, dest, timeout=timeout)
    if sha256:
        h = hashlib.sha256(dest.read_bytes()).hexdigest()
        if h != sha256:
            dest.unlink(missing_ok=True)
            raise RuntimeError("sha256 mismatch: expected %s actual %s" % (sha256, h))


def _fetch_bytes(url: str, dest: Path, timeout: int = 300) -> None:
    """Download to dest; retry once with Range on 401/403/405 or a dropped stream.

    On some networks gitcode releases reject direct requests without Range (HEAD 401, while a GET
    with `Range: bytes=0-` returns 206), and some CDNs drop long-lived connections.
    Strategy: plain GET first; on 401/403/405, or an interrupted transfer with an incomplete file,
    retry once resume-style with `Range: bytes=<bytes already present>-`.
    """
    def _attempt(headers: Dict[str, str], mode: str) -> bool:
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                # when the server ignores Range it returns 200 + the full body: appending would then
                # write the first part twice, so fall back to a truncating write.
                truncate = (mode == "ab" and getattr(resp, "status", 200) == 200
                            and dest.exists() and dest.stat().st_size > 0)
                with open(dest, "wb" if truncate else mode) as fh:
                    shutil.copyfileobj(resp, fh)
                return True
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403, 405) and mode == "wb":
                return False
            raise
        except (urllib.error.URLError, ConnectionError, OSError):
            return False

    if _attempt(dict(_UA), "wb"):
        return
    size = dest.stat().st_size if dest.exists() else 0
    headers = dict(_UA)
    headers["Range"] = ("bytes=%d-" % size) if size else "bytes=0-"
    headers.setdefault("Accept", "*/*")
    if _attempt(headers, "ab" if size else "wb"):
        return
    raise RuntimeError("download failed: %s" % url)


def _rmtree(path: Path) -> None:
    """Delete a directory tree; on Windows, read-only files of brew artifacts (mode 444/555)
    get write permission restored before deletion, otherwise PermissionError."""
    def _onerr(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=_onerr)


def _extract_with_retry(tar: tarfile.TarFile, member: tarfile.TarInfo,
                        dest: Path, attempts: int = 3) -> None:
    """Extract a single member, retrying on transient file locks (antivirus scanning a freshly written file)."""
    for i in range(attempts):
        try:
            tar.extract(member, dest, filter="data")
            return
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(0.6)


def _extract_bottle(tar_path: Path, out_dir: Path) -> Dict:
    """Extract a bottle into out_dir; returns {installed: path, symlinks_fixed: [...]}.

    Bottle layout: <name>/<version>/{lib,include,...}.
    Windows/NTFS cannot create symlinks: relative links inside the package are replaced by copies of
    their targets so that -lfoo can be resolved by the OHOS cross linker (same strategy as the KB fetch script).
    """
    symlinks_fixed: List[str] = []
    with tarfile.open(tar_path, "r:gz") as tar:
        members = tar.getmembers()
        # take the top-level <name> as the install root first
        top = members[0].name.split("/", 1)[0] if members else ""
        pending_links = []
        for m in members:
            if m.isdir():
                (out_dir / m.name).mkdir(parents=True, exist_ok=True)
            elif m.isreg():
                _extract_with_retry(tar, m, out_dir)
            elif m.issym():
                pending_links.append(m)
        # recreate symlinks: target inside the package and existing -> copy; otherwise skip.
        # linkname is relative to the link's directory (e.g. lib/libz.so -> libz.so.1.3.2)
        for m in pending_links:
            link_path = out_dir / m.name
            target = None
            if not m.linkname.startswith("/"):
                target = (link_path.parent / m.linkname).resolve()
            if target and target.is_file() and not link_path.exists():
                shutil.copy2(target, link_path)
                symlinks_fixed.append(m.name)
    installed = _locate_installed(out_dir, top)
    return {"installed": str(installed), "symlinks_fixed": symlinks_fixed}


def _locate_installed(out_dir: Path, top: str) -> Path:
    """Locate the install root that actually contains lib/include (bottles are two levels: <name>[/<version>]).

    If the top level contains lib/ or include/ -> use it; otherwise use the single subdirectory
    below it that contains lib/include (e.g. jsoncpp/1.9.8).
    """
    if not top:
        return out_dir
    top_dir = out_dir / top
    if (top_dir / "lib").is_dir() or (top_dir / "include").is_dir():
        return top_dir
    cands = [c for c in sorted(top_dir.iterdir()) if c.is_dir() and
             ((c / "lib").is_dir() or (c / "include").is_dir())]
    return cands[0] if cands else top_dir


def fetch_bottle(conn, name: str, out_dir: Path,
                 force: bool = False) -> Dict:
    """Download the arm64_ohos bottle of a Harmonybrew package and extract it into out_dir.

    Returns {package, version, bottle_url, sha256, installed, libs, hints};
    hints contains CMake/qmake integration snippets. Skipped when out_dir/<name>/<ver>/ already
    exists (force re-downloads).
    """
    node = _find_package(conn, name)
    if node is None:
        raise RuntimeError("package not found: %s (run ingest harmonybrew first; "
                           "a bare name may need an @ variant, e.g. openssl@3)" % name)
    url = node.get("artifact_url")
    if not url:
        raise RuntimeError("%s has no direct arm64_ohos bottle link (missing version or no bottle); "
                           "cross-compile from source instead" % name)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pkg_dir = out_dir / node["name"] / (node.get("version") or "")
    if pkg_dir.exists() and any(pkg_dir.iterdir()) and not force:
        return {"package": node["name"], "version": node["version"],
                "bottle_url": url, "installed": str(pkg_dir),
                "skipped": "already-exists"}

    cache = out_dir / ".cache"
    cache.mkdir(exist_ok=True)
    tar_path = cache / url.rsplit("/", 1)[-1]
    sha_full = node.get("bottle_sha256")
    _download(url, tar_path, sha_full)

    # extract into staging first, then move into place atomically on success: a failure midway leaves
    # no half-done directory, guaranteeing pkg_dir non-empty == artifact complete (so the
    # already-exists skip can be trusted)
    staging = out_dir / ".staging" / ("%s-%s" % (
        node["name"], node.get("version") or "x"))
    if staging.exists():
        _rmtree(staging)
    try:
        info = _extract_bottle(tar_path, staging)
    except Exception:
        _rmtree(staging)
        raise
    finally:
        tar_path.unlink(missing_ok=True)

    installed = Path(info["installed"])
    if pkg_dir.exists():          # force: overwrite the old artifact (may contain read-only files)
        _rmtree(pkg_dir)
    pkg_dir.parent.mkdir(parents=True, exist_ok=True)
    if installed == staging:
        # unusual layout without a top-level directory: move the contents, not the whole directory
        pkg_dir.mkdir(parents=True, exist_ok=True)
        for item in staging.iterdir():
            item.rename(pkg_dir / item.name)
        _rmtree(staging)
    else:
        installed.rename(pkg_dir)
        _rmtree(staging)
    installed = pkg_dir
    lib_dir = installed / "lib"
    libs = sorted(p.stem[3:] for p in lib_dir.glob("lib*.so")) if lib_dir.is_dir() else []
    hints = {
        "cmake": (
            "cmake -S . -B build_ohos \\\n"
            "  -DCMAKE_TOOLCHAIN_FILE=$NATIVE_OHOS_SDK/build/cmake/ohos.toolchain.cmake \\\n"
            "  -DOHOS_ARCH=arm64-v8a \\\n"
            "  -DCMAKE_PREFIX_PATH=%s \\\n"
            "  -DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=BOTH" % installed),
        "qmake": ("LIBS += -L%s/lib %s" % (
            installed, " ".join("-l%s" % l for l in libs))),
        "deploy": "deploy the .so files to entry/libs/arm64-v8a/ before they can run on the device",
    }
    return {"package": node["name"], "version": node["version"],
            "bottle_url": url, "sha256": "verified" if sha_full else "n/a",
            "installed": str(installed), "libs": libs,
            "symlinks_fixed": info["symlinks_fixed"][:10],
            "hints": hints}


def prefetch_bottles(conn, names: List[str], out_dir: Path,
                     force: bool = False, jobs: int = 8) -> Dict:
    """Prefetch the tars of several bottles into out_dir/.cache in parallel (download only, no extraction).

    Used by fetch_app_deps to pull in bulk before per-package processing -- measured on a weak
    network, serial downloads at 57KB/s dragged down the whole flow (90-minute timeout); with 8
    parallel threads the same workload takes about 8 minutes. Installed packages (pkg_dir exists)
    and cache hits (tar present with matching sha) are skipped automatically; a single failure does
    not raise (recorded in errors; the later serial phase correctly reports failed for that package).
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cache = out_dir / ".cache"
    cache.mkdir(exist_ok=True)

    plans = []          # (name, url, tar_path, sha)
    skipped_installed = 0
    for name in names:
        try:
            node = _find_package(conn, name)
        except Exception:
            node = None
        if node is None or not node.get("artifact_url"):
            continue    # lookup failed/no bottle: left for the serial phase to report as need_port
        pkg_dir = out_dir / node["name"] / (node.get("version") or "")
        if pkg_dir.exists() and any(pkg_dir.iterdir()) and not force:
            skipped_installed += 1
            continue
        tar_path = cache / node["artifact_url"].rsplit("/", 1)[-1]
        plans.append((node["name"], node["artifact_url"], tar_path,
                      node.get("bottle_sha256")))

    ok, failed = 0, []
    if plans:
        with ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
            futs = {ex.submit(_download, u, t, s): (n, u) for
                    n, u, t, s in plans}
            for fut in as_completed(futs):
                n, u = futs[fut]
                try:
                    fut.result()
                    ok += 1
                except Exception as exc:
                    failed.append({"name": n, "url": u, "error": str(exc)})
    return {"planned": len(plans), "downloaded_or_cached": ok,
            "skipped_installed": skipped_installed, "failed": failed}
