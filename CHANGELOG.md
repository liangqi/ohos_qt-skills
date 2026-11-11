# 变更日志

> 外部知识库（开发者版）发版记录。版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。
> 版本对象 = 外部仓整包（Qt 公开子集 + 内嵌 ohos-common-kb + kb-init skill + 根文档）。
>
> - **MAJOR** — 破坏性：删/移走用户依赖的页、`audience` 由 public→internal、目录重排致旧链接断、铁律/API 映射被证伪并反转
> - **MINOR** — 内容新增：新页/新节/新 API 映射条目/新 task 类型/内嵌新 KB 或 skill
> - **PATCH** — 内容修正：typo/措辞修正、错误解决方案更新、Qt 参考版本 bump
>
> 发版流程：在 `trunk` 上打 `vX.Y.Z` tag，并从该 tag 拉 `release/vX.Y.Z` 归档（见 CONTRIBUTING.md）。
> 每版的 `RELEASE-MANIFEST.yaml` 记录页面计数 + `content_tree_sha256`，可复现。

---

## v3.0.0-rc8 — 2026-11-11

按"只补索引、收敛事实块"的最小方案做了一轮内容核查（先只读测绘，再改）。测绘结论：
132 页两两比对，**页级重复为 0 对**；重复发生在被复制到多个文件的事实块上。

- **MINOR** 新增 `ohos-common-kb-public/_index.md`：内嵌平台库 27 页的索引入口。
  此前 23 页不在任何索引里，其中 15 页连链接都不可达，只能靠全库搜索命中
- **MINOR** `_index/_map.md` 补齐：补 `knowledge-sedimentation`、两篇复盘
  （`qt-opensource-apps-harmonyos-survey`、`tdesktop-harmonyos-porting`）、
  problems 一节改为指向 `_lookup` 的唯一入口、新增内嵌库入口；`total_pages` 按实际 52 条校正
- **FIX** `skills/kb-iterator/SKILL.md` 的 `_index/_agent-mesh.md` 是根相对写法，
  从该目录解析必定断链 → 改为 `../../_index/_agent-mesh.md`
- **FIX** `problems/_lookup.md` 漏收 `runtime-icons-missing-libqico.md`（合入时索引没跟上）
- **MINOR** 门禁新增两条：C8 相对 `.md` 链接必须存在（此前只查 wikilink）；
  C9 每个知识页至少要进一个索引（否则 Agent 按图索骥看不到）
- **MINOR** 计数收敛：`38 条铁律`/`44 条 QOH`/`56 个实战踩坑` 等数字此前散在
  SKILL、AGENTS、CLAUDE、`_task-routing` 与 README 五处，每次事实变化要手改五次
  （本轮会话为此红过三次 CI）。现在数字只留 README + `RELEASE-MANIFEST.yaml`，
  指导类文档改用不含数字的表述，一致性测试改为反向守卫
- **MINOR** 用例 95 → 99（C8 缺链/行内代码、C9 孤儿页/索引命中）

---

## v3.0.0-rc6 — 2026-11-11

另一台机器上做真实交叉编译移植后反馈的 10 条问题：前 4 条在门禁判据上，
其余在扫描取证与 CLI 交互。逐条核对后 8 条为真（1 条诊断有偏差、2 条已在此前修掉）。

- **FIX** `PARTIAL` 判定名存实亡：旧条件要求 G5 ∈ (PASS, PARTIAL)，而 G5 永远不会
  产出 PARTIAL，于是"编译+链接全过、打包还没做"一律判 FAIL——所有只做到编译阶段的
  迁移都被读成失败。现在 `G3 PASS 且 G4 PASS 且 G5 未失败` → PARTIAL，并在结果后
  补一行解释"阶段性成果、不可交付"；G5 真失败仍判 FAIL
- **FIX** G4 只看 `build.json` 的产物路径字符串，不查磁盘：手写或过期的路径也能过线。
  现在逐个 stat：全在 → PASS，部分缺 → PARTIAL，全缺 → FAIL
- **FIX** G2 的"已处理"没有证据链：`mark-risk --rule R001` 一次就能把 437 条 critical
  清零，无法区分"真隔离了"和"标过去了"。现在 `--evidence` 必填，记录存进
  `state.json`（rule → evidence/note/at）；历史纯 id 列表按"无证据"处理并判 FAIL
- **FIX** 扫描把鸿蒙不编译的代码算成 critical：`ThirdParty/`（如 tdesktop 的
  fcitx5-qt DBus 头）与平台专属目录（platform/win、windows/、macos/）里的命中
  现在自动降一档并标 `scope`，规则可用 `exclude` 排除路径、`scope: keep` 关闭降级
- **FIX** portgraph 平台取证：文件级排除原先只认 `platform/win/**`，漏 `*_win.cpp`
  与 `*.mm`；win32 规则把 `engine::SendMessage{` 这类同名成员当 API 调用。现在按
  文件名后缀识别平台专属文件，函数型符号要求调用括号
- **FIX** 无法登记外部构建结果：自定义 `build_ohos_k.py` 交叉编译成功后，`build`
  只会自己重跑一遍，逼得手写 `build.json` 才能让 G3/G4 反映真实状态（等于绕过工具且
  无证据）。新增 `build --record-only --artifacts <glob>`、`package --record-only --hap`
- **FIX** 子进程输出乱码：`text=True` 按 locale（中文 Windows = cp936）解码 UTF-8
  输出。改为读 bytes 后 UTF-8 优先、locale/gb18030 兜底
- **MINOR** `--project` 写在子命令之后此前被当成未知参数（或静默忽略）；现在两种写法
  等价，写在后面时打印一行说明
- **MINOR** G0 的 `cmake not on PATH` 补上可执行的修法（`config set cmake <绝对路径>`
  或 `build_command`）
- **FIX**（第二轮自查）`--json` 的 stdout 不是纯 JSON：人类可读的门禁表/风险报告/参数
  说明都写 stdout，机器侧 `json.load` 直接失败。人类输出在有 `--json` 时改走 stderr
- **MINOR** 退出码此前只有 0/1，PARTIAL 变成可达后需要独立语义：`0` PASS / `3` PARTIAL /
  `1` FAIL，写进 `verify --help`、TESTING、SKILL
- **FIX**（第二轮自查）状态文件损坏时整条命令崩在 `JSONDecodeError`：中断的运行会留下
  半截 `build.json`/`scan.json`，此前每个子命令都直接抛栈。现在按"没有这条证据"处理
  并告警（门禁只会更保守），`state.json` 损坏则给出重建步骤
- **FIX**（第二轮自查）作用域降级把 `vendor/`、`external/`、`contrib/` 也算作第三方——
  这些目录在别的工程里常被真实编译（AOSP 的 `external/` 就是），自动降级会漏掉会炸的
  真风险。名单收紧到 `ThirdParty/`、`third_party/`、`3rdparty/`；其余目录要排除请用
  `match.exclude` 显式声明
