/* Qt 应用鸿蒙化可移植性图谱 - AntV G6 v5 前端逻辑 */
'use strict';

const $ = (sel) => document.querySelector(sel);

/* 状态色：苹果设计系统（System Blue/Green/Red/Orange/Gray） */
const STATUS_COLOR = {
  ported: '#34c759',
  blocked: '#ff3b30',
  unknown: '#8e8e93',
  uncertain: '#ff9500',
  app: '#007aff',
};

/* 注册 ComboCombined 布局：CDN 包导出了类但未按名称注册，
   不注册时 type: 'comboCombined' 会静默退化为随机散布（布局失效） */
if (G6.register && G6.ExtensionCategory && G6.ExtensionCategory.LAYOUT
    && G6.ComboCombinedLayout) {
  try {
    G6.register(G6.ExtensionCategory.LAYOUT, 'comboCombined',
      G6.ComboCombinedLayout);
  } catch (e) { /* 已注册时忽略 */ }
}

let graph = null;
let currentAnalysis = null;
let currentRoot = null;
let currentPayload = null;
let nodeIndex = {};
/* 用户手动展开的聚合圈（cluster id），切换应用后保留；点击聚合圈切换 */
const expandedClusters = new Set();

/* ------------------------------------------------------------- 数据 */

async function api(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch (e) { /* ignore */ }
    throw new Error(msg);
  }
  return res.json();
}

async function loadApps() {
  const apps = await api('/api/apps');
  const sel = $('#app-select');
  sel.innerHTML = '';
  apps.forEach((a) => {
    const opt = document.createElement('option');
    opt.value = a.id;
    opt.textContent = `${a.name}${a.version ? ' ' + a.version : ''}`;
    sel.appendChild(opt);
  });
  if (apps.length === 0) {
    const opt = document.createElement('option');
    opt.textContent = '（无，请先 CLI scan）';
    sel.appendChild(opt);
  }
  return apps;
}

/* ------------------------------------------------------------- 图构建 */

/* 外部依赖（非聚合成员、非 app）达到该数量时，聚合成可展开的分组框，
   避免同层依赖过多把 dagre 列拉成数千像素的细高条 */
const EXT_GROUP_THRESHOLD = 20;
const EXT_GROUP_ID = 'cluster:extdeps';

function externalGroupEnabled(payload) {
  const nodes = (payload && payload.nodes) || [];
  let count = 0;
  nodes.forEach((n) => {
    if (n.kind !== 'app' && !n.cluster_id) count += 1;
  });
  return count >= EXT_GROUP_THRESHOLD;
}

/* 节点 → 聚合框映射（含合成的外部依赖分组），供布局与避让逻辑查询 */
let nodeComboOf = {};

function nodeSize(d) {
  const kind = d.data.kind;
  if (kind === 'app') return 40;
  if (kind === 'qt-module') return 9;
  if (d.data.port_status === 'blocked') return 11;
  return 7;
}

function nodeColor(d) {
  const data = d.data;
  if (data.kind === 'app') return STATUS_COLOR.app;
  return STATUS_COLOR[data.port_status] || STATUS_COLOR.unknown;
}

function nodeLabel(d) {
  const data = d.data;
  if (data.kind === 'app' || data.port_status === 'blocked'
      || data.kind === 'qt-module') {
    return data.name;
  }
  return '';
}

function comboStats(nodes) {
  let ok = 0, bad = 0;
  nodes.forEach((n) => {
    if (n.cluster_id === 'cluster:qt' && n.kind === 'qt-module') {
      if (n.port_status === 'ported') ok += 1;
      else if (n.port_status === 'blocked') bad += 1;
    }
  });
  return { ok, bad };
}

