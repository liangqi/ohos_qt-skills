---
id: problem-runtime-ohos-ime-reset-detach
type: problem
domain: runtime
tags: [ime, inputmethod, qohosinputcontext, reset, detach, pinyin, preedit, probe, hilog, imf]
created: 2026-09-12
updated: 2026-09-12
status: solved
severity: high
audience: public
refs: [fault-C-0002, fault-C-0003, problem-build-qt612-ohos-plugin-rebuild]
summary: >
  In the Qt 6.12-beta3 ohos platform plugin, QOhosInputContext::reset() detaches/attaches the input-method
  controller, which collapses the soft keyboard mid pinyin composition (handlePanelHiding), and commit() force-commits the pending
  pinyin letters, polluting the text. The fix aligns with the Android plugin's behavior: reset only finalizes the preedit and
  doesn't detach. Also captures the IMF probe troubleshooting method (IMEPROBE) and the classification of "Chinese search finds nothing"
  (the server doesn't index short Chinese words in global search; not a porting bug).
leader_summary: >
  Fixed the Detach/Attach bug in the Qt ohos plugin's IME reset + an IMF callback probe troubleshooting method + a three-way check classifying Chinese search returning no results
impact: [Input method, Platform backend, Troubleshooting methodology]
deliverables: [problem record]
evidence: []

error_message: >
  Symptoms (hilog): during composition, handlePanelHiding appears on the inputMethod side (the keyboard is collapsed),
  showTextInput fires 8+ times on the Qt side, the cursor jumps to the bottom of the edit area, and the final committed text contains pinyin letters.
  Key hilog lines: cross-compare IMEPROBE cb setPreviewText / IMEPROBE insertText raw=[...].
error_code: ""
keywords: [QOhosInputContext, reset, detach, attach, commit, preedit, setPreviewText, insertText, IMF, inputmethod_controller_capi, hilog, pinyin, Chinese input]
symptoms: "When typing pinyin in a Qt application on OHOS, the keyboard collapses midway / pinyin letters end up in the final text / the search box's query is polluted so nothing is found"
environment: "HarmonyOS PC (MateBook Pro, physical keyboard) + Qt 6.12-beta3 harmonyos kit libqohos.so + Huawei input method"
---

# The Detach/Attach bug in the Qt ohos plugin's IME reset() and the IMF probe troubleshooting method

## Symptoms

- Halfway through a pinyin composition, the system collapses the soft keyboard (inputMethod log `handlePanelHiding`);
- after a candidate is committed, the text contains pinyin letters (such as "ji极速搜索", i.e. stray "ji" before the intended Chinese words), polluting the search box's query;
- `showTextInput` fires 8+ times on the Qt side, and the cursor jumps to the bottom of the edit area.

## Root cause (Qt 6.12-beta3 `qohosinputcontext.cpp`)

The original `reset()` implementation:

```cpp
void QOhosInputContext::reset()
{
    setImConnectionState(Detached);   // ← OHOS IMF's Detach collapses the soft keyboard outright
    setImConnectionState(Attached);
}
```

Two stacked problems:

1. **Detach collapses the panel**: the semantics of OHOS IMF's `OH_InputMethodController_Detach` are more aggressive than Android's:
   detaching mid composition tears down the keyboard panel outright, interrupting candidate selection.
2. **commit pollutes the text**: `commit()` force-commits `m_pendingPreeditText` (the raw letter preview
   during pinyin composition) via `setCommitString`.

## Fix (aligned with the Qt Android plugin's behavior)

```cpp
void QOhosInputContext::reset()
{
    // Only finalize any pending preedit; don't detach/attach, keep the IMF connection and panel state
    if (!m_pendingPreeditText.isEmpty())
        commit();
}
```

Rebuild libqohos.so and deploy it by replacing the kit's copy, following
[build-qt612-ohos-plugin-rebuild](build-qt612-ohos-plugin-rebuild.md).

## The IMF probe troubleshooting method (IMEPROBE, reusable)

By default hilog doesn't print the contents of IMF callbacks, and **no text callbacks are visible in the application process's logs at all**: you must add
probes yourself. Two levels:

**① The callback entry level** (`qohosinputmethodproxy.cpp`, proving whether IMF calls back, and the argument lengths):

```cpp
// Inside the OH_TextEditorProxy_SetInsertTextFunc lambda:
qOhosPrintfDebug("IMEPROBE cb insertText len=%zu", length);
// Same for SetSetPreviewTextFunc / SetFinishTextPreviewFunc
```

**② The context level** (`qohosinputcontext.cpp`, proving string contents and flow):
add probes to reset/commit/sendInsertedTextToQt/sendInsertedPreviewTextToQt/pushTextAroundCursorToProxy,
together with a **code-point escaping helper** so hilog shows the exact content (avoiding being misled by encoding problems):

```cpp
QString imeProbeEscape(const QString &s)   // 'd' = ASCII as-is, everything else \uXXXX
```

**③ Capture and interpretation**: capture a 60-90s window with `hdc shell hilog` (collected in a Python background thread, to avoid
PowerShell distorting Chinese matches in BOM-less UTF-8), and read it in this order:

```
cb setPreviewText (during composition, pinyin letters, normal)
→ cb insertText raw=[\u6781 \u901f ...] (candidate commit; the code points should be the final Chinese)
→ pushText left=[...] (the contents of the Qt query field)
```

Measured this time: `insertText raw=[\u6781 \u901f \u641c \u7d22]` (极速搜索, "fast search") + `pushText`
consistent → **the IME commit path is clean**, ruling out the encoding/pollution hypothesis and narrowing the problem down to the application layer.

## Known unfixed problem: the first character is lost at the moment focus switches

Observed in the probe timing: at the instant focus switches (the Detach→Attach race) there was a
`previewText raw=[j]` immediately followed by `commit pending=[j]`: the first letter was committed to the old focus
object (at that moment pushText left=[] was empty; the new field hadn't been hooked up yet). It shows up as an occasional lost first character. Awaiting a fix upstream or
further local work (idea: before committing, check the focus object's ImEnabled query result).

## Appendix: how to classify "Chinese search finds nothing" (not a porting bug)

A **three-way check** used when Chinese search returned no results in a ported IM client, for reference on similar problems:

| Test | Result | Conclusion |
|------|--------|------------|
| Local conversation search for a single Chinese character | Hits conversations already joined | Local CJK indexing works |
| Remote global search for a short Chinese word | No results | See below |
| Official client (same account) searching the same word | Also no results | **The server doesn't index short Chinese words in global search; not a porting bug** |
| Latin-word query | Has results | The remote path works |

**Key point of the method**: classify an application-layer "malfunction" first by **comparing against the official client with the same account**: if the official one doesn't work either,
it's server-side/application design behavior, not a bug introduced by the port.

## Application-side log troubleshooting (general method)

Use `hdc file recv` to pull logs from the application's private directory (under `/data/app/el2/100/base/<bundle>/`;
the specific file names vary by application), and look at the application's own error codes (such as RPC Error) to tell client bugs
from server behavior (FLOOD_WAIT / PEER_ID_INVALID / USER_NOT_PARTICIPANT and so on).
