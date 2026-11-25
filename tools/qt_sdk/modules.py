"""Module availability views: adaptation matrix vs. actually built SDK.

Two report types behind the `modules` CLI subcommand:
- static_report(qt_version)    what the portgraph adaptation matrix says
                               for a Qt version, crossed with the default
                               `-skip` lists from building.QT_VERSIONS
- configured_report(sdk_dir)   which libQt5*.so files actually exist in
                               an installed SDK (+ config.summary hints)

Static classification:
- unsupported          the matrix marks the module blocked for that
                      version (or the whole section out of scope) -
                      platform-blocked, not enableable
- skipped_by_default   in the version's default skip list and not blocked
                      - buildable via `configure --with <module>`
- default_built        supported by the matrix and not skipped
- unknown              matrix row whose status cell could not be parsed
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

from . import building

KB_ROOT = Path(__file__).resolve().parent.parent.parent

# portgraph adaptation matrix (wiki module status snapshot)
DATA_FILE = KB_ROOT / "portgraph" / "data" / "qt-harmonyos-modules.md"

_VERSIONS = tuple(building.QT_VERSIONS)

# status cells in the matrix tables (supported / blocked marks)
_STATUS_CELL = {"✅": "supported", "❌": "unsupported"}

# a section heading carrying any of these marks is an out-of-scope block
_BLOCKED_MARKS = ("out of scope", "不在范围内")  # en + legacy zh

# first header cell of a module table (accept en and legacy zh)
_MODULE_HEADERS = ("模块", "module", "modules")

_LIB_NAME = re.compile(r"^lib(Qt5[A-Za-z0-9_]+)\.so")

# "Qt Gui:" style section headings in a config.summary
_SUMMARY_HEADING = re.compile(r"^\s*(Qt\s+[^:|]+?)\s*:\s*$")


def _display(raw: str) -> str:
    """Table cell -> display name (drop parenthesised qualifiers)."""
    name = re.sub(r"\s*[(（].*?[)）]", "", raw).strip()
    return name or raw.strip()


def _norm(raw: str) -> str:
    """Comparison key: lowercase, drop separators and the leading 'qt'
    ('Qt Location', 'qtlocation' and 'Qt-Location' all collapse alike)."""
    s = re.sub(r"[^a-z0-9]+", "", _display(raw).lower())
    return s[2:] if s.startswith("qt") else s


def _table_kind(cells: List[str], section: str) -> Optional[Dict]:
    """Classify a matrix table from its header row + section heading."""
    if any(mark in section.lower() for mark in _BLOCKED_MARKS):
        return {"kind": "blocked"}
    cols = {v: i for i, v in enumerate(cells) if v in _VERSIONS}
    if len(cols) == len(_VERSIONS) and cells and cells[0] in _MODULE_HEADERS:
        return {"kind": "status", "cols": cols}
    return None


def _add_row(modules: Dict[str, Dict], header: Dict,
             cells: List[str]) -> None:
    if not cells or not cells[0]:
        return
    key = _norm(cells[0])
    if not key:
        return
    entry = modules.setdefault(
        key, {"display": _display(cells[0]), "status": {}})
    if header["kind"] == "blocked":
        for v in _VERSIONS:
            entry["status"].setdefault(v, "unsupported")
        return
    for v, idx in header["cols"].items():
        cell = cells[idx] if idx < len(cells) else ""
        entry["status"].setdefault(v, _STATUS_CELL.get(cell, "unknown"))


def _parse_matrix(text: str) -> Dict[str, Dict]:
    """Parse the matrix tables into
    {norm_name: {"display": str, "status": {version: status}}}.

    Recognised tables (format: portgraph/data/qt-harmonyos-modules.md):
    - version status: header cells carry the version numbers, first column
      is the module column, cells hold the per-version status mark
    - blocked: the section heading marks the whole table out of scope
    Anything else (lookup guides, product tables) is ignored.
    """
    modules: Dict[str, Dict] = {}
    header: Optional[Dict] = None
    section = ""
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#"):
            section, header = line, None
            continue
        if not line.startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells and all(re.fullmatch(r"[-: ]*", c) for c in cells):
            continue                                  # separator row
        if header is None:
            header = _table_kind(cells, section)
        else:
            _add_row(modules, header, cells)
    return modules


def static_report(qt_version: str) -> dict:
    """Version module availability from portgraph data + default skip lists.
    Returns {qt_version, default_built, skipped_by_default, unsupported,
    unknown, source} - skipped_by_default are buildable via
    `configure --with`, unsupported are platform-blocked (not enableable)."""
    if qt_version not in building.QT_VERSIONS:
        raise ValueError("unsupported Qt version %r (known: %s)"
                         % (qt_version, ", ".join(sorted(_VERSIONS))))

    # skip entries keep their configure token so the resulting list is
    # directly usable with `configure --with <token>`
    skip_tokens: Dict[str, str] = {}
    for name in building.QT_VERSIONS[qt_version][1]:
        key = _norm(name)
        if key and key not in skip_tokens:
            skip_tokens[key] = name

    data: Dict[str, Dict] = {}
    parse_error: Optional[str] = None
    try:
        text = DATA_FILE.read_text(encoding="utf-8", errors="replace")
        data = _parse_matrix(text)
        if not data:
            parse_error = ("no module tables recognised in %s - matrix "
                           "format changed?" % DATA_FILE)
    except OSError as exc:
        parse_error = "cannot read %s (%s)" % (DATA_FILE, exc)

    def label(key: str) -> str:
        return data.get(key, {}).get("display") or skip_tokens.get(key) or key

    default_built: List[str] = []
    skipped: List[str] = []
    unsupported: List[str] = []
    unknown: List[str] = []
    for key in sorted(set(data) | set(skip_tokens),
                      key=lambda k: label(k).lower()):
        status = data.get(key, {}).get("status", {}).get(qt_version)
        if status == "unsupported":
            unsupported.append(label(key))
        elif key in skip_tokens:
            skipped.append(skip_tokens[key])
        elif status == "supported":
            default_built.append(label(key))
        else:
            unknown.append(label(key))

    return {"qt_version": qt_version,
            "default_built": default_built,
            "skipped_by_default": skipped,
            "unsupported": unsupported,
            "unknown": unknown,
            "source": str(DATA_FILE),
            "parse_error": parse_error}


def configured_report(sdk_dir, build_dir=None) -> dict:
    """Modules actually present in an installed SDK: glob libQt5*.so.
    Returns {modules, count, sdk_dir, from_summary}. from_summary lists
    modules mentioned in build_dir/config.summary when it exists."""
    found = set()
    if sdk_dir:
        lib_dir = Path(sdk_dir) / "lib"
        if lib_dir.is_dir():
            # versioned siblings (libQt5Core.so, libQt5Core.so.5, ...)
            # all collapse onto one module name - the set deduplicates
            for lib in lib_dir.glob("libQt5*.so*"):
                m = _LIB_NAME.match(lib.name)
                if m:
                    found.add(m.group(1))

    summary: List[str] = []
    if build_dir:
        path = Path(build_dir) / "config.summary"
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            names = set()
            for line in text.splitlines():
                m = _SUMMARY_HEADING.match(line)
                if m:
                    names.add(m.group(1).strip())
            summary = sorted(names)

    return {"modules": sorted(found), "count": len(found),
            "sdk_dir": str(sdk_dir or ""), "from_summary": summary}
