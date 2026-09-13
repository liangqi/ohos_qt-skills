---
id: document-picker-uri-access-failure
title: "DocumentViewPicker result cannot be read or written"
status: active
confidence: 0.7
sources: [{type: experience, name: "Tauri P2P app file/directory picking, on-device verification", date: 2026-08-06}]
created: 2026-08-14
updated: 2026-08-14
last_confirmed: 2026-08-06
superseded_by: null
tags: [problem, document-picker, uri, fileuri, permission]
refs: [document-picker-uri-access]
summary: "The picker URI is treated as an ordinary path, or the converted path lacks the required read/write grant, producing not-found / permission-denied errors."
audience: public
error_message: |
  Path is neither a file nor a directory
  No such file or directory
  Permission denied
---

# DocumentViewPicker result cannot be read or written

## Symptoms and cause

- The backend passes a URI such as `file://docs/...` straight to an ordinary filesystem API and gets "does not exist".
- After converting the URI to a path, reads succeed but writes fail.
- Access that previously worked stops working after the application restarts.

The root cause is conflating three things into a single value: the URI, the path representation, and the access grant. Converting a string does not grant you read/write or persistent permission.

## Solution

1. Go back to the picker adapter and keep the original URI.
2. Resolve it using the target SDK's fileuri/fileShare APIs.
3. Request the read/write mode your feature needs, and persist it only when the platform supports that and you genuinely need it.
4. Pass the usable handle/path to the backend along with an explicit permission scope.
5. Test files, directories, cancellation, restart, permission revocation, and a deleted target separately.

## Prevention

In your IPC/bridge types, give URIs and paths distinct names and carry the access mode/lifetime alongside them; don't let a bare string implicitly stand in for a capability.
