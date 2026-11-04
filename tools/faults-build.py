#!/usr/bin/env python3
"""faults-build.py — 故障库（症状×根因×方案×跟踪单图）构建与校验工具。

单一真源（修改这些文件后跑 build 重建派生物）：
  faults/_data/symptoms.yaml     症状 S 记录 + causes 边（S→C）
  faults/_data/workarounds.yaml  临时方案 W 记录 + targets 边（W→C）
  faults/_data/tickets.yaml      上游跟踪单 T 记录 + tracks 边（T→C）
  faults/C-xxxx-*.md             根因 C 深档案（frontmatter 为源）+ depends_on 边（C→C）

派生物（自动生成，勿手改）：
  faults/_graph.yaml             机读全量图（节点 + 边 + 聚合概览 + 反查索引）
  faults/_registry.md            登记总表（人类/AI 视图）

用法：
  python tools/faults-build.py build    # 校验 + 重建 _graph.yaml 与 _registry.md
  python tools/faults-build.py check    # 一致性门禁（exit 1 = 有 ERROR）
  python tools/faults-build.py review   # 复核到期扫描 + 状态推进建议 + 待审草稿清单
  python tools/faults-build.py all      # build + check

设计原则：事实由人写进真源，工具负责派生、校验与提醒（LLM 负责推理，tool 负责事实）。
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

# ── 枚举（规范见 faults/_index.md）──────────────────────────────────────────
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
              "upstream"}   # upstream = 第三方上游（Mesa/freedesktop 等）
T_STATUS = {"draft", "submitted", "accepted", "dup", "wontfix",
            "fixed", "released", "closed"}
T_OPEN = {"submitted", "accepted", "fixed", "released"}   # 已在跟的单
EVIDENCE_TYPES = {"demo", "logs", "both", "source", "docs"}
EVIDENCE_REPRO = {"demo", "logs", "both"}     # 可复现级证据（提上游单的门槛）
# 处置分类（派生自 nature × responsible，开发者视角"遇到该怎么办"；不入真源、无双写）
DISPOSITIONS = {
    "must-adapt": "鸿蒙必须适配",
    "qt-defect": "Qt 问题",
    "system-defect": "系统问题",
    "app-usage": "应用使用问题",
    "third-party": "三方库问题",
    "undetermined": "待定性",
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
ROOT_CAUSE_STATES = {"fix-confirmed", "verified", "closed"}   # 根治链：无需 W/T 完备性
EXTERNAL_RESP = {"qt-port", "qt-upstream", "ohos-runtime", "ohos-ndk",
                 "ohos-toolchain", "third-party"}
# 链路完备性（闭环规则，见 _index §四）：缺口向上传播，"未解决"由下游完备性决定
CHAIN_ORDER = ["root-resolved", "temp-resolved", "missing-ticket",
               "missing-workaround", "both-missing"]
CHAIN_LABELS = {
    "root-resolved": "根治",
    "temp-resolved": "临时了结",
    "missing-ticket": "缺单",
    "missing-workaround": "缺方案",
    "both-missing": "双缺",
}


def is_planned_ticket(t) -> bool:
    """排期中的单：status=draft 且写了 planned_filing。

    它不改变"链路仍有缺口"这个事实（chain_state_of 只认 T_OPEN），只是把
    "没人管"和"已排期待提"分开呈现——前者报 WARN，后者报 INFO。
    """
    return t.get("status") == "draft" and bool(t.get("planned_filing"))


def chain_state_of(fm, has_live_w, has_open_t):
    """defect（外部责任）临时了结 = W(adopted) 且 T(在跟)——缺一即未闭环；
    limitation / app / undetermined 临时了结 = W(adopted)；
    root-resolved = C.status 进入根治链（fix-confirmed 及之后），无需 W/T。"""
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


# ── 加载 ───────────────────────────────────────────────────────────────────
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


# ── 校验 ───────────────────────────────────────────────────────────────────
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
    # 链路完备性聚合（lint 与生成共用；幂等）
    aggregate(symptoms, workarounds, tickets, causes)
    c_ids = [c["_fm"].get("cid") for c in causes]
    s_ids = [s.get("id") for s in symptoms]
    w_ids = [w.get("id") for w in workarounds]
    t_ids = [t.get("id") for t in tickets]

    # ID 格式与唯一性
    for label, ids in (("S", s_ids), ("C", c_ids), ("W", w_ids), ("T", t_ids)):
        for i in ids:
            if not (isinstance(i, str) and ID_RE.match(i) and i[0] == label):
                errors.append(("E", label, "bad id: %r" % i))
        dup = {x for x in ids if isinstance(x, str) and ids.count(x) > 1}
        if dup:
            errors.append(("E", label, "duplicate ids: %s" % sorted(dup)))

    cause_set = set(c_ids)
    # 症状
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

    # 根因（C 页）
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

    # 临时方案
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

    # 跟踪单
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

    # ── lint：状态推进一致性（WARN，事实由人定，工具只提醒）──
    by_cid = {c["_fm"].get("cid"): c["_fm"] for c in causes}
    for cid, fm in by_cid.items():
        ws = [w for w in workarounds if cid in _as_list(w.get("targets"))]
        ts = [t for t in tickets if cid in _as_list(t.get("tracks"))]
        has_live_w = any(w.get("status") in ("tested", "adopted") for w in ws)
        has_open_t = any(t.get("status") in T_OPEN for t in ts)
        planned_ts = [t for t in ts if is_planned_ticket(t)]
        planned_note = "、".join("%s（计划 %s 提）" % (t.get("id"), t.get("planned_filing"))
                                for t in planned_ts)
        if fm.get("status") == "workaround" and not has_live_w:
            warns.append(("W", cid, "status=workaround but no tested/adopted W targets it"))
        if fm.get("status") == "workaround" and fm.get("_gaps"):
            if fm["_gaps"] == ["ticket"] and planned_ts:
                infos.append(("I", cid,
                              "缺跟踪单已排期：%s——链路按未闭环计，提交后把该单改 submitted"
                              % planned_note))
            else:
                warns.append(("W", cid,
                              "status=workaround 但链路未闭环（缺 %s）——按闭环规则不算"
                              "临时了结，待补齐" % "/".join(fm["_gaps"])))
        if fm.get("status") == "reported" and not has_open_t:
            warns.append(("W", cid, "status=reported but no open T tracks it"))
        if (fm.get("nature") == "defect"
                and fm.get("responsible") in ("qt-port", "qt-upstream")
                and fm.get("evidence_type") == "source"):
            msg = ("Qt-side defect evidenced only by 'source': 补最小复现 demo 或"
                   "运行日志后更稳（提上游 T 前必备，对齐 qt-bug-report HARD 闸门）")
            if planned_ts:
                infos.append(("I", cid, msg + "；已排期 %s" % planned_note))
            else:
                warns.append(("W", cid, msg))
        for t in ts:
            if t.get("status") in ("fixed", "released") and fm.get("status") \
                    not in ("fix-confirmed", "verified", "closed"):
                warns.append(("W", cid,
                              "T %s is %s but C status is '%s' — 待推进 fix-confirmed"
                              % (t.get("id"), t.get("status"), fm.get("status"))))

    # 证据门禁：在跟上游单的 defect/undetermined 必须持有可复现级证据（demo/logs/both）
    for t in tickets:
        if t.get("status") in T_OPEN and t.get("tracker") != "forum":
            for cid in _as_list(t.get("tracks")):
                fm = by_cid.get(cid)
                if fm and fm.get("nature") in ("defect", "undetermined") \
                        and fm.get("evidence_type") not in EVIDENCE_REPRO:
                    errors.append(("E", t.get("id") or "?",
                                   "open upstream ticket requires reproducible evidence "
                                   "(demo/logs/both) on %s, got '%s' — 无可复现材料的"
                                   "单据不提交（qt-bug-report HARD 闸门）"
                                   % (cid, fm.get("evidence_type"))))
    # 链路完备性：缺口向上传播，上游的了结宣称受下游完备性约束
    for s in symptoms:
        cs = _as_list(s.get("causes"))
        live_ws = [by_cid[c]["_live_ws"] for c in cs if c in by_cid]
        if s.get("status") == "resolved" and s.get("_gaps"):
            errors.append(("E", s.get("id"),
                           "S.status=resolved 但链路有缺口（缺 %s）——下游未闭环，"
                           "上游不得宣称彻底了结（降级 mitigated/active）"
                           % "/".join(s["_gaps"])))
        if s.get("status") == "mitigated":
            if cs and live_ws and not any(live_ws):
                errors.append(("E", s.get("id"),
                               "S.status=mitigated 但背后无 adopted W——缓解宣称必须有"
                               "采用中方案支撑（否则应标 active）"))
    return errors, warns, infos


# ── 聚合与生成 ──────────────────────────────────────────────────────────────
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
        fm["_fixed_in"] = "；".join(
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

    # S 链路聚合：缺口向上传播（任一 cause 有缺口则 S 未闭环，gaps 取并集）
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
    """YAML 标量输出：安全裸值或双引号。"""
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
    out.append("# faults/_graph.yaml — 故障图（机读全量图）【自动生成，勿手改】")
    out.append("#")
    out.append("# 重建：python tools/faults-build.py build")
    out.append("# 真源：_data/symptoms.yaml（S+causes 边）/_data/workarounds.yaml（W+targets 边）/")
    out.append("#       _data/tickets.yaml（T+tracks 边）/C-*.md frontmatter（C+depends_on 边）")
    out.append("# 模型规范：faults/_index.md ｜ 人类视图：faults/_registry.md（同为派生物）")
    out.append("#")
    out.append("# 节点：S 症状（应用层表现，检索入口）｜C 根因（defect 会修/limitation 规格限制→替代方案）")
    out.append("#       W 临时方案（proposed→tested→adopted→retired）｜T 上游跟踪单（Qt 单号/华为单号/交付件）")
    out.append("# 边：causes S→C（多因时 cause_relation: any_of|all_of）｜targets W→C｜tracks T→C")
    out.append("#      depends_on C→C（仅实证阻塞）｜manifests 为 causes 的派生反查索引")
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
    """症状的缓解方式（聚合其根因的 live W 标题）。"""
    titles = []
    for s in symptoms:
        if s["id"] != sid:
            continue
        for c in _as_list(s.get("causes")):
            for w in workarounds:
                if c in _as_list(w.get("targets")) and w.get("status") in ("tested", "adopted"):
                    titles.append(w["id"])
    return "；".join(titles) if titles else "—"


def _carry(workarounds, cid):
    ts = [w["id"] for w in workarounds
          if cid in _as_list(w.get("targets")) and w.get("status") != "retired"]
    return "；".join(ts) if ts else "—"


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
    L.append("  故障登记总表（症状×根因×方案×跟踪单图的人类视图）。【自动生成，勿手改——")
    L.append("  python tools/faults-build.py build 重建】机读全量图见 _graph.yaml，规范见 _index.md。")
    L.append("---")
    L.append("")
    L.append("# 故障登记总表")
    L.append("")
    L.append("> 按表现查 §症状索引（主入口）；\"归谁、是缺陷还是规格、修没修、怎么绕\"看根因。")
    L.append("> 机读全量图（单文件一次加载）：[_graph.yaml](_graph.yaml) ｜ 规范：[_index](_index.md)")
    L.append("> **本文件为派生物**：真源在 `_data/*.yaml` 与 `C-*.md`，修改后跑 `python tools/faults-build.py build`。")
    L.append("")
    L.append("## 统计")
    L.append("")
    L.append("| 维度 | 分布 |")
    L.append("|------|------|")
    ns = " / ".join("%s %d" % (k, len(v)) for k, v in natures.items() if v)
    L.append("| 节点 | 症状 %d（active %d / mitigated %d / resolved %d）｜根因 %d（%s）｜临时方案 %d｜跟踪单 %d |"
             % (len(symptoms),
                sum(1 for s in symptoms if s.get("status") == "active"),
                sum(1 for s in symptoms if s.get("status") == "mitigated"),
                sum(1 for s in symptoms if s.get("status") == "resolved"),
                len(causes), ns, len(workarounds), len(tickets)))
    resp = {}
    for c in causes:
        r = c["_fm"].get("responsible")
        resp[r] = resp.get(r, 0) + 1
    L.append("| 责任领域 | %s |" % " · ".join("%s %d" % kv for kv in sorted(resp.items())))
    dstat = {}
    for c in causes:
        d = c["_fm"].get("_disposition")
        dstat[d] = dstat.get(d, 0) + 1
    L.append("| 处置分类 | %s |" % " · ".join(
        "%s %d" % (DISPOSITIONS[k], dstat[k])
        for k in DISPOSITION_ORDER if k in dstat))
    chain = {}
    for c in causes:
        chain[c["_fm"]["_chain_state"]] = chain.get(c["_fm"]["_chain_state"], 0) + 1
    L.append("| 链路闭环 | 根治 %d · 临时了结 %d · 未闭环 %d（%s） |" % (
        chain.get("root-resolved", 0), chain.get("temp-resolved", 0),
        sum(v for k, v in chain.items() if k.startswith("missing") or k == "both-missing"),
        " · ".join("%s %d" % (CHAIN_LABELS[k], chain[k])
                   for k in ("missing-ticket", "missing-workaround", "both-missing")
                   if k in chain)))
    L.append("| 严重度 | %s |" % " · ".join(
        "%s %d" % (s, sum(1 for c in causes if c["_fm"].get("severity") == s))
        for s in SEVERITIES if any(c["_fm"].get("severity") == s for c in causes)))
    L.append("")
    # 症状索引
    L.append("## 症状索引（主入口）")
    L.append("")
    L.append("| S | 现象 | 域 | 严重度 | 状态 | 闭环 | 根因（nature） | 缓解（W） |")
    L.append("|---|------|----|:------:|------|------|---------------|----------|")
    for s in symptoms:
        cs = _as_list(s.get("causes"))
        clinks = []
        for c in causes:
            fm = c["_fm"]
            if fm.get("cid") in cs:
                clinks.append("[%s](%s)（%s）" % (fm["cid"], c["_path"].name, fm.get("nature")))
        rel = " ×".join(clinks)
        if len(cs) > 1:
            rel += "（%s）" % (s.get("cause_relation") or "any_of")
        zh = {"workaround": "方案", "ticket": "单", "cause": "根因"}
        gaps = s.get("_gaps") or []
        cell = ("双缺" if len(gaps) >= 2
                else ("—" if not gaps else "缺" + zh.get(gaps[0], gaps[0])))
        L.append("| %s | %s | %s | %s %s | %s | %s | %s | %s |" % (
            s["id"], _cut(s.get("title", ""), 40), s.get("domain"),
            SEV_ICON.get(s.get("severity"), ""), s.get("severity"),
            "**%s**" % s.get("status") if s.get("status") == "active" else s.get("status"),
            cell, rel, _ws_for(symptoms, workarounds, s["id"])))
    L.append("")
    # 按处置分类（开发者视角）
    L.append("## 按处置分类（开发者视角：遇到该怎么办）")
    L.append("")
    L.append("> 派生视图（nature × responsible 自动计算，规范见 _index §三）：**鸿蒙必须适配**=平台/SDK 规格如此，改自己的代码，无上游修复可等；**Qt 问题**=等 Qt 修复/本地补丁/提 QTBUG；**系统问题**=等系统·SDK·工具链版本或提华为侧单；**应用使用问题**=改应用代码，非框架问题；**三方库问题**=三方库自身缺陷；**待定性**=等上游定性。")
    L.append("")
    for key in DISPOSITION_ORDER:
        rows = [c for c in causes if c["_fm"].get("_disposition") == key]
        if not rows:
            continue
        L.append("### %s（%s，%d 条）" % (DISPOSITIONS[key], key, len(rows)))
        L.append("")
        L.append("| CID | 根因 | nature/responsible | 状态 | 方案（W）/路径 |")
        L.append("|-----|------|--------------------|------|---------------|")
        for c in rows:
            fm = c["_fm"]
            ws = _carry(workarounds, fm["cid"])
            path = fm.get("fix_route") or fm.get("evolution") or ""
            cell = ws if ws != "—" else (path or "—")
            L.append("| [%s](%s) | %s | %s/%s | %s | %s |" % (
                fm["cid"], c["_path"].name, _cut(fm.get("title", ""), 30),
                fm.get("nature"), fm.get("responsible"), fm.get("status"),
                _cut(cell, 30)))
        L.append("")
    # 未闭环清单（链路完备性缺口）
    L.append("## 未闭环清单（链路完备性缺口——待补齐，规则见 _index §四）")
    L.append("")
    L.append("> 闭环规则：**defect（外部责任）临时了结 = 采用中方案（W adopted）+ 在跟单（T）**；"
             "limitation / 应用问题 / 未定性 = 采用中方案；根治 = fix-confirmed 及之后。"
             "**缺口向上传播**：症状的了结宣称受根因链完备性约束（check 强制）。")
    L.append("")
    for key, label in (
            ("missing-ticket", "缺跟踪单（方案已就位，待提单/在跟）"),
            ("missing-workaround", "缺方案（无采用中的绕过/适配）"),
            ("both-missing", "双缺（未解决）")):
        rows = [c for c in causes if c["_fm"]["_chain_state"] == key]
        if not rows:
            continue
        L.append("### %s（%d）" % (label, len(rows)))
        L.append("")
        L.append("| CID | 根因 | 处置 | 状态 | 方案（W） | 单（T） | 症状 |")
        L.append("|-----|------|------|------|-----------|---------|------|")
        for c in rows:
            fm = c["_fm"]
            L.append("| [%s](%s) | %s | %s | %s | %s | %s | %s |" % (
                fm["cid"], c["_path"].name, _cut(fm.get("title", ""), 26),
                DISPOSITIONS.get(fm.get("_disposition"), ""), fm.get("status"),
                "、".join(fm.get("_live_ws") or []) or "✗",
                "、".join(list(fm.get("_open_ts") or [])
                          + ["%s（计划）" % t for t in (fm.get("_planned_ts") or [])]) or "✗",
                "、".join(fm.get("_manifests") or []) or "—"))
        L.append("")
    # 缺陷
    L.append("## 缺陷（defect——会修，跟修复版本与上游单）")
    L.append("")
    L.append("| CID | 根因 | 领域 | 严重度 | 状态 | 临时方案（W） | 跟踪单（T） | 修复到达路径 | 复核到期 |")
    L.append("|-----|------|------|:------:|------|--------------|------------|-------------|---------|")
    for c in natures["defect"]:
        fm = c["_fm"]
        L.append("| [%s](%s) | %s | %s | %s %s | %s | %s | %s | %s | %s |" % (
            fm["cid"], c["_path"].name, _cut(fm.get("title", ""), 34), fm.get("responsible"),
            SEV_ICON.get(fm.get("severity"), ""), fm.get("severity"), fm.get("status"),
            _carry(workarounds, fm["cid"]),
            "；".join(fm["_tickets"]) or "—",
            _cut(fm.get("fix_route") or "—", 30), fm.get("review_due", "")))
    L.append("")
    L.append("**未定（undetermined——等定性，跟上游答复；改判时 CID 不变）**")
    L.append("")
    L.append("| CID | 根因 | 领域 | 严重度 | 状态 | 临时方案（W） | 跟踪单（T） | 定性去向 | 复核到期 |")
    L.append("|-----|------|------|:------:|------|--------------|------------|---------|---------|")
    for c in natures["undetermined"]:
        fm = c["_fm"]
        L.append("| [%s](%s) | %s | %s | %s %s | %s | %s | %s | 见 C 页 | %s |" % (
            fm["cid"], c["_path"].name, _cut(fm.get("title", ""), 34), fm.get("responsible"),
            SEV_ICON.get(fm.get("severity"), ""), fm.get("severity"), fm.get("status"),
            _carry(workarounds, fm["cid"]), "；".join(fm["_tickets"]) or "—",
            fm.get("review_due", "")))
    L.append("")
    # 限制
    L.append("## 限制（limitation——规格如此，跟替代方案与演进）")
    L.append("")
    L.append("| CID | 限制 | 定性证据 | 替代方案（W） | 演进 | 状态 |")
    L.append("|-----|------|---------|--------------|------|------|")
    for c in natures["limitation"]:
        fm = c["_fm"]
        L.append("| [%s](%s) | %s | %s | %s | %s | %s |" % (
            fm["cid"], c["_path"].name, _cut(fm.get("title", ""), 34),
            _cut(fm.get("evidence") or "—", 30), _carry(workarounds, fm["cid"]),
            _cut(fm.get("evolution") or "—", 28), fm.get("status")))
    L.append("")
    # 临时方案清单
    L.append("## 临时方案清单（W）")
    L.append("")
    L.append("| W | 方案 | 作用根因 | 状态 | 最近验证 | 退役条件 |")
    L.append("|---|------|---------|------|---------|---------|")
    for w in workarounds:
        v = w.get("verified")
        vtxt = "%s %s" % (v.get("date", ""), v.get("env", "")) if isinstance(v, dict) else "—"
        L.append("| %s | %s | %s | %s | %s | %s |" % (
            w["id"], _cut(w.get("title", ""), 42), "；".join(_as_list(w.get("targets"))),
            w.get("status"), _cut(vtxt.strip() or "—", 28),
            _cut(w.get("retire_when") or "—", 30)))
    L.append("")
    # 跟踪单清单
    L.append("## 跟踪单清单（T）")
    L.append("")
    L.append("| T | 平台 | 单号 | 跟踪根因 | 状态 | 修复版本 | 提交日 | 说明 |")
    L.append("|---|------|------|---------|------|---------|--------|------|")
    for t in tickets:
        num = t.get("number") or "—"
        if t.get("url"):
            num = "[%s](%s)" % (num, t["url"])
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
            t["id"], t.get("tracker"), num, "；".join(_as_list(t.get("tracks"))),
            t.get("status"), t.get("fix_version") or "—", t.get("filed") or "—",
            _cut(t.get("notes") or "—", 32)))
    L.append("")
    # 关系速览
    L.append("## 关系速览")
    L.append("")
    L.append("```")
    for s in symptoms:
        cs = _as_list(s.get("causes"))
        head = "%s %s" % (s["id"], _cut(s.get("title", ""), 16))
        fms = {c["_fm"]["cid"]: c["_fm"] for c in causes}
        if len(cs) == 1:
            fm = fms.get(cs[0], {})
            L.append("%s ──→ %s %s [%s/%s]" % (
                head.ljust(26), cs[0], _cut(fm.get("title", ""), 20),
                fm.get("nature"), fm.get("responsible")))
        else:
            for i, cid in enumerate(cs):
                fm = fms.get(cid, {})
                branch = "──┬→" if i == 0 else "    └→"
                tail = "  ← %s（叠加）" % s.get("cause_relation") if i == 0 else ""
                L.append("%s %s %s %s [%s/%s]%s" % (
                    head.ljust(26) if i == 0 else " " * 26, branch, cid,
                    _cut(fm.get("title", ""), 20), fm.get("nature"),
                    fm.get("responsible"), tail))
    dep = [(c["_fm"]["cid"], d) for c in causes
           for d in _as_list(c["_fm"].get("depends_on"))]
    L.append("C→C depends_on：%s" % ("；".join("%s←%s" % (a, b) for a, b in dep) or "暂无"))
    orphan = [s["id"] for s in symptoms if not _as_list(s.get("causes"))]
    L.append("孤儿症状（causes 为空）：%s" % ("；".join(orphan) or "无"))
    L.append("```")
    L.append("")
    # 版本基线
    L.append("## 按版本基线（升级检查清单）")
    L.append("")
    L.append("换 Qt / OHOS 版本前查这里：目标版本下仍活跃的根因 + 必须随行携带的方案（W id）。")
    L.append("")
    for baseline in QT_BASELINES:
        rows = [c for c in causes
                if any(isinstance(a, str) and a.startswith(baseline)
                       for a in _as_list(c["_fm"].get("affects_qt")))]
        if not rows:
            continue
        L.append("### %s" % baseline)
        L.append("")
        L.append("| 根因 | 状态 | 携带项（W） |")
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
        L.append("### 其他 Qt 版本")
        L.append("")
        L.append("| 根因 | 状态 | 影响版本 | 携带项（W） |")
        L.append("|------|------|---------|------------|")
        for c in others:
            fm = c["_fm"]
            L.append("| %s | %s | %s | %s |" % (
                fm["cid"], fm.get("status"),
                _cut("；".join(str(a) for a in _as_list(fm.get("affects_qt"))), 30),
                _carry(workarounds, fm["cid"])))
        L.append("")
    L.append("### OHOS API / 系统版本")
    L.append("")
    L.append("| 根因 | 受影响版本 | 携带项（W） |")
    L.append("|------|-----------|------------|")
    for c in causes:
        fm = c["_fm"]
        if not _as_list(fm.get("affects_ohos")):
            continue
        L.append("| %s | %s | %s |" % (
            fm["cid"], _cut("；".join(str(a) for a in _as_list(fm.get("affects_ohos"))), 40),
            _carry(workarounds, fm["cid"])))
    L.append("")
    # 复核到期
    L.append("## 复核到期")
    L.append("")
    L.append("| 到期日 | CID | 状态 | 复核要点 |")
    L.append("|--------|-----|------|---------|")
    for c in sorted(causes, key=lambda c: str(c["_fm"].get("review_due") or "9999")):
        fm = c["_fm"]
        if fm.get("status") in ("closed",):
            continue
        L.append("| %s | %s | %s | %s |" % (
            fm.get("review_due", ""), fm["cid"], fm.get("status"),
            _cut(fm.get("review_note") or "—", 44)))
    L.append("")
    # 已了结
    L.append("## 已了结（verified / closed）")
    L.append("")
    if done:
        L.append("| CID | 根因 | 了结方式 | 修复/迁移版本 |")
        L.append("|-----|------|---------|--------------|")
        for c in done:
            fm = c["_fm"]
            L.append("| %s | %s | %s | %s |" % (
                fm["cid"], _cut(fm.get("title", ""), 30), fm.get("status"),
                fm.get("_fixed_in") or "—"))
    else:
        L.append("_（暂无。verified 后执行退役动作（移除 workaround、关联页注记、W 置 retired）"
                 "再入此表，见 [_index](_index.md) §四；wontfix/watching 属跟踪中的稳定态，留在上方视图。）_")
    L.append("")
    if warns:
        L.append("## 待处理提醒（check 的 WARN）")
        L.append("")
        for _, where, msg in warns:
            L.append("- `%s`：%s" % (where, msg))
        L.append("")
    return "\n".join(L)


# ── 子命令 ──────────────────────────────────────────────────────────────────
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
    """待审草稿（_drafts/，下划线前缀为模板；格式宽松，解析失败按 draft 计）。"""
    drafts_dir = FAULTS_DIR / "_drafts"
    out = []
    if drafts_dir.is_dir():
        for path in sorted(drafts_dir.glob("*.md")):
            if path.name.startswith("_"):
                continue
            fm, _ = parse_frontmatter(path)
            status = (fm or {}).get("status") if isinstance(fm, dict) else None
            if status == "promoted":
                continue          # 已合入（QOH/R 草稿 promote 后保留留痕），不再算待审
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
    print("faults review — 复核扫描（today=%s）" % today_d)
    print("=" * 60)
    if not due:
        print("（无到期条目）")
    for d, c in due:
        fm = c["_fm"]
        if d < today_d:
            flag = "逾期 %d 天" % (today_d - d).days
        elif d == today_d:
            flag = "今日到期"
        else:
            flag = "%d 天后" % (d - today_d).days
        print("\n[%s] %s（%s/%s，status=%s）" % (flag, fm["cid"], fm.get("nature"),
                                              fm.get("responsible"), fm.get("status")))
        print("  页面: %s" % c["_path"].name)
        print("  要点: %s" % (fm.get("review_note") or "—"))
        ws = [w["id"] for w in workarounds
              if fm["cid"] in _as_list(w.get("targets")) and w.get("status") != "retired"]
        if ws:
            print("  随行方案: %s（退役条件见 W 记录）" % "；".join(ws))
        ts = [t for t in tickets if fm["cid"] in _as_list(t.get("tracks"))]
        for t in ts:
            print("  跟踪单: %s %s %s [%s]" % (t["id"], t.get("tracker"),
                                             t.get("number") or "", t.get("status")))
    print("\n未闭环（待补齐——闭环规则见 _index §四：defect 外部责任=W+T；limitation/app=W）")
    print("-" * 60)
    gap_rows = [c for c in causes if c["_fm"].get("_gaps")]
    if not gap_rows:
        print("  （无——全部根因已闭环或根治）")
    for c in gap_rows:
        fm = c["_fm"]
        print("  [%s] 缺%s — W:%s T:%s ｜ %s"
              % (fm["cid"], "/".join(fm["_gaps"]),
                 "、".join(fm["_live_ws"]) or "✗",
                 "、".join(fm["_open_ts"]) or "✗",
                 _cut(fm.get("title", ""), 36)))
    print("\n待审草稿（faults/_drafts/，合入门禁见 faults/_index.md §六）")
    print("-" * 60)
    drafts = list_drafts()
    if not drafts:
        print("（无）")
    for name, status, title, result in drafts:
        line = "  [%s] %s — %s" % (status, name, title)
        if result:
            line += " ｜ %s" % result
        print(line)
    print("\n状态推进提醒（WARN）")
    print("-" * 60)
    if warns:
        for _, where, msg in warns:
            print("  [%s] %s" % (where, msg))
    else:
        print("（无）")
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