- **MINOR** `files`/`guard` 类命中同样走作用域判定，语义一致
- **MINOR** 用例 75 → 94（三档判定、G4 产物、G2 证据、作用域降级、登记式构建、
  参数位置、损坏状态），portgraph 123 → 127（后缀排除、win32 精度）

---

## v3.0.0-rc5 — 2026-11-04

把 telegramdesktop 真机实测的移交清单（`tdesktop-trunk-handoff-20261104`）逐条落进 trunk：
先修"会把没测读成通过"的工具判据，再补被这件事证伪/证实的知识。

- **FIX** `_scripts/ci.py` 在中文 Windows 上崩：子进程输出按 GBK 解码遇 UTF-8 字节抛
  `UnicodeDecodeError`（栈落在 `subprocess._readerthread`，完全不像编码问题）。现在三处一起改：
  本进程 stdio 强制 UTF-8、子进程环境带 `PYTHONUTF8=1`/`PYTHONIOENCODING=utf-8`、输出解码
  `errors="replace"`
- **FIX** G8 崩溃门禁会假 PASS（最严重的一条）：旧实现只跑全设备 `hilog` 就判 PASS，
  install/launch 失败时等于"没跑起来也算没崩溃"。现在 `crash_check` 先看上游
  install/launch 状态，非 PASS 直接 SKIP 并写明原因；日志按 `bundle_name` 过滤，
  过滤后一行都不属于本应用则判 NOT_RUN（空证据 ≠ 无崩溃）；`smoke` 区分"未测（exit 2）"
  与"崩溃（exit 1）"
- **FIX** 卫生检查只看会被提交的文件：`gitignore` 的本地 `workspace/` 构建树与
  `ENV.local.md` 曾产生 134 条 H2 噪声（真实错误被淹没）。改为按 `git ls-files` 过滤，
  保留 `--include-ignored` 逃生口
- **FIX** `draft` 曾写进 `.gitignore` 的 `drafts/`，按文档流程沉淀的知识进不了 trunk；
  改为写 `faults/_drafts/`（跟踪目录），文档与用例同步
- **FIX** 配置变更不再需要人记得 `--force`：`config set` 自动使 env_check/project_scan/
  qt_scan/risk_scan/dependency_scan 失效
- **FIX** `portgraph deps` 不认 `config set qt_version`：现在优先读 `.qt-ohos/env.json`，
  Qt 6 工程不再被打印成 `Qt: 5`
- **FIX** `analyze-log` 三条过宽模式造成误判：`QOH020` 的 `No such file or directory`
  （nmake 缺失被当成 libuuid 缺失）、`QOH023` 的 `undefined symbol`、`QOH019` 的
  `file not found` 全部收窄为带上下文的模式；`QOH001` 补 `Unknown platform type`
- **MINOR** 新增 `tools/ohos-platform-audit.py`：平台层两种分发（头内 `#ifdef` / 构建按
  路径选 `.cpp`）分类 + 断言头分发文件同时命名 `Q_OS_OHOS` 与 `Q_OS_HARMONY`；
  `--undefined link.log` 反推仍缺实现的平台符号（symcheck）
- **MINOR** 新增 `qt-ohos-run libcheck <lib> --level built|probed`：库级中间门禁，
  `probed` 必须带设备证据；G4 明细里显示"n built / m probed"，移植中间成果不再被整包失败吞掉
- **MINOR** 打包前置检查：`entry/libs/*/` 的版本化 `.so`（加载器按 soname 找不到）、
  非 `.so` 文件、`build-profile.json5` 的 `compatibleSdkVersion` 与 `env.json`
  `compatible_sdk` 不一致，都在打包前拦下
- **MINOR** 机器层：新增 `QOH043`（平台守卫单宏，Qt 6 kit 上死代码）、`QOH044`
  （宿主编译器未带 `--target` 导致 `Q_OS_WIN` 生效，"编译通过"是假证据）与 `R019`
  （`guard` 匹配器：命中 glob 的文件必须同时包含两个 OHOS 宏），规则引擎支持
  `match.guard`；`QOH042 → QOH043/044`、`R018 → R019`
- **MINOR** 知识层扩写：铁律 §六 从 2 条扩到 5 条（双宏守卫、两种分发、`-DQ_OS_OHOS`
  是假修复）并新增「平台模型 else 即 Linux 的 4 处失效点」；`porting-workflow` 增
  「树外消费 app 层前置清单」（5 前提 + 2 陷阱）；`third-party-libs` 增本地签名链路；
  `modules` 增 Qt 6.12+/6.13.0-dev 平台宏实测
- **MINOR** 修正复盘里的两处过度断言：`specific_ohos.h` 的 `inline` 不是"必须去掉"
  （未引用 TU 本就不发射符号，先 `llvm-nm` 判再改）；托盘是成员变量、
  `TrayIconSupported()` 挡不住构造，必须给完整 no-op 面
- **MINOR** 新增 8 个 problems 页（平台双宏、两种分发、树外 app 层前提、CMake `-include`
  去重、同名头自引用、appspawn `/proc/self/exe`、托盘必须存在、本地签名链）；
  知识页 124 → 132，QOH 42 → 44，R 18 → 19，problems 48 → 56，铁律 35 → 38
- **FIX** 对抗审查又抓出三处同类的假 PASS：`G2` 在根本没跑 risk scan 时输出"no critical
  risks detected"并判 PASS（空证据读成通过），改为 NOT_RUN；`G5` 打包命令自称 PASS 但
  找不到 `.hap` 时仍判 PASS，改判 FAIL；`G8` 未配 `bundle_name` 时抓的是全设备缓冲，
  别的进程的崩溃会混进来或盖住自己，这种证据最高只能 PARTIAL
- **FIX** `gen-manifest.py` 只按 `git ls-files --cached` 取文件清单：新写的页面在 `git add`
  之前不进摘要，于是**页数是对的、摘要漏页**——而"可对账"全押在摘要上。改为 `--cached
  --others --exclude-standard`
- **FIX** `ohos-platform-audit.py --strict` 的帮助写"源分发文件必须有 ohos/ 对应实现"，
  实际只检查 `ohos/` 目录存不存在；改为逐个源分发头断言核心名能在 `ohos/` 找到，缺失即退出 1
- **FIX** 打包前置检查拦下时把记录落成了 SKIP（"没测"），与 `build.json` 的 FAIL 对不上；
  新增 `state.fail_cmd()`，语义上"测了不合格"
- **FIX** 版本化 `.so` 旁边已有同名 `libfoo.so` 时仍报错（soname 其实已满足）→ 放行
- **FIX** `migrate` 链路把 smoke 的"未测"和"崩溃"都收敛成退出码 1，与 `smoke` 子命令的
  0/1/2 不一致 → 未测走 2
- **FIX** `faults-build review` 把 promote 之后仍留痕的草稿继续列成"待审"（改到 `faults/_drafts/`
  后这类文件会一直积累）→ 跳过 `status: promoted`
