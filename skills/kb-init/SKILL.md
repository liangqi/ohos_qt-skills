---
name: kb-init
description: |
  Environment initialization for the Qt for HarmonyOS knowledge base. Detects whether the user is running inside the ohos_qt-skills
  knowledge base and helps download it if not. Then fully configures DevEco Studio, the HarmonyOS SDK, the Qt SDK/source,
  and the build toolchain, generates ENV.local.md, and verifies the environment is ready.
  This skill must be triggered when the user says "initialize", "configure the environment", "first time using this", "setup", or "install",
  or when ENV.local.md doesn't exist.
  Even if the user doesn't explicitly say "initialize", you should proactively suggest running it on their first interaction with the knowledge base.
---

# kb-init: one-shot setup of the Qt for HarmonyOS development environment

This skill walks you through all the environment configuration Qt for HarmonyOS development requires. The process has two phases:

1. **Gathering decisions** (Phase 1): the agent asks you questions one at a time; once you've answered, you're done
2. **Automated execution** (Phase 2): the scripts install, download, and configure everything, then verify the environment is ready

> Design principle: anything a script can do deterministically should never be left to the agent's improvisation. The agent only asks you questions and invokes the scripts.

---

## Phase 0: confirm the knowledge base location

Before any configuration, confirm whether the user is inside the `ohos_qt-skills` knowledge base directory.

Run the detection:
```bash
bash skills/kb-init/scripts/detect-env.sh
```

Check the `KB_ROOT` and `KB_FOUND` fields in the output:

- If `KB_FOUND=true`: the user is already in the knowledge base; record the `KB_ROOT` value and move to Phase 1
- If `KB_FOUND=false`: the user isn't in the knowledge base and it needs downloading first

### Downloading the knowledge base

If `KB_FOUND=false`, ask the user:

> You haven't downloaded the Qt for HarmonyOS knowledge base yet. Which directory would you like it in?
> For example: `D:\dev` or `/Users/yourname/dev`
>
> The script will create an `ohos_qt-skills/` directory inside it.

Record the directory the user specifies as `KB_PARENT_DIR`, then run:

```bash
bash skills/kb-init/scripts/clone-kb.sh --dest=<KB_PARENT_DIR>
```

The script clones `https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills.git` into `<KB_PARENT_DIR>/ohos_qt-skills/`.

Afterwards, change the working directory to `<KB_PARENT_DIR>/ohos_qt-skills/` and re-run `detect-env.sh` to confirm `KB_FOUND=true`.

> Note: if the user invokes this skill from outside the knowledge base (from another AI tool, for example), the agent must clone the knowledge base for them first and then continue the remaining steps inside that directory.

---

## Phase 1: gather the user's decisions

Ask the following questions **one at a time**, in order. Wait for an answer before asking the next one. Don't list them all at once.

### Q1: which Qt version does your application need?

> Which version does your Qt application need?
> 1. **Qt 5.15** — recommended, for new projects
> 2. **Qt 5.12** — for maintaining older projects
> 3. **Not sure** — Qt 5.15 is recommended

Record this as `QT_VERSION` (`5.15` / `5.12`).

### Q2: how to obtain Qt

Branch based on the version from Q1:

**If Q1 = 5.15**:

> The HarmonyOS build of Qt 5.15 is only available with a commercial license. Do you have a Qt commercial license?
> 1. **Yes** — I'll download the source from Qt and build the SDK for you
> 2. **No** — Qt 5.15 requires a commercial license; please contact Qt sales. Alternatively, you can choose Qt 5.12 (which has an open-source release)

If the user chooses "No", go back to Q1 and let them pick a different version.

**If Q1 = 5.12**:

> Do you have a Qt commercial license?
> 1. **Yes** — download the source from Qt and build the SDK (5.12 or 5.15)
> 2. **No** — download the open-source release from GitCode (currently only qt-harmonyos-src-5.12.12-20260625)

Record this as `QT_SOURCE_METHOD` (`commercial` / `opensource`).

### Q3: build/download options

**If QT_SOURCE_METHOD = commercial**:

You'll need to build the SDK, so ask about the build options:

> Building the Qt SDK requires a few choices:
>
> **Rendering backend**:
> 1. **Desktop GL** — most desktop development scenarios; good performance
> 2. **GLES** — when you need rendering behavior to match HarmonyOS devices (for debugging rendering problems)
>
> **Build type**:
> 1. **Release** — the optimized build, for normal development
> 2. **Debug** — with debug information, for investigating Qt framework problems