function buildGraphData(payload) {
  const { nodes, edges, clusters } = payload;
  nodeIndex = {};
  nodes.forEach((n) => { nodeIndex[n.id] = n; });

  // 外部依赖过多时合成"外部依赖"分组框
  const extGroup = externalGroupEnabled(payload);

  // Qt 聚合默认收起（首帧即折叠态，无压缩动画），点击聚合圈后按展开状态重建
  const combos = (clusters || []).map((c) => {
    const { ok, bad } = comboStats(nodes);
    return {
      id: c.id,
      collapsed: !expandedClusters.has(c.id),
      data: { ...c, labelText: `${c.name}  ✅${ok} ❌${bad}` },
    };
  });

  if (extGroup) {
    let ok = 0, bad = 0;
    nodes.forEach((n) => {
      if (n.kind === 'app' || n.cluster_id) return;
      if (n.port_status === 'ported') ok += 1;
      else if (n.port_status === 'blocked') bad += 1;
    });
    combos.push({
      id: EXT_GROUP_ID,
      collapsed: !expandedClusters.has(EXT_GROUP_ID),
      data: {
        id: EXT_GROUP_ID, name: '外部依赖', kind: 'group',
        labelText: `外部依赖  ✅${ok} ❌${bad}`,
      },
    });
  }

  nodeComboOf = {};
  const gNodes = nodes.map((n) => {
    const combo = n.cluster_id
      || (extGroup && n.kind !== 'app' ? EXT_GROUP_ID : undefined);
    nodeComboOf[n.id] = combo;
    return { id: n.id, combo, data: n };
  });

  const seen = new Set();
  const gEdges = [];
  edges.forEach((e, i) => {
    if (!nodeIndex[e.src] || !nodeIndex[e.dst]) return;
    const id = `e${i}-${e.src}->${e.dst}`;
    if (seen.has(id)) return;
    seen.add(id);
    gEdges.push({ id, source: e.src, target: e.dst, data: e });
  });
  return { nodes: gNodes, edges: gEdges, combos };
}

/* ------------------------------------------------------------- 渲染 */

/* ------------------------------------------------------------- 布局策略 */

/* 以根节点 BFS 估算各层可见节点数；聚合成员（含外部依赖分组）整体折叠计 1 个 */
function levelWidths(payload) {
  const nodes = (payload && payload.nodes) || [];
  const edges = (payload && payload.edges) || [];
  const adj = {};
  edges.forEach((e) => {
    (adj[e.src] = adj[e.src] || []).push(e.dst);
  });
  const byId = {};
  nodes.forEach((n) => { byId[n.id] = n; });
  if (!currentRoot || !byId[currentRoot]) return [1];
  const depth = {};
  depth[currentRoot] = 0;
  const widths = [1];
  const groupSeen = {};
  const queue = [currentRoot];
  while (queue.length) {
    const id = queue.shift();
    (adj[id] || []).forEach((nxt) => {
      if (depth[nxt] !== undefined) return;
      const n = byId[nxt] || {};
      depth[nxt] = (depth[id] || 0) + 1;
      const grp = n.cluster_id || nodeComboOf[nxt];
      const counted = !grp || !groupSeen[grp];
      if (grp) groupSeen[grp] = true;
      if (counted) widths[depth[nxt]] = (widths[depth[nxt]] || 0) + 1;
      queue.push(nxt);
    });
  }
  return widths;
}

/* 自适应间距：同层依赖越多间距越小（8~20），目标布局高度约 1100，
   避免 autoFit 把整图压扁到节点无法识别 */
function dagreSep(payload) {
  const widths = levelWidths(payload);
  const maxLevel = Math.max.apply(null, widths);
  const nodesep = Math.max(8, Math.min(20,
    Math.round(1100 / Math.max(maxLevel, 1)) - 22));
  const ranksep = (widths.length - 1) >= 5 ? 80 : 120;
  return { nodesep, ranksep };
}

/* 布局用节点尺寸（比渲染尺寸略大，供布局引擎计算间距） */
function layoutNodeSize(d) {
  const data = (d && d.data) || d || {};
  if (data.kind === 'app') return 60;
  if (data.kind === 'qt-module') return 20;
  if (data.port_status === 'blocked') return 24;
  return 16;
}

/* 统计各聚合框成员数（含合成的外部依赖分组，用于计算圈内网格规模） */
function clusterCountsOf(payload) {
  const counts = {};
  const extGroup = externalGroupEnabled(payload);
  const nodes = (payload && payload.nodes) || [];
  nodes.forEach((n) => {
    if (n.cluster_id) counts[n.cluster_id] = (counts[n.cluster_id] || 0) + 1;
    else if (extGroup && n.kind !== 'app') {
      counts[EXT_GROUP_ID] = (counts[EXT_GROUP_ID] || 0) + 1;
    }
  });
  return counts;
}

