---
id: semantic-qt-harmonyos-third-party-libs
type: semantic
domain: tech
tags: [qt, harmonyos, third-party, cross-compile, cmake, vcpkg, dependency]
created: 2026-06-03
updated: 2026-07-07
status: active
audience: public
refs: [semantic-qt-harmonyos-build, semantic-qt-harmonyos-project-structure, semantic-qt-harmonyos-platform-limits, semantic-qt-ohos-project-analyzer-workflow]
summary: >
  三方库鸿蒙化指南：OHOS NDK 交叉编译（CMake 工具链配置）、.so 部署规则
  （entry/libs/arm64-v8a/）、CMake find_package 集成、平台限制对三方库的影响
  （chmod/symlink/dlopen/pthread_cancel）、vcpkg 参考、静态/动态链接策略、
  系统库可用性、header-only 库、已知兼容清单。
---

# 三方库鸿蒙化指南

> 将 Qt 应用移植到鸿蒙时，除了 Qt 模块本身的适配，还需要处理应用依赖的第三方 C/C++ 库。
> 本页覆盖交叉编译、部署、集成、平台限制影响等全流程。

---

## 1. 总体策略

| 策略 | 适用场景 | 复杂度 |
|------|---------|--------|
| **Header-only 库** | Eigen、nlohmann/json、spdlog（header-only 模式）等 | 🟢 低 — 直接包含头文件即可 |
| **源码交叉编译** | 有 CMake/autotools 构建系统的 C/C++ 库 | 🟡 中 — 需配置 OHOS 工具链 |
| **预编译 .so 集成** | 供应商提供 arm64 预编译二进制 | 🟡 中 — 需确认 ABI 兼容并正确部署 |
| **静态链接** | 希望避免 .so 部署问题的库 | 🟡 中 — 编译时链接，运行时无额外 .so |
| **系统库直链** | OHOS 系统自带的库（如 libz、libcrypto） | 🟢 低 — 直接链接，无需部署 |
| **替换/降级** | 不兼容且无法 patch 的库 | 🔴 高 — 需要寻找替代方案 |

---

> **📦 arm64 OHOS 预编译 bottle 来源 = Harmonybrew**：若某三方库已有 arm64_ohos 预编译包，可直接下载 .so 跳过本节交叉编译——见 [[fetch-ohos-third-party-lib]] 的一键拉取脚本（含依赖递归、sha256 校验、qmake/CMake 链接片段）。无 bottle 时继续按下文源码交叉编译。

## 2. OHOS NDK 交叉编译

### 2.1 工具链文件

OHOS NDK 提供了 CMake 工具链文件，位于 SDK 中：

```
<NATIVE_OHOS_SDK>/build/cmake/ohos.toolchain.cmake
```

交叉编译三方库时，使用此工具链文件：

```bash
cmake -S <三方库源码> -B build_ohos \
  -DCMAKE_TOOLCHAIN_FILE=$NATIVE_OHOS_SDK/build/cmake/ohos.toolchain.cmake \
  -DOHOS_ARCH=arm64-v8a \
  -DOHOS_PLATFORM=OHOS \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=<安装路径>
```

### 2.2 关键 CMake 变量

| 变量 | 说明 | 典型值 |
|------|------|--------|
| `CMAKE_TOOLCHAIN_FILE` | OHOS 工具链文件路径 | `$NATIVE_OHOS_SDK/build/cmake/ohos.toolchain.cmake` |
| `OHOS_ARCH` | 目标架构 | `arm64-v8a` |
| `OHOS_PLATFORM` | 目标平台 | `OHOS` |
| `CMAKE_INSTALL_PREFIX` | 安装路径（头文件+库） | 自定义路径 |
| `CMAKE_FIND_ROOT_PATH_MODE_PACKAGE` | find_package 搜索模式 | **`BOTH`**（同 Qt 交叉编译修复） |

> ⚠️ **铁律**：与 Qt 应用交叉编译相同，三方库的 CMake 构建也需要设置 `CMAKE_FIND_ROOT_PATH_MODE_PACKAGE=BOTH`，否则 `find_package` 无法找到依赖。详见 [[qt-harmonyos-project-structure]] §4.2。

### 2.3 典型交叉编译流程

```bash
# 以 zlib 为例
cd zlib-source/

cmake -S . -B build_ohos \
  -DCMAKE_TOOLCHAIN_FILE=$NATIVE_OHOS_SDK/build/cmake/ohos.toolchain.cmake \
  -DOHOS_ARCH=arm64-v8a \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=$HOME/ohos-libs/zlib

cmake --build build_ohos -j16
cmake --install build_ohos

# 产出：
# $HOME/ohos-libs/zlib/lib/libz.so
# $HOME/ohos-libs/zlib/include/zlib.h
```

