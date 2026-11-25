#!/usr/bin/env python3
"""Rebuild `_index/_dashboard.md` (derived counts and file inventory, zero third-party dependencies).

Why it exists: the dashboard's page count, per-domain active counts, number of problems entries,
and fault graph size are all **derived facts**, yet they used to be written by hand. Hand-written
numbers drift -- in practice a header said 15 while the table listed only 14 pages, and a total
of 48 disagreed with the real 49. The source of truth is the page frontmatter, the `problems/`
directory, and `faults/_registry.md`; this script re-projects them into the dashboard.

Usage:
    python _scripts/gen-dashboard.py            # rewrite _index/_dashboard.md
    python _scripts/gen-dashboard.py --check    # compare only; exit 1 if stale (for CI)
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
    ("semantic", "semantic", "Semantic knowledge: concepts, API mappings, module status, platform limitations"),
    ("procedural", "procedural", "Procedural knowledge: migration, troubleshooting, builds, releases, demos"),
    ("episodic", "episodic/postmortems", "Episodic knowledge: retrospectives from real projects"),
    ("preference", "preference", "Personal preferences"),
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
    """Blank out the two "generated on" dates before comparing; other dates (each page's updated) are kept."""
    text = re.sub(r"^updated: .*$", "", text, count=1, flags=re.M)
    return re.sub(r"(\*\*Last updated\*\*: )\d{4}-\d{2}-\d{2}", r"\1<date>", text)


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
            "description: >", "  Knowledge base health dashboard (derived counts, generated automatically from frontmatter).",
            "  Rebuild: python _scripts/gen-dashboard.py (never edit the numbers by hand).", "---", "",
            "# Knowledge base health dashboard", "",
            "> **Last updated**: %s | **Total active pages**: %d (semantic/procedural/episodic/preference)"
            " | **Archived**: %d" % (today, total, archived), "",
            "> This page is a derived view: the page lists and counts come from each page's frontmatter, the `problems/` directory, and",
            "> `faults/_registry.md`. To change a number, change the source of truth and then run `python _scripts/gen-dashboard.py`.",
            "", "---", "", "## 1. File inventory (derived)", ""]

    for name, _sub, desc in DOMAINS:
        rows = active[name]
        out += ["### %s (%d active)" % (name, len(rows)), "", f"_{desc}_", ""]
        if not rows:
            out += ["_(No active pages in this domain)_", ""]
            continue
        out += ["| Page | Status | Last updated |", "|------|:------:|:------------:|"]
        for filename, status, updated in rows:
            mark = "✅ Active" if status != "archived" else "🗄 Archived"
            out.append("| `%s` | %s | %s |" % (filename, mark, updated))
        out.append("")

    archived_rows = [(name, row) for name, _sub, _desc in DOMAINS
                     for row in domain_rows[name]
                     if row[1] == "archived"]
    if archived_rows:
        out += ["### Archived (%d)" % len(archived_rows), "",
                "> Archived pages are still readable and their links still work; they just no longer count as active pages. After review or revision they can move back to their domain.",
                "", "| Domain | Page | Last updated |", "|--------|------|:------------:|"]
        for name, (filename, _status, updated) in archived_rows:
            out.append("| %s | `%s` | %s |" % (name, filename, updated))
        out.append("")

    out += ["### problems (%d entries)" % problems, "",
            "See [_lookup](../problems/_lookup.md) — the single search entry point for the error knowledge base"
            " (along three dimensions: error code / symptom / domain).", "",
            "### faults (%d records: %d symptoms S + %d root causes C + %d workarounds W + %d tracking tickets T)"
            % (fault_total, counts["symptoms"], counts["causes"],
               counts["workarounds"], counts["tickets"]), "",
            "See [_registry](../faults/_registry.md) (the symptom index as the main entry point + classification by disposition) and "
            "[_graph.yaml](../faults/_graph.yaml) (the machine-readable full graph). The source of truth is `_data/*.yaml` + the C pages; "
            "the derived artifacts are rebuilt by `tools/faults-build.py build`.", "",
            "---", "", "## 2. Source coverage (derived)", "",
            "| Domain | Active pages | Notes |", "|--------|:------------:|-------|"]
    notes = {"semantic": "See the frontmatter refs on each page", "procedural": "See the frontmatter refs on each page",
             "episodic": "Project experience; no external sources", "preference": "Personal preferences"}
    for name, _sub, _desc in DOMAINS:
        out.append("| %s | %d | %s |" % (name, len(active[name]), notes.get(name, "")))
    out += ["| faults | %d | The issue tracking graph (%d symptoms + %d root causes + %d workarounds + %d tracking tickets) |"
            % (fault_total, counts["symptoms"], counts["causes"],
               counts["workarounds"], counts["tickets"]),
            "| **Total active** | **%d** | Excludes problems and the embedded platform library (counted separately) |" % total, ""]
    text = "\n".join(out) + "\n"
    # A clean tree must not turn red the next day: if the content is unchanged, keep the original generation date.
    # The frontmatter's updated: and the body's **Last updated**: are two places for the same fact;
    # reusing only one of them would still leave the file "dirty" the next day.
    if DASH.exists():
        current = DASH.read_text(encoding="utf-8", errors="replace")
        if _strip_date(text) == _strip_date(current):
            match = re.search(r"^updated: (.*)$", current, re.M)
            if match:
                text = re.sub(r"^updated: .*$", "updated: " + match.group(1),
                              text, count=1, flags=re.M)
            body = re.search(r"\*\*Last updated\*\*: (\d{4}-\d{2}-\d{2})", current)
            if body:
                # A digit right after `\1` is taken as an octal escape (\120 == "P"); \g<1> is required
                text = re.sub(r"(\*\*Last updated\*\*: )\d{4}-\d{2}-\d{2}",
                              r"\g<1>" + body.group(1), text, count=1)
    return text


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Rebuild _index/_dashboard.md")
    parser.add_argument("--check", action="store_true", help="compare only; exit 1 if stale")
    args = parser.parse_args(argv)
    text = render()
    current = DASH.read_text(encoding="utf-8") if DASH.exists() else ""
    if args.check:
        if _strip_date(text) == _strip_date(current):
            print("gen-dashboard: up to date")
            return 0
        print("gen-dashboard: _dashboard.md is stale; run python _scripts/gen-dashboard.py")
        return 1
    if text == current:
        print("gen-dashboard: content unchanged")
        return 0
    DASH.write_text(text, encoding="utf-8")
    print("gen-dashboard: rebuilt (%d active pages / %d problems / %d fault records)"
          % (sum(1 for _ in re.finditer(r"^\| `", text, re.M)),
             len([p for p in (ROOT / "problems").glob("*.md") if not p.name.startswith("_")]),
             sum(_registry_counts().values())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
