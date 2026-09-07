#!/bin/bash
# ═══════════════════════════════════════════════════════════
# KB Gate v3.0 — Canonical Trunk (ohos_qt-skills)
# 自动检查知识库的一致性问题（25 项检查）
# 用法: bash _scripts/kb-gate.sh
# 退出码: 0=通过(可含警告), 1=有 FAIL 级问题(阻止 push)
#
# v3.0 变更（Trunk Flip）:
#   - §14: 反转 — trunk 页面不得含 audience: 字段（存在即公开）
#   - §15: 泛化 — PRIVATE_PATTERNS 扫描所有页面（不再限 audience:public）
#   - §16: 泛化 — refs 必须解析到本仓存在的 id（无 internal 概念）
#   - §20: 泛化 — 正文交叉引用必须解析到本仓存在的页面
#   - §21: 泛化 — 所有页面不得含内部任务路由码
#   - §24: 新增 — drafts/ 卫生检查
#   - §25: 新增 — 机器维护文件完整性（_index/ 由 regen 管理）
#
# 分级语义:
#   FAIL → 计入 ERRORS，退出码 1，阻止 push
#   WARN → 计入 WARNINGS，退出码 0，仅提示
# ═══════════════════════════════════════════════════════════

# 注意：不用 set -e。一致性检查的本质是"一次报告全部问题"，
# 遇错即停违背目标。所有可能失败的命令显式兜底。
set -uo pipefail
shopt -s nullglob

KB_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ERRORS=0
WARNINGS=0
SECTION_COUNT=0
CURRENT_SECTION=""
declare -A SECTION_FAIL=()
declare -a PUBLIC_FILES=()  # §15 公开页列表（倒置 grep 用，预声明避 set -u unbound）
declare -A SECTION_WARN=()

# ── 颜色（非 tty 关闭 ANSI，避免重定向时出现字面 \[）──
if [ -t 1 ]; then
  RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
else
  RED=''; YELLOW=''; GREEN=''; CYAN=''; NC=''
fi


# ── timing (KB_TIMING=1 enables; stderr-only, no effect on exit code / detection) ──
# 用途：门禁耗时基线/优化前后对比（PR 报告）。生产（CI/push）不设 KB_TIMING → 零开销。
if [ "${KB_TIMING:-0}" = "1" ]; then
  declare -a _TS_NAMES=() _TS_MS=()
  _T_CUR=0; _T_LABEL=""
  _ts_mark()  { local now; now=$(date +%s%N); [ "$_T_CUR" != 0 ] && { _TS_NAMES+=("$_T_LABEL"); _TS_MS+=( $(( (now - _T_CUR) / 1000000 )) ); }; _T_LABEL="$1"; _T_CUR=$now; }
  _ts_flush() { local now; now=$(date +%s%N); [ "$_T_CUR" != 0 ] && { _TS_NAMES+=("$_T_LABEL"); _TS_MS+=( $(( (now - _T_CUR) / 1000000 )) ); }; }
  _ts_report(){ { echo "=== TIMING (ms) ==="; local total=0 i; for i in "${!_TS_NAMES[@]}"; do printf '%6d ms  %s\n' "${_TS_MS[$i]}" "${_TS_NAMES[$i]}"; total=$((total + ${_TS_MS[$i]})); done; printf '%6d ms  TOTAL(timed)\n' "$total"; } >&2; }
else
  _ts_mark()  { :; }
  _ts_flush() { :; }
  _ts_report(){ :; }
fi

pass() { echo -e "  ${GREEN}✅ PASS${NC}: $1"; }
fail() { echo -e "  ${RED}❌ FAIL${NC}: $1"; ERRORS=$((ERRORS + 1)); SECTION_FAIL["$CURRENT_SECTION"]=1; }
warn() { echo -e "  ${YELLOW}⚠️  WARN${NC}: $1"; WARNINGS=$((WARNINGS + 1)); SECTION_WARN["$CURRENT_SECTION"]=1; }
section() { _ts_mark "$1"; echo -e "\n${CYAN}━━━ $1 ━━━${NC}"; CURRENT_SECTION="$1"; SECTION_COUNT=$((SECTION_COUNT + 1)); }

echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║    KB Consistency Checker v2.0           ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo "  KB Root: $KB_ROOT"
echo "  Date:    $(date +%Y-%m-%d)"

# ═══════════════════════════════════════════════════════════
# 阶段 0：一次 find 缓存（排除噪声/本地目录）
# ═══════════════════════════════════════════════════════════
SCAN_DIR="$(mktemp -d "${TMPDIR:-/tmp}/kb-check.XXXXXX")"
SCAN_FILE="$SCAN_DIR/kb-scan.tmp"
SCAN_FM="$SCAN_DIR/kb-scan-fm.tmp"
trap 'rm -rf "$SCAN_DIR"' EXIT

EXCLUDES=()
for d in .git _templates .obsidian .claude .hvigor .sisyphus .omo .playwright-mcp build oh_modules outputs demos tools screenshot _temp raw dist solutions workspace qt-issue-tracker electron-harmonyos-kb .gitcode .github drafts ohos-common-kb-public skills; do
  EXCLUDES+=(-not -path "*/$d/*")
done
_ts_mark "phase0: find"
find "$KB_ROOT" -type f -name "*.md" "${EXCLUDES[@]}" | sort > "$SCAN_FILE"

# ── frontmatter 工具函数 ──

# 提取 frontmatter 块文本（首尾 --- 之间）。无 frontmatter 返回空。
# strip UTF-8 BOM (\xEF\xBB\xBF) first — some pages got BOM'd by an editor/merge, which breaks /^---/ detection.
extract_fm() {
  awk '{sub(/^\357\273\277/,"")} /^---[[:space:]]*$/{fm++; if(fm==2)exit; next} fm==1{print}' "$1"
}