### 2.4 autotools 项目的交叉编译

部分三方库使用 autotools（`./configure && make`），需要手动指定交叉编译器：

```bash
export CC=$NATIVE_OHOS_SDK/llvm/bin/clang
export CXX=$NATIVE_OHOS_SDK/llvm/bin/clang++
export CFLAGS="--target=aarch64-linux-ohos --sysroot=$NATIVE_OHOS_SDK/sysroot"
export LDFLAGS="--target=aarch64-linux-ohos"

./configure --host=aarch64-linux-ohos --prefix=$HOME/ohos-libs/<库名>
make -j16
make install
```

---

## 3. .so 部署规则

### 3.1 部署目录

交叉编译产出的 `.so` 文件需要复制到应用的 `entry/libs/arm64-v8a/` 目录下：

```
<工程目录>/
└── entry/
    └── libs/
        └── arm64-v8a/
            ├── libQt5Core.so          # Qt 库（自动部署）
            ├── libqohos.so            # QPA 插件（自动部署）
            ├── libz.so                # ★ 三方库（手动部署）
            ├── libssl.so              # ★ 三方库（手动部署）
            └── styles/
                └── libqohosstyle.so   # Qt 样式插件（手动部署）
```

### 3.2 部署脚本模板

```bash
#!/bin/bash
# deploy_third_party.sh — 将预编译的三方库 .so 复制到应用目录

TARGET_DIR=<工程目录>/entry/libs/arm64-v8a
THIRD_PARTY_LIBS=$HOME/ohos-libs

# 列出需要部署的三方库
THIRD_PARTY_SO_LIST=(
    "$THIRD_PARTY_LIBS/zlib/lib/libz.so"
    "$THIRD_PARTY_LIBS/openssl/lib/libssl.so"
    "$THIRD_PARTY_LIBS/openssl/lib/libcrypto.so"
    # 按需添加更多库...
)

for so in "${THIRD_PARTY_SO_LIST[@]}"; do
    if [ -f "$so" ]; then
        cp "$so" "$TARGET_DIR/"
        echo "Deployed: $(basename $so)"
    else
        echo "WARNING: $so not found!"
    fi
done

echo "Done. Verify: ls $TARGET_DIR/*.so"
```

### 3.3 运行时加载路径

鸿蒙应用运行时，`.so` 文件的搜索路径包含 `entry/libs/<arch>/`。只要将三方库 `.so` 放在此目录下，`dlopen()` 和动态链接器就能找到它们。

> ⚠️ **注意**：`dlopen()` 从**可写路径**加载 .so 会被拒绝（errno=22 EINVAL）。只能从应用 lib 目录（只读）加载。详见 [[qt-harmonyos-platform-limits]] §dlopen。

---

## 4. CMake 集成三方库

### 4.1 在应用 CMakeLists.txt 中链接三方库

> **铁律**：与 Qt 应用交叉编译相同，三方库的 CMake 构建也需要设置 `CMAKE_FIND_ROOT_PATH_MODE_PACKAGE=BOTH`，否则 `find_package` 无法找到依赖。完整的 save/restore 代码模式详见 [[qt-harmonyos-project-structure]] §4.2。

```cmake
# 1. 设置交叉编译 find_package 修复（同 Qt，详见 project-structure §4.2）
if(CMAKE_CROSSCOMPILING)
  set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH)
endif()

# 2. 查找三方库（如果库提供了 CMake config）
find_package(ZLIB REQUIRED)

# 3. 或者手动指定（如果库没有 CMake config）
set(THIRD_PARTY_PREFIX "$ENV{HOME}/ohos-libs")
include_directories(${THIRD_PARTY_PREFIX}/zlib/include)
link_directories(${THIRD_PARTY_PREFIX}/zlib/lib)

# 4. 链接到目标
target_link_libraries(QtHarmonyApp PRIVATE z ssl crypto)
```

### 4.2 使用 CMAKE_PREFIX_PATH

如果三方库安装时使用了标准目录结构（`lib/`、`include/`、`lib/cmake/`），可以通过 `CMAKE_PREFIX_PATH` 让 `find_package` 自动找到：

```cmake
# 在 DevEco 的 build-profile.json5 中设置：
# "arguments": "-DCMAKE_PREFIX_PATH=<Qt_SDK>;$ENV{HOME}/ohos-libs/zlib;$ENV{HOME}/ohos-libs/openssl"
```

### 4.3 静态链接三方库

如果三方库编译为静态库（`.a`），直接链接即可，无需部署 .so：

```cmake
target_link_libraries(QtHarmonyApp PRIVATE
    ${THIRD_PARTY_PREFIX}/zlib/lib/libz.a    # 静态链接
)
```

**优势**：避免 .so 部署问题，减少运行时依赖。
**劣势**：增大应用 .so 体积，多个模块使用同一静态库时可能符号冲突。

