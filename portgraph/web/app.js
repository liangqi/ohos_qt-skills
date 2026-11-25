/* Qt HarmonyOS Portability Graph - AntV G6 v5 frontend logic */
'use strict';

const $ = (sel) => document.querySelector(sel);

/* Status colors: Apple design system (System Blue/Green/Red/Orange/Gray) */
const STATUS_COLOR = {
  ported: '#34c759',
  blocked: '#ff3b30',
  unknown: '#8e8e93',
  uncertain: '#ff9500',
  app: '#007aff',
};

/* Register the ComboCombined layout: the CDN bundle exports the class but does not register it by name;
   without registration, type: 'comboCombined' silently degrades to random scatter (layout broken) */
if (G6.register && G6.ExtensionCategory && G6.ExtensionCategory.LAYOUT
    && G6.ComboCombinedLayout) {
  try {
    G6.register(G6.ExtensionCategory.LAYOUT, 'comboCombined',
      G6.ComboCombinedLayout);
  } catch (e) { /* ignore if already registered */ }
}

let graph = null;
let currentAnalysis = null;
let currentRoot = null;
let currentPayload = null;
let nodeIndex = {};
/* Combos the user expanded manually (cluster id); kept across app switches; clicking a combo toggles it */
const expandedClusters = new Set();

/* ------------------------------------------------------------- Data */

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
    opt.textContent = '(none; run CLI scan first)';
    sel.appendChild(opt);
  }
  return apps;
}

/* ------------------------------------------------------------- Graph construction */

/* When external dependencies (not combo members, not the app) reach this count, group them into an expandable box,
   so too many same-layer deps do not stretch a dagre column into a thin bar thousands of pixels tall */
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

/* Node -> combo mapping (including the synthesized external-deps group), queried by layout and avoidance logic */
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

  // Synthesize an "External deps" group box when there are too many external deps
  const extGroup = externalGroupEnabled(payload);

  // Qt combos are collapsed by default (collapsed from the first frame, no shrink animation); clicking a combo rebuilds per expand state
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
        id: EXT_GROUP_ID, name: 'External deps', kind: 'group',
        labelText: `External deps  ✅${ok} ❌${bad}`,
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

/* ------------------------------------------------------------- Rendering */

/* ------------------------------------------------------------- Layout strategy */

/* BFS from the root to estimate visible nodes per layer; combo members (including the external-deps group) count as 1 when collapsed */
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

/* Adaptive spacing: the more same-layer deps, the smaller the spacing (8~20); target layout height about 1100,
   so autoFit does not squash the graph until nodes are unrecognizable */
function dagreSep(payload) {
  const widths = levelWidths(payload);
  const maxLevel = Math.max.apply(null, widths);
  const nodesep = Math.max(8, Math.min(20,
    Math.round(1100 / Math.max(maxLevel, 1)) - 22));
  const ranksep = (widths.length - 1) >= 5 ? 80 : 120;
  return { nodesep, ranksep };
}

/* Node size used for layout (slightly larger than render size, for the layout engine to compute spacing) */
function layoutNodeSize(d) {
  const data = (d && d.data) || d || {};
  if (data.kind === 'app') return 60;
  if (data.kind === 'qt-module') return 20;
  if (data.port_status === 'blocked') return 24;
  return 16;
}

