# Task: Regenerate page "鸿蒙化可移植性图谱" (nodeId: page-index) — Apple 设计系统下的 dev-explorer 忠实复刻（原位重生成）

Output: ./portgraph\portgraph-explorer\pages\index.html（整文件覆盖重写，in-place regeneration，不新增页面文件）

## Packet fields

- laneContract: { resolvedLane: "library_bound", packetType: "LibraryBoundPagePacket", pageRuntimeGuide: "~/.trae-cn\builtin\design\default\skills\solo-design\intent-workflows\intent-page-library-bound\library-bound-page-runtime.md", dispatchContract: "~/.trae-cn\builtin\design\default\skills\solo-design\intent-workflows\intent-page-library-bound\dispatch-contract.md" }
- nodeId: page-index
- htmlSrc: pages/index.html
- title: 鸿蒙化可移植性图谱
- deviceType: desktop
- viewportMode: app-shell
- cssPath: ./portgraph\portgraph-explorer\colors_and_type.css
- brandPrefix: brand（仅指库内品牌色阶 --brand-50..900 的前缀；语义 token 一律无前缀命名，如 --background/--primary/--border，严禁虚构 --brand-<semantic> 之类别名）
- fillHtmlHeadCommand: 不使用。本任务是编辑/重生成任务：保留现有 head 基础设施，禁止运行 apply-html-head-contract.mjs
- assets: 图标经 css-mask 引用 ../assets/icons/dl_builtin_apple/{name}.svg（可用名见质量门第 7 条）
- domIdsRequired: []（本轮无交互接线需求）
- allowedWritePaths: ["pages/index.html"]
- forbiddenWriteRoots: ["*.design", "runtime-orchestration-summary.json", "validation-report.json", "finish-readiness-report.json", "portgraph-explorer.design", "runtime-dispatch-manifest.json"]
- pageType: information-dense
- qualityRisks: ["侧栏密集列表 CJK 换行", "SVG 拓扑图标签与几何不得重叠", "顶栏控件多需防挤压"]

## Tool discipline（硬性约束）

- 禁止调用 TodoWrite。完成 JSON 是唯一状态通道。
- 禁止创建辅助脚本。只写最终产物文件。
- 禁止启动预览服务器或浏览器会话。
- 禁止运行项目校验脚本（validate-design-workspace.mjs 等），主代理在校验阶段统一执行。
- 禁止写或改 .design、runtime-orchestration-summary.json、validation-report.json。
- 禁止生成图片。
- 禁止修改真实前端源码：./portgraph\web\ 下任何文件（只读参考）。
- 只允许写 allowedWritePaths 中列出的文件。
- 保留现有 data-dom-id 属性（现有页面 add-app-btn 按钮上有 data-dom-id="add-app-btn"，重写后必须保留在该按钮上）。

## 必读文件（写作前按序阅读）

1. ~/.trae-cn\builtin\design\default\skills\solo-design\intent-workflows\intent-page-library-bound\library-bound-page-runtime.md
2. ~/.trae-cn\builtin\design\default\skills\solo-design\intent-workflows\intent-page-library-bound\design-library-ingestion.md
3. ~/.trae-cn\builtin\design\default\skills\solo-design\intent-workflows\intent-page-library-bound\design-token-fidelity-rules.md
4. ~/.trae-cn\builtin\design\default\skills\solo-design\intent-workflows\intent-page-library-bound\component-conformance-rules.md
5. ~/.trae-cn\builtin\design\default\skills\solo-design\intent-workflows\intent-page-library-bound\icon-source-priority-rules.md
6. ~/.trae-cn\builtin\design\default\skills\solo-design\shared-runtime\agent-dispatch-runtime\shared-page-rendering-kernel.md
7. ~/.trae-cn\builtin\design\default\skills\solo-design\delivery-quality\page-rendering-quality-gate.md
8. 苹果设计系统：~/.trae-cn\design_libraries\dl_builtin_apple\colors_and_type.css、components\button.json、components\card.json、components\input.json、components\navigation.json、preview\component-button.html、preview\component-card.html、preview\component-input.html、preview\component-navigation.html、ui_kits\website\index.html
9. 真实前端（功能权威，只读）：./portgraph\web\index.html、./portgraph\web\app.js、./portgraph\web\style.css
10. 现有设计页 head（需原样保留）：./portgraph\portgraph-explorer\pages\index.html 的第 1-393 行（从 <!DOCTYPE html> 到 </head>；该文件总长约 1466 行，只需读 head 部分）

## 任务使命

用户原话："用这个设计系统，复刻 dev-explorer 风格页面。注意按真实画布做布局，不要出现两侧空白。不要修改前端的功能，仅改样式。"

