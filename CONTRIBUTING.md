# 贡献指南

## 本仓库是什么

本仓库**已从"只读派生视图"转为"主干开发仓"**：`trunk` 分支是唯一主干，知识、机器规则、
工具链都在这里演进，外部贡献通过开发分支合入。

> ⚠️ **迁移注意**：历史上本仓由上游内部知识库按 `audience:public` 过滤后整体重建。
> 自 `trunk`（v3.0.0）起，本仓取代该管道成为事实来源。**若上游重建管道仍在运行，
> 必须先停用**，否则本仓的合入会被下一次重建覆盖。

---

## 分支模型

| 分支 | 角色 | 谁可以动 | 规则 |
|------|------|---------|------|
| `trunk` | 主干 · 稳定版本 | 维护者 | 只接受开发分支的合并；合并前 `verify.sh` + 全量用例必须通过；发版打 `vX.Y.Z` tag |
| `dev/<主题>` | 开发 · 接受 PR | 任何贡献者 | 从 `trunk` 拉出；允许不稳定；合并回 `trunk` 前必须过门禁 |
| `release/vX.Y.Z` | 归档 | 维护者 | 从发版点拉出，只修致命缺陷（cherry-pick），不进新功能 |
| `main` 等其他历史分支 | 冻结 | 无人 | **不再接受提交**，仅作历史参考 |

```
trunk ──●────────●────────●────────●──→  稳定、可发版
         \      / \      / \      /
  dev/*   ●────●   ●────●   ●────●        开发、可合入
                   \
  release/vX.Y.Z     ●────●               归档、只修致命
```

---

## 发版流程（维护者）

发版是**可复算的机械动作**，不是手填清单。前提：`trunk` 上门禁全绿，且 `TESTING.md`
的真机端到端已有结论（通过，或 PARTIAL 且每条都有据）。

```bash
# 1. 确认当前提交就是你要发的树
bash _scripts/verify.sh && python -m unittest discover -s tests
python tools/faults-build.py check

# 2. 刷新发版清单（重算内容树摘要、页面数、用例数、时间戳）
python _scripts/gen-manifest.py

# 3. 置为 released 并回填 root_commit / released_at
python _scripts/gen-manifest.py --release

# 4. 清单自洽后再打 tag（tag 打在含 released 清单的那个提交上）
git add RELEASE-MANIFEST.yaml CHANGELOG.md
git commit -m "release: v3.0.0"
git tag -a v3.0.0 -m "ohos_qt-skills v3.0.0"
git push origin trunk --tags

# 5. 从 tag 拉归档线
git branch release/v3.0.0 v3.0.0 && git push origin release/v3.0.0
```

事后校验：`python _scripts/gen-manifest.py --check --strict` 应报"一致"。平时用
`--check`（不带 `--strict`）：计数必须一致，摘要允许是"旧快照"——否则每个普通提交都会红，
检查很快就没人看了。`verify.sh` 的 M1 同样只在**站在发版提交上**时强制摘要一致。

试用版/候选版可按同样流程打 `vX.Y.Z-rc1`，并把清单 `status` 留在 `trunk-candidate`。

---

## 怎么贡献

### 1. 代码 / 工具（`tools/`、`portgraph/`、`templates/`）

```bash
git switch -c dev/<your-topic> trunk
# 改动 + 补测试
bash _scripts/verify.sh
python -m unittest discover -s tests
git push origin dev/<your-topic>      # 提 PR 到 trunk
```

要求：

- 改动必须带测试；放宽门禁判据（G0–G12 / SV0–SV8）的 PR 一律不接受。
- 新 CLI 子命令要同步 `tests/test_kb_consistency.py` 里的子命令契约表（那是防漂移的锚）。
- 依赖只允许 Python 标准库；`portgraph serve` 之类的可选依赖必须隔离在可选路径。

### 2. 知识内容（`semantic/` `procedural/` `episodic/` `problems/` `faults/`）

- **新报错**：先查 `problems/_lookup.md` 是否已有；补充请附完整错误原文、环境三件套
  （Qt 版本 / OHOS SDK 版本 / DevEco 版本）、复现步骤与解法。
- **新故障**：按 `faults/_drafts/_template.md` 准备草稿（现象原文 / 环境 / **证据** /
  查重声明）。缺陷类必须附复现 demo（七原则见 `faults/_index.md` §六），规格限制类可用
  官方文档链接替代。**无证据的转述不予受理。**
- **页面规范**：frontmatter 必填 `id` / `type` / `summary` / `status` / `audience`；
  `id` 全仓唯一；`audience` 只能是 `public`；交叉引用用 `refs`（id）或 wikilink，不能断链。
- **不要写本机路径**：用 `ENV.local.md` 里的变量名（`QT5_15_OHOS_SDK` 等），`verify.sh`
  会拦 `/Users/<name>/` 这类泄漏。

知识真源的写入门是 `skills/kb-iterator`：业务 Agent 只能投草稿，合入需走主编门禁
（复现 demo 必测 + 人工核验 + 复现结果登记）。人可以按上面的规范直接提 PR，但同样要过门禁。

### 3. 索引与文档

`README.md` / `SKILL.md` / `AGENTS.md` / `_index/*` 里的**数字是被测试守护的断言**，
不是随手写的文案。数量变化时同步它们，否则 `tests/test_kb_consistency.py` 会红。

---

## 合并前门禁（缺一不可）

```bash
bash _scripts/verify.sh                     # 契约/结构/引用/卫生
python -m unittest discover -s tests -v     # 一致性 + 引擎 + 扫描
python tools/faults-build.py check          # 故障库真源 ↔ 派生物（改了 faults/knowledge 必跑）
```

- `ERROR` 必须清零；`WARN` 允许但要在 PR 里说明。
- 改了 `faults/_data/*.yaml` 或 C 页，必须 `python tools/faults-build.py build` 重建
  `_graph.yaml` / `_registry.md` 并提交。
- 提交信息写清"改了什么事实/判据"，不要只写 `update`。

---

## 不接受

- ❌ 放宽或绕过门禁判据、删除/跳过测试、为了让编译通过而注释功能代码。
- ❌ 无证据的故障定性（纯转述、猜测、聊天记录截图）。
- ❌ 提交构建产物（`.cxx/`、`.hvigor/`、`.idea/`、`.DS_Store`、`*.hap`）或本机绝对路径。
- ❌ 涉及内部/私有信息的内容（本仓只收 `audience:public`）。
- ❌ 在 `trunk` 或历史冻结分支上直接提交。

---

## 内嵌的 HarmonyOS 平台通用知识

`ohos-common-kb-public/` 是内嵌的平台知识子集（ArkTS / ArkUI / NAPI / Stage / 工具链，
27 页）。它在本仓内**可维护**：修正请直接提 PR，并在描述里标注依据的官方文档链接。
若与官方文档冲突，以官方文档为准。

## License

MIT（见 `LICENSE`）。提交的 PR / issue 内容视同在该协议下贡献。
