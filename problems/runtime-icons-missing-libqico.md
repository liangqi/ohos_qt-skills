---
id: problem-runtime-icons-missing-libqico
type: problem
domain: runtime
tags: [runtime, icons, qico, libqico, imageformat, QIcon, toolbar, menu, ico, imageformats, plugin-deploy]
created: 2026-07-29
updated: 2026-07-29
status: solved
severity: high
audience: public
refs: [semantic-qt-harmonyos-golden-rules, semantic-qt-harmonyos-project-structure, problem-runtime-sqlite-open-database]
summary: >
  Toolbar/menu/tray icons don't show in a Qt HarmonyOS application (the QIcon spots are blank): the icon resources are .ico, which need the qico imageformat plugin
  (libqico.so) to be read, but the HAP doesn't deploy the imageformats/ subdirectory → QFactoryLoader can't find it → QImageReader can't read
  .ico → the QIcon is empty. Fix: copy libqico.so from <SDK>/plugins/imageformats/ into entry/libs/<abi>/imageformats/.
leader_summary: >
  Captured the root cause of .ico icons not showing (the missing libqico.so imageformat plugin; it isn't built into QtGui), in the same family as the B7/B12 subdirectory plugin deployment issues.
impact: [Migration efficiency, Framework support]
deliverables: [problem record, RedisView HAP icon fix]
evidence: [HAP contains imageformats/libqico.so+libqgif.so, hilog makeJsPixelMapFromIcon 48x48 non-empty, toolbar icons visible in screenshots]

# ====== Search keywords ======
error_message: >
  Toolbar/menu QAction icons don't show; after setIcon(QIcon(":/Resources/x.ico")) the icon spot is blank
  QIcon(".ico") loads empty / QImageReader cannot read .ico
  hilog: makeJsPixelMapFromIcon original Icon dimensions: 0x0 (or no such line)
error_code: ""
keywords: [ico, qico, libqico, imageformat, imageformats, QIcon, toolbar, menubar, icons not showing, blank icons, qgif, qsvg, qjpeg, QFactoryLoader]
symptoms: >
  After the application starts, the toolbar/menu/tray icon spots are blank; QIcon(:/...x.ico) loads empty; switching to .png icons displays fine.

# ====== Problem details ======
environment: "Qt 5.12/5.15 for HarmonyOS, real device/emulator. Icon resources are in .ico format (common in Windows-style Qt applications)."
---

## Root cause

`.ico` (Windows icon) **is not a format QtGui supports out of the box**: Qt's built-in formats are only BMP/JPG/PNG/GIF/PBM/PGM/PPM/XBM/XPM. `.ico` is provided by the `qico` imageformat plugin (the `qtimageformats` module, `libqico.so`), which `QFactoryLoader` dlopens on demand at runtime from the `imageformats/` subdirectory of the application's lib directory.

By default an OHOS HAP only deploys the Qt core .so files + the QPA `libqohos.so` + `styles/libqohosstyle.so`, and **doesn't deploy the imageformats/ subdirectory** (like `sqldrivers/libqsqlite.so` and `styles/libqohosstyle.so`, these are categorized subdirectory plugins that must be placed by hand; see iron rules B7/B12). So `QImageReader` fails to read the .ico → `QIcon(":/Resources/run.ico")` is empty → the toolbar/menu/tray icon spots are blank.

Note: `.png` can be read out of the box, so `alipay.png`/`weiPay.png` in the qrc work fine; `wait.gif` needs `libqgif.so`, `.svg` needs `libqsvg.so`, and `.jpeg` needs `libqjpeg.so`.

## How to verify

1. `unzip -l entry-default-signed.hap | grep -i imageformat` → if there's no `libs/<abi>/imageformats/libqico.so`, it's missing.
2. `strings <SDK>/plugins/imageformats/libqico.so` to confirm the plugin exists.
3. After the fix, cold-start the app; `hdc shell hilog -x | grep makeJsPixelMap` should show `original Icon dimensions: 48x48` (not 0x0) = the .ico loaded; the toolbar icons are visible in a screenshot.

## Solution

Copy the needed plugins from the Qt OHOS SDK's `plugins/imageformats/` into the project's `entry/libs/<abi>/imageformats/` (hvigor automatically packages the entry/libs/ subdirectories into the HAP's `libs/<abi>/<subdir>/`):

```bash
ABI=arm64-v8a
SDK=<Qt OHOS SDK root>   # e.g. ${QT5_15_OHOS_SDK_FULL}
mkdir -p entry/libs/$ABI/imageformats
# Copy according to the formats the resources actually use (minimal set):
cp $SDK/plugins/imageformats/libqico.so entry/libs/$ABI/imageformats/   # .ico (required)
cp $SDK/plugins/imageformats/libqgif.so  entry/libs/$ABI/imageformats/   # .gif (if using wait.gif, etc.)
cp $SDK/plugins/imageformats/libqsvg.so  entry/libs/$ABI/imageformats/   # .svg (if there are SVG icons)
cp $SDK/plugins/imageformats/libqjpeg.so entry/libs/$ABI/imageformats/   # .jpeg/.jpg (if any)
```
Rebuild the HAP (`hvigorw assembleHap`) → reinstall → the icons show.

> The deployment location **must** be the `imageformats/` subdirectory (not the `libs/<abi>/` root), following the same rule as `styles/` and `sqldrivers/`: `QFactoryLoader` dlopens categorized plugins by subdirectory.

## Key diagnostic signals

- Distinguish "the icon resource isn't embedded" from "the .ico can't be read": the qrc contains the .ico + AUTORCC ON = embedded; `QIcon(":/...x.ico").isNull()` returning true = can't be read (libqico.so missing). If switching to a `.png` resource displays fine, that confirms the .ico plugin is missing.
- Only .ico doesn't show while .png works → 100% libqico.so is missing.
- If .svg doesn't show either → libqsvg.so is missing too (same reasoning).

## Related

- [[qt-harmonyos-golden-rules]] — B7 (libqohosstyle.so→styles/), B12 (libqsqlite.so→sqldrivers/; the same rule mentions libqsvg.so→imageformats/)
- [[qt-harmonyos-project-structure]] — §6.2 deploying categorized plugins into subdirectories
- [runtime-fail-sqlite-open-database](runtime-fail-sqlite-open-database.md) — same family (a missing sqldrivers/ subdirectory plugin)

> 📋 Back to the [error quick-reference table](_lookup.md)
