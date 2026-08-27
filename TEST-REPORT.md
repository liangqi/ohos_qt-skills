# Qt+CEF Demo 生成测试验证记录

> 2026-08-27 验证：外部知识库（含 `procedural/qt-cef-ohos-dev-guide.md` + `tools/kb-cef-graft.py` + `tools/kb-cef-graft.config.example.json`）在干净环境下，一轮生成可运行的 Qt+CEF 鸿蒙 demo。

## 测试环境

| 项 | 值 |
|----|-----|
| **Agent** | dsh |
| **模型** | glm-5.2 |
| **知识库** | ohos_qt-skills（外部版，含 qt-cef 指导 + 嫁接脚本 + 配置） |

## 测试提示词（脱敏）

```
用 <EXTERNAL_KB> 这个外部知识库，做一个 Qt+CEF 鸿蒙 demo 并在设备 <DEVICE> 上跑起来。

- <EXTERNAL_KB> = <外部知识库路径>
- <QT_TEMPLATE> = <Qt OHOS 模板路径（qtbase/src/harmonyos/templates）>
- <QT_SDK> = <Qt OHOS SDK 路径>
- <OPENQTCEF> = <OpenQtCef 解压路径>
- <DEVICE> = <设备 id>
```

> 实际测试填入真实路径/设备 id；此处脱敏为占位符。

## 执行数据

| 指标 | 值 |
|------|-----|
| 轮次 | 1 轮 · 36 步 |
| LLM 用时 | 19m49s |
| 工具调用用时 | 13m35s |
| 首 token 平均 | 5s |
| 输出速率 | 60 tok/s |
| 缓存命中 | 92% |
| 输入 token | 3.4M |
| 输出 token | 60.8K |

## 结果

✅ **一轮成功**：Agent 读知识库 → 自动路由到 `qt-cef-ohos-dev-guide` + `tools/kb-cef-graft.py` → 改配置 → `--run` 一条龙（graft 嫁接 + devecocli signature 签名 + run 装机启动 + log --crash 崩溃检查）→ app 运行中（`com.example.qtcefdemo` 主进程 + CEF `:NetworkService`/`:Renderer` 子进程），无崩溃。

嫁接脚本固化了 15 个运行踩坑（P1-P15，见 `tools/kb-cef-graft.py` `_PITFALLS` 注释），环境配置全在 `tools/kb-cef-graft.config.example.json`（换环境只改配置不改脚本）。
