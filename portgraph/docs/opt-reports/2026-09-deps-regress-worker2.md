# REGRESS-REPORT：portgraph 依赖分析「回归 + 泛化」两阶段实测报告

> 日期：2026-09-19 ｜ 分支：`worker2-deps-regress`（基线 `416ef8d` → 本次 6 个提交）
> 工作区：`~/harmony-workspace/worker2/portgraph/`
> 结论先行：**阶段1 回归一次通过（e2e musescore 报告与基线字节级一致，recall=100%/precision=95%/bug=0，闭包 89 各分类计数完全一致）；阶段2 泛化在 lmms + OpenShot/libopenshot 两个高星语料外项目暴露 4 类工具 bug（全部修复根因并补 6 个单测，87→93 全过），另定性 2 项数据源缺口与 10+ 项项目特有约定/观察项；全部修复后 e2e 四语料项目报告保持字节级不变（无跨项目回归）**。

---

## 阶段 1：musescore 回归（一次分析正确性验证）

### 1.1 测试设置与流程

- 代码：`worker2-deps-regress` @ `416ef8d`（含全部集成修复）+ 本轮修复
- 语料克隆：`workspace/musescore` @ master `2b540fe`（muse `8c2f77a` / muse_deps `6525edb`，与基线报告同源）
- 流程（严格 fresh，无人工修饰 oracle/overrides）：
  1. `rm portgraph.db && portgraph.py ingest all --offline`（hb-core 4758 formula / cmdpkgs 1248 包 gate=PASS / kb 63 Qt 模块）
  2. `portgraph.py scan workspace/musescore`
  3. `portgraph.py deps musescore --json`
  4. `portgraph.py fetch-deps musescore --dry-run --json`
  5. `tests/e2e/run_e2e.py run --project musescore --fresh-db`（oracle 为 muse_deps 引擎重写版，reviewed=true，25 条）

### 1.2 一次分析正确性核对结果（逐项）

| 核对维度 | 结果 | 明细 |
|---|---|---|
| e2e 指标 | ✅ 与基线完全一致 | recall=100% / precision=95% / bug_candidates=0（基线 §1 同值） |
| 可移植性判定 | ✅ | verdict=blocked，阻塞 8（ALSA/CoreAudio/D-Bus/PulseAudio/systemd/Win32 接口 + qtmod:dbus/x11extras）+ 未知 4，与基线 §2 逐条一致 |
| 直接依赖（depth-1） | ✅ | 34 项 = 18 package（14 解析到 bottle + 4 幽灵）+ 16 qt-module，清单与基线 §5 逐行一致 |
| 依赖分类 | ✅ | link 47 / runtime 51 / build_tools 22 / vendored 13（10 require_source_dep + mnxdom FetchContent + muse/muse_deps 子模块）/ env 4 / qt_modules 21 |
| 可选/条件依赖 | ✅ | jack/mnxdom（选项守卫，required=False + "默认 OFF"注记）、msdfgen/pipewire（条件块 + ohos_note）全部正确标注 |
| 版本校验 | ✅ 无虚假冲突 | 0 条 version_req（muse_deps 清单不带版本），Qt 6.8→satisfied，全部 any/unknown，无 conflict |
| need_port 定性 | ✅ 4/4 正确 | msdfgen/opusenc/pipewire/json_schema_validator——逐一复核 hb-core（4758）与 cmd-pkgs（1248）确无 bottle，源码 pin 在 muse_deps/recipes（与基线 agent 终判一致） |
| fetch-deps 闭包 | ✅ | 89 项：cmd_only 1（ca-certificates）/ need_port 4 / provided 16 / target 1 / vendored 10 / would_download 57，与基线 §4 完全一致 |
| 报告再生成 | ✅ **字节级一致** | 与 `tests/e2e/reports/musescore` 基线 diff 仅 `generated_at` 与 `repo_path`（基线在 worker1 工作区生成） |
| DB 确定性 | ✅ | fresh DB 输出与旧主库 diff 仅 2 处**改进**（icu4c@78/fontconfig 产物版本+bottle URL 补全，旧库为集成前代码所建；分类计数不变） |

**结论：一次分析正确性 PASS，不依赖任何人工修饰。**

### 1.3 计时与上轮对比

