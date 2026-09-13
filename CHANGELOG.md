# Changelog

> Release history of the external knowledge base (developer edition). Version numbers follow [Semantic Versioning](https://semver.org/).
> The versioned object = the whole external repository bundle (the public Qt subset + the embedded ohos-common-kb + the kb-init skill + the root documents).
>
> - **MAJOR** — breaking: deleting/relocating a page users depend on, changing `audience` from public to internal, directory reshuffles that break old links, or an iron rule / API mapping being disproven and reversed
> - **MINOR** — content additions: a new page/section/API mapping entry/task type, or a newly embedded KB or skill
> - **PATCH** — content corrections: typos and wording fixes, updated error solutions, Qt reference version bumps
>
> The release process is documented in the internal `procedural/release-external-edition.md`. Each release's `RELEASE-MANIFEST.yaml` records the source KB's git SHA plus content_tree_sha256, so it is reproducible.

---

## v2.2.1 — 2026-08-29

- fix(procedural+semantic): fix skills self-nesting and phantom skills in the manifest

- With a persisted/reused OUT (e.g. a second build into dist/dev-edition), `copy_skills` ran `cp -r src dst`, which copies src *into* the already-existing dst → producing a doubly nested skills/skills/. Changed to `rm -rf` + copying `/.` contents to prevent nesting.
- gen-release-manifest's skills enumeration blindly collected every subdirectory, registering the self-nested skills/ as a phantom skill (the manifest showed skills: ["kb-init","skills"]). Added a SKILL.md check plus a fallback that skips self-nested directories.
- PR #9 previously cleaned up the skills/skills/ artifact in the external repository by hand; this change hardens both layers at the source so it can't recur.

## v2.2.0 — 2026-08-27

- Qt5+CEF HarmonyOS development guide + issue templates (.gitcode/ISSUE_TEMPLATE/) + xsy-letos/xsy-pyqt migration experience + versioned release mechanism (kb-publish.py, a fixed script that releases from main)

## v2.1.0 — 2026-08-25

- Updated Qt 6.12 beta3 module status (QtHarmonyExtras is a standalone module again + corrected file permission interfaces); added QCTools/xi-qt OHOS migration experience; scrubbed hard-coded Qt paths from public pages; added a versioned release mechanism (README "Capability spec" section + RELEASE-MANIFEST + CHANGELOG)

## v2.0.0 — 2026-08-19

- **MINOR** Embedded the public subset of `ohos-common-kb` (ArkTS/ArkUI/NAPI/Stage model/DevEco toolchain basics) into `ohos-common-kb-public/`
- **MINOR** Added the `skills/kb-init/` initialization skill: detect the environment → guide installation of missing dependencies → generate `ENV.local.md` → validate the environment
- **MINOR** Multi-channel Qt source acquisition (commercial license via `codereview.qt-project.org` / open-source mirror `ohos-qt/qt-harmonyos-src` / prebuilt SDK releases)
- **MINOR** Added the root documents `SETUP.md` / `CONTRIBUTING.md` / `SECURITY.md`
- **MINOR** `RELEASE-MANIFEST.yaml` records multi-source SHAs + `content_tree_sha256` + page counts (builder v2, schema v1)

> The history of the old 5-skill repository from before v2.0.0 lives under the `legacy/pre-rewrite-*` tags (snapshotted into the internal `raw/imports/ohos_qt-skills-legacy/` for future reference). v1.0.0 was never backfilled.
