---
id: problem-build-fail-libuuid-missing-ohos-musl
type: problem
domain: build
tags: [build, ohos, musl, libuuid, uuid, cross-compile, porting, shim]
created: 2026-07-10
updated: 2026-07-10
status: solved
severity: high
audience: public
refs: [semantic-qt-harmonyos-third-party-libs, procedural-qt-app-harmonyos-migration, problem-build-fail-glibc-internal-symbols-ohos-musl]
summary: >
  The OHOS musl sysroot has no libuuid (no <uuid/uuid.h>, no -luuid). A Linux application with #include <uuid/uuid.h>
  + LIBS += -luuid fails to cross-compile for OHOS with fatal error: 'uuid/uuid.h' file not found (or a link error,
  cannot find -luuid). Preferred fix: put a drop-in shim on the OHOS build's include path (uuid_t=unsigned char[16],
  uuid_generate via QUuid::createUuid, uuid_unparse via snprintf) so the original code compiles unchanged.
leader_summary: Captured a zero-change shim for the most common missing system library (libuuid) when porting Linux applications to HarmonyOS
impact: [Migration efficiency, Build troubleshooting]
deliverables: [problem record, tcpview HAP, uuid shim]
evidence: [tcpview-ohos BUILD SUCCESSFUL, entry-default-unsigned.hap, OhosExampleApp/uuid/uuid.h]

error_message: >
  fatal error: 'uuid/uuid.h' file not found
  #include <uuid/uuid.h>
  (link-stage variant: ld.lld: error: unable to find library -luuid / cannot find -luuid)
error_code: ""
keywords: [libuuid, uuid_t, uuid_generate, uuid_unparse, uuid/uuid.h, -luuid, musl, QUuid, shim, drop-in]
symptoms: Porting a Linux Qt application to OHOS, the build can't find uuid/uuid.h or the link can't find -luuid
environment: OHOS Qt5.15.16 SDK (${QT5_15_OHOS_SDK_FULL}) + OHOS musl sysroot (aarch64-linux-ohos); tcpview (chipmunk-sm/tcpview) with LIBS += -luuid
---

# No libuuid in OHOS musl — the drop-in shim approach

## Error message

```
fatal error: 'uuid/uuid.h' file not found
   46 | #include <uuid/uuid.h>
      |          ^~~~~~~~~~~~~~~
(if the header is found, the link reports: ld.lld: error: unable to find library -luuid / cannot find -luuid)
```

## Scenario

A Linux Qt application generates unique IDs with libuuid (`#include <uuid/uuid.h>` + `LIBS += -luuid`) — tcpview's
`SocketInfo.uuid` / `uuid_generate` / `uuid_unparse` being a typical case. The OHOS musl sysroot doesn't ship libuuid,
so cross-compilation breaks immediately. In the tcpview case, batch triage identified it at the zero-stage pre-check
(the assessment marked `ohos_compatibility: maybe, replaceable by QUuid`), so the shim was in place before the first
build and the error never actually fired.

## Cause

OHOS uses musl libc and doesn't package libuuid (a BSD library from e2fsprogs that desktop glibc distributions include).
Under the musl sysroot, `usr/include/uuid/` doesn't exist and there's no corresponding `.so`.

## Solution

**Preferred: a drop-in shim (the original code is unchanged).** Put `OhosExampleApp/uuid/uuid.h` on the OHOS build's
include path and implement libuuid's three symbols using QUuid (QtCore is available in the OHOS Qt SDK):

```cpp
// OhosExampleApp/uuid/uuid.h
#include <QUuid>
#include <QByteArray>
#include <cstring>
#include <cstdio>
typedef unsigned char uuid_t[16];           // binary-compatible with libuuid
static inline void uuid_generate(uuid_t out) {
    const QByteArray rfc = QUuid::createUuid().toRfc4122(); // 16 raw bytes
    std::memcpy(out, rfc.constData(), 16);
}
static inline void uuid_unparse(const uuid_t uu, char *out) {
    const unsigned char *u = uu;
    std::snprintf(out, 37,
        "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-"
        "%02x%02x%02x%02x%02x%02x",
        u[0],u[1],u[2],u[3],u[4],u[5],u[6],u[7],
        u[8],u[9],u[10],u[11],u[12],u[13],u[14],u[15]);
}
```

Add `OhosExampleApp/` to `include_directories` in CMakeLists, and the original code's `#include <uuid/uuid.h>`
resolves to the shim (there's no system uuid.h on OHOS to take precedence). Simply don't link `-luuid` in CMake —
the `#include <uuid/uuid.h>` lines in the original datasource.h / rootmodule.h need no changes at all.

**Second choice**: replace the `uuid_t` fields and the `uuid_generate`/`uuid_unparse` calls with `QUuid` directly
(modifying the original code; only worth it when the shim is awkward for other reasons).

## Notes

- `uuid_t` must be `unsigned char[16]` (that's libuuid's definition); otherwise memset/copy of structs containing a
  `uuid_t` field will be the wrong size (as in tcpview's SocketInfo).
- `static inline` is safe across translation units (internal linkage, one copy per TU, no ODR conflict; both
  datasource.h and rootmodule.h are included by multiple .cpp files).
- `uuid_unparse` outputs 36 characters + NUL = 37 bytes, so the caller's guid buffer must be ≥ 37.
- This only covers "unique ID" semantics; if the application depends on a specific UUID version/variant, verify separately.

## Results

| Field | Content |
|-------|---------|
| Leadership summary | Captured a zero-change shim for the most common missing system library (libuuid) when porting Linux → OHOS |
| Scope of impact | Every Linux Qt application that depends on libuuid being ported to HarmonyOS |
| Deliverables | problem record + tcpview HAP + the uuid shim (OhosExampleApp/uuid/uuid.h) |
| Evidence | tcpview-ohos BUILD SUCCESSFUL + entry-default-unsigned.hap |
| How to reuse | Apply the shim directly whenever a build reports `uuid/uuid.h not found` or `cannot find -luuid` |

## Related

- [[semantic-qt-harmonyos-third-party-libs]] — Guide to porting third-party libraries to HarmonyOS
- [[procedural-qt-app-harmonyos-migration]] — The migration workflow (zero-stage pre-check)
- [[build-fail-glibc-internal-symbols-ohos-musl]] — The glibc-ism problem from the same batch