| 步骤 | 本轮实测（3 次取值区间） | 上轮报告数字（docs/opt-reports/2026-09-deps-test-worker4.md） |
|---|---|---|
| `ingest all --offline`（fresh DB） | 1.7s | —（上轮无 musescore 计时） |
| `scan`（5729 源文件 + muse/muse_deps 子模块） | 4.44–4.60s | — |
| `deps --json`（按应用名，不重扫） | 4.43–4.52s | — |
| **deps 全流程（scan + 入库 + 报告 --json）** | **8.9–9.1s** | krita 3.05s / strawberry 0.63s / QOwnNotes 0.81s（同机不同项目） |
| `fetch-deps --dry-run`（89 项闭包） | 0.063–0.070s | krita 112 项 0.06s / strawberry 0.05s / QOwnNotes 0.05s |
| e2e harness 全程（私有 DB+scan+analyze+fetch+对账） | 4.65s | — |

对比解读：musescore 上轮未单独计时，无可直接对比的同项目数字；与上轮已测项目比，musescore（5729 源文件 + 约 6300 个 muse_deps 引擎文件、CMake 面更大）9.0s 处于与 krita（6293 文件，3.05s）同数量级、按扫描规模合理放大的区间；**fetch-deps 闭包 BFS 延续上轮结论：非瓶颈**（0.06–0.07s vs 0.05–0.06s）。无性能回归迹象。

### 1.4 阶段1 发现并修复的工具 bug（2 项，commit `1f7cca5` / `ccf958e`）

1. **hb 版本提取：`.7z` 扩展 + 连字符补丁号版本 → 垃圾版本 + bottle URL 404**
   - 现象：musescore deps 报告 env_deps 段 `imagemagick available_version=31.7z`（真实版本 7.1.2-31）。
   - 根因：`_URL_VER_RE` 扩展名清单无 `7z`、版本组不允许 `-N` 补丁段，`ImageMagick-7.1.2-31.7z` 尾部 `31.7z` 被当版本；`bottle_url()` 据此构造 `imagemagick-31.7z_1.arm64_ohos.bottle.tar.gz`。
   - 修复：版本组 `(?:_\d+)? → (?:[_-]\d+)?`、扩展名清单补 `7z`。
   - 验证：全量 4758 formula 重解析仅 14 个版本变化；逐一 curl HEAD 实测 bottle 服务器——**13 个 200 OK**（含修复前 404 的 imagemagick/imagemagick@6），inxi 404 为数据源缺口（见 §3.2）。
2. **deps 分类表缺口：7 个名字被当普通包报"需源码交叉编译"误导警告**
   - `gmock`（链入 `${MODULE_TEST}` 测试目标）→ TEST_FRAMEWORKS；
   - `mmdevapi/msi/taskschd/userenv`（muse `OS_IS_WIN` 块内 target_link_libraries，同块 8 个兄弟库已在表）→ WIN32_SYSTEM_LIBS；
   - `AudioToolbox/Carbon/CoreMIDI`（`OS_IS_MAC` 块内 find_library）→ INTERFACE_BOUND_PACKAGES（platform-iface + 鸿蒙替代说明）。
   - 效果：musescore deps link 47→46、test 0→1、误导警告 9→2；e2e 基线不受影响（报告字节级一致）。

### 1.5 阶段1 观察项（不修，沿基线口径记录）

- `embind`（src/web/audioengine，`Q_OS_WASM` wasm-only 块）/ `gcrashpad`（muse_deps crashpad 源码依赖的内部目标名）：项目特有约定，条件块/目标名不可通用判定。
- `global → hb:global`（GNU Global 标签系统）巧合解析、need_port 幽灵无 source_url、require_dep 条件块不求值（msdfgen/pipewire 偏保守）：均为上轮已记录残留，本轮行为一致。

---

## 阶段 2：GitHub 高星 Qt 项目泛化

### 2.1 项目选择声明

| 项目 | 星标/克隆 | 选择理由 |
|---|---|---|
| **lmms** | ~8.3k★ @ `70aecee`（+11 个 submodule 浅层初始化） | 建议清单内；C++ Qt5(6) 音频工作站，CMake+pkg-config+vcpkg+autotools 混合构建，依赖面宽（音频栈与 musescore 同域不同构） |
| **OpenShot/libopenshot** | `f20829f` | 建议清单内 openshot 的 C++ 核心；Qt6+FFmpeg+JUCE+SWIG 多语言绑定 |
| ~~calibre~~ | — | **声明放弃**：PyQt 应用，超出 C++/CMake 扫描范围（见 §2.4 openshot-qt 实证，行为是"优雅为空"而非崩溃） |
| openshot-qt | `047f4a2` | 仅作 PyQt 范围边界实证，非分析对象 |

