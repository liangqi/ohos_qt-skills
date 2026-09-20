# corpus-a 依赖对账报告（portgraph E2E）

> 生成时间: 2026-09-19T15:12:59Z | 语料: corpus.json#corpus-a | 构建系统: cmake+qmake | 源文件: 6358
> Oracle: README.md（复核: 已复核，20 条；来源: README §Third-party 逐条人工复核：剥离许可后缀噪声；GYP/Ninja/CMake 改 build 型；Open Sans/Vazirmatn 字体与 Emoji alpha codes 为数据资产（非链接依赖）已删）

## 1. 结论速览

| 指标 | 值 |
|---|---|
| 可移植性 verdict | **blocked**（阻塞 7 / 未知 19 / 平台排除 2） |
| 检出召回率 | 71%（12/17 README 运行时依赖） |
| 检出精确率 | 40% |
| Bug 候选 | **3**（false-positive=1, missed-dep=2） |
| 依赖闭包 | 112 项（cmd_only 2, covered 1, need_port 21, provided 9, target 1, would_download 78） |

**Agent 复核说明**：

- 本轮（corpus-a deps-test）已修复：扫描器现解析 target_link_libraries 的 ns::external_<name> 导入目标名（剥前缀→raw_libs ext_target）并连边/建幽灵，openal/xxhash/webrtc/ada/qr-code-generator 等不再需要人工重分类
- gsl/range-v3/hunspell 等为 .gitmodules 自带子模块（vendored，随项目编译），harness 现按 .gitmodules 证据自动归 vendored 类
- breakpad/crashpad 的残留缺口根因：shallow clone 未初始化子模块（cmake/ 即 cmake_helpers），其内部的 find_package/breakpad-cp 选择逻辑不可见；完整方案需 'clone --recurse-submodules' 或按 .gitmodules 提示的缺失路径降级处理，见 TEST-REPORT 残留项
- lzma-sdk/liblzma/opus：主仓库构建文件确无引用（liblzma/opus 由 cmake_helpers 的外部 Libraries 预编译目录或 tg_owt 栈带入），readme-stale 归类符合当前扫描范围事实

## 2. 可移植性判定（analyze）

