# 回归 + 泛化测试报告：deps 性能基准与 GitHub 热门 Qt 项目泛化

> 分支 `worker4-deps-regress`（基线 416ef8d，含全部集成修复）
> 测试时间：2026-09-19 | 工作区：`portgraph/`
> 结论先行：**性能无回退且有提升（gen-a 3.70s→3.17s，优于上轮修复态 3.21s；相对 f98a2e7 基线 3.9x）**；过程中暴露并修复 **6 个真 bug**（1 个性能 + 5 个正确性，含 cloner submodule 拉取静默失效这一影响所有 submodule 型项目的根因）；泛化项目 gen-h/gen-o 分析质量良好，附带修复 dynamic_loads 平台守卫误报。单测 65→94 全过。

---

## 一、阶段 1：性能回归（4 e2e 语料 + 3 泛化项目）

### 1.1 数据源与环境

- 主库重建：`python portgraph.py ingest all` → 6069 节点（hb 4758 / cmdpkgs 1248 / kb-seed 63）/ 9504 边，与上轮口径一致。
- 计时方法：deps 全流程（scan + 入库 + 报告，含 `--json`）与 fetch-deps `--dry-run` 闭包，各 3 次取中位数。
- **基准方法勘误**：fetch-deps 传参是 app 名（`gen-a`）而非路径（`workspace/gen-a`），后者静默退出（exit 1）——上轮报告的 `fetch-deps <app>` 口径本次确认为 app 名，所有 fetch 计时已用正确参数重测。

### 1.2 A/B 对照（git worktree 隔离，同一克隆、同一 DB 重建流程）

| 项目 | f98a2e7（上上轮基线） | c04060a（上轮修复态） | 416ef8d（集成本轮实测） | 416ef8d+NOCASE 修复（bddcd59） |
|------|------|------|------|------|
| gen-a deps | 12.25s | 3.21s | **3.70s（+15%回退）** | **3.17s** |
| gen-e deps | 2.13s | 0.69s | 0.82s（+19%） | **0.58s** |
| gen-f deps | 3.21s | 0.86s | 1.06s（+23%） | **0.72s** |

**回退定位**（cProfile 前后对照）：集成（c04060a→416ef8d）新增的别名表/解析阶梯使 `find_node_by_name` 调用增多，而该函数 `lower(name)=lower(?)` 无法命中 `idx_nodes_name`（BINARY 排序）索引 → 每次全表扫描 6069 行，gen-a 报告期 350 次查找共 0.4s。

**修复（bddcd59）**：`name=? COLLATE NOCASE` + `idx_nodes_name_nocase` 函数索引。语义等价（SQLite `lower()`/`NOCASE` 均仅折 ASCII；全库 6159 名逐名等价校验通过；旧库经 `init_db` 的 `CREATE INDEX IF NOT EXISTS` 自动补索引）。350 次查找 0.4s→0.002s。

### 1.3 最终性能基准（全部修复后，完整克隆状态）

| 项目 | deps 中位数 | fetch-deps --dry-run | 说明 |
|------|------|------|------|
| gen-a | **3.17s** | 0.06s | 22769 源文件，无 submodule |
| gen-e | 0.60s | 0.06s | 闭包 61 项 |
| gen-f | 0.87s | 0.06s | 8 个 submodule 就位后（上轮为空目录扫描） |
| corpus-a | 3.66s | 0.06s | 6358 源文件（35 submodule 就位；集成基线生成时仅 2932） |
| corpus-b | 4.29s | 0.06s | 5729 源文件（corpus-b-core/corpus-b-deps 就位） |
| corpus-c | 0.53s | 0.06s | 884 源文件 |
| corpus-d | 0.50s | 0.06s | 710 源文件 |

- 与上轮可比结论：gen-a/gen-e **优于**上轮修复态（3.21/0.69），gen-f 在扫描范围扩大（submodule 补齐）的前提下仍持平（0.87 vs 0.86）；**无性能回退**。
- fetch-deps 闭包 BFS 恒 0.06s，非瓶颈（与上轮结论一致）。

### 1.4 正确性回归中暴露的 4 个 bug（阶段1顺带修复）

首轮 e2e 回归 corpus-b 指标异常（recall 100%→56%），stash A/B 证明与我的性能修复无关，根因排查链条如下：

