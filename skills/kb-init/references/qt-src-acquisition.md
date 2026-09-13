# Detailed guide to obtaining the Qt source

## Scenario A: You have a Qt commercial license

### Prerequisites

1. You hold a valid Qt commercial license
2. You can access https://codereview.qt-project.org
3. You have generated HTTP credentials on that site (Settings → HTTP Credentials → GENERATE NEW PASSWORD)

### Steps

```bash
# Clone (you'll be prompted for a username and password — use the credentials generated on codereview.qt-project.org)
git clone https://codereview.qt-project.org/qt/tqtc-qt5 <target-path>

cd <target-path>

# Switch to the 5.12 branch
git checkout tqtc/harmonyos-5.12.12

# Or switch to the 5.15 branch
git checkout tqtc/harmonyos-5.15.16

# Initialize submodules (required — QtOhosExtras lives in a submodule)
git submodule update --init --recursive
```

### Available branches

| Version | Branch name | Notes |
|---------|-------------|-------|
| Qt 5.12.12 | `tqtc/harmonyos-5.12.12` | LTS release, for maintaining older projects |
| Qt 5.15.16 | `tqtc/harmonyos-5.15.16` | Recommended, use this for new projects |

### Notes

- The clone may take a while (the Qt source is around 3 GB)
- `git submodule update --init --recursive` is also mandatory — otherwise the QtOhosExtras module will be missing
- If the clone fails, check that your HTTP credentials are correct and that your network can reach codereview.qt-project.org

---

## Scenario B: No license (open source)

### Prerequisites

1. git is installed with user.name and user.email configured
2. Your network can reach https://gitcode.com

### Steps

```bash
git clone https://gitcode.com/ohos-qt/qt-harmonyos-src <target-path>
cd <target-path>
```

### Available versions

| Version | Notes |
|---------|-------|
| qt-harmonyos-src-5.12.12-20260625 | Currently the only open-source version |

### Notes

- The open-source release only has Qt 5.12.12 — there is no 5.15
- If you need Qt 5.15, you must have a commercial license (scenario A)

---

## Scenario C: You only need the prebuilt SDK

### When this applies

You don't need to modify the Qt framework itself; you just want to build your Qt application against a prebuilt Qt SDK. This is the fastest way to get started.

### Steps

1. Visit the releases page: https://gitcode.com/ohos-qt/qt-harmonyos-src/releases
2. Find the SDK package matching your platform
3. Download it and extract it into a directory of your choice

### Available SDKs

| Platform | Rendering backend | Notes |
|----------|-------------------|-------|
| Windows | Desktop GL | Windows development, Desktop GL rendering |
| Windows | GLES | Windows development, GLES rendering |
| macOS | Desktop GL | macOS development, Desktop GL rendering |
| macOS | GLES | macOS development, GLES rendering |
| HarmonyOS | GLES | Runs on HarmonyOS devices, GLES rendering |

### Choosing a rendering backend

- **Desktop GL**: used for most desktop development; good performance
- **GLES**: use when you need rendering behavior to match HarmonyOS devices (for debugging rendering problems)

### Notes

- The directory you extract the prebuilt SDK into *is* the value for `CMAKE_PREFIX_PATH`
- The SDK already contains the Qt libraries, headers, and CMake configuration — no extra compilation needed
