"""Recursive portability inference engine (plan §3.2 / §5.1).

Rules:
  portable(n) = n's own status is ported
             AND all of n's platform interfaces are in {supported, convertible}
             AND all of n's effective dependencies (runtime/uses-module, excluding macos-conditional ones) are recursively portable
  blocked    = any hard condition fails (blocked dependency / unsupported interface / unsupported module)
  uncertain  = no hard blocker, but there are unknown dependencies or interfaces

Special case: interfaces wrapped in non-HarmonyOS platform conditional-compilation guards (guard=platform-excluded)
  -> not compiled in HarmonyOS builds, so not counted as hard blockers
  -> but recorded in platform_excluded, with an analysis of whether their functional category has a HarmonyOS alternative interface

Recursion follows only runtime / uses-module edges; build/test edges do not take part in the verdict.
Dependencies with platform_cond == "macos" are not needed on HarmonyOS and are skipped.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from . import db

RECURSE_EDGE_TYPES = ("runtime", "uses-module")
_SKIP_PLATFORM_CONDS = ("macos",)

KIND_LABELS = {
    "qt-module": "Unsupported Qt module",
    "package": "Blocked dependency package",
    "app": "Blocked dependency app",
}

_GUARD_RE = re.compile(r"guard=(\S+)")
# Matches the counts in an evidence string:
#   (A unconditional / B OHOS-compilable / C macro-guard excluded / D file-level excluded)
# The legacy Chinese wording (A 处无条件 / B 处鸿蒙可编译 / C 处宏守卫排除 / D 处文件级排除)
# is still accepted so databases scanned by older versions keep working.
_COUNT_RE = re.compile(
    r"\((\d+)\s*(?:处无条件|unconditional)\s*/\s*"
    r"(\d+)\s*(?:处鸿蒙可编译|OHOS-compilable)\s*/\s*"
    r"(\d+)\s*(?:处宏守卫排除|macro-guard excluded)\s*/\s*"
    r"(\d+)\s*(?:处文件级排除|file-level excluded)\)")


def _risk_from_evidence(evidence: str) -> Optional[str]:
    """Estimate the modification risk level from the hit distribution.

    risk = (unconditional + OHOS-compilable) / total hits
      - >= 0.8 -> high (most of the code compiles on HarmonyOS, needs heavy rewriting)
      - 0.3 ~ 0.8 -> medium
      - < 0.3 -> low (mostly excluded by platform guards, only minor adaptation needed)
    """
    if not evidence:
        return None
    m = _COUNT_RE.search(evidence)
    if not m:
        return None
    uncond, active, macro_excl, file_excl = map(int, m.groups())
    total = uncond + active + macro_excl + file_excl
    if total == 0:
        return None
    ratio = (uncond + active) / total
    if ratio >= 0.8:
        return "high"
    if ratio >= 0.3:
        return "medium"
    return "low"


class _Cache:
    def __init__(self):
        self.status: Dict[str, str] = {}
        self.blockers: Dict[str, List[Dict]] = {}
        self.unknowns: Dict[str, List[Dict]] = {}
        self.platform_excluded: Dict[str, List[Dict]] = {}
        self.on_stack: List[str] = []
        self.cycles: List[List[str]] = []


def _parse_guard(evidence: str) -> str:
    """Extract the guard state from an evidence string; defaults to ohos-active."""
    if not evidence:
        return "ohos-active"
    m = _GUARD_RE.search(evidence)
    return m.group(1) if m else "ohos-active"


def _find_ohos_alternatives(iface: Dict, alt_by_cat: Dict[str, List[Dict]]) -> List[Dict]:
    """Find HarmonyOS-supported/convertible alternative interfaces in the same functional category (using the precomputed index)."""
    cat = iface.get("category")
    if not cat:
        return []
    return [a for a in alt_by_cat.get(cat, []) if a["id"] != iface["id"]]


def _node_blocker(conn, node: Dict, iface_status_map: Dict) -> Optional[Dict]:
    """Hard blocker arising from the node's own base status (no dependency recursion)."""
    if node["kind"] in ("app", "framework"):
        return None  # the status of app / framework subprojects is computed recursively by this engine
    if node["port_status"] == "blocked":
        reason = node.get("port_evidence") or "base status is blocked"
        kind = ("unsupported-module" if node["kind"] == "qt-module"
                else "blocked-package")
        return {"node": node["id"], "name": node["name"], "kind": kind,
                "reason": reason, "artifact": artifact_info(node)}
    return None