- **FIX**（第二轮审查，跑真机式的合成工程才暴露）`ohos-platform-audit.py` 的分发判定
  要求"至少两个不同 Q_OS_ 宏"才算头分发，于是**只写一个宏的文件——正是它要抓的那类——
  被判成源分发并整体输出 PASS**，这个工具上一轮等于空转。判据改为"出现 Q_OS_ 条件编译
  或 include 了平台分目录实现即头分发"，并新增 `no_ohos_branch`（有链却完全没提 OHOS，
  建议加分支而不是加宏）；补 4 条分类回归
- **FIX** `crash_check` 只按 bundle 全名过滤日志：Qt 应用日志里常只写进程名，
  结果"过滤后一行都不属于本应用"→ 误判 NOT_RUN。改为 bundle + `process_name`
  （缺省取 bundle 末段）双词匹配，仍未命中时按 bundle 各段放宽一轮，再判未测
- **FIX** `analyze-log` 对 `undefined symbol` 类日志零命中且不给方向：现在会指到
  `ohos-platform-audit --undefined`（符号名千变万化，本来就不该塞固定模式）
- **FIX** 迁移链路缺少断链：compile 失败后仍继续调 hvigor → hdc → aa start，得到一串
  连带失败，报告里"没测"和"测了失败"混在一起。现在上游 compile/package 没过时，
  后续设备阶段记为 SKIP（`upstream:compile`）并停止调用，仓库里一条命令就能看出
  哪一步真正卡住
- **FIX** 打包前置检查只认 `"compatibleSdkVersion": "5.0.5(17)"` 这种字符串写法：新工程
  写的是纯 API 号 `"compatibleSdkVersion": 17`，正则匹配不到 → 一致性校验静默不执行。
  两种写法都读，比较时归一（全角括号、`5.0.5(17)` vs `17`）
- **FIX** `scan` 在阶段全部完成时**静默退出**：改了代码再 `scan` 看起来像重扫过，
  其实一个阶段都没跑。现在明确说"本次未重扫（上次时间）"并给 `--force` / `config set`
  两个入口
- **MINOR** `G10` 明细注明 `manual record`，读报告时能分清"机器测过"与"人声明过"；
  规则命中给出行号（此前是 `文件:0`）
- **MINOR** `.qt-ohos/env.json` 的键此前只散落在代码里（`bundle_name`、`compatible_sdk`、
  `hap_glob`、`crash_wait_sec` 等），`skills/qt-app-porting/SKILL.md` 增完整键表
- **MINOR** 用例 48 → 70（guard 匹配、G8 SKIP 传播、打包前置检查、门禁诚实性 8 条、
  摘要覆盖未跟踪文件、平台分发分类 4 条、crash 过滤 3 条、scan 幂等提示、SDK 版本比较 2 条），CLI 冒烟 6 → 7

---

## v3.0.0-rc3 — 2026-11-02

真机测试前的对抗性审查（用 telegramdesktop 这类真实 Qt6 工程当靶子跑通全流程），修掉 6 类会误导判断的问题。

- **FIX** Qt 主版本识别：原先只认 `find_package(Qt6` 字面量，而真实工程的 Qt 配置常写在子模块 `*.cmake` 里（tdesktop 的就在 `cmake/external/qt/package.cmake`）。旧逻辑在"找到模块但无版本"时**直接假定 Qt5**，导致 Qt6 工程被按 5.15 模块矩阵评估、`assess` 给出错的目标版本。现在按证据强度识别（`find_package(Qt6` > `Qt6::` 目标 > `find_package(QT NAMES Qt6)` > `QT_VERSION_MAJOR` > Qt6-only CMake 命令），判不出时**不再猜**：`scan` 显示 `qt: 未判定` 并告警，`assess` 显式标注"按 5.15 假设评估"，可用 `config set qt_version 6` 纠正
- **FIX** `.cmake` 文件纳入检测：此前只扫 `CMakeLists.txt`，子模块里的 `find_package(Qt...)`（Qt 官方向导、desktop-app cmake_helpers 这类）全部漏掉
- **FIX** CLI 参数统一：`init`/`scan`/`migrate`/`assess`/`recipes` 此前只吃位置参数，`--project <目录> init` 直接报错（而 TESTING 里写的正是这种形式）。现在两种写法等价；`recipes` 更隐蔽——`--project X recipes` 的位置参数默认值会把 `--project` 覆盖成 `None`，静默返回"没找到相似案例"
- **FIX** 误建状态目录：`init`/`scan`/`migrate`/`assess` 不给工程目录时改为明确报错退出（码 2），不再默认在当前目录建 `.qt-ohos/`
- **FIX** 相似案例评分归一化：原公式不除以项目特征数，一个 `cmake` 就能顶到 1.00，让明显无关的复盘排第一（tdesktop 曾被"匹配"到 Coin3D 1.00）。现在归一到 0..1 并输出 `match:` 依据行
- **MINOR** 新增 `_scripts/ci.py`：四条门禁的纯 Python 实现，Windows 无 bash 也能一条命令跑完；`_scripts/ci.sh` 改为薄壳。AGENTS/CONTRIBUTING/TESTING/README 中的门禁命令同步为 `python _scripts/ci.py`
- **MINOR** `TESTING.md` 新增 Windows 预检（`core.longpaths`、递归 clone 子模块、空格/中文路径）与 tdesktop 实测基线表（6920 文件 / 3298 源 / 12.3 秒扫描 / UNCERTAIN 结论 / 主要工作量在 ffmpeg 等三方交叉编译与 161 处 win32 专用代码）
- **MINOR** 分支内容复核补漏（追问"其他分支的知识是否都进了 trunk"后重审）：`sync/sync-2026-09-11`
  比 `main` 新 66 个提交，此前按 `-s ours` 只登记了祖先关系、没逐文件比对内容，漏了 2 个文件——
  补入 `episodic/postmortems/tdesktop-harmonyos-porting.md`（tdesktop v7.0.2 全量鸿蒙化复盘：
  59 bottle + 9 个源码编译、2088 目标适配、550MB HAP、IME reset 修复）与
  `problems/runtime-icons-missing-libqico.md`（.ico 图标不显示：缺 `imageformats/libqico.so`；
  取回时该页 frontmatter 缺闭合 `---`，已修）；知识页 122 → 124
- **MINOR** 补回三处被重写丢掉的文档小节：`SKILL.md`「使用前提」（此前 `§使用前提` 是悬空锚点）、
  `CONTRIBUTING.md`「反馈流程」（Issue 模板对照表 + `SECURITY.md` 入口）、`README.md`「常见问题」
  （成功判据 / 可移植性怎么判断 / 要不要商业 license / WebEngine 用 CEF 平替）与「本地要装什么」
- **MINOR** `LINEAGE.md` 写入复核结论：`sync/*` 的两个旧页已被内嵌公共库合并、`main` 的 139 个模板
  构建产物、`release/v2.1.0` 的 `skills/skills/` 旧布局副本，逐条写明不并入的原因与能力落点
