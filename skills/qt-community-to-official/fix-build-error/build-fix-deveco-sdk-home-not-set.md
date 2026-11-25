# DEVECO_SDK_HOME not set causes 00303217 Configuration Error

> ID: build-fix-12
> Date: 2026-10-10 (updated based on actual build)
> Files involved: no source changes (environment variable problem)
> Project root: `QtBugDemo-official/`
> Status: Fixed (build passes)

## 1. Error

When the script runs `hvigorw assembleHap`, hvigor fails right in the configuration phase:

```
> hvigor ERROR: 00303217 Configuration Error
Error Message: Invalid value of 'DEVECO_SDK_HOME' in the system environment path.

* Try the following:
  > Correct the value, run hvigorw --stop-daemon to stop the daemon process,
    and then try again.

> hvigor ERROR: BUILD FAILED in 836 ms
```

## 2. Root cause

Command-line `hvigorw` builds need the `DEVECO_SDK_HOME` environment variable to point to the DevEco SDK root directory.
**DevEco Studio sets this variable internally**, but command-line scripts don't inherit it — if the user's
shell environment doesn't set it, hvigor reports `00303217 Configuration Error`.

| Environment | DEVECO_SDK_HOME | Result |
|-------------|-----------------|--------|
| DevEco Studio | Set automatically by the IDE | Reaches CMake normally → shows the CMake error |
| Command-line script | Not set | `00303217` configuration error, **the build never reaches CMake** |

Likewise, `JAVA_HOME` must be set too (hvigor packaging depends on Java; DevEco ships its own JBR).

### The correct DEVECO_SDK_HOME value

```
# macOS — point to the parent directory that contains the default/ subdirectory
DEVECO_SDK_HOME=/Applications/DevEco-Studio.app/Contents/sdk

# ❌ Wrong: points to default/ itself (one level too deep)
# DEVECO_SDK_HOME=/Applications/DevEco-Studio.app/Contents/sdk/default
```

## 3. Fix

### 3.1 Automatic fix in the script (implemented)

The `_setup_build_env()` function in `migrate.py` detects and sets the environment variables automatically:

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

Every hvigorw build call uses this environment through `run_build()`.

### 3.2 Manual setup (persist in ~/.zshrc)

```bash
export DEVECO_SDK_HOME=/Applications/DevEco-Studio.app/Contents/sdk
export JAVA_HOME=/Applications/DevEco-Studio.app/Contents/jbr/Contents/Home
export PATH="$JAVA_HOME/bin:$PATH"
```

## 4. Verification

With the environment variables set, the hvigor configuration passes and the build reaches the CMake phase (subsequent CMake errors
are handled by build-fix-04).

## 5. Troubleshooting

`00303217 Configuration Error` can have several causes; check them in order:

1. **DEVECO_SDK_HOME** (this document): the variable is not set or points to the wrong level
2. **oh-package.json5** (build-fix-09): the `types/libentry` reference does not exist
3. **compatibleSdkVersion** (build-fix-08): the version number does not match the local SDK

The `Error Message:` line in the full build output names the specific cause.