# 一次性提取一个文件的关键 frontmatter 字段，输出 TSV 行：
# file<TAB>has_fm<TAB>type<TAB>id<TAB>status<TAB>updated<TAB>created<TAB>has_ad<TAB>has_ar<TAB>has_sb<TAB>audience<TAB>tags<TAB>refs<TAB>related_problems<TAB>has_summary<TAB>has_domain<TAB>has_severity<TAB>has_error_message
# 列号:  1       2       3     4     5       6        7        8       9       10      11        12      13      14                15           16          17              18
SEP=$(printf '\x1f')
extract_row() {
  awk -v f="$1" '
    BEGIN { in_fm=0; SEP=sprintf("%c",31) }
    { sub(/^\357\273\277/,"") }
    /^---[[:space:]]*$/ { if(in_fm==0){in_fm=1; has_fm=1; next} else {in_fm=0; next} }
    in_fm==0 { next }
    {
      sub(/\r$/,"")
      if ($0 ~ /^type:/)            { type=$0;     sub(/^type:[[:space:]]*/,"",type) }
      else if ($0 ~ /^id:/)         { id=$0;       sub(/^id:[[:space:]]*/,"",id) }
      else if ($0 ~ /^status:/)     { status=$0;   sub(/^status:[[:space:]]*/,"",status) }
      else if ($0 ~ /^updated:/)    { updated=$0;  sub(/^updated:[[:space:]]*/,"",updated) }
      else if ($0 ~ /^created:/)    { created=$0;  sub(/^created:[[:space:]]*/,"",created) }
      else if ($0 ~ /^audience:/)   { audience=$0; sub(/^audience:[[:space:]]*/,"",audience) }
      else if ($0 ~ /^archive_date:/)     { has_ad=1 }
      else if ($0 ~ /^archive_reason:/)   { has_ar=1 }
      else if ($0 ~ /^superseded_by:/)    { has_sb=1 }
      else if ($0 ~ /^summary:/)    { has_summary=1 }
      else if ($0 ~ /^domain:/)     { has_domain=1 }
      else if ($0 ~ /^severity:/)   { has_severity=1 }
      else if ($0 ~ /^error_message:/) { has_errmsg=1 }
      # flow list: field: [a, b, c]
      else if ($0 ~ /^tags:/)       { t=$0; sub(/^tags:[[:space:]]*\[? */,"",t); sub(/ *].*$/,"",t); gsub(/[[:space:]]/,"",t); tags=t }
      else if ($0 ~ /^refs:/)       { t=$0; sub(/^refs:[[:space:]]*\[? */,"",t); sub(/ *].*$/,"",t); gsub(/[[:space:]]/,"",t); refs=t }
      else if ($0 ~ /^related_problems:/) { t=$0; sub(/^related_problems:[[:space:]]*\[? */,"",t); sub(/ *].*$/,"",t); gsub(/[[:space:]]/,"",t); rprob=t }
    }
    END { printf "%s"SEP"%d"SEP"%s"SEP"%s"SEP"%s"SEP"%s"SEP"%s"SEP"%d"SEP"%d"SEP"%d"SEP"%s"SEP"%s"SEP"%s"SEP"%s"SEP"%d"SEP"%d"SEP"%d"SEP"%d\n", f, has_fm+0, type, id, status, updated, created, has_ad+0, has_ar+0, has_sb+0, audience, tags, refs, rprob, has_summary+0, has_domain+0, has_severity+0, has_errmsg+0 }
  ' "$1"
}

# 从 FM 文本提取列表字段（兼容 flow [a,b,c] 与 block - a 两格式），每行输出一个元素
extract_list() {
  printf '%s\n' "$2" | awk -v field="$1" '
    BEGIN { in_field=0 }
    # flow: field: [a, b, c] 或 field: []
    $0 ~ "^" field ":[[:space:]]*\\[" {
      line = $0
      sub("^" field ":[[:space:]]*\\[", "", line)
      sub("\\].*$", "", line)
      gsub(/[[:space:]]/, "", line)
      if (line != "") {
        n = split(line, arr, ",")
        for (i=1; i<=n; i++) if (arr[i] != "") print arr[i]
      }
      in_field = 0; next
    }
    # block 序列起点: field: (行尾无值)
    $0 ~ "^" field ":[[:space:]]*$" { in_field = 1; next }
    # 其他字段行: 结束 block
    in_field == 1 && /^[a-z_]+:/ { in_field = 0; next }
    in_field == 1 {
      if ($0 ~ /^[[:space:]]*- /) {
        line = $0
        sub(/^[[:space:]]*- /, "", line)
        sub(/\r$/, "", line)
        gsub(/[[:space:]]/, "", line)
        if (line != "") print line
      } else { in_field = 0 }
      next
    }
  '
}

# ═══════════════════════════════════════════════════════════
# 阶段 1：构建 frontmatter 缓存 + 累积 id 映射
# ═══════════════════════════════════════════════════════════
_ts_mark "phase1: fm-cache"
> "$SCAN_FM"
declare -A id_count=()
declare -A id_to_path=()
declare -A id_audience=()
declare -A page_tags_map=()
declare -A page_refs_map=()
declare -A page_rprob_map=()
declare -A file_status_map=()
declare -A basename_aud=()

# 用进程替换让循环体在主 shell（关联数组修改可保留）
# 分隔符用 \x1f(ASCII 31) 而非 \t：tab 是空白字符，read 会合并连续 tab 致列错位
# 列: 1=file 2=has_fm 3=type 4=id 5=status 6=updated 7=created 8=has_ad 9=has_ar 10=has_sb 11=audience 12=tags 13=refs 14=rprob 15=has_summary 16=has_domain 17=has_severity 18=has_errmsg
while IFS=$'\x1f' read -r file has_fm type id status updated created has_ad has_ar has_sb audience tags refs rprob has_summary has_domain has_severity has_errmsg; do
  [ "$has_fm" = "1" ] || continue
  # 写缓存（18 列全存，后续 section 按需读取）
  printf '%s\037%s\037%s\037%s\037%s\037%s\037%s\037%s\037%s\037%s\037%s\037%s\037%s\037%s\037%s\037%s\037%s\037%s\n' \
    "$file" "$has_fm" "$type" "$id" "$status" "$updated" "$created" "$has_ad" "$has_ar" "$has_sb" \
    "$audience" "$tags" "$refs" "$rprob" "$has_summary" "$has_domain" "$has_severity" "$has_errmsg" >> "$SCAN_FM"
  if [ -n "$id" ]; then
    id_count["$id"]=$(( ${id_count["$id"]:-0} + 1 ))
    id_to_path["$id"]="$file"
    id_audience["$id"]="$audience"
  fi
  # tags/refs/rprob 是逗号分隔字符串，空格转回逗号方便后续 split
  [ -n "$tags" ] && page_tags_map["$file"]="$tags"
  [ -n "$refs" ] && page_refs_map["$file"]="$refs"
  [ -n "$rprob" ] && page_rprob_map["$file"]="$rprob"
  [ -n "$status" ] && file_status_map["$file"]="$status"
  _bn="${file##*/}"; basename_aud["${_bn%.md}"]="$audience"   # 参数展开，省 fork
done < <(while IFS= read -r f; do extract_row "$f"; done < "$SCAN_FILE")

# 各域 active/archived 文件数（按文件系统实际状态）
declare -A DOMAIN_ACTIVE=() DOMAIN_ARCHIVED=()
for d in semantic procedural episodic preference problems; do
  DOMAIN_ACTIVE[$d]=0; DOMAIN_ARCHIVED[$d]=0
done
while IFS=$'\x1f' read -r file has_fm type id status updated created has_ad has_ar has_sb audience tags refs rprob has_summary has_domain has_severity has_errmsg; do
  [ "$has_fm" = "1" ] || continue
  for d in semantic procedural episodic preference problems; do
    [[ "$file" == *"/$d/"* ]] || continue
    [ "$status" = "active" ]   && DOMAIN_ACTIVE[$d]=$(( ${DOMAIN_ACTIVE[$d]} + 1 ))
    [ "$status" = "archived" ] && DOMAIN_ARCHIVED[$d]=$(( ${DOMAIN_ARCHIVED[$d]} + 1 ))
    break
  done
done < "$SCAN_FM"

MAP_FILE="$KB_ROOT/_index/_map.md"

# ═══════════════════════════════════════════════════════════
# 1. 派生索引生成器幂等+可跑通
#    （替代旧 S1 _map 计数 / S2 _map 链接 / S4 active 索引完整性 /
#     S6a problems 计数 / S7 Dashboard 数值 / S15 _tags 双向 /
#     S17b 域 _index 必需 / S17c _index/ 必需文件）
#    生成器幂等 = 跑两遍 sha256 一致；_task-routing.md 存在性在此一并查
# ═══════════════════════════════════════════════════════════
section "1. 派生索引生成器幂等+可跑通"

