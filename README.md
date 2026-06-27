# OHOS Qt Skills

Qt for HarmonyOS 开发的 AI Agent Skills 集合——帮助开发者将 Qt 项目编译、运行到鸿蒙系统上。

## Skills 的关系

**`qt-ohos-project-analyzer` 是总开关**，编排整个鸿蒙化编译流程，在需要时调用子 skill；`aki-bridge-generator` 和 `hmos-share-integration` 为功能扩展 skill，在需要集成鸿蒙系统 API 时使用：

```
qt-ohos-project-analyzer（总开关 / 鸿蒙化项目分析）
  ├── 调用 → create-qt-app（工程生成）
  └── 调用 → build-run-qt-app（编译运行）

aki-bridge-generator（AKI 桥接代码生成）
  └── 被 hmos-share-integration 依赖 — 分享功能需要 AKI 桥接框架

hmos-share-integration（碰一碰分享 / 手势分享 / 沙箱接收）
  └── 依赖 aki-bridge-generator — Share API 通过 AKI 桥接 Qt C++ 层
```
核心 skill 也可以独立使用，但在总开关编排下会进入**快速模式**（跳过重复确认、共享环境信息）。 
 
 
 --- 
 
 
 ## 各 Skill 主要功能 
 
 
 ### qt-ohos-project-analyzer — 总开关 / 编排器 
 
 
 1. **铁律定义** — 所有 skill 共享的流程纪律（禁止推测、知识库优先、修复必须沉淀等） 
 2. **MCP 工具链就绪检查** — 阻断性前置条件，未安装则暂停引导安装 
 3. **Qt/OHOS 前置环境确认** — 确认分支源码路径、编译产物路径、胶水模版 → 生成 `qt_env.md` 
 4. **依赖梳理** — Qt 版本兼容性评估、模块依赖、三方库、构建系统 
 5. **编排编译** — 调用 create-qt-app 创建工程 → 调用 build-run-qt-app 编译运行 → 双重交验确认 → 输出总结文档 
 
 
 ### create-qt-app — 工程生成 
 
 
 1. **从零创建新工程** — 下载模板 → 放 Qt 源码（QWidget/QML）→ 配置 CMake → 复制样式库 → 配置胶水代码 
 2. **已有 Qt 工程鸿蒙化** — 在工程根目录创建 `HarmonyOS/` 子目录放胶水代码，不干扰原有结构 
 
 
  ### build-run-qt-app — 编译运行 
  
  
  1. **DevEco MCP 安装配置** — 覆盖 Trae、Cursor、VS Code 等多种 IDE 
  2. **项目构建** — 调用 build_project，含构建失败排查流程（知识库优先 → 错误分类 → 修复沉淀） 
  3. **应用启动 + 日志查看** — 调用 start_app + get_hilog_or_faultlog_recent 
  4. **UI 测试**（可选）— UI 树获取 + UI 操作（点击/滑动/输入/截图） 

  ### aki-bridge-generator — AKI 桥接代码生成

  1. **桥接方向确认** — C++→ArkTS / ArkTS→C++ / 双向桥接
  2. **接口设计** — Qt Q_OBJECT 单例 + SafetyCallback 指针成员 + JSBIND_GLOBAL 全局函数模式
  3. **生成 C++ 桥接代码** — Bridge 类实现、SafetyCallback setter（delete+new 模式）、QMetaObject 线程转发
  4. **生成 AKI JSBinding** — JSBIND_GLOBAL + JSBIND_FUNCTION 声明、JSBIND_ADDON 注册
  5. **生成 ArkTS 调用代码** — ShareBridgeProxy 模块、SafetyCallback 回调注册、init() 初始化
  6. **配置类型声明** — index.d.ts + oh-package.json5 + entry devDependencies

  ### hmos-share-integration — 碰一碰分享 / 手势分享 / 沙箱接收

  1. **分享角色与类型确认** — 发送端（碰一碰/手势分享）/ 接收端（沙箱 dataReceive）/ 两者都要
  2. **桥接方案设计** — SafetyCallback 跨线程调用、windowId Qt→ArkTS 传递、SharableTarget/ReceivableTarget 回调流程
  3. **创建 ArkTS 侧代码** — ShareBridgeProxy.ets 完整实现（碰一碰文件/链接分享、沙箱接收）
  4. **创建 AKI JSBinding** — ShareBridge C++ 桥接类 + JSBIND_CLASS/JSBIND_ADDON 注册
  5. **Qt 侧集成** — windowId 获取、回调注册、消息队列转发
  6. **配置权限与依赖** — module.json5 权限、oh-package.json5（禁止声明 @kit.ShareKit）、modules.xml 注册
 
 
 --- 
 
 
 ## 目录结构
