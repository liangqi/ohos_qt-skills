---
id: fault-C-0017
cid: C-0017
type: cause
title: "非 UTF-8 终端（Windows Git Bash/GBK）下向 curl -d 直接内联中文：shell 按终端编码传字节，curl 设计上只透传，API 端按 UTF-8 解码成乱码"
nature: defect
domain: toolchain
fault_type: caveat
responsible: app
co_responsible: []
component: "Windows Git Bash（MSYS2）终端编码（GBK/CP936）× curl -d 参数透传"
severity: medium
evidence_type: logs
status: workaround
fix_route: "改用法：中文 JSON 写入 UTF-8 临时文件后 curl -d @file 引用（或整体切换 UTF-8 终端）"
review_note: "薄 C 页（app 使用问题）：与 Qt/HarmonyOS 无关（Windows 开发环境工具链问题），收录范围由主编确认；方案 B（chcp 65001）在所用 Git Bash 版本的稳定性可再评估"
depends_on: []
affects_qt: []
affects_ohos: []
qoh: []
first_seen: 2026-06-10
review_due: 2026-12-15
created: 2026-09-15
updated: 2026-09-15
tags: [curl, encoding, utf-8, gbk, git-bash, windows, mojibake, gitcode-api, app-usage]
audience: public
refs: [runtime-curl-chinese-garbled]
summary: >
  Windows Git Bash 终端默认编码非 UTF-8，中文直接写进 curl -d 时 shell 按
  GBK 传字节、curl 按设计原样透传，API 端按 UTF-8 解码成乱码（返回 200/201
  但中文字段为 Cyrillic/Latin-1 形态）。defect/app（应用使用问题，非框架/
  平台）；W-0014（UTF-8 文件 + @file 引用）已实战采用。
---

# C-0017 curl 中文乱码（Windows Git Bash 编码透传链）

> nature: defect ｜ 责任: app ｜ 状态: workaround ｜ 表现: S-0016 ｜ 方案: W-0014 ｜ 跟踪: 暂无 ｜ 复核: 2026-12-15

## 表现（symptoms）

### S-0016 Windows Git Bash 下 curl 请求体中文乱码

```
期望: "feat: Qt for HarmonyOS 知识库完整交付 + 门禁 CI 体系"
实际: "feat: Qt for HarmonyOS ֪ʶ + Ž CI ϵ"
```

curl POST/PATCH 请求体中的中文在 API 端（GitCode）显示为乱码（通常为
Cyrillic 或 Latin-1 字符形态，如"知识库"→"֪ʶ"、"门禁"→"Ž"）；API 返回
200/201 成功，但 title/body 等字段中的中文全部乱码。

## 根因 / 定性依据

Windows Git Bash（MSYS2）终端默认编码不是 UTF-8（GBK/CP936）。当 curl 的
`-d` 参数直接包含中文时：

1. Shell 将中文以终端编码（GBK/CP936）字节传递给 curl；
2. curl **按设计原样透传字节**——即使设置
   `Content-Type: application/json; charset=utf-8` 也不会自动转换编码；
3. API 端按 UTF-8 解码 → 乱码。

定性依据：错误原文对比（上）+ 排查步骤（`curl -v` 查看 `>` 开头请求体
实际字节、`file` 检查文件编码、`echo $LANG` 查 locale）。logs 级（错误
原文可判读，无 demo 工程）。

## 责任判定

`app`（使用方式）：curl 透传字节是文档化设计行为而非缺陷（无上游可修）；
终端编码是本机环境配置；根因落在"在非 UTF-8 终端里内联中文"这一用法上，
修复到达路径 = 改自己的命令用法。本条与 Qt/HarmonyOS 均无关（Windows
开发环境问题），收录价值在于可复用经验；深度内容（GitCode API 的
PATCH/Bearer 等配套经验）留在
[runtime-curl-chinese-garbled](../problems/runtime-curl-chinese-garbled.md)。

## 根治方案（defect）

改用法（等价于根治）：中文 JSON 写入 UTF-8 编码的临时文件，curl 以
`-d @file` 引用（W-0014）；或整体切换到 UTF-8 终端环境后再内联。

## 临时方案（Workarounds）

- **W-0014（adopted，2026-06-10 实战验证）**：方案 A（推荐）——heredoc 写入
  临时文件后 `@file` 引用：

  ```bash
  # 1. 用 heredoc 写入临时文件（heredoc 内容以 UTF-8 写入文件）
  cat > /tmp/pr_data.json << 'JSONEOF'
  {
    "title": "feat: Qt for HarmonyOS 知识库完整交付 + 门禁 CI 体系",
    "body": "描述内容..."
  }
  JSONEOF

  # 2. curl 读取文件（文件本身是 UTF-8，curl 原样发送）
  curl -s -X PATCH "https://gitcode.com/api/v5/repos/OWNER/REPO/pulls/1" \
    -H "Content-Type: application/json; charset=utf-8" \
    -H "Authorization: Bearer TOKEN" \
    -d @/tmp/pr_data.json
  ```

  代价：每次请求多一步写临时文件；heredoc 内容须确保 UTF-8。
  退役条件：终端环境可稳定保证 UTF-8 后，恢复 `-d` 直接内联中文。

  备选（同一根因，未单独立 W）：方案 B `chcp 65001` 切换代码页（部分
  Git Bash 版本不稳定）；方案 C `printf | curl -d @-` 管道。

## 跟踪单（Tickets）

暂无（使用问题，无上游可跟）。

## 版本验证记录

| 日期 | 环境（Qt/OHOS） | 动作 | 结果 | 状态变化 |
|------|----------------|------|------|---------|
| 2026-09-15 | Windows 10/11 + Git Bash (MSYS2) + curl 7.x/8.x（源页 2026-06-10 GitCode 建 PR 实战） | 随 problems 页建档转录：方案 A 实战解决，沉淀为可复用经验（Windows + Git Bash + curl + 中文 = 必须用文件传递 JSON） | 定性成立；方案 A 可用 | → workaround |

## 关联

- 症状（S）：S-0016
- 临时方案（W）：W-0014
- 跟踪单（T）：暂无
- problems：[runtime-curl-chinese-garbled](../problems/runtime-curl-chinese-garbled.md)
- 相关根因（C）：无