function comboAware(outerOptions, clusterCounts) {
  // comboCombined：聚合圈折叠时作为单点参与外部布局，展开时成员在圈内紧凑排布；
  // 纯 dagre/circular 会给已折叠成员也分配位置，把图拉成细长条。
  // 此 G6 版本的分层配置键是 layout（函数）：null = 聚合圈外部，其余 = 对应圈内部。
  // 圈内用显式区域的 grid：按成员数计算列数与尺寸，默认区域会把圈撑到超大。
  if (!G6.ComboCombinedLayout || !G6.GridLayout) return null;
  return {
    type: 'comboCombined',
    // 预留略大于渲染框：rect 聚合框按内容 + 标签渲染，比成员包围盒大一圈，
    // padding 加大让外层布局给展开的聚合框留足间隔
    comboPadding: 60,
    layout: (comboId) => {
      if (comboId == null) return outerOptions;
      const n = (clusterCounts && clusterCounts[comboId]) || 8;
      const cols = Math.ceil(Math.sqrt(n));
      const rows = Math.ceil(n / cols);
      return {
        type: 'grid', cols,
        nodeSize: 22,
        width: cols * 38, height: rows * 38,
      };
    },
  };
}

function layoutCandidates(payload) {
  const sel = $('#layout-select');
  const pref = sel ? sel.value : 'dagre';
  const hasClusters = ((payload && payload.clusters) || []).length > 0
    || externalGroupEnabled(payload);
  const clusterCounts = clusterCountsOf(payload);
  const list = [];
  if (pref === 'dagre') {
    // 横向层级：依赖自左向右流动（app 在最左，依赖逐层向右）
    const sep = dagreSep(payload);
    if (hasClusters && G6.AntVDagreLayout) {
      const comboLayout = comboAware({
        type: 'antv-dagre', rankdir: 'LR',
        nodesep: sep.nodesep, ranksep: sep.ranksep,
        nodeSize: layoutNodeSize,
      }, clusterCounts);
      if (comboLayout) list.push(comboLayout);
    }
    list.push({ type: 'antv-dagre', rankdir: 'LR', nodesep: sep.nodesep, ranksep: sep.ranksep });
    list.push({ type: 'dagre', rankdir: 'LR', nodesep: sep.nodesep, ranksep: sep.ranksep });
  } else if (pref === 'force') {
    if (G6.ForceAtlas2) {
      const comboLayout = comboAware({
        type: 'force-atlas2',
        preventOverlap: true, kr: 0.2, kg: 2, center: [0, 0],
      }, clusterCounts);
      if (comboLayout) list.push(comboLayout);
    }
    list.push({ type: 'force', preventOverlap: true, linkDistance: 46 });
  } else if (pref === 'circular') {
    if (hasClusters && G6.CircularLayout) {
      const comboLayout = comboAware({ type: 'circular' }, clusterCounts);
      if (comboLayout) list.push(comboLayout);
    }
    list.push({ type: 'circular' });
  }
  // 兜底布局
  list.push({ type: 'force', preventOverlap: true, linkDistance: 46 });
  list.push({ type: 'circular' });
  return list;
}

