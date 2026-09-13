---
id: problem-build-fail-glibc-internal-symbols-ohos-musl
type: problem
domain: build
tags: [build, ohos, musl, glibc, pid_t, uid_t, in6_addr, s6_addr32, porting]
created: 2026-07-10
updated: 2026-07-10
status: solved
severity: medium
audience: public
refs: [procedural-qt-app-harmonyos-migration, problem-build-fail-libuuid-missing-ohos-musl]
summary: >
  glibc exposes a set of "internal" symbols (typedefs such as __pid_t/__uid_t, and glibc-only members such as in6_addr.s6_addr32),
  while OHOS musl provides only the standard names (pid_t/uid_t, s6_addr[16]). A Linux application using glibc's internal names
  fails to compile on OHOS with "unknown type name '__pid_t'" / "no member named 's6_addr32'". Preferred fix: switch to the
  standard POSIX names (pid_t/uid_t — glibc supports them too, so the original Linux build still works); replace s6_addr32 with
  sscanf into 4× uint32 + memcpy into s6_addr[16] (the byte layout is identical).
leader_summary: Captured the reusable troubleshooting for glibc internal symbols (__pid_t/__uid_t/s6_addr32) being incompatible with musl when porting Linux → OHOS
impact: [Migration efficiency, Build troubleshooting]
deliverables: [problem record, tcpview HAP]
evidence: [tcpview-ohos attempt1 build.log (__pid_t/__uid_t errors), attempt2 BUILD SUCCESSFUL]

error_message: >
  error: unknown type name '__pid_t'; did you mean 'pid_t'?
      CRootModule(__pid_t processId, std::string fifoName);
  error: unknown type name '__uid_t'
      static QString GetUserNameString(__uid_t euid, bool bErrorUser);
  (another form, s6_addr32: error: no member named 's6_addr32' in 'struct in6_addr')
error_code: ""
keywords: [__pid_t, __uid_t, pid_t, uid_t, s6_addr32, s6_addr, in6_addr, glibc, musl, unknown type name, no member]
symptoms: Porting a Linux application to OHOS, the build reports unknown type name '__pid_t'/'__uid_t' or in6_addr has no member 's6_addr32'
environment: OHOS musl sysroot (aarch64-linux-ohos) + clang; tcpview (rootmodule.h/cusername.h/datasource.cpp)
---

# glibc internal symbols don't exist in OHOS musl (__pid_t/__uid_t/s6_addr32)

## Error messages

```
# Form A: __-prefixed typedefs (glibc internal names; musl has none)
C:/.../source/rootmodule.h:46:17: error: unknown type name '__pid_t'; did you mean 'pid_t'?
    CRootModule(__pid_t processId, std::string fifoName);
                ^~~~~~~
                pid_t
C:/.../source/cusername.h:26:38: error: unknown type name '__uid_t'
    static QString GetUserNameString(__uid_t euid, bool bErrorUser);

# Form B: glibc-only struct members (musl has none)
C:/.../source/datasource.cpp:399: error: no member named 's6_addr32' in 'struct in6_addr'
    sscanf(loc_addr, "%08X%08X%08X%08X", &socket_info.loc6.s6_addr32[0], ...);
```

## Scenario

A Linux application uses glibc's "internal" symbols directly (double-underscore-prefixed typedefs or glibc extension struct
members). These are available on glibc (which exposes both `__pid_t` and `pid_t`, and both `in6_addr.s6_addr32` and `s6_addr`),
but OHOS musl has only the standard names → the build reports unknown type name / no member. tcpview has three instances:
`__pid_t` in rootmodule.h, `__uid_t` in cusername.h, and `in6_addr.s6_addr32` in datasource.cpp.

## Cause

- glibc's `bits/alltypes.h` defines both `__pid_t`/`__uid_t` (the internal names) and typedefs `pid_t`/`uid_t` (the standard
  names, usually `typedef __pid_t pid_t`). musl only defines the standard names `pid_t`/`uid_t` (`typedef int pid_t;`) and
  doesn't expose the `__`-prefixed internal names.
- glibc's `struct in6_addr` provides three union views — `s6_addr`, `s6_addr16`, and `s6_addr32` (the latter two are glibc
  extensions). musl's `in6_addr` has only `s6_addr[16]` (a union + `#define s6_addr`), with no `s6_addr32`/`s6_addr16`.

## Solution

**Form A (__pid_t/__uid_t and friends): switch to the standard POSIX names.** `__pid_t`→`pid_t`, `__uid_t`→`uid_t`. glibc
supports the standard names too, so this doesn't break the original Linux/qmake build (a portable fix). Watch out for header
self-sufficiency: a header that uses `uid_t` but only includes something like `<QString>` needs `#include <sys/types.h>` added
(as was done in tcpview's cusername.h).

**Form B (s6_addr32): go through s6_addr[16] + memcpy.** sscanf 4 uint32s into a temporary array, then memcpy 16 bytes into
`s6_addr` — byte-for-byte identical to writing `s6_addr32[]` on glibc (a uint32 reinterpreted as 4 bytes in native byte order):

```cpp
unsigned int u32[4];
sscanf(loc_addr, "%08X%08X%08X%08X", &u32[0], &u32[1], &u32[2], &u32[3]);
memcpy(socket_info.loc6.s6_addr, u32, 16);
```

**Pre-check grep (phase zero)**: before porting a Linux application, grep for `__[a-z]+_t\b` (catching glibc internal typedefs
such as __pid_t/__uid_t/__gid_t/...) and `s6_addr32|s6_addr16` (glibc-only members) to find them all in one pass rather than
attempt by attempt.

## Notes

- Replacing `__`-prefixed typedefs with the standard names is safe in both directions (both glibc and musl have the standard
  names) — this is the preferred fix. Don't use a reverse shim like `typedef __pid_t pid_t` (musl has no `__pid_t` to source from).
- The memcpy equivalence for s6_addr32 only guarantees "the same byte layout" (matching the original behavior); it doesn't fix
  any latent byte-order display issue in the original logic — the porting goal is "unchanged behavior + it compiles", not
  changing the original algorithm.
- In musl, `pid_t`/`uid_t` come from `<sys/types.h>` (transitively included by `<pwd.h>`/`<unistd.h>` and others, but an
  explicit include is safest under the header-self-sufficiency principle).
- Don't misdiagnose: `getpwuid`/`gethostbyaddr`/`mkfifo`/`chmod`/`opendir`/`readlink`/`inet_ntoa`/`execv`/`posix_spawn` all
  **do exist** in musl (they compile; it's the sandbox that fails them at runtime) — those aren't glibc-isms, so don't change them.

## Results

| Field | Content |
|-------|---------|
| Leadership summary | Captured the reusable troubleshooting for glibc internal symbols (__pid_t/__uid_t/s6_addr32) being incompatible with musl when porting Linux → OHOS |
| Scope of impact | Every application ported from glibc/Linux to OHOS (including those using `__`-prefixed names or glibc extension members) |
| Deliverables | problem record + tcpview HAP |
| Evidence | attempt1 build.log (__pid_t/__uid_t errors) → fix → attempt2 compiles every .cpp |
| How to reuse | When you get `unknown type name '__*_t'`, switch to the standard name; when you get `no member 's6_addr32'`, switch to memcpy |

## Related

- [[procedural-qt-app-harmonyos-migration]] — Phase-zero pre-check (the grep patterns)
- [[build-fail-libuuid-missing-ohos-musl]] — Another missing musl system library from the same batch (tcpview)
- [[build-fail-qinitresource-extern-c-main]] — The linkage conflict from the same batch (tcpview)
