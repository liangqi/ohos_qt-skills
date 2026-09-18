# tdesktop 依赖对账报告（portgraph E2E）

> 生成时间: 2026-09-18T02:44:23Z | 语料: corpus.json#tdesktop | 构建系统: ? | 源文件: ?
> Oracle: README.md（复核: 已复核，20 条；来源: README §Third-party 逐条人工复核：剥离许可后缀噪声；GYP/Ninja/CMake 改 build 型；Open Sans/Vazirmatn 字体与 Emoji alpha codes 为数据资产（非链接依赖）已删）

## 1. 结论速览

| 指标 | 值 |
|---|---|
| 可移植性 verdict | **blocked**（阻塞 2 / 未知 1 / 平台排除 0） |
| 检出召回率 | 24%（4/17 README 运行时依赖） |
| 检出精确率 | 100% |
| Bug 候选 | **7**（missed-dep=7） |
| 依赖闭包 | 35 项（cmd_only 2, provided 5, target 1, would_download 27） |

**Agent 复核说明**：

- 核心发现：tdesktop 的外部依赖几乎全部以 desktop-app::external_* 前缀目标名经 target_link_libraries 集成，真正的 find_package 位于未初始化的 cmake/（cmake_helpers）子模块——portgraph 的 CMake 包检测对此类工程接近失明，openssl/zlib/ffmpeg 仅靠 include 启发式检出；建议扫描器增加 target_link_libraries 目标名解析（剥 external_/lib_/命名空间前缀）并提取 .gitmodules 子模块依赖
- opus/hunspell/liblzma/gsl/range-v3/lzma-sdk 的『README过时』并非 README 过时：均为 vendored 子模块（.gitmodules 声明）或经缺失的 cmake_helpers/外部 Libraries 目录集成，仓库内构建文件确无裸名引用，属当前扫描范围之外
- harness 取证 grep 的词边界（\b）无法匹配 external_zlib/external_openal 等下划线连写目标名，曾致 zlib 被误判 ★误报（实际 SourceFiles/_other/packer.h:18 有 #include <zlib.h>，且 4 处 target_link_libraries 链接 external_zlib）；建议 grep 变体增加剥前缀形式（external_/lib_）

## 2. 可移植性判定（analyze）

