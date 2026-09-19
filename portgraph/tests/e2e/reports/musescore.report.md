# musescore 依赖对账报告（portgraph E2E）

> 生成时间: 2026-09-19T15:12:53Z | 语料: corpus.json#musescore | 构建系统: cmake+qmake | 源文件: 5729
> Oracle: buildscripts/cmake/DependencyManifest.cmake + muse/buildscripts/cmake/ExtDepsManifest.cmake + muse/framework/{midi,audio/driver}/CMakeLists.txt + muse/framework/cmake/MuseDeclareOptions.cmake（人工整理）（复核: 已复核，25 条；来源: 针对 master 2b540fe（muse_deps 依赖引擎时代）重写：README 无依赖段（指向 wiki.spatia... 外部 wiki），oracle 依仓库内依赖清单人工整理。口径=默认构建需外部产物的依赖：require_dep(...)（预编译/系统模式）与项目自身 find_package 为 runtime/optional；require_source_dep（liblouis/kddockwidgets/picojson/pugixml/utfcpp/googletest/crashpad_client/vst3sdk/lodepng/asiosdk）与 FetchContent 的 mnxdom 源码模式为 vendored，随项目源码编译、无需外部产物，不入 oracle；require_tool/find_package(Git) 为主机构建工具列 build。可选性依 MuseDeclareOptions.cmake 默认值：MUSE_MODULE_AUDIO_JACK OFF、MUSE_MODULE_AUDIO_PIPEWIRE OFF、MUSE_MODULE_DRAW_USE_QTTEXTDRAW ON（→ msdfgen 不启用）、MSS_USE_SYSTEM_MNXDOM OFF（→ mnxdom 默认源码自带，系统模式才 pkg_check）；MUSE_MODULE_AUDIO_EXPORT ON、MUSE_BUILD_IMPEXP_MNX_MODULE ON。旧 oracle（CI setup.sh + MUE_COMPILE_USE_SYSTEM_* 时代）的 pulseaudio/openssl/tinyxml/ffmpeg 在 master 已不存在：PulseAudio 直连仅存于内嵌 fluidsynth 可选驱动，openssl 无任何清单引用。）

## 1. 结论速览

| 指标 | 值 |
|---|---|
| 可移植性 verdict | **blocked**（阻塞 8 / 未知 4 / 平台排除 1） |
| 检出召回率 | 100%（16/16 README 运行时依赖） |
| 检出精确率 | 95% |
| Bug 候选 | **0**（无） |
| 依赖闭包 | 89 项（cmd_only 1, need_port 4, provided 16, target 1, vendored 10, would_download 57） |

**Agent 复核说明**：

- oracle 针对 master 2b540fe（muse_deps 依赖引擎）重写：require_dep 清单（DependencyManifest/ExtDepsManifest）+ 项目 find_package（ALSA/Jack/mnxdom）+ SetupQt6.cmake；可选性依 MuseDeclareOptions.cmake 默认值。require_source_dep 的 10 个源码自带依赖（liblouis/kddockwidgets/picojson/pugixml/utfcpp/googletest/crashpad_client/vst3sdk/lodepng/asiosdk）按口径不入 oracle（随项目源码编译，无需外部产物），portgraph 以 vendored 边 + fetch-deps status=vendored 表达。
- 上一轮（旧版仓库，CI setup.sh 时代）的 10 个 ALIASES 缺口已在本轮修复入库（alsa→alsa-lib、sndfile→libsndfile、tinyxml→tinyxml2、glib2→glib、dbus1→dbus、ogg→libogg、vorbis→libvorbis、png→libpng、brotlidec→brotli、utfcpp→utf8cpp、nlohmann_json→nlohmann-json、intl→gettext）；fluidsynth/KDDockWidgets 内嵌三方与 muse_deps recipes 的误报源由 vendored 路径跳过修复；注释行 find_package 误匹配由注释剥离修复；buildscripts/ 目录误排除（build* 前缀）已修复。
- 残留（非本轮修复）：require_dep 条件块不求值（msdfgen/pipewire/asiosdk 等默认关闭的声明仍进闭包，fetch-deps 概览偏保守）；deps 报告 raw_libs 中项目内部 target 名（engraving/global/muse_* 等，由 declare_module 等函数创建，add_library 扫描不可见）与 hb:global 巧合解析为噪音。

## 2. 可移植性判定（analyze）