避开 e2e 语料四项目（tdesktop/musescore/keepassxc/qbittorrent）与上轮已用项目（krita/strawberry/QOwnNotes）。

### 2.2 lmms（5273 源文件，Qt 5.15/6.0，cmake+qmake）

**人工对照基准**：根 CMakeLists.txt（WANT_* 选项 + FIND_PACKAGE 块）、cmake/modules/Find*.cmake（自研模块 22 个）、vcpkg.json、.gitmodules（11 子模块）、zynaddsubfx/calf/swh/veal/adplug/gme 等子模块构建文件。

**正确检出（抽查确认）**：FFTW `>=3.0.0`（pkg_check，别名归并 unknown 属设计口径）、gtk+-2.0 `>=2.12.0` → hb:gtk+ 2.24.33 satisfied（hb 确有 GTK2 formula）、jack `>=0.77` → 1.9.22 ✓、Portaudio `>=19` → 19.7.0 ✓、X11/x11extras → platform-iface/blocked ✓、libjack dlopen → cmdpkgs:jack ✓、WANT_SDL(ON)→SDL2 required、WANT_JACK→optional ✓、zynaddsubfx 子模块依赖（fftw/boost/mxml/liblo）正确并入、vendored 22 项（子模块+ExternalProject+FetchContent pthreads4w 均带锁定信息）。

**修复的 4 类工具 bug（commit `2a64818` / `ddeb1d0`）**：

| # | 问题 | 根因 → 修复 |
|---|---|---|
| 1 | `PackageHandleStandardArgs` 幽灵 | `_FINDPKG_SKIP` 内错名 `findpackagehandlestandardargs`（带 Find 前缀永不匹配）→ 改正 + `CMAKE_BUILTIN_PACKAGES` 消费侧分类 |
| 2 | `Perl`/`PythonInterp` 主机解释器当运行时依赖（perl 连了 hb:perl 边） | BUILD_TOOL_FINDPKG 补 perl/pythoninterp（图侧过滤 + 报告侧 build-tool） |
| 3 | `CxxTest` 测试框架当运行时链接 | TEST_FRAMEWORKS 补 cxxtest |
| 4 | `OggVorbis` 复合模块名幽灵 | lmms FindOggVorbis 内部实为 find_package(Ogg/Vorbis)（两真依赖已分别检出）→ PKG_ALIASES oggvorbis→libvorbis |
| 5 | `libpulse`/`asound`/`pulse` 报 need_port | PulseAudio/ALSA 的 pkg-config 名与库名形态 → INTERFACE_BOUND_PACKAGES 补三项（platform-iface + 鸿蒙 AudioRenderer 指引） |
| 6 | `OpenGL` 幽灵 | OHOS 为 GLES/EGL 系统能力 → _FINDPKG_SKIP + CMAKE_BUILTIN_PACKAGES（system-lib + 适配说明） |
| 7 | `fluidsynth-1/2/3`/`sfftw` 版本化库名不归并 | veal FindFluidSynth 的 macOS dylib 变体 / swh 单精度 fftw → PKG_ALIASES 归并 |
| 8 | `FluidSynth` 报告侧误报"无产物" | 图侧靠 dashless 兑底解析 cmdpkgs:fluid-synth 而报告侧阶梯无 dashless 步骤（口径分裂）→ 显式别名 fluidsynth→fluid-synth（2.2.0 vs 2.4.6 = satisfied） |

**效果**：link 79→70 / build_tools 22→26 / test 0→1 / 闭包 132→125 / **need_port 17→12** / 误导警告 24→17。剩余 12 项 need_port 逐一核实**均无 bottle，unknown-ok 正确**：carla-native-plugin、carla-standalone（Carla 插件宿主）、fltk/ntk/ntk_images（zyn GUI）、gig（libgig）、oss、sndio（BSD 音频）、sdl（SDL1）、suil-0、suilmodules、wine（WANT_VST）。

