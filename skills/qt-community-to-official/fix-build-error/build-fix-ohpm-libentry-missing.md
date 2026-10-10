# oh-package.json5 引用已删除的 types/libentry 导致 ohpm 失败

> 编号：build-fix-09
> 日期：2026-09-28（基于实测构建）
> 涉及文件：`entry/oh-package.json5`
> 工程根：`QtBugDemo-official/`
> 当前状态：未修复

## 1. 报错

构建在 ohpm 安装阶段即失败（早于 CMake 配置）：

```
ohpm ERROR: Run install command failed
Error: 00617301 Fetch Source Code Failed
Error Message: Fetch local folder package error,
  /Users/xiaoliyu/code/.opencode/skills/qt-community-to-official/QtBugDemo-official/entry/src/main/cpp/types/libentry does not exist.
```

## 2. 根因

### 2.1 模版引用 types/libentry

模版 `entry/oh-package.json5` 含：

```json5
"devDependencies": {
    "@types/libentry.so": "file:./src/main/cpp/types/libentry",
    "@types/libqohos.so": "file:./src/main/qt"
}
```

`@types/libentry.so` 指向 `src/main/cpp/types/libentry/`，该目录在模版中
含 `index.d.ts`（导出 `add(a, b)` 示例函数）和 `oh-package.json5`。

### 2.2 migrate.py 删除了 types/libentry 但未更新 oh-package.json5

`migrate.py` 的 `create_clone_project()` 在创建新工程后，主动删除模版
libentry 相关文件（因为实际 CMake 目标名不同）：

```python
libentry_paths = [
    new_project_dir / "entry" / "src" / "main" / "cpp" / "hello.cpp",
    new_project_dir / "entry" / "src" / "main" / "cpp" / "types",       # ← 删除
    new_project_dir / "entry" / "oh_modules" / "@types" / "libentry.so",
]
```

删除 `types/` 目录后，`oh-package.json5` 中的
`"file:./src/main/cpp/types/libentry"` 指向的路径不存在 → ohpm 报错。

### 2.3 实际库名不匹配

| 项 | 模版默认值 | 实际值 |
|----|-----------|--------|
| CMake 目标 | `entry` | `qtbugdemo` |
| 产物 .so | `libentry.so` | `libqtbugdemo.so` |
| APP_LIBRARY_NAME | `libentry.so` | `libqtbugdemo.so` |

`@types/libentry.so` 引用对实际工程无意义——它声明的是模版的示例函数
`add(a, b)`，与实际 native 库 `libqtbugdemo.so` 无关。

## 3. 修复

从 `entry/oh-package.json5` 中移除 `@types/libentry.so` 引用：

```diff
   "devDependencies": {
-    "@types/libentry.so": "file:./src/main/cpp/types/libentry",
     "@types/libqohos.so": "file:./src/main/qt"
   },
```

保留 `@types/libqohos.so`——`src/main/qt/` 目录存在（含 `libqohos.d.ts`），
该引用有效。

## 4. 验证

修复后 ohpm install 成功，构建进入 CMake 配置阶段。

## Auto-fix

```yaml
match: "00617301|Fetch Source Code Failed|types/libentry does not exist"
files:
  - entry/oh-package.json5
actions:
  - type: remove_line
    pattern: '"@types/libentry.so"'
```
