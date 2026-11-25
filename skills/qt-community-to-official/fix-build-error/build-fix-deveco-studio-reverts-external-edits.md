# DevEco Studio reverts external file edits, so build fixes keep getting undone

> ID: build-fix-11
> Date: 2026-10-10 (updated based on actual build)
> Files involved: `CMakeLists.txt`, `build-profile.json5`, `pages/*.cpp` (all the fixed source files)
> Project root: `QtBugDemo-official/`
> Nature: build environment problem (the IDE reverts external edits)
> Outcome: revert mechanism identified, persistent solutions provided

## 1. Symptom

All 5 classes of build errors were fixed following build-fix-04 through build-fix-08 and the build was verified to pass,
but **the same build errors reappeared on later rebuilds**. Inspecting the source showed that **every fix had been reverted to
the original state** — CMakeLists.txt was back to `find_package`, the sources were back to `->screen()`
calls, `build-profile.json5` was back to `6.0.0(20)`, and the leftover include had returned.

Each round went fix → build → pass → fixes vanish after a while → the same errors reappear, an endless loop.

## 2. Root cause

### 2.1 DevEco Studio keeps running with this project open

The local DevEco Studio process (PID 6831) had been running continuously since August 19 with the
`QtBugDemo-official` project open:

```
$ ps aux | grep devecostudio
xiaoliyu  6831  ... /Applications/DevEco-Studio.app/Contents/MacOS/devecostudio
xiaoliyu 89730  ... clangd-aarch64 ... --compile-commands-dir=.../QtBugDemo-official/.idea/.deveco/cxx
```

The DevEco Studio editor holds in-memory buffers for every open file.

### 2.2 The IDE "Safe Write" mechanism reverts external changes

When an external tool (such as opencode, or command-line `sed`/`echo`) modifies a source file on disk,
DevEco Studio's file watcher detects the change, but what happens next depends on the IDE settings:

1. **If the IDE has not modified the file** (the buffer matches the disk) → the IDE reloads from disk → the external change is kept.
2. **If the IDE has modified the file** (the buffer has unsaved changes, or the IDE considers its version "authoritative") →
   the IDE writes the in-memory buffer back to disk → **the external change is overwritten and reverted**.

This project falls into case 2: the DevEco Studio editor buffers held the original file contents
(including `find_package`, `->screen()`, `SP_DialogSaveAllButton`, and so on); after an external tool
modified the files, the IDE wrote the buffers back → the fixes were reverted.

### 2.3 Evidence of the reverts

Timeline tracking of the files after each fix:

| Time | Event | Result |
|------|-------|--------|
| 10:22 | opencode writes the fixed CMakeLists.txt | File on disk updated |
| 10:26 | hvigorw build | BUILD SUCCESSFUL (read the fixed version) |
| 10:33 | opencode checks again | File reverted to the original version |
| 10:38 | opencode rewrites the fix | File on disk updated again |
| 10:38 | hvigorw build | BUILD SUCCESSFUL (read the fixed version) |

Between each "fix → build" round, DevEco Studio wrote its buffers back to disk, reverting the external changes.

### 2.4 Related: the daemon cwd points into the Trash

The hvigor daemon's cwd once pointed to `~/.Trash/QtBugDemo-official` (see build-fix-10),
which shows the project was once opened from the Trash location. DevEco Studio's project configuration may still hold stale path references,
making the file synchronization mess worse.

## 3. Solutions

### Option A: quit DevEco Studio before making external edits (recommended)

```bash
# 1. Quit DevEco Studio completely
osascript -e 'quit app "DevEco-Studio"'
# Confirm the process has exited
ps aux | grep devecostudio | grep -v grep || echo "DevEco Studio has exited"

# 2. Apply all source fixes (opencode / sed / manual edits)
#    With no IDE file watcher running, disk changes are not reverted

# 3. Reopen DevEco Studio
open -a "DevEco-Studio" <YOUR_HOME>/code/.opencode/skills/qt-community-to-official/QtBugDemo-official
```

### Option B: edit inside DevEco Studio (no external tools)

Edit the following files directly in the DevEco Studio editor (open each → edit → Ctrl+S to save):

| File | Change | Corresponding document |
|------|--------|------------------------|
| `entry/src/main/cpp/CMakeLists.txt` | Bypass find_package, link by direct path + turn off AUTO\* | build-fix-04 |
| `build-profile.json5` | `compatibleSdkVersion: "6.1.1(24)"` | build-fix-08 |
| `pages/s9_base_equals_window.cpp` | Delete `#include <QtOhosExtras/QOhosAbilityContext>` | build-fix-07 |
| `pages/f19_qtoolbar.cpp` | `SP_DialogSaveAllButton` → `SP_DialogSaveButton` | build-fix-06 |
| `pages/s11_dialog_dock_center.cpp` | Add `#include <QWindow>`; `parent->screen()` → `windowHandle()->screen()` | build-fix-05 |
| `pages/c3_dialog_dock.cpp` | Add `#include <QWindow>`; 2 × `->screen()` → `windowHandle()->screen()` | build-fix-05 |
| `pages/c7_dialog_upperhalf.cpp` | Add `#include <QWindow>`; `dlg->screen()` → `windowHandle()->screen()` | build-fix-05 |

### Option C: configure DevEco Studio not to revert external changes

