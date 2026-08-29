# 变更日志

> 外部知识库（开发者版）发版记录。版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。
> 版本对象 = 外部仓整包（Qt 公开子集 + 内嵌 ohos-common-kb + kb-init skill + 根文档）。
>
> - **MAJOR** — 破坏性：删/移走用户依赖的页、`audience` 由 public→internal、目录重排致旧链接断、铁律/API 映射被证伪并反转
> - **MINOR** — 内容新增：新页/新节/新 API 映射条目/新 task 类型/内嵌新 KB 或 skill
> - **PATCH** — 内容修正：typo/措辞修正、错误解决方案更新、Qt 参考版本 bump
>
> 发版流程见内部 `procedural/release-external-edition.md`。每版的 `RELEASE-MANIFEST.yaml` 记录源端 KB git SHA + content_tree_sha256，可复现。

---

## v2.2.1 — 2026-08-29

- fix(procedural+semantic): 修复 skills 自嵌套与 manifest 幽灵 skill

- copy_skills 在持久化/复用 OUT（如 dist/dev-edition 二次构建）下 cp -r src dst 会把 src 拷进已存在的 dst → 产出 skills/skills/ 双层嵌套；改 rm -rf + /. 拷内容防嵌套。
- gen-release-manifest skills 枚举盲目收所有子目录，把自嵌套的 skills/ 登记成幽灵 skill（manifest 出现 skills: ["kb-init","skills"]）；加 SKILL.md 校验 + 跳过自嵌套目录兜底。
- PR#9 曾手动清理外部仓 skills/skills/ 产物，本次在源端两层加固固化，避免复发。

## v2.2.0 — 2026-08-27

- Qt5+CEF 鸿蒙开发指导 + issue 模板（.gitcode/ISSUE_TEMPLATE/）+ xsy-letos/xsy-pyqt 迁移经验 + 版本化发版机制（kb-publish.py 固定脚本从 main 发版）

## v2.1.0 — 2026-08-25

- Qt6.12 beta3 模块状态更新（QtHarmonyExtras 重新独立成模块 + 文件权限接口修正）；新增 QCTools/xi-qt OHOS 迁移经验；修正公开页硬编码 Qt 路径脱敏；新增版本化发版机制（README 能力规格节 + RELEASE-MANIFEST + CHANGELOG）

## v2.0.0 — 2026-08-19

- **MINOR** 内嵌 `ohos-common-kb` 公开子集（ArkTS/ArkUI/NAPI/Stage 模型/DevEco 工具链基础）到 `ohos-common-kb-public/`
- **MINOR** 新增 `skills/kb-init/` 初始化 skill：环境探测 → 引导安装缺失依赖 → 生成 `ENV.local.md` → 校验环境
- **MINOR** 多渠道 Qt 源码获取（商业 license `codereview.qt-project.org` / 开源镜像 `ohos-qt/qt-harmonyos-src` / 预编译 SDK releases）
- **MINOR** 新增根文档 `SETUP.md` / `CONTRIBUTING.md` / `SECURITY.md`
- **MINOR** `RELEASE-MANIFEST.yaml` 记录多源 SHA + `content_tree_sha256` + 页数计数（builder v2, schema v1）

> v2.0.0 之前的旧 5-skill 仓库历史见 `legacy/pre-rewrite-*` tag（已快照至内部 `raw/imports/ohos_qt-skills-legacy/` 供未来继承）。未回填 v1.0.0。