REGEN="$KB_ROOT/_scripts/kb-regen-indexes.sh"
DERIVED_FILES="_index/_map.md _index/_tags.md _index/_dashboard.md problems/_lookup.md semantic/_index.md procedural/_index.md episodic/_index.md preference/_index.md problems/_index.md"
if [ ! -f "$REGEN" ]; then
  fail "生成器脚本不存在: _scripts/kb-regen-indexes.sh"
else
  TMP1=$(mktemp); TMP2=$(mktemp)
  if ! "$BASH" "$REGEN" >/dev/null 2>&1; then
    fail "生成器执行失败"
  else
    for f in $DERIVED_FILES; do [ -f "$KB_ROOT/$f" ] && sha256sum "$KB_ROOT/$f"; done > "$TMP1"
    # 幂等复跑只在生成器代码变更时执行（ADR-003：幂等检查是 code-change guard，防有人
    # 往派生 body 塞 date/随机致 write_if_changed 失效）。生成器未改则上次已验，跳过第 2 遍省 ~50% §1。
    # git diff 不可用（fresh clone/无 origin/main/dist 临时 git）时兜底跑第 2 遍（安全默认）。
    if git -C "$KB_ROOT" diff --quiet origin/main -- _scripts/kb-regen-indexes.sh 2>/dev/null; then
      pass "生成器幂等（代码未变，跳过二次复跑，上次已验）"
    else
      "$BASH" "$REGEN" >/dev/null 2>&1
      for f in $DERIVED_FILES; do [ -f "$KB_ROOT/$f" ] && sha256sum "$KB_ROOT/$f"; done > "$TMP2"
      if diff -q "$TMP1" "$TMP2" >/dev/null 2>&1; then
        pass "生成器幂等（二次运行 sha256 一致）"
      else
        fail "生成器非幂等（二次运行输出不一致）"
      fi
    fi
    [ -f "$KB_ROOT/_index/_task-routing.md" ] && pass "_task-routing.md 存在" || fail "_task-routing.md 不存在"
  fi
  rm -f "$TMP1" "$TMP2"
fi

# ═══════════════════════════════════════════════════════════
# 2. status 字段合法性（按 type 分流）
# ═══════════════════════════════════════════════════════════
section "2. status 字段合法性（按 type）"

INVALID=0
while IFS=$'\x1f' read -r _f _hfm _type _id _status _upd _cr _had _har _hsb _aud _tg _rf _rp _hs _hd _hsv _hem; do
  [ "$_hfm" = "1" ] || continue
  [ -n "$_type" ] || continue          # 无 type 的元文件/根文档跳过
  if [ -z "$_status" ]; then
    warn "缺 status: $(basename "$_f")"; INVALID=$((INVALID + 1)); continue
  fi
  case "$_type" in
    problem)
      case "$_status" in open|solved|workaround) :;; *) fail "problem 非法 status: '$_status' in $(basename "$_f")"; INVALID=$((INVALID + 1));; esac ;;
    semantic|procedural|episodic|preference|meta)
      case "$_status" in active|draft|archived|deprecated) :;; *) fail "非法 status: '$_status' (type=$_type) in $(basename "$_f")"; INVALID=$((INVALID + 1));; esac ;;
    *)
      warn "未知 type: '$_type' in $(basename "$_f")";;
  esac
done < "$SCAN_FM"
[ "$INVALID" -eq 0 ] && pass "所有 status 字段值合法（按 type 分流）"

# ═══════════════════════════════════════════════════════════
# 3. refs 交叉引用有效性（flow + block，id→path 映射）
# ═══════════════════════════════════════════════════════════
section "3. refs 交叉引用有效性"

BROKEN_REFS=0
while IFS=$'\x1f' read -r file has_fm type id status updated created has_ad has_ar has_sb audience tags refs rprob has_summary has_domain has_severity has_errmsg; do
  [ "$has_fm" = "1" ] || continue
  [ -n "$type" ] || continue
  [ -n "$refs" ] || continue
  IFS=',' read -ra ref_arr <<< "$refs"
  for ref in "${ref_arr[@]}"; do
    [ -z "$ref" ] && continue
    target="${id_to_path[$ref]:-}"
    if [ -z "$target" ] || [ ! -f "$target" ]; then
      fail "断裂的 ref: '$ref' in $(basename "$file")"
      BROKEN_REFS=$((BROKEN_REFS + 1))
    fi
  done
done < "$SCAN_FM"
[ "$BROKEN_REFS" -eq 0 ] && pass "所有 refs 交叉引用有效"

# ═══════════════════════════════════════════════════════════
# 4. problems related_problems refs 有效性
#    （旧 S6 拆分：6a total_problems 计数已折叠入 section 1 生成器幂等，
#     6b related_problems refs 有效性保留为独立 section）
# ═══════════════════════════════════════════════════════════
section "4. problems related_problems refs 有效性"