async function renderGraph(payload) {
  const container = $('#graph-container');
  const data = buildGraphData(payload);
  if (graph) { graph.destroy(); graph = null; }

  const layouts = layoutCandidates(payload);
  let lastErr = null;
  for (const layout of layouts) {
    try {
      graph = new G6.Graph({
        container,
        autoFit: 'view',
        animation: false,
        padding: 30,
        data,
        layout,
        node: {
          style: {
            size: nodeSize,
            fill: nodeColor,
            stroke: (d) => (d.data.kind === 'app' ? '#0064d6'
              : d.data.port_status === 'blocked' ? '#d70015' : '#ffffff'),
            lineWidth: (d) => (d.data.kind === 'app' ? 3 : 1.5),
            labelText: nodeLabel,
            // 项目节点（app）标签更大更重，与其放大的节点匹配
            labelFontSize: (d) => (d.data.kind === 'app' ? 13 : 9),
            labelFontWeight: (d) => (d.data.kind === 'app' ? 600 : 400),
            labelFill: '#48484a',
            labelPlacement: 'bottom',
            labelOffsetY: 2,
          },
          state: {
            highlight: { stroke: '#007aff', lineWidth: 2.5,
                         labelFontWeight: 'bold', labelFill: '#1d1d1f' },
            dim: { opacity: 0.15, labelOpacity: 0.1 },
          },
        },
        edge: {
          style: {
            stroke: (d) => (d.data.type === 'uses-module' ? '#007aff' : '#aeaeb2'),
            lineWidth: 0.7,
            endArrow: true, endArrowSize: 3,
            opacity: 0.75,
            lineDash: (d) => (d.data.platform_cond ? [3, 3] : undefined),
          },
          state: {
            highlight: { stroke: '#ff9500', lineWidth: 2, opacity: 1 },
            dim: { opacity: 0.08 },
          },
        },
        combo: {
          // rect 聚合框：渲染尺寸 = 成员包围盒 + padding，与布局预留一致，
          // 圆形聚合圈会按对角线放大渲染、遮挡相邻依赖
          type: 'rect',
          style: {
            fill: 'rgba(0,122,255,0.06)',
            stroke: '#007aff', lineWidth: 1.2, lineDash: [4, 3],
            radius: 10,
            labelText: (d) => d.data.labelText || d.data.name,
            labelFill: '#0064d6', labelFontSize: 12, labelFontWeight: 'bold',
            labelPlacement: 'top', labelOffsetY: -6,
            padding: 14,
          },
          state: { dim: { opacity: 0.25 } },
        },
        behaviors: [
          'drag-canvas', 'zoom-canvas', 'drag-element',
          { type: 'hover-activate', degree: 1 },
          // 聚合圈展开/收起由 bindGraphEvents 的 combo:click 统一处理（整图按状态重建，
          // 避免 G6 展开动画把成员堆在圈心）
        ],
        plugins: [{
          type: 'tooltip',
          trigger: 'hover',
          getContent: (evt, items) => {
            const d = items[0] && items[0].data;
            if (!d) return '';
            const status = d.kind === 'app' ? '分析目标'
              : { ported: '已移植', blocked: '阻塞', unknown: '未知',
                  uncertain: '待确认' }[d.port_status] || d.port_status;
            return `<div class="tip"><b>${d.name}</b>
              <span class="tip-status">${status}</span>
              ${d.version ? `<div>版本: ${d.version}</div>` : ''}
              <div class="tip-src">${d.source || ''} · ${d.kind}</div>
              ${d.port_evidence ? `<div class="tip-ev">${d.port_evidence}</div>` : ''}
              </div>`;
          },
        }],
      });
      await graph.render();
      // 数据级 collapsed 可能不生效，渲染后主动折叠一次（animation:false 无压缩动画）；
      // 已展开的聚合框跳过。data.combos 含合成的"外部依赖"分组
      for (const c of data.combos) {
        if (expandedClusters.has(c.id)) continue;
        try { await graph.collapseElement(c.id); } catch (e) { /* ignore */ }
      }
      // 展开的聚合框渲染尺寸可能略大于布局预留，把落在框内的
      // 非成员节点沿纵向推到框外，避免不同分组的内容混在一起
      for (const c of data.combos) {
        if (!expandedClusters.has(c.id)) continue;
        let cb;
        try { cb = graph.getElementRenderBounds(c.id); } catch (e) { continue; }
        if (!cb) continue;
        const top = cb.center[1] - cb.halfExtents[1];
        const bottom = cb.center[1] + cb.halfExtents[1];
        const left = cb.center[0] - cb.halfExtents[0];
        const right = cb.center[0] + cb.halfExtents[0];
        const updates = [];
        const pushed = [];
        const others = [];
        (payload.nodes || []).forEach((n) => {
          if (nodeComboOf[n.id] === c.id) return;
          let b;
          try { b = graph.getElementRenderBounds(n.id); } catch (e) { return; }
          if (!b) return;
          const x = b.center[0];
          const y = b.center[1];
          if (x < left - 8 || x > right + 8 || y < top - 8 || y > bottom + 8) {
            others.push({ x, y });
            return;
          }
          pushed.push({ id: n.id, x, y });
        });
        if (pushed.length) {
          // 被推开的节点沿纵向排开，并避让同列已有节点位置
          const taken = (px, py) => others.some((o) =>
            Math.abs(o.x - px) < 60 && Math.abs(o.y - py) < 44);
          const topSide = pushed.filter((p) => p.y < cb.center[1])
            .sort((a, b) => b.y - a.y);
          const bottomSide = pushed.filter((p) => p.y >= cb.center[1])
            .sort((a, b) => a.y - b.y);
          let slot = top - 44;
          topSide.forEach((p) => {
            while (taken(p.x, slot)) slot -= 44;
            updates.push({ id: p.id, style: { x: p.x, y: slot } });
            others.push({ x: p.x, y: slot });
            slot -= 44;
          });
          slot = bottom + 44;
          bottomSide.forEach((p) => {
            while (taken(p.x, slot)) slot += 44;
            updates.push({ id: p.id, style: { x: p.x, y: slot } });
            others.push({ x: p.x, y: slot });
            slot += 44;
          });
          try {
            graph.updateNodeData(updates);
            await graph.draw();
          } catch (e) { /* ignore */ }
        }
      }
      try { await graph.fitView(); } catch (e) { /* ignore */ }
      return;
    } catch (err) {
      lastErr = err;
      if (graph) { try { graph.destroy(); } catch (e) { /* ignore */ } graph = null; }
    }
  }
  container.innerHTML = `<div class="error">图谱渲染失败: ${lastErr}</div>`;
}

