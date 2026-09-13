---
id: episodic-qt-opensource-apps-harmonyos-survey
type: episodic
domain: project
tags: [qt, harmonyos, opensource, survey, porting-assessment, multi-agent-workflow]
created: 2026-06-25
updated: 2026-06-26
status: active
audience: public
refs: [semantic-qt-harmonyos-golden-rules, semantic-qt-harmonyos-platform-limits, semantic-qt-harmonyos-third-party-libs, semantic-qt-harmonyos-qt6-status, semantic-qt-harmonyos-modules]
summary: >
  On 2026-06-25, a multi-agent workflow scanned GitHub/KDE Apps/Gitee/SourceForge/Wikipedia, shortlisted 229 open-source Qt
  desktop applications, and assessed each one's HarmonyOS porting difficulty. Difficulty distribution: low 3 / medium 23 / high 126 / blocked 77; D-Bus (107),
  QtMultimedia (76), and QtWebEngine (62) are the three biggest blocking modules. The resulting list is in <INTERNAL_OUTPUT>. Captured the workflow lesson
  "large schema output fails → generate in the main loop".
---

# Survey of HarmonyOS porting difficulty for open-source Qt applications — lessons learned

## Project overview

| Field | Content |
|-------|---------|
| Date | 2026-06-25 |
| Role | Qt for HarmonyOS developer |
| Tech stack | Qt 5.12/5.15 for OHOS (the assessment baseline), a multi-agent workflow, Node.js report generation |
| Scale | Scanned 18 categories → deduplicated to 230 → confirmed 229 Qt applications, each assessed for difficulty |
| Status | Complete |
| Output | `<INTERNAL_OUTPUT>` + `.csv` (not included in the knowledge page index) |

## Background and goals

To demonstrate the knowledge base's capabilities and to shortlist adaptable open-source Qt applications for the HarmonyOS PC ecosystem, we needed to scan well-known open-source code sites for 150+ Qt desktop applications, compile a list, and assess each one's HarmonyOS porting difficulty (primarily the difficulty of porting its dependencies). Assessment fields: application category, site, Qt version, Qt modules, application value, and porting difficulty + explanation.

## Methodology (key decisions)

### Decision 1: multi-agent workflow orchestration (Discovery → Enrich → main-loop generation)
- **Background**: fetching the repository and assessing 150+ applications one by one doesn't fit in a single context, so it needed parallel orchestration.
- **Choice**: 18 category discovery agents searching in parallel (across GitHub/KDE/Gitee/SourceForge/Wikipedia) → deduplicate → one enrich agent per application (fetch the README + build files, extract the Qt version/modules/dependencies, score across 7 dimensions) → generate the report in the main loop.
- **Rationale**: a pipeline + barrier orchestration, with the difficulty assessment criteria distilled from 4 core KB pages (golden-rules/platform-limits/third-party-libs/qt6-status/modules) and injected into every enrich agent's prompt, so each assessment is grounded.
- **Result**: 248 agents, 319k tokens, producing 229 structured assessments. Quality was high — the difficulty judgments matched the KB's platform limitation knowledge (for example, JIT-based emulators are blocked by W^X/dlopen = 5).

### Decision 2: 7 assessment dimensions scored 1–5
- **Dimensions**: qt_version_fit / qt_module_availability / deps_ohos_difficulty / platform_specific_code / build_system / hardware_deps / architecture_fit
- **Primary yardstick**: Qt module availability — WebEngine/DBus/RemoteObjects/SerialBus/NFC/Gamepad are unavailable, Multimedia must be built yourself, and Qt 6 only has qtbase.

## Key findings (reusable lessons)

### HarmonyOS porting difficulty for Qt desktop applications is generally high
- **Difficulty distribution across 229 applications**: 🟢 low 3 | 🟡 medium 23 | 🟠 high 126 | 🔴 blocked 77 (**high + blocked = 89%**)
- **The three biggest blocking modules** (by application count): Qt D-Bus 107 | QtMultimedia 76 | QtWebEngine 62
- **Other unavailable modules**: X11Extras 15, AndroidExtras 6, WinExtras 6, MacExtras 5, Gamepad 2, RemoteObjects 1, SerialBus 1
- **Root cause**: Qt desktop applications generally depend on the Linux desktop ecosystem (D-Bus notifications/media keys, X11 window management, PulseAudio/ALSA audio, WebEngine-embedded web pages), none of which are available on HarmonyOS or which must be replaced with native OHOS APIs.

