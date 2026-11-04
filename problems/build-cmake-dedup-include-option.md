---
id: problem-build-cmake-dedup-include-option
type: problem
domain: build
tags: [cmake, -include, 预编译头, 去重, clang, toolchain, 迷惑报错]
created: 2026-11-04
updated: 2026-11-04
status: solved
severity: medium
audience: public
summary: "CMake 去重 -include 选项把两个头拼成 -include A B，clang 把 B 当输入文件"
# ====== 检索关键字（Agent 快速匹配用）======
error_message: >
  clang++: warning: treating 'c-header' input as 'c++-header' when in use
  clang++: error: cannot specify -o when generating multiple output files
error_code: ""
keywords: [-include, CMAKE_CXX_FLAGS, 去重, 预编译头, stdafx.h, libcxx_compat.h, toolchain, 无法指定 -o]
symptoms: "加了 -include stdafx.h 后报 'cannot specify -o when generating multiple output files'"
# ====== 问题详情 ======
environment: "CMake 3.x + OHOS clang 15 交叉 toolchain；宿主 Windows"
refs: [problem-build-app-layer-out-of-tree-prerequisites]
related_problems: [problem-build-app-layer-out-of-tree-prerequisites]
---

# CMake 去重 `-include` 后变成 `-include A B`

## 根因

交叉 toolchain 自己在编译器命令行上注入了一个预编译头，典型是：

```
-include /path/to/libcxx_compat.h
```

你为了编 app 层再加一个：

```cmake
target_compile_options(<t> PRIVATE -include ${SRC}/SourceFiles/stdafx.h)
```

CMake 认为这是**同一个选项的重复实例**，去重后合并成一个参数：

```
-include libcxx_compat.h SourceFiles/stdafx.h
```

clang 的 `-include` 只接受**一个**文件名，于是它把第二个 token 当成**输入文件**：

```
clang++: warning: treating 'c-header' input as 'c++-header' when in use
clang++: error: cannot specify -o when generating multiple output files
```

报错里**完全不提 `-include`**，所以很容易去查"多输出文件"相关的构建配置，方向全错。

## 解决方案

把选项和值写成一个 token：

```cmake
target_compile_options(<t> PRIVATE "-include${SRC}/SourceFiles/stdafx.h")
```

这样它是独立字符串，不参与 `-include` 的去重合并；toolchain 那一个保持不变，
两个预编译头都生效（`libcxx_compat.h` 先、`stdafx.h` 后，顺序由命令行保持）。

## 验证方法

1. 看实际命令行：`ninja -t commands <target> | head -1`，确认是
   `-includeA -includeB` 两个独立 token，而不是 `-include A B`。
2. 编过之后确认预编译头真的生效：随便去掉一个 `stdafx.h` 依赖的类型定义，报错应是
   "未声明标识符"，而不是"头文件找不到"。

## 适用范围

- 任何"toolchain 已注入 `-include`，应用还想再加一个"的交叉构建。
- 同源陷阱：toolchain 注入的 `-isystem` 同样会被归一化，写单 token 最稳。

