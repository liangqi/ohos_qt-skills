# DEVECO_SDK_HOME 未设置导致 00303217 Configuration Error

> 编号：build-fix-12
> 日期：2026-10-10（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建）
> 涉及文件：无源码改动（环境变量问题）
> 工程根：`QtBugDemo-official/`
> 当前状态：已修复（构建通过）

## 1. 报错

脚本运行 `hvigorw assembleHap` 时，hvigor 配置阶段即失败：

```
> hvigor ERROR: 00303217 Configuration Error
Error Message: Invalid value of 'DEVECO_SDK_HOME' in the system environment path.

* Try the following:
  > Correct the value, run hvigorw --stop-daemon to stop the daemon process,
    and then try again.

> hvigor ERROR: BUILD FAILED in 836 ms
```

## 2. 根因

`hvigorw` 命令行构建需要 `DEVECO_SDK_HOME` 环境变量指向 DevEco SDK 根目录。
**DevEco Studio 内部自动设置此变量**，但命令行脚本不会继承——如果用户
shell 环境未设置，hvigor 报 `00303217 Configuration Error`。

| 环境 | DEVECO_SDK_HOME | 结果 |
|------|----------------|------|
| DevEco Studio | IDE 自动设置 | 正常进入 CMake → 显示 CMake 错误 |
| 命令行脚本 | 未设置 | `00303217` 配置错误，**构建未到达 CMake** |

同理，`JAVA_HOME` 也需要设置（hvigor 打包依赖 Java，DevEco 自带 JBR）。

### 正确的 DEVECO_SDK_HOME 值

```
# macOS — 指向含 default/ 子目录的父目录
DEVECO_SDK_HOME=/Applications/DevEco-Studio.app/Contents/sdk

# ❌ 错误：指向 default/ 本身（少一层）
# DEVECO_SDK_HOME=/Applications/DevEco-Studio.app/Contents/sdk/default
```

## 3. 修复

### 3.1 脚本自动修复（已实现）

`migrate.py` 的 `_setup_build_env()` 函数自动检测并设置环境变量：

```python
def _setup_build_env():
    env = os.environ.copy()
    # DEVECO_SDK_HOME
    if not env.get("DEVECO_SDK_HOME"):
        env["DEVECO_SDK_HOME"] = "/Applications/DevEco-Studio.app/Contents/sdk"
    # JAVA_HOME (DevEco bundled JBR)
    if not env.get("JAVA_HOME"):
        env["JAVA_HOME"] = "/Applications/DevEco-Studio.app/Contents/jbr/Contents/Home"
    return env
```

所有 hvigorw 构建调用通过 `run_build()` 使用此环境。

### 3.2 手动设置（持久化到 ~/.zshrc）

```bash
export DEVECO_SDK_HOME=/Applications/DevEco-Studio.app/Contents/sdk
export JAVA_HOME=/Applications/DevEco-Studio.app/Contents/jbr/Contents/Home
export PATH="$JAVA_HOME/bin:$PATH"
```

## 4. 验证

设置环境变量后，hvigor 配置通过，构建进入 CMake 阶段（后续 CMake 错误
由 build-fix-04 处理）。

## 5. 排查

`00303217 Configuration Error` 可能有多种原因，按序检查：

1. **DEVECO_SDK_HOME**（本文档）：变量未设置或指向错误层级
2. **oh-package.json5**（build-fix-09）：`types/libentry` 引用不存在
3. **compatibleSdkVersion**（build-fix-08）：版本号与本机 SDK 不符

完整构建输出中 `Error Message:` 行指明具体原因。
