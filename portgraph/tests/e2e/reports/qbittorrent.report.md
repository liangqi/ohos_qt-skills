# qbittorrent 依赖对账报告（portgraph E2E）

> 生成时间: 2026-09-19T12:49:14Z | 语料: corpus.json#qbittorrent | 构建系统: cmake | 源文件: 710
> Oracle: INSTALL（复核: 已复核，7 条；来源: 手工编写：依赖清单在仓库根 INSTALL 文件（无扩展名，corpus oracle_files 误配为 INSTALL.md；且为纯文本编号列表非 markdown 标题，自动提取器无法解析）。已逐条对照 INSTALL 原文复核。）

## 1. 结论速览

| 指标 | 值 |
|---|---|
| 可移植性 verdict | **blocked**（阻塞 4 / 未知 1 / 平台排除 0） |
| 检出召回率 | 80%（4/5 README 运行时依赖） |
| 检出精确率 | 100% |
| Bug 候选 | **2**（missed-dep=1, resolution-gap=1） |
| 依赖闭包 | 19 项（cmd_only 1, need_port 1, provided 8, target 1, would_download 8） |

**Agent 复核说明**：

- missed-dep libtorrent-rasterbar 复核确认为 portgraph 真漏检：全部 find_package/pkg_check_modules 集中在 cmake/Modules/CheckPackages.cmake（L6 find_package(LibtorrentRasterbar QUIET...)、L9 pkg_check_modules(...libtorrent-rasterbar>=...)、L35 find_package(...REQUIRED)），而 port_graph/qt_scanner.py L120-121 把 cmake_files 过滤为仅 CMakeLists.txt、丢弃全部 .cmake 模块文件；include 启发式 THIRD_PARTY_HINTS 亦无 libtorrent 模式（源码大量 #include <libtorrent/...>）。libtorrent-rasterbar 是 qBittorrent 核心 BT 引擎库，漏检导致闭包与 need_port 清单缺失最大项，保留 ★ 不改判。
- 首跑 false-positive openssl@3 为 harness 取证缺陷而非 portgraph 误报：name_variants 对节点名 openssl@3 未生成去 @3 变体，grep 不到 CheckPackages.cmake:47 的 find_package(OpenSSL)；oracle 复核补全后 pass1 正确匹配（precision 0%→100%）。建议 name_variants 对含 @ 的节点名追加剥离 @version 的变体。
- 解析层预备缺口：hb-core Formula 与 cmd-pkgs 均无 libtorrent-rasterbar（cmd-pkgs 仅同名异库 libtorrent-rakshasa，即 INSTALL 原文警告的 rTorrent 用库）——即使修复 .cmake 扫描，该包仍会落入 pkg-unknown/need_port，且 resolve 不应误映射到 rakshasa。
- oracle 自动提取失败根因：依赖清单在仓库根 INSTALL 文件（无扩展名），corpus oracle_files 误配为 INSTALL.md；且 INSTALL 为纯文本编号列表（非 markdown 标题），即使文件名配对启发式也解析不了。本 oracle 为 agent 逐条对照 INSTALL 原文手工编写（7 条：5 runtime + 1 build + 1 optional）。

## 2. 可移植性判定（analyze）