/* Count members of each combo (including the synthesized external-deps group; used to size the in-combo grid) */
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
  // comboCombined: a collapsed combo takes part in the outer layout as a single point; when expanded, members are packed inside it;
  // plain dagre/circular also assigns positions to collapsed members, stretching the graph into a long thin strip.
  // In this G6 version the per-level config key is layout (a function): null = outside combos, others = inside that combo.
  // Inside combos use a grid with an explicit area: columns and size from member count; the default area blows the combo up.
  if (!G6.ComboCombinedLayout || !G6.GridLayout) return null;
  return {
    type: 'comboCombined',
    // Reserve slightly more than the rendered box: a rect combo renders content + label, a ring larger than the member bbox;
    // larger padding makes the outer layout leave enough room for expanded combos
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
    // Horizontal layers: deps flow left to right (app at far left, deps layer by layer to the right)
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
  // Fallback layout
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
            // Project node (app) label is larger and bolder, matching its enlarged node
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
          // rect combo: render size = member bbox + padding, consistent with the layout reservation;
          // circular combos render scaled by the diagonal and cover neighboring deps
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
          // Combo expand/collapse is handled centrally by combo:click in bindGraphEvents (whole graph rebuilt per state,
          // avoiding the G6 expand animation piling members in the combo center)
        ],
        plugins: [{
          type: 'tooltip',
          trigger: 'hover',
          getContent: (evt, items) => {
            const d = items[0] && items[0].data;
            if (!d) return '';
            const status = d.kind === 'app' ? 'Analysis target'
              : { ported: 'Ported', blocked: 'Blocked', unknown: 'Unknown',
                  uncertain: 'Needs confirmation' }[d.port_status] || d.port_status;
            return `<div class="tip"><b>${d.name}</b>
              <span class="tip-status">${status}</span>
              ${d.version ? `<div>Version: ${d.version}</div>` : ''}
              <div class="tip-src">${d.source || ''} · ${d.kind}</div>
              ${d.port_evidence ? `<div class="tip-ev">${d.port_evidence}</div>` : ''}
              </div>`;
          },
        }],
      });
      await graph.render();
      // Data-level collapsed may not take effect; collapse once explicitly after render (animation:false, no shrink animation);
      // skip expanded combos. data.combos includes the synthesized "External deps" group
      for (const c of data.combos) {
        if (expandedClusters.has(c.id)) continue;
        try { await graph.collapseElement(c.id); } catch (e) { /* ignore */ }
      }
      // An expanded combo may render slightly larger than its layout reservation; push
      // non-member nodes inside the box out vertically, so contents of different groups do not mix
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
          // Pushed-out nodes are spread vertically, avoiding existing nodes in the same column
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
  container.innerHTML = `<div class="error">Graph rendering failed: ${lastErr}</div>`;
}

/* ------------------------------------------------------------- Interaction */

let currentBlockers = [];
let currentRiskFilter = 'all';

