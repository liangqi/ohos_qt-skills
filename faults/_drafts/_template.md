---
# 草稿 frontmatter：格式宽松，协作者只需改 status/submitted/submitter；
# reviewer/review_result 由主编填写。
status: draft              # draft（新投）/ in-review（审核中）/ returned（已退回）/ rejected（不收）
submitted: YYYY-MM-DD
submitter: "<姓名/昵称/匿名>"
contact: "<可选：issue 链接/邮箱>"
reviewer: ""               # 主编填
review_result: ""          # 主编填：如 "promoted 2026-XX-XX（S-XXXX/C-XXXX）" / "returned：demo 无法构建" / "rejected：app 自身 bug"
---

# 草稿：<一句话现象标题（用开发者会说的词）>

> 本模板即**协作者提交清单**。必填项缺失会被主编直接退回；格式不拘（Markdown 即可），
> 不需要懂 S/C/W/T 数据模型——**编号与拆分由主编合入时完成**。
> 提交前先查重：`problems/_lookup.md`（报错）与 `faults/_registry.md` §症状索引（现象）。

## 一、现象【必填】

- **可观察表现（错误信息原文 / 日志关键行，不要转述）**：
- **触发条件 / 复现步骤**：
- **首次发现**（日期 + 场景/项目）：

## 二、环境【必填】

- **Qt 版本与 kit 来源**（预编译 SDK / 自编，注明 commit 或安装器版本）：
- **OHOS API 版本 / 系统版本 / 设备**：
- **构建方式**（CMake / hvigor / CLI / DevEco）：

## 三、证据【必填——问题确认门禁：定性 Qt 框架侧问题必须有 A 或 B（或组合）；无证据的转述不予受理】

> 规格限制类（limitation，如"沙箱禁 symlink""某 API 已弃用"）改填 **C2 官方文档/规格链接与适用版本**，无需 demo。

**A. 复现 demo（运行时行为异常类首选）**——编写七原则 + Qt 框架侧硬性要求见 `faults/_index.md` §六：
- 获取方式（仓库链接 / 附件路径 / 压缩包位置）：
- 已自验：☐ 可构建　☐ 可安装启动　☐ 现象出现　☐ 日志可判读（demo 内置关键日志点）
- **Qt 框架侧问题（缺陷归 Qt 适配层/上游）硬性要求**：☐ 复现逻辑集中在**单个 main.cpp**（ohos 工程仅胶水壳，不含业务代码）　☐ **复现步骤已写明**（编号到操作级 + 每步预期 + expected vs actual）
- **预期行为 vs 实际行为**：

**B. 调试日志 + 栈（无 demo 时必须，或与 demo 配套）**：
- hilog 关键行 / cppcrash·jscrash faultlog 栈回溯 / 探针日志 / 构建错误原文（粘贴原文，不转述）：
- 采集环境与时间窗口：

**C. 静态/文档证据（受限使用）**：
- C1 源码 file:line 引用链（**仅限 API 语义/宏分支/头文件等静态可判定问题**）：
- C2 官方文档/规格链接与适用版本（limitation 专用）：

## 四、初步根因【选填，有则填】

- 定位 / 证据链（源码位置、日志推论、隔离测试）：

## 五、临时方案 / 替代方案【选填】

- 怎么绕的 + 代价（功能受损/重编/降级…）：

## 六、上游单【选填】

- QTBUG / 华为 issue / 交付件链接与当前状态：

## 七、查重声明【必填，勾选】

- ☐ 已查 `problems/_lookup.md`：☐ 无同类报错　☐ 有但本条提供新信息：______
- ☐ 已查 `faults/_registry.md` §症状索引：☐ 无同表现　☐ 有但根因/方案是新信息：______

## 八、附件与自评【选填】

- 附件（faultlog / 截图 / 录屏路径）：
- 严重度自评（blocker/critical/high/medium/low）与理由：

---

<!-- 主编合入门禁（详见 faults/_index.md §六·协作草稿模式，全部留痕）：
     ① 查重：S/C 已有 → 退回改为对现有节点的补充，不重复建档
     ② 复现测试（按 nature 分级）：
        - defect/undetermined：必测草稿 demo（无法构建→退回修 demo；复现失败→退回补环境，未复现不合入）
        - limitation：核验官方文档/规格链接与适用版本
     ③ 人工核验：证据链属实 / nature 定性 / responsible 归层 / severity 校准 /
        版本·日期·单号事实（宁缺勿造）/ W 可用性与退役条件 / 脱敏（公开版）
     ④ 复现留痕：合入的 C 页"版本验证记录"第一行登记主编复现（日期/环境/结论）；
        协作者方案经主编验证的 W 记 tested，未验证记 proposed
     ⑤ promote：拆分为 S/C/W/T 真源记录（分配编号）→ 删除草稿文件（git 历史+验证记录即存档）
     ⑥ python tools/faults-build.py build（ERROR 清零）+ 关联页 refs 回填 fault-C-XXXX -->
