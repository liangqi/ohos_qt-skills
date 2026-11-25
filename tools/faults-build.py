#!/usr/bin/env python3
"""faults-build.py — build and validation tool for the fault base (symptom x cause x workaround x ticket graph).

Single source of truth (run build after editing these to rebuild the derived artifacts):
  faults/_data/symptoms.yaml     symptom S records + causes edges (S→C)
  faults/_data/workarounds.yaml  workaround W records + targets edges (W→C)
  faults/_data/tickets.yaml      upstream tracking ticket T records + tracks edges (T→C)
  faults/C-xxxx-*.md             root cause C in-depth pages (frontmatter is the source) + depends_on edges (C→C)

Derived artifacts (generated automatically, do not edit by hand):
  faults/_graph.yaml             machine-readable full graph (nodes + edges + aggregate overview + reverse-lookup indexes)
  faults/_registry.md            the registry (human/AI view)

Usage:
  python tools/faults-build.py build    # validate + rebuild _graph.yaml and _registry.md
  python tools/faults-build.py check    # consistency gate (exit 1 = has ERRORs)
  python tools/faults-build.py review   # scan for due reviews + status progression hints + list of drafts awaiting review
  python tools/faults-build.py all      # build + check

Design principle: humans write facts into the source of truth; the tool derives, validates and reminds (the LLM reasons, the tool owns the facts).
"""

from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qt_ohos import yaml_lite  # noqa: E402

KB_ROOT = Path(__file__).resolve().parent.parent
FAULTS_DIR = KB_ROOT / "faults"
DATA_DIR = FAULTS_DIR / "_data"
GRAPH_PATH = FAULTS_DIR / "_graph.yaml"
REGISTRY_PATH = FAULTS_DIR / "_registry.md"

# ── Enums (spec in faults/_index.md) ──────────────────────────────────────────
NATURES = {"defect", "limitation", "undetermined"}
RESPONSIBLES = {"qt-port", "qt-upstream", "ohos-runtime", "ohos-toolchain",
                "ohos-ndk", "third-party", "app", "undetermined"}
