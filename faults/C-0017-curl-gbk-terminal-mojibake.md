---
id: fault-C-0017
cid: C-0017
type: cause
title: "Inlining Chinese into curl -d in a non-UTF-8 terminal (Windows Git Bash/GBK): the shell passes bytes in the terminal encoding, curl by design passes them through unchanged, and the API decodes them as UTF-8 into mojibake"
nature: defect
domain: toolchain
fault_type: caveat
responsible: app
co_responsible: []
component: "Windows Git Bash (MSYS2) terminal encoding (GBK/CP936) × curl -d argument pass-through"
severity: medium
evidence_type: logs
status: workaround
fix_route: "Change the usage: write the Chinese JSON to a UTF-8 temporary file and reference it with curl -d @file (or switch to a UTF-8 terminal altogether)"
review_note: "Thin C page (app usage issue): unrelated to Qt/HarmonyOS (a Windows development environment toolchain problem); whether it is in scope is for the editor to confirm; the stability of option B (chcp 65001) in the Git Bash version in use can be re-evaluated"
depends_on: []
affects_qt: []
affects_ohos: []
qoh: []
first_seen: 2026-06-10
review_due: 2026-12-15
created: 2026-09-15
updated: 2026-09-15
tags: [curl, encoding, utf-8, gbk, git-bash, windows, mojibake, gitcode-api, app-usage]
audience: public
refs: [runtime-curl-chinese-garbled]
summary: >
  The Windows Git Bash terminal's default encoding is not UTF-8; when Chinese is written directly into curl -d, the shell passes
  GBK bytes, curl passes them through unchanged by design, and the API decodes them as UTF-8 into mojibake (it returns 200/201
  but the Chinese fields come out as Cyrillic/Latin-1). defect/app (Application usage issue, not framework/
  platform); W-0014 (UTF-8 file + @file reference) is adopted in practice.
---

# C-0017 Garbled Chinese in curl (the Windows Git Bash encoding pass-through chain)

> nature: defect | responsible: app | status: workaround | symptoms: S-0016 | workarounds: W-0014 | tickets: none yet | review: 2026-12-15

## Symptoms

### S-0016 curl request body Chinese text garbled under Windows Git Bash

<!-- The Chinese text in the samples below is intentional: it is the payload that gets garbled. -->

```
Expected: "feat: Qt for HarmonyOS 知识库完整交付 + 门禁 CI 体系"
Actual:   "feat: Qt for HarmonyOS ֪ʶ + Ž CI ϵ"
```

Chinese in the curl POST/PATCH request body shows up garbled on the API side (GitCode) (usually as
Cyrillic or Latin-1 characters, e.g. "知识库" (knowledge base) → "֪ʶ", "门禁" (gate) → "Ž"); the API returns
200/201 success, but all Chinese in fields such as title/body is garbled.

## Root cause / classification basis

The Windows Git Bash (MSYS2) terminal's default encoding is not UTF-8 (GBK/CP936). When curl's
`-d` argument contains Chinese directly:

1. the shell passes the Chinese to curl as bytes in the terminal encoding (GBK/CP936);
2. curl **passes the bytes through unchanged by design** -- even with
   `Content-Type: application/json; charset=utf-8` set, it doesn't convert the encoding;
3. the API side decodes them as UTF-8 → mojibake.

Classification basis: the comparison of the verbatim strings (above) + the troubleshooting steps (`curl -v` to see the actual bytes of the request body on the lines starting with `>`,
`file` to check the file encoding, `echo $LANG` to check the locale). Logs level (the verbatim error
is readable; no demo project).

## Responsibility

`app` (usage): curl passing bytes through is documented design behavior, not a defect (nothing to fix upstream);
the terminal encoding is local environment configuration; the root cause lies in the usage "inlining Chinese in a non-UTF-8 terminal",
and the fix route = change your own command usage. This entry is unrelated to both Qt and HarmonyOS (a Windows
development environment problem); its value is as a reusable lesson; the in-depth content (related GitCode API lessons such as
PATCH/Bearer) stays in
[runtime-curl-chinese-garbled](../problems/runtime-curl-chinese-garbled.md).

## Permanent fix (defect)

Change the usage (equivalent to a permanent fix): write the Chinese JSON to a UTF-8 encoded temporary file and have curl reference it with
`-d @file` (W-0014); or switch to a UTF-8 terminal environment altogether before inlining.

## Workarounds

- **W-0014 (adopted, verified in practice 2026-06-10)**: option A (recommended) -- write a
  temporary file with a heredoc and reference it with `@file`:

  ```bash
  # 1. Write the temporary file with a heredoc (the heredoc content is written to the file as UTF-8)
  cat > /tmp/pr_data.json << 'JSONEOF'
  {
    "title": "feat: Qt for HarmonyOS 知识库完整交付 + 门禁 CI 体系",
    "body": "描述内容..."
  }
  JSONEOF

  # 2. curl reads the file (the file itself is UTF-8, curl sends it unchanged)
  curl -s -X PATCH "https://gitcode.com/api/v5/repos/OWNER/REPO/pulls/1" \
    -H "Content-Type: application/json; charset=utf-8" \
    -H "Authorization: Bearer TOKEN" \
    -d @/tmp/pr_data.json
  ```

  Cost: each request needs an extra temporary-file write; the heredoc content must be UTF-8.
  Retirement condition: once the terminal environment reliably guarantees UTF-8, inline Chinese with `-d` can be used again.

  Alternatives (same root cause, no separate W): option B, switch the code page with `chcp 65001` (unstable in some
  Git Bash versions); option C, pipe with `printf | curl -d @-`.

## Tickets

None yet (a usage problem; nothing to track upstream).

## Version verification log

| Date | Environment (Qt/OHOS) | Action | Result | Status change |
|------|----------------|------|------|---------|
| 2026-09-15 | Windows 10/11 + Git Bash (MSYS2) + curl 7.x/8.x (source page: creating a GitCode PR in practice on 2026-06-10) | Transcribed when recording the problems page: option A solved it in practice; recorded as a reusable lesson (Windows + Git Bash + curl + Chinese = the JSON must be passed via a file) | Classification holds; option A works | → workaround |

## Related

- Symptoms (S): S-0016
- Workarounds (W): W-0014
- Tickets (T): none yet
- problems: [runtime-curl-chinese-garbled](../problems/runtime-curl-chinese-garbled.md)
- Related causes (C): none
