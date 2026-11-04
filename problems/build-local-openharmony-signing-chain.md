---
id: problem-build-local-openharmony-signing-chain
type: problem
domain: build
tags: [签名, HAP, OpenHarmony, 本地根证书, hap-sign-tool, 调试证书, 过期, 装机失败]
created: 2026-11-04
updated: 2026-11-04
status: solved
severity: medium
audience: public
summary: "没有华为开发者证书时，用 OpenHarmony 本地根证书自签 HAP 的完整链路"
# ====== 检索关键字（Agent 快速匹配用）======
error_message: >
  error: signature verification failed
  error: install failed due to grant request permissions failed
  hap-sign-tool: error: the certificate has expired
error_code: ""
keywords: [签名, HAP, hap-sign-tool, 本地根证书, OpenHarmony, profile, p7b, 调试证书, 装机失败]
symptoms: "HAP 装机报签名校验失败；或调试证书过期后全部装机失败"
# ====== 问题详情 ======
environment: "OpenHarmony 本地 SDK 与真机/模拟器；不依赖华为开发者账号"
refs: [problem-build-app-layer-out-of-tree-prerequisites, procedural-qt-harmonyos-build-run-workflow]
related_problems: []
---

# 用 OpenHarmony 本地根证书自签 HAP

## 什么时候需要

没有华为开发者账号/AGC 证书，又要把 HAP 装到真机或模拟器上。OpenHarmony 提供的
本地根证书（`OpenHarmony.p12`、`OpenHarmonyApplication.pem`、`UnsgnedReleasedProfileTemplate.json`
等）可以自签出可被**调试设备**接受的 HAP。

## 链路（五步，缺一步都会在装机时才报错）

```
① 生成密钥对  → ② 生成 CSR → ③ 用本地根证书签发应用证书（.cer）
→ ④ 生成 profile（.p7b，绑定 bundleName + 设备 UDID/调试类型）
→ ⑤ hap-sign-tool 用证书 + profile 签 HAP
```

关键点：

- **bundleName 必须三处一致**：`app.json5` / profile / 签名命令；
- **设备标识**：调试 profile 要绑定设备（真机 UDID 或模拟器类型），换设备要重签；
- **证书有效期**：自签证书通常只有数月，过期后表现为"昨天还能装，今天全失败"——
  这是**唯一**需要检查的地方，不要先去查构建；
- **产物布局**：签名后的 HAP 与未签名 HAP 分开目录，避免拿错。

## 验证方法

1. `hap-sign-tool verify-app -in <signed.hap> -out <out> -public-profile <p7b>` 通过；
2. `hdc install <signed.hap>` 返回成功且 `bm dump -n <bundle>` 能看到条目；
3. 卸载重装一次（排除"覆盖安装沿用旧签名"的假成功）。

## 与官方签名的差异

| 项 | 本地自签 | 官方（AGC） |
|----|---------|------------|
| 适用设备 | 调试设备/模拟器 | 任意正式设备 |
| 分发 | 不可上架 | 可上架 |
| 权限 | 受限（受限权限需 profile 授权） | 按申请授予 |
| 过期 | 证书有效期短，需定期重签 | 按证书有效期 |

本页只覆盖"能在自己设备上跑起来"的最小闭环；上架与正式分发仍要官方链路。
