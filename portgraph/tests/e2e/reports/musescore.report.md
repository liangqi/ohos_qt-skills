# musescore 依赖对账报告（portgraph E2E）

> 生成时间: 2026-09-19T12:36:16Z | 语料: corpus.json#musescore | 构建系统: cmake+qmake | 源文件: 3157
> Oracle: buildscripts/ci/linux/setup.sh + CMakeLists.txt + buildscripts/cmake/（人工整理）（复核: 已复核，18 条；来源: README 无依赖段（指向外部 wiki），oracle 依仓库内文件人工整理：CI setup.sh apt 清单（standard/runtime/ffmpeg 三段）+ 顶层 CMakeLists.txt 系统库开关（MUE_COMPILE_USE_SYSTEM_*）+ buildscripts/cmake 与 src/framework/*/cmake 的 Setup/Find 模块。CI runtime 段的 X11/xcb/GL/vulkan 等 Qt 桌面平台运行时依赖未逐条列入（非应用级依赖，鸿蒙口径无意义）。）

## 1. 结论速览

| 指标 | 值 |
|---|---|
| 可移植性 verdict | **uncertain**（阻塞 0 / 未知 2 / 平台排除 2） |
| 检出召回率 | 38%（3/8 README 运行时依赖） |
| 检出精确率 | 27% |
| Bug 候选 | **0**（无） |
| 依赖闭包 | 61 项（cmd_only 1, need_port 2, provided 2, target 1, would_download 55） |

**Agent 复核说明**：

- oracle 由仓库内文件人工整理（README 无依赖段、指向外部 wiki）：CI buildscripts/ci/linux/setup.sh apt 三段清单 + 顶层 CMakeLists.txt MUE_COMPILE_USE_SYSTEM_* 系统库开关 + buildscripts/cmake 与 src/framework/*/cmake 的 Setup/Find 模块；X11/xcb/GL/vulkan 等 Qt 桌面平台运行时依赖未逐条列入。
- 25 个初始 ★ 终判：10 个真别名缺口（ALIASES 缺 alsa→alsa-lib、sndfile→libsndfile、tinyxml→tinyxml2、glib2→glib、dbus1→dbus、png→libpng、ogg→libogg、brotlidec→brotli、iconv→libiconv、intl→gettext，formula 均在 hb-core）；12 个 unknown-ok（确无 bottle 或属内嵌三方/编译器运行时）；openssl@3 经 oracle 补录 libssl-dev 消解为 matched；util-linux 维持误报（内嵌 crashpad include 污染）。
- 结构性发现：depth-1 中约 2/3 包名来自 src/framework/*/thirdparty/ 内嵌三方代码（fluidsynth/freetype/flac/KDDockWidgets）自己的 find_package（且 fluidsynth 一项来自注释行误匹配）；portgraph 应跳过 thirdparty 内嵌路径、剥离 CMake 注释后再匹配。另 portgraph 只扫 CMakeLists.txt 不扫 .cmake（SetupSndFile/SetupFlac/SetupOpusEnc/FindJack 等），sndfile/harfbuzz 当前能对上纯靠内嵌代码巧合。

## 2. 可移植性判定（analyze）

（无硬阻塞）

未确认项 2 个：
- [unknown-package] pkg-unknown:mnxdom: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单
- [unknown-package] pkg-unknown:suil-0: 无鸿蒙预编译产物，需自行交叉编译移植；不在 Harmonybrew/cmd-pkgs 已知清单

## 3. 差异归因明细（oracle × portgraph 直接依赖）

| 归类 | README 侧 | portgraph 侧 | 类型/深度 | 证据/说明 |
|---|---|---|---|---|
| README过时 | alsa | — | runtime | README 声明但构建文件无引用 → 疑似 README 过时/笔误 |
| README过时 | jack | — | runtime | README 声明但构建文件无引用 → 疑似 README 过时/笔误 |
| README过时 | pulseaudio | — | runtime | README 声明但构建文件无引用 → 疑似 README 过时/笔误 |
| README过时 | sndfile | — | runtime | README 声明但构建文件无引用 → 疑似 README 过时/笔误 |
| README过时 | tinyxml | — | runtime | README 声明但构建文件无引用 → 疑似 README 过时/笔误 |
| README漏列 | — | curl | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | global | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | lilv | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | lv2 | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | pugixml | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | utf8cpp | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | zix | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| README漏列 | — | zlib | package d1 | 构建文件引用但 README 未列 → README 不完整（portgraph 正确） |
| 可选未启用 | ffmpeg | — | optional | 可选依赖，默认构建未启用 |
| 可选未启用 | harfbuzz | — | optional | 可选依赖，默认构建未启用 |
| 可选未启用 | flac | — | optional | 可选依赖，默认构建未启用 |
| 可选未启用 | opus | — | optional | 可选依赖，默认构建未启用 |
| 可选未启用 | libopusenc | — | optional | 可选依赖，默认构建未启用 |
| 可选未启用 | fontconfig | — | optional | 可选依赖，默认构建未启用 |
| 可选未启用 | mesa-gl | — | optional | 可选依赖，默认构建未启用 |
| 可选未启用 | nss | — | optional | 可选依赖，默认构建未启用 |
| 可选未启用 | portmidi | — | optional | 可选依赖，默认构建未启用 |
| 可选未启用 | dbus | — | optional | 可选依赖，默认构建未启用 |
| 粒度折叠 | — | Qt GUI | qt-module d1 | Qt 模块粒度：README 通常只写 'Qt' |
| 一致 | qt | Qt Core | qt-module d1 |  |
| 一致 | freetype | freetype | package d1 |  |
| 一致 | openssl | openssl@3 | package d1 |  【agent: 检出证据为内嵌 freetype md5.h 与 google_crashpad_client 的 openssl include；CI runtime 段声明 libssl-dev，判 matched 合理（但证据源在内嵌代码，同 util-linux 问题）】 |
| 未知包(正常) | — | mnxdom | package d1 | 未匹配到已知鸿蒙包：真实外部依赖，幽灵节点为正确检出（fetch-deps 报 need_port/需源码移植） |
| 未知包(正常) | — | suil-0 | package d1 | 未匹配到已知鸿蒙包：真实外部依赖，幽灵节点为正确检出（fetch-deps 报 need_port/需源码移植） |

归类统计：一致×3，可选未启用×10，粒度折叠×1，README漏列×8，README过时×5，未知包(正常)×2

## 4. 依赖闭包概览（fetch-deps --dry-run）

- 闭包总数 61 项：cmd_only 1，need_port 2，provided 2，target 1，would_download 55
- 可直下 bottle：curl、openssl@3、utf8cpp、zlib、lilv、lv2、pugixml、zix、freetype、global、brotli、libnghttp2、libnghttp3、libngtcp2、libssh2、zstd、libidn2、zlib-ng-compat、libsndfile、serd、sord、sratom、glib、libpng、libtool、ncurses、python@3.14、sqlite、universal-ctags、lz4、xz、libunistring、flac、lame、libogg、libvorbis、mpg123、opus、pcre2、bison
- 仅命令获取（cmd_only）：ca-certificates
- 需自行移植（need_port）：mnxdom、suil-0
  - mnxdom: ?
  - suil-0: ?

## 5. 直接依赖全量清单（portgraph depth-1）

| 节点 | 类型 | 边 | port_status | 深度 |
|---|---|---|---|---|
| curl | package | runtime | ported | 1 |
| freetype | package | runtime | ported | 1 |
| global | package | runtime | ported | 1 |
| lilv | package | runtime | ported | 1 |
| lv2 | package | runtime | ported | 1 |
| mnxdom | package | runtime | unknown | 1 |
| openssl@3 | package | runtime | ported | 1 |
| pugixml | package | runtime | ported | 1 |
| suil-0 | package | runtime | unknown | 1 |
| utf8cpp | package | runtime | ported | 1 |
| zix | package | runtime | ported | 1 |
| zlib | package | runtime | ported | 1 |
| Qt Core | qt-module | uses-module | ported | 1 |
| Qt GUI | qt-module | uses-module | ported | 1 |

## 6. 方法说明

- 对比口径：portgraph 直接依赖（depth-1 边）vs README/INSTALL 声明依赖；闭包仅做产物概览。
- 归因证据：对未匹配项自动 grep 克隆仓库构建文件（find_package/pkg_check_modules/target_link_libraries/vcpkg 等）。
- ★ 类（missed-dep / resolution-gap / false-positive）为 bug 候选，需人工确认；其余为预期差异。
- agent 可读报告：`/root/harmony-workspace/worker1/portgraph/tests/e2e/reports/musescore.report.json`