| # | bug | 根因 | 修复 |
|---|-----|------|------|
| 1 | **cloner submodule 拉取静默失效**（全项目级根因） | `git submodule update init ...` 裸 `init` 缺 `--` 被 git 当 pathspec 报错，`_init_submodules` 对 returncode≠0 完全静默 → 复用克隆的 submodule 永远拉不起来（corpus-a 35 个 submodule 全空、corpus-b-deps 空） | `--init` + 失败 stderr 可见（c069898）；复用路径实测拉起 |
| 2 | **wrapper 依赖被藏掉**（corpus-a：openal/ada/zlib/openssl/bt 全漏） | submodule 就位后 `external_X` 成为项目内目标（defined），叠加 vendored 路径跳过，wrapper 声明的真实依赖双重不可见 | wrapper 签名（`add_library(external_X)`）文件不按 vendored 跳过；wrapper 目标被链接时透传底层库名；wrapper 内部守卫（DESKTOP_APP_USE_PACKAGED）只切换获取方式不套 optional（c069898） |
| 3 | **OR 守卫误判 optional** | `if (X OR LINUX)` 因 LINUX 在鸿蒙恒真必然激活，旧逻辑见 OFF 选项正向引用即整帧标 optional | 任一恒真析取项（LINUX/UNIX/NOT WIN32/…）→ 不标 optional（c069898） |
| 4 | **meson/autotools 检测器缺 vendored 跳过** | CMake 检测器有 `_is_vendored_path` 跳过，`_absorb_meson`/`_absorb_autotools` 没有 → ThirdParty/nimf 的 configure.ac（anthy/gtk+/m17n）、xdg-desktop-portal 的 meson.build（libgeoclue/pipewire）泄漏进 depth-1 | 补齐同口径跳过（c069898） |

**e2e 最终指标**（submodule 完整初始化后重新生成基线，1270e53）：

| 项目 | 集成基线(416ef8d)¹ | 本轮最终 | 变化归因 |
|------|------|------|------|
| corpus-a | 53% / 60% / 2 | **71% / 38% / 4** | 2932→6358 源文件；wrapper 透传恢复 openal/ada/zlib/openssl/bt/boost/lz4；余 4 候选人工核验：breakpad/crashpad 为 cmake_helpers 内 add_subdirectory vendored 源码（定性正确）、libxcb/libdispatch 为真实 Linux 依赖（README 漏列） |
| corpus-b | 100% / 95% / 0 | 100% / 95% / 0 | 不变 |
| corpus-c | 100% / 23% / 0 | 100% / 23% / 0 | 不变 |
| corpus-d | 100% / 100% / 0 | 100% / 100% / 0 | 不变 |

¹ 注意：集成基线本身是在 cloner bug 下（submodule 未初始化的克隆）生成的，corpus-a 旧基线 53% 是"扫描范围不完整但查全率口径偏宽"的产物（cmark-gfm/ada 等经 external_X 幽灵机制计入）；本轮 71% 是完整扫描下的真实查全率。corpus-b/corpus-c/corpus-d 旧基线生成时 submodule 状态正常，故不受影响。

**决定性 A/B**：416ef8d 原代码在当前完整克隆上跑 corpus-a = 24%/57%/7，与本轮代码同克隆结果逐字段一致（仅差 wrapper/OR/vendored 修复带来的恢复项）——证明指标变化 100% 来自克隆条件与上述修复，无其他代码行为漂移。

### 1.5 分析正确性抽查（gen-e，逐项核对）

- **分类**：36 条 link 全部与源码一致——macOS 框架（AppKit/Carbon/CoreAudio/…）→ platform-iface ✓；dwmapi → win32-system-lib ✓；Threads → system-lib ✓；GTest → test ✓；Boost/ICU/TagLib/OpenSSL find_package 行号（175/179/214/171）与 CMakeLists 原文一致 ✓；gio/gobject/gio-unix 归并 glib ✓；gstreamer-base 归并 gstreamer ✓。
- **版本**：TagLib `>=1.12`（find_package(TagLib 2.0) + 多源合并）vs hb 2.3.2 = satisfied ✓；libchromaprint `>=1.4`、libgpod `>=0.7.92`、libmtp `>=1.0` 与源码 :207/:210/:211 完全一致 ✓；sqlite `>=3.9` → unknown + 量纲警告（库主版本 vs 包版本口径，符合设计）✓。
- **need_port 定性**（DB 逐名验证）：libchromaprint/libgpod/libmtp/libpulse/kdsingleapplication/backtrace 无 hb/cmdpkgs 包 → need_port 正确 ✓；gstreamer-app/audio/pbutils/tag（plugins-base 组件，上轮 tarball 实证）✓；libsparsehash→google-sparsehash、libebur128、libcdio 解析 ported ✓。
- **发现小瑕疵（未修）**：`find_package(KDSingleApplication-qt${QT_VERSION_MAJOR} 1.1.0 REQUIRED)` 变量内插后版本号 1.1.0 丢失（名字归一正确，need_port 定性不受影响）。

