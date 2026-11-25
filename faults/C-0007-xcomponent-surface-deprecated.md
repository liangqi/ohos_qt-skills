---
id: fault-C-0007
cid: C-0007
type: cause
title: ARKUI_XCOMPONENT_TYPE_SURFACE is deprecated in API 20; the migration direction is ContentSlot
nature: limitation
domain: api
fault_type: deprecation
responsible: ohos-runtime
co_responsible: []
component: "ArkUI XComponent (SURFACE type) / ContentSlot"
severity: medium
evidence_type: docs
status: watching
evidence: "Huawei's official deprecation notice (since API 20) + the ContentSlot render-control migration guide"
evolution: "ContentSlot (the official direction): watch capability coverage, the Qt-port migration pace (T-0002), and the SURFACE removal timeline"
fix_route: ""
review_note: "ContentSlot capability coverage and the Qt-port migration pace (T-0002); the platform's removal timeline for SURFACE"
depends_on: []
affects_qt: []
affects_ohos: ["API 20+"]
qoh: []
first_seen: 2026-06-02
review_due: 2026-12-14
created: 2026-09-14
updated: 2026-09-14
tags: [harmonyos, xcomponent, contentslot, opengl, surface, deprecation, limitation, evolution]
audience: public
refs: [semantic-qt-harmonyos-platform-limits]
summary: >
  The SURFACE-type XComponent (used by Qt OHOS as the OpenGL native render surface) is deprecated since API 20;
  the official migration direction is ContentSlot. limitation/ohos-runtime (specification evolution, not a defect);
  watching: no action for applications for now (no workaround); watch ContentSlot capability coverage and the Qt-port
  migration pace (tracking ticket T-0002 / QTBUG-146622).
---

# C-0007 XComponent SURFACE deprecated in API 20

> nature: limitation | responsible: ohos-runtime | status: watching | symptoms: S-0006 | review: 2026-12-14

## Symptoms

### S-0006 SURFACE-type XComponent render surface is on the deprecation track (API 20+)

Qt OHOS's native OpenGL rendering is still based on `ARKUI_XCOMPONENT_TYPE_SURFACE`, which has been marked deprecated since
API 20 -- **it still works today**, but it is on the deprecation track, with a risk of removal in a future API.

## Root cause / classification basis

Platform specification evolution: Huawei officially marked the SURFACE-type XComponent as deprecated (since API 20) and offers
ContentSlot as the new direction for native render control (the official documentation provides a render-control migration guide).
This is a **platform limitation/evolution**, not a defect -- there is no path to "fix it back to SURFACE", only migration.

## Responsibility

`ohos-runtime` (ArkUI platform specification). The party carrying out the evolution is Qt-port (migrating to ContentSlot);
tracked on the Qt side in QTBUG-146622 (T-0002).

## Alternatives and evolution (limitation)

- **Alternative**: migrate to ContentSlot (done at the Qt framework layer; application developers need no action and get it
  when upgrading the Qt OHOS SDK) -- there is no application-side workaround for this limitation (no W);
- **Evolution**: ContentSlot (the official direction). Watch points: ① whether ContentSlot's capability coverage for OpenGL/EGL
  scenarios is complete; ② the migration progress on the qtbase harmonyos branch (T-0002); ③ the platform's actual removal timeline for
  the SURFACE type (not announced yet).

## Tickets

- **T-0002 (qt-bug, QTBUG-146622, submitted)**: Qt-side migration tracking; the ticket number comes from the official platform
  limitations page (see [qt-harmonyos-platform-limits](../semantic/qt-harmonyos-platform-limits.md)
  §ArkUI/ArkTS APIs).

## Version verification log

| Date | Environment (Qt/OHOS) | Action | Result | Status change |
|------|----------------|------|------|---------|
| 2026-06-02 | API 20 documentation | Confirmed the deprecation and migration direction (recorded with the platform-limits page) | Classification holds | → watching |

## Related

- Symptoms (S): S-0006
- Workarounds (W): none (no action at the application layer)
- Tickets (T): T-0002
- semantic: [qt-harmonyos-platform-limits](../semantic/qt-harmonyos-platform-limits.md)