### Only 3 low-difficulty applications (score ≤ 2)
All are pure-Qt cross-platform UIs with few dependencies, on Qt5, using CMake, with a single window (such as DB Browser for SQLite, which only needs the SQLite chmod patch). **When choosing what to port, start from those 3 plus the 23 medium-difficulty ones.**

### Frequently recommended porting paths (patterns the enrich agents suggested repeatedly)
1. **Downgrade Qt 6 → Qt 5.15 for OHOS** (most modern Qt applications use Qt 6, while OHOS's primary target is Qt 5)
2. **Replace QtMultimedia**: cross-compile it yourself with the OHOS NDK, or switch to OHOS OHAudio/MediaPlayer
3. **Remove D-Bus**: reimplement notifications/media keys with HarmonyOS input events or AVSession
4. **Cross-compile FFmpeg**: almost every media application depends on it; verify chmod/symlink/dlopen compatibility with the OHOS NDK
5. **Rewrite the X11/Win32/Cocoa platform backend**: compositor/audio output/window management need rewriting for OHOS
6. **The SQLite chmod patch**: database applications reuse the existing KB solution

### JIT-based applications are fundamentally blocked
Emulators such as Dolphin, PCSX2, and RPCS3 depend on JIT dynamic recompilation (which needs writable + executable memory), and are constrained by HarmonyOS's W^X execution protection plus the rejection of dlopen from writable paths — an **architecture-level blocker**, not something swapping modules can solve. Falling back to an interpreter gives unusable performance.

## Pitfalls we hit

### Pitfall 1: the synthesis agent failed producing a giant JSON through the schema
- **Symptom**: asking a single agent to emit, via a StructuredOutput schema, a giant JSON containing a 150+ row markdown table + CSV + stats failed schema validation 5 times in a row (retry cap exceeded), failing the whole workflow.
- **Root cause**: the output was too long, and JSON escaping (markdown newlines/quotes/backslashes) kept breaking schema validation.
- **Fix**: drop the synthesis phase entirely so the workflow returns only the structured apps array (the discovery/enrich agent calls are unchanged → on resume they hit the cache and re-run for 0 tokens); the markdown/CSV are generated from the JSON by a Node.js script in the main loop.
- **Lesson**: **never have an agent emit large formatted text (markdown/CSV/code) through a schema**. Have agents emit small structured objects, and generate the formatted text with main-loop code. This is a key design principle for multi-agent workflows.

### Pitfall 2: the category strings returned by the enrich agents fragmented
- **Symptom**: the 18 discovery categories were canonical top-level categories, but the enrich agents improvised the category field, producing 79 fragmented categories (many containing a single application).
- **Fix**: add a category normalization mapping to the report generation script (CAT_MAP keyword matching → the 18 top-level categories), watching for keyword collisions ("editor" pulled office Markdown editors into developer tools; "data visualization" pulled science apps into databases) — resolved by adjusting CAT_MAP ordering and key assignments.
- **Lesson**: free-text fields from agents need normalization downstream; don't assume agents will strictly honor an enum.

## Reusable takeaways

- **A multi-agent survey workflow template**: discovery (fan out multi-source searches by domain) → deduplicate → enrich (fetch and assess item by item, with the difficulty criteria injected into the prompt) → generate the report in the main loop. Reusable for any "large list + per-item assessment" task.
- **Difficulty criteria should come from the KB**: distill golden-rules/platform-limits/third-party-libs/qt6-status/modules into assessment dimensions and inject them into the agent prompt for consistent, traceable assessments.
- **Resume + minimal-change fixes**: when a workflow fails, change only the failing part (drop synthesis) and leave the earlier agent calls unchanged → resume hits the cache and re-runs for 0 tokens. This is the most economical way to fix a failed workflow.
- **The report generation script**: `<INTERNAL_OUTPUT>` can serve as a reference template for a "JSON → markdown + CSV" generator.

## Related resources

- Output list: `<INTERNAL_OUTPUT>` + `.csv` (the complete assessment of 229 applications)
- Report generation script: `<INTERNAL_OUTPUT>`
- Workflow script: `.../workflows/scripts/qt-opensource-harmonyos-survey-wf_f8c299ff-12d.js`
- Sources for the assessment criteria: [[qt-harmonyos-golden-rules]], [[qt-harmonyos-platform-limits]], [[qt-harmonyos-third-party-libs]], [[qt-harmonyos-qt6-status]], [[qt-harmonyos-modules]]
