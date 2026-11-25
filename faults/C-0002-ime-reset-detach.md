---
id: fault-C-0002
cid: C-0002
type: cause
title: QOhosInputContext::reset() Detach/Attach closes the IMF panel and commits polluted text
nature: defect
domain: input
fault_type: bug
responsible: qt-port
co_responsible: []
component: "Qt 6.12-beta3 libqohos qohosinputcontext.cpp (reset/commit)"
severity: high
evidence_type: logs
status: workaround
fix_route: "Align with the Android plugin's behavior (reset only finalizes the preedit); lands with a later Qt 6.12 OHOS kit"
review_note: "Whether the next Qt 6.12 OHOS kit includes the reset fix; verify the lost first character (C-0003) at the same time"
depends_on: []
affects_qt: ["Qt 6.12-beta3 (libqohos)"]
affects_ohos: ["HarmonyOS PC (MateBook Pro, physical keyboard + Huawei IME)"]
qoh: []
first_seen: 2026-09-12
review_due: 2026-12-14
created: 2026-09-14
updated: 2026-09-14
tags: [qt, harmonyos, ime, inputmethod, qohosinputcontext, reset, detach, preedit, pinyin, workaround, bug]
audience: public
refs: [problem-runtime-ohos-ime-reset-detach, problem-build-qt612-ohos-plugin-rebuild, fault-C-0003]
summary: >
  QOhosInputContext::reset() detaches/attaches the input method controller, which closes the soft keyboard in the middle of
  pinyin composition, and commit() force-commits the pending pinyin letters. defect/qt-port; the fix = align with the Android plugin's behavior;
  workaround W-0002 (rebuild libqohos) is verified on a real device, pending the upstream merge into the Qt6 OHOS kit.
---

# C-0002 Detach/Attach in QOhosInputContext::reset()

> nature: defect | responsible: qt-port | status: workaround | symptoms: S-0002 | review: 2026-12-14

## Symptoms

### S-0002 Pinyin composition input breaks: the keyboard closes mid-input + pinyin letters pollute the committed text

- Halfway through pinyin composition, the system closes the soft keyboard (hilog `handlePanelHiding`);
- after choosing a candidate, pinyin letters are mixed into the text (e.g. "ji极速搜索": the stray pinyin letters "ji" in front of the committed Chinese words), polluting the search box query;
- on the Qt side, `showTextInput` fires 8+ times in a row and the cursor jumps to the bottom of the edit area.

## Root cause / classification basis (source-level, confirmed)

The original implementation of `reset()` in `qohosinputcontext.cpp`:

```cpp
void QOhosInputContext::reset()
{
    setImConnectionState(Detached);   // Detach in OHOS IMF closes the keyboard panel outright
    setImConnectionState(Attached);
}
```

1. **Detach closes the panel**: the semantics of OHOS IMF's `OH_InputMethodController_Detach` are more aggressive than Android's
   -- detaching mid-composition collapses the keyboard panel outright, interrupting candidate selection;
2. **commit pollutes the text**: `commit()` force-commits `m_pendingPreeditText` (the raw letter
   preview during pinyin composition) via `setCommitString`.

## Responsibility

`qt-port` (the Qt OHOS platform plugin's behavior is not aligned with the Qt Android plugin). The fix ships with the OHOS kit of a later
Qt 6.12 beta/RC.

## Permanent fix (defect, identified, pending upstream merge)

Align with the Qt Android plugin's behavior:

```cpp
void QOhosInputContext::reset()
{
    // Only finalize the pending preedit; no detach/attach, keep the IMF connection and panel state
    if (!m_pendingPreeditText.isEmpty())
        commit();
}
```

## Workarounds

- **W-0002 (adopted, verified 2026-09-12 on a real device)**: rebuild libqohos.so per the
  [build-qt612-ohos-plugin-rebuild](../problems/build-qt612-ohos-plugin-rebuild.md)
  procedure and deploy it into the kit. Cost: every kit update requires re-applying the patch and rebuilding.
  Retirement condition: once an upstream release contains this fix, go back to the official kit and drop the local rebuild.

## Tickets

- None yet (not reported). Root cause and fix verification were completed on 2026-09-12, and the IMEPROBE probe material is complete;
  to be filed per `procedural/qt-bug-report-generation.md`; suggest combining it with
  [C-0003](C-0003-ime-focus-switch-race.md) into one set of material. For the troubleshooting methodology see
  [runtime-ohos-ime-reset-detach](../problems/runtime-ohos-ime-reset-detach.md).

## Version verification log

| Date | Environment (Qt/OHOS) | Action | Result | Status change |
|------|----------------|------|------|---------|
| 2026-09-12 | Qt 6.12-beta3 / HarmonyOS PC (MateBook Pro) | Located with IMEPROBE probes + rebuilt libqohos and replaced it in the kit | Keyboard no longer closes, text no longer polluted | → workaround |

## Related

- Symptoms (S): S-0002
- Workarounds (W): W-0002
- Tickets (T): none yet
- problems: [runtime-ohos-ime-reset-detach](../problems/runtime-ohos-ime-reset-detach.md),
  [build-qt612-ohos-plugin-rebuild](../problems/build-qt612-ohos-plugin-rebuild.md)
- Related causes (C): [C-0003](C-0003-ime-focus-switch-race.md) (same component, focus-switch race, open)
