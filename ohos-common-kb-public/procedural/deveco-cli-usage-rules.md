---
id: deveco-cli-usage-rules
title: deveco-cli (devecocli) usage rules
status: active
confidence: 0.9
sources:
  - type: official
    name: "The deveco-cli repository's AGENTS.md / SKILL.md"
    date: 2026-08-03
    uri: "https://gitcode.com/openharmony-sig/deveco-cli"
  - type: experience
    name: "NeoHtop on-device deployment 2026-08-03 (first test of signature generate)"
    date: 2026-08-03
  - type: experience
    name: "open-pencil on-device deployment 2026-08-06 (re-test of signature generate)"
    date: 2026-08-06
created: 2026-08-03
updated: 2026-08-15
last_confirmed: 2026-08-06
superseded_by: null
tags: [deveco-cli, devecocli, toolchain, golden-rules, ohos-common]
refs: [deveco-mcp-capabilities]
summary: "devecocli as the preferred entry point, the capability boundaries of the low-level DevEco CLI, and headless diagnosis; minimal auditable low-level calls are allowed when the wrapper doesn't cover something or you're diagnosing the wrapper itself."
audience: public
---

# deveco-cli (devecocli) usage rules

> `devecocli` wraps the DevEco Studio toolchain (`ohpm`/`hvigor`/`hdc`/`emulator`/`hilog` + a bundled node/JBR/SDK), the HarmonyOS skills installer, and project scaffolding templates behind a single binary. Source: [openharmony-sig/deveco-cli](https://gitcode.com/openharmony-sig/deveco-cli).

## Why:

devecocli wraps the DevEco toolchain behind one entry point, unifying signature resolution, artifact location, and error attribution. Calling hdc/hvigor/ohpm directly is still a valid low-level capability, but should be limited to actions the wrapper doesn't cover, maintaining the wrapper, or constructing a minimal diagnostic reproduction. This page describes this knowledge ecosystem's tool-selection policy — don't mistake it for a HarmonyOS platform invariant.

## How to apply:

When the workspace has a `build-profile.json5`/`oh-package.json5`, pick a devecocli command from the "capability → scenario mapping table" first. If the wrapper has no corresponding capability, or you're diagnosing the wrapper layer, use a minimal low-level call and note the reason and the devecocli verification you returned to in your operation log. After changing `.ets`/`.ts`/`.cpp` files, run `deveco-mcp check` when the current MCP server is installed and supports them; use `deveco-mcp restart` if the LSP hangs. See [[deveco-mcp-capabilities]].

## Usage policy

| Severity | Rule | Why |
|---|---|---|
| Default | When the workspace has a `build-profile.json5`/`oh-package.json5` and devecocli covers the capability you need, prefer the wrapper command. | The wrapper unifies signing, artifacts, and error attribution; this is a tooling-ecosystem policy, not a platform limitation. |
| Exception | When devecocli doesn't cover the action, or you're maintaining/diagnosing the wrapper layer, you may make minimal calls to `hdc`/`hvigor`/`ohpm`/`emulator`; record the reason, and return to the wrapper for end-to-end verification afterwards. | Preserves low-level diagnosability while preventing a temporary detour from spreading into the default process. |
| Quality gate | When deveco-mcp is installed in the current environment and supports the target files, run `deveco-mcp check` after the AI modifies `.ets`/`.ts`/`.cpp`; when the MCP is unavailable, use the project's existing compile/lint/typecheck gates, and don't mistake "the MCP is missing" for a code failure. | Static diagnostics shorten the feedback loop, but tool availability and code correctness are two different things. See [[deveco-mcp-capabilities]]. |
| Misbehavior | When iterating on debugging, prefer `devecocli run --apply` (incremental deployment) or `--hotreload` for small changes rather than a full `run` every time. | A full build+install+launch is slow; incremental rebuilds only the changed files → installs via `bm quickfix` → restarts, and hot reload doesn't restart the application at all. |
| Misbehavior | `--hotreload` only works for **non-state code** (UI property values/text/method bodies/expressions); changes to `@State` decorators, native code, resources, or feature-hsp dependencies require a full `run`. | Hot reload doesn't reinitialize state, and can't cover native/resource/dependency-module changes. |
| Misbehavior | When deveco-mcp enters ERROR or hangs, use `deveco-mcp restart` (target=arkts/cpp/all) rather than restarting the IDE. | restart re-syncs the project and reinitializes the LSP in place; restarting the IDE is expensive and loses the session. |

## Capability → debugging/testing scenario mapping

| Scenario | Command | The low-level operation it replaces |
|---|---|---|
| Create a new HarmonyOS project | `devecocli create --app-name <n> --bundle-name <b> --api-level <l>` | Assembling a template by hand |
| Signing configuration | `devecocli auth login` → `devecocli signature generate --product <p>` (generates p12/csr/cer/profile, writes signingConfigs into `build-profile.json5`, and links product.signingConfig; the material is stored in `~/.ohos/config/`) | DevEco Studio GUI auto-signing (Project Structure → Signing Configs → Automatically generate signature) |
| Building | `devecocli build [--modules ...] [--product ...] [--build-mode debug\|release]` | Bare hvigor/ohpm |
| Install and run | `devecocli run [--module ...] [--device ...]` | Bare hdc install + aa start |
| Incremental deployment | `devecocli run --apply <fileName>` | A full run every time |
| Hot reload | In the background: `devecocli run --module <m> --hotreload` → `devecocli run --module <m> --hotreload-apply <file>` → when done, kill it + `--hotreload stop` | A full run every time |
| Device queries | `devecocli device list` / `device view -t <name\|serial>` | hdc list targets |
| Emulator | `devecocli emulator list/start/stop/create/delete/image` | The bare emulator binary |
| UI layout diagnosis | `devecocli ui layout [--id ...] [--depth ...] [--format json]` | Hand-written hdc snapshot |
| Screenshots | `devecocli ui screenshot --path <png>` | hdc snapshot_display + file recv |
| UI interaction automation | `devecocli ui click/swipe/text/longclick/drag ...` | Hand-written hdc input |
| Window list | `devecocli ui window list` | hdc dumpsys window |
| Runtime logs | `devecocli log [--level ...] [--bundle-name ...] [--keyword ...] [--from 5m] [--tail N] [--follow]` | hdc shell hilog |
| Crash analysis | `devecocli log --crash --bundle-name <b>` | Hunting for the crash file by hand |
| Code style | `devecocli check lint [--fix] [--format json]` | Bare codelinter |
| API compatibility (SDK upgrades) | `devecocli check compat --source-version <v> --target-version <v> [--output-path ./report]` | No equivalent (IDE only) |
| Documentation search | `devecocli docs search <kw>` / `docs read <id>` / `docs catalog` | Online search only |

## Common recipes

- **From a fresh checkout to the emulator**: `devecocli build` → `devecocli emulator list` → `devecocli emulator start "Name"` → `devecocli run`
- **Diagnosing a crash**: `devecocli log --crash --bundle-name <bundle>`
- **First-time signing (entirely from the CLI, no DevEco Studio IDE needed)**: `devecocli auth login` (in the user's own terminal) → `devecocli signature generate --product default` (generates p12/csr/cer/profile, writes `signingConfigs`, and links `product.signingConfig`, with the material stored in `~/.ohos/config/`) → `devecocli build` → `devecocli run`. Equivalent to ticking "Automatically generate signature" in the GUI, but doable in an agent/script with no GUI. Independently verified twice: NeoHtop (first test 2026-08-03) and open-pencil (re-test 2026-08-06); framework-specific pitfalls (such as Tauri's daemon env caching / `TAURI_OHOS_SKIP_DEVECO_SCRIPT`) are on each domain KB's deployment page.
- **Iterating on UI properties**: `devecocli run` (first time) → change `.fontColor` → write `.hvigor/changes.txt` → `devecocli run --hotreload-apply changes.txt` (the UI updates immediately without restarting)

## Boundaries (what devecocli doesn't replace)

- **Profiler performance timeline analysis** (memory/components/network/startup/jank) → the DevEco Studio Profiler or the `hiperf` command line
- **AppAnalyzer application health checks** → DevEco Studio's AppAnalyzer
- **Cross-language breakpoint debugging** (ArkTS & C++, assembly, reverse debugging) → the DevEco Studio debugger or `lldb`
- **IDE-integrated incremental debugging** → DevEco Studio's incremental debugging (devecocli's `--apply`/`--hotreload` are the command-line equivalents)