把画布页 pages/index.html 原位重生成为真实 dev-explorer 前端（web/index.html）的忠实复刻：结构、控件集合、内容区块与真实应用一一对应，视觉完全换成苹果设计系统（浅色、System Blue 单主色、细边框、克制阴影）。三个硬性目标：

1. 全出血画布布局：设计画布为 desktop 1440x900，页面必须铺满整个视口，左右零留白、零 max-width、零居中容器。
2. 静态 CSS 优先：全部结构性布局（外壳、顶栏、图例、工作区、SVG 尺寸、侧栏、卡片网格）必须由页内静态 <style> 承载，Tailwind CDN 加载失败时布局不得塌陷（这是上一版出现两侧空白的根因）。
3. 功能零改动：控件集合与真实应用完全一致；上一版擅自发明的控件（"深度"下拉、帮助/账户图标按钮、缩放 HUD、拖拽提示文案、独立大详情抽屉）一律不得出现。

## A. Head 保留（不动）

读取现有 pages/index.html 第 1-393 行（至 </head>），在新文件中原样复用：<!DOCTYPE html>、<html lang="zh-CN" class="light">、<style id="theme-vars">（苹果库全部 token）、Tailwind CDN script、lucide script、<style type="text/tailwindcss">（@theme inline + @layer base）、<style id="semantic-token-fallback">、图标 css-mask 与 no-scrollbar 样式块。不得增删改这些 head 基础设施；不得手工加 <link rel="stylesheet">。正文末尾（</body> 前）保留最后一个元素 <script>lucide.createIcons();</script>（即使页面未用 data-lucide 图标也保留，这是 head 基础设施的一部分）。

## B. 全出血布局规范（用户核心诉求）

- html 与 body：margin 0、padding 0、height 100%、overflow hidden；body 背景 var(--background)、前景 var(--foreground)、字体 var(--font-sans)。
- 外壳（建议类名 .explorer-app，保留 data-viewport-mode="app-shell"）：width 100%、height 100vh、display flex、flex-direction column。严禁 max-width、margin auto、水平 padding。
- 结构层级：顶栏（.topbar，flex 0 0 auto，高约 52px）→ 图例条（.legend，flex 0 0 auto，高约 38px）→ 工作区（.layout，flex 1 1 auto，min-height 0，flex row）。
- 工作区左：#graph-container（flex 1 1 auto、min-width 0、position relative），内含拓扑 SVG：position absolute、inset 0、width 100%、height 100%、display block（全部用静态 CSS 类，不用 Tailwind 工具类）；viewBox="0 0 1110 800"、preserveAspectRatio="xMidYMid meet"（1110 = 1440 - 330 侧栏，800 ≈ 900 - 52 - 38，画满整格）。
- 工作区右：aside.side-panel 宽 330px（真实应用宽度）、min-width 280px、border-left 1px var(--border)、bg var(--card)、overflow-y auto、flex column。
- 响应式降级 @media (max-width: 900px)：工作区改纵向、侧栏全宽 max-height 40%（真实应用行为）。
- 所有过渡 150-180ms cubic-bezier(0.32, 0.72, 0, 1)；@media (prefers-reduced-motion: reduce) 全部近零时长。
- 自检：假设 Tailwind CDN 完全不加载，页面仍必须呈现完整外壳+顶栏+图例+铺满的图+侧栏。结构性元素不得依赖任何 Tailwind 工具类。

## C. 功能忠实清单（与 web/index.html 逐一对应；禁止增删）

顶栏 .topbar（毛玻璃：background color-mix(in srgb, var(--muted) 88%, transparent)、backdrop-filter saturate(180%) blur(20px)、border-bottom 1px var(--border)、padding 0 16px、gap 12px、align-items center）：
- 左侧品牌：28x28 圆角方块品牌标（radius 9px、radial-gradient(circle at 32% 30%, var(--brand-300), var(--primary) 58%, var(--brand-600))、微阴影）+ h1 "鸿蒙化可移植性图谱"（15px/600）+ p "Qt 应用 × HarmonyOS 依赖拓扑分析"（11px muted）。
- 右侧控件组（flex、gap 8-10px、可换行）：
  - label "目标应用" + select#app-select：选项 tdesktop 5.3.2（selected）、krdc 23.08、filelight 23.08、MuseScore 4.5
  - label "布局" + select#layout-select：横向层级（selected）、力导向、环形
  - input#search-input type=search，placeholder "搜索节点名，回车定位"
  - button#add-app-btn "添加分析"（次级样式，data-dom-id="add-app-btn"）
  - button#reload-btn "重新分析"（主样式 primary）
  - span#verdict-badge.badge "存在阻塞点"（bad 态）