**观察项（项目特有约定/设计保守，记录不修）**：
- `sdl3` 来自 `cmake/apple/MacDeployQt.cmake`（macOS 打包脚本 pkg_check）→ 误报（有 bottle，仅多下载）；打包/deploy 脚本无通用识别规则。
- `SDL`（v1）来自 game-music-emu `player/`（`add_subdirectory(... EXCLUDE_FROM_ALL)` 不构建）→ 误报；扫描器无 EXCLUDE_FROM_ALL 感知。
- `FLTK` 软可选（无 REQUIRED/QUIET，失败仅降级 Zyn GUI）→ 保守 required=True，属 find_package 语义不可判定。
- `bash-completion` conflict=真（veal vendored configure.ac 要求 >=2.0，hb 为 1.3——Homebrew bash-completion 即 1.x 线）；bash-completion 本身是主机侧补全包。
- vendored 展示名噪音（`src/3rdparty` 父目录名、`doc/wiki` 文档子模块）；`suilmodules` 自研 Find 模块名幽灵。
- swh/veal vendored LADSPA 插件内 target_link/AC_CHECK_LIB 噪音（blo/db/gverb/iir/mx/pitchscale/rms/lash/libbinio）：**不跳过 submodule 路径是有意设计**（muse 反例：框架 submodule 的 ExtDepsManifest 必须扫描），语义边界待议。
- `qt.min_version=None`：`find_package(Qt${QT_VERSION_MAJOR} ${LMMS_QT_MIN_VERSION} ...)` 版本经变量未解析（组件变量已支持，版本变量未支持）——次要缺口。

### 2.3 OpenShot/libopenshot（316 源文件，Qt6，cmake）

**人工对照基准**：根/src CMakeLists.txt（option 默认值：ENABLE_MAGICK ON / ENABLE_OPENCV OFF / ENABLE_WAYLAND_CAPTURE ON）、bindings/（SWIG 五语言绑定）、cmake/Modules/Find*.cmake、external/godot-cpp 子模块。

**正确检出**：Qt6 Core/Gui/Widgets required ✓、`FFmpeg REQUIRED` ✓、`Resvg`→hb:resvg ✓、`ImageMagick`（阶段1 修复的 7.1.2-31 在此真实复现）✓、`OpenCV 4`→cmdpkgs 4.9.0（ENABLE_OPENCV OFF → required=False，选项守卫正确）✓、`Catch2 QUIET`→test 分类 ✓、`Protobuf 3` vs hb 12=satisfied ✓、godot-cpp vendored ✓、wayland-capture dlopen 提示 ✓。

**修复的 4 组工具 bug（commit `f543d9f`）**：

| # | 问题 | 根因 → 修复 |
|---|---|---|
| 1 | SWIG 绑定工具链当运行时依赖：`SWIG/Java/JNI/Ruby/PythonLibs` 连了 hb:ruby/hb:swig 运行时边、java/jni/pythonlibs 成 need_port 幽灵 | bindings/ 的 find_package 均为主机侧绑定生成 → BUILD_TOOL_FINDPKG 补 swig/ruby/java/jni/pythonlibs |
| 2 | `libpipewire-0.3` 解析阶梯缺组合形态 | 需同时去 lib 前缀+版本后缀（单项剥离均不命中）→ resolve_pkg_name/resolve_package 补 stripped[3:] 组合候选（单测构造 hb:pipewire 验证） |
| 3 | `dbghelp`/`imagehlp` win32 缺口库 | WIN32 块异常处理/DirectShow（同块 ole32/strmiids/uuid 已在表）→ WIN32_SYSTEM_LIBS |
| 4 | `opencv_core/video/highgui/dnn/tracking` 5 条独立幽灵 | OpenCV 4 导入目标名字面量（ENABLE_OPENCV OFF 块内）→ PKG_ALIASES 归并到 opencv；`jsoncppd`（Findjsoncpp debug 变体）→ jsoncpp |

**效果**：link 30→19 / build_tools 11→18 / 闭包 74→68 / **need_port 7→4**。剩余 4 项逐一核实**均无 bottle，unknown-ok 正确**：`babl`（色彩空间转换）、`libpipewire-0.3`/`libspa-0.2`（Wayland 屏幕捕获，Linux-only 默认 ON）、`openshotaudio`（JUCE 音频库，REQUIRED）。

**观察项**：`Protobuf` required=True——位于 ENABLE_OPENCV 块内 `else()` 分支（OpenCV_FOUND 后才求值），选项守卫对 else/elseif 保守不求值属**已文档化设计**；`babl`/`babl-0.1` 双条目（find_package 与 Findbabl find_library，闭包已归并，报告侧未合并，cosmetic）。

### 2.4 openshot-qt（PyQt 范围边界实证）

