---
id: deveco-mcp-capabilities
title: deveco-mcp capabilities and usage boundaries
status: active
confidence: 0.7
sources: [{type: official, name: "deveco-cli repository mcp/src-server + SKILL.md", date: 2026-08-03, uri: "https://gitcode.com/openharmony-sig/deveco-cli"}]
created: 2026-08-03
updated: 2026-08-15
last_confirmed: 2026-08-03
superseded_by: null
tags: [deveco-mcp, mcp, lsp, arkts, cpp, golden-rules, ohos-common]
refs: [deveco-cli-usage-rules]
summary: "Installing deveco-mcp, configuring clients, its check/restart capabilities, and its boundaries; build, run, UI, and log operations belong to devecocli or to explicit low-level diagnosis."
audience: public
---

# deveco-mcp capabilities and usage boundaries

> `deveco-mcp` is the stdio MCP server started by `devecocli serve mcp` (npm package `@deveco-codegenie/mcp`). Built on LSP, it gives AI coding tools static syntax analysis for HarmonyOS projects. It is a sub-capability of [[deveco-cli-usage-rules]], not a standalone toolchain.

## Tool inventory

| MCP tool | Capability | Applicable languages |
|---|---|---|
| `deveco-mcp_check` | Static syntax analysis of HarmonyOS project source files, returning structured diagnostics (severity/file/line/message) | ArkTS, C/C++ |
| `deveco-mcp_restart` | Restart the MCP server in place: re-sync the project + reinitialize the LSP (arkts/cpp/all) | — |

## Usage requirements

| Severity | Rule | Why |
|---|---|---|
| Quality gate | When the MCP is installed in the current environment and the target file is supported, run `deveco-mcp check` after the AI modifies a `.ets`/`.ts`/`.cpp` file. When the MCP is unavailable, run the project's existing compile/lint/typecheck gates instead. | LSP checks shorten the feedback loop, but MCP availability should not become a false blocker for the platform or the code. |
| Misbehavior | When deveco-mcp enters ERROR or hangs (symbols not updated after a large change, a stale LSP index), use `deveco-mcp restart` rather than restarting the IDE. | restart re-syncs the project and reinitializes the LSP in place; restarting the IDE is expensive and loses session state. |
| Misbehavior | **Don't retry repeatedly** after a `restart` failure — it's most likely a project/SDK configuration problem, so investigate the root cause first. | The tool description says so explicitly: "if initialization fails again after a restart, the cause is likely a persistent project/SDK configuration issue". |

## What check returns and how to use it

- Input: a list of file paths (relative to the project root or absolute; ArkTS `.ets`/`.ts` + C/C++ `.c`/`.cpp`/`.h`)
- Output: structured results grouped by `relative_path → severity → name_path → diagnostics_results`
- severity: 1=Error / 2=Warning / 3=Information / 4=Hint
- Usage: the AI edits code → `deveco-mcp check` → every Error must be fixed → recheck after fixing → only commit once everything passes

## Boundaries (what deveco-mcp does not do)

- **No runtime debugging**: breakpoints, variable inspection, call stacks, reverse debugging → use the DevEco Studio debugger or `lldb`
- **No code style checking**: lint (TS/ArkTS conventions) → use `devecocli check lint`
- **No API compatibility scanning**: breaking changes between SDK versions → use `devecocli check compat`
- **No performance/memory profiling**: profiler timelines → use the DevEco Studio Profiler or `hiperf`
- **No crash symbolication**: restoring obfuscated release stacks → use `hstack`

> deveco-mcp is the "syntax gatekeeper after AI generates code", not a full-featured debugger. For the complete HarmonyOS development tooling, see [[deveco-cli-usage-rules]].

## Prerequisites

- `devecocli init --mcp` (or configure `@deveco-codegenie/mcp@beta` in your AI tool by hand; requires a `DEVECO_PATH` environment variable pointing at your DevEco Studio installation)
- `node` available locally (npx uses it to launch)
- To verify: `/mcps` in your AI tool should show deveco-mcp as Connected

## Installation and client configuration

Prefer having `devecocli init --mcp` write the configuration your current agent/IDE supports. When you must configure by hand, the minimal form of a stdio server is:

```json
{
  "mcpServers": {
    "deveco-mcp": {
      "command": "npx",
      "args": ["-y", "@deveco-codegenie/mcp@beta"],
      "env": {
        "DEVECO_PATH": "<DevEco Studio installation>"
      }
    }
  }
}
```

Different clients may use `mcpServers`, `servers`, or some other local server schema; take the field names from your client's current documentation rather than copying a client-specific template that's easy to outdate. Only set `PROJECT_PATH` when the project can't be discovered automatically, and keep it in local configuration — don't write it into a shared knowledge page or the repository.

In offline or restricted-network environments you can use the officially published local server package; the binary name, download location, and system isolation handling change between versions, so check the corresponding release notes before installing.

## Two generations of tool names

Earlier toolchains exposed several actions such as `check_ets_files`, `check_cpp_files`, `build_project`, `start_app`, `project_sync`, and `get_app_ui_tree`. The current common rule defers to the tool list actually returned by the connected server, and abstracts static checking and restarting as `deveco-mcp check/restart`.

Therefore:

1. Don't hard-code "there must be exactly 11 tools" based on an old screenshot or an old page.
2. From the current MCP, use only `check`/`restart` as described by the actual tool descriptions; build/run/UI/log go through devecocli's capabilities in [[deveco-cli-usage-rules]].
3. If `check`/`restart` are missing, first confirm the project and LSP initialization state, then run a single restart; if it keeps failing, investigate the SDK/project configuration.
