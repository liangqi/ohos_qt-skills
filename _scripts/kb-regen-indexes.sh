#!/bin/bash
# ═══════════════════════════════════════════════════════════
# kb-regen-indexes.sh — 派生索引生成器（canonical trunk）
#
# 从各内容页 frontmatter 重建派生索引：
#   _index/_map.md / _index/_tags.md / problems/_lookup.md /
#   各域 _index.md / _index/_dashboard.md（派生计数部分）
# 在 trunk 中索引 committed（fresh clone 即可用）；
# 每次编辑页面后须运行本脚本重建，bot 也会自动检查漂移。
#
# 幂等：write_if_changed 比对 body(去掉 ^updated: 行)，内容未变则不写(保留旧 updated)。
# reused_by 不反算（丢弃，见 ADR-003）；AI 按需 `grep -rl '<id>'` 反查 refs。
#
# 用法:
#   bash _scripts/kb-regen-indexes.sh            # 全量生成
#   bash _scripts/kb-regen-indexes.sh /out/dir  # 指定 OUT(测试)
#
# 退出码: 0=成功
# ═══════════════════════════════════════════════════════════
set -uo pipefail
shopt -s nullglob

# UTF-8 locale 兜底（bash ${var:0:N} 与 awk substr 按字符切，避免字节切片截断 CJK）
for _loc in C.utf8 C.UTF-8 en_US.utf8 en_US.UTF-8; do
  if locale -a 2>/dev/null | grep -qiE "^${_loc}$"; then export LC_ALL="$_loc"; break; fi
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KB_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TODAY="$(date +%F)"
OUT="${1:-$KB_ROOT}"

if [ -t 1 ]; then
  C_GREEN='\033[0;32m'; C_YELLOW='\033[1;33m'; C_RED='\033[0;31m'; C_CYAN='\033[0;36m'; C_NC='\033[0m'
else
  C_GREEN=''; C_YELLOW=''; C_RED=''; C_CYAN=''; C_NC=''
fi
ok()   { echo -e "  ${C_GREEN}✓${C_NC} $1"; }
warn() { echo -e "  ${C_YELLOW}⚠${C_NC} WARN: $1" >&2; }
err()  { echo -e "  ${C_RED}✗${C_NC} $1" >&2; }
log()  { echo -e "${C_CYAN}━━━ $1 ━━━${C_NC}"; }

# ═══════════════════════════════════════════════════════════
# frontmatter 解析器（复用自 kb-dev-edition.sh + 门禁 BOM strip）
# BOM strip：\357\273\277 = UTF-8 BOM，破坏 awk /^---/ 检测，须先 sub 掉
# ═══════════════════════════════════════════════════════════
extract_fm() {  # $1=file → stdout frontmatter 文本（已去 BOM）
  awk '{sub(/^\357\273\277/,"")} /^---[[:space:]]*$/{fm++; if(fm==2)exit; next} fm==1{print}' "$1"
}
extract_field() {  # $1=字段名, $2=file → 单行值（兼容 flow / 折叠 > | / block 续行）
  awk -v fld="$1" '
    BEGIN { in_fm=0; capturing=0; val=""; folding=0; printed=0 }
    /^---[[:space:]]*$/ { if (in_fm==0) { in_fm=1; next } if (capturing && !printed) { print val; printed=1 } exit }
    in_fm==0 { next }
    { sub(/\r$/,""); sub(/^\357\273\277/,"")
      if (capturing==0 && $0 ~ "^" fld ":") {
        capturing=1; folding=0; v=$0; sub("^" fld ":[[:space:]]*", "", v); gsub(/^"/, "", v); gsub(/"$/, "", v)
        if (v == ">" || v == "|" || v == ">-" || v == "|-") { val=""; folding=1; next }
        val=v; next
      }
      if (capturing==1 && !printed) {
        if (folding==1 && $0 ~ /^[[:space:]]+/) { line=$0; sub(/^[[:space:]]+/, "", line); val=(val==""?line:val" "line); next }
        print val; printed=1; exit
      }
    }
    END { if (capturing==1 && folding==1 && !printed) print val }
  ' "$2"
}
get_summary() {  # summary > symptoms > error_message 三级回退
  local s
  s=$(extract_field summary "$1"); [ -n "$s" ] && { printf '%s\n' "$s"; return; }
  s=$(extract_field symptoms "$1"); [ -n "$s" ] && { printf '%s\n' "$s"; return; }
  s=$(extract_field error_message "$1"); [ -n "$s" ] && { printf '%s\n' "$s"; return; }
  printf '%s\n' "(无摘要)"
}
get_status() { awk -F': *' '{sub(/^\357\273\277/,"")} /^status:/{print $2; exit}' "$1" | tr -d '\r'; }

