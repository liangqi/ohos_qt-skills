# qbittorrent 依赖对账报告（portgraph E2E）

> 生成时间: 2026-09-19T14:32:24Z | 语料: corpus.json#qbittorrent | 构建系统: cmake | 源文件: 710
> Oracle: INSTALL（复核: 已复核，7 条；来源: 手工编写：依赖清单在仓库根 INSTALL 文件（无扩展名，corpus oracle_files 误配为 INSTALL.md；且为纯文本编号列表非 markdown 标题，自动提取器无法解析）。已逐条对照 INSTALL 原文复核。）

## 1. 结论速览

| 指标 | 值 |
|---|---|
| 可移植性 verdict | **blocked**（阻塞 4 / 未知 1 / 平台排除 0） |
| 检出召回率 | 100%（5/5 README 运行时依赖） |
| 检出精确率 | 100% |
| Bug 候选 | **0**（无） |
| 依赖闭包 | 19 项（cmd_only 1, need_port 1, provided 8, target 1, would_download 8） |

**Agent 复核说明**：

- 第二轮复核（worker3-deps-test，基线 f98a2e7）：首轮 2 个 resolution-gap（libtorrentrasterbar / systemd）均已确认根因并修复。1) libtorrentrasterbar 幽灵节点 = find_package(LibtorrentRasterbar)（CheckPackages.cmake:6，CamelCase 压平名）与 pkg_check_modules(libtorrent-rasterbar)（同文件 L9，连字符名）同库异名未归并——修复：project_scanner._link_third_party 按去分隔符键分组归并 + kb_seed.build_dashless_index 兜底解析（CamelCase 压平名 → 已知连字符包名，键长≥6 防碰撞）。libtorrent-rasterbar 确实不在 hb-core/cmd-pkgs（cmd-pkgs 仅异库 libtorrent-rakshasa，dashless 键不同不会误映射），保留单个 pkg-unknown:libtorrent-rasterbar 幽灵节点是正确结论（need_port），其版本约束 >= 2.0.10 因 CMake 宏参 ${version} 无法静态解析（残留项）。
- 2) systemd 幽灵节点 = find_package(Systemd)（dist/unix/CMakeLists.txt:3）被 if (SYSTEMD) 守卫，而 SYSTEMD 由 feature_option_dependent(... OFF "NOT GUI" OFF) 声明且默认 OFF（GUI 默认 ON），且该 find_package 仅用于探测服务文件安装目录（不链接）——修复：qt_scanner 新增 CMake 选项守卫分析（option/feature_option[_dependent]/cmake_dependent_option 默认值收集 + if 栈逐行追踪 + Find<Name>.cmake 模块继承调用处守卫），守卫内声明连 optional 边；optional 边不进入 runtime 闭包/可移植性分析/fetch-deps。前置根因：dist 目录被 EXCLUDE_DIRS 排除导致守卫上下文丢失（qBittorrent add_subdirectory(dist) 是真实构建子目录），已移除该排除。
- 上轮遗留的 harness 取证缺陷已修复：name_variants 对含 @version 的节点名（openssl@3）追加剥离变体，避免 grep 不到 find_package(OpenSSL) 而误判 false-positive。
- oracle 说明（沿首轮）：依赖清单在仓库根 INSTALL 文件（纯文本编号列表，corpus oracle_files 曾误配 INSTALL.md），本 oracle 为 agent 逐条对照 INSTALL 原文手工编写（7 条：5 runtime + 1 build + 1 optional），已复核。

## 2. 可移植性判定（analyze）

| 阻塞类型 | 节点 | 原因 |
|---|---|---|
| unsupported-interface | app:qbittorrent | 使用鸿蒙不支持的平台接口 macOS Cocoa/AppKit（os-api）macOS 专属 UI/系统框架；同类鸿蒙替代接口: POSIX/musl C 库、pthread 多线程、dlopen 动态加载、macOS 系统库绑定、glib 事件循环［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-ac |
| unsupported-interface | app:qbittorrent | 使用鸿蒙不支持的平台接口 D-Bus IPC（ipc）鸿蒙无 D-Bus（Qt D-Bus 模块 Out of scope）；需改用系统服务/IPC；同类鸿蒙替代接口: 鸿蒙 IPC/系统服务能力［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-active (10 处无条件 / 11 处鸿蒙可编译 /  |
| unsupported-interface | app:qbittorrent | 使用鸿蒙不支持的平台接口 Win32 API（os-api）Windows 专属系统接口；同类鸿蒙替代接口: POSIX/musl C 库、pthread 多线程、dlopen 动态加载、macOS 系统库绑定、glib 事件循环［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-active (3 处无条 |
| unsupported-module | qtmod:dbus | Qt for HarmonyOS 模块适配表: 不支持 - 鸿蒙无 D-Bus |

未确认项 1 个：
- [unknown-package] pkg-unknown:libtorrent-rasterbar: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单

## 3. 差异归因明细（oracle × portgraph 直接依赖）

| 归类 | README 侧 | portgraph 侧 | 类型/深度 | 证据/说明 |
|---|---|---|---|---|
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
| 一致 | libtorrent-rasterbar | libtorrent-rasterbar | package d1 | 匹配到幽灵节点：真实外部依赖且无已知鸿蒙包（fetch-deps 报 need_port/需源码移植，检出正确） |
| 一致 | openssl | openssl@3 | package d1 |  |
| 一致 | qt | Qt Core | qt-module d1 |  |
| 一致 | zlib | zlib | package d1 |  |

归类统计：构建工具×1，一致×5，可选未启用×1，粒度折叠×7

## 4. 依赖闭包概览（fetch-deps --dry-run）

- 闭包总数 19 项：cmd_only 1，need_port 1，provided 8，target 1，would_download 8
- 可直下 bottle：boost、openssl@3、zlib、icu4c@78、xz、zstd、zlib-ng-compat、lz4
- 仅命令获取（cmd_only）：ca-certificates
- 需自行移植（need_port）：libtorrent-rasterbar
  - libtorrent-rasterbar: ?

## 5. 直接依赖全量清单（portgraph depth-1）

| 节点 | 类型 | 边 | port_status | 深度 |
|---|---|---|---|---|
| boost | package | runtime | ported | 1 |
| libtorrent-rasterbar | package | runtime | unknown | 1 |
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