Record these as `RENDER_BACKEND` (`gl` / `gles`) and `BUILD_TYPE` (`release` / `debug`).

**If QT_SOURCE_METHOD = opensource**:

> The open-source release currently only has **qt-harmonyos-src-5.12.12-20260625**.
>
> What do you need?
> 1. **Both the source and the prebuilt SDK** — so you can read the source and develop against the SDK
> 2. **Only the prebuilt SDK** — the fastest way to get started; no source needed

Record this as `OPENSOURCE_DOWNLOAD` (`both` / `sdk-only`).

### Q4: DevEco Studio status

> Have you installed DevEco Studio?
> 1. **Installed** — please tell me the installation path (for example macOS: `/Applications/DevEco-Studio.app`, Windows: `C:\Program Files\Huawei\DevEco Studio`)
> 2. **Not installed** — I'll walk you through installing it

Record these as `DEVECO_STATUS` (`installed` / `not-installed`) and `DEVECO_PATH` (if installed).

### Q5: git configuration

> Is your git configured with a user name and email? (Cloning code requires it.)

Have the agent run the following to check:
```bash
git config --global user.name
git config --global user.email
```

If they're empty, ask for the user's name and email, then run:
```bash
git config --global user.name "the user's name"
git config --global user.email "the user's email"
```

### Q6: account verification for the commercial scenario

If QT_SOURCE_METHOD = commercial:

