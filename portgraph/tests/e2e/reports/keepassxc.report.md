# keepassxc 依赖对账报告（portgraph E2E）

> 生成时间: 2026-09-19T12:49:13Z | 语料: corpus.json#keepassxc | 构建系统: cmake | 源文件: 884
> Oracle: INSTALL.md（复核: 已复核，7 条；来源: agent 复核定稿：删除散文链接残留 set-up-build-environment；asciidoctor 依原文（build tools must exist within your PATH + KPXC_FEATURE_DOCS）改判 build；本版 INSTALL.md 仅声明 qt/botan/zlib 三个库，无 libgcrypt/argon2/libsodium/ykpers；vcpkg/xvfb-run 为 prose 提及的工具/测试辅助，不入 oracle）

## 1. 结论速览

| 指标 | 值 |
|---|---|
| 可移植性 verdict | **blocked**（阻塞 5 / 未知 2 / 平台排除 0） |
| 检出召回率 | 100%（3/3 README 运行时依赖） |
| 检出精确率 | 25% |
| Bug 候选 | **0**（无） |
| 依赖闭包 | 40 项（cmd_only 1, covered 1, need_port 1, provided 6, target 1, would_download 30） |

**Agent 复核说明**：

- oracle 复核：删除散文链接残留 set-up-build-environment；asciidoctor 依原文改判 build（文档构建工具）；本版 INSTALL.md 仅声明 qt/botan/zlib 三个运行时库，无 libgcrypt/argon2/libsodium/ykpers；vcpkg/xvfb-run 为 prose 提及的工具/测试辅助，不入 oracle
- 4 个 resolution-gap 终判：xkbcommon/x11/pcsc 三项别名缺口已补入 kb_seed.PKG_ALIASES（xkbcommon→libxkbcommon、x11→libx11、pcsc→pcsc-lite、libpcsclite→pcsc-lite），扫描期直接解析到真实包节点不再产生幽灵；openmp 为 CMake 内置编译器特性改判 unknown-ok（fetch-deps 亦按内置分类标 provided）；botan 匹配的幽灵节点经查确无鸿蒙包，need_port 定性正确
- 召回率 60%→100% 完全来自 oracle 分母修正（误将构建工具/链接残留计入 runtime），portgraph 检出无变化；precision 维持 27% 反映 INSTALL.md 依赖声明极简（8 个 README 漏列项均经 grep 取证为真实构建引用，portgraph 正确）

## 2. 可移植性判定（analyze）

