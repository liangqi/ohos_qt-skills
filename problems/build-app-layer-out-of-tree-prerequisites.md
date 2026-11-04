---
id: problem-build-app-layer-out-of-tree-prerequisites
type: problem
domain: build
tags: [树外构建, 预编译头, stdafx, cxx_std_20, 代码生成, codegen_style, scheme, TDESKTOP_API_ID, 交叉编译]
created: 2026-11-04
updated: 2026-11-04
status: solved
severity: medium
audience: public
summary: "大型 Qt 桌面应用的 app 层无法直接交叉编译 —— 卡在预编译头、两套代码生成和 5 个隐式前置"
# ====== 检索关键字（Agent 快速匹配用）======
error_message: >
  error: 'auto' not allowed in friend declaration
  error: no type named 'strong_ordering' in namespace 'std'
  error: use of undeclared identifier 'rpl'
  error: no template named 'flat_set' in namespace 'base'
  error: "You are required to provide API_ID and API_HASH"
  fatal error: 'styles/style_window.h' file not found
  fatal error: 'scheme.h' file not found
  fatal error: 'QOpenGLWidget' file not found
error_code: ""
keywords: [预编译头, stdafx.h, -include, cxx_std_20, codegen_style, codegen_scheme, scheme.h, TDESKTOP_API_ID, 树外构建, OBJECT 库]
symptoms: "把 app 层源码直接加进交叉工程后，6 类错误依次出现；每修一类才暴露下一类"
# ====== 问题详情 ======
environment: "Qt 6.13.0-dev OHOS kit（含 OpenGL/OpenGLWidgets，无 Svg）；OHOS clang 15；宿主 Windows"
refs: [problem-build-clang15-libcpp15-cpp20-gaps, problem-build-cmake-dedup-include-option, semantic-qt-harmonyos-porting-workflow]
related_problems: [problem-build-cmake-dedup-include-option]
---

# 大型 Qt 桌面应用的 app 层：5 个隐式前置 + 2 个陷阱

## 现象链（按实际遇到顺序）

把 `SourceFiles/` 当普通源码目录加进交叉工程做**编译校验**（依赖还没齐、想先验证平台层能否编过）时，
错误一类接一类出现，且**每一类的报错都不指向真因**：

```
# 1) 没开 C++20
error: 'auto' not allowed in friend declaration
error: no type named 'strong_ordering' in namespace 'std'
# 2) 没 force-include 预编译头（一次 40+ 条，全部指向错误方向）
error: use of undeclared identifier 'rpl'
error: no template named 'flat_set' in namespace 'base'
# 3) 缺 API 凭据（config.h 里硬 #error）
error: "You are required to provide API_ID and API_HASH"
# 4) 缺生成物（样式 / MTP scheme）
fatal error: 'styles/style_window.h' file not found
fatal error: 'scheme.h' file not found
# 5) 缺 Qt 模块
fatal error: 'QOpenGLWidget' file not found
```

## 根因：5 个隐式前置，缺一不可

| # | 前置 | 缺失时的表现 |
|---|------|-------------|
| 1 | `cxx_std_20` | `friend auto operator<=>(...) = default` 报 `auto not allowed` |
| 2 | `-include SourceFiles/stdafx.h` | 每个头都"未声明标识符"（头文件自身不含其依赖的 include） |
| 3 | `API_ID` / `API_HASH` 宏 | `config.h` 里硬 `#error` |
| 4 | 两套代码生成物 | 样式头 147 个文件 + MTP `scheme.h`（数 MB） |
| 5 | 正确的三方 include（GSL / range-v3 / expected）+ Qt 模块 | `range/v3/all.hpp` / `QOpenGLWidget` 找不到 |

第 4 项还有一层：**代码生成工具必须能在宿主执行**。被交叉编译的树里 `codegen_style`
会被编成目标架构的 ELF，构建期调用直接 `Error 127`（exec format error）。
上游 tdesktop 的 Android/iOS 交叉构建也是靠单独一套宿主 codegen 解决的。

## 两套生成物怎么各自脱离完整 configure

```bash
# 样式：73 个 .style -> 147 个文件
codegen_style -I<SourceFiles> -I<lib_ui> -I<Resources> \
  -o<gen>/styles -t<gen>/styles/td_ui_style -w<Telegram> <73 files>

# MTP scheme：纯 Python，无需宿主二进制
python <SourceFiles>/codegen/scheme/codegen_scheme.py -o<gen>/scheme \
  <scheme>/api.tl <scheme>/mtproto.tl
```

## 两个额外陷阱

1. **`-include` 必须写成单个 token**（`"-include<path>"`）：CMake 会**去重**重复的 `-include`，
   而交叉 toolchain 自己已注入一个（如 `-include libcxx_compat.h`），去重后变成 `-include A B`，
   clang 把 `B` 当**输入文件**：`error: cannot specify -o when generating multiple output files`
   —— 报错完全不提 `-include`。详见 [[build-cmake-dedup-include-option]]。
2. **未初始化的子模块**要先 `git submodule update --init <lib>`：`#include <translate_provider.h>`
   会解析到自身、被 `#pragma once` 吞掉，表现为"类型不存在"。详见
   [[build-uninitialized-submodule-same-name-header]]。

## 验证方法

最小交叉工程（OBJECT 库，不链接）可以先把 app 层编过：

```cmake
target_compile_features(<t> PRIVATE cxx_std_20)
target_compile_definitions(<t> PRIVATE API_ID=... API_HASH=... CRL_USE_QT)
target_compile_options(<t> PRIVATE "-include${SRC}/SourceFiles/stdafx.h")
target_include_directories(<t> PRIVATE
  <src>/SourceFiles <lib_ui> <lib_base> <gen>/styles <gen>/scheme)
target_link_libraries(<t> PRIVATE desktop-app::external_qt)
```

编过后用 `clang++ -H` 确认 include 树里是 `platform/ohos/specific_ohos.h`（不是 `win/`、`linux/`）。

## 边界

- 这条路线只做**编译校验**：依赖没齐时不能链接成完整应用，`verify` 的 G3 会 PASS、G4 只到 PARTIAL。
- 库级进展用 `qt-ohos-run libcheck <lib> --level built|probed` 记，整包门禁不再吞掉中间成果。