def artifact_info(node: Dict) -> Dict:
    """Summarize a node's HarmonyOS artifact and source link info.

    ready=True    a directly usable HarmonyOS artifact exists (no porting needed)
    provided=True provided by Qt / the HarmonyOS framework itself (e.g. Qt modules); no separate download or porting needed
    both False    no artifact; must be cross-compiled yourself, portability is decided recursively from dependencies/interfaces
    """
    url = node.get("artifact_url")
    cmd = node.get("artifact_cmd")
    local = node.get("artifact_local")
    kind = node.get("kind")
    status = node.get("port_status")
    provided = kind in ("qt-module", "platform-api") or (
        status == "ported" and not (url or cmd or local))
    return {
        "ready": bool(url or cmd or local),
        "provided": provided,
        "artifact_url": url,        # direct link to the HarmonyOS artifact (cmd-pkgs tar.gz)
        "artifact_cmd": cmd,        # command to obtain the artifact (brew install / install.sh)
        "artifact_local": local,    # path of the locally ready artifact
        "source_url": node.get("source_url"),   # source download URL
        "repo_url": node.get("repo_url"),       # source git repository
        "homepage": node.get("homepage"),       # project homepage
    }


def _evaluate(conn, node_id: str, cache: _Cache,
              iface_map: Dict[str, Dict],
              alt_by_cat: Dict[str, List[Dict]]) -> str:
    """Return portable / blocked / uncertain and fill the per-node blocker lists in cache."""
    if node_id in cache.status:
        return cache.status[node_id]
    if node_id in cache.on_stack:
        cache.cycles.append(cache.on_stack[cache.on_stack.index(node_id):]
                            + [node_id])
        cache.status.setdefault(node_id, "portable")
        cache.blockers.setdefault(node_id, [])
        cache.unknowns.setdefault(node_id, [])
        cache.platform_excluded.setdefault(node_id, [])
        return "portable"  # treat as passing inside a cycle to avoid infinite recursion

    cache.on_stack.append(node_id)
    blockers: List[Dict] = []
    unknowns: List[Dict] = []
    platform_excluded: List[Dict] = []

    node = db.get_node(conn, node_id)
    if node is None:
        blockers.append({"node": node_id, "name": node_id,
                         "kind": "missing-node", "reason": "dependency node does not exist"})
        status = "blocked"
    else:
        status = "portable"
        base = _node_blocker(conn, node, iface_map)
        if base:
            blockers.append(base)
            status = "blocked"
        elif (node["port_status"] == "unknown"
              and node["kind"] not in ("app", "framework")):
            art = artifact_info(node)
            if art["ready"]:
                reason = "HarmonyOS artifact already available (%s), no porting needed" % (
                    art["artifact_url"] or art["artifact_cmd"]
                    or art["artifact_local"])
            else:
                reason = ("no HarmonyOS prebuilt artifact, must be cross-compiled and ported yourself; "
                          + (node.get("port_evidence") or "porting status unknown"))
            hints: List[str] = []
            if node_id.startswith("pkg-unknown:"):
                # Distinguish "the knowledge base lacks this package" from "the name did not match":
                # give candidates for the latter, instead of hiding every naming issue behind "port it yourself"
                try:
                    from . import kb_seed as _kb
                    hints = _kb.suggest_packages(conn, node["name"])
                except Exception:
                    hints = []
                if hints:
                    reason += ("; the knowledge base has similar packages %s, the name may simply not match"
                               " (confirm the dependency name/version before deciding to port)"
                               % ", ".join(hints))
            unknowns.append({
                "node": node_id, "name": node["name"],
                "kind": ("unknown-package" if node["kind"] == "package"
                         else "unknown-status"),
                "reason": reason,
                "artifact": art,
                "name_hints": hints})

        # Platform interface checks
        for ni in db.node_interfaces(conn, node_id):
            ist = ni["ohos_status"]
            guard = _parse_guard(ni.get("evidence"))
            if ist == "unsupported" and guard == "platform-excluded":
                # wrapped in a non-HarmonyOS platform guard, not compiled on HarmonyOS -> not a hard blocker
                alts = _find_ohos_alternatives(ni, alt_by_cat)
                platform_excluded.append({
                    "node": node_id, "name": node["name"],
                    "iface": ni["name"], "category": ni.get("category"),
                    "guard": guard,
                    "reason": "interface %s is wrapped in a non-HarmonyOS platform conditional-compilation guard (not compiled on HarmonyOS)"
                              ", functional category=%s" % (ni["name"], ni.get("category")),
                    "alternatives": alts,
                    "evidence": ni.get("evidence", "")})
            elif ist == "unsupported":
                alts = _find_ohos_alternatives(ni, alt_by_cat)
                reason = "uses platform interface %s unsupported on HarmonyOS (%s) %s" % (
                    ni["name"], ni.get("category") or "",
                    ni.get("note") or "")
                if alts:
                    alt_names = ", ".join(a["name"] for a in alts)
                    reason += "; HarmonyOS alternative interfaces in the same category: %s" % alt_names
                if ni.get("evidence"):
                    reason += " [evidence: %s]" % ni["evidence"]
                blockers.append({
                    "node": node_id, "name": node["name"],
                    "kind": "unsupported-interface", "reason": reason,
                    "guard": guard, "alternatives": alts,
                    "risk": _risk_from_evidence(ni.get("evidence"))})
                status = "blocked"
            elif ist == "unknown":
                unknowns.append({
                    "node": node_id, "name": node["name"],
                    "kind": "unknown-interface",
                    "reason": "HarmonyOS support for platform interface %s is unconfirmed (guard=%s)"
                              % (ni["name"], guard)})

        # Dependency recursion
        for edge in db.out_edges(conn, node_id, RECURSE_EDGE_TYPES):
            if edge.get("platform_cond") in _SKIP_PLATFORM_CONDS:
                continue
            sub = _evaluate(conn, edge["dst"], cache, iface_map, alt_by_cat)
            if sub == "blocked":
                status = "blocked"
            elif sub == "uncertain" and status == "portable":
                status = "uncertain"
            for b in cache.blockers.get(edge["dst"], []):
                item = dict(b)
                item["path"] = [node_id] + b.get("path", [edge["dst"]])
                blockers.append(item)
            for u in cache.unknowns.get(edge["dst"], []):
                item = dict(u)
                item["path"] = [node_id] + u.get("path", [edge["dst"]])
                unknowns.append(item)
            for p in cache.platform_excluded.get(edge["dst"], []):
                item = dict(p)
                item["path"] = [node_id] + p.get("path", [edge["dst"]])
                platform_excluded.append(item)

    cache.on_stack.pop()
    for item in blockers:
        item.setdefault("path", [node_id])
    for item in unknowns:
        item.setdefault("path", [node_id])
    for item in platform_excluded:
        item.setdefault("path", [node_id])
    cache.status[node_id] = "blocked" if blockers else status
    cache.blockers[node_id] = blockers
    cache.unknowns[node_id] = unknowns
    cache.platform_excluded[node_id] = platform_excluded
    return cache.status[node_id]