| 阻塞类型 | 节点 | 原因 |
|---|---|---|
| unsupported-interface | app:qbittorrent | 使用鸿蒙不支持的平台接口 macOS Cocoa/AppKit（os-api）macOS 专属 UI/系统框架；同类鸿蒙替代接口: POSIX/musl C 库、pthread 多线程、dlopen 动态加载、macOS 系统库绑定、glib 事件循环［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-ac |
| unsupported-interface | app:qbittorrent | 使用鸿蒙不支持的平台接口 D-Bus IPC（ipc）鸿蒙无 D-Bus（Qt D-Bus 模块 Out of scope）；需改用系统服务/IPC；同类鸿蒙替代接口: 鸿蒙 IPC/系统服务能力［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-active (10 处无条件 / 11 处鸿蒙可编译 /  |
| unsupported-interface | app:qbittorrent | 使用鸿蒙不支持的平台接口 Win32 API（os-api）Windows 专属系统接口；同类鸿蒙替代接口: POSIX/musl C 库、pthread 多线程、dlopen 动态加载、macOS 系统库绑定、glib 事件循环［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-active (3 处无条 |
| unsupported-module | qtmod:dbus | Qt for HarmonyOS 模块适配表: 不支持 - 鸿蒙无 D-Bus |

未确认项 1 个：
- [unknown-package] pkg-unknown:libtorrentrasterbar: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单

## 3. 差异归因明细（oracle × portgraph 直接依赖）

| 归类 | README 侧 | portgraph 侧 | 类型/深度 | 证据/说明 |
|---|---|---|---|---|
| ★漏检 | libtorrent-rasterbar | — | runtime | README 声明且构建文件引用（strong=3 weak=0），portgraph 未检出 → 扫描器漏检候选 |
| ★解析缺口 | — | LibtorrentRasterbar | package d1 | pkg-unknown 幽灵节点：find_package 名未解析到已知鸿蒙包（ALIASES 缺口） |
| 可选未启用 | python | — | optional | 可选依赖，默认构建未启用 |
| 构建工具 | cmake | — | build | 构建工具，fetch-deps 不收 build 边 |
| 粒度折叠 | — | Qt D-Bus | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt Network | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt SQL | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt SVG | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt Test | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt Widgets | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt XML | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 一致 | boost | boost | package d1 |  |
| 一致 | openssl | openssl@3 | package d1 |  |
| 一致 | qt | Qt Core | qt-module d1 |  |
| 一致 | zlib | zlib | package d1 |  |

归类统计：构建工具×1，一致×4，★漏检×1，可选未启用×1，粒度折叠×7，★解析缺口×1

## 4. 依赖闭包概览（fetch-deps --dry-run）

- 闭包总数 19 项：cmd_only 1，need_port 1，provided 8，target 1，would_download 8
- 可直下 bottle：boost、openssl@3、zlib、icu4c@78、xz、zstd、zlib-ng-compat、lz4
- 仅命令获取（cmd_only）：ca-certificates
- 需自行移植（need_port）：LibtorrentRasterbar
  - LibtorrentRasterbar: ?

## 5. 直接依赖全量清单（portgraph depth-1）

| 节点 | 类型 | 边 | port_status | 深度 |
|---|---|---|---|---|
| boost | package | runtime | ported | 1 |
| LibtorrentRasterbar | package | runtime | unknown | 1 |
| openssl@3 | package | runtime | ported | 1 |
| zlib | package | runtime | ported | 1 |
| Qt Core | qt-module | uses-module | ported | 1 |
| Qt D-Bus | qt-module | uses-module | blocked | 1 |
| Qt Network | qt-module | uses-module | ported | 1 |
| Qt SQL | qt-module | uses-module | ported | 1 |
| Qt SVG | qt-module | uses-module | ported | 1 |
| Qt Test | qt-module | uses-module | ported | 1 |
| Qt Widgets | qt-module | uses-module | ported | 1 |
| Qt XML | qt-module | uses-module | ported | 1 |

## 6. 方法说明

- 对比口径：portgraph 直接依赖（depth-1 边）vs README/INSTALL 声明依赖；闭包仅做产物概览。
- 归因证据：对未匹配项自动 grep 克隆仓库构建文件（find_package/pkg_check_modules/target_link_libraries/vcpkg 等）。
- ★ 类（missed-dep / resolution-gap / false-positive）为 bug 候选，需人工确认；其余为预期差异。
- agent 可读报告：`/root/harmony-workspace/worker4/portgraph/tests/e2e/reports/qbittorrent.report.json`