```
ohos_qt-skills/
├── README.md                   # 项目说明
├── skills/                     # Skills 目录
│   ├── qt-ohos-project-analyzer/  # 总开关 / 鸿蒙化项目分析器
│   │   └── SKILL.md            # Skill 主文档
│   ├── create-qt-app/          # 创建 Qt 鸿蒙应用
│   │   └── SKILL.md            # Skill 主文档
│   │   ├── references/         # 参考文档
│   │   ├── templates/          # 模板文件
│   │   └── scripts/            # 脚本文件
│   ├── build-run-qt-app/       # 编译运行 Qt 鸿蒙应用
│   │   └── SKILL.md            # Skill 主文档
│   ├── aki-bridge-generator/   # AKI 桥接代码生成
│   │   ├── SKILL.md            # Skill 主文档
│   │   ├── references/         # AKI 参考文档（类型映射、JSBinding 语法、用法指南、示例）
│   │   └── templates/          # 代码模板（.h/.cpp/.ets）
│   ├── hmos-share-integration/ # 碰一碰分享 / 沙箱接收集成
│   │   ├── SKILL.md            # Skill 主文档
│   │   ├── references/         # 分享 API 参考、最佳实践
│   │   └── templates/          # 代码模板（.ets/.cpp/.h）
│   └── INDEX.md                # Skills 索引
├── docs/                       # 额外文档
│   └── qt-harmonyos-setup.md   # Qt 鸿蒙环境配置指南
└── LICENSE                     # 许可证文件
```

## Skills 列表

| Skill | 角色 | 描述 | 状态 |
|-------|------|------|------|
| [qt-ohos-project-analyzer](skills/qt-ohos-project-analyzer/SKILL.md) | **总开关** | 鸿蒙化项目分析：铁律 + 环境确认 + 依赖梳理 + 编排编译 + 验证交付 | ✅ 可用 |
| [create-qt-app](skills/create-qt-app/SKILL.md) | 子 skill | 生成 Qt 鸿蒙应用工程结构（QWidget 或 QML），或已有工程鸿蒙化 | ✅ 可用 |
| [build-run-qt-app](skills/build-run-qt-app/SKILL.md) | 子 skill | 使用 DevEco MCP 工具链编译、运行 Qt 鸿蒙应用并查看日志 | ✅ 可用 |
| [aki-bridge-generator](skills/aki-bridge-generator/SKILL.md) | 扩展 skill | 使用 AKI 框架生成 C++↔ArkTS 桥接代码（SafetyCallback、JSBIND_GLOBAL、类型声明） | ✅ 可用 |
| [hmos-share-integration](skills/hmos-share-integration/SKILL.md) | 扩展 skill | 集成碰一碰分享、手势分享、沙箱接收功能到 Qt 鸿蒙应用（依赖 aki-bridge-generator） | ✅ 可用 |

## 如何使用

### 1. 安装 Skills

将 skills 目录复制到你的 AI Agent 配置目录：

```bash
# 方法一：直接复制到 agent 的 skills 目录
cp -r skills/* <agent-config-dir>/skills/

# 方法二：克隆仓库
git clone https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills.git
# 然后在 agent 配置文件中添加 skills 路径
```

> 所有 skill 都需安装。核心 skill 会被总开关调用；扩展 skill（aki-bridge-generator、hmos-share-integration）在需要集成鸿蒙系统 API 时使用。单独使用子 skill 时也要先读取 `qt-ohos-project-analyzer/SKILL.md` 的铁律章节（§0）。

### 2. 在 AI Agent 中使用

**通过总开关（推荐）**：直接调用 `qt-ohos-project-analyzer`，它自动编排调用子 skill：

```
帮我把 CopyQ 项目鸿蒙化编译。
项目路径：/home/user/copyq
Qt 编译产物路径：/opt/qt5.15.16-arm64
```

**单独使用 create-qt-app 创建工程**：

```
帮我生成一个俄罗斯方块的 demo 工程，使用 QML。
工程目录放到：C:\Users\<username>\Documents\TetrisDemo
模板胶水代码路径：C:\Users\<username>\Downloads\ohostemplateforqtapplication.zip
```

**单独使用 build-run-qt-app 编译运行**（工程已就绪时）：

```
帮我在 DevEco 中编译运行这个 Qt 鸿蒙工程。
工程路径：/home/user/TetrisDemo
```

**单独使用 aki-bridge-generator 生成 AKI 桥接代码**：

```
帮我为 Qt 鸿蒙应用生成 AKI 桥接代码，需要调用鸿蒙 NFC API。
桥接方向：C++ → ArkTS（双向）
工程路径：/home/user/NfcApp
```

**单独使用 hmos-share-integration 集成分享功能**：

```
帮我把碰一碰分享功能集成到 Qt 鸿蒙应用中。
分享角色：发送端 + 接收端
工程路径：/home/user/ShareDemo
```

## 开发贡献

### Skill 文档规范

每个 skill 目录应包含：

- `SKILL.md` - Skill 主文档（必需）
  - YAML frontmatter：name, description
  - 详细的步骤说明
  - 常见问题和解决方案

- `references/` - 参考文档（可选）
  - API 文档、官方指南链接等

- `templates/` - 模板文件（可选）
  - 代码模板、配置文件模板等

- `scripts/` - 脚本文件（可选）
  - 辅助脚本、自动化工具等

### 提交新 Skill

1. Fork 本仓库
2. 在 `skills/` 目录下创建新的 skill 目录
3. 编写 `SKILL.md` 文档
4. 更新 README.md 中的 Skills 列表
5. 提交 Pull Request

## 相关链接

- [Qt for HarmonyOS 官方文档](https://wiki.qt.io/Qt_for_HarmonyOS)
- [DevEco Studio](https://developer.huawei.com/consumer/cn/deveco-studio/)
- [DevEco Toolbox GitHub](https://github.com/open-deveco/deveco-toolbox)
- [DevEco MCP Releases](https://github.com/open-deveco/deveco-mcp/releases)

## 许可证

本项目采用 Apache 2.0 许可证，详见 [LICENSE](LICENSE) 文件。