---

## 5. 平台限制对三方库的影响

鸿蒙平台的以下限制可能影响三方库的正常运行。移植前需检查三方库源码是否使用了这些 API。

### 5.1 chmod() / fchmod() 不可用

| 影响 | 说明 |
|------|------|
| **受影响库** | SQLite（数据库文件权限设置）、部分日志库（日志文件权限）、Boost.Filesystem |
| **表现** | 调用静默失败（对已有文件）或返回 false |
| **Workaround** | 用 `#ifndef __OHOS__` 条件编译跳过 `chmod()` 调用，或 patch 源码 |
| **参考** | [[qt-harmonyos-platform-limits]] §chmod |

```cpp
// Patch 示例：在源码中添加 OHOS 守卫
#ifndef __OHOS__
    chmod(path, 0644);
#endif
```

### 5.2 symlink() 不可用

| 影响 | 说明 |
|------|------|
| **受影响库** | 部分构建系统（创建符号链接）、Python 嵌入式解释器、某些包管理器 |
| **表现** | 返回 EACCES (13900012) |
| **Workaround** | 用文件拷贝替代符号链接 |
| **参考** | [[qt-harmonyos-platform-limits]] §symlink |

### 5.3 dlopen() 拒绝可写路径

| 影响 | 说明 |
|------|------|
| **受影响库** | 插件系统（如 Qt 自身的插件加载）、JIT 编译器、动态代码生成 |
| **表现** | 从 `/data/storage/el2/` 等可写路径 dlopen 被拒绝（EINVAL） |
| **Workaround** | 只能从应用 lib 目录（只读）加载 .so |
| **参考** | [[qt-harmonyos-platform-limits]] §dlopen |

### 5.4 pthread_cancel 相关 API 无实现

| 影响 | 说明 |
|------|------|
| **受影响库** | 使用 `PTHREAD_CANCEL_DISABLE` / `pthread_cancel()` 的库（如部分嵌入式数据库） |
| **表现** | 宏已定义但函数无实现，链接或运行时失败 |
| **Workaround** | `#undef PTHREAD_CANCEL_DISABLE`，改用协作式终止 |
| **参考** | [[qt-harmonyos-platform-limits]] §pthread_cancel |

### 5.5 无 tzdata

| 影响 | 说明 |
|------|------|
| **受影响库** | 依赖系统时区数据的库（如 Boost.DateTime、ICU 旧版本） |
| **Workaround** | 使用 ICU 后端处理时区 |

### 5.6 系统路径 stat() 返回 EACCES

| 影响 | 说明 |
|------|------|
| **受影响库** | 扫描系统目录的库（如 `find_executable` 类功能） |
| **表现** | `stat("/bin/sh")` 返回 errno=13 |

---

## 6. 系统库可用性

OHOS 系统（MUSL libc）自带以下常用库，可以直接链接，无需交叉编译或部署：

| 库 | 链接名 | 说明 |
|----|--------|------|
| zlib | `-lz` | 压缩库，系统自带 |
| libcrypto | `-lcrypto` | OpenSSL crypto，系统自带 |
| libssl | `-lssl` | OpenSSL SSL，系统自带 |
| libm | `-lm` | 数学库 |
| libc | `-lc` | C 标准库（MUSL） |
| libdl | `-ldl` | 动态链接 |
| libpthread | `-lpthread` | 线程 |

> **注意**：系统自带库的版本可能与桌面 Linux 不同。例如系统 OpenSSL 版本可能较旧。如果应用需要特定版本，仍需交叉编译并部署自定义版本。

```cmake
# 直接链接系统库（无需部署 .so）
target_link_libraries(QtHarmonyApp PRIVATE
    z        # 系统 zlib
    crypto   # 系统 OpenSSL crypto
    ssl      # 系统 OpenSSL SSL
)
```

---

## 7. Header-Only 库

Header-only 库（如 Eigen、nlohmann/json、spdlog header-only 模式、Catch2、{fmt} header-only 模式）**不需要交叉编译或部署**。直接在 CMake 中包含头文件路径即可：

```cmake
# Header-only 库：只需 include 路径
include_directories(${THIRD_PARTY_PREFIX}/eigen3/include)
include_directories(${THIRD_PARTY_PREFIX}/nlohmann-json/include)

# 或使用 add_subdirectory（如果库提供 CMakeLists.txt）
add_subdirectory(${THIRD_PARTY_PREFIX}/nlohmann-json)
target_link_libraries(QtHarmonyApp PRIVATE nlohmann_json::nlohmann_json)
```

---

## 8. vcpkg 参考

Qt 官方博客有一篇关于使用 vcpkg 为鸿蒙编译 C/C++ 库的文章：