PROBLEMS_DIR="$KB_ROOT/problems"
BROKEN_RELATED=0
if [ -d "$PROBLEMS_DIR" ]; then
  ALL_PROBLEM_IDS=""
  for PFILE in "$PROBLEMS_DIR"/*.md; do
    [[ "$(basename "$PFILE")" == _* ]] && continue
    PID=$(awk -F': *' '/^id:/{print $2; exit}' "$PFILE")
    PID="${PID%$'\r'}"
    [ -n "$PID" ] && ALL_PROBLEM_IDS="$ALL_PROBLEM_IDS $PID"
  done
  for PFILE in "$PROBLEMS_DIR"/*.md; do
    [[ "$(basename "$PFILE")" == _* ]] && continue
    rprob="${page_rprob_map[$PFILE]:-}"
    [ -n "$rprob" ] || continue
    IFS=',' read -ra rp_arr <<< "$rprob"
    for rel in "${rp_arr[@]}"; do
      [ -z "$rel" ] && continue
      if ! echo "$ALL_PROBLEM_IDS" | grep -qw "$rel"; then
        warn "related_problems 引用不存在的 ID: '$rel' in $(basename "$PFILE")"
        BROKEN_RELATED=$((BROKEN_RELATED + 1))
      fi
    done
  done
fi
[ "$BROKEN_RELATED" -eq 0 ] && pass "所有 related_problems 引用有效"

# ═══════════════════════════════════════════════════════════
# 5. updated 日期格式合法性
# ═══════════════════════════════════════════════════════════
section "5. updated 日期格式"

BAD_DATES=0
while IFS=$'\x1f' read -r file has_fm type id status updated created has_ad has_ar has_sb audience tags refs rprob has_summary has_domain has_severity has_errmsg; do
  [ "$has_fm" = "1" ] || continue
  [ -n "$updated" ] || continue
  if [[ ! "$updated" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    fail "无效日期格式: '$updated' in $(basename "$file")"
    BAD_DATES=$((BAD_DATES + 1))
  fi
done < "$SCAN_FM"
[ "$BAD_DATES" -eq 0 ] && pass "所有 updated 日期格式合法 (YYYY-MM-DD)"

# ═══════════════════════════════════════════════════════════
# 6. 归档页面 frontmatter 完整性
# ═══════════════════════════════════════════════════════════
section "6. 归档页 frontmatter 完整性"

ARCHIVE_ISSUES=0
while IFS=$'\x1f' read -r file has_fm type id status updated created has_ad has_ar has_sb audience tags refs rprob has_summary has_domain has_severity has_errmsg; do
  [ "$has_fm" = "1" ] || continue
  if [ "$status" = "archived" ] || [ "$status" = "deprecated" ]; then
    [ "$has_ad" = "1" ] || { warn "归档页缺 archive_date: $(basename "$file")"; ARCHIVE_ISSUES=$((ARCHIVE_ISSUES + 1)); }
    [ "$has_ar" = "1" ] || { warn "归档页缺 archive_reason: $(basename "$file")"; ARCHIVE_ISSUES=$((ARCHIVE_ISSUES + 1)); }
    [ "$has_sb" = "1" ] || { warn "归档页缺 superseded_by: $(basename "$file")"; ARCHIVE_ISSUES=$((ARCHIVE_ISSUES + 1)); }
  fi
done < "$SCAN_FM"
[ "$ARCHIVE_ISSUES" -eq 0 ] && pass "所有归档页面 frontmatter 完整"

# ═══════════════════════════════════════════════════════════
# 7. 嵌套路径检查（意外创建的 $KB_ROOT/c/ 副本）
# ═══════════════════════════════════════════════════════════
section "7. 嵌套路径检查"

if [ -d "$KB_ROOT/c" ]; then
  NESTED=$(find "$KB_ROOT/c" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
  fail "发现嵌套路径目录: \$KB_ROOT/c/ 包含 $NESTED 个 .md 文件（可能是意外创建的副本）"
else
  pass "无嵌套路径文件"
fi

# ═══════════════════════════════════════════════════════════
# 8. frontmatter 必填字段（按 type）
# ═══════════════════════════════════════════════════════════
section "8. frontmatter 必填字段"

# 单次 awk 处理所有文件（避免逐文件 fork，Windows Git Bash 上极慢）
# 输入：SCAN_FILE 中每行一个文件路径
# 输出：file\tmissing_field（每行一个缺失项）
MISSING_FIELDS_OUTPUT=$(xargs -d '\n' awk '
  BEGINFILE {
    in_fm=0; type=""; has_id=0; has_domain=0; has_tags=0
    has_created=0; has_updated=0; has_status=0; has_summary=0
    has_severity=0; has_error_message=0
  }
  { sub(/^\357\273\277/,""); sub(/\r$/,"") }
  /^---[[:space:]]*$/ { if(in_fm==0){in_fm=1; next} else {in_fm=0; next} }
  in_fm==0 { next }
  /^type:/           { type=$0; sub(/^type:[[:space:]]*/,"",type) }
  /^id:/             { has_id=1 }
  /^domain:/         { has_domain=1 }
  /^tags:/           { has_tags=1 }
  /^created:/        { has_created=1 }
  /^updated:/        { has_updated=1 }
  /^status:/         { has_status=1 }
  /^summary:/        { has_summary=1 }
  /^severity:/       { has_severity=1 }
  /^error_message:/  { has_error_message=1 }
  ENDFILE {
    if (type == "") next
    if (type == "problem") {
      n = split("id domain tags created updated status severity error_message", fields, " ")
    } else if (type ~ /^(semantic|procedural|episodic|preference|meta)$/) {
      n = split("id domain tags created updated status summary", fields, " ")
    } else { next }
    for (i=1; i<=n; i++) {
      f = fields[i]
      if (f=="id" && has_id) continue
      if (f=="domain" && has_domain) continue
      if (f=="tags" && has_tags) continue
      if (f=="created" && has_created) continue
      if (f=="updated" && has_updated) continue
      if (f=="status" && has_status) continue
      if (f=="summary" && has_summary) continue
      if (f=="severity" && has_severity) continue
      if (f=="error_message" && has_error_message) continue
      printf "%s\t%s\n", FILENAME, f
    }
  }
' < "$SCAN_FILE" 2>/dev/null)

MISSING_FIELDS=0
if [ -n "$MISSING_FIELDS_OUTPUT" ]; then
  while IFS=$'\t' read -r file field; do
    warn "缺 $field: $(basename "$file")"
    MISSING_FIELDS=$((MISSING_FIELDS + 1))
  done <<< "$MISSING_FIELDS_OUTPUT"
fi
[ "$MISSING_FIELDS" -eq 0 ] && pass "所有页面 frontmatter 必填字段齐全"

# ═══════════════════════════════════════════════════════════
# 9. id 唯一性
# ═══════════════════════════════════════════════════════════
section "9. id 唯一性"

DUP=0
for aid in "${!id_count[@]}"; do
  if [ "${id_count[$aid]}" -gt 1 ]; then
    fail "重复 id: '$aid' 出现 ${id_count[$aid]} 次"
    DUP=$((DUP + 1))
  fi
done
[ "$DUP" -eq 0 ] && pass "所有 id 唯一"

# ═══════════════════════════════════════════════════════════
# 10. id/文件名一致性（仅扁平域 semantic/procedural/preference）
# ═══════════════════════════════════════════════════════════
section "10. id/文件名一致性（扁平域）"

MISMATCH=0
while IFS=$'\x1f' read -r file has_fm type id status updated created has_ad has_ar has_sb audience tags refs rprob has_summary has_domain has_severity has_errmsg; do
  [ "$has_fm" = "1" ] || continue
  case "$type" in
    semantic|procedural|preference) :;;
    *) continue;;
  esac
  [[ "${file##*/}" == "_index.md" ]] && continue
  if [ -z "$id" ]; then
    warn "缺 id: $(basename "$file")"; MISMATCH=$((MISMATCH + 1)); continue
  fi
  base="${file##*/}"; base="${base%.md}"   # 参数展开，省 fork
  expected="$type-$base"
  if [ "$id" != "$expected" ]; then
    warn "id/文件名不一致: id='$id' 期望='$expected' in $(basename "$file")"
    MISMATCH=$((MISMATCH + 1))
  fi
done < "$SCAN_FM"
[ "$MISMATCH" -eq 0 ] && pass "扁平域 id 与文件名一致"

# ═══════════════════════════════════════════════════════════
# 11. type/目录一致性
# ═══════════════════════════════════════════════════════════
section "11. type/目录一致性"

TYPE_DIR_MISMATCH=0
while IFS=$'\x1f' read -r file has_fm type id status updated created has_ad has_ar has_sb audience tags refs rprob has_summary has_domain has_severity has_errmsg; do
  [ "$has_fm" = "1" ] || continue
  [ -n "$type" ] || continue
  expected_dir=""
  case "$type" in
    semantic)    expected_dir="/semantic/";;
    procedural)  expected_dir="/procedural/";;
    episodic)    expected_dir="/episodic/";;
    preference)  expected_dir="/preference/";;
    problem)     expected_dir="/problems/";;
    meta)        expected_dir="";;   # meta 允许 /_index/ 或 /reports/，下方单独判定
  esac
  if [ -n "$expected_dir" ]; then
    if [[ "$file" != *"$expected_dir"* ]]; then
      fail "type='$type' 但文件不在 $expected_dir : ${file#$KB_ROOT/}"
      TYPE_DIR_MISMATCH=$((TYPE_DIR_MISMATCH + 1))
    fi
  elif [ "$type" = "meta" ]; then
    # meta 页允许在 _index/ 或 reports/（领导仪表盘迁 reports/，见 §6.3）
    if [[ "$file" != *"/_index/"* ]] && [[ "$file" != *"/reports/"* ]]; then
      fail "type='meta' 但文件不在 /_index/ 或 /reports/ : ${file#$KB_ROOT/}"
      TYPE_DIR_MISMATCH=$((TYPE_DIR_MISMATCH + 1))
    fi
  fi