扫描结果：`build=unknown / sources=20 / qt_modules=[] / deps_linked=[]`——**优雅为空、不崩溃**。确认：portgraph deps 分析面向 C++/CMake/qmake 工程；PyQt 应用（openshot-qt、calibre 同类）在其范围外，需另行评估（Python 侧依赖 + Qt 运行时打包），此为**范围边界**而非缺陷。

---

## 3. 问题定性汇总

### 3.1 工具 bug（已全部修复 + 单测，5 个提交）

| 类别 | 项 | 影响 |
|---|---|---|
| 数据源解析（ingest） | imagemagick/imagemagick@6 版本 `31.7z`/`56.7z` → bottle URL 404 | fetch-deps 下载失败 |
| 分类表缺口 | gmock/cxxtest（test）、mmdevapi/msi/taskschd/userenv/dbghelp/imagehlp（win32）、AudioToolbox/Carbon/CoreMIDI（macOS 框架）、asound/pulse/libpulse（音频平台接口）、opengl（系统 GLES） | 误导性"需源码交叉编译"警告 / need_port 误报 |
| 主机工具误判 | perl/pythoninterp/pythonlibs/swig/ruby/java/jni 当运行时依赖 | 幽灵/无效下载 |
| 解析阶梯 | PackageHandleStandardArgs 错名、lib 前缀+版本后缀组合缺失、fluidsynth 报告侧口径分裂、oggvorbis/fluidsynth-N/sfftw/opencv_*/jsoncppd 不归并 | 幽灵节点/重复条目 |

### 3.2 数据源缺口（数据侧问题，非工具问题）

1. **inxi bottle 未发布**：formula 声明 arm64_ohos bottle（有 sha256），但 bottle 服务器单/双横线全变体 404——修复版本提取后新构造的 URL 同样 404。
2. **cmd-pkgs 命名含版本**：`sdl12-compat-1.2.68`（版本嵌在包名里）——`sdl`(SDL1) 无法稳定别名（升级即失效）；SDL1 检出维持 unknown-ok。

### 3.3 项目特有约定 / 已文档化设计（记录不修）

embind（wasm-only 块）、gcrashpad（muse_deps 内部目标）、MacDeployQt.cmake 的 sdl3（打包脚本）、gme player 的 SDL（EXCLUDE_FROM_ALL）、FLTK/babl 软可选 find_package、Protobuf else-分支保守、swh/veal vendored LADSPA 噪音（submodule 不跳过是 muse 反例要求）、vendored 展示名噪音、bash-completion 量纲 conflict（数据为真）、qt 版本经 set() 变量、global→hb:global 巧合（上轮残留）、need_port 幽灵无 source_url（上轮残留）。

---

## 4. 回归安全性

- **e2e 四语料**：tdesktop（53%/60%/2）、musescore（100%/95%/0）、keepassxc（100%/23%/0）、qbittorrent（100%/100%/0）——全部修复落地后**三次**全量重跑，报告与已提交基线**字节级一致**（diff 仅时间戳/repo_path），闭包计数逐项目核对不变。
- **单元测试**：87 → **93 全过**（新增 6 个：TestMusescoreRegressTables、test_lmms_regress_classifications、test_openshot_bindings_and_ladder、test_openshot_ladder_node_resolution、test_openshot_win32_and_target_merge、test_lmms_iface_libnames_and_merge + URL 版本提取用例扩充）。
- **bottle URL 真实性**：14 个版本变化 formula 逐一 HEAD 实测（13×200 / 1×404=数据源缺口）；imagemagick 修复前后 URL 对照（404→200）。

## 5. 提交清单（worker2-deps-regress，基线 416ef8d）

| commit | 内容 |
|---|---|
| `1f7cca5` | fix(ingest): 7z/连字符版本 URL 提取修复（imagemagick 31.7z→7.1.2-31）+ 全量 formula 验证 |
| `ccf958e` | fix(deps): musescore 回归暴露的 3 处表缺口（gmock/win32 库/macOS 框架） |
| `2a64818` | fix(deps): lmms 泛化轮暴露的 5 处分类/解析缺口 |
| `f543d9f` | fix(deps): libopenshot 泛化轮暴露的绑定工具链/win32 库/目标名归并缺口 |
| `ddeb1d0` | fix(deps): lmms 深挖轮——平台接口库名/版本化库名归并/fluidsynth 口径分裂 |
| （本次） | docs: REGRESS-REPORT.md |
