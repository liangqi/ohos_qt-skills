---
id: fault-C-0006
cid: C-0006
type: cause
title: libcxx-ohos <cmath> uses __promote but lacks #include <__math/promote.h>
nature: defect
domain: build
fault_type: bug
responsible: ohos-ndk
co_responsible: []
component: "OHOS NDK libcxx-ohos include/c++/v1/cmath (include list at lines 307-318 / __promote at line 544)"
severity: medium
evidence_type: source
status: diagnosed
fix_route: "SDK/NDK adds #include <__math/promote.h> to libcxx-ohos <cmath>"
review_note: "Whether libcxx-ohos <cmath> adds __math/promote.h (review together with C-0005)"
depends_on: []
affects_qt: []
affects_ohos: ["API 22", "API 24 Beta1 (libcxx-ohos)"]
qoh: []
first_seen: 2026-06-25
review_due: 2026-10-15
created: 2026-09-14
updated: 2026-09-14
tags: [ohos, ndk, libcxx, cmath, promote, build, bug]
audience: public
refs: [problem-build-fail-qt6-libcpp-musl-isystem, fault-C-0005]
summary: >
  libcxx-ohos's <cmath> uses __promote without #include <__math/promote.h> -- a definite defect,
  only exposed when the header search order changes and musl's <math.h> gets picked (i.e. the -isystem injection scenario of C-0005).
  defect/ohos-ndk, diagnosed (not reported); no standalone workaround; the symptom is avoided with the W-0004 combination.
---

# C-0006 libcxx-ohos cmath lacks the __math/promote.h include

> nature: defect | responsible: ohos-ndk | status: diagnosed | symptoms: S-0005 (combined with C-0005) | review: 2026-10-15

## Symptoms

### S-0005 Qt6 OHOS target build fails in a cascade (nullptr_t / __promote / hypot)

This cause contributes the `__promote` / `hypot ambiguous` part of the symptom (the `nullptr_t` part is directly determined by
the musl shadowing of [C-0005](C-0005-qt-cmake-isystem-injection.md)):

```
libcxx-ohos include/c++/v1/cmath:544:5: error: use of undeclared identifier '__promote'
libcxx-ohos include/c++/v1/cmath:552:12: error: call to 'hypot' is ambiguous
```

**Failure structure**: this cause (a libcxx-ohos header defect) stays latent on its own; only **in combination** with C-0005 (the -isystem injection
changes the header search order and picks musl's `<math.h>`) does it produce the symptom (S-0005's
cause_relation = all_of); a fix on either side clears it.

## Root cause / classification basis (source-level, confirmed)

- libcxx-ohos `<cmath>` **uses** `__promote` (line 544), but its include list
  (lines 307-318) only has `math.h`/`type_traits`/`version`/`__undef_macros` and
  **does not `#include <__math/promote.h>`** -- a definite defect in libcxx-ohos;
- with the normal include order it doesn't trigger (`__promote` is visible indirectly through other headers); it is only exposed when
  `-isystem` changes the search order and `<math.h>` resolves to the musl version;
- libcxx-ohos in both API 22 (Release 6.0.2.130) and API 24 Beta1 has this defect.

## Responsibility

`ohos-ndk` (the libcxx-ohos headers belong to the OHOS SDK/NDK). The fix ships with an SDK/NDK release.

## Permanent fix (defect)

The SDK side adds one line, `#include <__math/promote.h>`, to libcxx-ohos `<cmath>`.

## Workarounds

- No standalone fix; the symptom is mitigated via W-0004 (avoiding S-0005 by switching the build combination, see
  [C-0005](C-0005-qt-cmake-isystem-injection.md)).

## Tickets

- None yet (material in
  [build-fail-qt6-libcpp-musl-isystem](../problems/build-fail-qt6-libcpp-musl-isystem.md);
  to be filed with the OHOS SDK side per `procedural/qt-bug-report-generation.md`).

## Version verification log

| Date | Environment (Qt/OHOS) | Action | Result | Status change |
|------|----------------|------|------|---------|
| 2026-06-25 | libcxx-ohos (API 22 / API 24 Beta1) | Source review of the cmath include list | Confirmed `__math/promote.h` is missing | → diagnosed |

## Related

- Symptoms (S): S-0005 (combined with C-0005, all_of)
- Workarounds (W): no standalone workaround (comes with W-0004)
- Tickets (T): none yet
- problems: [build-fail-qt6-libcpp-musl-isystem](../problems/build-fail-qt6-libcpp-musl-isystem.md)
- Related causes (C): [C-0005](C-0005-qt-cmake-isystem-injection.md) (qt-port, combined responsibility)