done < "$SCAN_FM"
[ "$TYPE_DIR_MISMATCH" -eq 0 ] && pass "所有 type 与所在目录一致"

# ═══════════════════════════════════════════════════════════
# 12. 意外文件检查（根目录游离文件 + _temp/ 未清理）
# ═══════════════════════════════════════════════════════════
section "12. 意外文件检查"

STRAY=0
ALLOWED_ROOT="CLAUDE.md AGENTS.md README.md SETUP.md SETUP_PROMPT.md ENV.md ENV.example.md ENV.local.md kb.yaml TODO.md TODO.local.md TEAM.md TEAM_ONBOARDING.md WORKLOG.md LICENSE .gitignore"
for item in "$KB_ROOT"/*; do
  [ -d "$item" ] && continue          # 目录在 section 13 查
  name=$(basename "$item")
  if ! echo " $ALLOWED_ROOT " | grep -q " $name "; then
    warn "根目录游离文件: $name"
    STRAY=$((STRAY + 1))
  fi
done
if [ -d "$KB_ROOT/_temp" ]; then
  cnt=$(find "$KB_ROOT/_temp" -type f 2>/dev/null | wc -l | tr -d ' ')
  if [ "$cnt" -gt 0 ]; then
    warn "_temp/ 有 $cnt 个临时文件未清理"
    STRAY=$((STRAY + 1))
  fi
fi
[ "$STRAY" -eq 0 ] && pass "无意外文件"

# ═══════════════════════════════════════════════════════════
# 13. KB 结构校验（顶层目录白名单 + episodic 子目录白名单）
#     （旧 S17 拆分：17a 顶层目录白名单保留 / 17b 域 _index 必需折叠入
#      section 1 生成器幂等 / 17c _index/ 必需文件折叠入 section 1 生成器
#      （只留 _task-routing.md 存在性查，已在 section 1）/ 17d episodic 子目录白名单保留）
# ═══════════════════════════════════════════════════════════
section "13. KB 结构校验"

STRUCT_ISSUES=0
# 顶层目录白名单（标准结构 + 已知本地工作产物 + 工具隐藏目录）
ALLOWED_TOP="_index _scripts _templates semantic procedural episodic preference problems raw reports outputs demos tools _temp build oh_modules screenshot .git .obsidian .hvigor .claude .sisyphus .vscode .idea dist solutions workspace team .gitcode .github"
for item in "$KB_ROOT"/*/; do
  name=$(basename "$item")
  if ! echo " $ALLOWED_TOP " | grep -q " $name "; then
    warn "未知顶层目录: $name"
    STRUCT_ISSUES=$((STRUCT_ISSUES + 1))
  fi
