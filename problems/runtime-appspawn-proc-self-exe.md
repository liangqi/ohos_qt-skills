---
id: problem-runtime-appspawn-proc-self-exe
type: problem
domain: runtime
tags: [appspawn, /proc/self/exe, readlink, sandbox, ELF-parsing, immediate-exit, no-logs]
created: 2026-11-04
updated: 2026-11-04
status: open
severity: high
audience: public
summary: "The application exits right at startup with no logs: modern appspawn has the application re-exec itself, so /proc/self/exe is not an ELF"
# ====== Search keywords (for fast agent matching) ======
error_message: >
  (the application exits immediately after launch; hilog has no lines from this process, and faultlog has no cppcrash)
  readlink("/proc/self/exe") returns something that isn't an executable ELF, so reading e_ident fails
error_code: ""
keywords: [appspawn, proc/self/exe, readlink, ELF, exec, sandbox, exits at startup, no logs, restart storm]
symptoms: "After hdc launches the application, it instantly returns to the desktop; no crash stack, no application logs, as if the system killed it outright"
# ====== Problem details ======
environment: "HarmonyOS 5.x PC (the new appspawn launch chain); a self-drawn-UI application cross-built with the Qt 6.13.0-dev OHOS kit"
refs: [problem-runtime-tray-must-exist-noop, problem-platform-guard-needs-both-ohos-macros]
related_problems: [problem-runtime-tray-must-exist-noop]
---

# appspawn has the application "exec itself once more": `/proc/self/exe` is no longer an ELF

## Symptoms

- `hdc shell aa start` returns success, and the application disappears right away (back to the desktop);
- `hilog` has no logs at all from this process, and `/data/log/faultlog/faultlogger/` has no cppcrash;
- repeated launches form a "restart storm"; from the outside it looks like "the system killed the application outright".

## Root cause

The new appspawn launch chain has the application **exec itself once more** inside the sandbox. At that point the process's
`/proc/self/exe` doesn't point at the executable ELF on disk (but at an intermediate state/deleted node inside the sandbox),
while traditional desktop code relies on it for self-checks or to parse its own ELF header:

```cpp
char buf[PATH_MAX];
ssize_t n = readlink("/proc/self/exe", buf, sizeof(buf) - 1);
// open buf and read the ELF e_ident → not 0x7f 'E' 'L' 'F'
```

Once this code runs early in startup (static initialization, before `QApplication`), parsing fails → the process exits before producing
any logs, hence "no logs".

## How to diagnose

1. First confirm "did it ever come up at all": poll `hdc shell "ps -ef | grep <bundle>"` within 1 second of launching;
   if the process appears and then disappears, it entered the exec chain rather than failing on bad arguments.
2. Print the return value of `readlink("/proc/self/exe")` and the first 4 bytes of `e_ident`: anything other than `\x7fELF` means you've hit this problem.
3. Cross-check: the same binary works on a device with an older appspawn → the difference is in the launch chain, not the code logic.

## Solution

Remove the dependency on `/proc/self/exe`:

- When you need "your own path", use `QCoreApplication::applicationFilePath()` (the QPA already handles the sandbox semantics),
  or just use `argv[0]`;
- When you need ELF information (version, build number), switch to **injecting it at compile time** (`-DAPP_BUILD_ID=...`) or reading a bundled resource;
- Don't do "self-check"-style file parsing early in startup; move it after `QApplication` is constructed and add a fallback for failure.

## Boundaries

This page's status is `open`: the symptom was observed on a real device and traced to the exec chain, but it has **not yet** been reproduced side by side
with a minimal demo on different appspawn versions. By the evidence standard in `faults/_index.md` §6, it can for now only serve as
an experience record on a problems page, and can't be promoted to a C-page classification.