- **MINOR** 文档纠偏：`_templates/draft.md` 草稿入口改为 trunk 的 `faults/_drafts/` + 三类入口说明；`team/CONTRIBUTORS.md` 不再指向已不存在的 `_scripts/kb-init.py`；用例计数 41→48（引擎 12→19）

---

## v3.0.0 — 2026-10-31

首个 `trunk` 主干版本：由 `main`（v2.2.1 内容基线）+ `bitfun-release`（执行层 / 机器层 / 故障图 / 模板）
合并而成，并补齐仓库契约、门禁与分支模型。**旧分支 `main`、`bitfun-release` 冻结不动。**

- **BREAKING** 仓库定位变更：从"Qt 迁移参考知识库"改为"Qt → HarmonyOS 迁移工程仓"（知识层 + 机器层 + 执行层 + 治理层）。README / SKILL.md / AGENTS.md 全部重写，README 按架构-能力-上手-skills-CLI-目录-分支-质量-规格-限制-理念-发版组织；根 `SKILL.md` 改为标准 Agent Skill 形态（frontmatter `name/description/metadata` + `## Instructions` 12 步）
- **BREAKING** 分支模型改为三段式：`trunk`（主干/稳定，只收开发分支合并）/ `dev/<主题>`（开发，接受 PR）/ `release/vX.Y.Z`（归档）；`CONTRIBUTING.md` 重写，明确"本仓已从只读派生视图转为主干开发仓，上游重建管道必须停用以避免覆盖合入"
- **NEW** 仓库契约与自检门禁：`kb.yaml`（schema v1：入口/地图/自检命令/分层必需路径/可选路径）+ `_scripts/verify.sh` + `_scripts/verify.py`（零依赖，9 类检查：契约完整性、必需路径、AGENTS==CLAUDE、内容页 frontmatter 必填字段、id 唯一、audience 仅 public、wikilink 可解析、仪表盘计数、产物目录与本机绝对路径卫生）
- **FIX** 合并后由门禁检出并修复的 5 类结构缺陷：① 3 页 frontmatter 被格式化器破坏为 `***` 围栏 + 转义方括号（经归一化比对确认 bitfun 对该 3 页实质改动为 0 且引入 `<URL）→>` 断链，回退为 main 版本）；② `semantic/qt-harmonyos-blocking-taxonomy.md` 缺 `audience`；③ `problems/runtime-harmonydeployqt-deploy-gaps.md` 缺 `id/type/domain/status/severity/audience`；④ 3 处真实个人路径 `/Users/<name>/` → `<YOUR_HOME>`（verify 对 `you`/`currentUser` 等占位符豁免）；⑤ `skills/qt-community-to-official/SKILL.md` frontmatter `name` 与目录名不一致（`-cn` 后缀）
- **FIX** 恢复两处被静默删除的内容：`CLAUDE.md`（改由 verify 强制与 AGENTS.md 逐字一致，避免 Claude Code 用户手工复制）与 `episodic/postmortems/qt-opensource-apps-harmonyos-survey.md`（229 应用调研，唯一生态数据，已由 `<INTERNAL_OUTPUT>` 占位脱敏）
- **PATCH** 一致性测试修复：`_candidates` 增加仓库根相对候选（`kb.yaml`、`ENV.md` 这类根文件此前无法解析）；`_dashboard` 计数与恢复后的页面集对齐（episodic 6→7、合计 46→47）
- **MINOR** 以下为 bitfun-release 侧本轮并入的执行层/机器层/跟踪层能力（原 v2.3.0 未发布内容）

- **MINOR** 新增执行层（Execution Plane）：`tools/qt-ohos-run.py` 统一 CLI + `tools/qt_ohos/` 引擎（纯标准库实现），把迁移知识变成可执行、可恢复、可验证、可沉淀的工程闭环
  - `scan`：项目识别 + Qt 能力扫描 + 三方依赖扫描 + `knowledge/rules/` 18 条机器规则风险报告
  - `analyze-log`：`knowledge/errors/` 41 条 QOH 错误模式自动诊断（与 `problems/` 一一对应；36 条原有 + 5 条 Linux 源码编译沉淀，见下）
  - 状态机 + checkpoint/resume：目标项目 `.qt-ohos/`（state/scan/plan/changes/logs/patches）
  - Verification Gate G0-G12（`verify`）：成功由工具判定，TIMEOUT 永远不是 PASS
  - Source tracking：白名单自动修复（B9 `:!ohos` 作用域、B10 AUTORCC）+ patch 固化/可回滚
  - 知识蒸馏：`draft` / `promote`；`recipes` 检索 episodic 相似迁移案例
  - 任务预算：`QT_OHOS_TASK_BUDGET_SEC` / `QT_OHOS_TASK_DEADLINE`
