"""Error pattern engine: matches build/runtime logs against
knowledge/errors/QOH*.yaml entries.

Upgrades problems/_lookup.md (human search) into automatic diagnosis:

    qt-ohos-run analyze-log build.log

Entry schema (see knowledge/errors/index.yaml):

    id: QOH001
    name: qpa_plugin_not_found
    stage: [launch]
    severity: critical
    patterns:
      - "Could not find the Qt platform plugin"
      - "re:libqohos\\.so.*not found"     # re: prefix = regex
    root_causes: [...]
    diagnosis: [...]
    solutions: [...]
    refs:
      problems: [problems/runtime-fail-qpa-plugin-not-found.md]
      kb: [semantic/qt-harmonyos-project-structure.md]
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

from . import yaml_lite


def load_errors(kb_root) -> List[Dict]:
    err_dir = Path(kb_root) / "knowledge" / "errors"
    entries = []
    if not err_dir.is_dir():
        return entries
    for path in sorted(err_dir.glob("QOH*.yaml")):
        try:
            entry = yaml_lite.parse(path.read_text(encoding="utf-8"))
        except yaml_lite.YamlLiteError as exc:
            raise ValueError("bad error file %s: %s" % (path.name, exc))
        if isinstance(entry, dict) and entry.get("id"):
            entry["_file"] = path.name
            entry["_compiled"] = _compile_patterns(entry.get("patterns") or [])
            entries.append(entry)
    return entries


class ErrorEngine:
    def __init__(self, kb_root):
        self.entries = load_errors(kb_root)

    def analyze(self, text: str, stage_hint: str = "") -> List[Dict]:
        text_low = text.lower()
        hits = []
        for entry in self.entries:
            compiled = entry.get("_compiled") or []
            if not compiled:
                continue
            matched = []
            weight = 0.0
            for kind, needle, rx, original in compiled:
                if kind == "regex":
                    if rx is not None and rx.search(text):
                        matched.append(original)
                        weight += 1.0
                else:
                    if needle in text_low:
                        matched.append(original)
                        # longer literal patterns are more specific
                        weight += min(1.0, 0.4 + len(needle) / 120.0)
            if matched:
                score = round(weight / len(compiled), 3)
                hit = {
                    "id": entry.get("id"),
                    "name": entry.get("name"),
                    "score": score,
                    "severity": str(entry.get("severity", "medium")).lower(),
                    "stage": entry.get("stage") or [],
                    "matched_patterns": matched,
                    "root_causes": entry.get("root_causes") or [],
                    "diagnosis": entry.get("diagnosis") or [],
                    "solutions": entry.get("solutions") or [],
                    "refs": entry.get("refs") or {},
                }
                if stage_hint and stage_hint in [str(s).lower() for s in hit["stage"]]:
                    hit["score"] = round(min(1.0, hit["score"] + 0.1), 3)
                hits.append(hit)
        hits.sort(key=lambda h: (-h["score"], str(h["id"])))
        return hits

    def analyze_file(self, log_path) -> List[Dict]:
        path = Path(log_path)
        text = path.read_text(encoding="utf-8", errors="replace")
        stage_hint = ""
        name_low = path.name.lower()
        if "build" in name_low or "cmake" in name_low or "hvigor" in name_low:
            stage_hint = "build"
        elif "install" in name_low:
            stage_hint = "install"
        elif "launch" in name_low or "hilog" in name_low or "runtime" in name_low:
            stage_hint = "launch"
        return self.analyze(text, stage_hint)


def _compile_patterns(patterns) -> List:
    compiled = []
    for item in patterns:
        if item is None:
            continue
        text = str(item).strip()
        if not text:
            continue
        if text.startswith("re:"):
            expr = text[3:].strip()
            try:
                rx = re.compile(expr, re.IGNORECASE)
            except re.error:
                rx = None
            compiled.append(("regex", expr.lower(), rx, text))
        else:
            compiled.append(("literal", text.lower(), None, text))
    return compiled
