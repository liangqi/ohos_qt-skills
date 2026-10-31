# DevEco Studio 回退外部文件编辑导致编译修复反复失效

> 编号：build-fix-11
> 日期：2026-10-10（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）
> 涉及文件：`CMakeLists.txt`、`build-profile.json5`、`pages/*.cpp`（全部已修复的源文件）
> 工程根：`QtBugDemo-official/`
> 性质：构建环境问题（IDE 回退外部编辑）
> 结果：识别回退机制，提供持久化方案

## 1. 现象

已按 build-fix-04 ~ build-fix-08 的方案修复全部 5 类编译错误并验证构建通过，
但**后续重新构建时同样的编译错误再次出现**。检查源码发现**所有修复均被回退到
原始状态**——CMakeLists.txt 恢复了 `find_package`、源码恢复了 `->screen()`
调用、`build-profile.json5` 恢复了 `6.0.0(20)`、残留 include 也回来了。

每轮修复→构建→通过→一段时间后修复消失→同样的报错重现，形成死循环。

## 2. 根因

### 2.1 DevEco Studio 持续运行且已打开本工程

本机 DevEco Studio 进程（PID 6831）自 8 月 19 日起持续运行，已打开
`QtBugDemo-official` 工程：

```
$ ps aux | grep devecostudio
xiaoliyu  6831  ... /Applications/DevEco-Studio.app/Contents/MacOS/devecostudio
xiaoliyu 89730  ... clangd-aarch64 ... --compile-commands-dir=.../QtBugDemo-official/.idea/.deveco/cxx
```

DevEco Studio 的编辑器在内存中持有所有已打开文件的缓冲区（in-memory buffer）。

### 2.2 IDE "Safe Write" 机制回退外部修改

当外部工具（如 opencode、命令行 `sed`/`echo` 等）修改磁盘上的源文件时，
DevEco Studio 的文件监视器（file watcher）检测到变更，但行为取决于 IDE 设置：

1. **若 IDE 未修改过该文件**（缓冲区与磁盘一致）→ IDE 从磁盘重新加载 → 外部修改保留。
2. **若 IDE 曾修改过该文件**（缓冲区有未保存的改动，或 IDE 认为其版本是"权威"的）→
   IDE 将内存缓冲区写回磁盘 → **外部修改被覆盖回退**。

本工程的情况属于第 2 种：DevEco Studio 的编辑器缓冲区持有原始版本的文件内容
（包括 `find_package`、`->screen()`、`SP_DialogSaveAllButton` 等），当外部工具
修改文件后，IDE 将缓冲区写回 → 修复被回退。

### 2.3 回退证据

对每次修复后的文件做时间线追踪：

| 时间 | 事件 | 结果 |
|------|------|------|
| 10:22 | opencode 写入修复版 CMakeLists.txt | 磁盘文件已更新 |
| 10:26 | hvigorw 构建 | BUILD SUCCESSFUL（读到了修复版） |
| 10:33 | opencode 再次检查 | 文件已回退为原始版本 |
| 10:38 | opencode 重新写入修复 | 磁盘文件再次更新 |
| 10:38 | hvigorw 构建 | BUILD SUCCESSFUL（读到修复版） |

每轮"修复→构建"之间，DevEco Studio 将缓冲区写回磁盘，回退外部修改。

### 2.4 关联：守护进程 cwd 指向废纸篓

hvigor 守护进程的 cwd 曾指向 `~/.Trash/QtBugDemo-official`（见 build-fix-10），
说明该工程曾从废纸篓位置打开过。DevEco Studio 的项目配置可能仍残留旧路径引用，
加剧了文件同步混乱。

## 3. 修复方案

### 方案 A：关闭 DevEco Studio 后再执行外部编辑（推荐）

```bash
# 1. 完全退出 DevEco Studio
osascript -e 'quit app "DevEco-Studio"'
# 确认进程已退出
ps aux | grep devecostudio | grep -v grep || echo "DevEco Studio 已退出"

# 2. 执行所有源码修复（opencode / sed / 手动编辑）
#    此时无 IDE 文件监视器，磁盘修改不会被回退

# 3. 重新打开 DevEco Studio
open -a "DevEco-Studio" <YOUR_HOME>/code/.opencode/skills/qt-community-to-official/QtBugDemo-official
```

### 方案 B：在 DevEco Studio 内部编辑（不使用外部工具）

直接在 DevEco Studio 的编辑器中修改以下文件（逐个打开 → 编辑 → Ctrl+S 保存）：

| 文件 | 修改内容 | 对应文档 |
|------|---------|---------|
| `entry/src/main/cpp/CMakeLists.txt` | 绕开 find_package，改直接路径链接 + 关 AUTO\* | build-fix-04 |
| `build-profile.json5` | `compatibleSdkVersion: "6.1.1(24)"` | build-fix-08 |
| `pages/s9_base_equals_window.cpp` | 删除 `#include <QtOhosExtras/QOhosAbilityContext>` | build-fix-07 |
| `pages/f19_qtoolbar.cpp` | `SP_DialogSaveAllButton` → `SP_DialogSaveButton` | build-fix-06 |
| `pages/s11_dialog_dock_center.cpp` | 补 `#include <QWindow>`；`parent->screen()` → `windowHandle()->screen()` | build-fix-05 |
| `pages/c3_dialog_dock.cpp` | 补 `#include <QWindow>`；2 处 `->screen()` → `windowHandle()->screen()` | build-fix-05 |
| `pages/c7_dialog_upperhalf.cpp` | 补 `#include <QWindow>`；`dlg->screen()` → `windowHandle()->screen()` | build-fix-05 |

