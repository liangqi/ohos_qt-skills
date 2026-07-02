---
id: semantic-qt-harmonyos-platform-limits
type: semantic
domain: tech
tags: [qt, harmonyos, platform-limits, chmod, symlink, dlopen, timezone, font, xcomponent]
created: 2026-06-02
updated: 2026-06-16
status: active
audience: public
refs: [semantic-qt-harmonyos-overview, semantic-qt-harmonyos-api]
summary: >
  鸿蒙平台限制汇总：chmod/setPermissions 不可用、symlink 禁止第三方使用、
  stat() 系统路径 EACCES、dlopen() 拒绝可写路径、无 tzdata（时区用 ICU）、
  无等宽字体（需自带）、XComponent（SURFACE 类型）在 API 20 弃用、
  MUSL 不能加载 stripped ELF。每条含华为确认状态和 QTBUG 编号。
---

# 鸿蒙平台限制

> 来源：[HarmonyOS Platform Limitations](https://wiki.qt.io/Qt_for_HarmonyOS/platform_limitations)
> 父 issue：[QTBUG-146618](https://bugreports.qt.io/issues/?jql=project%20%3D%20QTBUG%20AND%20parent%20%3D%20QTBUG-146618)

## 文件系统与权限

### chmod() / QFile::setPermissions() 不可用
- **状态**：华为已确认
- **原因**：安全审查取消此接口，无替代
- **影响**：`QFile::setPermissions()` 对已有文件始终返回 false
- **注意**：对新创建的文件描述符（如 `QFile::copy()` 内部用 `fchmod()`）不受影响
- **QTBUG**：[QTBUG-146619](https://bugreports.qt.io/browse/QTBUG-146619)

### symlink() 不可用于第三方应用
- **状态**：华为已确认
- **错误码**：EACCES (13900012)
- **影响**：`QFile::link()` 和依赖符号链接的功能均失败
- **Workaround**：暂无
- **QTBUG**：[QTBUG-146621](https://bugreports.qt.io/browse/QTBUG-146621)

### stat() 系统路径返回 EACCES
- **状态**：华为未确认
- **表现**：`stat("/bin/sh")` 返回 errno=13
- **影响**：`QFileInfo::isFile()` 对系统可执行文件返回 false（但 `exists()` 和 `isExecutable()` 返回 true）
- **连锁影响**：`QStandardPaths::findExecutable()` 无法定位系统可执行文件
- **QTBUG**：[QTBUG-146625](https://bugreports.qt.io/browse/QTBUG-146625)

### open() 尾随斜杠不报错
- **状态**：华为未确认
- **表现**：`open("qwe//", O_RDWR|O_CREAT|O_CLOEXEC, 0666)` 在 Linux 报 EISDIR，鸿蒙上静默创建文件 `qwe`
- **QTBUG**：[QTBUG-146578](https://bugreports.qt.io/browse/QTBUG-146578)

### fread() 非阻塞管道错误设置 EOF
- **状态**：华为未确认
- **表现**：无数据时 `fread()` 非阻塞管道会错误设置 FILE* 的 EOF 标志
- **QTBUG**：[QTBUG-146579](https://bugreports.qt.io/browse/QTBUG-146579)

## 时区

### 无 tzdata
- **状态**：华为已确认，修复时间未知
- **原因**：系统 musl libc 有 tzdata，但不允许第三方读取
- **Workaround**：使用 **ICU 后端**处理时区
- **QTBUG**：[QTBUG-146717](https://bugreports.qt.io/browse/QTBUG-146717), [QTBUG-146559](https://bugreports.qt.io/browse/QTBUG-146559)

## 线程

### PTHREAD_CANCEL_DISABLE 定义但无实现
- **状态**：华为已确认，修复时间未知
- **Workaround**：`#undef PTHREAD_CANCEL_DISABLE`
- **QTBUG**：[QTBUG-146708](https://bugreports.qt.io/browse/QTBUG-146708)

## 动态链接

### MUSL-LDSO 无法加载 stripped ELF
- **状态**：华为已确认，修复时间未知
- **原因**：链接器内部依赖 `e_shnum` 和 `e_shoff` 字段
- **影响**：去掉 section header 的 .so 无法加载
- **QTBUG**：[QTBUG-146620](https://bugreports.qt.io/browse/QTBUG-146620)

### dlopen() 拒绝可写路径
- **状态**：华为未确认
- **表现**：`/data/storage/el2/` 下所有路径（包括 `QStandardPaths::writableLocation()` 返回的路径）的 `dlopen()` 被拒绝，errno=22 (EINVAL)
- **仅可访问**：`/data/storage/el1/`（运行时只读）
- **QTBUG**：[QTBUG-146624](https://bugreports.qt.io/browse/QTBUG-146624)

## 标准路径

### QStandardPaths 约束
- `standardLocations()` 和 `writableLocation()` 返回相同单路径
- `AppLocalDataLocation` 映射到鸿蒙 `preferencesDir`
- **不支持**（返回空）：`PublicShareLocation`, `TemplatesLocation`, `StateLocation`, `GenericStateLocation`
- `findExecutable()` 因 `stat()` 限制无法工作
- **QTBUG**：[QTBUG-146625](https://bugreports.qt.io/browse/QTBUG-146625)

### 资源目录
- 路径：`<bundleCodeDir>/entry/resources/resfile`
- 当前**无** QStandardPaths 枚举映射此路径
- **QTBUG**：[QTBUG-146626](https://bugreports.qt.io/browse/QTBUG-146626)

## 字体系统

### 无等宽字体
- **状态**：华为已确认
- **影响**：`QFontDatabase::systemFont(FixedFont)` 返回非等宽字体
- **Workaround**：应用需自带等宽字体，用 `QFontDatabase::addApplicationFont()` 注册
- **QTBUG**：[QTBUG-146623](https://bugreports.qt.io/browse/QTBUG-146623)

## ArkUI/ArkTS API

### XComponent（ARKUI_XCOMPONENT_TYPE_SURFACE）在 API 20 弃用
- **状态**：华为已弃用
- **影响**：Qt 使用 ARKUI_XCOMPONENT_TYPE_SURFACE 作为 OpenGL 原生渲染表面
- **迁移方向**：ContentSlot 组件
- **参考**：[ContentSlot 文档](https://developer.huawei.com/consumer/en/doc/harmonyos-guides/arkts-rendering-control-contentslot)
- **QTBUG**：[QTBUG-146622](https://bugreports.qt.io/browse/QTBUG-146622)

## 参考来源

- [HarmonyOS Platform Limitations](https://wiki.qt.io/Qt_for_HarmonyOS/platform_limitations)
- [HarmonyOS MUSL 特殊符号不导出](https://developer.huawei.com/consumer/en/doc/harmonyos-references/musl-peculiar-symbol)
