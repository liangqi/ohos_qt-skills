---
id: runtime-curl-chinese-garbled
type: problem
domain: runtime
tags: [curl, encoding, utf-8, git-bash, windows, gitcode-api, chinese, garbled]
created: 2026-06-10
updated: 2026-06-10
status: solved
audience: public
summary: "Chinese text in a curl API request body is garbled under Windows Git Bash (the encoding isn't UTF-8)"
severity: medium

# ====== Search keywords ======
error_message: >
  When calling an API with curl under Windows Git Bash, Chinese characters in the request body come out garbled.
  For example, "知识库" becomes "֪ʶ⽻" and "门禁" becomes "Ž".
  The API returns 200/201, but every Chinese field is mojibake.
error_code: "N/A"
keywords: [curl, garbled, mojibake, Chinese, encoding, UTF-8, Git Bash, Windows, API]
symptoms: "Chinese characters in a curl POST/PATCH request body show up garbled on the API side (e.g. Cyrillic characters like ֪ʶ⽻)"

# ====== Problem details ======
environment: "Windows 10/11 + Git Bash (MSYS2) + curl 7.x/8.x"
refs: []
related_problems: []
---

# curl mojibake with Chinese text (Windows Git Bash)

## Error message

```
# Expected: "feat: Qt for HarmonyOS 知识库完整交付 + 门禁 CI 体系"
# Actual:   "feat: Qt for HarmonyOS ֪ʶ + Ž CI ϵ"
```

The API returns 200/201 successfully, but all the Chinese in fields like title/body turns into mojibake (usually Cyrillic or Latin-1 characters).

## Root cause analysis

The Windows Git Bash terminal's default encoding is not UTF-8, so when curl's `-d` argument contains Chinese directly:

1. The shell passes the Chinese to curl in the terminal's encoding (e.g. GBK/CP936)
2. curl sends the bytes it received verbatim in the HTTP request body
3. The API decodes them as UTF-8 → mojibake

**The key point**: even with `Content-Type: application/json; charset=utf-8` set, curl does not convert the encoding — it just passes the bytes through.

## Solution

### Option A: write to a temporary file and reference it with `@file` (recommended)

Write the JSON to a temporary file (making sure the file itself is UTF-8 encoded), then have curl read the file:

```bash
# 1. Write the temporary file with a heredoc (heredoc content is written to the file as UTF-8)
cat > /tmp/pr_data.json << 'JSONEOF'
{
  "title": "feat: Qt for HarmonyOS 知识库完整交付 + 门禁 CI 体系",
  "body": "描述内容..."
}
JSONEOF

# 2. curl reads the file (the file is UTF-8, and curl sends it verbatim)
curl -s -X PATCH "https://gitcode.com/api/v5/repos/OWNER/REPO/pulls/1" \
  -H "Content-Type: application/json; charset=utf-8" \
  -H "Authorization: Bearer TOKEN" \
  -d @/tmp/pr_data.json
```

### Option B: switch the terminal encoding with `chcp 65001`

```bash
# Switch to the UTF-8 code page, then run curl
chcp 65001 >nul 2>&1
curl -s -X PATCH "URL" -H "Content-Type: application/json; charset=utf-8" \
  -d '{"title": "中文标题"}'
```

> ⚠️ Option B is unreliable in some Git Bash versions; option A is recommended.

### Option C: `printf` + a pipe

```bash
printf '{"title":"中文标题"}' | curl -s -X PATCH "URL" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d @-
```

## Additional notes on the GitCode API

| Operation | Method | Authentication | Endpoint |
|-----------|--------|----------------|----------|
| Create a PR | `POST` | `Authorization: Bearer TOKEN` | `/api/v5/repos/{owner}/{repo}/pulls` |
| Update a PR | `PATCH` (not PUT) | `Authorization: Bearer TOKEN` | `/api/v5/repos/{owner}/{repo}/pulls/{id}` |
| Auth failure | Returns `401 token not found` | Check: use the `Bearer` prefix, not `token` | — |

### GitCode API authentication format

```bash
# ✅ Correct
-H "Authorization: Bearer YOUR_TOKEN"

# ❌ Wrong (returns 401)
-H "Authorization: token YOUR_TOKEN"
```

## Troubleshooting steps

1. **Confirm where the garbling happens**: add `-v` to the curl command and check whether the request body on the `> ` lines is valid UTF-8
2. **Check the file encoding**: `file /tmp/pr_data.json` should report `UTF-8`
3. **Check the terminal encoding**: `echo $LANG` to see the current locale
4. **Verify on the API side**: check the title field in the JSON the API returns to confirm the fix

## Reusable lessons

1. **Windows + Git Bash + curl + Chinese = you must pass the JSON via a file**; don't write Chinese directly in the `-d` argument
2. **Use PATCH to update a PR on the GitCode API**; PUT isn't supported (returns 405)
3. **Use Bearer for GitCode API authentication**; the `token` prefix isn't supported (returns 401)
4. **API token safety**: once a token is exposed in a conversation or log, revoke it and regenerate immediately

## References

| Source type | Notes |
|-------------|-------|
| 🛠️ Hands-on experience | A real problem and its solution, hit while creating a GitCode PR on 2026-06-10 |