SEVERITIES = ["blocker", "critical", "high", "medium", "low"]
SEV_ICON = {"blocker": "⬜", "critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
C_STATUS = {"open", "diagnosed", "workaround", "reported", "fix-confirmed",
            "verified", "wontfix", "watching", "closed"}
S_STATUS = {"active", "mitigated", "resolved"}
W_STATUS = {"proposed", "tested", "adopted", "retired"}
W_RANK = {"adopted": 3, "tested": 2, "proposed": 1, "retired": 0}
T_TRACKERS = {"qt-bug", "ohos-issue", "gitee", "partner", "forum",
              "upstream"}   # upstream = third-party upstream (Mesa/freedesktop, etc.)
T_STATUS = {"draft", "submitted", "accepted", "dup", "wontfix",
            "fixed", "released", "closed"}
T_OPEN = {"submitted", "accepted", "fixed", "released"}   # tickets actively being tracked
EVIDENCE_TYPES = {"demo", "logs", "both", "source", "docs"}
EVIDENCE_REPRO = {"demo", "logs", "both"}     # reproducible-grade evidence (the bar for filing an upstream ticket)
# Disposition (derived from nature × responsible; the developer's view of "what to do when you hit it"; not stored in the source of truth, no double-writing)
DISPOSITIONS = {
    "must-adapt": "Must adapt for HarmonyOS",
    "qt-defect": "Qt issue",
    "system-defect": "System issue",
    "app-usage": "Application usage issue",
    "third-party": "Third-party library issue",
    "undetermined": "Pending classification",
}
DISPOSITION_ORDER = ["must-adapt", "qt-defect", "system-defect", "app-usage",
                     "third-party", "undetermined"]


def disposition_of(nature, responsible):
    if responsible == "app":
        return "app-usage"
    if nature == "limitation":
        return "must-adapt"
    if nature == "defect":
        if responsible in ("qt-port", "qt-upstream"):
            return "qt-defect"
        if responsible in ("ohos-runtime", "ohos-ndk", "ohos-toolchain"):
            return "system-defect"
        if responsible == "third-party":
            return "third-party"
    return "undetermined"
ROOT_CAUSE_STATES = {"fix-confirmed", "verified", "closed"}   # permanent-fix chain: no W/T completeness required
EXTERNAL_RESP = {"qt-port", "qt-upstream", "ohos-runtime", "ohos-ndk",
                 "ohos-toolchain", "third-party"}
# Chain completeness (closed-loop rule, see _index §4): gaps propagate upward; "unresolved" is decided by downstream completeness
CHAIN_ORDER = ["root-resolved", "temp-resolved", "missing-ticket",
               "missing-workaround", "both-missing"]
CHAIN_LABELS = {
    "root-resolved": "Root-fixed",
    "temp-resolved": "Temporarily resolved",
    "missing-ticket": "Missing ticket",
    "missing-workaround": "Missing workaround",
    "both-missing": "Both missing",
}


def is_planned_ticket(t) -> bool:
    """A scheduled ticket: status=draft with planned_filing set.

    It does not change the fact that "the chain still has a gap" (chain_state_of only
    counts T_OPEN); it just separates "nobody owns this" from "scheduled, to be filed" --
    the former is reported as WARN, the latter as INFO.
    """
    return t.get("status") == "draft" and bool(t.get("planned_filing"))


def chain_state_of(fm, has_live_w, has_open_t):
    """defect (external responsibility) temporarily resolved = W(adopted) and T(tracked) -- missing either means the loop is not closed;
    limitation / app / undetermined temporarily resolved = W(adopted);
    root-resolved = C.status has entered the permanent-fix chain (fix-confirmed and later); no W/T needed."""
    if fm.get("status") in ROOT_CAUSE_STATES:
        return "root-resolved", []
    gaps = []
    if not has_live_w:
        gaps.append("workaround")
    if (fm.get("nature") == "defect"
            and fm.get("responsible") in EXTERNAL_RESP and not has_open_t):
        gaps.append("ticket")
    if not gaps:
        return "temp-resolved", []
    if gaps == ["ticket"]:
        return "missing-ticket", gaps
    if gaps == ["workaround"]:
        return "missing-workaround", gaps
    return "both-missing", gaps


DOMAINS = {"build", "deploy", "runtime", "render", "api", "input",
           "lifecycle", "toolchain", "filesystem"}
FAULT_TYPES = {"bug", "crash", "build-blocker", "hang", "gap",
               "regression", "caveat", "deprecation"}

C_REQUIRED = ["id", "cid", "type", "title", "nature", "domain", "fault_type",
              "responsible", "component", "severity", "evidence_type", "status",
              "first_seen", "review_due", "created", "updated", "tags", "audience",
              "refs", "summary"]
S_REQUIRED = ["id", "title", "domain", "severity", "status", "causes", "first_seen"]
W_REQUIRED = ["id", "title", "targets", "status", "retire_when"]
T_REQUIRED = ["id", "tracker", "tracks", "status"]
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ID_RE = re.compile(r"^[SCWT]-\d{4}$")
QT_BASELINES = ["Qt 5.12.12", "Qt 5.15.16", "Qt 6.12"]


# ── Loading ─────────────────────────────────────────────────────────────────
def parse_frontmatter(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if not m:
        return None, "no frontmatter block"
    try:
        return (yaml_lite.parse(m.group(1)) or {}), None
    except yaml_lite.YamlLiteError as exc:
        return None, "frontmatter parse error: %s" % exc


def load_yaml_list(path: Path, key: str):
    if not path.is_file():
        return None, "file missing: %s" % path
    try:
        data = yaml_lite.parse(path.read_text(encoding="utf-8")) or {}
    except yaml_lite.YamlLiteError as exc:
        return None, "parse error: %s" % exc
    items = data.get(key)
    if not isinstance(items, list):
        return None, "missing top-level list '%s'" % key
    return items, None


def load_all():
    errors = []
    symptoms, err = load_yaml_list(DATA_DIR / "symptoms.yaml", "symptoms")
    if err:
        errors.append(("E", "symptoms.yaml", err))
    workarounds, err = load_yaml_list(DATA_DIR / "workarounds.yaml", "workarounds")
    if err:
        errors.append(("E", "workarounds.yaml", err))
    tickets, err = load_yaml_list(DATA_DIR / "tickets.yaml", "tickets")
    if err:
        errors.append(("E", "tickets.yaml", err))
    causes = []
    for path in sorted(FAULTS_DIR.glob("C-*.md")):
        fm, err = parse_frontmatter(path)
        if err:
            errors.append(("E", path.name, err))
            continue
        causes.append({"_path": path, "_fm": fm})
    return (symptoms or [], workarounds or [], tickets or [], causes), errors


# ── Validation ──────────────────────────────────────────────────────────────
def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _check_enum(errors, where, value, allowed, label):
    if value not in allowed:
        errors.append(("E", where, "%s '%s' not in %s" % (label, value, sorted(allowed))))


def _check_date(errors, where, value, label="date"):
    if value in ("", None):
        return
    if not isinstance(value, str) or not DATE_RE.match(value):
        errors.append(("E", where, "%s '%s' is not YYYY-MM-DD" % (label, value)))


def check_all(symptoms, workarounds, tickets, causes):
    errors = []
    warns = []
    infos = []
    # chain-completeness aggregation (shared by lint and generation; idempotent)
    aggregate(symptoms, workarounds, tickets, causes)
    c_ids = [c["_fm"].get("cid") for c in causes]
    s_ids = [s.get("id") for s in symptoms]
    w_ids = [w.get("id") for w in workarounds]
    t_ids = [t.get("id") for t in tickets]

    # ID format and uniqueness
    for label, ids in (("S", s_ids), ("C", c_ids), ("W", w_ids), ("T", t_ids)):
        for i in ids:
            if not (isinstance(i, str) and ID_RE.match(i) and i[0] == label):
                errors.append(("E", label, "bad id: %r" % i))
        dup = {x for x in ids if isinstance(x, str) and ids.count(x) > 1}
        if dup:
            errors.append(("E", label, "duplicate ids: %s" % sorted(dup)))

    cause_set = set(c_ids)
    # symptoms
    for s in symptoms:
        where = s.get("id") or "?"
        for f in S_REQUIRED:
            if s.get(f) in (None, ""):
                errors.append(("E", where, "missing field: %s" % f))
        _check_enum(errors, where, s.get("domain"), DOMAINS, "domain")
        _check_enum(errors, where, s.get("severity"), set(SEVERITIES), "severity")
        _check_enum(errors, where, s.get("status"), S_STATUS, "status")
        _check_date(errors, where, s.get("first_seen"), "first_seen")
        for c in _as_list(s.get("causes")):
            if c not in cause_set:
                errors.append(("E", where, "causes target missing: %s" % c))
        rel = s.get("cause_relation") or "any_of"
        if rel not in ("any_of", "all_of"):
            errors.append(("E", where, "bad cause_relation: %s" % rel))
        if len(_as_list(s.get("causes"))) < 2 and s.get("cause_relation"):
            errors.append(("E", where, "cause_relation set but <2 causes"))

    # causes (C pages)
    for c in causes:
        fm = c["_fm"]
        where = c["_path"].name
        for f in C_REQUIRED:
            if fm.get(f) in (None, ""):
                errors.append(("E", where, "missing field: %s" % f))
        cid = fm.get("cid")
        if isinstance(cid, str) and not where.startswith(cid + "-"):
            errors.append(("E", where, "filename does not start with %s-" % cid))
        if fm.get("type") != "cause":
            errors.append(("E", where, "type must be 'cause'"))
        _check_enum(errors, where, fm.get("nature"), NATURES, "nature")
        _check_enum(errors, where, fm.get("domain"), DOMAINS, "domain")
        _check_enum(errors, where, fm.get("fault_type"), FAULT_TYPES, "fault_type")
        _check_enum(errors, where, fm.get("responsible"), RESPONSIBLES, "responsible")
        _check_enum(errors, where, fm.get("severity"), set(SEVERITIES), "severity")
        _check_enum(errors, where, fm.get("evidence_type"), EVIDENCE_TYPES, "evidence_type")
        et = fm.get("evidence_type")
        if et == "docs" and fm.get("nature") == "defect":
            errors.append(("E", where,
                           "defect cannot be evidenced by docs alone (docs is limitation-only)"))
        if fm.get("nature") == "limitation" and et not in ("docs", "source", "logs"):
            errors.append(("E", where,
                           "limitation evidence_type must be docs/source/logs, got '%s'" % et))
        _check_enum(errors, where, fm.get("status"), C_STATUS, "status")
        _check_date(errors, where, fm.get("first_seen"), "first_seen")
        _check_date(errors, where, fm.get("review_due"), "review_due")
        _check_date(errors, where, fm.get("created"), "created")
        _check_date(errors, where, fm.get("updated"), "updated")
        if fm.get("nature") == "limitation" and not (fm.get("evidence") or fm.get("evolution")):
            errors.append(("E", where, "limitation needs evidence or evolution"))
        for d in _as_list(fm.get("depends_on")):
            if d not in cause_set or d == cid:
                errors.append(("E", where, "depends_on target missing/self: %s" % d))
        for r in _as_list(fm.get("refs")):
            if isinstance(r, str) and r.startswith("fault-"):
                if r.removeprefix("fault-") not in cause_set | set(s_ids):
                    errors.append(("E", where, "refs target missing: %s" % r))

    # workarounds
    for w in workarounds:
        where = w.get("id") or "?"
        for f in W_REQUIRED:
            if w.get(f) in (None, ""):
                errors.append(("E", where, "missing field: %s" % f))
        _check_enum(errors, where, w.get("status"), W_STATUS, "status")
        v = w.get("verified")
        if isinstance(v, dict):
            _check_date(errors, where, v.get("date"), "verified.date")
        for tgt in _as_list(w.get("targets")):
            if tgt not in cause_set:
                errors.append(("E", where, "targets missing: %s" % tgt))

    # tickets
    for t in tickets:
        where = t.get("id") or "?"
        for f in T_REQUIRED:
            if t.get(f) in (None, ""):
                errors.append(("E", where, "missing field: %s" % f))
        _check_enum(errors, where, t.get("tracker"), T_TRACKERS, "tracker")
        _check_enum(errors, where, t.get("status"), T_STATUS, "status")
        _check_date(errors, where, t.get("filed"), "filed")
        if t.get("status") == "released" and not t.get("fix_version"):
            errors.append(("E", where, "released ticket needs fix_version"))
        for tr in _as_list(t.get("tracks")):
            if tr not in cause_set:
                errors.append(("E", where, "tracks missing: %s" % tr))

    # ── lint: status progression consistency (WARN; humans decide the facts, the tool only reminds) ──
    by_cid = {c["_fm"].get("cid"): c["_fm"] for c in causes}
    for cid, fm in by_cid.items():
        ws = [w for w in workarounds if cid in _as_list(w.get("targets"))]
        ts = [t for t in tickets if cid in _as_list(t.get("tracks"))]
        has_live_w = any(w.get("status") in ("tested", "adopted") for w in ws)
        has_open_t = any(t.get("status") in T_OPEN for t in ts)
        planned_ts = [t for t in ts if is_planned_ticket(t)]
        planned_note = ", ".join("%s (planned filing %s)" % (t.get("id"), t.get("planned_filing"))
                                for t in planned_ts)
        if fm.get("status") == "workaround" and not has_live_w:
            warns.append(("W", cid, "status=workaround but no tested/adopted W targets it"))
        if fm.get("status") == "workaround" and fm.get("_gaps"):
            if fm["_gaps"] == ["ticket"] and planned_ts:
                infos.append(("I", cid,
                              "missing ticket is scheduled: %s -- the chain counts as not closed; "
                              "after filing, set that ticket to submitted"
                              % planned_note))
            else:
                warns.append(("W", cid,
                              "status=workaround but the chain is not closed (missing %s) -- "
                              "by the closed-loop rule this is not temporarily resolved; fill the gap"
                              % "/".join(fm["_gaps"])))
        if fm.get("status") == "reported" and not has_open_t:
            warns.append(("W", cid, "status=reported but no open T tracks it"))
        if (fm.get("nature") == "defect"
                and fm.get("responsible") in ("qt-port", "qt-upstream")
                and fm.get("evidence_type") == "source"):
            msg = ("Qt-side defect evidenced only by 'source': add a minimal repro demo or "
                   "runtime logs to make it solid (required before filing an upstream T; "
                   "matches the qt-bug-report HARD gate)")
            if planned_ts:
                infos.append(("I", cid, msg + "; scheduled %s" % planned_note))
            else:
                warns.append(("W", cid, msg))
        for t in ts:
            if t.get("status") in ("fixed", "released") and fm.get("status") \
                    not in ("fix-confirmed", "verified", "closed"):
                warns.append(("W", cid,
                              "T %s is %s but C status is '%s' — advance to fix-confirmed"
                              % (t.get("id"), t.get("status"), fm.get("status"))))

    # Evidence gate: a defect/undetermined cause with an open upstream ticket must hold reproducible-grade evidence (demo/logs/both)
    for t in tickets:
        if t.get("status") in T_OPEN and t.get("tracker") != "forum":
            for cid in _as_list(t.get("tracks")):
                fm = by_cid.get(cid)
                if fm and fm.get("nature") in ("defect", "undetermined") \
                        and fm.get("evidence_type") not in EVIDENCE_REPRO:
                    errors.append(("E", t.get("id") or "?",
                                   "open upstream ticket requires reproducible evidence "
                                   "(demo/logs/both) on %s, got '%s' — tickets without "
                                   "reproducible material are not filed (qt-bug-report HARD gate)"
                                   % (cid, fm.get("evidence_type"))))
    # Chain completeness: gaps propagate upward; an upstream claim of resolution is bounded by downstream completeness
    for s in symptoms:
        cs = _as_list(s.get("causes"))
        live_ws = [by_cid[c]["_live_ws"] for c in cs if c in by_cid]
        if s.get("status") == "resolved" and s.get("_gaps"):
            errors.append(("E", s.get("id"),
                           "S.status=resolved but the chain has gaps (missing %s) -- downstream "
                           "is not closed, so upstream may not claim full resolution (downgrade to mitigated/active)"
                           % "/".join(s["_gaps"])))
        if s.get("status") == "mitigated":
            if cs and live_ws and not any(live_ws):
                errors.append(("E", s.get("id"),
                               "S.status=mitigated but no adopted W backs it -- a mitigation claim "
                               "must be backed by an adopted workaround (otherwise mark it active)"))
    return errors, warns, infos


# ── Aggregation and generation ──────────────────────────────────────────────
def aggregate(symptoms, workarounds, tickets, causes):
    for c in causes:
        fm = c["_fm"]
        cid = fm.get("cid")
        fm["_manifests"] = [s["id"] for s in symptoms if cid in _as_list(s.get("causes"))]
        ws = [w for w in workarounds if cid in _as_list(w.get("targets"))]
        fm["_workarounds"] = [w["id"] for w in ws]
        live = [w for w in ws if w.get("status") in W_RANK]
        fm["_workaround_state"] = (max(live, key=lambda w: W_RANK[w["status"]])["status"]
                                   if live else "none")
        fm["_tickets"] = [t["id"] for t in tickets if cid in _as_list(t.get("tracks"))]
        fm["_fixed_in"] = "; ".join(
            t["fix_version"] for t in tickets
            if cid in _as_list(t.get("tracks")) and t.get("status") == "released"
            and t.get("fix_version"))
        fm["_disposition"] = disposition_of(fm.get("nature"), fm.get("responsible"))
        live_ws = [w["id"] for w in ws if w.get("status") == "adopted"]
        open_ts = [t["id"] for t in tickets
                   if cid in _as_list(t.get("tracks")) and t.get("status") in T_OPEN]
        planned_ts = [t["id"] for t in tickets
                      if cid in _as_list(t.get("tracks")) and is_planned_ticket(t)]
        fm["_live_ws"] = live_ws
        fm["_open_ts"] = open_ts
        fm["_planned_ts"] = planned_ts
        fm["_chain_state"], fm["_gaps"] = chain_state_of(fm, bool(live_ws), bool(open_ts))

    # S chain aggregation: gaps propagate upward (if any cause has a gap, S is not closed; gaps are unioned)
    by_cid = {c["_fm"].get("cid"): c["_fm"] for c in causes}
    for s in symptoms:
        cs = _as_list(s.get("causes"))
        if not cs:
            s["_chain_state"], s["_gaps"] = "unattributed", ["cause"]
            continue
        gaps = []
        worst = 0
        for cid in cs:
            fm = by_cid.get(cid)
            if not fm:
                continue
            idx = CHAIN_ORDER.index(fm["_chain_state"])
            if idx > worst:
                worst = idx
            for g in fm["_gaps"]:
                if g not in gaps:
                    gaps.append(g)
        s["_chain_state"] = CHAIN_ORDER[worst]
        s["_gaps"] = gaps


def _q(value) -> str:
    """YAML scalar output: a safe bare value or double-quoted."""
    s = str(value)
    if s == "":
        return '""'
    if re.match(r"^[A-Za-z0-9_.\-]+$", s) and s not in ("true", "false", "null", "yes", "no"):
        return s
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _flow(items) -> str:
    return "[" + ", ".join(_q(i) for i in items) + "]"


def today():
    return datetime.date.today().isoformat()


def gen_graph(symptoms, workarounds, tickets, causes) -> str:
    natures = {n: sum(1 for c in causes if c["_fm"].get("nature") == n)
               for n in ("defect", "limitation", "undetermined")}
    cstat = {}
    for c in causes:
        cstat[c["_fm"]["status"]] = cstat.get(c["_fm"]["status"], 0) + 1
    dstat = {}
    for c in causes:
        d = c["_fm"].get("_disposition")
        dstat[d] = dstat.get(d, 0) + 1
    out = []
    out.append("# faults/_graph.yaml — the fault graph (machine-readable full graph) [GENERATED, DO NOT EDIT BY HAND]")
    out.append("#")
    out.append("# Rebuild: python tools/faults-build.py build")
    out.append("# Source of truth: _data/symptoms.yaml (S + causes edges) / _data/workarounds.yaml (W + targets edges) /")
    out.append("#       _data/tickets.yaml (T + tracks edges) / C-*.md frontmatter (C + depends_on edges)")
    out.append("# Model spec: faults/_index.md | human view: faults/_registry.md (also derived)")
    out.append("#")
    out.append("# Nodes: S symptom (application-layer behavior, the lookup entry) | C cause (defect gets fixed / limitation = platform limitation -> alternative)")
    out.append("#       W workaround (proposed->tested->adopted->retired) | T upstream tracking ticket (Qt ticket / Huawei ticket / deliverable)")
    out.append("# Edges: causes S->C (with multiple causes, cause_relation: any_of|all_of) | targets W->C | tracks T->C")
    out.append("#      depends_on C->C (evidenced blocking only) | manifests is the derived reverse index of causes")
    out.append("")
    out.append("schema: 2")
    out.append("updated: %s" % today())
    out.append("")
    out.append("counts:")
    out.append("  symptoms: %d" % len(symptoms))
    out.append("  causes: %d" % len(causes))
    out.append("  workarounds: %d" % len(workarounds))
    out.append("  tickets: %d" % len(tickets))
    out.append("  nature: %s" % _flow(
        ["%s %d" % (k, v) for k, v in natures.items()]))
    out.append("  cause_status: %s" % _flow(
        ["%s %d" % (k, v) for k, v in sorted(cstat.items())]))
    out.append("  disposition: %s" % _flow(
        ["%s %d" % (k, dstat[k]) for k in DISPOSITION_ORDER if k in dstat]))
    chain = {}
    for c in causes:
        k = c["_fm"]["_chain_state"]
        chain[k] = chain.get(k, 0) + 1
    out.append("  chain_state: %s" % _flow(
        ["%s %d" % (k, chain[k]) for k in CHAIN_ORDER if k in chain]))
    out.append("")
    out.append("symptoms:")
    for s in symptoms:
        out.append("  - id: %s" % _q(s["id"]))
        out.append("    title: %s" % _q(s.get("title", "")))
        out.append("    domain: %s" % _q(s.get("domain", "")))
        out.append("    severity: %s" % _q(s.get("severity", "")))
        out.append("    status: %s" % _q(s.get("status", "")))
        out.append("    causes: %s" % _flow(_as_list(s.get("causes"))))
        if s.get("cause_relation") and len(_as_list(s.get("causes"))) > 1:
            out.append("    cause_relation: %s" % _q(s["cause_relation"]))
        out.append("    first_seen: %s" % _q(s.get("first_seen", "")))
        if _as_list(s.get("refs")):
            out.append("    refs: %s" % _flow(_as_list(s.get("refs"))))
        out.append("    chain_state: %s" % _q(s.get("_chain_state", "")))
        out.append("    gaps: %s" % _flow(s.get("_gaps") or []))
    out.append("")
    out.append("causes:")
    for c in causes:
        fm = c["_fm"]
        out.append("  - id: %s" % _q(fm["cid"]))
        out.append("    page: %s" % _q(c["_path"].name))
        out.append("    title: %s" % _q(fm.get("title", "")))
        out.append("    nature: %s" % _q(fm.get("nature", "")))
        out.append("    responsible: %s" % _q(fm.get("responsible", "")))
        out.append("    disposition: %s" % _q(fm.get("_disposition", "")))
        out.append("    domain: %s" % _q(fm.get("domain", "")))
        out.append("    severity: %s" % _q(fm.get("severity", "")))
        out.append("    evidence_type: %s" % _q(fm.get("evidence_type", "")))
        out.append("    status: %s" % _q(fm.get("status", "")))
        out.append("    manifests: %s" % _flow(fm["_manifests"]))
        out.append("    workarounds: %s" % _flow(fm["_workarounds"]))
        out.append("    workaround_state: %s" % _q(fm["_workaround_state"]))
        out.append("    tickets: %s" % _flow(fm["_tickets"]))
        out.append("    fixed_in: %s" % _q(fm.get("_fixed_in", "")))
        out.append("    depends_on: %s" % _flow(_as_list(fm.get("depends_on"))))
        out.append("    affects_qt: %s" % _flow(_as_list(fm.get("affects_qt"))))
        out.append("    affects_ohos: %s" % _flow(_as_list(fm.get("affects_ohos"))))
        out.append("    review_due: %s" % _q(fm.get("review_due", "")))
        out.append("    chain_state: %s" % _q(fm.get("_chain_state", "")))
        out.append("    gaps: %s" % _flow(fm.get("_gaps") or []))
    out.append("")
    out.append("workarounds:")
    for w in workarounds:
        out.append("  - id: %s" % _q(w["id"]))
        out.append("    title: %s" % _q(w.get("title", "")))
        out.append("    targets: %s" % _flow(_as_list(w.get("targets"))))
        out.append("    status: %s" % _q(w.get("status", "")))
        v = w.get("verified")
        if isinstance(v, dict):
            out.append("    verified:")
            out.append("      date: %s" % _q(v.get("date", "")))
            out.append("      env: %s" % _q(v.get("env", "")))
        out.append("    retire_when: %s" % _q(w.get("retire_when", "")))
        out.append("    detail: %s" % _q(w.get("detail", "")))
    out.append("")
    out.append("tickets:")
    for t in tickets:
        out.append("  - id: %s" % _q(t["id"]))
        out.append("    tracker: %s" % _q(t.get("tracker", "")))
        out.append("    number: %s" % _q(t.get("number", "")))
        out.append("    url: %s" % _q(t.get("url", "")))
        out.append("    tracks: %s" % _flow(_as_list(t.get("tracks"))))
        out.append("    status: %s" % _q(t.get("status", "")))
        out.append("    filed: %s" % _q(t.get("filed", "")))
        out.append("    fix_version: %s" % _q(t.get("fix_version", "")))
        out.append("    notes: %s" % _q(t.get("notes", "")))
    return "\n".join(out) + "\n"


def _ws_for(symptoms, workarounds, sid):
    """How a symptom is mitigated (aggregates the live W ids of its causes)."""
    titles = []
    for s in symptoms:
        if s["id"] != sid:
            continue
        for c in _as_list(s.get("causes")):
            for w in workarounds:
                if c in _as_list(w.get("targets")) and w.get("status") in ("tested", "adopted"):
                    titles.append(w["id"])
    return "; ".join(titles) if titles else "—"


def _carry(workarounds, cid):
    ts = [w["id"] for w in workarounds
          if cid in _as_list(w.get("targets")) and w.get("status") != "retired"]
    return "; ".join(ts) if ts else "—"


def _cut(text, n):
    return text if len(text) <= n else text[:n] + "…"


def gen_registry(symptoms, workarounds, tickets, causes, warns) -> str:
    natures = {n: [c for c in causes if c["_fm"].get("nature") == n]
               for n in ("defect", "undetermined", "limitation")}
    done = [c for c in causes if c["_fm"].get("status") in ("verified", "closed")]
    L = []
    L.append("---")
    L.append("updated: %s" % today())
    L.append("counts:")
    L.append("  symptoms: %d" % len(symptoms))
    L.append("  causes: %d" % len(causes))
    L.append("  workarounds: %d" % len(workarounds))
    L.append("  tickets: %d" % len(tickets))
    L.append("description: >")
    L.append("  The fault registry (human view of the symptom x cause x workaround x ticket graph).")
    L.append("  [GENERATED, DO NOT EDIT BY HAND -- rebuild with python tools/faults-build.py build]")
    L.append("  The machine-readable full graph is _graph.yaml; the spec is _index.md.")
    L.append("---")
    L.append("")
    L.append("# Fault registry")
    L.append("")
    L.append("> Look things up by behavior in §Symptom index (the main entry); for \"who owns it, defect or limitation, fixed or not, how to work around it\", see the causes.")
    L.append("> Machine-readable full graph (one file, one load): [_graph.yaml](_graph.yaml) | spec: [_index](_index.md)")
    L.append("> **This file is a derived artifact**: the source of truth is `_data/*.yaml` and `C-*.md`; after editing them run `python tools/faults-build.py build`.")
    L.append("")
    L.append("## Statistics")
    L.append("")
    L.append("| Dimension | Distribution |")
    L.append("|------|------|")
    ns = " / ".join("%s %d" % (k, len(v)) for k, v in natures.items() if v)
    L.append("| Nodes | symptoms %d (active %d / mitigated %d / resolved %d) / causes %d (%s) / workarounds %d / tickets %d |"
             % (len(symptoms),
                sum(1 for s in symptoms if s.get("status") == "active"),
                sum(1 for s in symptoms if s.get("status") == "mitigated"),
                sum(1 for s in symptoms if s.get("status") == "resolved"),
                len(causes), ns, len(workarounds), len(tickets)))
    resp = {}
    for c in causes:
        r = c["_fm"].get("responsible")
        resp[r] = resp.get(r, 0) + 1
    L.append("| Responsibility | %s |" % " · ".join("%s %d" % kv for kv in sorted(resp.items())))
    dstat = {}
    for c in causes:
        d = c["_fm"].get("_disposition")
        dstat[d] = dstat.get(d, 0) + 1
    L.append("| Disposition | %s |" % " · ".join(
        "%s %d" % (DISPOSITIONS[k], dstat[k])
        for k in DISPOSITION_ORDER if k in dstat))
    chain = {}
    for c in causes:
        chain[c["_fm"]["_chain_state"]] = chain.get(c["_fm"]["_chain_state"], 0) + 1
    L.append("| Chain closure | root-fixed %d · temporarily resolved %d · not closed %d (%s) |" % (
        chain.get("root-resolved", 0), chain.get("temp-resolved", 0),
        sum(v for k, v in chain.items() if k.startswith("missing") or k == "both-missing"),
        " · ".join("%s %d" % (CHAIN_LABELS[k], chain[k])
                   for k in ("missing-ticket", "missing-workaround", "both-missing")
                   if k in chain)))
    L.append("| Severity | %s |" % " · ".join(
        "%s %d" % (s, sum(1 for c in causes if c["_fm"].get("severity") == s))
        for s in SEVERITIES if any(c["_fm"].get("severity") == s for c in causes)))
    L.append("")
    # symptom index
    L.append("## Symptom index (main entry)")
    L.append("")
    L.append("| S | Symptom | Domain | Severity | Status | Closure | Cause (nature) | Mitigation (W) |")
    L.append("|---|------|----|:------:|------|------|---------------|----------|")
    for s in symptoms:
        cs = _as_list(s.get("causes"))
        clinks = []
        for c in causes:
            fm = c["_fm"]
            if fm.get("cid") in cs:
                clinks.append("[%s](%s) (%s)" % (fm["cid"], c["_path"].name, fm.get("nature")))
        rel = " ×".join(clinks)
        if len(cs) > 1:
            rel += " (%s)" % (s.get("cause_relation") or "any_of")
        gap_label = {"workaround": "workaround", "ticket": "ticket", "cause": "cause"}
        gaps = s.get("_gaps") or []
        cell = ("both missing" if len(gaps) >= 2
                else ("—" if not gaps else "missing " + gap_label.get(gaps[0], gaps[0])))
        L.append("| %s | %s | %s | %s %s | %s | %s | %s | %s |" % (
            s["id"], _cut(s.get("title", ""), 80), s.get("domain"),
            SEV_ICON.get(s.get("severity"), ""), s.get("severity"),
            "**%s**" % s.get("status") if s.get("status") == "active" else s.get("status"),
            cell, rel, _ws_for(symptoms, workarounds, s["id"])))
    L.append("")
    # by disposition (developer's view)
    L.append("## By disposition (developer's view: what to do when you hit it)")
    L.append("")
    L.append("> Derived view (computed automatically from nature × responsible; spec in _index §3): **Must adapt for HarmonyOS** = this is how the platform/SDK is specified; change your own code, there is no upstream fix to wait for; **Qt issue** = wait for a Qt fix / local patch / file a QTBUG; **System issue** = wait for a system/SDK/toolchain release or file a ticket with Huawei; **Application usage issue** = change the application code, not a framework problem; **Third-party library issue** = a defect in the third-party library itself; **Pending classification** = wait for upstream to classify it.")
    L.append("")
    for key in DISPOSITION_ORDER:
        rows = [c for c in causes if c["_fm"].get("_disposition") == key]
        if not rows:
            continue
        L.append("### %s (%s, %d)" % (DISPOSITIONS[key], key, len(rows)))
        L.append("")
        L.append("| CID | Cause | nature/responsible | Status | Workaround (W) / route |")
        L.append("|-----|------|--------------------|------|---------------|")
        for c in rows:
            fm = c["_fm"]
            ws = _carry(workarounds, fm["cid"])
            path = fm.get("fix_route") or fm.get("evolution") or ""
            cell = ws if ws != "—" else (path or "—")
            L.append("| [%s](%s) | %s | %s/%s | %s | %s |" % (
                fm["cid"], c["_path"].name, _cut(fm.get("title", ""), 60),
                fm.get("nature"), fm.get("responsible"), fm.get("status"),
                _cut(cell, 60)))
        L.append("")
    # not-closed list (chain completeness gaps)
    L.append("## Not closed (chain completeness gaps -- to be filled; rules in _index §4)")
    L.append("")
    L.append("> Closed-loop rule: **defect (external responsibility) temporarily resolved = an adopted workaround (W adopted) + a tracked ticket (T)**; "
             "limitation / application issue / unclassified = an adopted workaround; root-fixed = fix-confirmed and later. "
             "**Gaps propagate upward**: a symptom's claim of resolution is bounded by the completeness of its cause chain (enforced by check).")
    L.append("")
    for key, label in (
            ("missing-ticket", "Missing ticket (workaround in place; ticket to be filed/tracked)"),
            ("missing-workaround", "Missing workaround (no adopted workaround/adaptation)"),
            ("both-missing", "Both missing (unresolved)")):
        rows = [c for c in causes if c["_fm"]["_chain_state"] == key]
        if not rows:
            continue
        L.append("### %s (%d)" % (label, len(rows)))
        L.append("")
        L.append("| CID | Cause | Disposition | Status | Workaround (W) | Ticket (T) | Symptoms |")
        L.append("|-----|------|------|------|-----------|---------|------|")
        for c in rows:
            fm = c["_fm"]
            L.append("| [%s](%s) | %s | %s | %s | %s | %s | %s |" % (
                fm["cid"], c["_path"].name, _cut(fm.get("title", ""), 52),
                DISPOSITIONS.get(fm.get("_disposition"), ""), fm.get("status"),
                ", ".join(fm.get("_live_ws") or []) or "✗",
                ", ".join(list(fm.get("_open_ts") or [])
                          + ["%s (planned)" % t for t in (fm.get("_planned_ts") or [])]) or "✗",
                ", ".join(fm.get("_manifests") or []) or "—"))
        L.append("")
    # defects
    L.append("## Defects (defect -- will be fixed; track the fix version and upstream ticket)")
    L.append("")
    L.append("| CID | Cause | Responsible | Severity | Status | Workaround (W) | Ticket (T) | Fix route | Review due |")
    L.append("|-----|------|------|:------:|------|--------------|------------|-------------|---------|")
    for c in natures["defect"]:
        fm = c["_fm"]
        L.append("| [%s](%s) | %s | %s | %s %s | %s | %s | %s | %s | %s |" % (
            fm["cid"], c["_path"].name, _cut(fm.get("title", ""), 68), fm.get("responsible"),
            SEV_ICON.get(fm.get("severity"), ""), fm.get("severity"), fm.get("status"),
            _carry(workarounds, fm["cid"]),
            "; ".join(fm["_tickets"]) or "—",
            _cut(fm.get("fix_route") or "—", 60), fm.get("review_due", "")))
    L.append("")
    L.append("**Undetermined (undetermined -- awaiting classification, track the upstream reply; the CID stays the same if reclassified)**")
    L.append("")
    L.append("| CID | Cause | Responsible | Severity | Status | Workaround (W) | Ticket (T) | Classification outcome | Review due |")
    L.append("|-----|------|------|:------:|------|--------------|------------|---------|---------|")
    for c in natures["undetermined"]:
        fm = c["_fm"]
        L.append("| [%s](%s) | %s | %s | %s %s | %s | %s | %s | see the C page | %s |" % (
            fm["cid"], c["_path"].name, _cut(fm.get("title", ""), 68), fm.get("responsible"),
            SEV_ICON.get(fm.get("severity"), ""), fm.get("severity"), fm.get("status"),
            _carry(workarounds, fm["cid"]), "; ".join(fm["_tickets"]) or "—",
            fm.get("review_due", "")))
    L.append("")
    # limitations
    L.append("## Limitations (limitation -- this is how the platform works; track alternatives and evolution)")
    L.append("")
    L.append("| CID | Limitation | Classification evidence | Alternative (W) | Evolution | Status |")
    L.append("|-----|------|---------|--------------|------|------|")
    for c in natures["limitation"]:
        fm = c["_fm"]
        L.append("| [%s](%s) | %s | %s | %s | %s | %s |" % (
            fm["cid"], c["_path"].name, _cut(fm.get("title", ""), 68),
            _cut(fm.get("evidence") or "—", 60), _carry(workarounds, fm["cid"]),
            _cut(fm.get("evolution") or "—", 56), fm.get("status")))
    L.append("")
    # workaround list
    L.append("## Workarounds (W)")
    L.append("")
    L.append("| W | Workaround | Targets | Status | Last verified | Retire when |")
    L.append("|---|------|---------|------|---------|---------|")
    for w in workarounds:
        v = w.get("verified")
        vtxt = "%s %s" % (v.get("date", ""), v.get("env", "")) if isinstance(v, dict) else "—"
        L.append("| %s | %s | %s | %s | %s | %s |" % (
            w["id"], _cut(w.get("title", ""), 84), "; ".join(_as_list(w.get("targets"))),
            w.get("status"), _cut(vtxt.strip() or "—", 56),
            _cut(w.get("retire_when") or "—", 60)))
    L.append("")
    # ticket list
    L.append("## Tickets (T)")
    L.append("")
    L.append("| T | Tracker | Number | Tracks | Status | Fix version | Filed | Notes |")
    L.append("|---|------|------|---------|------|---------|--------|------|")
    for t in tickets:
        num = t.get("number") or "—"
        if t.get("url"):
            num = "[%s](%s)" % (num, t["url"])
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
            t["id"], t.get("tracker"), num, "; ".join(_as_list(t.get("tracks"))),
            t.get("status"), t.get("fix_version") or "—", t.get("filed") or "—",
            _cut(t.get("notes") or "—", 64)))
    L.append("")
    # relationship overview
    L.append("## Relationship overview")
    L.append("")
    L.append("```")
    for s in symptoms:
        cs = _as_list(s.get("causes"))
        head = "%s %s" % (s["id"], _cut(s.get("title", ""), 28))
        fms = {c["_fm"]["cid"]: c["_fm"] for c in causes}
        if len(cs) == 1:
            fm = fms.get(cs[0], {})
            L.append("%s ──→ %s %s [%s/%s]" % (
                head.ljust(38), cs[0], _cut(fm.get("title", ""), 36),
                fm.get("nature"), fm.get("responsible")))
        else:
            for i, cid in enumerate(cs):
                fm = fms.get(cid, {})
                branch = "──┬→" if i == 0 else "    └→"
                tail = "  ← %s (combined)" % s.get("cause_relation") if i == 0 else ""
                L.append("%s %s %s %s [%s/%s]%s" % (
                    head.ljust(38) if i == 0 else " " * 38, branch, cid,
                    _cut(fm.get("title", ""), 36), fm.get("nature"),
                    fm.get("responsible"), tail))
    dep = [(c["_fm"]["cid"], d) for c in causes
           for d in _as_list(c["_fm"].get("depends_on"))]
    L.append("C→C depends_on: %s" % ("; ".join("%s←%s" % (a, b) for a, b in dep) or "none yet"))
    orphan = [s["id"] for s in symptoms if not _as_list(s.get("causes"))]
    L.append("Orphan symptoms (empty causes): %s" % ("; ".join(orphan) or "none"))
    L.append("```")
    L.append("")
    # version baselines
    L.append("## By version baseline (upgrade checklist)")
    L.append("")
    L.append("Check here before switching Qt / OHOS versions: the causes still active on the target version + the workarounds that must be carried along (W ids).")
    L.append("")
    for baseline in QT_BASELINES:
        rows = [c for c in causes
                if any(isinstance(a, str) and a.startswith(baseline)
                       for a in _as_list(c["_fm"].get("affects_qt")))]
        if not rows:
            continue
        L.append("### %s" % baseline)
        L.append("")
        L.append("| Cause | Status | Carried (W) |")
        L.append("|------|------|------------|")
        for c in rows:
            fm = c["_fm"]
            L.append("| %s | %s | %s |" % (fm["cid"], fm.get("status"),
                                           _carry(workarounds, fm["cid"])))
        L.append("")
    others = [c for c in causes
              if _as_list(c["_fm"].get("affects_qt")) and not any(
                  isinstance(a, str) and a.startswith(b)
                  for b in QT_BASELINES for a in _as_list(c["_fm"].get("affects_qt")))]
    if others:
        L.append("### Other Qt versions")
        L.append("")
        L.append("| Cause | Status | Affected versions | Carried (W) |")
        L.append("|------|------|---------|------------|")
        for c in others:
            fm = c["_fm"]
            L.append("| %s | %s | %s | %s |" % (
                fm["cid"], fm.get("status"),
                _cut("; ".join(str(a) for a in _as_list(fm.get("affects_qt"))), 60),
                _carry(workarounds, fm["cid"])))
        L.append("")
    L.append("### OHOS API / system versions")
    L.append("")
    L.append("| Cause | Affected versions | Carried (W) |")
    L.append("|------|-----------|------------|")
    for c in causes:
        fm = c["_fm"]
        if not _as_list(fm.get("affects_ohos")):
            continue
        L.append("| %s | %s | %s |" % (
            fm["cid"], _cut("; ".join(str(a) for a in _as_list(fm.get("affects_ohos"))), 80),
            _carry(workarounds, fm["cid"])))
    L.append("")
    # reviews due
    L.append("## Reviews due")
    L.append("")
    L.append("| Due | CID | Status | Review focus |")
    L.append("|--------|-----|------|---------|")
    for c in sorted(causes, key=lambda c: str(c["_fm"].get("review_due") or "9999")):
        fm = c["_fm"]
        if fm.get("status") in ("closed",):
            continue
        L.append("| %s | %s | %s | %s |" % (
            fm.get("review_due", ""), fm["cid"], fm.get("status"),
            _cut(fm.get("review_note") or "—", 88)))
    L.append("")
    # resolved
    L.append("## Resolved (verified / closed)")
    L.append("")
    if done:
        L.append("| CID | Cause | Resolution | Fix/migration version |")
        L.append("|-----|------|---------|--------------|")
        for c in done:
            fm = c["_fm"]
            L.append("| %s | %s | %s | %s |" % (
                fm["cid"], _cut(fm.get("title", ""), 60), fm.get("status"),
                fm.get("_fixed_in") or "—"))
    else:
        L.append("_(None yet. After verified, carry out the retirement steps (remove the workaround, annotate related pages, set W to retired) "
                 "before adding an entry here, see [_index](_index.md) §4; wontfix/watching are stable tracked states and stay in the views above.)_")
    L.append("")
    if warns:
        L.append("## Pending reminders (WARNs from check)")
        L.append("")
        for _, where, msg in warns:
            L.append("- `%s`: %s" % (where, msg))
        L.append("")
    return "\n".join(L)


