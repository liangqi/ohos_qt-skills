---
id: document-picker-uri-access
title: DocumentViewPicker URIs and access grants
status: active
confidence: 0.7
sources: [{type: experience, name: "Tauri P2P app DocumentViewPicker, on-device verification", date: 2026-08-06}]
created: 2026-08-14
updated: 2026-08-14
last_confirmed: 2026-08-06
review_by: null
superseded_by: null
tags: [document-picker, uri, fileuri, permission, fileshare, sandbox]
refs: [document-picker-uri-access-failure, application-sandbox-paths]
summary: "A picker returns a URI carrying grant semantics; the URI, the converted path, and the temporary/persistent read-write grant must each be handled separately."
audience: public
---

# DocumentViewPicker URIs and access grants

What DocumentViewPicker returns is first and foremost a URI/capability, not an ordinary absolute path you can hand unconditionally to POSIX `open`, Rust `std::fs`, or a framework file API.

## Three layers of semantics

1. **URI identity**: describes the document or directory the user selected.
2. **Path representation**: some APIs can convert the URI into a path usable by the current process.
3. **Access grant**: which read/write operations are allowed, for how long, and whether it can be persisted.

Converting a URI to a path does not automatically broaden permissions, and the grant model for picking a file cannot be inferred from the one for picking a directory (or vice versa).

## Usage flow

1. Call the picker from your ArkTS/platform adapter.
2. Keep the original URI, and handle cancellation, empty results, and multi-selection.
3. Use platform capabilities such as fileuri/fileShare, per the target API, to resolve it and request the access you need.
4. Only pass a converted path down to the native/framework layer when the backend genuinely needs a path and the platform allows it.
5. When you need cross-process access or access that survives a restart, verify persistPermission's mode, scope, and failure behavior.
6. Test read, create, overwrite, rename, delete, and subdirectory access separately.

## Security boundaries

- Don't build arbitrary paths by string-concatenating onto the URI.
- Don't treat a single user selection as permanent full access to an entire directory tree.
- When a permission request fails, fall back to a user-comprehensible re-selection flow or the application's private directory.
- Avoid logging complete user file names, directories, and URI tokens.

## Adapter boundary

This common knowledge base maintains the URI/path/grant invariant. How a Tauri dialog plugin, a Qt file dialog, a JVM `File`, or a .NET stream expresses the result stays in the framework repository, along with its original error text.