/* ------------------------------------------------------------- 交互 */

let currentBlockers = [];
let currentRiskFilter = 'all';

function setStatus(verdict, blockers, unknowns, excluded) {
  const badge = $('#verdict-badge');
  const map = {
    portable: ['可完整鸿蒙化', 'ok'],
    blocked: ['存在阻塞点', 'bad'],
    uncertain: ['基本可行，有待确认项', 'warn'],
  };
  const [text, cls] = map[verdict] || [verdict, 'warn'];
  badge.textContent = text;
  badge.className = `badge ${cls}`;
  $('#blocker-count').textContent = blockers.length;
  $('#unknown-count').textContent = unknowns.length;
  $('#excluded-count').textContent = (excluded || []).length;

  currentBlockers = blockers;
  renderBlockers();
  const ul = $('#unknown-list');
  ul.innerHTML = '';
  unknowns.forEach((u) => ul.appendChild(blockerItem(u, 'unknown')));
  const el = $('#excluded-list');
  el.innerHTML = '';
  (excluded || []).forEach((p) => el.appendChild(excludedItem(p)));
}

function renderBlockers() {
  const bl = $('#blocker-list');
  bl.innerHTML = '';
  const filtered = currentRiskFilter === 'all'
    ? currentBlockers
    : currentBlockers.filter((b) => b.risk === currentRiskFilter);
  filtered.forEach((b) => bl.appendChild(blockerItem(b, 'blocked')));
}

function excludedItem(p) {
  const li = document.createElement('li');
  li.className = 'excluded-item';
  const alts = (p.alternatives || []).map((a) =>
    `<span class="alt-chip st-${a.ohos_status}">${a.name}</span>`
  ).join(' ');
  li.innerHTML = `<div class="b-kind">${p.iface}（${p.category || '?'}）</div>
    <div class="b-node">guard: ${p.guard}</div>
    <div class="b-reason">${p.reason}</div>
    <div class="b-alt">鸿蒙可替代: ${alts || '<span class="no-alt">无同类别替代，需自行实现</span>'}</div>`;
  return li;
}

function blockerItem(b, cls) {
  const li = document.createElement('li');
  li.className = cls;
  const path = (b.path || []).join(' → ');
  const alts = (b.alternatives || []).map((a) =>
    `<span class="alt-chip st-${a.ohos_status}">${a.name}</span>`
  ).join(' ');
  const riskLabel = { high: '高风险', medium: '中风险', low: '低风险' }[b.risk] || '';
  li.innerHTML = `<div class="b-kind">${kindLabel(b.kind)}
      ${b.risk ? `<span class="risk-chip risk-${b.risk}">${riskLabel}</span>` : ''}
    </div>
    <div class="b-node">${b.node}</div>
    <div class="b-reason">${b.reason}</div>
    ${b.guard ? `<div class="b-guard">guard: ${b.guard}</div>` : ''}
    ${alts ? `<div class="b-alt">鸿蒙可替代: ${alts}</div>` : ''}
    ${path ? `<div class="b-path">${path}</div>` : ''}`;
  li.addEventListener('click', () => highlightPath(b.path || [b.node]));
  return li;
}

