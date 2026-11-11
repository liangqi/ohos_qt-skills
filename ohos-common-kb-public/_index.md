---
updated: 2026-11-11
total_pages: 27
description: >
  内嵌 HarmonyOS 平台通用知识库的索引入口（ArkTS/ArkUI/NAPI/Stage/工具链）。
  这些页来自上游公共库，按领域列出；Qt 侧知识见 ../_index/_map.md。
---

# 内嵌平台知识索引（ohos-common-kb-public）

> Qt 侧的迁移知识在 [`_index/_map.md`](../_index/_map.md)；这里只收平台通用事实。
> 目录保持与上游一致（semantic / procedural / problems），便于同步时逐文件比对。

## 语义：平台模型与规格

- [`application-sandbox-paths`](semantic/application-sandbox-paths.md) — 区分 bundle 与数据路径、应用与 hdc shell mount namespace，并约束写入、chmod、dlopen 和 execve。
- [`arkui-window-xcomponent-model`](semantic/arkui-window-xcomponent-model.md) — 区分 WindowStage/main/subwindow、XComponent 节点、native surface、焦点/可见/可绘制状态及新旧 API seam。
- [`deveco-mcp-capabilities`](semantic/deveco-mcp-capabilities.md) — deveco-mcp 的安装、客户端配置、check/restart 能力和边界；构建、运行、UI 与日志操作由 devecocli 或明确的底层诊断承担。
- [`document-picker-uri-access`](semantic/document-picker-uri-access.md) — Picker 返回的是带授权语义的 URI；URI、转换后的 path、临时/持久读写授权必须分别处理。
- [`hap-application-identity`](semantic/hap-application-identity.md) — bundleName 的平台身份作用、语法/唯一性检查及其与 profile、安装和框架生成配置的关系。
- [`hap-native-project-structure`](semantic/hap-native-project-structure.md) — AppScope、module.json5、build-profile、native libs、product 与 signingConfig 的平台关系。
- [`harmonyos-development-fundamentals`](semantic/harmonyos-development-fundamentals.md) — HarmonyOS 应用开发的中立入口：区分 HarmonyOS 与 OpenHarmony，说明 Stage、ArkTS、ArkUI、Node-API 和 DevEco/hdc 的职责边界。
- [`harmonyos-platform-limits`](semantic/harmonyos-platform-limits.md) — 跨框架验证的平台限制入口：bundle 写入/权限、动态代码加载、MUSL/SDK 与高权限能力边界。
- [`native-runtime-embedding`](semantic/native-runtime-embedding.md) — hap-bin、进程内 SO 与 HNP 三种运行时集成模型及路径、签名、JIT 和验证契约。
- [`ohos-cross-compile-pitfalls`](semantic/ohos-cross-compile-pitfalls.md) — OHOS target cfg、c_char 符号性、系统权限签名和 fresh-clone 是跨框架移植的四类高频陷阱。
- [`ohos-native-third-party-libraries`](semantic/ohos-native-third-party-libraries.md) — OHOS NDK 三方库的 toolchain/sysroot、ABI、产物校验、HAP 部署与动态加载平台契约。
- [`privileged-system-capabilities`](semantic/privileged-system-capabilities.md) — API 可见、manifest 权限、profile ACL、应用类型和产品类型共同决定特权能力；普通应用必须设计降级。
- [`stage-uiability-lifecycle`](semantic/stage-uiability-lifecycle.md) — Stage/UIAbility 的创建、WindowStage、Want 路由、launchType、skills 与保存恢复平台语义。
- [`system-information-access-limits`](semantic/system-information-access-limits.md) — 普通应用不能假定 Linux procfs 全量可读；按指标使用平台 API，并区分不支持、权限拒绝与真实零值。

## 程序：工具链与交叉编译

- [`cpython-dynamic-embedding-ohos`](procedural/cpython-dynamic-embedding-ohos.md) — 以 libpython + C API 在 HarmonyOS 进程内嵌入 CPython，部署 stdlib/依赖并验证初始化、线程与路径。
- [`deveco-cli-usage-rules`](procedural/deveco-cli-usage-rules.md) — devecocli 优先入口、底层 DevEco CLI 能力边界与 headless 诊断；封装未覆盖或诊断封装本身时允许可审计的最小底层调用。
- [`ohos-gstreamer-cross-compile`](procedural/ohos-gstreamer-cross-compile.md) — 面向 OHOS 的 GStreamer core/plugin 交叉编译、feature 裁剪、依赖部署与最小 pipeline 验证。
- [`ohos-llvm-cross-compile`](procedural/ohos-llvm-cross-compile.md) — 用 OHOS NDK toolchain 构建 LLVM 类 CMake 原生工程，并验证 target artifact 与依赖闭包。

## 问题：平台侧踩坑与解法

- [`dlopen-rejects-writable-path`](problems/dlopen-rejects-writable-path.md) — 应用从普通可写 data/cache 路径 dlopen 代码被 loader/安全策略拒绝；随 HAP 合规打包并检查依赖闭包。
- [`document-picker-uri-access-failure`](problems/document-picker-uri-access-failure.md) — Picker URI 被当普通 path，或转换 path 后缺少所需 read/write grant，导致 not found/permission denied。
- [`executable-binary-eacces`](problems/executable-binary-eacces.md) — HAP 内 ELF bin 因未声明 executableBinaryPaths、签名/permission/profile 不完整或路径视角错误而 execve EACCES。
- [`executable-memory-permission-denied`](problems/executable-memory-permission-denied.md) — V8/HotSpot 等 JIT 因 writable executable memory 权限或 profile ACL 不成立而 ENOMEM/SIGABRT；声明权限并验证签名授权。
- [`hap-device-sdk-version-mismatch`](problems/hap-device-sdk-version-mismatch.md) — 设备 API 低于 HAP compatibleSdkVersion 时安装返回 9568297/older sdk version；按真实最低能力选择兼容版本。
- [`ohpm-install-timeout`](problems/ohpm-install-timeout.md) — ohpm install 长时间无响应或超时通常是 registry、代理或网络可达性问题；先诊断当前配置，再切换到组织批准且可达的 registry。
- [`procfs-system-information-unavailable`](problems/procfs-system-information-unavailable.md) — 库选择 Linux backend 后读取 /proc/stat、mounts 或 diskstats 被拒，CPU/disk 等返回空或 0。
- [`programmatic-hotspot-unavailable`](problems/programmatic-hotspot-unavailable.md) — enableHotspot 已废弃且限定非通用产品，普通应用的自动建热点功能需降级或改用受支持网络模式。
- [`runtime-write-to-readonly-bundle-path`](problems/runtime-write-to-readonly-bundle-path.md) — 应用把数据库、缓存、配置或生成文件写到随包资源/安装目录而 EACCES/EROFS；复制到平台可写数据目录。
