"""Migration report generation (.qt-ohos/report.md)."""

from __future__ import annotations

import time
from typing import Dict, List

from .state import STAGES
from .verifier import GATE_ORDER


def build_report(state, scan: Dict, plan: Dict, risk: Dict,
                 deps: List[Dict], gates: Dict, overall: str,
                 changes: List[Dict], patches: List[str],
                 recipes: List[Dict], hits: List[Dict]) -> str:
    lines = []
    add = lines.append

    add("# Qt HarmonyOS Migration Report")
    add("")
    add("- Project: **%s**" % state.project)
    add("- Generated: %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    add("- Overall verification result: **%s**" % overall)
    add("")

    add("## 1. Project profile")
    add("")
    add("| Item | Value |")
    add("|------|-------|")
    add("| Build system | %s |" % scan.get("build_system"))
    add("| Qt version hint | %s |" % (scan.get("qt_version_hint") or "-"))
    add("| Qt modules | %s |" % ", ".join(scan.get("qt_modules", [])) or "-")
    add("| Source files | %d |" % len(scan.get("sources", [])))
    add("| Prebuilt binaries | %d |" % len(scan.get("binary_artifacts", [])))
    add("")

    add("## 2. Risk scan (pre-scan)")
    add("")
    summary = risk.get("summary") or {}
    add("| Severity | Count |")
    add("|----------|:-----:|")
    for sev in ("critical", "high", "medium", "low"):
        if summary.get(sev):
            add("| %s | %d |" % (sev, summary[sev]))
    add("")
    critical = [f for f in risk.get("findings", []) if f["severity"] == "critical"]
    if critical:
        add("Critical findings:")
        add("")
        for f in critical[:20]:
            add("- **%s** %s — `%s:%s`" % (f["rule"], f.get("name"),
                                           f.get("file"), f.get("line")))
        add("")

    add("## 3. Third-party dependencies")
    add("")
    if deps:
        add("| Dependency | Status | Note |")
        add("|------------|--------|------|")
        for dep in deps:
            add("| %s | %s | %s |" % (dep["name"], dep["status"], dep["note"]))
    else:
        add("No third-party dependencies detected.")
    add("")

    add("## 4. Migration plan")
    add("")
    if plan and plan.get("steps"):
        for step in plan["steps"]:
            add("- [%s][%s] %s — %s" % (step["id"], step["action"],
                                        step["title"], step["severity"]))
    else:
        add("(no plan generated)")
    add("")

    add("## 5. Source changes (tracked)")
    add("")
    if changes:
        add("| File | Source | +/- | Description |")
        add("|------|--------|-----|-------------|")
        for change in changes:
            add("| `%s` | %s | +%d/-%d | %s |" % (
                change["file"], change["source"],
                change.get("added_lines", 0), change.get("removed_lines", 0),
                change["description"]))
        add("")
        if patches:
            add("Patches: " + ", ".join("`%s`" % p for p in patches))
    else:
        add("No tracked source changes.")
    add("")

    add("## 6. Stage progress")
    add("")
    completed = set(state.data.get("completed", []))
    for stage in STAGES:
        mark = "x" if stage in completed else " "
        add("- [%s] %s" % (mark, stage))
    add("")

    add("## 7. Verification gates")
    add("")
    if gates:
        add("| Gate | Title | Status | Detail |")
        add("|------|-------|--------|--------|")
        for gid in GATE_ORDER:
            info = gates[gid]
            add("| %s | %s | %s | %s |" % (gid, info["title"], info["status"],
                                            info["detail"][:80]))
    else:
        add("(not run)")
    add("")

    if hits:
        add("## 8. Remaining known issues (error-engine hits)")
        add("")
        for hit in hits[:10]:
            add("- **%s** %s (score %.2f) — %s" % (
                hit["id"], hit.get("name"), hit["score"],
                ", ".join(hit.get("root_causes", [])[:1])))
        add("")

    if recipes:
        add("## 9. Similar historical migrations")
        add("")
        for recipe in recipes:
            add("- %s (score %.2f) — %s" % (recipe["case"], recipe["score"],
                                             recipe["summary"][:80]))
        add("")

    add("## 10. Knowledge distillation")
    add("")
    drafts = state.data.get("drafts") or []
    if drafts:
        for draft in drafts:
            add("- %s" % draft)
    else:
        add("No knowledge drafts generated. If this migration hit a NEW problem,")
        add("run `qt-ohos-run draft \"<title>\"` before closing the task.")
    add("")
    return "\n".join(lines)