- 禁止出现："深度"下拉、帮助/账户图标按钮、缩放 HUD（+/−/fit）、"拖拽平移·滚轮缩放"提示文案、主题切换——真实应用没有这些。

图例条 .legend（bg var(--card)、border-bottom 1px var(--border)、padding 0 16px、gap 14-16px、11px muted、可换行）：
- 五个状态点：目标应用 var(--primary)、已移植 var(--state-success)、阻塞 var(--state-error)、未知 var(--muted-foreground)、待确认 var(--chart-3)；点 9px 圆。
- 聚合图例：15x11 圆角矩形（radius 5px）1.5px dashed var(--primary) + 文案 "Qt 模块聚合（点击展开/收起）"。
- span#graph-stats（margin-left auto、var(--font-mono)、tabular-nums）："10 节点 / 9 边"。

侧栏（与真实 DOM 结构对应）：
- section#blocker-panel.panel（padding 14px 16px）：
  - h2 "阻塞点" + span#blocker-count.count "2"
  - div#risk-filter.filter-row：全部（active）、高风险、中风险、低风险（胶囊筛选钮）
  - ul#blocker-list：两张阻塞卡片（内容见 F 节）
  - h2 "平台排除项（不编译）" + span#excluded-count.count "3"
  - p.panel-hint："被非鸿蒙平台条件编译守卫包裹，鸿蒙构建时不参与编译；列出其功能类别的鸿蒙替代接口。"
  - ul#excluded-list.excluded：三条排除卡片
  - h2 "待确认项" + span#unknown-count.count "1"
  - ul#unknown-list.secondary：一条待确认卡片
- section#detail-panel.panel.hidden：.detail-head（h2#detail-name + button#detail-close.btn.ghost "×"）+ div#detail-body（留空）——保持 hidden（真实应用点击节点后才显示，默认态不显示）。
- .hidden { display: none !important; }

隐藏层（保留结构，默认隐藏，与真实应用一致）：
- div#clone-modal.modal.hidden > .modal-card：h2 "添加分析目标"；hint "输入 GitHub 仓库地址，后端将 shallow clone 到 workspace/ 并自动扫描分析。任务在后台运行，可随时关闭或刷新查询。"（其中 workspace/ 用 code 样式）；input#clone-url type=url placeholder "https://github.com/owner/repo"；#clone-progress（hidden）内含进度条 + meta（span#clone-pct "0%" + span#clone-msg "等待任务启动…"）；.modal-actions：button#clone-cancel "取消"、button#clone-bg（hidden）"后台运行"、button#clone-submit "克隆并分析"（primary）；p#clone-status。
- button#job-chip.job-chip.hidden（fixed 右下、胶囊、1px var(--primary) 边框、内含 .job-chip-fill 动画条 + span#job-chip-text "0%"）。

## D. 苹果设计系统样式规范