The settings path in DevEco Studio (based on IntelliJ):

**Settings → Editor → File Edits → External Changes**

Make sure these options are enabled:
- `Synchronize files on frame activation` (sync from disk when the window is activated)
- `Synchronize file changes on VCS` (sync on VCS changes)

Make sure this option is **disabled**:
- `Save files if no IDE activity` (auto-saves buffers when idle — **this is the culprit behind the reverts**)

> The path may differ slightly between versions. Search Settings for "external change" or "auto save".

### Option D: pin the fixes with git (protection against reverts)

Initialize a git repository and commit the fixed version. Even if the IDE reverts the fixes, `git checkout` can restore them:

```bash
cd QtBugDemo-official
git init
git add -A
git commit -m "fix: apply build-fix-04~08 compilation fixes"

# If the IDE reverted the fixes:
git checkout -- entry/src/main/cpp/CMakeLists.txt
git checkout -- build-profile.json5
git checkout -- entry/src/main/cpp/pages/*.cpp
# Or restore everything at once:
git checkout -- .
```

## 4. Verification

```bash
# Confirm the fixes have not been reverted
cd QtBugDemo-official
grep "find_package(QT NAMES" entry/src/main/cpp/CMakeLists.txt && echo "REVERTED!" || echo "fix OK"
grep "compatibleSdkVersion" build-profile.json5  # should be 6.1.1(24)
grep "SP_DialogSaveAllButton" entry/src/main/cpp/pages/f19_qtoolbar.cpp && echo "REVERTED!" || echo "fix OK"

# Build
export DEVECO_SDK_HOME=/Applications/DevEco-Studio.app/Contents/sdk
export JAVA_HOME=/Applications/DevEco-Studio.app/Contents/jbr/Contents/Home
export PATH="$JAVA_HOME/bin:$PATH"
hvigorw assembleHap --mode module -p module=entry@default -p product=default --no-daemon
```

Expected: `BUILD SUCCESSFUL`, producing `entry-default-signed.hap`.

## 5. Diagnostic script

```bash
#!/bin/bash
# Check whether all fixes are still in effect (not reverted by the IDE)
cd "$(dirname "$0")/.."

checks=(
  "CMakeLists.txt|find_package(QT NAMES|REVERTED (find_package restored)"
  "CMakeLists.txt|CMAKE_AUTOMOC ON|REVERTED (AUTOMOC back to ON)"
  "build-profile.json5|6.0.0(20)|REVERTED (compatibleSdkVersion restored)"
  "pages/s9_base_equals_window.cpp|QtOhosExtras/QOhosAbilityContext|REVERTED (leftover include restored)"
  "pages/f19_qtoolbar.cpp|SP_DialogSaveAllButton|REVERTED (SP_DialogSaveAllButton restored)"
  "pages/s11_dialog_dock_center.cpp|parent->screen()|REVERTED (screen() API restored)"
  "pages/c3_dialog_dock.cpp|dlg.screen()|REVERTED (screen() API restored)"
  "pages/c3_dialog_dock.cpp|anchor->screen()|REVERTED (screen() API restored)"
  "pages/c7_dialog_upperhalf.cpp|dlg->screen()|REVERTED (screen() API restored)"
)

all_ok=true
for c in "${checks[@]}"; do
  IFS='|' read -r file pattern label <<< "$c"
  if grep -q "$pattern" "entry/src/main/cpp/$file" 2>/dev/null || grep -q "$pattern" "$file" 2>/dev/null; then
    echo "  ✗ $file: $label"
    all_ok=false
  fi
done

if $all_ok; then
  echo "✓ All fixes are in effect"
else
  echo ""
  echo "Cause: DevEco Studio may have reverted external edits (see build-fix-11)"
  echo "Fix: quit DevEco Studio → reapply the fixes → or edit inside the IDE"
fi
```

## 6. Summary

| Problem | Root cause | Fix |
|---------|------------|-----|
| Build errors keep reappearing | DevEco Studio editor buffers overwrite the files on disk, reverting external fixes | Edit after quitting the IDE / edit inside the IDE / disable auto-save / pin with git |

> **Key recommendation**: if you modify source with opencode or command-line tools, **quit DevEco Studio first**
> (`osascript -e 'quit app "DevEco-Studio"'`), then reopen it once the changes are done.
> This is the most reliable protection against reverts.

## 7. Index of existing build-fix documents

The following documents record the 5 classes of reverted build errors and their fixes; reapply them from here after a revert:

| ID | Document | Build error |
|----|----------|-------------|
| 04 | `build-fix-04-findpackage-qt6-fallback.md` | CMake find_package falls back to the system Qt6 |
| 05 | `build-fix-05-qwidget-screen-api-mismatch.md` | QWidget::screen() Qt 5.14+ API |
| 06 | `build-fix-06-sp-dialogsaveallbutton-api-mismatch.md` | SP_DialogSaveAllButton Qt 5.15+ API |
| 07 | `build-fix-07-unused-qtoshehtras-include-residue.md` | Unused include left over from migration |
| 08 | `build-fix-08-compatiblesdkversion-mismatch.md` | compatibleSdkVersion mismatch |
| 10 | `build-fix-10-eperm-uv-cwd-stale-daemon.md` | hvigor daemon cwd invalid |