> Please confirm you can access https://codereview.qt-project.org.
> 1. Open that URL in your browser
> 2. Sign in with your Qt account
> 3. Go to Settings → HTTP Credentials → GENERATE NEW PASSWORD
> 4. Note down the generated **username** and **password** (you'll need them to clone)
>
> Let me know when you're done.

Wait for the user to confirm before continuing. Record the `QT_USER` and `QT_PASS` they provide.

---

## Phase 2: automated execution

Once Phase 1 is complete, the agent has all the information it needs. All the paths below are under the `workspace/` subdirectory of the knowledge base root (`KB_ROOT`).

### Step 1: environment detection

```bash
bash skills/kb-init/scripts/detect-env.sh
```

Parse the output and give the user a brief summary of the current environment.

### Step 2: install DevEco Studio (if it isn't installed)

If the answer to Q4 was "not installed", read `references/deveco-install.md` and walk the user through installing it for their OS.

Once installed, re-run `detect-env.sh` to confirm `DEVECO_FOUND=true`.

**DevEco CLI (devecocli)**:
- macOS/Windows: DevEco Studio ships `devecocli` at `<DEVECO_PATH>/tools/devecocli`
- Linux: the Command Line Tools must be downloaded separately — see the Linux section of `references/deveco-install.md`

Have the agent check whether `devecocli` is available:
```bash
command -v devecocli || ls <DEVECO_PATH>/tools/devecocli 2>/dev/null
```

If it isn't, guide the user to add it to PATH or get it from the DevEco download page.

### Step 3: platform dependency check

Run the script matching the OS:

**macOS**:
```bash
bash skills/kb-init/scripts/install-deps-macos.sh
```

**Windows** (run it in Git Bash):
```bash
bash skills/kb-init/scripts/install-deps-linux.sh
```

**Linux**:
```bash
bash skills/kb-init/scripts/install-deps-linux.sh
```

**HarmonyOS** (a HarmonyOS PC / dev board / container):
```bash
bash skills/kb-init/scripts/install-deps-harmonyos.sh
```

> **A note on the HarmonyOS platform**: HarmonyOS uses [HarmonyBrew](https://gitcode.com/Harmonybrew) as its package manager (a HarmonyOS port of Homebrew). If HarmonyBrew isn't installed, the script prints the install command: `zsh -c "$(curl -fsSL https://harmonybrew.atomgit.com/install.sh)"`. Dependencies such as git and cmake can then be installed with `brew install`.

The scripts check dependencies such as git, curl, cmake, Node.js, the JDK, hdc, and the DevEco CLI. If anything FAILs, the agent should help the user fix it and re-run.

> **cmake is mandatory**: the knowledge base references cmake 189 times; it's the core tool for building Qt and your projects. If the cmake check fails, it must be installed first.

### Step 4: obtain the Qt source/SDK

Everything is installed under `KB_ROOT/workspace/`.

**Scenario A: commercial (source needed + build the SDK)**

```bash
bash skills/kb-init/scripts/clone-qt-src.sh \
  --method=commercial \
  --version=<QT_VERSION> \
  --user=<QT_USER> \
  --pass=<QT_PASS> \
  --dest=<KB_ROOT>/workspace/qt-src
```

Once the clone finishes, build the SDK:

```bash
bash skills/kb-init/scripts/compile-qt-sdk.sh \
  --src=<KB_ROOT>/workspace/qt-src/qt<VERSION> \
  --dest=<KB_ROOT>/workspace/qt-sdk \
  --render=<RENDER_BACKEND> \
  --build-type=<BUILD_TYPE> \
  --ohos-sdk-native=<OHOS_SDK_NATIVE_PATH>
```

The script prints `QT<VERSION>_OHOS_SDK=<path>`.

> **Security note**: in the commercial scenario, after cloning finishes, it's a good idea to strip the credentials from the git remote URL:
> ```bash
> cd <KB_ROOT>/workspace/qt-src/qt<VERSION>
> git remote set-url origin https://codereview.qt-project.org/qt/tqtc-qt5
> ```

> **The detailed build guide**: if you hit build problems or need to build manually, see `references/qt-compile-guide.md`, which contains the full build steps, option descriptions, and troubleshooting.

**Scenario B: opensource, both (source + SDK)**

```bash
bash skills/kb-init/scripts/clone-qt-src.sh \
  --method=opensource \
  --version=5.12 \
  --dest=<KB_ROOT>/workspace/qt-src
```

Then download the prebuilt SDK:

```bash
bash skills/kb-init/scripts/download-qt-sdk.sh \
  --platform=<OS> \
  --dest=<KB_ROOT>/workspace/qt-sdk
```

**Scenario C: opensource, sdk-only (the SDK only)**

```bash
bash skills/kb-init/scripts/download-qt-sdk.sh \
  --platform=<OS> \
  --dest=<KB_ROOT>/workspace/qt-sdk
```

### Step 5: generate ENV.local.md

```bash
bash skills/kb-init/scripts/generate-env-local.sh \
  --deveco-path="<DEVECO_PATH>" \
  --qt5-12-src="<KB_ROOT>/workspace/qt-src/qt5.12" \
  --qt5-15-src="<KB_ROOT>/workspace/qt-src/qt5.15" \
  --qt-build-root="<KB_ROOT>/workspace/qt-build" \
  --qt5-12-ohos-sdk="<SDK_PATH>" \
  --qt5-15-ohos-sdk="<SDK_PATH>" \
  --ohos-sdk-native="<OHOS_SDK_NATIVE_PATH>"
```

Only pass the paths the user actually has; omit the rest.

Show the user the result and ask them to confirm.

### Step 6: verify the environment

```bash
bash skills/kb-init/scripts/verify-env.sh
```

- `STATUS=ready`: tell the user the environment is ready
- `STATUS=not-ready`: show the reason for each FAIL, help them fix it, and re-verify

---

## Signs of completion

- The knowledge base is downloaded (for a fresh install)
- `ENV.local.md` has been generated in the KB root
- DevEco Studio + the OHOS SDK native toolchain + the DevEco CLI are ready
- The Qt OHOS SDK is configured
- `verify-env.sh` prints `STATUS=ready`

## Error handling

| Error | What to do |
|-------|------------|
| Cloning the knowledge base fails | Check the network; clone manually with `git clone https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills.git` |
| `detect-env.sh` fails to run | `chmod +x skills/kb-init/scripts/*.sh` |
| DevEco isn't detected after installing | Read `references/deveco-install.md` and check the path for your platform |
| The DevEco CLI isn't available | Check whether `<DEVECO_PATH>/tools/devecocli` exists; add it to PATH |
| git clone fails (commercial) | Check the HTTP credentials; check the network |
| git clone fails (opensource) | Check the network; try `git config --global http.sslVerify false` |
| The SDK download fails | Go to https://gitcode.com/ohos-qt/qt-harmonyos-src/releases manually |
| Building the SDK fails (commercial) | Check that MinGW/Perl/cmake are installed; see the troubleshooting section of `references/qt-compile-guide.md` |
| `verify-env.sh` reports FAIL | Fix each FAIL item as instructed and run it again |
| A Linux user has no DevEco Studio GUI | That's expected — use the Command Line Tools |

## Reference documents

- `references/deveco-install.md` — Detailed per-platform installation steps for DevEco Studio / the CLI
- `references/qt-src-acquisition.md` — Detailed descriptions of the two ways to obtain the Qt source
- `references/qt-compile-guide.md` — The complete guide to building Qt from source (required reading for commercial users; includes troubleshooting)
- `references/env-variables.md` — What every variable in ENV.md means and what it's for (including the tools bundled with DevEco)