function kindLabel(k) {
  return {
    'unsupported-module': '不支持的 Qt 模块',
    'unsupported-interface': '不支持的平台接口',
    'blocked-package': '阻塞的依赖包',
    'unknown-package': '未知包（无移植记录）',
    'unknown-interface': '接口支持性未确认',
    'unknown-status': '状态未知',
    'missing-node': '依赖缺失',
  }[k] || k;
}

function highlightPath(path) {
  if (!graph || !path.length) return;
  clearHighlight();
  const nodeSet = new Set(path);
  const edgeSet = new Set();
  for (let i = 0; i + 1 < path.length; i += 1) {
    edgeSet.add(`${path[i]}|${path[i + 1]}`);
  }
  const states = {};
  Object.keys(nodeIndex).forEach((id) => {
    states[id] = nodeSet.has(id) ? ['highlight'] : ['dim'];
  });
  graph.setElementState(states);
  (graph.getEdgeData() || []).forEach((e) => {
    const key = `${e.source}|${e.target}`;
    if (edgeSet.has(key)) {
      try { graph.setElementState({ [e.id]: ['highlight'] }); }
      catch (err) { /* ignore */ }
    }
  });
  const first = path[0];
  try { graph.focusElement(first, { duration: 300 }); }
  catch (err) { /* ignore */ }
}

function clearHighlight() {
  if (!graph) return;
  const states = {};
  Object.keys(nodeIndex).forEach((id) => { states[id] = []; });
  try { graph.setElementState(states); } catch (err) { /* ignore */ }
  (graph.getEdgeData() || []).forEach((e) => {
    try { graph.setElementState({ [e.id]: [] }); } catch (err) { /* ignore */ }
  });
}

