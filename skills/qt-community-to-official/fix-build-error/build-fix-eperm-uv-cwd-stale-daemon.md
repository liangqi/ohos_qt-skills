# EPERM: operation not permitted, uv_cwd —— hvigor 守护进程 cwd 失效

> 编号：build-fix-10
> 日期：2026-10-10（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）（基于实测构建更新）
> 涉及文件：无源码改动（运行环境 / 进程状态问题）
> 工程根：`QtBugDemo-official/`
> 性质：构建环境问题（非代码编译错误）
> 结果：`BUILD SUCCESSFUL`，签名 hap 正常产出

## 1. 现象

执行 `hvigorw assembleHap`，构建在 195 ms 内即失败，未进入编译阶段：

```
> hvigor ERROR: Failed :entry:default@BuildNativeWithCmake...
> hvigor ERROR: Error Code: 00308018 Unknown Error
  EPERM: operation not permitted, uv_cwd

* Try the following:
  > This error is unknown, view the detailed error logs in the
  > '.hvigor > outputs > build-logs' directory ...

> hvigor ERROR: BUILD FAILED in 195 ms
```

构建日志路径：`.hvigor/outputs/build-logs/build.log`

## 2. 根因

### 2.1 错误发生在 worker 线程的 process.cwd() 调用

构建日志的完整堆栈：

```
[DEBUG] worker[8] encounters error: EPERM: operation not permitted, uv_cwd.
[DEBUG] default@BuildNativeWithCmake work[19] failed.
[ERROR] Failed :entry:default@BuildNativeWithCmake...
[ERROR] stacktrace = Error: EPERM: operation not permitted, uv_cwd
    at process.cwd (node:internal/main/worker_thread:126:21)
    at MessagePort.<anonymous> (node:internal/main/worker_thread:144:50)
```

hvigor 用 Node.js **worker 线程**并行执行构建任务。worker 线程启动时，
Node.js 内部会调用 `uv_cwd()`（libuv）获取当前工作目录。若该目录已不可访问，
操作系统返回 `EPERM`（操作不允许）→ worker 线程立即崩溃 → 构建失败。

### 2.2 守护进程 cwd 指向已删除/移入废纸篓的目录

本机存在多个 hvigor 守护进程（DevEco Studio 启动后常驻）。用
`lsof -a -p <pid> -d cwd` 检查各守护进程的工作目录：

| PID | 启动时间 | cwd | 问题 |
|-----|---------|-----|------|
| 33436 | 今天 9:40 | `~/.Trash/QtBugDemo-official` | 项目目录已被移入废纸篓 |
| 33435 | 今天 9:40 | `~/.Trash/QtBugDemo-official` | 同上 |
| 24068 | 周四 12:00 | `~/.Trash/QtBugDemo-clone` | 另一工程也在废纸篓 |
| 3584 | 周四 11:00 | `.../qtbase/src/harmonyos/templates` | 旧模板目录（已不在） |
| 63148 | 周四 09:00 | `.../qtbase/src/harmonyos/templates` | 同上 |

这些守护进程在启动时，cwd 指向的目录此后被删除/移动到废纸篓。
**macOS 对 `~/.Trash` 有 TCC 访问限制**，其他进程（含 hvigor worker 线程）
无法访问 → `uv_cwd()` 返回 `EPERM`。

### 2.3 守护进程复用机制导致跨工程污染

hvigor 守护进程设计为**跨工程复用**：新构建启动时，hvigor 优先查找已运行的
守护进程（按 session ID 匹配），找到就复用。因此：

1. 用户曾在旧工程目录（`QtBugDemo-official`、`QtBugDemo-clone`）中启动构建 →
   守护进程以该目录为 cwd 启动。
2. 用户将旧工程移入废纸篓（或删除）。
3. 用户在新工程目录重新构建 → hvigor 复用了旧的守护进程（cwd 仍在废纸篓）→
   worker 线程继承失效 cwd → `EPERM: uv_cwd`。

## 3. 修复

### 3.1 终止所有失效的 hvigor 守护进程

