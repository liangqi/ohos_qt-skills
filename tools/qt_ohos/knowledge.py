"""Learning plane: knowledge drafts, promotion, and historical recipe search.

- draft:    distill a debugging session into drafts/QOHxxx.md
- promote:  turn a validated draft into problems/<slug>.md (human page, single
            source of truth) + knowledge/errors/QOHxxx.yaml (machine index);
            the errors index count is updated automatically
- recipes:  rank episodic/*.md migration cases by similarity to the project

Drafts live in the KB top-level drafts/ directory (see
_index/_organization.md §5): E{N}-*.md retros (kb-sediment.sh) and QOHxxx.md
error-pattern drafts (this CLI) share the same staging area.

Success criterion (borrowed from build_in_harmonyos): a migration that
produced no reusable knowledge is incomplete.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Dict, List

from . import yaml_lite

DRAFT_TEMPLATE = """---
id: {draft_id}
title: "{title}"
type: knowledge-draft
status: draft
stage: runtime
created: {date}
tags: [{tags}]
qt_versions: []
ohos_api: ""
generalizable: unknown
refs: []
summary: >
  {summary}
---

# {title}

## 症状 (Symptom)

{symptom}

## 环境 (Environment)

- Qt 版本：
- OHOS API：
- 设备/模拟器：

## 错误日志 (Error log)

```
{log}
```

## 根因 (Root cause)

（填写）

## 调用链 (Call chain)

（填写）

## 最小复现 (Minimal repro)

（填写）

## 修复 (Fix)

（填写）

## 验证方法 (Verification)

（填写）

## 可否泛化 (Generalizable?)

unknown
"""


def _draft_dir(kb_root) -> Path:
    return Path(kb_root) / "drafts"


def _existing_ids(kb_root) -> List[int]:
    ids = []
    errors_dir = Path(kb_root) / "knowledge" / "errors"
    for base, pattern in ((errors_dir, "QOH*.yaml"), (_draft_dir(kb_root), "QOH*.md")):
        if not base.is_dir():
            continue
        for path in base.glob(pattern):
            match = re.match(r"QOH(\d+)", path.stem)
            if match:
                ids.append(int(match.group(1)))
    return ids


def next_id(kb_root) -> int:
    ids = _existing_ids(kb_root)
    return (max(ids) + 1) if ids else 101


def create_draft(kb_root, title: str, summary: str = "",
                 symptom: str = "", log: str = "", tags: List[str] = None) -> Path:
    draft_id = "QOH%03d" % next_id(kb_root)
    directory = _draft_dir(kb_root)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ("%s.md" % draft_id)
    content = DRAFT_TEMPLATE.format(
        draft_id=draft_id,
        date=time.strftime("%Y-%m-%d"),
        tags=", ".join(tags or []),
        summary=summary or title,
        title=title,
        symptom=symptom or "（填写）",
        log=log.strip() or "（粘贴错误日志）",
    )
    path.write_text(content, encoding="utf-8")
    return path


PROBLEM_TEMPLATE = """---
id: problem-{page_id}
title: "{title}"
type: problem
status: open
confidence: 0.8
contributors: [<CONTRIBUTOR>]
created: {date}
updated: {date}
tags: [problem, {stage}]
refs: []
summary: "{summary}"
domain: {stage}
severity: medium
error_message: |
{log}
error_code: "N/A"
keywords: [{keywords}]
symptoms: "{symptom}"
environment: "待补充（Qt/SDK/OS 版本）"
related_problems: []
---

# {title}

## 错误信息

```
{log}
```

## 场景

（待补充：在什么情况下遇到此问题——Qt 版本、OS 版本、构建配置等）

## 原因

（待补充：根本原因分析，见 drafts/{draft_id}.md 的根因段）

## 解决方案

（待补充：如何解决，含具体命令/代码修改）

## 预防措施

（待补充）

## 关联