| 阻塞类型 | 节点 | 原因 |
|---|---|---|
| unsupported-interface | app:tdesktop | 使用鸿蒙不支持的平台接口 macOS Cocoa/AppKit（os-api）macOS 专属 UI/系统框架；同类鸿蒙替代接口: POSIX/musl C 库、pthread 多线程、dlopen 动态加载、macOS 系统库绑定、glib 事件循环［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-ac |
| unsupported-interface | app:tdesktop | 使用鸿蒙不支持的平台接口 Win32 API（os-api）Windows 专属系统接口；同类鸿蒙替代接口: POSIX/musl C 库、pthread 多线程、dlopen 动态加载、macOS 系统库绑定、glib 事件循环［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-active (54 处无 |

未确认项 1 个：
- [unknown-interface] app:tdesktop: 平台接口 fork()/exec() 进程模型 的鸿蒙支持性未确认（guard=ohos-active）

## 3. 差异归因明细（oracle × portgraph 直接依赖）

| 归类 | README 侧 | portgraph 侧 | 类型/深度 | 证据/说明 |
|---|---|---|---|---|
| ★漏检 | webrtc | — | runtime | README 声明但构建文件无引用 → 疑似 README 过时/笔误 【agent: Telegram/cmake/lib_tgcalls.cmake:212、td_ui.cmake:739 target_link_libraries(… desktop-app::external_webrtc) → portgraph 漏检】 |
| ★漏检 | breakpad | — | runtime | README 声明但构建文件无引用 → 疑似 README 过时/笔误 【agent: Telegram/CMakeLists.txt:2381 target_link_frameworks(Telegram PRIVATE Breakpad)（macstore 段）；Linux 侧经缺失子模块的 external_crash_reports 集成 → 漏检】 |
| ★漏检 | crashpad | — | runtime | README 声明但构建文件无引用 → 疑似 README 过时/笔误 【agent: Telegram/CMakeLists.txt:2349 find_program(CRASHPAD_HANDLER crashpad_handler)（macOS 段）+ :97 external_crash_reports → 漏检（主集成在缺失 cmake/ 子模块）】 |
| ★漏检 | openal | — | runtime | README 声明但构建文件无引用 → 疑似 README 过时/笔误 【agent: Telegram/CMakeLists.txt:100 target_link_libraries(Telegram … desktop-app::external_openal)（词边界 grep 匹配不到前缀目标名）→ portgraph 漏检】 |
| ★漏检 | xxhash | — | runtime | README 声明但构建文件无引用 → 疑似 README 过时/笔误 【agent: Telegram/CMakeLists.txt:101 target_link_libraries(… desktop-app::external_xxhash)，且 .gitmodules 声明 ThirdParty/xxHash 子模块 → portgraph 漏检】 |
| ★漏检 | qr-code-generator | — | runtime | README 声明但构建文件无引用 → 疑似 README 过时/笔误 【agent: Telegram/CMakeLists.txt:96 target_link_libraries(… desktop-app::external_qr_code_generator) → portgraph 漏检】 |
| ★漏检 | ada | — | runtime | README 声明但构建文件无引用 → 疑似 README 过时/笔误 【agent: Telegram/cmake/td_iv.cmake:175 target_link_libraries(td_iv … desktop-app::external_ada) → portgraph 漏检】 |
| README过时 | lzma-sdk | — | runtime | README 声明但构建文件无引用 → 疑似 README 过时/笔误 |
| README过时 | liblzma | — | runtime | README 声明但构建文件无引用 → 疑似 README 过时/笔误 |
| README过时 | opus | — | runtime | README 声明但构建文件无引用 → 疑似 README 过时/笔误 |
| README过时 | gsl | — | runtime | README 声明但构建文件无引用 → 疑似 README 过时/笔误 |
| README过时 | range-v3 | — | runtime | README 声明但构建文件无引用 → 疑似 README 过时/笔误 |
| README过时 | hunspell | — | runtime | README 声明但构建文件无引用 → 疑似 README 过时/笔误 |
| 构建工具 | gyp | — | build | 构建工具，fetch-deps 不收 build 边 |
| 构建工具 | ninja | — | build | 构建工具，fetch-deps 不收 build 边 |
| 构建工具 | cmake | — | build | 构建工具，fetch-deps 不收 build 边 |
| 粒度折叠 | — | Qt GUI | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt Network | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt SVG | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt Widgets | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 一致 | qt | Qt Core | qt-module d1 |  |
| 一致 | openssl | openssl@3 | package d1 |  |
| 一致 | zlib | zlib | package d1 |  |
| 一致 | ffmpeg | ffmpeg | package d1 |  |

归类统计：构建工具×3，一致×4，★漏检×7，粒度折叠×4，README过时×6

## 4. 依赖闭包概览（fetch-deps --dry-run）

- 闭包总数 35 项：cmd_only 2，provided 5，target 1，would_download 27
- 可直下 bottle：ffmpeg、openssl@3、zlib、lame、libvpx、opus、svt-av1、x264、x265、alsa-lib、libxcb、xz、zlib-ng-compat、mpg123、python@3.14、libxau、libxdmcp、mpdecimal、sqlite、zstd、gettext、util-linux、musl-compat、xorgproto、readline、lz4、libunistring
- 仅命令获取（cmd_only）：dav1d、ca-certificates

## 5. 直接依赖全量清单（portgraph depth-1）

| 节点 | 类型 | 边 | port_status | 深度 |
|---|---|---|---|---|
| ffmpeg | package | runtime | ported | 1 |
| openssl@3 | package | runtime | ported | 1 |
| zlib | package | runtime | ported | 1 |
| Qt Core | qt-module | uses-module | ported | 1 |
| Qt GUI | qt-module | uses-module | ported | 1 |
| Qt Network | qt-module | uses-module | ported | 1 |
| Qt SVG | qt-module | uses-module | ported | 1 |
| Qt Widgets | qt-module | uses-module | ported | 1 |

## 6. 方法说明

- 对比口径：portgraph 直接依赖（depth-1 边）vs README/INSTALL 声明依赖；闭包仅做产物概览。
- 归因证据：对未匹配项自动 grep 克隆仓库构建文件（find_package/pkg_check_modules/target_link_libraries/vcpkg 等）。
- ★ 类（missed-dep / resolution-gap / false-positive）为 bug 候选，需人工确认；其余为预期差异。
- agent 可读报告：`./portgraph\tests\e2e\reports\tdesktop.report.json`
