"""Feasibility assessment: portable / blocked / uncertain.

Combines (data flow per _index/_organization.md):
- scanner output        (build system, qt_modules, KF components, third-party deps)
- rule_engine findings  (knowledge/rules/R*.yaml)
- adaptation machine layer (knowledge/adaptation/):
    modules.yaml    Qt module availability matrix (MODULE-OUT-OF-SCOPE evidence)
    blockers.yaml   blocking-cause taxonomy + adaptation-vs-blocking boundary
    checklist.yaml  must-adapt checklist (AC01..AC14)
- episodic recipes      (effort reference, via knowledge.similar_recipes)

Verdict logic follows semantic/qt-harmonyos-blocking-taxonomy.md:
- MODULE-OUT-OF-SCOPE / KDE framework stack / CONCEPT-MISMATCH
  / PLATFORM-FEATURE-UNSUPPORTED  -> blocked
- LIB-MISSING candidates (self-compile modules, unverified third-party deps,
  ABI-PERFORMANCE)                  -> uncertain
- otherwise                         -> portable (with checklist hits + risks)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

from . import yaml_lite

ADAPT_DIR = "knowledge/adaptation"

_BLOCKING_CODES = {"MODULE-OUT-OF-SCOPE", "PLATFORM-FEATURE-UNSUPPORTED",
                   "CONCEPT-MISMATCH"}
_UNCERTAIN_CODES = {"LIB-MISSING", "ABI-PERFORMANCE", "OTHER"}

# platform-bound code signals (checklist AC09/AC10/AC12 evidence)
_GREPS = [
    ("linux-guard", r"Q_OS_LINUX"),
    ("x11", r"#\s*include\s*<\s*X11/|\bXOpenDisplay\s*\(|\bxcb_"),
    ("win32", r"#\s*include\s*<\s*windows\.h>|\bCreateWindow\s*\(|\bWinMain\b"),
    ("cocoa", r"#\s*include\s*<\s*Cocoa/|\bNSApplication\b"),
    ("dlopen", r"\bdlopen\s*\("),
    ("qprocess", r"\bQProcess\b|\bsystem\s*\(|\bpopen\s*\("),
]
_GREP_SAMPLE_LIMIT = 400          # max source files grepped
_GREP_FILE_LIMIT = 2 * 1024 * 1024


# ------------------------------------------------------------- data loading

def _load_yaml(path: Path) -> Optional[dict]:
    if not path.is_file():
        return None
    try:
        data = yaml_lite.parse(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except yaml_lite.YamlLiteError:
        return None


def load_adaptation(kb_root) -> Dict:
    root = Path(kb_root) / ADAPT_DIR
    return {
        "modules": _load_yaml(root / "modules.yaml") or {},
        "blockers": _load_yaml(root / "blockers.yaml") or {},
        "checklist": _load_yaml(root / "checklist.yaml") or {},
    }


def module_status(matrix: Dict, module: str, version_key: str):
    """Return (status, entry) for a scanner-style module name, or (None, None)."""
    modules = matrix.get("modules") or {}
    aliases = matrix.get("aliases") or {}
    name = str(module).lower()
    name = aliases.get(name, name)
    entry = modules.get(name)
    if not isinstance(entry, dict):
        return None, None
    status = entry.get(version_key)
    return status, entry


def _version_key(scan_info: Dict) -> str:
    hint = str(scan_info.get("qt_version_hint") or "")
    if hint.startswith("6"):
        return "qt6_12"
    return "qt5_15"     # Qt5 default target: 5.15.16 (5.12 fallback noted in matrix)


# ------------------------------------------------------------- project grep

def _grep_project(project_root, scan_info: Dict) -> Dict[str, List[str]]:
    """Light content grep for platform-bound signals. Returns name -> file list."""
    hits: Dict[str, List[str]] = {}
    if not project_root:
        return hits
    root = Path(project_root)
    patterns = [(name, re.compile(p)) for name, p in _GREPS]
    scanned = 0
    for src in scan_info.get("sources", []):
        if scanned >= _GREP_SAMPLE_LIMIT:
            break
        path = root / src.get("path", "")
        try:
            if not path.is_file() or path.stat().st_size > _GREP_FILE_LIMIT:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        scanned += 1
        for name, rx in patterns:
            if rx.search(text):
                hits.setdefault(name, []).append(src.get("path"))
    return hits


# ------------------------------------------------------------- evaluation

def evaluate(kb_root, scan_info: Dict, risk: Optional[Dict] = None,
             recipes: Optional[List[Dict]] = None,
             project_root=None) -> Dict:
    adapt = load_adaptation(kb_root)
    matrix = adapt["modules"]
    version_key = _version_key(scan_info)

    blockers: List[Dict] = []
    self_compile: List[Dict] = []
    restricted: List[Dict] = []
    unknown: List[str] = []

    # 1. Qt module matrix
    for mod in scan_info.get("qt_modules", []):
        status, entry = module_status(matrix, mod, version_key)
        if status is None and entry is None:
            unknown.append(mod)
            continue
        if status == "out-of-scope":
            blockers.append({
                "code": "MODULE-OUT-OF-SCOPE",
                "title": "Qt module '%s' is out of scope on HarmonyOS (%s)" % (
                    mod, version_key),
                "evidence": "module detected in project",
                "note": (entry.get("note") or ""),
                "substitute": (entry.get("substitute") or ""),
                "ref": (entry.get("ref") or "semantic/qt-harmonyos-modules.md"),
            })
        elif status == "self-compile":
            self_compile.append({
                "module": mod,
                "note": (entry.get("note") or "not in SDK; cross-compile it"),
                "ref": (entry.get("ref") or ""),
            })
        elif status == "restricted":
            restricted.append({
                "module": mod,
                "note": (entry.get("note") or ""),
                "ref": (entry.get("ref") or "semantic/qt-harmonyos-modules.md"),
            })

    # 2. KDE framework stack (framework-stack special case, LIB-MISSING)
    kf_components = scan_info.get("kf_components") or []
    frameworks = scan_info.get("frameworks") or []
    kde_stack = bool(frameworks) and len(kf_components) >= 5
    if kde_stack:
        blockers.append({
            "code": "LIB-MISSING",
            "title": "KDE Frameworks stack (%s, %d components)" % (
                ", ".join(frameworks[:2]), len(kf_components)),
            "evidence": "find_package(KF...) with %d components" % len(kf_components),
            "note": "框架栈大实例：工作量数人年且部分子模块平台无对应——判不投入",
            "substitute": "",
            "ref": "semantic/qt-harmonyos-blocking-taxonomy.md",
        })

    # 3. third-party dependencies -> LIB-MISSING candidates (uncertain)
    deps_to_verify: List[str] = []
    for dep in scan_info.get("third_party_hints") or []:
        deps_to_verify.append(dep.get("name", "?"))
    for name in (scan_info.get("cmake_packages") or {}).get("find_package") or []:
        if name not in deps_to_verify:
            deps_to_verify.append(name)
    pkg = scan_info.get("pkg_manifests") or {}
    for dep in pkg.get("conan") or []:
        if dep.get("name") not in deps_to_verify:
            deps_to_verify.append(dep.get("name", "?"))
    for name in pkg.get("vcpkg") or []:
        if name not in deps_to_verify:
            deps_to_verify.append(name)

    # 4. platform-bound code grep (checklist evidence)
    greps = _grep_project(project_root, scan_info)

    # 5. must-adapt checklist hits
    checklist_hits = _checklist_hits(adapt["checklist"], scan_info, greps)

    # 6. risk summary from rule engine
    findings = (risk or {}).get("findings") or []
    risk_summary = (risk or {}).get("summary") or {}
    critical_rules = sorted({f.get("rule") for f in findings
                             if f.get("severity") == "critical"})

    # 7. verdict per taxonomy
    if blockers:
        verdict = "blocked"
    elif self_compile or deps_to_verify:
        verdict = "uncertain"
    else:
        verdict = "portable"

    assessment = {
        "verdict": verdict,
        "qt_target": version_key,
        "blockers": blockers,
        "self_compile_modules": self_compile,
        "restricted_modules": restricted,
        "unknown_modules": unknown,
        "deps_to_verify": deps_to_verify,
        "kde_stack": kde_stack,
        "platform_grep": {k: v[:5] for k, v in greps.items()},
        "checklist_hits": checklist_hits,
        "risk_summary": risk_summary,
        "critical_rules": critical_rules,
        "effort_reference": (recipes or [])[:3],
    }
    assessment["summary"] = _summary(assessment)
    return assessment


def _checklist_hits(checklist: Dict, scan_info: Dict,
                    greps: Dict[str, List[str]]) -> List[Dict]:
    hits = []
    build = scan_info.get("build_system") or ""
    for item in checklist.get("items") or []:
        trigger = str(item.get("trigger") or "always")
        fired = (
            trigger == "always"
            or (trigger == "build_system 含 cmake" and "cmake" in build)
            or (trigger == "build_system 含 qmake" and "qmake" in build)
            or (trigger == "存在 .qrc 文件" and scan_info.get("qrc_files"))
            or (trigger == "多窗口或对话框"
                and (scan_info.get("ui_files") or "widgets" in
                     scan_info.get("qt_modules", [])))
            or (trigger == "源码含 Q_OS_LINUX" and greps.get("linux-guard"))
            or (trigger == "源码含平台 API 调用"
                and any(greps.get(k) for k in ("x11", "win32", "cocoa")))
            or (trigger == "源码含 dlopen 或绝对路径写文件" and greps.get("dlopen"))
            or (trigger == "源码含 QProcess/system/popen" and greps.get("qprocess"))
            or (trigger == "存在第三方依赖"
                and (scan_info.get("third_party_hints")
                     or (scan_info.get("cmake_packages") or {}).get("find_package")))
            or (trigger == "Qt5 老代码"
                and str(scan_info.get("qt_version_hint") or "").startswith("5"))
        )
        if fired:
            hits.append({
                "id": item.get("id"),
                "title": item.get("title"),
                "severity": item.get("severity"),
                "how": item.get("how"),
                "ref": item.get("ref"),
            })
    return hits


def _summary(a: Dict) -> str:
    parts = ["verdict=%s" % a["verdict"], "target=%s" % a["qt_target"]]
    if a["blockers"]:
        parts.append("%d blocker(s): %s" % (
            len(a["blockers"]),
            "; ".join(b["code"] for b in a["blockers"])))
    if a["self_compile_modules"]:
        parts.append("self-compile: %s" % ", ".join(
            m["module"] for m in a["self_compile_modules"]))
    if a["deps_to_verify"]:
        parts.append("%d third-party dep(s) to verify" % len(a["deps_to_verify"]))
    parts.append("%d must-adapt item(s)" % len(a["checklist_hits"]))
    return " | ".join(parts)


# ------------------------------------------------------------- rendering

def render(assessment: Dict) -> str:
    lines = []
    verdict = assessment.get("verdict", "?").upper()
    lines.append("")
    lines.append("Qt HarmonyOS Feasibility Assessment")
    lines.append("==================================")
    lines.append("Verdict : %s   (target: %s)" % (
        verdict, assessment.get("qt_target")))
    lines.append("Summary : %s" % assessment.get("summary"))

    if assessment.get("blockers"):
        lines.append("")
        lines.append("Blockers (adaptation cannot fix these):")
        for b in assessment["blockers"]:
            lines.append("  [%s] %s" % (b["code"], b["title"]))
            if b.get("note"):
                lines.append("        note: %s" % b["note"])
            if b.get("substitute"):
                lines.append("        substitute: %s" % b["substitute"])
            lines.append("        read: %s" % b.get("ref"))
    if assessment.get("self_compile_modules"):
        lines.append("")
        lines.append("Self-compile modules (not in SDK, cross-compile them):")
        for m in assessment["self_compile_modules"]:
            lines.append("  %-16s %s" % (m["module"], m["note"]))
    if assessment.get("restricted_modules"):
        lines.append("")
        lines.append("Restricted modules (verify feature coverage):")
        for m in assessment["restricted_modules"]:
            lines.append("  %-16s %s" % (m["module"], m["note"] or ""))
    if assessment.get("deps_to_verify"):
        lines.append("")
        lines.append("Third-party deps to verify (LIB-MISSING candidates):")
        lines.append("  %s" % ", ".join(assessment["deps_to_verify"]))
    if assessment.get("platform_grep"):
        lines.append("")
        lines.append("Platform-bound code signals (grep):")
        for name, files in assessment["platform_grep"].items():
            lines.append("  %-12s %d file(s), e.g. %s" % (
                name, len(files), files[0]))
    if assessment.get("checklist_hits"):
        lines.append("")
        lines.append("Must-adapt checklist (knowledge/adaptation/checklist.yaml):")
        for c in assessment["checklist_hits"]:
            lines.append("  %-6s %-9s %s" % (c["id"], c["severity"], c["title"]))
            lines.append("         how: %s" % c["how"])
            lines.append("         ref: %s" % c["ref"])
    risk = assessment.get("risk_summary") or {}
    if any(risk.get(s) for s in ("critical", "high")):
        lines.append("")
        lines.append("Risk scan: critical=%s high=%s%s" % (
            risk.get("critical", 0), risk.get("high", 0),
            "  rules: %s" % ", ".join(assessment.get("critical_rules") or [])
            if assessment.get("critical_rules") else ""))
    if assessment.get("effort_reference"):
        lines.append("")
        lines.append("Effort reference (similar historical migrations):")
        for r in assessment["effort_reference"]:
            lines.append("  %.2f  %-40s %s" % (
                r["score"], r["case"], r.get("summary", "")[:60]))
    lines.append("")
    lines.append("Deep dependency-graph analysis: see portgraph (local tool).")
    lines.append("Taxonomy: semantic/qt-harmonyos-blocking-taxonomy.md")
    return "\n".join(lines)