- **MINOR** 新增 `skills/qt-app-porting/` skill + 任务路由码 [P]；`templates/qt-ohos-app/` CMake 胶水模板（内嵌铁律 B1/B2/B10）
- **MINOR** 新增 `tests/`（引擎自测：YAML 解析、规则匹配、错误匹配、状态机、CLI 冒烟）
- **MINOR** 新增故障库 `faults/`（四实体图模型：症状 S × 根因 C × 临时方案 W × 跟踪单 T）——真源 `faults/_data/*.yaml`（S/W/T 记录+causes/targets/tracks 边）+ `C-*.md` 根因页（frontmatter+depends_on 边）；`tools/faults-build.py` 实现自动演进（`build` 重建派生物 `_graph.yaml` 机读全量图 + `_registry.md` 登记总表；`check` 一致性门禁：ID/枚举/边/日期/refs/limitation 证据；`review` 复核到期扫描+状态推进 lint）；根因定性 defect 会修 vs limitation 规格限制→替代方案，W 含验证与退役条件，T 承载 QTBUG/华为单号与 fix_version 修复版本号；种子 8 根因（5 defect + 2 limitation + 1 undetermined）+ 7 症状 + 6 方案 + 4 跟踪单（迁移自 problems/episodic/semantic 既有知识）；任务路由新增 [R] 故障跟踪
- **MINOR** 故障库新增协作提交与合入流程：`faults/_drafts/`（`_template.md` 协作者提交清单——现象原文/环境三件套/复现 demo·defect 类必附·limitation 类用官方文档链接替代/查重声明）+ 主编合入门禁六步（查重→**复现 demo 必测**·未复现不合入→人工核验·证据链/定性/归层/事实/脱敏→复现留痕登记 C 页验证记录→promote 拆分合入→build 门禁）；草稿状态机 draft/in-review/returned/rejected；`review` 子命令列出待审草稿
- **MINOR** 故障库新增问题确认证据标准与复现 demo 编写原则：C 页必填 `evidence_type`（demo 复现工程 / logs 调试日志+栈 / both / source 源码 file:line·仅静态可判定类 / docs·limitation 专用），`check` 机器强制——defect 禁仅凭 docs 定性、Qt 框架侧 defect 仅 source 收 WARN（提上游前补动态证据）、**在跟上游单（qt-bug/ohos-issue/partner）的 defect/undetermined 必须 demo/logs/both**（对齐 `qt-bug-report-generation` 可复现性 HARD 闸门）；复现 demo 编写七原则（最小化/自包含可构建/确定性/对照性/纯净根因/携带诊断输出/版本留痕）与无 demo 降级通道（日志+栈+采集环境三件套）；**Qt 框架侧问题 demo 硬性要求：复现逻辑集中在单个 main.cpp（ohos 工程仅胶水壳）+ 复现步骤编号到操作级（无步骤视为未完成）**
- **MINOR** 故障库新增**处置分类**派生视图（`faults-build.py` 从 nature×responsible 自动计算，不入真源）：鸿蒙必须适配（limitation）/ Qt 问题（defect+qt 侧）/ 系统问题（defect+ohos 侧）/ 应用使用问题（responsible=app，配套放宽为允许薄 C 页）/ 三方库问题 / 待定性；登记表新增 §按处置分类，`_graph.yaml` 增 disposition 字段
- **MINOR** 故障库**历史问题导入批次 1**（10 个问题，3 个并行子 agent 分析 + 主编审核合入）：QDialog blockedByModal（C-0009+patch）、@ohos.deviceInfo 裸 eval 模板崩溃（C-0010）、mainthread Q_ASSERT（C-0011，undetermined）、dlopen 可写路径（C-0012+QTBUG-146624）、沙箱只读写崩溃（C-0013）、跨屏闪烁（C-0014）、hvigor CLI/IDE 打包分歧（C-0015，undetermined）、QFileDialog 误加守卫（C-0016，应用使用问题首例）、curl 中文乱码（C-0017）、ZINK RGBA8 mipmap 黑纹理（C-0018，三方库首例）；图规模 S 7→17 / C 8→18 / W 6→15 / T 4→5，14 处源页 refs 回填
- **MINOR** 故障库新增**链路完备性（闭环规则）**：defect（外部责任）的"临时解决"必须同时具备采用中方案（W adopted）与在跟单（T）——缺一即未闭环（missing-ticket/missing-workaround/both-missing，`faults-build.py` 派生 `chain_state`/`gaps`）；limitation 与应用问题必须有采用中方案；**缺口向上传播**（S 的了结宣称受 causes 聚合约束：S=resolved 而链有缺 → ERROR，S=mitigated 无 adopted W → ERROR，C=workaround 未闭环 → WARN）；`_registry.md` 新增 §未闭环清单（缺单/缺方案/双缺分组）+ 症状索引闭环列 + 统计"链路闭环"行，`_graph.yaml` S/C 节点增 chain_state/gaps，`review` 增"未闭环（待补齐）"段；数据修正 W-0004 targets 扩至 C-0005+C-0006（换构建组合同时绕开两根因）
- **MINOR** qt-sdk-forge **Linux 全链路支持 + 实测验证**（Ubuntu 22.04 x86_64：Qt 5.12.12 GLES release + OpenHarmony SDK 6.1.0.35 → SV0-SV6/SV8 PASS，2026-09-19）。沉淀自一次完整 Linux 编译实战，五坑全部转为机器级预防（错误发生前拦截）：
  - **QOH037 源码快照缺陷**：GitCode 开源镜像初始导入丢全部执行位（620 个 shebang 脚本）、`main`/`5.12.12` 快照带 CRLF、且无 `tqtc/*` 商业分支名——`src-clone --method opensource` 现默认检出 POSIX 构建分支 `build/macos-arm64-qt5.12.12`（新增 `OPENSOURCE_BRANCHES` 映射 + `--branch` 覆盖），克隆后自动恢复执行位并以 git 提交固化，CRLF 树直接拒绝
  - **QOH038 python 别名缺失**：qtdeclarative 调 `python` 而 Linux 只有 `python3`——`build_env()` 自动创建 `.qtsdk/pyshim/python`（不污染宿主）；SV0 新增 `python3`/`python_alias` 检查
  - **QOH039 QtDBus 编不过**：clang 15 的 `-Wdeprecated-copy` × mkspec `-Werror`；且鸿蒙运行时无 DBus（QOH002）——CLI configure 内置 `-no-dbus`（对齐官方预构建与 semantic 页）
  - **QOH040 脏构建目录（增量第四坑）**：改配置/换 SDK 后旧 `qt_lib_dbus.pri` 残留使 `qtHaveModule(dbus)` 误真、ibus 插件照常构建——configure 新增指纹防护（configure 参数 + OHOS SDK 版本指纹），变化即自动清构建目录
  - **QOH041 SDK API 过旧**：qarkui QPA 编译期取 ArkUI NDK 符号地址，需 apiVersion ≥ 23（OpenHarmony ≥ 6.1；官方构建 API 24）——`build-matrix.md` 新增 §2.1「Linux 获取 OHOS SDK」：OpenHarmony 公开镜像 URL 规律、版本选择表、解压登记步骤、低内存 jobs 建议
  - 配套：`problems/` 新增 5 页（事实源）、`knowledge/errors/` 36→41 条、`_lookup.md` 重建、kb-init `qt-src-acquisition.md` 修正开源分支说明（同 QOH037 根因）