# ── Subcommands ─────────────────────────────────────────────────────────────
def cmd_check():
    (symptoms, workarounds, tickets, causes), errs = load_all()
    errors, warns, infos = check_all(symptoms, workarounds, tickets, causes)
    errors = errs + errors
    for level, where, msg in errors:
        print("  ERROR [%s] %s" % (where, msg))
    for _, where, msg in warns:
        print("  WARN  [%s] %s" % (where, msg))
    for _, where, msg in infos:
        print("  INFO  [%s] %s" % (where, msg))
    print("check: error=%d warn=%d info=%d"
          % (len(errors), len(warns), len(infos)))
    return 1 if errors else 0


def cmd_build():
    (symptoms, workarounds, tickets, causes), errs = load_all()
    errors, warns, infos = check_all(symptoms, workarounds, tickets, causes)
    errors = errs + errors
    if errors:
        for level, where, msg in errors:
            print("  ERROR [%s] %s" % (where, msg))
        print("build aborted: fix %d error(s) in sources first" % len(errors))
        return 1
    aggregate(symptoms, workarounds, tickets, causes)
    GRAPH_PATH.write_text(gen_graph(symptoms, workarounds, tickets, causes),
                          encoding="utf-8", newline="\n")
    REGISTRY_PATH.write_text(gen_registry(symptoms, workarounds, tickets, causes, warns),
                             encoding="utf-8", newline="\n")
    print("build OK: S=%d C=%d W=%d T=%d -> %s, %s (warn=%d)"
          % (len(symptoms), len(causes), len(workarounds), len(tickets),
             GRAPH_PATH.name, REGISTRY_PATH.name, len(warns)))
    return 0


