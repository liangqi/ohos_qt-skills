---
id: problem-build-qt6-no-undefined-symbols
type: problem
domain: build
tags: [no-undefined, unresolved-symbols, DT_NEEDED, musl, find_sym2, GNU_HASH, sysroot, G13, tdesktop]
created: 2026-11-18
updated: 2026-11-18
status: solved
severity: high
audience: public
refs: [semantic-qt-harmonyos-build, semantic-qt-harmonyos-third-party-libs]
summary: >
  The HarmonyOS toolchain forces -Wl,--no-undefined, and --allow-shlib-undefined has no effect.
  With unresolved symbols you can still produce a package, but on the device musl's find_sym2 SIGSEGVs (when an object has only
  DT_GNU_HASH, dso->hashtab is NULL). Gives two levels of criteria: link time and before installing.
leader_summary: >
  Split "the link passes" into two things, link-time symbol closure and runtime symbol resolvability, with one criterion each
impact: [Linking, Runtime crashes, Gates]
deliverables: [problem record]
evidence: []

error_message: >
  ld.lld: error: undefined symbol: __at_fini
  # or (not reported at link time, but after installing)
  ld-musl-aarch64.so.1(find_sym2+568) SIGSEGV
  # or
  /data/storage/el1/bundle/libs/arm64/libapp.so: undefined symbol: __register_frame_info
error_code: ""
keywords: [no-undefined, allow-shlib-undefined, unresolved symbols, UND, DT_NEEDED,
           GNU_HASH, DT_HASH, musl, find_sym2, dso->hashtab, sysroot, G13]
symptoms: "The link reports undefined symbol (or reports nothing at all); after installing, the process SIGSEGVs in
  ld-musl-aarch64.so.1(find_sym2), and the crash stack has no business-logic functions at all"
environment: "Qt 6 HarmonyOS kit + OHOS SDK sysroot + arm64-v8a device (tested with tdesktop 7.4.4)"
---

# Unresolved symbols: not reported at link time, crashing in find_sym2 on the device

## Symptoms

Two paths with completely different symptoms, but the same kind of root cause:

1. **Link time**: `ld.lld: error: undefined symbol: __at_fini`. It looks like some library
   isn't linked, but it's still reported after adding every `-l`, because the symbol itself isn't in any bundled library.
2. **Runtime**: the link passes, the HAP is assembled and installed, and after `aa start` the process dies in
   `ld-musl-aarch64.so.1(find_sym2+568)`; the crash stack has no business-logic functions, only the dynamic
   linker. On a real device this stack is easily mistaken for "the QPA plugin is broken".

## Root cause

Two independent mechanisms stacked together:

**Link time**: the HarmonyOS toolchain adds
`-Wl,--no-undefined` in `ohos.toolchain.cmake` (shared libraries may not leave unresolved symbols). That's the opposite of the usual Linux habit:
on desktop Linux, shared libraries may have unresolved symbols, which the `DT_NEEDED` closure provides at runtime.

`-Wl,--allow-shlib-undefined` has **no effect** with this toolchain; it's an ordering problem:
the toolchain file appends after `CMAKE_CXX_FLAGS`, so `--no-undefined` comes later on the final command line,
and the latter overrides the former.

**Runtime**: when musl's `find_sym2` looks up a symbol across a set of objects, it first looks at
`dso->hashtab`. That field comes from `DT_HASH` (the SysV hash). If a searched object
**has only `DT_GNU_HASH`** (modern lld's default behavior), `hashtab` is `NULL`, and
`find_sym2` doesn't null-check it there, so it segfaults.

In other words, it crashes only when both conditions are present: `unresolved symbols` + `a GNU-hash-only object`.
`-Bsymbolic`, `BIND_NOW`/`DF_1_NOW`, and `RTLD_GLOBAL` don't change this; they
change binding timing and visibility, not the object's hash table type.

## Criteria (two levels)

**Link time** (this project's own outputs):

```bash
llvm-nm -D --undefined-only libapp.so | grep -v ' U ' | head
# or use the tool: G13
python tools/qt-ohos-run.py verify    # G13 Loadable
```

G13's definition is "strong UND symbols − (bundled exports ∪ sysroot exports ∪ `undefined_allow`)":

- If `ohos_sdk_native` or `sysroot/usr/lib` isn't available → **SKIP** (never fail just because something can't be read,
  to avoid manufacturing false failures);
- If there are unresolved symbols → **PARTIAL** by default (listing the first few symbols with the hint "may SIGSEGV in
  find_sym2 on the board"); only `config set undefined_gate strict` makes it FAIL.

**Runtime** (confirming whether a system library is GNU-hash-only):

```bash
llvm-readelf -d $OHOS_SDK_NATIVE/sysroot/usr/lib/arm64-v8a/libc.so | grep -c DT_HASH
# 0 means only DT_GNU_HASH; combined with unresolved symbols, this reproduces the find_sym2 crash
```

## Fix

Handle symbols in three categories by source; don't just generically "link one more library":

| Symbol shape | Source | Handling |
|--------------|--------|----------|
| `__at_fini`, `__register_frame_info`, `_libva_so_tramp_resolve_all` | The desktop GCC/glibc runtime, or some library's gcc-specific assembly | Replace with the clang/libc++ equivalent, or remove the dependency on that library at the source |
| `ssl_*`/`crypto_*` | OpenSSL not in the package | `QT_HARMONYOS_EXTRA_LIBS`; see [runtime-hap-missing-so-closure](runtime-hap-missing-so-closure.md) |
| The application's own functions | Some `OBJECT`/`STATIC` library wasn't added to the link | Check whether `target_link_libraries` is missing that target |

Tested (tdesktop): of 4007 UND symbols, 13 belonged to the first category, present in neither the bundled libraries nor the sysroot;
these must be removed at the source level, since no amount of linking can supply them.

## Verification

```bash
python tools/qt-ohos-run.py verify        # G13's three states: PASS/PARTIAL/SKIP
python tools/qt-ohos-run.py doctor        # is there a sysroot (without one it can only SKIP)
```

## Related

- [build-qt6-app-must-be-shared](build-qt6-app-must-be-shared.md): the linking model
- [runtime-hap-missing-so-closure](runtime-hap-missing-so-closure.md): `.so` closure
- `semantic/qt-harmonyos-build-workflow.md`: explanation of G13's criteria