# ═══════════════════════════════════════════════════════════
# 幂等写入（内容未变 → 保留旧 updated，不写）
# ═══════════════════════════════════════════════════════════
write_if_changed() {  # $1=target path, $2=tmp content path
  local target="$1" tmp="$2"
  if [ -f "$target" ]; then
    local old_body new_body
    old_body=$(grep -v '^updated:' "$target" 2>/dev/null || true)
    new_body=$(grep -v '^updated:' "$tmp" 2>/dev/null || true)
    if [ "$old_body" = "$new_body" ]; then
      return 0  # 幂等：body 未变，保留旧文件（含旧 updated）
    fi
  fi
  mkdir -p "$(dirname "$target")"
  cp "$tmp" "$target"
}

# ═══════════════════════════════════════════════════════════
# 页面发现（源端全量，不分 audience）
# ═══════════════════════════════════════════════════════════
declare -a ALL_PAGES=()
discover_all_pages() {
  ALL_PAGES=()
  local f
  while IFS= read -r f; do
    f="${f#$KB_ROOT/}"; f="${f//\\//}"
    ALL_PAGES+=("$f")
  done < <(find "$KB_ROOT" -type f -name "*.md" \
    -not -path "*/.git/*" -not -path "*/_templates/*" \
    -not -path "*/.obsidian/*" -not -path "*/.claude/*" \
    -not -path "*/.hvigor/*" -not -path "*/.sisyphus/*" \
    -not -path "*/.omo/*" -not -path "*/build/*" \
    -not -path "*/oh_modules/*" -not -path "*/outputs/*" \
    -not -path "*/demos/*" -not -path "*/tools/*" \
    -not -path "*/screenshot/*" -not -path "*/_temp/*" \
    -not -path "*/raw/*" -not -path "*/dist/*" \
    -not -path "*/solutions/*" -not -path "*/workspace/*" \
    -not -path "*/team/*" -not -path "*/.playwright-mcp/*" \
    -not -path "*/ohos-common-kb-public/*" -not -path "*/skills/*" \
    -not -name "_*" \
    | sort)
}

# ═══════════════════════════════════════════════════════════
# problem 辅助（severity emoji + domain 中文标题）
# ═══════════════════════════════════════════════════════════
sev_of() { case "$1" in critical) printf '🔴';; high) printf '🟠';; medium) printf '🟡';; low) printf '🟢';; solved) printf '✅';; *) printf '⬜';; esac; }
dom_title() { case "$1" in build) printf '编译构建';; runtime) printf '运行时';; deploy) printf '部署安装';; sign) printf '签名';; upstream) printf '上游缺陷';; antipattern) printf '反模式/Caveat';; *) printf '%s' "$1";; esac; }