> For static syntax checking, see [[deveco-mcp-capabilities]] — deveco-mcp is a sub-capability of `devecocli serve mcp`, giving AI agents ArkTS/C++ LSP checks.

## Capability boundaries of the low-level DevEco CLI

`devecocli` is this ecosystem's stable operating entry point, but when troubleshooting the wrapper layer or maintaining build scripts you still need to understand the low-level responsibilities:

| Low-level entry point | Responsibility | Key boundary |
|---|---|---|
| `devecostudio format/inspect` | Formatting, offline checks, opening a project | Based on the IDE/IntelliJ launcher; doesn't build. The GUI's single-instance lock may block headless invocation |
| `hvigorw` | Listing tasks, clean, building HAP/HAR/HSP | A Node script; confirm task names with `tasks`, and use `--no-daemon` in automation |
| `ohpm` | Installing HarmonyOS/OpenHarmony project dependencies | Only handles package dependencies; doesn't build the application |
| `hdc` | The low-level channel for devices, installation, shell, files, and logs | Prefer the wrapper where devecocli covers it; for uncovered key/uitest/diagnostic actions, make minimal calls and record why |
| `hap-sign-tool` | A standalone HAP signing tool | Doesn't substitute for a correct profile, bundleName, and product signingConfig |
| `hnpcli` | The HNP native package tool | Only use it when you've explicitly adopted the HNP distribution model |

