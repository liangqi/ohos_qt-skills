---
id: build-fail-configure-exec-bit-crlf
type: problem
domain: build
status: solved
audience: public
created: 2026-09-19
updated: 2026-09-19
severity: high
tags: [build, linux, macos, src-clone, gitcode, crlf, exec-bit]
refs: [skills/qt-sdk-forge/references/build-matrix.md, knowledge/errors/QOH037.yaml]
error_message: "exec: /path/qt-harmonyos-src/qtbase/configure: Permission denied"
error_code: N/A
summary: >
  The GitCode open-source mirror's initial import commit stored every file as 100644 (losing the exec bits), and the main/5.12.12
  snapshots have Windows CRLF line endings. On POSIX (Linux/macOS), sh configure fails right away
  (Permission denied or bad interpreter: /bin/sh^M). src-clone has a built-in automatic fix.
---

# Lost exec bits / CRLF line endings in the open-source mirror's sources make configure fail

## Symptoms

On Linux/macOS, configure after cloning with `qt-sdk-run.py src-clone --method opensource`:

```
/path/qt-src/qt5.12/configure: 49: exec: /path/qt-src/qt5.12/qtbase/configure: Permission denied
```

or (when the branch has CRLF):

```
bad interpreter: /bin/sh^M: no such file or directory
```

## Cause

The initial import (`5e9825352`) of the GitCode open-source mirror `ohos-qt/qt-harmonyos-src` has two snapshot-level defects:

1. **Every file is 100644**: ~620 scripts with shebangs (`configure`, `syncqt.pl`, the various `*.sh`) lost their exec bits; git stores them as non-executable
2. **The main / 5.12.12 snapshots are CRLF**: the source package was exported from the Windows side, and a POSIX shell can't execute it

The mirror's actual branches (confirmed with `git ls-remote --heads`):

| Branch | Contents | Use for |
|--------|----------|---------|
| `main` / `5.12.12` | Upstream snapshot, CRLF + lost exec bits | Windows only |
| `build/macos-arm64-qt5.12.12` | **POSIX build branch**: LF line endings + build-enablement patches (warning suppression) | **Source builds on macOS/Linux should use this branch** |

Note: the `BRANCHES` mapping in early CLI versions (`tqtc/harmonyos-5.12.12`) is the commercial repository's name; that branch doesn't exist in the open-source mirror, so clone fails with `Remote branch not found`.

## Solution

**Now**: `src-clone --method opensource` has a built-in fix (since v2026-09-19):

- It checks out the POSIX build branch `build/macos-arm64-qt5.12.12` by default (`OPENSOURCE_BRANCHES`; override with `--branch`)
- After cloning, it scans for shebang scripts, restores +x, and pins that in a git commit (keeping the working tree clean so the SV1 gate passes)
- CRLF check: if the checked-out branch has CRLF, it FAILs right away and suggests switching branches

**Manual equivalent** (old CLI / existing clones):

```bash
git clone --branch build/macos-arm64-qt5.12.12 --single-branch \
  https://gitcode.com/ohos-qt/qt-harmonyos-src.git qt5.12
cd qt5.12
# Restore the exec bits and pin them in a commit
grep -rIl "^#!" --exclude-dir=.git . | tee /tmp/exec-files.txt
xargs -a /tmp/exec-files.txt chmod +x
xargs -a /tmp/exec-files.txt git update-index --chmod=+x
git commit -m "fix: restore executable bits lost in initial import"
```

## Verification

```bash
file qtbase/configure   # → POSIX shell script, ASCII text executable (no CRLF)
sh qtbase/configure --help
```