done
# episodic 子目录白名单
if [ -d "$KB_ROOT/episodic" ]; then
  for item in "$KB_ROOT/episodic"/*/; do
    name=$(basename "$item")
    case "$name" in
      decisions|postmortems|projects) :;;
      *) warn "episodic/ 下未知子目录: $name"; STRUCT_ISSUES=$((STRUCT_ISSUES + 1));;
    esac
  done
fi
[ "$STRUCT_ISSUES" -eq 0 ] && pass "KB 结构合法"

# ═══════════════════════════════════════════════════════════
# 14. trunk 页面不得含 audience: 字段（存在即公开，无需标注）
# ═══════════════════════════════════════════════════════════
section "14. trunk 页面无 audience 字段"

INVALID_AUD=0
while IFS=$'\x1f' read -r file has_fm type id status updated created has_ad has_ar has_sb audience tags refs rprob has_summary has_domain has_severity has_errmsg; do
  [ "$has_fm" = "1" ] || continue
  case "$type" in
    semantic|procedural|episodic|preference|problem)
      aud="$audience"
      if [ -n "$aud" ]; then
        fail "trunk 页面不应含 audience 字段（存在即公开）: $(basename "$file") audience=$aud"; INVALID_AUD=$((INVALID_AUD + 1))
      fi
      ;;
  esac
done < "$SCAN_FM"
[ "$INVALID_AUD" -eq 0 ] && pass "所有 trunk 内容页无 audience 字段"

# ═══════════════════════════════════════════════════════════
# 15. 所有页面不得命中私有内容模式（trunk 是公开仓，全部页面必须安全）
# ═══════════════════════════════════════════════════════════
section "15. 全仓无私有内容"

# 私有内容定义（原 dev-edition.manifest [global_redact] 的 LHS；泛化为任意用户路径）
PRIVATE_PATTERNS=(
  'C:[\\/]Users[\\/][A-Za-z0-9_.-]+'
  'C:[\\/]code[\\/]'
  'C:[\\/]Qt[\\/\\-]'
  'D:[\\/]oh[\\/]'
  '/home/[A-Za-z0-9_.-]+/'
  'codereview\.qtcompany\.cn:29416'
  'my\.feishu\.cn/'
  '于宗洋|刘子豪|王志铧|郭嘉伟'
  'Foxit PDF Editor'
  '系统同事|商业Qt客户'
  '(^|[^\\\/a-zA-Z0-9_])WORK_ROOT([^[:alnum:]_]|$)'
  'toTqtc|toOhos|toCustomers|fromCustomers|fromTqtc'
  'OHOS_TEMPLATE_ZIP'
  'TODO\.local\.md'
)
LEAK=0
# 收集所有有 frontmatter 的内容页
ALL_CONTENT_FILES=()
while IFS=$'\x1f' read -r file has_fm type id status updated created has_ad has_ar has_sb audience tags refs rprob has_summary has_domain has_severity has_errmsg; do
  [ "$has_fm" = "1" ] || continue
  ALL_CONTENT_FILES+=("$file")
done < "$SCAN_FM"
# 每模式一次 grep -lE 扫全部内容页
if [ ${#ALL_CONTENT_FILES[@]} -gt 0 ]; then
  for pat in "${PRIVATE_PATTERNS[@]}"; do
    while IFS= read -r _f; do
      [ -z "$_f" ] && continue
      # problems/ 页面的 error_message 字段允许包含路径（用于全文搜索匹配）
      case "$_f" in */problems/*) continue ;; esac
      fail "页面命中私有模式 '$pat': ${_f#$KB_ROOT/}"; LEAK=$((LEAK + 1))
    done < <(grep -lE "$pat" "${ALL_CONTENT_FILES[@]}" 2>/dev/null)
  done
fi
[ "$LEAK" -eq 0 ] && pass "全仓无私有内容（路径/人名/Gerrit/feishu/供应链 token 等）"

# ═══════════════════════════════════════════════════════════
# 16. refs 必须解析到本仓存在的 id（无悬空引用）
# ═══════════════════════════════════════════════════════════
section "16. refs 解析到本仓已有 id"

# id_audience 已在阶段 1 预构建（缓存）— trunk 模式下仅用于 id 存在性检查

BAD_REFS=0
while IFS=$'\x1f' read -r file has_fm type id status updated created has_ad has_ar has_sb audience tags refs rprob has_summary has_domain has_severity has_errmsg; do
  [ "$has_fm" = "1" ] || continue
  [ -n "$type" ] || continue
  [ -n "$refs" ] || continue
  IFS=',' read -ra ref_arr <<< "$refs"
  for ref in "${ref_arr[@]}"; do
    [ -z "$ref" ] && continue
    # 允许引用 ohos-common-kb-public 中的页面
    case "$ref" in ohos-common-kb*|harmonyos-*) continue ;; esac
    ra="${id_audience[$ref]:-__absent__}"
    if [ "$ra" = "__absent__" ]; then
      fail "refs 引用不存在的 id '$ref': ${file#$KB_ROOT/}"; BAD_REFS=$((BAD_REFS + 1))
    fi
  done
done < "$SCAN_FM"
[ "$BAD_REFS" -eq 0 ] && pass "所有 refs 解析到本仓已有 id"

# ═══════════════════════════════════════════════════════════
# 16b. 跨 KB common 依赖闭包（vendored ohos-common-kb-public）
# ═══════════════════════════════════════════════════════════
section "16b. 跨 KB common 依赖闭包"
COMMON_ROOT="$KB_ROOT/ohos-common-kb-public"
EXTERNAL_DEP_ERRORS=0
cross_kb_check() {
  source_file="$1"
  dependency="$2"
  rel="${dependency#ohos-common-kb/}"
  rel="${rel%.md}.md"
  target="$COMMON_ROOT/$rel"
  if [ -d "$COMMON_ROOT" ] && [ ! -f "$target" ]; then
    fail "跨 KB 目标不存在 '$dependency' (expected: ohos-common-kb-public/$rel): ${source_file#$KB_ROOT/}"; EXTERNAL_DEP_ERRORS=$((EXTERNAL_DEP_ERRORS + 1))
  fi
}
while IFS=$'\x1f' read -r file has_fm type id status updated created has_ad has_ar has_sb audience tags refs rprob has_summary has_domain has_severity has_errmsg; do
  [ "$has_fm" = "1" ] || continue
  while IFS= read -r dep; do
    case "$dep" in ohos-common-kb/*) cross_kb_check "$file" "$dep" ;; esac
  done < <(awk '
    /^```/ || /^~~~/ { fence=!fence; next }
    fence { next }
    { if (in_comment) { if (index($0,"-->") > 0) { sub(/^.*-->/,"",$0); in_comment=0 } else next }; if (index($0,"<!--") > 0) { before=substr($0,1,index($0,"<!--")-1); after=substr($0,index($0,"<!--")+4); if (index(after,"-->") > 0) $0=before substr(after,index(after,"-->")+3); else { $0=before; in_comment=1 } }; gsub(/`[^`]*`/,"",$0)
    { while(match($0,/\[\[ohos-common-kb\/[^]|#[:space:]]+/)){ print substr($0,RSTART+2,RLENGTH-2); $0=substr($0,RSTART+RLENGTH) } }
  ' "$file")
  while IFS= read -r dep; do
    case "$dep" in ohos-common-kb/*) cross_kb_check "$file" "$dep" ;; esac
  done < <(printf '%s\n' "$refs" | tr ',' '\n')
done < "$SCAN_FM"
for hub in "$KB_ROOT/problems/_lookup.md" "$KB_ROOT/problems/_index.md" "$KB_ROOT/_index/_task-routing.md" "$KB_ROOT/_index/_cross-refs.md"; do
  [ -f "$hub" ] || continue
  while IFS= read -r dep; do cross_kb_check "$hub" "$dep"; done < <(awk '
    /^```/ || /^~~~/ { fence=!fence; next }
    fence { next }
    { if (in_comment) { if (index($0,"-->") > 0) { sub(/^.*-->/,"",$0); in_comment=0 } else next }; if (index($0,"<!--") > 0) { before=substr($0,1,index($0,"<!--")-1); after=substr($0,index($0,"<!--")+4); if (index(after,"-->") > 0) $0=before substr(after,index(after,"-->")+3); else { $0=before; in_comment=1 } }; gsub(/`[^`]*`/,"",$0)
    { while(match($0,/\[\[ohos-common-kb\/[^]|#[:space:]]+/)){ print substr($0,RSTART+2,RLENGTH-2); $0=substr($0,RSTART+RLENGTH) } }
  ' "$hub")
done
[ "$EXTERNAL_DEP_ERRORS" -eq 0 ] && pass "跨 KB common 依赖闭包通过"

# ═══════════════════════════════════════════════════════════
# 17. issue#1 TODO 统一为 ADR-001 方案（防回归）
# ═══════════════════════════════════════════════════════════
section "17. issue#1 TODO 统一为 ADR-001"

TODO_ISSUES=0
if ! git -C "$KB_ROOT" check-ignore TODO.local.md >/dev/null 2>&1; then
  fail "TODO.local.md 未 gitignore（应为个人实际待办，不入库）"; TODO_ISSUES=$((TODO_ISSUES + 1))
fi
if git -C "$KB_ROOT" check-ignore TODO.md >/dev/null 2>&1; then
  fail "TODO.md 仍被 gitignore（应为入库纯模板）"; TODO_ISSUES=$((TODO_ISSUES + 1))
fi
if grep -qE '^TODO\.md$' "$KB_ROOT/.gitignore" 2>/dev/null; then
  fail ".gitignore 仍含独立 TODO.md 忽略行"; TODO_ISSUES=$((TODO_ISSUES + 1))
fi
if ! grep -q 'TODO.local.md' "$KB_ROOT/CLAUDE.md" 2>/dev/null || ! grep -q 'TODO.local.md' "$KB_ROOT/AGENTS.md" 2>/dev/null; then
  fail "CLAUDE/AGENTS 进度同步未指向 TODO.local.md"; TODO_ISSUES=$((TODO_ISSUES + 1))
fi
if ! grep -q '模板' "$KB_ROOT/TODO.md" 2>/dev/null; then
  fail "TODO.md 非模板（可能含实际条目）"; TODO_ISSUES=$((TODO_ISSUES + 1))
fi
[ "$TODO_ISSUES" -eq 0 ] && pass "TODO 统一为 ADR-001 方案（TODO.md=入库模板，TODO.local.md=个人实际待办）"

# ═══════════════════════════════════════════════════════════
# 18. issue#1 _changelog.md 悬空引用清除（防回归）
# ═══════════════════════════════════════════════════════════
section "18. issue#1 _changelog.md 悬空引用清除"

CHG_ISSUES=0
if [ -f "$KB_ROOT/_index/_changelog.md" ]; then
  fail "_index/_changelog.md 被重建（违反 06-25 退役为 ADR 的决策）"; CHG_ISSUES=$((CHG_ISSUES + 1))
fi
# live SOP 文件不应有 _changelog.md 活引用
# （排除 _dashboard.md 的退役声明与 ADR-001 退役决策本体——二者为合法历史/退役提及）
CHG_FILES="CLAUDE.md AGENTS.md _index/_task-routing.md episodic/postmortems/kb-correction-propagation.md procedural/commercial-qt-harmonyos-bug-triage.md semantic/workflow-supply-chain.md TEAM.md TEAM_ONBOARDING.md"
for cf in $CHG_FILES; do
  f="$KB_ROOT/$cf"
  [ -f "$f" ] || continue
  if grep -q '_changelog.md' "$f" 2>/dev/null; then
    fail "live SOP 仍有 _changelog.md 活引用: $cf"; CHG_ISSUES=$((CHG_ISSUES + 1))
  fi
done
[ "$CHG_ISSUES" -eq 0 ] && pass "_changelog.md 悬空引用已清除（未重建，退役为 ADR）"

# ═══════════════════════════════════════════════════════════
# 19. issue#1 共享文件硬编码个人路径（防回归）
# ═══════════════════════════════════════════════════════════
section "19. 共享文件无硬编码个人路径"

PATH_LEAK=0
# 个人路径不应出现在共享文件（trunk 所有文件都是公开的）
# 排除：problems/（error_message 中可能含路径用于全文匹配）
while IFS= read -r f; do
  case "$f" in
    */problems/*|*/ENV.local.md|*/TODO.local.md|*/postmortems/*) continue;;
  esac
  if grep -qE 'C:[\\/]Users[\\/][A-Za-z0-9_.-]+|/home/[A-Za-z0-9_.-]+/' "$f" 2>/dev/null; then
    fail "共享文件含个人路径: ${f#$KB_ROOT/}"; PATH_LEAK=$((PATH_LEAK + 1))
  fi
done < "$SCAN_FILE"
[ "$PATH_LEAK" -eq 0 ] && pass "共享文件无硬编码个人路径"

# ═══════════════════════════════════════════════════════════
# 20. 正文交叉引用不指向缺失页
#     （trunk 中所有引用必须解析到本仓存在的页面）
# ═══════════════════════════════════════════════════════════
section "20. 正文交叉引用不指向缺失页"

# basename_aud 已在阶段 1 预构建（缓存）

PROSE_LEAK=0
while IFS=$'\x1f' read -r file has_fm type id status updated created has_ad has_ar has_sb audience tags refs rprob has_summary has_domain has_severity has_errmsg; do
  [ "$has_fm" = "1" ] || continue
  [ -n "$type" ] || continue
  # 一次性提取正文引用：W:wikilink  M:mdlink  B:bare-slug(后不跟'(')  S:(internal)自披露
  # 注：reused_by 字段已从 frontmatter 删除（ADR-003 派生索引自动化），不再存在。
  refs=$( awk '
      /^---[[:space:]]*$/{fm++; if(fm==2){f=1; next} next}
      f{
        # §8.3 误报规避：先剥围栏代码块（```/~~~）与行内代码，避免 C++ [[maybe_unused]]/[[nodiscard]] 等属性被当成 wikilink（见 _index/_link-conventions.md）
        if ($0 ~ /^```/ || $0 ~ /^~~~/) { fence=!fence; next }
        if (fence) next
        gsub(/`[^`]*`/, "", $0)
        line=$0
        while (match(line, /\[\[[a-z0-9][a-z0-9_-]+/)) { print "W:" substr(line, RSTART+2, RLENGTH-2); line=substr(line, RSTART+RLENGTH) }
        line=$0
        while (match(line, /\]\([^)]*\.md\)/)) { m=substr(line,RSTART,RLENGTH); sub(/^\]\(/,"",m); sub(/\)$/,"",m); print "M:" m; line=substr(line,RSTART+RLENGTH) }
        line=$0
        while (match(line, /\[[a-z][a-z0-9-]+\]/)) { pos=RSTART+RLENGTH; after=substr($0,pos,1); if(after!="(") print "B:" substr(line,RSTART+1,RLENGTH-2); line=substr(line,RSTART+RLENGTH) }
        if ($0 ~ /（internal/) print "S:1"   # 仅全角（）自披露标注；半角 (internal) 是 C++ 可见性（如 QPlatformNativeInterface (internal)），非 KB 内外分区自披露，不报
      }
    ' "$file" )
  [ -z "$refs" ] && continue
  while IFS=: read -r kind val; do
    [ -z "$val" ] && continue
    case "$kind" in
      S) warn "页面正文含 (internal) 标注（trunk 无内外之分）: ${file#$KB_ROOT/}"; PROSE_LEAK=$((PROSE_LEAK+1)) ;;
      W) case "$val" in ohos-common-kb|ohos-common-kb/*|harmonyos-*) continue ;; esac
         ia="${id_audience[$val]:-__absent__}"; ba="${basename_aud[$val]:-__absent__}"
         if [ "$ia" = "__absent__" ] && [ "$ba" = "__absent__" ]; then fail "[[wikilink]] 指向缺失页 '$val': ${file#$KB_ROOT/}"; PROSE_LEAK=$((PROSE_LEAK+1)); fi ;;
      M) case "$val" in http://*|https://*) continue ;; esac
         target="$(dirname "$file")/$val"; target="${target//\/.\//\/}"
         if [ ! -f "$target" ]; then fail "markdown 链接指向缺失文件 '$val': ${file#$KB_ROOT/}"; PROSE_LEAK=$((PROSE_LEAK+1)); fi ;;
      B) : ;;  # 裸 [slug] 在 trunk 模式下不检查（误报率高，且无 internal 概念）
    esac
  done <<< "$refs"
done < "$SCAN_FM"
[ "$PROSE_LEAK" -eq 0 ] && pass "正文交叉引用全部解析到本仓已有页面"

# ═══════════════════════════════════════════════════════════
# 21. 正文无内部任务路由码 [I]/[J]/[K]/[L]/[P]/[R]/[O]/[E]/[U]
#     （私有 overlay 专用路由码不应出现在公开 trunk；WARN 级）
# ═══════════════════════════════════════════════════════════
section "21. 正文无内部任务路由码"

ROUTING_LEAK=0
while IFS=$'\x1f' read -r file has_fm type id status updated created has_ad has_ar has_sb audience tags refs rprob has_summary has_domain has_severity has_errmsg; do
  [ "$has_fm" = "1" ] || continue
  [ -n "$type" ] || continue
  if grep -qE '\[(I|J|K|L|P|R|O|E|U)\]([^(]|$)' "$file"; then
    warn "页面正文含内部任务路由码 [I/J/K/...]: ${file#$KB_ROOT/}"; ROUTING_LEAK=$((ROUTING_LEAK+1))
  fi
done < "$SCAN_FM"
[ "$ROUTING_LEAK" -eq 0 ] && pass "正文无内部任务路由码"

# ═══════════════════════════════════════════════════════════
# 22. active 页 summary 完整性
#     （所有 active 内容页必须有 summary 字段，保障 AI 用 grep -A3 替代
#      _map 的等价性——所有页都有 summary，grep 才等价。缺 summary 的 WARN。）
# ═══════════════════════════════════════════════════════════
section "22. active 页 summary 完整性"

SUMMARY_ISSUES=0
while IFS=$'\x1f' read -r file has_fm type id status updated created has_ad has_ar has_sb audience tags refs rprob has_summary has_domain has_severity has_errmsg; do
  [ "$has_fm" = "1" ] || continue
  [ "$status" = "active" ] || continue
  case "$type" in
    semantic|procedural|episodic|preference) :;;
    *) continue;;
  esac
  [[ "${file##*/}" == "_index.md" ]] && continue
  if [ "$has_summary" != "1" ]; then
    warn "active 页缺 summary: ${file#$KB_ROOT/}"
    SUMMARY_ISSUES=$((SUMMARY_ISSUES + 1))
  fi