function setStatus(verdict, blockers, unknowns, excluded) {
  const badge = $('#verdict-badge');
  const map = {
    portable: ['Fully portable to HarmonyOS', 'ok'],
    blocked: ['Has blockers', 'bad'],
    uncertain: ['Mostly feasible, items need confirmation', 'warn'],
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
  li.innerHTML = `<div class="b-kind">${p.iface} (${p.category || '?'})</div>
    <div class="b-node">guard: ${p.guard}</div>
    <div class="b-reason">${p.reason}</div>
    <div class="b-alt">HarmonyOS alternatives: ${alts || '<span class="no-alt">No same-category alternative; implement it yourself</span>'}</div>`;
  return li;
}

function blockerItem(b, cls) {
  const li = document.createElement('li');
  li.className = cls;
  const path = (b.path || []).join(' → ');
  const alts = (b.alternatives || []).map((a) =>
    `<span class="alt-chip st-${a.ohos_status}">${a.name}</span>`
  ).join(' ');
  const riskLabel = { high: 'High risk', medium: 'Medium risk', low: 'Low risk' }[b.risk] || '';
  li.innerHTML = `<div class="b-kind">${kindLabel(b.kind)}
      ${b.risk ? `<span class="risk-chip risk-${b.risk}">${riskLabel}</span>` : ''}
    </div>
    <div class="b-node">${b.node}</div>
    <div class="b-reason">${b.reason}</div>
    ${b.guard ? `<div class="b-guard">guard: ${b.guard}</div>` : ''}
    ${alts ? `<div class="b-alt">HarmonyOS alternatives: ${alts}</div>` : ''}
    ${path ? `<div class="b-path">${path}</div>` : ''}`;
  li.addEventListener('click', () => highlightPath(b.path || [b.node]));
  return li;
}

function kindLabel(k) {
  return {
    'unsupported-module': 'Unsupported Qt module',
    'unsupported-interface': 'Unsupported platform interface',
    'blocked-package': 'Blocked dependency package',
    'unknown-package': 'Unknown package (no porting record)',
    'unknown-interface': 'Interface support unconfirmed',
    'unknown-status': 'Status unknown',
    'missing-node': 'Missing dependency',
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

/* Allow only http(s) links, to avoid injection */
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

/* HarmonyOS artifact + source link block; when there is no artifact, state clearly that it must be ported */
function linkRows(art) {
  if (!art) return '<div class="empty">No link information</div>';
  const rows = [];
  if (art.artifact_url) {
    rows.push(linkRow('HarmonyOS artifact', art.artifact_url, 'Download aarch64 tar.gz'));
  } else if (art.artifact_cmd) {
    rows.push(linkRow('HarmonyOS artifact', null, art.artifact_cmd));
  } else if (art.artifact_local) {
    rows.push(linkRow('HarmonyOS artifact (local)', null, art.artifact_local));
  } else if (art.provided) {
    rows.push(`<div class="kv artifact-provided">
      <span>HarmonyOS artifact</span>
      <small>Provided by Qt / the HarmonyOS framework itself; no separate download or port needed</small>
    </div>`);
  } else {
    rows.push(`<div class="kv artifact-missing">
      <span>HarmonyOS artifact</span>
      <small>No prebuilt artifact -> cross-compile it yourself; portability is decided recursively by its deps and platform interfaces</small>
    </div>`);
  }
  if (art.source_url) rows.push(linkRow('Source download', art.source_url));
  if (art.repo_url) rows.push(linkRow('Source repository', art.repo_url));
  if (art.homepage) rows.push(linkRow('Project homepage', art.homepage));
  return rows.join('');
}

async function showNodeDetail(id) {
  let detail;
  try { detail = await api(`/api/node/${encodeURIComponent(id)}`); }
  catch (err) { return; }
  const n = detail.node;
  $('#detail-name').textContent = n.name;
  const statusText = { ported: 'Ported', blocked: 'Blocked', unknown: 'Unknown',
    uncertain: 'Needs confirmation' }[n.port_status] || n.port_status;
  const ifaceRows = detail.interfaces.map((i) => `
    <div class="kv ${i.ohos_status}">
      <span>${i.name}</span>
      <small>${i.ohos_status}${i.evidence ? ' · ' + i.evidence : ''}</small>
    </div>`).join('') || '<div class="empty">No platform interface records</div>';
  const depRows = detail.deps.map((e) => `
    <div class="kv dep" data-id="${e.dst}">
      <span>→ ${e.target_name}</span>
      <small>${e.type}${e.platform_cond ? ' · ' + e.platform_cond : ''}
        · ${e.target_status}</small>
    </div>`).join('') || '<div class="empty">No dependencies</div>';
  const depByRows = detail.dependents.map((e) => `
    <div class="kv dep" data-id="${e.src}">
      <span>← ${e.source_name}</span><small>${e.type}</small>
    </div>`).join('') || '<div class="empty">None</div>';

  $('#detail-body').innerHTML = `
    <div class="meta-chips">
      <span class="chip">${n.kind}</span>
      <span class="chip st-${n.port_status}">${statusText}</span>
      ${n.version ? `<span class="chip">v${n.version}</span>` : ''}
      <span class="chip">${n.source}</span>
    </div>
    ${n.description ? `<p class="desc">${n.description}</p>` : ''}
    ${n.port_evidence ? `<p class="evidence">Porting evidence: ${n.port_evidence}</p>` : ''}
    <h3>HarmonyOS artifact and source links</h3>${linkRows(detail.artifact)}
    <h3>Platform interface usage (attribute 2)</h3>${ifaceRows}
    <h3>Dependencies (attribute 3, ${detail.deps.length})</h3>${depRows}
    <h3>Dependents (${detail.dependents.length})</h3>${depByRows}`;
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

/* ------------------------------------------------------------- Main flow */

async function refreshAll() {
  const appSel = $('#app-select');
  const root = appSel.value || currentRoot;
  if (!root || root.startsWith('(')) return;
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
    `${payload.nodes.length} nodes / ${payload.edges.length} edges`
    + (payload.truncated ? ' (display limit reached; graph truncated)' : '');
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
  // Clicking a combo: toggle expand state and rebuild the whole graph, so layout is correct in both states
  // (expanded: members in a compact grid inside, outer layout reserves the expanded size; collapsed: back to compact layers)
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
      `<div class="error">Load failed: ${err.message}<br>
       Run <code>python tools/portgraph.py ingest all</code> first and
       <code>scan</code> a project</div>`;
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

  // ---- Add analysis (background job + progress polling; can run in background / refresh any time) ----
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
        $('#clone-status').textContent = job.message || 'Failed';
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
    if (!/^https?:\/\//.test(url)) { status.textContent = 'Enter an http(s) git URL'; return; }
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
      paintProgress(2, 'Job created, starting...');
      startPolling(cloneJobId);
    } catch (err) {
      status.textContent = 'Failed: ' + err.message;
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
