# 贡献指南

## 本仓库的性质

本仓库是 **Qt for HarmonyOS 知识库的公开主仓**（canonical trunk）。所有公开的 Qt 鸿蒙化知识在此维护，团队成员和外部开发者均可通过 PR 贡献。

## 如何贡献

### 方式一：提交 PR（推荐）

适用于：修正错误、补充知识、新增问题记录。

```bash
# 1. Fork 或 clone 本仓库
git clone https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills.git
cd ohos_qt-skills

# 2. 初始化本地环境
python _scripts/kb-init.py

# 3. 创建分支
git checkout -b <your-name>/<type>-<slug>

# 4. 编辑/新增内容（见下方"写什么"）

# 5. 验证
bash _scripts/verify.sh

# 6. 提交 + 推送 + 创建 PR
git add <files>
git commit -m "<type>(<scope>): <summary>"
git push origin <branch>
# 在 GitCode 上创建 PR -> main
```

### 方式二：提 Issue

适用于：报告错误、提出知识需求、提问。

在仓库提 Issue，使用对应模板：
- **Knowledge correction** — 发现内容错误
- **Knowledge request** — 希望补充的知识
- **Qt crossplatform diff** — Qt 跨平台差异报告
- **Qt doc inconsistency** — Qt 文档与实际行为不一致

维护者或 Agent 会将 Issue 转化为 PR（`closes #N`）。

## 写什么

### 两条路径

| 场景 | 目标路径 | 模板 |
|------|---------|------|
| 编译/部署/运行时 **报错** | `problems/<type>-<slug>.md` | `_templates/problem.md` |
| **新知识**（概念、流程、复盘） | `drafts/E{N}-<slug>.md` | `_templates/draft.md` |
| 已有页面的 **小修正** | 直接编辑 | — |

### 草稿流程

新的非报错类知识写入 `drafts/`（草稿暂存区）：
1. 取下一个编号：`ls drafts/E*.md | sort -V | tail -1` → max+1
2. 用 `_templates/draft.md` 创建 `drafts/E{N}-<slug>.md`
3. 随 PR 提交
4. **合入后自动 promote**：bot 将草稿移入正式目录（semantic/procedural/episodic）并重建索引

### 报错记录

实际的编译/运行时错误**直接写入 `problems/`**（不走草稿）：
- `error_message` 字段填入完整错误文本（便于全文搜索）
- 文件名格式：`<type>-<slug>.md`（如 `build-fail-missing-perl.md`）

## PR 规范

### 标题格式

```
<type>(<scope>): <summary>
```

- type: `add` / `fix` / `update` / `archive` / `doc`
- scope: 文件名或域（如 `problems`, `semantic`, `drafts`）
- 示例: `add(problems): EGL surface recreate 黑屏`, `fix(semantic): 更正窗口模型 API 签名`

### PR 描述

```markdown
## 变更类型
add | fix | update | archive

## 变更摘要
一两句话说明改了什么

## 影响的文件
- path/to/file1.md
- path/to/file2.md

## 自检清单
- [ ] `bash _scripts/verify.sh` 通过
- [ ] 不含客户名/商业内容/内部路径/同事真名
- [ ] 路径使用 `${ENV_VAR}` 占位符
- [ ] frontmatter 字段完整（id, title, status, summary, tags, refs）
- [ ] 新页面已在 `_index/_map.md` 中可见（verify.sh 会自动检查）
```

### 分支命名

```
<your-name>/<type>-<slug>
```

示例：`zhangsan/add-egl-blackscreen`, `lisi/fix-api-mapping`

## 审核流程

```
PR 提交
  |
  v
自动门禁（bot 每 10-15 分钟轮询）：
  - verify.sh 25 项检查
  - LLM 语义评审（frontmatter/铁律/泄露扫描）
  |
  v
+-- 门禁通过 + 低风险路径 + 已知作者 --> 自动合入
|
+-- 其他 --> 标记 "needs-editor"，等待人工审核
```

**低风险路径**（可自动合入）：`drafts/`、`problems/`
**需人工审核**：`semantic/`、`procedural/`、`_scripts/`、根文档

## 硬性规则（拒绝条件）

以下内容会导致 PR 被自动拒绝：

- **客户/商业信息**：客户名称、合同内容、商业 Qt 许可细节
- **内部路径**：`C:/Users/xxx`、内部服务器地址、内部 Gerrit URL
- **同事真名**：使用角色描述或 GitHub/GitCode ID 代替
- **密钥/凭证**：任何形式的 token、password、API key
- **未脱敏的内部工具链**：内部 CI 地址、内部包管理源

**路径脱敏规则**：使用 `${ENV_VAR}` 占位符（见 `ENV.md`），如：
- `${QT5_12_SRC}` 代替 `/home/user/qt5.12/`
- `${OHOS_SDK_ROOT}` 代替 `D:/HarmonyOS/sdk/`

## 内嵌的 HarmonyOS 平台通用知识

`ohos-common-kb-public/` 目录包含 HarmonyOS 平台通用知识（ArkTS、ArkUI、NAPI、Stage 模型等），由 `ohos-common-kb` 仓库定期同步。

如果你发现平台通用知识有问题：
- 可以在本仓提 Issue
- 也可以直接向 [ohos-common-kb](https://gitcode.com/su-meiyan/ohos-common-kb) 提 PR

## 版本与发布

本仓库使用 SemVer 版本管理：
- **MAJOR**: 架构变更（如本次 trunk flip）
- **MINOR**: 新增知识页面
- **PATCH**: 修正、问题记录补充

发布由 bot 在合入后自动执行（patch/minor），MAJOR 需 editor 手动触发。

## License

MIT（见 `LICENSE`）。提交 PR 即表示同意在该协议下贡献。