done < "$SCAN_FM"
[ "$SUMMARY_ISSUES" -eq 0 ] && pass "所有 active 内容页 summary 完整"

# ═══════════════════════════════════════════════════════════
# 23. 已迁移旧路径零活跃引用
#     Q3a Move 页面已删除，不允许 active 内容重新引入旧 id/path。
#     WORKLOG/activity/raw 等历史或来源记录不在 SCAN_FM active 页范围内。
# ═══════════════════════════════════════════════════════════
section "23. 已迁移旧路径零活跃引用"

RETIRED_REF_ISSUES=0
while IFS=$'\x1f' read -r file has_fm type id status updated created has_ad has_ar has_sb audience tags refs rprob has_summary has_domain has_severity has_errmsg; do
  [ "$has_fm" = "1" ] || continue
  [ "$status" = "active" ] || continue
  if grep -qE 'semantic/(deveco-cli-commands|deveco-mcp-toolchain|harmonyos-dev-fundamentals)\.md|\[\[(semantic-)?(deveco-cli-commands|deveco-mcp-toolchain|harmonyos-dev-fundamentals)(\||\]\])' "$file"; then
    fail "active 页重新引用已迁移旧路径: ${file#$KB_ROOT/}"
    RETIRED_REF_ISSUES=$((RETIRED_REF_ISSUES + 1))
  fi