def _dedupe(items: List[Dict]) -> List[Dict]:
    seen = set()
    out = []
    for it in items:
        # platform_excluded entries have no kind field (see where _evaluate builds them); .get is the fallback
        key = (it["node"], it.get("kind", ""), it.get("iface", ""), it["reason"])
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def analyze(conn, app_id: str) -> Dict:
    """Determine the portability of the target app."""
    node = db.get_node(conn, app_id)
    if node is None:
        raise ValueError("app node not found: %s" % app_id)
    iface_map = {i["id"]: i for i in db.all_interfaces(conn)}
    # Precompute the same-category alternative interface index to avoid a DB query per interface
    alt_by_cat: Dict[str, List[Dict]] = {}
    for i in iface_map.values():
        if i["ohos_status"] in ("supported", "convertible"):
            alt_by_cat.setdefault(i.get("category") or "", []).append(i)
    cache = _Cache()
    _evaluate(conn, app_id, cache, iface_map, alt_by_cat)

    blockers = _dedupe(cache.blockers.get(app_id, []))
    unknowns = _dedupe(cache.unknowns.get(app_id, []))
    platform_excluded = _dedupe(cache.platform_excluded.get(app_id, []))
    verdict = ("blocked" if blockers
               else "uncertain" if unknowns else "portable")

    evidence = {"portable": "all dependencies and platform interfaces can be ported to HarmonyOS",
                "blocked": "%d hard blockers found" % len(blockers),
                "uncertain": "no hard blockers, but %d items unconfirmed" % len(unknowns)
                }[verdict]
    if platform_excluded and verdict != "blocked":
        evidence += "; %d platform-excluded items (with functional alternative analysis)" % len(platform_excluded)
    db.upsert_node(conn, app_id, node["kind"], node["name"], node["source"],
                   verdict, version=node.get("version"),
                   description=node.get("description"), port_evidence=evidence,
                   cluster_id=node.get("cluster_id"))
    conn.commit()

    return {
        "app_id": app_id,
        "verdict": verdict,
        "blockers": blockers,
        "unknowns": unknowns,
        "platform_excluded": platform_excluded,
        "cycles": cache.cycles[:10],
        "stats": {"visited_nodes": len(cache.status)},
    }
