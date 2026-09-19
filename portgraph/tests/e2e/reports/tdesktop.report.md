# tdesktop 依赖对账报告（portgraph E2E）

> 生成时间: 2026-09-19T14:06:35Z | 语料: corpus.json#tdesktop | 构建系统: cmake | 源文件: 2932
> Oracle: README.md（复核: 已复核，20 条；来源: README §Third-party 逐条人工复核：剥离许可后缀噪声；GYP/Ninja/CMake 改 build 型；Open Sans/Vazirmatn 字体与 Emoji alpha codes 为数据资产（非链接依赖）已删）

## 1. 结论速览

| 指标 | 值 |
|---|---|
| 可移植性 verdict | **blocked**（阻塞 2 / 未知 8 / 平台排除 0） |
| 检出召回率 | 53%（9/17 README 运行时依赖） |
| 检出精确率 | 64% |
| Bug 候选 | **2**（missed-dep=2） |
| 依赖闭包 | 60 项（cmd_only 1, need_port 7, provided 5, target 1, would_download 46） |

**Agent 复核说明**：

- 本轮（tdesktop deps-test）已修复：扫描器现解析 target_link_libraries 的 ns::external_<name> 导入目标名（剥前缀→raw_libs ext_target）并连边/建幽灵，openal/xxhash/webrtc/ada/qr-code-generator 等不再需要人工重分类
- gsl/range-v3/hunspell 等为 .gitmodules 自带子模块（vendored，随项目编译），harness 现按 .gitmodules 证据自动归 vendored 类
- breakpad/crashpad 的残留缺口根因：shallow clone 未初始化子模块（cmake/ 即 cmake_helpers），其内部的 find_package/breakpad-cp 选择逻辑不可见；完整方案需 'clone --recurse-submodules' 或按 .gitmodules 提示的缺失路径降级处理，见 TEST-REPORT 残留项
- lzma-sdk/liblzma/opus：主仓库构建文件确无引用（liblzma/opus 由 cmake_helpers 的外部 Libraries 预编译目录或 tg_owt 栈带入），readme-stale 归类符合当前扫描范围事实

## 2. 可移植性判定（analyze）