```bash
# 终止 Node.js 守护进程
pkill -f 'daemon-process-boot-script'
# 终止 Java 守护进程
pkill -f 'hvigor-java-daemon'

# 若 SIGTERM 无法终止（守护进程忽略信号），用 SIGKILL 强制终止
kill -9 <残留 PID>
```

验证全部终止：

```bash
ps aux | grep -iE 'hvigor.*daemon|daemon-process-boot' | grep -v grep
# 预期：无输出
```

### 3.2 清理 .hvigor 缓存

守护进程可能缓存了失效的工作目录引用，清理缓存强制 hvigor 重新初始化：

```bash
rm -rf .hvigor/cache
```

### 3.3 重新构建

```bash
export DEVECO_SDK_HOME=/Applications/DevEco-Studio.app/Contents/sdk
export JAVA_HOME=/Applications/DevEco-Studio.app/Contents/jbr/Contents/Home
export PATH="$JAVA_HOME/bin:$PATH"

cd <工程根目录>
hvigorw assembleHap --mode module -p module=entry@default -p product=default --no-daemon
```

> `--no-daemon` 确保本次构建不复用任何守护进程，全部在当前进程内执行，
> cwd 即为当前 shell 的工作目录（有效）。

## 4. 验证

```
> hvigor Finished :entry:default@BuildNativeWithCmake... after 13 ms   ← 不再 EPERM
> hvigor Finished :entry:default@BuildNativeWithNinja... after 38 ms
> hvigor Finished :entry:default@CompileArkTS...
> hvigor Finished :entry:default@PackageHap...
> hvigor Finished :entry:default@SignHap...
> hvigor BUILD SUCCESSFUL in 2 s 598 ms
```

签名 hap 正常产出：

```
entry/build/default/outputs/default/entry-default-signed.hap  (276 MB)
```

## 5. 一键诊断脚本

遇到 `EPERM: operation not permitted, uv_cwd` 时，先运行此诊断：

```bash
#!/bin/bash
echo "=== hvigor 守护进程及其 cwd ==="
for pid in $(pgrep -f 'daemon-process-boot-script|hvigor-java-daemon'); do
  cwd=$(lsof -a -p "$pid" -d cwd 2>/dev/null | tail -1 | awk '{for(i=NF;i>=1;i--) if($i ~ /^\//) {print $i; exit}}')
  start=$(ps -p "$pid" -o lstart= 2>/dev/null | sed 's/^ *//')
  status="OK"
  [ -d "$cwd" ] || status="INVALID (cwd 目录不存在)"
  case "$cwd" in *Trash*) status="INVALID (cwd 在废纸篓)" ;; esac
  echo "  PID $pid  启动: $start  cwd: ${cwd:-?}  → $status"
done

echo ""
echo "=== 修复 ==="
echo "1. pkill -f 'daemon-process-boot-script' && pkill -f 'hvigor-java-daemon'"
echo "2. kill -9 <残留 PID>  (若 SIGTERM 无效)"
echo "3. rm -rf .hvigor/cache"
echo "4. hvigorw assembleHap --no-daemon"
```

## 6. 预防

| 场景 | 预防措施 |
|------|---------|
| 移动/删除工程目录 | 移动前先在 DevEco Studio 关闭工程（停止守护进程） |
| 切换工程 | 切换后执行 `pkill -f hvigor` 清理旧守护进程 |
| 定期清理 | 在 `.zshrc` 中加 `alias hvigor-clean='pkill -f "daemon-process-boot-script" 2>/dev/null; pkill -f "hvigor-java-daemon" 2>/dev/null; rm -rf .hvigor/cache'` |
| CI / 脚本构建 | 始终用 `--no-daemon` 避免复用守护进程 |

## 7. 备选方案（未采用）

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| 仅清理 `.hvigor/cache` | 改动小 | 守护进程仍存活，下次复用仍报错 | ✗ 不治本 |
| 重启 macOS | 一劳永逸 | 代价过大，影响其他工作 | ✗ 过度 |
| 授予终端 Full Disk Access | 可访问 `~/.Trash` | 治标不治本；废纸篓目录本身也不该作为 cwd | ✗ 方向错误 |
| **终止守护进程 + 清缓存 + --no-daemon** | 精准、即时、不影响其他进程 | 需手动执行（可脚本化） | ✓ 采用 |
