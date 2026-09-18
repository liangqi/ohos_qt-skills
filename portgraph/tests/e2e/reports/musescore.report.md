# musescore 依赖对账报告（portgraph E2E）

> 生成时间: 2026-09-18T02:44:26Z | 语料: corpus.json#musescore | 构建系统: ? | 源文件: ?
> Oracle: buildscripts/ci/linux/setup.sh + CMakeLists.txt + buildscripts/cmake/（人工整理）（复核: 已复核，18 条；来源: README 无依赖段（指向外部 wiki），oracle 依仓库内文件人工整理：CI setup.sh apt 清单（standard/runtime/ffmpeg 三段）+ 顶层 CMakeLists.txt 系统库开关（MUE_COMPILE_USE_SYSTEM_*）+ buildscripts/cmake 与 src/framework/*/cmake 的 Setup/Find 模块。CI runtime 段的 X11/xcb/GL/vulkan 等 Qt 桌面平台运行时依赖未逐条列入（非应用级依赖，鸿蒙口径无意义）。）

## 1. 结论速览

| 指标 | 值 |
|---|---|
| 可移植性 verdict | **blocked**（阻塞 9 / 未知 24 / 平台排除 0） |
| 检出召回率 | 50%（4/8 README 运行时依赖） |
| 检出精确率 | 46% |
| Bug 候选 | **11**（false-positive=1, resolution-gap=10） |
| 依赖闭包 | 87 项（already_local 2, cmd_only 2, need_port 23, provided 8, target 1, would_download 51） |

**Agent 复核说明**：

- oracle 由仓库内文件人工整理（README 无依赖段、指向外部 wiki）：CI buildscripts/ci/linux/setup.sh apt 三段清单 + 顶层 CMakeLists.txt MUE_COMPILE_USE_SYSTEM_* 系统库开关 + buildscripts/cmake 与 src/framework/*/cmake 的 Setup/Find 模块；X11/xcb/GL/vulkan 等 Qt 桌面平台运行时依赖未逐条列入。
- 25 个初始 ★ 终判：10 个真别名缺口（ALIASES 缺 alsa→alsa-lib、sndfile→libsndfile、tinyxml→tinyxml2、glib2→glib、dbus1→dbus、png→libpng、ogg→libogg、brotlidec→brotli、iconv→libiconv、intl→gettext，formula 均在 hb-core）；12 个 unknown-ok（确无 bottle 或属内嵌三方/编译器运行时）；openssl@3 经 oracle 补录 libssl-dev 消解为 matched；util-linux 维持误报（内嵌 crashpad include 污染）。
- 结构性发现：depth-1 中约 2/3 包名来自 src/framework/*/thirdparty/ 内嵌三方代码（fluidsynth/freetype/flac/KDDockWidgets）自己的 find_package（且 fluidsynth 一项来自注释行误匹配）；portgraph 应跳过 thirdparty 内嵌路径、剥离 CMake 注释后再匹配。另 portgraph 只扫 CMakeLists.txt 不扫 .cmake（SetupSndFile/SetupFlac/SetupOpusEnc/FindJack 等），sndfile/harfbuzz 当前能对上纯靠内嵌代码巧合。

## 2. 可移植性判定（analyze）

| 阻塞类型 | 节点 | 原因 |
|---|---|---|
| unsupported-interface | app:musescore | 使用鸿蒙不支持的平台接口 ALSA 直连（audio）鸿蒙音频走 AudioRenderer/AudioCapturer，ALSA 不可用；同类鸿蒙替代接口: 鸿蒙 AudioRenderer/AudioCapturer［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-active (95 处无条件 /  |
| unsupported-interface | app:musescore | 使用鸿蒙不支持的平台接口 macOS Cocoa/AppKit（os-api）macOS 专属 UI/系统框架；同类鸿蒙替代接口: POSIX/musl C 库、pthread 多线程、dlopen 动态加载、macOS 系统库绑定、glib 事件循环［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-ac |
| unsupported-interface | app:musescore | 使用鸿蒙不支持的平台接口 macOS CoreAudio（audio）macOS 专属音频框架；同类鸿蒙替代接口: 鸿蒙 AudioRenderer/AudioCapturer［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-active (0 处无条件 / 11 处鸿蒙可编译 / 0 处宏守卫排除 /  |
| unsupported-interface | app:musescore | 使用鸿蒙不支持的平台接口 D-Bus IPC（ipc）鸿蒙无 D-Bus（Qt D-Bus 模块 Out of scope）；需改用系统服务/IPC；同类鸿蒙替代接口: 鸿蒙 IPC/系统服务能力［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-active (10 处无条件 / 0 处鸿蒙可编译 / 2 |
| unsupported-interface | app:musescore | 使用鸿蒙不支持的平台接口 PulseAudio 直连（audio）鸿蒙无 PulseAudio 服务；同类鸿蒙替代接口: 鸿蒙 AudioRenderer/AudioCapturer［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-active (0 处无条件 / 8 处鸿蒙可编译 / 2 处宏守卫排除  |
| unsupported-interface | app:musescore | 使用鸿蒙不支持的平台接口 systemd（os-api）鸿蒙无 systemd 服务管理；同类鸿蒙替代接口: POSIX/musl C 库、pthread 多线程、dlopen 动态加载、macOS 系统库绑定、glib 事件循环［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-active (0 处无条 |
| unsupported-interface | app:musescore | 使用鸿蒙不支持的平台接口 Win32 API（os-api）Windows 专属系统接口；同类鸿蒙替代接口: POSIX/musl C 库、pthread 多线程、dlopen 动态加载、macOS 系统库绑定、glib 事件循环［证据: [含鸿蒙/通用守卫（会编译）] guard=ohos-active (80 处无 |
| unsupported-module | qtmod:dbus | Qt for HarmonyOS 模块适配表: 不支持 - 鸿蒙无 D-Bus |
| unsupported-module | qtmod:x11extras | Qt for HarmonyOS 模块适配表: 不支持 - X11 专属 |

未确认项 24 个：
- [unknown-interface] app:musescore: 平台接口 fork()/exec() 进程模型 的鸿蒙支持性未确认（guard=ohos-active）
- [unknown-package] pkg-unknown:alsa: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:brotlidec: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:dbus1: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:fluidsynth: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:glib2: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:iconv: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:instpatch: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:intl: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:lash: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:midishare: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:oboe: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:ogg: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:openmp: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:opensles: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单

## 3. 差异归因明细（oracle × portgraph 直接依赖）

| 归类 | README 侧 | portgraph 侧 | 类型/深度 | 证据/说明 |
|---|---|---|---|---|
| ★解析缺口 | alsa | alsa | package d1 | ⚠ 匹配到幽灵节点（pkg-unknown）——名字未解析到已知鸿蒙包，实为解析缺口，需复核 【agent: 真别名缺口：hb-core/Formula/a/alsa-lib.rb 与 cmd-pkgs alsa-lib 1.2.12 均存在，ALIASES 缺 alsa→alsa-lib；find_package(ALSA REQUIRED) 位于项目自身 src/framework/midi/ |
| ★解析缺口 | sndfile | sndfile | package d1 | ⚠ 匹配到幽灵节点（pkg-unknown）——名字未解析到已知鸿蒙包，实为解析缺口，需复核 【agent: 真别名缺口：hb-core/Formula/lib/libsndfile.rb 存在，ALIASES 缺 sndfile→libsndfile；项目 SetupSndFile.cmake:72 find_package(SndFile) 在 .cmake 文件中未被 portgraph 扫 |
| ★解析缺口 | tinyxml | tinyxml | package d1 | ⚠ 匹配到幽灵节点（pkg-unknown）——名字未解析到已知鸿蒙包，实为解析缺口，需复核 【agent: 真别名缺口：hb-core/Formula/t/tinyxml2.rb 与 cmd-pkgs tinyxml2 10.0.0 存在，ALIASES 缺 tinyxml→tinyxml2；src/framework/global/CMakeLists.txt:28 find_package( |
| ★解析缺口 | — | brotlidec | package d1 | pkg-unknown 幽灵节点：find_package 名未解析到已知鸿蒙包（ALIASES 缺口） 【agent: 真别名缺口：hb-core/Formula/b/brotli.rb 与 cmd-pkgs brotli 存在，ALIASES 缺 brotlidec→brotli（来自内嵌 freetype 可选依赖）】 |
| ★解析缺口 | — | dbus1 | package d1 | pkg-unknown 幽灵节点：find_package 名未解析到已知鸿蒙包（ALIASES 缺口） 【agent: 真别名缺口：hb-core/Formula/d/dbus.rb 与 cmd-pkgs dbus 1.14.10 存在，ALIASES 缺 dbus1→dbus（来自内嵌 fluidsynth）】 |
| ★解析缺口 | — | glib2 | package d1 | pkg-unknown 幽灵节点：find_package 名未解析到已知鸿蒙包（ALIASES 缺口） 【agent: 真别名缺口：hb-core/Formula/g/glib.rb 与 cmd-pkgs glib 2.88.0 存在，ALIASES 缺 glib2→glib（来自内嵌 fluidsynth 的 GLib2 find_package）】 |
| ★解析缺口 | — | iconv | package d1 | pkg-unknown 幽灵节点：find_package 名未解析到已知鸿蒙包（ALIASES 缺口） 【agent: 真别名缺口：hb-core/Formula/lib/libiconv.rb 与 cmd-pkgs libiconv 1.17 存在，ALIASES 缺 iconv→libiconv（musl 虽内置 iconv，但 libiconv bottle 确实存在；来自内嵌 flac/ |
| ★解析缺口 | — | intl | package d1 | pkg-unknown 幽灵节点：find_package 名未解析到已知鸿蒙包（ALIASES 缺口） 【agent: 真别名缺口：libintl 属 gettext（hb-core/Formula/g/gettext.rb、cmd-pkgs gettext 0.22.5 存在），ALIASES 缺 intl→gettext（来自内嵌 flac）】 |
| ★解析缺口 | — | ogg | package d1 | pkg-unknown 幽灵节点：find_package 名未解析到已知鸿蒙包（ALIASES 缺口） 【agent: 真别名缺口：hb-core/Formula/lib/libogg.rb 与 cmd-pkgs libogg 存在，ALIASES 缺 ogg→libogg（来自内嵌 flac 的 find_package(Ogg REQUIRED)）】 |
| ★解析缺口 | — | png | package d1 | pkg-unknown 幽灵节点：find_package 名未解析到已知鸿蒙包（ALIASES 缺口） 【agent: 真别名缺口：find_package(PNG) 名 png 未映射到 libpng（hb Formula/lib/libpng.rb、cmd-pkgs libpng 1.6.43）；且图中同时存在已解析的 libpng 节点→同库双节点（来自内嵌 freetype）】 |
| ★误报 | — | util-linux | package d1 | portgraph 检出但构建文件无引用 → 扫描误报候选（include 启发式/名字巧合） 【agent: 维持误报：全仓仅内嵌 google_crashpad_client/util/misc/uuid.cc:34 include <uuid/uuid.h>（libuuid→util-linux include 启发式），无任何构建文件 find_package/pkg_check/link |
| README漏列 | — | bzip2 | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | libpng | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | portaudio | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | readline | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | SDL2 | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | zlib | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| 可选未启用 | flac | — | optional | 可选依赖，默认构建未启用 |
| 可选未启用 | opus | — | optional | 可选依赖，默认构建未启用 |
| 可选未启用 | libopusenc | — | optional | 可选依赖，默认构建未启用 |
| 可选未启用 | fontconfig | — | optional | 可选依赖，默认构建未启用 |
| 可选未启用 | mesa-gl | — | optional | 可选依赖，默认构建未启用 |
| 可选未启用 | nss | — | optional | 可选依赖，默认构建未启用 |
| 可选未启用 | portmidi | — | optional | 可选依赖，默认构建未启用 |
| 可选未启用 | dbus | — | optional | 可选依赖，默认构建未启用 |
| 粒度折叠 | — | Qt D-Bus | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt GUI | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt QML | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt Quick | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt Test | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt Widgets | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 粒度折叠 | — | Qt X11 Extras | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 一致 | qt | Qt Core | qt-module d1 |  |
| 一致 | freetype | freetype | package d1 |  |
| 一致 | jack | jack | package d1 |  |
| 一致 | openssl | openssl@3 | package d1 |  【agent: 检出证据为内嵌 freetype md5.h 与 google_crashpad_client 的 openssl include；CI runtime 段声明 libssl-dev，判 matched 合理（但证据源在内嵌代码，同 util-linux 问题）】 |
| 一致(可选) | ffmpeg | ffmpeg | package d1 |  |
| 一致(可选) | harfbuzz | harfbuzz | package d1 |  |
| 未知包(正常) | pulseaudio | pulseaudio | package d1 | ⚠ 匹配到幽灵节点（pkg-unknown）——名字未解析到已知鸿蒙包，实为解析缺口，需复核 【agent: hb/cmd-pkgs 确无 pulseaudio 库包（仅 pulseaudio-ctl/pulsemixer 控制工具，非同名库）；PulseAudio 直连已由 unsupported-interface 阻塞项单独覆盖】 |
| 未知包(正常) | — | fluidsynth | package d1 | pkg-unknown 幽灵节点：find_package 名未解析到已知鸿蒙包（ALIASES 缺口） 【agent: hb/cmd-pkgs 确无 fluidsynth；且系内嵌 thirdparty 自带源码构建，find_package(FluidSynth) 实为 fluidsynth-2.3.3/CMakeLists.txt:851 注释行（'# Exported targets fo |
| 未知包(正常) | — | instpatch | package d1 | pkg-unknown 幽灵节点：find_package 名未解析到已知鸿蒙包（ALIASES 缺口） 【agent: hb/cmd-pkgs 确无 libinstpatch；来自内嵌 fluidsynth 的可选 MIDI 补丁支持】 |
| 未知包(正常) | — | lash | package d1 | pkg-unknown 幽灵节点：find_package 名未解析到已知鸿蒙包（ALIASES 缺口） 【agent: hb/cmd-pkgs 确无 lash（LASH 音频会话管理已停止维护）；来自内嵌 fluidsynth 可选驱动】 |
| 未知包(正常) | — | midishare | package d1 | pkg-unknown 幽灵节点：find_package 名未解析到已知鸿蒙包（ALIASES 缺口） 【agent: hb/cmd-pkgs 确无 midishare（macOS 专属 MIDI 框架）；来自内嵌 fluidsynth 平台分支】 |
| 未知包(正常) | — | oboe | package d1 | pkg-unknown 幽灵节点：find_package 名未解析到已知鸿蒙包（ALIASES 缺口） 【agent: hb/cmd-pkgs 确无 oboe formula；来自内嵌 fluidsynth 的 enable-oboe 选项分支（Android/OHOS 音频驱动，fluidsynth-2.3.3/CMakeLists.txt:676）】 |
| 未知包(正常) | — | openmp | package d1 | pkg-unknown 幽灵节点：find_package 名未解析到已知鸿蒙包（ALIASES 缺口） 【agent: 编译器运行时（CMake OpenMP 模块）非三方包，应与 Threads 一样跳过；来自内嵌 fluidsynth】 |
| 未知包(正常) | — | opensles | package d1 | pkg-unknown 幽灵节点：find_package 名未解析到已知鸿蒙包（ALIASES 缺口） 【agent: NDK 原生音频 API（OHOS NDK 自带头文件）非 bottle 包；来自内嵌 fluidsynth Android 分支】 |
| 未知包(正常) | — | pipewire | package d1 | pkg-unknown 幽灵节点：find_package 名未解析到已知鸿蒙包（ALIASES 缺口） 【agent: hb/cmd-pkgs 确无 pipewire；来自内嵌 fluidsynth 可选音频服务器驱动】 |
| 未知包(正常) | — | pyside | package d1 | pkg-unknown 幽灵节点：find_package 名未解析到已知鸿蒙包（ALIASES 缺口） 【agent: hb/cmd-pkgs 确无 pyside；来自内嵌 KDDockWidgets/python 绑定（默认不构建）】 |
| 未知包(正常) | — | python3 | package d1 | pkg-unknown 幽灵节点：find_package 名未解析到已知鸿蒙包（ALIASES 缺口） 【agent: 宿主构建工具（内嵌 KDDockWidgets python 绑定的 find_package(Python3)）；python@3.14 bottle 虽存在但映射为目标侧运行时依赖无意义】 |
| 未知包(正常) | — | shiboken | package d1 | pkg-unknown 幽灵节点：find_package 名未解析到已知鸿蒙包（ALIASES 缺口） 【agent: hb/cmd-pkgs 确无 shiboken；来自内嵌 KDDockWidgets/python 绑定（默认不构建）】 |
| 未知包(正常) | — | systemd | package d1 | pkg-unknown 幽灵节点：find_package 名未解析到已知鸿蒙包（ALIASES 缺口） 【agent: hb/cmd-pkgs 确无 systemd（Linux 服务管理器非移植目标包）；systemd 接口已由 unsupported-interface 阻塞项覆盖】 |

归类统计：★误报×1，一致×4，一致(可选)×2，可选未启用×8，粒度折叠×7，README漏列×6，★解析缺口×10，未知包(正常)×13

## 4. 依赖闭包概览（fetch-deps --dry-run）

- 闭包总数 87 项：already_local 2，cmd_only 2，need_port 23，provided 8，target 1，would_download 51
- 可直下 bottle：bzip2、ffmpeg、harfbuzz、jack、portaudio、readline、SDL2、zlib、freetype、libpng、util-linux、openssl@3、lame、libvpx、opus、svt-av1、x264、x265、alsa-lib、libxcb、xz、zlib-ng-compat、cairo、glib、graphite2、gettext、mpg123、python@3.14、libxau、libxdmcp、libx11、libxext、libxrender、lzo、pixman、bison、python-setuptools、pcre2、dbus、libunistring
- 仅命令获取（cmd_only）：dav1d、ca-certificates
- 需自行移植（need_port）：alsa、brotlidec、dbus1、fluidsynth、glib2、iconv、instpatch、intl、lash、midishare、oboe、ogg、openmp、opensles、pipewire、png、pulseaudio、pyside、python3、shiboken
  - alsa: ?
  - brotlidec: ?
  - dbus1: ?
  - fluidsynth: ?
  - glib2: ?
  - iconv: ?
  - instpatch: ?
  - intl: ?
  - lash: ?
  - midishare: ?

## 5. 直接依赖全量清单（portgraph depth-1）

| 节点 | 类型 | 边 | port_status | 深度 |
|---|---|---|---|---|
| alsa | package | runtime | unknown | 1 |
| brotlidec | package | runtime | unknown | 1 |
| bzip2 | package | runtime | ported | 1 |
| dbus1 | package | runtime | unknown | 1 |
| ffmpeg | package | runtime | ported | 1 |
| fluidsynth | package | runtime | unknown | 1 |
| freetype | package | runtime | ported | 1 |
| glib2 | package | runtime | unknown | 1 |
| harfbuzz | package | runtime | ported | 1 |
| iconv | package | runtime | unknown | 1 |
| instpatch | package | runtime | unknown | 1 |
| intl | package | runtime | unknown | 1 |
| jack | package | runtime | ported | 1 |
| lash | package | runtime | unknown | 1 |
| libpng | package | runtime | ported | 1 |
| midishare | package | runtime | unknown | 1 |
| oboe | package | runtime | unknown | 1 |
| ogg | package | runtime | unknown | 1 |
| openmp | package | runtime | unknown | 1 |
| opensles | package | runtime | unknown | 1 |
| openssl@3 | package | runtime | ported | 1 |
| pipewire | package | runtime | unknown | 1 |
| png | package | runtime | unknown | 1 |
| portaudio | package | runtime | ported | 1 |
| pulseaudio | package | runtime | unknown | 1 |
| pyside | package | runtime | unknown | 1 |
| python3 | package | runtime | unknown | 1 |
| readline | package | runtime | ported | 1 |
| SDL2 | package | runtime | ported | 1 |
| shiboken | package | runtime | unknown | 1 |
| sndfile | package | runtime | unknown | 1 |
| systemd | package | runtime | unknown | 1 |
| tinyxml | package | runtime | unknown | 1 |
| util-linux | package | runtime | ported | 1 |
| zlib | package | runtime | ported | 1 |
| Qt Core | qt-module | uses-module | ported | 1 |
| Qt D-Bus | qt-module | uses-module | blocked | 1 |
| Qt GUI | qt-module | uses-module | ported | 1 |
| Qt QML | qt-module | uses-module | ported | 1 |
| Qt Quick | qt-module | uses-module | ported | 1 |
| Qt Test | qt-module | uses-module | ported | 1 |
| Qt Widgets | qt-module | uses-module | ported | 1 |
| Qt X11 Extras | qt-module | uses-module | blocked | 1 |

## 6. 方法说明

- 对比口径：portgraph 直接依赖（depth-1 边）vs README/INSTALL 声明依赖；闭包仅做产物概览。
- 归因证据：对未匹配项自动 grep 克隆仓库构建文件（find_package/pkg_check_modules/target_link_libraries/vcpkg 等）。
- ★ 类（missed-dep / resolution-gap / false-positive）为 bug 候选，需人工确认；其余为预期差异。
- agent 可读报告：`./portgraph\tests\e2e\reports\musescore.report.json`