### 1.6 单测结构 bug（顺带修复）

`tests/test_port_graph.py` 的 `if __name__: unittest.main()` 位于文件中部（1601 行），其后 13 个测试类（22 个用例，多轮 merge 追加所致）**从未被执行过**——历史报告的"56/65 全过"实为部分执行。已移至文件末尾，全量 94 用例全过。

---

## 二、阶段 2：GitHub 热门 Qt 项目泛化

**选择声明**：gen-o（cnr-isti-vclab/gen-o，Qt5 三维网格处理，~4.5k star）+ gen-h（gen-h/gen-h，Qt6 文本编辑器，~2k star）。原拟 speedcrunch，**GitHub 仓库已关闭**（仅剩迁移声明，项目移至 Bitbucket），弃选改 gen-h——已避开 e2e 四项目与其他 worker 选择。

### 2.1 检出完整性

| 项目 | 克隆 | submodule | 说明 |
|------|------|------|------|
| gen-o | shallow clone 1m55s（431MB 工作区） | src/vcglib ✓ 就位（修复后 cloner） | HEAD 71e7b0b |
| gen-h | shallow clone 12s | 无 submodule | HEAD 37652c5 |

cloner `--init` 修复在两个新项目上直接验证：gen-o vcglib 一次拉起（该 submodule 在旧代码下会静默失败）。

### 2.2 gen-h：分析质量优秀

- **真实依赖**：Qt6（≥6.4，14 组件）+ uchardet（pkg_check_modules，CMakeLists:36）——**全部正确检出**；闭包 13 项（provided 11 = Qt 模块 + qtpromise vendored，would_download 1 = uchardet 0.0.7，target 1）。
- **平台定性正确**：Qt D-Bus、QtWebEngine → blocked（与 KB 模块状态一致，移植阻断点如实呈现）；Core5Compat → 映射 core ported ✓。
- **发现并修复 1 个 bug（5985fb3）**：`QLibrary("kernel32")`（singleapplication.cpp:163，位于 `#if defined(Q_OS_WIN)` 块内）被误报为运行时动态加载。修复：宏栈机制从 project_scanner 移驻 qt_scanner（re-export 兼容），dynamic_loads 按行排除 platform-excluded（预过滤保证不损性能）。附带修复 qt_scanner 缺 `import warnings` 导致宏表达式求值 NameError 被吞为保守真。
- 残留小噪声：`qtpromise.tests.utils`（vendored 库 src/ui/libs/qtpromise 的测试 cmake 目标名混入 link 名单，1 条，不影响 need_port/闭包）。
- **性能**：deps 0.18s / fetch-deps 0.05s。

### 2.3 gen-o：主依赖正确，发现 vendored 子树内噪声

- **主依赖正确**（src/CMakeLists.txt）：Eigen3/GLEW/OpenGL/muparser/openctm/lib3ds 全部检出；lib3ds→hb 1.3.0 ✓、eigen/fftw/opencv→ported ✓；Qt5 ≥5.15 检出 ✓。
- **need_port 定性核验**（DB 验证）：muparser/openctm/GLEW 无鸿蒙包 → need_port 正确；OpenGL → need_port 合理（OHOS 为 OpenGL ES，需 EGL/GLES 适配）。
- **vcglib submodule 为 vendored** ✓（`src/vcglib`、`src/external` 正确识别），但其内部 **vcglib 自身的示例/测试工程**（`src/vcglib/apps/*`、`src/vcglib/eigenlib/unsupported/test/*`）的 find_package/qmake LIBS 泄漏进应用 depth-1：Adolc/CUDA/HIP/GoogleHash/MPREAL/GLFW3/embree/GLUT/freeglut/cholmod 系列等约 20 条（gen-o 主构建不编译这些目标）。主 CMakeLists 真实依赖不受影响，闭包 21 项中 need_port 10 里有约一半源于此噪声。
- **Qt major 误判**：报告 `major: 4`（vcglib 遗留 qmake 工程的 QT 变量污染），主工程实为 Qt5 ≥5.15；模块表混入 qtcore/qtgui 小写 unknown 变体。
- **性能**：deps 2.94-3.00s（22k+ 源文件）/ fetch-deps 0.05s。