def _draft_title(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^#\s+(.+)$", text, re.M)
    return m.group(1).strip() if m else path.stem


def list_drafts():
    """Drafts awaiting review (_drafts/; an underscore prefix marks a template; the format is loose, a parse failure counts as draft)."""
    drafts_dir = FAULTS_DIR / "_drafts"
    out = []
    if drafts_dir.is_dir():
        for path in sorted(drafts_dir.glob("*.md")):
            if path.name.startswith("_"):
                continue
            fm, _ = parse_frontmatter(path)
            status = (fm or {}).get("status") if isinstance(fm, dict) else None
            if status == "promoted":
                continue          # already merged (QOH/R drafts keep a trace after promote); no longer awaiting review
            result = (fm or {}).get("review_result") if isinstance(fm, dict) else None
            out.append((path.name, status or "draft", _draft_title(path), result or ""))
    return out


def cmd_review():
    (symptoms, workarounds, tickets, causes), errs = load_all()
    errors, warns, infos = check_all(symptoms, workarounds, tickets, causes)
    if errs + errors:
        for level, where, msg in errs + errors:
            print("  ERROR [%s] %s" % (where, msg))
        print("review aborted: sources have errors")
        return 1
    aggregate(symptoms, workarounds, tickets, causes)
    today_d = datetime.date.today()
    due = []
    for c in causes:
        fm = c["_fm"]
        if fm.get("status") == "closed":
            continue
        try:
            d = datetime.date.fromisoformat(str(fm.get("review_due")))
        except ValueError:
            continue
        due.append((d, c))
    due.sort(key=lambda x: x[0])
    print("faults review — review scan (today=%s)" % today_d)
    print("=" * 60)
    if not due:
        print("(no entries due)")
    for d, c in due:
        fm = c["_fm"]
        if d < today_d:
            flag = "overdue by %d days" % (today_d - d).days
        elif d == today_d:
            flag = "due today"
        else:
            flag = "in %d days" % (d - today_d).days
        print("\n[%s] %s (%s/%s, status=%s)" % (flag, fm["cid"], fm.get("nature"),
                                              fm.get("responsible"), fm.get("status")))
        print("  page: %s" % c["_path"].name)
        print("  focus: %s" % (fm.get("review_note") or "—"))
        ws = [w["id"] for w in workarounds
              if fm["cid"] in _as_list(w.get("targets")) and w.get("status") != "retired"]
        if ws:
            print("  carried workarounds: %s (retirement conditions in the W records)" % "; ".join(ws))
        ts = [t for t in tickets if fm["cid"] in _as_list(t.get("tracks"))]
        for t in ts:
            print("  ticket: %s %s %s [%s]" % (t["id"], t.get("tracker"),
                                             t.get("number") or "", t.get("status")))
    print("\nNot closed (to be filled -- closed-loop rule in _index §4: defect with external responsibility = W+T; limitation/app = W)")
    print("-" * 60)
    gap_rows = [c for c in causes if c["_fm"].get("_gaps")]
    if not gap_rows:
        print("  (none -- all causes are closed or root-fixed)")
    for c in gap_rows:
        fm = c["_fm"]
        print("  [%s] missing %s — W:%s T:%s | %s"
              % (fm["cid"], "/".join(fm["_gaps"]),
                 ", ".join(fm["_live_ws"]) or "✗",
                 ", ".join(fm["_open_ts"]) or "✗",
                 _cut(fm.get("title", ""), 72)))
    print("\nDrafts awaiting review (faults/_drafts/; merge gate in faults/_index.md §6)")
    print("-" * 60)
    drafts = list_drafts()
    if not drafts:
        print("(none)")
    for name, status, title, result in drafts:
        line = "  [%s] %s — %s" % (status, name, title)
        if result:
            line += " | %s" % result
        print(line)
    print("\nStatus progression reminders (WARN)")
    print("-" * 60)
    if warns:
        for _, where, msg in warns:
            print("  [%s] %s" % (where, msg))
    else:
        print("(none)")
    return 0


def main(argv):
    cmd = argv[0] if argv else "all"
    if cmd in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    if cmd == "build":
        return cmd_build()
    if cmd == "check":
        return cmd_check()
    if cmd == "review":
        return cmd_review()
    if cmd == "all":
        rc = cmd_build()
        if rc == 0:
            rc = cmd_check()
        return rc
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
