# Task: Regenerate page "HarmonyOS Portability Graph" (nodeId: page-index) — a faithful dev-explorer replica under the Apple design system (in-place regeneration)

Output: ./portgraph\portgraph-explorer\pages\index.html (overwrite the whole file, in-place regeneration, no new page file)

## Packet fields

- laneContract: { resolvedLane: "library_bound", packetType: "LibraryBoundPagePacket", pageRuntimeGuide: "~/.trae-cn\builtin\design\default\skills\solo-design\intent-workflows\intent-page-library-bound\library-bound-page-runtime.md", dispatchContract: "~/.trae-cn\builtin\design\default\skills\solo-design\intent-workflows\intent-page-library-bound\dispatch-contract.md" }
- nodeId: page-index
- htmlSrc: pages/index.html
- title: HarmonyOS Portability Graph
- deviceType: desktop
- viewportMode: app-shell
- cssPath: ./portgraph\portgraph-explorer\colors_and_type.css
- brandPrefix: brand (only the prefix of the library's brand color scale --brand-50..900; semantic tokens are always unprefixed, such as --background/--primary/--border; never invent aliases like --brand-<semantic>)
- fillHtmlHeadCommand: not used. This is an edit/regeneration task: keep the existing head infrastructure; running apply-html-head-contract.mjs is forbidden
- assets: icons referenced via css-mask from ../assets/icons/dl_builtin_apple/{name}.svg (available names in quality gate item 7)
- domIdsRequired: [] (no interaction wiring needed this round)
- allowedWritePaths: ["pages/index.html"]
- forbiddenWriteRoots: ["*.design", "runtime-orchestration-summary.json", "validation-report.json", "finish-readiness-report.json", "portgraph-explorer.design", "runtime-dispatch-manifest.json"]
- pageType: information-dense
- qualityRisks: ["CJK line wrapping in dense side-panel lists", "SVG topology labels must not overlap geometry", "many top-bar controls need protection against squeezing"]

## Tool discipline (hard constraints)

- Do not call TodoWrite. The completion JSON is the only status channel.
- Do not create helper scripts. Write only the final output file.
- Do not start a preview server or browser session.
- Do not run project validation scripts (validate-design-workspace.mjs, etc.); the main agent runs them all in the validation phase.
- Do not write or modify .design, runtime-orchestration-summary.json, or validation-report.json.
- Do not generate images.
- Do not modify the real front-end source: any file under ./portgraph\web\ (read-only reference).
- Only write the files listed in allowedWritePaths.
- Keep the existing data-dom-id attributes (the add-app-btn button on the existing page has data-dom-id="add-app-btn"; after the rewrite it must stay on that button).

## Required reading (read in order before writing)

1. ~/.trae-cn\builtin\design\default\skills\solo-design\intent-workflows\intent-page-library-bound\library-bound-page-runtime.md
2. ~/.trae-cn\builtin\design\default\skills\solo-design\intent-workflows\intent-page-library-bound\design-library-ingestion.md
3. ~/.trae-cn\builtin\design\default\skills\solo-design\intent-workflows\intent-page-library-bound\design-token-fidelity-rules.md
4. ~/.trae-cn\builtin\design\default\skills\solo-design\intent-workflows\intent-page-library-bound\component-conformance-rules.md
5. ~/.trae-cn\builtin\design\default\skills\solo-design\intent-workflows\intent-page-library-bound\icon-source-priority-rules.md
6. ~/.trae-cn\builtin\design\default\skills\solo-design\shared-runtime\agent-dispatch-runtime\shared-page-rendering-kernel.md
7. ~/.trae-cn\builtin\design\default\skills\solo-design\delivery-quality\page-rendering-quality-gate.md
8. The Apple design system: ~/.trae-cn\design_libraries\dl_builtin_apple\colors_and_type.css, components\button.json, components\card.json, components\input.json, components\navigation.json, preview\component-button.html, preview\component-card.html, preview\component-input.html, preview\component-navigation.html, ui_kits\website\index.html
9. The real front end (authoritative for functionality, read-only): ./portgraph\web\index.html, ./portgraph\web\app.js, ./portgraph\web\style.css
10. The existing design page head (keep verbatim): lines 1-393 of ./portgraph\portgraph-explorer\pages\index.html (from <!DOCTYPE html> to </head>; the file is about 1466 lines long, only the head needs reading)

## Mission

The user's words: "Use this design system to replicate the dev-explorer-style page. Lay it out against the real canvas, with no blank space on either side. Don't change the front end's functionality, only the styles."

Regenerate the canvas page pages/index.html in place as a faithful replica of the real dev-explorer front end (web/index.html): structure, control set, and content blocks map one-to-one onto the real app, with the visuals fully switched to the Apple design system (light, a single System Blue primary, thin borders, restrained shadows). Three hard goals:

1. Full-bleed canvas layout: the design canvas is desktop 1440x900; the page must fill the whole viewport, with zero left/right margins, zero max-width, and zero centered containers.
2. Static CSS first: all structural layout (shell, top bar, legend, workspace, SVG size, side panel, card grid) must be carried by an in-page static <style>, so the layout doesn't collapse if the Tailwind CDN fails to load (this was the root cause of the blank space on both sides in the previous version).
3. Zero functional changes: the control set matches the real app exactly; controls the previous version invented on its own (a "depth" dropdown, help/account icon buttons, a zoom HUD, drag-hint text, a standalone large detail drawer) must not appear.

## A. Keep the head (don't touch)

Read lines 1-393 of the existing pages/index.html (up to </head>) and reuse them verbatim in the new file: <!DOCTYPE html>, <html lang="en" class="light">, <style id="theme-vars"> (all Apple library tokens), the Tailwind CDN script, the lucide script, <style type="text/tailwindcss"> (@theme inline + @layer base), <style id="semantic-token-fallback">, and the icon css-mask and no-scrollbar style blocks. Do not add, remove, or modify this head infrastructure; do not hand-add <link rel="stylesheet">. At the end of the body (before </body>) keep the last element <script>lucide.createIcons();</script> (keep it even if the page uses no data-lucide icons; it is part of the head infrastructure).

## B. Full-bleed layout spec (the user's core requirement)

- html and body: margin 0, padding 0, height 100%, overflow hidden; body background var(--background), foreground var(--foreground), font var(--font-sans).
- Shell (suggested class name .explorer-app, keep data-viewport-mode="app-shell"): width 100%, height 100vh, display flex, flex-direction column. max-width, margin auto, and horizontal padding are strictly forbidden.
- Structural hierarchy: top bar (.topbar, flex 0 0 auto, about 52px tall) → legend bar (.legend, flex 0 0 auto, about 38px tall) → workspace (.layout, flex 1 1 auto, min-height 0, flex row).
- Workspace left: #graph-container (flex 1 1 auto, min-width 0, position relative), containing the topology SVG: position absolute, inset 0, width 100%, height 100%, display block (all via static CSS classes, no Tailwind utility classes); viewBox="0 0 1110 800", preserveAspectRatio="xMidYMid meet" (1110 = 1440 - 330 side panel, 800 ≈ 900 - 52 - 38, filling the whole cell).
- Workspace right: aside.side-panel width 330px (the real app's width), min-width 280px, border-left 1px var(--border), bg var(--card), overflow-y auto, flex column.
- Responsive fallback @media (max-width: 900px): the workspace goes vertical, the side panel full width with max-height 40% (real app behavior).
- All transitions 150-180ms cubic-bezier(0.32, 0.72, 0, 1); under @media (prefers-reduced-motion: reduce) all near-zero duration.
- Self-check: assuming the Tailwind CDN doesn't load at all, the page must still show the complete shell + top bar + legend + full-size graph + side panel. Structural elements must not depend on any Tailwind utility class.

## C. Functional fidelity checklist (one-to-one with web/index.html; no additions or removals)

Top bar .topbar (frosted glass: background color-mix(in srgb, var(--muted) 88%, transparent), backdrop-filter saturate(180%) blur(20px), border-bottom 1px var(--border), padding 0 16px, gap 12px, align-items center):
- Left brand: a 28x28 rounded-square brand mark (radius 9px, radial-gradient(circle at 32% 30%, var(--brand-300), var(--primary) 58%, var(--brand-600)), subtle shadow) + h1 "HarmonyOS Portability Graph" (15px/600) + p "Qt app × HarmonyOS dependency topology analysis" (11px muted).
- Right control group (flex, gap 8-10px, wrappable):
  - label "Target app" + select#app-select: options corpus-a 5.3.2 (selected), krdc 23.08, filelight 23.08, corpus-b 4.5
  - label "Layout" + select#layout-select: Horizontal hierarchy (selected), Force-directed, Circular
  - input#search-input type=search, placeholder "Search node name, Enter to locate"
  - button#add-app-btn "Add analysis" (secondary style, data-dom-id="add-app-btn")
  - button#reload-btn "Re-analyze" (primary style)
  - span#verdict-badge.badge "Has blockers" (bad state)
- Must not appear: a "depth" dropdown, help/account icon buttons, a zoom HUD (+/−/fit), "drag to pan · scroll to zoom" hint text, a theme switch — the real app has none of these.

Legend bar .legend (bg var(--card), border-bottom 1px var(--border), padding 0 16px, gap 14-16px, 11px muted, wrappable):
- Five status dots: Target app var(--primary), Ported var(--state-success), Blocked var(--state-error), Unknown var(--muted-foreground), To confirm var(--chart-3); dots are 9px circles.
- Cluster legend: a 15x11 rounded rectangle (radius 5px) with 1.5px dashed var(--primary) + the text "Qt module cluster (click to expand/collapse)".
- span#graph-stats (margin-left auto, var(--font-mono), tabular-nums): "10 nodes / 9 edges".

Side panel (matching the real DOM structure):
- section#blocker-panel.panel (padding 14px 16px):
  - h2 "Blockers" + span#blocker-count.count "2"
  - div#risk-filter.filter-row: All (active), High risk, Medium risk, Low risk (pill filter buttons)
  - ul#blocker-list: two blocker cards (content in section F)
  - h2 "Platform-excluded items (not compiled)" + span#excluded-count.count "3"
  - p.panel-hint: "Wrapped in conditional-compilation guards for non-HarmonyOS platforms, so they are not compiled in a HarmonyOS build; the HarmonyOS alternative interfaces for their functional category are listed."
  - ul#excluded-list.excluded: three exclusion cards
  - h2 "Items to confirm" + span#unknown-count.count "1"
  - ul#unknown-list.secondary: one to-confirm card
- section#detail-panel.panel.hidden: .detail-head (h2#detail-name + button#detail-close.btn.ghost "×") + div#detail-body (left empty) — keep it hidden (in the real app it only appears after clicking a node; not shown in the default state).
- .hidden { display: none !important; }

Hidden layers (keep the structure, hidden by default, consistent with the real app):
- div#clone-modal.modal.hidden > .modal-card: h2 "Add analysis target"; hint "Enter a GitHub repository URL; the backend will shallow clone it into workspace/ and scan and analyze it automatically. The job runs in the background; you can close this or refresh to check at any time." (with workspace/ in code style); input#clone-url type=url placeholder "https://github.com/owner/repo"; #clone-progress (hidden) containing a progress bar + meta (span#clone-pct "0%" + span#clone-msg "Waiting for the job to start…"); .modal-actions: button#clone-cancel "Cancel", button#clone-bg (hidden) "Run in background", button#clone-submit "Clone and analyze" (primary); p#clone-status.
- button#job-chip.job-chip.hidden (fixed bottom right, pill, 1px var(--primary) border, containing an animated .job-chip-fill bar + span#job-chip-text "0%").

## D. Apple design system style spec

- Token discipline: zero hard-coded colors in visible content (#hex/rgb/hsl all forbidden, except inside theme-vars); use only the semantic tokens and actual token names from colors_and_type.css (--background/--foreground/--card/--muted/--muted-foreground/--border/--primary/--primary-foreground/--ring/--brand-200/--brand-300/--brand-600/--state-success/--state-success-surface/--state-error/--state-error-surface/--chart-3/--text-400/--text-600/--text-700/--radius-md/--radius-lg/--shadow-sm/--shadow-md/--shadow-lg/--shadow-2xl/--font-sans/--font-mono). All colors inside the SVG go through CSS classes or style attributes (e.g. class="n-success" → fill: var(--state-success)); writing fill="var(--...)" in SVG presentation attributes is strictly forbidden (presentation attributes don't resolve CSS variables and render black).
- Controls: select 30px tall, appearance none, padding 0 26px 0 10px, 12px, bg var(--card), 1px var(--border), radius var(--radius-md), a 13px chevron on the right (css-mask referencing ../assets/icons/dl_builtin_apple/chevron-down.svg, color var(--muted-foreground)); focus-visible: border var(--ring) + box-shadow 0 0 0 3px var(--brand-200). Search box 220px boxed (no icon, muted placeholder). Buttons are 30px pills (999px): primary = bg var(--primary)/text var(--primary-foreground)/border the same color; secondary = bg var(--card)/1px var(--border); hover (primary opacity .88 / secondary bg var(--muted)), active scale(0.97), focus-visible ring.
- Badges/pills: verdict-badge 26px pill 11px/500; bad state color var(--state-error) + border var(--state-error) + bg var(--state-error-surface). count badge: 10px, bg var(--muted), muted text, pill. risk-chip: high = bg var(--state-error-surface)/text var(--state-error); medium = bg color-mix(in srgb, var(--chart-3) 16%, var(--card))/text var(--chart-3).
- Cards: bg var(--card), 1px var(--border), a 3px status bar on the left (high→var(--state-error), medium→var(--chart-3), unknown→var(--muted-foreground), excluded→var(--text-400)), radius var(--radius-md), padding 10px 12px; hover translateX(3px) + box-shadow var(--shadow-md); static cards get no shadow.
- Modal: overlay rgba(0,0,0,0.38) + backdrop-filter blur(8px); card min(460px, 92vw), bg var(--card), 1px var(--border), radius var(--radius-lg), padding 22px 24px, box-shadow var(--shadow-2xl); input 38px, var(--font-mono), radius var(--radius-md), on focus border var(--ring) + ring 3px var(--brand-200); progress bar track 6px var(--muted), fill var(--primary).
- Typography: body var(--font-sans) 11-15px; node names/guards/paths/stats var(--font-mono); b-node 12px/600; b-reason 11px muted line height 1.55; h2 13px/600; panel-hint 11px muted.
- alt-chip: st-supported = text/border var(--state-success) + bg var(--state-success-surface); st-convertible = var(--chart-3) + color-mix 14% var(--card); no-alt = var(--state-error) + var(--state-error-surface).

## E. Topology SVG spec (hand-drawn static replica, viewBox="0 0 1110 800")

- Background: a 22x22 dot-grid pattern in <defs> (1.5px dots var(--border)) covering the whole graph; an arrowhead marker (var(--border)).
- App node corpus-a: cx≈120, cy≈400, r 26, fill var(--primary), stroke var(--brand-600) 3px; label below: mono 11px/600 var(--foreground) "corpus-a" + 9px muted "v5.3.2 · app".
- Qt cluster (expanded, the state after clicking the cluster circle in the real app): dashed circle cx≈400, cy≈400, r≈165, stroke var(--primary) 1.4px dasharray 5 4 (opacity about .55), fill var(--primary) opacity .04; label above the circle: "Qt module cluster" (12px/600 var(--primary)) + "3 supported · 1 blocked" (10px muted, with the numbers in tspans colored state-success/state-error respectively).
- 4 Qt module nodes inside the cluster (mono 9.5-10px labels below the nodes): qtbase (about 350,250, r 11, success), qt5compat (about 430,330, r 11, success), qtsvg (about 330,430, r 11, success), qtwebengine (about 430,510, r 13, error, label var(--text-700)); success nodes fill var(--state-success), stroke var(--card) 2px; error nodes fill var(--state-error).
- 5 external dependency nodes (spread on the right, r 10, labels as above): zlib (about 690,150, success), openssl@3 (about 790,270, success), ffmpeg (about 680,400, success), libsecret (about 800,520, success), libexif (about 880,630, fill var(--chart-3), label var(--text-700)).
- Edges: corpus-a→4 Qt modules (uses-module semantics): stroke var(--primary) 1.4px, opacity .9, with arrowheads; corpus-a→5 external dependencies (runtime semantics): stroke var(--border) 1.2px, opacity .85, with arrowheads; of these, corpus-a→libsecret is dasharray 4 4 (platform_cond platform-conditional edge). All cubic Bézier curves (C command), from the edge of the source node to the edge of the target node, never crossing node bodies or overlapping labels.
- Interaction states (pure CSS): .gnode circle transition 150ms; .gnode:hover circle stroke var(--primary), stroke-width 2.5; svg cursor grab.
- Quality requirements: zero overlap and zero overflow between labels and geometry; the graph spans the full 1110 width horizontally (left edge ≈90, right edge ≈1000+) and uses the 800 height vertically; this is a dependency topology graph, not a data chart, so no axes.

## F. Side panel content (real semantic data)

Blocker card 1 (risk-high): b-kind "Unsupported platform interface" + risk-chip "High risk"; b-node "app:corpus-a"; b-reason "Uses the platform interface macOS Cocoa / AppKit, which HarmonyOS does not support; 4 unconditionally compiled hits will take part in the HarmonyOS build, and 212 file-level hits are already excluded by platform."; b-path (dashed top border, mono 10px var(--primary)) "app:corpus-a → platform interface → macOS Cocoa / AppKit".
Blocker card 2 (risk-medium): b-kind "Unsupported Qt module" + risk-chip "Medium risk"; b-node "qt-module:qtwebengine"; b-reason "Qt WebEngine depends on Chromium and has no official HarmonyOS port; consider using the system WebView capability instead."; b-guard chip "guard: uses-module"; b-alt "HarmonyOS alternative: " + alt-chip st-convertible "OHOS WebView"; b-path "app:corpus-a → qt-module:qtwebengine".
3 platform-excluded items (structure: b-kind "iface (category)", b-node "guard: …", b-reason, b-alt chips):
1. "X11 (window system)" / "guard: #ifdef Q_OS_LINUX" / "Under the platform/unix path, only enabled in Linux/X11 builds; not compiled in a HarmonyOS build." / alt-chip st-supported "OHOS WindowManager"
2. "ALSA (audio)" / "guard: #ifdef Q_OS_LINUX" / "The audio backend is only conditionally compiled on Linux; HarmonyOS uses the system audio framework." / alt-chip st-supported "OHOS AudioFramework"
3. "Win32 / GDI (window drawing)" / "guard: #ifdef Q_OS_WIN" / "Windows-only implementation file; not compiled in a HarmonyOS build." / no-alt red text "No alternative in the same category; implement it yourself"
To-confirm card 1: b-kind "Unknown package (no port record)"; b-node "libexif"; b-reason "Neither Harmonybrew nor cmd-pkgs has a record of this package; confirm the port source manually."

## G. Quality gate self-check (check each item after writing, before returning)

1. Token compliance: no hard-coded colors, no Tailwind named colors, no invented variable names; all SVG colors via CSS classes/style.
2. Layout production stability (mandatory for layout-risk pages): criticalLayoutCssPresent=true, runtimeOnlyTailwindDependency=false; the four first-screen regions (top bar/legend/graph/side panel) are fully visible without Tailwind; horizontal overflow none, overlap none.
3. Zero tolerance for hard visual defects: no emoji icons (the cluster label uses the text "3 supported · 1 blocked", not ✅❌), no zero-spacing control clusters, no overflow/overlap.
4. Language consistency: all UI text in English (technical terms such as qtbase/openssl@3/guard kept as-is).
5. Structural completeness: no TODO/placeholder/truncation; the hidden structures (detail-panel/clone-modal/job-chip) are all present and hidden by default.
6. Every interactive control has hover/active/focus-visible states; reduced-motion fallback.
7. Icon sources: this page only needs chevron-down (library icon via css-mask); if other icons are needed, prefer the library's 40 SVGs (arrow-*/box/check/chevron-*/circle-*/external-link/file/folder*/funnel/grip/heart/house/mail/map-pin/message-circle-more/mouse-pointer-click/pen-line/send-horizontal/star/tag/thumbs-*/trash-2/triangle-alert/user), with lucide only as a fallback.

## Completion JSON (the only status channel; the final message returns only this JSON)

Must include: nodeId, page, title, qualityGate (passed/failed/blocked), domIds ([]), componentsRead (["button","card","input","navigation"]), extraComponentsRead, headInfrastructureStatus (semanticTokenFallback: "inherited"), htmlWriteMode, headManagementEvidence, toolDisciplineEvidence (todoWriteUsed=false, previewStarted=false, validationScriptsRunBySubAgent=false, helperScriptsCreated=false, imagesGeneratedBySubAgent=false, wroteOnlyAllowedPaths=true), toolCallLedger, designIntentEvidence (visualNorthStarApplied/compositionPatternUsed/continuityAnchorsApplied/antiSlopCheck), interactionStates, motionEvidence, visualStructureEvidence (primitiveTokenEvidence/layoutGeometryEvidence), alignmentEvidence (alignment mode of each region), headingCtaEvidence, sourceContextPreserved (list at least 3 preserved source-page elements and their real-app counterparts), sharedShellPreserved ("not applicable"), iconPolicyEvidence, animationLibrariesUsed ([]), staticRenderingEvidence (criticalLayoutCssPresent/runtimeOnlyTailwindDependency/layoutCriticalSelectors), viewportIntegrityEvidence (targetFrame: "desktop", firstScreenRegionsVisible, horizontalOverflowRisk: "none", overlapRisk: "none"), blockedReason (null).