/* 仅放行 http(s) 链接，避免注入 */
function safeUrl(u) {
  return (typeof u === 'string' && /^https?:\/\//i.test(u)) ? u : null;
}
function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
function linkRow(label, url, text) {
  const u = safeUrl(url);
  const body = u
    ? `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(text || u)}</a>`
    : `<code>${esc(text || url)}</code>`;
  return `<div class="kv link"><span>${esc(label)}</span><small>${body}</small></div>`;
}

/* 鸿蒙产物 + 源码链接区块；无产物时明确提示需自行移植 */
function linkRows(art) {
  if (!art) return '<div class="empty">无链接信息</div>';
  const rows = [];
  if (art.artifact_url) {
    rows.push(linkRow('鸿蒙产物', art.artifact_url, '下载 aarch64 tar.gz'));
  } else if (art.artifact_cmd) {
    rows.push(linkRow('鸿蒙产物', null, art.artifact_cmd));
  } else if (art.artifact_local) {
    rows.push(linkRow('鸿蒙产物(本地)', null, art.artifact_local));
  } else if (art.provided) {
    rows.push(`<div class="kv artifact-provided">
      <span>鸿蒙产物</span>
      <small>由 Qt / 鸿蒙框架本身提供，无需单独下载或移植</small>
    </div>`);
  } else {
    rows.push(`<div class="kv artifact-missing">
      <span>鸿蒙产物</span>
      <small>无预编译产物 → 需自行交叉编译，能否鸿蒙化由其依赖与平台接口递归判定</small>
    </div>`);
  }
  if (art.source_url) rows.push(linkRow('源码下载', art.source_url));
  if (art.repo_url) rows.push(linkRow('源码仓库', art.repo_url));
  if (art.homepage) rows.push(linkRow('项目主页', art.homepage));
  return rows.join('');
}

async function showNodeDetail(id) {
  let detail;
  try { detail = await api(`/api/node/${encodeURIComponent(id)}`); }
  catch (err) { return; }
  const n = detail.node;
  $('#detail-name').textContent = n.name;
  const statusText = { ported: '已移植', blocked: '阻塞', unknown: '未知',
    uncertain: '待确认' }[n.port_status] || n.port_status;
  const ifaceRows = detail.interfaces.map((i) => `
    <div class="kv ${i.ohos_status}">
      <span>${i.name}</span>
      <small>${i.ohos_status}${i.evidence ? ' · ' + i.evidence : ''}</small>
    </div>`).join('') || '<div class="empty">无平台接口记录</div>';
  const depRows = detail.deps.map((e) => `
    <div class="kv dep" data-id="${e.dst}">
      <span>→ ${e.target_name}</span>
      <small>${e.type}${e.platform_cond ? ' · ' + e.platform_cond : ''}
        · ${e.target_status}</small>
    </div>`).join('') || '<div class="empty">无依赖</div>';
  const depByRows = detail.dependents.map((e) => `
    <div class="kv dep" data-id="${e.src}">
      <span>← ${e.source_name}</span><small>${e.type}</small>
    </div>`).join('') || '<div class="empty">无</div>';

  $('#detail-body').innerHTML = `
    <div class="meta-chips">
      <span class="chip">${n.kind}</span>
      <span class="chip st-${n.port_status}">${statusText}</span>
      ${n.version ? `<span class="chip">v${n.version}</span>` : ''}
      <span class="chip">${n.source}</span>
    </div>
    ${n.description ? `<p class="desc">${n.description}</p>` : ''}
    ${n.port_evidence ? `<p class="evidence">移植证据: ${n.port_evidence}</p>` : ''}
    <h3>鸿蒙产物与源码链接</h3>${linkRows(detail.artifact)}
    <h3>平台接口使用（属性2）</h3>${ifaceRows}
    <h3>依赖（属性3，${detail.deps.length}）</h3>${depRows}
    <h3>被依赖（${detail.dependents.length}）</h3>${depByRows}`;
  $('#detail-panel').classList.remove('hidden');
  $('#detail-body').querySelectorAll('.dep').forEach((el) => {
    el.addEventListener('click', () => {
      const id2 = el.getAttribute('data-id');
      if (nodeIndex[id2]) {
        try { graph.focusElement(id2, { duration: 300 }); }
        catch (err) { /* ignore */ }
      }
      showNodeDetail(id2);
    });
  });
}

/* ------------------------------------------------------------- 主流程 */

async function refreshAll() {
  const appSel = $('#app-select');
  const root = appSel.value || currentRoot;
  if (!root || root.startsWith('（')) return;
  currentRoot = root;

  const [payload, analysis] = await Promise.all([
    api(`/api/graph?root=${encodeURIComponent(root)}`),
    api(`/api/analysis/${encodeURIComponent(root)}`),
  ]);
  currentAnalysis = analysis;
  currentPayload = payload;
  await renderGraph(payload);
  bindGraphEvents();
  setStatus(analysis.verdict, analysis.blockers, analysis.unknowns,
            analysis.platform_excluded);
  $('#graph-stats').textContent =
    `${payload.nodes.length} 节点 / ${payload.edges.length} 边`
    + (payload.truncated ? '（已达展示上限，图已截断）' : '');
}

function bindGraphEvents() {
  if (!graph) return;
  graph.on('node:click', (evt) => {
    const id = evt.target && evt.target.id;
    if (id) showNodeDetail(id);
  });
  graph.on('canvas:click', () => {
    $('#detail-panel').classList.add('hidden');
    clearHighlight();
  });
  // 点击聚合圈：切换展开状态并整图重建，保证两种状态下布局都正确
  // （展开时成员在圈内紧凑网格、外层按展开尺寸留位；收起时回到紧凑层级）
  graph.on('combo:click', async (evt) => {
    const id = evt.target && evt.target.id;
    if (!id || !currentPayload) return;
    if (expandedClusters.has(id)) expandedClusters.delete(id);
    else expandedClusters.add(id);
    await renderGraph(currentPayload);
    bindGraphEvents();
  });
}

async function init() {
  try {
    const apps = await loadApps();
    if (apps.length) { await refreshAll(); }
  } catch (err) {
    $('#graph-container').innerHTML =
      `<div class="error">加载失败: ${err.message}<br>
       请先运行 <code>python tools/portgraph.py ingest all</code> 并
       <code>scan</code> 一个项目</div>`;
  }

  $('#reload-btn').addEventListener('click', () => refreshAll());
  $('#app-select').addEventListener('change', () => refreshAll());
  $('#layout-select').addEventListener('change', async () => {
    if (currentPayload) {
      await renderGraph(currentPayload);
      bindGraphEvents();
    }
  });
  document.querySelectorAll('#risk-filter .filter-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#risk-filter .filter-btn')
        .forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      currentRiskFilter = btn.getAttribute('data-risk');
      renderBlockers();
    });
  });
  $('#detail-close').addEventListener('click', () => {
    $('#detail-panel').classList.add('hidden');
  });

  // ---- 添加分析（后台任务 + 进度轮询，可后台运行/随时刷新）----
  const modal = $('#clone-modal');
  let cloneJobId = null;
  let clonePollTimer = null;
  const jobRunning = () => cloneJobId && clonePollTimer;

  function paintProgress(pct, msg) {
    $('#clone-fill').style.width = pct + '%';
    $('#clone-pct').textContent = pct + '%';
    $('#clone-msg').textContent = msg || '';
    $('#job-chip-text').textContent = pct + '%';
  }
  function stopPolling() {
    if (clonePollTimer) { clearInterval(clonePollTimer); clonePollTimer = null; }
  }
  async function finishJob(job) {
    stopPolling();
    cloneJobId = null;
    $('#job-chip').classList.add('hidden');
    modal.classList.add('hidden');
    $('#clone-progress').classList.add('hidden');
    $('#clone-bg').classList.add('hidden');
    $('#clone-submit').disabled = false;
    const apps = await loadApps();
    const appId = job.result && job.result.scan && job.result.scan.app_id;
    if (appId && apps.some((a) => a.id === appId)) $('#app-select').value = appId;
    await refreshAll();
  }
  function goBackground() {
    modal.classList.add('hidden');
    if (jobRunning()) $('#job-chip').classList.remove('hidden');
  }
  function startPolling(jobId) {
    stopPolling();
    clonePollTimer = setInterval(async () => {
      let job;
      try { job = await api('/api/job/' + jobId); } catch (e) { return; }
      paintProgress(job.percent || 0, job.message || '');
      if (job.status === 'done') {
        await finishJob(job);
      } else if (job.status === 'error') {
        stopPolling(); cloneJobId = null;
        $('#clone-status').textContent = job.message || '失败';
        $('#clone-bg').classList.add('hidden');
        $('#clone-submit').disabled = false;
        $('#job-chip').classList.add('hidden');
      }
    }, 1000);
  }

  $('#add-app-btn').addEventListener('click', () => {
    $('#clone-status').textContent = '';
    if (!jobRunning()) {
      $('#clone-url').value = '';
      $('#clone-progress').classList.add('hidden');
    }
    modal.classList.remove('hidden');
    $('#clone-url').focus();
  });
  $('#clone-cancel').addEventListener('click', () => {
    if (jobRunning()) goBackground(); else modal.classList.add('hidden');
  });
  modal.addEventListener('click', (evt) => {
    if (evt.target === modal) {
      if (jobRunning()) goBackground(); else modal.classList.add('hidden');
    }
  });
  $('#clone-bg').addEventListener('click', goBackground);
  $('#job-chip').addEventListener('click', () => {
    $('#job-chip').classList.add('hidden');
    modal.classList.remove('hidden');
  });
  $('#clone-url').addEventListener('keydown', (evt) => {
    if (evt.key === 'Enter') $('#clone-submit').click();
  });
  $('#clone-submit').addEventListener('click', async () => {
    const url = $('#clone-url').value.trim();
    const status = $('#clone-status');
    if (!/^https?:\/\//.test(url)) { status.textContent = '请输入 http(s) git 地址'; return; }
    status.textContent = '';
    $('#clone-submit').disabled = true;
    try {
      const r = await api('/api/clone', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });
      cloneJobId = r.job_id;
      $('#clone-progress').classList.remove('hidden');
      $('#clone-bg').classList.remove('hidden');
      paintProgress(2, '任务已创建，正在启动…');
      startPolling(cloneJobId);
    } catch (err) {
      status.textContent = '失败: ' + err.message;
      $('#clone-submit').disabled = false;
    }
  });
  $('#search-input').addEventListener('keydown', (evt) => {
    if (evt.key !== 'Enter' || !graph) return;
    const q = evt.target.value.trim().toLowerCase();
    if (!q) return;
    const hit = Object.values(nodeIndex).find(
      (n) => n.name.toLowerCase().includes(q));
    if (hit) {
      try { graph.focusElement(hit.id, { duration: 300 }); }
      catch (err) { /* ignore */ }
      showNodeDetail(hit.id);
    }
  });
}

init();
