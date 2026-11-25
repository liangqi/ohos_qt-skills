# EPERM: operation not permitted, uv_cwd — hvigor daemon cwd invalid

> ID: build-fix-10
> Date: 2026-10-10 (updated based on actual build)
> Files involved: no source changes (runtime environment / process state problem)
> Project root: `QtBugDemo-official/`
> Nature: build environment problem (not a code compilation error)
> Outcome: `BUILD SUCCESSFUL`, signed hap produced normally

## 1. Symptom

Running `hvigorw assembleHap`, the build fails within 195 ms, before reaching the compilation phase:

```
> hvigor ERROR: Failed :entry:default@BuildNativeWithCmake...
> hvigor ERROR: Error Code: 00308018 Unknown Error
  EPERM: operation not permitted, uv_cwd

* Try the following:
  > This error is unknown, view the detailed error logs in the
  > '.hvigor > outputs > build-logs' directory ...

> hvigor ERROR: BUILD FAILED in 195 ms
```

Build log path: `.hvigor/outputs/build-logs/build.log`

## 2. Root cause

### 2.1 The error occurs in the worker thread's process.cwd() call

The full stack trace from the build log:

```
[DEBUG] worker[8] encounters error: EPERM: operation not permitted, uv_cwd.
[DEBUG] default@BuildNativeWithCmake work[19] failed.
[ERROR] Failed :entry:default@BuildNativeWithCmake...
[ERROR] stacktrace = Error: EPERM: operation not permitted, uv_cwd
    at process.cwd (node:internal/main/worker_thread:126:21)
    at MessagePort.<anonymous> (node:internal/main/worker_thread:144:50)
```

hvigor runs build tasks in parallel on Node.js **worker threads**. When a worker thread starts,
Node.js internally calls `uv_cwd()` (libuv) to get the current working directory. If that directory is no longer accessible,
the operating system returns `EPERM` (operation not permitted) → the worker thread crashes immediately → the build fails.

### 2.2 The daemon cwd points to a deleted directory or one moved to the Trash

Several hvigor daemons exist on this machine (they stay resident after DevEco Studio starts). Use
`lsof -a -p <pid> -d cwd` to check each daemon's working directory:

| PID | Start time | cwd | Problem |
|-----|------------|-----|---------|
| 33436 | Today 9:40 | `~/.Trash/QtBugDemo-official` | The project directory was moved to the Trash |
| 33435 | Today 9:40 | `~/.Trash/QtBugDemo-official` | Same as above |
| 24068 | Thursday 12:00 | `~/.Trash/QtBugDemo-clone` | Another project, also in the Trash |
| 3584 | Thursday 11:00 | `.../qtbase/src/harmonyos/templates` | Old template directory (no longer exists) |
| 63148 | Thursday 09:00 | `.../qtbase/src/harmonyos/templates` | Same as above |

When these daemons started, their cwd pointed to directories that were later deleted or moved to the Trash.
**macOS applies TCC access restrictions to `~/.Trash`**, so other processes (including hvigor worker threads)
cannot access it → `uv_cwd()` returns `EPERM`.

### 2.3 Daemon reuse causes cross-project contamination

hvigor daemons are designed to be **reused across projects**: when a new build starts, hvigor first looks for an already running
daemon (matched by session ID) and reuses it if found. Therefore:

1. The user once started a build in an old project directory (`QtBugDemo-official`, `QtBugDemo-clone`) →
   a daemon started with that directory as its cwd.
2. The user moved the old project to the Trash (or deleted it).
3. The user rebuilt in a new project directory → hvigor reused the old daemon (cwd still in the Trash) →
   the worker threads inherit the invalid cwd → `EPERM: uv_cwd`.

## 3. Fix

### 3.1 Kill all stale hvigor daemons

```bash
# Kill the Node.js daemons
pkill -f 'daemon-process-boot-script'
# Kill the Java daemons
pkill -f 'hvigor-java-daemon'

# If SIGTERM cannot kill them (the daemon ignores the signal), force-kill with SIGKILL
kill -9 <leftover PID>
```

