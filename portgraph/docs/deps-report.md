# deps — 综合依赖分析（Agent 工具）

给定一个 Qt 工程（路径或已扫描的应用名），产出**依赖全景画像**：
每个依赖是什么角色、版本要求多少、鸿蒙产物从哪拿。

```bash
python portgraph.py deps <项目路径|应用名> [--json]
```

与既有命令的分工：

| 命令 | 回答的问题 |
|---|---|
| `analyze` | 能不能移植（portable/blocked/uncertain + 阻塞点） |
| **`deps`** | **依赖全景：谁要编译产物、谁是构建工具、谁只运行时用、版本范围是否满足** |
| `fetch-deps` | 产物怎么拿（bottle 直下 / manifest / 集成片段） |

---

## 依赖角色模型

一个工程的依赖按**角色**分五类（一个依赖可同时出现在多个视角，如 gmp 既是
link 又因被 mpfr 传递依赖而出现在 runtime）：

| role | 含义 | 缺失后果 | 来源证据 |
|---|---|---|---|
| `link` | **编译产物依赖**：目标侧 headers + .so/.a，交叉编译/链接应用时必须存在 | 编译/链接失败 | `find_package`、`pkg_check_modules`、Conan/vcpkg 清单、`#include` 三方头、qmake `LIBS += -lfoo`、KF 组件 |
| `build-tool` | **编译器/构建工具依赖**：构建机运行，不部署到设备 | 构建无法进行（交叉编译产物不受影响） | `cmake_minimum_required`、C++ 标准、`find_program`、`execute_process/add_custom_command COMMAND`、`find_package(ECM/gettext/…)` |
| `runtime` | **运行时依赖**：设备侧 .so，不参与编译但缺了跑不起来 | 部署后 dlopen/链接失败 | link 依赖的传递闭包（hb runtime 边）、`dlopen`/`QLibrary`/`QPluginLoader` 字面量 |
| `test` | 测试专用，不进发行包 | 测试无法构建 | `find_package(GTest/Catch2/…)`、`enable_testing` |
| `vendored` | 项目内自带源码，随项目编译，无需外部产物 | 无（锁定提交在仓库内） | `.gitmodules`、`3rdparty/` 等目录 |
| `provided` | Qt 模块等由 Qt SDK / 鸿蒙框架提供 | 无（随 Qt for HarmonyOS 部署） | `QT +=`、`find_package(Qt5/6 COMPONENTS …)`、`#include <Qt…>` |

特殊 kind：`system-lib`（zlib/openssl/icu/pthread 等 OHOS 系统自带库，
link 但无需自带产物）、`framework`（KDE Frameworks 组件，需源码交叉编译）。

## 版本范围

每个 link 依赖可携带多源版本约束，**同时存在时取最差结果**（任一冲突即冲突）：

| 约束来源 | 形态 | 示例 |
|---|---|---|
| `find_package` 最低版本 | `min_version` | `find_package(ZLIB 1.2 REQUIRED)` |
| pkg-config 约束 | `version_req` | `pkg_check_modules(FF "libavcodec >= 58")` |
| Conan 范围 | `version_range`（原样保留） | `zlib/[>=1.2 <2]` |
| vcpkg 约束 | `version>=` | `vcpkg.json` dependencies |
| Qt 版本 | `qt.min_version` | `find_package(Qt5 5.15 …)` vs 鸿蒙可用 5.12/5.15/6.12 |

`version_check` 取值：`satisfied`（满足）/ `conflict`（冲突，进 warnings）/
`any`（无约束）/ `unknown`（无可用版本可比，含 conan 范围仅近似取首个
`>=x` 检查）。

## 报告结构（--json）

```jsonc
{
  "project": {"name", "root", "build_system", "version", "sources"},
  "qt": {"major", "min_version", "check", "available_on_ohos",
         "modules": [{"module", "status", "required"}], "kf_components"},
  "toolchain": {"cmake_min", "cxx_standard", "compiler", "cxx_note",
                "tools": [{"tool", "how", "provided_by": "host|qt-sdk"}],
                "has_testing"},
  "link_deps": [{
      "name", "kind", "required", "min_version", "version_req",
      "version_range", "version_check", "components", "evidence": [...],
      "resolved_node", "port_status", "available_version",
      "artifact": {"ready", "provided", "source", "repo_url", ...},
      "ohos_note"}],
  "runtime_deps": [{"name", "version", "artifact", "needed_by": [...]}],
  "dynamic_loads": [{"name", "resolved_node", "artifact", "how"}],
  "test_deps": [{"name", "source"}],
  "vendored": [{"name", "path", "url"}],
  "counts": {...}, "warnings": [{"level": "warn|info", "msg"}]
}
```

## Agent 决策表（按角色）

| 角色 | Agent 应该做什么 |
|---|---|
| `link`（有产物） | `fetch-deps` 会下载；版本 `conflict` 时先确认是否可用旧版或源码编译新版 |
| `link`（无产物） | 拿 `artifact.repo_url`/`source_url` 源码交叉编译；`[optional]` 的可评估裁剪 |
| `build-tool` | 构建机准备即可（Windows/Linux/macOS 均可）；`provided_by=qt-sdk` 的随 Qt SDK |
| `runtime` | 部署到 `entry/libs/arm64-v8a/`；由 `fetch-deps` 一并拉取（bottle 不捆绑依赖） |
| `test` | 发行包不需要；如需在鸿蒙跑测试才处理 |
| `vendored` | 随项目一起编译；注意 shallow clone 后 submodule 未初始化 |
| `system-lib` | 直接链接系统库，无需自带产物 |

## 依赖闭包与扫描口径

- **版本信息来自构建文件原文**：`find_package` 参数、pkg-config spec、
  Conan/vcpkg 清单、`.gitmodules`；`deps` 传路径时自动入库（幂等重扫），
  传应用名时用 `scan` 记录的 `root_<app_id>` meta 回溯项目路径
- **runtime 传递闭包**沿 hb/cmd-pkgs 图的 `runtime` 边递归（跳过 macos
  条件与 provided 节点），与 `fetch-deps` 口径一致
- **动态加载只识别字符串字面量**；变量拼接（`QLibrary(name + ".so")`）
  无法静态确定，会缺报——运行时验证仍需以设备为准
- 工具链检测只记**已知工具名或命中启发式后缀**（`*-config`/`*-scanner`/
  `*-codegen`/`glib-*`）的 `COMMAND`/`find_program` token，避免把任意
  可执行名当依赖

## fetch-deps manifest 的 role 字段

`fetch-deps` 的 manifest 每个条目新增 `role`（按闭包深度判定）：

- `link`：应用的直接依赖（depth 1，编译/链接需要）
- `runtime`：传递依赖（depth ≥2，设备侧 .so）
- `provided`：Qt 模块；`target`：应用自身

manifest 顶层新增 `roles` 计数。深度判定是**图口径**的近似；带版本范围/
REQUIRED/OPTIONAL 语义的精确分类用 `deps` 报告。

## 已知限制

- find_package 名称 → hb 包名对齐依赖 `kb_seed.resolve_package` 别名表，
  同名异义（如多精度库 MPC vs 音乐播放器 mpc）可能错配，产物 URL 落地
  前应人工核对
- Conan 范围检查为近似（取首个 `>=x`）；`<y` 上界不参与比较
- meson/autotools 工程只吃到 Conan/vcpkg/include 线索，构建文件本身
  的 `dependency('foo', version: …)` 未解析
