# 分支收敛记录

本仓历史上有多条并行分支（内容同步、发布、架构实验）。本文件记录**每条分支的内容并入
`trunk` 的实际情况**，以及少数**有意不并入**的内容和它们的现对应物——避免"看起来合并了、
其实少了半截"，也避免同一件事在仓里出现两套做法。

复核命令（任何时刻都能重跑）：

```bash
git fetch origin
for b in $(git branch -r | grep -v HEAD | sed 's#origin/##' | tr -d ' '); do
  printf "%-26s 祖先=%s 独有提交=%s\n" "$b" \
    "$(git merge-base --is-ancestor origin/$b trunk && echo YES || echo NO)" \
    "$(git rev-list --count trunk..origin/$b)"
done
```

---

## 一、并入状态

| 分支 | 独有提交 | 状态 | 说明 |
|------|:--------:|------|------|
| `main` | 0 | **已全部并入** | v2.2.1 知识基线，是 `trunk` 的祖先 |
| `bitfun-release` | 0 | **已全部并入** | 执行层（CLI）、机器层（QOH/R）、故障图、模板的来源 |
| `fix/kb-init-scripts` | 0 | **已全部并入** | 祖先 |
| `sync/rewrite-*`、`sync/sync-*`（5 条） | 0 | **已全部并入** | 历史同步点，均为祖先 |
| `release/v2.1.0` | 0 | **已全部并入** | 旧发版线，祖先 |
| `matrix-release` | 1 | **内容已并入** | 唯一提交是 `README.md` + `SKILL.md` 重写：`trunk` 以这两份文档为基底，再叠加治理层（`kb.yaml`、`_scripts/`、`TESTING.md`、`CONTRIBUTING.md`、分支模型、发版流程） |
| `lzh-add-qt-cef-graft-test` | 1 | **内容已并入** | CEF 开发指南与 PyQt 状态页此前已在 `trunk`；本次补入 `tools/kb-cef-graft.py` + 配置样例，并把指南里"脚本不在本知识库"的旧说法改正 |
| `trunk-flip-v3` | 4 | **部分并入** | 补入 `team/`、`_templates/`、`procedural/knowledge-sedimentation.md`、`_scripts/pre-push`；其余见第二节 |

三条内容已并入的分支同时用 `git merge -s ours` 登记了祖先关系（只记历史、不动文件树），
所以 `--is-ancestor` 对**全部 13 条分支**都返回 YES，`trunk..<分支>` 恒为 0：
内容与历史都不再有分支悬空。

`matrix-release` 之所以单独存在，是为了让**只有知识层**的对外版本先发出去；它的文档口径
（正面陈述、保留全部命令与操作细节）现在就是 `trunk` 的文档口径，两处不再分叉。

---

## 二、有意不并入的内容

判断标准只有一条：**同一件事是否有两套做法**。会与 `trunk` 现状冲突、或已被 `trunk`
工具链取代的，不复制进来，在表里写明它的能力现在落在哪里。

| 来自 | 内容 | 不并入的原因 | 现在这个能力在哪 |
|------|------|------------|----------------|
| `trunk-flip-v3` | `_scripts/kb-gate.sh`（946 行） | 检查项与 `verify.py` 大面积重合，且编码的是**旧 schema**（如"trunk 页面无 `audience` 字段"——与本仓 `audience: public` 必填相反），并入会造成两套互斥判据 | `_scripts/verify.py`（10 类）+ `_scripts/ci.sh` |
| `trunk-flip-v3` | `_scripts/kb-release.sh`、`_scripts/RELEASE-STATE` | 发版状态机被 `RELEASE-MANIFEST.yaml`（机算、可对账）取代 | `_scripts/gen-manifest.py` + `CONTRIBUTING.md` §发版流程 |
| `trunk-flip-v3` | `_scripts/kb-regen-indexes.sh`（345 行） | 生成格式基于旧索引布局，直接跑会把仪表盘改回旧格式 | 计数由 `tests/test_kb_consistency.py` 守（页数/域计数/故障规模与文档绑定），条目随页手动补一行；**这是本仓的已知空白**，将来补时应按当前布局重写而非移植 |
| `trunk-flip-v3` | `_scripts/kb-sediment.sh`（254 行） | 写入目标是 `drafts/E{N}-*`，与本仓 `faults/_drafts/` 是两套草稿约定 | `procedural/knowledge-sedimentation.md`（协议）+ `skills/kb-iterator`（流程）+ `faults/_drafts/_template.md` |
| `trunk-flip-v3` | `_scripts/kb-promote-drafts.sh` | 同上，草稿目录约定不同 | 主编门禁（`faults/_index.md` §六）+ `skills/kb-iterator/SKILL.md` |
| `trunk-flip-v3` | `_scripts/kb-bot.py`（408 行，PR 机器人） | 依赖外部 bot 运行环境与 GitCode 凭据，不在知识层职责内 | 未提供；由维护者手工执行合并门禁 |
| `trunk-flip-v3` | `_scripts/kb-init.py` | 环境初始化已由 skill 承担（检测 + 安装命令 + 写 `ENV.local.md`） | `skills/kb-init/SKILL.md` + `tools/qt-sdk-run.py init` |
| `trunk-flip-v3` | `_scripts/kb-sync-common.sh` | 用于同步内嵌平台知识子集；本仓 `ohos-common-kb-public/` 已是裁剪后的稳定子集，无同步源 | **已知空白**：将来若恢复上游同步再补 |
| `trunk-flip-v3` | `drafts/README.md` + `drafts/` 目录 | 与 `faults/_drafts/` 重复的草稿入口 | `faults/_drafts/`（模板 `faults/_drafts/_template.md`） |
| `lzh-*` | `TEST-REPORT.md`（仓库根的一次性验证记录） | 根目录放一次性测试报告会让入口文件越来越杂；结论已体现在 CEF 指南的版本/集成章节 | `procedural/qt-cef-ohos-dev-guide.md` 的实测记录小节 |

> 未并入的内容仍完整保存在对应冻结分支上，随时可取：`git show origin/trunk-flip-v3:_scripts/kb-regen-indexes.sh`。

---

## 三、并入后的一致性

`trunk` 的判据只有一处：`bash _scripts/ci.sh` 全绿。并入动作本身也受它约束——
页面计数、故障规模、用例数、发版清单任何一处对不上，门禁直接红（`M1`、`C8`、
`test_document_counts` 系列）。