- **PATCH** qt-sdk-forge CLI 修复：`env` 子命令现尊重 `config set qt_src/ohos_sdk_native`（原先只读 ENV.local.md，配置 apparent 失效）；`building.py` configure 失败路径 `key` 未赋值崩溃；`run_git()` 调用签名错误 7 处（releasing/srctree/patching，`release`/`upstream-check` 必崩）；`-no-dbus` 加入内置 configure 参数
- **MINOR** 新增多 Agent 协作协议 `_index/_agent-mesh.md`（单一真源）：知识库拆分为 7 核心 + 2 可选 agent 的接口卡（触发/CLI/门禁/状态平面/入站出站交付件，port-assessor / framework-analyst / test-verifier 以接口卡为定义）；新增 **Task Ledger 平面**（`workspace/tasks/`，gitignored）——`task.yaml` 任务台账 + `flow.jsonl` 流转日志（七类固定写点：task-created / handoff-in·out / gate / anomaly / budget-exhausted / human-required / draft-produced / task-closed，追加不可改写、每条带 refs）+ `ho-*.yaml` 移交信封（泛化 qt-sdk-forge inbox 协议，8 种 type）；三条任务链（移植 / 问题 / 演进）；**人工接入点三级分类**（H1 阻断决策 / H2 人工执行 / H3 复核确认）逐 agent 明确 + 5 条通用红线（凭据·账号·付费·对外提交一律人工、发布·删除·ENV 切换须确认、门禁语义不得升格、无证据不定性、human-required 必留痕）；并发契约沿用 `.qtsdk/` 文件锁 + 原子替换。配套新增 `skills/task-dispatcher/`（调度中枢：建档→路由→监控→关单移交）与 `skills/kb-iterator/`（工程迭代主编：合入门禁 / 索引再生 / kb-verify 事实校验 / flow.jsonl 复盘蒸馏 / 演进复核——唯一真源写入门）；qt-app-porting 与 qt-sdk-forge SKILL.md 补"接口与人工接入"节；AGENTS 技能表注册、_task-routing 挂接
- **PATCH** 发布分支裁剪（bitfun-release）：`CLAUDE.md` 移出版本管理（`AGENTS.md` 同内容保留为入库真源，本地可复制生成，README/AGENTS 多工具表同步修正）；`HANDOVER.md` 交接文档与内部工作草稿不入库（.gitignore 防回滑）；`_agent-mesh.md` §八内部调度平台 ID 脱敏（协议与编排语义保留）
- **MINOR** 新增根级 `SKILL.md`：知识库 skill 化总入口——frontmatter 触发词覆盖"鸿蒙化/移植 Qt/三方依赖分析/构建报错"等场景（鸿蒙化 Qt 应用时自动加载），正文固化主工作流（Step 0 portgraph 可行性评估与依赖闭包 → qt-ohos-run 流水线 → G0-G12 门禁）、三方依赖分析与下载（deps 角色分类 + fetch/fetch-deps bottle 一键获取）、知识检索入口与纪律红线
- **PATCH** README 全面重写并与知识库实际对齐（多路一致性校验）：任务路由 13→15 类（补 [S] SDK 工程）、QOH 错误模式 36→41、API 映射 12→13 类、目录树补 knowledge/tools/portgraph/templates/tests/.gitcode 与 5 个 skills、Skills 表补全（SKILL.md 总入口 + qt-sdk-forge/task-dispatcher/kb-iterator + portgraph 仓库工具）、移除对外失效的 `_scripts/kb-dev-edition.sh` 引用；结构按开源最佳实践重构（徽章行 + 核心能力表 + 30 秒上手 + AI 接入矩阵 + CLI 折叠子命令清单 + FAQ + 已知限制 + 版本 v2.3.0）
- **MINOR** 新增知识库一致性自测 `tests/test_kb_consistency.py`（20 用例，纯标准库，`python -m unittest discover -s tests -v` 与引擎测试同跑）：**L1** Skill 清单规范（根级+5 子级 SKILL.md frontmatter name/description、AGENTS 技能表登记完整性）；**L2** 文档计数一致性——文档声称 == 实际值（QOH 41 / R 规则 18 / 铁律 35 / 任务路由 15 / API 映射 13 / problems 46 / faults 图 17-18-15-5 / 测试用例数），数字漂移在提交前被拦截（keep numbers real）；**L3** 交叉引用完整性（QOH refs → problems 页、README/SKILL/AGENTS/_task-routing 行内路径解析——支持 `qt-`/`qt-harmonyos-`/`qt-ohos-` 简写前缀约定、README 相对链接与锚点）；**L4** CLI 契约（qt-ohos-run 24 / qt-sdk-run 24 / portgraph 10 子命令集合，增删命令须显式更新测试）；**L5** faults-build check 集成门禁（exit 0 = ERROR 清零）
- **PATCH** 一致性测试落地即修复一批同源过时项与规范缺陷：AGENTS.md（36→41 QOH、`_scripts/kb-dev-edition.sh` 失效引用移除、H1 标题 CLAUDE.md→AGENTS.md）；_task-routing.md（[H] ~36→145+ API、"33 条铁律"→35、B1-B11→B1-B12、W1-W5→W1-W6、"36 条错误模式"→41、决策树补 [P] 自动迁移条目）；portgraph/README.md（接口白名单 19→22、单测 35→119）；_dashboard.md（semantic 24→26 补 blocking-taxonomy/dev-guide 两页、problems 41→46、合计活跃 47→48）；skills/qt-app-porting/SKILL.md frontmatter 规范化（`***`/长横线围栏→`---`，描述体补缩进）、kb-iterator 与 task-dispatcher 的长横线闭合围栏→`---`；portgraph 测试删除 1 个同类遮蔽的死用例（test_build_tools_count_matches_display，120 定义→119 实跑）；README [N] 路由 deveco-mcp-capabilities 补全 ohos-common-kb-public/ 前缀、单测数 120→119
- **PATCH** 知识库应用名脱敏（内容策略：知识库不携带特定应用名的鸿蒙化信息，防止 agent 锚定具体案例走捷径）：删除 episodic 应用复盘 2 页（某 IM 客户端全量移植复盘、229 应用普查页），通用经验蒸馏保留——"同文件多处修改必须串行"入 qt-app-harmonyos-migration 陷阱节、bottle 缺口镜像源/静态转共享技巧入 third-party-libs §3.4、三大阻断模块统计（D-Bus/QtMultimedia/QtWebEngine）入 modules 快速查找；路由/协议/procedural 层实证引用改"某大型应用"式表述并移除内部协作过程细节；problems/semantic 证据性提及泛化（批次编译清单、参考实现等）；portgraph 文档示例换 sample-app 虚构样例（e2e corpus.json 测试基础设施真实 URL 豁免；SARibbon/Coin3D 等三方库名按 [M] 路向知识保留）；faults 真源 W-0008 标题同步脱敏并重建派生物（build OK / check 0 ERROR）。计数联动：episodic 8→6、合计活跃 48→46。注：远端历史提交仍含应用名，未改写公开历史
- **FIX** devecocli 工具可用性预检（干净环境测试实证：agent 无法一次定位 devecocli）。根因：三处文档三个说法且全不符事实——kb-init 称"DevEco Studio 自带于 `<DEVECO>/tools/devecocli`"（实测不存在）、usage-rules 让装 `@deveco-test/deveco-cli`（测试通道）、deveco-install 让装 `deveco-cli`（裸包名在 npm 上不存在）；实际来源为 npm 包 `@deveco/deveco-cli`（二进制 `devecocli`，PATH 可用）。修复：① deveco-cli-usage-rules 新增"工具可用性预检（开工前必做）"——四级定位顺序（ENV.local.md `DEVECO_CLI` → PATH → npm 全局 → DevEco 捆绑）+ `--version` 验证 + 失败即停报告纪律；② detect-env.sh 定位优先级改为 PATH → npm 全局 → 捆绑兜底，新增 `DEVECO_CLI_VERSION` 输出，OSS 检测改为 npm 包探测；③ generate-env-local.sh 新增 `--deveco-cli` 参数写入 `DEVECO_CLI` 变量；④ install-deveco-cli.sh / install-deps-harmonyos.sh 包名与二进制名全部修正（`npm i -g @deveco/deveco-cli`）；⑤ kb-init SKILL 检查段与故障排查表重写（双 shell 命令）；⑥ env-variables/deveco-install 补 `DEVECO_CLI` 变量与"常见误认"表；⑦ 根 SKILL.md 纪律红线与 AGENTS.md 执行纪律新增"工具可用性预检"条目。顺带：usage-rules 中 NeoHtop/open-pencil 应用名泛化（脱敏策略补漏）
- **NEW** `tools/cpp20-gap-scan.py`——OHOS clang15/libc++15 的 C++20 缺口**编译前预检与机械修复**（干净环境实测驱动：大工程全量编译一轮数十分钟，"撞错→定位→修复"逐轮迭代代价高，预检一次出全部命中点）。8 条规则对齐 problems/build-clang15-libcpp15-cpp20-gaps.md：GAP-01 结构化绑定 lambda 捕获（P1091）/ GAP-02 make_unique_for_overwrite（唯一自动修复项，幂等）/ GAP-03 stop_token·jthread / GAP-04 atomic_ref / GAP-05 std::ranges / GAP-06 defaulted `<=>` 含 shared_ptr / GAP-07 纯 init-capture lambda / GAP-08 pthread_setaffinity_np；P0634·P0960·construct_at·variant best_match 编译期才能发现，文档注明不在扫描范围。scan 模式 CI 友好（有缺口 exit 1，支持 --json），fix 默认 dry-run。接入：迁移工作流阶段零预检第 8 项 + SKILL.md Step 1 构建前步骤 + problems 页"预检工具"节；problems 页"其他同类坑"补实战新缺口 2 条（make_unique_for_overwrite、init-capture+this）。单测 9 例（tests/test_cpp20_gap_scan.py）
- **NEW** QOH042（harmonydeployqt 设备侧部署缺口，5 类系统性问题）——来源：干净环境全流程鸿蒙化测试的 agent 自沉淀草稿（人工核验后合入，应用痕迹已泛化）：①QPA 插件非 Qt 依赖（fontconfig 链）不部署（copyPlatformPlugin 只认 libQt6* 前缀）；②无 SONAME 的 bottle .so 产生绝对路径 DT_NEEDED，readElfDependencies 遇盘符 `:` 截断整个依赖清单；③libz.so.1 按 Android 惯例被跳过但不在鸿蒙应用 linker namespace；④设备系统库在 chipset-sdk-sp/ndk/platformsdk 非标路径；⑤bottle 缺无版本化文件名。附 readelf 闭包检查方法与 5 条部署前检查清单 + hvigor 环境三件套（DEVECO_SDK_HOME/JAVA_HOME/反斜杠 PATH）。新增 problems/runtime-harmonydeployqt-deploy-gaps.md（与 runtime-hap-missing-so-closure 互为部署侧/运行时侧姊妹篇）+ knowledge/errors/QOH042.yaml + _lookup 索引行；计数联动 41→42（index.yaml/README/SKILL/AGENTS/_task-routing/build-matrix）。本轮实测该部署缺口类问题耗 时约占全程 1/4（单步最长 3h），入 QOH 后 analyze-log 可机器直达
- **FIX（测试驱动）** 回合收尾纪律（SKILL.md 纪律红线 #7 + AGENTS.md 执行纪律）——干净环境全流程测试第二轮实测死因：非交互 CLI 会话中主 agent 输出"进行中"总结后结束回合（回合结束=会话退出），3 个脱管子进程完成各自 stub 后就地解散，无人接管构建阶段，流水线断链。新纪律：未达 verify 终态或人工确认点禁止收尾，后台任务必须 wait 至完成；确需中止时状态落盘 .qt-ohos/ 并写明续跑方式
- **NEW（测试驱动）** libc++15 实验性开关 `-D_LIBCPP_ENABLE_EXPERIMENTAL`（problems/build-clang15-libcpp15-cpp20-gaps.md §9 + cpp20-gap-scan GAP-05 建议前置）——实测默认缺 16 项 ranges 算法、加开关后全部可用且 <format> 同步解锁，可省逐算法改写；jthread/expected/source_location/clock_cast 仍缺按原章节处理
- **NEW（测试驱动）** 大仓库获取韧性（SKILL.md Step 0）——弱网下 clone 大 pack 被掐断（curl 56 early EOF）重试仍失败时，改 codeload tarball 断点续传（github.com/<owner>/<repo>/tar.gz/refs/heads/<branch>），解压入 portgraph workspace 后 scan 照常
- **FIX（测试驱动）** 回合收尾纪律升级为操作级（SKILL.md 红线 #7 + AGENTS.md）——第三轮测试 42 分钟即死于同一模式（拉到纪律版 KB 仍"委派 3 个后台代理后收尾"），纯"禁止收尾"表述不足以纠正模型行为；升级为操作级禁令：**禁止"委派后台代理后收尾等待"**（该模式在此环境=任务中断），长任务必须回合内同步等待或顺序自己执行，确要并行只能会话内阻塞式等待；并强调"没有任何机制会唤醒你"
- **PERF（测试驱动）** portgraph `fetch-deps` 并行下载——第四轮测试实测死因：弱网下串行下载 57KB/s 拖垮全流程（单步 90 分钟超时 + 最终 manifest 30 分钟，agent 被迫自研 4 批并行下载脚本 471 秒拿下 33 包）。修复：`fetch_bottle` 拆出 `prefetch_bottles`（ThreadPoolExecutor 并行预取 tar 到 .cache，默认 8 线程，缓存命中/已安装自动跳过，单包失败不阻断）；`_download` 加缓存命中跳过（sha 匹配不重下，天然支持重跑只补缺）；解压保持串行（规避 Windows 杀软文件锁竞态）。CLI 新增 `--jobs`（默认 8，0/1 关闭）。单测 4 例（tests/test_prefetch.py：并行+缓存命中 mtime 验证 / 已安装跳过 / 坏 sha 失败清理 / 无 sha 信任已有文件）
- **PATCH** devecocli 预检修复的实现文件落地（补齐上上条 FIX ①-⑥ 的脚本与文档）+ 新增 `.gitattributes` 强制 `*.sh text eol=lf`——Windows 检出把 shell 脚本变 CRLF 后 `bash detect-env.sh` 直接语法报错，是预检脚本"改了却跑不起来"的根因，入库统一 LF 一劳永逸
- **PATCH** `tools/qt_sdk/releasing.py` `parse_version` 接受同日二次出包后缀 `.N`（如 `5.15+p1.20261009.2`）——同一天切第二个版本是 `release()` 自身支持的合法操作，却过不了自己的 SV6 版本门禁
- **NEW（trunk 治理）** 发版清单可机算可对账：新增 `_scripts/gen-manifest.py`（重算 `content_tree_sha256` = sha256 over sorted `<relpath>\0<sha256>`、Qt/平台页面数、用例数、`built_at` 并原地写回；`--check` 比对、`--check --strict` 用于 tag 前、`--release` 置 released 并回填 `root_commit`），`verify.py` 增 M1 检查（第 10 类）：version/status 枚举、页面数、skills 清单、用例数必须等于实际，且只有站在 `root_commit` 上时才强制摘要一致。此前清单里的 162 用例、5 warning 均为手填过期值
- **NEW（trunk 治理）** `_scripts/ci.sh`：一条命令跑完四条门禁（verify / faults check / 全量用例 / 5 个 CLI `--help` 冒烟），退出码即结论，供流水线或 pre-push 直接调用
- **FIX** `qt-ohos-run.py scan` 的工程路径改为可选位置参数并让出 `--project` 的 dest——此前 `--project <dir> scan` 直接 argparse 报错（文档里写的正是这种写法），`scan <dir>` 与 `--project <dir> scan` 现已等价
- **FIX** `plan`/`patch` 在非工程目录下的提示改为直接给出 `--project <工程>` 用法（原提示只说"run init first"，与用户刚做完 `scan ~/app` 的事实冲突）；`analyze-log` 不再要求工程状态（纯日志分析却先打一行 init 提示）
- **FIX（测试驱动）** 用例数从 grep 计数改为 AST 实计并纳入文档守护：`test_testcase_counts` 原用 `grep -c 'def test_'`，把自身正则字符串里的两处字面量算成用例（声称 22 实际 20），portgraph 又漏数 `test_prefetch.py` 的 4 个（119 实际 123）；现按 `Test*` 类下的 `test_` 方法统计，并核对 README 与 TESTING 的每一处声称（12 + 20 + 9 = 41，另图谱 123）
- **FIX（卫生）** 清理 `skills/qt-community-to-official/templates/` 下 178 个误入库的构建产物（`.cxx` 62 / `oh_modules` 79 / `.idea`+`.deveco` 14 / `.hvigor` 9 / `.DS_Store` 14），并补 `.gitignore` 6 条规则防复发；`verify` 的 5 条 H1 警告归零，模板目录 2.9 MB → 500 KB
- **NEW（故障库闭环松绑）** 缺跟踪单的 defect 若已挂排期占位单（`T.status=draft` + `planned_filing`），`faults-build check` 报 INFO 而非 WARN：缺口仍按未闭环计（`chain_state` 不变、仍列在 `_registry.md` 未闭环清单并标注 `T-xxxx（计划）`），只是把"没人管"和"已排期盼提"分开。本版为 C-0001/0002/0005/0009/0010/0018 建 T-0008…T-0013（计划 2026-11-30），tracker 枚举补 `upstream`（第三方上游，如 Mesa）
- **MERGE（分支收敛）** 三条此前未完全并入 `trunk` 的分支已收敛，逐条记录在新增的 `LINEAGE.md`（含复核命令与"有意不并入"清单）：`matrix-release` 的 README/SKILL 重写成为 `trunk` 文档基底（原 `trunk` 仍是 116 行精简版 SKILL 与带"不再是"表述的 README——那是已被否掉的写法）；`lzh-add-qt-cef-graft-test` 的 `tools/kb-cef-graft.py` + 配置样例并入，并改正 CEF 指南里"嫁接脚本不在本知识库"的旧说法（脚本就在 `tools/`）；`trunk-flip-v3` 补入 `team/`（CONTRIBUTORS、TEAM_ONBOARDING）、`_templates/`（draft/knowledge-page/problem）、`procedural/knowledge-sedimentation.md`（改写到本仓机制：草稿入 `faults/_drafts/`、派生物 `faults-build build`、收工 `ci.sh`）、`_scripts/pre-push`（泄露门禁钩子）
- **NOT-MERGED（有意不并入）** `kb-gate.sh`（旧 schema，与 `audience: public` 必填相反）、`kb-release.sh`/`RELEASE-STATE`（已被 `gen-manifest.py` 取代）、`kb-regen-indexes.sh`（旧索引布局）、`kb-sediment.sh`/`kb-promote-drafts.sh`/`drafts/`（与 `faults/_drafts/` 两套草稿约定）、`kb-bot.py`（外部 bot 环境）、`kb-init.py`（已被 `skills/kb-init` 承担）、`kb-sync-common.sh`（无同步源）、根目录 `TEST-REPORT.md`（一次性记录）。原件仍在冻结分支上，理由与现对应物见 `LINEAGE.md` §二；`kb-regen-indexes.sh` 与 `kb-sync-common.sh` 标注为本仓已知空白
- note: `RELEASE-MANIFEST.yaml` 的 `content_tree_sha256` 现由 `_scripts/gen-manifest.py` 生成；发版流程见 `CONTRIBUTING.md` §发版流程

