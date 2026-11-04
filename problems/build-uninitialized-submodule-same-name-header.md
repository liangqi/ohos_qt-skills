---
id: problem-build-uninitialized-submodule-same-name-header
type: problem
domain: build
tags: [git submodule, 同名头, include 路径, pragma once, 自包含, translate_provider]
created: 2026-11-04
updated: 2026-11-04
status: solved
severity: medium
audience: public
summary: "子模块未初始化时，尖括号 include 解析到自己，被 pragma once 吞掉 → 类型不存在"
# ====== 检索关键字（Agent 快速匹配用）======
error_message: >
  error: no member named 'TranslateProvider' in namespace 'Ui'
  error: unknown type name 'TranslateProviderRequest'
error_code: ""
keywords: [submodule, git submodule update --init, 同名头, 尖括号 include, pragma once, include 路径, 自包含]
symptoms: "类型明明存在却报未声明；报错指向业务代码，实际是子模块没拉"
# ====== 问题详情 ======
environment: "CMake 交叉构建；仓库用 git submodule 管理 Telegram/lib_* 子模块"
refs: [problem-build-app-layer-out-of-tree-prerequisites]
related_problems: [problem-build-app-layer-out-of-tree-prerequisites]
---

# 子模块没初始化 → 同名头解析到自己

## 根因

应用源码里有一条尖括号 include：

```cpp
// SourceFiles/lang/translate_provider.h
#include <translate_provider.h>     // 指向 Telegram/lib_translate/translate_provider.h
```

尖括号表示"在 include 路径里找"。当子模块 `Telegram/lib_translate` **未初始化**（目录空）时，
而 `SourceFiles/lang` 又在 include 路径里，这一行就解析到**它自己**：

1. `SourceFiles/lang/translate_provider.h` 被自己 include；
2. 文件头的 `#pragma once` 判定"已包含"，整段内容被跳过；
3. 于是 `Ui::TranslateProvider`、`TranslateProviderRequest` 全部"不存在"。

报错指向业务代码（`no member named 'TranslateProvider' in namespace 'Ui'`），
和"子模块没拉"完全不像。

## 解决方案

```bash
git submodule update --init Telegram/lib_translate
# 或一次性全拉
git submodule update --init --recursive
```

不要靠"改 include 顺序"或"加 -I"绕：绕过去之后真实现仍然缺失，链接期会再爆一次。

## 验证方法

1. `git submodule status | grep '^-'` —— 以 `-` 开头即未初始化。
2. 编过后确认头来自谁：`clang++ -H ... | grep translate_provider` 应显示
   `Telegram/lib_translate/translate_provider.h`，而不是 `SourceFiles/lang/translate_provider.h`。

## 关联

这类"报错不指向真因"的构建错误在本仓成组出现（C++20 缺口、预编译头、API 凭据、代码生成、
Qt 模块、同名头），排查顺序见 [[build-app-layer-out-of-tree-prerequisites]]。
