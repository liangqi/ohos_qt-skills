---
id: problem-runtime-dlopen-writable-path
type: problem
domain: runtime
tags: [runtime, dlopen, sandbox, writable-path, el2, plugin-loading]
created: 2026-06-03
updated: 2026-06-03
status: solved
audience: public
severity: high

# ====== 检索关键字（Agent 快速匹配用）======
error_message: >
  dlopen failed: cannot open shared object file
  dlopen: errno=22 (EINVAL)
  library not found in writable path
error_code: "errno=22 (EINVAL)"
keywords: [dlopen, writable, el2, sandbox, plugin, dynamic-loading, EINVAL]
symptoms: "运行时加载 .so 插件失败，dlopen 返回 EINVAL，路径在 /data/storage/el2/ 下"

# ====== 问题详情 ======
environment: "Qt 5.12/5.15 for HarmonyOS, 真机"
refs: [semantic-qt-harmonyos-platform-limits, semantic-qt-harmonyos-third-party-libs, semantic-qt-harmonyos-golden-rules]
related_problems: [problem-runtime-qpa-plugin-not-found]
---

# dlopen 从可写路径加载 .so 被拒绝

## 错误信息

```
dlopen failed: library "/data/storage/el2/100/base/files/plugins/libMyPlugin.so"
cannot open shared object file: errno=22 (EINVAL)
```

或 Qt 层面的报错：

```
QPluginLoader: Could not load plugin: dlopen failed
```

## 场景

应用尝试从 `QStandardPaths::writableLocation()` 返回的路径（通常在 `/data/storage/el2/` 下）动态加载 .so 插件文件，`dlopen()` 返回 EINVAL。

常见于：
- 插件系统（将插件 .so 下载到可写目录后加载）
- JIT 编译器（运行时生成代码写入文件后加载）
- 热更新机制（替换 .so 后重新加载）

## 原因

鸿蒙沙箱安全策略：**`dlopen()` 拒绝从可写路径加载 .so**。只允许从应用 lib 目录（只读）加载。

具体限制：
- `/data/storage/el2/` 下所有路径（包括 `files/`、`cache/`、`preferences/`）→ **被拒绝**
- `/data/storage/el1/` 下 → 运行时只读，**可能可以**
- 应用 lib 目录（`entry/libs/arm64-v8a/`）→ **允许**

## 解决方案

### 方案 A：将 .so 放在应用 lib 目录（推荐）

将所有需要动态加载的 .so 文件在打包时放入 `entry/libs/arm64-v8a/`：

```bash
cp libMyPlugin.so entry/libs/arm64-v8a/
```

然后在代码中使用标准 dlopen（不带路径，让系统搜索 lib 目录）：

```cpp
// ✅ 不指定路径，系统自动搜索应用 lib 目录
void *handle = dlopen("libMyPlugin.so", RTLD_NOW);
```

### 方案 B：静态链接替代动态加载

如果插件集合是固定的，改为编译时静态链接：

```cmake
# 替代 dlopen，直接链接
target_link_libraries(QtHarmonyApp PRIVATE
    MyPlugin  # 静态库
)
```

### 方案 C：使用 Qt 插件机制

利用 Qt 自带的插件系统（`Q_PLUGIN_METADATA`），Qt 会在应用 lib 目录中搜索插件：

```cpp
// 插件放在 entry/libs/arm64-v8a/ 下
QPluginLoader loader("libMyPlugin.so");
QObject *plugin = loader.instance();
```

## 注意事项

- 这是平台限制 P3（[[qt-harmonyos-platform-limits]] §dlopen），华为未确认是否会放开
- `QStandardPaths::writableLocation()` 返回的路径**全部**在 el2 下，都不能用于 dlopen
- 如果需要运行时下载代码执行，考虑使用 ArkTS/JS 脚本替代 .so 插件
- 第三方库（如 Qt 自身的插件加载）也受此限制——确保所有 .so 都在打包时部署到 lib 目录

## 相关

- [[qt-harmonyos-platform-limits]] — §dlopen 限制详情
- [[qt-harmonyos-third-party-libs]] — §3 .so 部署规则
- [[qt-harmonyos-golden-rules]] — 规则 P3

### 相关问题

- [runtime-fail-qpa-plugin-not-found](runtime-fail-qpa-plugin-not-found.md) — 同类 dlopen 失败，但原因是 .so 文件缺失而非路径权限

> 📋 返回 [错误速查表](_lookup.md)