## v2.2.1 — 2026-08-29

- fix(procedural+semantic): 修复 skills 自嵌套与 manifest 幽灵 skill

- copy_skills 在持久化/复用 OUT（如 dist/dev-edition 二次构建）下 cp -r src dst 会把 src 拷进已存在的 dst → 产出 skills/skills/ 双层嵌套；改 rm -rf + /. 拷内容防嵌套。
- gen-release-manifest skills 枚举盲目收所有子目录，把自嵌套的 skills/ 登记成幽灵 skill（manifest 出现 skills: ["kb-init","skills"]）；加 SKILL.md 校验 + 跳过自嵌套目录兜底。
- PR#9 曾手动清理外部仓 skills/skills/ 产物，本次在源端两层加固固化，避免复发。

## v2.2.0 — 2026-08-27

- Qt5+CEF 鸿蒙开发指导 + issue 模板（.gitcode/ISSUE_TEMPLATE/）+ xsy-letos/xsy-pyqt 迁移经验 + 版本化发版机制（kb-publish.py 固定脚本从 main 发版）

## v2.1.0 — 2026-08-25

- Qt6.12 beta3 模块状态更新（QtHarmonyExtras 重新独立成模块 + 文件权限接口修正）；新增若干 Qt 应用 OHOS 迁移编译经验；修正公开页硬编码 Qt 路径脱敏；新增版本化发版机制（README 能力规格节 + RELEASE-MANIFEST + CHANGELOG）

## v2.0.0 — 2026-08-19

- **MINOR** 内嵌 `ohos-common-kb` 公开子集（ArkTS/ArkUI/NAPI/Stage 模型/DevEco 工具链基础）到 `ohos-common-kb-public/`
- **MINOR** 新增 `skills/kb-init/` 初始化 skill：环境探测 → 引导安装缺失依赖 → 生成 `ENV.local.md` → 校验环境
- **MINOR** 多渠道 Qt 源码获取（商业 license `codereview.qt-project.org` / 开源镜像 `ohos-qt/qt-harmonyos-src` / 预编译 SDK releases）
- **MINOR** 新增根文档 `SETUP.md` / `CONTRIBUTING.md` / `SECURITY.md`
- **MINOR** `RELEASE-MANIFEST.yaml` 记录多源 SHA + `content_tree_sha256` + 页数计数（builder v2, schema v1）

> v2.0.0 之前的旧 5-skill 仓库历史见 `legacy/pre-rewrite-*` tag（已快照至内部 `raw/imports/ohos_qt-skills-legacy/` 供未来继承）。未回填 v1.0.0。