### 2.4 问题定性汇总

| 问题 | 项目 | 定性 | 处置 |
|------|------|------|------|
| kernel32 dynamic_load 误报 | gen-h | defect（平台宏守卫未过滤） | **已修**（5985fb3）+ 2 单测 |
| cloner submodule 静默失效 | 全部 submodule 项目 | defect（语法错误+吞错） | **已修**（c069898）+ 单测 |
| vendored 子树内示例/测试工程泄漏 | gen-o（vcglib apps/eigenlib tests） | defect（方向：submodule 内非构建目标目录的深度约束） | 未修，记录残留（见三） |
| qtpromise.tests.utils 目标名混入 | gen-h | defect（轻微，1 条噪声） | 未修，记录残留 |
| Qt major 误判（4）| gen-o | defect（轻微，遗留 qmake 污染 hint） | 未修，记录残留 |
| KDSingleApplication-qt 版本号丢失 | gen-e | defect（轻微，${VAR} 内插后版本 token 丢失） | 未修，记录残留 |

---

## 三、残留项（未修，供后续处理）

1. **submodule 内非构建目录的依赖泄漏**（gen-o：vcglib 的 apps/eigenlib/unsupported test 工程泄漏约 20 条 depth-1 噪声）。方向：结合 .gitmodules 子模块路径 + "主构建不含的子目录"（apps/test/unsupported 命名特征）做深度约束；需避免误伤 corpus-b corpus-b-core 这类"依赖清单在 submodule 里"的正常场景。
2. **vendored 库测试目标名混入 link 名单**（gen-h qtpromise.tests.utils；路径 src/ui/libs/ 无 vendored 特征段）。
3. **Qt major hint 污染**（gen-o：遗留 qmake 工程把主工程 Qt5 判成 4；建议主 CMakeLists 的 find_package(QtN) 优先级高于 qmake hint）。
4. **find_package 名含 ${VAR} 时版本 token 丢失**（gen-e KDSingleApplication-qt 1.1.0）。
5. **e2e harness 对已解析改名的漏检匹配**（liblzma→xz 已通过 kb_seed.ALIASES 打通；同类情况建议 harness 侧统一消费 PKG_ALIASES）。
6. **harness grep 取证范围**（libxcb/libdispatch 误报候选：引用位于 submodule wrapper 内，harness 构建文件检索未覆盖；建议纳入 submodule 路径）。
7. 上轮残留 #2/#3/#4（find_library debug 后缀、结构化平台块解析、qt_scanner 共享读缓存）依旧有效。

---

## 四、修复与提交清单

| 提交 | 内容 |
|------|------|
| bddcd59 | perf：find_node_by_name NOCASE 函数索引（回退修复）+3 单测 |
| c069898 | fix：cloner `--init` 语法 + wrapper 三重透传 + OR 守卫语义 + meson/autotools vendored 跳过 + liblzma 别名 + 单测结构修复 |
| 1270e53 | test(e2e)：基线以完整克隆重新生成 + breakpad/crashpad 备注更新 |
| 5985fb3 | fix：dynamic_loads 平台宏守卫过滤（宏栈移驻 qt_scanner）+2 单测 |
| （本提交） | docs：REGRESS-REPORT.md |

单测 65→**94 全过**（含历史从未执行的 22 个存量用例）；e2e 四项目最终指标见 §1.4。

---

## 五、复现命令

```bash
cd portgraph
python tests/test_port_graph.py                        # 94 tests OK
python portgraph.py ingest all                         # 主库 6069 节点
# 性能（3 次取中位）
/usr/bin/time -f "%es" python portgraph.py deps workspace/gen-a --json > /dev/null
/usr/bin/time -f "%es" python portgraph.py fetch-deps gen-a --dry-run > /dev/null   # 注意：app 名不是路径
# e2e 回归（submodule 完整克隆）
python tests/e2e/run_e2e.py run --all --fresh-db
# 泛化项目
python portgraph.py deps workspace/gen-o --json
python portgraph.py deps workspace/gen-h --json
python portgraph.py fetch-deps gen-o --dry-run
# A/B（worktree 隔离）
git worktree add .ab/c04060a c04060a   # workspace 内符号链接共享克隆后同流程计时
```
