#!/usr/bin/env python3
"""重建 `_index/_dashboard.md`（派生计数与文件清单，零第三方依赖）。

为什么需要它：仪表盘里的页数、每域活跃数、problems 条目数、故障图规模都是**派生事实**，
却一直是手写的。手写就会漂移——实测出现过表头写 15、表里只列 14 页，以及合计 48 与
真实 49 不符。真源在页面 frontmatter、`problems/` 目录与 `faults/_registry.md`，本脚本
把它们重新投影成仪表盘。

用法：
    python _scripts/gen-dashboard.py            # 重写 _index/_dashboard.md
    python _scripts/gen-dashboard.py --check    # 只比对，过期则退出 1（CI 用）
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
DASH = ROOT / "_index" / "_dashboard.md"
DOMAINS = [
    ("semantic", "semantic", "语义知识：概念、API 映射、模块状态、平台限制"),
    ("procedural", "procedural", "程序知识：迁移、排障、构建、发版、Demo"),
    ("episodic", "episodic/postmortems", "情景知识：真实项目复盘"),
    ("preference", "preference", "个人偏好"),
]


def _frontmatter(text: str) -> Dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    out: Dict[str, str] = {}
    for line in text[3:end].splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            key, _, value = line.partition(":")
            out[key.strip()] = value.strip()
    return out


def _pages(sub: str) -> List[Tuple[str, str, str]]:
    base = ROOT / sub
    if not base.is_dir():
        return []
    rows = []
    for path in sorted(base.glob("*.md")):
        if path.name.startswith("_"):
            continue
        fm = _frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        status = fm.get("status", "active")
        updated = fm.get("updated") or fm.get("created") or "-"
        rows.append((path.name, status, updated))
    return rows


def _registry_counts() -> Dict[str, int]:
    text = (ROOT / "faults" / "_registry.md").read_text(encoding="utf-8", errors="replace")
    counts = {}
    for key in ("symptoms", "causes", "workarounds", "tickets"):
        m = re.search(rf"{key}:\s*(\d+)", text)
        counts[key] = int(m.group(1)) if m else 0
    return counts


def _strip_date(text: str) -> str:
    """把两处"生成日期"抹平后再比较，其余日期（各页 updated）保留。"""
    text = re.sub(r"^updated: .*$", "", text, count=1, flags=re.M)
    return re.sub(r"(\*\*最后更新\*\*：)\d{4}-\d{2}-\d{2}", r"\1<date>", text)


def render(today: str | None = None) -> str:
    today = today or datetime.date.today().isoformat()
    domain_rows = {name: _pages(sub) for name, sub, _desc in DOMAINS}
    active = {name: [r for r in rows if r[1] != "archived"]
              for name, rows in domain_rows.items()}
    archived = sum(len(domain_rows[n]) - len(active[n]) for n in active)
    total = sum(len(v) for v in active.values())
    problems = len([p for p in (ROOT / "problems").glob("*.md")
                    if not p.name.startswith("_")])
    counts = _registry_counts()
    fault_total = sum(counts.values())

    out: List[str] = []
    out += ["---", f"updated: {today}", f"total_pages: {total}",
            "description: >", "  知识库健康仪表盘（派生计数，从 frontmatter 自动生成）。",
            "  重建：python _scripts/gen-dashboard.py（禁止手改数字）。", "---", "",
            "# 知识库健康仪表盘", "",
            "> **最后更新**：%s ｜ **总活跃页面**：%d（semantic/procedural/episodic/preference）"
            " ｜ **归档**：%d" % (today, total, archived), "",
            "> 本页是派生视图：页面清单与计数来自各页 frontmatter、`problems/` 目录与",
            "> `faults/_registry.md`。要改数字请改真源，然后跑 `python _scripts/gen-dashboard.py`。",
            "", "---", "", "## 一、文件清单（派生）", ""]

    for name, _sub, desc in DOMAINS:
        rows = active[name]
        out += ["### %s（%d 活跃）" % (name, len(rows)), "", f"_{desc}_", ""]
        if not rows:
            out += ["_（本域无活跃页）_", ""]
            continue
        out += ["| 页面 | 状态 | 最后更新 |", "|------|:----:|:--------:|"]
        for filename, status, updated in rows:
            mark = "✅ 活跃" if status != "archived" else "🗄 归档"
            out.append("| `%s` | %s | %s |" % (filename, mark, updated))
        out.append("")

    archived_rows = [(name, row) for name, _sub, _desc in DOMAINS
                     for row in domain_rows[name]
                     if row[1] == "archived"]
    if archived_rows:
        out += ["### 归档（%d）" % len(archived_rows), "",
                "> 已归档页仍可读、链接有效，只是不再计入活跃页；复核或修订后可移回对应域。",
                "", "| 域 | 页面 | 最后更新 |", "|----|------|:--------:|"]
        for name, (filename, _status, updated) in archived_rows:
            out.append("| %s | `%s` | %s |" % (name, filename, updated))
        out.append("")

    out += ["### problems（%d 条目）" % problems, "",
            "详见 [_lookup](../problems/_lookup.md)——错误知识库的唯一检索入口"
            "（按错误码 / 症状 / 领域三维）。", "",
            "### faults（%d 记录：%d 症状 S + %d 根因 C + %d 方案 W + %d 跟踪单 T）"
            % (fault_total, counts["symptoms"], counts["causes"],
               counts["workarounds"], counts["tickets"]), "",
            "详见 [_registry](../faults/_registry.md)（症状索引主入口 + 按处置分类）与 "
            "[_graph.yaml](../faults/_graph.yaml)（机读全量图）。真源 `_data/*.yaml` + C 页；"
            "派生物由 `tools/faults-build.py build` 重建。", "",
            "---", "", "## 二、来源覆盖率（派生）", "",
            "| 域 | 活跃页 | 备注 |", "|----|:------:|------|"]
    notes = {"semantic": "见各页 frontmatter refs", "procedural": "见各页 frontmatter refs",
             "episodic": "项目经验，无外部来源", "preference": "个人偏好"}
    for name, _sub, _desc in DOMAINS:
        out.append("| %s | %d | %s |" % (name, len(active[name]), notes.get(name, "")))
    out += ["| faults | %d | 问题跟踪图（%d 症状 + %d 根因 + %d 方案 + %d 跟踪单） |"
            % (fault_total, counts["symptoms"], counts["causes"],
               counts["workarounds"], counts["tickets"]),
            "| **合计活跃** | **%d** | 不含 problems 与内嵌平台库（单独计数） |" % total, ""]
    text = "\n".join(out) + "\n"
    # 干净树隔日不该变红：内容没变就沿用原 updated 日期。
    if DASH.exists():
        current = DASH.read_text(encoding="utf-8", errors="replace")
        if _strip_date(text) == _strip_date(current):
            match = re.search(r"^updated: (.*)$", current, re.M)
            if match:
                text = re.sub(r"^updated: .*$", "updated: " + match.group(1),
                              text, count=1, flags=re.M)
    return text


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="重建 _index/_dashboard.md")
    parser.add_argument("--check", action="store_true", help="只比对，过期退出 1")
    args = parser.parse_args(argv)
    text = render()
    current = DASH.read_text(encoding="utf-8") if DASH.exists() else ""
    if args.check:
        if _strip_date(text) == _strip_date(current):
            print("gen-dashboard: 一致")
            return 0
        print("gen-dashboard: _dashboard.md 过期，运行 python _scripts/gen-dashboard.py")
        return 1
    if text == current:
        print("gen-dashboard: 内容未变")
        return 0
    DASH.write_text(text, encoding="utf-8")
    print("gen-dashboard: 已重建（%d 活跃页 / %d problems / %d 故障记录）"
          % (sum(1 for _ in re.finditer(r"^\| `", text, re.M)),
             len([p for p in (ROOT / "problems").glob("*.md") if not p.name.startswith("_")]),
             sum(_registry_counts().values())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
