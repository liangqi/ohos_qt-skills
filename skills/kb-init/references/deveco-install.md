# DevEco development tools installation guide

This file covers installing three kinds of tools:
1. **DevEco Studio** — the GUI IDE (macOS / Windows)
2. **Command Line Tools** — the command-line toolset (Linux / HarmonyOS)
3. **deveco-cli** — the open-source AI development tool (all platforms)

---

## macOS

### DevEco Studio

#### Download

1. Go to https://developer.huawei.com/consumer/cn/deveco-studio/
2. Choose the macOS build of **DevEco Studio** (both Intel and Apple Silicon are supported)
3. Download the `.dmg` installer

> **Automatic download**: `bash skills/kb-init/scripts/download-cmdline-tools.sh --dest=<directory>` downloads the installer into the directory you specify.

#### Install

1. Double-click the `.dmg` file
2. Drag DevEco Studio into `/Applications`
3. On first launch, if the system says it "can't verify the developer", go to **System Settings → Privacy & Security** and click "Open Anyway"
4. On first launch, DevEco Studio downloads the HarmonyOS SDK automatically

#### Verify

```bash
ls /Applications/DevEco-Studio.app
ls /Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/native/llvm/bin/clang
ls /Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/toolchains/hdc
```

### Add the tools to PATH (recommended)

```bash
echo 'export PATH="/Applications/DevEco-Studio.app/Contents/tools:$PATH"' >> ~/.zshrc
echo 'export PATH="/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/toolchains:$PATH"' >> ~/.zshrc
source ~/.zshrc
devecocli --version  # verify DevEco CLI
hdc version          # verify hdc
```

---

## Windows

### DevEco Studio

#### Download

1. Go to https://developer.huawei.com/consumer/cn/deveco-studio/
2. Choose the Windows build of **DevEco Studio**
3. Download the `.exe` installer

> **Automatic download**: `bash skills/kb-init/scripts/download-cmdline-tools.sh --dest=<directory>` downloads the installer automatically.

#### Install

1. Double-click the `.exe` installer
2. Follow the wizard (it installs to `C:\Program Files\Huawei\DevEco Studio` by default)
3. On first launch, it downloads the HarmonyOS SDK automatically

#### Verify

```powershell
dir "C:\Program Files\Huawei\DevEco Studio"
dir "C:\Program Files\Huawei\DevEco Studio\sdk\default\openharmony\native\llvm\bin\clang.exe"
dir "C:\Program Files\Huawei\DevEco Studio\sdk\default\openharmony\toolchains\hdc.exe"
```

### Add the tools to PATH (recommended)

1. Open **System Settings → Advanced system settings → Environment Variables**
2. Add to **Path**:
   - `C:\Program Files\Huawei\DevEco Studio\tools`
   - `C:\Program Files\Huawei\DevEco Studio\sdk\default\openharmony\toolchains`
3. Open a new PowerShell window and verify: `devecocli --version` and `hdc version`

---

## Linux

### Command Line Tools

DevEco Studio **has no Linux GUI build**. Linux users use the **Command Line Tools for HarmonyOS**.

#### Automatic installation (recommended)

```bash
bash skills/kb-init/scripts/download-cmdline-tools.sh \
  --dest=~/commandline-tools \
  --url=<the link from the download page>
```

The script downloads, extracts, and prints the SDK path.

#### Manual installation

1. Go to https://developer.huawei.com/consumer/cn/download/
2. Find the Linux build of **Command Line Tools for HarmonyOS**
3. Download the `.tar.gz` archive

```bash
mkdir -p ~/commandline-tools
tar xzf commandline-tools-linux-*.tar.gz -C ~/commandline-tools
```

#### Configure PATH

```bash
echo 'export PATH="$HOME/commandline-tools/tools:$PATH"' >> ~/.bashrc
echo 'export PATH="$HOME/commandline-tools/sdk/default/openharmony/toolchains:$PATH"' >> ~/.bashrc
echo 'export OHOS_SDK_NATIVE="$HOME/commandline-tools/sdk/default/openharmony/native"' >> ~/.bashrc
source ~/.bashrc
```

#### Verify

```bash
devecocli --version
hdc version
ls ~/commandline-tools/sdk/default/openharmony/native/llvm/bin/clang
```

---

## HarmonyOS

### Platform limitations

HarmonyOS PC currently has the following limitations:

| Tool | Status | How to obtain |
|------|--------|---------------|
| DevEco Studio | Unavailable | No HarmonyOS build; not listed in the app store |
| Command Line Tools | Requires an application | File a ticket on the unified ticket platform to request the telemetry build |
| deveco-cli | Worth trying | The repository doesn't declare support, but you can try installing it via npm |

### Applying for the Command Line Tools

1. Go to the unified ticket platform at https://developer.huawei.com/consumer/cn/
2. File a ticket requesting the **telemetry build of Command Line Tools for HarmonyOS**
3. Once you have the download link, run:

```bash
bash skills/kb-init/scripts/download-cmdline-tools.sh \
  --dest=~/commandline-tools \
  --url=<download link>
```

4. Configure PATH:

```bash
echo 'export PATH="$HOME/commandline-tools/tools:$PATH"' >> ~/.zshrc
echo 'export PATH="$HOME/commandline-tools/sdk/default/openharmony/toolchains:$PATH"' >> ~/.zshrc
echo 'export OHOS_SDK_NATIVE="$HOME/commandline-tools/sdk/default/openharmony/native"' >> ~/.zshrc
source ~/.zshrc
```

### What you can set up while waiting for the CLT

The tools below can be installed via HarmonyBrew and don't depend on DevEco/CLT:

```bash
# Install HarmonyBrew (if you haven't already)
zsh -c "$(curl -fsSL https://harmonybrew.atomgit.com/install.sh)"

# Install the basic tools
brew install git cmake node
```

---

## deveco-cli (all platforms)

The `devecocli` command is provided by the open-source tool deveco-cli (repository: https://gitcode.com/openharmony-sig/deveco-cli, npm package name `@deveco/deveco-cli`). It wraps the DevEco toolchain (ohpm/hvigor/hdc/emulator/hilog + the bundled node/JBR/SDK) and covers building, installing, logs, signing, the emulator, and UI automation. Some DevEco Studio versions also bundle a copy at `tools/devecocli{.bat}` with the same functionality; use whichever one you locate (for the lookup order, see `ohos-common-kb-public/procedural/deveco-cli-usage-rules.md` §Tool availability pre-check).

- **Requires**: Node.js >= 18

### Automatic installation (recommended)

```bash
bash skills/kb-init/scripts/install-deveco-cli.sh --method=npm
```

### Manual installation

```bash
npm i -g @deveco/deveco-cli
devecocli --version   # note: the binary is named devecocli
```

### Verify

```bash
devecocli --version
```

### Common mix-ups

| Name | What it actually is |
|------|---------------------|
| `devecocli` | This tool (npm `@deveco/deveco-cli`, the stable channel; bundled with some DevEco versions) |
| `deveco-cli` (bare package name/command) | **Doesn't exist** — the npm scoped package is `@deveco/deveco-cli`, and the only binary is `devecocli` |
| `@deveco-test/deveco-cli` | The test-channel package; don't use it in install commands |
| `devecostudio` | The DevEco Studio GUI launcher, not a build CLI |
