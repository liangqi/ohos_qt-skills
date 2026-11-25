---
updated: 2026-11-18
total_pages: 48
description: >
  Knowledge base health dashboard (derived counts, generated automatically from frontmatter).
  Rebuild: python _scripts/gen-dashboard.py (never edit the numbers by hand).
---

# Knowledge base health dashboard

> **Last updated**: 2026-11-18 | **Total active pages**: 48 (semantic/procedural/episodic/preference) | **Archived**: 1

> This page is a derived view: the page lists and counts come from each page's frontmatter, the `problems/` directory, and
> `faults/_registry.md`. To change a number, change the source of truth and then run `python _scripts/gen-dashboard.py`.

---

## 1. File inventory (derived)

### semantic (25 active)

_Semantic knowledge: concepts, API mappings, module status, platform limitations_

| Page | Status | Last updated |
|------|:------:|:------------:|
| `qdrag-cancel-cross-platform.md` | ✅ Active | 2026-07-13 |
| `qt-harmonyos-accessibility.md` | ✅ Active | 2026-07-23 |
| `qt-harmonyos-api-mapping.md` | ✅ Active | 2026-08-15 |
| `qt-harmonyos-api.md` | ✅ Active | 2026-08-06 |
| `qt-harmonyos-blocking-taxonomy.md` | ✅ Active | 2026-09-08 |
| `qt-harmonyos-build-run-workflow.md` | ✅ Active | 2026-08-15 |
| `qt-harmonyos-build.md` | ✅ Active | 2026-07-03 |
| `qt-harmonyos-code-patterns.md` | ✅ Active | 2026-08-14 |
| `qt-harmonyos-golden-rules.md` | ✅ Active | 2026-08-14 |
| `qt-harmonyos-lifecycle.md` | ✅ Active | 2026-08-14 |
| `qt-harmonyos-modules.md` | ✅ Active | 2026-11-04 |
| `qt-harmonyos-overview.md` | ✅ Active | 2026-08-14 |
| `qt-harmonyos-platform-limits.md` | ✅ Active | 2026-08-15 |
| `qt-harmonyos-porting-workflow.md` | ✅ Active | 2026-08-14 |
| `qt-harmonyos-project-structure.md` | ✅ Active | 2026-08-14 |
| `qt-harmonyos-pyqt-status.md` | ✅ Active | 2026-08-26 |
| `qt-harmonyos-qt6-status.md` | ✅ Active | 2026-09-09 |
| `qt-harmonyos-system-tray.md` | ✅ Active | 2026-07-23 |
| `qt-harmonyos-third-party-libs.md` | ✅ Active | 2026-08-15 |
| `qt-harmonyos-window-model.md` | ✅ Active | 2026-08-14 |
| `qt-ohos-extras-examples.md` | ✅ Active | 2026-07-21 |
| `qt-ohos-extras.md` | ✅ Active | 2026-07-21 |
| `qt-ohos-js-thread-gateway.md` | ✅ Active | 2026-07-27 |
| `qt-ohos-project-analyzer-workflow.md` | ✅ Active | 2026-07-02 |
| `qt515-vs-qt512-api-diff.md` | ✅ Active | 2026-06-13 |

### procedural (15 active)

_Procedural knowledge: migration, troubleshooting, builds, releases, demos_

| Page | Status | Last updated |
|------|:------:|:------------:|
| `demo-generation.md` | ✅ Active | 2026-07-23 |
| `fetch-ohos-third-party-lib.md` | ✅ Active | 2026-07-07 |
| `framework-fix-verification.md` | ✅ Active | 2026-06-05 |
| `framework-issue-analysis.md` | ✅ Active | 2026-08-14 |
| `knowledge-sedimentation.md` | ✅ Active | 2026-09-07 |
| `llvm-ohos-cross-compile.md` | ✅ Active | 2026-08-14 |
| `qt-app-harmonyos-completion.md` | ✅ Active | 2026-08-12 |
| `qt-app-harmonyos-full-pipeline.md` | ✅ Active | 2026-08-15 |
| `qt-app-harmonyos-migration.md` | ✅ Active | 2026-09-12 |
| `qt-bug-report-generation.md` | ✅ Active | 2026-08-12 |
| `qt-bug-report-sample.md` | ✅ Active | 2026-08-01 |
| `qt-cef-ohos-dev-guide.md` | ✅ Active | 2026-08-26 |
| `qt-ohos-run-test.md` | ✅ Active | 2026-09-29 |
| `qt6-ohos-manual-deploy.md` | ✅ Active | 2026-08-06 |
| `qt6-ohos-windows-cli-deploy.md` | ✅ Active | 2026-08-01 |

### episodic (8 active)

_Episodic knowledge: retrospectives from real projects_

| Page | Status | Last updated |
|------|:------:|:------------:|
| `coin3d-quarter-ohos.md` | ✅ Active | 2026-06-08 |
| `ohostemplate-blockedbymodal-patch.md` | ✅ Active | 2026-08-06 |
| `qt-opensource-apps-harmonyos-survey.md` | ✅ Active | 2026-06-26 |
| `quit-deadlock-tsfn.md` | ✅ Active | 2026-07-13 |
| `saribbon-ohos.md` | ✅ Active | 2026-06-26 |
| `tdesktop-harmonyos-porting.md` | ✅ Active | 2026-09-12 |
| `toolwindow-crossscreen-flicker.md` | ✅ Active | 2026-06-05 |
| `wa-nativewindow-leave-bug.md` | ✅ Active | 2026-06-09 |

### preference (0 active)

_Personal preferences_

_(No active pages in this domain)_

### Archived (1)

> Archived pages are still readable and their links still work; they just no longer count as active pages. After review or revision they can move back to their domain.

| Domain | Page | Last updated |
|--------|------|:------------:|
| semantic | `qt-harmonyos-dev-guide.md` | 2026-06-02 |

### problems (59 entries)

See [_lookup](../problems/_lookup.md) — the single search entry point for the error knowledge base (along three dimensions: error code / symptom / domain).

### faults (61 records: 17 symptoms S + 18 root causes C + 15 workarounds W + 11 tracking tickets T)

See [_registry](../faults/_registry.md) (the symptom index as the main entry point + classification by disposition) and [_graph.yaml](../faults/_graph.yaml) (the machine-readable full graph). The source of truth is `_data/*.yaml` + the C pages; the derived artifacts are rebuilt by `tools/faults-build.py build`.

---

## 2. Source coverage (derived)

| Domain | Active pages | Notes |
|--------|:------------:|-------|
| semantic | 25 | See the frontmatter refs on each page |
| procedural | 15 | See the frontmatter refs on each page |
| episodic | 8 | Project experience; no external sources |
| preference | 0 | Personal preferences |
| faults | 61 | The issue tracking graph (17 symptoms + 18 root causes + 15 workarounds + 11 tracking tickets) |
| **Total active** | **48** | Excludes problems and the embedded platform library (counted separately) |