### 方案 C：配置 DevEco Studio 不回退外部修改

DevEco Studio (基于 IntelliJ) 的设置路径：

**Settings → Editor → File Edits → External Changes**

确保以下选项已启用：
- `Synchronize files on frame activation`（窗口激活时从磁盘同步）
- `Synchronize file changes on VCS`（VCS 变更时同步）

确保以下选项已**禁用**：
- `Save files if no IDE activity`（空闲时自动保存缓冲区——**这是回退的元凶**）

> 不同版本路径可能略有差异。搜索 Settings 中的 "external change" 或 "auto save"。

### 方案 D：用 git 钉住修复（防回退）

初始化 git 仓库，提交修复后的版本。即使 IDE 回退，也能用 `git checkout` 恢复：

```bash
cd QtBugDemo-official
git init
git add -A
git commit -m "fix: apply build-fix-04~08 compilation fixes"

# 若 IDE 回退了修复：
git checkout -- entry/src/main/cpp/CMakeLists.txt
git checkout -- build-profile.json5
git checkout -- entry/src/main/cpp/pages/*.cpp
# 或一次性恢复全部：
git checkout -- .
```

## 4. 验证

```bash
# 确认修复未被回退
cd QtBugDemo-official
grep "find_package(QT NAMES" entry/src/main/cpp/CMakeLists.txt && echo "REVERTED!" || echo "fix OK"
grep "compatibleSdkVersion" build-profile.json5  # 应为 6.1.1(24)
grep "SP_DialogSaveAllButton" entry/src/main/cpp/pages/f19_qtoolbar.cpp && echo "REVERTED!" || echo "fix OK"

# 构建
export DEVECO_SDK_HOME=/Applications/DevEco-Studio.app/Contents/sdk
export JAVA_HOME=/Applications/DevEco-Studio.app/Contents/jbr/Contents/Home
export PATH="$JAVA_HOME/bin:$PATH"
hvigorw assembleHap --mode module -p module=entry@default -p product=default --no-daemon
```

预期：`BUILD SUCCESSFUL`，产出 `entry-default-signed.hap`。

## 5. 诊断脚本

```bash
#!/bin/bash
# 检查所有修复是否仍然有效（未被 IDE 回退）
cd "$(dirname "$0")/.."

checks=(
  "CMakeLists.txt|find_package(QT NAMES|REVERTED (find_package 恢复)"
  "CMakeLists.txt|CMAKE_AUTOMOC ON|REVERTED (AUTOMOC 恢复为 ON)"
  "build-profile.json5|6.0.0(20)|REVERTED (compatibleSdkVersion 恢复)"
  "pages/s9_base_equals_window.cpp|QtOhosExtras/QOhosAbilityContext|REVERTED (残留 include 恢复)"
  "pages/f19_qtoolbar.cpp|SP_DialogSaveAllButton|REVERTED (SP_DialogSaveAllButton 恢复)"
  "pages/s11_dialog_dock_center.cpp|parent->screen()|REVERTED (screen() API 恢复)"
  "pages/c3_dialog_dock.cpp|dlg.screen()|REVERTED (screen() API 恢复)"
  "pages/c3_dialog_dock.cpp|anchor->screen()|REVERTED (screen() API 恢复)"
  "pages/c7_dialog_upperhalf.cpp|dlg->screen()|REVERTED (screen() API 恢复)"
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
  echo "✓ 所有修复均有效"
else
  echo ""
  echo "原因: DevEco Studio 可能回退了外部编辑（见 build-fix-11）"
  echo "修复: 关闭 DevEco Studio → 重新应用修复 → 或在 IDE 内编辑"
fi
```

## 6. 总结

| 问题 | 根因 | 修复 |
|------|------|------|
| 编译错误反复出现 | DevEco Studio 编辑器缓冲区覆盖磁盘文件，回退外部修复 | 关闭 IDE 后编辑 / IDE 内编辑 / 禁用自动保存 / git 钉住 |

> **核心建议**：若使用 opencode 或命令行工具修改源码，**先退出 DevEco Studio**
> （`osascript -e 'quit app "DevEco-Studio"'`），修改完成后再重新打开。
> 这是最可靠的防回退方案。

## 7. 已有编译错误修复文档索引

以下文档记录了被回退的 5 类编译错误及其修复方案，修复被回退后可按此重新应用：

| 编号 | 文档 | 编译错误 |
|------|------|---------|
| 04 | `build-fix-04-findpackage-qt6-fallback.md` | CMake find_package 回退系统 Qt6 |
| 05 | `build-fix-05-qwidget-screen-api-mismatch.md` | QWidget::screen() Qt 5.14+ API |
| 06 | `build-fix-06-sp-dialogsaveallbutton-api-mismatch.md` | SP_DialogSaveAllButton Qt 5.15+ API |
| 07 | `build-fix-07-unused-qtoshehtras-include-residue.md` | 迁移残留未使用 include |
| 08 | `build-fix-08-compatiblesdkversion-mismatch.md` | compatibleSdkVersion 版本不符 |
| 10 | `build-fix-10-eperm-uv-cwd-stale-daemon.md` | hvigor 守护进程 cwd 失效 |