- Token 纪律：可见内容零硬编码颜色（#hex/rgb/hsl 全禁，theme-vars 内除外）；只用 colors_and_type.css 的语义 token 与实际 token 名（--background/--foreground/--card/--muted/--muted-foreground/--border/--primary/--primary-foreground/--ring/--brand-200/--brand-300/--brand-600/--state-success/--state-success-surface/--state-error/--state-error-surface/--chart-3/--text-400/--text-600/--text-700/--radius-md/--radius-lg/--shadow-sm/--shadow-md/--shadow-lg/--shadow-2xl/--font-sans/--font-mono）。SVG 内所有颜色一律走 CSS 类或 style 属性（如 class="n-success" → fill: var(--state-success)），严禁在 SVG 表现属性里写 fill="var(--...)"（表现属性不解析 CSS 变量，会渲染成黑色）。
- 控件：select 高 30px、appearance none、padding 0 26px 0 10px、12px、bg var(--card)、1px var(--border)、radius var(--radius-md)、右侧 13px chevron（css-mask 引用 ../assets/icons/dl_builtin_apple/chevron-down.svg，色 var(--muted-foreground)）；focus-visible：border var(--ring) + box-shadow 0 0 0 3px var(--brand-200)。搜索框 220px 盒式（无图标、placeholder muted）。按钮 30px 胶囊（999px）：primary = bg var(--primary)/字 var(--primary-foreground)/边框同色；secondary = bg var(--card)/1px var(--border)；hover（primary opacity .88 / secondary bg var(--muted)）、active scale(0.97)、focus-visible ring。
- 徽章/胶囊：verdict-badge 26px 胶囊 11px/500；bad 态 color var(--state-error) + border var(--state-error) + bg var(--state-error-surface)。count 徽章：10px、bg var(--muted)、muted 字、胶囊。risk-chip：high = bg var(--state-error-surface)/字 var(--state-error)；medium = bg color-mix(in srgb, var(--chart-3) 16%, var(--card))/字 var(--chart-3)。
- 卡片：bg var(--card)、1px var(--border)、左侧 3px 状态条（high→var(--state-error)、medium→var(--chart-3)、unknown→var(--muted-foreground)、excluded→var(--text-400)）、radius var(--radius-md)、padding 10px 12px；hover translateX(3px) + box-shadow var(--shadow-md)；静态卡片不加阴影。
- 弹窗：遮罩 rgba(0,0,0,0.38) + backdrop-filter blur(8px)；卡片 min(460px, 92vw)、bg var(--card)、1px var(--border)、radius var(--radius-lg)、padding 22px 24px、box-shadow var(--shadow-2xl)；输入 38px、var(--font-mono)、radius var(--radius-md)、focus 时 border var(--ring) + ring 3px var(--brand-200)；进度条轨道 6px var(--muted)、填充 var(--primary)。
- 排版：正文 var(--font-sans) 11-15px；节点名/守卫/路径/统计 var(--font-mono)；b-node 12px/600；b-reason 11px muted 行高 1.55；h2 13px/600；panel-hint 11px muted。
- alt-chip：st-supported = 字/边 var(--state-success) + bg var(--state-success-surface)；st-convertible = var(--chart-3) + color-mix 14% var(--card)；no-alt = var(--state-error) + var(--state-error-surface)。

## E. 拓扑 SVG 规范（手绘静态复刻，viewBox="0 0 1110 800"）

- 底纹：<defs> 内 22x22 dot-grid pattern（1.5px 圆点 var(--border)）铺满全图；箭头 marker（var(--border)）。
- app 节点 tdesktop：cx≈120、cy≈400、r 26、fill var(--primary)、stroke var(--brand-600) 3px；下方标签：mono 11px/600 var(--foreground) "tdesktop" + 9px muted "v5.3.2 · app"。
- Qt 聚合（展开态，真实应用点击聚合圈后的状态）：虚线圆 cx≈400、cy≈400、r≈165、stroke var(--primary) 1.4px dasharray 5 4（透明度约 .55）、fill var(--primary) 透明度 .04；圆上方标签："Qt 模块聚合"（12px/600 var(--primary)）+ "3 支持 · 1 阻塞"（10px muted，数字分别用 state-success/state-error 着色的 tspans）。
- 聚合内 4 个 Qt 模块节点（mono 9.5-10px 标签在节点下方）：qtbase（约 350,250，r 11，success）、qt5compat（约 430,330，r 11，success）、qtsvg（约 330,430，r 11，success）、qtwebengine（约 430,510，r 13，error，标签 var(--text-700)）；success 节点 fill var(--state-success)、stroke var(--card) 2px；error 节点 fill var(--state-error)。
- 外部依赖 5 个节点（右侧分布，r 10，标签同上）：zlib（约 690,150，success）、openssl@3（约 790,270，success）、ffmpeg（约 680,400，success）、libsecret（约 800,520，success）、libexif（约 880,630，fill var(--chart-3)，标签 var(--text-700)）。
- 边：tdesktop→4 个 Qt 模块（uses-module 语义）：stroke var(--primary) 1.4px、透明度 .9、带箭头；tdesktop→5 个外部依赖（runtime 语义）：stroke var(--border) 1.2px、透明度 .85、带箭头；其中 tdesktop→libsecret 一条 dasharray 4 4（platform_cond 平台条件边）。全部三次贝塞尔曲线（C 指令），从节点边缘出发到目标节点边缘，不得穿越节点本体、不得与标签重叠。
- 交互态（纯 CSS）：.gnode circle 过渡 150ms；.gnode:hover circle stroke var(--primary)、stroke-width 2.5；svg cursor grab。
- 质量要求：标签与几何零重叠、零越界；全图横向铺满 1110 宽（左缘 ≈90、右缘 ≈1000+），纵向利用 800 高；这是一张依赖拓扑图而非数据图表，不用坐标轴。

## F. 侧栏内容（真实语义数据）