# ═══════════════════════════════════════════════════════════
# 计数器（参数化 out + pages_name）
# ═══════════════════════════════════════════════════════════
problems_count() { find "$1/problems" -maxdepth 1 -name "*.md" -not -name "_*" 2>/dev/null | wc -l | tr -d ' '; }
domain_active_count() {  # $1=out $2=pages_name $3=domain
  local out="$1"; local -n _dac_pages="$2"; local d="$3"; local n=0 f
  for f in "${_dac_pages[@]}"; do [[ "$f" == "$d"/* ]] || continue; [ "$(get_status "$out/$f")" = "active" ] && n=$((n+1)); done
  printf '%s' "$n"
}
count_archived() {  # $1=out $2=pages_name
  local out="$1"; local -n _ca_pages="$2"; local n=0 f
  for f in "${_ca_pages[@]}"; do [ "$(get_status "$out/$f")" = "archived" ] && n=$((n+1)); done
  printf '%s' "$n"
}

# ═══════════════════════════════════════════════════════════
# regen_map（参数化 out + pages_name）
# ═══════════════════════════════════════════════════════════
regen_map() {  # $1=out $2=pages_name
  local out="$1"; local -n pages="$2"
  local tmp; tmp=$(mktemp)
  local d f slug rel sum status n total=0
  {
    for d in semantic procedural episodic preference; do
      printf '\n## %s\n\n' "$d"; n=0
      for f in "${pages[@]}"; do
        [[ "$f" == "$d"/* ]] || continue
        status=$(get_status "$out/$f"); [ "$status" = "active" ] || continue
        slug=$(basename "$f" .md); rel="../$f"; sum=$(get_summary "$out/$f")
        printf '%s\n' "- [$slug]($rel) — $sum"; n=$((n+1)); total=$((total+1))
      done
      [ "$n" -eq 0 ] && printf '%s\n' "_（本域无活跃页）_"
    done
    printf '\n## problems\n\n'
    printf '%s\n' "- [_lookup](../problems/_lookup.md) — 错误速查表（$(problems_count "$out") 条）"
    total=$((total+1))
    printf -- '\n\n---\n\n## 快速查找指南\n\n| 我想知道... | 去看哪类知识 |\n|------------|------------|\n| 某个技术/概念是什么 | semantic |\n| 某件事怎么操作 | procedural |\n| 某个项目经验 | episodic |\n| 遇到某个错误怎么办 | problems → _lookup.md |\n| Qt 鸿蒙化的某个方面 | semantic → qt-harmonyos-* |\n| 某个 Qt 模块是否在鸿蒙支持 | semantic → qt-harmonyos-modules |\n| 鸿蒙平台有什么限制 | semantic → qt-harmonyos-platform-limits |\n| 分析 Qt 应用 bug / 定位问题 | procedural → framework-issue-analysis |\n| 验证修复是否生效 | procedural → framework-fix-verification |\n| 把 Qt 应用迁移到鸿蒙 | procedural → qt-app-harmonyos-migration |\n| 创建独立 demo / 测试工程 | procedural → demo-generation |\n'
  } > "$tmp"
  local body; body=$(cat "$tmp")
  { printf -- '---\nupdated: %s\ntotal_pages: %s\ndescription: >\n  知识地图（从 frontmatter summary 自动生成）。按 summary 判断相关性；沿 refs 追深度上下文。\n---\n\n# 知识地图\n\n> 按 summary 判断相关性；沿 refs 追深度上下文。\n' "$TODAY" "$total"
    printf '%s\n' "$body"
  } > "$tmp"
  write_if_changed "$out/_index/_map.md" "$tmp"
  rm -f "$tmp"
}

# ═══════════════════════════════════════════════════════════
# regen_tags（扁平全量，Q2 决策）
# ═══════════════════════════════════════════════════════════
regen_tags() {  # $1=out $2=pages_name
  local out="$1"; local -n pages="$2"
  declare -A tag_pages=()
  local f status FM t
  for f in "${pages[@]}"; do
    status=$(get_status "$out/$f"); [ "$status" = "active" ] || continue
    FM=$(extract_fm "$out/$f"); [ -z "$FM" ] && continue
    while IFS= read -r t; do [ -z "$t" ] && continue; tag_pages["$t"]+="$f "; done < <(printf '%s' "$FM" | awk '
      BEGIN { in_field=0 }
      /^tags:[[:space:]]*\[/ { line=$0; sub(/^tags:[[:space:]]*\[/,"",line); sub(/\].*$/,"",line); gsub(/[[:space:]]/,"",line); n=split(line,a,","); for(i=1;i<=n;i++) if(a[i]!="") print a[i]; next }
      /^tags:[[:space:]]*$/ { in_field=1; next }
      in_field==1 && /^[a-z_]+:/ { in_field=0; next }
      in_field==1 { if($0 ~ /^[[:space:]]*- /){line=$0; sub(/^[[:space:]]*- /,"",line); sub(/\r$/,"",line); gsub(/[[:space:]]/,"",line); if(line!="") print line} else in_field=0; next }
    ')
  done
  local tmp; tmp=$(mktemp)
  { printf -- '---\nupdated: %s\ndescription: >\n  按标签聚合（从各页 tags 自动生成，扁平全量）。\n---\n\n# 标签索引\n\n## 全部标签\n\n' "$TODAY"
    local t p slug links
    for t in $(printf '%s\n' "${!tag_pages[@]}" | LC_ALL=C sort); do
      links=""; for p in ${tag_pages[$t]}; do slug=$(basename "$p" .md); links+="[$slug](../$p), "; done; links="${links%, }"
      printf '%s\n' "- **$t**: $links"
    done
  } > "$tmp"
  write_if_changed "$out/_index/_tags.md" "$tmp"
  rm -f "$tmp"
}

# ═══════════════════════════════════════════════════════════
# regen_lookup（按领域分组 + severity emoji，B.6 net-new）
# ═══════════════════════════════════════════════════════════
regen_lookup() {  # $1=out $2=pages_name
  local out="$1"; local -n pages="$2"
  local tmp; tmp=$(mktemp)
  local f ec sev dom desc slug pcount=0
  for f in "${pages[@]}"; do [[ "$f" == problems/* ]] || continue; [[ "$(basename "$f")" == _* ]] && continue; pcount=$((pcount+1)); done
  # 收集 problem 按 domain 分组
  declare -A by_domain=()
  for f in "${pages[@]}"; do
    [[ "$f" == problems/* ]] || continue; [[ "$(basename "$f")" == _* ]] && continue
    slug=$(basename "$f" .md)
    sev=$(extract_field severity "$out/$f")
    dom=$(extract_field domain "$out/$f"); [ -z "$dom" ] && dom="未分类"
    desc=$(extract_field symptoms "$out/$f"); [ -z "$desc" ] && desc=$(extract_field error_message "$out/$f")
    by_domain["$dom"]+="${slug}|${sev}|${desc}"$'\n'
  done
  { printf -- '---\nupdated: %s\ntotal_problems: %s\ndescription: >\n  错误速查索引（从 problem 页 frontmatter 重建）。\n---\n\n# 错误速查表\n\n> 遇到执行错误时，先在此搜索 error_message / error_code。\n> Qt 平台已知限制在 semantic/qt-harmonyos-platform-limits.md。\n\n' "$TODAY" "$pcount"
    printf -- '## 按错误码速查\n\n| 错误码 | 问题文件 | 简述 |\n|--------|---------|------|\n'
    for f in "${pages[@]}"; do
      [[ "$f" == problems/* ]] || continue; [[ "$(basename "$f")" == _* ]] && continue
      ec=$(extract_field error_code "$out/$f"); [ -n "$ec" ] || continue
      slug=$(basename "$f" .md); desc=$(extract_field symptoms "$out/$f"); [ -z "$desc" ] && desc=$(extract_field error_message "$out/$f")
      printf '%s\n' "| $ec | [$slug]($slug.md) | $desc |"
    done
    printf -- '\n## 按症状速查\n\n| 症状关键字 | 问题文件 | 简述 |\n|-----------|---------|------|\n'
    for f in "${pages[@]}"; do
      [[ "$f" == problems/* ]] || continue; [[ "$(basename "$f")" == _* ]] && continue
      slug=$(basename "$f" .md); desc=$(extract_field symptoms "$out/$f"); [ -z "$desc" ] && desc=$(extract_field error_message "$out/$f")
      local d48="${desc:0:48}"
      printf '%s\n' "| \`$d48\` | [$slug]($slug.md) | $desc |"
    done
    printf -- '\n## 按领域分组\n'
    local domkey
    for domkey in $(printf '%s\n' "${!by_domain[@]}" | LC_ALL=C sort); do
      printf '\n### %s\n\n| 严重度 | 问题文件 | 简述 |\n|:------:|---------|------|\n' "$(dom_title "$domkey")"
      local line s rest sev2 dsc2
      while IFS= read -r line; do
        [ -z "$line" ] && continue
        s="${line%%|*}"; rest="${line#*|}"; sev2="${rest%%|*}"; dsc2="${rest#*|}"
        printf '%s\n' "| $(sev_of "$sev2") $sev2 | [$s]($s.md) | $dsc2 |"
      done < <(printf '%s' "${by_domain[$domkey]}")
    done
  } > "$tmp"
  write_if_changed "$out/problems/_lookup.md" "$tmp"
  rm -f "$tmp"
}

# ═══════════════════════════════════════════════════════════
# regen_domain_index（episodic 补 decisions/，暂无措辞修复）
# ═══════════════════════════════════════════════════════════
regen_domain_index() {  # $1=out $2=pages_name $3=domain
  local out="$1"; local -n pages="$2"; local d="$3"
  local desc n=0 f status slug sum rel
  case "$d" in
    semantic)   desc="语义知识域索引。技术概念、API 参考、平台限制、模块状态、构建/工程。";;
    procedural) desc="程序知识域索引。工作流、操作步骤。";;
    episodic)   desc="情景知识域索引。项目复盘、决策记录。";;
    preference) desc="偏好知识域索引。";;
    problems)   desc="实际执行错误知识库。编译/部署/运行时报错与解决方案。";;
  esac
  local tmp; tmp=$(mktemp)
  { printf -- '---\ndomain: %s\ndescription: >\n  %s\n---\n\n# %s\n\n' "$d" "$desc" "$d"
    if [ "$d" = "episodic" ]; then printf '## 子目录\n\n| 目录 | 用途 |\n|------|------|\n| postmortems/ | 踩坑与复盘 |\n| decisions/ | 架构决策记录(ADR) |\n\n'; fi
    if [ "$d" = "problems" ]; then printf '错误速查入口：[_lookup](_lookup.md)。Qt 平台已知限制在 semantic/qt-harmonyos-platform-limits.md。\n\n'
    else printf '## 本域知识页\n\n'; fi
    for f in "${pages[@]}"; do
      [[ "$f" == "$d"/* ]] || continue
      status=$(get_status "$out/$f"); [ "$status" = "active" ] || continue
      slug=$(basename "$f" .md); sum=$(get_summary "$out/$f"); rel="${f#$d/}"
      printf '%s\n' "- [$slug]($rel) — $sum"; n=$((n+1))
    done
    [ "$n" -eq 0 ] && printf '%s\n' "_（本域无活跃页）_"
  } > "$tmp"
  write_if_changed "$out/$d/_index.md" "$tmp"
  rm -f "$tmp"
}

# ═══════════════════════════════════════════════════════════
# fill_dashboard（源端精简版：计数 + 文件清单 + 覆盖率，不含审计/评分/历史）
# 审计/评分快照在 _index/_dashboard-audit.md（人工维护，入库）
# ═══════════════════════════════════════════════════════════
fill_dashboard() {  # $1=out $2=pages_name
  local out="$1"; local -n pages="$2"
  local total_active=0 archived sem proc epi pref pcount f st
  for f in "${pages[@]}"; do
    [[ "$f" == semantic/* || "$f" == procedural/* || "$f" == episodic/* || "$f" == preference/* ]] || continue
    st=$(get_status "$out/$f"); [ "$st" = "active" ] && total_active=$((total_active+1))
  done
  archived=$(count_archived "$out" "$2")
  sem=$(domain_active_count "$out" "$2" semantic)
  proc=$(domain_active_count "$out" "$2" procedural)
  epi=$(domain_active_count "$out" "$2" episodic)
  pref=$(domain_active_count "$out" "$2" preference)
  pcount=$(problems_count "$out")
  local tmp; tmp=$(mktemp)
  { printf -- '---\nupdated: %s\ntotal_pages: %s\ndescription: >\n  知识库健康仪表盘（派生计数，从 frontmatter 自动生成）。审计/评分快照见 _dashboard-audit.md。\n---\n\n# 知识库健康仪表盘\n\n> **最后更新**：%s | **总活跃页面**：%s | **归档**：%s\n\n---\n\n## 一、文件清单（派生）\n\n' "$TODAY" "$total_active" "$TODAY" "$total_active" "$archived"
    local d pg upd
    for d in semantic procedural episodic preference; do
      printf '\n### %s（%s 活跃）\n\n| 页面 | 状态 | 最后更新 |\n|------|:----:|:--------:|\n' "$d" "$(domain_active_count "$out" "$2" "$d")"
      for f in "${pages[@]}"; do
        [[ "$f" == "$d"/* ]] || continue
        st=$(get_status "$out/$f"); [ "$st" = "active" ] || continue
        pg=$(basename "$f" .md); upd=$(extract_field updated "$out/$f")
        printf '%s\n' "| \`$pg.md\` | ✅ 活跃 | $upd |"
      done
    done
    printf -- '\n### problems（%s 条目）\n\n详见 [_lookup](../problems/_lookup.md)。\n' "$pcount"
    printf -- '\n---\n\n## 二、来源覆盖率（派生）\n\n| 域 | 活跃页 | 备注 |\n|----|:------:|------|\n| semantic | %s | 见各页 frontmatter refs |\n| procedural | %s | 见各页 frontmatter refs |\n| episodic | %s | 项目经验，无外部来源 |\n| preference | %s | 个人偏好 |\n| **合计活跃** | **%s** | |\n\n' "$sem" "$proc" "$epi" "$pref" "$total_active"
    printf -- '> 审计状态、质量评分、主题覆盖矩阵、已知空白、变更历史见 [_dashboard-audit.md](_dashboard-audit.md)（人工快照，⚠️ SNAPSHOT）。\n'
  } > "$tmp"
  write_if_changed "$out/_index/_dashboard.md" "$tmp"
  rm -f "$tmp"
}

# ═══════════════════════════════════════════════════════════
# main（仅直接执行时跑；被 source 时不跑）
# ═══════════════════════════════════════════════════════════
regen_all() {  # $1=out $2=pages_name
  local out="$1"; local -n pages="$2"
  regen_map "$out" "$2"; ok "_index/_map.md"
  regen_tags "$out" "$2"; ok "_index/_tags.md"
  regen_lookup "$out" "$2"; ok "problems/_lookup.md"
  local d
  for d in semantic procedural episodic preference problems; do
    regen_domain_index "$out" "$2" "$d"; ok "$d/_index.md"
  done
  fill_dashboard "$out" "$2"; ok "_index/_dashboard.md"
}

main() {
  log "派生索引生成（OUT=${OUT}）"
  [ -z "${LC_ALL:-}" ] && warn "无 UTF-8 locale，CJK 切片可能损坏"
  discover_all_pages
  regen_all "$OUT" ALL_PAGES
  log "完成（共 ${#ALL_PAGES[@]} 页扫描）"
}

# source-guard：被 kb-dev-edition.sh source 时不跑 main
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  main
fi