A common misconception is treating the `devecostudio` launcher's command-line options as a build CLI; actual project builds are executed by hvigor. Low-level commands and options change between DevEco Studio versions, so run `--help`/`tasks` for your target installed version rather than guessing task names from an older page.

### Minimal diagnosis of wrapper-layer failures

When a `devecocli` error points at a low-level tool, you're maintaining the wrapper itself, or there's no wrapper command for the action you need:

1. Use `devecocli`'s verbose logs to identify which stage failed
2. Verify that the bundled Node/JBR/SDK all come from the same DevEco installation
3. For hvigor, run only `tasks --no-daemon` or an equivalent minimal failure reproduction
4. Check `NODE_HOME`, the Java executable, and the project path — but don't write local absolute paths into the knowledge base
5. If it's an uncovered capability, record the minimal scope of the low-level command and its exit condition
6. Once fixed or finished, return to `devecocli build/run` or the project's existing end-to-end gates to verify

A `signingConfigs` entry only participates in the build when it's referenced by the target `products[].signingConfig`; the profile must also match the application identity and the required permissions. Keep signing material in a secure local location at all times — never in command logs, knowledge pages, or commits.

### `hvigorw` / `java` not found

If the logs say `hvigorw not found`, `java not found`, or "`hvigorw` / `java` not found", first confirm that the current terminal is using the JBR, Node, and SDK that ship with DevEco. Prefer using the bundled toolchain through `devecocli`; when diagnosing low-level scripts, check whether `JAVA_HOME`, `OHOS_HOME`, and their executable directories are on the current process's `PATH`, and verify with a minimal `hvigorw --help` or `tasks --no-daemon` from your target installed version. Don't bake machine-specific absolute paths into a knowledge page or a project template.

## Prerequisites

- `devecocli` on PATH: `npm i -g @deveco-test/deveco-cli`
- Install the skill into your AI agent: `devecocli init --skill` (or `--mcp` to configure the deveco-mcp server)
- DevEco Studio ≥ 6.1.0 (`--apply` needs ≥ 6.1.1 for hvigor's `assembleDevHqf`)
- Under zsh, the version numbers for `check compat` must be quoted