| 阻塞类型 | 节点 | 原因 |
|---|---|---|
| unsupported-interface | app:musescore | 使用鸿蒙不支持的平台接口 ALSA 直连（audio）鸿蒙音频走 AudioRenderer/AudioCapturer，ALSA 不可用；同类鸿蒙替代接口: 鸿蒙 AudioRenderer/AudioCapturer［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-active (89 处无条件 /  |
| unsupported-interface | app:musescore | 使用鸿蒙不支持的平台接口 macOS CoreAudio（audio）macOS 专属音频框架；同类鸿蒙替代接口: 鸿蒙 AudioRenderer/AudioCapturer［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-active (2 处无条件 / 11 处鸿蒙可编译 / 0 处宏守卫排除 /  |
| unsupported-interface | app:musescore | 使用鸿蒙不支持的平台接口 D-Bus IPC（ipc）鸿蒙无 D-Bus（Qt D-Bus 模块 Out of scope）；需改用系统服务/IPC；同类鸿蒙替代接口: 鸿蒙 IPC/系统服务能力［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-active (10 处无条件 / 0 处鸿蒙可编译 / 2 |
| unsupported-interface | app:musescore | 使用鸿蒙不支持的平台接口 PulseAudio 直连（audio）鸿蒙无 PulseAudio 服务；同类鸿蒙替代接口: 鸿蒙 AudioRenderer/AudioCapturer［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-active (0 处无条件 / 8 处鸿蒙可编译 / 2 处宏守卫排除  |
| unsupported-interface | app:musescore | 使用鸿蒙不支持的平台接口 systemd（os-api）鸿蒙无 systemd 服务管理；同类鸿蒙替代接口: dlopen 动态加载、glib 事件循环、macOS 系统库绑定、POSIX/musl C 库、pthread 多线程［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-active (0 处无条 |
| unsupported-interface | app:musescore | 使用鸿蒙不支持的平台接口 Win32 API（os-api）Windows 专属系统接口；同类鸿蒙替代接口: dlopen 动态加载、glib 事件循环、macOS 系统库绑定、POSIX/musl C 库、pthread 多线程［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-active (30 处无 |
| unsupported-module | qtmod:dbus | Qt for HarmonyOS 模块适配表: 不支持 - 鸿蒙无 D-Bus |
| unsupported-module | qtmod:x11extras | Qt for HarmonyOS 模块适配表: 不支持 - X11 专属 |

未确认项 4 个：
- [unknown-package] pkg-unknown:msdfgen: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:opusenc: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:pipewire: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:json-schema-validator: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单

## 3. 差异归因明细（oracle × portgraph 直接依赖）

| 归类 | README 侧 | portgraph 侧 | 类型/深度 | 证据/说明 |
|---|---|---|---|---|
| README漏列 | — | global | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| 可选未启用 | jack | — | optional | 可选依赖，默认构建未启用 |
| 可选未启用 | mnxdom | — | optional | 可选依赖，默认构建未启用 |
| 构建工具 | git | — | build | 构建工具，fetch-deps 不收 build 边 |
| 构建工具 | crashpad_handler | — | build | 构建工具，fetch-deps 不收 build 边 |
| 构建工具 | sentry-cli | — | build | 构建工具，fetch-deps 不收 build 边 |
| 构建工具 | dump_syms | — | build | 构建工具，fetch-deps 不收 build 边 |
| 构建工具 | uncrustify | — | build | 构建工具，fetch-deps 不收 build 边 |
| 粒度折叠 | — | Qt Core | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt D-Bus | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt GUI | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt Network | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt Network Authorization | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt Print Support | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt QML | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt Quick | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt Quick Widgets | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt SVG | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt Test | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt WebSockets | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt Widgets | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt X11 Extras | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt XML | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 一致 | qt | Qt Concurrent | qt-module d1 |  |
| 一致 | alsa | alsa-lib | package d1 |  |
| 一致 | ogg | libogg | package d1 |  |
| 一致 | vorbis | libvorbis | package d1 |  |
| 一致 | flac | flac | package d1 |  |
| 一致 | opus | opus | package d1 |  |
| 一致 | libsndfile | libsndfile | package d1 |  |
| 一致 | zlib | zlib | package d1 |  |
| 一致 | freetype | freetype | package d1 |  |
| 一致 | harfbuzz | harfbuzz | package d1 |  |
| 一致 | libpng | libpng | package d1 |  |
| 一致 | fdk-aac | fdk-aac | package d1 |  |
| 一致 | lame | lame | package d1 |  |
| 一致 | opusenc | opusenc | package d1 | 匹配到幽灵节点：真实外部依赖且无已知鸿蒙包（fetch-deps 报 need_port/需源码移植，检出正确） 【agent: 无 bottle 属实：hb-core/cmd-pkgs 均无 opusenc/libopusenc formula（源码 pin 在 muse_deps/recipes/opusenc/spec.cmake），portgraph 标 need_port 正确；requ |
| 一致 | nlohmann_json | nlohmann-json | package d1 |  |
| 一致 | json_schema_validator | json_schema_validator | package d1 | 匹配到幽灵节点：真实外部依赖且无已知鸿蒙包（fetch-deps 报 need_port/需源码移植，检出正确） 【agent: 无 bottle 属实：hb-core/cmd-pkgs 均无 json-schema-validator（源码 pin 在 muse_deps/recipes/json_schema_validator），need_port 正确】 |
| 一致(可选) | msdfgen | msdfgen | package d1 | 匹配到幽灵节点：真实外部依赖且无已知鸿蒙包（fetch-deps 报 need_port/需源码移植，检出正确） 【agent: 无 bottle 属实：hb/cmd-pkgs 均无 msdfgen；且默认构建不启用（MUSE_MODULE_DRAW_USE_QTTEXTDRAW 默认 ON）】 |
| 一致(可选) | pipewire | pipewire | package d1 | 匹配到幽灵节点：真实外部依赖且无已知鸿蒙包（fetch-deps 报 need_port/需源码移植，检出正确） 【agent: 无 bottle 属实：hb/cmd-pkgs 确无 pipewire 库包（MUSE_MODULE_AUDIO_PIPEWIRE 默认 OFF）；需要时走 PipeWire 直连 unsupported-interface 阻塞项】 |

归类统计：构建工具×5，一致×16，一致(可选)×2，可选未启用×2，粒度折叠×15，README漏列×1

## 4. 依赖闭包概览（fetch-deps --dry-run）

- 闭包总数 89 项：cmd_only 1，need_port 4，provided 16，target 1，vendored 10，would_download 57
- 可直下 bottle：alsa-lib、freetype、zlib、harfbuzz、libpng、libogg、fdk-aac、flac、lame、opus、libvorbis、libsndfile、nlohmann-json、global、zlib-ng-compat、cairo、glib、graphite2、icu4c@78、mpg123、libtool、ncurses、python@3.14、sqlite、universal-ctags、fontconfig、libx11、libxcb、libxext、libxrender、lzo、pixman、bison、python-setuptools、pcre2、dbus、util-linux、m4、mpdecimal、openssl@3
- 仅命令获取（cmd_only）：ca-certificates
- 需自行移植（need_port）：msdfgen、opusenc、pipewire、json_schema_validator
  - msdfgen: ?
  - opusenc: ?
  - pipewire: ?
  - json_schema_validator: ?

## 5. 直接依赖全量清单（portgraph depth-1）

| 节点 | 类型 | 边 | port_status | 深度 |
|---|---|---|---|---|
| alsa-lib | package | runtime | ported | 1 |
| fdk-aac | package | runtime | ported | 1 |
| flac | package | runtime | ported | 1 |
| freetype | package | runtime | ported | 1 |
| global | package | runtime | ported | 1 |
| harfbuzz | package | runtime | ported | 1 |
| json_schema_validator | package | runtime | unknown | 1 |
| lame | package | runtime | ported | 1 |
| libogg | package | runtime | ported | 1 |
| libpng | package | runtime | ported | 1 |
| libsndfile | package | runtime | ported | 1 |
| libvorbis | package | runtime | ported | 1 |
| msdfgen | package | runtime | unknown | 1 |
| nlohmann-json | package | runtime | ported | 1 |
| opus | package | runtime | ported | 1 |
| opusenc | package | runtime | unknown | 1 |
| pipewire | package | runtime | unknown | 1 |
| zlib | package | runtime | ported | 1 |
| Qt Concurrent | qt-module | uses-module | ported | 1 |
| Qt Core | qt-module | uses-module | ported | 1 |
| Qt D-Bus | qt-module | uses-module | blocked | 1 |
| Qt GUI | qt-module | uses-module | ported | 1 |
| Qt Network | qt-module | uses-module | ported | 1 |
| Qt Network Authorization | qt-module | uses-module | ported | 1 |
| Qt Print Support | qt-module | uses-module | ported | 1 |
| Qt QML | qt-module | uses-module | ported | 1 |
| Qt Quick | qt-module | uses-module | ported | 1 |
| Qt Quick Widgets | qt-module | uses-module | ported | 1 |
| Qt SVG | qt-module | uses-module | ported | 1 |
| Qt Test | qt-module | uses-module | ported | 1 |
| Qt WebSockets | qt-module | uses-module | ported | 1 |
| Qt Widgets | qt-module | uses-module | ported | 1 |
| Qt X11 Extras | qt-module | uses-module | blocked | 1 |
| Qt XML | qt-module | uses-module | ported | 1 |

## 6. 方法说明

- 对比口径：portgraph 直接依赖（depth-1 边）vs README/INSTALL 声明依赖；闭包仅做产物概览。
- 归因证据：对未匹配项自动 grep 克隆仓库构建文件（find_package/pkg_check_modules/target_link_libraries/vcpkg 等）。
- ★ 类（missed-dep / resolution-gap / false-positive）为 bug 候选，需人工确认；其余为预期差异。
- agent 可读报告：`tests/e2e/reports/musescore.report.json`