阻塞点卡片 1（risk-high）：b-kind "不支持的平台接口" + risk-chip "高风险"；b-node "app:tdesktop"；b-reason "使用鸿蒙不支持的平台接口 macOS Cocoa / AppKit，4 处无条件编译命中将参与鸿蒙构建，212 处文件级命中已被平台排除。"；b-path（dashed 顶边线、mono 10px var(--primary)）"app:tdesktop → 平台接口 → macOS Cocoa / AppKit"。
阻塞点卡片 2（risk-medium）：b-kind "不支持的 Qt 模块" + risk-chip "中风险"；b-node "qt-module:qtwebengine"；b-reason "Qt WebEngine 依赖 Chromium，鸿蒙无官方移植记录，建议改用系统 WebView 能力。"；b-guard chip "guard: uses-module"；b-alt "鸿蒙可替代: " + alt-chip st-convertible "OHOS WebView"；b-path "app:tdesktop → qt-module:qtwebengine"。
平台排除项 3 条（结构：b-kind "iface（category）"、b-node "guard: …"、b-reason、b-alt chips）：
1. "X11（窗口系统）" / "guard: #ifdef Q_OS_LINUX" / "位于 platform/unix 路径，仅在 Linux/X11 构建启用，鸿蒙构建不参与编译。" / alt-chip st-supported "OHOS WindowManager"
2. "ALSA（音频）" / "guard: #ifdef Q_OS_LINUX" / "音频后端仅在 Linux 条件编译，鸿蒙走系统音频框架。" / alt-chip st-supported "OHOS AudioFramework"
3. "Win32 / GDI（窗口绘制）" / "guard: #ifdef Q_OS_WIN" / "Windows 专属实现文件，鸿蒙构建不参与编译。" / no-alt 红字 "无同类别替代，需自行实现"
待确认卡片 1：b-kind "未知包（无移植记录）"；b-node "libexif"；b-reason "Harmonybrew 与 cmd-pkgs 均无该包记录，需人工确认移植来源。"

## G. 质量门自检（写完后逐项核对再返回）

1. Token 合规：无硬编码颜色、无 Tailwind 命名色、无虚构变量名；SVG 颜色全部 CSS 类/Style。
2. 布局生产稳定性（layout-risk 页必查）：criticalLayoutCssPresent=true、runtimeOnlyTailwindDependency=false；首屏四区（顶栏/图例/图/侧栏）在无 Tailwind 下完整可见；水平溢出 none、重叠 none。
3. 硬视觉缺陷零容忍：无 emoji 图标（聚合标签用 "3 支持 · 1 阻塞" 文本，不用 ✅❌）、无零间距控件簇、无越界/重叠。
4. 语言一致：全部 UI 文案中文（技术名词 qtbase/openssl@3/guard 等保留原文）。
5. 结构完整：无 TODO/占位/截断；隐藏结构（detail-panel/clone-modal/job-chip）齐全且默认隐藏。
6. 每个可交互控件有 hover/active/focus-visible 态；reduced-motion 降级。
7. 图标来源：本页仅需 chevron-down（库图标 css-mask）；如需其他图标优先用库内 40 个 SVG（arrow-*/box/check/chevron-*/circle-*/external-link/file/folder*/funnel/grip/heart/house/mail/map-pin/message-circle-more/mouse-pointer-click/pen-line/send-horizontal/star/tag/thumbs-*/trash-2/triangle-alert/user），lucide 仅作兜底。

## Completion JSON（唯一状态通道，最终消息只返回这个 JSON）

必须包含：nodeId、page、title、qualityGate（passed/failed/blocked）、domIds（[]）、componentsRead（["button","card","input","navigation"]）、extraComponentsRead、headInfrastructureStatus（semanticTokenFallback: "inherited"）、htmlWriteMode、headManagementEvidence、toolDisciplineEvidence（todoWriteUsed=false、previewStarted=false、validationScriptsRunBySubAgent=false、helperScriptsCreated=false、imagesGeneratedBySubAgent=false、wroteOnlyAllowedPaths=true）、toolCallLedger、designIntentEvidence（visualNorthStarApplied/compositionPatternUsed/continuityAnchorsApplied/antiSlopCheck）、interactionStates、motionEvidence、visualStructureEvidence（primitiveTokenEvidence/layoutGeometryEvidence）、alignmentEvidence（各区域对齐模式）、headingCtaEvidence、sourceContextPreserved（列至少 3 个保留的源页元素及真实应用对应关系）、sharedShellPreserved（"not applicable"）、iconPolicyEvidence、animationLibrariesUsed（[]）、staticRenderingEvidence（criticalLayoutCssPresent/runtimeOnlyTailwindDependency/layoutCriticalSelectors）、viewportIntegrityEvidence（targetFrame: "desktop"、firstScreenRegionsVisible、horizontalOverflowRisk: "none"、overlapRisk: "none"）、blockedReason（null）。