done < "$SCAN_FM"
[ "$RETIRED_REF_ISSUES" -eq 0 ] && pass "已迁移旧路径保持零活跃引用"

# ═══════════════════════════════════════════════════════════
# 24. drafts/ 卫生检查
#     草稿必须有 status:draft, type 字段合法, 编号唯一, 不被正式页引用
# ═══════════════════════════════════════════════════════════
section "24. drafts/ 卫生检查"

DRAFT_ISSUES=0
declare -A DRAFT_IDS=()
shopt -s nullglob
for draft in "$KB_ROOT"/drafts/E*-*.md; do
  bn="$(basename "$draft")"
  # Check status: draft
  d_status="$(awk '/^---/{fm++;next} fm==1 && /^status:/{sub(/^status:[[:space:]]*/,"");print;exit}' "$draft")"
  if [ "$d_status" != "draft" ]; then
    fail "草稿 $bn status 不是 draft (found: '$d_status')"; DRAFT_ISSUES=$((DRAFT_ISSUES+1))
  fi
  # Check type field
  d_type="$(awk '/^---/{fm++;next} fm==1 && /^type:/{sub(/^type:[[:space:]]*/,"");print;exit}' "$draft")"
  case "$d_type" in
    semantic|procedural|episodic|problem|preference) :;;
    *) fail "草稿 $bn type 不合法: '$d_type' (须为 semantic|procedural|episodic|problem|preference)"; DRAFT_ISSUES=$((DRAFT_ISSUES+1));;
  esac
  # Check id uniqueness
  d_id="$(awk '/^---/{fm++;next} fm==1 && /^id:/{sub(/^id:[[:space:]]*/,"");print;exit}' "$draft")"
  if [ -n "$d_id" ]; then
    if [ -n "${DRAFT_IDS[$d_id]:-}" ]; then
      fail "草稿 id 重复: '$d_id' in $bn and ${DRAFT_IDS[$d_id]}"; DRAFT_ISSUES=$((DRAFT_ISSUES+1))
    fi
    DRAFT_IDS["$d_id"]="$bn"
    # Check: formal pages must not ref draft ids
    while IFS=$'\x1f' read -r file has_fm type id status updated created has_ad has_ar has_sb audience tags refs rprob has_summary has_domain has_severity has_errmsg; do
      [ "$has_fm" = "1" ] || continue
      [ -n "$refs" ] || continue
      if echo ",$refs," | grep -q ",$d_id,"; then
        fail "正式页 refs 引用草稿 id '$d_id': ${file#$KB_ROOT/}"; DRAFT_ISSUES=$((DRAFT_ISSUES+1))
      fi
    done < "$SCAN_FM"
  fi
done
[ "$DRAFT_ISSUES" -eq 0 ] && pass "drafts/ 卫生良好（status/type/id 合法，无正式页引用草稿）"

# ═══════════════════════════════════════════════════════════
# 25. 机器维护文件不应被手动编辑
#     _index/ 文件由 kb-regen-indexes.sh 生成；如果 git diff 显示
#     手动修改（非 regen 产出），提醒重新运行 regen
# ═══════════════════════════════════════════════════════════
section "25. 索引文件由 regen 管理（幂等检查）"

INDEX_ISSUES=0
if command -v git >/dev/null 2>&1 && [ -d "$KB_ROOT/.git" ]; then
  # 保存当前索引状态，运行 regen，对比
  INDEX_TMP="$(mktemp -d)"
  for idx in "$KB_ROOT"/_index/*.md; do
    [ -f "$idx" ] && cp "$idx" "$INDEX_TMP/$(basename "$idx")"
  done
  # 运行 regen
  bash "$KB_ROOT/_scripts/kb-regen-indexes.sh" >/dev/null 2>&1 || true
  # 对比
  for idx in "$KB_ROOT"/_index/*.md; do
    bn="$(basename "$idx")"
    if [ -f "$INDEX_TMP/$bn" ] && ! cmp -s "$idx" "$INDEX_TMP/$bn"; then
      # regen 改变了文件 → 提交前需要重新 regen
      cp "$INDEX_TMP/$bn" "$idx"  # 恢复原状
      warn "索引 $bn 与 regen 输出不一致 — 请运行 bash _scripts/kb-regen-indexes.sh"
      INDEX_ISSUES=$((INDEX_ISSUES+1))
    fi
  done
  # 恢复所有索引到 pre-regen 状态
  for idx in "$INDEX_TMP"/*.md; do
    [ -f "$idx" ] && cp "$idx" "$KB_ROOT/_index/$(basename "$idx")"
  done
  rm -rf "$INDEX_TMP"
fi
[ "$INDEX_ISSUES" -eq 0 ] && pass "索引文件与 regen 输出一致"

# ═══════════════════════════════════════════════════════════
# 汇总
# ═══════════════════════════════════════════════════════════
echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
_ts_flush; _ts_report
fail_sections=${#SECTION_FAIL[@]}
pass_sections=$((SECTION_COUNT - fail_sections))
echo "  检查完成: $SECTION_COUNT 项"
echo -e "  ${GREEN}通过${NC}: $pass_sections / $SECTION_COUNT"
[ "$ERRORS" -gt 0 ]   && echo -e "  ${RED}失败${NC}: $ERRORS"
[ "$WARNINGS" -gt 0 ] && echo -e "  ${YELLOW}警告${NC}: $WARNINGS"

if [ "$ERRORS" -eq 0 ] && [ "$WARNINGS" -eq 0 ]; then
  echo -e "\n  ${GREEN}🎉 所有检查通过！知识库一致性良好。${NC}"
  exit 0
elif [ "$ERRORS" -eq 0 ]; then
  echo -e "\n  ${YELLOW}⚠️  无严重问题，但有 $WARNINGS 个警告需要关注。${NC}"
  exit 0
else
  echo -e "\n  ${RED}❌ 发现 $ERRORS 个问题需要修复。${NC}"
  exit 1
fi