Verify that all of them are gone:

```bash
ps aux | grep -iE 'hvigor.*daemon|daemon-process-boot' | grep -v grep
# Expected: no output
```

### 3.2 Clear the .hvigor cache

The daemon may have cached references to the invalid working directory; clear the cache to force hvigor to reinitialize:

```bash
rm -rf .hvigor/cache
```

### 3.3 Rebuild

```bash
export DEVECO_SDK_HOME=/Applications/DevEco-Studio.app/Contents/sdk
export JAVA_HOME=/Applications/DevEco-Studio.app/Contents/jbr/Contents/Home
export PATH="$JAVA_HOME/bin:$PATH"

cd <project root directory>
hvigorw assembleHap --mode module -p module=entry@default -p product=default --no-daemon
```

> `--no-daemon` ensures this build reuses no daemon and runs entirely in the current process,
> so the cwd is the current shell's working directory (valid).

## 4. Verification

```
> hvigor Finished :entry:default@BuildNativeWithCmake... after 13 ms   ← no more EPERM
> hvigor Finished :entry:default@BuildNativeWithNinja... after 38 ms
> hvigor Finished :entry:default@CompileArkTS...
> hvigor Finished :entry:default@PackageHap...
> hvigor Finished :entry:default@SignHap...
> hvigor BUILD SUCCESSFUL in 2 s 598 ms
```

The signed hap is produced normally:

```
entry/build/default/outputs/default/entry-default-signed.hap  (276 MB)
```

## 5. One-shot diagnostic script

When you hit `EPERM: operation not permitted, uv_cwd`, run this diagnostic first:

```bash
#!/bin/bash
echo "=== hvigor daemons and their cwd ==="
for pid in $(pgrep -f 'daemon-process-boot-script|hvigor-java-daemon'); do
  cwd=$(lsof -a -p "$pid" -d cwd 2>/dev/null | tail -1 | awk '{for(i=NF;i>=1;i--) if($i ~ /^\//) {print $i; exit}}')
  start=$(ps -p "$pid" -o lstart= 2>/dev/null | sed 's/^ *//')
  status="OK"
  [ -d "$cwd" ] || status="INVALID (cwd directory does not exist)"
  case "$cwd" in *Trash*) status="INVALID (cwd is in the Trash)" ;; esac
  echo "  PID $pid  started: $start  cwd: ${cwd:-?}  → $status"
done

echo ""
echo "=== Fix ==="
echo "1. pkill -f 'daemon-process-boot-script' && pkill -f 'hvigor-java-daemon'"
echo "2. kill -9 <leftover PID>  (if SIGTERM has no effect)"
echo "3. rm -rf .hvigor/cache"
echo "4. hvigorw assembleHap --no-daemon"
```

## 6. Prevention

| Scenario | Prevention |
|----------|------------|
| Moving/deleting a project directory | Close the project in DevEco Studio first (stops the daemons) |
| Switching projects | Run `pkill -f hvigor` after switching to clean up old daemons |
| Periodic cleanup | Add `alias hvigor-clean='pkill -f "daemon-process-boot-script" 2>/dev/null; pkill -f "hvigor-java-daemon" 2>/dev/null; rm -rf .hvigor/cache'` to `.zshrc` |
| CI / scripted builds | Always use `--no-daemon` to avoid reusing daemons |

## 7. Alternatives (not adopted)

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| Only clear `.hvigor/cache` | Small change | The daemon stays alive and fails again on the next reuse | ✗ Doesn't fix the root cause |
| Restart macOS | Fixes it for good | Too costly, disrupts other work | ✗ Overkill |
| Grant the terminal Full Disk Access | Can access `~/.Trash` | Treats the symptom only; a Trash directory should not be a cwd anyway | ✗ Wrong direction |
| **Kill daemons + clear cache + --no-daemon** | Precise, immediate, does not affect other processes | Must be run manually (can be scripted) | ✓ Adopted |