- [Building C/C++ libraries for HarmonyOS with vcpkg](https://www.qt.io/blog/building-libraries-for-harmonyos-with-vcpkg)

vcpkg 可以自动化三方库的交叉编译流程。需要自定义 triplet 文件指向 OHOS NDK 工具链。

---

## 9. 已知兼容清单

> 此清单随实践积累。每次移植新三方库时，更新此表。

| 库 | 版本 | 引入方式 | OHOS 兼容性 | 备注 |
|----|------|---------|-------------|------|
| zlib | 系统自带 | 系统库 `-lz` | 🟢 可用 | 系统自带 |
| OpenSSL (crypto/ssl) | 系统自带 | 系统库 `-lcrypto -lssl` | 🟢 可用 | 系统自带；Qt 编译需额外配置头文件 |
| Eigen | 任意 | Header-only | 🟢 可用 | 纯头文件 |
| nlohmann/json | 任意 | Header-only | 🟢 可用 | 纯头文件 |
| SQLite | 3.x | 源码编译 / 系统 | 🟡 需 patch | 内部可能调用 `chmod()`，需 `#ifndef __OHOS__` 守卫 |
| ICU | 系统自带 | 系统库 | 🟢 可用 | Qt 时区后端依赖 |
| Boost (header-only) | 任意 | Header-only | 🟢 可用 | 纯头文件部分 |
| Boost.Filesystem | 任意 | 源码编译 | ⚠️ 确认有风险 | 使用 `chmod()`/`symlink()`，两者在 OHOS 均受限（详见 [[qt-harmonyos-platform-limits]]） |
| protobuf | 任意 | 源码编译 | 🟡 需验证 | 基础功能应可用（无 OHOS 特定限制），但未实际编译测试 |
| libcurl | 任意 | 源码编译 | 🟡 需验证 | 依赖 OpenSSL（OHOS 系统自带），网络 API 应兼容，但未实际编译测试 |
| freetype | — | Qt 内置 | 🟢 无需关注 | Qt 6 在 `src/3rdparty/freetype` 中内置 freetype，随 Qt GUI 一起编译 |
| Coin3D 4.0 | — | 预编译 .so | ✅ 已验证 | `libCoin.so.80` (ARM aarch64) 可直接集成，需 `-DCOIN_DLL` + 链接 `libGLv4.so` + `libEGL.so`。详见 [[coin3d-quarter-ohos]] |
| Quarter 1.2.3 | — | 源码编译 | ✅ 已验证 | 依赖 Coin3D + Qt5::Widgets/OpenGL，需移除 UiTools、自定义 FindOpenGL.cmake。详见 [[coin3d-quarter-ohos]] |
| QScintilla | 2.11.6 | 源码编译 (qmake) | ✅ 已验证 | 代码编辑器组件（含语法高亮），纯 QtCore/Gui/Widgets/PrintSupport 依赖，OHOS 交叉编译需自定义 mkspec (ohos-clang-win) 和短路径。无需源码修改 |

---

## 10. 迁移评估检查清单

移植 Qt 应用时，在 [[qt-ohos-project-analyzer-workflow]] §3.4 的基础上，对每个三方库逐项确认：

- [ ] **列出所有三方库**：库名、版本、功能、引入方式
- [ ] **分类**：header-only / 源码编译 / 预编译 / 系统库
- [ ] **源码编译的库**：是否使用 CMake？是否可配置 OHOS 工具链？
- [ ] **平台限制检查**：源码中是否使用了 `chmod()`/`symlink()`/`dlopen()`/`pthread_cancel()`？
- [ ] **交叉编译**：使用 OHOS NDK 工具链编译通过？
- [ ] **.so 部署**：编译产出的 .so 已复制到 `entry/libs/arm64-v8a/`？
- [ ] **CMake 集成**：`CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH` 已设置？
- [ ] **系统库**：是否可以直接使用系统版本，无需自带？
- [ ] **静态链接**：是否可以用静态链接避免 .so 部署问题？
- [ ] **验证**：编译通过 + 运行时 .so 加载成功 + 功能正常？

---

## 参考来源

- [Building Qt for HarmonyOS](https://wiki.qt.io/Building_Qt_for_HarmonyOS) — Qt 交叉编译工具链配置（可复用于三方库）
- [Building C/C++ libraries for HarmonyOS with vcpkg (Qt Blog)](https://www.qt.io/blog/building-libraries-for-harmonyos-with-vcpkg) — vcpkg 三方库编译参考
- [HarmonyOS Platform Limitations](https://wiki.qt.io/Qt_for_HarmonyOS/platform_limitations) — 平台限制详情（影响三方库兼容性）
- [Qt for HarmonyOS Project Structure](../semantic/qt-harmonyos-project-structure.md) — .so 部署目录和 CMake 配置