| 阻塞类型 | 节点 | 原因 |
|---|---|---|
| unsupported-interface | app:tdesktop | 使用鸿蒙不支持的平台接口 macOS Cocoa/AppKit（os-api）macOS 专属 UI/系统框架；同类鸿蒙替代接口: POSIX/musl C 库、pthread 多线程、dlopen 动态加载、macOS 系统库绑定、glib 事件循环［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-ac |
| unsupported-interface | app:tdesktop | 使用鸿蒙不支持的平台接口 Win32 API（os-api）Windows 专属系统接口；同类鸿蒙替代接口: POSIX/musl C 库、pthread 多线程、dlopen 动态加载、macOS 系统库绑定、glib 事件循环［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-active (54 处无 |

未确认项 8 个：
- [unknown-interface] app:tdesktop: 平台接口 fork()/exec() 进程模型 的鸿蒙支持性未确认（guard=ohos-active）
- [unknown-package] pkg-unknown:libudev: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:ada: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:auto-updates: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:crash-reports: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:rnnoise: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:tde2e: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:webrtc: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单

## 3. 差异归因明细（oracle × portgraph 直接依赖）

| 归类 | README 侧 | portgraph 侧 | 类型/深度 | 证据/说明 |
|---|---|---|---|---|
| ★漏检 | breakpad | — | runtime | README 声明但构建文件无引用 → 疑似 README 过时/笔误 【agent: 主集成位于未初始化的 cmake/（cmake_helpers）子模块：Linux 侧经 external_crash_reports 包装（CMakeLists.txt:97 链接、cmake_helpers 内部实现 breakpad/crashpad 二选一），主仓库仅 macstore 段 target |
| ★漏检 | crashpad | — | runtime | README 声明但构建文件无引用 → 疑似 README 过时/笔误 【agent: 主集成位于未初始化的 cmake/（cmake_helpers）子模块：macOS 段 find_program(CRASHPAD_HANDLER crashpad_handler)（:2349）+ external_crash_reports（:97）→ 克隆未初始化子模块导致扫描范围外，属工具残留缺口（见  |
| README过时 | lzma-sdk | — | runtime | README 声明但构建文件无引用 → 疑似 README 过时/笔误 |
| README过时 | liblzma | — | runtime | README 声明但构建文件无引用 → 疑似 README 过时/笔误 |
| README过时 | opus | — | runtime | README 声明但构建文件无引用 → 疑似 README 过时/笔误 |
| README漏列 | — | boost | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | cmark-gfm | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | glib | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | libfido2 | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | minizip | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| 构建工具 | gyp | — | build | 构建工具，fetch-deps 不收 build 边 |
| 构建工具 | ninja | — | build | 构建工具，fetch-deps 不收 build 边 |
| 构建工具 | cmake | — | build | 构建工具，fetch-deps 不收 build 边 |
| 粒度折叠 | — | Qt GUI | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt Network | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt SVG | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt Widgets | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 一致 | qt | Qt Core | qt-module d1 |  |
| 一致 | openssl | openssl@3 | package d1 |  |
| 一致 | webrtc | webrtc | package d1 | 匹配到幽灵节点：真实外部依赖且无已知鸿蒙包（fetch-deps 报 need_port/需源码移植，检出正确） |
| 一致 | zlib | zlib | package d1 |  |
| 一致 | openal | openal-soft | package d1 |  |
| 一致 | ffmpeg | ffmpeg | package d1 |  |
| 一致 | xxhash | xxhash | package d1 |  |
| 一致 | qr-code-generator | libqrcodegen | package d1 |  |
| 一致 | ada | ada | package d1 | 匹配到幽灵节点：真实外部依赖且无已知鸿蒙包（fetch-deps 报 need_port/需源码移植，检出正确） |
| 自带子模块 | gsl | — | runtime |  .gitmodules 自带子模块（Telegram/ThirdParty/GSL → https://github.com/Microsoft/GSL.git）：随项目源码一起编译，不作为外部包获取/检测 |
| 自带子模块 | range-v3 | — | runtime |  .gitmodules 自带子模块（Telegram/ThirdParty/range-v3 → https://github.com/ericniebler/range-v3.git）：随项目源码一起编译，不作为外部包获取/检测 |
| 自带子模块 | hunspell | — | runtime |  .gitmodules 自带子模块（Telegram/ThirdParty/hunspell → https://github.com/hunspell/hunspell）：随项目源码一起编译，不作为外部包获取/检测 |
| 未知包(正常) | — | auto_updates | package d1 | 未匹配到已知鸿蒙包：真实外部依赖，幽灵节点为正确检出（fetch-deps 报 need_port/需源码移植） |
| 未知包(正常) | — | crash_reports | package d1 | 未匹配到已知鸿蒙包：真实外部依赖，幽灵节点为正确检出（fetch-deps 报 need_port/需源码移植） |
| 未知包(正常) | — | libudev | package d1 | 未匹配到已知鸿蒙包：真实外部依赖，幽灵节点为正确检出（fetch-deps 报 need_port/需源码移植） |
| 未知包(正常) | — | rnnoise | package d1 | 未匹配到已知鸿蒙包：真实外部依赖，幽灵节点为正确检出（fetch-deps 报 need_port/需源码移植） |
| 未知包(正常) | — | tde2e | package d1 | 未匹配到已知鸿蒙包：真实外部依赖，幽灵节点为正确检出（fetch-deps 报 need_port/需源码移植） |

归类统计：构建工具×3，一致×9，★漏检×2，粒度折叠×4，README漏列×5，README过时×3，未知包(正常)×5，自带子模块×3

## 4. 依赖闭包概览（fetch-deps --dry-run）

- 闭包总数 60 项：cmd_only 1，need_port 7，provided 5，target 1，would_download 46
- 可直下 bottle：libfido2、ffmpeg、openssl@3、zlib、boost、cmark-gfm、glib、minizip、openal-soft、libqrcodegen、xxhash、dav1d、lame、libvpx、opus、svt-av1、x264、x265、alsa-lib、libxcb、xz、zlib-ng-compat、icu4c@78、zstd、bison、python-setuptools、pcre2、dbus、util-linux、mpg123、python@3.14、libxau、libxdmcp、lz4、python@3.12、gettext、readline、mpdecimal、sqlite、musl-compat
- 仅命令获取（cmd_only）：ca-certificates
- 需自行移植（need_port）：libudev、ada、auto_updates、crash_reports、rnnoise、tde2e、webrtc
  - libudev: ?
  - ada: ?
  - auto_updates: ?
  - crash_reports: ?
  - rnnoise: ?
  - tde2e: ?
  - webrtc: ?

## 5. 直接依赖全量清单（portgraph depth-1）

| 节点 | 类型 | 边 | port_status | 深度 |
|---|---|---|---|---|
| ada | package | runtime | unknown | 1 |
| auto_updates | package | runtime | unknown | 1 |
| boost | package | runtime | ported | 1 |
| cmark-gfm | package | runtime | ported | 1 |
| crash_reports | package | runtime | unknown | 1 |
| ffmpeg | package | runtime | ported | 1 |
| glib | package | runtime | ported | 1 |
| libfido2 | package | runtime | ported | 1 |
| libqrcodegen | package | runtime | ported | 1 |
| libudev | package | runtime | unknown | 1 |
| minizip | package | runtime | ported | 1 |
| openal-soft | package | runtime | ported | 1 |
| openssl@3 | package | runtime | ported | 1 |
| rnnoise | package | runtime | unknown | 1 |
| tde2e | package | runtime | unknown | 1 |
| webrtc | package | runtime | unknown | 1 |
| xxhash | package | runtime | ported | 1 |
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
- agent 可读报告：`/root/harmony-workspace/worker3/portgraph/tests/e2e/reports/tdesktop.report.json`