- 机器索引：knowledge/errors/{draft_id}.yaml
"""


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return slug[:48] or "problem"


def _draft_field(text: str, field: str) -> str:
    match = re.search(r"^%s:\s*>?\s*\n?\s*(.+)$" % field, text, re.M)
    if not match:
        return ""
    value = match.group(1).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1].strip()
    return value


def _draft_body_section(text: str, heading: str) -> str:
    match = re.search(r"^## %s.*?\n(.*?)(?=\n## |\Z)" % re.escape(heading),
                      text, re.S | re.M)
    if not match:
        return ""
    body = match.group(1).strip()
    body = re.sub(r"^```[a-z]*\s*$|\n```[a-z]*\s*$", "", body).strip()
    return body if "（填写）" not in body and "（粘贴" not in body else ""


def promote_draft(kb_root, draft_id: str):
    """Promote a validated draft into its dual destination:

    1. problems/<stage>-fail-<slug>.md  - the human page (single source of
       truth, schema per _index/_organization.md §3.2)
    2. knowledge/errors/QOHxxx.yaml     - the machine index skeleton
    3. knowledge/errors/index.yaml      - entry_count bumped automatically

    Returns the path of the generated problems/ page.
    """
    draft_id = draft_id.upper()
    draft_path = _draft_dir(kb_root) / ("%s.md" % draft_id)
    if not draft_path.exists():
        raise FileNotFoundError("draft not found: %s" % draft_path)
    errors_dir = Path(kb_root) / "knowledge" / "errors"
    errors_dir.mkdir(parents=True, exist_ok=True)
    target = errors_dir / ("%s.yaml" % draft_id)
    if target.exists():
        raise FileExistsError("error entry already exists: %s" % target)

    text = draft_path.read_text(encoding="utf-8")
    fm = _frontmatter(text)
    title = _draft_field(text, "title") or draft_id
    summary = _draft_field(text, "summary") or title
    symptom = _draft_body_section(text, "症状 (Symptom)")
    log = _draft_body_section(text, "错误日志 (Error log)")
    stage = str(fm.get("stage") or "runtime").lower()
    if stage not in ("build", "package", "install", "launch", "runtime"):
        stage = "runtime"
    slug = _slugify(title)
    page_id = "%s-fail-%s" % (stage, slug)

    # 1. human problems/ page (single source of truth)
    problems_dir = Path(kb_root) / "problems"
    problems_dir.mkdir(parents=True, exist_ok=True)
    page_path = problems_dir / ("%s.md" % page_id)
    if page_path.exists():
        raise FileExistsError("problems page already exists: %s" % page_path)
    log_text = log or "（待补充：完整错误输出）"
    page = PROBLEM_TEMPLATE.format(
        page_id=page_id, title=title.replace('"', "'"),
        date=time.strftime("%Y-%m-%d"), stage=stage,
        summary=summary.replace('"', "'")[:120],
        log="\n".join("  " + ln for ln in log_text.splitlines()),
        keywords=", ".join(sorted({stage, slug.split("-")[0]})),
        symptom=(symptom or summary).replace('"', "'")[:100],
        draft_id=draft_id)
    page_path.write_text(page, encoding="utf-8")

    # 2. machine index skeleton
    entry = {
        "id": draft_id,
        "name": slug.replace("-", "_"),
        "stage": [stage],
        "severity": "medium",
        "patterns": ["TODO: add 2-4 literal log patterns"],
        "root_causes": ["TODO"],
        "diagnosis": ["TODO"],
        "solutions": ["TODO"],
        "refs": {"problems": ["problems/%s.md" % page_id], "kb": []},
        "summary": summary,
    }
    target.write_text(yaml_lite.dump(entry), encoding="utf-8")

    # 3. bump the errors index count
    index_path = errors_dir / "index.yaml"
    if index_path.is_file():
        index_text = index_path.read_text(encoding="utf-8")
        count_match = re.search(r"entry_count:\s*(\d+)", index_text)
        if count_match:
            index_text = index_text.replace(
                "entry_count: %s" % count_match.group(1),
                "entry_count: %d" % (int(count_match.group(1)) + 1), 1)
            index_path.write_text(index_text, encoding="utf-8")

    # 4. mark the draft promoted
    updated = text.replace("status: draft", "status: promoted", 1)
    draft_path.write_text(updated, encoding="utf-8")
    return page_path


# --------------------------------------------------------------- recipes

def similar_recipes(kb_root, scan_info: Dict, top: int = 5) -> List[Dict]:
    """Rank episodic migration cases by feature overlap with the project."""
    episodic_dir = Path(kb_root) / "episodic"
    project_terms = set(scan_info.get("qt_modules", []))
    project_terms.add(scan_info.get("build_system", ""))
    project_terms.update(d["name"] for d in scan_info.get("third_party_hints", []))
    project_terms = {t for t in project_terms if t}

    results = []
    for path in sorted(episodic_dir.rglob("*.md")):
        if path.name.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        fm = _frontmatter(text)
        tags = set()
        raw_tags = fm.get("tags") or []
        if isinstance(raw_tags, list):
            tags.update(str(t).lower() for t in raw_tags)
        tags.update(re.findall(r"[a-z0-9]{3,}", (fm.get("summary") or "").lower()))
        overlap = project_terms & tags
        body_low = text.lower()
        body_hits = {t for t in project_terms if t in body_low}
        # 归一化到 0..1：原公式不除以项目特征数，一个 "cmake" 就能顶到 1.00，
        # 让"相似度 1.00 的 Coin3D"这种明显无关的案例排到第一。
        raw = 0.6 * len(overlap) + 0.1 * len(body_hits)
        score = round(min(1.0, raw / max(1, len(project_terms))), 2)
        if score > 0:
            results.append({
                "case": path.relative_to(Path(kb_root)).as_posix(),
                "score": score,
                "matched": sorted(overlap | body_hits)[:8],
                "summary": (fm.get("summary") or "").strip()[:120],
            })
    results.sort(key=lambda r: -r["score"])
    return results[:top]


def _frontmatter(text: str) -> Dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    try:
        data = yaml_lite.parse(text[3:end])
        return data if isinstance(data, dict) else {}
    except yaml_lite.YamlLiteError:
        return {}