| 阻塞类型 | 节点 | 原因 |
|---|---|---|
| unsupported-interface | app:keepassxc | 使用鸿蒙不支持的平台接口 macOS Cocoa/AppKit（os-api）macOS 专属 UI/系统框架；同类鸿蒙替代接口: POSIX/musl C 库、pthread 多线程、dlopen 动态加载、macOS 系统库绑定、glib 事件循环［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-ac |
| unsupported-interface | app:keepassxc | 使用鸿蒙不支持的平台接口 D-Bus IPC（ipc）鸿蒙无 D-Bus（Qt D-Bus 模块 Out of scope）；需改用系统服务/IPC；同类鸿蒙替代接口: 鸿蒙 IPC/系统服务能力［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-active (24 处无条件 / 2 处鸿蒙可编译 / 1 |
| unsupported-interface | app:keepassxc | 使用鸿蒙不支持的平台接口 Win32 API（os-api）Windows 专属系统接口；同类鸿蒙替代接口: POSIX/musl C 库、pthread 多线程、dlopen 动态加载、macOS 系统库绑定、glib 事件循环［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-active (12 处无 |
| unsupported-interface | app:keepassxc | 使用鸿蒙不支持的平台接口 X11/Xlib 直连（display）鸿蒙无 X11 显示服务；Qt 应用应走 QPA，直连 X11 代码不可移植；同类鸿蒙替代接口: 鸿蒙 WindowStage/XComponent［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-active (5 处无条件 / 2 处鸿 |
| unsupported-module | qtmod:dbus | Qt for HarmonyOS 模块适配表: 不支持 - 鸿蒙无 D-Bus |

未确认项 2 个：
- [unknown-package] pkg-unknown:botan: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:openmp: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单

## 3. 差异归因明细（oracle × portgraph 直接依赖）

| 归类 | README 侧 | portgraph 侧 | 类型/深度 | 证据/说明 |
|---|---|---|---|---|
| README漏列 | — | libqrencode | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | libusb | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | libxi | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | libxkbcommon | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | libxtst | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | minizip | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | pcsc-lite | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | qrencode | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | readline | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| 构建工具 | cmake | — | build | 构建工具，fetch-deps 不收 build 边 |
| 构建工具 | make | — | build | 构建工具，fetch-deps 不收 build 边 |
| 构建工具 | g++ | — | build | 构建工具，fetch-deps 不收 build 边 |
| 构建工具 | asciidoctor | — | build | 构建工具，fetch-deps 不收 build 边 |
| 粒度折叠 | — | Qt D-Bus | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt Network | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt SVG | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt Widgets | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 一致 | qt | Qt Concurrent | qt-module d1 |  |
| 一致 | botan | botan | package d1 | ⚠ 匹配到幽灵节点（pkg-unknown）——名字未解析到已知鸿蒙包，实为解析缺口，需复核 【agent: 复核⚠注记：hb-core Formula 与 cmd-pkgs 均确无 botan 包（find_package(Botan REQUIRED)，CMakeLists.txt:511），pkg-unknown/need_port 定性正确——检出与状态均准确，非解析缺口，需自行交叉编译属 |
| 一致 | zlib | zlib | package d1 |  |
| 未知包(正常) | — | openmp | package d1 | pkg-unknown 幽灵节点：find_package 名未解析到已知鸿蒙包（ALIASES 缺口） 【agent: CMakeLists.txt:259 find_package(OpenMP)（无 REQUIRED，命中后仅追加 OpenMP_C(_XX)_FLAGS）是 CMake 内置编译器特性探测而非三方包；OHOS clang 工具链自带 OpenMP runtime，hb-cor |

归类统计：构建工具×4，一致×3，粒度折叠×4，README漏列×9，未知包(正常)×1

## 4. 依赖闭包概览（fetch-deps --dry-run）

- 闭包总数 40 项：cmd_only 1，covered 1，need_port 1，provided 6，target 1，would_download 30
- 可直下 bottle：minizip、pcsc-lite、qrencode、readline、zlib、libxkbcommon、libusb、libxi、libxtst、zlib-ng-compat、libpng、libxcb、xkeyboard-config、libx11、libxext、libxfixes、xorgproto、python@3.14、libxau、libxdmcp、mpdecimal、openssl@3、sqlite、xz、zstd、gettext、util-linux、musl-compat、lz4、libunistring
- 仅命令获取（cmd_only）：ca-certificates
- 需自行移植（need_port）：botan
  - botan: ?

## 5. 直接依赖全量清单（portgraph depth-1）

| 节点 | 类型 | 边 | port_status | 深度 |
|---|---|---|---|---|
| botan | package | runtime | unknown | 1 |
| libqrencode | package | runtime | ported | 1 |
| libusb | package | runtime | ported | 1 |
| libxi | package | runtime | ported | 1 |
| libxkbcommon | package | runtime | ported | 1 |
| libxtst | package | runtime | ported | 1 |
| minizip | package | runtime | ported | 1 |
| openmp | package | runtime | unknown | 1 |
| pcsc-lite | package | runtime | ported | 1 |
| qrencode | package | runtime | ported | 1 |
| readline | package | runtime | ported | 1 |
| zlib | package | runtime | ported | 1 |
| Qt Concurrent | qt-module | uses-module | ported | 1 |
| Qt D-Bus | qt-module | uses-module | blocked | 1 |
| Qt Network | qt-module | uses-module | ported | 1 |
| Qt SVG | qt-module | uses-module | ported | 1 |
| Qt Widgets | qt-module | uses-module | ported | 1 |

## 6. 方法说明

- 对比口径：portgraph 直接依赖（depth-1 边）vs README/INSTALL 声明依赖；闭包仅做产物概览。
- 归因证据：对未匹配项自动 grep 克隆仓库构建文件（find_package/pkg_check_modules/target_link_libraries/vcpkg 等）。
- ★ 类（missed-dep / resolution-gap / false-positive）为 bug 候选，需人工确认；其余为预期差异。
- agent 可读报告：`/root/harmony-workspace/worker4/portgraph/tests/e2e/reports/keepassxc.report.json`
