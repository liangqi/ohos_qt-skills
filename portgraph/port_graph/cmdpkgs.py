"""cmd-pkgs ingestion: parse the README tables of OpenHarmony aarch64 prebuilt packages (see plan §4.2).

README.md has two tables (language runtimes / command-line && third-party libraries), both with
columns |软件|版本|安装命令| (software | version | install command; the upstream README is in Chinese).
Listed in the table = released (port status ported). For multiple versions of the same name,
the last occurrence wins (the list is updated in order).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Dict, List

from . import CMDPKGS_DIR, OHOS_LIBS, db

REPO_URL = "https://gitcode.com/OpenHarmonyPCDeveloper/cmd-pkgs"
EXPECTED_COUNT = 1247          # number of packages declared by the README
TOLERANCE = 0.10

# The upstream cmd-pkgs README uses Chinese headers (软件 = software, 版本 = version);
# English variants are accepted too.
_HEADER_RE = re.compile(r"^\|[^|]*(?:软件|[Ss]oftware)[^|]*\|[^|]*(?:版本|[Vv]ersion)[^|]*\|")
_SEP_RE = re.compile(r"^\|[\s:|-]+\|?\s*$")

# Direct artifact link template (taken from the URL construction in cmd-pkgs/scripts/install.sh, verified)
#   URL=".../releases/download/pkgs/${NAME}-${VER}-ohos-aarch64.tar.gz"
PKG_BASE = ("https://gitcode.com/OpenHarmonyPCDeveloper/cmd-pkgs"
            "/releases/download/pkgs")
INSTALL_SH = PKG_BASE + "/install.sh"


def artifact_url(name: str, version: str) -> str:
    """Direct link to the HarmonyOS aarch64 prebuilt artifact tar.gz."""
    return "%s/%s-%s-ohos-aarch64.tar.gz" % (PKG_BASE, name, version)


def install_cmd(name: str, version: str) -> str:
    """One-line command that installs this HarmonyOS artifact."""
    return ("curl -fsSL %s | sh -s -- %s %s"
            % (INSTALL_SH, name, version))


def scan_local_artifacts(libs_dir: Path) -> Dict[str, str]:
    """Scan the locally downloaded HarmonyOS artifact directory -> {package name: local path}.

    Directories look like ohos-libs/<name>/<version>/ (the contents may nest another <version>/).
    A hit means the HarmonyOS artifact for that library is ready and can be linked directly when cross-compiling.
    """
    libs_dir = Path(libs_dir)
    found: Dict[str, str] = {}
    if not libs_dir.is_dir():
        return found
    for pkg in libs_dir.iterdir():
        if not pkg.is_dir():
            continue
        for ver in pkg.iterdir():
            if ver.is_dir():
                found[pkg.name.lower()] = str(ver)
                break
    return found


def annotate_local_artifacts(conn, libs_dir: Path) -> int:
    """Write the paths of locally ready HarmonyOS artifacts into artifact_local of same-named nodes.

    A library may have several nodes with the same name (hb:<name> / cmdpkgs:<name>); all are annotated.
    Returns the number of annotated nodes.
    """
    local = scan_local_artifacts(libs_dir)
    if not local:
        return 0
    marked = 0
    for name, path in local.items():
        for nid in ("hb:%s" % name, "cmdpkgs:%s" % name):
            node = db.get_node(conn, nid)
            if node and not node.get("artifact_local"):
                conn.execute(
                    "UPDATE nodes SET artifact_local=? WHERE id=?", (path, nid))
                marked += 1
    conn.commit()
    return marked


def crossfill_links(conn) -> int:
    """Cross-fill link info between same-named packages from different data sources.

    hb:<name> has a source link but only a brew command for the artifact; cmdpkgs:<name> has a direct
    artifact link but the README table has no source URL. After filling both ways, either node can give
    the complete "source download + HarmonyOS artifact" info. Returns the number of fields filled.

    Version-bearing fields (the URLs of artifact_url/artifact_cmd/source_url contain the version)
    are only cross-filled when both sources have the same version, so an 8.1.1 artifact link is never
    attached to a 9.0.1 node.
    """
    versioned = ("artifact_url", "artifact_cmd", "source_url")
    stable = ("repo_url", "homepage")   # version-independent, always cross-filled
    filled = 0
    rows = conn.execute(
        "SELECT name FROM nodes WHERE id LIKE 'cmdpkgs:%'").fetchall()
    for r in rows:
        name = r["name"]
        hb = db.get_node(conn, "hb:%s" % name)
        cp = db.get_node(conn, "cmdpkgs:%s" % name)
        if not hb or not cp:
            continue
        same_ver = (hb.get("version") or "") == (cp.get("version") or "")
        for f in (versioned if same_ver else ()) + stable:
            if not hb.get(f) and cp.get(f):
                conn.execute("UPDATE nodes SET %s=? WHERE id=?" % f,
                             (cp[f], "hb:%s" % name))
                filled += 1
            elif not cp.get(f) and hb.get(f):
                conn.execute("UPDATE nodes SET %s=? WHERE id=?" % f,
                             (hb[f], "cmdpkgs:%s" % name))
                filled += 1
    conn.commit()
    return filled


def ensure_repo(dest: Path = CMDPKGS_DIR) -> Path:
    """Clone or update the cmd-pkgs repository."""
    dest = Path(dest)
    if (dest / ".git").exists():
        subprocess.run(["git", "-C", str(dest), "pull", "--ff-only"],
                       capture_output=True, text=True, timeout=300)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(dest)],
                       capture_output=True, text=True, timeout=600, check=True)
    return dest


def _split_row(line: str) -> List[str]:
    """Split a table row, protecting escaped \\|."""
    protected = line.replace("\\|", "\x00")
    cells = [c.strip().replace("\x00", "|") for c in protected.strip().split("|")]
    return [c for c in cells[1:-1]] if len(cells) >= 2 else cells


def parse_readme(readme_path: Path) -> List[Dict]:
    """Parse the README tables -> [{name, version}] (for duplicate names the last version wins)."""
    entries: Dict[str, Dict] = {}
    in_table = False
    for raw in readme_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if _HEADER_RE.match(line):
            in_table = True
            continue
        if in_table and _SEP_RE.match(line):
            continue
        if in_table:
            if not line.startswith("|"):
                in_table = False
                continue
            cells = _split_row(line)
            if len(cells) < 2 or not cells[0]:
                continue
            name, version = cells[0], cells[1]
            entries[name] = {"name": name, "version": version}
    return list(entries.values())


def ingest(conn, repo_dir: Path = CMDPKGS_DIR, pull: bool = False) -> Dict:
    """Parse the README and write to the DB. Returns stats."""
    repo_dir = Path(repo_dir)
    if pull or not (repo_dir / "README.md").exists():
        ensure_repo(repo_dir)
    entries = parse_readme(repo_dir / "README.md")

    db.init_db(conn)
    for e in entries:
        db.upsert_node(
            conn, "cmdpkgs:%s" % e["name"], "package", e["name"], "cmdpkgs",
            "ported", version=e["version"],
            description="OpenHarmony aarch64 prebuilt package",
            port_evidence="cmd-pkgs README has released a HarmonyOS aarch64 prebuilt "
                          "artifact; download and install directly, no porting needed",
            links={"artifact_url": artifact_url(e["name"], e["version"]),
                   "artifact_cmd": install_cmd(e["name"], e["version"])})
    db.set_meta(conn, "ingest_cmdpkgs_at", db.now())
    db.set_meta(conn, "cmdpkgs_count", str(len(entries)))
    conn.commit()

    # Annotate locally ready HarmonyOS artifacts (ohos-libs/<name>/<version>/)
    local_marked = annotate_local_artifacts(conn, OHOS_LIBS)
    # Cross-fill source links and direct artifact links between same-named packages
    crossfilled = crossfill_links(conn)

    deviation = abs(len(entries) - EXPECTED_COUNT) / EXPECTED_COUNT
    return {
        "parsed": len(entries), "expected": EXPECTED_COUNT,
        "deviation": round(deviation, 3),
        "gate": "PASS" if deviation <= TOLERANCE else "WARN",
        "local_artifacts_marked": local_marked,
        "links_crossfilled": crossfilled,
        "sample": entries[:3],
    }