| 阻塞类型 | 节点 | 原因 |
|---|---|---|
| unsupported-interface | app:corpus-a | 使用鸿蒙不支持的平台接口 macOS Cocoa/AppKit（os-api）macOS 专属 UI/系统框架；同类鸿蒙替代接口: dlopen 动态加载、glib 事件循环、macOS 系统库绑定、POSIX/musl C 库、pthread 多线程［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-ac |
| unsupported-interface | app:corpus-a | 使用鸿蒙不支持的平台接口 D-Bus IPC（ipc）鸿蒙无 D-Bus（Qt D-Bus 模块 Out of scope）；需改用系统服务/IPC；同类鸿蒙替代接口: 鸿蒙 IPC/系统服务能力［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-active (54 处无条件 / 7 处鸿蒙可编译 / 5 |
| unsupported-interface | app:corpus-a | 使用鸿蒙不支持的平台接口 systemd（os-api）鸿蒙无 systemd 服务管理；同类鸿蒙替代接口: dlopen 动态加载、glib 事件循环、macOS 系统库绑定、POSIX/musl C 库、pthread 多线程［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-active (0 处无条 |
| unsupported-interface | app:corpus-a | 使用鸿蒙不支持的平台接口 Win32 API（os-api）Windows 专属系统接口；同类鸿蒙替代接口: dlopen 动态加载、glib 事件循环、macOS 系统库绑定、POSIX/musl C 库、pthread 多线程［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-active (107 处 |
| unsupported-interface | app:corpus-a | 使用鸿蒙不支持的平台接口 X11/Xlib 直连（display）鸿蒙无 X11 显示服务；Qt 应用应走 QPA，直连 X11 代码不可移植；同类鸿蒙替代接口: 鸿蒙 WindowStage/XComponent［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-active (34 处无条件 / 3 处 |
| unsupported-module | qtmod:dbus | Qt for HarmonyOS 模块适配表: 不支持 - 鸿蒙无 D-Bus |
| unsupported-module | qtmod:waylandcompositor | Qt for HarmonyOS 模块适配表: 不支持 - Linux/Wayland 合成器框架，鸿蒙窗口模型非 Wayland |

未确认项 19 个：
- [unknown-interface] app:corpus-a: 平台接口 fork()/exec() 进程模型 的鸿蒙支持性未确认（guard=ohos-active）
- [unknown-package] pkg-unknown:ada: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:microsoft: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:range: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:tde2e: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:tg-owt: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:tl: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:breakpad-client: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:giomm-2-68: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:libudev: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:pangocairo: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:pangoft2: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:rnnoise: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:auto-updates: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:crash-reports: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单

## 3. 差异归因明细（oracle × portgraph 直接依赖）

| 归类 | README 侧 | portgraph 侧 | 类型/深度 | 证据/说明 |
|---|---|---|---|---|
| ★漏检 | breakpad | — | runtime | README 声明但构建文件无引用 → 疑似 README 过时/笔误 【agent: 主集成位于 cmake/（cmake_helpers）子模块：Linux 侧经 external_crash_reports 包装（CMakeLists.txt:97），主仓库仅 macstore 段 target_link_frameworks(corpus-a PRIVATE Breakpad)（:2381 |
| ★漏检 | crashpad | — | runtime | README 声明但构建文件无引用 → 疑似 README 过时/笔误 【agent: 主集成位于 cmake/（cmake_helpers）子模块：Linux 侧经 external_crash_reports 包装（CMakeLists.txt:97），主仓库仅 macstore 段 target_link_frameworks(corpus-a PRIVATE Breakpad)（:2381 |
| ★误报 | — | libxcb | package d1 | portgraph 检出但构建文件无引用 → 扫描误报候选（include 启发式/名字巧合） |
| README过时 | lzma-sdk | — | runtime | README 声明但构建文件无引用 → 疑似 README 过时/笔误 |
| README过时 | opus | — | runtime | README 声明但构建文件无引用 → 疑似 README 过时/笔误 |
| README漏列 | — | boost | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | cmark-gfm | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | glib | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | glibmm | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | jpeg-turbo | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | libavif | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | libheif | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | libjxl | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | libvpx | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | libxkbcommon | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | lz4 | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | minizip | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | openh264 | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | opus | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | pango | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | protobuf | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | xxhash | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| 构建工具 | gyp | — | build | 构建工具，fetch-deps 不收 build 边 |
| 构建工具 | ninja | — | build | 构建工具，fetch-deps 不收 build 边 |
| 构建工具 | cmake | — | build | 构建工具，fetch-deps 不收 build 边 |
| 粒度折叠 | — | KF archive | framework d1 | KDE Frameworks 组件粒度：README 通常只写 'KDE Frameworks' |
| 粒度折叠 | — | KF coreaddons | framework d1 | KDE Frameworks 组件粒度：README 通常只写 'KDE Frameworks' |
| 粒度折叠 | — | KF desktoptojson | framework d1 | KDE Frameworks 组件粒度：README 通常只写 'KDE Frameworks' |
| 粒度折叠 | — | Qt D-Bus | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt GUI | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt Network | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt Quick | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt Quick Widgets | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt SVG | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt Wayland Compositor | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt Widgets | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 一致 | qt | Qt Core | qt-module d1 |  |
| 一致 | openssl | openssl@3 | package d1 |  |
| 一致 | webrtc | webrtc | package d1 | 匹配到幽灵节点：真实外部依赖且无已知鸿蒙包（fetch-deps 报 need_port/需源码移植，检出正确） |
| 一致 | zlib | zlib | package d1 |  |
| 一致 | liblzma | xz | package d1 |  |
| 一致 | openal | openal-soft | package d1 |  |
| 一致 | ffmpeg | ffmpeg | package d1 |  |
| 一致 | range-v3 | range | package d1 | ⚠ 匹配到幽灵节点：库里存在形近已知包 range-v3（hb:range-v3）→ 名字解析缺口，需复核 |
| 一致 | xxhash | libxxhash | package d1 |  |
| 一致 | qr-code-generator | libqrcodegen | package d1 |  |
| 一致 | hunspell | hunspell | package d1 |  |
| 一致 | ada | ada | package d1 | 匹配到幽灵节点：真实外部依赖且无已知鸿蒙包（fetch-deps 报 need_port/需源码移植，检出正确） |
| 自带子模块 | gsl | — | runtime |  .gitmodules 自带子模块（corpus-a/ThirdParty/GSL → https://github.com/Microsoft/GSL.git）：随项目源码一起编译，不作为外部包获取/检测 |
| 未知包(正常) | — | auto_updates | package d1 | 未匹配到已知鸿蒙包：真实外部依赖，幽灵节点为正确检出（fetch-deps 报 need_port/需源码移植） |
| 未知包(正常) | — | breakpad-client | package d1 | 未匹配到已知鸿蒙包：真实外部依赖，幽灵节点为正确检出（fetch-deps 报 need_port/需源码移植） |
| 未知包(正常) | — | crash_reports | package d1 | 未匹配到已知鸿蒙包：真实外部依赖，幽灵节点为正确检出（fetch-deps 报 need_port/需源码移植） |
| 未知包(正常) | — | giomm-2.68 | package d1 | 未匹配到已知鸿蒙包：真实外部依赖，幽灵节点为正确检出（fetch-deps 报 need_port/需源码移植） |
| 未知包(正常) | — | libudev | package d1 | 未匹配到已知鸿蒙包：真实外部依赖，幽灵节点为正确检出（fetch-deps 报 need_port/需源码移植） |
| 未知包(正常) | — | microsoft | package d1 | 未匹配到已知鸿蒙包：真实外部依赖，幽灵节点为正确检出（fetch-deps 报 need_port/需源码移植） |
| 未知包(正常) | — | pangocairo | package d1 | 未匹配到已知鸿蒙包：真实外部依赖，幽灵节点为正确检出（fetch-deps 报 need_port/需源码移植） |
| 未知包(正常) | — | pangoft2 | package d1 | 未匹配到已知鸿蒙包：真实外部依赖，幽灵节点为正确检出（fetch-deps 报 need_port/需源码移植） |
| 未知包(正常) | — | ranges | package d1 | 未匹配到已知鸿蒙包：真实外部依赖，幽灵节点为正确检出（fetch-deps 报 need_port/需源码移植） |
| 未知包(正常) | — | rnnoise | package d1 | 未匹配到已知鸿蒙包：真实外部依赖，幽灵节点为正确检出（fetch-deps 报 need_port/需源码移植） |
| 未知包(正常) | — | tde2e | package d1 | 未匹配到已知鸿蒙包：真实外部依赖，幽灵节点为正确检出（fetch-deps 报 need_port/需源码移植） |
| 未知包(正常) | — | tg_owt | package d1 | 未匹配到已知鸿蒙包：真实外部依赖，幽灵节点为正确检出（fetch-deps 报 need_port/需源码移植） |
| 未知包(正常) | — | tl | package d1 | 未匹配到已知鸿蒙包：真实外部依赖，幽灵节点为正确检出（fetch-deps 报 need_port/需源码移植） |
| 未知包(正常) | — | tlottie | package d1 | 未匹配到已知鸿蒙包：真实外部依赖，幽灵节点为正确检出（fetch-deps 报 need_port/需源码移植） |
| 未知包(正常) | — | tmc | package d1 | 未匹配到已知鸿蒙包：真实外部依赖，幽灵节点为正确检出（fetch-deps 报 need_port/需源码移植） |

归类统计：构建工具×3，★误报×1，一致×12，★漏检×2，粒度折叠×11，README漏列×17，README过时×2，未知包(正常)×15，自带子模块×1

## 4. 依赖闭包概览（fetch-deps --dry-run）

- 闭包总数 112 项：cmd_only 2，covered 1，need_port 21，provided 9，target 1，would_download 78
- 可直下 bottle：boost、jpeg-turbo、libavif、libheif、xz、lz4、minizip、openal-soft、openssl@3、opus、protobuf、xxhash、zlib、glib、glibmm、hunspell、ffmpeg、libjxl、openh264、libvpx、libxcb、libxkbcommon、cmark-gfm、pango、libqrcodegen、icu4c@78、zstd、zlib-ng-compat、dav1d、libpng、libde265、libtiff、webp、x265、abseil、bison、python-setuptools、pcre2、dbus、util-linux
- 仅命令获取（cmd_only）：aom、ca-certificates
- 需自行移植（need_port）：ada、microsoft、range、tde2e、tg_owt、tl、breakpad-client、giomm-2.68、libudev、pangocairo、pangoft2、rnnoise、auto_updates、crash_reports、ranges、tlottie、tmc、webrtc、KF archive、KF coreaddons
  - ada: ?
  - microsoft: ?
  - range: ?
  - tde2e: ?
  - tg_owt: ?
  - tl: ?
  - breakpad-client: ?
  - giomm-2.68: ?
  - libudev: ?
  - pangocairo: ?

## 5. 直接依赖全量清单（portgraph depth-1）

| 节点 | 类型 | 边 | port_status | 深度 |
|---|---|---|---|---|
| KF archive | framework | runtime | unknown | 1 |
| KF coreaddons | framework | runtime | unknown | 1 |
| KF desktoptojson | framework | runtime | unknown | 1 |
| ada | package | runtime | unknown | 1 |
| auto_updates | package | runtime | unknown | 1 |
| boost | package | runtime | ported | 1 |
| breakpad-client | package | runtime | unknown | 1 |
| cmark-gfm | package | runtime | ported | 1 |
| crash_reports | package | runtime | unknown | 1 |
| ffmpeg | package | runtime | ported | 1 |
| giomm-2.68 | package | runtime | unknown | 1 |
| glib | package | runtime | ported | 1 |
| glibmm | package | runtime | ported | 1 |
| hunspell | package | runtime | ported | 1 |
| jpeg-turbo | package | runtime | ported | 1 |
| libavif | package | runtime | ported | 1 |
| libheif | package | runtime | ported | 1 |
| libjxl | package | runtime | ported | 1 |
| libqrcodegen | package | runtime | ported | 1 |
| libudev | package | runtime | unknown | 1 |
| libvpx | package | runtime | ported | 1 |
| libxcb | package | runtime | ported | 1 |
| libxkbcommon | package | runtime | ported | 1 |
| libxxhash | package | runtime | ported | 1 |
| lz4 | package | runtime | ported | 1 |
| microsoft | package | runtime | unknown | 1 |
| minizip | package | runtime | ported | 1 |
| openal-soft | package | runtime | ported | 1 |
| openh264 | package | runtime | ported | 1 |
| openssl@3 | package | runtime | ported | 1 |
| opus | package | runtime | ported | 1 |
| pango | package | runtime | ported | 1 |
| pangocairo | package | runtime | unknown | 1 |
| pangoft2 | package | runtime | unknown | 1 |
| protobuf | package | runtime | ported | 1 |
| range | package | runtime | unknown | 1 |
| ranges | package | runtime | unknown | 1 |
| rnnoise | package | runtime | unknown | 1 |
| tde2e | package | runtime | unknown | 1 |
| tg_owt | package | runtime | unknown | 1 |
| tl | package | runtime | unknown | 1 |
| tlottie | package | runtime | unknown | 1 |
| tmc | package | runtime | unknown | 1 |
| webrtc | package | runtime | unknown | 1 |
| xxhash | package | runtime | ported | 1 |
| xz | package | runtime | ported | 1 |
| zlib | package | runtime | ported | 1 |
| Qt Core | qt-module | uses-module | ported | 1 |
| Qt D-Bus | qt-module | uses-module | blocked | 1 |
| Qt GUI | qt-module | uses-module | ported | 1 |
| Qt Network | qt-module | uses-module | ported | 1 |
| Qt Quick | qt-module | uses-module | ported | 1 |
| Qt Quick Widgets | qt-module | uses-module | ported | 1 |
| Qt SVG | qt-module | uses-module | ported | 1 |
| Qt Wayland Compositor | qt-module | uses-module | blocked | 1 |
| Qt Widgets | qt-module | uses-module | ported | 1 |

## 6. 方法说明

- 对比口径：portgraph 直接依赖（depth-1 边）vs README/INSTALL 声明依赖；闭包仅做产物概览。
- 归因证据：对未匹配项自动 grep 克隆仓库构建文件（find_package/pkg_check_modules/target_link_libraries/vcpkg 等）。
- ★ 类（missed-dep / resolution-gap / false-positive）为 bug 候选，需人工确认；其余为预期差异。
- agent 可读报告：`tests/e2e/reports/corpus-a.report.json`
